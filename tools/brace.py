import sys, os, re
def check(p):
    t=open(p,encoding='utf-8-sig',errors='replace').read()
    depth=0; ln=1; bad=[]
    for line in t.replace('\r','').split('\n'):
        q=False; s=''
        for ch in line:
            if ch=='"': q=not q
            if ch=='#' and not q: break
            s+=ch
        depth += s.count('{')-s.count('}')
        if depth<0: bad.append(ln)
        ln+=1
    return depth, bad
for p in sys.argv[1:]:
    d,b=check(p)
    print(f"{'OK ' if d==0 and not b else 'BLAD'} bilans={d} ujemne@{b[:5]}  {os.path.basename(p)}")
