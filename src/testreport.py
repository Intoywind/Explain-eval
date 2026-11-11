"""正式测试报告（第七份输入第 4 节）：合并评测集，原课程 Skill、通用 V1、通用 V2 三份 × 两个模型。

python -m src.merged && python -m src.testreport --out reports/

- 分数来自 merged_scores 表（src.merged 写入；每份回答一行，含清零前后的卡点分、步骤分和失败记 0）。
- 得分率 = 得分之和 ÷ 满分之和。生成失败的回答记 0、分母照算；needs_review 和没评过的不进分子分母，单独列出。
- 逐卡点、逐步骤的“答上率 / 做到率”直接用裁判对每一项的 answered / done（引句校验后，不套清零），只算 ok 的回答。
- 规则标签（items_long_test_rule_map.json）和过程 / 结果（items_long_test_aspect_map.json）只在这里做分组统计。
- 每张表后的 [Qn] 指向附录的 SQL；主结果另附一条可单独运行的查询。
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
from .merged import GROUPS, MODELS
from .report import Report, _md, _q
from .run import UsageError, _rel, find_model, load_config

GN = {"original_eval": "原课程", "general_v1": "V1", "general_v2": "V2"}
SN = {"gpt-6.1-sol": "sol", "gpt-6-luna": "luna"}
TIERS = ["长题", "短题"]
KINDS = ["做题类", "概念理解类", "短题"]
COURSES = ["COMP2711", "IEDA1280", "ECON1221"]
READERS = ["零基础", "有前置"]
GAP_TYPES = ["术语未先定义", "切换处漏连接", "公式未接含义", "前提未交代"]
SEVERITIES = ["读者没法往下读", "只是不顺"]
LEVELS = ["原话", "报告定位", "推测"]
PREREQ_MARK = "先拿来用了、到后面才补上的，不算"
CACHE_PRICE = {"gpt-6-luna": 0.01, "gpt-6.1-sol": None}
JUDGE_CACHE_PRICE = 0.05
EPS = 1e-9

MAIN_SQL = """-- 主结果：各组合并卡点分得分率（生成失败记 0、分母照算；needs_review / 没评过的不计）
SELECT model_name, skill_group,
       sum(gate_score) AS gate_points, sum(gate_max) AS gate_max,
       round(100.0 * sum(gate_score) / sum(gate_max), 2) AS gate_rate_pct,
       count(*) AS n_responses, sum(failed) AS n_failed
FROM merged_scores
WHERE status IN ('ok', 'failed')
GROUP BY model_name, skill_group
ORDER BY model_name, skill_group;"""


def _pct(v, nd=1):
    return "—" if v is None else f"{100 * v:.{nd}f}%"


def _pp(a, b):
    if a is None or b is None:
        return "—"
    d = 100 * (b - a)
    return f"{0.0 if abs(d) < 0.05 else d:+.1f}"


def _rate(rows, num="gate_score", den="gate_max"):
    rs = [r for r in rows if r["status"] in ("ok", "failed")]
    d = sum(r[den] for r in rs)
    return (sum(r[num] for r in rs) / d) if d else None, sum(r[num] for r in rs), d


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _short(s, n=120):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n] + "…"


def build(args):
    cfg = load_config(Path(args.config))
    jcfg = judge_model_cfg(cfg)
    prompt = load_prompt(Path(args.judge_prompt))
    items, items_rel = load_items(Path(args.items), False)
    rule_map = json.loads(Path(args.rule_map).read_text(encoding="utf-8"))
    aspect_map = json.loads(Path(args.aspect_map).read_text(encoding="utf-8"))
    conn = db.connect(db_path_from_config(cfg))
    R = Report(conn)
    t_ms, MS = R.q("每份回答的计分（merged_scores，src.merged 写入）", """
SELECT m.*, rc.char_count, j.n_redundancy, j.attempts AS j_attempts, j.flags AS j_flags, j.error AS j_error,
       json_extract(j.parsed_json, '$.knowledge_error') AS kerr, json_extract(j.parsed_json, '$.incomplete') AS incomp
FROM merged_scores m
LEFT JOIN rule_checks rc ON rc.call_id = m.call_id
LEFT JOIN judgments j ON j.id = m.judgment_id
ORDER BY m.model_name, m.skill_group, m.item_id, m.repeat_idx""")
    if not MS:
        raise UsageError("merged_scores 是空的，先运行 python -m src.merged")
    t_g, GATE = R.q("逐卡点（只取 merged_scores 里 ok 的回答；answered 是引句校验后的值，不套清零）", """
SELECT m.skill_group, m.model_name, m.item_id, m.repeat_idx, m.tier, m.kind, m.course, m.reader,
       g.question_id, g.answered, g.reason, m.judgment_id
FROM merged_scores m JOIN judge_gate g ON g.judgment_id = m.judgment_id
WHERE m.status = 'ok'""")
    t_s, STEP = R.q("逐步骤（同上，done 不套清零）", """
SELECT m.skill_group, m.model_name, m.item_id, m.repeat_idx, m.tier, m.reader, s.step_id, s.done
FROM merged_scores m JOIN judge_steps s ON s.judgment_id = m.judgment_id
WHERE m.status = 'ok'""")
    t_gap, GAPS = R.q("跳步（只取 ok 的回答、引句通过校验的）", """
