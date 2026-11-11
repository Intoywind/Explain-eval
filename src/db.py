"""SQLite 读写。

两张表：
- runs：每次执行 run.py 一行，记命令参数和汇总数字。
- calls：每次调用被测模型一行（成功或失败都记）。status='ok' 的行算成功记录，用于断点续跑。

断点续跑的键：（item_id、model_name、repeat_idx、request_sha256）。
request_sha256 见 request_hash()：Skill、材料、请求、读者设定、生成参数任何一处变了都会变；
判分清单不进请求，改它们不影响。
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path


def canonical_json(obj) -> str:
    """规范化 JSON：键排序、无多余空白、保留中文。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def request_hash(system: str, user: str, params: dict) -> str:
    """sha256(system prompt + user message + 调用参数的规范化 JSON)。
    三段之间用 NUL 字符（\x00）分隔，避免拼接边界产生歧义；参数是实际发出的参数（params_used.sent）。"""
    data = system + "\x00" + user + "\x00" + canonical_json(params)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    argv          TEXT NOT NULL,     -- 完整命令参数（JSON 列表）
    skill_arg     TEXT NOT NULL,
    model_name    TEXT NOT NULL,
    items_file    TEXT NOT NULL,
    repeats       INTEGER NOT NULL,
    n_ok          INTEGER,
    n_failed      INTEGER,
    n_skipped     INTEGER,
    input_tokens  INTEGER,
    output_tokens INTEGER
);

CREATE TABLE IF NOT EXISTS calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    item_id         TEXT NOT NULL,
    items_file      TEXT NOT NULL,
    skill_file      TEXT NOT NULL,   -- Skill 文件路径（相对项目根目录）
    skill_sha256    TEXT NOT NULL,   -- Skill 文件原始字节的 sha256
    request_sha256  TEXT,            -- 实际发出的请求的哈希，见 request_hash()；断点续跑用
    model_name      TEXT NOT NULL,   -- config.yaml 里的模型名
    provider        TEXT NOT NULL,
    model_id        TEXT NOT NULL,   -- 发给接口的模型名
    model_version   TEXT,            -- 接口返回的实际模型版本
    repeat_idx      INTEGER NOT NULL,-- 第几次重复，从 1 开始
    system_prompt   TEXT NOT NULL,
    user_message    TEXT NOT NULL,
    params_used     TEXT NOT NULL,   -- JSON：{"sent": 发出的参数, "reported_by_api": 接口回报的实际参数或 null}
    response_text   TEXT,
    finish_reason   TEXT,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    usage_raw       TEXT,            -- 接口返回的完整用量 JSON
    latency_s       REAL,            -- 最后一次尝试的耗时（秒）
    attempts        INTEGER,         -- 一共尝试了几次
    created_at      TEXT NOT NULL,   -- UTC 时间戳
    status          TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    error           TEXT
);

"""

JUDGE_SCHEMA = """
-- 当前回答：同一个（条目、被测模型、Skill 文件、第几次重复）有多条成功记录时取最新一条。
-- 旧请求参数下的成功记录（例如 examples 试跑留下的）不再参与裁判、盲打和报告。
CREATE VIEW IF NOT EXISTS current_calls AS
SELECT c.* FROM calls c
WHERE c.status = 'ok' AND c.id = (
    SELECT max(c2.id) FROM calls c2
    WHERE c2.status = 'ok' AND c2.item_id = c.item_id AND c2.model_name = c.model_name
      AND c2.skill_file = c.skill_file AND c2.repeat_idx = c.repeat_idx);

CREATE TABLE IF NOT EXISTS judge_runs (
    judge_run_id     TEXT PRIMARY KEY,
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    argv             TEXT NOT NULL,
    judge_model_name TEXT NOT NULL,
    prompt_file      TEXT NOT NULL,
    prompt_sha256    TEXT NOT NULL,
    n_ok INTEGER, n_failed INTEGER, n_skipped INTEGER,
    input_tokens INTEGER, output_tokens INTEGER
);

