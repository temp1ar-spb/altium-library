import olefile,struct
def records(data):
    i=0;out=[]
    while i<len(data):
        n=struct.unpack('<H',data[i:i+2])[0]; flag=data[i+3]; body=data[i+4:i+4+n]; i+=4+n
        if flag==0:
            d={}
            for kv in body.rstrip(b'\0').decode('latin1').split('|'):
                if '=' in kv:
                    k,v=kv.split('=',1); d[k.upper()]=v
            out.append(('t',d,body))
        else: out.append(('b',None,body))
    return out
def pin(body):
    rec,=struct.unpack('<i',body[:4])
    p=5
    owner,=struct.unpack('<h',body[p:p+2]);p+=2
    ownerpart=body[p];p+=1  # approx
    return body

def ps(b,p):
    n=b[p]; return b[p+1:p+1+n].decode('latin1'), p+1+n
def parse_pin(b):
    d={}
    p=4; p+=1
    d['owner']=struct.unpack('<h',b[p:p+2])[0]; p+=2
    d['mode']=b[p]; p+=1
    d['sym']=tuple(b[p:p+4]); p+=4
    d['desc'],p=ps(b,p)
    d['formal']=b[p]; d['elec']=b[p+1]; d['flags']=b[p+2]; p+=3
    d['len'],d['x'],d['y']=struct.unpack('<hhh',b[p:p+6]); p+=6
    d['color']=struct.unpack('<i',b[p:p+4])[0]; p+=4
    d['name'],p=ps(b,p); d['des'],p=ps(b,p)
    d['rest']=b[p:]
    return d
def v(d,k):
    return float(d.get(k,0))+float(d.get(k+'_FRAC',0))/1e5
def load(path):
    o=olefile.OleFileIO(path); comps={}
    for e in o.listdir():
        if len(e)==2 and e[1]=='Data':
            comps[e[0]]=records(o.openstream('/'.join(e)).read())
    return o,comps
