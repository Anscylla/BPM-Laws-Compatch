# -*- coding: utf-8 -*-
"""Three-way merge of one database entry: vanilla is the ancestor, BPM the base.

Both mods edit the same vanilla entry. BPM restructures, Laws+ adds cases. The merge keeps
BPM's body and folds in what Laws+ added on top of vanilla, so neither loses anything.

Blocks are paired by how much of their content they share, not by name: a possible block can
hold several OR blocks and the name says nothing about which is which. A pairing that cannot
be made confidently is reported rather than guessed at.
"""
import re

SIM = 0.34          # below this two blocks are not the same block

# Blocks that hold alternatives rather than terms of a sum. Inside one of these a variant the
# base does not carry may simply be added; anywhere else that would change a number.
CARRY = re.compile(r'/name =/first_valid =')

# What a mod of laws adds is named: a law or an ideology the other side never heard of.
REFS = re.compile(r'(?:law_type:law_[a-z_]+|ideology:ideology_[a-z_]+)')

# Sections the game reads once per entry: a second one is dropped with
# "Effect/Trigger section already read earlier" in the log. Everything else - a modifier list,
# a list of laws, a flag definition - may appear again and adds up. Read off the game's own
# log, so the list is what has been seen rather than what the wiki says.
ONCE = {
    'is_visible', 'can_enact', 'can_impose', 'possible', 'would_sponsor',
    'trigger', 'creation_trigger', 'character_support_trigger', 'change_allowed_trigger',
    'can_pressure_interest_group',
    'on_activate', 'on_deactivate', 'on_enact', 'on_impose', 'on_created', 'on_enable',
    'on_government_type_change', 'on_post_government_type_change',
    'immediate', 'effect',
    'ai_will_do', 'ai_enact_weight_modifier', 'ai_impose_chance',
    'pop_weight', 'monarch_weight', 'join_weight', 'character_support_weight',
    'pop_support_weight', 'additional_radicalism_factors',
}


def _head_name(item):
    return item[1].split('=')[0].strip() if item[0] == 'block' else None


def _strip(line):
    out, q = '', False
    for ch in line:
        if ch == '"':
            q = not q
        if ch == '#' and not q:
            break
        out += ch
    return out


ASSIGN = re.compile(r'[^\s{}]+\s*[?!<>]?=\s*[^\s{}]+')


def _scalars(text):
    """One line can hold several conditions: OR = { c:BAV ?= this c:SGF ?= this }.

    Left whole, such a line matches nothing on the other side and the whole block reads as
    something neither mod wrote. A quoted value is left alone, since a space inside it says
    nothing about where one condition ends.
    """
    text = text.strip()
    if not text:
        return []
    parts = ASSIGN.findall(text)
    if len(parts) > 1 and '"' not in text and \
            ''.join(text.split()) == ''.join(''.join(p.split()) for p in parts):
        return [('scalar', re.sub(r'\s+', ' ', p.strip())) for p in parts]
    return [('scalar', re.sub(r'\s+', ' ', text))]


def parse(body):
    """-> [('scalar', text) | ('block', head, [children])] for one block's contents."""
    lines = body.split('\n')
    items, i = [], 0
    while i < len(lines):
        raw = _strip(lines[i])
        s = raw.strip()
        if not s:
            i += 1
            continue
        opens = s.count('{') - s.count('}')
        # A block opened and closed on one line. A line that closes one block and opens the
        # next - } else = { - balances out the same way and is not one: it is left as it is
        # written, since the block it opens ends on some later line.
        if '{' in s and opens == 0 and ('}' not in s or s.index('{') < s.index('}')):
            head = s[:s.index('{')].strip()
            items.append(('block', head, parse(s[s.index('{') + 1:s.rindex('}')])))
            i += 1
            continue
        if opens > 0:
            head = s[:s.index('{')].strip()
            depth, inner, j = opens, [], i + 1
            while j < len(lines) and depth > 0:
                t = _strip(lines[j])
                depth += t.count('{') - t.count('}')
                if depth > 0:
                    inner.append(lines[j])
                j += 1
            items.append(('block', head, parse('\n'.join(inner))))
            i = j
        else:
            items.extend(_scalars(s))
            i += 1
    return items


def flat(item):
    """Every leaf of an item, for comparing two of them."""
    if item[0] == 'scalar':
        return {item[1]}
    out = {item[1] + ' {'}
    for c in item[2]:
        out |= flat(c)
    return out


def similarity(a, b):
    fa, fb = flat(a), flat(b)
    return len(fa & fb) / float(len(fa | fb)) if (fa | fb) else 1.0