-- 每次裁判一行。status：ok = 计分；error = 调用或格式失败；needs_review = 重判后证据仍不合格
-- （知识错误没有对得上清单的 which 和有效引句，或答上/踩中却没有有效引句），只存原始输出和原因，不计分、不进统计。
CREATE TABLE IF NOT EXISTS judgments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    judge_run_id        TEXT NOT NULL REFERENCES judge_runs(judge_run_id),
    call_id             INTEGER NOT NULL REFERENCES calls(id),   -- 被评的回答
    item_id             TEXT NOT NULL,
    judge_model_name    TEXT NOT NULL,
    judge_provider      TEXT NOT NULL,
    judge_model_id      TEXT NOT NULL,
    judge_model_version TEXT,
    prompt_file         TEXT NOT NULL,
    prompt_sha256       TEXT NOT NULL,     -- 裁判 prompt 文件原始字节的 sha256
    rubric_sha256       TEXT NOT NULL,     -- 条目 gate_questions + recommended_steps（+ knowledge_errors）的哈希
    request_sha256      TEXT NOT NULL,     -- 裁判请求（system + user + 参数）的哈希；断点续跑用
    user_message        TEXT NOT NULL,     -- 发给裁判的 USER 段全文
    params_used         TEXT NOT NULL,     -- JSON：{"sent", "reported_by_api"}
    raw_output          TEXT,              -- 最后一次尝试的原始输出
    parsed_json         TEXT,              -- 解析后的 JSON，每条引句附校验结果
    flags               TEXT,              -- JSON：quote_invalid 的问题和步骤 id、各部分作废引句数
    knowledge_pass      INTEGER,           -- 第一档：1 通过 / 0 不通过
    incomplete          INTEGER,           -- 没答全：1 / 0（不影响记分，单独统计）
    incomplete_missing  TEXT,              -- JSON 列表
    gate_num            INTEGER,           -- 第二档：卡点分分子（知识不通过时为 0）
    gate_den            INTEGER,
    step_num            INTEGER,           -- 第三档：步骤分分子（知识不通过时为 0）
    step_den            INTEGER,
    gate_all            INTEGER,           -- 卡点全答上：知识通过且 gate_num = gate_den
    n_gaps              INTEGER,           -- gaps 总数（含引句作废的）
    n_gaps_blocking     INTEGER,           -- 引句有效、severity=读者没法往下读 的 gaps 数
    n_redundancy        INTEGER,           -- 引句有效的 redundancy 数
    n_extra_steps       INTEGER,
    finish_reason       TEXT,
    input_tokens        INTEGER,           -- 所有尝试累计
    output_tokens       INTEGER,
    usage_raw           TEXT,              -- 最后一次尝试的原始用量
    latency_s           REAL,              -- 所有尝试累计
    attempts            INTEGER,           -- 一共调用了几次裁判（含格式不对的重试）
    created_at          TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('ok', 'error', 'needs_review')),
    error               TEXT               -- error：失败原因；needs_review：不合格的原因
);
CREATE INDEX IF NOT EXISTS idx_judgments_resume ON judgments (call_id, judge_model_name, request_sha256, status);

-- 逐问题：answered 是引句校验后的判断；answered_raw 是裁判原话
CREATE TABLE IF NOT EXISTS judge_gate (
    judgment_id   INTEGER NOT NULL REFERENCES judgments(id),
    call_id       INTEGER NOT NULL,
    item_id       TEXT NOT NULL,
    question_id   TEXT NOT NULL,
    answered_raw  INTEGER NOT NULL,
    answered      INTEGER NOT NULL,
    quote_invalid INTEGER NOT NULL,
    quotes        TEXT NOT NULL,     -- JSON 列表
    quotes_valid  TEXT NOT NULL,     -- JSON 列表，与 quotes 一一对应
    reason        TEXT
);