SELECT m.skill_group, m.model_name, m.tier, m.reader, g.subtype, g.severity
FROM merged_scores m JOIN judge_gaps g ON g.judgment_id = m.judgment_id
WHERE m.status = 'ok' AND g.quote_valid = 1""")

    def sub(xs, g=None, m=None, **kw):
        return [x for x in xs if (g is None or x["skill_group"] == g) and (m is None or x["model_name"] == m)
                and all(x[k] == v for k, v in kw.items())]

    srcl = {(iid, q["id"]): q["source_level"] for iid, it in items.items() for q in it["gate_questions"]}
    prereq = {(iid, q["id"]) for iid, it in items.items() if it["tier"] == "长题"
              for q in it["gate_questions"] if PREREQ_MARK in q["accept"]}
    for g in GATE:
        k = f"{g['item_id']}#{g['question_id']}"
        g["rule"], g["aspect"] = rule_map.get(k), aspect_map.get(k)
        g["level"] = srcl[(g["item_id"], g["question_id"])]

    n_by = Counter((r["skill_group"], r["model_name"], r["status"]) for r in MS)
    L = [f"# 正式测试：原课程 Skill、通用 V1、通用 V2（合并评测集，{prompt.rel}）", "",
         f"- 条目：`{items_rel}`（60 条：长题 30、短题 30），md5 02c0dc26e61799b7d2f7547195f11bee；每组每条 3 次。",
         "- 组 = Skill × 被测模型。原课程 = `skills/original_eval/` 里按课程选的那份；V1 = `skills/general_v1.md`；"
         "V2 = `skills/general_v2.md`（md5 32ab9d6e…，第五稿）。sol = gpt-6.1-sol，luna = gpt-6-luna。",
         f"- 裁判：{jcfg['name']}，prompt `{prompt.rel}`（sha256 {prompt.sha256[:12]}…）。短题沿用已有的回答和判分（判分清单哈希已核对一致），长题是这一轮新生成、新判的。",
         "- 分值：长题每个卡点、步骤 2 分，短题 1 分；卡点满分每组每遍 391、步骤 577（3 次重复各乘 3）。"
         "清零按每条的 `zero_rule`：短题、做题类整份清零；概念理解类只清讲错的那一部分。生成失败记 0、分母照算。",
         f"- 生成时间：{datetime.now(timezone.utc).isoformat(timespec='seconds')}。每张表后的 [Qn] 指向附录 SQL。", ""]

    # 0. 份数
    L += [f"## 0. 份数 [{t_ms}]", "", "| 模型 | Skill | 回答 | ok | 生成失败记 0 | 待复核 | 判分出错 | 没评 |", "|---|---|---|---|---|---|---|---|"]
    for m in MODELS:
        for g in GROUPS:
            L.append(f"| {SN[m]} | {GN[g]} | {sum(v for (a, b, _), v in n_by.items() if a == g and b == m)} | "
                     + " | ".join(str(n_by.get((g, m, s), 0)) for s in ("ok", "failed", "needs_review", "error", "unjudged")) + " |")
    pending = sum(v for (a, b, s), v in n_by.items() if s in ("needs_review", "error", "unjudged"))
    L += ["", "待复核、判分出错、没评的回答不进得分率的分子和分母" + (f"（共 {pending} 份，见第 11 节）。" if pending else "（这一轮没有）。"), ""]

    # 1. 主结果
    def rates_row(rows_fn, num="gate_score", den="gate_max"):
        rr = {g: _rate(rows_fn(g), num, den) for g in GROUPS}
        o, a, b = (rr[g][0] for g in GROUPS)
        cells = " | ".join(f"{_pct(rr[g][0])}（{rr[g][1]:,}/{rr[g][2]:,}）" for g in GROUPS)
        return cells + f" | {_pp(a, b)} | {_pp(o, b)} | {_pp(o, a)}"

    hdr = "| 原课程 | V1 | V2 | V2 − V1（百分点） | V2 − 原课程 | V1 − 原课程 |"
    L += [f"## 1. 主结果：合并卡点分得分率 [{t_ms}]", "",
          "得分率 = 清零后卡点得分之和 ÷ 卡点满分之和（每组 180 份回答，满分 391 × 3 = 1,173）。**主指标：sol 上 V2 − V1**，目标 15 个百分点。", "",
          "| 模型 " + hdr, "|---|---|---|---|---|---|---|"]
    main = {}
    for m in MODELS:
        L.append(f"| {SN[m]} | " + rates_row(lambda g, m=m: sub(MS, g, m)) + " |")
        main[m] = {g: _rate(sub(MS, g, m))[0] for g in GROUPS}
    d = 100 * (main["gpt-6.1-sol"]["general_v2"] - main["gpt-6.1-sol"]["general_v1"])
    L += ["", f"**主指标（sol，V2 − V1）：{d:+.1f} 个百分点**；目标 15 个百分点，"
          + ("达到。" if d >= 15 - 1e-9 else "没有达到。"), ""]

    # 2. 稳定性
    units = sorted({r["unit"] for r in MS})
    L += [f"## 2. 差异稳不稳：以“一道题”为单位 [{t_ms}]", "",
          f"单位 = 一道题（长题 15 道、短题 15 个知识点，两个读者版本合成一个单位，共 {len(units)} 个）。每个单位把 3 次重复 × 两个读者版本的清零后卡点得分加起来比较。"
          f"区间：以单位为单位有放回抽样 {args.boot} 次（种子 {args.boot_seed}），每次重算整体得分率之差，取 2.5% 和 97.5% 分位。", "",
          "| 模型 | 比较 | 点估计（百分点） | 95% 区间 | 单位：上升 / 持平 / 下降 |", "|---|---|---|---|---|"]
    for m in MODELS:
        us = {}
        for u in units:
            rows_u = [r for r in sub(MS, m=m) if r["unit"] == u and r["status"] in ("ok", "failed")]
            us[u] = {g: (sum(r["gate_score"] for r in rows_u if r["skill_group"] == g),
                         sum(r["gate_max"] for r in rows_u if r["skill_group"] == g)) for g in GROUPS}
        for a, b in (("general_v1", "general_v2"), ("original_eval", "general_v2"), ("original_eval", "general_v1")):
            def diff(sample):
                na = sum(us[u][a][0] for u in sample); da = sum(us[u][a][1] for u in sample)
                nb = sum(us[u][b][0] for u in sample); db_ = sum(us[u][b][1] for u in sample)
                return 100 * (nb / db_ - na / da) if da and db_ else 0.0
            point = diff(units)
            rng = random.Random(args.boot_seed)
            boots = sorted(diff([rng.choice(units) for _ in units]) for _ in range(args.boot))
            lo, hi = boots[int(0.025 * args.boot)], boots[int(0.975 * args.boot) - 1]
            up = sum(us[u][b][0] > us[u][a][0] for u in units)
            dn = sum(us[u][b][0] < us[u][a][0] for u in units)
            L.append(f"| {SN[m]} | {GN[b]} − {GN[a]} | {point:+.1f} | [{lo:+.1f}, {hi:+.1f}] | {up} / {len(units) - up - dn} / {dn} |")
    L += ["", "每个单位的满分在各组之间相同（同样的条目、同样 3 次）；生成失败的回答记 0 计入。", ""]

    # 3. 分开看
    def breakdown(title, num, den, tag):
        out = [f"## {title} [{tag}]", "", "每格：得分率（得分/满分）。差值单位是百分点。", ""]
        for dim, vals, fld in (("长题 / 短题", TIERS, "tier"), ("题型", KINDS, "kind"), ("课程", COURSES, "course"),
                               ("读者版本", READERS, "reader")):
            out += [f"### 按{dim}", "", "| 模型 | " + dim + " " + hdr, "|---|---|---|---|---|---|---|---|"]
            for m in MODELS:
                for v in vals:
                    out.append(f"| {SN[m]} | {v} | " + rates_row(lambda g, m=m, v=v: sub(MS, g, m, **{fld: v}), num, den) + " |")
            out.append("")
        return out

    L += breakdown("3. 分开看：卡点分", "gate_score", "gate_max", t_ms)

    # 4. 步骤分
    L += [f"## 4. 步骤分（只当对照）[{t_ms}]", "", "### 汇总", "", "| 模型 " + hdr, "|---|---|---|---|---|---|---|"]
    for m in MODELS:
        L.append(f"| {SN[m]} | " + rates_row(lambda g, m=m: sub(MS, g, m), "step_score", "step_max") + " |")
    L += [""] + breakdown("4b. 分开看：步骤分", "step_score", "step_max", t_ms)[1:]
    L += ["### 步骤得分率和卡点得分率并排", "", "| 模型 | Skill | 卡点得分率 | 步骤得分率 | 步骤 − 卡点（百分点） |", "|---|---|---|---|---|"]
    for m in MODELS:
        for g in GROUPS:
            gr, sr = _rate(sub(MS, g, m))[0], _rate(sub(MS, g, m), "step_score", "step_max")[0]
            L.append(f"| {SN[m]} | {GN[g]} | {_pct(gr)} | {_pct(sr)} | {_pp(gr, sr)} |")
    gate_by_j = defaultdict(list)
    for x in GATE:
        gate_by_j[x["judgment_id"]].append(x)
    L += ["", "### 步骤得分率高于本组中位数、但卡点没全答上的回答", "",
          "组 = Skill × 模型。步骤得分率 = 这份回答清零后的步骤得分 ÷ 步骤满分；“卡点没全答上”看每个卡点的 answered（不套清零）。"
          "中位数在本组 ok 的回答里算，“高于”是严格大于；中位数已是 100% 时没有回答能严格高于它，这时改列“步骤 100% 但卡点没全答上”的。", ""]
    for m in MODELS:
        for g in GROUPS:
            ok = [r for r in sub(MS, g, m) if r["status"] == "ok"]
            rate = {id(r): r["step_score"] / r["step_max"] for r in ok}
            med = statistics.median(rate.values())
            full = med >= 1 - EPS
            sel = [r for r in ok if (rate[id(r)] >= 1 - EPS if full else rate[id(r)] > med + EPS)
                   and any(not x["answered"] for x in gate_by_j[r["judgment_id"]])]
            L += [f"#### {SN[m]} × {GN[g]}：中位数 {_pct(med)}"
                  + ("（已是 100%，改列步骤 100% 的）" if full else "") + f"，符合的 {len(sel)} 份"
                  + f"（长题 {sum(r['tier'] == '长题' for r in sel)}、短题 {sum(r['tier'] == '短题' for r in sel)}）", ""]
            if sel:
                L += ["| 条目 | 第几次 | 步骤得分率 | 没答上的卡点（过程 / 结果） |", "|---|---|---|---|"]
                for r in sel:
                    miss = [x for x in gate_by_j[r["judgment_id"]] if not x["answered"]]
                    L.append(f"| {r['item_id']} | {r['repeat_idx']} | {_pct(rate[id(r)])} | "
                             + "，".join(f"{x['question_id']}（{x['aspect'] or '短题'}）" for x in sorted(miss, key=lambda x: x["question_id"])) + " |")
                L.append("")
            n_proc = sum(1 for r in sel for x in gate_by_j[r["judgment_id"]] if not x["answered"] and x["aspect"] == "过程")
            n_res = sum(1 for r in sel for x in gate_by_j[r["judgment_id"]] if not x["answered"] and x["aspect"] == "结果")
            if sel:
                L += [f"没答上的长题卡点里：过程类 {n_proc} 个，结果类 {n_res} 个。", ""]

    # 5. 知识错误和没答全
    L += [f"## 5. 知识错误和没答全 [{t_ms}]", "",
          "| 模型 | Skill | ok | 知识不通过（长题 / 短题） | 其中概念理解类只清一部分的 | 没答全（长题 / 短题） | 清零前卡点得分率 | 清零后 | 清零差（百分点） |",
          "|---|---|---|---|---|---|---|---|---|"]
    for m in MODELS:
        for g in GROUPS:
            ok = [r for r in sub(MS, g, m) if r["status"] == "ok"]
            kf = [r for r in ok if r["knowledge_pass"] == 0]
            inc = [r for r in ok if r["incomplete"] == 1]
            raw = _rate(sub(MS, g, m), "gate_raw", "gate_max")[0] if all(r["gate_raw"] is not None for r in sub(MS, g, m) if r["status"] in ("ok", "failed")) else None
            aft = _rate(sub(MS, g, m))[0]
            L.append(f"| {SN[m]} | {GN[g]} | {len(ok)} | {len(kf)}（{sum(r['tier'] == '长题' for r in kf)} / {sum(r['tier'] == '短题' for r in kf)}） "
                     f"| {sum(r['kind'] == '概念理解类' for r in kf)} | {len(inc)}（{sum(r['tier'] == '长题' for r in inc)} / {sum(r['tier'] == '短题' for r in inc)}） "
                     f"| {_pct(raw)} | {_pct(aft)} | {_pp(raw, aft)} |")
    L += ["", "清零前得分率里生成失败的回答也记 0。", "", "### 知识不通过的回答逐份（长题）", "",
          "| 模型 | Skill | 条目 | 第几次 | 题型 | 清零 | 卡点 清零前 → 后 | which |", "|---|---|---|---|---|---|---|---|"]
    for r in [r for r in MS if r["status"] == "ok" and r["knowledge_pass"] == 0 and r["tier"] == "长题"]:
        zp = r["zeroed_parts"]
        zp = "整份" if zp == "all" else ("第 " + "、".join(str(x) for x in json.loads(zp)) + " 部分" if zp else "—")
        which = (json.loads(r["kerr"] or "{}") or {}).get("which") or []
        L.append(f"| {SN[r['model_name']]} | {GN[r['skill_group']]} | {r['item_id']} | {r['repeat_idx']} | {r['kind']} | {zp} "
                 f"| {r['gate_raw']} → {r['gate_score']} | {_md('；'.join(_short(w, 60) for w in which))} |")
    L.append("")

    # 7. 规则标签、过程 / 结果、跳步
    L += [f"## 7. 按规则标签、过程 / 结果分组；跳步 [{t_g}] [{t_gap}]", "", "### 按规则标签（长题卡点，只做描述）", "",
          "每格：答上率（答上次数/判过次数），不套清零。", "",
          "| 规则标签 | 卡点数 | " + " | ".join(f"{SN[m]} {GN[g]}" for m in MODELS for g in GROUPS) + " |",
          "|---|---|" + "---|" * (len(MODELS) * len(GROUPS))]
    long_gate = [x for x in GATE if x["tier"] == "长题"]

    def ans(xs):
        return f"{_pct(_mean([x['answered'] for x in xs]))}（{sum(x['answered'] for x in xs)}/{len(xs)}）" if xs else "—"

    tags = sorted({v for v in rule_map.values()}, key=lambda t: (not t.startswith("规则"), int(re.sub(r"\D", "", t) or 0), t))
    for t in tags:
        n = sum(1 for v in rule_map.values() if v == t)
        L.append(f"| {t} | {n} | " + " | ".join(ans([x for x in long_gate if x["rule"] == t and x["skill_group"] == g and x["model_name"] == m])
                                                for m in MODELS for g in GROUPS) + " |")
    L += ["", "### 按过程 / 结果（长题卡点）", "",
          f"过程 {sum(v == '过程' for v in aspect_map.values())} 个、结果 {sum(v == '结果' for v in aspect_map.values())} 个"
          f"（零基础版过程 {sum(v == '过程' for k, v in aspect_map.items() if '零基础' in k)} 个，有前置版过程 {sum(v == '过程' for k, v in aspect_map.items() if '有前置' in k)} 个）。差值是答上率之差（百分点）。", "",
          "| 模型 | 类别 | 读者版本 | 原课程 | V1 | V2 | V2 − V1 | V2 − 原课程 |", "|---|---|---|---|---|---|---|---|"]
    for m in MODELS:
        for asp in ("过程", "结果"):
            for rd in READERS + [None]:
                xs = {g: [x for x in long_gate if x["aspect"] == asp and x["skill_group"] == g and x["model_name"] == m
                          and (rd is None or x["reader"] == rd)] for g in GROUPS}
                rt = {g: _mean([x["answered"] for x in xs[g]]) for g in GROUPS}
                if not xs["general_v1"]:
                    continue
                L.append(f"| {SN[m]} | {asp} | {rd or '合计'} | " + " | ".join(ans(xs[g]) for g in GROUPS)
                         + f" | {_pp(rt['general_v1'], rt['general_v2'])} | {_pp(rt['original_eval'], rt['general_v2'])} |")
    no_proc = sorted({k.split('#')[0] for k in aspect_map} - {k.split('#')[0] for k, v in aspect_map.items() if v == "过程"})
    L += ["", f"没有过程卡点的条目（{len(no_proc)} 条）：{'、'.join(no_proc)}；这几条的过程一头看下面的跳步比例。", "",
          "### 跳步：有严重跳步的回答占比", "",
          "“有严重跳步”= 至少有一处“读者没法往下读”且引句通过校验的跳步（`judgments.n_gaps_blocking > 0`）。只做描述，不进主指标。", "",
          "| 模型 | 长题 / 短题 | 读者版本 | 原课程 | V1 | V2 |", "|---|---|---|---|---|---|"]
    for m in MODELS:
        for tr in TIERS:
            for rd in READERS + [None]:
                cells = []
                for g in GROUPS:
                    ok = [r for r in sub(MS, g, m, tier=tr) if r["status"] == "ok" and (rd is None or r["reader"] == rd)]
                    nb = sum((r["n_gaps_blocking"] or 0) > 0 for r in ok)
                    cells.append(f"{_pct(nb / len(ok) if ok else None)}（{nb}/{len(ok)}）")
                L.append(f"| {SN[m]} | {tr} | {rd or '合计'} | " + " | ".join(cells) + " |")
    L += ["", "### 跳步按类型 × 严重程度的条数（引句通过校验的；长题 / 短题）", "",
          "| 模型 | 类型 | 严重程度 | " + " | ".join(GN[g] for g in GROUPS) + " |", "|---|---|---|---|---|---|"]
    gc = Counter((x["model_name"], x["skill_group"], x["subtype"], x["severity"], x["tier"]) for x in GAPS)
    for m in MODELS:
        for t in GAP_TYPES:
            for sv in SEVERITIES:
                L.append(f"| {SN[m]} | {t} | {sv} | " + " | ".join(f"{gc.get((m, g, t, sv, '长题'), 0)} / {gc.get((m, g, t, sv, '短题'), 0)}" for g in GROUPS) + " |")
    L.append("")

    # 8. 证据级别
    L += [f"## 8. 按卡点的证据级别（source_level）[{t_g}]", "", "长题、短题合在一起；答上率不套清零。", "",
          "| 模型 | 证据级别 | 卡点数 | 原课程 | V1 | V2 | V2 − V1 |", "|---|---|---|---|---|---|---|"]
    for m in MODELS:
        for lv in LEVELS:
            xs = {g: [x for x in GATE if x["level"] == lv and x["skill_group"] == g and x["model_name"] == m] for g in GROUPS}
            n = sum(1 for v in srcl.values() if v == lv)
            L.append(f"| {SN[m]} | {lv} | {n} | " + " | ".join(ans(xs[g]) for g in GROUPS)
                     + f" | {_pp(_mean([x['answered'] for x in xs['general_v1']]), _mean([x['answered'] for x in xs['general_v2']]))} |")
    L.append("")

    # 9. 篇幅和冗余
    L += [f"## 9. 篇幅和冗余（长题）[{t_ms}]", "", "字数 = 回答全文的字符数（含标点、公式源码和空白）；只算 ok 的长回答。冗余 = 裁判记下、引句通过校验的冗余条数。", "",
          "| 模型 | 读者版本 | 原课程 平均字数 | V1 | V2 | V2 ÷ V1 | V2 ÷ 原课程 | 冗余条数（原课程 / V1 / V2） |", "|---|---|---|---|---|---|---|---|"]
    for m in MODELS:
        for rd in READERS + [None]:
            ok = {g: [r for r in sub(MS, g, m, tier="长题") if r["status"] == "ok" and (rd is None or r["reader"] == rd)] for g in GROUPS}
            avg = {g: _mean([r["char_count"] for r in ok[g]]) for g in GROUPS}
            red = {g: sum(r["n_redundancy"] or 0 for r in ok[g]) for g in GROUPS}
            ratio = lambda a, b: f"{avg[b] / avg[a]:.2f}" if avg[a] and avg[b] else "—"
            L.append(f"| {SN[m]} | {rd or '合计'} | " + " | ".join(f"{avg[g]:,.0f}" if avg[g] else "—" for g in GROUPS)
                     + f" | {ratio('general_v1', 'general_v2')} | {ratio('original_eval', 'general_v2')} | "
                     + " / ".join(str(red[g]) for g in GROUPS) + " |")
    L.append("")

    # 10. 卡点全答上、结果类全答上且没被判没答全；前置概念卡点稳定性
    L += [f"## 10. “卡点全部答上”的份数占比；结果类卡点全答上且没答全 [{t_ms}] [{t_g}]", "",
          "“卡点全答上”= 知识通过且所有卡点 answered（和以前的 gate_all 一样）；不是主指标。“更严的”只看长题：结果类卡点全部 answered，且没有被判没答全。", "",
          "| 模型 | Skill | 卡点全答上：长题 | 短题 | 长题更严：结果类全答上且没被判没答全 | 结果类全答上但被判没答全 |", "|---|---|---|---|---|---|"]
    res_inc = []
    for m in MODELS:
        for g in GROUPS:
            cells = []
            for tr in TIERS:
                ok = [r for r in sub(MS, g, m, tier=tr) if r["status"] == "ok"]
                n = sum(r["knowledge_pass"] == 1 and all(x["answered"] for x in gate_by_j[r["judgment_id"]]) for r in ok)
                cells.append(f"{_pct(n / len(ok) if ok else None)}（{n}/{len(ok)}）")
            ok = [r for r in sub(MS, g, m, tier="长题") if r["status"] == "ok"]
            res_all = [r for r in ok if all(x["answered"] for x in gate_by_j[r["judgment_id"]] if x["aspect"] == "结果")]
            strict = [r for r in res_all if not r["incomplete"]]
            ri = [r for r in res_all if r["incomplete"]]
            res_inc += ri
            L.append(f"| {SN[m]} | {GN[g]} | {cells[0]} | {cells[1]} | {_pct(len(strict) / len(ok) if ok else None)}（{len(strict)}/{len(ok)}） | {len(ri)} |")
    L += ["", f"### 结果类卡点全答上但被判没答全的回答：{len(res_inc)} 份", ""]
    if res_inc:
        L += ["| 模型 | Skill | 条目 | 第几次 | 缺了什么（裁判的 missing） |", "|---|---|---|---|---|"]
        for r in res_inc:
            ic = json.loads(r["incomp"] or "{}") or {}
            L.append(f"| {SN[r['model_name']]} | {GN[r['skill_group']]} | {r['item_id']} | {r['repeat_idx']} | {_md('；'.join(ic.get('missing') or []) or _short(ic.get('note'), 100))} |")
    L.append("")
    L += repeat_section(R, jcfg["name"], prompt.sha256, items, prereq, args.repeat_seed)

    # 11. 失败、待复核、重判、花费
    L += [f"## 11. 失败记 0、待复核、重判次数、实际花费 [{t_ms}]", ""]
    fails = [r for r in MS if r["status"] == "failed"]
    L += [f"### 生成失败、记 0 的回答：{len(fails)} 份", ""]
    if fails:
        t_f, frows = R.q("生成失败的回答的调用记录", """
