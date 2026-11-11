"""长请求验证报告（第四份输入）：同样的卡点、步骤，单独讲（短条目）vs 连着讲（长请求）。

python -m src.longreport --out reports/

- 短的一边：data/items.jsonl 的当前回答 × judge_v2 × 当前判分清单的最新 ok 记录（ECON-003 用重判后的）。
- 长的一边：data/items_long_dev.jsonl 的当前回答 × judge_v2 × 长条目判分清单的最新 ok 记录。
- 逐卡点、逐步骤直接用裁判对每一项的 answered / done（引句校验后），不套知识清零。
- 不改 items_snapshot 等四组汇总用的表；只读数据库。每张表后的 [Qn] 指向附录里取数的 SQL。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .judge import ROOT, db_path_from_config, judge_model_cfg, load_items, load_prompt, rubric_hash
from .report import Report, _md, _q
from .run import UsageError, _rel, find_model, load_config

MODELS = ["gpt-6.1-sol", "gpt-6-luna"]
SHORT_NAME = {"gpt-6.1-sol": "sol", "gpt-6-luna": "luna"}
CN_NUM = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五"}
EPS = 1e-9


def _pct(a, b):
    return "—" if not b else f"{100 * a / b:.1f}%（{a}/{b}）"


def _r(a, b):
    return "—" if not b else f"{a / b:.2f}"


# ---------------- 取数 ----------------

def judged_rows(R: Report, title: str, item_ids: list[str], rubric: dict, skill: str, judge_name: str,
                prompt_sha: str, statuses=("ok",)) -> list[dict]:
    """当前回答 × 该裁判、该 prompt、判分清单与给定条目一致的最新一条记录（状态在 statuses 里）。"""
    vals = " UNION ALL ".join(f"SELECT {_q(i)} AS item_id, {_q(rubric[i])} AS rubric_sha256" for i in item_ids)
    st = ", ".join(_q(s) for s in statuses)
    _, rows = R.q(title, f"""WITH it AS ({vals})
SELECT c.id AS call_id, c.item_id, c.model_name, c.repeat_idx, length(c.response_text) AS n_chars,
       c.output_tokens AS gen_out, json_extract(c.usage_raw, '$.output_tokens_details.reasoning_tokens') AS gen_reason,
       j.id AS judgment_id, j.status, j.knowledge_pass, j.incomplete, j.incomplete_missing, j.gate_num, j.gate_den,
       j.step_num, j.step_den, j.gate_all, j.error, j.flags,
       json_extract(j.parsed_json, '$.knowledge_error.which') AS k_which,
       json_extract(j.parsed_json, '$.knowledge_error.quotes') AS k_quotes,
       json_extract(j.parsed_json, '$.knowledge_error.note') AS k_note,
       json_extract(j.parsed_json, '$.incomplete.note') AS i_note
FROM current_calls c
JOIN it ON it.item_id = c.item_id
LEFT JOIN judgments j ON j.id = (
     SELECT max(x.id) FROM judgments x
     WHERE x.call_id = c.id AND x.judge_model_name = {_q(judge_name)} AND x.prompt_sha256 = {_q(prompt_sha)}
       AND x.rubric_sha256 = it.rubric_sha256 AND x.status IN ({st}))
