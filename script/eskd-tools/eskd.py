"""Bring the SchLib files to GOST (ESKD) conventions. Writes a change log."""
import sys, os, glob, collections, json, re
sys.path.insert(0, os.path.dirname(__file__))
import lib
from lib import Rec, Pin, MM
import refdes

LIB = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else LIB
os.makedirs(OUT, exist_ok=True)
LOG = collections.defaultdict(list)

IC_FILES = lambda f: f.startswith('ic-') or f in ('module.SchLib', 'optoelectronics.SchLib', 'oscilator.SchLib')
GRAPHIC = {'4', '5', '6', '7', '8', '11', '12', '13', '14'}
ROW = 5 * MM          # pin pitch 5 mm
X_L, X_M1, X_M2, X_R = 5 * MM, 15 * MM, 30 * MM, 40 * MM   # library 3-field layout


def log(fn, comp, msg):
    LOG[fn].append(f'{comp}: {msg}')


# ---------------- helpers for new primitives ----------------
def rect(part, x1, y1, x2, y2):
    r = Rec(pairs=[['RECORD', '14'], ['IsNotAccesible', 'T'], ['OwnerPartId', str(part)]])
    r.setnum('Location.X', x1); r.setnum('Location.Y', y1)
    r.setnum('Corner.X', x2); r.setnum('Corner.Y', y2)
    r.pairs += [['LineWidth', '1'], ['Color', '128'], ['AreaColor', '11599871'], ['UniqueID', lib.uid()]]
    return r


def poly(part, pts):
    r = Rec(pairs=[['RECORD', '6'], ['IsNotAccesible', 'T'], ['OwnerPartId', str(part)],
                   ['LineWidth', '1'], ['Color', '128'], ['LocationCount', str(len(pts))]])
    for i, (x, y) in enumerate(pts, 1):
        r.setnum(f'X{i}', x); r.setnum(f'Y{i}', y)
    r.pairs.append(['UniqueID', lib.uid()])
    return r


def label(part, x, y, text, font):
    r = Rec(pairs=[['RECORD', '4'], ['IsNotAccesible', 'T'], ['OwnerPartId', str(part)]])
    r.setnum('Location.X', x); r.setnum('Location.Y', y)
    r.pairs += [['FontID', str(font)], ['Justification', '1'], ['Text', text]]
    return r


def triangle(part, cx, ytop):
    """amplifier sign (GOST 2.759) 5x5 mm, left edge at cx-2.5 mm"""
    x0 = cx - 2.5 * MM
    return poly(part, [(x0, ytop), (x0, ytop - 5 * MM), (x0 + 5 * MM, ytop - 2.5 * MM), (x0, ytop)])


def hysteresis(part, x, y):
    """hysteresis sign (GOST 2.743), 3x2.5 mm, lower-left corner at (x, y)"""
    u = MM
    return [poly(part, [(x, y), (x + 2.5 * u, y), (x + 2.5 * u, y + 2.5 * u)]),
            poly(part, [(x + 1 * u, y), (x + 1 * u, y + 2.5 * u), (x + 3.5 * u, y + 2.5 * u)])]


def fully_inverted(name):
    """'S\\', 'O\\E\\' -> True ; 'A\\/B', 'R/W\\' -> False"""
    if '\\' not in name:
        return False
    chars = [c for c in name if c != '\\']
    return name.count('\\') == len(chars) and all(name[i + 1] == '\\' for i, c in enumerate(name) if c != '\\')


def main_font(comp):
    d = comp.texts('34')
    return int(d[0].get('FontID', 2)) if d else 2


def part_count(comp):
    return int(comp.recs[0].get('PartCount', '2')) - 1


def place_texts(comp, x_left):
    for r in comp.recs:
        if isinstance(r, Rec) and r.rtype == '34':
            r.setnum('Location.X', x_left); r.setnum('Location.Y', 2.5 * MM)
        if isinstance(r, Rec) and r.rtype == '41' and r.get('Name') == 'PartNumber' and r.get('IsHidden') != 'T':
            r.setnum('Location.X', x_left); r.setnum('Location.Y', 0.3 * MM)