SELECT m.skill_group, m.model_name, m.item_id, m.repeat_idx, count(c.id) AS n_calls,
       group_concat(coalesce(c.finish_reason, '') || ' ' || coalesce(substr(c.error, 1, 80), ''), ' | ') AS errs
FROM merged_scores m LEFT JOIN calls c ON c.item_id = m.item_id AND c.model_name = m.model_name
     AND c.skill_file = m.skill_file AND c.repeat_idx = m.repeat_idx
WHERE m.status = 'failed' GROUP BY 1, 2, 3, 4""")
        L += [f"[{t_f}]", "", "| 模型 | Skill | 条目 | 第几次 | 调用次数 | 最后的错误 |", "|---|---|---|---|---|---|"]
        L += [f"| {SN[r['model_name']]} | {GN[r['skill_group']]} | {r['item_id']} | {r['repeat_idx']} | {r['n_calls']} | {_md(_short(r['errs'], 160))} |" for r in frows]
    nr = [r for r in MS if r["status"] in ("needs_review", "error", "unjudged")]
    L += ["", f"### 待复核、判分出错、没评：{len(nr)} 份", ""]
    L += [f"- {SN[r['model_name']]} × {GN[r['skill_group']]}｜{r['item_id']} 第 {r['repeat_idx']} 次（call {r['call_id']}）：{r['status']}｜{_short(r['j_error'], 200)}" for r in nr]
    long_j = [r for r in MS if r["tier"] == "长题" and r["judgment_id"] is not None]
    hist = Counter()
    n_rej = 0
    for r in long_j:
        h = (json.loads(r["j_flags"] or "{}") or {}).get("rejudge_history") or []
        n_rej += bool(h)
        for x in h:
            hist[x.get("kind")] += 1
    L += ["", f"### 重判：长题第一遍 {len(long_j)} 份里重判过的 {n_rej} 份，共重判 {sum(hist.values())} 次"
          + (f"（{'，'.join(f'{k} {v} 次' for k, v in sorted(hist.items()))}；format = 输出格式不对，evidence = 证据不合格）" if hist else "") + "。", ""]
    L += costs(R, cfg, jcfg, items_rel, prompt.sha256)

    # 附录：逐卡点
    L += [f"## 附录 A（第 6 项）：长题逐卡点对比 [{t_g}]", "", "每格是“答上次数/判过次数”（每个模型每组 3 次），不套清零。", "",
          "| 条目 | 卡点 | 过程 / 结果 | 规则标签 | " + " | ".join(f"{SN[m]} {GN[g]}" for m in MODELS for g in GROUPS) + " |",
          "|---|---|---|---|" + "---|" * (len(MODELS) * len(GROUPS))]
    cnt = defaultdict(lambda: [0, 0])
    for x in long_gate:
        k = (x["skill_group"], x["model_name"], x["item_id"], x["question_id"])
        cnt[k][0] += x["answered"]
        cnt[k][1] += 1
    for iid, it in items.items():
        if it["tier"] != "长题":
            continue
        for q in it["gate_questions"]:
            k = f"{iid}#{q['id']}"
            L.append(f"| {iid} | {q['id']} | {aspect_map.get(k, '—')} | {rule_map.get(k, '—')} | "
                     + " | ".join((lambda c: f"{c[0]}/{c[1]}" if c[1] else "—")(cnt[(g, m, iid, q['id'])]) for m in MODELS for g in GROUPS) + " |")
    L += ["", "## 附录 B：主结果的查询", "", "在 `sqlite3 results/eval.db` 里运行（先跑 `python -m src.merged` 写 merged_scores）：", "",
          "```sql", MAIN_SQL, "```", "", "重算全部：`python -m src.merged && python -m src.testreport --out reports/`。", "",
          "## 附录 C：其余 SQL", ""]
    for k, (title, sql) in enumerate(R.sqls, 1):
        L += [f"### Q{k}. {title}", "", "```sql", sql, "```", ""]
    conn.close()
    return "\n".join(L), Path(args.out) / f"test_three_skills__{Path(args.judge_prompt).stem}.md"


def repeat_section(R, judge_name, prompt_sha, items, prereq, seed) -> list[str]:
    t, rows = R.q("长回答第二遍（repeat_judgments）与第一遍配对", f"""
