"""Mini-shell for recon one-liners: ; && || | $(...) `...` ${V:-d} for/case/if/{}
groups, redirections, read/printf/unset/exit/command/which/getconf/toybox,
plus stdin text filters (grep/head/cut/tr/dd/sed/awk/sort/uniq/wc/tac).

Single commands dispatch to shell.handle_line so emulation stays in one place.
"""
import fnmatch
import re
import shlex

from . import shell as S


class _Exit(Exception):
    def __init__(self, code=0, out=""):
        super().__init__(code)
        self.code = code
        self.out = out


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


_KNOWN_CMDS = S.KNOWN_CMDS

KNOWN_FILES_EXTRA = {
    "/proc/self/status": (
        "Name:\tsh\nUmask:\t0022\nState:\tR (running)\n"
        "Cpus_allowed:\tffffffff\nCpus_allowed_list:\t0-31\n"
        "Mems_allowed:\t00000001\nMems_allowed_list:\t0\n"
    ),
    "/sys/devices/system/cpu/online": "0-31\n",
    "/sys/devices/system/cpu/possible": "0-31\n",
}

_KNOWN_FILES = {
    "/proc/version", "/proc/cpuinfo", "/proc/meminfo", "/proc/uptime",
    "/etc/os-release", "/etc/passwd", "/etc/hosts", "/etc/hostname",
    "/etc/shadow", "/etc/gshadow",
}
_KNOWN_FILES.update(KNOWN_FILES_EXTRA)


def _fake_file(path):
    if path in KNOWN_FILES_EXTRA:
        return KNOWN_FILES_EXTRA[path]
    if path == "/proc/version":
        return ("Linux version 6.8.0-41-generic (buildd@lcy02-amd64-101) "
                "#41-Ubuntu SMP PREEMPT_DYNAMIC Thu Aug  1 16:25:12 UTC 2026 (x86_64)\n")
    if path == "/proc/cpuinfo":
        return S.FAKE_CPUINFO.replace("\r\n", "\n")
    if path == "/proc/meminfo":
        return S.FAKE_MEMINFO.replace("\r\n", "\n")
    if path == "/proc/uptime":
        return S._fake_uptime() + "\n"
    if path == "/etc/os-release":
        return S.FAKE_OS_RELEASE.replace("\r\n", "\n")
    if path == "/etc/passwd":
        return S.FAKE_PASSWD.replace("\r\n", "\n")
    if path == "/etc/hosts":
        return S.FAKE_HOSTS.replace("\r\n", "\n")
    if path == "/etc/hostname":
        return "honey\n"
    return None


_BUILTINS = ("command ", "printf ", "getconf ", "read ", "unset ",
             "which ", "type ", "test ", "true", "false", "exit",
             "tee ", "return ", "export ")


def is_compound(line):
    s = line.strip()
    if "$(" in s or "`" in s:
        return True
    for tok in ("|", "&&", "||", ";"):
        if tok in s:
            return True
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", s):
        return True
    if s.startswith(("(", "{", "busybox ", "toybox ", "[ ", "test ",
                     "if ", "for ", "case ", "while ")):
        return True
    if s in ("true", "false") or s.startswith(("exit", "return ")):
        return True
    w = s.split()[0] if s.split() else ""
    if w in ("command", "printf", "getconf", "read", "unset", "which",
             "type", "tee", "export"):
        return True
    if re.search(r"\d?>/dev/null|2>&1|<\s*\S", s):
        return True
    return False


# ---------------- splitting ----------------

def _split_top(text, sep):
    parts, depth, q, cur, i = [], 0, None, "", 0
    while i < len(text):
        c = text[i]
        if q:
            cur += c
            if c == q:
                q = None
            i += 1
            continue
        if c in ("'", '"'):
            q, cur = c, cur + c
            i += 1
            continue
        if c == "$" and i + 1 < len(text) and text[i + 1] == "{":
            j = text.find("}", i + 2)
            j = len(text) - 1 if j < 0 else j
            cur += text[i:j + 1]
            i = j + 1
            continue
        if c == "$" and i + 1 < len(text) and text[i + 1] == "(":
            depth += 1
            cur += "$("
            i += 2
            continue
        if c in "({":
            depth += 1
            cur += c
            i += 1
            continue
        if c in ")}" and depth:
            depth -= 1
            cur += c
            i += 1
            continue
        if depth == 0 and text.startswith(sep, i):
            parts.append(cur)
            cur = ""
            i += len(sep)
            continue
        cur += c
        i += 1
    parts.append(cur)
    return parts


# ---------------- expansion ----------------