# ---------------- rebuild of ANSI symbols ----------------
def rebuild(comp, fn, kind):
    """kind: 'amp' | ('gate', func, invert_out, schmitt)"""
    if comp.texts('14'):
        return          # already drawn as a GOST rectangle
    font = main_font(comp)
    parts = part_count(comp)
    pins = comp.pins()
    new_graphics = []
    power_pins = []
    gate_simple = isinstance(kind, tuple) and parts > 1
    for part in range(1, parts + 1):
        pp = [p for p in pins if p.owner == part]
        ins = sorted([p for p in pp if p.rot == 2], key=lambda p: -p.y)
        outs = sorted([p for p in pp if p.rot == 0], key=lambda p: -p.y)
        ups = [p for p in pp if p.rot == 1]
        downs = [p for p in pp if p.rot == 3]
        if isinstance(kind, tuple):
            _, func, inv, schmitt = kind
            vert = sorted(ups, key=lambda p: -p.y) + sorted(downs, key=lambda p: -p.y)
            for p in outs:
                if inv:
                    p.sym[1] = 1
            if gate_simple:
                power_pins += vert
                # simple element: main field only, 10 mm wide
                n = max(len(ins), 1)
                for i, p in enumerate(ins):
                    p.set_geom(X_L, -(i + 1) * ROW, ROW); p.flags &= ~0x08
                for i, p in enumerate(outs):
                    p.set_geom(X_L + 10 * MM, -(i + 1) * ROW, ROW); p.flags &= ~0x08
                bottom = -(n + 1) * ROW
                new_graphics.append(rect(part, X_L, bottom, X_L + 10 * MM, 0))
                cx = X_L + 5 * MM
                lx = cx - (2 * MM if schmitt else 0)
                new_graphics.append(label(part, lx, -4 * MM, func, font))
                if schmitt:
                    new_graphics += hysteresis(part, cx + 0.5 * MM, -4 * MM)
                continue
            left = [ins, vert]
            right = [outs]
        else:
            refs = [p for p in ups + downs if p.name.upper().startswith('REF')]
            vup = sorted([p for p in ups if p not in refs], key=lambda p: -p.y)
            vdn = sorted([p for p in downs if p not in refs], key=lambda p: -p.y)
            ins = ins + sorted(refs, key=lambda p: p.name)
            main_in = [p for p in ins if p.name.upper().replace(' ', '') not in ('REF', 'REF1', 'REF2', 'SHDN', 'EN', 'NC')]
            aux_in = [p for p in ins if p not in main_in]
            left = [main_in, aux_in]
            right = [vup, outs, vdn]
            for p in (main_in if kind == 'amp' else []):
                n = p.name.upper()
                if n.startswith('IN-') or n.startswith('-IN') or n == '-' or n.endswith('IN-'):
                    p.sym[1] = 1
        # 3-field layout
        def lay(groups, x, rot):
            y = -ROW; seps = []; first = True
            for g in groups:
                if not g:
                    continue
                if not first:
                    seps.append(y)
                    y -= ROW
                first = False
                for p in g:
                    p.set_geom(x, y, ROW)
                    p.flags = (p.flags & ~3) | rot | 0x08 | 0x10
                    y -= ROW
            return y, seps
        yl, sl = lay(left, X_L, 2)
        yr, sr = lay(right, X_R, 0)
        bottom = min(yl, yr)
        new_graphics.append(rect(part, X_L, bottom, X_R, 0))
        new_graphics.append(poly(part, [(X_M1, 0), (X_M1, bottom)]))
        new_graphics.append(poly(part, [(X_M2, 0), (X_M2, bottom)]))
        for y in sl:
            new_graphics.append(poly(part, [(X_L, y), (X_M1, y)]))
        for y in sr:
            new_graphics.append(poly(part, [(X_M2, y), (X_R, y)]))
        cx = (X_M1 + X_M2) / 2
        if kind == 'amp':
            new_graphics.append(triangle(part, cx, -2.5 * MM))
        elif isinstance(kind, tuple):
            _, func, inv, schmitt = kind
            new_graphics.append(label(part, cx - (2 * MM if schmitt else 0), -6.5 * MM, func, font))
            if schmitt:
                new_graphics += hysteresis(part, cx + 0.5 * MM, -6.5 * MM)
    if gate_simple and power_pins:
        # separate power section (GOST 2.743: power may be shown as a separate part)
        newpart = parts + 1
        seen = set()
        y = -ROW
        for p in sorted(power_pins, key=lambda p: p.rot):   # up (VCC) first
            if p.des in seen:
                comp.recs.remove(p); continue
            seen.add(p.des)
            p.owner = newpart
            p.set_geom(X_L, y, ROW)
            p.flags = (p.flags & ~3) | 2 | 0x08 | 0x10
            y -= ROW
        new_graphics.append(rect(newpart, X_L, y, X_L + 10 * MM, 0))
        comp.recs[0].set('PartCount', str(newpart + 1))
        log(fn, comp.name, f'power pins moved to separate section (part {newpart})')
    # name unnamed power pins
    for p in comp.pins():
        if p.name.strip() == '' and p.elec in (4, 7):
            p.name = POWER_NAMES.get((comp.name, p.des), '')
    for p in comp.pins():
        p.text = None
    # replace graphics
    comp.recs = [r for r in comp.recs if not (isinstance(r, Rec) and r.rtype in GRAPHIC)]
    first_pin = next(i for i, r in enumerate(comp.recs) if isinstance(r, Pin))
    comp.recs[first_pin:first_pin] = new_graphics
    place_texts(comp, X_L)
    comp.pins_changed = True
    log(fn, comp.name, 'redrawn from ANSI shape to GOST 2.743/2.759 rectangle' + (f' ({kind[1]})' if isinstance(kind, tuple) else ' (amplifier sign)' if kind == 'amp' else ''))


