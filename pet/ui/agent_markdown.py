import html
import re


HL_KEYWORD = "#c678dd"
HL_BUILTIN = "#56b6c2"
HL_STRING = "#98c379"
HL_NUMBER = "#d19a66"
HL_COMMENT = "#7f848e"
HL_FUNC = "#61afef"

KEYWORDS = {
    "def", "class", "return", "if", "elif", "else", "for", "while", "in", "is",
    "not", "and", "or", "import", "from", "as", "with", "try", "except",
    "finally", "raise", "pass", "break", "continue", "lambda", "yield", "global",
    "nonlocal", "assert", "del", "async", "await", "None", "True", "False",
    "function", "var", "let", "const", "new", "this", "typeof", "instanceof",
    "throw", "catch", "switch", "case", "default", "extends", "super", "export",
    "void", "delete", "of", "null", "undefined", "true", "false", "do",
}
BUILTINS = {
    "print", "len", "range", "int", "str", "float", "list", "dict", "set",
    "tuple", "bool", "open", "isinstance", "enumerate", "zip", "map", "filter",
    "sum", "min", "max", "abs", "sorted", "type", "self", "cls", "console",
    "Math", "JSON", "Object", "Array",
}

# Language-aware keyword/builtin sets for the dependency-free fallback highlighter.
PY_KEYWORDS = {
    "def", "class", "return", "if", "elif", "else", "for", "while", "in", "is",
    "not", "and", "or", "import", "from", "as", "with", "try", "except",
    "finally", "raise", "pass", "break", "continue", "lambda", "yield", "global",
    "nonlocal", "assert", "del", "async", "await", "None", "True", "False",
}
JS_KEYWORDS = {
    "function", "var", "let", "const", "new", "this", "typeof", "instanceof",
    "throw", "catch", "switch", "case", "default", "extends", "super", "export",
    "import", "from", "as", "void", "delete", "of", "null", "undefined", "true",
    "false", "do", "return", "if", "else", "for", "while", "in", "class", "try",
    "finally", "async", "await", "yield", "break", "continue",
}
TS_KEYWORDS = JS_KEYWORDS | {
    "interface", "type", "enum", "implements", "namespace", "declare",
    "readonly", "public", "private", "protected", "abstract", "keyof",
    "infer", "is", "satisfies",
}
SHELL_KEYWORDS = {
    "if", "then", "fi", "else", "elif", "for", "do", "done", "while", "until",
    "case", "esac", "function", "in", "return", "export", "local", "set",
    "unset", "source", "alias",
}
SQL_KEYWORDS = {
    "select", "from", "where", "insert", "into", "values", "update", "set",
    "delete", "create", "table", "drop", "alter", "add", "column", "join",
    "left", "right", "inner", "outer", "full", "cross", "on", "using", "group",
    "by", "order", "having", "limit", "offset", "as", "and", "or", "not",
    "null", "is", "in", "like", "between", "distinct", "union", "all", "case",
    "when", "then", "else", "end", "asc", "desc", "primary", "key", "foreign",
    "references", "default", "index", "view", "with",
}
LANG_KEYWORDS = {
    "python": PY_KEYWORDS,
    "javascript": JS_KEYWORDS,
    "typescript": TS_KEYWORDS,
    "bash": SHELL_KEYWORDS,
    "sql": SQL_KEYWORDS,
}
LANG_BUILTINS = {
    "python": {
        "print", "len", "range", "int", "str", "float", "list", "dict", "set",
        "tuple", "bool", "open", "isinstance", "enumerate", "zip", "map",
        "filter", "sum", "min", "max", "abs", "sorted", "type", "self", "cls",
    },
    "javascript": {
        "console", "Math", "JSON", "Object", "Array", "String", "Number",
        "Boolean", "Promise", "document", "window", "require", "module", "process",
    },
    "typescript": {
        "console", "Math", "JSON", "Object", "Array", "String", "Number",
        "Boolean", "Promise", "Record", "Partial", "Readonly", "Map", "Set",
    },
    "bash": {
        "echo", "cd", "ls", "cat", "grep", "sed", "awk", "cp", "mv", "rm",
        "mkdir", "pwd", "exit", "read", "printf",
    },
}
_LANG_ALIASES = {
    "py": "python", "python3": "python",
    "js": "javascript", "jsx": "javascript", "mjs": "javascript",
    "cjs": "javascript", "node": "javascript",
    "ts": "typescript", "tsx": "typescript",
    "sh": "bash", "shell": "bash", "zsh": "bash",
    "console": "bash", "shell-session": "bash",
}

