#!/usr/bin/env python3
"""
Generate training and public-test flow data for the Sentinel-7 IDS
rule-inference task.

Produces (under OUTPUT_DIR, default /output):
  flows_train.csv                 ~40 000 labelled flows (seed 42)
  public_test/flows.csv           500 unlabelled flows (seed 99)
  public_test/expected.csv        500 expected decisions

Run at Docker build time.  The generator and all rule constants are
excluded from the final image by the multi-stage Dockerfile.
"""

import csv
import os
import random
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ═══════════════════════════════════════════════════════════════════════
# Rule constants  —  NOT shipped to the final image
# ═══════════════════════════════════════════════════════════════════════
ALLOWED_IPS = {'10.0.0.1', '10.0.0.2', '10.0.0.3'}
RATE_THRESHOLD = 50
RATE_WINDOW = 60.0                # seconds, inclusive at both ends
PORT_SCAN_MIN = 1
PORT_SCAN_MAX = 1023              # inclusive
PORT_SCAN_MAX_PACKETS = 2         # ≤ 2  (inclusive)
HTTPS_PORT = 443
AFTER_HOURS = {0, 1, 2, 3, 4, 5}
EXFIL_THRESHOLD = 10_000_000      # strict  >
SENSOR_TZ = ZoneInfo('America/Chicago')

OUTPUT_DIR = os.environ.get('OUTPUT_DIR', '/output')
PT_DIR = os.path.join(OUTPUT_DIR, 'public_test')

# ═══════════════════════════════════════════════════════════════════════
# Timestamp helpers
# ═══════════════════════════════════════════════════════════════════════

def parse_ts(s: str) -> datetime:
    """'YYYY-MM-DDTHH:MM:SSZ'  →  aware UTC datetime."""
    return datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)


def ts_float(s: str) -> float:
    """Timestamp string  →  Unix timestamp (float)."""
    return parse_ts(s).timestamp()