POWER_NAMES = {
    ('HEF4001BT', '7'): 'VSS', ('HEF4001BT', '14'): 'VDD',
}
for c in ['SN74LVC1G11DBVR', 'SN74LVC1G27DBVR', 'SN74LVC1G332DBVR']:
    POWER_NAMES[(c, '2')] = 'GND'; POWER_NAMES[(c, '5')] = 'VCC'
for c in ['SN74LVC1G86DBVR', 'SN74LVC1GU04', 'SN74AUP1G17DBVR']:
    POWER_NAMES[(c, '3')] = 'GND'; POWER_NAMES[(c, '5')] = 'VCC'
for c in ['SN74LVC2G14DBVR', 'SN74LVC2G17DCKR', 'SN74LVC2G34DBVR']:
    POWER_NAMES[(c, '2')] = 'GND'; POWER_NAMES[(c, '5')] = 'VCC'
for c in ['SN74AUP2G08DCUR', 'SN74AUP3G34DCUR', 'SN74LVC2G132DCUR']:
    POWER_NAMES[(c, '4')] = 'GND'; POWER_NAMES[(c, '8')] = 'VCC'

GATES = {
    'HEF4001BT': ('&', True, True),          # really HEF4093BT (see report)
    'SN74AUP1G17DBVR': ('1', False, True),
    'SN74AUP2G08DCUR': ('&', False, False),
    'SN74AUP3G34DCUR': ('1', False, False),
    'SN74LVC1G11DBVR': ('&', False, False),
    'SN74LVC1G27DBVR': ('1', True, False),
    'SN74LVC1G332DBVR': ('1', False, False),
    'SN74LVC1G86DBVR': ('=1', False, False),
    'SN74LVC1GU04': ('1', True, False),
    'SN74LVC2G132DCUR': ('&', True, True),
    'SN74LVC2G14DBVR': ('1', True, True),
    'SN74LVC2G17DCKR': ('1', False, True),
    'SN74LVC2G34DBVR': ('1', False, False),
}
AMPS = {
    'ic-amplifier.SchLib': ['INA826AIDGKR', 'LMV321IDBVR', 'LMV611MFX_NOPB', 'MAX4466EXK+T', 'OA Type1',
                            'OA Type1 + Compensation', 'OA x2 Type1', 'OA x4 Type1', 'OPA2227UA',
                            'OPA320AIDBVR', 'TSV991ILT'],
    'ic-comparator.SchLib': ['LMV7271MF_NOPB', 'MCP6541T-I_OT', 'NCS2250SN2T1G', 'TLV3491AIDBVR'],
    'ic-sensor.SchLib': ['INA180A3IDBVR', 'INA181A1IDBVR', 'INA197AIDBVR', 'INA199A1DCKR', 'INA282AIDGKR'],
}
PLAIN3 = {'ic-sensor.SchLib': ['MCP9700AT', 'TMP235A2DCKR']}

