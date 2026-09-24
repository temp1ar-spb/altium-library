import olefile,struct,glob,os
NB={1:1,2:6,3:1,4:1,5:2,6:1,11:1,12:1}
def pads(data):
    i=0; n=struct.unpack('<I',data[:4])[0]; i=4+n
    out=[]
    while i<len(data):
        t=data[i]; i+=1
        if t==0: break
        blocks=[]
        for k in range(NB[t]):
            l=struct.unpack('<I',data[i:i+4])[0]; blocks.append(data[i+4:i+4+l]); i+=4+l
        if t==2:
            nm=blocks[0]
            if blocks[4][0] in (1,32,74) or (1<blocks[4][0]<32): out.append(nm[1:1+nm[0]].decode('latin1'))
    return out
def load_all(libdir):
    fps={}
    for f in glob.glob(libdir+'/*.PcbLib'):
        o=olefile.OleFileIO(f); fn=os.path.basename(f)
        keys={}
        if o.exists('SectionKeys'):
            b=o.openstream('SectionKeys').read(); n=struct.unpack('<I',b[:4])[0]; p=4
            for _ in range(n):
                l=struct.unpack('<I',b[p:p+4])[0]; s=b[p+5:p+4+l].decode('latin1'); p+=4+l
                l2=struct.unpack('<I',b[p:p+4])[0]; k=b[p+5:p+4+l2].decode('latin1'); p+=4+l2
                keys[k]=s
        for e in o.listdir():
            if len(e)==2 and e[1]=='Data':
                raw=o.openstream(e).read()
                name=raw[5:5+raw[4]].decode('latin1') if len(raw)>5 else e[0]
                try: fps[(fn,name)]=pads(o.openstream(e).read())
                except Exception as ex: fps[(fn,name)]=('ERR',str(ex))
    return fps

def pads_full(data):
    i=0; n=struct.unpack('<I',data[:4])[0]; i=4+n; out=[]
    while i<len(data):
        t=data[i]; i+=1
        if t==0: break
        blocks=[]
        for k in range(NB[t]):
            l=struct.unpack('<I',data[i:i+4])[0]; blocks.append(data[i+4:i+4+l]); i+=4+l
        if t==2:
            nm=blocks[0]; g=blocks[4]
            x,y=struct.unpack('<ii',g[13:21])
            sx,sy=struct.unpack('<ii',g[21:29])
            hole=struct.unpack('<i',g[45:49])[0]
            out.append(dict(name=nm[1:1+nm[0]].decode('latin1'),layer=g[0],x=x/10000*0.0254,y=y/10000*0.0254,sx=sx/10000*0.0254,sy=sy/10000*0.0254,hole=hole/10000*0.0254))
    return out
def raw(lib,name):
    o=olefile.OleFileIO(lib)
    for e in o.listdir():
        if len(e)==2 and e[1]=='Data':
            r=o.openstream(e).read()
            if r[5:5+r[4]].decode('latin1')==name: return r
