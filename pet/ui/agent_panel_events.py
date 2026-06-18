from ..utils import extract_message_text, summarize_tool_payload


class AgentPanelEventsMixin:
    DIAGNOSTIC_EVENT_KEYS = (
        "error",
        "errorMessage",
        "message",
        "stderr",
        "output",
        "reason",
        "details",
    )

    def rpc_event_diagnostic_text(self, event):
        if not isinstance(event, dict):
            return ""
        event_type = str(event.get("type") or "")
        diagnostic = bool(event.get("isError") or event.get("error") or event.get("success") is False)
        diagnostic = diagnostic or any(marker in event_type.lower() for marker in ("error", "fail", "failed"))
        parts = []
        for key in self.DIAGNOSTIC_EVENT_KEYS:
            value = event.get(key)
            if value in (None, "", {}, []):
                continue
            if key == "message" and isinstance(value, dict):
                nested_error = value.get("error") or value.get("errorMessage") or value.get("stderr")
                if nested_error:
                    diagnostic = True
                    parts.append(str(nested_error))
                elif value.get("isError"):
                    diagnostic = True
                    text = extract_message_text(value) or summarize_tool_payload(value, limit=600)
                    if text:
                        parts.append(text)
                continue
            if isinstance(value, str):
                lower = value.lower()
                if any(marker in lower for marker in ("error", "failed", "exception", "timeout", "fetch failed")):
                    diagnostic = True
                parts.append(value)
            else:
                parts.append(summarize_tool_payload(value, limit=600))
        if not diagnostic or not parts:
            return ""
        seen = set()
        unique = []
        for part in parts:
            part = str(part).strip()
            if part and part not in seen:
                seen.add(part)
                unique.append(part)
        return "\n".join(unique)

    def handle_rpc_event(self, event):
        if not isinstance(event, dict):
            return
        event_type = event.get("type")
        diagnostic = self.rpc_event_diagnostic_text(event)
        if diagnostic:
            self.record_run_diagnostic(diagnostic)
        if event_type == "response":
            if not event.get("success", False):
                text = event.get("error") or "RPC \u547d\u4ee4\u5931\u8d25\u3002"
                if not getattr(self, "pi_running", False):
                    self.append_message("system", text)
            return
        if event_type == "agent_start":
            self.set_activity("\u6b63\u5728\u601d\u8003\u2026")
            return
        if event_type == "agent_end":
            will_retry = event.get("willRetry")
            if will_retry:
                self.set_activity("\u6b63\u5728\u81ea\u52a8\u91cd\u8bd5\u2026")
            else:
                self.finish_run()
                self.sync_rpc_messages()
            return
        if event_type == "message_start":
            message = event.get("message", {})
            role = message.get("role")
            if role == "assistant":
                self.set_activity("\u6b63\u5728\u751f\u6210\u56de\u590d\u2026")
            elif role in {"reasoning", "thinking"}:
                self.set_activity("\u6b63\u5728\u601d\u8003\u2026")
            return
        if event_type == "message_update":
            message = event.get("message", {})
            role = message.get("role")
            if role == "assistant":
                text = extract_message_text(message)
                if text:
                    self.upsert_agent_text(text)
            elif role in {"reasoning", "thinking"}:
                text = extract_message_text(message)
                if text:
                    if self.active_reasoning_index is None:
                        self.active_reasoning_index = self.append_message("reasoning", text)
                    else:
                        self.update_message(self.active_reasoning_index, text)
            return
        if event_type == "message_end":
            message = event.get("message", {})
            role = message.get("role")
            if role == "assistant":
                text = extract_message_text(message)
                if text:
                    self.upsert_agent_text(text)
                self.finish_live_stream(render=True)
            elif role in {"reasoning", "thinking"}:
                text = extract_message_text(message)
                if text:
                    if self.active_reasoning_index is None:
                        self.active_reasoning_index = self.append_message("reasoning", text)
                    else:
                        self.update_message(self.active_reasoning_index, text)
                self.active_reasoning_index = None
            elif role == "toolResult":
                text = extract_message_text(message)
                if text:
                    is_error = bool(message.get("isError"))
                    pseudo_event = {
                        "toolCallId": message.get("toolCallId")
                        or message.get("toolUseId")
                        or message.get("id"),
                        "name": message.get("toolName") or message.get("name") or "tool",
                        "result": text,
                        "isError": is_error,
                    }
                    self.upsert_tool_event(
                        pseudo_event,
                        "\u5931\u8d25" if is_error else "\u5b8c\u6210",
                        is_error=is_error,
                    )
            return
        if event_type == "tool_execution_start":
            self.upsert_tool_event(event, "\u8fd0\u884c\u4e2d")
            return
        if event_type == "tool_execution_update":
            self.upsert_tool_event(event, "\u8fd0\u884c\u4e2d")
            return
        if event_type == "tool_execution_end":
            self.upsert_tool_event(
                event,
                "\u5931\u8d25" if event.get("isError") else "\u5b8c\u6210",
                is_error=event.get("isError"),
            )
            return
        if event_type == "session_info_changed":
            # Cosmetic rename notice -> refresh list quietly, no transcript noise.
            self.refresh_sessions()
            return
        if event_type == "thinking_level_changed":
            self.flash_status(f"\u601d\u8003\u5f3a\u5ea6\uff1a{event.get('level')}")
            self.update_status_labels()
            return
        if event_type in {"compaction_start", "auto_retry_start"}:
            self.set_activity(
                "\u6b63\u5728\u538b\u7f29\u4e0a\u4e0b\u6587\u2026"
                if event_type == "compaction_start"
                else "\u6b63\u5728\u81ea\u52a8\u91cd\u8bd5\u2026"
            )
            return
        if event_type in {"compaction_end", "auto_retry_end"}:
            if self.pi_running:
                self.set_activity("\u6b63\u5728\u601d\u8003\u2026")
            else:
                self.set_activity("")
            return
