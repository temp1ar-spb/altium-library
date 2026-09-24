"""Read/modify/write Altium SchLib files (binary v5) without Altium."""
import struct, zlib, random, string
import cfb

MM = 1 / 0.254          # DXP units (10 mil) per mm


# ---------- text records ----------
class Rec:
    """Text record with preserved key order/case."""
    def __init__(self, body=None, pairs=None):
        if pairs is not None:
            self.pairs = list(pairs)
        else:
            s = body.rstrip(b'\0').decode('latin1')
            self.pairs = []
            parts = s.split('|')
            self.lead = parts[0]
            for kv in parts[1:]:
                if '=' not in kv:
                    self.pairs.append([None, kv])
                    continue
                k, _, v = kv.partition('=')
                self.pairs.append([k, v])

    def get(self, k, d=None):
        ku = k.upper()
        for p in self.pairs:
            if p[0] is not None and p[0].upper() == ku:
                return p[1]
        return d

    def set(self, k, v):
        ku = k.upper()
        for p in self.pairs:
            if p[0] is not None and p[0].upper() == ku:
                p[1] = v
                return
        self.pairs.append([k, v])

    def delete(self, k):
        ku = k.upper()
        self.pairs = [p for p in self.pairs if p[0] is None or p[0].upper() != ku]

    def num(self, k):
        return float(self.get(k, 0)) + float(self.get(k + '_Frac', 0)) / 1e5

    def setnum(self, k, v):
        i, f = split(v)
        self.delete(k)
        self.delete(k + '_Frac')
        if i:
            self.pairs.append([k, str(i)])
        if f:
            self.pairs.append([k + '_Frac', str(f)])

    @property
    def rtype(self):
        return self.get('RECORD')

    def bytes(self):
        return (getattr(self, 'lead', '') + '|' + '|'.join(v if k is None else f'{k}={v}' for k, v in self.pairs)).encode('latin1') + b'\0'