WHERE c.skill_file = {_q(skill)} AND c.model_name IN ({', '.join(_q(m) for m in MODELS)})
ORDER BY c.item_id, c.model_name, c.repeat_idx""")
    return rows


def unit_rows(conn, judgment_ids: list[int]) -> tuple[dict, dict]:
    """judgment_id -> {question_id: answered}，judgment_id -> {step_id: done}。"""
    g, s = defaultdict(dict), defaultdict(dict)
    if not judgment_ids:
        return g, s
    ph = ",".join("?" * len(judgment_ids))
    for r in conn.execute(f"SELECT judgment_id, question_id, answered FROM judge_gate WHERE judgment_id IN ({ph})", judgment_ids):
        g[r[0]][r[1]] = r[2]
    for r in conn.execute(f"SELECT judgment_id, step_id, done FROM judge_steps WHERE judgment_id IN ({ph})", judgment_ids):
        s[r[0]][r[1]] = r[2]
    return g, s


# ---------------- 切分长回答 ----------------

def split_parts(text: str, n: int = 5) -> list[str] | None:
    """按“第 i 部分”的标题把长回答切成 n 段。标题行：以 #、**、【 或“第”开头，含“第 i 部分”或“第一部分”等。
    5 个标题都能按顺序找到才切，否则返回 None。第 1 部分之前的开场白不算进任何部分。"""
    pos = []
    start = 0
    for i in range(1, n + 1):
        pat = re.compile(rf"^[ \t]*(#+\s*|\*\*|【|)\s*(\*\*)?\s*【?第\s*({i}|{CN_NUM[i]})\s*部分", re.M)
        m = pat.search(text, start)
        if not m:
            return None
        pos.append(m.start())
        start = m.end()
    pos.append(len(text))
    return [text[pos[k]:pos[k + 1]] for k in range(n)]


# ---------------- 报告 ----------------

def build(args) -> tuple[str, Path]:
    cfg = load_config(Path(args.config))
    jcfg = judge_model_cfg(cfg)
    judge_name = jcfg["name"]
    prompt = load_prompt(Path(args.judge_prompt))
    short_items, short_rel = load_items(Path(args.short_items), False)
    long_items, long_rel = load_items(Path(args.long_items), False)
    mp = json.loads(Path(args.map).read_text(encoding="utf-8"))
    skill = _rel(Path(args.skill))
    conn = db.connect(db_path_from_config(cfg))
    R = Report(conn)

    # 长条目每一项 -> (短条目 id, 短项 id, 部分序号)
    unit_map = {}
    for k, v in mp.items():
        lid, uid = k.split("#")
        sid, suid = v.split("#")
        unit_map[(lid, uid)] = (sid, suid, int(re.match(r"p(\d+)", uid).group(1)))
    used_short = sorted({v[0] for v in unit_map.values()})

    s_rubric = {i: rubric_hash(short_items[i]) for i in used_short}
    l_rubric = {i: rubric_hash(it) for i, it in long_items.items()}
    short = judged_rows(R, "短的一边：短条目当前回答 × judge_v2 × 当前判分清单的最新 ok 记录",
                        used_short, s_rubric, skill, judge_name, prompt.sha256)
    long_ = judged_rows(R, "长的一边：长请求当前回答 × judge_v2 × 长条目判分清单的最新记录（ok / needs_review / error）",
                        sorted(long_items), l_rubric, skill, judge_name, prompt.sha256,
                        statuses=("ok", "needs_review", "error"))
    t_short, t_long = "Q1", "Q2"
    _, gen_all = R.q("长请求的全部生成调用（含失败、截断）", f"""
SELECT c.id, c.run_id, c.item_id, c.model_name, c.repeat_idx, c.status, c.finish_reason, c.error,
       c.input_tokens, c.output_tokens,
       coalesce(json_extract(c.usage_raw, '$.input_tokens_details.cached_tokens'), 0) AS cached,
       json_extract(c.params_used, '$.sent') AS sent