def _expand_vars(st, text):
    def sub(m):
        if m.group(1) is not None:  # ${...}
            inner = m.group(1)
            mm = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)((:-|:-|:?\+|:=)(.*))?$", inner, re.S)
            if not mm:
                return ""
            name, op, val = mm.group(1), mm.group(3), mm.group(4) or ""
            cur = st.env.get(name, "")
            if op in (":-", "-"):
                return cur if cur else val
            if op == "+":
                return val if cur else ""
            return cur
        name = m.group(2)
        if name == "?":
            return str(getattr(st, "_last_code", 0))
        if name == "$":
            return str(4000 + (hash(st.src_ip) % 50000))
        if name == "#":
            return "0"
        return st.env.get(name, "")
    return re.sub(r"\$\{([^}]*)\}|\$([A-Za-z_][A-Za-z0-9_?#$]*)", sub, text)


def _scan_balanced(text, i):
    """Scan a '$(...)' starting at i (text[i]=='$'). Return index just past
    the matching ')', case-arm aware (a ')' closing a case pattern does not
    pop). Falls back to len(text) on unbalanced input."""
    n = len(text)
    j, depth, q = i + 2, 1, None
    case_st = []
    while j < n and depth:
        c = text[j]
        if q:
            if c == q:
                q = None
            j += 1
            continue
        if c in ("'", '"'):
            q = c
            j += 1
            continue
        if c == "(":
            depth += 1
            j += 1
            continue
        if c == ")":
            if case_st and case_st[-1].get("armed") and depth == case_st[-1]["depth"]:
                case_st[-1]["armed"] = False
                j += 1
                continue
            depth -= 1
            j += 1
            continue
        # keyword tracking for case state (word-boundary aware, cheap)
        if (c == "c" and text.startswith("case ", j)
                and (j == 0 or not text[j - 1].isalnum())):
            case_st.append({"depth": depth, "armed": False, "seen_in": False})
            j += 5
            continue
        if (c == "i" and text.startswith("in", j)
                and (j == 0 or not text[j - 1].isalnum())
                and (j + 2 >= n or not text[j + 2].isalnum())
                and case_st and not case_st[-1]["seen_in"]
                and depth == case_st[-1]["depth"]):
            case_st[-1]["seen_in"] = True
            case_st[-1]["armed"] = True
            j += 2
            continue
        if text.startswith(";;", j):
            if case_st and depth == case_st[-1]["depth"]:
                case_st[-1]["armed"] = True
            j += 2
            continue
        if (c == "e" and text.startswith("esac", j)
                and (j == 0 or not text[j - 1].isalnum())
                and (j + 4 >= n or not text[j + 4].isalnum())):
            if case_st and depth == case_st[-1]["depth"]:
                case_st.pop()
            j += 4
            continue
        j += 1
    return j


def _cmdsubst(st, text):
    out, i = [], 0
    while i < len(text):
        if text[i] == "$" and i + 1 < len(text) and text[i + 1] == "(":
            j = _scan_balanced(text, i)
            inner = text[i + 2:j - 1] if j <= len(text) and text[j - 1:j] == ")" else text[i + 2:j]
            res, scode = run_script(st, inner, subshell=True)
            st._subst_code = scode
            out.append(res.replace("\r\n", "\n").strip())
            i = j
        elif text[i] == "`":
            j = text.find("`", i + 1)
            j = len(text) if j < 0 else j
            res, scode = run_script(st, text[i + 1:j], subshell=True)
            st._subst_code = scode
            out.append(res.replace("\r\n", "\n").strip())
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _words(s):
    try:
        return shlex.split(s, posix=True)
    except Exception:
        return s.split()


# ---------------- test/[ ----------------

def _test(st, toks):
    toks = [t for t in toks]
    neg = False
    if toks and toks[0] == "!":
        neg, toks = True, toks[1:]
    ok = False
    if len(toks) == 0:
        ok = False
    elif len(toks) == 1:
        ok = bool(toks[0])
    elif len(toks) == 2:
        a, b = toks
        if a == "-n":
            ok = bool(b)
        elif a == "-z":
            ok = not b
        elif a == "-f":
            ok = b in _KNOWN_FILES
        elif a in ("-d", "-e"):
            ok = b.rstrip("/") in S.FAKE_FILES or b in ("/", "/tmp", "/etc", "/proc", "/sys")
        elif a == "-s":
            c = _fake_file(b)
            ok = bool(c)
        elif a == "-x":
            ok = b in _KNOWN_FILES or "/" in b
    elif len(toks) == 3:
        a, op, b = toks
        if op in ("=", "=="):
            ok = fnmatch.fnmatch(a, b) if any(x in b for x in "*?[") else a == b
        elif op == "!=":
            ok = a != b
        elif op in ("-eq", "-ne", "-gt", "-lt", "-ge", "-le"):
            try:
                ai, bi = int(a), int(b)
                ok = {"-eq": ai == bi, "-ne": ai != bi, "-gt": ai > bi,
                      "-lt": ai < bi, "-ge": ai >= bi, "-le": ai <= bi}[op]
            except Exception:
                ok = False
    return (not ok) if neg else ok


