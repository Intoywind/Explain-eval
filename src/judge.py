"""裁判：给已入库的讲解逐项判断，由代码算三档结果。

python -m src.judge --prompt prompts/judge_v2.md                 # 评所有还没被这个裁判、这版请求评过的当前回答
python -m src.judge --prompt prompts/judge_v2.md --dry-run       # 只打印第一条完整的裁判请求，不调 API
python -m src.judge --prompt prompts/judge_v2.md --skill skills/general_v1.md --model gpt-6.1-sol --limit 5
python -m src.judge --prompt prompts/judge_v2.md --call-ids 3,40,77
python -m src.judge --known --prompt prompts/judge_v2.md         # 已知样本检查（data/known_cases.jsonl），不进统计
python -m src.judge --fixtures --prompt prompts/judge_v2.md      # 裁判验收样例（tests/judge_fixtures/），存 fixture_judgments，不进统计
python -m src.judge --repeat 30 --seed 20261111 --prompt prompts/judge_v2.md   # 稳定性检查：按课程分层抽 30 份再判一遍，存 repeat_judgments

“当前回答”见 db.current_calls：同一个（条目、被测模型、Skill 文件、第几次重复）取最新的成功记录。
断点续跑：同一份回答、同一个裁判模型、同一个裁判请求哈希（prompt、条目判分清单、参数、讲解任何一处变了都会变）
已有 ok 或 needs_review 记录就跳过（needs_review 等人工复核，不自动再判）。

证据不合格（知识错误没有对得上清单的 which 和有效引句；答上/踩中却没有有效引句）不清零、不改判，
让裁判重判同一份回答，最多 2 次；仍不合格整份标 needs_review，不计分、不进统计。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import db, providers, rules
from .run import ROOT, PER_COURSE_SKILL_DIRS, UsageError, _rel, estimate_cost, load_config
from .schema import expected_split, validate_file
from .scoring import JudgeFormatError, parse_judge_output, score

PLACEHOLDERS = ("reader_learned", "reader_not_learned", "material", "request",
                "knowledge_errors", "gate_questions", "recommended_steps", "response")
_PH_RE = re.compile(r"\{\{(\w+)\}\}")
SYSTEM_MARK = "===== SYSTEM ====="
USER_MARK = "===== USER ====="
FORMAT_RETRIES = 2   # 裁判输出格式不对、或证据不合格时，最多再判 2 次


# ---------------- prompt ----------------

@dataclass
class JudgePrompt:
    path: Path
    rel: str
    sha256: str
    system: str
    user_template: str


def load_prompt(path: Path) -> JudgePrompt:
    if not path.is_file():
        raise UsageError(f"裁判 prompt 不存在：{path}")
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    if text.count(SYSTEM_MARK) != 1 or text.count(USER_MARK) != 1:
        raise UsageError(f"{path} 里应各有一行 {SYSTEM_MARK} 和 {USER_MARK}")
    _, rest = text.split(SYSTEM_MARK, 1)
    system, user = rest.split(USER_MARK, 1)
    system, user = system.strip(), user.strip()
    found = set(_PH_RE.findall(system + user))
    if _PH_RE.search(system):
        raise UsageError(f"{path} 的 SYSTEM 段不应有占位符：{_PH_RE.findall(system)}")
    if found != set(PLACEHOLDERS):
        raise UsageError(f"{path} 的占位符应为 {sorted(PLACEHOLDERS)}，实际 {sorted(found)}")
    return JudgePrompt(path=path, rel=_rel(path), sha256=hashlib.sha256(raw).hexdigest(),
                       system=system, user_template=user)


def _bullets(xs: list[str]) -> str:
    return "\n".join(f"- {x}" for x in xs) if xs else "（无）"


def rubric_of(item: dict) -> dict:
    """发给裁判的判分清单：知识错误清单、卡点问题（只 id/text/accept）、推荐步骤（id/text）。"""
    return {
        "knowledge_errors": list(item["knowledge_errors"]),
        "gate_questions": [{"id": q["id"], "text": q["text"], "accept": q["accept"]} for q in item["gate_questions"]],
        "recommended_steps": [{"id": s["id"], "text": s["text"]} for s in item["recommended_steps"]],
    }


def rubric_hash(item: dict) -> str:
    return hashlib.sha256(db.canonical_json(rubric_of(item)).encode("utf-8")).hexdigest()


def fill_user(template: str, item: dict, response_text: str) -> str:
    rb = rubric_of(item)
    values = {
        "reader_learned": _bullets(item["reader_known"]["learned"]),
        "reader_not_learned": _bullets(item["reader_known"]["not_learned"]),
        "material": item["material"],
        "request": item["request"],
        "knowledge_errors": _bullets(rb["knowledge_errors"]),
        "gate_questions": "\n".join(f"- id: {q['id']}\n  问题：{q['text']}\n  accept：{q['accept']}"
                                    for q in rb["gate_questions"]),
        "recommended_steps": "\n".join(f"- id: {s['id']}\n  步骤：{s['text']}" for s in rb["recommended_steps"]),
        "response": response_text,
    }
    # 一次替换完，讲解里即使出现 {{...}} 也不会被再次替换
    return _PH_RE.sub(lambda m: values[m.group(1)], template)


def forbidden_texts(item: dict, cfg: dict) -> list[str]:
    """裁判不能拿到的信息：Skill 名、被测模型名、条目 source/subtype、卡点问题的出处。"""
    out = [item["source"], item["subtype"]]
    for q in item["gate_questions"]:
        out += [q.get("source_ref", ""), q.get("source_quote", "")]
    for m in cfg.get("models") or []:
        out += [m.get("name", ""), m.get("model_id", "")]
    out += ["general_v1", *(f"skills/{d}" for d in PER_COURSE_SKILL_DIRS)]
    for d in PER_COURSE_SKILL_DIRS:
        out += [p.stem for p in (ROOT / "skills" / d).glob("*.md")]
    return [t for t in out if isinstance(t, str) and len(t.strip()) >= 4]


def check_no_leak(item: dict, cfg: dict, user: str, response_text: str) -> None:
    # 讲解本身是被评对象，不在检查范围；只查我们拼进去的部分
    outside = user.replace(response_text, "", 1)
    leaked = [t for t in forbidden_texts(item, cfg) if t in outside]
    if leaked:
        raise UsageError(f"条目 {item['id']} 的裁判请求里出现了不该给裁判的信息：{leaked[0][:60]!r}")


# ---------------- 输入 ----------------

def load_items(path: Path, holdout: bool) -> tuple[dict, str]:
    if expected_split(path) == "holdout" and not holdout:
        raise UsageError(f"{path} 是保留集（holdout），默认不读。确实要用，请显式加 --holdout")
    if not path.is_file():
        raise UsageError(f"条目文件不存在：{path}")
    items, errors = validate_file(path)
    if errors:
        raise UsageError(f"{path} 校验未通过（{len(errors)} 处错误），先运行 python -m src.schema {path}")
    return {it["id"]: it for it in items}, _rel(path)


def db_path_from_config(cfg: dict) -> Path:
    p = Path((cfg.get("defaults") or {}).get("db_path") or "results/eval.db")
    return p if p.is_absolute() else ROOT / p


def judge_model_cfg(cfg: dict) -> dict:
    j = cfg.get("judge")
    if not j:
        raise UsageError("config.yaml 里没有 judge: 配置")
    for k in ("name", "provider", "model_id"):
        if not j.get(k):
            raise UsageError(f"config.yaml 的 judge 缺少 {k}")
    if j["provider"] not in cfg["providers"]:
        raise UsageError(f"judge 的接口 {j['provider']!r} 没有在 providers 里配置")
    return j


def skill_filter_sql(skill_arg: str) -> tuple[str, list]:
    if skill_arg in PER_COURSE_SKILL_DIRS:
        return "skill_file LIKE ?", [f"skills/{skill_arg}/%"]
    return "skill_file = ?", [_rel(Path(skill_arg))]


def select_calls(conn, args) -> list:
    where, params = ["1=1"], []
    if args.skill:
        w, p = skill_filter_sql(args.skill)
        where.append(w)
        params += p
    if args.model:
        where.append("model_name = ?")
        params.append(args.model)
    if args.call_ids:
        ids = [int(x) for x in args.call_ids.split(",") if x.strip()]
        where.append(f"id IN ({','.join('?' * len(ids))})")
        params += ids
    rows = conn.execute(
        f"SELECT id, item_id, model_name, skill_file, repeat_idx, response_text FROM current_calls"
        f" WHERE {' AND '.join(where)} ORDER BY id", params).fetchall()
    return rows


# ---------------- 调用裁判 ----------------

@dataclass
class JudgeResult:
    status: str                  # ok / error / needs_review
    raw: str | None              # 最后一次的原始输出
    parsed: object | None        # ok 和 needs_review 时是最后一次的解析结果
    error: str | None            # error：失败原因；needs_review：不合格的原因
    attempts: int                # 一共调用了几次（含网络重试）
    input_tokens: int
    output_tokens: int
    latency_s: float
    last: providers.CallOutcome | None
    history: list = None         # 每次重判的原因：[{"kind": "format"/"evidence", "reasons": [...]}]

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def n_rejudge(self) -> int:
        return len(self.history or [])


def run_judge(jcfg: dict, cfg: dict, system: str, user: str, item: dict, response_text: str,
              log=print) -> JudgeResult:
    """调用裁判并解析。下面两种情况让裁判重判同一份回答，最多 FORMAT_RETRIES 次：
    - 格式不对（不是 JSON、缺字段、id 对不上、被截断）：仍不对记 error；
    - 证据不合格（scoring.evidence_problems）：仍不合格记 needs_review，不计分。
    网络类重试在 providers.call 里另算。"""
    tin = tout = 0
    lat = 0.0
    attempts = 0
    last = None
    raw = None
    history: list = []
    kind, reasons, parsed = None, [], None
    for k in range(FORMAT_RETRIES + 1):
        out = providers.call(jcfg, cfg, system, user, log=log)
        last = out
        attempts += out.attempts or 1
        tin += out.input_tokens or 0
        tout += out.output_tokens or 0
        lat += out.latency_s or 0.0
        if not out.ok:
            return JudgeResult("error", raw, None, out.error, attempts, tin, tout, lat, last, history)
        raw = out.text
        parsed = None
        if out.finish_reason == "length":
            kind, reasons = "format", ["裁判输出因长度上限被截断"]
        else:
            try:
                parsed = parse_judge_output(raw, item, response_text)
            except JudgeFormatError as e:
                kind, reasons = "format", [f"裁判输出格式不对：{e}"]
            else:
                if not parsed.problems:
                    return JudgeResult("ok", raw, parsed, None, attempts, tin, tout, lat, last, history)
                kind, reasons = "evidence", list(parsed.problems)
        if k < FORMAT_RETRIES:
            history.append({"kind": kind, "reasons": reasons})
            log(f"    {'证据不合格' if kind == 'evidence' else '格式不对'}：{'；'.join(reasons)[:300]}；"
                f"重判（第 {k + 1}/{FORMAT_RETRIES} 次）")
    msg = "；".join(reasons) + f"（已重判 {FORMAT_RETRIES} 次）"
    if kind == "evidence":
        return JudgeResult("needs_review", raw, parsed, msg, attempts, tin, tout, lat, last, history)
    return JudgeResult("error", raw, None, msg, attempts, tin, tout, lat, last, history)


def parsed_rows(p) -> dict:
    """把 Parsed 拆成逐项表的行。"""
    return {
        "gate": [{"question_id": g.id, "answered_raw": int(g.answered_raw), "answered": int(g.answered),
                  "quote_invalid": int(g.quote_invalid), "quotes": g.quotes, "quotes_valid": g.quotes_valid,
                  "reason": g.reason} for g in p.gate],
        "steps": [{"step_id": s.id, "done_raw": int(s.done_raw), "done": int(s.done),
                   "quote_invalid": int(s.quote_invalid), "quotes": s.quotes, "quotes_valid": s.quotes_valid,
                   "reason": s.reason} for s in p.steps],
        "extra_steps": [{"quote": x["quote"], "what": x["what"], "quote_valid": int(x["quote_valid"])}
                        for x in p.extra_steps],
        "gaps": [{"quote": x["quote"], "subtype": x["subtype"], "severity": x["severity"], "why": x["why"],
                  "quote_valid": int(x["quote_valid"])} for x in p.gaps],
        "redundancy": [{"quote": x["quote"], "what": x["what"], "quote_valid": int(x["quote_valid"])}
                       for x in p.redundancy],
    }


def parsed_json(p) -> dict:
    """解析结果（裁判原 JSON + 每条引句的校验结果 + 校验后的判断）。"""
    rows = parsed_rows(p)
    return {
        "knowledge_error": {**p.data["knowledge_error"], "quotes_valid": p.knowledge_quotes_valid},
        "incomplete": p.data["incomplete"],
        "gate": rows["gate"], "steps": rows["steps"],
        "extra_steps": rows["extra_steps"], "gaps": rows["gaps"], "redundancy": rows["redundancy"],
    }


# ---------------- 主流程 ----------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args(argv):
    ap = argparse.ArgumentParser(prog="python -m src.judge", description="给已入库的讲解评分")
    ap.add_argument("--prompt", required=True, help="裁判 prompt 文件，例如 prompts/judge_v2.md")
    ap.add_argument("--items", default="data/items.jsonl", help="评分用的条目文件，默认 data/items.jsonl")
    ap.add_argument("--holdout", action="store_true", help="允许读取保留集")
    ap.add_argument("--skill", help="只评这份 Skill 的回答（文件路径，或 original / original_eval）")
    ap.add_argument("--model", help="只评这个被测模型的回答（config 里的模型名）")
    ap.add_argument("--call-ids", help="只评这些回答（calls.id，逗号分隔）")
    ap.add_argument("--limit", type=int, help="最多评几份（跳过的不算）")
    ap.add_argument("--workers", type=int, default=4, help="并发数，默认 4；限速仍按 config")
    ap.add_argument("--known", action="store_true", help="已知样本检查：评 data/known_cases.jsonl，不进统计")
    ap.add_argument("--fixtures", action="store_true",
                    help="裁判验收样例：评 tests/judge_fixtures/manifest.json 里的样例，结果存 fixture_judgments 表，不进统计")
    ap.add_argument("--repeat", type=int, metavar="N",
                    help="稳定性检查：从第一遍 ok 的当前回答里按课程分层随机抽 N 份，再判一遍，存 repeat_judgments，不进统计")
    ap.add_argument("--seed", type=int, default=20261111, help="--repeat 抽样的随机种子，默认 20261111")
    ap.add_argument("--dry-run", action="store_true", help="只打印第一条完整的裁判请求，不调 API")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    return ap.parse_args(argv)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)
    try:
        return _main(args, argv)
    except UsageError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2


def _main(args, argv) -> int:
    cfg = load_config(Path(args.config))
    jcfg = judge_model_cfg(cfg)
    prompt = load_prompt(Path(args.prompt))
    items_by_id, items_rel = load_items(Path(args.items), args.holdout)
    params = providers.build_params(jcfg, cfg)
    db_path = db_path_from_config(cfg)

    if args.known:
        return _main_known(args, argv, cfg, jcfg, prompt, items_by_id, params, db_path)
    if args.fixtures:
        return _main_fixtures(args, argv, cfg, jcfg, prompt, items_by_id, params, db_path)
    if args.repeat:
        return _main_repeat(args, argv, cfg, jcfg, prompt, items_by_id, params, db_path)

    # 选回答。dry-run 只读打开，不建表不写库
    if args.dry_run:
        conn = db.connect_readonly(db_path)
        if conn is None:
            raise UsageError(f"{_rel(db_path)} 不存在或尚未升级")
        try:
            conn.execute("SELECT 1 FROM current_calls LIMIT 1")
        except Exception:
            conn.close()
            conn = db.connect(db_path)  # 还没有 current_calls 视图：建一次（只加表和视图，不改已有数据）
    else:
        conn = db.connect(db_path)
    rows = select_calls(conn, args)
    not_in_items = sorted({r["item_id"] for r in rows if r["item_id"] not in items_by_id})
    rows = [r for r in rows if r["item_id"] in items_by_id]

    todo, n_skip = [], 0
    for r in rows:
        item = items_by_id[r["item_id"]]
        user = fill_user(prompt.user_template, item, r["response_text"])
        check_no_leak(item, cfg, user, r["response_text"])
        req_hash = db.request_hash(prompt.system, user, params)
        if _has_judgment_safe(conn, r["id"], jcfg["name"], req_hash):
            n_skip += 1
            continue
        todo.append((r, item, user, req_hash))
    if args.limit is not None:
        todo = todo[:args.limit]

    if args.dry_run:
        _print_dry_run(prompt, jcfg, params, rows, todo, n_skip, not_in_items)
        conn.close()
        return 0

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    try:
        providers.require_key(jcfg["provider"], cfg)
    except RuntimeError as e:
        raise UsageError(str(e))

    n_rules = rules.update_all(conn, items_by_id, items_rel)
    run_id = "J" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)
    db.start_judge_run(conn, {"judge_run_id": run_id, "started_at": _now(),
                              "argv": ["python", "-m", "src.judge", *argv], "judge_model_name": jcfg["name"],
                              "prompt_file": prompt.rel, "prompt_sha256": prompt.sha256, "purpose": "main"})
    print(f"judge_run_id {run_id}｜裁判 {jcfg['name']}（{jcfg['provider']}）｜prompt {prompt.rel}（{prompt.sha256[:12]}）"
          f"｜待评 {len(todo)} 份，跳过 {n_skip} 份｜参数 {params}｜规则检查已更新 {n_rules} 份")
    if not_in_items:
        print(f"注意：这些条目不在 {items_rel} 里，它们的回答不评：{not_in_items}")

    n_ok = n_fail = n_review = 0
    tin = tout = 0
    n_rejudge = {"format": 0, "evidence": 0}

    def work(t):
        r, item, user, _ = t
        return run_judge(jcfg, cfg, prompt.system, user, item, r["response_text"],
                         log=lambda m, iid=item["id"]: print(f"  [{iid} call {r['id']}] {m.strip()}"))

    try:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            futs = {ex.submit(work, t): t for t in todo}
            for k, fut in enumerate(as_completed(futs), 1):
                r, item, user, req_hash = futs[fut]
                res = fut.result()
                tin += res.input_tokens
                tout += res.output_tokens
                row = {
                    "judge_run_id": run_id, "call_id": r["id"], "item_id": item["id"],
                    "judge_model_name": jcfg["name"], "judge_provider": jcfg["provider"],
                    "judge_model_id": jcfg["model_id"],
                    "judge_model_version": res.last.model_version if res.last else None,
                    "prompt_file": prompt.rel, "prompt_sha256": prompt.sha256,
                    "rubric_sha256": rubric_hash(item),
                    "request_sha256": db.request_hash(prompt.system, user,
                                                      res.last.params_sent if res.last else params),
                    "user_message": user,
                    "params_used": {"sent": res.last.params_sent if res.last else params,
                                    "reported_by_api": res.last.params_reported if res.last else None},
                    "raw_output": res.raw,
                    "finish_reason": res.last.finish_reason if res.last else None,
                    "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
                    "usage_raw": res.last.usage_raw if res.last else None,
                    "latency_s": res.latency_s, "attempts": res.attempts, "created_at": _now(),
                }
                head = f"[{k}/{len(todo)}] call {r['id']} {item['id']} 第{r['repeat_idx']}次"
                for h in res.history or []:
                    n_rejudge[h["kind"]] += 1
                rj = f"｜重判 {res.n_rejudge} 次" if res.n_rejudge else ""
                if res.ok:
                    p = res.parsed
                    sc = score(p)
                    fl = {**p.flags(), "rejudge_history": res.history or []}
                    row.update({
                        "parsed_json": parsed_json(p), "flags": fl,
                        "knowledge_pass": int(sc.knowledge_pass), "incomplete": int(sc.incomplete),
                        "incomplete_missing": p.incomplete_missing,
                        "gate_num": sc.gate_num, "gate_den": sc.gate_den,
                        "step_num": sc.step_num, "step_den": sc.step_den, "gate_all": int(sc.gate_all),
                        "n_gaps": len(p.gaps), "n_gaps_blocking": sc.n_gaps_blocking,
                        "n_redundancy": sc.n_redundancy, "n_extra_steps": len(p.extra_steps),
                        "status": "ok", "error": None,
                    })
                    rows_ = parsed_rows(p)
                    db.insert_judgment(conn, row, rows_["gate"], rows_["steps"], rows_["extra_steps"],
                                       rows_["gaps"], rows_["redundancy"])
                    n_ok += 1
                    print(f"{head} 成功｜知识{'通过' if sc.knowledge_pass else '不通过'}"
                          f"{'｜没答全' if sc.incomplete else ''}｜卡点 {sc.gate_num}/{sc.gate_den}"
                          f"｜步骤 {sc.step_num}/{sc.step_den}{rj}"
                          f"｜作废引句 {sum(fl['invalid_quotes'].values())} 条（gaps 等非计分项）"
                          f"｜{res.input_tokens}+{res.output_tokens} tokens")
                elif res.status == "needs_review":
                    # 只存原始输出、解析结果和不合格原因；不算三档分，不写逐项表，不进统计
                    p = res.parsed
                    row.update({"parsed_json": parsed_json(p),
                                "flags": {**p.flags(), "rejudge_history": res.history or []},
                                "status": "needs_review", "error": res.error})
                    db.insert_judgment(conn, row, [], [], [], [], [])
                    n_review += 1
                    print(f"{head} 待复核（needs_review）｜{res.error}")
                else:
                    row.update({"status": "error", "error": res.error,
                                "flags": {"rejudge_history": res.history or []}})
                    db.insert_judgment(conn, row, [], [], [], [], [])
                    n_fail += 1
                    print(f"{head} 失败｜{res.error}")
    except KeyboardInterrupt:
        print("\n已中断；已完成的裁判记录都已写入数据库，再次运行会跳过它们。")
    finally:
        db.finish_judge_run(conn, run_id, finished_at=_now(), n_ok=n_ok, n_failed=n_fail, n_skipped=n_skip,
                            n_needs_review=n_review, input_tokens=tin, output_tokens=tout)
        conn.close()

    cost = estimate_cost(jcfg, tin, tout)
    print("-" * 72)
    print(f"成功 {n_ok} 份，失败 {n_fail} 份，待复核（needs_review）{n_review} 份，跳过 {n_skip} 份"
          f"｜重判：证据不合格 {n_rejudge['evidence']} 次，格式不对 {n_rejudge['format']} 次")
    print(f"总用量：输入 {tin} tokens，输出 {tout} tokens｜费用 "
          + (f"约 ${cost:.4f}（按标价，未计缓存折扣）" if cost is not None else "未估算"))
    return 0 if n_fail == 0 and n_review == 0 else 1


def _has_judgment_safe(conn, call_id, judge_name, req_hash) -> bool:
    try:
        return db.has_judgment(conn, call_id, judge_name, req_hash)
    except Exception:   # 只读库里还没有 judgments 表
        return False


def _print_dry_run(prompt, jcfg, params, rows, todo, n_skip, not_in_items) -> None:
    bar = "=" * 72
    print(bar)
    print(f"裁判：{jcfg['name']}（{jcfg['provider']}，model_id {jcfg['model_id']}）｜参数 {params}")
    print(f"prompt：{prompt.rel}（sha256 {prompt.sha256[:12]}）")
    print(f"符合条件的回答 {len(rows)} 份：将跳过 {n_skip} 份（已评过），将评 {len(todo)} 份")
    if not_in_items:
        print(f"不在条目文件里、不评：{not_in_items}")
    if not todo:
        print("没有需要评的回答。")
        return
    r, item, user, req_hash = todo[0]
    print(f"第一条：call {r['id']}｜{item['id']}｜请求哈希 {req_hash[:12]}")
    print(bar)
    print("[system]")
    print(prompt.system)
    print(bar)
    print("[user]")
    print(user)
    print(bar)
    print(f"泄漏检查：{len(rows)} 份请求里都没有 Skill 名、被测模型名、条目 source/subtype、卡点问题出处")
    print("dry-run：未调用 API，未写数据库。")


# ---------------- 已知样本检查 ----------------

def _main_known(args, argv, cfg, jcfg, prompt, items_by_id, params, db_path) -> int:
    path = ROOT / "data" / "known_cases.jsonl"
    if not path.is_file():
        print(f"{_rel(path)} 不存在，跳过已知样本检查。")
        return 0
    cases = []
    for ln, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            c = json.loads(line)
        except json.JSONDecodeError as e:
            raise UsageError(f"{_rel(path)}:{ln} 不是合法 JSON：{e}")
        for k in ("item_id", "text", "expected_missing"):
            if k not in c:
                raise UsageError(f"{_rel(path)}:{ln} 缺少 {k}")
        if c["item_id"] not in items_by_id:
            raise UsageError(f"{_rel(path)}:{ln} 的 item_id {c['item_id']!r} 不在条目文件里")
        cases.append((ln, c))
    built = []
    for ln, c in cases:
        item = items_by_id[c["item_id"]]
        user = fill_user(prompt.user_template, item, c["text"])
        check_no_leak(item, cfg, user, c["text"])
        built.append((ln, c, item, user))
    if args.dry_run:
        ln, c, item, user = built[0]
        print(f"已知样本 {len(built)} 条；第一条（第 {ln} 行，{item['id']}）的裁判请求：")
        print("[system]\n" + prompt.system + "\n[user]\n" + user)
        return 0

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    providers.require_key(jcfg["provider"], cfg)
    conn = db.connect(db_path)
    run_id = "K" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)
    n_mismatch = 0
    for ln, c, item, user in built:
        res = run_judge(jcfg, cfg, prompt.system, user, item, c["text"])
        exp = sorted(c["expected_missing"])
        row = {"judge_run_id": run_id, "case_idx": ln, "item_id": item["id"],
               "text_sha256": hashlib.sha256(c["text"].encode("utf-8")).hexdigest(), "note": c.get("note"),
               "judge_model_name": jcfg["name"], "judge_model_version": res.last.model_version if res.last else None,
               "prompt_sha256": prompt.sha256, "rubric_sha256": rubric_hash(item),
               "params_used": {"sent": res.last.params_sent if res.last else params,
                               "reported_by_api": res.last.params_reported if res.last else None},
               "raw_output": res.raw, "expected_missing": exp,
               "input_tokens": res.input_tokens, "output_tokens": res.output_tokens, "created_at": _now()}
        if res.status == "needs_review":
            row.update({"parsed_json": parsed_json(res.parsed), "flags": res.parsed.flags(),
                        "status": "needs_review", "error": res.error})
            print(f"第 {ln} 行 {item['id']}｜待复核（needs_review）：{res.error}")
        elif res.ok:
            act = sorted(g.id for g in res.parsed.gate if not g.answered)
            row.update({"parsed_json": parsed_json(res.parsed), "flags": res.parsed.flags(),
                        "actual_missing": act, "status": "ok", "error": None})
            same = act == exp
            n_mismatch += not same
            print(f"第 {ln} 行 {item['id']}｜预期没答上 {exp or '无'}｜实际没答上 {act or '无'}｜{'一致' if same else '不一致'}"
                  f"{'｜知识不通过' if res.parsed.knowledge_found else ''}")
        else:
            row.update({"status": "error", "error": res.error})
            print(f"第 {ln} 行 {item['id']}｜裁判失败：{res.error}")
        db.insert_known(conn, row)
    conn.close()
    print(f"已知样本 {len(built)} 条，不一致 {n_mismatch} 条（这些记录存在 known_judgments 表，不进入任何统计）")
    return 0


# ---------------- 稳定性检查（第二遍） ----------------

def stratified_sample(pool: list[dict], n: int, seed: int) -> list[dict]:
    """按课程分层：n 份平均分给各课程（课程按名字排序，余数给排在前面的课程）；
    每门课程内，先按 call_id 排序，再用 random.Random(seed) 抽。同一个池子、同一个种子，结果固定。"""
    import random
    by_course: dict[str, list[dict]] = {}
    for r in sorted(pool, key=lambda r: r["call_id"]):
        by_course.setdefault(r["course"], []).append(r)
    courses = sorted(by_course)
    rng = random.Random(seed)
    out = []
    for k, c in enumerate(courses):
        want = n // len(courses) + (1 if k < n % len(courses) else 0)
        if want > len(by_course[c]):
            raise UsageError(f"课程 {c} 只有 {len(by_course[c])} 份可抽，不够 {want} 份")
        out += rng.sample(by_course[c], want)
    return sorted(out, key=lambda r: r["call_id"])


def _main_repeat(args, argv, cfg, jcfg, prompt, items_by_id, params, db_path) -> int:
    conn = db.connect(db_path)
    pool = []
    for r in conn.execute("SELECT id, item_id, model_name, skill_file, repeat_idx, response_text FROM current_calls"
                          " ORDER BY id").fetchall():
        item = items_by_id.get(r["item_id"])
        if item is None:
            continue
        j = conn.execute(
            "SELECT id, status FROM judgments WHERE id = (SELECT max(id) FROM judgments WHERE call_id=? AND"
            " judge_model_name=? AND prompt_sha256=? AND rubric_sha256=? AND status IN ('ok','needs_review'))",
            (r["id"], jcfg["name"], prompt.sha256, rubric_hash(item))).fetchone()
        if j is None or j["status"] != "ok":   # 第一遍待复核或没评过的不抽
            continue
        pool.append({"call_id": r["id"], "row": r, "item": item, "course": item["course"], "first_id": j["id"]})
    sample = stratified_sample(pool, args.repeat, args.seed)
    todo, n_skip = [], 0
    for s_ in sample:
        user = fill_user(prompt.user_template, s_["item"], s_["row"]["response_text"])
        check_no_leak(s_["item"], cfg, user, s_["row"]["response_text"])
        req = db.request_hash(prompt.system, user, params)
        if db.has_repeat(conn, s_["call_id"], jcfg["name"], req, args.seed):
            n_skip += 1
            continue
        todo.append((s_, user))
    courses = sorted({s_["course"] for s_ in sample})
    print(f"可抽 {len(pool)} 份（第一遍 ok）｜种子 {args.seed}｜抽中 {len(sample)} 份："
          + "，".join(f"{c} {sum(s_['course'] == c for s_ in sample)}" for c in courses)
          + f"｜待评 {len(todo)}，已评过跳过 {n_skip}")
    print("抽中的 call_id：" + ",".join(str(s_["call_id"]) for s_ in sample))
    if args.dry_run:
        conn.close()
        return 0

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    providers.require_key(jcfg["provider"], cfg)
    run_id = "R" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)
    db.start_judge_run(conn, {"judge_run_id": run_id, "started_at": _now(),
                              "argv": ["python", "-m", "src.judge", *argv], "judge_model_name": jcfg["name"],
                              "prompt_file": prompt.rel, "prompt_sha256": prompt.sha256, "purpose": "repeat"})
    print(f"judge_run_id {run_id}｜结果存 repeat_judgments，不进统计")

    def work(t):
        s_, user = t
        return run_judge(jcfg, cfg, prompt.system, user, s_["item"], s_["row"]["response_text"],
                         log=lambda m, cid=s_["call_id"]: print(f"  [call {cid}] {m.strip()}"))

    n_ok = n_fail = n_review = tin = tout = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(work, t): t for t in todo}
        for k, fut in enumerate(as_completed(futs), 1):
            s_, user = futs[fut]
            res = fut.result()
            tin += res.input_tokens
            tout += res.output_tokens
            item = s_["item"]
            row = {"judge_run_id": run_id, "first_judgment_id": s_["first_id"], "call_id": s_["call_id"],
                   "item_id": item["id"], "course": s_["course"], "sample_seed": args.seed,
                   "judge_model_name": jcfg["name"],
                   "judge_model_version": res.last.model_version if res.last else None,
                   "prompt_file": prompt.rel, "prompt_sha256": prompt.sha256, "rubric_sha256": rubric_hash(item),
                   "request_sha256": db.request_hash(prompt.system, user, res.last.params_sent if res.last else params),
                   "params_used": {"sent": res.last.params_sent if res.last else params,
                                   "reported_by_api": res.last.params_reported if res.last else None},
                   "raw_output": res.raw, "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
                   "usage_raw": res.last.usage_raw if res.last else None, "latency_s": res.latency_s,
                   "attempts": res.attempts, "created_at": _now(), "status": res.status, "error": res.error}
            if res.parsed is not None:
                row.update({"parsed_json": parsed_json(res.parsed),
                            "flags": {**res.parsed.flags(), "rejudge_history": res.history or []}})
            else:
                row["flags"] = {"rejudge_history": res.history or []}
            if res.ok:
                sc = score(res.parsed)
                row.update({"knowledge_pass": int(sc.knowledge_pass), "incomplete": int(sc.incomplete),
                            "gate_num": sc.gate_num, "gate_den": sc.gate_den, "step_num": sc.step_num,
                            "step_den": sc.step_den, "gate_all": int(sc.gate_all)})
                n_ok += 1
            elif res.status == "needs_review":
                n_review += 1
            else:
                n_fail += 1
            db.insert_repeat(conn, row)
            print(f"[{k}/{len(todo)}] call {s_['call_id']} {item['id']} {res.status}"
                  + (f"｜重判 {res.n_rejudge} 次" if res.n_rejudge else "") + (f"｜{res.error}" if res.error else ""))
    db.finish_judge_run(conn, run_id, finished_at=_now(), n_ok=n_ok, n_failed=n_fail, n_skipped=n_skip,
                        n_needs_review=n_review, input_tokens=tin, output_tokens=tout)
    conn.close()
    cost = estimate_cost(jcfg, tin, tout)
    print("-" * 72)
    print(f"成功 {n_ok}，失败 {n_fail}，待复核 {n_review}，跳过 {n_skip}｜输入 {tin}，输出 {tout} tokens｜费用 "
          + (f"约 ${cost:.4f}（按标价）" if cost is not None else "未估算"))
    return 0 if n_fail == 0 and n_review == 0 else 1


# ---------------- 裁判验收样例 ----------------

FIXTURE_DIR = ROOT / "tests" / "judge_fixtures"


def check_fixture(expect: dict, parsed, status: str) -> tuple[dict, bool | None]:
    """按 manifest 的 expect 逐项取实际值并比较。返回（实际值，是否全部符合）；没有解析结果时返回 None。
    needs_review 的结果也照样比较（它有解析结果），但调用方要单独标出来。"""
    if parsed is None:
        return {}, None
    act, ok = {}, True
    if "knowledge_found" in expect:
        act["knowledge_found"] = parsed.knowledge_found
        ok &= parsed.knowledge_found == expect["knowledge_found"]
    if "which" in expect:
        act["which"] = parsed.knowledge_which
        ok &= sorted(w.strip() for w in parsed.knowledge_which) == sorted(expect["which"])
    if "quote_contains" in expect:
        qs = [q for q, v in zip(parsed.data["knowledge_error"].get("quotes") or [], parsed.knowledge_quotes_valid) if v]
        act["valid_quotes"] = qs
        ok &= any(expect["quote_contains"] in q for q in qs)
    if "gate" in expect:
        g = next(g for g in parsed.gate if g.id == expect["gate"])
        act[f"{g.id}.answered"] = g.answered
        ok &= g.answered == expect["answered"]
    if "step" in expect:
        st = next(x for x in parsed.steps if x.id == expect["step"])
        act[f"{st.id}.done"] = st.done
        ok &= st.done == expect["done"]
    if "incomplete" in expect:
        act["incomplete"] = parsed.incomplete_found
        ok &= parsed.incomplete_found == expect["incomplete"]
    if "missing_contains" in expect:
        act["incomplete.missing"] = parsed.incomplete_missing
        ok &= any(expect["missing_contains"] in m for m in parsed.incomplete_missing)
    if "zeroed" in expect:
        if status == "ok":
            sc = score(parsed)
            zeroed = not sc.knowledge_pass and sc.gate_num == 0 and sc.step_num == 0
            act["zeroed"] = zeroed
            act["scores"] = f"卡点 {sc.gate_num}/{sc.gate_den}，步骤 {sc.step_num}/{sc.step_den}"
            ok &= zeroed == expect["zeroed"]
        else:
            act["zeroed"] = None
            ok = False
    return act, bool(ok)


def _main_fixtures(args, argv, cfg, jcfg, prompt, items_by_id, params, db_path) -> int:
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    built = []
    for fx in manifest:
        text = (FIXTURE_DIR / fx["text_file"]).read_text(encoding="utf-8")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != fx["text_sha256"]:
            raise UsageError(f"{fx['text_file']} 与 manifest 的 sha256 不一致，请先重新生成样例")
        item = items_by_id.get(fx["item_id"])
        if item is None:
            raise UsageError(f"样例 {fx['id']} 的条目 {fx['item_id']} 不在条目文件里")
        user = fill_user(prompt.user_template, item, text)
        check_no_leak(item, cfg, user, text)
        built.append((fx, text, item, user))
    if args.dry_run:
        fx, text, item, user = built[0]
        print(f"样例 {len(built)} 份；第一份（{fx['id']}，{item['id']}）的裁判请求：")
        print("[system]\n" + prompt.system + "\n[user]\n" + user)
        return 0

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    providers.require_key(jcfg["provider"], cfg)
    conn = db.connect(db_path)
    run_id = "F" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)
    print(f"judge_run_id {run_id}｜裁判 {jcfg['name']}｜prompt {prompt.rel}（{prompt.sha256[:12]}）｜样例 {len(built)} 份"
          f"｜结果存 fixture_judgments，不进统计")

    def work(b):
        fx, text, item, user = b
        return run_judge(jcfg, cfg, prompt.system, user, item, text,
                         log=lambda m, fid=fx["id"]: print(f"  [{fid}] {m.strip()}"))

    tin = tout = n_pass = 0
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(work, b): b for b in built}
        for fut in as_completed(futs):
            fx, text, item, user = futs[fut]
            res = fut.result()
            results[fx["id"]] = (fx, text, item, user, res)
    for fx, text, item, user, res in (results[f["id"]] for f in manifest):
        tin += res.input_tokens
        tout += res.output_tokens
        act, passed = check_fixture(fx["expect"], res.parsed, res.status)
        n_pass += bool(passed) and res.status == "ok"
        row = {"judge_run_id": run_id, "fixture_id": fx["id"], "item_id": item["id"],
               "source_call_id": fx["source_call_id"], "text_sha256": fx["text_sha256"],
               "judge_model_name": jcfg["name"], "judge_model_version": res.last.model_version if res.last else None,
               "prompt_file": prompt.rel, "prompt_sha256": prompt.sha256, "rubric_sha256": rubric_hash(item),
               "request_sha256": db.request_hash(prompt.system, user, res.last.params_sent if res.last else params),
               "params_used": {"sent": res.last.params_sent if res.last else params,
                               "reported_by_api": res.last.params_reported if res.last else None},
               "raw_output": res.raw,
               "parsed_json": parsed_json(res.parsed) if res.parsed is not None else None,
               "flags": {**(res.parsed.flags() if res.parsed is not None else {}),
                         "rejudge_history": res.history or []},
               "expect": fx["expect"], "actual": act, "passed": None if passed is None else int(passed),
               "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
               "attempts": res.attempts, "latency_s": res.latency_s, "created_at": _now(),
               "status": res.status, "error": res.error}
        db.insert_fixture(conn, row)
        verdict = {True: "符合预期", False: "不符合预期", None: "无结果"}[passed]
        rj = f"｜重判 {res.n_rejudge} 次" if res.n_rejudge else ""
        print(f"{fx['id']} {item['id']:<16} {res.status:<12} {verdict}{rj}｜实际 {json.dumps(act, ensure_ascii=False)}"
              + (f"｜{res.error}" if res.error else ""))
    conn.close()
    cost = estimate_cost(jcfg, tin, tout)
    print("-" * 72)
    print(f"样例 {len(built)} 份，状态 ok 且符合预期 {n_pass} 份｜输入 {tin} tokens，输出 {tout} tokens｜费用 "
          + (f"约 ${cost:.4f}（按标价）" if cost is not None else "未估算"))
    return 0 if n_pass == len(built) else 1


if __name__ == "__main__":
    sys.exit(main())
