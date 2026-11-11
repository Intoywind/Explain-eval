"""从原课程 Skill 生成测试副本：只删环境指令（读写文件、存进度、本机路径），讲解规则不动。
每处删除必须恰好匹配一次，否则报错。原文件不改。"""
import sys, pathlib, re
SRC = pathlib.Path(sys.argv[1]); DST = pathlib.Path(sys.argv[2]); DST.mkdir(parents=True, exist_ok=True)

# (文件, 要删的原文, 理由)
CUTS = {
"econ1221_v1.6.md": [
 ("开始／续接时读[四轮计划](references/round-plan.md)和[进度](references/progress.md)，第一次选材再读[材料、题源与勘误](references/materials-and-questions.md)。",
  "每次都触发；要读的计划、进度、材料文件在单次调用里不存在"),
 ("本机课程原件与整理笔记的确切入口见材料索引。先读对应原件，",
  "每次都触发；要读本机原件"),
 ("索引失效先查用户指定材料与现有目录；",
  "要查本机目录"),
 ("6. 正式包和学习输出保存在 Obsidian ECON1221 的 AI工作区；进度更新本包的 references/progress.md。保持一个正式包，不修改 COMP2711 包，不向原始课程 PDF 写批注或覆盖它。无法保存时给出简短续接状态，不能宣称已经落盘。\n",
  "整条是保存位置和存进度"),
 ("选题前先对照本模块相关课件、指定习题和 Tutorial，",
  "每次都触发；要翻本机课件和习题"),
 ("每次交付后只更新进度中的模块状态、使用题源、实际卡点、下次起点与去重记忆卡。",
  "存进度"),
],
"comp2711_v2.3.md": [
 ("开始或续接时，读取[轮次计划](references/round-plan.md)和[学习进度](references/progress.md)；选题再读[题源与勘误](references/exam-index.md)，打开所需原件。",
  "每次都触发；要读计划、进度、题源文件"),
 ("材料位置依次检查：用户本次指定的目录/附件 → 本机 iCloud 课程原件根目录 → 另一环境的挂载目录。核对具体文件可读，而不只检查文件夹存在：",
  "每次都触发；要检查本机目录（第 5 条只删这句和下面四个依赖本机的分项，“多版本分工”“版本冲突”两项保留）"),
 ("   - 本机：`<本机课程资料目录>/HKUST_yr2_26FALL课程/COMP2711/`\n",
  "本机绝对路径，带用户名"),
 ("   - 挂载：`/mnt/project-files/COMP2711/`\n",
  "挂载路径"),
 ("   - 在原件根目录内，`Common_Slides/` 核对范围，`L3_Mingxun_Zhou/Course_Notes/` 解释规则，`Past_Exams/` 找真题，`Homework/`、`Tutorials/` 补充题源。根目录失效先检查用户现有附件和课程材料指引，不立即让用户重传。\n",
  "本机目录里各文件夹的用途"),
 ("   - **用户需要提供什么**：当前课程原件可读时，由模型按本轮计划自己定位资料，无需用户逐份挑选或重复上传。若换到无法读取本机目录的聊天，先列本轮最小文件清单：范围通知、相应主题的Common Slides和L3 Course Notes、选用的历年卷；已有可读材料不重复索要，不让用户上传所有版本。不能把收到路径当作已经读到文件。\n",
  "单次调用里读不到本机目录，这条每次都会触发，让模型先向用户要文件"),
 ("先说明缺哪份材料并只问一次可用路径；①②④可先交付，③保留“待原题补齐”，记录**本模块未完整交付**。",
  "单次调用里永远拿不到历年卷文件，这句每次讲到③都会触发，要模型问路径、标未完成（第 7 条其余标注题源的规则保留）"),
 ("材料到位后先补③及其秋明连接。",
  "同上，依赖之后补材料"),
 ("__ITEM8__", "整条是进度和输出的保存位置"),
 ("取题前看[题源与勘误](references/exam-index.md)，",
  "要读题源文件"),
 ("按最新round-plan.md和progress.md核对轮数、大块数量及应教知识点；",
  "每次自检都触发；要读计划和进度文件"),
 ("教学交付后更新[学习进度](references/progress.md)：已讲模块、题源、实际卡点、待补项、下一起点和去重后的A4候选。",
  "存进度"),
],
"ieda1280_v1.5.md": [
 ("准备每轮前，读 [完整范围与材料](references/scope-and-sources.md) 的对应轮次。输出前必须读 [三项自检](references/quality-gates.md)。\n\n",
  "每次都触发；要读范围文件和自检文件"),
 ("实际读取对应课程原件；AI 总结只用于找材料。原件和勘误入口见材料参考。",
  "每次都触发；要读本机原件"),
 ("唯一正式 skill 源文件位于课程 Obsidian AI工作区中的本包，安装入口指向本包。清单保存到同一 AI工作区的“四轮知识清单”目录；每轮一份稳定文件，追问造成的必要修订更新对应段落。不覆盖原始课程 PDF。保存失败如实说明，不宣称落盘成功。\n\n",
  "整段是 Skill 和清单的保存位置"),
],
}

log = []
for name, cuts in CUTS.items():
    text = (SRC/name).read_text(encoding="utf-8"); orig = text
    lines = text.split("\n")
    for old, why in cuts:
        if old in ("__ITEM5__", "__ITEM8__"):
            start_pat = "5. 材料位置依次检查" if old == "__ITEM5__" else "8. 进度存本包的"
            ls = text.split("\n")
            i = [k for k,l in enumerate(ls) if l.startswith(start_pat)]
            assert len(i) == 1, (name, old)
            j = i[0] + 1
            while j < len(ls) and ls[j].startswith("   "): j += 1
            old = "\n".join(ls[i[0]:j]) + "\n"
        n = text.count(old)
        assert n == 1, f"{name}: 匹配 {n} 次: {old[:40]}"
        lineno = orig[:orig.index(old)].count("\n") + 1
        text = text.replace(old, "", 1)
        log.append((name, lineno, old.rstrip("\n"), why))
    for bad in ("本机课程资料目录", "HKUST_yr2_26FALL课程", "/mnt/", "progress.md", "round-plan"):
        assert bad not in text, (name, bad)
    (DST/name).write_text(text, encoding="utf-8")

out = ["# 原课程 Skill 测试副本：删改清单", "",
       "规则：只删单次 API 调用里做不到、且每次都会触发的环境指令（读写文件、存进度、本机路径）。讲解规则一个字不动；只在特定情况才触发的条件句保留。原文件不改。", ""]
for name in CUTS:
    out.append(f"## {name}"); out.append("")
    for f, ln, old, why in log:
        if f != name: continue
        where = f"原第 {ln} 行" if ln else "编号"
        out.append(f"- {where}，{why}：")
        out.append(f"  > {old.replace(chr(10), chr(10)+'  > ')}")
    out.append("")
(DST/"删改清单.md").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
