"""生成裁判验收样例（第三份输入第 5 节）：5 组对照、10 份。

python tests/judge_fixtures/make_fixtures.py        # 从 results/eval.db 取真实回答，按下面的最小改动生成

每份样例 = 一份 general_v1 × gpt-6.1-sol 的真实成功回答 + 下面写明的改动。
每处改动都是“原文里恰好出现一次的一段文字 → 新文字”，找不到或出现多次就报错停止，不会悄悄改错地方。
输出：
  <id>.md          样例全文（裁判要评的讲解）
  diffs/<id>.diff  相对原回答的 unified diff（原样回答没有 diff）
  manifest.json    每份样例的条目、来源回答（calls.id 和原文 sha256）、改动说明、预期
"""

from __future__ import annotations

import difflib
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DB = ROOT / "results" / "eval.db"

D2_PARAGRAPH = (
    "为什么最后会停在两边相等的那个利率上？因为两边不相等时，利率自己会动。如果利率偏高，人们想持有的货币比中央银行提供的少，"
    "手里多出来的钱就会被拿去换成能生利息的资产，愿意把钱借出去的人变多，利率被压低；利率一降，人们又愿意多持有一些货币。"
    "如果利率偏低，情况相反：人们想持有的货币比现有的多，就会把生息的资产换回钱，利率被抬高。"
    "利率就这样一直变，直到人们想持有的数量正好等于中央银行提供的数量才停下来。停下来时的利率就叫均衡利率，题目问的就是它。"
)

C2_CUT_START = "先不背公式。假设已经备了 \\(Q\\) 份，考虑：**要不要再加一份？**\n\n"
C2_KEEP_Q = "这里，\\(Q\\) 是当前备货量，单位是份；用 \\(D\\) 表示当天需求量，单位也是份。\n\n"

