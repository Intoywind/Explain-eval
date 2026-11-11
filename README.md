# explain-eval

测大模型给指定读者讲解课程知识时有没有跳步：术语没先定义、换记号时漏了连接、公式没接上含义、前提没交代。

两轮内容：批量运行被测模型（第一轮）；裁判自动评分、人工盲打、人和裁判对比、两份 Skill 的比较报告（第二轮）。

## 目录

```
skills/            被测的 Skill 文件（不改）
  general_v1.md
  general_v2.md    通用 Skill v2（第五稿）
  original/        三门课各自的原版 Skill，--skill original 时按 course 选
  original_eval/   原版 Skill 的测试副本（删去环境指令），--skill original_eval 时按 course 选
data/
  items.jsonl      开发集，30 条（不改）
  holdout.jsonl    保留集，默认不读，必须显式加 --holdout
  examples.jsonl   items.jsonl 的前 2 条，用于试跑
drafts/            条目生成脚本和旧版存档（程序不读）
prompts/
  judge_v1.md      裁判 prompt 第 1 版（保留不动）
  judge_v2.md      当前使用的裁判 prompt（分 SYSTEM / USER 两段，{{双花括号}} 是占位符；相对 v1 的改动写在文件头注释里）
src/
  schema.py        条目字段定义和校验
  providers.py     统一调用 HKUST GenAI API / OpenAI API（限速、重试、密钥脱敏）
  db.py            SQLite 读写
  run.py           批量运行入口
  scoring.py       裁判输出的解析、引句校验、三档记分（纯函数）
  judge.py         裁判入口
  rules.py         规则检查（篇幅、没学过的词）
  blind.py         人工盲打网页导出、人和裁判对比
  report.py        两份 Skill 的比较报告
  summary.py       四组正式评分的汇总（含裁判稳定性、COMP 关键词、花费）
  longreport.py    长请求验证报告（单独讲 vs 连着讲）
  v2report.py      通用 V1 对 V2 在 30 条短题上的对比报告
tests/             单元测试
  judge_fixtures/  裁判验收样例（make_fixtures.py 从真实回答生成）
config.yaml        接口、默认参数、模型列表、裁判
results/eval.db    运行结果（不入库）
blind/             盲打网页和对应表（不入库）
reports/           比较报告
notes/             AI 编程记录
```

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 然后填密钥；.env 已被 .gitignore 忽略
```

## 配置

`config.yaml`：

- `providers`：两个接口。`hkust` 是 OpenAI 兼容的 chat completions，用请求头 `api-key`，按每分钟 60 次限速；`openai` 用官方 SDK 的 Responses 接口，默认 `store: false`。
- `defaults`：数据库路径、全局生成参数（默认为空，即用接口自己的默认值）、重试设置（首次失败后最多再试 3 次，指数退避）。
- `models`：每个模型写 `name`（命令行用）、`provider`、`model_id`、可选的 `params` 和 `price_per_1m_tokens`（只用于估算费用）。

密钥只从环境变量读：`HKUST_GENAI_API_KEY`、`OPENAI_API_KEY`（可放在 `.env`）。

## 使用

校验条目：

```bash
python -m src.schema data/items.jsonl
```

只组装请求、不调用 API（打印第一条的完整请求，以及每条用了哪份 Skill）：

```bash
python -m src.run --skill skills/general_v1.md --model gpt-6.1-sol --items data/examples.jsonl --dry-run
```

正式运行：

```bash
python -m src.run --skill skills/general_v1.md --model gpt-6.1-sol --items data/items.jsonl --repeats 1
python -m src.run --skill original --model gpt-6.1-sol --items data/items.jsonl --repeats 1
python -m src.run --skill original_eval --model gpt-6.1-sol --items data/items.jsonl --repeats 1
```

读保留集必须加 `--holdout`：

```bash
python -m src.run --skill original --model gpt-6.1-sol --items data/holdout.jsonl --holdout
```

## 请求怎么组装

- 系统提示词 = Skill 文件全文（原样，包括开头的 YAML 头）。
- 用户消息 = 三段，顺序固定，段间空一行；列表项用“；”连接，空列表写“无”：

  ```
  【读者已经会什么】
  学过：…；…
  没学过：…；…

  【材料】
  <material 原文>

  【请求】
  <request 原文>
  ```

- 只读取条目的 `reader_known`、`material`、`request` 三个字段。组装后还会检查：知识错误清单、卡点问题（含 accept、source_quote）、推荐步骤的文本，只要有一条出现在用户消息里，就报错停止。

## 结果怎么存

`results/eval.db`：

- `calls`：每次调用一行，包括 run_id、item_id、Skill 文件和 sha256、模型名、接口返回的实际模型版本、第几次重复、完整的系统提示词和用户消息、`params_used`（发出的参数和接口回报的实际参数）、完整回答、finish_reason、输入/输出用量和原始用量、耗时、尝试次数、时间戳、status、error。
- `runs`：每次执行一行，记录命令参数和汇总数字。

规则：

- **断点续跑**：同一个（item_id、模型名、第几次重复、请求哈希）已有 `status='ok'` 的记录才跳过。请求哈希 `request_sha256` = sha256(system prompt + `\x00` + user message + `\x00` + 实际发出参数的规范化 JSON)，规范化 JSON 指键排序、无多余空白、不转义中文。Skill、材料、请求、读者设定、生成参数任何一处变了都会重跑；判分清单不进请求，改它们不触发重跑。旧库打开时会自动加这一列，并用存着的 system_prompt、user_message、params_used.sent 补算。`--dry-run` 会预览将跳过和需调用的次数。
- **失败**：网络错误、超时、429、5xx 会等待后重试（429 遵守 Retry-After）；其他 4xx 直接记为失败。仍失败就记下错误，继续下一条。
- **截断**：回答因长度上限被截断（finish_reason=length）记为失败，不算成功记录，下次运行会重新调用。

查看示例：

```bash
sqlite3 -header -column results/eval.db "select item_id, model_version, status, finish_reason, input_tokens, output_tokens from calls"
```

## 裁判（第二轮）

```bash
python -m src.judge --prompt prompts/judge_v2.md --dry-run      # 打印第一条完整的裁判请求
python -m src.judge --prompt prompts/judge_v2.md                # 评所有还没评过的当前回答
python -m src.judge --prompt prompts/judge_v2.md --skill skills/general_v1.md --model gpt-6.1-sol --limit 5
python -m src.judge --prompt prompts/judge_v2.md --call-ids 16,31
python -m src.judge --known --prompt prompts/judge_v2.md        # 已知样本检查（data/known_cases.jsonl，不存在就跳过）
python -m src.judge --fixtures --prompt prompts/judge_v2.md     # 裁判验收样例（tests/judge_fixtures/，先运行其中的 make_fixtures.py 生成）
python -m src.judge --repeat 30 --seed 20261111 --prompt prompts/judge_v2.md   # 裁判稳定性：抽 30 份判第二遍
```

- 裁判模型在 `config.yaml` 的 `judge:` 下配置。gpt-6.1-terra 在默认推理强度下不接受 temperature，所以不发；接口回报的实际参数存进 `judgments.params_used`。
- 裁判只拿到：读者学过/没学过、材料、请求、知识错误清单、卡点问题（id、text、accept）、推荐步骤（id、text）、讲解全文。拿不到 Skill、被测模型、重复次数、条目 source/subtype/difficulty、卡点问题出处；组装后会检查。
- **当前回答**：同一个（条目、被测模型、Skill 文件、第几次重复）有多条成功记录时取最新一条（视图 `current_calls`）。裁判、盲打、报告都只用当前回答。
- **断点续跑**：同一份回答、同一个裁判模型、同一个裁判请求哈希（prompt、判分清单、参数、讲解任何一处变了都会变）已有成功记录就跳过。所以改了卡点问题或推荐步骤，旧回答会被重新评，旧记录保留。
- **格式重试**：裁判输出不是合法 JSON、缺字段、类型不对、gaps 的 subtype/severity 不在允许值里、或 gate/steps 的 id 和条目对不上，最多再判 2 次；仍失败记 `error` 继续。和证据不合格的重判共用这 2 次。网络类错误另按 `defaults.retry` 重试。
- `--workers`（默认 4）并发调用，限速仍按 config。
- **稳定性检查**（`--repeat N --seed S`）：从第一遍 ok 的当前回答里按课程分层随机抽 N 份（N 平均分给各课程，余数给课程名排在前面的；课程内按 call_id 排序后用 `random.Random(seed)` 抽），同一裁判、同一版请求再判一遍。结果存 `repeat_judgments`，单独一个 judge_run（`judge_runs.purpose = 'repeat'`），不进任何分数。

### 记分（代码算，裁判不直接给分）

| 档 | 字段 | 记法 |
|---|---|---|
| 知识 | `knowledge_errors` | 触发任一项 = 知识不通过 |
| 卡点分 | `gate_questions` | 答上数 / 问题数（存分子、分母） |
| 步骤分 | `recommended_steps` | 踩中数 / 步骤数（存分子、分母） |

- 知识不通过时卡点分、步骤分的分子记 0，分母不变；逐项原始判断照常入库。
- 引句校验：每条引句去掉首尾空白、连续空白压成一个后，必须是讲解原文（同样规范化）的子串。
- **没有有效证据不能清零，也不能改判**。下面几种情况算“证据不合格”，让裁判重判同一份回答，最多 2 次：
  - `knowledge_error.found` 为 true，但 `which` 为空、或有一条对不上条目的 `knowledge_errors`（去首尾空白后相同才算对上）、或 `quotes` 里没有一条通过校验；
  - 某个卡点 `answered` 为 true、或某个步骤 `done` 为 true，但没有一条引句通过校验。
- 重判后仍不合格的，整份标 `needs_review`（待复核）：存原始输出、解析结果和不合格原因，不算三档分、不写逐项表、不进任何统计；报告单独列出份数和清单。续跑时 `needs_review` 也算评过，不自动再判。
- 引句理由：引句核对不上是裁判抄错了原文，不能把这个错算到被测回答头上。
- “没答全”（`incomplete`）单独记，不影响记分。“卡点全答上” = 知识通过且卡点分 = 1，只用于辅助统计。

### 表

- `judgments`：每次裁判一行：原始输出、解析结果（含每条引句的校验结果）、校验标记、裁判模型和版本、prompt 哈希、判分清单哈希、请求哈希、用量、三档结果。
- `judge_gate` / `judge_steps`：逐问题、逐步骤（只有 `status='ok'` 的裁判结果才有；能计分的结果里 `answered`/`done` 与 `*_raw` 相同）。
- `judge_extra_steps` / `judge_gaps` / `judge_redundancy`：清单外步骤、跳步、冗余，每条带 `quote_valid`。
- `rule_checks`：每份回答的字符数、用到了哪些“没学过”的词和第一次出现的位置（只做字符串匹配，仅供参考）。`python -m src.rules` 单独刷新，裁判运行时也会自动刷新。
- `known_judgments`：已知样本检查的记录，不进入任何统计。
- `fixture_judgments`：裁判验收样例的记录（含 manifest 里的预期、实际值、是否符合、重判记录），不进入任何统计。
- `repeat_judgments`：稳定性检查的第二遍，`first_judgment_id` 指向第一遍的 judgments 记录，记下抽样种子；不进入任何分数。
- `judge_runs.purpose`：`main` = 正式评分，`repeat` = 稳定性检查；更早的记录为空。

## 人工盲打

```bash
python -m src.blind export --design outcome --per-part 15 --seed 20261112 --out blind/round1/   # 正式盲标包
python -m src.blind export --n 50 --seed 1 --out blind/test/                                     # 按条件轮流抽
python -m src.blind compare blind/round1/key.json ~/Downloads/blind_round1_xxx.json
```

- `index.html` 是单文件网页，不依赖网络，直接双击打开即可。Markdown 和公式已预先转好（公式用浏览器原生的 MathML 显示，转不了的原样显示 TeX）。
- 页面不显示 Skill、被测模型、条目 id、裁判结果、卡点问题出处；对应关系只在 `key.json` 里，打分完再用。
- 先填“看懂了没有”，填完才显示卡点问题；推荐步骤默认折叠、选填。进度自动存在浏览器本地；“导出结果”下载 JSON。
- 抽样（`--design condition`，默认）：轮流按（Skill 组 × 被测模型）取，每次挑这个条件下被抽次数最少的条目，尽量让每个条目、每份 Skill 都抽到。
- 抽样（`--design outcome`）：按 `--judge-prompt` 那版裁判的当前结果分两部分，各抽 `--per-part` 份：fail = 知识不通过或至少一个卡点问题没答上，pass = 知识通过且卡点全答上。先抽 fail 再抽 pass；每次挑使（本部分该组已抽数 + 本部分该课程已抽数）最小的回答，再看（组 × 课程）格子和该条目已抽数，并列时用种子随机；同一条目两部分合计最多 3 份。没评过或待复核的回答不抽。30 份顺序打乱；部分、组、课程和裁判记录 id 只写在 `key.json`。
- `compare` 输出 Markdown（默认写到 key.json 旁边的 `compare.md`）：逐问题一致率和 Cohen's kappa、每份回答的卡点分对比（裁判判知识不通过的单列）、逐步骤一致率和 kappa、全部分歧清单、总体判断 × 卡点分交叉表、分歧偏向。

## 两份 Skill 的比较报告

```bash
python -m src.report --a skills/general_v1.md --b original_eval --model gpt-6.1-sol --judge-prompt prompts/judge_v2.md --out reports/
```

- 只比较两边都有裁判结果、且重复次数相同的条目；其余列出来，不计入。
- 先在条目内对几次重复取平均（知识不通过的那次按 0），再在条目间取平均。
- 每个数字后面的 [Qn] 指向文末附录的 SQL，可以直接在 `sqlite3 results/eval.db` 里运行。报告运行时会把当前条目元数据写进 `items_snapshot`、`items_gate`、`items_steps` 三张表供 SQL 关联。
- 单列：各组的 needs_review 份数和清单；裁判 note 以“清单外：”开头的结果（条目、回答 id、note 原文）。
- 只报数字，不做显著性检验，不下结论。

## 三组汇总

```bash
python -m src.summary --judge-prompt prompts/judge_v2.md --out reports/
```

- 输出 `reports/summary__judge_v2.md`：各组份数；知识通过率、没答全比例、卡点分和步骤分均值（按回答、按条目两种）与分布；两份 Skill × 两档模型的 2×2 表；同一模型下两份 Skill 逐条目的升降条数；ECON-003 按新条目重判前后的变化；逐条目三组对比；知识不通过清单；needs_review 和失败清单；“清单外”备注；gaps 的 severity 分布；裁判稳定性（两遍的一致率和 kappa）；COMP original_eval 回答里要文件路径、“待原题补齐”“非历年真题”的份数和原句；实际花费。
- 只用 `judgments` 表里的正式评分；第二遍和验收样例不进分数。每个数字后的 [Qn] 指向文末附录的 SQL。

## 长请求验证

```bash
python -m src.run --skill skills/general_v1.md --model gpt-6.1-sol --items data/items_long_dev.jsonl --repeats 3 \
    --max-output-tokens 32000 --timeout 1800 --workers 3 --stream