FROM calls c
WHERE c.item_id IN ({', '.join(_q(i) for i in long_items)}) AND c.skill_file = {_q(skill)}
ORDER BY c.model_name, c.item_id, c.repeat_idx, c.id""")
    t_gen = "Q3"

    ok_short = [r for r in short if r["status"] == "ok"]
    ok_long = [r for r in long_ if r["status"] == "ok"]
    sg, ss = unit_rows(conn, [r["judgment_id"] for r in ok_short])
    lg, ls = unit_rows(conn, [r["judgment_id"] for r in ok_long])

    # 每一项：短的答上次数/判过次数，长的答上次数/判过次数
    def tally(kind):
        units = []
        for (lid, uid), (sid, suid, part) in sorted(unit_map.items(), key=lambda x: (x[0][0], x[1][2], x[0][1])):
            if (kind == "gate") != uid[2:].startswith("q"):
                continue
            row = {"lid": lid, "uid": uid, "sid": sid, "suid": suid, "part": part,
                   "course": long_items[lid]["course"], "reader": lid.rsplit("-", 1)[1]}
            src = short_items[sid]["gate_questions" if kind == "gate" else "recommended_steps"]
            row["text"] = next(x["text"] for x in src if x["id"] == suid)
            for m in MODELS:
                sv = [(sg if kind == "gate" else ss)[r["judgment_id"]].get(suid)
                      for r in ok_short if r["item_id"] == sid and r["model_name"] == m]
                lv = [(lg if kind == "gate" else ls)[r["judgment_id"]].get(uid)
                      for r in ok_long if r["item_id"] == lid and r["model_name"] == m]
                sv = [v for v in sv if v is not None]
                lv = [v for v in lv if v is not None]
                row[m] = (sum(sv), len(sv), sum(lv), len(lv))
            units.append(row)
        return units

    gates, steps = tally("gate"), tally("step")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    L = ["# 长请求验证：单独讲 vs 连着讲", "",
         f"- 生成时间：{now}",
         f"- Skill：`{skill}`；被测模型：{', '.join(MODELS)}；裁判：{judge_name}，prompt `{prompt.rel}`（sha256 {prompt.sha256[:12]}…）",
         f"- 短条目 `{short_rel}`，长请求 `{long_rel}`，对应表 `{_rel(Path(args.map))}`",
         "- 逐项对比用裁判对每个卡点、步骤的判断（引句校验后），**不套知识清零**。",
         "- 短的一边是已有的正式评分（ECON-003 用按新条目重判后的记录）；长的一边只用 status=ok 的裁判记录。", ""]

    # 0. 份数
    L += [f"## 0. 份数 [{t_gen}] [{t_short}] [{t_long}]", "",
          "| 组 | 长请求调用 | 成功 | 截断（不送裁判） | 其他失败 | 裁判 ok | 待复核 | 裁判失败 | 短条目裁判 ok |",
          "|---|---|---|---|---|---|---|---|---|"]
    for m in MODELS:
        g = [r for r in gen_all if r["model_name"] == m]
        lr = [r for r in long_ if r["model_name"] == m]
        L.append(f"| general_v1 × {m} | {len(g)} | {sum(r['status'] == 'ok' for r in g)} "
                 f"| {sum(r['status'] != 'ok' and r['finish_reason'] == 'length' for r in g)} "
                 f"| {sum(r['status'] != 'ok' and r['finish_reason'] != 'length' for r in g)} "
                 f"| {sum(r['status'] == 'ok' for r in lr)} | {sum(r['status'] == 'needs_review' for r in lr)} "
                 f"| {sum(r['status'] == 'error' for r in lr)} | {sum(r['model_name'] == m for r in ok_short)} |")
    sent = sorted({r["sent"] for r in gen_all if r["sent"]})
    L += ["", "长请求实际发送的参数：" + "；".join(f"`{s}`" for s in sent), ""]

    # 1/2. 卡点汇总
    def summarize(units, label):
        out = [f"| 组 | {label}数 | 短：答上率 | 长：答上率 | 差（长 − 短） | 下降 | 持平 | 上升 |", "|---|---|---|---|---|---|---|---|"]
        for m in MODELS:
            sa = sum(u[m][0] for u in units); sn = sum(u[m][1] for u in units)
            la = sum(u[m][2] for u in units); ln = sum(u[m][3] for u in units)
            comp = [u for u in units if u[m][1] and u[m][3]]
            d = [u[m][2] / u[m][3] - u[m][0] / u[m][1] for u in comp]
            diff = (la / ln - sa / sn) if sn and ln else None
            out.append(f"| general_v1 × {m} | {len(units)} | {_pct(sa, sn)} | {_pct(la, ln)} | "
                       + ("—" if diff is None else f"{100 * diff:+.1f} 个百分点")
                       + f" | {sum(x < -EPS for x in d)} | {sum(abs(x) <= EPS for x in d)} | {sum(x > EPS for x in d)} |")
        return out

    def breakdown(units, field, values, label):
        out = [f"| {label} | " + " | ".join(f"{SHORT_NAME[m]}：短 → 长（项数）" for m in MODELS) + " |",
               "|---|" + "---|" * len(MODELS)]
        for v in values:
            sub = [u for u in units if u[field] == v]
            cells = []
            for m in MODELS:
                sa = sum(u[m][0] for u in sub); sn = sum(u[m][1] for u in sub)
                la = sum(u[m][2] for u in sub); ln = sum(u[m][3] for u in sub)
                cells.append(f"{_r(sa, sn)} → {_r(la, ln)}（{len(sub)}）" if sn and ln else "—")
            out.append(f"| {v} | " + " | ".join(cells) + " |")
        return out

    def updown_by(units, field, values, label):
        out = [f"| {label} | " + " | ".join(f"{SHORT_NAME[m]}：降 / 平 / 升" for m in MODELS) + " |",
               "|---|" + "---|" * len(MODELS)]
        for v in values:
            sub = [u for u in units if u[field] == v]
            cells = []
            for m in MODELS:
                d = [u[m][2] / u[m][3] - u[m][0] / u[m][1] for u in sub if u[m][1] and u[m][3]]
                cells.append(f"{sum(x < -EPS for x in d)} / {sum(abs(x) <= EPS for x in d)} / {sum(x > EPS for x in d)}")
            out.append(f"| {v} | " + " | ".join(cells) + " |")
        return out

    parts = [1, 2, 3, 4, 5]
    courses = sorted({u["course"] for u in gates})
    readers = ["零基础", "有前置"]
    L += ["## 1. 卡点：汇总", "",
          "答上率 = 答上的（卡点 × 次）/ 判过的（卡点 × 次）。下降 / 持平 / 上升按每个卡点比较“长的答上比例”和“短的答上比例”。", ""]
    L += summarize(gates, "卡点")
    L += ["", "**按第几部分**（越靠后是不是掉得越多）", ""] + breakdown(gates, "part", parts, "部分")
    L += [""] + updown_by(gates, "part", parts, "部分")
    L += ["", "**按课程**", ""] + breakdown(gates, "course", courses, "课程")
    L += ["", "**按读者版本**", ""] + breakdown(gates, "reader", readers, "读者") + [""]

    L += ["## 2. 卡点：逐条对比（51 个 × 2 组）", "",
          "每格：短 = 单独讲时 3 次里答上几次；长 = 连着讲时 3 次里答上几次。▼ 下降，▲ 上升。", "",
          "| 长请求 | 部分 | 卡点 | 原卡点 | 问题 | sol 短 | sol 长 | luna 短 | luna 长 |", "|---|---|---|---|---|---|---|---|---|"]
    for u in gates:
        cells = []
        for m in MODELS:
            a, n, b, k = u[m]
            mark = ""
            if n and k:
                d = b / k - a / n
                mark = " ▼" if d < -EPS else " ▲" if d > EPS else ""
            cells += [f"{a}/{n}", f"{b}/{k}{mark}"]
        L.append(f"| {u['lid']} | {u['part']} | {u['uid']} | {u['sid']}#{u['suid']} | {_md(u['text'])[:60]} | " + " | ".join(cells) + " |")
    L.append("")

    # 3. 步骤
    L += ["## 3. 推荐步骤：汇总（逐条表见附录 A）", ""] + summarize(steps, "步骤")
    L += ["", "**按第几部分**", ""] + breakdown(steps, "part", parts, "部分")
    L += [""] + updown_by(steps, "part", parts, "部分")
    L += ["", "**按课程**", ""] + breakdown(steps, "course", courses, "课程")
    L += ["", "**按读者版本**", ""] + breakdown(steps, "reader", readers, "读者") + [""]

    # 4. 卡点全答上
    L += ["## 4. 卡点全部答上的占比", "",
          "“全答上”不套知识清零（所有卡点 answered 都为真）；另给一列套知识清零的版本（知识通过且全答上，即短条目已有的 gate_all）。",
          "短条目合成一份：同一门课、同一读者版本的 5 条短条目，按重复序号配对（第 1 次重复的 5 份算一份，以此类推），5 份都全答上才算。", "",
          "| 组 | 长回答：全答上 | 长回答：知识通过且全答上 | 短回答（每份）：全答上 | 短回答（每份）：知识通过且全答上 | 5 份短回答合一份：全答上 | 合一份：知识都通过且全答上 |",
          "|---|---|---|---|---|---|---|"]
    for m in MODELS:
        lrows = [r for r in ok_long if r["model_name"] == m]
        srows = [r for r in ok_short if r["model_name"] == m]
        l_all = sum(all(v for v in lg[r["judgment_id"]].values()) for r in lrows)
        l_allk = sum(bool(r["knowledge_pass"]) and all(v for v in lg[r["judgment_id"]].values()) for r in lrows)
        s_all = sum(all(v for v in sg[r["judgment_id"]].values()) for r in srows)
        s_allk = sum(bool(r["gate_all"]) for r in srows)
        # 合成一份
        b_tot = b_all = b_allk = 0
        for lid in sorted(long_items):
            sids = sorted({v[0] for (l, _), v in unit_map.items() if l == lid})
            reps = sorted({r["repeat_idx"] for r in srows if r["item_id"] in sids})
            for rep in reps:
                bundle = [r for r in srows if r["item_id"] in sids and r["repeat_idx"] == rep]
                if len(bundle) != len(sids):
                    continue
                b_tot += 1
                b_all += all(all(v for v in sg[r["judgment_id"]].values()) for r in bundle)
                b_allk += all(bool(r["gate_all"]) for r in bundle)
        L.append(f"| general_v1 × {m} | {_pct(l_all, len(lrows))} | {_pct(l_allk, len(lrows))} | {_pct(s_all, len(srows))} "
                 f"| {_pct(s_allk, len(srows))} | {_pct(b_all, b_tot)} | {_pct(b_allk, b_tot)} |")
    L.append("")

    # 5. 篇幅
    L += ["## 5. 篇幅", "",
          "短回答字数之和 = 同一门课、同一读者版本、同一重复序号的 5 份短回答字数相加。字数是 Python 的字符数（含标点、空白、公式源码）。", "",
          "| 组 | 长请求 | 第几次 | 长回答字数 | 输出 tokens（其中推理） | 5 份短回答字数之和 | 比例 | 能按部分切开 |",
          "|---|---|---|---|---|---|---|---|"]
    short_by = {(r["item_id"], r["model_name"], r["repeat_idx"]): r for r in short}
    texts = {r[0]: r[1] for r in conn.execute(
        f"SELECT id, response_text FROM calls WHERE id IN ({','.join(str(r['call_id']) for r in long_ + short) or '0'})")}
    part_ratios = defaultdict(list)   # (model, part) -> [(long_chars, short_chars)]
    split_fail = []
    ratio_sum = defaultdict(lambda: [0, 0])
    for r in sorted(long_, key=lambda r: (MODELS.index(r["model_name"]), r["item_id"], r["repeat_idx"])):
        lid, m, rep = r["item_id"], r["model_name"], r["repeat_idx"]
        sids = sorted({v[0] for (l, _), v in unit_map.items() if l == lid})
        srs = [short_by.get((sid, m, rep)) for sid in sids]
        ssum = sum(x["n_chars"] for x in srs if x) if all(srs) else None
        pieces = split_parts(texts[r["call_id"]])
        if pieces:
            for i, pc in enumerate(pieces, 1):
                if srs[i - 1]:
                    part_ratios[(m, i)].append((len(pc), srs[i - 1]["n_chars"]))
        else:
            split_fail.append(r["call_id"])
        if ssum:
            ratio_sum[m][0] += r["n_chars"]
            ratio_sum[m][1] += ssum
        L.append(f"| general_v1 × {m} | {lid} | {rep} | {r['n_chars']:,} | {r['gen_out']:,}（{r['gen_reason'] or 0:,}） "
                 f"| {ssum:,} | {_r(r['n_chars'], ssum)} | {'是' if pieces else '否'} |" if ssum else
                 f"| general_v1 × {m} | {lid} | {rep} | {r['n_chars']:,} | {r['gen_out']:,} | — | — | {'是' if pieces else '否'} |")
    L += ["", "合计比例（长回答字数之和 / 对应短回答字数之和）：" +
          "；".join(f"{m} {_r(*ratio_sum[m])}" for m in MODELS if ratio_sum[m][1]), ""]
    L += ["**按部分**（只算能按“第 i 部分”标题切开的长回答；第 1 部分之前的开场白不算）", "",
          "| 部分 | " + " | ".join(f"{SHORT_NAME[m]}：长 / 短（份数）" for m in MODELS) + " |", "|---|" + "---|" * len(MODELS)]
    for i in parts:
        cells = []
        for m in MODELS:
            v = part_ratios[(m, i)]
            cells.append(f"{sum(a for a, _ in v) / sum(b for _, b in v):.2f}（{len(v)}）" if v else "—")
        L.append(f"| 第 {i} 部分 | " + " | ".join(cells) + " |")
    L += ["", f"切不开的长回答：{', '.join(map(str, split_fail)) or '无'}", ""]

    # 6. 知识错误、没答全
    L += ["## 6. 知识错误和没答全", ""]
    kf = [r for r in ok_long if not r["knowledge_pass"]]
    L += [f"长回答里触发知识错误的 {len(kf)} 份（共 {len(ok_long)} 份）：", ""]
    if kf:
        L += ["| 组 | 长请求 | 第几次 | 哪一部分 | which | 引句 |", "|---|---|---|---|---|---|"]
        for r in kf:
            which = json.loads(r["k_which"] or "[]")
            pts = sorted({int(m_.group(1)) for w in which for m_ in [re.match(r"（第 (\d+) 部分）", w.strip())] if m_})
            L.append(f"| {r['model_name']} | {r['item_id']} | {r['repeat_idx']} | {', '.join(map(str, pts)) or '?'} "
                     f"| {_md('；'.join(which))} | {_md(' / '.join(json.loads(r['k_quotes'] or '[]')))[:200]} |")
    inc = [r for r in ok_long if r["incomplete"]]
    L += ["", f"没答全（incomplete）的 {len(inc)} 份：", ""]
    if inc:
        L += ["| 组 | 长请求 | 第几次 | 漏了什么 | 能按部分切开 |", "|---|---|---|---|---|"]
        for r in inc:
            L.append(f"| {r['model_name']} | {r['item_id']} | {r['repeat_idx']} | {_md('；'.join(json.loads(r['incomplete_missing'] or '[]')))} "
                     f"| {'否' if r['call_id'] in split_fail else '是'} |")
    notes = [r for r in ok_long if (r["k_note"] or "").strip().startswith("清单外")]
    L += ["", f"“清单外”备注 {len(notes)} 份：", ""]
    if notes:
        L += ["| 组 | 长请求 | 第几次 | 备注 |", "|---|---|---|---|"]
        L += [f"| {r['model_name']} | {r['item_id']} | {r['repeat_idx']} | {_md(r['k_note'])} |" for r in notes]
    L.append("")

    # 7. 待复核、重判、稳定性、花费
    nr = [r for r in long_ if r["status"] in ("needs_review", "error")]
    rj = defaultdict(int)
    for r in long_:
        for h in (json.loads(r["flags"] or "{}").get("rejudge_history") or []):
            rj[h["kind"]] += 1
    L += ["## 7. 待复核、重判、稳定性、花费", "",
          f"- 待复核（needs_review）{sum(r['status'] == 'needs_review' for r in long_)} 份，裁判失败 {sum(r['status'] == 'error' for r in long_)} 份。",
          f"- 重判：证据不合格 {rj['evidence']} 次，格式不对 {rj['format']} 次（只算最终记录里的重判历史）。"]
    if nr:
        L += ["", "| 组 | 长请求 | 第几次 | 状态 | 原因 |", "|---|---|---|---|---|"]
        L += [f"| {r['model_name']} | {r['item_id']} | {r['repeat_idx']} | {r['status']} | {_md(r['error'])} |" for r in nr]
    L.append("")
    L += consistency(R, conn, judge_name, prompt.sha256, sorted(long_items))
    L += costs(R, cfg, jcfg, gen_all, sorted(long_items), prompt.sha256)

    # 附录 A：逐步骤
    L += ["## 附录 A：推荐步骤逐条对比（103 个 × 2 组）", "",
          "| 长请求 | 部分 | 步骤 | 原步骤 | 步骤文字 | sol 短 | sol 长 | luna 短 | luna 长 |", "|---|---|---|---|---|---|---|---|---|"]
    for u in steps:
        cells = []
        for m in MODELS:
            a, n, b, k = u[m]
            mark = ""
            if n and k:
                d = b / k - a / n
                mark = " ▼" if d < -EPS else " ▲" if d > EPS else ""
            cells += [f"{a}/{n}", f"{b}/{k}{mark}"]
        L.append(f"| {u['lid']} | {u['part']} | {u['uid']} | {u['sid']}#{u['suid']} | {_md(u['text'])[:60]} | " + " | ".join(cells) + " |")
    L.append("")
    L += ["## 附录 B：SQL", "", "逐卡点、逐步骤的判断再从 judge_gate / judge_steps 按 judgment_id 取。", ""]
    for k, (title, sql) in enumerate(R.sqls, 1):
        L += [f"**Q{k}. {title}**", "", "```sql", sql, "```", ""]
    conn.close()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    return "\n".join(L) + "\n", out / f"long_dev__{Path(prompt.rel).stem}.md"


def consistency(R: Report, conn, judge_name: str, prompt_sha: str, long_ids: list[str]) -> list[str]:
    t, rows = R.q("长请求的第二遍（repeat_judgments）与第一遍配对", f"""
