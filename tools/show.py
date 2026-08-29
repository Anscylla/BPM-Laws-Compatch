import pdx, conflicts as c, os, sys, re
def find(root, d, key):
    base=os.path.join(root,*d.split('/'))
    for dp,_,fs in os.walk(base):
        for fn in sorted(fs):
            if not fn.endswith('.txt'): continue
            b=pdx.get_top(pdx.read(os.path.join(dp,fn)),key)
            if b: return os.path.relpath(os.path.join(dp,fn),root), b
    return None,None
d=sys.argv[1]
for key in sys.argv[2:]:
    for root,tag in ((c.BPM,'BPM'),(c.LP,'L+')):
        fn,b=find(root,d,key)
        print(f'##### {tag} {key} [{fn}]')
        print(b if b else 'BRAK')
    print('='*70)