# ---------------- main entry ----------------

def run_script(st, text, subshell=False):
    out_lines, code = [], 0
    try:
        nodes = _statements(text)
        first = True
        for idx, (node, sep) in enumerate(nodes):
            if not first:
                # separator between previous node and this one
                op = nodes[idx - 1][1]
                if op == "&&" and code != 0:
                    continue  # short-circuit: keep failing code
                if op == "||" and code == 0:
                    continue  # short-circuit: keep success code
            first = False
            o = ""
            try:
                o, code = _exec_node(st, node, "")
            except _Exit:
                raise  # outer handler merges this frame's out_lines once
            except (_Break, _Continue):
                code = 0
            if o:
                out_lines.append(o)
            st._last_code = code
    except _Exit as e:
        body = "\n".join(out_lines)
        combined = ((body + "\n" + e.out) if body else e.out).replace("\r\n", "\n")
        if subshell:
            return combined, e.code
        e.out = combined
        raise
    body = "\n".join(out_lines).replace("\r\n", "\n")
    return body, code


_KW_OPEN = ("if ", "for ", "while ", "case ", "{ ", "({")


def _is_word(text, n, i, word):
    if not text.startswith(word, i):
        return False
    j = i + len(word)
    if j < n and text[j].isalnum():
        return False
    if i > 0 and text[i - 1].isalnum() and word[0].isalnum():
        return False
    return True


def _statements(text):
    """Yield (node_text, separator_after) respecting keyword/paren depth."""
    nodes, cur, kw, stack, case_st, q, i = [], "", 0, [], [], None, 0
    n = len(text)
    while i < n:
        c = text[i]
        if q:
            cur += c
            if c == q:
                q = None
            i += 1
            continue
        if c in ("'", '"'):
            q, cur = c, cur + c
            i += 1
            continue
        if c == "$" and i + 1 < n and text[i + 1] == "{":
            j = text.find("}", i + 2)
            j = n - 1 if j < 0 else j
            cur += text[i:j + 1]
            i = j + 1
            continue
        if c == "$" and i + 1 < n and text[i + 1] == "(":
            stack.append("$(")
            cur += "$("
            i += 2
            continue
        if c == "(":
            stack.append("(")
            cur += c
            i += 1
            continue
        if c == "{" and (i == 0 or text[i - 1] in " ;\t\n("):
            stack.append("{")
            cur += c
            i += 1
            continue
        if c == ")":
            if (stack and stack[-1] in ("$(", "(")
                    and len(stack) > _case_floor(case_st)
                    and not (case_st and case_st[-1]["armed"]
                             and len(stack) == case_st[-1]["depth"])):
                stack.pop()
                cur += c
                i += 1
                continue
            if _case_arm_close(case_st, len(stack)):
                case_st[-1]["armed"] = False
                cur += c
                i += 1
                continue
            cur += c
            i += 1
            continue
        if c == "}" and stack and stack[-1] == "{":
            stack.pop()
            cur += c
            i += 1
            continue
        # keywords tracked at any paren depth; only separators are gated
        if _is_word(text, n, i, "case "):
            case_st.append({"depth": len(stack), "armed": False,
                            "seen_in": False})
            kw += 1
            cur += "case "
            i += 5
            continue
        matched = False
        for word, delta in (("if ", 1), ("for ", 1), ("while ", 1),
                            ("fi", -1), ("done", -1), ("esac", -1)):
            L = len(word)
            if not text.startswith(word, i):
                continue
            if word[-1].isalnum():
                if i + L < n and text[i + L].isalnum():
                    continue
                if i > 0 and text[i - 1].isalnum():
                    continue
                if delta < 0 and kw == 0:
                    continue
            if word == "esac" and case_st and len(stack) == case_st[-1]["depth"]:
                case_st.pop()
            kw += delta
            cur += word
            i += L
            matched = True
            break
        if matched:
            continue
        if (_is_word(text, n, i, "in") and case_st
                and not case_st[-1]["seen_in"]
                and len(stack) == case_st[-1]["depth"]):
            case_st[-1]["seen_in"] = True
            case_st[-1]["armed"] = True
            cur += "in"
            i += 2
            continue
        if text.startswith(";;", i):
            if case_st and len(stack) == case_st[-1]["depth"]:
                case_st[-1]["armed"] = True
            cur += ";;"
            i += 2
            continue
        if not stack and kw == 0:
            if text.startswith("&&", i):
                nodes.append((cur.strip(), "&&"))
                cur = ""
                i += 2
                continue
            if text.startswith("||", i):
                nodes.append((cur.strip(), "||"))
                cur = ""
                i += 2
                continue
            if c in ";\n":
                nodes.append((cur.strip(), ";"))
                cur = ""
                i += 1
                continue
        cur += c
        i += 1
    if cur.strip():
        nodes.append((cur.strip(), ";"))
    return [(t, s) for t, s in nodes if t]