python -m src.judge --prompt prompts/judge_v2.md --items data/items_long_dev.jsonl --max-output-tokens 32000 --timeout 1800 --stream --workers 6
python -m src.judge --repeat 12 --seed 20261113 --strata model_course --prompt prompts/judge_v2.md --items data/items_long_dev.jsonl \
    --max-output-tokens 32000 --timeout 1800 --stream
python -m src.longreport --out reports/
```

- `data/items_long_dev.jsonl` 由 `drafts/build_items_long.py` 从 `data/items.jsonl` 拼成：同课同读者版本的 5 条并成一条，卡点、步骤 id 加 `p<i>` 前缀，文字加“（第 i 部分）”；`data/items_long_dev_map.json` 记录对应关系。
- **流式（`--stream`）**：本机网络会在约 60 秒时断开非流式请求，长输出必须用流式。流式只是传输方式，不进请求哈希。
- `--max-output-tokens`、`--timeout` 只覆盖这一次运行，不改 config；`max_output_tokens` 进实际发送的参数、存进库，也进请求哈希。
- 长请求条目 id 与短条目不同，`current_calls` 里互不覆盖；四组汇总、两份 Skill 比较、盲标只认 `data/items.jsonl` 里的条目（`items_snapshot`），长请求数据不进这些报告。
- 报告 `reports/long_dev__judge_v2.md`：逐卡点（不套知识清零）短 vs 长、按部分/课程/读者分解、步骤、卡点全答上占比（含 5 份短回答按重复序号合一份）、篇幅（按“第 i 部分”标题切开）、知识错误与没答全、待复核、第二遍一致率、花费。

## 通用 V1 对 V2（30 条短题）

```bash
python -m src.run --skill skills/general_v2.md --model gpt-6.1-sol --items data/items.jsonl --repeats 3 --workers 6 --stream
python -m src.run --skill skills/general_v2.md --model gpt-6-luna --items data/items.jsonl --repeats 3 --workers 6 --stream
python -m src.judge --prompt prompts/judge_v2.md --skill skills/general_v2.md --workers 8 --stream
python -m src.judge --repeat 20 --seed 20261112 --strata model --skill skills/general_v2.md --prompt prompts/judge_v2.md --workers 8 --stream
python -m src.v2report --out reports/
```

- `--repeat` 现在也认 `--skill`、`--model`：先筛出可抽的回答再分层；`--strata model` 按被测模型分层。不给这两个参数时和以前一样。
- 裁判的泄漏检查也查 `skills/` 下各份通用 Skill 的文件名和 YAML 头里的 name、version（如 general_v2、general-explain-v2、2.0-draft5）。
- 四组汇总（`src.summary`）只算 general_v1 和 original_eval 的回答，V2 的生成、判分、第二遍、花费都不进它。
- 报告 `reports/short_v1_vs_v2__judge_v2.md`：汇总（按课程、读者版本）、逐卡点、重点卡点、变差的卡点、步骤（逐条在附录）、篇幅和冗余、编程入门内容检查、知识错误、跳步、步骤分与卡点分对照、样例挑选依据、待复核、第二遍一致率、花费。
- 样例 `reports/short_v1_vs_v2_samples.md`：6 组同一条目、同一模型、同一重复序号的 V1/V2 回答原文，不附裁判结论。

## 测试

```bash
python -m unittest discover -s tests -t . -v
```
