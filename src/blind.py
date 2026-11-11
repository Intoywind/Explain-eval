"""人工盲打：导出盲打网页，以及把人工结果和裁判对比。

python -m src.blind export --n 50 --seed 1 --out blind/round1/
python -m src.blind export --design outcome --per-part 15 --seed 20261112 --out blind/round1/   # 按裁判结果分两部分抽
python -m src.blind compare blind/round1/key.json <导出的 JSON> [--judge-prompt prompts/judge_v2.md] [--out 报告.md]

网页是一个自带全部内容的 HTML 文件，不依赖网络：Markdown 由 Python 的 markdown 库预先转成 HTML，
\\( \\) 和 \\[ \\] 里的公式由 latex2mathml 转成 MathML（浏览器原生显示）；转不了的公式原样显示 TeX 源码。
页面里不含 Skill、被测模型、条目 id、裁判结果、卡点问题出处；对应关系只在 key.json 里。
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .judge import ROOT, db_path_from_config, judge_model_cfg, load_items, load_prompt, rubric_hash
from .run import PER_COURSE_SKILL_DIRS, UsageError, _rel, load_config


# ---------------- 抽样 ----------------

def skill_group(skill_file: str) -> str:
    """按课程选文件的 Skill 归成一组（original / original_eval），其余就是文件路径本身。"""
    for d in PER_COURSE_SKILL_DIRS:
        if skill_file.startswith(f"skills/{d}/"):
            return d
    return skill_file


def sample_calls(rows: list, n: int, seed: int) -> list:
    """尽量让每个条目、每个条件（Skill 组 × 被测模型）都抽到：
    轮流按条件取，每次在该条件下挑被抽次数最少的条目（并列时随机），再随机挑一次重复。"""
    rng = random.Random(seed)
    by_cond: dict[tuple, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_cond[(skill_group(r["skill_file"]), r["model_name"])][r["item_id"]].append(r)
    conds = sorted(by_cond)
    rng.shuffle(conds)
    item_count: Counter = Counter()
    picked, used = [], set()
    while len(picked) < n:
        progressed = False
        for cond in conds:
            if len(picked) >= n:
                break
            cands = [(iid, [r for r in rs if r["id"] not in used]) for iid, rs in by_cond[cond].items()]
            cands = [(iid, rs) for iid, rs in cands if rs]
            if not cands:
                continue
            low = min(item_count[iid] for iid, _ in cands)
            iid, rs = rng.choice(sorted([c for c in cands if item_count[c[0]] == low], key=lambda c: c[0]))
            r = rng.choice(sorted(rs, key=lambda x: x["id"]))
            picked.append(r)
            used.add(r["id"])
            item_count[iid] += 1
            progressed = True
        if not progressed:
            break
    rng.shuffle(picked)
    return picked


def group_name(skill_file: str, model_name: str) -> str:
    sg = skill_group(skill_file)
    sg = sg[len("skills/"):-len(".md")] if sg.startswith("skills/") and sg.endswith(".md") else sg
    return f"{sg} × {model_name}"


def sample_by_outcome(rows: list, per_part: int, seed: int, max_per_item: int = 3) -> list:
    """按裁判结果分两部分各抽 per_part 份：
    fail = 知识不通过，或至少一个卡点问题没答上；pass = 知识通过且卡点全部答上。
    rows 每个元素要有 id、item_id、group、course、part。先抽 fail（通常更少），再抽 pass；
    每次在该部分里挑使（本部分该组已抽数 + 本部分该课程已抽数）最小的，再看（组 × 课程）格子、该条目已抽数，
    最后随机；同一条目两部分合计最多 max_per_item 份。"""
    rng = random.Random(seed)
    item_cnt: Counter = Counter()
    picked, used = [], set()
    for part in ("fail", "pass"):
        pool = sorted((r for r in rows if r["part"] == part), key=lambda r: r["id"])
        cg, cc, cell = Counter(), Counter(), Counter()
        for _ in range(per_part):
            cands = [r for r in pool if r["id"] not in used and item_cnt[r["item_id"]] < max_per_item]
            if not cands:
                raise UsageError(f"{part} 部分可抽的回答不够 {per_part} 份")
            keyed = [((cg[r["group"]] + cc[r["course"]], cell[(r["group"], r["course"])], item_cnt[r["item_id"]]), r)
                     for r in cands]
            best = min(k for k, _ in keyed)
            r = rng.choice([r for k, r in keyed if k == best])
            picked.append(r)
            used.add(r["id"])
            item_cnt[r["item_id"]] += 1
            cg[r["group"]] += 1
            cc[r["course"]] += 1
            cell[(r["group"], r["course"])] += 1
    rng.shuffle(picked)
    return picked


# ---------------- Markdown + 公式 ----------------

_MATH_RE = re.compile(r"\\\((.+?)\\\)|\\\[(.+?)\\\]", re.S)


def render_markdown(text: str) -> tuple[str, int]:
    """返回（HTML，转换失败的公式个数）。"""
    import latex2mathml.converter
    import markdown

    maths: list[str] = []
    n_fail = 0

    def stash(m):
        nonlocal n_fail
        tex = m.group(1) if m.group(1) is not None else m.group(2)
        block = m.group(2) is not None
        try:
            ml = latex2mathml.converter.convert(tex.strip(), display="block" if block else "inline")
        except Exception:
            n_fail += 1
            ml = f'<code class="tex">{html.escape(m.group(0))}</code>'
        maths.append(f'<div class="math-block">{ml}</div>' if block else ml)
        return f"MATHPH{len(maths) - 1}XEND"

    s = _MATH_RE.sub(stash, text)
    s = s.replace("\\$", "$").replace("&", "&amp;").replace("<", "&lt;")  # 讲解里的原始 HTML 一律当文本
    out = markdown.markdown(s, extensions=["tables", "sane_lists", "fenced_code"])
    out = re.sub(r"<p>\s*(MATHPH\d+XEND)\s*</p>", r"\1", out)
    out = re.sub(r"MATHPH(\d+)XEND", lambda m: maths[int(m.group(1))], out)
    return out, n_fail


# ---------------- export ----------------

def cmd_export(args) -> int:
    cfg = load_config(Path(args.config))
    items_by_id, items_rel = load_items(Path(args.items), args.holdout)
    conn = db.connect(db_path_from_config(cfg))
    rows = [r for r in conn.execute(
        "SELECT id, item_id, model_name, skill_file, repeat_idx, response_text FROM current_calls ORDER BY id")
        if r["item_id"] in items_by_id]
    if not rows:
        raise UsageError("数据库里没有可抽的回答")
    meta = {}
    if args.design == "outcome":
        jcfg = judge_model_cfg(cfg)
        prompt = load_prompt(Path(args.judge_prompt))
        cand = []
        for r in rows:
            it = items_by_id[r["item_id"]]
            j = conn.execute(
                "SELECT id, status, knowledge_pass, gate_num, gate_den FROM judgments WHERE id = (SELECT max(id) FROM judgments"
                " WHERE call_id=? AND judge_model_name=? AND prompt_sha256=? AND rubric_sha256=?)",
                (r["id"], jcfg["name"], prompt.sha256, rubric_hash(it))).fetchone()
            if j is None or j["status"] != "ok":   # 没评过、待复核、失败的不抽
                continue
            part = "pass" if j["knowledge_pass"] and j["gate_num"] == j["gate_den"] else "fail"
            cand.append({**dict(r), "group": group_name(r["skill_file"], r["model_name"]), "course": it["course"],
                         "part": part, "judgment_id": j["id"]})
        picked = sample_by_outcome(cand, args.per_part, args.seed)
        meta = {"design": "outcome", "per_part": args.per_part, "max_per_item": 3,
                "judge_model_name": jcfg["name"], "judge_prompt": prompt.rel, "judge_prompt_sha256": prompt.sha256,
                "pool": {p: sum(c["part"] == p for c in cand) for p in ("fail", "pass")}}
    else:
        if args.n is None:
            raise UsageError("--design condition 需要 --n")
        picked = sample_calls(rows, args.n, args.seed)
        meta = {"design": "condition"}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    width = max(2, len(str(len(picked))))
    entries, key, n_math_fail = [], {}, 0
    for k, r in enumerate(picked, 1):
        bid = f"B{k:0{width}d}"
        it = items_by_id[r["item_id"]]
        body, nf = render_markdown(r["response_text"])
        n_math_fail += nf
        entries.append({
            "bid": bid,
            "learned": it["reader_known"]["learned"],
            "not_learned": it["reader_known"]["not_learned"],
            "material": it["material"],
            "request": it["request"],
            "response_html": body,
            "gate": [{"id": q["id"], "text": q["text"], "accept": q["accept"]} for q in it["gate_questions"]],
            "steps": [{"id": s["id"], "text": s["text"]} for s in it["recommended_steps"]],
        })
        key[bid] = {"call_id": r["id"], "item_id": r["item_id"], "skill_file": r["skill_file"],
                    "model_name": r["model_name"], "repeat_idx": r["repeat_idx"],
                    "rubric_sha256": rubric_hash(it),
                    "gate_ids": [q["id"] for q in it["gate_questions"]],
                    "step_ids": [s["id"] for s in it["recommended_steps"]]}
        if meta["design"] == "outcome":
            key[bid].update({"group": r["group"], "course": r["course"], "part": r["part"],
                             "judgment_id": r["judgment_id"]})

    round_name = out.name or "round"
    data_json = json.dumps({"round": round_name, "entries": entries}, ensure_ascii=False)
    storage_key = "explain-eval-blind-" + hashlib.sha256(data_json.encode()).hexdigest()[:12]
    page = (PAGE_TEMPLATE
            .replace("__TITLE__", html.escape(f"讲解盲打 · {round_name}"))
            .replace("__STORAGE_KEY__", storage_key)
            .replace("__DATA__", data_json.replace("</", "<\\/")))

    # 页面里不能有的东西
    forbidden = set()
    for m in cfg.get("models") or []:
        forbidden |= {m.get("name", ""), m.get("model_id", "")}
    forbidden |= {r["skill_file"] for r in rows} | {Path(r["skill_file"]).stem for r in rows}
    forbidden |= {"general_v1", "original_eval"}
    forbidden |= set(items_by_id)
    forbidden.discard("")
    hits = sorted(t for t in forbidden if t in page)
    if hits:
        raise UsageError(f"网页里出现了不该显示的内容，已停止：{hits[:5]}")

    (out / "index.html").write_text(page, encoding="utf-8")
    (out / "key.json").write_text(json.dumps({
        "round": round_name, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n": len(picked), "seed": args.seed, "items_file": items_rel, "storage_key": storage_key,
        "sampling": meta, "key": key}, ensure_ascii=False, indent=2), encoding="utf-8")

    want = args.n if meta["design"] == "condition" else 2 * args.per_part
    print(f"抽了 {len(picked)} 份（要求 {want}），种子 {args.seed}，覆盖 {len({v['item_id'] for v in key.values()})} 个条目"
          f"（库里共 {len({r['item_id'] for r in rows})} 个）")
    cond = Counter(group_name(key[b]["skill_file"], key[b]["model_name"]) for b in key)
    for g, c in sorted(cond.items()):
        print(f"  {g}：{c} 份")
    if meta["design"] == "outcome":
        print(f"  可抽池子：fail {meta['pool']['fail']} 份，pass {meta['pool']['pass']} 份")
        for f in ("part", "course"):
            print(f"  按{'部分' if f == 'part' else '课程'}：" + "，".join(f"{k} {v}" for k, v in sorted(Counter(x[f] for x in key.values()).items())))
        print("  部分 × 组：" + "，".join(f"{p}/{g} {v}" for (p, g), v in sorted(Counter((x["part"], x["group"]) for x in key.values()).items())))
        print("  部分 × 课程：" + "，".join(f"{p}/{c} {v}" for (p, c), v in sorted(Counter((x["part"], x["course"]) for x in key.values()).items())))
        print(f"  同一条目最多 {max(Counter(x['item_id'] for x in key.values()).values())} 份")
    print(f"要判的卡点问题 {sum(len(x['gate_ids']) for x in key.values())} 个，推荐步骤 {sum(len(x['step_ids']) for x in key.values())} 个")
    print(f"网页：{_rel(out / 'index.html')}（{(out / 'index.html').stat().st_size // 1024} KB）")
    print(f"对应表：{_rel(out / 'key.json')}（不要打开它，盲打完再用）")
    print(f"公式转换失败 {n_math_fail} 处（这些原样显示 TeX 源码）；页面里搜不到 Skill 文件名、模型名、条目 id")
    return 0


# ---------------- compare ----------------

def kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    """Cohen's kappa（两分类）。双方都只用了同一个取值时无法计算，返回 None。"""
    n = len(pairs)
    if n == 0:
        return None
    po = sum(a == b for a, b in pairs) / n
    pa = sum(a for a, _ in pairs) / n
    pb = sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe >= 1:
        return None
    return (po - pe) / (1 - pe)


