"""批量运行入口。

python -m src.run --skill skills/general_v1.md --model <config 里的模型名> --items data/items.jsonl --repeats 1
python -m src.run --skill original ...        # 每条按 course 自动选 skills/original/ 里对应的文件
python -m src.run ... --dry-run               # 只组装请求，打印第一条完整内容，不调用 API
python -m src.run --items data/holdout.jsonl --holdout ...   # 读保留集必须显式加 --holdout
"""

from __future__ import annotations

import argparse
import hashlib
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import db, providers
from .schema import expected_split, validate_file

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_DIR = ROOT / "skills" / "original"

# 只有这三个字段会进入发给被测模型的请求
REQUEST_FIELDS = ("reader_known", "material", "request")
# 泄漏检查时，判分文本短于这个长度的不查（太短容易和材料偶然重合）
_LEAK_MIN_LEN = 6


class UsageError(Exception):
    """命令参数或输入有问题，打印原因后以退出码 2 结束。"""


@dataclass
class Skill:
    path: Path      # 绝对路径
    rel: str        # 相对项目根目录的路径，存进数据库
    text: str
    sha256: str


@dataclass
class Prepared:
    item: dict
    skill: Skill
    system: str
    user: str


# ---------------- 组装 ----------------

def _rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p.resolve())


def load_skill(path: Path, cache: dict) -> Skill:
    path = path.resolve()
    if path not in cache:
        raw = path.read_bytes()
        cache[path] = Skill(path=path, rel=_rel(path), text=raw.decode("utf-8"),
                            sha256=hashlib.sha256(raw).hexdigest())
    return cache[path]


def original_skill_for(course: str) -> Path:
    """在 skills/original/ 里找文件名以 <课程号小写>_ 开头的那份。"""
    hits = sorted(ORIGINAL_DIR.glob(f"{course.lower()}_*.md"))
    if len(hits) != 1:
        raise UsageError(f"skills/original/ 里课程 {course} 对应的文件应恰好 1 份，实际 {len(hits)} 份：{[h.name for h in hits]}")
    return hits[0]


def _fmt_list(xs: list[str]) -> str:
    return "；".join(xs) if xs else "无"


def build_user_message(item: dict) -> str:
    """用户消息 = 三段，顺序固定：读者已经会什么 → 材料 → 请求。只读取 REQUEST_FIELDS。"""
    rk = item["reader_known"]
    return (
        "【读者已经会什么】\n"
        f"学过：{_fmt_list(rk['learned'])}\n"
        f"没学过：{_fmt_list(rk['not_learned'])}\n"
        "\n"
        "【材料】\n"
        f"{item['material']}\n"
        "\n"
        "【请求】\n"
        f"{item['request']}"
    )


def scoring_texts(item: dict) -> list[str]:
    """条目里只用于判分的文本，用来检查它们没有混进请求。"""
    out = list(item.get("knowledge_errors") or [])
    for q in item.get("gate_questions") or []:
        out += [q.get("text", ""), q.get("accept", ""), q.get("source_quote", "")]
    for s in item.get("recommended_steps") or []:
        out.append(s.get("text", ""))
    return [t for t in out if isinstance(t, str) and len(t.strip()) >= _LEAK_MIN_LEN]


def check_no_leak(item: dict, user: str) -> None:
    leaked = [t for t in scoring_texts(item) if t in user]
    if leaked:
        raise UsageError(f"条目 {item['id']} 的判分内容出现在了请求里，已停止：{leaked[0][:60]!r}")


def prepare(items: list[dict], skill_arg: str) -> list[Prepared]:
    cache: dict = {}
    fixed: Skill | None = None
    if skill_arg != "original":
        p = Path(skill_arg)
        if not p.is_file():
            raise UsageError(f"Skill 文件不存在：{skill_arg}")
        fixed = load_skill(p, cache)
    out = []
    for it in items:
        skill = fixed or load_skill(original_skill_for(it["course"]), cache)
        user = build_user_message(it)
        check_no_leak(it, user)
        out.append(Prepared(item=it, skill=skill, system=skill.text, user=user))
    return out