# 每份：id、组、条目、来源回答 calls.id、改动列表 [(说明, 原文片段, 新片段)]、预期
FIXTURES = [
    {
        "id": "A1", "group": "A", "item_id": "COMP-005-零基础", "call_id": 55,
        "edits": [("在讲独立性的那句后面加一句先提误区再否定的话",
                   "公式仍成立。",
                   "公式仍成立。有人以为需要 X、Y 独立才成立，这是不对的。")],
        "expect": {"knowledge_found": False},
        "expect_text": "不触发知识错误（讲解最终主张“不要求独立”，误区是先提后否定）",
    },
    {
        "id": "A2", "group": "A", "item_id": "COMP-005-零基础", "call_id": 55,
        "edits": [("把讲独立性的那句改成错误说法",
                   "公式**不要求 independence（独立性）**：即使知道 \\(X\\) 的取值会改变对 \\(Y\\) 各种取值概率的判断，公式仍成立。",
                   "这条公式只有在 X、Y 独立时才成立。")],
        "expect": {"knowledge_found": True, "which": ["说成需要独立才成立"], "quote_contains": "只有在 X、Y 独立时才成立"},
        "expect_text": "触发知识错误，which 是清单原文“说成需要独立才成立”，引句是改后的那一句",
    },
    {
        "id": "B1", "group": "B", "item_id": "IEDA-002-零基础", "call_id": 67,
        "edits": [],
        "expect": {"step": "s3", "done": True},
        "expect_text": "s3“先比较交货期和订货周期的长短，再决定怎么算”踩中",
    },
    {
        "id": "B2", "group": "B", "item_id": "IEDA-002-零基础", "call_id": 67,
        "edits": [
            ("删掉开头拿“交货时间较长”解释第二问为什么要算在途货的句子",
             "不一定是同一个数。尤其是第二问，交货时间较长，必须考虑已经订了但还没到的货。\n",
             "不一定是同一个数。\n"),
            ("删掉第一问里“2 周短于 2.6 周的订货周期，所以不用算在途货”的句子",
             "因为2周短于一个2.6周的 Order cycle（订货周期），正常循环中，下单时没有上一批尚未到达的货需要另外计入。\n\n",
             ""),
            ("删掉第二问里“每隔 2.6 周订一批而每批要等 6 周，所以前面有订单在路上”的句子",
             "但我们**每隔2.6周就订一批，而每批要等6周才到**。因此，下新订单时，前面已经有订单在路上。\n\n",
             ""),
            ("文末加一句事后补充的比较",
             "按题目要求的现货口径，再订货点是7.69件。**",
             "按题目要求的现货口径，再订货点是7.69件。**\n\n另外，第一问的交货期比订货周期短，第二问的比订货周期长。"),
            ("删掉第二问里“再早一批已经等待7.8周，超过6周，已经到货。因此，”（到货时间表保留）",
             "再早一批已经等待7.8周，超过6周，已经到货。因此，**现在下单前，有两批在途订单，共50件**。",
             "**现在下单前，有两批在途订单，共50件**。"),
        ],
        "expect": {"step": "s3", "done": False},
        "expect_text": "s3 没踩中（两件事只在文末并列出现，没有把比较当作决定算法的理由）",
    },
    {
        "id": "C1", "group": "C", "item_id": "IEDA-003-零基础", "call_id": 73,
        "edits": [],
        "expect": {"step": "s3", "done": True},
        "expect_text": "s3“说明多备一份什么时候划算”踩中",
    },
    {
        "id": "C2", "group": "C", "item_id": "IEDA-003-零基础", "call_id": 73,
        "edits": "C2",   # 见 make_c2()：整段替换，保留记号说明和 F(Q) 的定义
        "expect": {"step": "s3", "done": False},
        "expect_text": "s3 没踩中（只预告“接下来解释为什么多备一份划算”，后面直接接计算）",
    },
    {
        "id": "D1", "group": "D", "item_id": "ECON-001-零基础", "call_id": 91,
        "edits": [],
        "expect": {"knowledge_found": False, "gate": "q1", "answered": False},
        "expect_text": "知识通过；卡点 q1 没答上（没讲两边不相等时利率怎么动）",
    },
    {
        "id": "D2", "group": "D", "item_id": "ECON-001-零基础", "call_id": 91,
        "edits": [("在第 4 节“解题的任务：找出一个利率……”那句之后插入指定段落",
                   "**解题的任务：找出一个利率 \\(i\\)，让人们想持有的货币恰好等于中央银行提供的货币。**\n",
                   "**解题的任务：找出一个利率 \\(i\\)，让人们想持有的货币恰好等于中央银行提供的货币。**\n\n"
                   + D2_PARAGRAPH + "\n")],
        "expect": {"knowledge_found": False, "gate": "q1", "answered": True},
        "expect_text": "知识通过；卡点 q1 答上",
    },
    {
        "id": "E1", "group": "E", "item_id": "ECON-004-零基础", "call_id": 19,
        "edits": [
            ("推导里报出的货币供给结果 3636.36 改成 4000",
             "M=2\\times\\frac{2000}{1.10}\\approx3636.36", "M=2\\times\\frac{2000}{1.10}\\approx4000"),
            ("答案表里的货币供给 \\$3,636.36 改成 \\$4,000.00",
             "| Money supply（货币供给）\\(M\\) | \\$3,636.36 |", "| Money supply（货币供给）\\(M\\) | \\$4,000.00 |"),
        ],
        "expect": {"knowledge_found": True, "zeroed": True},
        "expect_text": "触发知识错误，卡点分和步骤分清零",
    },
    {
        "id": "E2", "group": "E", "item_id": "ECON-004-零基础", "call_id": 19,
        "edits": [
            ("删掉算出准备金 181.82 的公式块和结论句",
             "\\[\nRes=0.10D\n=0.10\\times\\frac{2000}{1.10}\n\\approx181.82\n\\]\n\n所以 **Reserves（准备金）约为 \\$181.82**。\n\n",
             ""),
            ("删掉答案表里的准备金一行",
             "| Reserves（准备金）\\(Res\\) | \\$181.82 |\n", ""),
            ("删掉检查里报出 181.82 的那句",
             "**检查：**公众现钞加银行准备金为 \\(1818.18+181.82=2000\\)，符合题目给出的现钞总量。",
             "**检查：**"),
        ],
        "expect": {"knowledge_found": False, "incomplete": True, "missing_contains": "准备金", "zeroed": False},
        "expect_text": "不触发知识错误；incomplete.found 为 true、missing 提到准备金；卡点分、步骤分照常计、不清零",
    },
]


def apply(text: str, edits) -> str:
    for desc, old, new in edits:
        n = text.count(old)
        if n != 1:
            raise SystemExit(f"改动“{desc}”：要改的原文出现 {n} 次（应恰好 1 次），已停止：{old[:60]!r}")
        text = text.replace(old, new, 1)
    return text


