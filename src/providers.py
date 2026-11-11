"""统一调用 HKUST GenAI API 和 OpenAI API。

对外只有一个函数 call(model_cfg, config, system, user)：按 config 里模型注明的接口发请求，
负责限速、失败重试和密钥脱敏，返回 CallOutcome。换接口只需改 config.yaml。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

import httpx

# Responses 接口返回体里，描述“这次实际用了什么参数”的字段
_OPENAI_REPORTED_PARAM_KEYS = [
    "temperature", "top_p", "max_output_tokens", "reasoning", "text",
    "service_tier", "truncation", "store", "parallel_tool_calls",
]


@dataclass
class CallOutcome:
    ok: bool                        # 接口调用是否成功拿到回答（截断等判定由调用方决定）
    text: str | None = None
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    usage_raw: dict | None = None
    model_version: str | None = None     # 接口返回的实际模型版本
    params_sent: dict = field(default_factory=dict)
    params_reported: dict | None = None  # 接口回报的实际参数（hkust 的 chat completions 不回报，为 None）
    latency_s: float | None = None       # 最后一次尝试的耗时
    attempts: int = 0
    error: str | None = None


class _CallError(Exception):
    def __init__(self, message: str, retryable: bool, retry_after: float | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


# ---------------- 密钥 ----------------

def _key_env_names(config: dict) -> list[str]:
    return [p["api_key_env"] for p in config["providers"].values() if p.get("api_key_env")]


def redact(text: str, config: dict) -> str:
    """把任何已配置密钥的值替换成 ***，用于错误信息和日志。"""
    for name in _key_env_names(config):
        val = os.environ.get(name)
        if val and len(val) >= 8:
            text = text.replace(val, "***")
    return text


def require_key(provider_name: str, config: dict) -> str:
    env = config["providers"][provider_name]["api_key_env"]
    val = os.environ.get(env, "").strip()
    if not val:
        raise RuntimeError(f"缺少环境变量 {env}（接口 {provider_name} 的密钥）。请在 .env 中填写，参见 .env.example")
    return val


# ---------------- 限速 ----------------

_last_call_at: dict[str, float] = {}


def _throttle(provider_name: str, pcfg: dict) -> None:
    rpm = pcfg.get("rate_limit_per_minute")
    if not rpm:
        return
    gap = 60.0 / float(rpm)
    last = _last_call_at.get(provider_name)
    if last is not None:
        wait = gap - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _last_call_at[provider_name] = time.monotonic()


# ---------------- 参数 ----------------

def build_params(model_cfg: dict, config: dict) -> dict:
    """实际发送的参数 = 接口默认参数 < 全局默认参数 < 模型参数。"""
    pcfg = config["providers"][model_cfg["provider"]]
    params: dict = {}
    params.update(pcfg.get("default_params") or {})
    params.update((config.get("defaults") or {}).get("params") or {})
    params.update(model_cfg.get("params") or {})
    return params


# ---------------- 各接口 ----------------

def _call_hkust(model_cfg: dict, pcfg: dict, key: str, system: str, user: str, params: dict) -> dict:
    body = {
        "model": model_cfg["model_id"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **params,
    }
    try:
        r = httpx.post(
            pcfg["url"],
            params=pcfg.get("query_params") or None,
            headers={"api-key": key, "Content-Type": "application/json"},
            json=body,
            timeout=pcfg.get("timeout_seconds", 300),
        )
    except httpx.TimeoutException as e:
        raise _CallError(f"请求超时：{type(e).__name__}", retryable=True)
    except httpx.TransportError as e:
        raise _CallError(f"网络错误：{type(e).__name__}: {e}", retryable=True)

    if r.status_code == 429:
        ra = r.headers.get("retry-after")
        try:
            ra_s = float(ra) if ra else None
        except ValueError:
            ra_s = None
        raise _CallError(f"HTTP 429 限速：{r.text[:300]}", retryable=True, retry_after=ra_s)
    if r.status_code >= 500:
        raise _CallError(f"HTTP {r.status_code}：{r.text[:300]}", retryable=True)
    if r.status_code >= 400:
        raise _CallError(f"HTTP {r.status_code}：{r.text[:500]}", retryable=False)
    try:
        data = r.json()
        choice = data["choices"][0]
        text = choice["message"].get("content") or ""
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise _CallError(f"返回格式无法解析：{type(e).__name__}: {r.text[:300]}", retryable=True)
    usage = data.get("usage") or {}
    return {
        "text": text,
        "finish_reason": choice.get("finish_reason"),
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "usage_raw": usage,
        "model_version": data.get("model"),
        "params_reported": None,
    }


_openai_clients: dict = {}


def _call_openai(model_cfg: dict, pcfg: dict, key: str, system: str, user: str, params: dict) -> dict:
    import openai

    timeout = pcfg.get("timeout_seconds", 600)
    ck = (key, timeout)
    if ck not in _openai_clients:
        # SDK 自带的重试关掉，统一走本模块的重试逻辑，便于计数和记录
        _openai_clients[ck] = openai.OpenAI(api_key=key, timeout=timeout, max_retries=0)
    client = _openai_clients[ck]
    try:
        resp = client.responses.create(
            model=model_cfg["model_id"],
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **params,
        )
    except openai.RateLimitError as e:
        ra = None
        try:
            ra = float(e.response.headers.get("retry-after"))
        except (TypeError, ValueError, AttributeError):
            pass
        raise _CallError(f"限速 429：{e}", retryable=True, retry_after=ra)
    except (openai.APITimeoutError, openai.APIConnectionError) as e:
        raise _CallError(f"网络错误：{type(e).__name__}: {e}", retryable=True)
    except openai.InternalServerError as e:
        raise _CallError(f"服务端错误：{e}", retryable=True)
    except openai.APIStatusError as e:
        raise _CallError(f"HTTP {e.status_code}：{e}", retryable=False)

    d = resp.model_dump()
    status = d.get("status")
    reason = (d.get("incomplete_details") or {}).get("reason")
    if status == "completed":
        finish = "stop"
    elif status == "incomplete" and reason == "max_output_tokens":
        finish = "length"
    elif status == "incomplete" and reason:
        finish = reason
    else:
        finish = status
    if status == "failed":
        raise _CallError(f"接口返回 failed：{json.dumps(d.get('error'), ensure_ascii=False)[:300]}", retryable=True)
    usage = d.get("usage") or {}
    return {
        "text": resp.output_text or "",
        "finish_reason": finish,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "usage_raw": usage,
        "model_version": d.get("model"),
        "params_reported": {k: d.get(k) for k in _OPENAI_REPORTED_PARAM_KEYS if k in d},
    }


_IMPLS = {"hkust": _call_hkust, "openai": _call_openai}


# ---------------- 对外唯一入口 ----------------

def call(model_cfg: dict, config: dict, system: str, user: str, log=print) -> CallOutcome:
    """调用 model_cfg 所注明接口上的模型。失败按 config.defaults.retry 等待后重试；
    最终仍失败时返回 ok=False 和错误信息，不抛异常。"""
    provider = model_cfg["provider"]
    if provider not in _IMPLS:
        return CallOutcome(ok=False, error=f"未知接口 {provider!r}，可选：{', '.join(_IMPLS)}")
    pcfg = config["providers"][provider]
    retry = (config.get("defaults") or {}).get("retry") or {}
    max_retries = int(retry.get("max_retries", 3))
    base = float(retry.get("base_wait_seconds", 5))
    cap = float(retry.get("max_wait_seconds", 60))
    params = build_params(model_cfg, config)

    try:
        key = require_key(provider, config)
    except RuntimeError as e:
        return CallOutcome(ok=False, params_sent=params, error=str(e))

    attempt = 0
    while True:
        attempt += 1
        _throttle(provider, pcfg)
        t0 = time.monotonic()
        try:
            r = _IMPLS[provider](model_cfg, pcfg, key, system, user, params)
            return CallOutcome(ok=True, params_sent=params, latency_s=time.monotonic() - t0,
                               attempts=attempt, **r)
        except _CallError as e:
            latency = time.monotonic() - t0
            msg = redact(str(e), config)
            if not e.retryable or attempt > max_retries:
                tag = "不可重试" if not e.retryable else f"已重试 {max_retries} 次"
                return CallOutcome(ok=False, params_sent=params, latency_s=latency,
                                   attempts=attempt, error=f"{msg}（{tag}）")
            wait = min(cap, base * 2 ** (attempt - 1))
            if e.retry_after:
                wait = max(wait, min(e.retry_after, 120.0))
            log(f"    第 {attempt} 次调用失败：{msg[:200]}；{wait:.0f} 秒后重试")
            time.sleep(wait)
        except Exception as e:  # 防御：未预料的异常也记录下来，不中断整批
            return CallOutcome(ok=False, params_sent=params, latency_s=time.monotonic() - t0,
                               attempts=attempt, error=redact(f"未预料的错误 {type(e).__name__}: {e}", config))
