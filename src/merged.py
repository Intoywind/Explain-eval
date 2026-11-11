"""合并评测集的计分（第七份输入第 3 节）。

python -m src.merged                     # 重算并写入 merged_scores 表（每次整表重写）

- 输入：data/items_merged.jsonl（每行的 points、zero_rule、parts）和数据库里的回答、裁判记录。
- 组 = Skill 组 × 被测模型；Skill 组：original_eval（按课程选 skills/original_eval/ 里的那份）、general_v1、general_v2。
- 每个（组、条目、第几次重复）一行，3 次重复都有行；没有成功生成的那次记为失败：卡点分、步骤分记 0，分母照算。
- 回答：短题取 data/items.jsonl 的当前回答，长题取 data/items_merged.jsonl 的当前回答（current_calls）。
- 裁判：该回答 × 该裁判 × 该版 prompt × 当前判分清单（rubric_sha256）的最新一条记录。
  ok 才计分；needs_review、没评过的 status 照记，分数为空，不进统计（报告单独列）。
- 分值：卡点答上一个得 points.gate_each 分，步骤做到一个得 points.step_each 分；answered / done 用引句校验后的值。
- 清零（knowledge_pass = 0 时）：
  - 整份清零：卡点分、步骤分都记 0。
  - 只清讲错的那一部分：which 的每一条对上 knowledge_errors 的第几条（去首尾空白后相同），查 parts.knowledge_errors 得到第几部分；
    这些部分的卡点（parts.gates）、步骤（parts.steps）记 0，parts.steps 为 null 的步骤不受影响。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .judge import ROOT, db_path_from_config, judge_model_cfg, load_items, load_prompt, rubric_hash
from .run import PER_COURSE_SKILL_DIRS, UsageError, _rel, load_config, per_course_skill_for

GROUPS = ["original_eval", "general_v1", "general_v2"]
MODELS = ["gpt-6.1-sol", "gpt-6-luna"]
REPEATS = 3
SHORT_ITEMS_FILE = "data/items.jsonl"

SCHEMA = """
CREATE TABLE IF NOT EXISTS merged_scores (
    skill_group   TEXT NOT NULL,     -- original_eval / general_v1 / general_v2
    skill_file    TEXT NOT NULL,
    model_name    TEXT NOT NULL,
    item_id       TEXT NOT NULL,
    repeat_idx    INTEGER NOT NULL,
    tier          TEXT NOT NULL,     -- 短题 / 长题
    kind          TEXT NOT NULL,     -- 短题 / 做题类 / 概念理解类
    course        TEXT NOT NULL,
    reader        TEXT NOT NULL,     -- 零基础 / 有前置
    unit          TEXT NOT NULL,     -- 一道题：去掉读者版本后缀的条目 id
    call_id       INTEGER,           -- 没有成功生成时为空
    judgment_id   INTEGER,
    status        TEXT NOT NULL,     -- ok / failed（生成失败，记 0）/ needs_review / error / unjudged
    failed        INTEGER NOT NULL,  -- 1 = 生成失败、记 0
    knowledge_pass INTEGER, incomplete INTEGER,
    gate_raw      INTEGER,           -- 清零前的卡点得分
    gate_score    INTEGER,           -- 清零后的卡点得分（计分用）
    gate_max      INTEGER NOT NULL,
    step_raw      INTEGER, step_score INTEGER, step_max INTEGER NOT NULL,
    zeroed_parts  TEXT,              -- JSON：概念理解类被清零的部分；整份清零为 "all"
    n_gaps_blocking INTEGER,
    judge_prompt_sha256 TEXT NOT NULL,
    computed_at   TEXT NOT NULL,
    PRIMARY KEY (skill_group, model_name, item_id, repeat_idx)
);
"""


def unit_of(item_id: str) -> str:
    for suf in ("-零基础", "-有前置"):
        if item_id.endswith(suf):
            return item_id[: -len(suf)]
    return item_id


def reader_of(item_id: str) -> str:
    return "零基础" if item_id.endswith("零基础") else "有前置" if item_id.endswith("有前置") else "其他"


def skill_file_for(group: str, item: dict) -> str:
    if group in PER_COURSE_SKILL_DIRS:
        return _rel(per_course_skill_for(group, item["course"]))
    return f"skills/{group}.md"


def score_response(item: dict, parsed: dict | None, knowledge_pass: int | None, failed: bool = False) -> dict:
    """一份回答的卡点分、步骤分（纯函数）。parsed 是裁判记录的 parsed_json（gate[].answered、steps[].done、knowledge_error.which）。"""
    pts = item["points"]
    gmax, smax = pts["gate_total"], pts["step_total"]
    if failed:
        return {"gate_raw": 0, "gate_score": 0, "gate_max": gmax, "step_raw": 0, "step_score": 0, "step_max": smax,
                "zeroed_parts": None, "failed": 1}
    gate = {g["question_id"]: int(bool(g["answered"])) for g in parsed["gate"]}
    steps = {s["step_id"]: int(bool(s["done"])) for s in parsed["steps"]}
    want_q = [q["id"] for q in item["gate_questions"]]
    want_s = [s["id"] for s in item["recommended_steps"]]
    if set(gate) != set(want_q) or set(steps) != set(want_s):
        raise ValueError(f"{item['id']}：裁判记录的卡点或步骤 id 和条目对不上")
    g_raw = sum(gate.values()) * pts["gate_each"]
    s_raw = sum(steps.values()) * pts["step_each"]
    out = {"gate_raw": g_raw, "gate_score": g_raw, "gate_max": gmax, "step_raw": s_raw, "step_score": s_raw,
           "step_max": smax, "zeroed_parts": None, "failed": 0}
    if knowledge_pass is None or knowledge_pass == 1:
        return out
    if item["zero_rule"] == "整份清零":
        out.update(gate_score=0, step_score=0, zeroed_parts="all")
        return out
    # 只清讲错的那一部分
    listed = [k.strip() for k in item["knowledge_errors"]]
    which = (parsed.get("knowledge_error") or {}).get("which") or []
    parts = item["parts"]
    hit = set()
    for w in which:
        w = w.strip()
        if w not in listed:
            raise ValueError(f"{item['id']}：which {w!r} 对不上知识错误清单")
        hit.add(parts["knowledge_errors"][listed.index(w)])
    if not hit:
        raise ValueError(f"{item['id']}：知识不通过但 which 为空")
    g = sum(v for q, v in gate.items() if parts["gates"][q] not in hit) * pts["gate_each"]
    s = sum(v for k, v in steps.items() if parts["steps"][k] is None or parts["steps"][k] not in hit) * pts["step_each"]
    out.update(gate_score=g, step_score=s, zeroed_parts=sorted(hit))
    return out


def compute(conn, items: dict, judge_name: str, prompt_sha: str, items_rel: str) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for grp in GROUPS:
        for m in MODELS:
            for iid, it in items.items():
                sf = skill_file_for(grp, it)
                ifile = SHORT_ITEMS_FILE if it["tier"] == "短题" else items_rel
                for rep in range(1, REPEATS + 1):
                    base = {"skill_group": grp, "skill_file": sf, "model_name": m, "item_id": iid, "repeat_idx": rep,
                            "tier": it["tier"], "kind": it["kind"], "course": it["course"], "reader": reader_of(iid),
                            "unit": unit_of(iid), "judge_prompt_sha256": prompt_sha, "computed_at": now}
                    c = conn.execute("SELECT id FROM current_calls WHERE item_id=? AND model_name=? AND skill_file=?"
                                     " AND repeat_idx=? AND items_file=?", (iid, m, sf, rep, ifile)).fetchone()
                    if c is None:
                        rows.append({**base, "call_id": None, "judgment_id": None, "status": "failed",
                                     "knowledge_pass": None, "incomplete": None, "n_gaps_blocking": None,
                                     **score_response(it, None, None, failed=True)})
                        continue
                    j = conn.execute(
                        "SELECT id, status, knowledge_pass, incomplete, n_gaps_blocking, parsed_json FROM judgments"
                        " WHERE id = (SELECT max(id) FROM judgments WHERE call_id=? AND judge_model_name=?"
                        " AND prompt_sha256=? AND rubric_sha256=?)", (c["id"], judge_name, prompt_sha, rubric_hash(it))).fetchone()
                    if j is None or j["status"] != "ok":
                        rows.append({**base, "call_id": c["id"], "judgment_id": j["id"] if j else None,
                                     "status": j["status"] if j else "unjudged", "failed": 0,
                                     "knowledge_pass": None, "incomplete": None, "n_gaps_blocking": None,
                                     "gate_raw": None, "gate_score": None, "gate_max": it["points"]["gate_total"],
                                     "step_raw": None, "step_score": None, "step_max": it["points"]["step_total"],
                                     "zeroed_parts": None})
                        continue
                    sc = score_response(it, json.loads(j["parsed_json"]), j["knowledge_pass"])
                    rows.append({**base, "call_id": c["id"], "judgment_id": j["id"], "status": "ok",
                                 "knowledge_pass": j["knowledge_pass"], "incomplete": j["incomplete"],
                                 "n_gaps_blocking": j["n_gaps_blocking"], **sc})
    return rows


def store(conn, rows: list[dict]) -> None:
    conn.executescript(SCHEMA)
    cols = ["skill_group", "skill_file", "model_name", "item_id", "repeat_idx", "tier", "kind", "course", "reader", "unit",
            "call_id", "judgment_id", "status", "failed", "knowledge_pass", "incomplete", "gate_raw", "gate_score",
            "gate_max", "step_raw", "step_score", "step_max", "zeroed_parts", "n_gaps_blocking",
            "judge_prompt_sha256", "computed_at"]
    with conn:
        conn.execute("DELETE FROM merged_scores")
        for r in rows:
            v = dict(r)
            if v["zeroed_parts"] is not None and not isinstance(v["zeroed_parts"], str):
                v["zeroed_parts"] = json.dumps(v["zeroed_parts"])
            conn.execute(f"INSERT INTO merged_scores ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                         [v[c] for c in cols])


def run(args) -> list[dict]:
    cfg = load_config(Path(args.config))
    jcfg = judge_model_cfg(cfg)
    prompt = load_prompt(Path(args.judge_prompt))
    items, items_rel = load_items(Path(args.items), False)
    conn = db.connect(db_path_from_config(cfg))
    rows = compute(conn, items, jcfg["name"], prompt.sha256, items_rel)
    store(conn, rows)
    conn.close()
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.merged", description="合并评测集计分，写入 merged_scores")
    ap.add_argument("--items", default="data/items_merged.jsonl")
    ap.add_argument("--judge-prompt", default="prompts/judge_v2.md")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    args = ap.parse_args(argv)
    try:
        rows = run(args)
    except UsageError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    from collections import Counter
    st = Counter((r["skill_group"], r["model_name"], r["status"]) for r in rows)
    print(f"merged_scores 写入 {len(rows)} 行")
    for k in sorted(st):
        print(f"  {k[0]} × {k[1]}：{k[2]} {st[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
