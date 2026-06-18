import html


def welcome_html(suggestions, text_css, faint_css, tool_bg, border_css, fs, empty_px):
    chips = []
    for sid, text in suggestions:
        chips.append(
            f'<div style="margin:6px 0;"><a href="suggest:{sid}" '
            f'style="text-decoration:none; color:{faint_css}; background:{tool_bg}; '
            f'border:1px solid {border_css}; border-radius:18px; padding:8px 16px;">'
            f'{html.escape(text)}</a></div>'
        )
    title_px = max(1, int(round(22 * fs)))
    hint_px = max(1, int(round(11 * fs)))
    return (
        f'<div style="margin-top:92px; text-align:center; color:{text_css};">'
        f'<div style="font-size:{title_px}px; font-weight:700; letter-spacing:0;">准备好了</div>'
        f'<div style="margin-top:8px; color:{faint_css}; font-size:{empty_px}px;">'
        f'输入任务，开始对话</div>'
        f'<div style="margin-top:18px;">{"".join(chips)}</div>'
        f'<div style="margin-top:20px; color:{faint_css}; font-size:{hint_px}px;">'
        f'Enter 发送 · Shift+Enter 换行 · ↑ 历史 · /help 命令</div>'
        f'</div>'
    )


def chat_bubble_html(body, side, bg, border_css, text_css, max_width, padding, line_height, margin):
    align = "right" if side == "right" else "left"
    return (
        f'<table width="100%" cellspacing="0" cellpadding="0" style="margin:{margin};">'
        f'<tr><td align="{align}">'
        f'<table cellspacing="0" cellpadding="0" style="max-width:{max_width};"><tr>'
        f'<td style="background:{bg}; border:1px solid {border_css}; border-radius:18px; '
        f'padding:{padding}; color:{text_css}; line-height:{line_height};">{body}</td>'
        f'</tr></table></td></tr></table>'
    )


def local_output_html(label, body, faint_css, text_css, label_px):
    return (
        f'<div style="margin:16px 0 4px 0; color:{faint_css}; font-size:{label_px}px; '
        f'font-weight:700; letter-spacing:0;">{html.escape(str(label))}</div>'
        f'<div style="color:{text_css}; line-height:1.6;">{body}</div>'
    )


def run_summary_html(index, elapsed, tool_count, collapsed, faint_css):
    if isinstance(elapsed, (int, float)) and elapsed >= 0:
        elapsed_text = f"{elapsed:.1f}s" if elapsed < 60 else f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
    else:
        elapsed_text = "—"
    arrow = "▸" if collapsed else "▾"
    detail = f" · {tool_count} 个步骤" if tool_count else ""
    return (
        f'<div style="margin:7px 2px 3px 2px;">'
        f'<a href="run-toggle:{index}" style="text-decoration:none; color:{faint_css}; '
        f'font-size:0.84em; letter-spacing:0;">'
        f'{arrow} ✓ 已处理 {elapsed_text}{detail}</a></div>'
    )


def system_line_html(body, color):
    return f'<div style="margin:9px 2px; color:{color}; font-size:0.86em;">{body}</div>'
