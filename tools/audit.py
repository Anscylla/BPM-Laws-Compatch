import os, re, sys, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conflicts import scan, BPM, LP, CP, VAN, bpm, lp, van

lp_keys = set(k for _, k in lp)
bpm_keys = set(k for _, k in bpm)
van_keys = set(k for _, k in van)
exclusive = sorted(k for k in lp_keys - van_keys - bpm_keys if len(k) > 4)
open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'lp_exclusive.txt'),'w').write('\n'.join(exclusive))
print(f"Laws+ ekskluzywnych identyfikatorow: {len(exclusive)}")
pat = re.compile(r'\b(' + '|'.join(re.escape(k) for k in exclusive) + r')\b')

def rd(p):
    return open(p, encoding='utf-8-sig', errors='replace').read().replace('\r','').split('\n')

rows=[]
for dirpath,_,files in os.walk(os.path.join(CP,'common')):
    rel = os.path.relpath(dirpath, CP).replace(chr(92),'/')
    for fn in sorted(files):
        if not fn.endswith('.txt'): continue
        cpf = os.path.join(dirpath, fn)
        src = None
        for root,tag in ((BPM,'BPM'),(LP,'L+')):
            cand = os.path.join(root, rel.replace('/',os.sep), fn)
            if os.path.exists(cand): src = (cand, tag); break
        cptxt = rd(cpf)
        hits_all = sum(1 for l in cptxt if pat.search(l))
        if src:
            added = [l for l in difflib.unified_diff(rd(src[0]), cptxt, n=0) if l.startswith('+') and not l.startswith('+++')]
            hits = sum(1 for l in added if pat.search(l))
            rows.append((rel+'/'+fn, src[1], len(added), hits, hits_all))
        else:
            rows.append((rel+'/'+fn, 'BRAK', len(cptxt), '-', hits_all))

print(f"\n{'PLIK':<58}{'ZRODLO':<7}{'+LINII':>7}{'LP-HIT':>8}{'LP-CALY':>9}")
for r in rows:
    print(f"{r[0]:<58}{r[1]:<7}{r[2]:>7}{str(r[3]):>8}{r[4]:>9}")
