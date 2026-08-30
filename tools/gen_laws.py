"""Generate common/laws/zzzzzzzzzz_compat_laws.txt: BPM law entries + Laws+ cross-references."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdx, conflicts as c

PROJ = r"C:\Users\oskar\Documents\Paradox Interactive\Victoria 3\mod\[1.13] BPM  Laws+ Compatch"

FORCE_NO_ELECTION = """\t\tif = { # Laws+ compat: ustroj bez legislatywy wylacza wybory
\t\t\tlimit = { NOT = { has_law = law_type:law_no_election } }
\t\t\tactivate_law = law_type:law_no_election
\t\t}"""

RESTORE_BALLOT = """\t\tif = { # Laws+ compat: przywroc glosowanie po wyjsciu z braku wyborow
\t\t\tlimit = { has_law = law_type:law_no_election }
\t\t\tif = {
\t\t\t\tlimit = { country_has_monarchy_law = yes }
\t\t\t\tactivate_law = law_type:law_semi_constitutional
\t\t\t}
\t\t\telse = { activate_law = law_type:law_non_secret_ballot }
\t\t}"""

DROP_SEMI_CONST = """\t\tif = { # Laws+ compat: republika nie utrzymuje ustroju polkonstytucyjnego
\t\t\tlimit = { has_law = law_type:law_semi_constitutional }
\t\t\tactivate_law = law_type:law_non_secret_ballot
\t\t}"""

FORCE_DIRECT_DEMOCRACY = """\t\tif = { # Laws+ compat
\t\t\tlimit = { NOT = { has_law = law_type:law_direct_democracy } }
\t\t\tactivate_law = law_type:law_direct_democracy
\t\t}"""

# law -> list of (kind, arg)
PATCH = {
    # --- lawgroup_distribution_of_power: sprzezenie z lawgroup_ballot_system ---
    'law_autocracy':            [('on_activate', FORCE_NO_ELECTION)],
    'law_elder_council':        [('on_activate', FORCE_NO_ELECTION)],
    'law_oligarchy':            [('on_activate', FORCE_NO_ELECTION)],
    'law_organic_regulation':   [('on_activate', FORCE_NO_ELECTION)],
    'law_technocracy':          [('on_activate', FORCE_NO_ELECTION)],
    # DECYZJA D1 - prawa wylacznie z BPM, brak odpowiednika w Laws+
    'law_military_junta':       [('on_activate', FORCE_NO_ELECTION)],
    'law_census_voting':        [('on_activate', RESTORE_BALLOT),
                                 ('nor_in', ('ai_impose_chance',
                                             'has_law = law_type:law_wealth_voting',
                                             '\t\t\t\t\t\thas_law_or_variant = law_type:law_weighted_universal_voting\t# Laws+'))],
    'law_landed_voting':        [('on_activate', RESTORE_BALLOT)],
    'law_wealth_voting':        [('on_activate', RESTORE_BALLOT)],
    'law_universal_suffrage':   [('on_activate', RESTORE_BALLOT),
                                 ('nor_in', ('ai_impose_chance',
                                             'has_law = law_type:law_census_voting',
                                             '\t\t\t\t\t\thas_law_or_variant = law_type:law_weighted_universal_voting\t# Laws+'))],
    'law_single_party_state':   [('on_activate', RESTORE_BALLOT)],
    'law_organic_democracy':    [('on_activate', RESTORE_BALLOT)],   # DECYZJA D1
    'law_anarchy':              [('on_activate', FORCE_DIRECT_DEMOCRACY)],
    # --- lawgroup_governance_principles ---
    'law_council_republic':       [('on_activate', DROP_SEMI_CONST)],
    'law_parliamentary_republic': [('on_activate', DROP_SEMI_CONST)],
    'law_corporate_state':      [('after_line', ('has_ideology = ideology:ideology_corporatist_leader',
                                                 'has_ideology = ideology:ideology_national_socialist\t# Laws+'))],
    'law_social_monarchy':      [('after_line', ('has_ideology = ideology:ideology_corporatist_leader',
                                                 'has_ideology = ideology:ideology_clerical_fascist\t# Laws+'))],
    'law_monarchy':             [('disallow', ['law_proletariat_dictatorship'])],
    # --- lawgroup_economic_system ---
    'law_agrarianism':          [('disallow', ['law_corporatocracy'])],
    # law_traditionalism pominiete - BPM nie nadpisuje disallowing_laws/is_visible, wersja Laws+ zostaje
    'law_interventionism':      [('disallow', ['law_corporatocracy'])],
    'law_command_economy':      [('disallow', ['law_corporatocracy'])],
    'law_cooperative_ownership':[('disallow', ['law_corporatocracy'])],
    'law_laissez_faire':        [('disallow', ['law_proletariat_dictatorship'])],
    # --- lawgroup_citizenship ---
    'law_multicultural':        [('is_visible', 'NOT = { has_law = law_type:law_cosmopolitanism }')],
}


def apply_disallow(body, laws):
    snippet = '\n'.join(f'\t\t{l}\t# Laws+' for l in laws)
    return pdx.append_in_sub(body, 'disallowing_laws', snippet, create=True)


def apply_is_visible(body, cond):
    r = pdx.find_sub(body, 'is_visible')
    if r:
        return pdx.append_in_sub(body, 'is_visible', f'\t\t{cond}\t# Laws+')
    lines = body.split('\n')
    lines[-1:-1] = ['\tis_visible = {', f'\t\t{cond}\t# Laws+', '\t}']
    return '\n'.join(lines)


def apply_nor_in(body, section, anchor, newline):
    """Insert `newline` right after the line containing `anchor` inside `section`."""
    r = pdx.find_sub(body, section)
    if not r:
        return body, False
    lines = body.split('\n')
    for i in range(r[0], r[1] + 1):
        if anchor in pdx.strip_c(lines[i]):
            lines.insert(i + 1, newline)
            return '\n'.join(lines), True
    return body, False


def apply_after_line(body, anchor, newline):
    lines = body.split('\n')
    out, hit = [], False
    for line in lines:
        out.append(line)
        if anchor in pdx.strip_c(line):
            indent = re.match(r'\s*', line).group(0)
            out.append(indent + newline)
            hit = True
    return '\n'.join(out), hit


SECTIONS_TOUCHED = {
    'law_agrarianism': ['disallowing_laws'],
    'law_interventionism': ['disallowing_laws'],
    'law_laissez_faire': ['disallowing_laws'],
    'law_command_economy': ['disallowing_laws'],
    'law_cooperative_ownership': ['disallowing_laws'],
    'law_monarchy': ['disallowing_laws'],
    'law_multicultural': ['is_visible'],
}

chunks, warn = [], []
for law, ops in PATCH.items():
    fn, body = pdx.find_law(c.BPM, law)
    if not body:
        warn.append(f'{law}: BRAK w BPM - pomijam')
        continue
    src = fn
    for kind, arg in ops:
        if kind == 'on_activate':
            body = pdx.append_in_sub(body, 'on_activate', arg, create=True)
        elif kind == 'disallow':
            body = apply_disallow(body, arg)
        elif kind == 'is_visible':
            body = apply_is_visible(body, arg)
        elif kind == 'nor_in':
            body, ok = apply_nor_in(body, arg[0], arg[1], arg[2])
            if not ok:
                warn.append(f'{law}: nie znaleziono kotwicy "{arg[1]}" w {arg[0]}')
        elif kind == 'after_line':
            body, ok = apply_after_line(body, arg[0], arg[1])
            if not ok:
                warn.append(f'{law}: nie znaleziono kotwicy "{arg[0]}"')
    if body.lstrip('﻿').startswith('INJECT:'):
        keep = SECTIONS_TOUCHED[law]
        lines = body.split(chr(10))
        out = [lines[0]]
        for sec in keep:
            r = pdx.find_sub(body, sec)
            if r:
                out += lines[r[0]:r[1] + 1]
            else:
                warn.append(f'{law}: brak sekcji {sec} do wyciecia z INJECT')
        out.append('}')
        body = chr(10).join(out)
        chunks.append((law, src, body))
    else:
        chunks.append((law, src, pdx.mark_replace(body)))

hdr = """# BPM / Laws+ Compatch - prawa
# Bazuje na aktualnych definicjach z Better Politics Mod, uzupelnionych o sprzezenia
# z prawami z Laws+ (lawgroup_ballot_system, law_corporatocracy, law_proletariat_dictatorship, ...).
# REPLACE: nadpisuje wpis w calosci; plik musi ladowac sie jako ostatni (prefiks zzzzz_).

"""
out = os.path.join(PROJ, 'common', 'laws', 'zzzzzzzzzz_compat_laws.txt')
with open(out, 'w', encoding='utf-8-sig', newline='\n') as f:
    f.write(hdr)
    for law, src, body in chunks:
        f.write(f'# --- {law}  (zrodlo: BPM/{src}) ---\n{body}\n\n')

print(f'Zapisano {len(chunks)} praw -> {out}')
for w in warn:
    print('  UWAGA:', w)