def _pct(x, d):
    return f"{x}/{d}（{x / d:.0%}）" if d else "0/0（—）"


def _k(v):
    return "无法计算（双方取值全部相同）" if v is None else f"{v:.3f}"


def _yn(v, yes, no):
    return yes if v else no


def _md(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def cmd_compare(args) -> int:
    cfg = load_config(Path(args.config))
    jcfg = judge_model_cfg(cfg)
    prompt = load_prompt(Path(args.judge_prompt))
    keyf = json.loads(Path(args.key).read_text(encoding="utf-8"))
    human = json.loads(Path(args.human).read_text(encoding="utf-8"))
    hans = human.get("answers") or {}
    items_by_id, _ = load_items(ROOT / keyf.get("items_file", "data/items.jsonl"), args.holdout)
    conn = db.connect(db_path_from_config(cfg))

    recs = []   # 每份：bid, key, human, judgment, gate rows, step rows
    missing_judge, not_filled, review_judge = [], [], []
    for bid, k in keyf["key"].items():
        h = hans.get(bid)
        if not h or h.get("understood") is None:
            not_filled.append(bid)
            continue
        it = items_by_id[k["item_id"]]
        j = conn.execute(
            "SELECT * FROM judgments WHERE call_id=? AND judge_model_name=? AND prompt_sha256=? AND status='ok'"
            " ORDER BY (rubric_sha256=?) DESC, id DESC LIMIT 1",
            (k["call_id"], jcfg["name"], prompt.sha256, rubric_hash(it))).fetchone()
        if j is None:
            rv = conn.execute(
                "SELECT 1 FROM judgments WHERE call_id=? AND judge_model_name=? AND prompt_sha256=? AND status='needs_review'"
                " LIMIT 1", (k["call_id"], jcfg["name"], prompt.sha256)).fetchone()
            (review_judge if rv else missing_judge).append(bid)
            continue
        g = {r["question_id"]: r for r in conn.execute("SELECT * FROM judge_gate WHERE judgment_id=?", (j["id"],))}
        s = {r["step_id"]: r for r in conn.execute("SELECT * FROM judge_steps WHERE judgment_id=?", (j["id"],))}
        recs.append({"bid": bid, "k": k, "h": h, "j": j, "g": g, "s": s, "item": it})

    L = [f"# 人工盲打 vs 裁判：{keyf.get('round', '')}", "",
         f"- 对应表：`{args.key}`；人工结果：`{args.human}`",
         f"- 裁判：{jcfg['name']}，prompt `{prompt.rel}`（sha256 {prompt.sha256[:12]}）",
         f"- 参与对比的回答 {len(recs)} 份；人工没填总体判断的 {len(not_filled)} 份；"
         f"裁判还没评的 {len(missing_judge)} 份{('：' + '、'.join(missing_judge)) if missing_judge else ''}；"
         f"裁判结果待复核（needs_review，不计分）的 {len(review_judge)} 份{('：' + '、'.join(review_judge)) if review_judge else ''}",
         "- 卡点问题和推荐步骤用裁判的计分结果（status=ok 的记录；证据不合格的已重判或标为待复核，不参与对比）。", ""]

    # 1. 逐问题
    gate_pairs, gate_dis = [], []
    for r in recs:
        for qid in r["k"]["gate_ids"]:
            hv = (r["h"].get("gate") or {}).get(qid)
            if hv is None or qid not in r["g"]:
                continue
            jv = bool(r["g"][qid]["answered"])
            gate_pairs.append((bool(hv), jv))
            if bool(hv) != jv:
                gate_dis.append((r, qid, bool(hv), r["g"][qid]))
    agree = sum(a == b for a, b in gate_pairs)
    L += ["## 1. 逐个卡点问题", "",
          f"- 判断数：{len(gate_pairs)}；一致：{_pct(agree, len(gate_pairs))}；Cohen's kappa：{_k(kappa(gate_pairs))}",
          f"- 人工判答上 {sum(a for a, _ in gate_pairs)} 个，裁判判答上 {sum(b for _, b in gate_pairs)} 个", ""]

    # 2. 每份回答的卡点分
    L += ["## 2. 每份回答的卡点分", ""]
    kpass = [r for r in recs if r["j"]["knowledge_pass"]]
    kfail = [r for r in recs if not r["j"]["knowledge_pass"]]

    def hscore(r):
        gs = r["h"].get("gate") or {}
        ids = r["k"]["gate_ids"]
        filled = [q for q in ids if gs.get(q) is not None]
        return (sum(bool(gs[q]) for q in filled), len(ids), len(filled) == len(ids))

    rows2 = []
    for r in kpass:
        hn, hd, full = hscore(r)
        if not full:
            continue
        rows2.append((r, hn / hd, r["j"]["gate_num"] / r["j"]["gate_den"]))
    same = sum(abs(a - b) < 1e-9 for _, a, b in rows2)
    mad = sum(abs(a - b) for _, a, b in rows2) / len(rows2) if rows2 else 0
    md = sum(b - a for _, a, b in rows2) / len(rows2) if rows2 else 0
    L += [f"知识通过、人工把卡点问题都填了的回答 {len(rows2)} 份：",
          f"- 卡点分完全相同：{_pct(same, len(rows2))}",
          f"- 平均绝对差：{mad:.3f}；平均差（裁判 − 人工）：{md:+.3f}", ""]
    L += [f"裁判判知识不通过的 {len(kfail)} 份（裁判卡点分按规则记 0；人工不判知识，单列）：", ""]
    if kfail:
        L += ["| 盲打编号 | 条目 | 裁判触发的知识错误 | 人工卡点分 | 裁判卡点分（计分 / 未清零的原始判断） |", "|---|---|---|---|---|"]
        for r in kfail:
            hn, hd, _ = hscore(r)
            raw = sum(int(x["answered"]) for x in r["g"].values())
            which = json.loads(r["j"]["parsed_json"])["knowledge_error"].get("which") or []
            L.append(f"| {r['bid']} | {r['k']['item_id']} | {_md('；'.join(which))} | {hn}/{hd} | "
                     f"{r['j']['gate_num']}/{r['j']['gate_den']}（原始 {raw}/{r['j']['gate_den']}） |")
    else:
        L.append("（无）")
    L.append("")

    # 3. 逐步骤
    step_pairs, step_dis, n_step_ans = [], [], 0
    for r in recs:
        hs = r["h"].get("steps") or {}
        got = False
        for sid in r["k"]["step_ids"]:
            hv = hs.get(sid)
            if hv is None or sid not in r["s"]:
                continue
            got = True
            jv = bool(r["s"][sid]["done"])
            step_pairs.append((bool(hv), jv))
            if bool(hv) != jv:
                step_dis.append((r, sid, bool(hv), r["s"][sid]))
        n_step_ans += got
    agree_s = sum(a == b for a, b in step_pairs)
    L += ["## 3. 逐个推荐步骤（只算人工填了的）", "",
          f"- 填了步骤的回答 {n_step_ans} 份，判断数 {len(step_pairs)}；一致：{_pct(agree_s, len(step_pairs))}；"
          f"Cohen's kappa：{_k(kappa(step_pairs))}", ""]

    # 4. 分歧清单
    L += ["## 4. 全部分歧", "", "| 盲打编号 | 条目 | 类型 | 问题或步骤 | 人工 | 裁判 | 裁判的引句（✓ 通过校验）和理由 |",
          "|---|---|---|---|---|---|---|"]
    for kind, lst in (("卡点", gate_dis), ("步骤", step_dis)):
        for r, xid, hv, jr in lst:
            if kind == "卡点":
                text = next(q["text"] for q in r["item"]["gate_questions"] if q["id"] == xid)
                hs_, js_ = _yn(hv, "答上", "没答上"), _yn(jr["answered"], "答上", "没答上")
                if jr["quote_invalid"]:
                    js_ += "（原判答上，引句作废）"
            else:
                text = next(s["text"] for s in r["item"]["recommended_steps"] if s["id"] == xid)
                hs_, js_ = _yn(hv, "踩中", "没踩中"), _yn(jr["done"], "踩中", "没踩中")
                if jr["quote_invalid"]:
                    js_ += "（原判踩中，引句作废）"
            qs = json.loads(jr["quotes"])
            qv = json.loads(jr["quotes_valid"])
            ev = "；".join(f"「{_md(q)}」{'✓' if v else '✗'}" for q, v in zip(qs, qv)) or "（无引句）"
            L.append(f"| {r['bid']} | {r['k']['item_id']} | {kind} {xid} | {_md(text)} | {hs_} | {js_} | {ev}｜理由：{_md(jr['reason'])} |")
    if not gate_dis and not step_dis:
        L.append("| （无分歧） | | | | | | |")
    L.append("")

    # 5. 交叉表
    cells = Counter()
    lists = {"full_not_understood": [], "notfull_understood": []}
    for r in recs:
        u = r["h"]["understood"] == "understood"
        full = r["j"]["gate_num"] == r["j"]["gate_den"]
        cells[(u, full)] += 1
        if full and not u:
            lists["full_not_understood"].append(r)
        if not full and u:
            lists["notfull_understood"].append(r)
    L += ["## 5. 人工总体判断 × 裁判卡点分", "",
          "| | 裁判卡点分 = 1 | 裁判卡点分 < 1 | 合计 |", "|---|---|---|---|"]
    for u, lab in ((True, "人工：看懂了"), (False, "人工：没看懂")):
        L.append(f"| {lab} | {cells[(u, True)]} | {cells[(u, False)]} | {cells[(u, True)] + cells[(u, False)]} |")
    L.append(f"| 合计 | {cells[(True, True)] + cells[(False, True)]} | {cells[(True, False)] + cells[(False, False)]} | {len(recs)} |")
    L.append("")
    for name, lab in (("full_not_understood", "卡点全答上但我没看懂"), ("notfull_understood", "卡点没全答上但我看懂了")):
        L.append(f"**{lab}**（{len(lists[name])} 份）：")
        for r in lists[name]:
            note = _md(r["h"].get("note") or "")
            L.append(f"- {r['bid']}｜{r['k']['item_id']}｜裁判卡点分 {r['j']['gate_num']}/{r['j']['gate_den']}"
                     f"{'｜裁判判知识不通过' if not r['j']['knowledge_pass'] else ''}{f'｜我的备注：{note}' if note else ''}")
        if not lists[name]:
            L.append("- （无）")
        L.append("")

    # 6. 偏向
    def bias(pairs, yes):
        loose = sum(1 for h, j in pairs if j and not h)
        strict = sum(1 for h, j in pairs if h and not j)
        tot = loose + strict
        if tot == 0:
            verdict = "没有分歧"
        elif loose > strict:
            verdict = f"裁判偏松（裁判判{yes}而人工没判的更多）"
        elif strict > loose:
            verdict = f"裁判偏严（人工判{yes}而裁判没判的更多）"
        else:
            verdict = "两边一样多，看不出偏向"
        return f"分歧 {tot} 个：裁判判{yes}、人工没判 {loose} 个；人工判{yes}、裁判没判 {strict} 个。{verdict}"

    L += ["## 6. 分歧偏向", "", f"- 卡点问题：{bias(gate_pairs, '答上')}", f"- 推荐步骤：{bias(step_pairs, '踩中')}", ""]

    text = "\n".join(L)
    outp = Path(args.out) if args.out else Path(args.key).with_name("compare.md")
    outp.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n已写入 {_rel(outp)}")
    return 0


# ---------------- 入口 ----------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.blind", description="人工盲打")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="抽样并生成盲打网页")
    e.add_argument("--design", choices=["condition", "outcome"], default="condition",
                   help="condition：按（Skill 组 × 被测模型）轮流抽（默认）；outcome：按裁判结果分两部分各抽 --per-part 份")
    e.add_argument("--n", type=int, help="--design condition 时抽几份")
    e.add_argument("--per-part", type=int, default=15, help="--design outcome 时每部分抽几份，默认 15")
    e.add_argument("--judge-prompt", default="prompts/judge_v2.md", help="--design outcome 时按哪版裁判结果分部分")
    e.add_argument("--seed", type=int, default=1)
    e.add_argument("--out", required=True)
    e.add_argument("--items", default="data/items.jsonl")
    e.add_argument("--holdout", action="store_true")
    c = sub.add_parser("compare", help="人工结果和裁判对比")
    c.add_argument("key")
    c.add_argument("human")
    c.add_argument("--judge-prompt", default="prompts/judge_v2.md")
    c.add_argument("--out", help="Markdown 输出路径，默认和 key.json 同目录的 compare.md")
    c.add_argument("--holdout", action="store_true")
    args = ap.parse_args(argv)
    try:
        return cmd_export(args) if args.cmd == "export" else cmd_compare(args)
    except UsageError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2


PAGE_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  --bg: #f7f7f5; --panel: #ffffff; --text: #1f2328; --muted: #656d76; --line: #d8dbe0;
  --accent: #2f6fde; --accent-soft: #e8f0fd; --ok: #1a7f37; --warn: #b35900; --code: #f1f2f4;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #16181c; --panel: #1f2227; --text: #e6e8eb; --muted: #9aa3ad; --line: #353a42;
          --accent: #6ea2ff; --accent-soft: #233149; --ok: #4ac26b; --warn: #f0a04b; --code: #2a2e35; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
       font: 16px/1.7 -apple-system, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif; }
