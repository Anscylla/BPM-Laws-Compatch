"""Small Paradox-script utilities: brace-accurate block extraction and patching."""
import os, re

TOPRE = re.compile(r'^(?:REPLACE:|INJECT:|TRY_REPLACE:|TRY_INJECT:|REPLACE_OR_CREATE:|INJECT_OR_CREATE:)?'
                   r'(?P<key>[A-Za-z_][A-Za-z0-9_.\-]*)\s*=\s*\{')


def strip_c(line):
    q = False
    out = ''
    for ch in line:
        if ch == '"':
            q = not q
        if ch == '#' and not q:
            break
        out += ch
    return out


def read(p):
    return open(p, encoding='utf-8-sig', errors='replace').read().replace('\r', '')


def find_top(text, key):
    """Return (start_line, end_line) inclusive for top-level `key = { ... }`, else None."""
    lines = text.split('\n')
    depth = 0
    for i, line in enumerate(lines):
        s = strip_c(line).strip()
        if depth == 0:
            m = TOPRE.match(s)
            if m and m.group('key') == key:
                d = 0
                for j in range(i, len(lines)):
                    d += strip_c(lines[j]).count('{') - strip_c(lines[j]).count('}')
                    if d == 0:
                        return i, j
        depth += strip_c(line).count('{') - strip_c(line).count('}')
        if depth < 0:
            depth = 0
    return None


def get_top(text, key):
    r = find_top(text, key)
    if not r:
        return None
    return '\n'.join(text.split('\n')[r[0]:r[1] + 1])


def find_law(root, key, sub='common/laws'):
    """-> (filename, body) for the first file in `root/sub` defining `key`."""
    base = os.path.join(root, *sub.split('/'))
    if not os.path.isdir(base):
        return None, None
    for fn in sorted(os.listdir(base)):
        if not fn.endswith('.txt'):
            continue
        t = read(os.path.join(base, fn))
        b = get_top(t, key)
        if b:
            return fn, b
    return None, None


def find_sub(body, name, depth_wanted=1):
    """Find `name = {` at the given depth inside a top-level body.
    -> (start_line, end_line) inclusive, else None."""
    lines = body.split('\n')
    depth = 0
    for i, line in enumerate(lines):
        s = strip_c(line).strip()
        if depth == depth_wanted and re.match(r'^' + re.escape(name) + r'\s*=\s*\{', s):
            d = 0
            for j in range(i, len(lines)):
                d += strip_c(lines[j]).count('{') - strip_c(lines[j]).count('}')
                if d == 0:
                    return i, j
        depth += strip_c(line).count('{') - strip_c(line).count('}')
    return None


def append_in_sub(body, name, snippet, create=True):
    """Insert `snippet` just before the closing brace of sub-block `name`.
    If absent and create, append a new `name = { snippet }` before the entry's closing brace."""
    lines = body.split('\n')
    r = find_sub(body, name)
    add = snippet.split('\n')
    if r:
        s, e = r
        if s == e:  # one-liner  name = { a b }
            inner = re.sub(r'^(\s*' + re.escape(name) + r'\s*=\s*\{)(.*)\}\s*$', r'\2', lines[s]).strip()
            lines[s:s + 1] = [f'\t{name} = {{', f'\t\t{inner}'] + add + ['\t}']
        else:
            lines[e:e] = add
        return '\n'.join(lines)
    if not create:
        return body
    lines[-1:-1] = [f'\t{name} = {{'] + add + ['\t}']
    return '\n'.join(lines)


def mark_replace(body):
    first = body.split('\n')[0].lstrip('﻿')
    if not first.startswith(('REPLACE:', 'INJECT:', 'TRY_')):
        first = 'REPLACE:' + first
    return '\n'.join([first] + body.split('\n')[1:])
