"""
Equibase Result Chart Parser — extracts finishers, trainer, sire, and W/P/S payouts
Handles standard Equibase result chart PDFs for any track
Usage: python process_results.py <result.pdf> [TRACK_CODE]
"""

import re, sys, subprocess
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

TRACK_NAMES = {
    'GP':  'Gulfstream Park',   'CT':  'Charles Town',
    'FP':  'Fairmount Park',    'EVD': 'Evangeline Downs',
    'MVR': 'Mahoning Valley',   'DD':  'Delta Downs',
    'FG':  'Fair Grounds',      'ST':  'Sha Tin',
    'HV':  'Happy Valley',      'SAR': 'Saratoga',
    'SA':  'Santa Anita',       'LRL': 'Laurel Park',
}

COND_MAP = {
    'MAIDENSPECIALWEIGHT': 'MSW', 'MAIDENCLAIMING': 'MCL',
    'ALLOWANCEOPTIONALCLAIMING': 'AOC', 'ALLOWANCE': 'ALW',
    'CLAIMING': 'CLM', 'STAKES': 'STK', 'HANDICAP': 'HCP',
    'STARTERCLAIMING': 'STC', 'STARTERALLOWANCE': 'STA',
    'STARTEROPTIONALCLAIMING': 'SOC', 'WAIVERCLAIMING': 'WVC',
}

DIST_PATTERNS = [
    # Furlongs — check "AndOneHalf" before bare number (Equibase spells "FourAndOneHalf")
    (r'(?i)fourandone.?half.?furlongs?',        '4.5F'),
    (r'(?i)four.?furlongs?',                    '4F'),
    (r'(?i)fiveandone.?half.?furlongs?',        '5.5F'),
    (r'(?i)five.?furlongs?',                    '5F'),
    (r'(?i)sixandone.?half.?furlongs?',         '6.5F'),
    (r'(?i)six.?furlongs?',                     '6F'),
    (r'(?i)sevenandone.?half.?furlongs?',       '7.5F'),
    (r'(?i)seven.?furlongs?',                   '7F'),
    # Miles
    (r'(?i)oneandone.?sixteenth.?miles?',       '1 1/16M'),
    (r'(?i)oneandone.?eighth.?miles?',          '1 1/8M'),
    (r'(?i)oneandaquarter.?miles?',             '1 1/4M'),
    (r'(?i)oneandthree.?eighths?.?miles?',      '1 3/8M'),
    (r'(?i)oneandone.?half.?miles?',            '1.5M'),
    (r'(?i)one.?mile',                          '1M'),
]

def extract_text(filepath):
    path = Path(filepath)
    if path.suffix.lower() != '.pdf':
        return path.read_text(errors='replace')
    # pdfplumber with layout=True produces concatenated tokens (e.g. "TaptoConnect(Jockey)")
    # that all downstream regexes are calibrated for. pdftotext -layout preserves spaces
    # and breaks those regexes, so pdfplumber is always the primary extractor.
    import pdfplumber
    try:
        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text(layout=True) or '' for page in pdf.pages]
        text = '\f'.join(pages)
        if text.strip():
            return text
    except Exception:
        pass
    # Fallback to pdftotext only if pdfplumber fails entirely
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', str(path), '-'],
            capture_output=True, text=True, errors='replace'
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except FileNotFoundError:
        pass
    return ''

def fmt_dist(raw):
    clean = re.sub(r'(?i)OnThe(Dirt|Turf|AllWeatherTrack)', '', raw)
    clean = re.sub(r'(?i)CurrentTrackRecord.*', '', clean).strip()
    for pat, label in DIST_PATTERNS:
        if re.match(pat, clean):
            return label
    return clean[:15]