def make_c2(text: str) -> tuple[str, list]:
    """C2：把第 2 节里解释“多备一份什么时候划算”的部分换成一句预告，后面直接接计算。
    保留：记号 Q、D 的说明，F(Q) 的定义（属于 s2），临界比率的整理结果和“取第一个达到门槛的数量”（属于 s4）。
    删掉：两种结果的表、边际分析、期望新增利润式子及其文字解释、“F(Q) 与 CR 比较”的三条结论、
          第 3 节末尾用具体数字核对“多备一份值不值”的小节（它同样在讲多备一份什么时候划算）。"""
    start = text.index(C2_CUT_START)
    fq_start = text.index("其中，\n\\[\nF(Q)=P(D\\le Q)\n\\]")
    fq_end = text.index("的概率。\n", fq_start) + len("的概率。\n")
    cut_end = text.index("整理得：")
    fq = text[fq_start:fq_end]
    new_mid = "接下来解释为什么多备一份划算。\n\n" + C2_KEEP_Q + fq + "\n"
    out = text[:start] + new_mid + text[cut_end:]
    edits_desc = [
        "第 2 节：从“先不背公式……要不要再加一份？”到“只要期望新增利润为正……>0”整段，换成一句“接下来解释为什么多备一份划算。”，"
        "保留其中记号 Q、D 的说明和 F(Q) 的定义，后面直接接“整理得：F(Q)<Cu/(Cu+Co)”",
    ]
    bullets = ("- 若 \\(F(Q)<CR\\)：多备一份仍能增加期望利润。\n"
               "- 若 \\(F(Q)>CR\\)：多备一份会降低期望利润。\n"
               "- 若 \\(F(Q)=CR\\)：多备一份的期望新增利润为零，备 \\(Q\\) 份和 \\(Q+1\\) 份一样好。\n\n")
    out = apply(out, [("删掉“F(Q) 与 CR 比较”的三条结论", bullets, "")])
    edits_desc.append("删掉临界比率之后“若 F(Q)<CR 多备一份仍能增加期望利润……”三条")
    check_start = out.index("### 用“多备一份”核对")
    check_end = out.index("**核心理解：")
    out = out[:check_start] + out[check_end:]
    edits_desc.append("删掉第 3 节末尾“### 用‘多备一份’核对”整个小节（用 89→90、90→91 的期望新增利润说明值不值得加）")
    tail = [
        ("临界比率定义句改成“它是一个累计概率门槛。”",
         "**它是判断“是否还值得多备一份”的累计概率门槛。**", "**它是一个累计概率门槛。**"),
        ("文末“少订损失越大，就越值得多备，门槛也越高。”改成“少订损失越大，门槛也越高。”",
         "少订损失越大，就越值得多备，门槛也越高。", "少订损失越大，门槛也越高。"),
    ]
    out = apply(out, tail)
    edits_desc += [d for d, _, _ in tail]
    return out, edits_desc


def main() -> int:
    if not DB.is_file():
        print(f"找不到 {DB}", file=sys.stderr)
        return 2
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    (HERE / "diffs").mkdir(exist_ok=True)
    manifest = []
    for fx in FIXTURES:
        row = conn.execute("SELECT item_id, skill_file, model_name, status, response_text FROM calls WHERE id=?",
                           (fx["call_id"],)).fetchone()
        item_id, skill, model, status, original = row
        assert (item_id, skill, model, status) == (fx["item_id"], "skills/general_v1.md", "gpt-6.1-sol", "ok"), row[:4]
        if fx["edits"] == "C2":
            text, desc = make_c2(original)
        else:
            text = apply(original, fx["edits"])
            desc = [d for d, _, _ in fx["edits"]]
        (HERE / f"{fx['id']}.md").write_text(text, encoding="utf-8")
        diff_path = None
        if text != original:
            diff = difflib.unified_diff(original.splitlines(keepends=True), text.splitlines(keepends=True),
                                        fromfile=f"calls.id={fx['call_id']}（原回答）", tofile=f"{fx['id']}.md", n=2)
            diff_path = f"diffs/{fx['id']}.diff"
            (HERE / diff_path).write_text("".join(diff), encoding="utf-8")
        manifest.append({
            "id": fx["id"], "group": fx["group"], "item_id": fx["item_id"],
            "source_call_id": fx["call_id"],
            "source_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
            "text_file": f"{fx['id']}.md", "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "edits": desc or ["无改动（真实回答原样）"], "diff_file": diff_path,
            "expect": fx["expect"], "expect_text": fx["expect_text"],
        })
        print(f"{fx['id']}  {fx['item_id']:<16} call {fx['call_id']:<4} 改动 {len(desc)} 处  {len(original)} → {len(text)} 字符")
    (HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {HERE.relative_to(ROOT)}/：10 份样例、{sum(1 for m in manifest if m['diff_file'])} 份 diff、manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
