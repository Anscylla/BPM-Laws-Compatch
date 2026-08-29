"""Show Laws+ lines (with block context) that reference Laws+-exclusive ids and are missing in BPM."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conflicts import BPM, LP, VAN, bpm, lp, van, KEY

lp_keys = {k for _, k in lp}; bpm_keys = {k for _, k in bpm}; van_keys = {k for _, k in van}
EXCL = sorted(k for k in lp_keys - van_keys - bpm_keys if len(k) > 4)
PAT = re.compile(r'\b(' + '|'.join(map(re.escape, EXCL)) + r')\b')


def strip_c(line):
    q = False; out = ''
    for ch in line:
        if ch == '"': q = not q
        if ch == '#' and not q: break
        out += ch
    return out


def blocks(path):
    try:
        txt = open(path, encoding='utf-8-sig', errors='replace').read().replace('\r', '')
    except Exception:
        return {}
    out, depth, cur, acc = {}, 0, None, []
    for line in txt.split('\n'):
        s = strip_c(line).strip()
        if depth == 0:
            m = KEY.match(s)
            if m: cur, acc = m.group('key'), []
        if cur is not None: acc.append(line)
        d0 = depth
        depth += strip_c(line).count('{') - strip_c(line).count('}')
        if depth < 0: depth = 0
        if cur is not None and d0 > 0 and depth == 0:
            out.setdefault(cur, []).extend(acc); cur = None
    return out


CACHE = {}
def get(root, d, fn):
    p = os.path.join(root, d.replace('/', os.sep), fn)
    if p not in CACHE: CACHE[p] = blocks(p)
    return CACHE[p]


target_dirs = sys.argv[1:] or ['common/parties']
for (d, k) in sorted(set(bpm) & set(lp)):
    if d not in target_dirs: continue
    lplines, bpmlines = [], []
    for fn, _ in lp[(d, k)]: lplines += get(LP, d, fn).get(k, [])
    for fn, _ in bpm[(d, k)]: bpmlines += get(BPM, d, fn).get(k, [])
    bpmtxt = '\n'.join(bpmlines)
    miss = sorted(set(PAT.findall('\n'.join(lplines))) - set(PAT.findall(bpmtxt)))
    if not miss: continue
    print(f'\n=========== {d}/{k}   [brakuje: {", ".join(miss)}]')
    mp = re.compile(r'\b(' + '|'.join(map(re.escape, miss)) + r')\b')
    # print path of enclosing blocks for each hit
    stack = []
    depth = 0
    for line in lplines:
        s = strip_c(line).strip()
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{', s)
        if mp.search(strip_c(line)):
            print(f'   [{" > ".join(stack) or "ROOT"}]  {line.strip()}')
        if m and strip_c(line).count('{') > strip_c(line).count('}'):
            stack.append(m.group(1))
        depth_before = depth
        depth += strip_c(line).count('{') - strip_c(line).count('}')
        while len(stack) > max(depth - 1, 0):
            stack.pop()
