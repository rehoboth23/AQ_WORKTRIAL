#!/usr/bin/env python3
"""
Generate address before/after TSV pairs from the retired normalisation engine.

Usage: python3 generate_data.py SEED COUNT MODE OUTPUT
  SEED:   random seed (42 for training data)
  COUNT:  number of address pairs to generate
  MODE:   'training' for diverse pairs, 'public' for simple single-rule pairs
  OUTPUT: path to write TSV file (one before<TAB>after pair per line)
"""
import random
import re
import sys


# ---------------------------------------------------------------------------
# Engine: exact reproduction of the retired normalisation engine
# ---------------------------------------------------------------------------
def engine_normalize(addr):
    """
    Apply the retired engine's ~25 ordered regex rewrite rules.
    Rule order matters when rules overlap.
    """
    # --- Cleanup phase (rules 1-5) ---
    # 1. Uppercase
    addr = addr.upper()
    # 2. Remove all periods
    addr = addr.replace('.', '')
    # 3. Remove all commas
    addr = addr.replace(',', '')
    # 4. Collapse whitespace to single space
    addr = re.sub(r'\s+', ' ', addr)
    # 5. Strip leading/trailing whitespace
    addr = addr.strip()

    # --- PO BOX normalization (rules 6-8b) ---
    # 6. P O BOX (with spaces) → PO BOX
    addr = re.sub(r'\bP\s+O\s+BOX\b', 'PO BOX', addr)
    # 7. PO BOX # NNN → PO BOX NNN  (remove # immediately after PO BOX)
    addr = re.sub(r'PO BOX # (\d)', r'PO BOX \1', addr)
    # 8. PO BOX <digits> APT → PO BOX <digits> #
    addr = re.sub(r'\bPO BOX (\d+) APT\b', r'PO BOX \1 #', addr)
    # 8b. PO BOX <digits> UNIT → PO BOX <digits> #
    addr = re.sub(r'\bPO BOX (\d+) UNIT\b', r'PO BOX \1 #', addr)

    # --- Direction expansion (rules 9-16) ---
    # Compound directions first (must precede single-letter rules)
    addr = re.sub(r'\bNE\b', 'NORTHEAST', addr)
    addr = re.sub(r'\bNW\b', 'NORTHWEST', addr)
    addr = re.sub(r'\bSE\b', 'SOUTHEAST', addr)
    addr = re.sub(r'\bSW\b', 'SOUTHWEST', addr)
    # Single-letter directions
    addr = re.sub(r'\bN\b', 'NORTH', addr)
    addr = re.sub(r'\bS\b', 'SOUTH', addr)
    addr = re.sub(r'\bE\b', 'EAST', addr)
    addr = re.sub(r'\bW\b', 'WEST', addr)

    # --- Unit designator normalization (rules 17-23) ---
    # SUITE→STE→# chain (order matters: 17 then 18)
    addr = re.sub(r'\bSUITE\b', 'STE', addr)
    addr = re.sub(r'\bSTE\b', '#', addr)
    addr = re.sub(r'\bAPT\b', '#', addr)
    addr = re.sub(r'\bUNIT\b', '#', addr)
    addr = re.sub(r'\bRM\b', 'ROOM', addr)
    addr = re.sub(r'\bBLDG\b', 'BUILDING', addr)
    addr = re.sub(r'\bFL\b', 'FLOOR', addr)

    # --- Street type expansion with position-dependent lookahead (rules 24-31) ---
    # Only expand when followed by end-of-string or a normalised unit designator
    _lookahead = r'(?=\s*$|\s+#|\s+ROOM|\s+BUILDING|\s+FLOOR)'
    for abbr, full in [('ST', 'STREET'), ('AVE', 'AVENUE'), ('RD', 'ROAD'),
                       ('DR', 'DRIVE'), ('LN', 'LANE'), ('BLVD', 'BOULEVARD'),
                       ('PL', 'PLACE'), ('CT', 'COURT')]:
        addr = re.sub(rf'\b{abbr}{_lookahead}', full, addr)

    # --- Final whitespace cleanup ---
    addr = re.sub(r'\s+', ' ', addr)
    addr = addr.strip()
    return addr


