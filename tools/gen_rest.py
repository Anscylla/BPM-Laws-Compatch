"""Generate the remaining compat files: triggers, effects, gov types, amendments, movements, IGs."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdx, conflicts as c

PROJ = r"C:\Users\oskar\Documents\Paradox Interactive\Victoria 3\mod\[1.13] BPM  Laws+ Compatch"
warn = []

FASC = ['has_ideology = ideology:ideology_clerical_fascist\t# Laws+',
        'has_ideology = ideology:ideology_national_socialist\t# Laws+']


def find(root, d, key):
    base = os.path.join(root, *d.split('/'))
    for dp, _, fs in os.walk(base):
        for fn in sorted(fs):
            if not fn.endswith('.txt'):
                continue
            b = pdx.get_top(pdx.read(os.path.join(dp, fn)), key)
            if b:
                return os.path.relpath(os.path.join(dp, fn), root).replace(os.sep, '/'), b
    return None, None


def indent_of(line):
    return re.match(r'[ \t]*', line).group(0)


def op_after(body, anchor, newlines, key='', first_only=False):
    out, hit = [], 0
    for line in body.split('\n'):
        out.append(line)
        if anchor in pdx.strip_c(line) and not (first_only and hit):
            ind = indent_of(line)
            out += [ind + nl for nl in newlines]
            hit += 1
    if not hit:
        warn.append(f'{key}: brak kotwicy "{anchor}"')
    return '\n'.join(out)


def op_replace_line(body, anchor, block, key=''):
    out, hit = [], 0
    for line in body.split('\n'):
        if anchor in pdx.strip_c(line):
            ind = indent_of(line)
            out += [ind + b for b in block.split('\n')]
            hit += 1
        else:
            out.append(line)
    if not hit:
        warn.append(f'{key}: brak kotwicy "{anchor}" (replace_line)')
    return '\n'.join(out)


def op_in_sub(body, sub, snippet, key=''):
    if not pdx.find_sub(body, sub):
        warn.append(f'{key}: brak sekcji "{sub}" - tworze nowa')
    return pdx.append_in_sub(body, sub, snippet, create=True)


def op_append_top(body, snippet):
    lines = body.split('\n')
    lines[-1:-1] = snippet.split('\n')
    return '\n'.join(lines)


PATCHES = [
    ('common/scripted_triggers', 'zzzzz_compat_triggers.txt', [
        # Ideologie przywodcow z Laws+ wpiete w klasyfikatory BPM.
        ('bpm_leader_is_fascist', [('after', 'ideology:ideology_fascist', FASC)]),
        ('bpm_leader_is_nationalist', [('after', 'ideology:ideology_fascist', FASC)]),
        ('bpm_leader_is_radical_liberal', [
            ('after', 'ideology:ideology_radical',
             ['has_ideology = ideology:ideology_anarcho_liberal\t# Laws+'])]),
    ]),
    ('common/scripted_effects', 'zzzzz_compat_effects.txt', [
        ('bpm_disable_elective_laws', [
            ('append_top',
             '\tif = { # Laws+ compat: ustroj bez legislatywy wylacza wybory\n'
             '\t\tlimit = { NOT = { has_law = law_type:law_no_election } }\n'
             '\t\tactivate_law = law_type:law_no_election\n\t}')]),
        ('bpm_setup_global_laws_varlists', [
            ('append_top',
             '\tadd_to_global_variable_list = { # Laws+ compat\n'
             '\t\tname = bpm_laws_foundation_category\n'
             '\t\ttarget = law_type:law_corporatocracy\n\t}')]),
        ('calculate_populism_progress', [
            ('replace_line', 'has_law = law_type:law_secret_police',
             'OR = {\n\thas_law = law_type:law_secret_police\n'
             '\thas_law_or_variant = law_type:law_gendarmerie\t# Laws+\n}')]),
        ('calculate_communism_progress', [
            ('replace_line', 'has_law = law_type:law_secret_police',
             'OR = {\n\thas_law = law_type:law_secret_police\n'
             '\thas_law_or_variant = law_type:law_gendarmerie\t# Laws+\n}')]),
    ]),
    ('common/government_types', 'zzzzz_compat_government_types.txt', [
        ('gov_council_republic', [
            ('after', 'has_law = law_type:law_technocracy',
             ['has_law = law_type:law_no_election\t# Laws+'])]),
        ('gov_soviet_republic', [
            ('after', 'has_law = law_type:law_technocracy',
             ['has_law = law_type:law_no_election\t# Laws+'])]),
        ('gov_council_dictatorship', [
            ('after', 'has_law = law_type:law_military_junta',
             ['AND = { # Laws+',
              '\thas_law_or_variant = law_type:law_proletariat_dictatorship',
              '\thas_law_or_variant = law_type:law_no_election',
              '}'])]),
        ('gov_soviet_dictatorship', [
            ('after', 'has_law = law_type:law_military_junta',
             ['AND = { # Laws+',
              '\thas_law_or_variant = law_type:law_proletariat_dictatorship',
              '\thas_law_or_variant = law_type:law_no_election',
              '}'])]),
        ('gov_fascist_corporate_state', [
            ('in_sub', 'possible', '\t\tNOT = { has_law = law_type:law_ecclesiarchy }\t# Laws+')]),
    ]),
    ('common/amendments', 'zzzzz_compat_amendments.txt', [
        ('amendment_electoral_clientelism', [
            ('in_sub', 'allowed_laws',
             '\t\tlaw_ecclesiarchy\t# Laws+\n\t\tlaw_weighted_universal_voting\t# Laws+')]),
        ('amendment_tradition_of_free_elections', [
            ('in_sub', 'allowed_laws',
             '\t\tlaw_ecclesiarchy\t# Laws+\n\t\tlaw_weighted_universal_voting\t# Laws+')]),
        ('amendment_foreign_investment_seizures', [('after', 'ideology:ideology_fascist', FASC)]),
        ('amendment_industrial_socialization', [
            ('after', 'ideology:ideology_fascist',
             ['has_ideology = ideology:ideology_national_socialist\t# Laws+'])]),
        ('amendment_shop_councils', [
            ('after', 'ideology:ideology_fascist',
             ['has_ideology = ideology:ideology_national_socialist\t# Laws+'])]),
    ]),
    ('common/political_movements', 'zzzzz_compat_political_movements.txt', [
        ('movement_fascist', [
            ('in_sub', 'character_ideologies',
             '\t\tideology_clerical_fascist\t# Laws+\n\t\tideology_national_socialist\t# Laws+'),
            ('after', 'ideology:ideology_fascist', FASC)]),
        # movement_corporatist pominiety - BPM wylacza ten ruch (creation_trigger = always no)
        ('movement_cultural_majority', [('after', 'ideology:ideology_ethno_nationalist', FASC)]),
        ('movement_carlist', [
            ('after', 'character_has_carlist_ideology = yes',
             ['has_ideology = ideology:ideology_clerical_fascist\t# Laws+'])]),
        ('movement_miguelist', [
            ('after', 'character_has_miguelist_ideology = yes',
             ['has_ideology = ideology:ideology_clerical_fascist\t# Laws+'])]),
        ('movement_legitimist', [
            ('after', 'ideology:ideology_legitimist',
             ['has_ideology = ideology:ideology_clerical_fascist\t# Laws+'])]),
        ('movement_modernizer', [
            ('after', 'ideology:ideology_reformer',
             ['has_ideology = ideology:ideology_anarcho_liberal\t# Laws+'])]),
        ('movement_meiji_restorationist', [
            ('after', 'ideology:ideology_reformer',
             ['has_ideology = ideology:ideology_anarcho_liberal\t# Laws+'])]),
    ]),
    ('common/interest_groups', 'zzzzz_compat_interest_groups.txt', [
        ('ig_petty_bourgeoisie', [
            ('after', 'has_law = law_type:law_appointed_bureaucrats',
             ['has_law_or_variant = law_type:law_meritocratic_bureaucracy\t# Laws+'])]),
        ('ig_devout', [
            ('after', 'has_law = law_type:law_theocracy',
             ['has_law = law_type:law_gwageo\t# Laws+'])]),
    ]),
]

for d, outname, items in PATCHES:
    chunks = []
    for key, ops in items:
        fn, body = find(c.BPM, d, key)
        if not body:
            warn.append(f'{d}/{key}: BRAK w BPM')
            continue
        for kind, *args in ops:
            if kind == 'after':
                body = op_after(body, args[0], args[1], key=key)
            elif kind == 'replace_line':
                body = op_replace_line(body, args[0], args[1], key=key)
            elif kind == 'in_sub':
                body = op_in_sub(body, args[0], args[1], key=key)
            elif kind == 'append_top':
                body = op_append_top(body, args[0])
        chunks.append((key, fn, pdx.mark_replace(body)))
    out = os.path.join(PROJ, *d.split('/'), outname)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8-sig', newline='\n') as f:
        f.write(f'# BPM / Laws+ Compatch - {d}\n'
                f'# Definicje z Better Politics Mod uzupelnione o tresc z Laws+.\n\n')
        for key, fn, body in chunks:
            f.write(f'# --- {key}  (zrodlo: BPM/{fn}) ---\n{body}\n\n')
    print(f'{d}: {len(chunks)} wpisow -> {outname}')

print()
for w in warn:
    print('UWAGA:', w)
