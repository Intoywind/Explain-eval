"""两份 Skill 的比较报告。

python -m src.report --a skills/general_v1.md --b original_eval --model gpt-6.1-sol --judge-prompt prompts/judge_v1.md --out reports/

- 只比较两份 Skill 都有裁判结果、且重复次数相同的条目；不满足的列出来，不计入。
- 先在条目内把几次重复取平均，再在条目之间取平均（每条条目权重相同）。知识不通过的那次按 0 分进入平均。
- 只报数字，不做显著性检验，不下“哪份更好”的结论。
- 每个数字后面的 [Qn] 指向文末附录里得到它的 SQL。SQL 可以直接在 sqlite3 里对 results/eval.db 运行：
  报告运行时会把当前条目文件的元数据写进 items_snapshot / items_gate / items_steps 三张表。
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .judge import ROOT, db_path_from_config, judge_model_cfg, load_items, load_prompt, rubric_hash
from .run import PER_COURSE_SKILL_DIRS, UsageError, _rel, load_config

EPS = 1e-9

SNAPSHOT_SQL = """
CREATE TABLE IF NOT EXISTS items_snapshot (
    item_id TEXT PRIMARY KEY, course TEXT, subtype TEXT, reader TEXT, difficulty TEXT,
    rubric_sha256 TEXT, items_file TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS items_gate (
    item_id TEXT, question_id TEXT, source_level TEXT, text TEXT, PRIMARY KEY (item_id, question_id));
CREATE TABLE IF NOT EXISTS items_steps (
    item_id TEXT, step_id TEXT, text TEXT, PRIMARY KEY (item_id, step_id));
"""


def snapshot_items(conn, items_by_id: dict, items_rel: str) -> None:
    """把当前条目文件的元数据写进库，供报告 SQL 关联（每次运行覆盖）。"""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.executescript(SNAPSHOT_SQL)
    with conn:
        conn.execute("DELETE FROM items_snapshot")
        conn.execute("DELETE FROM items_gate")
        conn.execute("DELETE FROM items_steps")
        for it in items_by_id.values():
            reader = "零基础" if it["id"].endswith("零基础") else "有前置" if it["id"].endswith("有前置") else "其他"
            conn.execute("INSERT INTO items_snapshot VALUES (?,?,?,?,?,?,?,?)",
                         (it["id"], it["course"], it["subtype"], reader, it["difficulty"], rubric_hash(it), items_rel, now))
            for q in it["gate_questions"]:
                conn.execute("INSERT INTO items_gate VALUES (?,?,?,?)", (it["id"], q["id"], q["source_level"], q["text"]))
            for s in it["recommended_steps"]:
                conn.execute("INSERT INTO items_steps VALUES (?,?,?)", (it["id"], s["id"], s["text"]))


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def side_cond(arg: str) -> tuple[str, str]:
    """返回（SQL 条件，显示名）。"""
    if arg in PER_COURSE_SKILL_DIRS:
        return f"c.skill_file LIKE {_q(f'skills/{arg}/%')}", f"{arg}（按课程选 skills/{arg}/ 里的文件）"
    p = Path(arg)
    if not p.is_file():
        raise UsageError(f"Skill 文件不存在：{arg}（也可以写 {' / '.join(PER_COURSE_SKILL_DIRS)}）")
    rel = _rel(p)
    return f"c.skill_file = {_q(rel)}", rel


class Report:
    def __init__(self, conn):
        self.conn = conn
        self.sqls: list[tuple[str, str]] = []

    def q(self, title: str, sql: str) -> tuple[str, list]:
        self.sqls.append((title, sql.strip()))
        tag = f"Q{len(self.sqls)}"
        return tag, [dict(r) for r in self.conn.execute(sql).fetchall()]


def _f(v, nd=3):
    return "—" if v is None else f"{v:.{nd}f}"


def _d(v, nd=3):
    if v is None:
        return "—"
    if abs(v) < 0.5 * 10 ** -nd:   # 浮点误差造成的 -0.000
        v = 0.0
    return f"{v:+.{nd}f}"


def _md(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")


def build(args) -> tuple[str, Path]:
    cfg = load_config(Path(args.config))
    jcfg = judge_model_cfg(cfg)
    judge_name = args.judge_model or jcfg["name"]
    prompt = load_prompt(Path(args.judge_prompt))
    items_by_id, items_rel = load_items(Path(args.items), args.holdout)
    conn = db.connect(db_path_from_config(cfg))
    snapshot_items(conn, items_by_id, items_rel)
    cond_a, name_a = side_cond(args.a)
    cond_b, name_b = side_cond(args.b)
    if cond_a == cond_b:
        raise UsageError("--a 和 --b 是同一份 Skill")

    base = f"""WITH base AS (  -- 当前回答 × 该裁判、该版 prompt、判分清单与当前条目一致的最新成功裁判
  SELECT CASE WHEN {cond_a} THEN 'A' ELSE 'B' END AS side,
         c.id AS call_id, c.item_id, c.repeat_idx, j.id AS judgment_id,
         j.knowledge_pass, j.incomplete, j.gate_num, j.gate_den, j.step_num, j.step_den, j.gate_all,
         j.n_gaps_blocking, j.n_redundancy, rc.char_count
  FROM current_calls c
  JOIN items_snapshot s ON s.item_id = c.item_id
  JOIN judgments j ON j.id = (
       SELECT max(x.id) FROM judgments x
       WHERE x.call_id = c.id AND x.status = 'ok' AND x.judge_model_name = {_q(judge_name)}
         AND x.prompt_sha256 = {_q(prompt.sha256)} AND x.rubric_sha256 = s.rubric_sha256)
  LEFT JOIN rule_checks rc ON rc.call_id = c.id
  WHERE c.model_name = {_q(args.model)} AND (({cond_a}) OR ({cond_b}))
),
eligible AS (  -- 两边都有、且裁判过的重复次数相同的条目
  SELECT item_id FROM base GROUP BY item_id
  HAVING sum(side = 'A') > 0 AND sum(side = 'A') = sum(side = 'B')
),
per_item AS (  -- 条目内先对几次重复取平均；知识不通过的那次 gate_num/step_num 已是 0
  SELECT b.item_id, b.side, count(*) AS n,
         avg(1.0 * gate_num / gate_den) AS gate, avg(1.0 * step_num / step_den) AS step,
         avg(CASE WHEN knowledge_pass = 1 THEN 1.0 * gate_num / gate_den END) AS gate_ex,
         avg(CASE WHEN knowledge_pass = 1 THEN 1.0 * step_num / step_den END) AS step_ex,
         sum(1 - knowledge_pass) AS n_kfail, sum(incomplete) AS n_incomplete, sum(gate_all) AS n_gate_all,
         avg(n_gaps_blocking) AS gaps_blocking, avg(n_redundancy) AS redundancy, avg(char_count) AS chars
  FROM base b JOIN eligible e USING (item_id)
  GROUP BY b.item_id, b.side
),
paired AS (
  SELECT a.item_id, a.n AS n_rep,
         a.gate AS gate_a, b.gate AS gate_b, b.gate - a.gate AS gate_diff,
         a.step AS step_a, b.step AS step_b, b.step - a.step AS step_diff,
         a.gate_ex AS gate_ex_a, b.gate_ex AS gate_ex_b, b.gate_ex - a.gate_ex AS gate_ex_diff,
         a.step_ex AS step_ex_a, b.step_ex AS step_ex_b, b.step_ex - a.step_ex AS step_ex_diff,
         a.n_kfail AS kfail_a, b.n_kfail AS kfail_b, a.n_incomplete AS inc_a, b.n_incomplete AS inc_b,
         b.gaps_blocking - a.gaps_blocking AS gaps_diff, b.redundancy - a.redundancy AS red_diff,
         b.chars - a.chars AS chars_diff
  FROM per_item a JOIN per_item b ON a.item_id = b.item_id AND a.side = 'A' AND b.side = 'B'
)"""

    R = Report(conn)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    L = [f"# Skill 比较：A = {name_a}，B = {name_b}", "",
         f"- 被测模型：{args.model}；裁判：{judge_name}，prompt `{prompt.rel}`（sha256 {prompt.sha256[:12]}）",
         f"- 条目文件：`{items_rel}`；生成时间 {now}",
         "- 差值一律是 B − A。卡点分、步骤分是两个独立的数，不合成总分。只报数字，不做显著性检验。",
         "- 每个数字后的 [Qn] 是附录里得到它的 SQL。", ""]

    # 0. 计入与不计入
    t0, cover = R.q("每个条目在 A、B 下各有几次裁判结果", f"""{base}
SELECT s.item_id, coalesce(sum(b.side = 'A'), 0) AS n_a, coalesce(sum(b.side = 'B'), 0) AS n_b,
       s.item_id IN (SELECT item_id FROM eligible) AS eligible
FROM items_snapshot s LEFT JOIN base b ON b.item_id = s.item_id
GROUP BY s.item_id ORDER BY s.item_id""")
    elig = [r for r in cover if r["eligible"]]
    excl = [r for r in cover if not r["eligible"]]
    L += ["## 0. 计入的条目", "",
          f"计入 {len(elig)} 条，不计入 {len(excl)} 条 [{t0}]。"]
    if excl:
        L += ["", "| 不计入的条目 | A 的裁判结果数 | B 的裁判结果数 |", "|---|---|---|"]
        L += [f"| {r['item_id']} | {r['n_a']} | {r['n_b']} |" for r in excl]
    L.append("")
    if not elig:
        L.append("没有可比较的条目，后面各节为空。")

    # 0b. 待复核
    tr, rv = R.q("待复核（needs_review）的裁判结果：不计分、不进统计", f"""SELECT CASE WHEN {cond_a} THEN 'A' ELSE 'B' END AS side,
       c.id AS call_id, c.item_id, c.repeat_idx, j.id AS judgment_id, j.error AS reasons
FROM current_calls c
JOIN items_snapshot s ON s.item_id = c.item_id
JOIN judgments j ON j.id = (
     SELECT max(x.id) FROM judgments x
     WHERE x.call_id = c.id AND x.status IN ('ok', 'needs_review') AND x.judge_model_name = {_q(judge_name)}
       AND x.prompt_sha256 = {_q(prompt.sha256)} AND x.rubric_sha256 = s.rubric_sha256)
WHERE j.status = 'needs_review' AND c.model_name = {_q(args.model)} AND (({cond_a}) OR ({cond_b}))
ORDER BY side, c.item_id, c.repeat_idx""")
    L += [f"## 待复核（needs_review）[{tr}]", "",
          f"重判 2 次后证据仍不合格的裁判结果，不计分、不进以下任何统计，需要人工看：A {sum(r['side'] == 'A' for r in rv)} 份，"
          f"B {sum(r['side'] == 'B' for r in rv)} 份。这些回答所在的条目如果因此两边重复次数不同，会出现在第 0 节的不计入清单里。", ""]
    if rv:
        L += ["| 边 | 回答 id（calls.id） | 条目 | 第几次 | 裁判记录 id | 不合格原因 |", "|---|---|---|---|---|---|"]
        L += [f"| {r['side']} | {r['call_id']} | {r['item_id']} | {r['repeat_idx']} | {r['judgment_id']} | {_md(r['reasons'])} |" for r in rv]
        L.append("")

    # 1. 主指标
    t1, per = R.q("逐条：卡点分、步骤分（A、B、差值）", f"""{base}
SELECT * FROM paired ORDER BY item_id""")
    t2, sg = R.q("卡点分汇总：平均差、变好/持平/变差条数", f"""{base}
SELECT count(*) AS n, avg(gate_a) AS mean_a, avg(gate_b) AS mean_b, avg(gate_diff) AS mean_diff,
       sum(gate_diff > {EPS}) AS better, sum(abs(gate_diff) <= {EPS}) AS same, sum(gate_diff < -{EPS}) AS worse
FROM paired""")
    sg = sg[0]
    L += ["## 1. 主指标：卡点分", "",
          f"- 条目平均：A {_f(sg['mean_a'])}，B {_f(sg['mean_b'])}，平均差 {_d(sg['mean_diff'])} [{t2}]",
          f"- 变好 {sg['better'] or 0} 条，持平 {sg['same'] or 0} 条，变差 {sg['worse'] or 0} 条 [{t2}]", "",
          f"| 条目 | 重复 | 卡点 A | 卡点 B | 差 | 步骤 A | 步骤 B | 差 |", "|---|---|---|---|---|---|---|---|"]
    L += [f"| {r['item_id']} | {r['n_rep']} | {_f(r['gate_a'])} | {_f(r['gate_b'])} | {_d(r['gate_diff'])} | "
          f"{_f(r['step_a'])} | {_f(r['step_b'])} | {_d(r['step_diff'])} |" for r in per]
    L += [f"", f"（逐条数字 [{t1}]）", ""]

    # 2. 副指标
    t3, ss = R.q("步骤分汇总", f"""{base}
SELECT count(*) AS n, avg(step_a) AS mean_a, avg(step_b) AS mean_b, avg(step_diff) AS mean_diff,
       sum(step_diff > {EPS}) AS better, sum(abs(step_diff) <= {EPS}) AS same, sum(step_diff < -{EPS}) AS worse
FROM paired""")
    ss = ss[0]
    L += ["## 2. 副指标：步骤分", "",
          f"- 条目平均：A {_f(ss['mean_a'])}，B {_f(ss['mean_b'])}，平均差 {_d(ss['mean_diff'])} [{t3}]",
          f"- 变好 {ss['better'] or 0} 条，持平 {ss['same'] or 0} 条，变差 {ss['worse'] or 0} 条 [{t3}]",
          f"- 逐条数字见第 1 节的表 [{t1}]", ""]

    # 3. 知识不通过、没答全
    t4, kf = R.q("知识不通过、没答全：次数和条目", f"""{base}
SELECT b.side,
       sum(1 - b.knowledge_pass) AS n_kfail,
       group_concat(CASE WHEN b.knowledge_pass = 0 THEN b.item_id || '#' || b.repeat_idx END, '、') AS kfail_items,
       sum(b.incomplete) AS n_incomplete,
       group_concat(CASE WHEN b.incomplete = 1 THEN b.item_id || '#' || b.repeat_idx END, '、') AS inc_items,
       count(*) AS n_answers
FROM base b JOIN eligible e USING (item_id)
GROUP BY b.side ORDER BY b.side""")
    kfd = {r["side"]: r for r in kf}
    t5, ex = R.q("排除知识不通过的那几次之后的卡点分、步骤分", f"""{base}
SELECT count(*) AS n_both,
       avg(gate_ex_a) AS gate_a, avg(gate_ex_b) AS gate_b, avg(gate_ex_diff) AS gate_diff,
       avg(step_ex_a) AS step_a, avg(step_ex_b) AS step_b, avg(step_ex_diff) AS step_diff
FROM paired WHERE gate_ex_a IS NOT NULL AND gate_ex_b IS NOT NULL""")
    ex = ex[0]
    L += ["## 3. 知识不通过、没答全", "", "| | A | B |", "|---|---|---|"]
    for key, lab in (("n_kfail", "知识不通过（次）"), ("n_incomplete", "没答全（次）"), ("n_answers", "回答总数")):
        L.append(f"| {lab} | {(kfd.get('A') or {}).get(key) or 0} | {(kfd.get('B') or {}).get(key) or 0} |")
    L.append(f"\n[{t4}]\n")
    for side in ("A", "B"):
        r = kfd.get(side)
        L.append(f"- {side} 知识不通过：{(r['kfail_items'] if r and r['kfail_items'] else '无')}")
        L.append(f"- {side} 没答全：{(r['inc_items'] if r and r['inc_items'] else '无')}")
    L += ["", "条目号后的 #n 是第几次重复。", "",
          "主表与“排除知识不通过的那几次”并排（后者只算两边都至少有一次知识通过的条目）：", "",
          "| | 卡点 A | 卡点 B | 卡点差 | 步骤 A | 步骤 B | 步骤差 | 条目数 |", "|---|---|---|---|---|---|---|---|",
          f"| 主表 [{t2}][{t3}] | {_f(sg['mean_a'])} | {_f(sg['mean_b'])} | {_d(sg['mean_diff'])} | {_f(ss['mean_a'])} | {_f(ss['mean_b'])} | {_d(ss['mean_diff'])} | {sg['n']} |",
          f"| 排除知识不通过 [{t5}] | {_f(ex['gate_a'])} | {_f(ex['gate_b'])} | {_d(ex['gate_diff'])} | {_f(ex['step_a'])} | {_f(ex['step_b'])} | {_d(ex['step_diff'])} | {ex['n_both']} |", ""]

    # 4. 卡点全答上
    t6, ga = R.q("“卡点全答上”的回答占比", f"""{base}
SELECT b.side, sum(b.gate_all) AS n_all, count(*) AS n, 1.0 * sum(b.gate_all) / count(*) AS share
FROM base b JOIN eligible e USING (item_id) GROUP BY b.side ORDER BY b.side""")
    L += ["## 4. 辅助统计：卡点全答上", ""]
    for r in ga:
        L.append(f"- {r['side']}：{r['n_all']}/{r['n']} 份回答（{_f(r['share'])}）[{t6}]")
    L.append("")

    # 5. 分组
    L += ["## 5. 分组的卡点分和步骤分", "", "组内仍是先条目内平均、再条目间平均。", ""]
    for col, lab in (("subtype", "subtype"), ("reader", "读者版本"), ("course", "course")):
        t, rows = R.q(f"按 {lab} 分组", f"""{base}
SELECT s.{col} AS grp, count(*) AS n_items,
       avg(p.gate_a) AS gate_a, avg(p.gate_b) AS gate_b, avg(p.gate_diff) AS gate_diff,
       avg(p.step_a) AS step_a, avg(p.step_b) AS step_b, avg(p.step_diff) AS step_diff
FROM paired p JOIN items_snapshot s USING (item_id)
GROUP BY s.{col} ORDER BY s.{col}""")
        L += [f"**按 {lab}** [{t}]", "", "| 组 | 条目数 | 卡点 A | 卡点 B | 差 | 步骤 A | 步骤 B | 差 |", "|---|---|---|---|---|---|---|---|"]
        L += [f"| {r['grp']} | {r['n_items']} | {_f(r['gate_a'])} | {_f(r['gate_b'])} | {_d(r['gate_diff'])} | "
              f"{_f(r['step_a'])} | {_f(r['step_b'])} | {_d(r['step_diff'])} |" for r in rows]
        L.append("")

    # 6. source_level
    t7, sl = R.q("按卡点问题的 source_level：答上率", f"""{base},
q AS (  -- 逐问题：计分口径的答上（知识不通过的那次算没答上）
  SELECT b.side, b.item_id, ig.source_level,
         CASE WHEN b.knowledge_pass = 1 AND g.answered = 1 THEN 1.0 ELSE 0.0 END AS hit
  FROM base b JOIN eligible e USING (item_id)
  JOIN judge_gate g ON g.judgment_id = b.judgment_id
  JOIN items_gate ig ON ig.item_id = b.item_id AND ig.question_id = g.question_id
),
qi AS (SELECT side, item_id, source_level, avg(hit) AS rate, count(*) AS n FROM q GROUP BY side, item_id, source_level)
SELECT source_level, side, count(*) AS n_items, sum(n) AS n_judgments, avg(rate) AS rate
FROM qi GROUP BY source_level, side ORDER BY source_level, side""")
    sld: dict = {}
    for r in sl:
        sld.setdefault(r["source_level"], {})[r["side"]] = r
    L += ["## 6. 按卡点问题的出处级别", "",
          "答上率按计分口径（知识不通过的那次算没答上）；先在条目内平均，再在条目间平均。", "",
          "| source_level | 条目数 | A 答上率 | B 答上率 | 差 |", "|---|---|---|---|---|"]
    for lvl, d in sld.items():
        a, b = d.get("A"), d.get("B")
        diff = (b["rate"] - a["rate"]) if a and b else None
        L.append(f"| {lvl} | {(a or b)['n_items']} | {_f(a['rate'] if a else None)} | {_f(b['rate'] if b else None)} | {_d(diff)} |")
    L += [f"\n[{t7}]", ""]

    # 7. 问题层面 / 步骤层面的翻转
    for kind, table, idcol, flag, meta in (("卡点问题", "judge_gate", "question_id", "answered", "items_gate"),
                                           ("推荐步骤", "judge_steps", "step_id", "done", "items_steps")):
        t, rows = R.q(f"{kind}：A、B 下的命中次数（计分口径）", f"""{base},
x AS (
  SELECT b.side, b.item_id, g.{idcol} AS xid,
         sum(CASE WHEN b.knowledge_pass = 1 AND g.{flag} = 1 THEN 1 ELSE 0 END) AS hit, count(*) AS n
  FROM base b JOIN eligible e USING (item_id)
  JOIN {table} g ON g.judgment_id = b.judgment_id
  GROUP BY b.side, b.item_id, g.{idcol}
)
SELECT a.item_id, a.xid, m.text, a.hit AS hit_a, a.n AS n_a, b.hit AS hit_b, b.n AS n_b
FROM x a JOIN x b ON a.item_id = b.item_id AND a.xid = b.xid AND a.side = 'A' AND b.side = 'B'
JOIN {meta} m ON m.item_id = a.item_id AND m.{idcol} = a.xid
WHERE a.hit <> b.hit ORDER BY a.item_id, a.xid""")
        up = [r for r in rows if r["hit_b"] > r["hit_a"]]
        down = [r for r in rows if r["hit_b"] < r["hit_a"]]
        verb = "答上" if kind == "卡点问题" else "踩中"
        L += [f"## 7{'a' if kind == '卡点问题' else 'b'}. {kind}：A、B 下{verb}次数不同的 [{t}]", "",
              f"计分口径（知识不通过的那次算没{verb}）。“A 1/3”表示 A 的 3 次重复里{verb} 1 次。", ""]
        for lst, lab in ((up, f"B 比 A 多{verb}"), (down, f"A 比 B 多{verb}")):
            L += [f"**{lab}**（{len(lst)} 项）", ""]
            if lst:
                L += ["| 条目 | id | 内容 | A | B |", "|---|---|---|---|---|"]
                L += [f"| {r['item_id']} | {r['xid']} | {_md(r['text'])} | {r['hit_a']}/{r['n_a']} | {r['hit_b']}/{r['n_b']} |" for r in lst]
            else:
                L.append("（无）")
            L.append("")

    # 8. extra_steps
    t8, es = R.q("清单外步骤（extra_steps）", f"""{base}
SELECT b.item_id, b.side, b.repeat_idx, x.quote, x.what, x.quote_valid
FROM base b JOIN eligible e USING (item_id)
JOIN judge_extra_steps x ON x.judgment_id = b.judgment_id
ORDER BY b.item_id, b.side, b.repeat_idx""")
    L += [f"## 8. 清单外步骤（extra_steps）[{t8}]", "",
          "裁判记下的、推荐步骤清单里没有的帮助性步骤。✗ 表示引句没通过原文校验。", ""]
    if es:
        cur = None
        for r in es:
            if r["item_id"] != cur:
                cur = r["item_id"]
                L += ["", f"**{cur}**", ""]
            L.append(f"- {r['side']}#{r['repeat_idx']}：{_md(r['what'])}｜「{_md(r['quote'])}」{'' if r['quote_valid'] else ' ✗'}")
    else:
        L.append("（无）")
    L.append("")

    # 9. 辅助指标
    t9, ax = R.q("辅助指标：逐条相减后的平均差", f"""{base}
SELECT count(*) AS n, avg(gaps_diff) AS gaps_diff, avg(red_diff) AS red_diff, avg(chars_diff) AS chars_diff
FROM paired""")
    t10, axs = R.q("辅助指标：A、B 各自的条目平均", f"""{base}
SELECT side, avg(gaps_blocking) AS gaps_blocking, avg(redundancy) AS redundancy, avg(chars) AS chars
FROM per_item GROUP BY side ORDER BY side""")
    ax = ax[0]
    axd = {r["side"]: r for r in axs}
    L += ["## 9. 辅助指标", "", "每份回答先数，条目内平均，再逐条 B − A，最后取平均。gaps 和 redundancy 只数引句通过校验的。", "",
          "| 指标 | A | B | 平均差 |", "|---|---|---|---|"]
    for key, dk, lab, nd in (("gaps_blocking", "gaps_diff", "“读者没法往下读”的 gaps 数", 2),
                             ("redundancy", "red_diff", "redundancy 处数", 2), ("chars", "chars_diff", "篇幅（字符）", 0)):
        L.append(f"| {lab} | {_f((axd.get('A') or {}).get(key) if 'A' in axd else None, nd)} | "
                 f"{_f((axd.get('B') or {}).get(key) if 'B' in axd else None, nd)} | {_d(ax[dk], nd)} |")
    L += [f"\n[{t10}][{t9}]", ""]

    # 附录
    L += ["---", "", "## 附录：SQL", "",
          "在项目根目录运行 `sqlite3 results/eval.db`，粘贴即可复现。`items_snapshot`、`items_gate`、`items_steps` 是本报告运行时由 "
          f"`{items_rel}` 写入的条目元数据；`current_calls` 是“同一条目、模型、Skill 文件、重复次数取最新成功记录”的视图。", ""]
    for i, (title, sql) in enumerate(R.sqls, 1):
        L += [f"### Q{i}. {title}", "", "```sql", sql + ";", "```", ""]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    def slug(s):
        return re.sub(r"[^\w.-]+", "_", Path(s).stem if s.endswith(".md") else s)

    out = out_dir / f"{slug(args.a)}__vs__{slug(args.b)}__{slug(args.model)}__{slug(prompt.rel)}.md"
    out.write_text("\n".join(L), encoding="utf-8")
    conn.close()
    return "\n".join(L), out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.report", description="两份 Skill 的比较报告")
    ap.add_argument("--a", required=True, help="Skill A：文件路径，或 original / original_eval")
    ap.add_argument("--b", required=True, help="Skill B：同上")
    ap.add_argument("--model", required=True, help="被测模型（config 里的模型名）")
    ap.add_argument("--judge-prompt", required=True)
    ap.add_argument("--judge-model", help="裁判模型名，默认 config 的 judge.name")
    ap.add_argument("--out", default="reports/")
    ap.add_argument("--items", default="data/items.jsonl")
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    args = ap.parse_args(argv)
    try:
        _, out = build(args)
    except UsageError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    print(f"报告已写入 {_rel(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
