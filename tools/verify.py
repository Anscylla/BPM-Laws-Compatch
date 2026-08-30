"""Verify the compatch against the WHOLE active playset:
  * czy kazdy wpis patcha wygrywa rozstrzyganie ASCII po nazwie pliku,
  * czy kazdy REPLACE: ma cel (inaczej gra rzuci blad),
  * ktore wpisy dzielimy z modami spoza BPM/Laws+.
Run: python tools/verify.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import playset
from conflicts import scan

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cp = scan(PROJ)

print(f'Zrodel w zestawie (vanilla + mody): {len(playset._ROOTS)}')
print(f'Wpisow w compatchu: {len(cp)}\n')

lose, orphan, shared = [], [], []
for (d, k) in sorted(cp):
    cpfiles = [fn for fn, _ in cp[(d, k)]]
    modes = [mo for _, mo in cp[(d, k)]]
    rivals = playset.effective(d, k)[1]      # [(filename, label, mode)] w kolejnosci ladowania
    if not rivals:
        if any(m.startswith(('REPLACE', 'INJECT')) and not m.startswith('TRY') for m in modes):
            orphan.append(f'{d}/{k}  (REPLACE bez celu)')
        continue
    ext = [r for r in rivals if r[1] not in ('(vanilla)', '2932134122', '2941539986')]
    if ext:
        shared.append((d, k, ext))
    for cpfn in cpfiles:
        after = [r for r in rivals if r[0] > cpfn]
        if after:
            lose.append(f'{d}/{cpfn} :: {k}  <- {after[-1][1]}/{after[-1][0]}')

print(f'PRZEGRYWANE wpisy: {len(lose)}')
for x in lose[:40]:
    print('  !!!', x)
print(f'\nSIEROTY (REPLACE bez celu): {len(orphan)}')
for x in orphan[:40]:
    print('  !!!', x)
print(f'\nWpisy dzielone z modami trzecimi (baza patcha to ich wersja): {len(shared)}')
seen = {}
for d, k, ext in shared:
    for fn, lab, mode in ext:
        seen.setdefault((lab, fn), 0)
        seen[(lab, fn)] += 1
for (lab, fn), n in sorted(seen.items(), key=lambda kv: -kv[1]):
    print(f'  {n:>4}x  {lab}/{fn}')

print('\nOK' if not lose and not orphan else '\nSA PROBLEMY - patrz wyzej')
