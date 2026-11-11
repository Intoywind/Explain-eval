"""三组正式评分的汇总（第三份输入第 7 节）。

python -m src.summary --judge-prompt prompts/judge_v2.md --out reports/

- 组 = Skill 组 × 被测模型；Skill 组：skills/original_eval/ 下的按课程文件算一组，其余按文件名。
- 每份当前回答取该裁判、该版 prompt、判分清单与当前条目一致的最新一条裁判记录（judgments 表）；
  稳定性检查的第二遍在 repeat_judgments 表，验收样例在 fixture_judgments 表，都不进入这里的分数。
- 均值给两种：按回答平均（每份回答一票），按条目平均（条目内先平均，再在条目间平均，每条条目权重相同）。
  知识不通过的回答，卡点分、步骤分按 0 进入平均。待复核（needs_review）和失败的不计分，单独列出。
- 每个数字后的 [Qn] 指向文末附录里的 SQL，可以直接在 sqlite3 里对 results/eval.db 运行
  （先跑过一次本脚本，items_snapshot 表才是当前条目）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .judge import ROOT, db_path_from_config, judge_model_cfg, load_items, load_prompt
from .report import Report, _f, _md, _q, snapshot_items
from .run import UsageError, _rel, load_config

GROUP_ORDER = ["general_v1 × gpt-6.1-sol", "original_eval × gpt-6.1-sol",
               "general_v1 × gpt-6-luna", "original_eval × gpt-6-luna"]
SHORT = {"general_v1 × gpt-6.1-sol": "通用·sol", "original_eval × gpt-6.1-sol": "原版·sol",
         "general_v1 × gpt-6-luna": "通用·luna", "original_eval × gpt-6-luna": "原版·luna"}
SKILLS = ["general_v1", "original_eval"]
MODELS = ["gpt-6.1-sol", "gpt-6-luna"]
EPS = 1e-9

# COMP original_eval 关键词：向用户要文件路径 / 写了“待原题补齐”“非历年真题”
ASK_PATH_RE = r"(文件|PDF|pdf|本地)?路径|上传|请(你)?(提供|发送|发来|给出|贴出)[^。\n]{0,12}(文件|PDF|pdf|原题|题目|试卷)"
KEYWORDS = ["待原题补齐", "非历年真题"]


def _pct(v):
    return "—" if v is None else f"{100 * v:.1f}%"


def group_sql(judge_name: str, prompt_sha: str) -> str:
    return f"""WITH sel AS (  -- 每份当前回答 × 该裁判、该版 prompt、判分清单一致的最新一条裁判记录（可能没有）
  SELECT CASE WHEN c.skill_file LIKE 'skills/original_eval/%' THEN 'original_eval'
              WHEN c.skill_file LIKE 'skills/original/%' THEN 'original'
              ELSE replace(replace(c.skill_file, 'skills/', ''), '.md', '') END || ' × ' || c.model_name AS grp,
         c.id AS call_id, c.item_id, c.repeat_idx, s.course, s.reader,
         j.id AS judgment_id, j.status, j.knowledge_pass, j.incomplete, j.gate_num, j.gate_den,
         j.step_num, j.step_den, j.gate_all, j.error, j.parsed_json, j.flags
  FROM current_calls c
  JOIN items_snapshot s ON s.item_id = c.item_id
  LEFT JOIN judgments j ON j.id = (
       SELECT max(x.id) FROM judgments x
       WHERE x.call_id = c.id AND x.judge_model_name = {_q(judge_name)}
         AND x.prompt_sha256 = {_q(prompt_sha)} AND x.rubric_sha256 = s.rubric_sha256)
)"""


def build(args) -> tuple[str, Path]:
    cfg = load_config(Path(args.config))
    jcfg = judge_model_cfg(cfg)
    judge_name = jcfg["name"]
    prompt = load_prompt(Path(args.judge_prompt))
    items_by_id, items_rel = load_items(Path(args.items), False)
    conn = db.connect(db_path_from_config(cfg))
    snapshot_items(conn, items_by_id, items_rel)
    R = Report(conn)
    SEL = group_sql(judge_name, prompt.sha256)
    gk = lambda g: GROUP_ORDER.index(g) if g in GROUP_ORDER else 99

    L = [f"# 三组正式评分汇总（{prompt.rel}）", "",
         f"- 裁判：{judge_name}（{jcfg['model_id']}），prompt `{prompt.rel}`（sha256 {prompt.sha256[:12]}…）；条目文件 `{items_rel}`",
         f"- 生成时间：{datetime.now(timezone.utc).isoformat(timespec='seconds')}",
         "- 组 = Skill 组 × 被测模型。知识不通过的回答卡点分、步骤分按 0 计；待复核、失败的不计分，单独列出。",
         "- 均值给两种：按回答平均；按条目平均（条目内先平均，再在条目间平均）。两者只在有回答不计分时才可能不同。",
         "- 每个数字后的 [Qn] 指向文末附录的 SQL。", ""]

    # 1. 份数
    t1, cnt = R.q("各组份数：当前回答、ok、待复核、失败、未评", SEL + """
