"""Port the Laws+ laws onto BPM's own systems:
   - country_rigidity_baseline_add (BPM-only stat; every Laws+ law sits at 0 without this)
   - institution / institution_modifier where BPM binds an institution to the whole law group
Values mirror BPM's scale for the neighbouring laws in the same group.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdx, conflicts as c

PROJ = r"C:\Users\oskar\Documents\Paradox Interactive\Victoria 3\mod\[1.13] BPM  Laws+ Compatch"

# --- rigidity: BPM's reference points are noted next to each value ---------------
RIGIDITY = {
    # lawgroup_distribution_of_power   (BPM: wealth -10, census -15, universal -20, anarchy -5, organic_democracy +25)
    'law_weighted_universal_voting': -18,
    'law_ecclesiarchy':               15,
    'law_proletariat_dictatorship':   10,
    # lawgroup_ballot_system - nowa grupa Laws+, skala jak drabina cenzusowa BPM
    'law_no_election':                10,
    'law_semi_constitutional':         5,
    'law_non_secret_ballot':           0,
    'law_secret_ballot':              -5,
    'law_direct_democracy':          -15,
    # lawgroup_internal_security       (BPM: national_guard +2, secret_police +4)
    'law_garde_nationale':             2,
    'law_gendarmerie':                 3,
    # lawgroup_policing                (BPM: local +2, dedicated +2, militarized +4)
    'law_privatized_police':           2,
    # lawgroup_trade_policy            (BPM: sakoku +10, isolationism +10, canton +10)
    'law_sakoku_shugi':               10,
    # lawgroup_economic_system         (BPM: traditionalism +10, reszta 0)
    'law_early_industrialization':     8,
    'law_class_collaboration':         5,
    'law_state_capitalism':            0,
    # lawgroup_governance_principles   (BPM: monarchy +10)
    'law_corporatocracy':             10,
}

# --- institutions: BPM wiaze institution_economy z CALA grupa lawgroup_economic_system ---
INSTITUTION = {
    'law_early_industrialization': ('institution_economy', [
        'state_aristocrats_investment_pool_efficiency_mult = 0.10',
        'state_clergymen_investment_pool_efficiency_mult = 0.10',
        'state_farmers_investment_pool_efficiency_mult = 0.10',
        'state_capitalists_investment_pool_efficiency_mult = 0.05',
        'country_farmers_pol_str_mult = 0.05',
    ]),
    'law_class_collaboration': ('institution_economy', [
        'country_private_construction_allocation_mult = -0.05',
        'state_capitalists_investment_pool_efficiency_mult = 0.05',
        'state_shopkeepers_investment_pool_efficiency_mult = 0.05',
        'state_laborers_investment_pool_efficiency_mult = 0.05',
        'state_machinists_investment_pool_efficiency_mult = 0.05',
        'country_government_dividends_efficiency_add = 0.08',
    ]),
    'law_state_capitalism': ('institution_economy', [
        'state_construction_mult = 0.15',
        'state_bureaucrats_investment_pool_efficiency_mult = 0.08',
        'country_bureaucrats_pol_str_mult = 0.05',
        'country_government_dividends_efficiency_add = 0.15',
        'building_company_government_dividends_add = 0.10',
    ]),
}

warn, chunks = [], []
for law in sorted(set(RIGIDITY) | set(INSTITUTION)):
    fn, body = pdx.find_law(c.LP, law)
    if not body:
        warn.append(f'{law}: BRAK w Laws+ - pomijam')
        continue

    rig = RIGIDITY.get(law)
    if rig:
        if 'country_rigidity_baseline_add' in body:
            warn.append(f'{law}: juz ma rigidity - pomijam')
        else:
            line = f'\t\tcountry_rigidity_baseline_add = {rig}\t# BPM compat'
            if pdx.find_sub(body, 'modifier'):
                body = pdx.append_in_sub(body, 'modifier', line)
            else:
                lines = body.split('\n')
                lines[-1:-1] = ['\tmodifier = {', line, '\t}']
                body = '\n'.join(lines)

    if law in INSTITUTION:
        inst, mods = INSTITUTION[law]
        if re.search(r'^\s*institution\s*=', body, re.M):
            warn.append(f'{law}: juz ma institution - pomijam')
        else:
            lines = body.split('\n')
            block = [f'\tinstitution = {inst}\t# BPM compat',
                     '\tinstitution_modifier = {'] + [f'\t\t{m}' for m in mods] + ['\t}']
            lines[-1:-1] = block
            body = '\n'.join(lines)

    if law not in INSTITUTION and not rig:
        continue  # nic do zmiany
    chunks.append((law, fn, pdx.mark_replace(body)))

out = os.path.join(PROJ, 'common', 'laws', 'zzzzz_compat_lawsplus_laws.txt')
with open(out, 'w', encoding='utf-8-sig', newline='\n') as f:
    f.write('# BPM / Laws+ Compatch - prawa Laws+ przeniesione na model BPM\n'
            '# Bazuja na aktualnych definicjach Laws+, dopisane sa:\n'
            '#  * country_rigidity_baseline_add - stat wylacznie BPM, bez niego kazde prawo\n'
            '#    Laws+ jest neutralne dla sztywnosci politycznej, wokol ktorej BPM balansuje gre;\n'
            '#  * institution / institution_modifier tam, gdzie BPM wiaze instytucje z cala grupa praw.\n'
            '# WYGENEROWANE: python tools/gen_lp_laws.py\n\n')
    for law, fn, body in chunks:
        f.write(f'# --- {law}  (zrodlo: Laws+/{fn}) ---\n{body}\n\n')

print(f'Zapisano {len(chunks)} praw Laws+ -> {out}')
for w in warn:
    print('  UWAGA:', w)
