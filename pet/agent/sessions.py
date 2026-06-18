import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..config import PI_DATA_DIR, ROOT
from ..utils import extract_message_text, parse_iso_timestamp, summarize_tool_payload


def agent_session_dir(cwd=ROOT, agent_dir=PI_DATA_DIR):
    resolved = str(Path(cwd).resolve())
    safe_path = "--" + re.sub(r"[/\\:]", "-", re.sub(r"^[/\\]", "", resolved)) + "--"
    return Path(agent_dir) / "sessions" / safe_path


def make_agent_session_id():
    return f"pet-agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


@dataclass
class AgentSessionSummary:
    session_id: str
    path: Path | None
    name: str
    updated: float
    message_count: int
    preview: str

    @property
    def label(self):
        when = time.strftime("%m-%d %H:%M", time.localtime(self.updated)) if self.updated else "\u672a\u77e5\u65f6\u95f4"
        title = self.name or self.preview or self.session_id
        if len(title) > 34:
            title = title[:34] + "..."
        return f"{when} \u00b7 {title}"


def iter_session_entries(path):
    try:
        with Path(path).open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def summarize_session_file(path):
    path = Path(path)
    session_id = path.stem
    name = ""
    preview = ""
    first_user = ""
    message_count = 0
    updated = path.stat().st_mtime if path.exists() else time.time()
    for entry in iter_session_entries(path):
        entry_type = entry.get("type")
        if entry_type == "session":
            session_id = entry.get("id") or session_id
            updated = parse_iso_timestamp(entry.get("timestamp")) or updated
        elif entry_type == "session_info":
            name = (entry.get("name") or "").strip()
        elif entry_type == "message":
            message = entry.get("message", {})
            role = message.get("role")
            text = extract_message_text(message)
            if role in {"user", "assistant"}:
                message_count += 1
                msg_time = message.get("timestamp")
                if isinstance(msg_time, (int, float)):
                    updated = max(updated, msg_time / 1000 if msg_time > 10_000_000_000 else msg_time)
                updated = max(updated, parse_iso_timestamp(entry.get("timestamp")) or 0)
            if text and role == "user" and not first_user:
                first_user = text
            if text:
                preview = text
    return AgentSessionSummary(
        session_id=session_id,
        path=path,
        name=name,
        updated=updated,
        message_count=message_count,
        preview=name or first_user or preview or "(\u7a7a\u4f1a\u8bdd)",
    )


def list_agent_sessions():
    directory = agent_session_dir()
    if not directory.exists():
        return []
    summaries = []
    for path in directory.glob("*.jsonl"):
        try:
            summaries.append(summarize_session_file(path))
        except OSError:
            continue
    summaries.sort(key=lambda item: item.updated, reverse=True)
    return summaries


def load_session_messages(path):
    # Only the actual conversation is replayed (user / agent / tool). The old
    # implementation also injected "\u4f1a\u8bdd\u540d\uff1a / \u6a21\u578b\uff1a / \u601d\u8003\u5f3a\u5ea6\uff1a / \u4e0a\u4e0b\u6587\u5df2\u538b\u7f29" system
    # lines, which cluttered the transcript. We keep history clean and
    # Codex-like by dropping those meta entries.
    messages = []
    for entry in iter_session_entries(path):
        if entry.get("type") != "message":
            continue
        message = entry.get("message", {})
        role = message.get("role", "")
        text = extract_message_text(message)
        if not text:
            continue
        if role == "user":
            messages.append(("user", text))
        elif role == "assistant":
            if all(ch in ".\u2026" for ch in text.strip()):
                continue
            messages.append(("agent", text))
        elif role == "toolResult":
            messages.append(("tool", text))
    return messages


def find_session_summary(session_id):
    for summary in list_agent_sessions():
        if summary.session_id == session_id:
            return summary
    return None


# Retained for backwards compatibility with callers that imported this helper.
_ = summarize_tool_payload
