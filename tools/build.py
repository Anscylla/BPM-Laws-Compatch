#!/usr/bin/env python3
"""Build script for the BPM / Laws+ compatibility patch.

Regenerates every file under common/ from the current Better Politics Mod and
Laws+ installations, then validates the result.

    python tools/build.py                 build and validate
    python tools/build.py --check         validate only
    python tools/build.py --game DIR --workshop DIR

Game and workshop directories are located automatically: from the patch's own
path when it lives inside a Steam workshop folder, otherwise from the Steam
library folders.
"""
import argparse
import os
import re
import sys
from collections import defaultdict

APP_ID = '529340'
BPM_ID = '2932134122'
LP_ID = '2941539986'
LEGACY_PATCH_ID = '3481491071'
PREFIX = 'zzzzzzzzzz_compat_'

MOD_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------
# Locating the game and the workshop
# --------------------------------------------------------------------------

def _steamapps_from(path):
    cur = os.path.abspath(path)
    while True:
        parent, name = os.path.split(cur)
        if not parent or parent == cur:
            return None
        if name.lower() == 'steamapps':
            return cur
        cur = parent


def _library_roots(steam_root):
    out = [os.path.join(steam_root, 'steamapps')]
    vdf = os.path.join(steam_root, 'steamapps', 'libraryfolders.vdf')
    if os.path.isfile(vdf):
        try:
            text = open(vdf, encoding='utf-8', errors='replace').read()
        except OSError:
            return out
        for m in re.finditer(r'"path"\s*"([^"]+)"', text):
            out.append(os.path.join(m.group(1).replace('\\\\', os.sep), 'steamapps'))
    return out


def _steam_candidates():
    seen, out = set(), []

    def add(p):
        if p and p not in seen and os.path.isdir(p):
            seen.add(p)
            out.append(p)

    for var in ('ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA', 'HOME'):
        base = os.environ.get(var)
        if base:
            add(os.path.join(base, 'Steam'))
            add(os.path.join(base, '.steam', 'steam'))
            add(os.path.join(base, 'Library', 'Application Support', 'Steam'))
    for drive in 'CDEFGH':
        add(f'{drive}:\\Steam')
        add(f'{drive}:\\Games\\Steam')
    return out


def locate(game_arg=None, workshop_arg=None):
    """-> (game_dir, workshop_dir). Either may be None if not found."""
    game = os.path.abspath(game_arg) if game_arg else None
    workshop = os.path.abspath(workshop_arg) if workshop_arg else None

    roots = []
    own = _steamapps_from(MOD_ROOT)
    if own:
        roots.append(own)
    for steam in _steam_candidates():
        roots.extend(_library_roots(steam))
    for env in ('VIC3_STEAMAPPS',):
        if os.environ.get(env):
            roots.insert(0, os.environ[env])

    for root in roots:
        if game is None:
            cand = os.path.join(root, 'common', 'Victoria 3')
            if os.path.isdir(os.path.join(cand, 'game')):
                game = cand
        if workshop is None:
            cand = os.path.join(root, 'workshop', 'content', APP_ID)
            if os.path.isdir(cand):
                workshop = cand
        if game and workshop:
            break
    return (os.path.join(game, 'game') if game else None), workshop


# --------------------------------------------------------------------------
# Paradox script utilities
# --------------------------------------------------------------------------

TOPRE = re.compile(r'^(?:REPLACE:|INJECT:|TRY_REPLACE:|TRY_INJECT:|REPLACE_OR_CREATE:|'
                   r'INJECT_OR_CREATE:)?(?P<key>[A-Za-z_][A-Za-z0-9_.\-]*)\s*=\s*\{')
MODES = ('REPLACE_OR_CREATE:', 'INJECT_OR_CREATE:', 'TRY_REPLACE:', 'TRY_INJECT:',
         'REPLACE:', 'INJECT:')

# Sections parsed as an effect or a trigger. A second block of the same name inside
# one entry is discarded by the game with "section already read earlier", so these
# can only be changed by replacing the whole entry. Every other block (modifier
# lists, law lists) is additive, so a patch must carry only the added lines.
EFFECT_TRIGGER_SECTIONS = {
    'on_activate', 'on_deactivate', 'on_enact', 'on_impose', 'on_created',
    'is_visible', 'can_enact', 'can_impose', 'ai_will_do', 'would_sponsor',
    'possible', 'trigger', 'creation_trigger', 'character_support_trigger',
    'can_pressure_interest_group', 'change_allowed_trigger', 'on_government_type_change',
    'on_post_government_type_change', 'effect', 'ai_enact_weight_modifier',
    'ai_impose_chance', 'pop_weight', 'monarch_weight', 'join_weight',
    'character_support_weight', 'pop_support_weight', 'additional_radicalism_factors',
}


def strip_c(line):
    q, out = False, ''
    for ch in line:
        if ch == '"':
            q = not q
        if ch == '#' and not q:
            break
        out += ch
    return out


def read(path):
    return open(path, encoding='utf-8-sig', errors='replace').read().replace('\r', '')


def toplevel_keys(path):
    out, depth = [], 0
    for line in read(path).split('\n'):
        s = strip_c(line).strip()
        if depth == 0:
            m = TOPRE.match(s)
            if m:
                mode = ''
                for k in MODES:
                    if s.startswith(k):
                        mode = k[:-1]
                        break
                out.append((m.group('key'), mode))
        depth += strip_c(line).count('{') - strip_c(line).count('}')
        if depth < 0:
            depth = 0
    return out


def get_top(text, key):
    lines, depth = text.split('\n'), 0
    for i, line in enumerate(lines):
        s = strip_c(line).strip()
        if depth == 0:
            m = TOPRE.match(s)
            if m and m.group('key') == key:
                d = 0
                for j in range(i, len(lines)):
                    d += strip_c(lines[j]).count('{') - strip_c(lines[j]).count('}')
                    if d == 0:
                        return '\n'.join(lines[i:j + 1])
        depth += strip_c(line).count('{') - strip_c(line).count('}')
        if depth < 0:
            depth = 0
    return None


def find_sub(body, name, depth_wanted=1):
    lines, depth = body.split('\n'), 0
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
    lines, r, add = body.split('\n'), find_sub(body, name), snippet.split('\n')
    if r:
        s, e = r
        if s == e:
            inner = re.sub(r'^(\s*' + re.escape(name) + r'\s*=\s*\{)(.*)\}\s*$', r'\2',
                           lines[s]).strip()
            lines[s:s + 1] = [f'\t{name} = {{', f'\t\t{inner}'] + add + ['\t}']
        else:
            lines[e:e] = add
        return '\n'.join(lines)
    if not create:
        return body
    lines[-1:-1] = [f'\t{name} = {{'] + add + ['\t}']
    return '\n'.join(lines)


