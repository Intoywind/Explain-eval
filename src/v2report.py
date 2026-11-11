"""通用 V1 对 V2 在 30 条短题上的对比报告（第六份输入）。

python -m src.v2report --out reports/

- 两边都是 data/items.jsonl 的当前回答 × judge_v2 × 当前判分清单的最新裁判记录（ECON-003 用重判后的），
  取法和四组汇总（src.summary）一样；分数只算 status='ok' 的记录。
- 汇总分数（知识通过率、卡点分、步骤分、卡点全答上）的算法和四组汇总一致：知识不通过时卡点分、步骤分记 0。
- “卡点答上率（不清零）”和逐卡点、逐步骤的次数直接用裁判对每一项的 answered / done（引句校验后），不套知识清零。
- 另写一份给人读的样例文件（--samples-out），只放原文，不放裁判结论。
- 每张表后的 [Qn] 指向附录里取数的 SQL，可以直接在 sqlite3 results/eval.db 里运行。
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .judge import ROOT, db_path_from_config, judge_model_cfg, load_items, load_prompt
from .report import Report, _md, _q, snapshot_items
from .run import UsageError, _rel, find_model, load_config

MODELS = ["gpt-6.1-sol", "gpt-6-luna"]
SIDES = ["V1", "V2"]
COURSES = ["COMP2711", "IEDA1280", "ECON1221"]
READERS = ["零基础", "有前置"]
GAP_TYPES = ["术语未先定义", "切换处漏连接", "公式未接含义", "前提未交代"]
SEVERITIES = ["读者没法往下读", "只是不顺"]
BLOCKING = "读者没法往下读"
CACHE_PRICE = {"gpt-6-luna": 0.01, "gpt-6.1-sol": None}   # sol 的缓存单价 config 里没有
JUDGE_CACHE_PRICE = 0.05
# V2 “好坏对照”表的例子取自编程入门；这些词出现在回答里就列出来（不区分大小写）
OFFTOPIC_TERMS = [r"\bdouble\b", r"二分查找", r"二分", r"binary search", r"双精度", r"浮点", r"整数除法",
                  r"price\s*=", r"9\s*/\s*2", r"log₂\s*n"]
EPS = 1e-9


def _pct(v):
    return "—" if v is None else f"{100 * v:.1f}%"


def _f(v, nd=3):
    return "—" if v is None else f"{v:.{nd}f}"


def _pp(a, b):
    """b − a，百分点。"""
    if a is None or b is None:
        return "—"
    d = 100 * (b - a)
    return f"{0.0 if abs(d) < 0.05 else d:+.1f} 个百分点"


def _dd(a, b, nd=3):
    if a is None or b is None:
        return "—"
    d = b - a
    return f"{0.0 if abs(d) < 0.5 * 10 ** -nd else d:+.{nd}f}"


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _frac(a, b):
    return f"{a}/{b}" if b else "—"


def _short(s, n=120):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n] + "…"


# ---------------- 取数 ----------------

def base_sql(judge_name: str, prompt_sha: str, a: str, b: str) -> str:
    return f"""WITH sel AS (  -- 两份 Skill 的当前回答 × 该裁判、该版 prompt、判分清单与当前条目一致的最新一条裁判记录
  SELECT CASE c.skill_file WHEN {_q(a)} THEN 'V1' WHEN {_q(b)} THEN 'V2' END AS side,
         c.model_name, c.id AS call_id, c.item_id, c.repeat_idx, s.course, s.reader,
         c.output_tokens AS gen_out, rc.char_count,
         j.id AS judgment_id, j.status, j.error, j.knowledge_pass, j.incomplete, j.gate_num, j.gate_den,
         j.step_num, j.step_den, j.gate_all, j.n_gaps_blocking, j.n_redundancy, j.attempts, j.flags, j.parsed_json
  FROM current_calls c
  JOIN items_snapshot s ON s.item_id = c.item_id
  LEFT JOIN rule_checks rc ON rc.call_id = c.id
  LEFT JOIN judgments j ON j.id = (
       SELECT max(x.id) FROM judgments x
       WHERE x.call_id = c.id AND x.judge_model_name = {_q(judge_name)}
         AND x.prompt_sha256 = {_q(prompt_sha)} AND x.rubric_sha256 = s.rubric_sha256)
  WHERE c.skill_file IN ({_q(a)}, {_q(b)})
)"""


def load(R: Report, judge_name: str, prompt_sha: str, a: str, b: str) -> dict:
    SEL = base_sql(judge_name, prompt_sha, a, b)
    t_base, rows = R.q("每份当前回答和它的裁判结果（两份 Skill × 两个模型）", SEL + """
SELECT side, model_name, call_id, item_id, repeat_idx, course, reader, gen_out, char_count,
       judgment_id, status, error, knowledge_pass, incomplete, gate_num, gate_den, step_num, step_den, gate_all,
       n_gaps_blocking, n_redundancy, attempts, flags,
       json_extract(parsed_json, '$.knowledge_error') AS kerr, json_extract(parsed_json, '$.incomplete') AS incomp
FROM sel ORDER BY side, model_name, item_id, repeat_idx""")
    t_gate, gate = R.q("逐卡点：只取 ok 的裁判记录，answered 是引句校验后的值（不套知识清零）", SEL + """
SELECT sel.side, sel.model_name, sel.call_id, sel.item_id, sel.repeat_idx, sel.course, sel.reader,
       g.question_id, g.answered, g.quotes, g.quotes_valid, g.reason, ig.text AS q_text
FROM sel JOIN judge_gate g ON g.judgment_id = sel.judgment_id
JOIN items_gate ig ON ig.item_id = g.item_id AND ig.question_id = g.question_id
WHERE sel.status = 'ok' ORDER BY sel.item_id, g.question_id, sel.model_name, sel.side, sel.repeat_idx""")
    t_step, steps = R.q("逐步骤：只取 ok 的裁判记录，done 是引句校验后的值（不套知识清零）", SEL + """
SELECT sel.side, sel.model_name, sel.call_id, sel.item_id, sel.repeat_idx, sel.course, sel.reader,
       st.step_id, st.done, its.text AS s_text
FROM sel JOIN judge_steps st ON st.judgment_id = sel.judgment_id
JOIN items_steps its ON its.item_id = st.item_id AND its.step_id = st.step_id
WHERE sel.status = 'ok' ORDER BY sel.item_id, st.step_id, sel.model_name, sel.side, sel.repeat_idx""")
    t_gap, gaps = R.q("跳步：只取 ok 的裁判记录，引句通过校验的", SEL + """
