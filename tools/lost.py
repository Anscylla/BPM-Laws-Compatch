import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conflicts import BPM, LP, CP, VAN, bpm, lp, van, KEY

lp_keys=set(k for _,k in lp); bpm_keys=set(k for _,k in bpm); van_keys=set(k for _,k in van)
excl = sorted(k for k in lp_keys-van_keys-bpm_keys if len(k)>4)
pat = re.compile(r'\b(' + '|'.join(re.escape(k) for k in excl) + r')\b')

def bodies(path):
    try: txt=open(path,encoding='utf-8-sig',errors='replace').read()
    except: return {}
    lines=[]
    for line in txt.replace('\r','').split('\n'):
        q=False;buf=''
        for ch in line:
            if ch=='"': q=not q
            if ch=='#' and not q: break
            buf+=ch
        lines.append(buf)
    out={};depth=0;cur=None;acc=[]
    for line in lines:
        s=line.strip()
        if depth==0:
            m=KEY.match(s)
            if m: cur=m.group('key'); acc=[]
        if cur is not None: acc.append(line)
        d0=depth; depth+=line.count('{')-line.count('}')
        if depth<0: depth=0
        if cur is not None and d0>0 and depth==0:
            out.setdefault(cur,[]).append('\n'.join(acc)); cur=None
    return out

cache={}
def get(root,d,fn):
    p=os.path.join(root,d.replace('/',os.sep),fn)
    if p not in cache: cache[p]=bodies(p)
    return cache[p]

print("### UTRACONA TRESC Laws+ (wpis wygrywa BPM, a wersja L+ odwoluje sie do rzeczy z Laws+)\n")
tot=0
for (d,k) in sorted(set(bpm)&set(lp)):
    lpbody=''
    for fn,_ in lp[(d,k)]:
        lpbody+='\n'.join(get(LP,d,fn).get(k,[]))
    bpmbody=''
    for fn,_ in bpm[(d,k)]:
        bpmbody+='\n'.join(get(BPM,d,fn).get(k,[]))
    lost=sorted(set(pat.findall(lpbody)) - set(pat.findall(bpmbody)))
    if lost:
        tot+=1
        print(f"{d}/{k}\n    brakuje w BPM: {', '.join(lost)}")
print(f"\nRAZEM wpisow z utracona trescia: {tot}")
