"""SQLite 读写。

两张表：
- runs：每次执行 run.py 一行，记命令参数和汇总数字。
- calls：每次调用被测模型一行（成功或失败都记）。status='ok' 的行算成功记录，用于断点续跑。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

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

CREATE INDEX IF NOT EXISTS idx_calls_resume
    ON calls (item_id, skill_sha256, model_name, repeat_idx, status);
"""

CALL_COLUMNS = [
    "run_id", "item_id", "items_file", "skill_file", "skill_sha256", "model_name",
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
    return conn


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


def has_success(conn, item_id: str, skill_sha256: str, model_name: str, repeat_idx: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM calls WHERE item_id=? AND skill_sha256=? AND model_name=? AND repeat_idx=?"
        " AND status='ok' LIMIT 1",
        (item_id, skill_sha256, model_name, repeat_idx),
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
