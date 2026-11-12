# explain-eval

测大模型按指定读者讲解课程知识时，**答案是对的，却跳过了这位读者看懂所必需的一步**：术语没先定义、换记号时漏了连接、公式没接上含义、前提没交代。

## 结果

同一批题、同一个裁判，三份讲解 Skill 各跑一遍。数字是**合并卡点分得分率**：所有回答的卡点得分之和 ÷ 卡点满分之和。每组 180 份回答，满分 1,173；讲错知识的回答按规则清零。

| 被测模型 | 原课程 Skill | 通用 V1 | 通用 V2 | V2 − V1 | 95% 区间 |
|---|---|---|---|---|---|
| gpt-6.1-sol（强） | 79.9% | 77.8% | 86.1% | **+8.3 个百分点** | [+3.6, +13.7] |
| gpt-6-luna（弱） | 52.3% | 53.5% | 60.7% | +7.2 个百分点 | [+2.8, +11.6] |

- 主指标是强模型上的 V2 − V1。跑之前定的目标是 15 个百分点，实际是 +8.3，**没有达到**。
- 区间的算法：以“一道题”为单位（30 个单位）有放回抽样 2000 次。
- V2 相对原课程 Skill：强模型 +6.2 [+2.6, +10.5]，弱模型 +8.4 [+0.7, +15.0]。V1 相对原课程 Skill：两个模型的区间都跨过 0。

完整报告见 [`reports/test_three_skills__judge_v2.md`](reports/test_three_skills__judge_v2.md)。里面有按长题 / 短题、题型、课程、读者版本分开的结果，以及步骤分、跳步、篇幅、裁判一致率和实际花费。主结果的查询附在报告末尾。

## 怎么测的

- **评测条目**：60 条（[`data/items_merged.jsonl`](data/items_merged.jsonl)）。短题 30 条，长题 30 条（15 道题，每道各有零基础、有前置两个读者版本）。三门课是离散数学、运营管理和宏观经济学。
- **每条条目给被测模型三样东西**：读者已经会什么、材料原文、请求原文。系统提示词是所选 Skill 的全文，不加任何其他指令。判分用的内容不进请求，程序在组装请求后会逐条检查。
- **卡点问题**：共 221 个（短题 51 个，长题 170 个）。每个卡点问“读者到这里会卡在哪”，并写明怎样算答上。
- **三档记分**：
  1. 知识：裁判判出知识错误清单里的错误，这份回答的卡点分、步骤分清零。概念理解类长题只清讲错的那一部分。
  2. 卡点分：主指标。
  3. 推荐步骤分：只当对照。
  - 长题每个卡点、步骤记 2 分，短题记 1 分。
- **裁判引原句**：裁判每判一项“答上”“做到”或“讲错”，都必须引用讲解原文。程序校验引句确实出现在讲解里；校验不过就重判，仍不过的标“待复核”，不计分。
- **重复**：每条条目每组生成 3 次。
- **裁判一致率**：长回答随机抽 54 份（六组各 9 份）再判一遍。知识判断一致 53/54，卡点一致率 96.8%，步骤一致率 97.0%。

## 做法

作者主导整个项目：从真实使用中的失败里选定评测问题，确定三组对照、主指标、三档记分规则和卡点标准，逐条审定评测条目，并在每一轮结果出来后决定下一步。工程实现采用 AI 编程，以 [`docs/specs/`](docs/specs/) 下 7 份带验收标准的需求文档驱动 Claude Code 完成。主结果另用独立脚本从数据库复算核对。

## 目录

```
skills/                      被测的 Skill
  general_v1.md              通用 V1
  general_v2.md              通用 V2（第五稿，正式测试用）
  original/                  三门课各自的原课程 Skill
  original_eval/             原课程 Skill 的测试副本（删去读写本机文件等环境指令；删改清单.md 逐条列出）
data/
  items.jsonl                短题 30 条（开发集）
  items_long_test.jsonl      长题 30 条
  items_merged.jsonl         正式评测集 60 条 = 短题 + 长题，带分值和清零规则
  items_merged_points.md     分值表
  items_long_test_*_map.json 长题卡点的规则标签、过程 / 结果分类、题型（只用于报告分组，不发给模型和裁判）
  examples.jsonl             短题前 2 条，试跑用
  holdout.jsonl              保留集（空），必须显式加 --holdout 才读
prompts/
  judge_v2.md                裁判 prompt（正式使用）；judge_v1.md 是第一版
src/
  schema.py                  条目校验
  providers.py               统一调用 OpenAI / HKUST GenAI 接口（限速、重试、密钥脱敏）
  db.py                      SQLite 读写
  run.py                     批量生成
  judge.py                   裁判（引句校验、重判、待复核、判第二遍）
  scoring.py                 裁判输出解析与三档记分
  merged.py                  正式评测集计分（merged_scores 表）
  testreport.py              正式测试报告
  rules.py                   规则检查（篇幅、没学过的词）
  blind.py                   人工盲标网页导出、人和裁判对比
  report.py / summary.py / v2report.py / longreport.py   各阶段的比较报告
tests/                       单元测试和裁判验收样例
reports/                     各阶段报告（正式结果是 test_three_skills__judge_v2.md）
docs/specs/                  7 份需求文档（每一轮的要求和验收标准）
notes/
  ai_coding_log.md           AI 编程记录
  commit_map.md              改写历史前后的提交编号对照（文档里引用的是旧编号）
drafts/                      条目生成脚本、各版草稿和存档
config.yaml                  接口、模型、裁判和默认参数（密钥不在这里）
```

