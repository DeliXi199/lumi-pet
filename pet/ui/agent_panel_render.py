import html
import re
import tempfile
import time
from pathlib import Path

from ..qt import QApplication, QColor, QFont, QFontMetrics, QImage, QMimeData, QPainter, QRectF, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument, Qt, QTimer
from ..utils import extract_tool_payload_text, summarize_tool_payload
from .agent_message_html import chat_bubble_html, local_output_html, run_summary_html, system_line_html, welcome_html
from .agent_markdown import highlight_code, highlight_code_pygments

ACTIVITY_SPINNER_FRAMES = ("\u280b", "\u2819", "\u2839", "\u2838", "\u283c", "\u2834", "\u2826", "\u2827", "\u2807", "\u280f")


class AgentPanelRenderMixin:
    ROLE_LABELS = {"user": "\u4f60", "agent": "Codex", "tool": "\u5de5\u5177", "system": "\u7cfb\u7edf"}
    ERROR_HINTS = ("\u5931\u8d25", "\u9519\u8bef", "\u9000\u51fa\u7801", "\u4e0d\u53ef\u7528", "\u672a\u627e\u5230", "\u8d85\u65f6", "\u5f02\u5e38")
    STREAM_FAST_RENDER_DELAY_MS = 24
    STREAM_NORMAL_RENDER_DELAY_MS = 72
    STREAM_SLOW_RENDER_DELAY_MS = 150
    IDLE_RENDER_DELAY_MS = 35

    def reset_user_bubble_images(self):
        """Prepare the per-panel image cache used by rendered user bubbles.

        User bubbles are painted into PNGs so Qt can show smooth rounded
        corners. Repainting every old bubble on each streamed token was a
        noticeable source of stutter, so images now live for the panel lifetime
        and are reused by content/style key.
        """
        if not isinstance(getattr(self, "_render_image_cache", None), dict):
            self._render_image_cache = {}
        if not isinstance(getattr(self, "_user_bubble_image_paths", None), list):
            self._user_bubble_image_paths = []
        if not hasattr(self, "_render_image_counter"):
            self._render_image_counter = 0

    def cleanup_render_images(self):
        for path in getattr(self, "_user_bubble_image_paths", []):
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass
        self._user_bubble_image_paths = []
        self._render_image_cache = {}

    def save_render_image(self, image, prefix):
        self.reset_user_bubble_images()
        render_dir = Path(tempfile.gettempdir()) / "pet_agent_rendered_blocks"
        render_dir.mkdir(parents=True, exist_ok=True)
        counter = getattr(self, "_render_image_counter", 0)
        self._render_image_counter = counter + 1
        image_path = render_dir / f"{prefix}_{id(self)}_{counter}.png"
        image.save(str(image_path), "PNG")
        self._user_bubble_image_paths.append(str(image_path))
        return image_path.as_uri()

    def user_bubble_image_html(self, body, bg_rgba, text_css, margin, plain_text=None):
        try:
            viewport_width = self.message_stream.viewport().width() or self.message_stream.width() or 960
            max_bubble_width = int(max(220, min(720, viewport_width * 0.58)))
            pad_x = 16
            pad_y = 8
            scale = 2

            def image_html(src, logical_width, logical_height):
                return (
                    f'<table width="100%" cellspacing="0" cellpadding="0" style="margin:{margin};">'
                    f'<tr><td align="right">'
                    f'<img src="{src}" width="{logical_width}" height="{logical_height}" />'
                    f'</td></tr></table>'
                )

            def cached_image(cache_key):
                cached = getattr(self, "_render_image_cache", {}).get(cache_key)
                if not cached:
                    return None
                src, logical_width, logical_height = cached
                return image_html(src, logical_width, logical_height)

            def save_image(image, logical_width, logical_height, cache_key):
                src = self.save_render_image(image, "user_bubble")
                self._render_image_cache[cache_key] = (src, logical_width, logical_height)
                return (
                    image_html(src, logical_width, logical_height)
                )

            plain = str(plain_text or "").strip()
            if plain and "\n" not in plain and len(plain) <= 80 and not re.search(r"[`*_#>\[\]\(\)]", plain):
                font = self.message_stream.font()
                font.setWeight(QFont.Weight.Normal)
                try:
                    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
                    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
                except Exception:
                    pass
                metrics = QFontMetrics(font)
                text_width = metrics.horizontalAdvance(plain)
                text_height = metrics.height()
                logical_width = min(max_bubble_width, max(46, text_width + pad_x * 2))
                if logical_width >= text_width + pad_x * 2:
                    cache_key = (
                        "user_plain",
                        plain,
                        bg_rgba,
                        text_css,
                        max_bubble_width,
                        font.family(),
                        round(font.pointSizeF(), 2),
                        str(font.weight()),
                    )
                    cached = cached_image(cache_key)
                    if cached:
                        return cached
                    logical_height = max(34, text_height + pad_y * 2)
                    image = QImage(
                        logical_width * scale,
                        logical_height * scale,
                        QImage.Format.Format_ARGB32_Premultiplied,
                    )
                    image.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(image)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
                    painter.scale(scale, scale)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(*bg_rgba))
                    painter.drawRoundedRect(
                        QRectF(0, 0, logical_width, logical_height),
                        logical_height / 2,
                        logical_height / 2,
                    )
                    painter.setFont(font)
                    painter.setPen(QColor(232, 236, 245))
                    painter.drawText(
                        QRectF(pad_x, 0, text_width + 2, logical_height),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        plain,
                    )
                    painter.end()
                    return save_image(image, logical_width, logical_height, cache_key)

            max_content_width = max_bubble_width - pad_x * 2
            pad_y = 9
            radius = 18
            stream_font = self.message_stream.font()
            cache_key = (
                "user_rich",
                body,
                bg_rgba,
                text_css,
                max_bubble_width,
                stream_font.family(),
                round(stream_font.pointSizeF(), 2),
                round(getattr(self, "font_scale", 1.0), 2),
            )
            cached = cached_image(cache_key)
            if cached:
                return cached

            def make_doc(width=None):
                doc = QTextDocument()
                doc.setDefaultFont(stream_font)
                doc.setDocumentMargin(0)
                doc.setHtml(
                    f'<div style="margin:0; color:{text_css}; line-height:1.62; '
                    f'font-family:\'Segoe UI Variable Text\',\'Segoe UI\',\'Microsoft YaHei UI\',\'Microsoft YaHei\',sans-serif;">{body}</div>'
                )
                if width is not None:
                    doc.setTextWidth(width)
                return doc

            natural_doc = make_doc()
            natural_width = int(natural_doc.idealWidth()) + 2
            content_width = max(52, min(max_content_width, natural_width))
            doc = make_doc(content_width)
            doc_height = max(24, int(doc.size().height()) + 2)
            image_width = int(content_width + pad_x * 2)
            image_height = int(doc_height + pad_y * 2)

            image = QImage(image_width * scale, image_height * scale, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.scale(scale, scale)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(*bg_rgba))
            painter.drawRoundedRect(QRectF(0, 0, image_width, image_height), radius, radius)
            painter.translate(pad_x, pad_y)
            doc.drawContents(painter, QRectF(0, 0, content_width, doc_height))
            painter.end()
            return save_image(image, image_width, image_height, cache_key)
        except Exception:
            return chat_bubble_html(body, "right", self.css_rgba(bg_rgba[:3], bg_rgba[3]), "transparent", text_css, "60%", "10px 16px", "1.72", margin)

    # ----------------------------------------------------------- render scheduling
    def text_update_has_boundary(self, old_text, new_text):
        old_text = str(old_text or "")
        new_text = str(new_text or "")
        if not old_text:
            return True
        delta = new_text[len(old_text):] if new_text.startswith(old_text) else new_text
        if not delta:
            return False
        if old_text.count("```") != new_text.count("```"):
            return True
        return bool(re.search(r"[\n。！？.!?；;：:，,、)]\s*$", delta) or "\n" in delta)

    def render_delay_for_update(self, role=None, old_text=None, new_text=None):
        is_streaming = bool(
            getattr(self, "pi_running", False)
            or getattr(self, "active_agent_index", None) is not None
            or getattr(self, "active_reasoning_index", None) is not None
        )
        if not is_streaming:
            return self.IDLE_RENDER_DELAY_MS

        old = str(old_text or "")
        new = str(new_text or "")
        delta_len = len(new) - len(old) if new.startswith(old) else len(new)
        transcript_size = len(getattr(self, "display_messages", []))
        heavy = transcript_size > 30 or len(new) > 7000

        if role in {"agent", "reasoning"} and self.text_update_has_boundary(old, new):
            return self.STREAM_NORMAL_RENDER_DELAY_MS if heavy else self.STREAM_FAST_RENDER_DELAY_MS
        if delta_len >= (220 if heavy else 80):
            return self.STREAM_NORMAL_RENDER_DELAY_MS if heavy else self.STREAM_FAST_RENDER_DELAY_MS
        return self.STREAM_SLOW_RENDER_DELAY_MS if heavy else self.STREAM_NORMAL_RENDER_DELAY_MS

    def flush_render_now(self):
        timer = getattr(self, "_render_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
        self._render_dirty = True
        self._render_full_pending = True
        self._flush_render()

    def reset_live_stream_state(self):
        self._live_stream_index = None
        self._live_stream_role = None
        self._live_stream_text = ""
        self._finished_live_stream_index = None
        self._stream_incremental_ready = False
        self._stream_anchor = None
        self._render_full_pending = False

    def begin_live_stream(self, index, role, text):
        if role != "agent":
            return
        self._finished_live_stream_index = None
        self._live_stream_index = index
        self._live_stream_role = role
        self._live_stream_text = str(text or "")
        self.flush_render_now()

    def finish_live_stream(self, render=True):
        finished_index = getattr(self, "_live_stream_index", None)
        had_live_stream = getattr(self, "_live_stream_index", None) is not None
        self._live_stream_index = None
        self._live_stream_role = None
        self._live_stream_text = ""
        self._finished_live_stream_index = finished_index if render and had_live_stream else None
        if render and had_live_stream:
            self.flush_render_now()

    def can_append_live_stream(self, index, role, old_text, new_text):
        if role != "agent":
            return False
        if index != getattr(self, "_live_stream_index", None):
            return False
        if index != len(getattr(self, "display_messages", [])) - 1:
            return False
        if not getattr(self, "pi_running", False):
            return False
        old_text = str(old_text or "")
        new_text = str(new_text or "")
        return bool(new_text.startswith(old_text) and len(new_text) > len(old_text))

    def append_live_stream_delta(self, delta):
        if not delta:
            return
        scrollbar = self.message_stream.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 8
        cursor = self.message_stream.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setFont(self.message_stream.font())
        fmt.setForeground(QColor(229, 232, 238))
        cursor.insertText(str(delta), fmt)
        self._last_render_at = time.monotonic()
        if at_bottom:
            self._scroll_message_stream_to_bottom()
        self.update_scroll_bottom_button()

    def try_append_live_stream(self, index, role, old_text, new_text):
        if not self.can_append_live_stream(index, role, old_text, new_text):
            return False
        delta = str(new_text or "")[len(str(old_text or "")):]
        self.append_live_stream_delta(delta)
        self._live_stream_text = str(new_text or "")
        self._render_dirty = False
        return True

    def schedule_render(self, role=None, old_text=None, new_text=None, force=False, incremental=False):
        """Content-aware render scheduling for streamed output.

        A full render_messages() rebuilds the whole QTextBrowser document, which
        is the expensive, flicker-prone part during streaming. While the active
        assistant message streams we instead rewrite only that one block in
        place (update_streaming_block) so earlier content never repaints.
        """
        if force:
            self.flush_render_now()
            return
        self._render_dirty = True
        if not incremental:
            self._render_full_pending = True
        timer = getattr(self, "_render_timer", None)
        if timer is None:
            timer = self._render_timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._flush_render)
        delay = self.render_delay_for_update(role, old_text, new_text)
        if not timer.isActive() or delay < max(0, timer.remainingTime()):
            timer.start(delay)

    def _flush_render(self):
        if not getattr(self, "_render_dirty", False):
            return
        self._render_dirty = False
        self._last_render_at = time.monotonic()
        do_full = (
            getattr(self, "_render_full_pending", True)
            or not getattr(self, "_stream_incremental_ready", False)
        )
        self._render_full_pending = False
        if do_full:
            self.render_messages()
        else:
            self.update_streaming_block()

    # ----------------------------------------------------------- message api
    def append_message(self, role, text):
        if role == "user":
            self.request_scroll_to_bottom(stick=True)
        self.display_messages.append({"role": role, "text": text})
        if role == "agent" and text:
            self.last_agent_text = text
        self.schedule_render(role=role, old_text="", new_text=text)
        return len(self.display_messages) - 1

    def update_message(self, index, text):
        if index is None or index < 0 or index >= len(self.display_messages):
            return index
        item = self.display_messages[index]
        old_text = item.get("text", "")
        item["text"] = text
        if item.get("role") == "agent" and text:
            self.last_agent_text = text
        if self.is_active_stream_message(index):
            # Only the streaming assistant block changed -> rewrite just that
            # block (progressive markdown, no full-transcript repaint/flicker).
            self.schedule_render(
                role=item.get("role"), old_text=old_text, new_text=text, incremental=True
            )
        else:
            self.schedule_render(role=item.get("role"), old_text=old_text, new_text=text)
        return index

    def is_active_stream_message(self, index):
        return (
            getattr(self, "pi_running", False)
            and index == getattr(self, "_live_stream_index", None)
            and index == getattr(self, "active_agent_index", None)
            and index == len(getattr(self, "display_messages", [])) - 1
        )

    def update_display_item(self, index, **fields):
        if index is None or index < 0 or index >= len(self.display_messages):
            return
        self.display_messages[index].update(fields)
        self.schedule_render()

    def tool_event_key(self, event):
        return event.get("toolCallId") or event.get("id") or event.get("name") or str(len(self.display_messages))

    def format_tool_event_text(self, event):
        name = event.get("name") or event.get("tool") or "tool"
        parts = [f"**{name}**"]
        args = event.get("args") or event.get("input")
        if args not in (None, "", {}, []):
            parts.append("```\n" + extract_tool_payload_text(args, limit=900) + "\n```")
        result = event.get("result") or event.get("output")
        if result not in (None, "", {}, []):
            parts.append("```\n" + extract_tool_payload_text(result, limit=900) + "\n```")
        return "\n".join(parts)

    def collapsed_tool_summary(self, event_or_text):
        if isinstance(event_or_text, dict):
            name = event_or_text.get("name") or event_or_text.get("tool") or "tool"
            payload = event_or_text.get("result") or event_or_text.get("args") or event_or_text.get("input")
            tail = summarize_tool_payload(payload, limit=120) if payload not in (None, "", {}, []) else ""
            return f"{name}{(' \u00b7 ' + tail) if tail else ''}"
        text = re.sub(r"\s+", " ", str(event_or_text or "")).strip()
        return text[:120]

    def ensure_active_tool_group(self):
        """Return the (index, group) of the run's single tool card, creating it.

        All tool calls in one run live as steps inside one collapsible card
        instead of a separate card per micro-operation.
        """
        index = getattr(self, "active_tool_group_index", None)
        if index is not None and 0 <= index < len(self.display_messages):
            group = self.display_messages[index]
            if group.get("role") == "tool_group":
                return index, group
        group = {
            "role": "tool_group",
            "running": True,
            "collapsed": True,
            "elapsed": None,
            "steps": [],
        }
        self.display_messages.append(group)
        self.active_tool_group_index = len(self.display_messages) - 1
        self.tool_step_indices = {}
        return self.active_tool_group_index, group

    def upsert_tool_event(self, event, status_label=None, is_error=None):
        key = self.tool_event_key(event)
        if is_error is None:
            is_error = bool(event.get("isError") or event.get("error"))
        status_text = status_label or ("\u5931\u8d25" if is_error else "\u5b8c\u6210")
        text = self.format_tool_event_text(event)
        summary = self.collapsed_tool_summary(event)
        step_fields = {
            "key": key,
            "text": text,
            "tool_name": event.get("name") or event.get("tool") or "tool",
            "tool_status": status_text,
            "is_error": bool(is_error),
            "summary": summary,
        }
        _, group = self.ensure_active_tool_group()
        steps = group.setdefault("steps", [])
        step_indices = getattr(self, "tool_step_indices", None)
        if not isinstance(step_indices, dict):
            step_indices = self.tool_step_indices = {}
        existing_idx = step_indices.get(key)
        if existing_idx is not None and 0 <= existing_idx < len(steps):
            existing = steps[existing_idx]
            step_fields.setdefault("collapsed", existing.get("collapsed", True))
            existing.update(step_fields)
        else:
            step_fields.setdefault("collapsed", True)
            steps.append(step_fields)
            step_indices[key] = len(steps) - 1
        self.schedule_render()

    def handle_message_link(self, url):
        href = url.toString() if hasattr(url, "toString") else str(url)
        if href.startswith("runstep-toggle:"):
            try:
                _, group_str, step_str = href.split(":")
                group_index = int(group_str)
                step_index = int(step_str)
            except (ValueError, IndexError):
                return
            if 0 <= group_index < len(self.display_messages):
                group = self.display_messages[group_index]
                steps = group.get("steps") or []
                if 0 <= step_index < len(steps):
                    steps[step_index]["collapsed"] = not steps[step_index].get("collapsed", True)
                    self.render_messages()
        elif href.startswith("tool-toggle:") or href.startswith("run-toggle:"):
            try:
                index = int(href.split(":", 1)[1])
            except (ValueError, IndexError):
                return
            if 0 <= index < len(self.display_messages):
                item = self.display_messages[index]
                item["collapsed"] = not item.get("collapsed", True)
                self.render_messages()
        elif href.startswith("copy-code:"):
            try:
                code_id = int(href.split(":", 1)[1])
            except (ValueError, IndexError):
                return
            code = getattr(self, "_code_blocks", {}).get(code_id)
            if code is not None:
                mime = QMimeData()
                mime.setText(code)
                QApplication.clipboard().setMimeData(mime)
                self._copied_code_id = code_id
                self.render_messages()
                QTimer.singleShot(1200, lambda cid=code_id: self.clear_copied_code_marker(cid))
        elif href.startswith("suggest:"):
            sid = href.split(":", 1)[1]
            text = getattr(self, "_welcome_suggestions", {}).get(sid)
            if text:
                self.prompt_input.setPlainText(text)
                self.update_prompt_height()
                self.prompt_input.setFocus()

    def clear_copied_code_marker(self, code_id):
        if getattr(self, "_copied_code_id", None) == code_id:
            self._copied_code_id = None
            self.render_messages()

    # --------------------------------------------------------- markdown -> html
    def _looks_like_diff(self, code, lang):
        if (lang or "").strip().lower() in {"diff", "patch"}:
            return True
        head = code.lstrip()[:600]
        if head.startswith("diff --git "):
            return True
        if head.startswith("@@ ") or "\n@@ " in code[:1200]:
            return True
        if head.startswith("--- ") and "\n+++ " in code[:1200]:
            return True
        return False

    def _diff_highlight_html(self, code):
        """Render a unified diff with Codex-like green/red line coloring."""
        add_bg, add_fg = "rgba(70,160,100,0.16)", "#86c79a"
        del_bg, del_fg = "rgba(200,84,84,0.15)", "#e08a8a"
        hunk_fg, meta_fg = "#6cb6c2", "#8e94a0"
        meta_prefixes = (
            "+++", "---", "diff ", "index ", "new file", "deleted file",
            "rename ", "similarity ", "old mode", "new mode", "\\ No newline",
        )
        out = []
        for line in code.split("\n"):
            esc = html.escape(line) or "&nbsp;"
            if line.startswith("@@"):
                out.append(f'<div style="color:{hunk_fg};">{esc}</div>')
            elif line.startswith(meta_prefixes):
                out.append(f'<div style="color:{meta_fg};">{esc}</div>')
            elif line.startswith("+"):
                out.append(f'<div style="background:{add_bg}; color:{add_fg};">{esc}</div>')
            elif line.startswith("-"):
                out.append(f'<div style="background:{del_bg}; color:{del_fg};">{esc}</div>')
            else:
                out.append(f'<div>{esc}</div>')
        return "".join(out)

    def code_block_html(self, code, lang, code_bg, base_color, border_color, muted):
        registry = getattr(self, "_code_blocks", None)
        if registry is None:
            registry = self._code_blocks = {}
        code_id = getattr(self, "_code_counter", 0)
        self._code_counter = code_id + 1
        registry[code_id] = code
        cache = getattr(self, "_highlight_cache", None)
        if not isinstance(cache, dict):
            cache = self._highlight_cache = {}
        is_diff = self._looks_like_diff(code, lang)
        cache_key = ("diff::" if is_diff else "", lang or "", code)
        highlighted = cache.get(cache_key)
        if highlighted is None:
            if is_diff:
                highlighted = self._diff_highlight_html(code)
            else:
                highlighted = highlight_code_pygments(code, lang) or highlight_code(code, lang)
            cache[cache_key] = highlighted
        label = "diff" if is_diff else ((lang or "").strip().lower() or "code")
        fs = getattr(self, "font_scale", 1.0)
        lbl_px = max(1, int(round(12 * fs)))
        body_px = max(1, int(round(14 * fs)))
        copied = getattr(self, "_copied_code_id", None) == code_id
        copy_label = "✓" if copied else "复制"
        copy_color = "#7ee2a8" if copied else muted
        body = (
            f'<div style="margin-top:10px; font-family:\'Cascadia Code\',Consolas,monospace; '
            f'font-size:{body_px}px; color:{base_color}; white-space:pre-wrap; '
            f'line-height:1.55;">{highlighted}</div>'
        )
        return (
            f'<table width="100%" cellspacing="0" cellpadding="0" style="margin-top:18px; margin-bottom:18px;">'
            f'<tr><td bgcolor="#292929" style="padding:14px 18px 16px 18px;">'
            f'<span style="color:{muted}; font-size:{lbl_px}px;">{html.escape(label or "text")}</span>'
            f'&nbsp;&nbsp;<a href="copy-code:{code_id}" '
            f'style="color:{copy_color}; text-decoration:none; font-size:{lbl_px}px;">{copy_label}</a>'
            f'{body}</td></tr></table>'
        )

    def inline_markdown_html(self, text):
        escaped = html.escape(text)
        escaped = re.sub(
            r"`([^`]+)`",
            lambda m: (
                f'<code style="background:rgb(45,52,66); color:#edf2ff; '
                f'padding:1px 5px; border-radius:5px; '
                f'font-family:\'Cascadia Code\',Consolas,monospace;">{m.group(1)}</code>'
            ),
            escaped,
        )
        escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
        escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", escaped)
        escaped = re.sub(r"~~([^~]+)~~", r"<s>\1</s>", escaped)
        escaped = re.sub(
            r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
            lambda m: f'<a href="{m.group(2)}" style="color:#6cb6ff;">{m.group(1)}</a>',
            escaped,
        )
        return escaped

    def message_markdown_html(self, text, base_color, code_bg, border_color, muted):
        lines = str(text or "").split("\n")
        blocks = []
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]
            stripped = line.strip()
            if stripped.startswith("```"):
                lang = stripped[3:].strip()
                code_lines = []
                i += 1
                while i < n and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                if i < n:
                    i += 1
                code = "\n".join(code_lines)
                blocks.append(self.code_block_html(code, lang, code_bg, base_color, border_color, muted))
                continue
            if not stripped:
                i += 1
                continue
            heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
            if heading:
                level = len(heading.group(1))
                size = {1: "1.25em", 2: "1.15em", 3: "1.05em", 4: "1.0em"}[level]
                blocks.append(
                    f'<div style="font-size:{size}; font-weight:700; color:{base_color}; margin:10px 0 4px 0;">'
                    f'{self.inline_markdown_html(heading.group(2))}</div>'
                )
                i += 1
                continue
            if stripped in {"---", "***", "___"}:
                blocks.append(f'<div style="border-top:1px solid {border_color}; margin:10px 0;"></div>')
                i += 1
                continue
            if stripped.startswith(">"):
                quote = self.inline_markdown_html(re.sub(r"^>\s?", "", stripped))
                blocks.append(
                    f'<div style="border-left:2px solid {border_color}; padding-left:10px; '
                    f'color:{muted}; margin:4px 0;">{quote}</div>'
                )
                i += 1
                continue
            bullet = re.match(r"^[-*]\s+(.*)$", stripped)
            if bullet:
                items = []
                while i < n and re.match(r"^[-*]\s+(.*)$", lines[i].strip()):
                    content = re.match(r"^[-*]\s+(.*)$", lines[i].strip()).group(1)
                    items.append(f'<li style="margin:2px 0;">{self.inline_markdown_html(content)}</li>')
                    i += 1
                blocks.append(f'<ul style="margin:4px 0 4px 4px; padding-left:18px;">{"".join(items)}</ul>')
                continue
            ordered = re.match(r"^\d+\.\s+(.*)$", stripped)
            if ordered:
                items = []
                while i < n and re.match(r"^\d+\.\s+(.*)$", lines[i].strip()):
                    content = re.match(r"^\d+\.\s+(.*)$", lines[i].strip()).group(1)
                    items.append(f'<li style="margin:2px 0;">{self.inline_markdown_html(content)}</li>')
                    i += 1
                blocks.append(f'<ol style="margin:4px 0 4px 4px; padding-left:20px;">{"".join(items)}</ol>')
                continue
            blocks.append(
                f'<div style="margin:3px 0; color:{base_color};">{self.inline_markdown_html(stripped)}</div>'
            )
            i += 1
        return "".join(blocks) or '<div style="opacity:0.6;">\u2026</div>'

    def live_stream_text_html(self, text, base_color):
        escaped = html.escape(str(text or ""))
        if not escaped:
            return '<span style="opacity:0.6;">\u2026</span>'
        return (
            f'<span style="color:{base_color}; white-space:pre-wrap;">'
            f'{escaped}</span>'
        )

    def activity_status_html(self, faint_css, accent_css):
        activity = str(getattr(self, "_activity_text", "") or "").strip()
        flash = str(getattr(self, "_flash_text", "") or "").strip()
        if activity:
            marker = ACTIVITY_SPINNER_FRAMES[getattr(self, "_spin_index", 0) % len(ACTIVITY_SPINNER_FRAMES)]
            suffix = ""
            started = getattr(self, "_run_started_at", None)
            if getattr(self, "pi_running", False) and started is not None:
                secs = int(max(0.0, time.monotonic() - started))
                suffix = f" \u00b7 {secs}s \u00b7 Esc \u4e2d\u65ad"
            text = f"{marker}  {activity}{suffix}"
            color = accent_css
        elif flash:
            text = flash
            color = faint_css
        else:
            return ""
        return (
            f'<div style="margin:8px 22% 12px 2px; color:{color}; '
            f'font-size:0.92em; line-height:1.6; font-family:\'Segoe UI Variable Text\','
            f'\'Segoe UI\',\'Microsoft YaHei UI\',\'Microsoft YaHei\',sans-serif;">'
            f'{html.escape(text)}</div>'
        )

    def _message_palette(self):
        text_css = self.css_rgb((229, 232, 238))
        muted_css = self.css_rgb((154, 161, 173))
        code_bg = self.css_rgb((7, 9, 13))
        border_css = self.css_rgb((62, 70, 86))
        theme = self.model.themes[self.model.theme_key]
        accent_css = self.css_rgb(self.softer(theme.accent))
        return text_css, muted_css, code_bg, border_css, accent_css

    def agent_block_html(self, raw_text, text_css, code_bg, border_css, muted_css, accent_css, caret=False):
        body = self.message_markdown_html(raw_text, text_css, code_bg, border_css, muted_css)
        if caret:
            body += f'<span style="color:{accent_css};">\u2588</span>'
        return (
            f'<div style="margin:10px 22% 24px 2px; color:{text_css}; '
            f'line-height:1.82; font-size:1.01em; white-space:pre-wrap;">{body}</div>'
        )

    def update_streaming_block(self):
        """Rewrite only the active streaming assistant block in place.

        render_messages() rendered every earlier message as a static prefix and
        recorded where the streaming block begins. Here we replace just that
        trailing region with freshly rendered markdown, so the rest of the
        transcript never repaints and the answer streams smoothly like Codex.
        """
        index = getattr(self, "_live_stream_index", None)
        anchor = getattr(self, "_stream_anchor", None)
        if (
            index is None
            or anchor is None
            or not (0 <= index < len(self.display_messages))
            or self.display_messages[index].get("role") != "agent"
        ):
            self.render_messages()
            return
        doc = self.message_stream.document()
        if anchor > doc.characterCount():
            self.render_messages()
            return
        raw_text = self.display_messages[index].get("text", "")
        text_css, muted_css, code_bg, border_css, accent_css = self._message_palette()
        stream_html = self.agent_block_html(
            raw_text, text_css, code_bg, border_css, muted_css, accent_css, caret=True
        )
        scrollbar = self.message_stream.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 8
        stick_to_bottom = self.should_scroll_to_bottom(at_bottom)
        prev_value = scrollbar.value()
        cursor = QTextCursor(doc)
        cursor.beginEditBlock()
        cursor.setPosition(anchor)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        # Keep the streamed block isolated so tokens never reflow onto the
        # preceding status / user line.
        cursor.setBlockFormat(QTextBlockFormat())
        cursor.insertHtml(stream_html)
        cursor.endEditBlock()
        self._last_render_at = time.monotonic()
        if stick_to_bottom:
            self.schedule_scroll_to_bottom()
        else:
            scrollbar.setValue(min(prev_value, scrollbar.maximum()))
        self.update_scroll_bottom_button()

    # --------------------------------------------------------------- render
    def render_messages(self):
        self._render_dirty = False
        self.reset_user_bubble_images()
        self._code_blocks = {}
        self._code_counter = 0
        fs = getattr(self, "font_scale", 1.0)
        label_px = max(1, int(round(10 * fs)))
        empty_px = max(1, int(round(14 * fs)))
        theme = self.model.themes[self.model.theme_key]
        accent = theme.accent
        accent_css = self.css_rgb(self.softer(accent))
        text_css = self.css_rgb((229, 232, 238))
        muted_css = self.css_rgb((154, 161, 173))
        faint_css = self.css_rgb((112, 120, 134))
        user_bg_rgba = (45, 53, 74, 238)
        user_bg = self.css_rgba(user_bg_rgba[:3], user_bg_rgba[3])
        agent_bg = self.css_rgba((18, 20, 25), 230)
        tool_bg = self.css_rgb((18, 21, 27))
        code_bg = self.css_rgb((7, 9, 13))
        border_css = self.css_rgb((62, 70, 86))
        tool_border_css = self.css_rgb((45, 52, 65))
        err_css = self.css_rgb((226, 122, 122))
        ok_css = self.css_rgb((86, 188, 154))

        scrollbar = self.message_stream.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 8
        stick_to_bottom = self.should_scroll_to_bottom(at_bottom)
        prev_value = scrollbar.value()

        if not self.display_messages:
            self._stream_incremental_ready = False
            self._stream_anchor = None
            self._welcome_suggestions = {}
            suggestions = [
                "\u89e3\u91ca\u8fd9\u6bb5\u4ee3\u7801\u7684\u4f5c\u7528",
                "\u5e2e\u6211\u5b9a\u4f4d\u5e76\u4fee\u590d\u8fd9\u4e2a\u62a5\u9519",
                "\u4e3a\u8fd9\u4e2a\u51fd\u6570\u7f16\u5199\u5355\u5143\u6d4b\u8bd5",
                "\u628a\u8fd9\u6bb5\u4ee3\u7801\u91cd\u6784\u5f97\u66f4\u6e05\u6670",
            ]
            suggestion_pairs = []
            for sidx, stext in enumerate(suggestions):
                sid = str(sidx)
                self._welcome_suggestions[sid] = stext
                suggestion_pairs.append((sid, stext))
            self.message_stream.setHtml(welcome_html(suggestion_pairs, text_css, faint_css, tool_bg, border_css, fs, empty_px))
            return

        run_collapsed = {}
        for entry in self.display_messages:
            if entry.get("role") == "run_summary":
                run_collapsed[entry.get("run")] = entry.get("collapsed", True)

        blocks = []
        stream_block_pos = None
        # Spinner/activity now render in the dedicated status-label widget, so
        # they are no longer injected inline (which previously merged onto the
        # streamed answer line). Keep this empty.
        activity_html = ""
        activity_inserted = False
        for index, item in enumerate(self.display_messages):
            role = item.get("role", "system")
            raw_text = item.get("text", "")
            if getattr(self, "transcript_mode", False) and role in {
                "reasoning", "tool", "tool_group", "run_summary", "system", "local_output"
            }:
                continue
            if role == "user":
                body = self.message_markdown_html(raw_text, text_css, code_bg, border_css, muted_css)
                blocks.append(
                    self.user_bubble_image_html(body, user_bg_rgba, text_css, "18px 4px 10px 0", raw_text)
                )
            elif role == "agent":
                is_live_stream = (
                    getattr(self, "pi_running", False)
                    and index == getattr(self, "active_agent_index", None)
                    and index == getattr(self, "_live_stream_index", None)
                )
                show_caret = is_live_stream or (
                    getattr(self, "pi_running", False)
                    and index == getattr(self, "active_agent_index", None)
                    and index != getattr(self, "_finished_live_stream_index", None)
                )
                if is_live_stream:
                    if activity_html and not activity_inserted:
                        blocks.append(activity_html)
                        activity_inserted = True
                    stream_block_pos = len(blocks)
                blocks.append(
                    self.agent_block_html(
                        raw_text, text_css, code_bg, border_css, muted_css, accent_css, caret=show_caret
                    )
                )
            elif role == "local_output":
                label = item.get("label") or "\u8f93\u51fa"
                body = self.message_markdown_html(raw_text, text_css, code_bg, border_css, muted_css)
                blocks.append(local_output_html(label, body, faint_css, text_css, label_px))
            elif role == "reasoning":
                is_active = (
                    index == getattr(self, "active_reasoning_index", None)
                    and getattr(self, "pi_running", False)
                )
                collapsed = item.get("collapsed", True) and not is_active
                arrow = "\u25be" if not collapsed else "\u25b8"
                header = (
                    f'<a href="tool-toggle:{index}" style="text-decoration:none; color:{faint_css}; '
                    f'font-family:Consolas,monospace; font-size:0.86em;">'
                    f'{arrow} \U0001f4ad \u601d\u8003</a>'
                )
                if collapsed:
                    summary = html.escape(self.collapsed_tool_summary(raw_text))
                    inner = (
                        f'<div style="color:{faint_css}; font-size:0.82em; margin-top:3px; '
                        f'font-style:italic;">{summary}</div>'
                        if summary
                        else ""
                    )
                else:
                    body = self.message_markdown_html(raw_text, faint_css, code_bg, border_css, muted_css)
                    inner = f'<div style="color:{faint_css}; font-style:italic; line-height:1.6;">{body}</div>'
                    if is_active:
                        inner += f'<span style="color:{accent_css};">\u2588</span>'
                blocks.append(
                    f'<div style="margin:10px 0; border-left:2px solid {border_css}; '
                    f'padding:2px 0 2px 10px;">{header}{inner}</div>'
                )
            elif role == "tool":
                if run_collapsed.get(item.get("run")):
                    continue
                collapsed = item.get("collapsed", True)
                status = item.get("tool_status") or "\u5b8c\u6210"
                tool_name = item.get("tool_name") or "\u5de5\u5177"
                is_error = item.get("is_error", False)
                arrow = "\u25be" if not collapsed else "\u25b8"
                dot = err_css if is_error else (accent_css if status == "\u8fd0\u884c\u4e2d" else ok_css)
                header = (
                    f'<a href="tool-toggle:{index}" style="text-decoration:none; color:{muted_css}; '
                    f'font-family:Consolas,monospace; font-size:0.9em;">'
                    f'{arrow} <span style="color:{dot};">\u25cf</span> {html.escape(str(tool_name))} \u00b7 {status}</a>'
                )
                if collapsed:
                    summary = item.get("summary")
                    if summary is None:
                        summary = self.collapsed_tool_summary(raw_text)
                    summary = html.escape(summary or "")
                    inner = (
                        f'<div style="color:{faint_css}; font-size:0.85em; margin-top:3px; '
                        f'font-family:Consolas,monospace;">{summary}</div>'
                        if summary
                        else ""
                    )
                else:
                    inner = self.message_markdown_html(raw_text, text_css, code_bg, border_css, muted_css)
                blocks.append(
                    f'<div style="margin:12px 8% 12px 0; background:{tool_bg}; '
                    f'border:1px solid {tool_border_css}; border-radius:10px; padding:8px 12px;">'
                    f'{header}{inner}</div>'
                )
            elif role == "tool_group":
                steps = item.get("steps") or []
                running = item.get("running", False)
                collapsed = item.get("collapsed", True)
                step_count = len(steps)
                any_error = any(s.get("is_error") for s in steps)
                arrow = "\u25be" if not collapsed else "\u25b8"
                if running:
                    count_text = f" \u00b7 {step_count} \u4e2a\u6b65\u9aa4" if step_count else ""
                    head_label = (
                        f'<span style="color:{accent_css};">\u25cf</span> '
                        f'\u6b63\u5728\u6267\u884c\u5de5\u5177{count_text}'
                    )
                else:
                    elapsed = item.get("elapsed")
                    if isinstance(elapsed, (int, float)) and elapsed >= 0:
                        if elapsed < 60:
                            elapsed_text = f"{elapsed:.1f}s"
                        else:
                            elapsed_text = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
                    else:
                        elapsed_text = "\u2014"
                    detail = f" \u00b7 {step_count} \u4e2a\u6b65\u9aa4" if step_count else ""
                    if any_error:
                        head_label = (
                            f'<span style="color:{err_css};">!</span> '
                            f'\u8fd0\u884c\u5f02\u5e38 {elapsed_text}{detail}'
                        )
                    else:
                        head_label = (
                            f'<span style="color:{ok_css};">\u2713</span> '
                            f'\u5df2\u5904\u7406 {elapsed_text}{detail}'
                        )
                header = (
                    f'<a href="tool-toggle:{index}" style="text-decoration:none; color:{muted_css}; '
                    f'font-family:Consolas,monospace; font-size:0.9em;">{arrow} {head_label}</a>'
                )
                inner = ""
                if not collapsed and steps:
                    rows = []
                    for step_index, step in enumerate(steps):
                        s_status = step.get("tool_status") or "\u5b8c\u6210"
                        s_name = step.get("tool_name") or "tool"
                        s_error = step.get("is_error", False)
                        s_collapsed = step.get("collapsed", True)
                        s_arrow = "\u25be" if not s_collapsed else "\u25b8"
                        s_dot = err_css if s_error else (accent_css if s_status == "\u8fd0\u884c\u4e2d" else ok_css)
                        s_header = (
                            f'<a href="runstep-toggle:{index}:{step_index}" style="text-decoration:none; '
                            f'color:{muted_css}; font-family:Consolas,monospace; font-size:0.86em;">'
                            f'{s_arrow} <span style="color:{s_dot};">\u25cf</span> '
                            f'{html.escape(str(s_name))} \u00b7 {s_status}</a>'
                        )
                        if s_collapsed:
                            s_sum = html.escape(step.get("summary") or "")
                            s_inner = (
                                f'<div style="color:{faint_css}; font-size:0.82em; margin:2px 0 0 16px; '
                                f'font-family:Consolas,monospace;">{s_sum}</div>'
                                if s_sum
                                else ""
                            )
                        else:
                            s_inner = (
                                f'<div style="margin:2px 0 0 16px;">'
                                f'{self.message_markdown_html(step.get("text", ""), text_css, code_bg, border_css, muted_css)}</div>'
                            )
                        rows.append(
                            f'<div style="margin-top:6px; padding-top:6px; '
                            f'border-top:1px solid {border_css};">{s_header}{s_inner}</div>'
                        )
                    inner = "".join(rows)
                blocks.append(
                    f'<div style="margin:12px 8% 12px 0; background:{tool_bg}; '
                    f'border:1px solid {tool_border_css}; padding:8px 12px; '
                    f'border-radius:10px;">{header}{inner}</div>'
                )
            elif role == "run_summary":
                blocks.append(run_summary_html(index, item.get("elapsed"), item.get("tool_count") or 0, item.get("collapsed", True), faint_css))
            else:
                is_err = any(hint in raw_text for hint in self.ERROR_HINTS)
                color = err_css if is_err else faint_css
                blocks.append(system_line_html(self.inline_markdown_html(raw_text), color))

        if activity_html and not activity_inserted:
            blocks.append(activity_html)

        wrapper_open = (
            f'<div style="font-family:\'Segoe UI Variable Text\',\'Segoe UI\',\'Microsoft YaHei UI\',\'Microsoft YaHei\',sans-serif; '
            f'color:{text_css}; padding:4px 2px 18px 2px;">'
        )
        incremental = (
            stream_block_pos is not None and stream_block_pos == len(blocks) - 1
        )
        if incremental:
            # Render every earlier message as a static prefix, then remember the
            # boundary so streamed token updates rewrite only the trailing block.
            prefix_html = wrapper_open + "".join(blocks[:stream_block_pos])
            self.message_stream.setHtml(prefix_html)
            cursor = QTextCursor(self.message_stream.document())
            cursor.movePosition(QTextCursor.MoveOperation.End)
            # Begin the streamed answer on its own, format-reset block. Inserting
            # HTML at the end of a non-empty block makes Qt merge it onto the
            # previous line; a fresh block keeps the reply cleanly separated.
            cursor.insertBlock()
            cursor.setBlockFormat(QTextBlockFormat())
            self._stream_anchor = cursor.position()
            cursor.insertHtml(blocks[stream_block_pos])
            self._stream_incremental_ready = True
        else:
            document = wrapper_open + "".join(blocks) + "</div>"
            self.message_stream.setHtml(document)
            self._stream_incremental_ready = False
            self._stream_anchor = None
        scrollbar = self.message_stream.verticalScrollBar()
        if stick_to_bottom:
            self.schedule_scroll_to_bottom()
        else:
            scrollbar.setValue(min(prev_value, scrollbar.maximum()))
            self._force_scroll_to_bottom = False
        self.update_scroll_bottom_button()

    def is_message_stream_at_bottom(self, threshold=12):
        bar = self.message_stream.verticalScrollBar()
        return bar.maximum() <= 0 or bar.value() >= bar.maximum() - threshold

    def should_scroll_to_bottom(self, at_bottom=None):
        if at_bottom is None:
            at_bottom = self.is_message_stream_at_bottom()
        return bool(getattr(self, "_force_scroll_to_bottom", False) or getattr(self, "_stick_to_bottom", True) or at_bottom)

    def request_scroll_to_bottom(self, stick=True):
        self._force_scroll_to_bottom = True
        if stick:
            self._stick_to_bottom = True

    def schedule_scroll_to_bottom(self):
        self._force_scroll_to_bottom = False
        self._stick_to_bottom = True
        self._scroll_message_stream_to_bottom()
        QTimer.singleShot(0, self._scroll_message_stream_to_bottom)
        QTimer.singleShot(60, self._scroll_message_stream_to_bottom)
        QTimer.singleShot(180, self._scroll_message_stream_to_bottom)

    def _scroll_message_stream_to_bottom(self):
        if not (getattr(self, "_force_scroll_to_bottom", False) or getattr(self, "_stick_to_bottom", True)):
            self.update_scroll_bottom_button()
            return
        bar = self.message_stream.verticalScrollBar()
        self._auto_scrolling = True
        try:
            bar.setValue(bar.maximum())
            self._stick_to_bottom = True
            self._force_scroll_to_bottom = False
        finally:
            self._auto_scrolling = False
        self.update_scroll_bottom_button()

    def scroll_messages_to_bottom(self):
        # One-click jump to the very bottom. Snap now, then re-snap after
        # the event loop settles pending layout / image sizing (and any
        # text still streaming in) so we reliably land on the true bottom.
        self.request_scroll_to_bottom(stick=True)
        self.schedule_scroll_to_bottom()

    def handle_message_scroll_value_changed(self, _value=None):
        if not getattr(self, "_auto_scrolling", False):
            self._stick_to_bottom = self.is_message_stream_at_bottom()
            if self._stick_to_bottom:
                self._force_scroll_to_bottom = False
        self.update_scroll_bottom_button()

    def handle_message_scroll_range_changed(self, _minimum=None, _maximum=None):
        if getattr(self, "_force_scroll_to_bottom", False) or getattr(self, "_stick_to_bottom", True):
            self.schedule_scroll_to_bottom()
        else:
            self.update_scroll_bottom_button()

    def update_scroll_bottom_button(self):
        btn = getattr(self, "scroll_bottom_btn", None)
        if btn is None:
            return
        bar = self.message_stream.verticalScrollBar()
        if bar.maximum() <= 0 or bar.value() >= bar.maximum() - 8:
            btn.hide()
            return
        viewport = self.message_stream.viewport()
        btn.move(viewport.width() - btn.width() - 14, viewport.height() - btn.height() - 14)
        btn.show()
        btn.raise_()

    AGENT_FONT_FAMILIES = [
        "Segoe UI Variable Text",
        "Segoe UI",
        "Microsoft YaHei UI",
        "Microsoft YaHei",
    ]

    def _build_message_font(self, size_pt):
        font = QFont()
        try:
            font.setFamilies(self.AGENT_FONT_FAMILIES)
        except Exception:
            font.setFamily("Segoe UI")
        font.setPointSizeF(size_pt)
        font.setWeight(QFont.Weight.Normal)
        try:
            font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
            font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        except Exception:
            pass
        return font

    def apply_message_font(self):
        base = getattr(self, "_base_message_pt", None)
        if base is None or base <= 0:
            base = self.message_stream.font().pointSizeF()
            if base <= 0:
                base = 12.0
            self._base_message_pt = base
        size = base * getattr(self, "font_scale", 1.0)
        self.message_stream.setFont(self._build_message_font(size))
        prompt = getattr(self, "prompt_input", None)
        if prompt is not None:
            # Input text uses the exact same size/family as the messages.
            prompt.setFont(self._build_message_font(size))

    def adjust_font_scale(self, delta):
        scale = round(getattr(self, "font_scale", 1.0) + delta, 2)
        self.font_scale = max(0.8, min(2.4, scale))
        self.apply_message_font()
        self.render_messages()
        self.flash_status(f"\u5b57\u53f7 {int(round(self.font_scale * 100))}%")

    def reset_font_scale(self):
        self.font_scale = 1.1
        self.apply_message_font()
        self.render_messages()
        self.flash_status("\u5b57\u53f7 110%")

    def collapse_all_sections(self):
        any_expanded = False
        for entry in self.display_messages:
            erole = entry.get("role")
            if erole in {"tool", "reasoning", "run_summary", "tool_group"} and not entry.get("collapsed", True):
                any_expanded = True
                break
            if erole == "tool_group" and any(not s.get("collapsed", True) for s in entry.get("steps", [])):
                any_expanded = True
                break
        collapse = any_expanded
        for entry in self.display_messages:
            erole = entry.get("role")
            if erole in {"tool", "reasoning", "run_summary", "tool_group"}:
                entry["collapsed"] = collapse
                if erole == "tool_group":
                    for step in entry.get("steps", []):
                        step["collapsed"] = collapse
        btn = getattr(self, "collapse_all_btn", None)
        if btn is not None:
            btn.setText("\u5c55\u5f00\u5168\u90e8" if collapse else "\u6298\u53e0\u5168\u90e8")
        self.render_messages()

    def toggle_transcript_mode(self):
        self.transcript_mode = not getattr(self, "transcript_mode", False)
        btn = getattr(self, "transcript_btn", None)
        if btn is not None:
            btn.setChecked(self.transcript_mode)
        self.flash_status(
            "\u7cbe\u7b80\u89c6\u56fe\uff1a\u4ec5\u663e\u793a\u5bf9\u8bdd" if self.transcript_mode else "\u5b8c\u6574\u89c6\u56fe"
        )
        self.render_messages()

    @staticmethod
    def softer(accent):
        return (
            int(accent[0] + (236 - accent[0]) * 0.30),
            int(accent[1] + (239 - accent[1]) * 0.30),
            int(accent[2] + (245 - accent[2]) * 0.30),
        )
