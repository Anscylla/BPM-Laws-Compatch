"""Regresja: czy patch niczego nie GUBI z modow zrodlowych.

Kazdy nasz wpis nadpisuje (INJECT: sekcja po sekcji, REPLACE: caly wpis) fragment
definicji z BPM albo Laws+. Ten skrypt sprawdza, czy w tym, co wystawiamy, nie zniknela
zadna linia obecna w oryginale - dokladnie ten blad skasowal listy praw powtarzalnych
BPM, gdy czesciowy INJECT wyciol z efektu skryptowego niezmienione wywolania.

Run: python tools/check_truncation.py
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdx
from conflicts import scan, toplevel_keys, BPM, LP, VAN

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def source_body(d, key):
    """Cialo wpisu z modow zrodlowych: ostatnie (ASCII) wystapienie w Laws+/BPM,
    z doklejonymi INJECT-ami - czyli to, co patch zastaje."""
    cands = []
    for root, tag in ((VAN, 'VAN'), (LP, 'L+'), (BPM, 'BPM')):
        base = os.path.join(root, *d.split('/'))
        if not os.path.isdir(base):
            continue
        for fn in sorted(os.listdir(base)):
            if not fn.endswith('.txt'):
                continue
            fp = os.path.join(base, fn)
            modes = {k: m for k, m in toplevel_keys(fp)}
            if key not in modes:
                continue
            b = pdx.get_top(pdx.read(fp), key)
            if b:
                cands.append((fn, tag, modes[key], b))
    if not cands:
        return None
    cands.sort(key=lambda t: t[0])
    body = None
    for _, _, mode, b in cands:
        if mode.startswith('INJECT') and body is not None:
            body = pdx.overlay(body, b)      # INJECT doklada / podmienia sekcje
        else:
            body = b                          # definicja i REPLACE odrzucaja poprzednia
    return body


def meaningful(lines):
    out = []
    lines = list(lines)
    if lines:
        lines[0] = re.sub(r'^(REPLACE|INJECT|TRY_REPLACE|TRY_INJECT|REPLACE_OR_CREATE|INJECT_OR_CREATE):', '', lines[0].lstrip('﻿'))
    for l in lines:
        s = pdx.strip_c(l).strip()
        if s and s not in ('{', '}'):
            s = re.sub(r'\s+', ' ', s)
            # celowe poprawki API 1.13 - nie traktuj ich jako utraty tresci
            s = re.sub(r'\bhas_role = (agitator|general|admiral|politician)\b',
                       r'has_role_of_type = \1', s)
            out.append(s)
    return out


problems, checked = [], 0
cp = scan(PROJ)
by_dir = {}
for (d, k), v in cp.items():
    by_dir.setdefault(d, []).append((k, v[0][1]))

for d, keys in sorted(by_dir.items()):
    for key, mode in sorted(keys):
        ours = None
        base = os.path.join(PROJ, *d.split('/'))
        for fn in sorted(os.listdir(base)):
            if fn.endswith('.txt'):
                b = pdx.get_top(pdx.read(os.path.join(base, fn)), key)
                if b:
                    ours = b
                    break
        src = source_body(d, key)
        if ours is None or src is None:
            continue
        checked += 1
        if mode.startswith('REPLACE'):
            lost = set(meaningful(src.split('\n'))) - set(meaningful(ours.split('\n')))
            if lost:
                problems.append((d, key, 'CALY WPIS', sorted(lost)[:6], len(lost)))
            continue
        # INJECT: nasze sekcje to DELTA - silnik sumuje bloki modyfikatorow i skleja listy,
        # wiec czesciowy blok niczego nie gubi. Bledem jest wylacznie wstrzykniecie sekcji
        # efektu/triggera, ktora juz istnieje - taka jest odrzucana z bledem.
        for kind, name, content in pdx.depth1_items(ours):
            if kind != 'section' or name not in pdx.EFFECT_TRIGGER_SECTIONS:
                continue
            if pdx._find_item(src, kind, name):
                problems.append((d, key, name,
                                 ['INJECT sekcji efektu/triggera, ktora juz istnieje'
                                  ' - silnik ja odrzuci'], 1))

print(f'Sprawdzonych wpisow: {checked}')
print(f'Wpisy gubiace tresc zrodla: {len(problems)}\n')
for d, key, where, sample, n in problems:
    print(f'  !!! {d}/{key}  [{where}]  brakuje {n} linii, np.:')
    for s in sample:
        print(f'        {s}')
print('OK - nic nie ginie' if not problems else 'SA STRATY - patrz wyzej')