def parse_results(text):
    pages = text.split('\f')
    races = {}

    for page in pages:
        if len(page.strip()) < 50:
            continue
        lines = page.split('\n')

        # ── Race number: header ends with "-RaceN" ────────────────────────────
        race_num = None
        for line in lines[:5]:
            m = re.search(r'-Race\s*(\d+)\s*$', line.strip())
            if m:
                race_num = int(m.group(1))
                break
        if race_num is None:
            continue

        race = {
            'num': race_num,
            'conditions': '', 'distance': '', 'surface': 'Dirt', 'purse': '',
            'finishers': [],
            'winner_trainer': '', 'winner_sire': '',
            'time': '', 'win': '', 'place': '', 'show': '',
        }

        # ── Race conditions ───────────────────────────────────────────────────
        for line in lines[:15]:
            if not race['conditions']:
                cm = re.match(r'^\s+([A-Z]{4,})-Thoroughbred', line)
                if cm:
                    race['conditions'] = COND_MAP.get(cm.group(1), cm.group(1)[:12])

            if not race['distance']:
                dm = re.search(r'Distance:(.+?)(?:CurrentTrack|$)', line)
                if dm:
                    raw_dist = dm.group(1)
                    if re.search(r'(?i)OnTheTurf', raw_dist):
                        race['surface'] = 'Turf'
                    elif re.search(r'(?i)AllWeather|Tapeta|Polytrack', raw_dist):
                        race['surface'] = 'AW'
                    race['distance'] = fmt_dist(raw_dist)

            if not race['purse']:
                pm = re.search(r'Purse:\$([\d,]+)', line)
                if pm:
                    race['purse'] = f"${pm.group(1)}"

        # ── Finisher rows (in finish order after "LastRaced Pgm HorseName") ───
        in_table = False
        finish_pos = 0
        for line in lines:
            if re.search(r'LastRaced\s+Pgm\s+HorseName', line):
                in_table = True
                finish_pos = 0
                continue
            if in_table:
                if not line.strip() or 'FractionalTimes' in line:
                    in_table = False
                    continue
                # Pattern: [optional_last_race] pgm HorseName(Jockey)
                # pgm is 1-2 digits; HorseName starts uppercase, min 4 chars, ends at "("
                # Jockey Club name chars: letters, apostrophe, period, hyphen (spaces
                # are removed by pdfplumber's layout extraction so not needed here).
                # Country-of-origin suffix like (Ire) or (Fr) appears as (Suffix)(Jockey)
                # in concatenated output — the first "(" already delimits the name.
                # DQ-prefixed horses (disqualified) are skipped so official finish order
                # is preserved; the DQ'd horse appears first in the physical table but
                # last officially, and we never want it counted as the winner.
                fm = re.search(r'\b(\d{1,2})\s+([A-Z][A-Za-z\'\.\-]{3,})\(', line)
                if fm:
                    pgm, horse = fm.group(1), fm.group(2)
                    if horse.startswith('DQ-'):
                        continue
                    finish_pos += 1
                    # Odds: last decimal on the line (running positions use fractions, not decimals)
                    decimals = re.findall(r'\d+\.\d+', line)
                    odds = decimals[-1] if decimals else '?'
                    # Jockey: first parenthesised group after the horse name that
                    # contains a comma (LastName,FirstName). Foreign-bred horses
                    # produce a country tag first — e.g. ToppersAtSeaside(Ire)(Rispoli,Umberto)
                    # — so the comma filter skips the country.
                    jockey = ''
                    for pg in re.finditer(r'\(([^)]+)\)', line[fm.end()-1:]):
                        if ',' in pg.group(1):
                            jockey = pg.group(1).strip()
                            break
                    race['finishers'].append({
                        'pos': finish_pos, 'pp': pgm, 'horse': horse,
                        'jockey': jockey, 'trainer': '', 'odds': odds
                    })

        # ── Final time ────────────────────────────────────────────────────────
        for line in lines:
            tm = re.search(r'FinalTime:([0-9:.]+)', line)
            if tm:
                race['time'] = tm.group(1)
                break

        # ── Winner sire ───────────────────────────────────────────────────────
        # Format: "Winner: HorseName,...byKEENICEoutof..." (spaces removed by PDF)
        for line in lines:
            if 'Winner:' in line:
                sm = re.search(r'by([A-Z][A-Za-z\'\.\- ]+?)(?:outof|Foaled)', line)
                if sm:
                    race['winner_sire'] = sm.group(1).strip().rstrip('.')
                break

        # ── Trainer ───────────────────────────────────────────────────────────
        # Only match line that STARTS with "Trainer:" (avoids "NewTrainer:" for claims)
        for line in lines:
            if re.match(r'^\s*Trainer:', line):
                trm = re.search(r'Trainer:([^\n\r]+)', line)
                if trm:
                    raw = trm.group(1).strip()
                    race['winner_trainer'] = raw.replace(',', ', ', 1)
                break

        # ── Per-position trainers from the plural "Trainers:" line ────────────
        # Format: "Trainers: 4-Sise,Jr.,Clifford;7-O'Neill,Doug;..." — one entry
        # per starter. Wraps across continuation lines for full fields. Read
        # until the next keyword starts the next section.
        buf, in_trainers = '', False
        for line in lines:
            s = line.strip()
            if not in_trainers:
                if s.startswith('Trainers:'):
                    in_trainers = True
                    buf = s[len('Trainers:'):].strip()
            else:
                if not s or re.match(
                    r'^(Owners?:|Footnotes|Winner:|Trainer:|Pgm |Total|Claiming|'
                    r'Fractional|Run-Up|Copyright|SplitTimes|Weather|LastRaced)',
                    s, re.I
                ):
                    break
                buf += s
        if buf:
            trainers_by_pgm = {}
            for entry in buf.split(';'):
                em = re.match(r'\s*(\d+)-(.+?)\s*$', entry)
                if em:
                    trainers_by_pgm[em.group(1)] = em.group(2).strip()
            for f in race['finishers']:
                if f['pp'] in trainers_by_pgm:
                    f['trainer'] = trainers_by_pgm[f['pp']]

        # ── W/P/S payouts ─────────────────────────────────────────────────────
        # Table: "Pgm Horse  Win Place Show WagerType WinningNumbers Payoff Pool"
        # Row 1 (winner):   WIN  PLACE  SHOW  $1.00Exacta ...
        # Row 2 (2nd):            PLACE  SHOW  $1.00Trifecta ...
        # Row 3 (3rd):                   SHOW  $1.00Superfecta ...
        payout_idx = None
        for i, line in enumerate(lines):
            if re.search(r'Pgm\s+Horse\s+Win\s+Place', line):
                payout_idx = i
                break

        if payout_idx is not None:
            payout_rows = []
            for j in range(payout_idx + 1, min(payout_idx + 6, len(lines))):
                l = lines[j].strip()
                if not l or 'PastPerformance' in l:
                    break
                if re.search(r'\d+\.\d+', l):
                    payout_rows.append(l)

            def wps(row):
                # Cut before the wager type section ("$1.00Exacta", "$2.00Daily", etc.)
                cut = re.split(r'\$\d+\.\d+[A-Z]', row)[0]
                return re.findall(r'\d+\.\d+', cut)

            # Equibase sometimes orders the WPS table by program number rather than
            # finish position. Sort descending by value count so the winner row
            # (Win+Place+Show = 3 values) is always first regardless of table order.
            payout_rows.sort(key=lambda r: len(wps(r)), reverse=True)

            if payout_rows:
                a = wps(payout_rows[0])
                if len(a) >= 1: race['win']   = f"${a[0]}"
                if len(a) >= 2: race['place'] = f"${a[1]}"
                if len(a) >= 3: race['show']  = f"${a[2]}"
            if not race['place'] and len(payout_rows) >= 2:
                a = wps(payout_rows[1])
                if len(a) >= 1: race['place'] = f"${a[0]}"
                if len(a) >= 2: race['show']  = f"${a[1]}"
            if not race['show'] and len(payout_rows) >= 3:
                a = wps(payout_rows[2])
                if a: race['show'] = f"${a[0]}"

        races[race_num] = race

    return races