**作废或存档内容，只留作记录，结果不引用：**

- `data/items_long_dev*` 和 `reports/long_dev__judge_v2.md`：把同一门课的几道短题硬拼成一次请求的“长请求”，后来判定不是正常的学习请求，结果不引用。
- `drafts/` 下文件名带“存档”或 `archive` 的：条目和 Skill 的历次草稿。

不在仓库里的：`.env`（密钥）、`results/`（数据库和日志）、`blind/`（人工盲标网页）。

## 怎么运行

### 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填 OPENAI_API_KEY（或 HKUST_GENAI_API_KEY）；.env 已被 .gitignore 忽略
```

`config.yaml` 里每个模型写 `name`（命令行用）、`provider`（`openai` 或 `hkust`）、`model_id`、可选的 `params` 和价格。密钥只从环境变量读。

### 校验条目、只组装请求不调接口

```bash
python -m src.schema data/items_merged.jsonl
python -m src.run --skill skills/general_v2.md --model gpt-6.1-sol --items data/items_merged.jsonl --tier 长题 --repeats 3 \
    --max-output-tokens 32000 --stream --dry-run
python -m src.judge --prompt prompts/judge_v2.md --items data/items_merged.jsonl --tier 长题 --max-output-tokens 32000 --stream --dry-run
```

`--dry-run` 打印第一条完整请求和续跑预览（会跳过几次、要调用几次）。输出上限等参数要和正式运行一致，否则请求哈希不同，预览会显示需要重跑。

### 正式测试的完整流程

```bash
# 生成：三份 Skill × 两个模型，长题每条 3 次（短题沿用已有回答，用 --items data/items.jsonl 生成）
python -m src.run --skill skills/general_v2.md --model gpt-6.1-sol --items data/items_merged.jsonl --tier 长题 --repeats 3 \
    --max-output-tokens 32000 --timeout 1800 --stream --workers 16
python -m src.run --skill original_eval --model gpt-6.1-sol --items data/items_merged.jsonl --tier 长题 --repeats 3 \
    --max-output-tokens 32000 --timeout 1800 --stream --workers 16      # original_eval：每门课的题配这门课自己的那份

# 判分
python -m src.judge --prompt prompts/judge_v2.md --items data/items_merged.jsonl --tier 长题 --skill skills/general_v2.md \
    --model gpt-6.1-sol --max-output-tokens 32000 --timeout 1800 --stream --workers 8
python -m src.judge --repeat 54 --seed 20261114 --strata skill_model --prompt prompts/judge_v2.md \
    --items data/items_merged.jsonl --tier 长题 --max-output-tokens 32000 --timeout 1800 --stream --workers 27

# 计分和报告
python -m src.merged
python -m src.testreport --out reports/
```

### 规则

- **断点续跑**：同一个（条目、模型、第几次重复、请求哈希）已有成功记录就跳过。请求哈希覆盖 system prompt、用户消息和实际发出的参数，任何一处变了都会重跑。裁判同理，按裁判请求哈希跳过。
- **失败**：网络错误、超时、429、5xx 会等待后重试，最多 3 次。回答因长度上限被截断的记为失败，下次运行会重新调用。
- **流式**：`--stream` 只是传输方式，不进请求哈希。长输出要用它，非流式请求超过约 60 秒可能被网络断开。
- **当前回答**：同一个（条目、模型、Skill、第几次重复）有多份成功记录时取最新一份。
- **保留集**：读 `data/holdout.jsonl` 必须显式加 `--holdout`。

### 各阶段的报告

```bash
python -m src.summary --judge-prompt prompts/judge_v2.md --out reports/          # 短题四组汇总
python -m src.v2report --out reports/                                            # V1 对 V2，30 条短题
python -m src.report --a skills/general_v1.md --b original_eval --model gpt-6.1-sol --judge-prompt prompts/judge_v2.md --out reports/
python -m src.blind export --design outcome --per-part 15 --seed 20261112 --out blind/round1/   # 人工盲标网页
```

### 测试

```bash
python -m pytest            # 或 python -m unittest discover -s tests -t .
```

## 已知的局限

- 没有不带 Skill 的基线，说不清三份 Skill 各自比“什么都不加”好多少。
- V2 的规则比 V1 长得多（约 4 倍），没做拆条对照，不知道是哪几条规则起的作用。
- 只测了一家厂商的两档模型。
- 裁判和被测模型是同一家厂商的模型。
- 长题的卡点多数能对上 V2 的某条规则（`data/items_long_test_rule_map.json`）。V2 是照短题的失败写的，测试题又按同样的失败类型出，结果可能偏向 V2。

## 题目来源

`data/` 里的材料是为评测改写的课程内容短摘。离散数学的 3 道长题取自往年期中题，运营管理有 1 道长题节选自课程官方样卷；条目的 `source` 字段都有标注。全部材料仅用于本项目的评测。