def _case_floor(case_st):
    if case_st and case_st[-1]["armed"]:
        return case_st[-1]["depth"]
    return 0


def _case_arm_close(case_st, depth):
    return bool(case_st) and case_st[-1]["armed"] and depth == case_st[-1]["depth"]


def _exec_node(st, node, stdin):
    w = node.split()[0] if node.split() else ""
    if w == "if":
        return _exec_if(st, node)
    if w == "for":
        return _exec_for(st, node)
    if w == "case":
        return _exec_case(st, node)
    if node.startswith("{") and node.rstrip().endswith("}"):
        inner = node.strip()[1:node.rstrip().rfind("}")]
        return run_script(st, inner)
    return _run_pipeline(st, node, stdin)


def _split_if_parts(body):
    """Split if-body into [(cond, chunk)] for if/elif/else at depth 0."""
    parts, cur, cond, depth, q, i = [], "", None, 0, None, 0
    n = len(body)
    expect_cond = True
    while i < n:
        c = body[i]
        if q:
            cur += c
            if c == q:
                q = None
            i += 1
            continue
        if c in ("'", '"'):
            q, cur = c, cur + c
            i += 1
            continue
        if depth == 0:
            for kw in ("if ", "for ", "while ", "case "):
                if body.startswith(kw, i):
                    depth += 1
                    cur += kw
                    i += len(kw)
                    break
            else:
                if body.startswith("fi", i) and (i + 2 >= n or not body[i + 2].isalnum()):
                    depth -= 1
                    cur += "fi"
                    i += 2
                    continue
                rest = body[i:]
                if expect_cond and rest.startswith("then") and (len(rest) == 4 or not rest[4].isalnum()):
                    cond, cur, expect_cond = cur.strip(), "", False
                    i += 4
                    continue
                if not expect_cond and rest.startswith("elif ") :
                    parts.append((cond, cur))
                    cur, cond, expect_cond = "", rest[5:], True
                    i += 5
                    # read elif cond up to then handled by loop
                    tmp = ""
                    # re-scan: collect until 'then'
                    j, qq, dd = i, None, 0
                    buf = ""
                    while j < n:
                        cc = body[j]
                        if qq:
                            buf += cc
                            if cc == qq:
                                qq = None
                            j += 1
                            continue
                        if cc in ("'", '"'):
                            qq, buf = cc, buf + cc
                            j += 1
                            continue
                        if dd == 0 and body.startswith("then", j) and (j + 4 >= n or not body[j + 4].isalnum()):
                            break
                        buf += cc
                        j += 1
                    cond, cur, i = buf.strip(), "", j + 4
                    continue
                if not expect_cond and rest.startswith("else") and (len(rest) == 4 or not rest[4].isalnum()):
                    parts.append((cond, cur))
                    cond, cur = "true", ""
                    i += 4
                    continue
                cur += c
                i += 1
            continue
        cur += c
        i += 1
    parts.append((cond or "true", cur))
    return parts


def _exec_if(st, node):
    inner = node.strip()
    assert inner.startswith("if ")
    body = inner[3:].strip()
    if body.endswith("fi"):
        body = body[:-2]
    for cond, chunk in _split_if_parts(body):
        o, code = run_script(st, cond)
        if code == 0:
            return run_script(st, chunk)
    return "", 0


def _exec_for(st, node):
    m = re.match(r"for\s+(\w+)\s+in\s+(.*?);\s*do\s*(.*)\s*done\s*$", node, re.S)
    if not m:
        return "", 1
    var, wordstr, body = m.group(1), m.group(2), m.group(3)
    words = _words(_expand_vars(st, _cmdsubst(st, wordstr)))
    out, code = [], 0
    for w in words:
        st.env[var] = w
        try:
            o, code = run_script(st, body)
        except _Continue:
            continue
        except _Break:
            break
        if o:
            out.append(o)
    return "\n".join(out), code


def _exec_case(st, node):
    m = re.match(r"case\s+(.*?)\s+in\s+(.*)\s*esac\s*$", node, re.S)
    if not m:
        return "", 1
    word = _expand_vars(st, _cmdsubst(st, m.group(1).strip()))
    word = _strip_q(word)
    body = m.group(2)
    for arm in _split_top(body, ";;"):
        arm = arm.strip()
        if not arm:
            continue
        if ")" not in arm:
            continue
        pat, _, cmds = arm.partition(")")
        pats = [p.strip() for p in _split_top(pat, "|")]
        if any(fnmatch.fnmatch(word, _strip_q(p)) for p in pats):
            return run_script(st, cmds.strip())
    return "", 0