# exposed pads that the datasheet requires to be tied to ground but that have no pin in the symbol
EP_ADD = {
    'ic-adc-dac-dds.SchLib': ['LTC2204CUK'],
    'ic-amplifier.SchLib': ['LM4673SD_NOPB'],
    'ic-gate-driver.SchLib': ['DRV8353RSRGZT', 'LM5101ASD', 'LM5109BSD_NOPB'],
    'ic-mcu.SchLib': ['ESP8266EX', 'MSP432P401MIRGCT', 'NRF52832-QFAA-R', 'STM32F401CCU6', 'STM32F410CBU6'],
    'ic-power-module.SchLib': ['TMC2209'],
    'ic-sensor.SchLib': ['MAX30205MTA+_1'],
}
PIN_RENAME = {
    ('ic-interface.SchLib', 'CH340G'): {'12': 'D\\C\\D\\', '9': 'C\\T\\S\\', '10': 'D\\S\\R\\', '11': 'R\\I\\',
                                         '13': 'D\\T\\R\\', '14': 'R\\T\\S\\'},
    ('ic-interface.SchLib', 'DS90LV047'): {'9': 'DOUT4-', '13': 'DOUT2-', '8': 'E\\N\\'},
    ('ic-power-controller.SchLib', 'LM5060MM/NOPB'): {'8': 'P\\G\\D\\'},
    ('ic-sensor.SchLib', 'SPL06-001'): {'2': 'C\\S\\B\\'},
    ('ic-memory.SchLib', 'AT45DB041E'): {'3': 'R\\E\\S\\E\\T\\', '4': 'C\\S\\', '5': 'W\\P\\'},
}
PIN_ADD = {
    # TPS736xx DBV: pin 4 = NR (fixed versions) / FB (adjustable)
    ('ic-power-linear-reg.SchLib', 'TPS736**DVBR'): ('4', 'NR/FB', 4, 2),
}
FOOTPRINT_FIX = {
    # AP3417C is a 5-pin SOT-23-5 part; it was linked to the SOT23-6 land pattern
    ('ic-power-switchmode.SchLib', 'AP3417CKTR-G1'): ('SOT23-6', 'SOT23-5'),
}
GND_NAMES = ('GND', 'VSS', 'AGND', 'DGND', 'PGND', 'GNDA', 'VSSA', 'SGND', 'GND_PAD')


def part_graphics(comp, part):
    return [r for r in comp.recs if isinstance(r, Rec) and r.rtype in GRAPHIC and r.get('OwnerPartId') == str(part)]


def graphic_points(r):
    t = r.rtype
    if t in ('14', '13'):
        return [('Location.X', 'Location.Y'), ('Corner.X', 'Corner.Y')]
    if t in ('6', '7', '5'):
        n = int(r.get('LocationCount', 0))
        return [(f'X{i}', f'Y{i}') for i in range(1, n + 1)]
    return [('Location.X', 'Location.Y')]