-- 逐步骤：done 是引句校验后的判断
CREATE TABLE IF NOT EXISTS judge_steps (
    judgment_id   INTEGER NOT NULL REFERENCES judgments(id),
    call_id       INTEGER NOT NULL,
    item_id       TEXT NOT NULL,
    step_id       TEXT NOT NULL,
    done_raw      INTEGER NOT NULL,
    done          INTEGER NOT NULL,
    quote_invalid INTEGER NOT NULL,
    quotes        TEXT NOT NULL,
    quotes_valid  TEXT NOT NULL,
    reason        TEXT
);

CREATE TABLE IF NOT EXISTS judge_extra_steps (
    judgment_id INTEGER NOT NULL REFERENCES judgments(id),
    call_id     INTEGER NOT NULL,
    item_id     TEXT NOT NULL,
    quote       TEXT NOT NULL,
    what        TEXT,
    quote_valid INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS judge_gaps (
    judgment_id INTEGER NOT NULL REFERENCES judgments(id),
    call_id     INTEGER NOT NULL,
    item_id     TEXT NOT NULL,
    quote       TEXT NOT NULL,
    subtype     TEXT NOT NULL,
    severity    TEXT NOT NULL,
    why         TEXT,
    quote_valid INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS judge_redundancy (
    judgment_id INTEGER NOT NULL REFERENCES judgments(id),
    call_id     INTEGER NOT NULL,
    item_id     TEXT NOT NULL,
    quote       TEXT NOT NULL,
    what        TEXT,
    quote_valid INTEGER NOT NULL
);

-- 规则检查（不调模型），每份回答一行
CREATE TABLE IF NOT EXISTS rule_checks (
    call_id            INTEGER PRIMARY KEY REFERENCES calls(id),
    char_count         INTEGER NOT NULL,  -- 讲解全文字符数
    n_not_learned_hits INTEGER NOT NULL,  -- 用到了几个 reader_known.not_learned 里的词
    not_learned_hits   TEXT NOT NULL,     -- JSON：[{"term", "first_pos"}]，first_pos 是第一次出现的字符位置（从 0 起）
    items_file         TEXT NOT NULL,
    created_at         TEXT NOT NULL
);

-- 已知样本检查（--known）的记录，不进入任何统计
CREATE TABLE IF NOT EXISTS known_judgments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    judge_run_id     TEXT NOT NULL,
    case_idx         INTEGER NOT NULL,   -- known_cases.jsonl 第几行（从 1 起）
    item_id          TEXT NOT NULL,
    text_sha256      TEXT NOT NULL,
    note             TEXT,
    judge_model_name TEXT NOT NULL,
    judge_model_version TEXT,
    prompt_sha256    TEXT NOT NULL,
    rubric_sha256    TEXT NOT NULL,
    params_used      TEXT NOT NULL,
    raw_output       TEXT,
    parsed_json      TEXT,
    flags            TEXT,
    expected_missing TEXT NOT NULL,      -- JSON 列表
    actual_missing   TEXT,               -- JSON 列表：校验后没答上的问题 id
    input_tokens INTEGER, output_tokens INTEGER,
    created_at       TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('ok', 'error', 'needs_review')),
    error            TEXT
);

-- 裁判验收样例（tests/judge_fixtures/）的裁判结果：只用来验收裁判，不进入任何评分统计
CREATE TABLE IF NOT EXISTS fixture_judgments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    judge_run_id     TEXT NOT NULL,
    fixture_id       TEXT NOT NULL,      -- A1 … E2
    item_id          TEXT NOT NULL,
    source_call_id   INTEGER,            -- 样例由哪份真实回答改成
    text_sha256      TEXT NOT NULL,
    judge_model_name TEXT NOT NULL,
    judge_model_version TEXT,
    prompt_file      TEXT NOT NULL,
    prompt_sha256    TEXT NOT NULL,
    rubric_sha256    TEXT NOT NULL,
    request_sha256   TEXT NOT NULL,
    params_used      TEXT NOT NULL,
    raw_output       TEXT,
    parsed_json      TEXT,
    flags            TEXT,               -- 含 rejudge_history
    expect           TEXT NOT NULL,      -- manifest 里的预期
    actual           TEXT,               -- 与预期对应的实际值
    passed           INTEGER,            -- 1 符合预期 / 0 不符合 / NULL 没有可比的结果
    input_tokens INTEGER, output_tokens INTEGER, attempts INTEGER, latency_s REAL,
    created_at       TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('ok', 'error', 'needs_review')),
    error            TEXT
);
"""

INDEX_SQL = """
DROP INDEX IF EXISTS idx_calls_resume;
CREATE INDEX IF NOT EXISTS idx_calls_resume_v2
    ON calls (item_id, model_name, repeat_idx, request_sha256, status);
