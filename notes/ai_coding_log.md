# AI 编程记录

## 2026-11-11 第一轮：项目骨架和批量运行（Claude Code，claude-opus-5-5）

### 我让 AI 做什么

搭建评测项目骨架和“批量运行”，不做自动评分。`skills/`、`data/items.jsonl`、`drafts/` 不改。要求包括：

- `schema.py` 校验条目，打印行号和原因。
- `providers.py` 用一个统一函数调用 HKUST GenAI API 和 OpenAI API。
- `db.py` 把每次调用存进 SQLite。
- `run.py` 支持 `--skill original`、`--holdout` 保护、断点续跑、重试、`--dry-run` 和结束时的汇总。
- 密钥只从环境变量读。

确认计划时补充的要求：

- 两份《给ClaudeCode的…输入》提交进 git；《开工前要准备的.md》加进 .gitignore。
- 数据库额外记录实际模型版本、finish_reason、实际参数；因长度上限被截断的回答记为失败。
- 第一次提交前确认 .env 在 .gitignore 里，git status 里看不到它。
- 真实 API 只跑 examples.jsonl 的 2 条，报告用量和费用，经我确认后再跑 30 条。

被测模型：OpenAI `gpt-6.1-sol`（我只用 OpenAI 接口）。

### 实际新建、修改的文件

新建：

- `README.md`、`.gitignore`、`.env.example`、`config.yaml`、`requirements.txt`
- `data/examples.jsonl`：items.jsonl 前 2 行原样复制，逐字节一致
- `src/__init__.py`、`src/schema.py`、`src/providers.py`、`src/db.py`、`src/run.py`
- `notes/ai_coding_log.md`（本文件）

未提交（被忽略）：`.env`（我自己写入的密钥）、`.venv/`、`results/eval.db`

修改：

- `.env`：我粘贴密钥时粘了两遍。AI 确认前后两半完全相同后只保留一份，过程中没有显示密钥。
- `skills/`、`data/items.jsonl`、`data/holdout.jsonl`、`drafts/` 没有改动。

### 过程中发现的问题和处理

- **source 格式**：items.jsonl 第 15–18 行（COMP-003、COMP-004）的 source 是 `real:COMP2711-GPT自查C08`，没有 `#`。这项校验降为“提醒”，照样打印，但不影响通过；条目本身没改。
- **SSL 证书**：本机 python.org 版 Python 缺 SSL 根证书，用 urllib 访问 HTTPS 会失败。项目代码走 httpx 和 openai SDK，两者都用 certifi，不受影响。
- **模型版本**：`gpt-6.1-sol` 没有带日期的固定版本，接口返回的 model 也只是 `gpt-6.1-sol`。实际模型版本仍逐条记录在 `model_version`。

### 用哪几条命令验证、结果如何

| # | 命令 | 结果 |
|---|---|---|
| 1 | `python -m src.schema data/items.jsonl` | 30 条全部通过（另有 4 条 source 格式提醒） |
| 1 | 改坏 examples.jsonl 后 `python -m src.schema data/examples.jsonl` | 报出：第1行缺 knowledge_errors；第2行 recommended_steps 为 0 项、gate_questions id 重复、split 与文件不一致。退出码 1。改回后与 items.jsonl 前两行逐字节一致 |
| 2 | `python -m src.run --skill skills/general_v1.md --model gpt-6.1-sol --items data/examples.jsonl --dry-run` | 三段顺序正确；system 与 general_v1.md 全文一致；14 条判分文本都不在输出中 |
| 3 | `python -m src.run --skill original --model gpt-6.1-sol --items data/items.jsonl --dry-run` | 三门课各 10 条，都选对了对应文件；30 条的 system 与对应文件逐字相同 |
| 4 | `python -m src.run ... --items data/holdout.jsonl --dry-run` | 报错“是保留集（holdout），默认不读”，退出码 2；加 `--holdout` 后正常（空文件） |
| 额外 | 本地假 hkust 接口（临时目录，不入库） | 500/429 会重试，429 遵守 Retry-After；一直失败的那条尝试 4 次后记为失败并继续下一条；截断记为失败、再跑会重调；跳过逻辑正确；请求用 `api-key` 头、没有 Authorization 头；回显的密钥被脱敏为 `***` |
| 5 | `python -m src.run --skill skills/general_v1.md --model gpt-6.1-sol --items data/examples.jsonl --repeats 1` | 2 条成功：输入 2872、输出 4063 tokens，约 $0.046。数据库 2 行，字段齐全 |
| 5 | 同一命令再跑一次 | 跳过 2 条 |
| 提交前 | `git status --ignored`、搜索密钥 | .env 被忽略，不在待提交列表中；仓库文件里搜不到密钥 |

### 待定

- 30 条的正式运行还没跑，等我确认费用后再跑。
