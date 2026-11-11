"""规则检查（不调模型）：每份讲解算篇幅，以及用到了哪些读者“没学过”的词。

只做字符串匹配，仅作参考，不参与判定。
python -m src.rules [--items data/items.jsonl]   # 给所有当前回答算一遍并入库（已有的覆盖）
python -m src.judge 运行时也会自动先算一遍。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import db


def check(response_text: str, item: dict) -> dict:
    text = response_text or ""
    hits = []
    for term in item["reader_known"]["not_learned"]:
        pos = text.find(term)
        if pos >= 0:
            hits.append({"term": term, "first_pos": pos})
    return {"char_count": len(text), "n_not_learned_hits": len(hits), "not_learned_hits": hits}


def update_all(conn, items_by_id: dict, items_file: str) -> int:
    """给 current_calls 里条目在 items_by_id 中的每份回答算规则检查，写入 rule_checks。返回行数。"""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    n = 0
    with conn:
        for r in conn.execute("SELECT id, item_id, response_text FROM current_calls").fetchall():
            item = items_by_id.get(r["item_id"])
            if item is None:
                continue
            db.upsert_rule_check(conn, {"call_id": r["id"], **check(r["response_text"], item),
                                        "items_file": items_file, "created_at": now})
            n += 1
    return n


def main(argv=None) -> int:
    from .judge import ROOT, load_items, db_path_from_config, UsageError
    from .run import load_config
    ap = argparse.ArgumentParser(prog="python -m src.rules", description="规则检查：篇幅、没学过的词")
    ap.add_argument("--items", default="data/items.jsonl")
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    args = ap.parse_args(argv)
    try:
        items_by_id, items_rel = load_items(Path(args.items), args.holdout)
        conn = db.connect(db_path_from_config(load_config(Path(args.config))))
    except UsageError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    n = update_all(conn, items_by_id, items_rel)
    print(f"规则检查：{n} 份回答已写入 rule_checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
