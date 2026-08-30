"""Regenerate common/ideologies/zzzzzzzzzz_compat_ideologies.txt.

Takes the CURRENT Better Politics Mod ideology definitions and re-applies the
Laws+ law stances stored in the previously generated compat file (or, on a first
run, in the old workshop compatch 3481491071).

Run:  python tools/merge_ideo.py
"""
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdx
from conflicts import BPM, LP, CP, VAN, bpm, lp, van

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, 'common', 'ideologies', 'zzzzzzzzzz_compat_ideologies.txt')

NEW_LP_LAWS = ({k for d, k in lp if d == 'common/laws'}
               - {k for d, k in van if d == 'common/laws'}
               - {k for d, k in bpm if d == 'common/laws'})

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lawgroups.json')
LAWGROUP = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

STANCE = re.compile(r'^\s*(law_[a-z0-9_]+)\s*=\s*(\w+)\s*$')


def top_blocks(txt):
    lines, res, depth, cur, acc = txt.split('\n'), [], 0, None, []
    for line in lines:
        s = pdx.strip_c(line).strip()
        if depth == 0:
            m = pdx.TOPRE.match(s)
            if m:
                cur, acc = m.group('key'), []
        if cur is not None:
            acc.append(line)
        d0 = depth
        depth += pdx.strip_c(line).count('{') - pdx.strip_c(line).count('}')
        if depth < 0:
            depth = 0
        if cur is not None and d0 > 0 and depth == 0:
            res.append((cur, acc)); cur = None
    return res


def sub_blocks(lines):
    out, depth, cur, start = {}, 0, None, None
    for i, line in enumerate(lines):
        s = pdx.strip_c(line).strip()
        if depth == 1 and cur is None:
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{', s)
            if m:
                cur, start = m.group(1), i
        d0 = depth
        depth += pdx.strip_c(line).count('{') - pdx.strip_c(line).count('}')
        if cur is not None and depth <= 1 and d0 >= 2:
            out.setdefault(cur, (start, i)); cur = None
    return out


# ---- 1. collect the Laws+ stances we want to keep: {ideology: {lawgroup: {law: stance}}}
WANT = {}
sources = []
if os.path.exists(OUT):
    sources.append(('poprzedni compat', OUT, None))
else:
    d = os.path.join(CP, 'common', 'ideologies')
    for fn in sorted(os.listdir(d)):
        if fn.endswith('.txt'):
            sources.append(('stary workshop compatch', os.path.join(d, fn), fn))

for label, path, _ in sources:
    for key, lines in top_blocks(pdx.read(path)):
        for grp, (s, e) in sub_blocks(lines).items():
            if not grp.startswith('lawgroup_'):
                continue
            for l in lines[s:e + 1]:
                m = STANCE.match(pdx.strip_c(l))
                if m and m.group(1) in NEW_LP_LAWS:
                    tail = l[len(l.split('#')[0]):] if '#' in l else ''   # zachowaj znacznik "# auto"
                    WANT.setdefault(key, {}).setdefault(grp, {})[m.group(1)] = (m.group(2), tail)
print(f'Zrodlo stanowisk: {sources[0][0]} ({len(WANT)} ideologii)')

# ---- 2. re-apply them onto the current BPM definitions
merged, missing, gaps = [], [], []
base = os.path.join(BPM, 'common', 'ideologies')
for fn in sorted(os.listdir(base)):
    if not fn.endswith('.txt'):
        continue
    for key, blines in top_blocks(pdx.read(os.path.join(base, fn))):
        want = WANT.get(key)
        bsub = sub_blocks(blines)
        if want:
            out = list(blines)
            adds = {}
            for grp, laws in want.items():
                have = set()
                if grp in bsub:
                    bs, be = bsub[grp]
                    have = {m.group(1) for l in blines[bs:be + 1]
                            if (m := STANCE.match(pdx.strip_c(l)))}
                for law, (st, tail) in laws.items():
                    if law not in have:
                        sep = '\t' if tail else ''
                        adds.setdefault(grp, []).append(f'\t\t{law} = {st}{sep}{tail}')
            for grp in sorted(adds, key=lambda g: bsub.get(g, (10**6, 10**6))[1], reverse=True):
                if grp in bsub:
                    out[bsub[grp][1]:bsub[grp][1]] = adds[grp]
                else:
                    out[-1:-1] = [f'\t{grp} = {{'] + adds[grp] + ['\t}']
            if adds:
                delta = pdx.inject_delta('\n'.join(blines), '\n'.join(out), key)
                if delta:
                    merged.append((fn, key, delta))
        elif any(g.startswith('lawgroup_') for g in bsub):
            missing.append(f'{fn}/{key}')
        # coverage report
        for grp in bsub:
            if not grp.startswith('lawgroup_'):
                continue
            bs, be = bsub[grp]
            have = {m.group(1) for l in blines[bs:be + 1] if (m := STANCE.match(pdx.strip_c(l)))}
            have |= set((want or {}).get(grp, {}))
            miss = sorted({l for l, g in LAWGROUP.items() if g == grp} - have)
            if miss:
                gaps.append(f'{fn}/{key}/{grp}: {", ".join(miss)}')

with open(OUT, 'w', encoding='utf-8-sig', newline='\n') as f:
    f.write('# BPM / Laws+ Compatch - stanowiska ideologii BPM wobec praw z Laws+\n'
            '# WYGENEROWANE: python tools/merge_ideo.py  (nie edytuj recznie bez potrzeby -\n'
            '# skrypt przy kolejnym uruchomieniu odczyta stanowiska z tego pliku i przeniesie\n'
            '# je na aktualne definicje BPM).\n\n')
    last = None
    for fn, key, body in merged:
        if fn != last:
            f.write(f'\n########## {fn} ##########\n\n'); last = fn
        f.write(body + '\n\n')

print(f'Scalono ideologii: {len(merged)}  ->  {OUT}')
print(f'Ideologie BPM z blokami lawgroup, ktore nie maja zadnych stanowisk Laws+: {len(missing)}')
for m in missing:
    print('  ', m)
print(f'\nLuki (brak stanowiska wobec konkretnego prawa Laws+): {len(gaps)}')
