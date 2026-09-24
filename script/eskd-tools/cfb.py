"""Minimal Compound File Binary (v3, 512-byte sectors) writer."""
import struct, olefile
FREE=0xFFFFFFFF; EOC=0xFFFFFFFE; FAT=0xFFFFFFFD; DIF=0xFFFFFFFC
def _cmp(a):
    return (len(a), a.upper())
class Node:
    def __init__(s,name,typ,data=b'',clsid=b'\0'*16):
        s.name=name;s.typ=typ;s.data=data;s.children=[];s.clsid=clsid
def tree_from_ole(path):
    o=olefile.OleFileIO(path)
    root=Node('Root Entry',5,clsid=bytes.fromhex(o.root.clsid.replace('-','')) if o.root.clsid else b'\0'*16)
    def walk(de,node):
        for k in de.kids:
            if k.entry_type==1:
                n=Node(k.name,1); walk(k,n)
            else:
                n=Node(k.name,2,o.openstream(o._find(k.name) if False else k.sid).read() if False else None)
                n.data=o._open(k.isectStart,k.size).read()
            node.children.append(n)
    walk(o.root,root); o.close(); return root
def write(root,path):
    entries=[]
    def flat(n):
        n.idx=len(entries); entries.append(n)
        for c in sorted(n.children,key=lambda c:_cmp(c.name)): flat(c)
    flat(root)
    # mini stream
    mini=bytearray(); minifat=[]
    big=[]  # (node) streams >=4096
    for n in entries:
        if n.typ==2:
            if len(n.data)<4096:
                n.start=len(mini)//64 if n.data else EOC
                cnt=(len(n.data)+63)//64
                for i in range(cnt): minifat.append(n.start+i+1 if i<cnt-1 else EOC)
                mini+=n.data+b'\0'*(cnt*64-len(n.data))
            else: big.append(n)
    sectors=[]  # list of bytes per sector
    fat=[]
    def alloc(data):
        if not data: return EOC
        cnt=(len(data)+511)//512; start=len(sectors)
        for i in range(cnt):
            sectors.append(bytes(data[i*512:(i+1)*512]).ljust(512,b'\0'))
            fat.append(start+i+1 if i<cnt-1 else EOC)
        return start
    for n in big: n.start=alloc(n.data)
    root.start=alloc(bytes(mini)); root.size=len(mini)
    mf=b''.join(struct.pack('<I',x) for x in minifat)
    mfstart=alloc(mf) if minifat else EOC
    # directory: balanced binary tree per storage (all black)
    def build(sib):
        if not sib: return FREE
        m=len(sib)//2; n=sib[m]
        n.left=build(sib[:m]); n.right=build(sib[m+1:]); return n.idx
    for n in entries:
        n.left=n.right=FREE
    for n in entries:
        kids=sorted(n.children,key=lambda c:_cmp(c.name))
        n.child=build(kids) if kids else FREE
    d=bytearray()
    for n in entries:
        nm=n.name.encode('utf-16le')
        e=nm.ljust(64,b'\0')+struct.pack('<HBB',len(nm)+2,n.typ,1)
        e+=struct.pack('<III',n.left,n.right,n.child)+n.clsid+struct.pack('<I',0)+b'\0'*16
        size=root.size if n.typ==5 else (len(n.data) if n.typ==2 else 0)
        start=n.start if n.typ in(2,5) else 0
        if n.typ==2 and not n.data: start=EOC
        if n.typ==5 and size==0: start=EOC
        e+=struct.pack('<III',start,size,0)
        d+=e
    while len(d)%512: d+=(b'\0'*64+struct.pack('<HBB',0,0,0)+struct.pack('<III',FREE,FREE,FREE)+b'\0'*36+struct.pack('<III',0,0,0))
    dirstart=alloc(bytes(d))
    # FAT sectors
    n_data=len(sectors)
    nfat=1
    while True:
        total=n_data+nfat
        ndif=0 if nfat<=109 else ( (nfat-109+126)//127 )
        total+=ndif
        if nfat*128>=total: break
        nfat+=1
    fatstart=len(sectors)
    fat+= [FAT]*nfat + [DIF]*ndif
    fat+= [FREE]*(nfat*128-len(fat))
    fb=b''.join(struct.pack('<I',x) for x in fat)
    for i in range(nfat): sectors.append(fb[i*512:(i+1)*512])
    fatlist=list(range(fatstart,fatstart+nfat))
    difstart=len(sectors) if ndif else EOC
    if ndif:
        rest=fatlist[109:]
        for k in range(ndif):
            chunk=rest[k*127:(k+1)*127]; chunk+= [FREE]*(127-len(chunk))
            nxt=difstart+k+1 if k<ndif-1 else EOC
            sectors.append(b''.join(struct.pack('<I',x) for x in chunk+[nxt]))
    hdr=bytes.fromhex('d0cf11e0a1b11ae1')+b'\0'*16+struct.pack('<HHHHH',0x3E,3,0xFFFE,9,6)+b'\0'*6
    hdr+=struct.pack('<IIIIIIIII',0,nfat,dirstart,0,4096,mfstart,len(minifat)and (len(mf)+511)//512 or 0,difstart,ndif)
    hf=fatlist[:109]+[FREE]*(109-min(109,len(fatlist)))
    hdr+=b''.join(struct.pack('<I',x) for x in hf)
    assert len(hdr)==512
    open(path,'wb').write(hdr+b''.join(sectors))
def streams(path):
    o=olefile.OleFileIO(path); r={'/'.join(e):o.openstream(e).read() for e in o.listdir()}; o.close(); return r