SELECT grp, count(*) AS n, coalesce(sum(status = 'ok'), 0) AS n_ok,
       coalesce(sum(status = 'needs_review'), 0) AS n_review, coalesce(sum(status = 'error'), 0) AS n_error,
       sum(judgment_id IS NULL) AS n_unjudged
FROM sel GROUP BY grp""")
    cnt.sort(key=lambda r: gk(r["grp"]))
    L += [f"## 1. 份数 [{t1}]", "", "| 组 | 当前回答 | ok | 待复核 | 失败 | 未评 |", "|---|---|---|---|---|---|"]
    L += [f"| {r['grp']} | {r['n']} | {r['n_ok']} | {r['n_review']} | {r['n_error']} | {r['n_unjudged']} |" for r in cnt]
    L.append("")

    # 2. 主要结果
    t2, main = R.q("各组主要结果（按回答平均，只算 ok）", SEL + """
SELECT grp, count(*) AS n_ok,
       avg(knowledge_pass) AS k_pass, sum(knowledge_pass = 0) AS n_k_fail,
       avg(incomplete) AS incomplete, sum(incomplete) AS n_incomplete,
       avg(1.0 * gate_num / gate_den) AS gate, avg(1.0 * step_num / step_den) AS step,
       avg(gate_all) AS gate_all
FROM sel WHERE status = 'ok' GROUP BY grp""")
    t3, main_i = R.q("各组卡点分、步骤分（按条目平均，只算 ok）", SEL + """,
per_item AS (
  SELECT grp, item_id, avg(1.0 * gate_num / gate_den) AS gate, avg(1.0 * step_num / step_den) AS step,
         avg(knowledge_pass) AS k_pass, avg(incomplete) AS incomplete
  FROM sel WHERE status = 'ok' GROUP BY grp, item_id)
SELECT grp, count(*) AS n_items, avg(k_pass) AS k_pass, avg(incomplete) AS incomplete,
       avg(gate) AS gate, avg(step) AS step
FROM per_item GROUP BY grp""")
    mi = {r["grp"]: r for r in main_i}
    main.sort(key=lambda r: gk(r["grp"]))
    L += [f"## 2. 主要结果 [{t2}] [{t3}]", "",
          "| 组 | ok 份数 | 知识通过率 | 没答全比例 | 卡点分均值（按回答） | 卡点分均值（按条目） | 步骤分均值（按回答） | 步骤分均值（按条目） | 卡点全答上比例 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in main:
        i = mi.get(r["grp"], {})
        L.append(f"| {r['grp']} | {r['n_ok']} | {_pct(r['k_pass'])}（不通过 {r['n_k_fail']} 份） "
                 f"| {_pct(r['incomplete'])}（{r['n_incomplete']} 份） | {_f(r['gate'])} | {_f(i.get('gate'))} "
                 f"| {_f(r['step'])} | {_f(i.get('step'))} | {_pct(r['gate_all'])} |")
    L += ["", "卡点全答上 = 知识通过且所有卡点问题都答上。", ""]

    # 2b. 2×2
    by_g = {r["grp"]: r for r in main}
    L += [f"## 2b. 两份 Skill × 两档模型 [{t2}]", "",
          "每格：卡点分均值 / 步骤分均值 / 卡点全答上比例（按回答平均，只算 ok；所有回答都 ok 时与按条目平均相同）。", "",
          "| Skill \\ 模型 | " + " | ".join(MODELS) + " |", "|---|" + "---|" * len(MODELS)]
    for sk in SKILLS:
        cells = []
        for m in MODELS:
            r = by_g.get(f"{sk} × {m}")
            cells.append("—" if r is None else f"{_f(r['gate'])} / {_f(r['step'])} / {_pct(r['gate_all'])}")
        L.append(f"| {sk} | " + " | ".join(cells) + " |")
    L.append("")

    # 2c. 同一模型下两份 Skill 的逐条目比较
    t2c, pi2 = R.q("逐条目 × 组的卡点分、步骤分（条目内平均，只算 ok）", SEL + """