header { position: sticky; top: 0; z-index: 5; background: var(--panel); border-bottom: 1px solid var(--line);
         padding: 10px 16px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
header h1 { font-size: 16px; margin: 0; }
header .grow { flex: 1; }
button { font: inherit; padding: 6px 14px; border-radius: 6px; border: 1px solid var(--line);
         background: var(--panel); color: var(--text); cursor: pointer; }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button:disabled { opacity: .45; cursor: default; }
.layout { display: flex; max-width: 1200px; margin: 0 auto; }
nav { width: 120px; flex: none; padding: 16px 8px; position: sticky; top: 56px; align-self: flex-start;
      max-height: calc(100vh - 56px); overflow-y: auto; }
nav a { display: flex; justify-content: space-between; padding: 3px 8px; border-radius: 5px; color: var(--text);
        text-decoration: none; font-size: 14px; }
nav a.cur { background: var(--accent-soft); font-weight: 600; }
nav .dot { color: var(--muted); }
nav .dot.done { color: var(--ok); }
nav .dot.part { color: var(--warn); }
main { flex: 1; min-width: 0; padding: 16px; }
section.card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px 20px; margin-bottom: 16px; }
h2 { font-size: 15px; margin: 0 0 8px; color: var(--muted); font-weight: 600; }
.pre { white-space: pre-wrap; word-break: break-word; }
.tags span { display: inline-block; border: 1px solid var(--line); border-radius: 999px; padding: 0 10px; margin: 2px 4px 2px 0; font-size: 14px; }
.resp { overflow-x: auto; }
.resp table { border-collapse: collapse; margin: 8px 0; }
.resp th, .resp td { border: 1px solid var(--line); padding: 4px 10px; }
.resp blockquote { margin: 8px 0; padding: 2px 14px; border-left: 3px solid var(--line); color: var(--muted); }
.resp code { background: var(--code); padding: 1px 4px; border-radius: 4px; }
.resp h1, .resp h2, .resp h3 { color: var(--text); font-size: 17px; margin: 18px 0 6px; }
.math-block { overflow-x: auto; margin: 8px 0; }
math { font-size: 1.05em; }
.q { border-top: 1px solid var(--line); padding: 12px 0; }
.q:first-of-type { border-top: none; }
.q .accept { color: var(--muted); font-size: 14px; margin: 4px 0 8px; }
.choices label { margin-right: 18px; cursor: pointer; white-space: nowrap; }
.required::after { content: " *必填"; color: var(--warn); font-size: 13px; }
.locked { color: var(--muted); font-style: italic; }
textarea { width: 100%; min-height: 70px; font: inherit; padding: 8px; border-radius: 6px; border: 1px solid var(--line);
           background: var(--bg); color: var(--text); }