def _take_value(text):
    """Split 'VALUE rest...' -> (value, rest) with quote/$()-awareness.

    Returns (text, None) when there is no trailing command.
    """
    if text.startswith("$("):
        j = _scan_balanced(text, 0)
        if j < len(text) and text[j - 1:j] == ")":
            val = text[:j]
            tail = text[j:].strip()
            return (val, tail) if tail else (text, None)
        return text, None
    if text[:1] in ("'", '"'):
        q = text[0]
        j = text.find(q, 1)
        if j < 0:
            return text, None
        tail = text[j + 1:].strip()
        return (text[:j + 1], tail) if tail else (text, None)
    m = re.match(r"^(\S+)(?:\s+(.*))?$", text, re.S)
    if not m:
        return text, None
    if m.group(2) is None:
        return text, None
    return m.group(1), m.group(2)


def _strip_q(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


# ---------------- pipelines ----------------

def _run_pipeline(st, stmt, stdin):
    segs = _split_top(stmt, "|")
    if len(segs) == 1:
        return _run_single(st, stmt, stdin)
    data, code = stdin, 0
    try:
        for seg in segs:
            seg = seg.strip()
            if not seg:
                continue
            if _is_filter(seg):
                data, code = _run_filter(st, seg, data)
            else:
                data, code = _run_single(st, seg, data)
    except _Exit as e:
        e.out = (data + "\n" + e.out) if data else e.out
        raise
    return data, code


_FILTERS = ("grep", "head", "tr", "dd", "cut", "sed", "awk", "sort",
            "uniq", "wc", "tac", "tee")


def _is_filter(seg):
    toks = _words(seg)
    return bool(toks) and toks[0] in _FILTERS


def _strip_redirects(st, seg):
    """Remove /dev/null sinks + 2>&1 (global, safe anywhere).

    `< file` is extracted ONLY for structurally simple commands (no shell
    operators outside quotes/$()) — inside compound lines the `<` belongs
    to an inner command that handles it when it becomes a single node.
    Returns (cleaned, infile_or_None).
    """
    st._had_sink = bool(re.search(r"\s(\d*>>?&?\d*\s*/dev/null|2>&1|[12]?>\s*/dev/null)", seg))
    seg = re.sub(r"\s\d*>>?&?\d*\s*/dev/null", "", seg)
    seg = re.sub(r"\s2>&1", "", seg)
    seg = re.sub(r"\s[12]?>\s*/dev/null", "", seg)
    if _has_ops(seg):
        return seg.strip(), None
    m = re.search(r"<\s*(\S+)", seg)
    if m:
        return (seg[:m.start()] + seg[m.end():]).strip(), _strip_q(m.group(1))
    return seg.strip(), None


def _has_ops(seg):
    """True if ; && || | $() backticks or keywords appear outside quotes."""
    q, i = None, 0
    n = len(seg)
    while i < n:
        c = seg[i]
        if q:
            if c == q:
                q = None
            i += 1
            continue
        if c in ("'", '"'):
            q = c
            i += 1
            continue
        if c == "$" and i + 1 < n and seg[i + 1] in ("(", "{"):
            return True
        if c == "`":
            return True
        if c == "|":
            return True
        if seg.startswith("&&", i) or seg.startswith("||", i):
            return True
        if c == ";":
            return True
        i += 1
    head = seg.strip().split()[0] if seg.strip().split() else ""
    if head in ("if", "for", "while", "case", "{", "("):
        return True
    return False


def _run_filter(st, seg, stdin):
    seg, infile = _strip_redirects(st, seg)
    toks = _words(seg)
    cmd, args = toks[0], toks[1:]
    src = stdin
    if cmd == "tee":
        return src, 0
    nonflags = [a for a in args if not a.startswith("-") or a.startswith("/")]
    fop = None
    if cmd in ("grep", "sed", "awk"):
        # first non-flag is the pattern/program; a file follows only if
        # there is more than one non-flag operand containing a path
        cands = [a for a in nonflags if "/" in a]
        if len(nonflags) > 1 and cands:
            fop = cands[-1]
    else:
        for a in reversed(args):
            if a and not a.startswith("-"):
                fop = a
                break
        if fop and "/" not in fop:
            fop = None
    if fop and cmd != "grep":
            c = _fake_file(fop)
            if c is not None:
                src = c
            elif fop.startswith("/"):
                return f"{cmd}: {fop}: No such file or directory", 1
    lines = src.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]

    if cmd == "grep":
        pats = [a for a in args if not a.startswith("-") or a.startswith("/")]
        pat = pats[0] if pats else ""
        if pat.startswith("/") and pat.endswith("/") and len(pat) > 1:
            pat = pat[1:-1]
        flags = "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("/"))
        if fop and not fop.startswith("-"):
            c = _fake_file(fop)
            if c is not None:
                lines = [l for l in c.split("\n")]
                if lines and lines[-1] == "":
                    lines = lines[:-1]
            elif "/" in fop:
                return f"grep: {fop}: No such file or directory", 2
        try:
            rx = re.compile(pat, re.I if "i" in flags else 0)
        except Exception:
            return "", 2
        hits = [l for l in lines if rx.search(l)]
        if "q" in flags:
            return "", 0 if hits else 1
        if "c" in flags:
            return str(len(hits)), 0
        m = re.search(r"-m\s*(\d+)", seg)
        if not m:
            for a in args:
                if re.match(r"-m\d+", a):
                    m = re.match(r"-m(\d+)", a)
        if m:
            hits = hits[:int(m.group(1))]
        l_only = "l" in flags
        if l_only:
            return (fop or "(standard input)") if hits else "", 0 if hits else 1
        return "\n".join(hits), 0 if hits else 1
    if cmd == "head":
        m = re.search(r"-c\s*(\d+)", seg)
        if m:
            return src[:int(m.group(1))], 0
        n = 10
        m = re.search(r"-n\s*(\d+)", seg)
        if m:
            n = int(m.group(1))
        else:
            for a in args:
                if re.match(r"-\d+$", a):
                    n = int(a[1:])
        return "\n".join(lines[:n]), 0
    if cmd == "tr":
        m = re.search(r"-d\s+'([^']*)'|-d\s+\"([^\"]*)\"|-d\s+(\S+)", seg)
        charset = ""
        if m:
            charset = m.group(1) or m.group(2) or m.group(3) or ""
        charset = charset.replace("\\n", "\n").replace("\\t", "\t")
        return "".join(c for c in src if c not in charset), 0
    if cmd == "dd":
        bs, count = 512, 1
        m = re.search(r"bs=(\d+)", seg)
        if m:
            bs = int(m.group(1))
        m = re.search(r"count=(\d+)", seg)
        if m:
            count = int(m.group(1))
        return src[:bs * count], 0
    if cmd == "cut":
        d, flist = "\t", None
        m = re.search(r"-d\s*(\S)", seg)
        if m:
            d = m.group(1).strip("'\"")
        m = re.search(r"-f\s*([\d,\-]+)", seg)
        if m:
            flist = m.group(1)
        if not flist:
            return src, 0
        out = []
        for l in lines:
            f = l.split(d)
            sel = []
            for part in flist.split(","):
                if "-" in part:
                    a, b = part.split("-", 1)
                    a = int(a) - 1 if a else 0
                    b = int(b) if b else len(f)
                    sel.extend(f[a:b])
                else:
                    i = int(part) - 1
                    if 0 <= i < len(f):
                        sel.append(f[i])
            out.append(d.join(sel))
        return "\n".join(out), 0
    if cmd == "sed":
        exprs = []
        skip = False
        for a in args:
            if skip:
                skip = False
                continue
            if a in ("-e", "-n", "-r", "-E"):
                if a == "-e":
                    skip = True
                continue
            if a.startswith("-"):
                continue
            exprs.extend(a.split(";"))
        cur = list(lines)
        for e in exprs:
            e = e.strip()
            if not e:
                continue
            m = re.match(r"/(.*?)/d$", e)
            if m:
                try:
                    rx = re.compile(_posix(m.group(1)))
                    cur = [l for l in cur if not rx.search(l)]
                except Exception:
                    pass
                continue
            m = re.match(r"s(.)(.*?)\1(.*?)\1([g]*)$", e)
            if m:
                try:
                    rx = re.compile(_posix(m.group(2)))
                    cur = [rx.sub(m.group(3), l, count=0 if "g" in m.group(4) else 1) for l in cur]
                except Exception:
                    pass
        return "\n".join(cur), 0
    if cmd == "awk":
        prog = " ".join(args)
        if "Cpus_allowed_list" in prog:
            return "32", 0
        if "/sys/devices/system/cpu/online" in prog:
            return "0-31", 0
        fsep, a2 = None, list(args)
        while a2:
            a = a2.pop(0)
            if a == "-F" and a2:
                fsep = a2.pop(0)
            elif a.startswith("-F") and len(a) > 2:
                fsep = a[2:]
            elif a.startswith("-"):
                continue
            else:
                prog = a + (" " + " ".join(a2) if a2 else "")
                break
        if "BEGIN" in prog and "getline" not in prog and (len(lines) == 0 or not lines[0]):
            pass
        out = []
        for stmt in prog.split(";"):
            m = re.match(r"(?:/(.*?)/)?\s*\{\s*print\s+([^}]+)\}", stmt.strip())
            if not m:
                continue
            pat, expr = m.group(1), m.group(2)
            for l in lines:
                if pat:
                    try:
                        if not re.search(_posix(pat), l):
                            continue
                    except Exception:
                        continue
                f = l.split(fsep or None)
                def fld(t):
                    t = t.strip()
                    if t == "$0":
                        return l
                    mm = re.match(r"\$(\d+)", t)
                    if mm:
                        i = int(mm.group(1)) - 1
                        return f[i] if 0 <= i < len(f) else ""
                    return _strip_q(t)
                out.append(" ".join(fld(t) for t in expr.split(",")))
        return "\n".join(out), 0
    if cmd == "sort":
        u = any(a.startswith("-") and "u" in a for a in args)
        s = sorted(lines)
        if u:
            s = list(dict.fromkeys(s))
        return "\n".join(s), 0
    if cmd == "uniq":
        return "\n".join(l for i, l in enumerate(lines) if i == 0 or l != lines[i - 1]), 0
    if cmd == "wc":
        if "-c" in args:
            return str(len(src.encode())), 0
        if "-l" in args:
            return str(len(lines)), 0
        if "-w" in args:
            return str(sum(len(l.split()) for l in lines)), 0
        return f"{len(lines)} {sum(len(l.split()) for l in lines)} {len(src.encode())}", 0
    if cmd == "tac":
        return "\n".join(reversed(lines)), 0
    return src, 0