SELECT item_id, grp, avg(1.0 * gate_num / gate_den) AS gate, avg(1.0 * step_num / step_den) AS step
FROM sel WHERE status = 'ok' GROUP BY item_id, grp""")
    pm = {(r["item_id"], r["grp"]): r for r in pi2}
    L += [f"## 2c. 同一模型下两份 Skill 的逐条目比较（original_eval 相对 general_v1）[{t2c}]", "",
          "每条条目先在条目内对 3 次重复取平均，再比较 original_eval 和 general_v1；两边都有结果的条目才计入。", "",
          "| 模型 | 指标 | 条目数 | original_eval 更高 | 持平 | original_eval 更低 | 平均差 |", "|---|---|---|---|---|---|---|"]
    for m in MODELS:
        for metric, label in (("gate", "卡点分"), ("step", "步骤分（附）")):
            diffs = []
            for iid in sorted(items_by_id):
                a, b = pm.get((iid, f"general_v1 × {m}")), pm.get((iid, f"original_eval × {m}"))
                if a and b:
                    diffs.append(b[metric] - a[metric])
            if not diffs:
                L.append(f"| {m} | {label} | 0 | — | — | — | — |")
                continue
            up = sum(d > EPS for d in diffs)
            dn = sum(d < -EPS for d in diffs)
            L.append(f"| {m} | {label} | {len(diffs)} | {up} | {len(diffs) - up - dn} | {dn} | {sum(diffs) / len(diffs):+.3f} |")
    L.append("")

    # 3. 分布
    t4, gd = R.q("卡点分分布（每份 ok 回答的 gate_num/gate_den）", SEL + """
SELECT grp, round(1.0 * gate_num / gate_den, 3) AS v, sum(knowledge_pass = 0) AS n_k_fail, count(*) AS n
FROM sel WHERE status = 'ok' GROUP BY grp, v ORDER BY grp, v""")
    t5, sd = R.q("步骤分分布（每份 ok 回答的 step_num/step_den，分 5 档）", SEL + """
SELECT grp, CASE WHEN step_num = 0 THEN '0'
                 WHEN 1.0 * step_num / step_den < 0.5 THEN '(0, 0.5)'
                 WHEN 1.0 * step_num / step_den < 0.8 THEN '[0.5, 0.8)'
                 WHEN step_num < step_den THEN '[0.8, 1)'
                 ELSE '1' END AS bucket,
       sum(knowledge_pass = 0) AS n_k_fail, count(*) AS n
FROM sel WHERE status = 'ok' GROUP BY grp, bucket""")
    gvals = sorted({r["v"] for r in gd})
    gmap = {(r["grp"], r["v"]): r for r in gd}
    groups = [r["grp"] for r in cnt]   # 所有有当前回答的组，按 GROUP_ORDER 排
    L += [f"## 3. 分布", "", f"**卡点分**（份数；括号里是其中知识不通过、按 0 计的份数）[{t4}]", "",
          "| 组 | " + " | ".join(f"{v:g}" for v in gvals) + " |", "|---|" + "---|" * len(gvals)]
    for g in groups:
        cells = []
        for v in gvals:
            r = gmap.get((g, v))
            cells.append("0" if r is None else f"{r['n']}" + (f"（{r['n_k_fail']}）" if r["n_k_fail"] else ""))
        L.append(f"| {g} | " + " | ".join(cells) + " |")
    buckets = ["0", "(0, 0.5)", "[0.5, 0.8)", "[0.8, 1)", "1"]
    smap = {(r["grp"], r["bucket"]): r for r in sd}
    L += ["", f"**步骤分**（份数；括号里是其中知识不通过、按 0 计的份数）[{t5}]", "",
          "| 组 | " + " | ".join(buckets) + " |", "|---|" + "---|" * len(buckets)]
    for g in groups:
        cells = []
        for b in buckets:
            r = smap.get((g, b))
            cells.append("0" if r is None else f"{r['n']}" + (f"（{r['n_k_fail']}）" if r["n_k_fail"] else ""))
        L.append(f"| {g} | " + " | ".join(cells) + " |")
    L.append("")

    # 4. 逐条目
    t6, pi = R.q("逐条目 × 组（只算 ok）", SEL + """
SELECT item_id, grp, count(*) AS n_ok, sum(knowledge_pass) AS n_k_pass, sum(incomplete) AS n_incomplete,
       avg(1.0 * gate_num / gate_den) AS gate, avg(1.0 * step_num / step_den) AS step
FROM sel WHERE status = 'ok' GROUP BY item_id, grp ORDER BY item_id""")
    pmap = {(r["item_id"], r["grp"]): r for r in pi}
    short = SHORT
    L += [f"## 4. 逐条目三组对比 [{t6}]", "",
          "每格：知识通过份数/ok 份数 · 卡点分 · 步骤分（条目内几次重复的平均）。“没答全”列出该组 incomplete 的份数。"
          "组名缩写：" + "，".join(f"{v} = {k}" for k, v in short.items()) + "。", "",
          "| 条目 | " + " | ".join(short.get(g, g) for g in groups) + " | 没答全（" + "/".join(short.get(g, g) for g in groups) + "） |",
          "|---|" + "---|" * (len(groups) + 1)]
    for iid in sorted(items_by_id):
        cells, inc = [], []
        for g in groups:
            r = pmap.get((iid, g))
            if r is None:
                cells.append("—")
                inc.append("—")
            else:
                cells.append(f"{r['n_k_pass']}/{r['n_ok']} · {r['gate']:.2f} · {r['step']:.2f}")
                inc.append(str(r["n_incomplete"]))
        L.append(f"| {iid} | " + " | ".join(cells) + " | " + "/".join(inc) + " |")
    L.append("")

    # 5. 知识不通过清单
    t7, kf = R.q("知识不通过的回答", SEL + """