"""

CALL_COLUMNS = [
    "run_id", "item_id", "items_file", "skill_file", "skill_sha256", "request_sha256", "model_name",
    "provider", "model_id", "model_version", "repeat_idx", "system_prompt",
    "user_message", "params_used", "response_text", "finish_reason",
    "input_tokens", "output_tokens", "usage_raw", "latency_s", "attempts",
    "created_at", "status", "error",
]


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    migrate(conn)
    conn.executescript(INDEX_SQL)
    conn.executescript(JUDGE_SCHEMA)
    migrate_judge(conn)
    return conn


def _table_sql(conn, name: str) -> str | None:
    r = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return r[0] if r else None


def _ddl_from_schema(name: str) -> str:
    m = re.search(rf"CREATE TABLE IF NOT EXISTS {name} \(.*?\n\);", JUDGE_SCHEMA, flags=re.S)
    return m.group(0)


def migrate_judge(conn) -> None:
    """旧库升级：judgments / known_judgments 的 status 约束加上 needs_review（SQLite 改不了约束，只能重建表）；
    judge_runs 加 n_needs_review 列。"""
    for name in ("judgments", "known_judgments"):
        old = _table_sql(conn, name)
        if old is None or "needs_review" in old:
            continue
        ddl = _ddl_from_schema(name).replace(f"CREATE TABLE IF NOT EXISTS {name} (", f"CREATE TABLE {name}__new (", 1)
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({name})")]
        with conn:
            conn.execute(ddl)
            conn.execute(f"INSERT INTO {name}__new ({', '.join(cols)}) SELECT {', '.join(cols)} FROM {name}")
            conn.execute(f"DROP TABLE {name}")
            conn.execute(f"ALTER TABLE {name}__new RENAME TO {name}")
    conn.executescript(
        "CREATE INDEX IF NOT EXISTS idx_judgments_resume ON judgments (call_id, judge_model_name, request_sha256, status);")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(judge_runs)")}
    if "n_needs_review" not in cols:
        with conn:
            conn.execute("ALTER TABLE judge_runs ADD COLUMN n_needs_review INTEGER")


def connect_readonly(path: str | Path) -> sqlite3.Connection | None:
    """只读打开（dry-run 预览用）。库不存在或还没迁移过时返回 None。"""
    path = Path(path)
    if not path.is_file():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(calls)")}
    if "request_sha256" not in cols:
        conn.close()
        return None
    return conn


def migrate(conn) -> int:
    """旧库升级：没有 request_sha256 列就加上，并用存着的 system_prompt、user_message、
    params_used.sent 给空值行补算。返回补算的行数。"""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(calls)")}
    if "request_sha256" not in cols:
        conn.execute("ALTER TABLE calls ADD COLUMN request_sha256 TEXT")
    rows = conn.execute(
        "SELECT id, system_prompt, user_message, params_used FROM calls WHERE request_sha256 IS NULL"
    ).fetchall()
    for r in rows:
        sent = (json.loads(r["params_used"]) or {}).get("sent") or {}
        conn.execute("UPDATE calls SET request_sha256=? WHERE id=?",
                     (request_hash(r["system_prompt"], r["user_message"], sent), r["id"]))
    conn.commit()
    return len(rows)


def start_run(conn, run_id: str, started_at: str, argv: list[str], skill_arg: str,
              model_name: str, items_file: str, repeats: int) -> None:
    conn.execute(
        "INSERT INTO runs (run_id, started_at, argv, skill_arg, model_name, items_file, repeats)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, started_at, json.dumps(argv, ensure_ascii=False), skill_arg, model_name, items_file, repeats),
    )
    conn.commit()


def finish_run(conn, run_id: str, finished_at: str, n_ok: int, n_failed: int, n_skipped: int,
               input_tokens: int, output_tokens: int) -> None:
    conn.execute(
        "UPDATE runs SET finished_at=?, n_ok=?, n_failed=?, n_skipped=?, input_tokens=?, output_tokens=?"
        " WHERE run_id=?",
        (finished_at, n_ok, n_failed, n_skipped, input_tokens, output_tokens, run_id),
    )
    conn.commit()


def has_success(conn, item_id: str, model_name: str, repeat_idx: int, request_sha256: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM calls WHERE item_id=? AND model_name=? AND repeat_idx=? AND request_sha256=?"
        " AND status='ok' LIMIT 1",
        (item_id, model_name, repeat_idx, request_sha256),
    ).fetchone()
    return row is not None


def insert_call(conn, row: dict) -> None:
    missing = [c for c in CALL_COLUMNS if c not in row]
    if missing:
        raise ValueError(f"insert_call 缺少列：{missing}")
    values = []
    for c in CALL_COLUMNS:
        v = row[c]
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        values.append(v)
    conn.execute(
        f"INSERT INTO calls ({', '.join(CALL_COLUMNS)}) VALUES ({', '.join('?' * len(CALL_COLUMNS))})",
        values,
    )
    conn.commit()  # 每条立即提交，中途中断也不丢已完成的结果


# ---------------- 裁判 ----------------

def _dumps(v):
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v


def _insert(conn, table: str, row: dict) -> int:
    cols = list(row)
    cur = conn.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [_dumps(row[c]) for c in cols],
    )
    return cur.lastrowid


def has_judgment(conn, call_id: int, judge_model_name: str, request_sha256: str) -> bool:
    """已有 ok 或 needs_review（待人工复核，不自动再判）的记录就算评过。"""
    row = conn.execute(
        "SELECT 1 FROM judgments WHERE call_id=? AND judge_model_name=? AND request_sha256=?"
        " AND status IN ('ok', 'needs_review') LIMIT 1",
        (call_id, judge_model_name, request_sha256),
    ).fetchone()
    return row is not None


def insert_judgment(conn, row: dict, gate: list[dict], steps: list[dict],
                    extra_steps: list[dict], gaps: list[dict], redundancy: list[dict]) -> int:
    """一份裁判记录和它的逐项记录在同一个事务里写入。"""
    with conn:
        jid = _insert(conn, "judgments", row)
        base = {"judgment_id": jid, "call_id": row["call_id"], "item_id": row["item_id"]}
        for table, rows in (("judge_gate", gate), ("judge_steps", steps), ("judge_extra_steps", extra_steps),
                            ("judge_gaps", gaps), ("judge_redundancy", redundancy)):
            for r in rows:
                _insert(conn, table, {**base, **r})
    return jid


def start_judge_run(conn, row: dict) -> None:
    with conn:
        _insert(conn, "judge_runs", row)


def finish_judge_run(conn, judge_run_id: str, **fields) -> None:
    sets = ", ".join(f"{k}=?" for k in fields)
    with conn:
        conn.execute(f"UPDATE judge_runs SET {sets} WHERE judge_run_id=?", [*fields.values(), judge_run_id])


def upsert_rule_check(conn, row: dict) -> None:
    cols = list(row)
    conn.execute(
        f"INSERT OR REPLACE INTO rule_checks ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [_dumps(row[c]) for c in cols],
    )


def insert_known(conn, row: dict) -> None:
    with conn:
        _insert(conn, "known_judgments", row)


def insert_fixture(conn, row: dict) -> None:
    with conn:
        _insert(conn, "fixture_judgments", row)