SELECT sel.side, sel.model_name, sel.call_id, sel.item_id, g.subtype, g.severity
FROM sel JOIN judge_gaps g ON g.judgment_id = sel.judgment_id
WHERE sel.status = 'ok' AND g.quote_valid = 1""")
    return {"rows": rows, "gate": gate, "steps": steps, "gaps": gaps,
            "t": {"base": t_base, "gate": t_gate, "step": t_step, "gap": t_gap}}


# ---------------- 计算 ----------------

def metrics(rows: list[dict], gate: list[dict], steps: list[dict]) -> dict:
    ok = [r for r in rows if r["status"] == "ok"]
    by_item = defaultdict(list)
    for r in ok:
        by_item[r["item_id"]].append(r)
    g_item = _mean([_mean([x["gate_num"] / x["gate_den"] for x in v]) for v in by_item.values()])
    s_item = _mean([_mean([x["step_num"] / x["step_den"] for x in v]) for v in by_item.values()])
    return {
        "n": len(rows), "n_ok": len(ok),
        "k_pass": _mean([r["knowledge_pass"] for r in ok]),
        "gate": _mean([r["gate_num"] / r["gate_den"] for r in ok]), "gate_item": g_item,
        "step": _mean([r["step_num"] / r["step_den"] for r in ok]), "step_item": s_item,
        "gate_all": _mean([r["gate_all"] for r in ok]),
        "n_gate_all": sum(r["gate_all"] for r in ok),
        "gate_raw": _mean([g["answered"] for g in gate]), "n_gate_rows": len(gate),
        "n_gate_ans": sum(g["answered"] for g in gate),
        "step_raw": _mean([s["done"] for s in steps]), "n_step_rows": len(steps),
    }


def per_unit_counts(rows: list[dict], key: str, val: str) -> dict:
    """{(model, side, item_id, unit_id): [做到次数, 判过次数]}"""
    out = defaultdict(lambda: [0, 0])
    for r in rows:
        k = (r["model_name"], r["side"], r["item_id"], r[key])
        out[k][0] += r[val]
        out[k][1] += 1
    return out


def updown(cnt: dict, model: str, units: list[tuple]) -> tuple[int, int, int]:
    up = flat = down = 0
    for iid, uid in units:
        a, b = cnt.get((model, "V1", iid, uid)), cnt.get((model, "V2", iid, uid))
        if not a or not b or not a[1] or not b[1]:
            continue
        ra, rb = a[0] / a[1], b[0] / b[1]
        if rb > ra + EPS:
            up += 1
        elif rb < ra - EPS:
            down += 1
        else:
            flat += 1
    return up, flat, down


# ---------------- 报告 ----------------

def build(args) -> tuple[str, str, Path, Path]:
    cfg = load_config(Path(args.config))
    jcfg = judge_model_cfg(cfg)
    judge_name = jcfg["name"]
    prompt = load_prompt(Path(args.judge_prompt))
    items_by_id, items_rel = load_items(Path(args.items), False)
    a, b = _rel(Path(args.a)), _rel(Path(args.b))
    conn = db.connect(db_path_from_config(cfg))
    snapshot_items(conn, items_by_id, items_rel)
    R = Report(conn)
    D = load(R, judge_name, prompt.sha256, a, b)
    rows, gate, steps, gaps, T = D["rows"], D["gate"], D["steps"], D["gaps"], D["t"]

    gate_units = [(iid, q["id"]) for iid, it in items_by_id.items() for q in it["gate_questions"]]
    step_units = [(iid, s["id"]) for iid, it in items_by_id.items() for s in it["recommended_steps"]]
    item_course = {iid: it["course"] for iid, it in items_by_id.items()}
    item_reader = {iid: ("零基础" if iid.endswith("零基础") else "有前置") for iid in items_by_id}
    gcnt = per_unit_counts(gate, "question_id", "answered")
    scnt = per_unit_counts(steps, "step_id", "done")

    def sub(xs, model=None, side=None, course=None, reader=None):
        return [x for x in xs if (model is None or x["model_name"] == model) and (side is None or x["side"] == side)
                and (course is None or x["course"] == course) and (reader is None or x["reader"] == reader)]

    L = [f"# 通用 V1 对 V2：30 条短题（{prompt.rel}）", "",
         f"- V1 = `{a}`，V2 = `{b}`；被测模型 gpt-6.1-sol（下称 sol）、gpt-6-luna（下称 luna），每条 3 次。",
         f"- 裁判：{judge_name}（{jcfg['model_id']}），prompt `{prompt.rel}`（sha256 {prompt.sha256[:12]}…）；条目文件 `{items_rel}`。",
         f"- 生成时间：{datetime.now(timezone.utc).isoformat(timespec='seconds')}",
         "- 两边都取当前回答 × 这版裁判 × 当前判分清单的最新裁判记录（V1 的 ECON-003 用的是按新条目重判后的），分数只算 status='ok' 的。",
         "- V2 的生成命令：`python -m src.run --skill skills/general_v2.md --model <模型> --items data/items.jsonl --repeats 3 --workers 6 --stream`。"
         "发出的用户消息、参数（sol：store=false、reasoning.effort=medium；luna 另加 text.verbosity=medium）、输出上限（都不设，用接口默认）"
         "和 V1 两组逐字相同，生成前已逐条核对。V1 当时没用流式；流式只是传输方式（本机网络会断开超过约 60 秒的非流式请求），不进请求哈希。",
         "- V2 的判分：`python -m src.judge --prompt prompts/judge_v2.md --skill skills/general_v2.md --workers 8 --stream`，参数与 V1 判分相同；"
         "第二遍：`--repeat 20 --seed 20261112 --strata model --skill skills/general_v2.md`。",
         "- **这是开发题上的检查**：V2 是照这批题的失败写的，补得回来只说明 V2 没写偏，不能当作 V2 有效的证据。",
         "- 每张表后的 [Qn] 指向文末附录的 SQL。", ""]

    # 0. 份数
    L += [f"## 0. 份数 [{T['base']}]", "",
          "| 模型 | Skill | 当前回答 | ok | 待复核 | 失败 | 未评 |", "|---|---|---|---|---|---|---|"]
    for m in MODELS:
        for sd in SIDES:
            g = sub(rows, m, sd)
            L.append(f"| {m} | {sd} | {len(g)} | {sum(r['status'] == 'ok' for r in g)} "
                     f"| {sum(r['status'] == 'needs_review' for r in g)} | {sum(r['status'] == 'error' for r in g)} "
                     f"| {sum(r['judgment_id'] is None for r in g)} |")
    t_tr, gen_fail = R.q("V2 生成时没有成功的调用（截断 finish_reason=length 等）", f"""