SELECT grp, item_id, call_id, repeat_idx,
       json_extract(parsed_json, '$.knowledge_error.which') AS which,
       json_extract(parsed_json, '$.knowledge_error.quotes') AS quotes
FROM sel WHERE status = 'ok' AND knowledge_pass = 0 ORDER BY item_id, grp, repeat_idx""")
    L += [f"## 5. 知识不通过的回答（{len(kf)} 份）[{t7}]", "", "| 组 | 条目 | call | 第几次 | which | 引句 |", "|---|---|---|---|---|---|"]
    for r in kf:
        L.append(f"| {r['grp']} | {r['item_id']} | {r['call_id']} | {r['repeat_idx']} | "
                 f"{_md('；'.join(json.loads(r['which'] or '[]')))} | {_md(' / '.join(json.loads(r['quotes'] or '[]')))[:200]} |")
    L.append("")

    # 6. 待复核 / 失败
    t8, nr = R.q("待复核（needs_review）和失败（error）的回答", SEL + """
SELECT grp, item_id, call_id, repeat_idx, status, judgment_id, error
FROM sel WHERE status IN ('needs_review', 'error') OR judgment_id IS NULL ORDER BY status, item_id, grp""")
    L += [f"## 6. 待复核（needs_review）和失败 [{t8}]", ""]
    for g in groups:
        L.append(f"- {g}：待复核 {sum(r['grp'] == g and r['status'] == 'needs_review' for r in nr)} 份，"
                 f"失败 {sum(r['grp'] == g and r['status'] == 'error' for r in nr)} 份，"
                 f"未评 {sum(r['grp'] == g and r['judgment_id'] is None for r in nr)} 份")
    if nr:
        L += ["", "| 组 | 条目 | call | 第几次 | 状态 | judgment | 原因 |", "|---|---|---|---|---|---|---|"]
        L += [f"| {r['grp']} | {r['item_id']} | {r['call_id']} | {r['repeat_idx']} | {r['status'] or '未评'} | "
              f"{r['judgment_id'] or '—'} | {_md(r['error'])} |" for r in nr]
    L.append("")

    # 7. 清单外
    t9, notes = R.q("“清单外”备注（knowledge_error.note 或 incomplete.note 以“清单外”开头）", SEL + """
SELECT grp, item_id, call_id, repeat_idx, status,
       json_extract(parsed_json, '$.knowledge_error.note') AS k_note,
       json_extract(parsed_json, '$.incomplete.note') AS i_note
FROM sel WHERE status IN ('ok', 'needs_review')
  AND (ltrim(coalesce(json_extract(parsed_json, '$.knowledge_error.note'), '')) LIKE '清单外%'
    OR ltrim(coalesce(json_extract(parsed_json, '$.incomplete.note'), '')) LIKE '清单外%')
ORDER BY item_id, grp, repeat_idx""")
    L += [f"## 7. “清单外”备注（{len(notes)} 份）[{t9}]", "",
          "裁判以“清单外：”开头记下的清单以外的事实错误。不触发知识错误，不影响分数，供复核。", ""]
    for g in groups:
        L.append(f"- {g}：{sum(r['grp'] == g for r in notes)} 份")
    if notes:
        L += ["", "| 组 | 条目 | call | 第几次 | 备注 |", "|---|---|---|---|---|"]
        for r in notes:
            txt = " ".join(n for n in (r["k_note"], r["i_note"]) if n and n.strip().startswith("清单外"))
            L.append(f"| {r['grp']} | {r['item_id']} | {r['call_id']} | {r['repeat_idx']} | {_md(txt)} |")
    L.append("")

    # 8. gaps
    t10, gs = R.q("gaps 的 severity 分布（只算 ok 回答）", SEL + """