# ---------------- 配置 ----------------

def load_config(path: Path) -> dict:
    if not path.is_file():
        raise UsageError(f"配置文件不存在：{path}")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for k in ("providers", "models"):
        if not cfg.get(k):
            raise UsageError(f"{path} 缺少 {k}")
    return cfg


def find_model(cfg: dict, name: str) -> dict:
    for m in cfg["models"]:
        if m.get("name") == name:
            for k in ("provider", "model_id"):
                if not m.get(k):
                    raise UsageError(f"模型 {name} 缺少 {k}")
            if m["provider"] not in cfg["providers"]:
                raise UsageError(f"模型 {name} 的接口 {m['provider']!r} 没有在 providers 里配置")
            return m
    names = [m.get("name") for m in cfg["models"]]
    raise UsageError(f"config 里没有模型 {name!r}，可选：{names}")


def estimate_cost(model_cfg: dict, in_tok: int, out_tok: int) -> float | None:
    price = model_cfg.get("price_per_1m_tokens") or {}
    pi, po = price.get("input"), price.get("output")
    if pi is None or po is None:
        return None
    return in_tok / 1e6 * float(pi) + out_tok / 1e6 * float(po)


# ---------------- 主流程 ----------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args(argv):
    ap = argparse.ArgumentParser(prog="python -m src.run", description="批量运行讲解评测")
    ap.add_argument("--skill", required=True, help="Skill 文件路径，或 original（按 course 选 skills/original/ 里的文件）")
    ap.add_argument("--model", required=True, help="config.yaml 里 models[].name")
    ap.add_argument("--items", required=True, help="条目文件 .jsonl")
    ap.add_argument("--repeats", type=int, default=1, help="每条重复几次，默认 1")
    ap.add_argument("--holdout", action="store_true", help="允许读取保留集（holdout）")
    ap.add_argument("--dry-run", action="store_true", help="只组装请求并打印第一条，不调用 API")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"), help="配置文件，默认 config.yaml")
    return ap.parse_args(argv)


def print_dry_run(preps: list[Prepared], model_cfg: dict, cfg: dict) -> None:
    first = preps[0]
    bar = "=" * 72
    print(bar)
    print(f"第一条：{first.item['id']}  （Skill：{first.skill.rel}，sha256 {first.skill.sha256[:12]}）")
    print(f"模型：{model_cfg['name']}  接口：{model_cfg['provider']}  model_id：{model_cfg['model_id']}")
    print(f"将发送的参数：{providers.build_params(model_cfg, cfg)}")
    print(bar)
    print("[system]")
    print(first.system)
    print(bar)
    print("[user]")
    print(first.user)
    print(bar)
    print(f"全部 {len(preps)} 条的 Skill 选择：")
    for p in preps:
        print(f"  {p.item['id']:<24} {p.item['course']:<9} → {p.skill.rel}  ({p.skill.sha256[:12]})")
    print(f"判分内容泄漏检查：{len(preps)} 条全部通过（用户消息里没有知识错误清单、卡点问题、推荐步骤的文本）")
    print("dry-run：未调用 API，未写数据库。")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)
    try:
        return _main(args, argv)
    except UsageError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2