SELECT model_name, item_id, repeat_idx, finish_reason, error, output_tokens, created_at FROM calls
WHERE skill_file = {_q(b)} AND items_file = {_q(items_rel)} AND status != 'ok' ORDER BY model_name, item_id, repeat_idx""")
    L += ["", f"V2 生成时没有成功的调用 [{t_tr}]：" + ("无。" if not gen_fail else "")]
    if gen_fail:
        L += ["", "| 模型 | 条目 | 第几次 | finish_reason | 输出 tokens | 错误 |", "|---|---|---|---|---|---|"]
        L += [f"| {r['model_name']} | {r['item_id']} | {r['repeat_idx']} | {r['finish_reason'] or '—'} "
              f"| {r['output_tokens'] or '—'} | {_md(_short(r['error'], 100))} |" for r in gen_fail]
    n_trunc = Counter(r["model_name"] for r in gen_fail if r["finish_reason"] == "length")
    L += ["", "截断（finish_reason=length）的份数：" + "，".join(f"{m} {n_trunc.get(m, 0)} 份" for m in MODELS)
          + "。截断的记为失败、不送裁判；续跑会重新调用，当前回答里没有截断的。", ""]

    # 1. 汇总
    L += [f"## 1. 汇总 [{T['base']}] [{T['gate']}] [{T['step']}]", "",
          "知识通过率、卡点分、步骤分、卡点全答上的算法和四组汇总一致（知识不通过时卡点分、步骤分记 0；按回答平均，括号里是按条目平均）。"
          "“卡点答上率（不清零）”= 所有 ok 回答里每个卡点的 answered 的平均。", ""]
    for m in MODELS:
        ma = metrics(sub(rows, m, "V1"), sub(gate, m, "V1"), sub(steps, m, "V1"))
        mb = metrics(sub(rows, m, "V2"), sub(gate, m, "V2"), sub(steps, m, "V2"))
        up, flat, down = updown(gcnt, m, gate_units)
        L += [f"### {m}", "", "| 指标 | V1 | V2 | V2 − V1 |", "|---|---|---|---|",
              f"| ok 份数 | {ma['n_ok']} | {mb['n_ok']} | |",
              f"| 知识通过率 | {_pct(ma['k_pass'])} | {_pct(mb['k_pass'])} | {_pp(ma['k_pass'], mb['k_pass'])} |",
              f"| 卡点分（按回答；按条目） | {_f(ma['gate'])}（{_f(ma['gate_item'])}） | {_f(mb['gate'])}（{_f(mb['gate_item'])}） "
              f"| {_dd(ma['gate'], mb['gate'])}（{_dd(ma['gate_item'], mb['gate_item'])}） |",
              f"| 步骤分（按回答；按条目） | {_f(ma['step'])}（{_f(ma['step_item'])}） | {_f(mb['step'])}（{_f(mb['step_item'])}） "
              f"| {_dd(ma['step'], mb['step'])}（{_dd(ma['step_item'], mb['step_item'])}） |",
              f"| 卡点全答上的份数占比 | {_pct(ma['gate_all'])}（{ma['n_gate_all']}/{ma['n_ok']}） "
              f"| {_pct(mb['gate_all'])}（{mb['n_gate_all']}/{mb['n_ok']}） | {_pp(ma['gate_all'], mb['gate_all'])} |",
              f"| 卡点答上率（不清零） | {_pct(ma['gate_raw'])}（{ma['n_gate_ans']}/{ma['n_gate_rows']}） "
              f"| {_pct(mb['gate_raw'])}（{mb['n_gate_ans']}/{mb['n_gate_rows']}） | {_pp(ma['gate_raw'], mb['gate_raw'])} |",
              f"| 步骤做到率（不清零） | {_pct(ma['step_raw'])} | {_pct(mb['step_raw'])} | {_pp(ma['step_raw'], mb['step_raw'])} |",
              f"| {len(gate_units)} 个卡点：V2 比 V1 答上次数 上升 / 持平 / 下降 | | | {up} / {flat} / {down} |", ""]

    for dim, vals, fld in (("课程", COURSES, "course"), ("读者版本", READERS, "reader")):
        L += [f"### 1b. 按{dim} [{T['base']}] [{T['gate']}]", "",
              "每格写“V1 → V2”。卡点分、步骤分按回答平均（套知识清零）；卡点答上率不清零，括号里是差。", "",
              f"| 模型 | {dim} | ok 份数 | 知识通过率 | 卡点分 | 步骤分 | 卡点全答上 | 卡点答上率（不清零） | 卡点 升/平/降 |",
              "|---|---|---|---|---|---|---|---|---|"]
        for m in MODELS:
            for v in vals:
                kw = {fld: v}
                ma = metrics(sub(rows, m, "V1", **kw), sub(gate, m, "V1", **kw), sub(steps, m, "V1", **kw))
                mb = metrics(sub(rows, m, "V2", **kw), sub(gate, m, "V2", **kw), sub(steps, m, "V2", **kw))
                units = [u for u in gate_units if (item_course if fld == "course" else item_reader)[u[0]] == v]
                up, flat, down = updown(gcnt, m, units)
                L.append(f"| {m} | {v} | {ma['n_ok']} → {mb['n_ok']} | {_pct(ma['k_pass'])} → {_pct(mb['k_pass'])} "
                         f"| {_f(ma['gate'])} → {_f(mb['gate'])} | {_f(ma['step'])} → {_f(mb['step'])} "
                         f"| {_pct(ma['gate_all'])} → {_pct(mb['gate_all'])} "
                         f"| {_pct(ma['gate_raw'])} → {_pct(mb['gate_raw'])}（{_pp(ma['gate_raw'], mb['gate_raw'])}） "
                         f"| {up}/{flat}/{down}（共 {len(units)}） |")
        L.append("")

    # 2. 逐卡点
    L += [f"## 2. 逐卡点对比（{len(gate_units)} 个卡点 × 2 个模型）[{T['gate']}]", "",
          "每格是“答上次数/判过次数”（各 3 次，待复核的不算在判过次数里）；不套知识清零。▲ = V2 比 V1 多，▼ = V2 比 V1 少。", "",
          "| 条目 | 卡点 | 卡点问题 | sol V1 | sol V2 | luna V1 | luna V2 |", "|---|---|---|---|---|---|---|"]

    def cell(m, sd, iid, qid, c=gcnt):
        x = c.get((m, sd, iid, qid))
        return _frac(*x) if x else "—"

    def mark(m, iid, uid, c=gcnt):
        x, y = c.get((m, "V1", iid, uid)), c.get((m, "V2", iid, uid))
        if not x or not y or not x[1] or not y[1]:
            return ""
        d = y[0] / y[1] - x[0] / x[1]
        return " ▲" if d > EPS else " ▼" if d < -EPS else ""

    qtext = {(iid, q["id"]): q["text"] for iid, it in items_by_id.items() for q in it["gate_questions"]}
    for iid, qid in gate_units:
        L.append(f"| {iid} | {qid} | {_md(_short(qtext[(iid, qid)], 60))} "
                 + " | ".join(f"{cell(m, 'V1', iid, qid)} | {cell(m, 'V2', iid, qid)}{mark(m, iid, qid)}" for m in MODELS) + " |")
    L.append("")

    gate_by = defaultdict(list)   # (model, side, iid, qid) -> 逐次记录
    for g in gate:
        gate_by[(g["model_name"], g["side"], g["item_id"], g["question_id"])].append(g)

    def first_valid_quote(g):
        qs, vs = json.loads(g["quotes"] or "[]"), json.loads(g["quotes_valid"] or "[]")
        for q, v in zip(qs, vs):
            if v:
                return q
        return None

    # 3. 重点看的卡点
    L += [f"## 3. 重点看的卡点：V1 没有每次都答上的 [{T['gate']}]", ""]
    focus = {m: [(iid, qid) for iid, qid in gate_units
                 if (x := gcnt.get((m, "V1", iid, qid))) and x[0] < x[1]] for m in MODELS}
    L += ["按模型分别从 V1 的裁判记录里筛：" + "，".join(f"{m} {len(focus[m])} 个" for m in MODELS)
          + "（第六份输入里数的是 sol 7 个、luna 12 个"
          + ("，一致" if len(focus['gpt-6.1-sol']) == 7 and len(focus['gpt-6-luna']) == 12 else "，**不一致**") + "）。", ""]
    for m in MODELS:
        tot_a = sum(gcnt[(m, "V1", i, q)][0] for i, q in focus[m])
        tot_n = sum(gcnt[(m, "V1", i, q)][1] for i, q in focus[m])
        tot_b = sum(gcnt.get((m, "V2", i, q), [0, 0])[0] for i, q in focus[m])
        tot_bn = sum(gcnt.get((m, "V2", i, q), [0, 0])[1] for i, q in focus[m])
        nb_up = sum(1 for i, q in focus[m] if mark(m, i, q) == " ▲")
        nb_all = sum(1 for i, q in focus[m] if (y := gcnt.get((m, "V2", i, q))) and y[1] and y[0] == y[1])
        L += [f"### {m}（{len(focus[m])} 个）", "",
              f"合计答上次数：V1 {tot_a}/{tot_n}，V2 {tot_b}/{tot_bn}；V2 比 V1 多的 {nb_up} 个，V2 三次都答上的 {nb_all} 个。", "",
              "| 条目 | 卡点 | V1 | V2 | V2 答上时裁判引的原句（摘一句） / V2 没答上时裁判的判语 |", "|---|---|---|---|---|"]
        for iid, qid in focus[m]:
            recs = gate_by.get((m, "V2", iid, qid), [])
            parts = []
            hit = next((g for g in recs if g["answered"]), None)
            if hit is not None:
                q = first_valid_quote(hit)
                parts.append(f"答上（第 {hit['repeat_idx']} 次）引句：“{_md(_short(q, 140))}”")
            for g in recs:
                if not g["answered"]:
                    parts.append(f"没答上（第 {g['repeat_idx']} 次）：{_md(_short(g['reason'], 220))}")
            L.append(f"| {iid} | {qid} | {cell(m, 'V1', iid, qid)} | {cell(m, 'V2', iid, qid)} | {'<br>'.join(parts) or '—'} |")
        L.append("")

    # 4. V2 变差的卡点
    L += [f"## 4. V2 变差的卡点：V2 答上次数比 V1 少的 [{T['gate']}]", ""]
    any_worse = False
    for m in MODELS:
        worse = [(iid, qid) for iid, qid in gate_units if mark(m, iid, qid) == " ▼"]
        L += [f"### {m}（{len(worse)} 个）", ""]
        if not worse:
            L += ["没有。", ""]
            continue
        any_worse = True
        L += ["| 条目 | 卡点 | V1 | V2 | V2 没答上的那几次，裁判的判语 |", "|---|---|---|---|---|"]
        for iid, qid in worse:
            rs = [f"第 {g['repeat_idx']} 次：{_md(_short(g['reason'], 300))}"
                  for g in gate_by.get((m, "V2", iid, qid), []) if not g["answered"]]
            L.append(f"| {iid} | {qid} | {cell(m, 'V1', iid, qid)} | {cell(m, 'V2', iid, qid)} | {'<br>'.join(rs)} |")
        L.append("")

    # 5. 推荐步骤
    L += [f"## 5. 推荐步骤（{len(step_units)} 个）[{T['step']}]", "",
          "做到率直接用裁判对每个步骤的 done（不套知识清零）；升降按每个步骤的做到比例比较。逐条表在附录 A。", "",
          "| 模型 | V1 做到率 | V2 做到率 | 差 | 步骤 上升 / 持平 / 下降 |", "|---|---|---|---|---|"]
    for m in MODELS:
        ma = _mean([s["done"] for s in sub(steps, m, "V1")])
        mb = _mean([s["done"] for s in sub(steps, m, "V2")])
        up, flat, down = updown(scnt, m, step_units)
        L.append(f"| {m} | {_pct(ma)} | {_pct(mb)} | {_pp(ma, mb)} | {up} / {flat} / {down} |")
    never = [(iid, sid) for iid, sid in step_units
             if sum(scnt.get((m, "V1", iid, sid), [0, 0])[1] for m in MODELS) > 0
             and sum(scnt.get((m, "V1", iid, sid), [0, 0])[0] for m in MODELS) == 0]
    stext = {(iid, s["id"]): s["text"] for iid, it in items_by_id.items() for s in it["recommended_steps"]}
    L += ["", f"### V1 的 6 份回答（两个模型各 3 次）里一次都没做到的步骤：{len(never)} 个", "",
          "| 条目 | 步骤 | 步骤内容 | V1 sol | V1 luna | V2 sol | V2 luna |", "|---|---|---|---|---|---|---|"]
    for iid, sid in never:
        L.append(f"| {iid} | {sid} | {_md(_short(stext[(iid, sid)], 70))} | "
                 + " | ".join(cell(m, sd, iid, sid, scnt) for sd in SIDES for m in MODELS) + " |")
    nv2 = sum(scnt.get((m, "V2", i, s), [0, 0])[0] for i, s in never for m in MODELS)
    nv2n = sum(scnt.get((m, "V2", i, s), [0, 0])[1] for i, s in never for m in MODELS)
    nv2_any = sum(1 for i, s in never if sum(scnt.get((m, "V2", i, s), [0, 0])[0] for m in MODELS) > 0)
    L += ["", f"这些步骤在 V2 的回答里合计做到 {nv2}/{nv2n} 次；{len(never)} 个里 V2 至少做到一次的 {nv2_any} 个。", ""]

    # 6. 篇幅和冗余
    L += [f"## 6. 篇幅和冗余 [{T['base']}]", "",
          "字数 = 回答全文的字符数（`rule_checks.char_count`，含标点、公式源码和空白）。比例 = V2 ÷ V1，按（模型、条目、第几次重复）配对。", ""]
    by_key = {(r["side"], r["model_name"], r["item_id"], r["repeat_idx"]): r for r in rows}
    pairs = []
    for (sd, m, iid, rep), r in by_key.items():
        if sd != "V1":
            continue
        r2 = by_key.get(("V2", m, iid, rep))
        if r2 and r["char_count"] and r2["char_count"]:
            pairs.append({"model": m, "item_id": iid, "rep": rep, "reader": item_reader[iid], "course": item_course[iid],
                          "a": r["char_count"], "b": r2["char_count"], "ratio": r2["char_count"] / r["char_count"],
                          "a_out": r["gen_out"], "b_out": r2["gen_out"]})
    L += ["| 模型 | 读者版本 | 配对数 | V1 平均字数 | V2 平均字数 | 比例 均值 | 比例 中位数 | 比例 最小–最大 |",
          "|---|---|---|---|---|---|---|---|"]
    for m in MODELS:
        for rd in READERS + [None]:
            ps = [p for p in pairs if p["model"] == m and (rd is None or p["reader"] == rd)]
            if not ps:
                continue
            rs = [p["ratio"] for p in ps]
            L.append(f"| {m} | {rd or '合计'} | {len(ps)} | {_mean([p['a'] for p in ps]):,.0f} | {_mean([p['b'] for p in ps]):,.0f} "
                     f"| {_mean(rs):.2f} | {statistics.median(rs):.2f} | {min(rs):.2f}–{max(rs):.2f} |")
    big = sorted([p for p in pairs if p["ratio"] > 2], key=lambda p: -p["ratio"])
    L += ["", f"### 比例超过 2 的配对：{len(big)} 对（涉及 {len({(p['model'], p['item_id']) for p in big})} 个（模型 × 条目））", ""]
    if big:
        L += ["| 模型 | 条目 | 第几次 | V1 字数 | V2 字数 | 比例 |", "|---|---|---|---|---|---|"]
        L += [f"| {p['model']} | {p['item_id']} | {p['rep']} | {p['a']:,} | {p['b']:,} | {p['ratio']:.2f} |" for p in big]
    L += ["", "### 裁判记下的冗余（只统计有前置版；引句通过校验的条数）", "",
          "| 模型 | V1 份数 | V1 冗余条数（每份平均） | V1 有冗余的份数 | V2 份数 | V2 冗余条数（每份平均） | V2 有冗余的份数 |",
          "|---|---|---|---|---|---|---|"]
    for m in MODELS:
        cells = []
        for sd in SIDES:
            ok = [r for r in sub(rows, m, sd, reader="有前置") if r["status"] == "ok"]
            n = sum(r["n_redundancy"] or 0 for r in ok)
            cells.append(f"{len(ok)} | {n}（{n / len(ok):.2f}） | {sum((r['n_redundancy'] or 0) > 0 for r in ok)}" if ok else "— | — | —")
        L.append(f"| {m} | " + " | ".join(cells) + " |")

    t_txt, texts = R.q("V2 的当前回答原文（找和题目无关的编程入门内容）", f"""
