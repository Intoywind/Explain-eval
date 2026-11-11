import json, sys, collections

# 长请求版开发集：把同一门课的 5 个知识点合并进一次请求，卡点问题和推荐步骤原样沿用。
# 用途：检验“一次讲得多时是不是更容易跳步”。同样的 51 个卡点，单独讲（data/items.jsonl）和连着讲（本文件的产物）对比。
# 运行：python3 drafts/build_items_long.py data/items.jsonl data/items_long_dev.jsonl
# 产物另带一个 *_map.json：长条目里每个卡点、步骤对应原条目的哪一个，用于逐项对比。

TOP_REQUEST = "下面是同一门课的 {n} 个部分。按顺序把每个部分都讲一遍，每个部分开头写了我想要什么。"

def main(src, dst):
    rows = [json.loads(l) for l in open(src, encoding="utf-8")]
    groups = collections.OrderedDict()
    for r in rows:
        course_code, _, label = r["id"].split("-")          # ECON-001-零基础
        groups.setdefault((course_code, label), []).append(r)
    out, mp = [], {}
    for (course_code, label), items in groups.items():
        items.sort(key=lambda r: r["id"])
        new_id = f"{course_code}-L01-{label}"
        parts, gates, steps, kerr = [], [], [], []
        learned, not_learned = [], []
        for i, r in enumerate(items, 1):
            parts.append(f"【第 {i} 部分】{r['request']}\n{r['material']}")
            for g in r["gate_questions"]:
                gid = f"p{i}{g['id']}"
                gates.append(dict(g, id=gid, text=f"（第 {i} 部分）{g['text']}"))
                mp[f"{new_id}#{gid}"] = f"{r['id']}#{g['id']}"
            for s in r["recommended_steps"]:
                sid = f"p{i}{s['id']}"
                steps.append(dict(id=sid, text=f"（第 {i} 部分）{s['text']}"))
                mp[f"{new_id}#{sid}"] = f"{r['id']}#{s['id']}"
            kerr += [f"（第 {i} 部分）{e}" for e in r["knowledge_errors"]]
            for x in r["reader_known"]["learned"]:
                if x not in learned: learned.append(x)
            for x in r["reader_known"]["not_learned"]:
                if x not in not_learned: not_learned.append(x)
        # 一个部分标了“学过”的内容，整条里就算学过
        not_learned = [x for x in not_learned if x not in learned]
        out.append(dict(
            id=new_id, course=items[0]["course"],
            knowledge_point="、".join(r["knowledge_point"] for r in items),
            subtype="长请求", source="merged:" + ",".join(r["id"] for r in items), difficulty="高",
            reader_known=dict(learned=learned, not_learned=not_learned),
            request=TOP_REQUEST.format(n=len(items)),
            material="\n\n".join(parts),
            knowledge_errors=kerr, gate_questions=gates, recommended_steps=steps,
            split="dev"))
    with open(dst, "w", encoding="utf-8") as f:
        for r in out: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    json.dump(mp, open(dst.replace(".jsonl", "_map.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in out:
        print(r["id"], "卡点", len(r["gate_questions"]), "步骤", len(r["recommended_steps"]), "材料字符", len(r["material"]))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
