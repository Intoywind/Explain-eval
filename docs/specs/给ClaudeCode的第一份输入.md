# 给 Claude Code 的第一份输入

这份文件是什么：第一轮交给 Claude Code 的任务说明。它只让 Claude Code 搭项目骨架和“批量运行”（把条目发给被测模型、把回答存下来），不做评分。评分是第二轮，见《给ClaudeCode的第二份输入》。

用法：在 Claude Code 里打开这个文件夹（explain-eval）：桌面端用 Code 标签选文件夹，或在终端 cd 进来输入 claude。然后把下面两条“---”之间的全部内容粘贴进去。它会先给你看计划，你回“可以”后它才动手。

---

我在做一个评测项目：测大模型给指定读者讲解课程知识时，有没有跳步（术语没先定义、换记号时漏了连接、公式没接上含义、前提没交代）。当前文件夹已经有三样东西，都不要改：`skills/`（被测的 Skill 文件）、`data/items.jsonl`（30 条评测条目）、`drafts/`（生成条目的脚本和存档）。这一轮只搭项目骨架和“批量运行”，不做自动评分。

请先读 `skills/` 下所有文件、`data/items.jsonl` 的前两行和本说明，给我一份简短计划（要建哪些文件、每个文件做什么、你打算怎么验证），等我确认后再写代码。

## 1. 目录结构

```
explain-eval/
  README.md               项目说明、怎么运行
  .gitignore              至少忽略 .env、results/、__pycache__/
  .env.example            只写变量名，不写真实密钥
  config.yaml             模型列表（名字由我填）、默认参数
  skills/                 已存在，不要改里面的内容
    general_v1.md
    original/comp2711_v2.3.md
    original/ieda1280_v1.5.md
    original/econ1221_v1.6.md
  data/
    items.jsonl           已存在，开发集，每行一条评测条目，不要改
    holdout.jsonl         已存在（现在是空的），保留集，默认不读
    examples.jsonl        2 条示例条目（你从 items.jsonl 复制前 2 行）
  drafts/                 已存在，条目的生成脚本和旧版存档，不要改、不要读进程序
  src/
    schema.py             条目字段定义和校验
    providers.py          统一调用 HKUST GenAI API 和 OpenAI API
    db.py                 SQLite 读写
    run.py                批量运行入口
  results/eval.db         运行结果（被 .gitignore 忽略）
  notes/ai_coding_log.md  AI 编程记录
```

## 2. 评测条目格式（data/*.jsonl，每行一个 JSON）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | 字符串 | 唯一，如 `ECON-001-零基础` |
| course | 枚举 | `COMP2711` / `IEDA1280` / `ECON1221` |
| knowledge_point | 字符串 | 知识点名称 |
| subtype | 枚举 | `术语未先定义` / `切换处漏连接` / `公式未接含义` / `前提未交代` |
| source | 字符串 | `real:<报告名>#<条目号>` 或 `new` |
| difficulty | 枚举 | `低` / `中` / `高` |
| reader_known | 对象 | `{"learned": [...], "not_learned": [...]}` |
| request | 字符串 | 请求原文 |
| material | 字符串 | 讲义片段或题目原文 |
| knowledge_errors | 列表 | 知识错误清单，判分用（第一档），字符串列表，至少 1 项 |
| gate_questions | 列表 | 卡点问题，判分用（第二档），至少 1 项。每项 `{"id": "q1", "text": "...", "accept": "...", "source_level": "...", "source_ref": "...", "source_quote": "..."}`，其中 `source_quote` 可以是空字符串 |
| recommended_steps | 列表 | 推荐步骤，判分用（第三档），至少 1 项。每项 `{"id": "s1", "text": "..."}` |
| split | 枚举 | `dev` / `holdout`，必须和所在文件一致 |

`source_level` 的枚举值：`原话` / `报告定位` / `推测`。

`schema.py` 要能校验：字段齐全、枚举值合法、id 不重复、knowledge_errors 至少 1 项、gate_questions 至少 1 项且每项字段齐全、recommended_steps 至少 1 项且每项字段齐全、同一条内问题 id 不重复、步骤 id 不重复、split 与文件一致。空文件算通过。提供命令 `python -m src.schema data/items.jsonl`，打印每条错误的行号和原因。