SELECT sel.grp, g.severity, g.subtype, g.quote_valid, count(*) AS n
FROM sel JOIN judge_gaps g ON g.judgment_id = sel.judgment_id
WHERE sel.status = 'ok' GROUP BY sel.grp, g.severity, g.subtype, g.quote_valid""")
    sev = ["读者没法往下读", "只是不顺"]
    subs = sorted({r["subtype"] for r in gs})
    nok = {r["grp"]: r["n_ok"] for r in main}
    L += [f"## 8. gaps 的 severity 分布 [{t10}]", "",
          "条数（引句有效的；括号里是引句作废、不计入的条数）。每份平均 = 引句有效的条数 / ok 份数。", "",
          "| 组 | " + " | ".join(sev) + " | 合计 | 每份平均 |", "|---|---|---|---|---|"]
    for g in groups:
        cells, tot = [], 0
        for s_ in sev:
            v = sum(r["n"] for r in gs if r["grp"] == g and r["severity"] == s_ and r["quote_valid"])
            iv = sum(r["n"] for r in gs if r["grp"] == g and r["severity"] == s_ and not r["quote_valid"])
            tot += v
            cells.append(f"{v}" + (f"（{iv}）" if iv else ""))
        L.append(f"| {g} | " + " | ".join(cells) + f" | {tot} | " + (f"{tot / nok[g]:.2f}" if nok.get(g) else "—") + " |")
    L += ["", "按类型（引句有效的；读者没法往下读 / 只是不顺）：", "",
          "| 组 | " + " | ".join(subs) + " |", "|---|" + "---|" * len(subs)]
    for g in groups:
        cells = []
        for sb in subs:
            a = sum(r["n"] for r in gs if r["grp"] == g and r["subtype"] == sb and r["severity"] == sev[0] and r["quote_valid"])
            b = sum(r["n"] for r in gs if r["grp"] == g and r["subtype"] == sb and r["severity"] == sev[1] and r["quote_valid"])
            cells.append(f"{a} / {b}")
        L.append(f"| {g} | " + " | ".join(cells) + " |")
    L.append("")

    # 8b. ECON-003 重判前后
    L += rejudge_section(R, judge_name, prompt.sha256, "ECON-003-%")

    # 9. 稳定性
    L += consistency_section(R, judge_name, prompt.sha256)

    # 10. COMP original_eval 关键词
    L += keyword_section(R)

    # 11. 花费
    L += cost_section(R, jcfg, prompt.sha256)

    # 附录
    L += ["## 附录：SQL", ""]
    for k, (title, sql) in enumerate(R.sqls, 1):
        L += [f"**Q{k}. {title}**", "", "```sql", sql, "```", ""]
    conn.close()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"summary__{Path(prompt.rel).stem}.md"
    return "\n".join(L) + "\n", out


def rejudge_section(R: Report, judge_name: str, prompt_sha: str, like: str) -> list[str]:
    t, rows = R.q("条目改动前后的裁判结果：同一份当前回答，旧判分清单的最新 ok 记录 vs 当前判分清单的最新 ok 记录", f"""
SELECT CASE WHEN c.skill_file LIKE 'skills/original_eval/%' THEN 'original_eval'
            ELSE replace(replace(c.skill_file, 'skills/', ''), '.md', '') END || ' × ' || c.model_name AS grp,
       c.id AS call_id, c.item_id, c.repeat_idx,
       o.id AS old_id, o.knowledge_pass AS k_old, o.gate_num AS g_old, o.gate_den AS gd_old,
       o.step_num AS s_old, o.step_den AS sd_old, json_extract(o.parsed_json, '$.knowledge_error.which') AS which_old,
       n.id AS new_id, n.knowledge_pass AS k_new, n.gate_num AS g_new, n.gate_den AS gd_new,
       n.step_num AS s_new, n.step_den AS sd_new, json_extract(n.parsed_json, '$.knowledge_error.which') AS which_new,
       json_extract(n.parsed_json, '$.knowledge_error.note') AS note_new
FROM current_calls c
JOIN items_snapshot s ON s.item_id = c.item_id
LEFT JOIN judgments n ON n.id = (
     SELECT max(x.id) FROM judgments x WHERE x.call_id = c.id AND x.status = 'ok'
       AND x.judge_model_name = {_q(judge_name)} AND x.prompt_sha256 = {_q(prompt_sha)} AND x.rubric_sha256 = s.rubric_sha256)
LEFT JOIN judgments o ON o.id = (
     SELECT max(x.id) FROM judgments x WHERE x.call_id = c.id AND x.status = 'ok'
       AND x.judge_model_name = {_q(judge_name)} AND x.prompt_sha256 = {_q(prompt_sha)} AND x.rubric_sha256 != s.rubric_sha256)
