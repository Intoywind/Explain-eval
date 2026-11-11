"""评测条目的字段定义和校验。

用法：python -m src.schema data/items.jsonl [更多文件 ...]
每条错误打印“文件:行号 [id] 原因”；全部通过退出码 0，有错误退出码 1。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

COURSES = {"COMP2711", "IEDA1280", "ECON1221"}
SUBTYPES = {"术语未先定义", "切换处漏连接", "公式未接含义", "前提未交代",
            "长请求",   # 长请求：几条短条目拼成的一条（drafts/build_items_long.py），不是一种跳步类型
            "长题"}     # 长题：正式测试集里的长条目（drafts/build_items_long_test.py），不是一种跳步类型
DIFFICULTIES = {"低", "中", "高"}
SPLITS = {"dev", "holdout", "test"}
# 合并评测集（data/items_merged.jsonl）多出来的字段；只用于计分，可选，出现了就校验
TIERS = {"短题": "dev", "长题": "test"}          # tier → 合并文件里该条应有的 split
KINDS = {"短题", "做题类", "概念理解类"}
ZERO_RULES = {"整份清零", "只清讲错的那一部分"}
OPTIONAL_FIELDS = ["tier", "kind", "points", "zero_rule", "parts"]
SOURCE_LEVELS = {"原话", "报告定位", "推测"}

FIELDS = [
    "id", "course", "knowledge_point", "subtype", "source", "difficulty",
    "reader_known", "request", "material", "knowledge_errors",
    "gate_questions", "recommended_steps", "split",
]
GATE_FIELDS = ["id", "text", "accept", "source_level", "source_ref", "source_quote"]
GATE_MAY_BE_EMPTY = {"source_quote"}
STEP_FIELDS = ["id", "text"]

# 只用于判分和分析、绝对不能发给被测模型的字段
SCORING_FIELDS = ["knowledge_errors", "gate_questions", "recommended_steps", "source", "subtype", "difficulty"]

# source 必须是 new、以 real: 开头，或 merged:<条目 id>,<条目 id>,…（长请求，由这些短条目拼成）（错误）；
# real: 后面不是 <报告名>#<条目号> 的只给提醒（items.jsonl 里有 real:报告名C08 这种写法）
# notes:<讲义或笔记名> 是长题的出处写法
SOURCE_RE = re.compile(r"^(new|real:.+|notes:.+|merged:[^,\s]+(,[^,\s]+)*)$")
SOURCE_STRICT_RE = re.compile(r"^(new|real:[^#\s][^#]*#.+|notes:.+|merged:[^,\s]+(,[^,\s]+)*)$")


def expected_split(path: str | Path) -> str:
    """按文件名决定该文件里的条目应属哪个 split：文件名含 holdout 的为 holdout；含 merged 的是合并评测集，
    按每条的 tier 决定（返回 "mixed"）；含 _test 的为 test；其余为 dev。"""
    name = Path(path).name
    if "holdout" in name:
        return "holdout"
    if "merged" in name:
        return "mixed"
    if "_test" in name:
        return "test"
    return "dev"


def _check_merged_extra(obj: dict, errs: list[str]) -> None:
    tier, kind, pts, zr, parts = (obj.get(k) for k in OPTIONAL_FIELDS)
    if "tier" in obj and tier not in TIERS:
        errs.append(f"tier 非法：{tier!r}，应为 {'/'.join(TIERS)}")
    if "kind" in obj and kind not in KINDS:
        errs.append(f"kind 非法：{kind!r}，应为 {'/'.join(sorted(KINDS))}")
    if "zero_rule" in obj and zr not in ZERO_RULES:
        errs.append(f"zero_rule 非法：{zr!r}")
    if "points" in obj:
        need = ("gate_each", "gate_total", "step_each", "step_total")
        if not isinstance(pts, dict) or any(not isinstance(pts.get(k), int) for k in need):
            errs.append("points 应为 {gate_each, gate_total, step_each, step_total}，都是整数")
        else:
            nq, ns = len(obj.get("gate_questions") or []), len(obj.get("recommended_steps") or [])
            if pts["gate_total"] != pts["gate_each"] * nq:
                errs.append(f"points.gate_total {pts['gate_total']} ≠ gate_each × 卡点数 {pts['gate_each']}×{nq}")
            if pts["step_total"] != pts["step_each"] * ns:
                errs.append(f"points.step_total {pts['step_total']} ≠ step_each × 步骤数 {pts['step_each']}×{ns}")
    if zr == "只清讲错的那一部分":
        if not isinstance(parts, dict) or not all(k in parts for k in ("gates", "steps", "knowledge_errors")):
            errs.append("zero_rule 为“只清讲错的那一部分”时 parts 应为 {gates, steps, knowledge_errors}")
        else:
            qids = {q.get("id") for q in obj.get("gate_questions") or []}
            sids = {x.get("id") for x in obj.get("recommended_steps") or []}
            if set(parts["gates"]) != qids:
                errs.append("parts.gates 的键和卡点 id 对不上")
            if any(v is None for v in parts["gates"].values()):
                errs.append("parts.gates 不能有 null（每个卡点都要属于一个部分）")
            if set(parts["steps"]) != sids:
                errs.append("parts.steps 的键和步骤 id 对不上")
            ke = parts["knowledge_errors"]
            if not isinstance(ke, list) or len(ke) != len(obj.get("knowledge_errors") or []):
                errs.append("parts.knowledge_errors 应与 knowledge_errors 等长（每条知识错误属于第几部分）")
    elif "parts" in obj and parts is not None:
        errs.append("zero_rule 为整份清零时 parts 应为 null")


def _nonempty_str(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _check_str_list(name: str, v, errs: list[str], min_len: int = 0) -> None:
    if not isinstance(v, list):
        errs.append(f"{name} 应为列表，实际是 {type(v).__name__}")
        return
    if len(v) < min_len:
        errs.append(f"{name} 至少 {min_len} 项，实际 {len(v)} 项")
    for i, x in enumerate(v):
        if not _nonempty_str(x):
            errs.append(f"{name}[{i}] 应为非空字符串")


def _check_obj_list(name: str, v, fields: list[str], may_be_empty: set[str],
                    errs: list[str], extra=None) -> None:
    if not isinstance(v, list):
        errs.append(f"{name} 应为列表，实际是 {type(v).__name__}")
        return
    if len(v) < 1:
        errs.append(f"{name} 至少 1 项，实际 0 项")
    seen: dict[str, int] = {}
    for i, x in enumerate(v):
        where = f"{name}[{i}]"
        if not isinstance(x, dict):
            errs.append(f"{where} 应为对象")
            continue
        missing = [f for f in fields if f not in x]
        if missing:
            errs.append(f"{where} 缺少字段 {', '.join(missing)}")
        unknown = [f for f in x if f not in fields]
        if unknown:
            errs.append(f"{where} 有未定义字段 {', '.join(unknown)}")
        for f in fields:
            if f not in x:
                continue
            val = x[f]
            if not isinstance(val, str):
                errs.append(f"{where}.{f} 应为字符串")
            elif f not in may_be_empty and not val.strip():
                errs.append(f"{where}.{f} 不能为空")
        qid = x.get("id")
        if isinstance(qid, str) and qid:
            if qid in seen:
                errs.append(f"{where}.id 重复：{qid!r} 已在 {name}[{seen[qid]}] 出现")
            else:
                seen[qid] = i
        if extra:
            extra(where, x, errs)


def _check_gate_extra(where: str, x: dict, errs: list[str]) -> None:
    lvl = x.get("source_level")
    if isinstance(lvl, str) and lvl and lvl not in SOURCE_LEVELS:
        errs.append(f"{where}.source_level 非法：{lvl!r}，应为 {'/'.join(sorted(SOURCE_LEVELS))}")


def item_warnings(obj) -> list[str]:
    """不影响通过、但值得看一眼的问题。"""
    warns: list[str] = []
    src = obj.get("source") if isinstance(obj, dict) else None
    if isinstance(src, str) and SOURCE_RE.match(src) and not SOURCE_STRICT_RE.match(src):
        warns.append(f"source 未按 real:<报告名>#<条目号> 写：{src!r}")
    return warns


def validate_item(obj, split: str) -> list[str]:
    """校验单条条目（不含跨条目的 id 唯一性），返回错误原因列表。"""
    errs: list[str] = []
    if not isinstance(obj, dict):
        return [f"每行应是一个 JSON 对象，实际是 {type(obj).__name__}"]

    missing = [f for f in FIELDS if f not in obj]
    if missing:
        errs.append(f"缺少字段 {', '.join(missing)}")
    unknown = [f for f in obj if f not in FIELDS and f not in OPTIONAL_FIELDS]
    if unknown:
        errs.append(f"有未定义字段 {', '.join(unknown)}")

    for f in ("id", "knowledge_point", "request", "material", "source"):
        if f in obj and not _nonempty_str(obj[f]):
            errs.append(f"{f} 应为非空字符串")

    for f, allowed in (("course", COURSES), ("subtype", SUBTYPES),
                       ("difficulty", DIFFICULTIES), ("split", SPLITS)):
        if f in obj and obj[f] not in allowed:
            errs.append(f"{f} 非法：{obj[f]!r}，应为 {'/'.join(sorted(allowed))}")

    if _nonempty_str(obj.get("source")) and not SOURCE_RE.match(obj["source"]):
        errs.append(f"source 格式不对：{obj['source']!r}，应为 new、以 real: 开头或 merged:<条目 id>,…")

    if split == "mixed":   # 合并评测集：短题应为 dev，长题应为 test
        if obj.get("tier") not in TIERS:
            errs.append("合并评测集里每条都要有 tier（短题 / 长题）")
        elif obj.get("split") != TIERS[obj["tier"]]:
            errs.append(f"split 为 {obj.get('split')!r}，tier 为 {obj['tier']} 的条目应为 {TIERS[obj['tier']]!r}")
    elif "split" in obj and obj["split"] in SPLITS and obj["split"] != split:
        errs.append(f"split 为 {obj['split']!r}，与所在文件不一致（该文件应为 {split!r}）")
    _check_merged_extra(obj, errs)

    if "reader_known" in obj:
        rk = obj["reader_known"]
        if not isinstance(rk, dict):
            errs.append("reader_known 应为对象 {learned: [...], not_learned: [...]}")
        else:
            for k in ("learned", "not_learned"):
                if k not in rk:
                    errs.append(f"reader_known 缺少 {k}")
                else:
                    _check_str_list(f"reader_known.{k}", rk[k], errs)
            unknown_rk = [k for k in rk if k not in ("learned", "not_learned")]
            if unknown_rk:
                errs.append(f"reader_known 有未定义字段 {', '.join(unknown_rk)}")

    if "knowledge_errors" in obj:
        _check_str_list("knowledge_errors", obj["knowledge_errors"], errs, min_len=1)
    if "gate_questions" in obj:
        _check_obj_list("gate_questions", obj["gate_questions"], GATE_FIELDS,
                        GATE_MAY_BE_EMPTY, errs, extra=_check_gate_extra)
    if "recommended_steps" in obj:
        _check_obj_list("recommended_steps", obj["recommended_steps"], STEP_FIELDS, set(), errs)
    return errs


def validate_file(path: str | Path, warnings: list | None = None) -> tuple[list[dict], list[tuple[int, str, str]]]:
    """校验一个 jsonl 文件。返回 (成功解析的条目, [(行号, id, 原因), ...])。空文件算通过。
    传入 warnings 列表时，把提醒以 (行号, id, 原因) 追加进去。"""
    path = Path(path)
    split = expected_split(path)
    items: list[dict] = []
    errors: list[tuple[int, str, str]] = []
    first_line_of_id: dict[str, int] = {}

    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # 文件末尾的换行
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            errors.append((lineno, "-", "空行"))
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append((lineno, "-", f"不是合法 JSON：{e.msg}（第 {e.colno} 列）"))
            continue
        iid = obj.get("id") if isinstance(obj, dict) and isinstance(obj.get("id"), str) else "-"
        for msg in validate_item(obj, split):
            errors.append((lineno, iid, msg))
        if warnings is not None:
            for msg in item_warnings(obj):
                warnings.append((lineno, iid, msg))
        if iid != "-" and iid:
            if iid in first_line_of_id:
                errors.append((lineno, iid, f"id 重复：已在第 {first_line_of_id[iid]} 行出现"))
            else:
                first_line_of_id[iid] = lineno
        if isinstance(obj, dict):
            items.append(obj)
    return items, errors


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("用法：python -m src.schema <文件.jsonl> [...]", file=sys.stderr)
        return 2
    bad = False
    for p in argv:
        if not Path(p).is_file():
            print(f"{p}: 文件不存在", file=sys.stderr)
            bad = True
            continue
        warns: list = []
        items, errors = validate_file(p, warns)
        for lineno, iid, msg in warns:
            print(f"{p}:{lineno} [{iid}] 提醒：{msg}")
        if errors:
            bad = True
            for lineno, iid, msg in errors:
                print(f"{p}:{lineno} [{iid}] {msg}")
            n_bad = len({e[0] for e in errors})
            print(f"{p}: 共 {len(items)} 条，{n_bad} 行有错误，{len(errors)} 处错误")
        else:
            print(f"{p}: 共 {len(items)} 条，全部通过（split 应为 {expected_split(p)}）")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