SELECT r.call_id, r.item_id, r.judge_run_id, r.sample_seed, r.status AS r_status, j.status AS j_status,
       c.model_name, j.id AS first_id, r.parsed_json AS p2, j.knowledge_pass AS k1, r.knowledge_pass AS k2
FROM repeat_judgments r JOIN judgments j ON j.id = r.first_judgment_id JOIN calls c ON c.id = r.call_id
WHERE r.judge_model_name = {_q(judge_name)} AND r.prompt_sha256 = {_q(prompt_sha)}
  AND r.item_id IN ({', '.join(_q(i) for i in long_ids)})
ORDER BY c.model_name, r.call_id""")
    L = [f"### 裁判稳定性：抽 12 份判第二遍 [{t}]", ""]
    if not rows:
        return L + ["还没有第二遍的记录。", ""]
    g1, s1 = unit_rows(conn, [r["first_id"] for r in rows])
    both = [r for r in rows if r["r_status"] == "ok" and r["j_status"] == "ok"]
    L += [f"- 随机种子 {', '.join(sorted({str(r['sample_seed']) for r in rows}))}，按（被测模型 × 课程）分层，每组 6 份、每门课 2 份；"
          f"judge_run {', '.join(sorted({r['judge_run_id'] for r in rows}))}；抽中的 call：{', '.join(str(r['call_id']) for r in rows)}。",
          f"- 第二遍 {len(rows)} 份：ok {sum(r['r_status'] == 'ok' for r in rows)}，待复核 {sum(r['r_status'] == 'needs_review' for r in rows)}，"
          f"失败 {sum(r['r_status'] == 'error' for r in rows)}；两遍都 ok 的 {len(both)} 份。", "",
          "| 组 | 份数 | 知识一致 | 卡点一致 | 步骤一致 |", "|---|---|---|---|---|"]
    dis = []
    tot = [0, 0, 0, 0, 0, 0]
    for m in MODELS + ["合计"]:
        sub = both if m == "合计" else [r for r in both if r["model_name"] == m]
        ka = sum(r["k1"] == r["k2"] for r in sub)
        ga = gt = sa = st = 0
        for r in sub:
            p2 = json.loads(r["p2"])
            b_g = {x["question_id"]: x["answered"] for x in p2["gate"]}
            b_s = {x["step_id"]: x["done"] for x in p2["steps"]}
            for q, v in g1[r["first_id"]].items():
                gt += 1
                ga += v == b_g.get(q)
                if m != "合计" and v != b_g.get(q):
                    dis.append((r["call_id"], r["item_id"], q, v, b_g.get(q)))
            for q, v in s1[r["first_id"]].items():
                st += 1
                sa += v == b_s.get(q)
                if m != "合计" and v != b_s.get(q):
                    dis.append((r["call_id"], r["item_id"], q, v, b_s.get(q)))
        L.append(f"| {m if m == '合计' else 'general_v1 × ' + m} | {len(sub)} | {_pct(ka, len(sub))} | {_pct(ga, gt)} | {_pct(sa, st)} |")
    if dis:
        L += ["", f"两遍不一致的项（{len(dis)} 处；1 = 答上/踩中）：", "", "| call | 长请求 | 项 | 第一遍 | 第二遍 |", "|---|---|---|---|---|"]
        L += [f"| {c} | {i} | {q} | {a} | {b} |" for c, i, q, a, b in sorted(dis)]
    L.append("")
    return L


def costs(R: Report, cfg: dict, jcfg: dict, gen_all: list[dict], long_ids: list[str], prompt_sha: str) -> list[str]:
    L = ["### 实际花费", "",
         "生成按 config 里各模型的标价算；“其中缓存”是接口报告的缓存输入 tokens。sol 的缓存单价 config 里没有，只给标价；"
         "luna 缓存输入按 $0.01、裁判按 $0.05 计（config 注释里的价格）。", "",
         "| 项目 | 调用 | 输入 tokens（其中缓存） | 输出 tokens | 标价 | 计缓存折扣 |", "|---|---|---|---|---|---|"]
    cache_price = {"gpt-6-luna": 0.01, "gpt-6.1-sol": None}
    tot_l = tot_d = 0.0
    for m in MODELS:
        g = [r for r in gen_all if r["model_name"] == m]
        mc = find_model(cfg, m)
        pr = mc.get("price_per_1m_tokens") or {}
        tin = sum(r["input_tokens"] or 0 for r in g); tout = sum(r["output_tokens"] or 0 for r in g)
        cached = sum(r["cached"] or 0 for r in g)
        lp = (tin * pr["input"] + tout * pr["output"]) / 1e6
        cp = cache_price[m]
        dp = ((tin - cached) * pr["input"] + cached * cp + tout * pr["output"]) / 1e6 if cp is not None else None
        tot_l += lp; tot_d += dp if dp is not None else lp
        L.append(f"| 生成 general_v1 × {m} | {len(g)} | {tin:,}（{cached:,}） | {tout:,} | ${lp:.3f} | "
                 + (f"${dp:.3f}" if dp is not None else "—（按标价计入合计）") + " |")
    pr = jcfg.get("price_per_1m_tokens") or {}
    ids = ", ".join(_q(i) for i in long_ids)
    for label, table in (("裁判第一遍", "judgments"), ("裁判第二遍", "repeat_judgments")):
        _, rows = R.q(f"长请求的裁判用量：{table}", f"""