def _posix(pat):
    return (pat.replace("[[:space:]]", r"\s").replace("[[:digit:]]", r"\d")
               .replace("[[:alpha:]]", r"[A-Za-z]").replace("[[:alnum:]]", r"\w"))


# ---------------- single commands ----------------

def _run_single(st, stmt, stdin):
    stmt = stmt.strip()
    if not stmt:
        return "", 0
    if stmt.startswith("(") and stmt.endswith(")"):
        return run_script(st, stmt[1:-1], subshell=True)
    if stmt.startswith("{") and stmt.rstrip().endswith("}"):
        s2 = stmt.strip()
        return run_script(st, s2[1:s2.rfind("}")])
    if stmt.startswith("busybox ") or stmt.startswith("toybox "):
        stmt = stmt.split(None, 1)[1] if len(stmt.split(None, 1)) > 1 else ""
        stmt = stmt.strip()
    # input redirection for plain commands (cat < file, read < file)
    stmt, infile = _strip_redirects(st, stmt)
    if infile:
        c = _fake_file(infile)
        if c is None and infile.startswith("/"):
            if infile in ("/etc/shadow", "/etc/gshadow"):
                return f"bash: {infile}: Permission denied", 1
        st._redir_in = c or ""
    st._subst_code = 0
    # leading VAR= assignments (IFS=, LC_ALL=C, ...) — parsed UNEXPANDED so
    # that V=$(...) values containing spaces are not mistaken for commands
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", stmt, re.S)
        if not m:
            break
        rest = m.group(2)
        if rest[:1].isspace() or rest == "":
            st.env[m.group(1)] = ""
            stmt = rest.strip()
            if not stmt:
                return "", 0
            continue
        val, tail = _take_value(rest)
        if tail is None:
            break  # whole thing is one assignment -> handled below
        st.env[m.group(1)] = _strip_q(_expand_vars(st, _cmdsubst(st, val)))
        stmt = tail.strip()
        if not stmt:
            return "", st._subst_code if ("$(" in val or "`" in val) else 0
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", stmt, re.S)
    if m:
        rawval = m.group(2).strip()
        st.env[m.group(1)] = _strip_q(_expand_vars(st, _cmdsubst(st, rawval)))
        return "", st._subst_code if ("$(" in rawval or "`" in rawval) else 0
    stmt = _expand_vars(st, _cmdsubst(st, stmt))
    if stmt.startswith("busybox ") or stmt.startswith("toybox "):
        stmt = stmt.split(None, 1)[1] if len(stmt.split(None, 1)) > 1 else ""
        stmt = stmt.strip()
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", stmt, re.S)
        if not m:
            break
        rest = m.group(2).strip()
        val, tail = _take_value(rest)
        if tail is None:
            break  # whole thing is one assignment -> handled below
        st.env[m.group(1)] = _strip_q(_expand_vars(st, _cmdsubst(st, val)))
        stmt = tail.strip()
        if not stmt:
            return "", st._subst_code if ("$(" in val or "`" in val) else 0
    if stmt.startswith("export "):
        for chunk in _words(stmt[len("export "):]):
            if "=" in chunk:
                k, v = chunk.split("=", 1)
                st.env[k] = _strip_q(_expand_vars(st, _cmdsubst(st, v)))
        return "", 0
    if re.match(r"^(sh|bash|dash)\s+-c\s+", stmt):
        m = re.match(r"^(?:sh|bash|dash)\s+-c\s+(.*)$", stmt, re.S)
        inner = _strip_q(m.group(1).strip())
        return run_script(st, inner)
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", stmt, re.S)
    if m:
        rawval = m.group(2).strip()
        st.env[m.group(1)] = _strip_q(_expand_vars(st, _cmdsubst(st, rawval)))
        return "", st._subst_code if ("$(" in rawval or "`" in rawval) else 0
    if stmt in ("true", ":"):
        return "", 0
    if stmt == "false":
        return "", 1
    if stmt.startswith("exit"):
        code = 0
        mm = re.match(r"exit\s+(\d+)", stmt)
        if mm:
            code = int(mm.group(1))
        raise _Exit(code)
    if stmt == "break":
        raise _Break()
    if stmt == "continue":
        raise _Continue()
    if stmt.startswith("exec "):
        raise _Exit(0)
    if stmt.startswith("unset "):
        for v in _words(stmt[len("unset "):]):
            st.env.pop(v, None)
        return "", 0
    if stmt.startswith("test ") or (stmt.startswith("[ ") and stmt.rstrip().endswith("]")):
        inner = stmt[5:] if stmt.startswith("test ") else stmt[1:stmt.rstrip().rfind("]")]
        toks = _words(inner)
        ok = _test(st, [_expand_vars(st, _cmdsubst(st, t)) for t in toks])
        return "", 0 if ok else 1
    if stmt.startswith("command "):
        rest = _words(stmt[len("command "):])
        while rest and rest[0].startswith("-"):
            rest = rest[1:]
        if rest and rest[0] == "-v" :
            rest = rest[1:]
        if not rest:
            return "", 0
        name = rest[0]
        if name in _KNOWN_CMDS or "/" in name:
            return name if "/" in name else f"/usr/bin/{name}", 0
        return "", 1
    if stmt.startswith("which ") or stmt.startswith("type "):
        name = _words(stmt)[1] if len(_words(stmt)) > 1 else ""
        if name in _KNOWN_CMDS:
            return f"/usr/bin/{name}", 0
        return "", 1
    if stmt.startswith("getconf "):
        arg = _words(stmt)[1] if len(_words(stmt)) > 1 else ""
        if "NPROCESSORS" in arg:
            return "32", 0
        if arg == "PATH":
            return "/bin:/usr/bin", 0
        return "", 1
    if stmt.startswith("printf "):
        rest = stmt[len("printf "):].strip()
        try:
            fmt = _words(rest)[0]
        except Exception:
            return "", 1
        fmt = _strip_q(fmt)
        fmt = fmt.replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")
        vals = [_strip_q(x) for x in _words(rest)[1:]]
        out = []
        i, vi = 0, 0
        while i < len(fmt):
            if fmt[i] == "%" and i + 1 < len(fmt) and fmt[i + 1] in "sdrx":
                out.append(vals[vi] if vi < len(vals) else "")
                vi += 1
                i += 2
            else:
                out.append(fmt[i])
                i += 1
        return "".join(out).rstrip("\n"), 0
    if stmt.startswith("read "):
        rest = _words(stmt[len("read "):])
        names = [x for x in rest if not x.startswith("-")]
        data = stdin
        if not data and hasattr(st, "_redir_in"):
            data = st._redir_in or ""
            st._redir_in = ""
        line = data.split("\n")[0] if data else ""
        if not line:
            return "", 1
        parts = line.split()
        for i, nm in enumerate(names):
            if i < len(names) - 1:
                st.env[nm] = parts[i] if i < len(parts) else ""
            else:
                st.env[nm] = " ".join(parts[i:])
        return "", 0
    if stmt.split()[0] in ("cat",) and getattr(st, "_redir_in", ""):
        data = st._redir_in
        st._redir_in = ""
        if len(stmt.split()) == 1:
            return data.replace("\n", "\r\n").rstrip("\r\n"), 0
        out, _, _ = S.handle_simple(st, stmt)
        return _unwrap(st, out), 0
    out, _logged, _kind = S.handle_simple(st, stmt)
    body = _unwrap(st, out)
    code = 0
    if "command not found" in body or "No such file" in body:
        code = 127
    elif "Permission denied" in body:
        code = 126
    if code in (126, 127) and getattr(st, "_had_sink", False):
        body = ""
    return body.replace("\r\n", "\n"), code


def _unwrap(st, out):
    body = out
    if body.startswith("\r\n"):
        body = body[2:]
    suffix = "\r\n" + S.prompt(st)
    if body.endswith(suffix):
        body = body[:-len(suffix)]
    return body