_TOKEN_RE = re.compile(
    r"(?P<bcomment>/[*](?s:.*?)[*]/)"
    r"|(?P<comment>#.*|//.*)"
    r'|(?P<string>"""(?s:.*?)"""|' + r"'''(?s:.*?)'''" + r'|"[^"]*"|' + r"'[^']*'" + r'|`[^`]*`)'
    r"|(?P<number>[0-9][0-9_]*[.]?[0-9]*)"
    r"|(?P<decorator>@[A-Za-z_][A-Za-z0-9_.]*)"
    r"|(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?P<ws>\s+)"
    r"|(?P<other>.)"
)


def _resolve_lang(lang):
    key = (lang or "").strip().lower()
    return _LANG_ALIASES.get(key, key)


def highlight_code(code, lang=None):
    resolved = _resolve_lang(lang)
    keywords = LANG_KEYWORDS.get(resolved, KEYWORDS)
    builtins = LANG_BUILTINS.get(resolved, BUILTINS)
    case_insensitive = resolved == "sql"
    is_json = resolved in {"json", "json5", "jsonc"}
    out = []
    length = len(code)
    for m in _TOKEN_RE.finditer(code):
        kind = m.lastgroup
        text = m.group()
        esc = html.escape(text)
        if kind in ("comment", "bcomment"):
            out.append('<span style="color:' + HL_COMMENT + '; font-style:italic;">' + esc + '</span>')
        elif kind == "string":
            if is_json:
                nxt = m.end()
                while nxt < length and code[nxt] in " \t":
                    nxt += 1
                if nxt < length and code[nxt] == ":":
                    out.append('<span style="color:' + HL_FUNC + ';">' + esc + '</span>')
                    continue
            out.append('<span style="color:' + HL_STRING + ';">' + esc + '</span>')
        elif kind == "number":
            out.append('<span style="color:' + HL_NUMBER + ';">' + esc + '</span>')
        elif kind == "decorator":
            out.append('<span style="color:' + HL_FUNC + ';">' + esc + '</span>')
        elif kind == "name":
            probe = text.lower() if case_insensitive else text
            if probe in keywords:
                out.append('<span style="color:' + HL_KEYWORD + ';">' + esc + '</span>')
            elif probe in builtins:
                out.append('<span style="color:' + HL_BUILTIN + ';">' + esc + '</span>')
            else:
                nxt = m.end()
                while nxt < length and code[nxt] in " \t":
                    nxt += 1
                if nxt < length and code[nxt] == "(":
                    out.append('<span style="color:' + HL_FUNC + ';">' + esc + '</span>')
                else:
                    out.append(esc)
        else:
            out.append(esc)
    return "".join(out)


try:
    from pygments import highlight as _pyg_highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.util import ClassNotFound

    _PYG_FORMATTER = HtmlFormatter(noclasses=True, nowrap=True, style="monokai")
    _HAS_PYGMENTS = True
except Exception:  # pragma: no cover - Pygments is an optional dependency
    _HAS_PYGMENTS = False


def highlight_code_pygments(code, lang):
    """Pygments-highlighted inline HTML when available, else None (use fallback)."""
    if not _HAS_PYGMENTS:
        return None
    try:
        if lang:
            try:
                lexer = get_lexer_by_name(lang, stripnl=False)
            except ClassNotFound:
                lexer = guess_lexer(code)
        else:
            lexer = guess_lexer(code)
        return _pyg_highlight(code, lexer, _PYG_FORMATTER).strip("\n")
    except Exception:
        return None