def print_results(races, track_name, filename):
    print(f"\n{'='*72}")
    print(f"  RESULTS : {track_name.upper()}")
    print(f"  Source  : {filename}")
    print(f"{'='*72}")

    for rn in sorted(races.keys()):
        r = races[rn]
        meta = '  |  '.join(filter(None, [r['conditions'], r['distance'], r['surface'], r['purse']]))
        print(f"\n{'─'*72}")
        print(f"  RACE {rn}  —  {meta}")
        print(f"{'─'*72}")

        if r['finishers']:
            print(f"  {'Pos':>3}  {'PP':>3}  {'Horse':<30}  {'Odds':>6}  {'Jockey':<24}  {'Trainer':<24}")
            for f in sorted(r['finishers'], key=lambda x: x['pos'])[:8]:
                print(
                    f"  {f['pos']:>3}  {f['pp']:>3}  {f['horse']:<30}  {f['odds']:>6}"
                    f"  {f.get('jockey',''):<24}  {f.get('trainer',''):<24}"
                )
        else:
            print("  (no finisher data parsed)")

        if r['time']:           print(f"\n  Time    : {r['time']}")
        if r['winner_trainer']: print(f"  Trainer : {r['winner_trainer']}")
        if r['winner_sire']:    print(f"  Sire    : {r['winner_sire']}")

        payouts = []
        if r['win']:   payouts.append(f"WIN  {r['win']:>7}")
        if r['place']: payouts.append(f"PLC  {r['place']:>7}")
        if r['show']:  payouts.append(f"SHW  {r['show']:>7}")
        print(f"\n  {'   '.join(payouts) if payouts else 'Payouts: (not found)'}")

    print(f"\n{'='*72}")
    print(f"  {len(races)} race(s) processed")
    print(f"{'='*72}\n")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python process_results.py <result.pdf> [TRACK_CODE]")
        sys.exit(1)

    filepath = sys.argv[1]
    track = sys.argv[2].upper() if len(sys.argv) > 2 else 'GP'

    print(f"Processing {Path(filepath).name} [{track}]...")
    text = extract_text(filepath)
    races = parse_results(text)
    print(f"Found {len(races)} race(s)")
    print_results(races, TRACK_NAMES.get(track, track), Path(filepath).name)
