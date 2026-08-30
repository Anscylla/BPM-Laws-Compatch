import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conflicts import scan, BPM, LP, VAN, bpm, lp, van
PROJ = r"C:\Users\oskar\Documents\Paradox Interactive\Victoria 3\mod\[1.13] BPM  Laws+ Compatch"
cp = scan(PROJ)
print(f'Wpisow w compatchu: {len(cp)}')
bad = orphan = ok = 0
for (d, k) in sorted(cp):
    cpfiles = [fn for fn, _ in cp[(d, k)]]
    modes = [mo for _, mo in cp[(d, k)]]
    rivals = []
    for db, tag in ((bpm, 'BPM'), (lp, 'L+'), (van, 'VAN')):
        for fn, _ in db.get((d, k), []):
            rivals.append((tag, fn))
    if not rivals:
        if any(m.startswith(('REPLACE', 'INJECT')) and not m.startswith('TRY') for m in modes):
            print(f'  !!! SIEROTA (REPLACE bez celu): {d}/{k}')
            orphan += 1
        continue
    for cpfn in cpfiles:
        eff = [(t, f) for t, f in rivals if f != cpfn]
        if not eff:
            ok += 1; continue
        latest = max(eff, key=lambda tf: tf[1])
        if cpfn > latest[1]:
            ok += 1
        else:
            print(f'  !!! PRZEGRYWA: {d}/{cpfn} :: {k}  <- {latest[0]}:{latest[1]}')
            bad += 1
print(f'\nOK: {ok}   przegrywajacych: {bad}   sierot: {orphan}')