SELECT r.call_id, r.item_id, r.sample_seed, r.judge_run_id, r.status AS r_status, j.status AS j_status,
       m.skill_group, m.model_name, j.knowledge_pass AS k1, r.knowledge_pass AS k2,
       json_extract(j.parsed_json, '$.knowledge_error.which') AS w1, json_extract(r.parsed_json, '$.knowledge_error.which') AS w2,
       j.parsed_json AS p1, r.parsed_json AS p2
FROM repeat_judgments r JOIN judgments j ON j.id = r.first_judgment_id
JOIN merged_scores m ON m.call_id = r.call_id AND m.tier = '长题'
WHERE r.judge_model_name = {_q(judge_name)} AND r.prompt_sha256 = {_q(prompt_sha)} AND r.sample_seed = {int(seed)}
ORDER BY r.call_id""")
    L = [f"### 裁判判两遍：长回答 54 份（六组各 9 份）[{t}]", ""]
    if not rows:
        return L + ["还没有第二遍的记录。", ""]
    both = [r for r in rows if r["r_status"] == "ok" and r["j_status"] == "ok"]
    L += [f"- 种子 {seed}；judge_run {', '.join(sorted({r['judge_run_id'] for r in rows}))}；抽中 {len(rows)} 份，"
          + "，".join(f"{SN[m]} {GN[g]} {sum(r['skill_group'] == g and r['model_name'] == m for r in rows)}" for m in MODELS for g in GROUPS)
          + f"；两遍都 ok 的 {len(both)} 份。", "",
          "| 范围 | 份数 | 知识判断一致 | which 也一致 | 卡点一致率 | 步骤一致率 |", "|---|---|---|---|---|---|"]
    pre_ag = pre_n = 0
    pre_dis = []
    for scope in [None] + MODELS:
        bs = [r for r in both if scope is None or r["model_name"] == scope]
        ka = sum(r["k1"] == r["k2"] for r in bs)
        wa = sum(r["k1"] == r["k2"] and sorted(json.loads(r["w1"] or "[]")) == sorted(json.loads(r["w2"] or "[]")) for r in bs)
        res = {}
        for kind, idk, vk in (("gate", "question_id", "answered"), ("steps", "step_id", "done")):
            ag = tot = 0
            for r in bs:
                a = {u[idk]: u[vk] for u in json.loads(r["p1"])[kind]}
                b = {u[idk]: u[vk] for u in json.loads(r["p2"])[kind]}
                for k in a:
                    tot += 1
                    ag += a[k] == b.get(k)
                    if scope is None and kind == "gate" and (r["item_id"], k) in prereq:
                        pre_n += 1
                        pre_ag += a[k] == b.get(k)
                        if a[k] != b.get(k):
                            pre_dis.append(f"{SN[r['model_name']]} {GN[r['skill_group']]}｜{r['item_id']}（call {r['call_id']}）{k}：第一遍 {a[k]}，第二遍 {b.get(k)}")
            res[kind] = (ag, tot)
        L.append(f"| {SN.get(scope, '合计')} | {len(bs)} | {ka}/{len(bs)} | {wa}/{len(bs)} | "
                 + " | ".join(f"{_pct(a / n if n else None)}（{a}/{n}）" for a, n in (res["gate"], res["steps"])) + " |")
    L += ["", f"**前置概念卡点**（判据里有“{PREREQ_MARK}”的，长题 {len(prereq)} 个位次）：在这 54 份里出现 {pre_n} 次，"
          f"两遍一致 {pre_ag}/{pre_n}（{_pct(pre_ag / pre_n if pre_n else None)}）。" + ("两遍不一样的：" if pre_dis else "没有判得不一样的。")]
    L += [f"- {x}" for x in pre_dis] + [""]
    return L


def costs(R, cfg, jcfg, items_rel, prompt_sha) -> list[str]:
    L = ["### 实际花费（这一轮：长题的生成和判分；短题沿用，不另花钱）", "",
         "生成按 config 的标价；sol 缓存单价 config 里没有，只给标价；luna 缓存按 $0.01、裁判按 $0.05。", "",
         "| 项目 | 记录数 | 输入 tokens（其中缓存） | 输出 tokens | 标价 | 计缓存折扣 |", "|---|---|---|---|---|---|"]
    t, gen = R.q("长题生成的用量（全部调用记录，含失败）", f"""