WHERE c.item_id LIKE {_q(like)}
ORDER BY c.item_id, grp, c.repeat_idx""")
    title = like.rstrip("-%")
    both = [r for r in rows if r["old_id"] and r["new_id"]]
    kchg = [r for r in both if r["k_old"] != r["k_new"]]
    L = [f"## 8b. {title} 按新条目重判前后 [{t}]", "",
         f"- {title} 当前回答 {len(rows)} 份；按新条目判过的 {sum(bool(r['new_id']) for r in rows)} 份；"
         f"有旧判分可比的 {len(both)} 份（没有旧判分的是条目改动后才生成的回答）。旧判分保留在库里，不进上面任何统计。",
         f"- 知识判断变了的 {len(kchg)} 份；卡点分变了的 {sum((r['g_old'], r['gd_old']) != (r['g_new'], r['gd_new']) for r in both)} 份；"
         f"步骤分变了的 {sum((r['s_old'], r['sd_old']) != (r['s_new'], r['sd_new']) for r in both)} 份。", "",
         "| 组 | 条目 | call | 第几次 | 知识（旧 → 新） | 卡点分（旧 → 新） | 步骤分（旧 → 新） | 旧 which |", "|---|---|---|---|---|---|---|---|"]
    kp = lambda v: "—" if v is None else ("通过" if v else "**不通过**")
    for r in rows:
        fr = lambda a, b, ok: f"{a}/{b}" if ok else "—"
        k = f"{kp(r['k_old'])} → {kp(r['k_new'])}" + (" ⚑" if r["old_id"] and r["new_id"] and r["k_old"] != r["k_new"] else "")
        g = f"{fr(r['g_old'], r['gd_old'], r['old_id'])} → {fr(r['g_new'], r['gd_new'], r['new_id'])}"
        st = f"{fr(r['s_old'], r['sd_old'], r['old_id'])} → {fr(r['s_new'], r['sd_new'], r['new_id'])}"
        L.append(f"| {r['grp']} | {r['item_id']} | {r['call_id']} | {r['repeat_idx']} | {k} | {g} | {st} | "
                 f"{_md('；'.join(json.loads(r['which_old'] or '[]')))} |")
    L += ["", "⚑ = 知识判断变了。", ""]
    return L


def consistency_section(R: Report, judge_name: str, prompt_sha: str) -> list[str]:
    t, rows = R.q("稳定性检查：第二遍（repeat_judgments）与第一遍（judgments）配对", f"""
SELECT r.id AS repeat_id, r.judge_run_id, r.sample_seed, r.call_id, r.item_id, r.course, r.status AS r_status,
       j.id AS first_id, j.status AS j_status,
       j.knowledge_pass AS k1, r.knowledge_pass AS k2, j.incomplete AS i1, r.incomplete AS i2,
       j.gate_num AS g1, r.gate_num AS g2, j.gate_den AS gden, j.step_num AS s1, r.step_num AS s2, j.step_den AS sden,
       j.parsed_json AS p1, r.parsed_json AS p2
