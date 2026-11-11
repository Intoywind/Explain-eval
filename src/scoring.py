"""裁判输出的解析、引句校验和三档记分。全是纯函数，不碰数据库和网络，便于单元测试。

- parse_judge_output(raw, item, response_text)：解析裁判返回的文本，检查结构；
  结构不对抛 JudgeFormatError（调用方据此重试）。返回 Parsed，里面带好每条引句的校验结果，
  以及 problems：证据不合格的地方（见 evidence_problems）。
- problems 不为空时，调用方让裁判重判同一份回答（最多 2 次）；仍不合格就整份标 needs_review，不计分。
  理由：引句核对不上是裁判抄错了原文，不能把这个错算到被测回答头上。
- score(parsed)：按三档规则算分，返回 Scores。分数只由代码算，裁判不直接给分。
  problems 不为空的结果不能计分（抛 ValueError）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

GAP_SUBTYPES = ("术语未先定义", "切换处漏连接", "公式未接含义", "前提未交代")
GAP_SEVERITIES = ("读者没法往下读", "只是不顺")
SEVERITY_BLOCKING = "读者没法往下读"

TOP_KEYS = ("knowledge_error", "incomplete", "gate", "steps", "extra_steps", "gaps", "redundancy")


class JudgeFormatError(ValueError):
    """裁判输出不是合法 JSON、缺字段、类型不对、或 gate/steps 的 id 和条目对不上。"""


# ---------------- 引句校验 ----------------

_WS = re.compile(r"\s+")


def normalize(s: str) -> str:
    """去掉首尾空白，把连续空白压成一个空格。"""
    return _WS.sub(" ", s).strip()


def quote_ok(quote, response_norm: str) -> bool:
    """规范化后非空，且是（同样规范化过的）讲解原文的子串。"""
    if not isinstance(quote, str):
        return False
    q = normalize(quote)
    return q != "" and q in response_norm


# ---------------- 解析 ----------------

@dataclass
class GateJudgment:
    id: str
    answered_raw: bool          # 裁判原始判断
    quotes: list[str]
    quotes_valid: list[bool]
    reason: str

    @property
    def quote_invalid(self) -> bool:
        """裁判说答上了，但没有一条引句通过校验（这种结果会进重判，不会被计分）。"""
        return self.answered_raw and not any(self.quotes_valid)

    @property
    def answered(self) -> bool:
        """答上了且至少一条引句通过。能计分的结果里它和 answered_raw 相同。"""
        return self.answered_raw and any(self.quotes_valid)


@dataclass
class StepJudgment:
    id: str
    done_raw: bool
    quotes: list[str]
    quotes_valid: list[bool]
    reason: str

    @property
    def quote_invalid(self) -> bool:
        return self.done_raw and not any(self.quotes_valid)

    @property
    def done(self) -> bool:
        return self.done_raw and any(self.quotes_valid)


@dataclass
class Parsed:
    data: dict                              # 裁判输出的 JSON（原样）
    knowledge_found: bool
    knowledge_which: list[str]
    knowledge_which_valid: list[bool]       # which 每一条能否对上条目的 knowledge_errors
    knowledge_quotes_valid: list[bool]
    incomplete_found: bool
    incomplete_missing: list[str]
    gate: list[GateJudgment]                # 按条目里 gate_questions 的顺序
    steps: list[StepJudgment]               # 按条目里 recommended_steps 的顺序
    extra_steps: list[dict] = field(default_factory=list)   # 每项加 quote_valid
    gaps: list[dict] = field(default_factory=list)          # 每项加 quote_valid
    redundancy: list[dict] = field(default_factory=list)    # 每项加 quote_valid
    problems: list[str] = field(default_factory=list)       # 证据不合格的地方；不为空就要重判

    def flags(self) -> dict:
        """校验标记汇总，存进数据库。"""
        return {
            "problems": list(self.problems),
            "gate_quote_invalid": [g.id for g in self.gate if g.quote_invalid],
            "step_quote_invalid": [s.id for s in self.steps if s.quote_invalid],
            "knowledge_quote_invalid": self.knowledge_found and not any(self.knowledge_quotes_valid),
            "invalid_quotes": {
                "gate": sum(not v for g in self.gate for v in g.quotes_valid),
                "steps": sum(not v for s in self.steps for v in s.quotes_valid),
                "knowledge_error": sum(not v for v in self.knowledge_quotes_valid),
                "extra_steps": sum(not x["quote_valid"] for x in self.extra_steps),
                "gaps": sum(not x["quote_valid"] for x in self.gaps),
                "redundancy": sum(not x["quote_valid"] for x in self.redundancy),
            },
        }


def _extract_json_text(raw: str) -> str:
    """prompt 要求不用代码块包裹；万一包了，剥掉一层 ```json ... ```。"""
    s = raw.strip()
    m = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", s, flags=re.S)
    return m.group(1) if m else s


def _req(obj: dict, key: str, typ, where: str):
    if not isinstance(obj, dict) or key not in obj:
        raise JudgeFormatError(f"{where} 缺少字段 {key}")
    v = obj[key]
    if typ is bool:
        ok = isinstance(v, bool)
    elif typ is list:
        ok = isinstance(v, list)
    elif typ is str:
        ok = isinstance(v, str)
    else:
        ok = isinstance(v, typ)
    if not ok:
        raise JudgeFormatError(f"{where}.{key} 应为 {typ.__name__}，实际是 {type(v).__name__}")
    return v


def _str_list(obj: dict, key: str, where: str) -> list[str]:
    v = _req(obj, key, list, where)
    for i, x in enumerate(v):
        if not isinstance(x, str):
            raise JudgeFormatError(f"{where}.{key}[{i}] 应为字符串")
    return v


def _check_ids(got: list[str], want: list[str], name: str) -> None:
    if got != want:
        if sorted(got) == sorted(want):
            return  # 顺序不同但一一对应，可以接受
        raise JudgeFormatError(f"{name} 的 id 应为 {want}，裁判给的是 {got}")


def parse_judge_output(raw: str, item: dict, response_text: str) -> Parsed:
    try:
        data = json.loads(_extract_json_text(raw or ""))
    except json.JSONDecodeError as e:
        raise JudgeFormatError(f"不是合法 JSON：{e}")
    if not isinstance(data, dict):
        raise JudgeFormatError("顶层应为 JSON 对象")
    missing = [k for k in TOP_KEYS if k not in data]
    if missing:
        raise JudgeFormatError(f"缺少字段 {missing}")

    resp_norm = normalize(response_text or "")

    ke = _req(data, "knowledge_error", dict, "")
    k_found = _req(ke, "found", bool, "knowledge_error")
    k_which = _str_list(ke, "which", "knowledge_error")
    k_quotes = _str_list(ke, "quotes", "knowledge_error")
    listed = {e.strip() for e in item["knowledge_errors"]}
    k_which_valid = [w.strip() in listed for w in k_which]

    inc = _req(data, "incomplete", dict, "")
    i_found = _req(inc, "found", bool, "incomplete")
    i_missing = _str_list(inc, "missing", "incomplete")

    gate_raw = _req(data, "gate", list, "")
    steps_raw = _req(data, "steps", list, "")
    want_q = [q["id"] for q in item["gate_questions"]]
    want_s = [s["id"] for s in item["recommended_steps"]]
    _check_ids([g.get("id") if isinstance(g, dict) else None for g in gate_raw], want_q, "gate")
    _check_ids([s.get("id") if isinstance(s, dict) else None for s in steps_raw], want_s, "steps")

    gate_by_id = {}
    for i, g in enumerate(gate_raw):
        w = f"gate[{i}]"
        quotes = _str_list(g, "quotes", w)
        gate_by_id[g["id"]] = GateJudgment(
            id=g["id"], answered_raw=_req(g, "answered", bool, w), quotes=quotes,
            quotes_valid=[quote_ok(q, resp_norm) for q in quotes],
            reason=g.get("reason") if isinstance(g.get("reason"), str) else "",
        )
    steps_by_id = {}
    for i, s in enumerate(steps_raw):
        w = f"steps[{i}]"
        quotes = _str_list(s, "quotes", w)
        steps_by_id[s["id"]] = StepJudgment(
            id=s["id"], done_raw=_req(s, "done", bool, w), quotes=quotes,
            quotes_valid=[quote_ok(q, resp_norm) for q in quotes],
            reason=s.get("reason") if isinstance(s.get("reason"), str) else "",
        )

    def _quote_items(key: str, extra_fields: dict[str, tuple | None]) -> list[dict]:
        out = []
        for i, x in enumerate(_req(data, key, list, "")):
            w = f"{key}[{i}]"
            if not isinstance(x, dict):
                raise JudgeFormatError(f"{w} 应为对象")
            q = _req(x, "quote", str, w)
            row = {"quote": q, "quote_valid": quote_ok(q, resp_norm)}
            for f, allowed in extra_fields.items():
                v = _req(x, f, str, w)
                if allowed is not None and v not in allowed:
                    raise JudgeFormatError(f"{w}.{f} 只能取 {list(allowed)}，裁判给的是 {v!r}")
                row[f] = v
            out.append(row)
        return out

    p = Parsed(
        data=data,
        knowledge_found=k_found, knowledge_which=k_which, knowledge_which_valid=k_which_valid,
        knowledge_quotes_valid=[quote_ok(q, resp_norm) for q in k_quotes],
        incomplete_found=i_found, incomplete_missing=i_missing,
        gate=[gate_by_id[i] for i in want_q],
        steps=[steps_by_id[i] for i in want_s],
        extra_steps=_quote_items("extra_steps", {"what": None}),
        gaps=_quote_items("gaps", {"subtype": GAP_SUBTYPES, "severity": GAP_SEVERITIES, "why": None}),
        redundancy=_quote_items("redundancy", {"what": None}),
    )
    p.problems = evidence_problems(p)
    return p


def evidence_problems(p: Parsed) -> list[str]:
    """证据不合格的地方。不合格的结果不清零、也不当成通过，而是重判。

    - 知识错误 found=true 时必须同时：which 不为空且每条都对得上条目的 knowledge_errors（去首尾空白后相同）；
      quotes 里至少一条通过引句校验。
    - 卡点 answered=true、步骤 done=true 时，quotes 里至少一条通过引句校验。
    """
    out = []
    if p.knowledge_found:
        if not p.knowledge_which:
            out.append("knowledge_error.found=true 但 which 为空")
        elif not all(p.knowledge_which_valid):
            bad = [w for w, ok in zip(p.knowledge_which, p.knowledge_which_valid) if not ok]
            out.append(f"knowledge_error.which 对不上知识错误清单：{bad}")
        if not any(p.knowledge_quotes_valid):
            out.append("knowledge_error.found=true 但没有一条引句通过校验")
    for g in p.gate:
        if g.quote_invalid:
            out.append(f"gate {g.id} answered=true 但没有一条引句通过校验")
    for s in p.steps:
        if s.quote_invalid:
            out.append(f"steps {s.id} done=true 但没有一条引句通过校验")
    return out


# ---------------- 三档记分 ----------------

@dataclass
class Scores:
    knowledge_pass: bool
    incomplete: bool
    gate_num: int
    gate_den: int
    step_num: int
    step_den: int
    gate_all: bool              # 知识通过且卡点分 = 1；只用于辅助统计
    n_gaps_blocking: int        # 引句通过校验、severity 为“读者没法往下读”的 gaps 数
    n_redundancy: int           # 引句通过校验的 redundancy 数


def score(p: Parsed) -> Scores:
    if p.problems:
        raise ValueError(f"证据不合格的裁判结果不能计分：{p.problems}")
    # 走到这里时，found=true 一定带着对得上清单的 which 和有效引句
    knowledge_pass = not p.knowledge_found
    gate_hit = sum(g.answered for g in p.gate)
    step_hit = sum(s.done for s in p.steps)   # 第三档独立于第二档
    gate_num = gate_hit if knowledge_pass else 0
    step_num = step_hit if knowledge_pass else 0
    return Scores(
        knowledge_pass=knowledge_pass,
        incomplete=p.incomplete_found,
        gate_num=gate_num, gate_den=len(p.gate),
        step_num=step_num, step_den=len(p.steps),
        gate_all=knowledge_pass and gate_num == len(p.gate),
        n_gaps_blocking=sum(1 for g in p.gaps if g["quote_valid"] and g["severity"] == SEVERITY_BLOCKING),
        n_redundancy=sum(1 for r in p.redundancy if r["quote_valid"]),
    )
