"""Effective-VFS reference check for the vanilla + BPM + Laws+ (+ compatch) stack."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conflicts import BPM, LP, VAN, CP, toplevel_keys

PROJ = r"C:\Users\oskar\Documents\Paradox Interactive\Victoria 3\mod\[1.13] BPM  Laws+ Compatch"
VANROOT = os.path.join(VAN)

# load order: vanilla, BPM, Laws+, compatch  (later shadows same relative path)
ROOTS = [('VAN', VANROOT), ('BPM', BPM), ('L+', LP), ('CP', PROJ)]
if '--nocompatch' in sys.argv:
    ROOTS = ROOTS[:3]

vfs = {}   # relpath -> (tag, abspath)
for tag, root in ROOTS:
    for sub in ('common', 'events'):
        base = os.path.join(root, sub)
        for dp, _, fs in os.walk(base):
            for fn in fs:
                if not fn.lower().endswith('.txt'):
                    continue
                ap = os.path.join(dp, fn)
                rel = os.path.relpath(ap, root).replace(os.sep, '/')
                vfs[rel] = (tag, ap)

defined = {}   # dir -> set(keys)
for rel, (tag, ap) in vfs.items():
    d = rel.rsplit('/', 1)[0]
    for k, mode in toplevel_keys(ap):
        defined.setdefault(d, set()).add(k)

LAWS = defined.get('common/laws', set())
IDEO = defined.get('common/ideologies', set())
MOVE = defined.get('common/political_movements', set())
LGRP = defined.get('common/law_groups', set())
IGS = defined.get('common/interest_groups', set())
PARTY = defined.get('common/parties', set())
INST = defined.get('common/institutions', set())
GOV = defined.get('common/government_types', set())

CHECKS = [
    (re.compile(r'law_type:(law_[a-z0-9_]+)'), LAWS, 'law'),
    (re.compile(r'ideology:(ideology_[a-z0-9_]+)'), IDEO, 'ideology'),
    (re.compile(r'movement_type:(movement_[a-z0-9_]+)'), MOVE, 'movement'),
    (re.compile(r'institution:(institution_[a-z0-9_]+)'), INST, 'institution'),
    (re.compile(r'^\s*group\s*=\s*(lawgroup_[a-z0-9_]+)', re.M), LGRP, 'lawgroup'),
    (re.compile(r'\big:(ig_[a-z0-9_]+)'), IGS, 'interest_group'),
    (re.compile(r'has_government_type\s*=\s*(gov_[a-z0-9_]+)'), GOV, 'government_type'),
]

bad = {}
for rel, (tag, ap) in sorted(vfs.items()):
    txt = open(ap, encoding='utf-8-sig', errors='replace').read()
    txt = '\n'.join(l.split('#')[0] for l in txt.replace('\r', '').split('\n'))
    for rx, pool, label in CHECKS:
        for m in rx.finditer(txt):
            name = m.group(1)
            if name not in pool:
                bad.setdefault((label, name), set()).add(f'{tag}:{rel}')

print(f'Plikow w VFS: {len(vfs)}   (load order: {[t for t,_ in ROOTS]})')
print(f'Nierozwiazane referencje: {len(bad)}\n')
for (label, name), where in sorted(bad.items()):
    w = sorted(where)
    print(f'  [{label}] {name}   <- {", ".join(w[:4])}{" ..." if len(w) > 4 else ""}')