def add_ep(comp, fn, des='0', forced=None):
    """forced = (name, elec, rot): add an arbitrary pin under the lowest pin on that side"""
    pins = comp.pins()
    if any(p.des == des for p in pins):
        return
    gnd = [p for p in pins if p.mode == 0 and ('GND' in p.name.upper() or 'VSS' in p.name.upper())]
    epname = 'EP'
    exact = [p for p in gnd if p.name.strip().upper() in GND_NAMES]
    if forced:
        epname = forced[0]
        ref = min([p for p in pins if p.mode == 0 and p.rot == forced[2]], key=lambda p: p.y)
    elif gnd:
        ref = min(exact or gnd, key=lambda p: p.y)
    else:
        # no ground pin at all: the exposed pad is the only ground (e.g. ESP8266EX pin 33 GND)
        ref = min([p for p in pins if p.mode == 0 and p.rot == 0], key=lambda p: p.y)
        epname = 'GND'
    part = ref.owner
    side = [p for p in pins if p.owner == part and p.rot == ref.rot and abs(p.x - ref.x) < 0.5 and p.mode == 0]
    lowest = min(side, key=lambda p: p.y)
    newy = lowest.y - ROW
    graphics = part_graphics(comp, part)
    sep = None
    if forced or epname == 'GND' or not ('GND' in lowest.name.upper() or 'VSS' in lowest.name.upper()):
        # start a new group: blank row + separator line in the side field
        sep_y = newy
        newy -= ROW
        vx = [r.num('X1') for r in graphics if r.rtype == '6' and r.get('LocationCount') == '2'
              and abs(r.num('X1') - r.num('X2')) < 0.01]
        inner = [x for x in vx if (x < ref.x - 0.5 if ref.rot == 0 else x > ref.x + 0.5)]
        if inner:
            xin = max(inner) if ref.rot == 0 else min(inner)
            sep = poly(part, [(ref.x, sep_y), (xin, sep_y)])
    ys = [r.num(ky) for r in graphics if r.rtype in ('14', '6', '13') for kx, ky in graphic_points(r)]
    bottom = min(ys)
    if newy - bottom < ROW - 0.5:
        shift = ROW - (newy - bottom)
        for r in graphics:
            for kx, ky in graphic_points(r):
                if abs(r.num(ky) - bottom) < 0.5:
                    r.setnum(ky, bottom - shift)
        # hidden/visible texts placed under the body move too
        for r in comp.recs:
            if isinstance(r, Rec) and r.rtype in ('41', '34') and r.get('Location.Y') is not None and r.num('Location.Y') < bottom + 0.5:
                r.setnum('Location.Y', r.num('Location.Y') - shift)
    if sep is not None:
        first_pin = next(i for i, r in enumerate(comp.recs) if isinstance(r, Pin))
        comp.recs.insert(first_pin, sep)
    p = Pin(ref.bytes())
    p.frac = ref.frac
    p.set_geom(ref.x, newy, ref.length)
    p.name, p.des, p.elec = epname, des, (forced[1] if forced else 7)
    p.sym = [0, 0, 0, 0]
    p.text = getattr(ref, 'text', None)
    idx = comp.recs.index(side[-1]) if side else comp.recs.index(ref)
    last_pin = max(i for i, r in enumerate(comp.recs) if isinstance(r, Pin))
    comp.recs.insert(last_pin + 1, p)
    comp.pins_changed = True
    log(fn, comp.name, f'added pin {des} "{epname}"' + ('' if forced else ' (exposed pad)') + f' below {ref.name.strip()}')


def fix_logic_details(comp, fn):
    font = main_font(comp)
    if comp.name == 'SN74AUP1G74DCUR':
        for p in comp.pins():
            if p.name == 'CLK' and p.sym[0] != 3:
                p.sym[0] = 3; log(fn, comp.name, 'CLK: added dynamic input indicator')
            if p.name == 'P\\R\\E':
                p.name = 'P\\R\\E\\'; log(fn, comp.name, 'PRE: overbar fixed (P\\R\\E -> P\\R\\E\\)')
    labels = {'74ALVC74': 'T', 'SN74AUP1G74DCUR': 'T', '74HC4051D': 'MUX', '74LVC157': 'MUX'}
    if comp.name in labels:
        want = labels[comp.name]
        for part in range(1, part_count(comp) + 1):
            ex = [r for r in comp.texts('4') if r.get('OwnerPartId') == str(part)]
            if ex:
                for r in ex:
                    if r.get('Text') != want:
                        log(fn, comp.name, f'main field label {r.get("Text")} -> {want}')
                        r.set('Text', want)
                continue
            vx = sorted({round(r.num('X1'), 2) for r in part_graphics(comp, part)
                         if r.rtype == '6' and r.get('LocationCount') == '2' and abs(r.num('X1') - r.num('X2')) < 0.01})
            rc = [r for r in part_graphics(comp, part) if r.rtype == '14'][0]
            xs = sorted([rc.num('Location.X'), rc.num('Corner.X')])
            inner = [x for x in vx if xs[0] + 1 < x < xs[1] - 1]
            if len(inner) >= 2:
                cx = (inner[0] + inner[-1]) / 2
            else:
                cx = sum(xs) / 2
            top = max(rc.num('Location.Y'), rc.num('Corner.Y'))
            lb = label(part, cx, top - 6.5 * MM, want, font)
            first_pin = next(i for i, r in enumerate(comp.recs) if isinstance(r, Pin))
            comp.recs.insert(first_pin, lb)
            log(fn, comp.name, f'main field label "{want}" added')


