import json, re, sys, hashlib

# 合并评测集：短题（data/items.jsonl，30 条）+ 长题测试集（data/items_long_test.jsonl，18 条）并成一份。
# Xia 2026-11-11 定的三件事：
#   1. 评测集要合并。
#   2. 分值：长题每个卡点 2 分，短题每个卡点 1 分（推荐步骤同样按 2 比 1，这一条是 Claude 照卡点类推的，待 Xia 确认）。
#      卡点分和步骤分仍然分开报，各自报“得分 ÷ 满分”的百分比。
#   3. 讲错知识怎么清零：短题整份清零（原规则不变）；做题类长题整份清零；概念理解类长题只清讲错的那一部分。
# 卡点问题、推荐步骤、知识错误清单原样照抄，一个字不改：已经判过的短题回答不用重判。
# 长请求开发集（data/items_long_dev.jsonl）不并入：它是 30 条短题拼起来的，卡点重复，只用来改 V2。
# 运行：python3 drafts/build_items_merged.py
# 产物：data/items_merged.jsonl（每行多四个顶层字段：tier、kind、points、zero_rule，概念理解类另有 parts）
#       data/items_merged_points.md（分值表，给人看）

POINTS = {"长题": 2, "短题": 1}                 # 每个卡点、每个步骤的分值；改了要在两版 Skill 开跑之前
SOURCES = [("短题", "data/items.jsonl"), ("长题", "data/items_long_test.jsonl")]
KIND_MAP = "data/items_long_test_kind_map.json"   # 长题是“做题类”还是“概念理解类”
OUT = "data/items_merged.jsonl"
OUT_MD = "data/items_merged_points.md"
PART = re.compile(r"^（第 (\d+) (?:题|部分)）")

def part_of(text):
    m = PART.match(text)
    return int(m.group(1)) if m else None

def main():
    kind_map = json.load(open(KIND_MAP, encoding="utf-8"))
    out = []
    for tier, path in SOURCES:
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            kind = "短题" if tier == "短题" else kind_map[r["id"]]
            p = POINTS[tier]
            r["tier"] = tier
            r["kind"] = kind
            r["points"] = {"gate_each": p, "gate_total": p * len(r["gate_questions"]),
                           "step_each": p, "step_total": p * len(r["recommended_steps"])}
            if kind == "概念理解类":
                r["zero_rule"] = "只清讲错的那一部分"
                r["parts"] = {"gates": {g["id"]: part_of(g["text"]) for g in r["gate_questions"]},
                              "steps": {s["id"]: part_of(s["text"]) for s in r["recommended_steps"]},
                              "knowledge_errors": [part_of(e) for e in r["knowledge_errors"]]}
                assert all(v is not None for v in r["parts"]["gates"].values()), r["id"]
                assert all(v is not None for v in r["parts"]["knowledge_errors"]), r["id"]
            else:
                r["zero_rule"] = "整份清零"
                r["parts"] = None
            out.append(r)
    ids = [r["id"] for r in out]
    assert len(ids) == len(set(ids)), "题目 id 重复"
    G = sum(r["points"]["gate_total"] for r in out); S = sum(r["points"]["step_total"] for r in out)
    L = ["# 合并评测集分值表", "",
         f"长题每个卡点 {POINTS['长题']} 分、每个步骤 {POINTS['长题']} 分；短题每个卡点 {POINTS['短题']} 分、每个步骤 {POINTS['短题']} 分。"
         f"卡点分满分 {G}，步骤分满分 {S}，两个分数分开报，各报“得分 ÷ 满分”。", "",
         "讲错知识：短题和做题类长题整份清零；概念理解类长题只清讲错的那一部分。", "",
         "| 类别 | 题数 | 卡点数 | 卡点分 | 占卡点满分 | 步骤数 | 步骤分 | 占步骤满分 |", "|---|---|---|---|---|---|---|---|"]
    for kind in ("做题类", "概念理解类", "短题"):
        rs = [r for r in out if r["kind"] == kind]
        g = sum(r["points"]["gate_total"] for r in rs); s_ = sum(r["points"]["step_total"] for r in rs)
        name = kind if kind == "短题" else "长题·" + kind
        L.append(f"| {name} | {len(rs)} | {sum(len(r['gate_questions']) for r in rs)} | {g} | {g/G:.0%} | "
                 f"{sum(len(r['recommended_steps']) for r in rs)} | {s_} | {s_/S:.0%} |")
    L += ["", "| 课程 | 卡点分 | 占卡点满分 | 步骤分 | 占步骤满分 |", "|---|---|---|---|---|"]
    for c in dict.fromkeys(r["course"] for r in out):
        rs = [r for r in out if r["course"] == c]
        g = sum(r["points"]["gate_total"] for r in rs); s_ = sum(r["points"]["step_total"] for r in rs)
        L.append(f"| {c} | {g} | {g/G:.0%} | {s_} | {s_/S:.0%} |")
    L += ["", "| 题目 | 类别 | 课程 | 知识点 | 卡点数 | 卡点分 | 步骤数 | 步骤分 | 讲错知识 |", "|---|---|---|---|---|---|---|---|---|"]
    order = {"概念理解类": 0, "做题类": 1, "短题": 2}
    for r in sorted(out, key=lambda r: (order[r["kind"]], r["id"])):
        p = r["points"]
        L.append(f"| {r['id']} | {r['kind']} | {r['course']} | {r['knowledge_point']} | {len(r['gate_questions'])} | "
                 f"{p['gate_total']} | {len(r['recommended_steps'])} | {p['step_total']} | {r['zero_rule']} |")
    with open(OUT, "w", encoding="utf-8") as f:
        for r in out: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L[:20]))
    print(len(out), "条", hashlib.md5(open(OUT, "rb").read()).hexdigest())

if __name__ == "__main__":
    main()