def fmt_ts(dt: datetime) -> str:
    """Aware datetime  →  'YYYY-MM-DDTHH:MM:SSZ'."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def local_hour(s: str) -> int:
    """UTC timestamp string  →  hour in America/Chicago."""
    return parse_ts(s).astimezone(SENSOR_TZ).hour


def random_utc_ts(year: int = 2024) -> str:
    """Random UTC timestamp anywhere in *year*."""
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    secs = random.randint(0, int((end - start).total_seconds()) - 1)
    return fmt_ts(start + timedelta(seconds=secs))


def utc_at(y, m, d, h, minute=None, second=None) -> str:
    """Build a UTC timestamp from components."""
    minute = minute if minute is not None else random.randint(0, 59)
    second = second if second is not None else random.randint(0, 59)
    return fmt_ts(datetime(y, m, d, h, minute, second, tzinfo=timezone.utc))


def local_at(y, m, d, h, minute=None, second=None) -> str:
    """Build a UTC timestamp that maps to a given America/Chicago local hour."""
    minute = minute if minute is not None else random.randint(0, 59)
    second = second if second is not None else random.randint(0, 59)
    return fmt_ts(datetime(y, m, d, h, minute, second, tzinfo=SENSOR_TZ))


# ═══════════════════════════════════════════════════════════════════════
# Rule engine
# ═══════════════════════════════════════════════════════════════════════

def compute_rate_counts(flows: list) -> list:
    """For each flow, count flows from the same src_ip in [t-60, t] inclusive."""
    by_src: dict[str, list] = defaultdict(list)
    for i, f in enumerate(flows):
        by_src[f['src_ip']].append((ts_float(f['timestamp']), i))

    counts = [0] * len(flows)
    for entries in by_src.values():
        entries.sort()
        times = [e[0] for e in entries]
        idxs = [e[1] for e in entries]
        for j in range(len(entries)):
            t = times[j]
            lo = bisect_left(times, t - RATE_WINDOW)
            hi = bisect_right(times, t)
            counts[idxs[j]] = hi - lo
    return counts


def decide_one(flow: dict, rc: int) -> str:
    """Apply the eight ordered rules; return 'flag' or 'pass'."""
    sip = flow['src_ip']
    dip = flow['dst_ip']
    dp = int(flow['dst_port'])
    pr = flow['protocol']
    pk = int(flow['packets'])
    bt = int(flow['bytes'])

    # 1 — allow-list
    if sip in ALLOWED_IPS:
        return 'pass'
    # 2 — internal destination
    if dip.startswith('10.'):
        return 'pass'
    # 3 — rate limit  (strictly greater than threshold)
    if rc > RATE_THRESHOLD:
        return 'flag'
    # 4 — HTTPS pass
    if dp == HTTPS_PORT and pr == 'TCP':
        return 'pass'
    # 5 — port scan
    if (PORT_SCAN_MIN <= dp <= PORT_SCAN_MAX
            and pr == 'TCP'
            and pk <= PORT_SCAN_MAX_PACKETS):
        return 'flag'
    # 6 — after-hours  (local hour 0-5)
    if local_hour(flow['timestamp']) in AFTER_HOURS:
        return 'flag'
    # 7 — data exfiltration  (strictly greater than threshold)
    if bt > EXFIL_THRESHOLD and pr == 'TCP':
        return 'flag'
    # 8 — default
    return 'pass'


def label_all(flows: list) -> list:
    """Add 'decision' key to every flow dict (in place)."""
    counts = compute_rate_counts(flows)
    for i, f in enumerate(flows):
        f['decision'] = decide_one(f, counts[i])
    return flows


# ═══════════════════════════════════════════════════════════════════════
# IP / port helpers
# ═══════════════════════════════════════════════════════════════════════

_EXT_PREFIXES = [
    (192, 168), (172, 16), (203, 0), (198, 51),
    (45, 10), (91, 200), (77, 50), (55, 25),
    (88, 99), (37, 120), (109, 70), (51, 15),
]

def rand_ext_ip() -> str:
    a, b = random.choice(_EXT_PREFIXES)
    return f"{a}.{b}.{random.randint(0, 255)}.{random.randint(1, 254)}"

def rand_int_ip() -> str:
    return f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"

_COMMON_PORTS = [80, 443, 22, 53, 25, 8080, 3389, 21, 23,
                 110, 143, 993, 995, 587, 3306, 5432, 6379, 27017, 9200]

def rand_port() -> int:
    return random.choice(_COMMON_PORTS + [random.randint(1, 65535)])


# ═══════════════════════════════════════════════════════════════════════
# Flow factory
# ═══════════════════════════════════════════════════════════════════════

def mk_flow(fid: int, **kw) -> dict:
    """Create a flow dict; any field can be overridden via kwargs."""
    f = {
        'flow_id':    str(fid),
        'timestamp':  kw['timestamp']  if 'timestamp'  in kw else random_utc_ts(),
        'src_ip':     kw['src_ip']     if 'src_ip'     in kw else rand_ext_ip(),
        'src_port':   kw['src_port']   if 'src_port'   in kw else random.randint(1024, 65535),
        'dst_ip':     kw['dst_ip']     if 'dst_ip'     in kw else rand_ext_ip(),
        'dst_port':   kw['dst_port']   if 'dst_port'   in kw else rand_port(),
        'protocol':   kw['protocol']   if 'protocol'   in kw else random.choice(['TCP', 'UDP']),
        'bytes':      kw['bytes']      if 'bytes'      in kw else random.randint(100, 5_000_000),
        'packets':    kw['packets']    if 'packets'    in kw else random.randint(1, 100),
    }
    return f


# ═══════════════════════════════════════════════════════════════════════
# Training-data generator  (seed 42)
# ═══════════════════════════════════════════════════════════════════════

def gen_training(seed: int = 42) -> list:
    random.seed(seed)
    flows: list = []
    fid = 0

    # Pool of background source IPs
    bg_srcs = [rand_ext_ip() for _ in range(300)]
    bg_src_set = set(bg_srcs)
    burst_used: set = set()

    def new_burst_src() -> str:
        while True:
            ip = rand_ext_ip()
            if ip not in bg_src_set and ip not in burst_used:
                burst_used.add(ip)
                return ip

    allowed_sorted = sorted(ALLOWED_IPS)

    # ── 1.  Background flows  (15 000) ──────────────────────────────
    for _ in range(15000):
        flows.append(mk_flow(fid, src_ip=random.choice(bg_srcs)))
        fid += 1

    # ── 2.  Internal-destination flows  (3 000) ─────────────────────
    for _ in range(3000):
        flows.append(mk_flow(fid, dst_ip=rand_int_ip(),
                             src_ip=random.choice(bg_srcs)))
        fid += 1

    # ── 3.  Allow-list flows  (2 000)  — scans, after-hours, exfil ─
    #        all should be labelled 'pass'
    for _ in range(2000):
        al = allowed_sorted[random.randint(0, 2)]
        sc = random.choice(['normal', 'scan', 'afterhours', 'exfil'])
        if sc == 'scan':
            flows.append(mk_flow(fid, src_ip=al,
                                 dst_port=random.randint(1, 1023),
                                 protocol='TCP', packets=random.randint(1, 2),
                                 dst_ip=rand_ext_ip()))
        elif sc == 'afterhours':
            flows.append(mk_flow(fid, src_ip=al,
                                 timestamp=local_at(2024,
                                                    random.randint(1, 12),
                                                    random.randint(1, 28),
                                                    random.randint(0, 5)),
                                 dst_ip=rand_ext_ip()))
        elif sc == 'exfil':
            flows.append(mk_flow(fid, src_ip=al,
                                 bytes=random.randint(11_000_000, 100_000_000),
                                 protocol='TCP', dst_ip=rand_ext_ip()))
        else:
            flows.append(mk_flow(fid, src_ip=al, dst_ip=rand_ext_ip()))
        fid += 1

    # ── 4.  Rate bursts  (~6 200)  — sizes near and far from threshold
    burst_sizes = [10, 15, 20, 25, 30, 35, 40, 45,
                   46, 47, 48, 49, 50, 51, 52, 53,
                   55, 60, 65, 70, 80, 100]
    for _ in range(120):
        bs = new_burst_src()
        base = parse_ts(random_utc_ts())
        n = random.choice(burst_sizes)
        for _ in range(n):
            off = random.randint(0, 58)
            ts = fmt_ts(base + timedelta(seconds=off))
            r = random.random()
            if r < 0.10:
                flows.append(mk_flow(fid, src_ip=bs, timestamp=ts,
                                     dst_port=443, protocol='TCP',
                                     packets=random.randint(1, 50),
                                     dst_ip=rand_ext_ip()))
            elif r < 0.20:
                flows.append(mk_flow(fid, src_ip=bs, timestamp=ts,
                                     dst_port=random.randint(1, 1023),
                                     protocol='TCP',
                                     packets=random.randint(1, 2),
                                     dst_ip=rand_ext_ip()))
            else:
                flows.append(mk_flow(fid, src_ip=bs, timestamp=ts,
                                     dst_ip=rand_ext_ip()))
            fid += 1

    # ── 5.  Window-edge quirk evidence  (50 groups ≈ 2 475) ─────────
    #        groups of ~47-50 flows within 1 s, then one flow at
    #        exactly +60.0 s — counted by the inclusive window
    for _ in range(50):
        es = new_burst_src()
        base = parse_ts(random_utc_ts())
        n = random.randint(47, 50)
        for _ in range(n):
            off = random.randint(0, 1)
            ts = fmt_ts(base + timedelta(seconds=off))
            flows.append(mk_flow(fid, src_ip=es, timestamp=ts,
                                 dst_ip=rand_ext_ip()))
            fid += 1
        # flow exactly 60 s later — its [t-60, t] window includes all
        ts_edge = fmt_ts(base + timedelta(seconds=60))
        flows.append(mk_flow(fid, src_ip=es, timestamp=ts_edge,
                             dst_ip=rand_ext_ip()))
        fid += 1

    # ── 6.  Port-scan boundary flows  (2 000) ───────────────────────
    for _ in range(2000):
        port = random.choice([1, 22, 80, 443, 1023, 1024, 8080,
                              random.randint(1, 1023),
                              random.randint(1024, 65535)])
        pkts = random.choice([1, 2, 3, 4, random.randint(1, 10)])
        flows.append(mk_flow(fid, dst_port=port, protocol='TCP',
                             packets=pkts,
                             src_ip=random.choice(bg_srcs),
                             dst_ip=rand_ext_ip(),
                             timestamp=local_at(2024,
                                                random.randint(6, 12),
                                                random.randint(1, 28),
                                                random.randint(10, 16))))
        fid += 1

    # ── 7.  After-hours boundary flows  (2 000) ─────────────────────
    for _ in range(2000):
        m, d = random.randint(1, 12), random.randint(1, 28)
        h = random.choice([0, 1, 2, 3, 4, 5, 6, 7, 22, 23, 12, 15])
        ts = local_at(2024, m, d, h)
        flows.append(mk_flow(fid, timestamp=ts,
                             src_ip=random.choice(bg_srcs),
                             dst_ip=rand_ext_ip(),
                             protocol='UDP',
                             dst_port=random.randint(20000, 60000)))
        fid += 1

    # ── 8.  Exfiltration boundary flows  (1 000) ────────────────────
    for _ in range(1000):
        byts = random.choice([
            10_000_000,      # exactly at threshold → pass
            10_000_001,      # just over            → flag
            9_999_999,       # just under           → pass
            15_000_000,      # clearly over         → flag
            50_000_000,      # clearly over         → flag
            5_000_000,       # clearly under        → pass
            random.randint(9_500_000, 10_500_000),
        ])
        flows.append(mk_flow(fid, bytes=byts, protocol=random.choice(['TCP', 'TCP', 'TCP', 'UDP']),
                             src_ip=random.choice(bg_srcs),
                             dst_ip=rand_ext_ip(),
                             timestamp=local_at(2024,
                                                random.randint(6, 12),
                                                random.randint(1, 28),
                                                random.randint(10, 16))))
        fid += 1

    # ── 9.  DST transition flows  (800) ─────────────────────────────
    # March 10 — spring forward (hour 2 does not exist)
    for _ in range(400):
        h = random.choice([0, 1, 3, 4, 5, 6, 12, 18])
        ts = local_at(2024, 3, 10, h, minute=random.randint(0, 59))
        flows.append(mk_flow(fid, timestamp=ts,
                             src_ip=random.choice(bg_srcs),
                             dst_ip=rand_ext_ip(),
                             protocol='UDP',
                             dst_port=random.randint(20000, 60000)))
        fid += 1
    # November 3 — fall back (hour 1 occurs twice: CDT then CST)
    for _ in range(400):
        h_utc = random.choice([5, 6, 7, 8, 9, 12, 18])
        ts = utc_at(2024, 11, 3, h_utc, minute=random.randint(0, 59))
        flows.append(mk_flow(fid, timestamp=ts,
                             src_ip=random.choice(bg_srcs),
                             dst_ip=rand_ext_ip(),
                             protocol='UDP',
                             dst_port=random.randint(20000, 60000)))
        fid += 1

    # ── 10.  HTTPS + after-hours overlap  (500) ─────────────────────
    for _ in range(500):
        m, d = random.randint(1, 12), random.randint(1, 28)
        h = random.choice([0, 1, 2, 3, 4, 5, 6])
        ts = local_at(2024, m, d, h)
        pkts = random.choice([1, 2, 3, 10])
        flows.append(mk_flow(fid, timestamp=ts,
                             dst_port=443, protocol='TCP',
                             packets=pkts,
                             src_ip=random.choice(bg_srcs),
                             dst_ip=rand_ext_ip()))
        fid += 1

    # ── 11.  Fill to 40 000 ─────────────────────────────────────────
    while fid < 40000:
        flows.append(mk_flow(fid))
        fid += 1

    # Shuffle so row order is not flow_id order
    random.shuffle(flows)

    # Label every flow
    label_all(flows)
    return flows


# ═══════════════════════════════════════════════════════════════════════
# Public-test generator  (seed 99)  — common-path, far from boundaries
# ═══════════════════════════════════════════════════════════════════════

def gen_public_test(seed: int = 99) -> list:
    random.seed(seed)
    flows: list = []
    fid = 0

    allowed_sorted = sorted(ALLOWED_IPS)
    pt_srcs: set = set()

    def pt_src() -> str:
        while True:
            ip = rand_ext_ip()
            if ip not in pt_srcs:
                pt_srcs.add(ip)
                return ip

    # 3 clear rate violations  (60 flows each = 180)
    for _ in range(3):
        bs = pt_src()
        base = parse_ts(random_utc_ts())
        for _ in range(60):
            off = random.randint(0, 30)
            ts = fmt_ts(base + timedelta(seconds=off))
            flows.append(mk_flow(fid, src_ip=bs, timestamp=ts,
                                 dst_ip=rand_ext_ip(),
                                 dst_port=80, protocol='TCP',
                                 packets=random.randint(10, 100)))
            fid += 1

    # 320 individual clear-case flows
    for _ in range(320):
        sc = random.choice([
            'default_pass', 'clear_scan', 'clear_afterhours',
            'clear_exfil', 'internal', 'https', 'allowlist',
        ])
        m, d = random.randint(6, 12), random.randint(1, 28)
        if sc == 'default_pass':
            ts = local_at(2024, m, d, random.randint(10, 16))
            flows.append(mk_flow(fid, timestamp=ts, protocol='UDP',
                                 dst_port=random.randint(20000, 60000),
                                 src_ip=pt_src(), dst_ip=rand_ext_ip()))
        elif sc == 'clear_scan':
            ts = local_at(2024, m, d, random.randint(10, 16))
            flows.append(mk_flow(fid, timestamp=ts, dst_port=80,
                                 protocol='TCP', packets=1,
                                 src_ip=pt_src(), dst_ip=rand_ext_ip()))
        elif sc == 'clear_afterhours':
            ts = local_at(2024, m, d, random.randint(0, 3))
            flows.append(mk_flow(fid, timestamp=ts, protocol='UDP',
                                 dst_port=random.randint(20000, 60000),
                                 src_ip=pt_src(), dst_ip=rand_ext_ip()))
        elif sc == 'clear_exfil':
            ts = local_at(2024, m, d, random.randint(10, 16))
            flows.append(mk_flow(fid, timestamp=ts,
                                 bytes=random.randint(50_000_000, 100_000_000),
                                 protocol='TCP', dst_port=8080,
                                 packets=random.randint(10, 100),
                                 src_ip=pt_src(), dst_ip=rand_ext_ip()))
        elif sc == 'internal':
            ts = local_at(2024, m, d, random.randint(0, 3))
            flows.append(mk_flow(fid, timestamp=ts,
                                 dst_ip=rand_int_ip(),
                                 src_ip=pt_src()))
        elif sc == 'https':
            ts = local_at(2024, m, d, random.randint(10, 16))
            flows.append(mk_flow(fid, timestamp=ts, dst_port=443,
                                 protocol='TCP',
                                 packets=random.randint(10, 100),
                                 src_ip=pt_src(), dst_ip=rand_ext_ip()))
        elif sc == 'allowlist':
            al = allowed_sorted[random.randint(0, 2)]
            ts = local_at(2024, m, d, random.randint(10, 16))
            flows.append(mk_flow(fid, timestamp=ts, src_ip=al,
                                 dst_ip=rand_ext_ip()))
        fid += 1

    random.shuffle(flows)
    label_all(flows)
    return flows


# ═══════════════════════════════════════════════════════════════════════
# CSV writers
# ═══════════════════════════════════════════════════════════════════════

_TRAIN_COLS = ['flow_id', 'timestamp', 'src_ip', 'src_port', 'dst_ip',
               'dst_port', 'protocol', 'bytes', 'packets', 'decision']
_FLOW_COLS  = ['flow_id', 'timestamp', 'src_ip', 'src_port', 'dst_ip',
               'dst_port', 'protocol', 'bytes', 'packets']


def write_train(path: str, flows: list) -> None:
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(_TRAIN_COLS)
        for fl in flows:
            w.writerow([fl[c] for c in _TRAIN_COLS])


def write_pt_flows(path: str, flows: list) -> None:
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(_FLOW_COLS)
        for fl in flows:
            w.writerow([fl[c] for c in _FLOW_COLS])


def write_pt_expected(path: str, flows: list) -> None:
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['flow_id', 'decision'])
        for fl in flows:
            w.writerow([fl['flow_id'], fl['decision']])


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PT_DIR, exist_ok=True)

    train = gen_training(seed=42)
    write_train(os.path.join(OUTPUT_DIR, 'flows_train.csv'), train)

    pt = gen_public_test(seed=99)
    write_pt_flows(os.path.join(PT_DIR, 'flows.csv'), pt)
    write_pt_expected(os.path.join(PT_DIR, 'expected.csv'), pt)

    tf = sum(1 for f in train if f['decision'] == 'flag')
    pf = sum(1 for f in pt if f['decision'] == 'flag')
    print(f"Training:  {len(train)} flows  "
          f"({tf} flag, {len(train) - tf} pass)")
    print(f"Public:    {len(pt)} flows  "
          f"({pf} flag, {len(pt) - pf} pass)")
