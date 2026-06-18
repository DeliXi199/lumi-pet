import json
from datetime import datetime


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def lerp(a, b, k):
    return a + (b - a) * k


def color_mix(a, b, amount):
    amount = clamp(amount, 0.0, 1.0)
    return (
        int(a[0] + (b[0] - a[0]) * amount),
        int(a[1] + (b[1] - a[1]) * amount),
        int(a[2] + (b[2] - a[2]) * amount),
    )


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def parse_iso_timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


MOJIBAKE_HINTS = ("浣", "鎴", "鐨", "涓", "鍦", "锛", "鈥", "€", "绋", "妗")


def repair_mojibake(text):
    if not isinstance(text, str) or not text or not any(hint in text for hint in MOJIBAKE_HINTS):
        return text
    try:
        candidate = text.encode("gbk").decode("utf-8")
    except UnicodeError:
        return text
    useful_chars = "你我他的是了一不在有和就人都中为上个国说要到可以这个项目代码文件功能"
    old_score = sum(text.count(ch) for ch in useful_chars)
    new_score = sum(candidate.count(ch) for ch in useful_chars)
    return candidate if new_score > old_score else text


def extract_message_text(message, include_thinking=False):
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
    if isinstance(content, str):
        return repair_mojibake(content)
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            parts.append(block.get("text", ""))
        elif include_thinking and block_type == "thinking":
            thinking = block.get("thinking") or block.get("summary") or ""
            if isinstance(thinking, list):
                thinking = "\n".join(str(item) for item in thinking)
            parts.append(str(thinking))
    return repair_mojibake("\n".join(part for part in parts if part).strip())


def summarize_tool_payload(value, limit=360):
    try:
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(value)
    text = repair_mojibake(text.strip())
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def extract_tool_payload_text(value, limit=900):
    if value is None:
        return ""
    text = ""
    if isinstance(value, dict):
        content = value.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                item_text = item.get("text") or item.get("data") or ""
                if item_text:
                    parts.append(str(item_text))
            text = "\n".join(parts).strip()
        elif isinstance(content, str):
            text = content.strip()
        if not text:
            text = summarize_tool_payload(value, limit=limit)
        details = value.get("details")
        if isinstance(details, dict):
            full_output = details.get("fullOutputPath")
            if full_output:
                text = (text + "\n" if text else "") + f"完整输出：{full_output}"
    elif isinstance(value, str):
        text = value.strip()
    else:
        text = summarize_tool_payload(value, limit=limit)
    text = repair_mojibake(text)
    if len(text) > limit:
        return text[:limit] + "..."
    return text