# ---------------------------------------------------------------------------
# Street-address components
# ---------------------------------------------------------------------------
STREET_NAMES = [
    'MAIN', 'OAK', 'PINE', 'ELM', 'CEDAR', 'MAPLE', 'BIRCH', 'WILLOW',
    'LAKE', 'HILL', 'PARK', 'RIVER', 'FOREST', 'VALLEY', 'CHURCH',
    'SPRING', 'MEADOW', 'CREEK', 'STONE', 'HARVEST', 'SUNSET', 'VIEW',
    'PIONEER', 'WALNUT', 'CHERRY', 'JUNIPER', 'HAWTHORN', 'BEECH',
    'HICKORY', 'SYCAMORE', 'ASPEN', 'MAGNOLIA', 'DOGWOOD', 'ASH',
    'CYPRESS', 'OLIVE', 'PALM', 'SPRUCE', 'POPLAR', 'SAND', 'ROCK',
    'SUMMIT', 'CREST', 'RIDGE', 'BROOK', 'GROVE', 'DALE', 'HARPER',
    'FLETCHER', 'WARREN', 'GRAHAM', 'COLBY', 'TANNER', 'BLAKE',
]
SAINT_NAMES = [
    'ANDREWS', 'MARK', 'JOHN', 'PAUL', 'LUKE', 'JAMES', 'MARY',
    'PETER', 'GEORGE', 'DAVID', 'STEPHEN', 'MICHAEL', 'FRANCIS',
    'ANNE', 'CATHERINE', 'ELIZABETH', 'PATRICK', 'JOSEPH',
]
DR_NAMES = ['MARTIN LUTHER KING', 'KING JR', 'SEUSS', 'PEPPER', 'WELLS']
NUMBERED_STREETS = [
    '1ST', '2ND', '3RD', '4TH', '5TH', '6TH', '7TH', '8TH', '9TH', '10TH',
    '11TH', '12TH', '21ST', '22ND', '23RD', '42ND', '45TH', '100TH',
]
STREET_TYPES = ['ST', 'AVE', 'RD', 'DR', 'LN', 'BLVD', 'PL', 'CT']
DIR_SINGLE = ['N', 'S', 'E', 'W']
DIR_COMPOUND = ['NE', 'NW', 'SE', 'SW']
DIR_WORDS = ['NORTH', 'SOUTH', 'EAST', 'WEST']
UNIT_DESIGS = ['SUITE', 'APT', 'UNIT', 'RM', 'BLDG', 'FL']


# ---------------------------------------------------------------------------
# Tiny helpers
# ---------------------------------------------------------------------------
def _ri(max_val=9999):
    return random.randint(1, max_val)

def _rc(seq):
    return random.choice(seq)

def _runit():
    if random.random() < 0.6:
        return str(_ri(199))
    return f'{_ri(49)}{_rc("ABCD")}'


# ---------------------------------------------------------------------------
# Noise / realism helpers
# ---------------------------------------------------------------------------
def _lower_all(s):
    return s.lower()

def _title_words(s):
    return ' '.join(w.capitalize() for w in s.split())

def _mixed_case(s):
    return ' '.join(w.lower() if random.random() < 0.5 else w for w in s.split())

def apply_case_noise(s):
    r = random.random()
    if r < 0.45:
        return s                    # all upper
    elif r < 0.65:
        return _lower_all(s)
    elif r < 0.80:
        return _title_words(s)
    else:
        return _mixed_case(s)


def add_comma_before_unit(s):
    """Insert a comma before the first unit designator found."""
    for ud in ['SUITE', 'STE', 'APT', 'UNIT', 'RM', 'BLDG', 'FL']:
        token = f' {ud} '
        idx = s.find(token)
        if idx > 0 and ',' not in s[:idx]:
            if random.random() < 0.5:
                return s[:idx] + ',' + s[idx:]
            break
    return s


def add_periods_to_abbrevs(s):
    """Sprinkle periods after abbreviations for realism."""
    mid = {
        ' ST ': ' ST. ', ' AVE ': ' AVE. ', ' RD ': ' RD. ',
        ' DR ': ' DR. ', ' LN ': ' LN. ', ' BLVD ': ' BLVD. ',
        ' PL ': ' PL. ', ' CT ': ' CT. ',
        ' N ': ' N. ', ' S ': ' S. ', ' E ': ' E. ', ' W ': ' W. ',
        ' NE ': ' N.E. ', ' NW ': ' N.W. ', ' SE ': ' S.E. ', ' SW ': ' S.W. ',
        ' APT ': ' APT. ', ' STE ': ' STE. ', ' SUITE ': ' SUITE. ',
        ' RM ': ' RM. ', ' BLDG ': ' BLDG. ', ' FL ': ' FL. ',
    }
    for orig, repl in mid.items():
        if orig in s and random.random() < 0.30:
            s = s.replace(orig, repl, 1)
    # end-of-string abbreviation
    for abbr in STREET_TYPES + DIR_SINGLE:
        if s.endswith(f' {abbr}') and random.random() < 0.25:
            s += '.'
    return s