def depth1_items(body):
    """-> [('section', name, [lines]) | ('scalar', name, line)] in order."""
    lines, out, depth, i = body.split('\n'), [], 0, 0
    while i < len(lines):
        line = lines[i]
        s = strip_c(line).strip()
        if depth == 1:
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{', s)
            if m:
                d, j = 0, i
                while j < len(lines):
                    d += strip_c(lines[j]).count('{') - strip_c(lines[j]).count('}')
                    if d == 0:
                        break
                    j += 1
                out.append(('section', m.group(1), lines[i:j + 1]))
                depth += sum(strip_c(x).count('{') - strip_c(x).count('}')
                             for x in lines[i:j + 1])
                i = j + 1
                continue
            m2 = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*[^{\s].*$', s)
            if m2:
                out.append(('scalar', m2.group(1), line))
        depth += strip_c(line).count('{') - strip_c(line).count('}')
        i += 1
    return out


def find_item(body, kind, name):
    lines, depth, i = body.split('\n'), 0, 0
    while i < len(lines):
        s = strip_c(lines[i]).strip()
        if depth == 1:
            if kind == 'section' and re.match(r'^' + re.escape(name) + r'\s*=\s*\{', s):
                d, j = 0, i
                while j < len(lines):
                    d += strip_c(lines[j]).count('{') - strip_c(lines[j]).count('}')
                    if d == 0:
                        return i, j
                    j += 1
            if kind == 'scalar' and re.match(r'^' + re.escape(name) + r'\s*=\s*[^{\s]', s):
                return i, i
        depth += strip_c(lines[i]).count('{') - strip_c(lines[i]).count('}')
        i += 1
    return None


def overlay(base, patch):
    body = base
    for kind, name, content in depth1_items(patch):
        block = content if kind == 'section' else [content]
        r = find_item(body, kind, name)
        lines = body.split('\n')
        if r:
            lines[r[0]:r[1] + 1] = block
        else:
            lines[-1:-1] = block
        body = '\n'.join(lines)
    return body


def mark_replace(body):
    first = body.split('\n')[0].lstrip('﻿')
    for m in MODES:
        if first.startswith(m):
            first = first[len(m):]
            break
    return '\n'.join(['REPLACE:' + first] + body.split('\n')[1:])


def _dup_names(body):
    seen = set()
    for kind, name, _ in depth1_items(body):
        if (kind, name) in seen:
            return True
        seen.add((kind, name))
    return False


def inject_delta(orig, patched, key=None):
    """-> an INJECT: entry carrying only what was added, or None when only a full
    REPLACE is safe."""
    if key is None:
        key = TOPRE.match(patched.split('\n')[0].lstrip('﻿').strip()).group('key')
    if _dup_names(orig) or _dup_names(patched):
        return None
    before = {}
    for kind, name, content in depth1_items(orig):
        before.setdefault((kind, name), content)
    keep = []
    for kind, name, content in depth1_items(patched):
        old = before.get((kind, name))
        if old is None:
            keep.extend(content if kind == 'section' else [content])
            continue
        if old == content:
            continue
        if kind != 'section' or name in EFFECT_TRIGGER_SECTIONS:
            return None
        known = {strip_c(l).strip() for l in old}
        added = [l for l in content[1:-1]
                 if strip_c(l).strip() and strip_c(l).strip() not in known]
        if added:
            keep.extend([content[0]] + added + [content[-1]])
    if not keep:
        return None
    return '\n'.join([f'INJECT:{key} = {{'] + keep + ['}'])


API_FIXES = ((re.compile(r'\bhas_role\s*=\s*(agitator|general|admiral|politician)\b'),
              r'has_role_of_type = \1'),
             (re.compile(r'\bis_ruler\s*=\s*(yes|no)\b'), r'is_ruler_of_own_country = \1'),)


def api_fix(lines):
    out = []
    for line in lines:
        for rx, rep in API_FIXES:
            line = rx.sub(rep, line)
        out.append(line)
    return out


# --------------------------------------------------------------------------
# Source index
# --------------------------------------------------------------------------

class Sources:
    def __init__(self, game, workshop):
        self.game = game
        self.bpm = os.path.join(workshop, BPM_ID)
        self.lp = os.path.join(workshop, LP_ID)
        self.legacy = os.path.join(workshop, LEGACY_PATCH_ID)
        self._entries = {}

    def entries(self, root, subdir):
        """-> {key: (filename, mode, body)} for one directory of one source."""
        ck = (root, subdir)
        if ck in self._entries:
            return self._entries[ck]
        out = {}
        base = os.path.join(root, *subdir.split('/'))
        if os.path.isdir(base):
            for fn in sorted(os.listdir(base)):
                if not fn.endswith('.txt'):
                    continue
                path = os.path.join(base, fn)
                text = read(path)
                for key, mode in toplevel_keys(path):
                    body = get_top(text, key)
                    if body is not None and key not in out:
                        out[key] = (fn, mode, body)
        self._entries[ck] = out
        return out

    def walk(self, root, subdir):
        """Same as entries() but recursive, for nested directories."""
        ck = ('walk', root, subdir)
        if ck in self._entries:
            return self._entries[ck]
        out = {}
        base = os.path.join(root, *subdir.split('/'))
        for dp, _, fs in os.walk(base):
            for fn in sorted(fs):
                if not fn.endswith('.txt'):
                    continue
                path = os.path.join(dp, fn)
                text = read(path)
                for key, mode in toplevel_keys(path):
                    body = get_top(text, key)
                    if body is not None and key not in out:
                        out[key] = (os.path.relpath(path, root).replace(os.sep, '/'),
                                    mode, body)
        self._entries[ck] = out
        return out

    def find(self, subdir, key, root=None):
        e = self.walk(root or self.bpm, subdir).get(key)
        return (e[0], e[2]) if e else (None, None)

    def law_table(self):
        """-> {law: (lawgroup, progressiveness)} after vanilla/BPM/Laws+ resolution."""
        vfs = {}
        roots = [self.game, self.bpm, self.lp,
                 os.path.join(os.path.dirname(self.bpm), DONOR_ID)]
        for root in roots:
            base = os.path.join(root, 'common', 'laws')
            if os.path.isdir(base):
                for fn in os.listdir(base):
                    if fn.endswith('.txt'):
                        vfs[fn] = os.path.join(base, fn)
        out = {}
        for fn in sorted(vfs):
            text = read(vfs[fn])
            for key, _ in toplevel_keys(vfs[fn]):
                body = get_top(text, key)
                if not body:
                    continue
                g = re.search(r'^\s*group\s*=\s*(lawgroup_\w+)', body, re.M)
                p = re.search(r'^\s*progressiveness\s*=\s*(-?\d+)', body, re.M)
                if g:
                    out.setdefault(key, (g.group(1), int(p.group(1)) if p else 0))
        return out

    def law_keys(self, root):
        return set(self.entries(root, 'common/laws'))


# --------------------------------------------------------------------------
# Patch definitions
# --------------------------------------------------------------------------

TAG_LP = '\t# laws+'
TAG_AUTO = '\t# derived'
TAG_BPM = '\t# bpm'

FASC = [f'has_ideology = ideology:ideology_clerical_fascist{TAG_LP}',
        f'has_ideology = ideology:ideology_national_socialist{TAG_LP}']

FORCE_NO_ELECTION = ('\t\tif = {\n'
                     '\t\t\tlimit = { NOT = { has_law = law_type:law_no_election } }\n'
                     '\t\t\tactivate_law = law_type:law_no_election\n\t\t}')
RESTORE_BALLOT = ('\t\tif = {\n'
                  '\t\t\tlimit = { has_law = law_type:law_no_election }\n'
                  '\t\t\tif = {\n'
                  '\t\t\t\tlimit = { country_has_monarchy_law = yes }\n'
                  '\t\t\t\tactivate_law = law_type:law_semi_constitutional\n'
                  '\t\t\t}\n'
                  '\t\t\telse = { activate_law = law_type:law_non_secret_ballot }\n\t\t}')
DROP_SEMI_CONST = ('\t\tif = {\n'
                   '\t\t\tlimit = { has_law = law_type:law_semi_constitutional }\n'
                   '\t\t\tactivate_law = law_type:law_non_secret_ballot\n\t\t}')
FORCE_DIRECT_DEMOCRACY = ('\t\tif = {\n'
                          '\t\t\tlimit = { NOT = { has_law = law_type:law_direct_democracy } }\n'
                          '\t\t\tactivate_law = law_type:law_direct_democracy\n\t\t}')

# Better Politics Mod laws wired to the law groups Laws+ introduces.
BPM_LAW_PATCH = {
    'law_autocracy':          [('on_activate', FORCE_NO_ELECTION)],
    'law_elder_council':      [('on_activate', FORCE_NO_ELECTION)],
    'law_oligarchy':          [('on_activate', FORCE_NO_ELECTION)],
    'law_organic_regulation': [('on_activate', FORCE_NO_ELECTION)],
    'law_technocracy':        [('on_activate', FORCE_NO_ELECTION)],
    'law_military_junta':     [('on_activate', FORCE_NO_ELECTION)],
    'law_census_voting':      [('on_activate', RESTORE_BALLOT),
                               ('nor_in', ('ai_impose_chance',
                                           'has_law = law_type:law_wealth_voting',
                                           '\t\t\t\t\t\thas_law_or_variant = '
                                           'law_type:law_weighted_universal_voting' + TAG_LP))],
    'law_landed_voting':      [('on_activate', RESTORE_BALLOT)],
    'law_wealth_voting':      [('on_activate', RESTORE_BALLOT)],
    'law_universal_suffrage': [('on_activate', RESTORE_BALLOT),
                               ('nor_in', ('ai_impose_chance',
                                           'has_law = law_type:law_census_voting',
                                           '\t\t\t\t\t\thas_law_or_variant = '
                                           'law_type:law_weighted_universal_voting' + TAG_LP))],
    'law_single_party_state': [('on_activate', RESTORE_BALLOT)],
    'law_organic_democracy':  [('on_activate', RESTORE_BALLOT)],
    'law_anarchy':            [('on_activate', FORCE_DIRECT_DEMOCRACY)],
    'law_council_republic':       [('on_activate', DROP_SEMI_CONST)],
    'law_parliamentary_republic': [('on_activate', DROP_SEMI_CONST)],
    'law_corporate_state':    [('after_line', ('has_ideology = ideology:ideology_corporatist_leader',
                                               'has_ideology = ideology:ideology_national_socialist'
                                               + TAG_LP))],
    'law_social_monarchy':    [('after_line', ('has_ideology = ideology:ideology_corporatist_leader',
                                               'has_ideology = ideology:ideology_clerical_fascist'
                                               + TAG_LP))],
    'law_monarchy':             [('disallow', ['law_proletariat_dictatorship'])],
    'law_agrarianism':          [('disallow', ['law_corporatocracy'])],
    'law_interventionism':      [('disallow', ['law_corporatocracy'])],
    'law_command_economy':      [('disallow', ['law_corporatocracy'])],
    'law_cooperative_ownership':[('disallow', ['law_corporatocracy'])],
    'law_laissez_faire':        [('disallow', ['law_proletariat_dictatorship'])],
    'law_multicultural':        [('is_visible', 'NOT = { has_law = law_type:law_cosmopolitanism }')],
}

# country_rigidity_baseline_add is a Better Politics Mod stat; Laws+ laws sit at zero
# without it. Values follow the scale BPM uses for neighbouring laws in the same group:
# distribution of power  wealth -10, census -15, universal -20, anarchy -5, organic +25
# internal security      national guard +2, secret police +4
# policing               local +2, dedicated +2, militarized +4
# trade policy           sakoku / isolationism / canton +10
# economic system        traditionalism +10
# governance principles  monarchy +10
RIGIDITY = {
    'law_weighted_universal_voting': -18,
    'law_ecclesiarchy':               15,
    'law_proletariat_dictatorship':   10,
    'law_no_election':                10,
    'law_semi_constitutional':         5,
    'law_non_secret_ballot':           0,
    'law_secret_ballot':              -5,
    'law_direct_democracy':          -15,
    'law_garde_nationale':             2,
    'law_gendarmerie':                 3,
    'law_privatized_police':           2,
    'law_sakoku_shugi':               10,
    'law_early_industrialization':     8,
    'law_class_collaboration':         5,
    'law_state_capitalism':            0,
    'law_corporatocracy':             10,
}

# BPM binds institution_economy to every law in lawgroup_economic_system.
INSTITUTION = {
    'law_early_industrialization': ('institution_economy', [
        'state_aristocrats_investment_pool_efficiency_mult = 0.10',
        'state_clergymen_investment_pool_efficiency_mult = 0.10',
        'state_farmers_investment_pool_efficiency_mult = 0.10',
        'state_capitalists_investment_pool_efficiency_mult = 0.05',
        'country_farmers_pol_str_mult = 0.05']),
    'law_class_collaboration': ('institution_economy', [
        'country_private_construction_allocation_mult = -0.05',
        'state_capitalists_investment_pool_efficiency_mult = 0.05',
        'state_shopkeepers_investment_pool_efficiency_mult = 0.05',
        'state_laborers_investment_pool_efficiency_mult = 0.05',
        'state_machinists_investment_pool_efficiency_mult = 0.05',
        'country_government_dividends_efficiency_add = 0.08']),
    'law_state_capitalism': ('institution_economy', [
        'state_construction_mult = 0.15',
        'state_bureaucrats_investment_pool_efficiency_mult = 0.08',
        'country_bureaucrats_pol_str_mult = 0.05',
        'country_government_dividends_efficiency_add = 0.15',
        'building_company_government_dividends_add = 0.10']),
}

OTHER_PATCHES = [
    ('common/scripted_triggers', 'triggers', [
        ('bpm_leader_is_fascist', [('after', 'ideology:ideology_fascist', FASC)]),
        ('bpm_leader_is_nationalist', [('after', 'ideology:ideology_fascist', FASC)]),
        ('bpm_leader_is_radical_liberal',
         [('after', 'ideology:ideology_radical',
           [f'has_ideology = ideology:ideology_anarcho_liberal{TAG_LP}'])]),
    ]),
    ('common/scripted_effects', 'effects', [
        ('bpm_disable_elective_laws',
         [('append_top', '\tif = {\n'
                         '\t\tlimit = { NOT = { has_law = law_type:law_no_election } }\n'
                         '\t\tactivate_law = law_type:law_no_election\n\t}')]),
        ('bpm_setup_global_laws_varlists',
         [('append_top', '\tadd_to_global_variable_list = {\n'
                         '\t\tname = bpm_laws_foundation_category\n'
                         '\t\ttarget = law_type:law_corporatocracy\n\t}')]),
        ('calculate_populism_progress',
         [('replace_line', 'has_law = law_type:law_secret_police',
           'OR = {\n\thas_law = law_type:law_secret_police\n'
           '\thas_law_or_variant = law_type:law_gendarmerie\n}')]),
        ('calculate_communism_progress',
         [('replace_line', 'has_law = law_type:law_secret_police',
           'OR = {\n\thas_law = law_type:law_secret_police\n'
           '\thas_law_or_variant = law_type:law_gendarmerie\n}')]),
    ]),
    ('common/government_types', 'government_types', [
        ('gov_council_republic', [('after', 'has_law = law_type:law_technocracy',
                                   [f'has_law = law_type:law_no_election{TAG_LP}'])]),
        ('gov_soviet_republic', [('after', 'has_law = law_type:law_technocracy',
                                  [f'has_law = law_type:law_no_election{TAG_LP}'])]),
        ('gov_council_dictatorship',
         [('after', 'has_law = law_type:law_military_junta',
           ['AND = {', '\thas_law_or_variant = law_type:law_proletariat_dictatorship',
            '\thas_law_or_variant = law_type:law_no_election', '}'])]),
        ('gov_soviet_dictatorship',
         [('after', 'has_law = law_type:law_military_junta',
           ['AND = {', '\thas_law_or_variant = law_type:law_proletariat_dictatorship',
            '\thas_law_or_variant = law_type:law_no_election', '}'])]),
        ('gov_fascist_corporate_state',
         [('in_sub', 'possible', f'\t\tNOT = {{ has_law = law_type:law_ecclesiarchy }}{TAG_LP}')]),
    ]),
    ('common/amendments', 'amendments', [
        ('amendment_electoral_clientelism',
         [('in_sub', 'allowed_laws',
           f'\t\tlaw_ecclesiarchy{TAG_LP}\n\t\tlaw_weighted_universal_voting{TAG_LP}')]),
        ('amendment_tradition_of_free_elections',
         [('in_sub', 'allowed_laws',
           f'\t\tlaw_ecclesiarchy{TAG_LP}\n\t\tlaw_weighted_universal_voting{TAG_LP}')]),
        ('amendment_foreign_investment_seizures', [('after', 'ideology:ideology_fascist', FASC)]),
        ('amendment_industrial_socialization',
         [('after', 'ideology:ideology_fascist',
           [f'has_ideology = ideology:ideology_national_socialist{TAG_LP}'])]),
        ('amendment_shop_councils',
         [('after', 'ideology:ideology_fascist',
           [f'has_ideology = ideology:ideology_national_socialist{TAG_LP}'])]),
    ]),
    ('common/political_movements', 'political_movements', [
        ('movement_fascist',
         [('in_sub', 'character_ideologies',
           f'\t\tideology_clerical_fascist{TAG_LP}\n\t\tideology_national_socialist{TAG_LP}'),
          ('after', 'ideology:ideology_fascist', FASC)]),
        ('movement_cultural_majority', [('after', 'ideology:ideology_ethno_nationalist', FASC)]),
        ('movement_carlist', [('after', 'character_has_carlist_ideology = yes',
                               [f'has_ideology = ideology:ideology_clerical_fascist{TAG_LP}'])]),
        ('movement_miguelist', [('after', 'character_has_miguelist_ideology = yes',
                                 [f'has_ideology = ideology:ideology_clerical_fascist{TAG_LP}'])]),
        ('movement_legitimist', [('after', 'ideology:ideology_legitimist',
                                  [f'has_ideology = ideology:ideology_clerical_fascist{TAG_LP}'])]),
        ('movement_modernizer', [('after', 'ideology:ideology_reformer',
                                  [f'has_ideology = ideology:ideology_anarcho_liberal{TAG_LP}'])]),
        ('movement_meiji_restorationist',
         [('after', 'ideology:ideology_reformer',
           [f'has_ideology = ideology:ideology_anarcho_liberal{TAG_LP}'])]),
    ]),
    ('common/interest_groups', 'interest_groups', [
        ('ig_petty_bourgeoisie',
         [('after', 'has_law = law_type:law_appointed_bureaucrats',
           [f'has_law_or_variant = law_type:law_meritocratic_bureaucracy{TAG_LP}'])]),
        ('ig_devout', [('after', 'has_law = law_type:law_theocracy',
                        [f'has_law = law_type:law_gwageo{TAG_LP}'])]),
    ]),
]

# Laws+ ideologies take their stance on Better Politics Mod laws from the closest
# Better Politics Mod counterpart.
IDEOLOGY_COUNTERPART = {
    'ideology_national_socialist': 'ideology_fascist',
    'ideology_clerical_fascist': 'ideology_integralist',
    'ideology_anarcho_liberal': 'ideology_radical',
}

# Laws+ law -> (counterpart law, amplify one step). Used where progressiveness is a
# poor proxy, and for the two law groups Laws+ introduces, which map onto the
# franchise ladder and the citizenship ladder respectively.
ANALOGUE = {
    'law_no_election':         ('law_autocracy', False),
    'law_semi_constitutional': ('law_landed_voting', False),
    'law_non_secret_ballot':   ('law_wealth_voting', False),
    'law_secret_ballot':       ('law_universal_suffrage', False),
    'law_direct_democracy':    ('law_universal_suffrage', True),
    'law_violent_suppresion':         ('law_ethnostate', True),
    'law_racial_hierarchy':           ('law_racial_segregation', False),
    'law_no_codified_discrimination': ('law_multicultural', False),
    'law_badge_of_shame':             ('law_racial_segregation', False),
    'law_servitude':                  ('law_ethnostate', False),
    'law_forced_labour':              ('law_ethnostate', True),
    'law_proletariat_dictatorship':   ('law_single_party_state', False),
    'law_corporatocracy':             ('law_corporate_state', False),
    'law_sakoku_shugi':      ('law_isolationism', False),
    'law_amabutho':          ('law_peasant_levies', False),
    'law_seodang':           ('law_religious_schools', False),
    'law_mestnichestvo':     ('law_hereditary_bureaucrats', True),
    'law_hellenoturkism':    ('law_cultural_exclusion', False),
    'law_cosmopolitanism':   ('law_multicultural', True),
    'law_privatized_police': ('law_no_police', False),
    'law_free_health_system':        ('law_public_health_insurance', True),
    'law_no_income_tax':             ('law_consumption_based_taxation', False),
    'law_paradox_employee_benefits': ('law_worker_protections', True),
    'law_garde_nationale':           ('law_national_guard', False),
    'law_religious_pluralism':       ('law_freedom_of_conscience', False),
}

# Laws+ dropped three rungs of lawgroup_discriminated_pop but kept everything they
# need: the scripted effects, the tooltips and two of the three icons. The patch
# restores them from the donor listed below. law_servitude has no icon left, so it
# borrows the vanilla serfdom one.
DONOR_ID = '3543498311'
RESTORED_LAWS = {
    'law_badge_of_shame': {},
    'law_servitude': {'icon': 'gfx/interface/icons/law_icons/serfdom.dds'},
    'law_forced_labour': {},
}

STANCES = ['strongly_disapprove', 'disapprove', 'neutral', 'approve', 'strongly_approve']
VAL = {s: i - 2 for i, s in enumerate(STANCES)}
NAME = {v: k for k, v in VAL.items()}
STANCE_RE = re.compile(r'^\s*(law_[a-z0-9_]+)\s*=\s*(\w+)')
STANCE_EXACT = re.compile(r'^\s*(law_[a-z0-9_]+)\s*=\s*(\w+)\s*$')

HEADER = ('# BPM / Laws+ compatibility patch - {}\n'
          '# Generated by tools/build.py. Do not rename: the zzzzzzzzzz_ prefix keeps\n'
          '# these files last in the ASCII order the game resolves conflicts by.\n\n')


# --------------------------------------------------------------------------
# Generic block helpers
# --------------------------------------------------------------------------

def top_blocks(text):
    lines, res, depth, cur, acc = text.split('\n'), [], 0, None, []
    for line in lines:
        s = strip_c(line).strip()
        if depth == 0:
            m = TOPRE.match(s)
            if m:
                cur, acc = m.group('key'), []
        if cur is not None:
            acc.append(line)
        d0 = depth
        depth += strip_c(line).count('{') - strip_c(line).count('}')
        if depth < 0:
            depth = 0
        if cur is not None and d0 > 0 and depth == 0:
            res.append((cur, acc))
            cur = None
    return res


def sub_blocks(lines):
    out, depth, cur, start = {}, 0, None, None
    for i, line in enumerate(lines):
        s = strip_c(line).strip()
        if depth == 1 and cur is None:
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{', s)
            if m:
                cur, start = m.group(1), i
        d0 = depth
        depth += strip_c(line).count('{') - strip_c(line).count('}')
        if cur is not None and depth <= 1 and d0 >= 2:
            out.setdefault(cur, (start, i))
            cur = None
    return out


def indent_of(line):
    return re.match(r'[ \t]*', line).group(0)


def op_after(body, anchor, newlines, warn, key):
    out, hit = [], 0
    for line in body.split('\n'):
        out.append(line)
        if anchor in strip_c(line):
            ind = indent_of(line)
            out += [ind + nl for nl in newlines]
            hit += 1
    if not hit:
        warn.append(f'{key}: anchor not found: {anchor}')
    return '\n'.join(out)


def op_after_first(body, anchor, newline):
    out, hit = [], False
    for line in body.split('\n'):
        out.append(line)
        if not hit and anchor in strip_c(line):
            out.append(indent_of(line) + newline)
            hit = True
    return '\n'.join(out), hit


def op_replace_line(body, anchor, block, warn, key):
    out, hit = [], 0
    for line in body.split('\n'):
        if anchor in strip_c(line):
            ind = indent_of(line)
            out += [ind + b for b in block.split('\n')]
            hit += 1
        else:
            out.append(line)
    if not hit:
        warn.append(f'{key}: anchor not found: {anchor}')
    return '\n'.join(out)


def op_nor_in(body, section, anchor, newline):
    r = find_sub(body, section)
    if not r:
        return body, False
    lines = body.split('\n')
    for i in range(r[0], r[1] + 1):
        if anchor in strip_c(lines[i]):
            lines.insert(i + 1, newline)
            return '\n'.join(lines), True
    return body, False


def write_file(subdir, name, chunks, warn):
    path = os.path.join(MOD_ROOT, *subdir.split('/'), PREFIX + name + '.txt')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8-sig', newline='\n') as f:
        f.write(HEADER.format(subdir))
        last = None
        for group, key, body in chunks:
            if group and group != last:
                f.write(f'\n########## {group} ##########\n\n')
                last = group
            f.write(f'# {key}\n{body}\n\n')
    return len(chunks)


# --------------------------------------------------------------------------
# Generators
# --------------------------------------------------------------------------

def build_ideologies(src, report):
    """BPM ideologies get a stance on every Laws+ law in the groups they care about."""
    out_path = os.path.join(MOD_ROOT, 'common', 'ideologies', PREFIX + 'ideologies.txt')
    laws = src.law_table()
    group_of = {k: v[0] for k, v in laws.items()}
    prog = {k: v[1] for k, v in laws.items()}
    new_lp = ((src.law_keys(src.lp) - src.law_keys(src.game) - src.law_keys(src.bpm))
              | set(RESTORED_LAWS))

    want = defaultdict(lambda: defaultdict(dict))

    def harvest(text, tag=None):
        for key, lines in top_blocks(text):
            for grp, (s, e) in sub_blocks(lines).items():
                if not grp.startswith('lawgroup_'):
                    continue
                for line in lines[s:e + 1]:
                    m = STANCE_EXACT.match(strip_c(line))
                    if m and m.group(1) in new_lp and m.group(1) not in want[key][grp]:
                        tail = line[len(line.split('#')[0]):] if '#' in line else ''
                        want[key][grp][m.group(1)] = (m.group(2), tag or ('\t' + tail if tail else ''))

    # 1. stances already carried by a previous build, then the legacy workshop patch
    if os.path.isfile(out_path):
        harvest(read(out_path))
    elif os.path.isdir(os.path.join(src.legacy, 'common', 'ideologies')):
        base = os.path.join(src.legacy, 'common', 'ideologies')
        for fn in sorted(os.listdir(base)):
            if fn.endswith('.txt'):
                harvest(read(os.path.join(base, fn)))
    # 2. stances Laws+ writes itself and a full BPM override would discard
    lpbase = os.path.join(src.lp, 'common', 'ideologies')
    for fn in sorted(os.listdir(lpbase)):
        if fn.endswith('.txt'):
            harvest(read(os.path.join(lpbase, fn)), TAG_LP)

    bpm_base = os.path.join(src.bpm, 'common', 'ideologies')
    bpm_ideo = {}
    for fn in sorted(os.listdir(bpm_base)):
        if fn.endswith('.txt'):
            for key, lines in top_blocks(read(os.path.join(bpm_base, fn))):
                bpm_ideo[key] = (fn, lines)

    def amplify(v):
        return v + 1 if v > 0 else (v - 1 if v < 0 else 0)

    def interpolate(known, law):
        p = prog.get(law, 0)
        if not known:
            return None
        dists = sorted((abs(prog.get(k, 0) - p), k) for k in known)
        best = dists[0][0]
        near = [k for d, k in dists if d == best]
        return round(sum(known[k] for k in near) / len(near))

    chunks, derived = [], 0
    for key, (fn, blines) in bpm_ideo.items():
        body = '\n'.join(blines)
        subs = sub_blocks(blines)
        lines = list(blines)

        # apply the collected stances
        adds = defaultdict(list)
        for grp, stances in want.get(key, {}).items():
            have = set()
            if grp in subs:
                s, e = subs[grp]
                have = {m.group(1) for l in blines[s:e + 1]
                        if (m := STANCE_EXACT.match(strip_c(l)))}
            for law, (stance, tag) in stances.items():
                if law not in have:
                    adds[grp].append(f'\t\t{law} = {stance}{tag}')
        for grp in sorted(adds, key=lambda g: subs.get(g, (10 ** 6, 10 ** 6))[1], reverse=True):
            if grp in subs:
                lines[subs[grp][1]:subs[grp][1]] = adds[grp]
            else:
                lines[-1:-1] = [f'\t{grp} = {{'] + adds[grp] + ['\t}']

        # derive whatever is still missing
        subs = sub_blocks(lines)
        have = {}
        for grp, (s, e) in subs.items():
            if not grp.startswith('lawgroup_'):
                continue
            for l in lines[s:e + 1]:
                m = STANCE_RE.match(strip_c(l))
                if m and m.group(2) in VAL:
                    have[m.group(1)] = VAL[m.group(2)]
        if have:
            per_group = defaultdict(list)
            for law in sorted(new_lp):
                if law in have or law not in group_of:
                    continue
                grp, val = group_of[law], None
                if law in ANALOGUE:
                    an, amp = ANALOGUE[law]
                    if an in have:
                        val = amplify(have[an]) if amp else have[an]
                if val is None:
                    known = {k: v for k, v in have.items()
                             if group_of.get(k) == grp and k != law}
                    if known:
                        val = interpolate(known, law)
                if val is None:
                    continue
                per_group[grp].append(f'\t\t{law} = {NAME[max(-2, min(2, val))]}{TAG_AUTO}')
                derived += 1
            for grp in sorted(per_group,
                              key=lambda g: subs.get(g, (10 ** 6, 10 ** 6))[1], reverse=True):
                if grp in subs:
                    lines[subs[grp][1]:subs[grp][1]] = per_group[grp]
                else:
                    lines[-1:-1] = [f'\t{grp} = {{'] + per_group[grp] + ['\t}']

        if '\n'.join(lines) != body:
            chunks.append((fn, key, mark_replace('\n'.join(api_fix(lines)))))

    n = write_file('common/ideologies', 'ideologies', chunks, report['warn'])
    report['ideologies'] = n
    report['derived'] = report.get('derived', 0) + derived


def build_lp_ideologies(src, report):
    """Laws+ ideologies get a stance on Better Politics Mod laws."""
    chunks = []
    for lp_id, bpm_id in IDEOLOGY_COUNTERPART.items():
        _, lpb = src.find('common/ideologies', lp_id, src.lp)
        _, bb = src.find('common/ideologies', bpm_id, src.bpm)
        if not lpb or not bb:
            report['warn'].append(f'{lp_id}: counterpart not found')
            continue
        lpg = {n: (s, e) for n, (s, e) in
               ((n, (0, 0)) for n in [])}  # placeholder, filled below
        lpg = {}
        for kind, name, content in depth1_items(lpb):
            if kind == 'section' and name.startswith('lawgroup_'):
                lpg[name] = content
        lines = lpb.split('\n')
        subs = sub_blocks(lines)
        bsubs = sub_blocks(bb.split('\n'))
        newblocks = []
        for grp, (s, e) in bsubs.items():
            if not grp.startswith('lawgroup_') or grp in subs:
                continue
            block = bb.split('\n')[s:e + 1]
            newblocks += [''] + [f'\t{grp} = {{'] + block[1:]
        for grp in sorted(set(subs) & set(bsubs), key=lambda g: subs[g][1], reverse=True):
            if not grp.startswith('lawgroup_'):
                continue
            have = {m.group(1) for l in lines[subs[grp][0]:subs[grp][1] + 1]
                    if (m := STANCE_EXACT.match(strip_c(l)))}
            add = []
            for l in bb.split('\n')[bsubs[grp][0]:bsubs[grp][1] + 1]:
                m = STANCE_EXACT.match(strip_c(l))
                if m and m.group(1) not in have:
                    add.append(f'\t\t{m.group(1)} = {m.group(2)}{TAG_BPM}')
            if add:
                lines[subs[grp][1]:subs[grp][1]] = add
        lines[-1:-1] = newblocks
        chunks.append((None, lp_id, mark_replace('\n'.join(api_fix(lines)))))
    report['lp_ideologies'] = write_file('common/ideologies', 'lawsplus_ideologies',
                                         chunks, report['warn'])


def build_bpm_laws(src, report):
    chunks, warn = [], report['warn']
    for law, ops in BPM_LAW_PATCH.items():
        fn, body = src.find('common/laws', law, src.bpm)
        if not body:
            warn.append(f'{law}: not found in Better Politics Mod')
            continue
        orig = body
        for kind, arg in ops:
            if kind == 'on_activate':
                body = append_in_sub(body, 'on_activate', arg, create=True)
            elif kind == 'disallow':
                body = append_in_sub(body, 'disallowing_laws',
                                     '\n'.join(f'\t\t{l}{TAG_LP}' for l in arg), create=True)
            elif kind == 'is_visible':
                if find_sub(body, 'is_visible'):
                    body = append_in_sub(body, 'is_visible', f'\t\t{arg}{TAG_LP}')
                else:
                    lines = body.split('\n')
                    lines[-1:-1] = ['\tis_visible = {', f'\t\t{arg}{TAG_LP}', '\t}']
                    body = '\n'.join(lines)
            elif kind == 'nor_in':
                body, ok = op_nor_in(body, arg[0], arg[1], arg[2])
                if not ok:
                    warn.append(f'{law}: anchor not found in {arg[0]}')
            elif kind == 'after_line':
                body, ok = op_after_first(body, arg[0], arg[1])
                if not ok:
                    warn.append(f'{law}: anchor not found: {arg[0]}')
        delta = inject_delta(orig, body, law)
        if delta is None:
            if orig.lstrip('﻿').startswith('INJECT:'):
                warn.append(f'{law}: skipped, the base definition comes from Laws+ and '
                            f'the change touches an effect or trigger section')
                continue
            delta = mark_replace(body)
        chunks.append((None, law, delta))
    report['bpm_laws'] = write_file('common/laws', 'laws', chunks, warn)


def build_lp_laws(src, report):
    chunks, warn = [], report['warn']
    for law in sorted(set(RIGIDITY) | set(INSTITUTION)):
        fn, body = src.find('common/laws', law, src.lp)
        if not body:
            warn.append(f'{law}: not found in Laws+')
            continue
        orig, rig = body, RIGIDITY.get(law)
        if rig and 'country_rigidity_baseline_add' not in body:
            line = f'\t\tcountry_rigidity_baseline_add = {rig}{TAG_BPM}'
            if find_sub(body, 'modifier'):
                body = append_in_sub(body, 'modifier', line)
            else:
                lines = body.split('\n')
                lines[-1:-1] = ['\tmodifier = {', line, '\t}']
                body = '\n'.join(lines)
        if law in INSTITUTION and not re.search(r'^\s*institution\s*=', body, re.M):
            inst, mods = INSTITUTION[law]
            lines = body.split('\n')
            lines[-1:-1] = ([f'\tinstitution = {inst}{TAG_BPM}', '\tinstitution_modifier = {']
                            + [f'\t\t{m}' for m in mods] + ['\t}'])
            body = '\n'.join(lines)
        if body == orig:
            continue
        delta = inject_delta(orig, body, law)
        chunks.append((None, law, delta if delta else mark_replace(body)))
    report['lp_laws'] = write_file('common/laws', 'lawsplus_laws', chunks, warn)


def build_restored_laws(src, report):
    """Re-add the lawgroup_discriminated_pop laws Laws+ removed."""
    donor = os.path.join(os.path.dirname(src.bpm), DONOR_ID)
    if not os.path.isdir(donor):
        report['warn'].append(f'donor {DONOR_ID} not installed, discrimination laws skipped')
        return
    chunks = []
    for law, opts in RESTORED_LAWS.items():
        _, body = src.find('common/laws', law, donor)
        if not body:
            report['warn'].append(f'{law}: not found in donor {DONOR_ID}')
            continue
        lines = api_fix(body.split('\n'))
        if 'icon' in opts:
            lines = [re.sub(r'(icon\s*=\s*)"[^"]*"', r'\1"' + opts['icon'] + '"', l)
                     for l in lines]
        chunks.append((None, law, '\n'.join(lines)))
    report['discrimination_laws'] = write_file('common/laws', 'discrimination_laws',
                                               chunks, report['warn'])


def build_other(src, report):
    warn = report['warn']
    for subdir, name, items in OTHER_PATCHES:
        chunks = []
        for key, ops in items:
            fn, body = src.find(subdir, key, src.bpm)
            if not body:
                warn.append(f'{subdir}/{key}: not found in Better Politics Mod')
                continue
            orig = body
            for kind, *args in ops:
                if kind == 'after':
                    body = op_after(body, args[0], args[1], warn, key)
                elif kind == 'replace_line':
                    body = op_replace_line(body, args[0], args[1], warn, key)
                elif kind == 'in_sub':
                    body = append_in_sub(body, args[0], args[1], create=True)
                elif kind == 'append_top':
                    lines = body.split('\n')
                    lines[-1:-1] = args[0].split('\n')
                    body = '\n'.join(lines)
            if subdir in ('common/scripted_effects', 'common/scripted_triggers'):
                chunks.append((None, key, mark_replace(body)))
                continue
            delta = inject_delta(orig, body, key)
            if delta is None:
                if orig.lstrip('﻿').startswith('INJECT:'):
                    warn.append(f'{key}: skipped, base definition comes from Laws+')
                    continue
                delta = mark_replace(body)
            chunks.append((None, key, delta))
        report[name] = write_file(subdir, name, chunks, warn)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def our_files():
    for dp, _, fs in os.walk(os.path.join(MOD_ROOT, 'common')):
        for fn in sorted(fs):
            if fn.endswith('.txt'):
                yield os.path.join(dp, fn)


def check_braces():
    bad = []
    for path in our_files():
        depth = 0
        for n, line in enumerate(read(path).split('\n'), 1):
            depth += strip_c(line).count('{') - strip_c(line).count('}')
            if depth < 0:
                bad.append(f'{os.path.basename(path)}:{n} unbalanced')
                break
        if depth:
            bad.append(f'{os.path.basename(path)} ends at depth {depth}')
    return bad


def check_precedence(src):
    """Every entry must sort last, and every REPLACE/INJECT must have a target."""
    problems = []
    for path in our_files():
        subdir = os.path.relpath(os.path.dirname(path), MOD_ROOT).replace(os.sep, '/')
        our_name = os.path.basename(path)
        for key, mode in toplevel_keys(path):
            rivals = []
            for root in (src.game, src.bpm, src.lp):
                for k, (fn, _, _) in src.walk(root, subdir).items():
                    if k == key:
                        rivals.append(fn.rsplit('/', 1)[-1])
            if not rivals:
                if mode.startswith(('REPLACE', 'INJECT')) and not mode.startswith('TRY'):
                    problems.append(f'{subdir}/{key}: {mode}: has no target')
                continue
            later = [f for f in rivals if f > our_name]
            if later:
                problems.append(f'{subdir}/{key}: loses to {later[-1]}')
    return problems


def check_no_loss(src):
    """Nothing the source mods define may disappear from what we emit."""
    problems = []

    def norm(lines):
        out = []
        for i, l in enumerate(lines):
            if i == 0:
                for m in MODES:
                    if l.lstrip('﻿').startswith(m):
                        l = l.lstrip('﻿')[len(m):]
                        break
            s = strip_c(l).strip()
            if s and s not in ('{', '}'):
                s = re.sub(r'\s+', ' ', s)
                for rx, rep in API_FIXES:
                    s = rx.sub(rep, s)
                out.append(s)
        return out

    for path in our_files():
        subdir = os.path.relpath(os.path.dirname(path), MOD_ROOT).replace(os.sep, '/')
        text = read(path)
        for key, mode in toplevel_keys(path):
            ours = get_top(text, key)
            cands = []
            for root in (src.game, src.lp, src.bpm):
                e = src.walk(root, subdir).get(key)
                if e:
                    cands.append(e)
            if not ours or not cands:
                continue
            cands.sort(key=lambda t: t[0].rsplit('/', 1)[-1])
            base = None
            for fn, m, body in cands:
                base = overlay(base, body) if (m.startswith('INJECT') and base) else body
            if mode.startswith('REPLACE'):
                lost = set(norm(base.split('\n'))) - set(norm(ours.split('\n')))
                if lost:
                    problems.append(f'{subdir}/{key}: {len(lost)} line(s) dropped, '
                                    f'e.g. {sorted(lost)[0]}')
            else:
                for kind, name, _ in depth1_items(ours):
                    if kind == 'section' and name in EFFECT_TRIGGER_SECTIONS \
                            and find_item(base, kind, name):
                        problems.append(f'{subdir}/{key}: injects {name}, which already '
                                        f'exists and would be discarded')
    return problems


def check_references(src):
    """Report law, ideology and movement references nothing defines."""
    pools = {}
    for sub, label in (('common/laws', 'law'), ('common/ideologies', 'ideology'),
                       ('common/political_movements', 'movement'),
                       ('common/law_groups', 'lawgroup')):
        keys = set()
        for root in (src.game, src.bpm, src.lp, MOD_ROOT):
            keys |= set(src.walk(root, sub))
        pools[label] = keys
    checks = [(re.compile(r'law_type:(law_[a-z0-9_]+)'), 'law'),
              (re.compile(r'ideology:(ideology_[a-z0-9_]+)'), 'ideology'),
              (re.compile(r'movement_type:(movement_[a-z0-9_]+)'), 'movement'),
              (re.compile(r'^\s*group\s*=\s*(lawgroup_[a-z0-9_]+)', re.M), 'lawgroup')]
    problems = set()
    for path in our_files():
        text = '\n'.join(strip_c(l) for l in read(path).split('\n'))
        for rx, label in checks:
            for m in rx.finditer(text):
                if m.group(1) not in pools[label]:
                    problems.add(f'{os.path.basename(path)}: unresolved {label} '
                                 f'{m.group(1)}')
    return sorted(problems)


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description='Build the BPM / Laws+ compatibility patch.')
    ap.add_argument('--game', help='Victoria 3 install directory')
    ap.add_argument('--workshop', help='workshop content directory for the game')
    ap.add_argument('--check', action='store_true', help='validate without rebuilding')
    args = ap.parse_args()

    game, workshop = locate(args.game, args.workshop)
    if not game or not workshop:
        print('Could not locate the game or the workshop directory.')
        print('Pass them explicitly: --game DIR --workshop DIR')
        return 2
    src = Sources(game, workshop)
    for name, path in (('Better Politics Mod', src.bpm), ('Laws+', src.lp)):
        if not os.path.isdir(path):
            print(f'{name} not found at {path}')
            return 2

    report = {'warn': []}
    if not args.check:
        for path in our_files():
            if os.path.basename(path).startswith(PREFIX):
                os.remove(path)
        # two passes: the second promotes derived stances to inputs, then settles
        for _ in range(2):
            build_ideologies(src, report)
        build_lp_ideologies(src, report)
        build_bpm_laws(src, report)
        build_lp_laws(src, report)
        build_restored_laws(src, report)
        build_other(src, report)

        print('generated:')
        for k in ('ideologies', 'lp_ideologies', 'bpm_laws', 'lp_laws',
                  'discrimination_laws', 'triggers',
                  'effects', 'government_types', 'amendments', 'political_movements',
                  'interest_groups'):
            if k in report:
                print(f'  {k:<20} {report[k]} entries')
        print(f'  {"derived stances":<20} {report.get("derived", 0)}')
        for w in report['warn']:
            print(f'  note: {w}')

    print('\nvalidation:')
    failed = False
    for label, problems in (('brace balance', check_braces()),
                            ('load order', check_precedence(src)),
                            ('content preserved', check_no_loss(src)),
                            ('references', check_references(src))):
        if problems:
            failed = True
            print(f'  {label}: {len(problems)} problem(s)')
            for p in problems[:20]:
                print(f'    {p}')
        else:
            print(f'  {label}: ok')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