## 3. 怎么组装一次请求

- 系统提示词 = 所选 Skill 文件的全文。
- 用户消息 = 三段，顺序固定：
  1. `【读者已经会什么】` 学过：…；没学过：…
  2. `【材料】` material 原文
  3. `【请求】` request 原文
- 不加任何其他指令，避免影响被测结果。
- `knowledge_errors`、`gate_questions`、`recommended_steps`、`source`、`subtype`、`difficulty` 只用于判分和分析，绝对不能出现在发给被测模型的请求里。

## 4. run.py 的要求

- 命令形式：`python -m src.run --skill skills/general_v1.md --model <config 里的模型名> --items data/items.jsonl --repeats 1`
- 也支持 `--skill original`：这时每条条目按 course 自动选 `skills/original/` 里对应的那份。
- 读 `data/holdout.jsonl` 必须显式加 `--holdout`，否则拒绝并报错。
- 每次调用存进 SQLite 一行：run_id、item_id、skill 文件名、skill 内容的哈希、模型名、第几次重复、完整请求（系统提示词和用户消息）、完整回答、输入和输出的用量、耗时、时间戳、错误信息（如果有）。
- 断点续跑：同一个（item_id、模型、第几次重复、实际发出的请求哈希）已经有成功记录的，才跳过。请求哈希 = sha256(system prompt + user message + 调用参数的规范化 JSON)，所以 Skill、材料、请求、读者设定或生成参数任何一处变了，都会重跑，旧回答保留在库里但不再被当作这一版的结果。判分清单（knowledge_errors、gate_questions、recommended_steps）不进请求，改它们不触发重跑。
- 调用失败时等一会儿重试，最多 3 次；仍失败就记下错误，继续下一条，不要整体中断。
- `--dry-run`：只组装请求，打印第一条的完整内容，不调用 API。
- 运行结束打印：成功几条、失败几条、跳过几条、总用量。

## 5. API、密钥和安全

- 模型可能来自两个接口，都在 config.yaml 里按“接口”配置，每个模型注明走哪个接口：
  - `hkust`：HKUST GenAI API，OpenAI 兼容的 chat completions。地址 `https://hkust.azure-api.net/hkust-genai/v1/chat/completions`；鉴权用请求头 `api-key: <密钥>`（不是 Authorization: Bearer）；网关限速每分钟 60 次，脚本要控制速率，遇到限速等待后重试。密钥变量 `HKUST_GENAI_API_KEY`。
  - `openai`：OpenAI 官方 API，用官方 Python SDK。密钥变量 `OPENAI_API_KEY`。
- providers.py 对外只提供一个统一的调用函数，换接口只改配置。
- 密钥只从环境变量读（可以用 .env 加载）。任何文件、日志、数据库、提交记录里都不能出现密钥。
- 模型名写在 config.yaml 里，不要在代码里写死，我会自己填。

## 6. 验收（做完后逐条跑给我看）

1. `python -m src.schema data/items.jsonl` 通过，报告 30 条；把 examples.jsonl 故意改坏一条（比如删掉 knowledge_errors，或把 recommended_steps 改成空列表）能报出行号和原因，验证完改回来。
2. `python -m src.run --skill skills/general_v1.md --model <任一模型> --items data/examples.jsonl --dry-run` 打印出组装好的请求，三段顺序正确，里面没有知识错误清单、卡点问题和推荐步骤的内容。
3. `--skill original` 的 dry-run 能按 course 选对文件。
4. 不加 `--holdout` 去读 holdout.jsonl 会报错。
5. 用真实 API 跑 examples.jsonl 的 2 条：数据库里有 2 行，字段齐全；再跑一次同样的命令，显示跳过 2 条。

## 7. 收尾

- `git init`，提交一次，提交说明写清这一轮做了什么。
- 在 `notes/ai_coding_log.md` 记一条：我让你做什么、你实际建了和改了哪些文件、用哪几条命令验证的、结果如何。
- 最后告诉我：哪些地方你做了假设、哪些地方需要我决定。

---