SELECT CASE WHEN skill_file LIKE 'skills/original_eval/%' THEN 'original_eval' ELSE replace(replace(skill_file, 'skills/', ''), '.md', '') END AS grp,
       model_name, count(*) AS n, coalesce(sum(input_tokens), 0) AS tin, coalesce(sum(output_tokens), 0) AS tout,
       coalesce(sum(json_extract(usage_raw, '$.input_tokens_details.cached_tokens')), 0) AS cached
FROM calls WHERE items_file = {_q(items_rel)} GROUP BY 1, 2""")
    tl = td = 0.0
    for r in sorted(gen, key=lambda r: (MODELS.index(r["model_name"]), GROUPS.index(r["grp"]))):
        pr = find_model(cfg, r["model_name"]).get("price_per_1m_tokens") or {}
        lp = (r["tin"] * pr["input"] + r["tout"] * pr["output"]) / 1e6
        cp = CACHE_PRICE.get(r["model_name"])
        dp = ((r["tin"] - r["cached"]) * pr["input"] + r["cached"] * cp + r["tout"] * pr["output"]) / 1e6 if cp is not None else lp
        tl += lp; td += dp
        L.append(f"| 生成 {GN[r['grp']]} × {SN[r['model_name']]} | {r['n']} | {r['tin']:,}（{r['cached']:,}） | {r['tout']:,} | ${lp:.3f} | ${dp:.3f} |")
    pr = jcfg.get("price_per_1m_tokens") or {}
    for label, table in (("裁判第一遍（长题）", "judgments"), ("裁判第二遍（长题）", "repeat_judgments")):
        _, rr = R.q(f"长题裁判用量：{table}", f"""