def split(v):
    """units -> (int, frac) with the same sign, frac in 1e-5 units."""
    t = round(v * 1e5)
    s = -1 if t < 0 else 1
    t = abs(t)
    return s * (t // 100000), s * (t % 100000)


# ---------- binary pin records ----------
class Pin:
    def __init__(self, b=None):
        if b is None:
            return
        self.head = b[:5]
        p = 5
        self.owner = struct.unpack('<h', b[p:p + 2])[0]; p += 2
        self.mode = b[p]; p += 1
        self.sym = list(b[p:p + 4]); p += 4
        n = b[p]; self.desc = b[p + 1:p + 1 + n]; p += 1 + n
        self.formal, self.elec, self.flags = b[p], b[p + 1], b[p + 2]; p += 3
        self.len, self.xi, self.yi = struct.unpack('<hhh', b[p:p + 6]); p += 6
        self.color = struct.unpack('<i', b[p:p + 4])[0]; p += 4
        n = b[p]; self.name = b[p + 1:p + 1 + n].decode('latin1'); p += 1 + n
        n = b[p]; self.des = b[p + 1:p + 1 + n].decode('latin1'); p += 1 + n
        self.rest = b[p:]
        self.frac = (0, 0, 0)

    @staticmethod
    def new(owner, name, des, elec, x, y, length, rot, show_name=True, sym=(0, 0, 0, 0)):
        p = Pin()
        p.head = struct.pack('<i', 2) + b'\0'
        p.owner, p.mode, p.sym, p.desc = owner, 0, list(sym), b''
        p.formal, p.elec = 1, elec
        p.flags = rot | 0x20 | 0x10 | (0x08 if show_name else 0)
        p.color = 0
        p.name, p.des = name, des
        p.rest = b'\0\x03|&|\0'
        p.set_geom(x, y, length)
        return p

    def set_geom(self, x, y, length):
        xi, xf = split(x); yi, yf = split(y); li, lf = split(length)
        self.xi, self.yi, self.len = xi, yi, li
        self.frac = (xf, yf, lf)

    @property
    def x(self): return self.xi + self.frac[0] / 1e5
    @property
    def y(self): return self.yi + self.frac[1] / 1e5
    @property
    def length(self): return self.len + self.frac[2] / 1e5
    @property
    def rot(self): return self.flags & 3

    def hot(self):
        dx, dy = [(1, 0), (0, 1), (-1, 0), (0, -1)][self.rot]
        return self.x + dx * self.length, self.y + dy * self.length

    def bytes(self):
        n = self.name.encode('latin1'); d = self.des.encode('latin1')
        return (self.head + struct.pack('<hB', self.owner, self.mode) + bytes(self.sym)
                + bytes([len(self.desc)]) + self.desc
                + bytes([self.formal, self.elec, self.flags])
                + struct.pack('<hhh', self.len, self.xi, self.yi) + struct.pack('<i', self.color)
                + bytes([len(n)]) + n + bytes([len(d)]) + d + self.rest)


# ---------- streams ----------
def read_records(data):
    i = 0; out = []
    while i < len(data):
        n = struct.unpack('<H', data[i:i + 2])[0]; flag = data[i + 3]
        body = data[i + 4:i + 4 + n]; i += 4 + n
        out.append(Rec(body) if flag == 0 else Pin(body))
    return out


def write_records(recs):
    out = bytearray()
    for r in recs:
        b = r.bytes()
        out += struct.pack('<H', len(b)) + b'\0' + bytes([0 if isinstance(r, Rec) else 1]) + b
    return bytes(out)


def read_sub(data):
    """PinFrac / PinTextData: header record + [(key, payload)]"""
    if not data:
        return None, []
    n = struct.unpack('<I', data[:4])[0] & 0xffffff
    hdr = Rec(data[4:4 + n]); i = 4 + n; out = []
    while i < len(data):
        l = struct.unpack('<I', data[i:i + 4])[0] & 0xffffff
        body = data[i + 4:i + 4 + l]; i += 4 + l
        nl = body[1]; key = body[2:2 + nl].decode(); zl = struct.unpack('<I', body[2 + nl:6 + nl])[0]
        out.append((key, zlib.decompress(body[6 + nl:6 + nl + zl])))
    return hdr, out


def write_sub(name, items):
    hb = f'|HEADER={name}|Weight={len(items)}'.encode() + b'\0'
    out = bytearray(struct.pack('<I', len(hb)) + hb)
    for key, payload in items:
        z = zlib.compress(payload)
        k = key.encode()
        body = b'\xd0' + bytes([len(k)]) + k + struct.pack('<I', len(z)) + z
        out += struct.pack('<I', len(body) | 0x01000000) + body
    return bytes(out)


def uid():
    return ''.join(random.choice(string.ascii_uppercase) for _ in range(8))


class Component:
    def __init__(self, node):
        self.node = node
        kids = {c.name: c for c in node.children}
        self.recs = read_records(kids['Data'].data)
        fr = kids.get('PinFrac'); td = kids.get('PinTextData')
        _, self.pinfrac = read_sub(fr.data) if fr else (None, [])
        _, self.pintext = read_sub(td.data) if td else (None, [])
        pins = self.pins()
        fracmap = {k: struct.unpack('<iii', v) for k, v in self.pinfrac}
        for i, p in enumerate(pins):
            p.frac = fracmap.get(str(i), (0, 0, 0))
        self.textmap = {int(k): v for k, v in self.pintext}
        for i, p in enumerate(pins):
            p.text = self.textmap.get(i)

    @property
    def name(self):
        return self.recs[0].get('LibReference')

    def pins(self):
        return [r for r in self.recs if isinstance(r, Pin)]

    def texts(self, rtype):
        return [r for r in self.recs if isinstance(r, Rec) and r.rtype == rtype]

    def store(self):
        # recompute OWNERINDEX links using object identity captured in link()
        for r in self.recs:
            if isinstance(r, Rec) and getattr(r, '_owner', None) is not None:
                r.set('OwnerIndex', str(self.recs.index(r._owner)))
        pins = self.pins()
        if getattr(self, 'pins_changed', False):
            self.recs[0].set('AllPinCount', str(len(pins)))
        kids = {c.name: c for c in self.node.children}
        kids['Data'].data = write_records(self.recs)
        frac = [(str(i), struct.pack('<iii', *p.frac)) for i, p in enumerate(pins) if any(p.frac)]
        text = [(str(i), p.text) for i, p in enumerate(pins) if getattr(p, 'text', None)]
        for nm, items in (('PinFrac', frac), ('PinTextData', text)):
            data = write_sub(nm, items)
            if nm in kids:
                kids[nm].data = data
            elif items:
                self.node.children.append(cfb.Node(nm, 2, data))

    def link(self):
        """remember OWNERINDEX targets as objects so records can be moved."""
        for r in self.recs:
            if isinstance(r, Rec) and r.get('OwnerIndex') is not None:
                r._owner = self.recs[int(r.get('OwnerIndex'))]


class SchLib:
    def __init__(self, path):
        self.path = path
        self.tree = cfb.tree_from_ole(path)
        self.nodes = {c.name: c for c in self.tree.children}
        self.header = self.nodes['FileHeader']
        self.comps = {}
        for c in self.tree.children:
            if c.typ == 1 and any(k.name == 'Data' for k in c.children):
                comp = Component(c)
                comp.link()
                self.comps[c.name] = comp

    # FileHeader: int32 len + text
    def header_rec(self):
        d = self.header.data
        n = struct.unpack('<I', d[:4])[0]
        return Rec(d[4:4 + n]), d[4 + n:]

    def set_header(self, rec, tail):
        b = rec.bytes()
        self.header.data = struct.pack('<I', len(b)) + b + tail

    def save(self, path=None):
        for c in self.comps.values():
            c.store()
        cfb.write(self.tree, path or self.path)