def add_extra_whitespace(s):
    """Occasionally double a space."""
    if random.random() < 0.12:
        parts = s.split(' ')
        if len(parts) > 2:
            idx = random.randint(1, len(parts) - 1)
            parts.insert(idx, '')
            s = ' '.join(parts)
    return s


def apply_noise(addr):
    """Apply realistic noise (casing, punctuation, spacing) to an address."""
    # Comma before unit (while still uppercase so we can find it)
    if random.random() < 0.40:
        addr = add_comma_before_unit(addr)
    # Periods
    if random.random() < 0.25:
        addr = add_periods_to_abbrevs(addr)
    # Case
    addr = apply_case_noise(addr)
    # Extra whitespace
    if random.random() < 0.10:
        addr = add_extra_whitespace(addr)
    return addr


# ---------------------------------------------------------------------------
# Training-address generators
# ---------------------------------------------------------------------------
def gen_simple():
    return f'{_ri()} {_rc(STREET_NAMES)} {_rc(STREET_TYPES)}'

def gen_dir_single():
    return f'{_ri()} {_rc(DIR_SINGLE)} {_rc(STREET_NAMES)} {_rc(STREET_TYPES)}'

def gen_dir_compound():
    return f'{_ri()} {_rc(DIR_COMPOUND)} {_rc(STREET_NAMES)} {_rc(STREET_TYPES)}'

def gen_numbered_street():
    return f'{_ri()} {_rc(DIR_SINGLE)} {_rc(NUMBERED_STREETS)} {_rc(STREET_TYPES)}'

def gen_with_unit(ud=None):
    if ud is None:
        ud = _rc(UNIT_DESIGS)
    return f'{_ri()} {_rc(STREET_NAMES)} {_rc(STREET_TYPES)}, {ud} {_runit()}'

def gen_with_ste():
    return f'{_ri()} {_rc(STREET_NAMES)} {_rc(STREET_TYPES)}, STE {_runit()}'

def gen_compound_dir_unit():
    return (f'{_ri()} {_rc(DIR_COMPOUND)} {_rc(STREET_NAMES)} '
            f'{_rc(STREET_TYPES)}, {_rc(UNIT_DESIGS)} {_runit()}')

def gen_dir_unit_combo():
    d = _rc(DIR_SINGLE + DIR_COMPOUND)
    return (f'{_ri()} {d} {_rc(STREET_NAMES)} '
            f'{_rc(STREET_TYPES)}, {_rc(UNIT_DESIGS)} {_runit()}')

def gen_period_dir_unit():
    """3-rule chain: period direction + unit + street type."""
    d = _rc(DIR_COMPOUND)
    pd = '.'.join(d) + '.'
    return (f'{_ri()} {pd} {_rc(STREET_NAMES)} '
            f'{_rc(STREET_TYPES)}., {_rc(UNIT_DESIGS)} {_runit()}')

def gen_period_dir_simple():
    d = _rc(DIR_COMPOUND)
    pd = '.'.join(d) + '.'
    return f'{_ri()} {pd} {_rc(STREET_NAMES)} {_rc(STREET_TYPES)}.'

def gen_single_dir_period():
    return f'{_ri()} {_rc(DIR_SINGLE)}. {_rc(STREET_NAMES)} {_rc(STREET_TYPES)}.'

def gen_po_box():
    return f'PO BOX {_ri(9999)}'

def gen_po_box_spaces():
    return f'P O BOX {_ri(9999)}'

def gen_po_box_period():
    return f'P.O. BOX {_ri(9999)}'

def gen_po_box_apt():
    return f'PO BOX {_ri(9999)} APT {_runit()}'

def gen_po_box_unit():
    return f'PO BOX {_ri(9999)} UNIT {_runit()}'

def gen_po_box_hash():
    return f'PO BOX # {_ri(9999)}'