SELECT c.id AS call_id, c.model_name, c.item_id, c.repeat_idx, c.response_text FROM current_calls c
JOIN items_snapshot s ON s.item_id = c.item_id WHERE c.skill_file = {_q(b)} ORDER BY c.model_name, c.item_id, c.repeat_idx""")
    _, v1texts = R.q("V1 的当前回答原文（同一批词在 V1 里出现的次数，作对照）", f"""
SELECT c.id AS call_id, c.model_name, c.item_id, c.repeat_idx, c.response_text FROM current_calls c
JOIN items_snapshot s ON s.item_id = c.item_id WHERE c.skill_file = {_q(a)} ORDER BY c.model_name, c.item_id, c.repeat_idx""")
    pat = re.compile("|".join(OFFTOPIC_TERMS), re.I)
    hits = []
    for r in texts:
        for mt in pat.finditer(r["response_text"] or ""):
            s0, e0 = max(0, mt.start() - 40), min(len(r["response_text"]), mt.end() + 40)
            in_mat = bool(re.search(re.escape(mt.group(0)), items_by_id[r["item_id"]]["material"], re.I))
            hits.append((r, mt.group(0), r["response_text"][s0:e0], in_mat))
    v1_hits = sum(len(pat.findall(r["response_text"] or "")) for r in v1texts)
    L += ["", f"### V2 回答里有没有出现“好坏对照”表里的编程入门内容 [{t_txt}]", "",
          "按这些词查（不区分大小写）：" + "、".join(f"`{t}`" for t in OFFTOPIC_TERMS) + "。", "",
          f"V2 的 {len(texts)} 份回答里命中 {len(hits)} 处（涉及 {len({h[0]['call_id'] for h in hits})} 份）；"
          f"作对照，V1 的 {len(v1texts)} 份回答里命中 {v1_hits} 处。", ""]
    if hits:
        L += ["| 模型 | 条目 | 第几次 | 命中 | 上下文 | 材料里本来就有这个词 |", "|---|---|---|---|---|---|"]
        L += [f"| {r['model_name']} | {r['item_id']} | {r['repeat_idx']} | `{_md(w)}` | {_md(_short(ctx, 120))} | {'是' if im else '否'} |"
              for r, w, ctx, im in hits]
    L.append("")

    # 7. 知识错误和没答全
    L += [f"## 7. 知识错误和没答全 [{T['base']}]", "",
          "| 模型 | Skill | ok 份数 | 知识不通过 份数 | 所在条目（次数） | 没答全 份数 | 所在条目（次数） |", "|---|---|---|---|---|---|---|"]
    kf = {}
    for m in MODELS:
        for sd in SIDES:
            ok = [r for r in sub(rows, m, sd) if r["status"] == "ok"]
            kfail = [r for r in ok if r["knowledge_pass"] == 0]
            inc = [r for r in ok if r["incomplete"] == 1]
            kf[(m, sd)] = kfail
            ci = lambda xs: "，".join(f"{k}（{v}）" for k, v in sorted(Counter(r["item_id"] for r in xs).items())) or "—"
            L.append(f"| {m} | {sd} | {len(ok)} | {len(kfail)} | {ci(kfail)} | {len(inc)} | {ci(inc)} |")
    L += ["", "### V2 的知识错误逐条（裁判的 which 和 note）", ""]
    any_k = False
    for m in MODELS:
        v1_items = {r["item_id"] for r in kf[(m, "V1")]}
        for r in kf[(m, "V2")]:
            any_k = True
            ke = json.loads(r["kerr"] or "{}")
            new = "V1 同条目同模型也有知识错误" if r["item_id"] in v1_items else "**新出现**（V1 同条目同模型 3 次都没有）"
            L += [f"- {m}｜{r['item_id']} 第 {r['repeat_idx']} 次（call {r['call_id']}）｜{new}",
                  f"  - which：{'；'.join(ke.get('which') or [])}",
                  f"  - note：{_short(ke.get('note'), 400)}"]
    if not any_k:
        L.append("V2 没有知识不通过的回答。")
    L += ["", "### V2 的没答全逐条（裁判的 missing 和 note）", ""]
    any_i = False
    for m in MODELS:
        for r in [x for x in sub(rows, m, "V2") if x["status"] == "ok" and x["incomplete"] == 1]:
            any_i = True
            ic = json.loads(r["incomp"] or "{}")
            L.append(f"- {m}｜{r['item_id']} 第 {r['repeat_idx']} 次：{'；'.join(ic.get('missing') or [])}｜{_short(ic.get('note'), 300)}")
    if not any_i:
        L.append("V2 没有没答全的回答。")
    L.append("")

    # 8. 跳步
    L += [f"## 8. 跳步 [{T['base']}] [{T['gap']}]", "",
          "“有严重跳步”= 至少有一处严重程度为“读者没法往下读”、且引句通过校验的跳步（`judgments.n_gaps_blocking > 0`）。", "",
          "| 模型 | Skill | ok 份数 | 有严重跳步的份数 | 占比 |", "|---|---|---|---|---|"]
    for m in MODELS:
        for sd in SIDES:
            ok = [r for r in sub(rows, m, sd) if r["status"] == "ok"]
            nb = sum((r["n_gaps_blocking"] or 0) > 0 for r in ok)
            L.append(f"| {m} | {sd} | {len(ok)} | {nb} | {_pct(nb / len(ok) if ok else None)} |")
    L += ["", "按类型 × 严重程度的条数（只算引句通过校验的）：", "",
          "| 模型 | 类型 | " + " | ".join(f"V1 {s} | V2 {s}" for s in SEVERITIES) + " |", "|---|---|" + "---|" * (2 * len(SEVERITIES))]
    gc = Counter((g["model_name"], g["side"], g["subtype"], g["severity"]) for g in gaps)
    for m in MODELS:
        for t in GAP_TYPES + ["合计"]:
            cells = []
            for s in SEVERITIES:
                for sd in SIDES:
                    cells.append(str(sum(v for (mm, ss, tt, sv), v in gc.items() if mm == m and ss == sd and sv == s
                                         and (t == "合计" or tt == t))))
            L.append(f"| {m} | {t} | " + " | ".join(cells) + " |")
    L.append("")

    # 9. 步骤分高但有卡点没答上
    L += [f"## 9. 步骤做到率高于本组中位数、但有卡点没答上的回答 [{T['gate']}] [{T['step']}]", "",
          "组 = Skill × 模型。步骤做到率 = 这份回答里 done 的步骤数 ÷ 步骤数（不套知识清零）；“有卡点没答上”看每个卡点的 answered。"
          "“高于中位数”是严格大于。", ""]
    s_by_call = defaultdict(list)
    for s in steps:
        s_by_call[s["call_id"]].append(s["done"])
    g_by_call = defaultdict(list)
    for g in gate:
        g_by_call[g["call_id"]].append(g)
    for m in MODELS:
        for sd in SIDES:
            ok = [r for r in sub(rows, m, sd) if r["status"] == "ok"]
            rate = {r["call_id"]: _mean(s_by_call[r["call_id"]]) for r in ok}
            med = statistics.median(rate.values()) if rate else None
            sel = [r for r in ok if rate[r["call_id"]] > med + EPS and any(not g["answered"] for g in g_by_call[r["call_id"]])]
            L += [f"### {m} × {sd}：中位数 {_pct(med)}，符合的 {len(sel)} 份", ""]
            if med is not None and med >= 1 - EPS:   # 中位数已是 100%，没有回答能严格高于它；改列“做到率 100% 但有卡点没答上”的
                sel = [r for r in ok if rate[r["call_id"]] >= 1 - EPS and any(not g["answered"] for g in g_by_call[r["call_id"]])]
                L += [f"中位数已是 100%，没有回答能严格高于它。补充：步骤全做到（100%）但有卡点没答上的 {len(sel)} 份。", ""]
            if sel:
                L += ["| 条目 | 第几次 | 步骤做到率 | 没答上的卡点 |", "|---|---|---|---|"]
                L += [f"| {r['item_id']} | {r['repeat_idx']} | {_pct(rate[r['call_id']])} "
                      f"| {', '.join(g['question_id'] for g in g_by_call[r['call_id']] if not g['answered'])} |" for r in sel]
                L.append("")

    # 10. 样例
    samples, sample_lines = pick_samples(rows, gate, pairs, args.sample_seed)
    txt = {r["call_id"]: r["response_text"] for r in texts + v1texts}
    for c in samples:
        c["text_V1"], c["text_V2"] = txt[c["c1"]], txt[c["c2"]]
    L += [f"## 10. 给人读的样例：`{_rel(Path(args.samples_out))}` [{T['base']}] [{T['gate']}]", "",
          f"按下面的规则挑 6 组（同一条目、同一模型、同一重复序号的 V1 和 V2），随机种子 {args.sample_seed}；"
          "样例文件里只放请求和两份回答原文，不放裁判结论，也不写是按哪条规则挑的。挑选依据只写在这里：", ""]
    L += sample_lines + [""]

    # 11. 待复核、重判、花费、第二遍
    L += [f"## 11. 待复核、重判次数、第二遍一致率、实际花费 [{T['base']}]", ""]
    for m in MODELS:
        for sd in SIDES:
            nr = [r for r in sub(rows, m, sd) if r["status"] in ("needs_review", "error")]
            L.append(f"- {m} × {sd}：待复核 {sum(r['status'] == 'needs_review' for r in nr)} 份，失败 {sum(r['status'] == 'error' for r in nr)} 份"
                     + ("：" + "；".join(f"{r['item_id']} 第 {r['repeat_idx']} 次（call {r['call_id']}，{r['status']}）：{_short(r['error'], 160)}"
                                         for r in nr) if nr else "。"))
    L.append("")
    v2j = [r for r in rows if r["side"] == "V2" and r["judgment_id"] is not None]
    hist = Counter()
    n_rej = 0
    for r in v2j:
        h = (json.loads(r["flags"] or "{}") or {}).get("rejudge_history") or []
        if h:
            n_rej += 1
        for x in h:
            hist[x.get("kind")] += 1
    L += [f"- V2 第一遍判分的重判：{n_rej} 份重判过，共重判 {sum(hist.values())} 次"
          + (f"（{'，'.join(f'{k} {v} 次' for k, v in sorted(hist.items()))}；format = 输出格式不对，evidence = 证据不合格）" if hist else "")
          + "。", ""]
    L += consistency(R, judge_name, prompt.sha256, b, args.repeat_seed)
    L += costs(R, cfg, jcfg, b, items_rel, prompt.sha256)

    # 附录 A：逐步骤
    L += [f"## 附录 A：逐步骤对比（{len(step_units)} 个步骤 × 2 个模型）[{T['step']}]", "",
          "每格是“做到次数/判过次数”；不套知识清零。▲ / ▼ 同第 2 节。", "",
          "| 条目 | 步骤 | 步骤内容 | sol V1 | sol V2 | luna V1 | luna V2 |", "|---|---|---|---|---|---|---|"]
    for iid, sid in step_units:
        L.append(f"| {iid} | {sid} | {_md(_short(stext[(iid, sid)], 60))} | "
                 + " | ".join(f"{cell(m, 'V1', iid, sid, scnt)} | {cell(m, 'V2', iid, sid, scnt)}{mark(m, iid, sid, scnt)}"
                              for m in MODELS) + " |")
    L += ["", "## 附录 B：SQL", "", "可以直接在 `sqlite3 results/eval.db` 里运行（先跑过一次本脚本，items_snapshot 才是当前条目）。", ""]
    for k, (title, sql) in enumerate(R.sqls, 1):
        L += [f"### Q{k}. {title}", "", "```sql", sql, "```", ""]
    conn.close()

    S = render_samples(samples, items_by_id, a, b, args.sample_seed)
    out = Path(args.out) / f"short_v1_vs_v2__{Path(args.judge_prompt).stem}.md"
    return "\n".join(L), S, out, Path(args.samples_out)


def pick_samples(rows, gate, pairs, seed):
    rng = random.Random(seed)
    by_key = {(r["side"], r["model_name"], r["item_id"], r["repeat_idx"]): r for r in rows}
    g_by_call = defaultdict(dict)
    for g in gate:
        g_by_call[g["call_id"]][g["question_id"]] = g["answered"]
    cand = []
    for p in pairs:
        r1 = by_key[("V1", p["model"], p["item_id"], p["rep"])]
        r2 = by_key[("V2", p["model"], p["item_id"], p["rep"])]
        if r1["status"] != "ok" or r2["status"] != "ok":
            continue
        g1, g2 = g_by_call[r1["call_id"]], g_by_call[r2["call_id"]]
        cand.append({**p, "c1": r1["call_id"], "c2": r2["call_id"],
                     "fixed": [q for q in g1 if not g1[q] and g2.get(q)],
                     "both_all": all(g1.values()) and all(g2.values()) and r1["knowledge_pass"] and r2["knowledge_pass"],
                     "v2_miss": [q for q in g2 if not g2[q]]})
    chosen, lines, used_items = [], [], set()

    def take(pool, why, k=2):
        pool = sorted(pool, key=lambda c: (c["model"], c["item_id"], c["rep"]))
        got = []
        for m in MODELS:   # 尽量两个模型各一组、条目不重复
            pm = [c for c in pool if c["model"] == m and c["item_id"] not in used_items and c not in chosen]
            if pm and len(got) < k:
                got.append(rng.choice(pm))
                used_items.add(got[-1]["item_id"])
        rest = [c for c in pool if c not in chosen and c not in got]
        while len(got) < k and rest:
            c = rng.choice(rest)
            rest.remove(c)
            got.append(c)
        for c in got:
            chosen.append(c)
            lines.append(f"- 样例 {len(chosen)}：{c['item_id']}｜{c['model']}｜第 {c['rep']} 次（V1 call {c['c1']}，V2 call {c['c2']}）"
                         f"｜{why(c)}｜字数 {c['a']:,} → {c['b']:,}（比例 {c['ratio']:.2f}）")
        if len(got) < k:
            lines.append(f"- （这一类只找到 {len(got)} 组）")

    take([c for c in cand if c["fixed"]], lambda c: f"V1 没答上而 V2 答上：{', '.join(c['fixed'])}（候选 {sum(bool(x['fixed']) for x in cand)} 组）")
    take([c for c in cand if c["both_all"]], lambda c: f"两边都答上了全部卡点、知识都通过（候选 {sum(x['both_all'] for x in cand)} 组）")
    miss = [c for c in cand if c["v2_miss"] and c not in chosen]
    take(miss, lambda c: f"V2 没答上：{', '.join(c['v2_miss'])}（候选 {len(miss)} 组）", k=1)
    rest = sorted([c for c in cand if c not in chosen], key=lambda c: -c["ratio"])
    if rest:
        c = rest[0]
        chosen.append(c)
        lines.append(f"- 样例 {len(chosen)}：{c['item_id']}｜{c['model']}｜第 {c['rep']} 次（V1 call {c['c1']}，V2 call {c['c2']}）"
                     f"｜篇幅比例最大（其余配对里）｜字数 {c['a']:,} → {c['b']:,}（比例 {c['ratio']:.2f}）")
    return chosen, lines


def render_samples(samples, items_by_id, a, b, seed) -> str:
    from .run import build_user_message
    L = ["# V1 / V2 回答原文配对（30 条短题）", "",
         f"V1 = `{a}`，V2 = `{b}`。每组是同一条目、同一被测模型、同一重复序号的两份回答，原样照贴（Markdown 原文），"
         f"不附裁判结论。挑选依据见 `reports/short_v1_vs_v2__judge_v2.md` 第 10 节（随机种子 {seed}）。", ""]
    for k, c in enumerate(samples, 1):
        L += ["", "---", "", f"# 样例 {k}：{c['item_id']}｜{c['model']}｜第 {c['rep']} 次", "",
              "## 发给被测模型的用户消息", "", "````text", build_user_message(items_by_id[c["item_id"]]), "````", ""]
        for side, cid in (("V1", c["c1"]), ("V2", c["c2"])):
            L += ["---", "", f"## {side} 的回答（call {cid}）", "", f"**〔{side} 回答原文开始〕**", "",
                  c[f"text_{side}"], "", f"**〔{side} 回答原文结束〕**", ""]
    return "\n".join(L)


def consistency(R: Report, judge_name: str, prompt_sha: str, b: str, seed: int) -> list[str]:
    t, rows = R.q("V2 第二遍（repeat_judgments）与第一遍配对", f"""