def pair(src_items, dst_items):
    """-> {index in src: index in dst} for items that are the same item, changed.

    A block whose name appears once on each side is that block, however heavily it was
    rewritten: join_weight is join_weight even when a mod replaces every line of it. Only
    where a name is ambiguous - several OR blocks in one trigger - does content decide.

    The same holds for a single line: where each side names ideology once, that is one
    property with two values, not two properties, and the entry may only carry one of them.
    """
    out, taken = {}, set()

    def names(items):
        seen = {}
        for n, it in enumerate(items):
            key = it[1].split('=')[0].strip()
            if key and (it[0] == 'block' or '=' in it[1]):
                seen.setdefault((it[0], key), []).append(n)
        return seen

    sn, dn = names(src_items), names(dst_items)
    for name, si in sn.items():
        di = dn.get(name, [])
        if len(si) == 1 and len(di) == 1:
            out[si[0]] = di[0]
            taken.add(di[0])

    for i, a in enumerate(src_items):
        if i in out:
            continue
        best, score = None, SIM
        for j, b in enumerate(dst_items):
            if j in taken or a[0] != b[0]:
                continue
            if a[0] == 'block' and a[1] != b[1]:
                continue
            s = similarity(a, b)
            if s > score:
                best, score = j, s
        if best is not None:
            out[i], _ = best, taken.add(best)
    return out


def merge(van, bpm, lp, path, notes, conceded, base=''):
    """-> merged item list. van/bpm/lp are item lists of the same block.

    Whatever Laws+ changed inside something Better Politics Mod removed is recorded in
    conceded: it is not carried over, and it is not a loss either. Better Politics Mod is the
    mod that reshaped politics, and a weight or an event list it deleted is gone on purpose.
    """
    v2l, v2b = pair(van, lp), pair(van, bpm)
    out = list(bpm)
    used_lp = set(v2l.values())

    # items both mods changed from the same ancestor: merge their insides
    for vi, li in v2l.items():
        if vi not in v2b:
            # A list of alternatives is not a sum: first_valid takes the first that matches,
            # so a variant Better Politics Mod does not carry can simply be added after its
            # own and will only ever answer where none of them do.
            if CARRY.search(path) and flat(van[vi]) != flat(lp[li]):
                out.append(lp[li])
                continue
            # Laws+ naming a law or an ideology this entry never mentions is Laws+ adding
            # something of its own, and it has to keep working: Better Politics Mod cannot
            # have a rule for it, so carrying it cannot say the same thing twice. This is the
            # one case where something Better Politics Mod removed still comes across.
            if flat(van[vi]) != flat(lp[li]):
                fresh = {r for r in REFS.findall(' '.join(sorted(flat(lp[li]))))
                         if r not in base}
                if fresh:
                    out.append(lp[li])
                    continue
            # Only worth a word where Laws+ actually changed it. Where Laws+ merely carried
            # the base game's line and BPM removed it, the removal is BPM's own decision.
            if flat(van[vi]) != flat(lp[li]):
                notes.append('%s: follows BPM, which drops %r that Laws+ changed' %
                             (path, van[vi][1] if van[vi][0] == 'block' else van[vi][1][:40]))
            conceded |= flat(lp[li])
            continue
        bi = v2b[vi]
        if van[vi][0] == 'block':
            out[bi] = ('block', bpm[bi][1],
                       merge(van[vi][2], bpm[bi][2], lp[li][2],
                             path + '/' + van[vi][1], notes, conceded, base))
        elif flat(van[vi]) != flat(lp[li]):
            # One line, one value. Where only Laws+ moved it, its value stands; where both
            # did, there is no third value that means both and BPM is the mod that decides.
            if flat(van[vi]) == flat(bpm[bi]):
                conceded |= flat(bpm[bi])
                out[bi] = lp[li]
            else:
                notes.append('%s: both set %r differently, follows BPM' %
                             (path, van[vi][1][:60]))
                conceded |= flat(lp[li])

    # what Laws+ added outright
    have = set()
    for it in out:
        have |= flat(it)
    for j, it in enumerate(lp):
        if j in used_lp:
            continue
        if flat(it) & have == flat(it):
            continue                      # BPM already says it
        name = _head_name(it)
        if name in ONCE:
            # A second one of these is dropped by the game, so the two become one section:
            # a trigger then reads as an and, an effect runs both.
            for k, o in enumerate(out):
                if _head_name(o) == name:
                    known = set()
                    for c in o[2]:
                        known |= flat(c)
                    out[k] = ('block', o[1],
                              o[2] + [c for c in it[2] if flat(c) & known != flat(c)])
                    break
            else:
                out.append(it)
            continue
        out.append(it)
    return out


def render(items, indent=1):
    tab = '\t' * indent
    out = []
    for it in items:
        if it[0] == 'scalar':
            out.append(tab + it[1])
        else:
            out.append(tab + it[1] + ' {')
            out.extend(render(it[2], indent + 1))
            out.append(tab + '}')
    return out


def merge_entry(van_body, bpm_body, lp_body):
    """-> (merged body, notes, conceded). Bodies include their own 'key = {' first line."""
    def guts(b):
        lines = b.split('\n')
        return '\n'.join(lines[1:-1]) if len(lines) > 2 else ''
    notes, conceded = [], set()
    items = merge(parse(guts(van_body)), parse(guts(bpm_body)), parse(guts(lp_body)),
                  '', notes, conceded, bpm_body)
    head = bpm_body.split('\n')[0]
    return '\n'.join([head] + render(items) + ['}']), notes, conceded
