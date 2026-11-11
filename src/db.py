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
    return conn


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
