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


def _strip(line):
    out, q = '', False
    for ch in line:
        if ch == '"':
            q = not q
        if ch == '#' and not q:
            break
        out += ch
    return out


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
        if opens > 0:
            head = s[:s.index('{')].strip()
            depth, inner, j = opens, [], i + 1
            # a block opened and closed on one line
            if depth == 0:
                items.append(('block', head, parse(s[s.index('{') + 1:s.rindex('}')])))
                i += 1
                continue
            while j < len(lines) and depth > 0:
                t = _strip(lines[j])
                depth += t.count('{') - t.count('}')
                if depth > 0:
                    inner.append(lines[j])
                j += 1
            items.append(('block', head, parse('\n'.join(inner))))
            i = j
        else:
            items.append(('scalar', re.sub(r'\s+', ' ', s)))
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
    """
    out, taken = {}, set()

    def names(items):
        seen = {}
        for n, it in enumerate(items):
            if it[0] == 'block':
                seen.setdefault(it[1], []).append(n)
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


def merge(van, bpm, lp, path, notes, conceded):
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
            # own and will only ever answer where none of them do. Weights are the opposite,
            # which is why this is not the general rule.
            if CARRY.search(path) and flat(van[vi]) != flat(lp[li]):
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
                             path + '/' + van[vi][1], notes, conceded))

    # what Laws+ added outright
    have = set()
    for it in out:
        have |= flat(it)
    for j, it in enumerate(lp):
        if j in used_lp:
            continue
        if flat(it) & have == flat(it):
            continue                      # BPM already says it
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
                  '', notes, conceded)
    head = bpm_body.split('\n')[0]
    return '\n'.join([head] + render(items) + ['}']), notes, conceded
