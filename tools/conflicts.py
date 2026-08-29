import os, re, sys, json
from collections import defaultdict

BPM = r"C:\Steam\steamapps\workshop\content\529340\2932134122"
LP  = r"C:\Steam\steamapps\workshop\content\529340\2941539986"
CP  = r"C:\Steam\steamapps\workshop\content\529340\3481491071"
VAN = r"C:\Steam\steamapps\common\Victoria 3\game"

KEY = re.compile(r'^(?P<mode>REPLACE:|INJECT:|TRY_REPLACE:|TRY_INJECT:|REPLACE_OR_CREATE:|INJECT_OR_CREATE:)?(?P<key>[A-Za-z_][A-Za-z0-9_.\-]*)\s*=\s*\{')

def toplevel_keys(path):
    """Return list of (key, mode) defined at brace depth 0."""
    out = []
    try:
        txt = open(path, encoding='utf-8-sig', errors='replace').read()
    except Exception:
        return out
    # strip comments
    lines = []
    for line in txt.split('\n'):
        q = False; buf = ''
        for ch in line:
            if ch == '"': q = not q
            if ch == '#' and not q: break
            buf += ch
        lines.append(buf)
    depth = 0
    for line in lines:
        s = line.strip()
        if depth == 0:
            m = KEY.match(s)
            if m:
                out.append((m.group('key'), (m.group('mode') or '').rstrip(':')))
        depth += line.count('{') - line.count('}')
        if depth < 0: depth = 0
    return out

def scan(root, subdirs=('common','events')):
    db = defaultdict(list)  # (reldir, key) -> [(filename, mode)]
    for sub in subdirs:
        base = os.path.join(root, sub)
        for dirpath, _, files in os.walk(base):
            reldir = os.path.relpath(dirpath, root).replace(chr(92),'/')
            for fn in files:
                if not fn.lower().endswith('.txt'): continue
                for key, mode in toplevel_keys(os.path.join(dirpath, fn)):
                    db[(reldir, key)].append((fn, mode))
    return db

bpm, lp, cp, van = scan(BPM), scan(LP), scan(CP), scan(VAN)

if __name__ == "__main__":
    conf = sorted(set(bpm) & set(lp))
    bydir = defaultdict(list)
    for d,k in conf: bydir[d].append(k)

    print("=== KONFLIKTY ENTRY-LEVEL BPM vs Laws+ (ta sama definicja w obu modach) ===")
    for d in sorted(bydir):
        ks = bydir[d]
        print(f"\n--- {d}  ({len(ks)} wpisów) ---")
        for k in sorted(ks):
            bf = bpm[(d,k)]; lf = lp[(d,k)]
            # winner = ASCII-latest filename
            allf = [(fn,'BPM',mo) for fn,mo in bf] + [(fn,'L+',mo) for fn,mo in lf]
            win = sorted(allf, key=lambda t: t[0])[-1]
            incp = 'CP' if (d,k) in cp else '  '
            print(f"  {incp} {k:<48} BPM:{','.join(f'{f}' for f,_ in bf):<40} L+:{','.join(f'{f}' for f,_ in lf):<36} -> {win[1]} ({win[0]})")
    print(f"\nRAZEM konfliktów: {len(conf)}")