SELECT count(*) AS n, sum(input_tokens) AS tin, sum(output_tokens) AS tout, sum(attempts) AS att,
       sum(coalesce(json_extract(usage_raw, '$.input_tokens_details.cached_tokens'), 0)) AS cached
FROM {table} WHERE item_id IN ({ids}) AND prompt_sha256 = {_q(prompt_sha)}""")
        r = rows[0]
        tin, tout, cached = r["tin"] or 0, r["tout"] or 0, r["cached"] or 0
        lp = (tin * pr["input"] + tout * pr["output"]) / 1e6
        dp = ((tin - cached) * pr["input"] + cached * 0.05 + tout * pr["output"]) / 1e6
        tot_l += lp; tot_d += dp
        L.append(f"| {label} | {r['n']} 份（{r['att'] or 0} 次调用） | {tin:,}（{cached:,}） | {tout:,} | ${lp:.3f} | ${dp:.3f} |")
    L += [f"| **合计** | | | | **${tot_l:.3f}** | **${tot_d:.3f}** |", "",
          "裁判的“缓存（最后一次）”只计每条记录最后一次调用报告的缓存；重判过的记录前几次按标价，所以折扣价是上限。",
          "",
          "**没有计入的部分**：第一次跑长请求时没用流式，非流式请求在约 60 秒时被网络断开（库里此前没有一次成功调用超过 60 秒）。"
          "被断开的尝试没有返回用量，表里算不到：sol 约 12 次（停掉前），luna 1 份重试 4 次后记为失败（库里那条 error，用量为空）、另有 2 次重试后成功。"
          "如果这些尝试在服务端照常生成并计费，按每次约 60 秒、sol 约 4,000 个输出 token 估，sol 最多约 $0.5，luna 可忽略。", ""]
    return L


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.longreport", description="长请求验证报告")
    ap.add_argument("--short-items", default="data/items.jsonl")
    ap.add_argument("--long-items", default="data/items_long_dev.jsonl")
    ap.add_argument("--map", default="data/items_long_dev_map.json")
    ap.add_argument("--skill", default="skills/general_v1.md")
    ap.add_argument("--judge-prompt", default="prompts/judge_v2.md")
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
