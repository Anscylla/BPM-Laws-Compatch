"""Fill the remaining gaps: every BPM ideology that has an opinion in a law group
must also have one about the Laws+ laws in that group.

Two rules, both derived from BPM's own data - nothing is invented by hand:
  A) ANALOGUE - law maps onto the closest law BPM/vanilla already has; the ideology's
     stance on that law is copied (optionally amplified one step for "more extreme"
     versions). Used where progressiveness is a poor proxy, and for the two law groups
     Laws+ invents outright (ballot_system, discriminated_pop), which are mapped onto
     BPM's franchise ladder and citizenship ladder respectively.
  B) INTERPOLATION - otherwise the stance is interpolated by `progressiveness` from the
     ideology's stances on the neighbouring laws of the same group.

Derived lines are tagged `# auto`; edit them freely, the generator keeps whatever it finds.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdx, conflicts as c

PROJ = r"C:\Users\oskar\Documents\Paradox Interactive\Victoria 3\mod\[1.13] BPM  Laws+ Compatch"
OUT = os.path.join(PROJ, 'common', 'ideologies', 'zzzzzzzzzz_compat_ideologies.txt')

STANCES = ['strongly_disapprove', 'disapprove', 'neutral', 'approve', 'strongly_approve']
VAL = {s: i - 2 for i, s in enumerate(STANCES)}
NAME = {v: k for k, v in VAL.items()}
STANCE_RE = re.compile(r'^\s*(law_[a-z0-9_]+)\s*=\s*(\w+)')

# law -> (analogue law, amplify)
ANALOGUE = {
    # lawgroup_ballot_system -> drabina cenzusowa BPM (lawgroup_distribution_of_power)
    'law_no_election':          ('law_autocracy', False),
    'law_semi_constitutional':  ('law_landed_voting', False),
    'law_non_secret_ballot':    ('law_wealth_voting', False),
    'law_secret_ballot':        ('law_universal_suffrage', False),
    'law_direct_democracy':     ('law_universal_suffrage', True),
    # lawgroup_discriminated_pop -> drabina obywatelstwa
    'law_violent_suppresion':          ('law_ethnostate', True),
    'law_racial_hierarchy':            ('law_racial_segregation', False),
    'law_no_codified_discrimination':  ('law_multicultural', False),
    # ustroj / gospodarka
    'law_proletariat_dictatorship': ('law_single_party_state', False),
    'law_corporatocracy':           ('law_corporate_state', False),
    # smaczki, gdzie progressiveness jest zlym przyblizeniem
    'law_sakoku_shugi':      ('law_isolationism', False),
    'law_amabutho':          ('law_peasant_levies', False),
    'law_seodang':           ('law_religious_schools', False),
    'law_mestnichestvo':     ('law_hereditary_bureaucrats', True),
    'law_hellenoturkism':    ('law_cultural_exclusion', False),
    'law_cosmopolitanism':   ('law_multicultural', True),
    'law_privatized_police': ('law_no_police', False),
    'law_free_health_system':       ('law_public_health_insurance', True),
    'law_no_income_tax':            ('law_consumption_based_taxation', False),
    'law_paradox_employee_benefits':('law_worker_protections', True),
    'law_garde_nationale':          ('law_national_guard', False),
    'law_religious_pluralism':      ('law_freedom_of_conscience', False),
}


# ---- effective law table (vanilla -> BPM -> Laws+) --------------------------------
def law_table():
    vfs = {}
    for root in (c.VAN, c.BPM, c.LP):
        base = os.path.join(root, 'common', 'laws')
        if not os.path.isdir(base):
            continue
        for fn in os.listdir(base):
            if fn.endswith('.txt'):
                vfs[fn] = os.path.join(base, fn)
    out = {}
    for fn in sorted(vfs):
        t = pdx.read(vfs[fn])
        for k, _ in c.toplevel_keys(vfs[fn]):
            b = pdx.get_top(t, k)
            if not b:
                continue
            g = re.search(r'^\s*group\s*=\s*(lawgroup_\w+)', b, re.M)
            p = re.search(r'^\s*progressiveness\s*=\s*(-?\d+)', b, re.M)
            if g:
                out.setdefault(k, (g.group(1), int(p.group(1)) if p else 0))
    return out


LAWS = law_table()
NEW_LP = ({k for d, k in c.lp if d == 'common/laws'}
          - {k for d, k in c.van if d == 'common/laws'}
          - {k for d, k in c.bpm if d == 'common/laws'})
GROUP_OF = {k: v[0] for k, v in LAWS.items()}
PROG = {k: v[1] for k, v in LAWS.items()}


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


def amplify(v):
    return v + 1 if v > 0 else (v - 1 if v < 0 else 0)


def clamp(v):
    return max(-2, min(2, v))


def interpolate(known, law):
    """known: {law: value} within the same group. Nearest neighbour(s) by progressiveness."""
    p = PROG.get(law, 0)
    if not known:
        return None
    dists = sorted((abs(PROG.get(k, 0) - p), k) for k in known)
    best = dists[0][0]
    near = [k for d, k in dists if d == best]
    return round(sum(known[k] for k in near) / len(near))


# ---- load current state ----------------------------------------------------------
compat = {k: v for k, v in top_blocks(pdx.read(OUT))} if os.path.exists(OUT) else {}
bpm_ideo = {}
base = os.path.join(c.BPM, 'common', 'ideologies')
for fn in sorted(os.listdir(base)):
    if fn.endswith('.txt'):
        for k, lines in top_blocks(pdx.read(os.path.join(base, fn))):
            bpm_ideo[k] = (fn, lines)

added, out_chunks, stats = 0, [], {}
for key, (fn, blines) in bpm_ideo.items():
    lines = list(compat.get(key, blines))
    subs = sub_blocks(lines)
    # all stances the ideology currently holds
    have = {}
    for grp, (s, e) in subs.items():
        if not grp.startswith('lawgroup_'):
            continue
        for l in lines[s:e + 1]:
            m = STANCE_RE.match(pdx.strip_c(l))
            if m and m.group(2) in VAL:
                have[m.group(1)] = VAL[m.group(2)]
    if not have:
        continue

    per_group = {}
    for law in sorted(NEW_LP):
        if law in have or law not in GROUP_OF:
            continue
        g = GROUP_OF[law]
        val = None
        if law in ANALOGUE:
            an, amp = ANALOGUE[law]
            if an in have:
                val = amplify(have[an]) if amp else have[an]
        if val is None:
            known = {k: v for k, v in have.items() if GROUP_OF.get(k) == g and k != law}
            if known:
                val = interpolate(known, law)
        if val is None:
            continue
        per_group.setdefault(g, []).append(f'\t\t{law} = {NAME[clamp(val)]}\t# auto')
        added += 1
        stats[law] = stats.get(law, 0) + 1

    if not per_group:
        if key in compat:
            out_chunks.append((fn, key, '\n'.join(lines)))
        continue

    for g in sorted(per_group, key=lambda g: subs.get(g, (10**6, 10**6))[1], reverse=True):
        if g in subs:
            lines[subs[g][1]:subs[g][1]] = per_group[g]
        else:
            lines[-1:-1] = [f'\t{g} = {{'] + per_group[g] + ['\t}']
    lines[0] = pdx.mark_replace(lines[0])
    out_chunks.append((fn, key, '\n'.join(lines)))

order = {fn: i for i, fn in enumerate(sorted({f for f, _ in bpm_ideo.values()}))}
out_chunks.sort(key=lambda t: (order[t[0]], t[1]))

with open(OUT, 'w', encoding='utf-8-sig', newline='\n') as f:
    f.write('# BPM / Laws+ Compatch - stanowiska ideologii BPM wobec praw z Laws+\n'
            '# WYGENEROWANE: python tools/merge_ideo.py && python tools/gen_ideo_gaps.py\n'
            '# Linie oznaczone "# auto" sa wyprowadzone regulami (analogia / interpolacja po\n'
            '# progressiveness) - mozna je swobodnie recznie poprawiac, generator ich nie nadpisze.\n\n')
    last = None
    for fn, key, body in out_chunks:
        if fn != last:
            f.write(f'\n########## {fn} ##########\n\n'); last = fn
        f.write(body + '\n\n')

print(f'Ideologii w pliku: {len(out_chunks)}   dopisanych stanowisk: {added}')
for law, n in sorted(stats.items(), key=lambda kv: -kv[1]):
    print(f'  {law:<38}+{n}')