FROM repeat_judgments r JOIN judgments j ON j.id = r.first_judgment_id
JOIN items_snapshot s ON s.item_id = r.item_id   -- 只算当前条目文件里的条目（长请求等另一套条目不算）
WHERE r.judge_model_name = {_q(judge_name)} AND r.prompt_sha256 = {_q(prompt_sha)}
ORDER BY r.call_id""")
    L = [f"## 9. 裁判稳定性：抽 30 份判第二遍 [{t}]", ""]
    if not rows:
        return L + ["还没有第二遍的记录。", ""]
    seeds = sorted({r["sample_seed"] for r in rows})
    runs = sorted({r["judge_run_id"] for r in rows})
    both = [r for r in rows if r["r_status"] == "ok" and r["j_status"] == "ok"]
    L += [f"- 抽样：第一遍 ok 的当前回答，按课程分层，每门课 10 份；随机种子 {', '.join(map(str, seeds))}；"
          f"judge_run {', '.join(runs)}。",
          f"- 第二遍 {len(rows)} 份：ok {sum(r['r_status'] == 'ok' for r in rows)}，"
          f"待复核 {sum(r['r_status'] == 'needs_review' for r in rows)}，失败 {sum(r['r_status'] == 'error' for r in rows)}；"
          f"两遍都 ok、可以比较的 {len(both)} 份。", ""]

    def per_unit(kind, idk, vk):
        agree = tot = 0
        dis = []
        for r in both:
            a = {x[idk]: x[vk] for x in json.loads(r["p1"])[kind]}
            b = {x[idk]: x[vk] for x in json.loads(r["p2"])[kind]}
            for k in a:
                tot += 1
                if a[k] == b.get(k):
                    agree += 1
                else:
                    dis.append((r["call_id"], r["item_id"], k, a[k], b.get(k)))
        return agree, tot, dis

    def kappa(pairs):
        n = len(pairs)
        if not n:
            return None
        po = sum(a == b for a, b in pairs) / n
        pa = sum(a for a, _ in pairs) / n
        pb = sum(b for _, b in pairs) / n
        pe = pa * pb + (1 - pa) * (1 - pb)
        return None if pe == 1 else (po - pe) / (1 - pe)

    ga, gt, gdis = per_unit("gate", "question_id", "answered")
    sa, st, sdis = per_unit("steps", "step_id", "done")
    k_pairs = [(r["k1"], r["k2"]) for r in both]
    i_pairs = [(r["i1"], r["i2"]) for r in both]
    g_pairs, s_pairs = [], []
    for r in both:
        a = {x["question_id"]: x["answered"] for x in json.loads(r["p1"])["gate"]}
        b = {x["question_id"]: x["answered"] for x in json.loads(r["p2"])["gate"]}
        g_pairs += [(a[k], b[k]) for k in a]
        a = {x["step_id"]: x["done"] for x in json.loads(r["p1"])["steps"]}
        b = {x["step_id"]: x["done"] for x in json.loads(r["p2"])["steps"]}
        s_pairs += [(a[k], b[k]) for k in a]
    n = len(both)
    kag = sum(a == b for a, b in k_pairs)
    iag = sum(a == b for a, b in i_pairs)
    g_same = sum(r["g1"] == r["g2"] for r in both)
    s_same = sum(r["s1"] == r["s2"] for r in both)
    kp = lambda v: "—" if v is None else f"{v:.2f}"
    L += ["| 项目 | 比较单位 | 一致 / 总数 | 一致率 | Cohen's kappa |", "|---|---|---|---|---|",
          f"| 知识（通过 / 不通过） | 每份回答 | {kag} / {n} | {_pct(kag / n if n else None)} | {kp(kappa(k_pairs))} |",
          f"| 卡点（答上 / 没答上） | 每个卡点问题 | {ga} / {gt} | {_pct(ga / gt if gt else None)} | {kp(kappa(g_pairs))} |",
          f"| 步骤（踩中 / 没踩中） | 每个推荐步骤 | {sa} / {st} | {_pct(sa / st if st else None)} | {kp(kappa(s_pairs))} |",
          f"| 卡点分完全相同 | 每份回答 | {g_same} / {n} | {_pct(g_same / n if n else None)} | |",
          f"| 步骤分完全相同 | 每份回答 | {s_same} / {n} | {_pct(s_same / n if n else None)} | |",
          f"| 没答全（附带） | 每份回答 | {iag} / {n} | {_pct(iag / n if n else None)} | {kp(kappa(i_pairs))} |", "",
          "卡点、步骤按第一遍判过的每个问题、每个步骤逐个比较（裁判看到的是同一份讲解、同一份请求）。"
          "kappa 在两遍几乎全是同一个值时会很低或算不出，要和一致率一起看。", ""]
    by_c = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    for r in both:
        c = by_c[r["course"]]
        c[0] += r["k1"] == r["k2"]
        c[1] += 1
    for kind, dis_all, idk, vk in (("gate", gdis, "question_id", "answered"), ("steps", sdis, "step_id", "done")):
        for r in both:
            a = {x[idk]: x[vk] for x in json.loads(r["p1"])[kind]}
            b = {x[idk]: x[vk] for x in json.loads(r["p2"])[kind]}
            off = 2 if kind == "gate" else 4
            by_c[r["course"]][off] += sum(a[k] == b.get(k) for k in a)
            by_c[r["course"]][off + 1] += len(a)
    L += ["按课程：", "", "| 课程 | 份数 | 知识一致 | 卡点一致 | 步骤一致 |", "|---|---|---|---|---|"]
    for c in sorted(by_c):
        v = by_c[c]
        L.append(f"| {c} | {v[1]} | {v[0]}/{v[1]} | {v[2]}/{v[3]} | {v[4]}/{v[5]} |")
    kdis = [(r["call_id"], r["item_id"], "知识", r["k1"], r["k2"]) for r in both if r["k1"] != r["k2"]]
    alld = kdis + gdis + sdis
    if alld:
        L += ["", f"两遍不一致的地方（{len(alld)} 处；1 = 通过/答上/踩中）：", "",
              "| call | 条目 | 项 | 第一遍 | 第二遍 |", "|---|---|---|---|---|"]
        L += [f"| {c} | {i} | {k} | {a} | {b} |" for c, i, k, a, b in sorted(alld)]
    L.append("")
    return L


def keyword_section(R: Report) -> list[str]:
    t, rows = R.q("COMP 的 original_eval 当前回答（关键词在 Python 里匹配）", """