def gen_pobox_nospace():
    return f'POBOX {_ri(9999)}'

def gen_dir_word_street():
    return f'{_ri()} {_rc(DIR_WORDS)} {_rc(STREET_TYPES)}'

def gen_saint_name():
    return f'{_ri()} ST {_rc(SAINT_NAMES)} {_rc(STREET_TYPES)}'

def gen_dr_name():
    return f'{_ri()} DR {_rc(DR_NAMES)} {_rc(STREET_TYPES + ["BLVD"])}'

def gen_rm_bldg_fl():
    return f'{_ri()} {_rc(STREET_NAMES)} {_rc(STREET_TYPES)}, {_rc(["RM","BLDG","FL"])} {_runit()}'

def gen_complex():
    d = _rc(DIR_SINGLE + DIR_COMPOUND + [''])
    name = _rc(STREET_NAMES)
    st = _rc(STREET_TYPES)
    ud = _rc(UNIT_DESIGS + ['STE'])
    un = _runit()
    if d:
        return f'{_ri()} {d} {name} {st}, {ud} {un}'
    return f'{_ri()} {name} {st}, {ud} {un}'


# ---------------------------------------------------------------------------
# Plan: (generator, count) pairs
# ---------------------------------------------------------------------------
TRAINING_PLAN = [
    (gen_simple,             100),
    (gen_dir_single,          80),
    (gen_dir_compound,        40),
    (gen_numbered_street,     18),
    (gen_with_unit,           80),
    (gen_with_ste,            30),
    (gen_compound_dir_unit,   50),
    (gen_dir_unit_combo,      50),
    (gen_period_dir_unit,     30),
    (gen_period_dir_simple,   25),
    (gen_single_dir_period,   15),
    (gen_po_box,              55),
    (gen_po_box_spaces,       20),
    (gen_po_box_period,        5),
    (gen_po_box_apt,           3),
    (gen_po_box_unit,          2),
    (gen_po_box_hash,          3),
    (gen_pobox_nospace,        8),
    (gen_dir_word_street,     55),
    (gen_saint_name,          25),
    (gen_dr_name,              5),
    (gen_rm_bldg_fl,         45),
    (gen_complex,             65),
]

PUBLIC_PLAN = [
    (gen_simple,             15),
    (gen_dir_single,         10),
    (gen_with_unit,          10),
    (gen_with_ste,            3),
    (gen_po_box,              8),
    (gen_po_box_spaces,       5),
    (gen_rm_bldg_fl,          4),
    (gen_numbered_street,     3),
]


# ---------------------------------------------------------------------------
# Top-level generation
# ---------------------------------------------------------------------------
def generate_addresses(seed, count, plan):
    random.seed(seed)
    all_funcs = [p[0] for p in plan]

    addresses = []
    for func, cnt in plan:
        for _ in range(cnt):
            addresses.append(apply_noise(func()))

    # pad to count
    while len(addresses) < count:
        addresses.append(apply_noise(_rc(all_funcs)()))

    return addresses[:count]


def generate_public(seed, count):
    """Generate simple single-rule addresses for the public test set."""
    random.seed(seed)
    addresses = []
    for func, cnt in PUBLIC_PLAN:
        for _ in range(cnt):
            addr = func()
            # Limited noise for public tests (no near-misses or ordering traps)
            addr = apply_case_noise(addr)
            if random.random() < 0.30:
                addr = add_periods_to_abbrevs(addr)
            addresses.append(addr)
    while len(addresses) < count:
        addr = gen_simple()
        addr = apply_case_noise(addr)
        addresses.append(addr)
    return addresses[:count]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    seed   = int(sys.argv[1])
    count  = int(sys.argv[2])
    mode   = sys.argv[3] if len(sys.argv) > 3 else 'training'
    output = sys.argv[4] if len(sys.argv) > 4 else None

    if mode == 'training':
        addrs = generate_addresses(seed, count, TRAINING_PLAN)
    elif mode == 'public':
        addrs = generate_public(seed, count)
    else:
        raise ValueError(f'Unknown mode: {mode!r}')

    lines = []
    for addr in addrs:
        norm = engine_normalize(addr)
        lines.append(f'{addr}\t{norm}')

    content = '\n'.join(lines) + '\n'

    if output:
        with open(output, 'w') as f:
            f.write(content)
    else:
        sys.stdout.write(content)