SELECT r.id AS repeat_id, r.judge_run_id, r.sample_seed, r.call_id, r.item_id, r.course, c.model_name,
       r.status AS r_status, j.status AS j_status, j.knowledge_pass AS k1, r.knowledge_pass AS k2,
       j.parsed_json AS p1, r.parsed_json AS p2
FROM repeat_judgments r JOIN judgments j ON j.id = r.first_judgment_id
JOIN calls c ON c.id = r.call_id
WHERE c.skill_file = {_q(b)} AND r.judge_model_name = {_q(judge_name)} AND r.prompt_sha256 = {_q(prompt_sha)}
  AND r.sample_seed = {int(seed)}
ORDER BY r.call_id""")
    L = [f"### 裁判第二遍：V2 抽 20 份 [{t}]", ""]
    if not rows:
        return L + ["还没有第二遍的记录。", ""]
    both = [r for r in rows if r["r_status"] == "ok" and r["j_status"] == "ok"]
    L += [f"- 抽样：V2 第一遍 ok 的当前回答，按被测模型分层，每个模型 10 份；随机种子 {seed}；"
          f"judge_run {', '.join(sorted({r['judge_run_id'] for r in rows}))}。",
          f"- 抽中：" + "，".join(f"{m} {sum(r['model_name'] == m for r in rows)} 份" for m in MODELS)
          + f"；call_id {', '.join(str(r['call_id']) for r in rows)}。",
          f"- 第二遍 ok {sum(r['r_status'] == 'ok' for r in rows)}，待复核 {sum(r['r_status'] == 'needs_review' for r in rows)}，"
          f"失败 {sum(r['r_status'] == 'error' for r in rows)}；两遍都 ok、可以比较的 {len(both)} 份。", "",
          "| 模型 | 份数 | 知识判断一致 | 卡点一致率 | 步骤一致率 |", "|---|---|---|---|---|"]
    dis = []
    for m in MODELS + [None]:
        bs = [r for r in both if m is None or r["model_name"] == m]
        ka = sum(r["k1"] == r["k2"] for r in bs)
        res = {}
        for kind, idk, vk in (("gate", "question_id", "answered"), ("steps", "step_id", "done")):
            ag = tot = 0
            for r in bs:
                x = {u[idk]: u[vk] for u in json.loads(r["p1"])[kind]}
                y = {u[idk]: u[vk] for u in json.loads(r["p2"])[kind]}
                for k in x:
                    tot += 1
                    if x[k] == y.get(k):
                        ag += 1
                    elif m is None and kind == "gate":
                        dis.append(f"{r['model_name']}｜{r['item_id']}（call {r['call_id']}）{k}：第一遍 {x[k]}，第二遍 {y.get(k)}")
            res[kind] = (ag, tot)
        L.append(f"| {m or '合计'} | {len(bs)} | {ka}/{len(bs)} | {_pct(res['gate'][0] / res['gate'][1] if res['gate'][1] else None)}"
                 f"（{res['gate'][0]}/{res['gate'][1]}） | {_pct(res['steps'][0] / res['steps'][1] if res['steps'][1] else None)}"
                 f"（{res['steps'][0]}/{res['steps'][1]}） |")
    L += ["", "两遍不一致的卡点：" + ("无。" if not dis else ""), *[f"- {d}" for d in dis], ""]
    return L


def costs(R: Report, cfg: dict, jcfg: dict, b: str, items_rel: str, prompt_sha: str) -> list[str]:
    L = ["### 实际花费（这一轮：V2 的生成和判分）", "",
         "生成按 config 里各模型的标价算；“其中缓存”是接口报告的缓存输入 tokens。sol 的缓存单价 config 里没有，只给标价；"
         f"luna 缓存输入按 ${CACHE_PRICE['gpt-6-luna']}、裁判按 ${JUDGE_CACHE_PRICE} 计（config 注释里的价格）。"
         "生成算的是 V2 在这个条目文件上的全部调用记录（含失败的）。", "",
         "| 项目 | 记录数 | 输入 tokens（其中缓存） | 输出 tokens | 标价 | 计缓存折扣 |", "|---|---|---|---|---|---|"]
    tot_l = tot_d = 0.0
    t1, gen = R.q("V2 生成的用量（全部调用记录）", f"""
