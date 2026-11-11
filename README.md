# explain-eval

测大模型给指定读者讲解课程知识时有没有跳步：术语没先定义、换记号时漏了连接、公式没接上含义、前提没交代。

本轮只有项目骨架和批量运行，**还没有自动评分**。

## 目录

```
skills/            被测的 Skill 文件（不改）
  general_v1.md
  original/        三门课各自的原版 Skill，--skill original 时按 course 选
  original_eval/   原版 Skill 的测试副本（删去环境指令），--skill original_eval 时按 course 选
data/
  items.jsonl      开发集，30 条（不改）
  holdout.jsonl    保留集，默认不读，必须显式加 --holdout
  examples.jsonl   items.jsonl 的前 2 条，用于试跑
drafts/            条目生成脚本和旧版存档（程序不读）
src/
  schema.py        条目字段定义和校验
  providers.py     统一调用 HKUST GenAI API / OpenAI API（限速、重试、密钥脱敏）
  db.py            SQLite 读写
  run.py           批量运行入口
config.yaml        接口、默认参数、模型列表
results/eval.db    运行结果（不入库）
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
