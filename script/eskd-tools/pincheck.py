import sys,glob,os,collections;sys.path.insert(0,'.')
from sch import *; import pcb
L=sys.argv[1] if len(sys.argv)>1 else 'library'
F=pcb.load_all(L)
byname=collections.defaultdict(list)
for (fn,n),v in F.items(): byname[n.upper()].append((fn,v))
rows=[]
for f in sorted(glob.glob(L+'/*.SchLib')):
    o,comps=load(f); fn=os.path.basename(f)
    for name,recs in sorted(comps.items()):
        pins=[parse_pin(b) for k,d,b in recs if k=='b']
        pins=[p for p in pins if p['mode']==0]
        des=[p['des'] for p in pins]
        # duplicates within same part
        dup=[k for k,c in collections.Counter((p['owner'],p['des']) for p in pins).items() if c>1]
        pinset=set(des)
        models=[d for k,d,b in recs if k=='t' and d.get('RECORD')=='45' and d.get('MODELTYPE')=='PCBLIB']
        if not models: rows.append((fn,name,'-','NO FOOTPRINT','',''));continue
        for m in models:
            ent=m.get('MODELDATAFILEENTITY0') or m.get('MODELNAME'); lib=m.get('MODELDATAFILE0','')
            v=F.get((lib,ent))
            where=lib
            if v is None:
                c=byname.get((ent or '').upper())
                if not c: rows.append((fn,name,ent,'FOOTPRINT NOT FOUND',lib,''));continue
                where,v=c[0]; where+='(!)'
            padset=set(x for x in v if x!='')
            sp=[x for x in padset if x!=x.strip()]
            a=sorted(pinset-padset,key=lambda s:(len(s),s)); b=sorted(padset-pinset,key=lambda s:(len(s),s))
            st='OK' if not a and not b and not dup else 'MISMATCH'
            if sp: st='MISMATCH'; b=b+['SPACE:'+repr(x) for x in sp]
            rows.append((fn,name,ent,st,'pins w/o pad: '+' '.join(a) if a else '', ('pads w/o pin: '+' '.join(b) if b else '')+(' dup: '+str(dup) if dup else ''), where))
import json; 
c=collections.Counter(r[3] for r in rows); print(c)
for r in rows:
    if r[3]!='OK': print(r)