SELECT c.id AS call_id, c.item_id, c.repeat_idx, c.skill_file, c.response_text
FROM current_calls c
WHERE c.skill_file LIKE 'skills/original_eval/%' AND c.item_id LIKE 'COMP-%'
ORDER BY c.item_id, c.repeat_idx""")
    L = [f"## 10. COMP 的 original_eval 回答：要文件路径、“待原题补齐”“非历年真题” [{t}]", "",
         f"COMP 的 original_eval 当前回答共 {len(rows)} 份。“要文件路径”按正则 `{ASK_PATH_RE}` 匹配，命中的原句列在下面供核对；"
         "另两项是原文逐字查找。", ""]
    hits = defaultdict(list)
    for r in rows:
        txt = r["response_text"] or ""
        for m in re.finditer(ASK_PATH_RE, txt):
            s, e = max(0, m.start() - 40), min(len(txt), m.end() + 40)
            hits["要文件路径"].append((r, txt[s:e]))
        for kw in KEYWORDS:
            for m in re.finditer(re.escape(kw), txt):
                s, e = max(0, m.start() - 40), min(len(txt), m.end() + 40)
                hits[kw].append((r, txt[s:e]))
    L += ["| 项目 | 份数 | 次数 | 命中的回答（call） |", "|---|---|---|---|"]
    for k in ["要文件路径", *KEYWORDS]:
        calls = sorted({r["call_id"] for r, _ in hits[k]})
        L.append(f"| {k} | {len(calls)} | {len(hits[k])} | {', '.join(map(str, calls)) or '—'} |")
    any_hit = [(k, r, ctx) for k in hits for r, ctx in hits[k]]
    if any_hit:
        L += ["", "| 项目 | call | 条目 | 上下文 |", "|---|---|---|---|"]
        L += [f"| {k} | {r['call_id']} | {r['item_id']} | {_md(ctx)} |" for k, r, ctx in any_hit]
    L.append("")
    return L


def cost_section(R: Report, jcfg: dict, prompt_sha: str) -> list[str]:
    price = jcfg.get("price_per_1m_tokens") or {}
    pin, pout = price.get("input"), price.get("output")
    pcache = price.get("cached_input", 0.05)
    t, rows = R.q("裁判花费：按 judge_run 汇总（这版 prompt 的正式评分和第二遍）", f"""
SELECT jr.judge_run_id, coalesce(jr.purpose, 'main') AS purpose, jr.started_at, jr.finished_at,
       count(x.id) AS n_rows, sum(x.input_tokens) AS tin, sum(x.output_tokens) AS tout,
       sum(CASE WHEN x.attempts = 1 THEN 0 ELSE 1 END) AS n_multi,
       sum(coalesce(json_extract(x.usage_raw, '$.input_tokens_details.cached_tokens'), 0)) AS cached_last
FROM judge_runs jr
JOIN (SELECT id, judge_run_id, item_id, input_tokens, output_tokens, attempts, usage_raw FROM judgments
      UNION ALL
      SELECT id, judge_run_id, item_id, input_tokens, output_tokens, attempts, usage_raw FROM repeat_judgments) x
  ON x.judge_run_id = jr.judge_run_id
JOIN items_snapshot s ON s.item_id = x.item_id   -- 只算当前条目文件里的条目
WHERE jr.prompt_sha256 = {_q(prompt_sha)}
GROUP BY jr.judge_run_id ORDER BY jr.started_at""")
    L = [f"## 11. 实际花费 [{t}]", "",
         f"单价（每百万 tokens）：输入 ${pin}，缓存输入 ${pcache}，输出 ${pout}。"
         "“计缓存折扣”只用每条记录最后一次调用报告的缓存 tokens；重判过的记录前几次调用的缓存不知道，按标价算，所以是上限。", "",
         "| judge_run | 用途 | 记录数 | 其中调用多次的 | 输入 tokens | 其中缓存（最后一次） | 输出 tokens | 标价 | 计缓存折扣 |",
         "|---|---|---|---|---|---|---|---|---|"]
    tot = [0, 0, 0, 0.0, 0.0]
    for r in rows:
        tin, tout, cached = r["tin"] or 0, r["tout"] or 0, r["cached_last"] or 0
        list_c = (tin * pin + tout * pout) / 1e6 if pin is not None else None
        disc_c = ((tin - cached) * pin + cached * pcache + tout * pout) / 1e6 if pin is not None else None
        tot[0] += tin; tot[1] += cached; tot[2] += tout; tot[3] += list_c or 0; tot[4] += disc_c or 0
        L.append(f"| {r['judge_run_id']} | {r['purpose']} | {r['n_rows']} | {r['n_multi']} | {tin:,} | {cached:,} | {tout:,} "
                 f"| ${list_c:.3f} | ${disc_c:.3f} |")
    L.append(f"| **合计** | | | | {tot[0]:,} | {tot[1]:,} | {tot[2]:,} | **${tot[3]:.3f}** | **${tot[4]:.3f}** |")
    L += ["", "验收样例（fixture_judgments）不在这张表里，第 6 节已单独报过。", ""]
    return L


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.summary", description="三组正式评分的汇总")
    ap.add_argument("--judge-prompt", default="prompts/judge_v2.md")
    ap.add_argument("--items", default="data/items.jsonl")
    ap.add_argument("--out", default="reports")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    args = ap.parse_args(argv)
    try:
        text, out = build(args)
    except UsageError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    out.write_text(text, encoding="utf-8")
    print(f"已写入 {_rel(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