SELECT model_name, count(*) AS n, sum(coalesce(input_tokens, 0)) AS tin, sum(coalesce(output_tokens, 0)) AS tout,
       sum(coalesce(json_extract(usage_raw, '$.input_tokens_details.cached_tokens'), 0)) AS cached
FROM calls WHERE skill_file = {_q(b)} AND items_file = {_q(items_rel)} GROUP BY model_name""")
    for r in sorted(gen, key=lambda r: MODELS.index(r["model_name"]) if r["model_name"] in MODELS else 9):
        pr = find_model(cfg, r["model_name"]).get("price_per_1m_tokens") or {}
        lp = (r["tin"] * pr["input"] + r["tout"] * pr["output"]) / 1e6
        cp = CACHE_PRICE.get(r["model_name"])
        dp = ((r["tin"] - r["cached"]) * pr["input"] + r["cached"] * cp + r["tout"] * pr["output"]) / 1e6 if cp is not None else None
        tot_l += lp
        tot_d += dp if dp is not None else lp
        L.append(f"| 生成 general_v2 × {r['model_name']} | {r['n']} | {r['tin']:,}（{r['cached']:,}） | {r['tout']:,} | ${lp:.3f} | "
                 + (f"${dp:.3f}" if dp is not None else "—（按标价计入合计）") + " |")
    pr = jcfg.get("price_per_1m_tokens") or {}
    for label, table in (("裁判第一遍", "judgments"), ("裁判第二遍", "repeat_judgments")):
        _, rr = R.q(f"V2 的裁判用量：{table}", f"""