details summary { cursor: pointer; font-weight: 600; }
.pager { display: flex; justify-content: space-between; margin: 8px 0 32px; }
.status { color: var(--muted); font-size: 14px; }
@media (max-width: 720px) { nav { display: none; } main { padding: 12px; } section.card { padding: 12px 14px; } }
</style>
</head>
<body>
<header>
  <h1 id="title"></h1>
  <span class="status" id="progress"></span>
  <span class="grow"></span>
  <span class="status" id="saved"></span>
  <button class="primary" id="export">导出结果</button>
</header>
<div class="layout">
  <nav id="nav"></nav>
  <main id="main"></main>
</div>
<script type="application/json" id="data">__DATA__</script>
<script>
(function () {
  var DATA = JSON.parse(document.getElementById("data").textContent);
  var KEY = "__STORAGE_KEY__";
  var E = DATA.entries;
  var state = { cur: 0, answers: {} };
  try { var s = localStorage.getItem(KEY); if (s) { state = JSON.parse(s); } } catch (e) {}
  if (!state.answers) state.answers = {};
  if (!(state.cur >= 0 && state.cur < E.length)) state.cur = 0;

  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); setSaved("已自动保存在本浏览器"); }
    catch (e) { setSaved("浏览器不允许本地保存：关掉前请先导出"); }
  }
  function setSaved(t) { document.getElementById("saved").textContent = t; }
  function ans(bid) { return state.answers[bid] || (state.answers[bid] = { understood: null, gate: {}, steps: {}, note: "" }); }
  function status(e) {
    var a = state.answers[e.bid];
    if (!a || a.understood == null) return (a && Object.keys(a.gate || {}).length) ? "part" : "none";
    var allGate = e.gate.every(function (q) { return a.gate[q.id] === true || a.gate[q.id] === false; });
    return allGate ? "done" : "part";
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  function radio(name, val, opts) {
    return '<span class="choices">' + opts.map(function (o) {
      return '<label><input type="radio" name="' + name + '" value="' + o[0] + '"' + (val === o[2] ? " checked" : "") + "> " + o[1] + "</label>";
    }).join("") + "</span>";
  }

  function renderNav() {
    var done = 0;
    document.getElementById("nav").innerHTML = E.map(function (e, i) {
      var st = status(e); if (st === "done") done++;
      var sym = st === "done" ? "●" : st === "part" ? "◐" : "○";
      return '<a href="#" data-i="' + i + '" class="' + (i === state.cur ? "cur" : "") + '">' + e.bid + '<span class="dot ' + st + '">' + sym + "</span></a>";
    }).join("");
    document.getElementById("progress").textContent = "已完成 " + done + " / " + E.length + "（总体判断和卡点问题都填了才算完成）";
  }

  function render() {
    var e = E[state.cur], a = ans(e.bid);
    document.getElementById("title").textContent = "讲解盲打 · " + e.bid + "（" + (state.cur + 1) + "/" + E.length + "）";
    var h = "";
    h += '<section class="card"><h2>读者已经学过</h2><div class="tags">' + (e.learned.length ? e.learned.map(function (x) { return "<span>" + esc(x) + "</span>"; }).join("") : "（无）") + "</div>";
    h += '<h2 style="margin-top:12px">读者没学过</h2><div class="tags">' + (e.not_learned.length ? e.not_learned.map(function (x) { return "<span>" + esc(x) + "</span>"; }).join("") : "（无）") + "</div></section>";
    h += '<section class="card"><h2>材料</h2><div class="pre">' + esc(e.material) + "</div></section>";
    h += '<section class="card"><h2>请求</h2><div class="pre">' + esc(e.request) + "</div></section>";
    h += '<section class="card"><h2>讲解</h2><div class="resp">' + e.response_html + "</div></section>";
    h += '<section class="card"><h2 class="required">总体判断：作为这个读者，我看懂了没有？</h2>' +
         radio("understood", a.understood, [["understood", "看懂了", "understood"], ["not_understood", "没看懂", "not_understood"]]) + "</section>";
    h += '<section class="card"><h2 class="required">卡点问题：讲解答上了没有</h2>';
    if (a.understood == null) {
      h += '<p class="locked">先填上面的总体判断，再看卡点问题。</p>';
    } else {
      e.gate.forEach(function (q) {
        var v = a.gate[q.id];
        h += '<div class="q"><div><b>' + esc(q.id) + "</b>　" + esc(q.text) + '</div><div class="accept">算答上的标准：' + esc(q.accept) + "</div>" +
             radio("g_" + q.id, v === undefined ? null : v, [["1", "答上了", true], ["0", "没答上", false]]) + "</div>";
      });
    }
    h += "</section>";
    var anySteps = Object.keys(a.steps || {}).length > 0;
    h += '<section class="card"><details' + (anySteps ? " open" : "") + '><summary>推荐步骤（选填）：讲解踩中了没有</summary>';
    e.steps.forEach(function (s) {
      var v = a.steps[s.id];
      h += '<div class="q"><div><b>' + esc(s.id) + "</b>　" + esc(s.text) + "</div>" +
           radio("s_" + s.id, v === undefined ? null : v, [["1", "踩中了", true], ["0", "没踩中", false], ["x", "不填", "__none__"]]) + "</div>";
    });
    h += "</details></section>";
    h += '<section class="card"><h2>备注（选填）</h2><textarea id="note">' + esc(a.note || "") + "</textarea></section>";
    h += '<div class="pager"><button id="prev"' + (state.cur === 0 ? " disabled" : "") + '>← 上一份</button><button id="next"' + (state.cur === E.length - 1 ? " disabled" : "") + ">下一份 →</button></div>";
    var m = document.getElementById("main");
    m.innerHTML = h;

    m.querySelectorAll('input[name="understood"]').forEach(function (el) {
      el.addEventListener("change", function () { a.understood = el.value; save(); render(); });
    });
    e.gate.forEach(function (q) {
      m.querySelectorAll('input[name="g_' + q.id + '"]').forEach(function (el) {
        el.addEventListener("change", function () { a.gate[q.id] = el.value === "1"; save(); renderNav(); });
      });
    });
    e.steps.forEach(function (s) {
      m.querySelectorAll('input[name="s_' + s.id + '"]').forEach(function (el) {
        el.addEventListener("change", function () {
          if (el.value === "x") delete a.steps[s.id]; else a.steps[s.id] = el.value === "1";
          save();
        });
      });
    });
    document.getElementById("note").addEventListener("input", function (ev) { a.note = ev.target.value; save(); });
    document.getElementById("prev").addEventListener("click", function () { go(state.cur - 1); });
    document.getElementById("next").addEventListener("click", function () { go(state.cur + 1); });
    renderNav();
  }

  function go(i) { if (i < 0 || i >= E.length) return; state.cur = i; save(); render(); window.scrollTo(0, 0); }

  document.getElementById("nav").addEventListener("click", function (ev) {
    var a = ev.target.closest("a"); if (!a) return; ev.preventDefault(); go(+a.dataset.i);
  });

  document.getElementById("export").addEventListener("click", function () {
    var out = { round: DATA.round, exported_at: new Date().toISOString(), n_entries: E.length, answers: {} };
    var incomplete = [];
    E.forEach(function (e) {
      var a = state.answers[e.bid];
      if (status(e) !== "done") incomplete.push(e.bid);
      if (a) out.answers[e.bid] = { understood: a.understood, gate: a.gate || {}, steps: a.steps || {}, note: a.note || "" };
    });
    if (incomplete.length && !confirm("还有 " + incomplete.length + " 份没填完（" + incomplete.slice(0, 8).join("、") + (incomplete.length > 8 ? "……" : "") + "）。仍然导出？")) return;
    var blob = new Blob([JSON.stringify(out, null, 2)], { type: "application/json" });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url; link.download = "blind_" + DATA.round + "_" + new Date().toISOString().slice(0, 19).replace(/[:T]/g, "") + ".json";
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  });

  render();
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
