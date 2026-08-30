"""Give the three Laws+-exclusive leader ideologies stances on BPM's own laws,
by merging in the law-group blocks of their closest BPM analogue."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdx, conflicts as c

PROJ = r"C:\Users\oskar\Documents\Paradox Interactive\Victoria 3\mod\[1.13] BPM  Laws+ Compatch"

ANALOGUE = {
    'ideology_national_socialist': 'ideology_fascist',
    'ideology_clerical_fascist': 'ideology_integralist',
    'ideology_anarcho_liberal': 'ideology_radical',
}

STANCE = re.compile(r'^\s*(law_[a-z0-9_]+)\s*=\s*(\w+)\s*$')


def find(root, d, key):
    base = os.path.join(root, *d.split('/'))
    for dp, _, fs in os.walk(base):
        for fn in sorted(fs):
            if not fn.endswith('.txt'):
                continue
            b = pdx.get_top(pdx.read(os.path.join(dp, fn)), key)
            if b:
                return fn, b
    return None, None


def groups(body):
    """-> {lawgroup: (start, end)} at depth 1"""
    out, depth = {}, 0
    lines = body.split('\n')
    for i, line in enumerate(lines):
        s = pdx.strip_c(line).strip()
        if depth == 1:
            m = re.match(r'^(lawgroup_[a-z0-9_]+)\s*=\s*\{', s)
            if m:
                d = 0
                for j in range(i, len(lines)):
                    d += pdx.strip_c(lines[j]).count('{') - pdx.strip_c(lines[j]).count('}')
                    if d == 0:
                        out[m.group(1)] = (i, j)
                        break
        depth += pdx.strip_c(line).count('{') - pdx.strip_c(line).count('}')
    return out


chunks, report = [], []
for lpid, bpmid in ANALOGUE.items():
    _, lpb = find(c.LP, 'common/ideologies', lpid)
    _, bb = find(c.BPM, 'common/ideologies', bpmid)
    if not lpb or not bb:
        report.append(f'{lpid}: BRAK ({lpid if not lpb else bpmid})')
        continue
    lpg, bg = groups(lpb), groups(bb)
    lines = list(lpb.split('\n'))
    added_groups, added_laws = [], []

    # 1) whole law groups the Laws+ ideology has no opinion on
    newblocks = []
    for g, (s, e) in bg.items():
        if g in lpg:
            continue
        blk = bb.split('\n')[s:e + 1]
        newblocks += ['', f'\t{g} = {{\t# z BPM/{bpmid}'] + blk[1:]
        added_groups.append(g)

    # 2) laws inside shared groups (insert bottom-up so indices stay valid)
    for g in sorted(set(lpg) & set(bg), key=lambda g: lpg[g][1], reverse=True):
        have = {m.group(1) for l in lpb.split('\n')[lpg[g][0]:lpg[g][1] + 1]
                if (m := STANCE.match(pdx.strip_c(l)))}
        add = []
        for l in bb.split('\n')[bg[g][0]:bg[g][1] + 1]:
            m = STANCE.match(pdx.strip_c(l))
            if m and m.group(1) not in have:
                add.append(f'\t\t{m.group(1)} = {m.group(2)}\t# z BPM/{bpmid}')
                added_laws.append(f'{g}/{m.group(1)}')
        if add:
            lines[lpg[g][1]:lpg[g][1]] = add

    lines[-1:-1] = newblocks
    # Poprawka API 1.13 w tresci przejmowanej z Laws+: has_role -> has_role_of_type.
    # Skoro nasza definicja wygrywa, to my odpowiadamy za bledy w niej (Laws+ ma tu
    # PostValidate of trigger 'has_role' returned false).
    lines = [re.sub(r'\bhas_role\s*=\s*(agitator|general|admiral|politician)\b',
                    r'has_role_of_type = \1', l) for l in lines]
    body = pdx.mark_replace('\n'.join(lines))
    chunks.append((lpid, bpmid, body))
    report.append(f'{lpid} <- {bpmid}: +{len(added_groups)} grup ({", ".join(added_groups)}), '
                  f'+{len(added_laws)} pojedynczych praw')

out = os.path.join(PROJ, 'common', 'ideologies', 'zzzzzzzzzz_compat_lawsplus_ideologies.txt')
with open(out, 'w', encoding='utf-8-sig', newline='\n') as f:
    f.write('# BPM / Laws+ Compatch - ideologie wlasne Laws+ uzupelnione o stanowiska\n'
            '# wobec praw dodanych przez Better Politics Mod (skopiowane z najblizszej\n'
            '# ideologii-odpowiednika w BPM).\n\n')
    for lpid, bpmid, body in chunks:
        f.write(f'# --- {lpid}  (baza: Laws+, uzupelnienie: BPM/{bpmid}) ---\n{body}\n\n')

print(f'Zapisano -> {out}')
for r in report:
    print(' ', r)