SELECT count(*) AS n, coalesce(sum(x.input_tokens), 0) AS tin, coalesce(sum(x.output_tokens), 0) AS tout,
       coalesce(sum(x.attempts), 0) AS att,
       coalesce(sum(json_extract(x.usage_raw, '$.input_tokens_details.cached_tokens')), 0) AS cached
FROM {table} x JOIN calls c ON c.id = x.call_id
WHERE c.skill_file = {_q(b)} AND c.items_file = {_q(items_rel)} AND x.prompt_sha256 = {_q(prompt_sha)}""")
        r = rr[0]
        lp = (r["tin"] * pr["input"] + r["tout"] * pr["output"]) / 1e6
        dp = ((r["tin"] - r["cached"]) * pr["input"] + r["cached"] * JUDGE_CACHE_PRICE + r["tout"] * pr["output"]) / 1e6
        tot_l += lp
        tot_d += dp
        L.append(f"| {label} | {r['n']} 份（{r['att']} 次调用） | {r['tin']:,}（{r['cached']:,}） | {r['tout']:,} | ${lp:.3f} | ${dp:.3f} |")
    L += [f"| **合计** | | | | **${tot_l:.3f}** | **${tot_d:.3f}** |", "",
          "裁判的“其中缓存”只计每条记录最后一次调用报告的缓存；重判过的记录前几次按标价，所以折扣价是上限。", ""]
    return L


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.v2report", description="通用 V1 对 V2 在 30 条短题上的对比报告")
    ap.add_argument("--a", default="skills/general_v1.md")
    ap.add_argument("--b", default="skills/general_v2.md")
    ap.add_argument("--items", default="data/items.jsonl")
    ap.add_argument("--judge-prompt", default="prompts/judge_v2.md")
    ap.add_argument("--repeat-seed", type=int, default=20261112, help="V2 第二遍抽样用的种子（报告只认这个种子的第二遍）")
    ap.add_argument("--sample-seed", type=int, default=20261112, help="挑给人读的样例用的种子")
    ap.add_argument("--out", default="reports")
    ap.add_argument("--samples-out", default="reports/short_v1_vs_v2_samples.md")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    args = ap.parse_args(argv)
    try:
        text, samples, out, sout = build(args)
    except UsageError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    out.write_text(text, encoding="utf-8")
    sout.write_text(samples, encoding="utf-8")
    print(f"已写入 {_rel(out)}、{_rel(sout)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