def _main(args, argv) -> int:
    items_path = Path(args.items)
    if args.repeats < 1:
        raise UsageError("--repeats 至少为 1")

    # 1. 保留集保护：在打开文件之前就检查
    if expected_split(items_path) == "holdout" and not args.holdout:
        raise UsageError(f"{args.items} 是保留集（holdout），默认不读。确实要跑，请显式加 --holdout")
    if not items_path.is_file():
        raise UsageError(f"条目文件不存在：{args.items}")

    # 2. 校验条目
    items, errors = validate_file(items_path)
    if errors:
        for lineno, iid, msg in errors:
            print(f"{args.items}:{lineno} [{iid}] {msg}", file=sys.stderr)
        raise UsageError(f"{args.items} 校验未通过（{len(errors)} 处错误），先运行 python -m src.schema {args.items}")
    if any(it["split"] == "holdout" for it in items) and not args.holdout:
        raise UsageError("条目里有 holdout，需显式加 --holdout")
    if not items:
        print(f"{args.items} 没有条目，无事可做。")
        return 0

    # 3. 配置、模型、组装请求
    cfg = load_config(Path(args.config))
    model_cfg = find_model(cfg, args.model)
    preps = prepare(items, args.skill)

    if args.dry_run:
        print_dry_run(preps, model_cfg, cfg)
        return 0

    # 4. 真实运行
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    try:
        providers.require_key(model_cfg["provider"], cfg)
    except RuntimeError as e:
        raise UsageError(str(e))

    db_path = Path((cfg.get("defaults") or {}).get("db_path") or "results/eval.db")
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    conn = db.connect(db_path)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)
    items_rel = _rel(items_path)
    db.start_run(conn, run_id, _now(), ["python", "-m", "src.run", *argv], args.skill,
                 model_cfg["name"], items_rel, args.repeats)
    print(f"run_id {run_id}｜模型 {model_cfg['name']}（{model_cfg['provider']}）｜{len(items)} 条 × {args.repeats} 次｜数据库 {_rel(db_path)}")

    n_ok = n_fail = n_skip = 0
    tok_in = tok_out = 0
    total = len(preps) * args.repeats
    k = 0
    try:
        for p in preps:
            for r in range(1, args.repeats + 1):
                k += 1
                head = f"[{k}/{total}] {p.item['id']} 第{r}次"
                if db.has_success(conn, p.item["id"], p.skill.sha256, model_cfg["name"], r):
                    n_skip += 1
                    print(f"{head} 跳过（已有成功记录）")
                    continue
                out = providers.call(model_cfg, cfg, p.system, p.user)
                status, error = ("ok", None) if out.ok else ("error", out.error)
                if out.ok and out.finish_reason == "length":
                    status, error = "error", "回答因长度上限被截断（finish_reason=length），不算成功记录"
                tok_in += out.input_tokens or 0
                tok_out += out.output_tokens or 0
                db.insert_call(conn, {
                    "run_id": run_id, "item_id": p.item["id"], "items_file": items_rel,
                    "skill_file": p.skill.rel, "skill_sha256": p.skill.sha256,
                    "model_name": model_cfg["name"], "provider": model_cfg["provider"],
                    "model_id": model_cfg["model_id"], "model_version": out.model_version,
                    "repeat_idx": r, "system_prompt": p.system, "user_message": p.user,
                    "params_used": {"sent": out.params_sent, "reported_by_api": out.params_reported},
                    "response_text": out.text, "finish_reason": out.finish_reason,
                    "input_tokens": out.input_tokens, "output_tokens": out.output_tokens,
                    "usage_raw": out.usage_raw, "latency_s": out.latency_s,
                    "attempts": out.attempts, "created_at": _now(),
                    "status": status, "error": error,
                })
                if status == "ok":
                    n_ok += 1
                    print(f"{head} 成功｜输入 {out.input_tokens} 输出 {out.output_tokens} tokens｜{out.latency_s:.1f}s｜{out.model_version}")
                else:
                    n_fail += 1
                    print(f"{head} 失败｜{error}")
    except KeyboardInterrupt:
        print("\n已中断；已完成的调用都已写入数据库，再次运行同一命令会跳过它们。")
    finally:
        db.finish_run(conn, run_id, _now(), n_ok, n_fail, n_skip, tok_in, tok_out)
        conn.close()

    cost = estimate_cost(model_cfg, tok_in, tok_out)
    cost_s = f"约 ${cost:.4f}" if cost is not None else "未估算（config 里没填 price_per_1m_tokens）"
    print("-" * 72)
    print(f"成功 {n_ok} 条，失败 {n_fail} 条，跳过 {n_skip} 条")
    print(f"总用量：输入 {tok_in} tokens，输出 {tok_out} tokens｜费用 {cost_s}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