SELECT count(*) AS n, coalesce(sum(x.input_tokens), 0) AS tin, coalesce(sum(x.output_tokens), 0) AS tout,
       coalesce(sum(x.attempts), 0) AS att,
       coalesce(sum(json_extract(x.usage_raw, '$.input_tokens_details.cached_tokens')), 0) AS cached
FROM {table} x JOIN calls c ON c.id = x.call_id
WHERE c.items_file = {_q(items_rel)} AND x.prompt_sha256 = {_q(prompt_sha)}""")
        r = rr[0]
        lp = (r["tin"] * pr["input"] + r["tout"] * pr["output"]) / 1e6
        dp = ((r["tin"] - r["cached"]) * pr["input"] + r["cached"] * JUDGE_CACHE_PRICE + r["tout"] * pr["output"]) / 1e6
        tl += lp; td += dp
        L.append(f"| {label} | {r['n']} 份（{r['att']} 次调用） | {r['tin']:,}（{r['cached']:,}） | {r['tout']:,} | ${lp:.3f} | ${dp:.3f} |")
    L += [f"| **合计** | | | | **${tl:.2f}** | **${td:.2f}** |", "",
          "裁判的缓存只计每条记录最后一次调用报告的；重判过的前几次按标价，所以折扣价是上限。", ""]
    return L


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.testreport", description="正式测试报告（三份 Skill × 两个模型）")
    ap.add_argument("--items", default="data/items_merged.jsonl")
    ap.add_argument("--judge-prompt", default="prompts/judge_v2.md")
    ap.add_argument("--rule-map", default="data/items_long_test_rule_map.json")
    ap.add_argument("--aspect-map", default="data/items_long_test_aspect_map.json")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--boot-seed", type=int, default=20261113)
    ap.add_argument("--repeat-seed", type=int, default=20261114, help="长回答第二遍的抽样种子（报告只认这个种子）")
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