def fonts(L, fn):
    hdr, tail = L.header_rec()
    changed = []
    for p in hdr.pairs:
        if p[0] and p[0].upper().startswith('FONTNAME') and p[1] != 'ISOCPEUR':
            changed.append(f'{p[0]}: {p[1]} -> ISOCPEUR')
            p[1] = 'ISOCPEUR'
    L.set_header(hdr, tail)
    if changed:
        LOG[fn].append('fonts: ' + '; '.join(changed))


def header_partcounts(L):
    hdr, tail = L.header_rec()
    n = int(hdr.get('CompCount', 0))
    by = {c.name: c for c in L.comps.values()}
    for i in range(n):
        ref = hdr.get(f'LibRef{i}')
        if ref in by:
            hdr.set(f'PartCount{i}', by[ref].recs[0].get('PartCount'))
    L.set_header(hdr, tail)


def process(path):
    fn = os.path.basename(path)
    L = lib.SchLib(path)
    fonts(L, fn)
    for sname, comp in L.comps.items():
        comp.sname = sname
        # designators
        for d in comp.texts('34'):
            cur = d.get('Text', '')
            new = refdes.prefix(fn, comp.name, cur, comp.recs[0].get('ComponentDescription'))
            if new and cur.rstrip('?*') != new:
                d.set('Text', new + '?')
                log(fn, comp.name, f'designator {cur} -> {new}?')
        if fn == 'ic-logic.SchLib' and comp.name in GATES:
            f, inv, sch = GATES[comp.name]
            rebuild(comp, fn, ('gate', f, inv, sch))
        if sname in AMPS.get(fn, []):
            rebuild(comp, fn, 'amp')
        if sname in PLAIN3.get(fn, []):
            rebuild(comp, fn, 'plain')
        if fn == 'ic-logic.SchLib':
            fix_logic_details(comp, fn)
        for d_, nm in PIN_RENAME.get((fn, comp.name), {}).items():
            for p in comp.pins():
                if p.des == d_ and p.name != nm:
                    log(fn, comp.name, f'pin {d_}: name {p.name!r} -> {nm!r}')
                    p.name = nm
        if (fn, comp.name) in PIN_ADD:
            d_, nm, el, rot = PIN_ADD[(fn, comp.name)]
            add_ep(comp, fn, d_, (nm, el, rot))
        if (fn, comp.name) in FOOTPRINT_FIX:
            old, new = FOOTPRINT_FIX[(fn, comp.name)]
            for r in comp.texts('45'):
                if r.get('ModelName') == old:
                    r.set('ModelName', new); r.set('ModelDatafileEntity0', new)
                    log(fn, comp.name, f'footprint {old} -> {new}')
        if sname in EP_ADD.get(fn, []):
            add_ep(comp, fn)
        if fn in ('ic-amplifier.SchLib', 'ic-comparator.SchLib'):
            for p in comp.pins():
                n = p.name.upper().replace(' ', '')
                if re.fullmatch(r'(IN[A-D]?-|-IN[A-D]?|IN-[A-D]?)', n) and p.sym[1] == 0:
                    p.sym[1] = 1
                    log(fn, comp.name, f'pin {p.des} {p.name}: inversion indicator (inverting input)')
        if IC_FILES(fn):
            for p in comp.pins():
                if fully_inverted(p.name) and p.sym[1] == 0:
                    p.sym[1] = 1
                    log(fn, comp.name, f'pin {p.des} {p.name}: inversion indicator added')
    header_partcounts(L)
    L.save(os.path.join(OUT, fn))


for f in sorted(glob.glob(os.path.join(LIB, '*.SchLib'))):
    process(f)
json.dump(LOG, open(os.path.join(OUT, 'eskd-changelog.json'), 'w'), ensure_ascii=False, indent=1)
print(sum(len(v) for v in LOG.values()), 'changes')
