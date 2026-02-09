from __future__ import annotations

import json
import os
import re
from typing import Any, Iterable

import requests


def _extract_json(text: str) -> Any:
    """Extract the first valid JSON value from text."""
    # Try direct parse first.
    try:
        return json.loads(text)
    except Exception:
        pass

    # Fallback: find the first {...} or [...]
    m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            return None
    return None


def call_openrouter_effects(
    *,
    text: str,
    model: str = "anthropic/claude-3.5-sonnet",
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.1,
) -> list[dict[str, Any]]:
    """
    Call OpenRouter to turn effect text into structured instructions.
    Returns a list of instruction dicts.
    """
    api_key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    base_url = base_url or os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    prompt = (
        "你是結構化解析器，輸入是寶可夢卡牌的招式/特性文字（繁中）。"
        "請輸出 JSON array，每個元素是一個步驟/指令："
        '{ "step": "簡短描述", "condition": "觸發條件或前提，若沒有留空字串", "action": "要做的動作", '
        '"result": "造成的結果或影響", "notes": "其他補充(可省略)" }。'
        "不要加入解釋文字，只輸出 JSON。"
    )

    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
    }
    resp = requests.post(base_url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    parsed = _extract_json(content) or []
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return []
    # Ensure dicts only
    cleaned: list[dict[str, Any]] = []
    for item in parsed:
        if isinstance(item, dict):
            cleaned.append(item)
        elif isinstance(item, str):
            cleaned.append({"step": item})
    return cleaned

