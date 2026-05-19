"""
Fairmount Park Comprehensive Results Report
Processes all PDFs in fp-results-2025 + fp-results-2026

Outputs:
  1) Trainer win stats (wins, win%, avg payout)  — min 5 starts
  2) Jockey win stats (wins, win%, avg payout)   — min 5 starts
  3) Sire win counts
  4) Iron horses (3+ wins)
"""

import re, sys, subprocess
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

SCRIPTS        = Path(__file__).parent
BASE           = SCRIPTS.parent / "Fairmount Park"
DIRS           = [BASE / "fp-results-2025", BASE / "fp-results-2026"]
MIN_STARTS     = 5
MIN_HORSE_WINS = 3

# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text(filepath):
    path = Path(filepath)
    try:
        r = subprocess.run(
            ['pdftotext', '-layout', str(path), '-'],
            capture_output=True, text=True, errors='replace'
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    except FileNotFoundError:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            pages = [p.extract_text(layout=True) or '' for p in pdf.pages]
        return '\f'.join(pages)
    except Exception as e:
        print(f"  [WARN] Cannot extract {path.name}: {e}", file=sys.stderr)
        return ''

# ---------------------------------------------------------------------------
# Per-file parser
# ---------------------------------------------------------------------------

def parse_file(path):
    """
    Returns list of race dicts per race page found in the PDF.
    Keys: race_num, winner_horse, winner_jockey, winner_trainer,
          winner_sire, win_payout (float|None),
          all_jockeys [(horse,jockey)], all_trainers [str]
    """
    text = extract_text(path)
    if not text:
        return []

    pages = text.split('\f')
    races = []

    for page in pages:
        if len(page.strip()) < 50:
            continue
        lines = page.split('\n')

        # ── race number ───────────────────────────────────────────────────
        # Header: "FAIRMOUNT PARK - April 22, 2025 - Race 1    ...  Video Race Replay"
        race_num = None
        for line in lines[:6]:
            m = re.search(r'- Race (\d+)', line)
            if m:
                race_num = int(m.group(1))
                break
        if race_num is None:
            continue

        race = {
            'race_num':       race_num,
            'winner_horse':   '',
            'winner_jockey':  '',
            'winner_trainer': '',
            'winner_sire':    '',
            'win_payout':     None,
            'all_jockeys':    [],
            'all_trainers':   [],
        }

        # ── finisher table ────────────────────────────────────────────────
        # Header: "Last Raced    Pgm Horse Name (Jockey)  ..."
        # Each row: [date] [track] [pgm] [Horse Name] ([Jockey Name]) ...
        # End:      "Fractional Times: ..."
        in_table  = False
        fin_pos   = 0
        for line in lines:
            if re.search(r'Last\s+Raced.*Pgm.*Horse', line):
                in_table = True
                fin_pos  = 0
                continue
            if in_table:
                if 'Fractional' in line and 'Times' in line:
                    in_table = False
                    continue
                # Match: [pgm] [Horse Name] ([Jockey, Name])
                # pgm is a standalone 1-2 digit number followed by a space
                # Horse name starts with uppercase letter
                fm = re.search(
                    r'(?<![A-Za-z0-9])(\d{1,2})\s+([A-Z][A-Za-z\' ]+?)\s*\(([^)]+)\)',
                    line
                )
                if fm:
                    fin_pos += 1
                    horse  = fm.group(2).strip()
                    jockey = fm.group(3).strip()
                    race['all_jockeys'].append((horse, jockey))
                    if fin_pos == 1:
                        race['winner_horse']  = horse
                        race['winner_jockey'] = jockey

        # ── winner sire ───────────────────────────────────────────────────
        # "Winner: HorseName, ... by SireName out of ..."
        for line in lines:
            if 'Winner:' in line:
                sm = re.search(r'\bby\s+([A-Z][A-Za-z\.\s]+?)\s+out\s+of\b', line, re.IGNORECASE)
                if sm:
                    race['winner_sire'] = sm.group(1).strip().rstrip('.')
                break

        # ── winner trainer ────────────────────────────────────────────────
        # Line that starts with "Trainer: LastName, First"
        for line in lines:
            if re.match(r'^\s*Trainer:', line):
                trm = re.search(r'Trainer:\s*([^\n\r]+)', line)
                if trm:
                    raw = trm.group(1).strip()
                    race['winner_trainer'] = raw
                break

        # ── all trainers: from "Trainers: N - Name; M - Name; ..." ───────
        # Join page into one string to handle potential line wraps
        flat = ' '.join(lines)
        tm = re.search(r'Trainers:\s*(.*?)(?:Owners:|Footnotes|Copyright)', flat)
        if tm:
            chunk = tm.group(1)
            entries = re.findall(r'\d+\s*-\s*([A-Za-z][A-Za-z ,\.\'III]+?)(?:\s*;|$)', chunk)
            race['all_trainers'] = [e.strip() for e in entries if len(e.strip()) > 3]

        if not race['all_trainers'] and race['winner_trainer']:
            race['all_trainers'] = [race['winner_trainer']]

        # ── win payout ────────────────────────────────────────────────────
        # "Total WPS Pool: $NNN  Win   Place  Show ..."
        # Next line starting with "Pgm Horse" contains: win  place  show  $wager Exacta...
        wps_idx = None
        for i, line in enumerate(lines):
            if 'Total WPS Pool' in line:
                wps_idx = i
                break

        if wps_idx is not None:
            for j in range(wps_idx + 1, min(wps_idx + 8, len(lines))):
                l = lines[j]
                if re.match(r'\s*Pgm\s+Horse', l):
                    # Cut before wager type section ("$2.00Exacta", "$1.00Trifecta", etc.)
                    cut = re.split(r'\$\d+\.\d+[A-Z]', l)[0]
                    nums = re.findall(r'\d+\.\d+', cut)
                    if nums:
                        try:
                            race['win_payout'] = float(nums[0])
                        except ValueError:
                            pass
                    break

        races.append(race)

    return races

# ---------------------------------------------------------------------------
# Aggregate across all files
# ---------------------------------------------------------------------------

def build_stats():
    trainer_wins    = defaultdict(int)
    trainer_starts  = defaultdict(int)
    trainer_payouts = defaultdict(list)

    jockey_wins     = defaultdict(int)
    jockey_starts   = defaultdict(int)
    jockey_payouts  = defaultdict(list)

    sire_wins  = defaultdict(int)
    horse_wins = defaultdict(int)

    total_races = 0
    total_files = 0
    skipped     = 0

    for d in DIRS:
        if not d.exists():
            print(f"[WARN] Not found: {d}", file=sys.stderr)
            continue
        pdfs = sorted(d.glob("*.pdf"))
        print(f"  {d.name}: {len(pdfs)} PDFs", file=sys.stderr)
        for pdf in pdfs:
            races = parse_file(pdf)
            if not races:
                print(f"    [SKIP] {pdf.name}", file=sys.stderr)
                skipped += 1
                continue
            total_files += 1
            for r in races:
                total_races += 1

                # jockey starts: every finisher in the table
                for horse, jockey in r['all_jockeys']:
                    if jockey:
                        jockey_starts[jockey] += 1

                # trainer starts: from "Trainers:" section
                for trainer in r['all_trainers']:
                    if trainer:
                        trainer_starts[trainer] += 1

                # wins
                jk = r['winner_jockey']
                if jk:
                    jockey_wins[jk] += 1
                    if r['win_payout']:
                        jockey_payouts[jk].append(r['win_payout'])

                tr = r['winner_trainer']
                if tr:
                    trainer_wins[tr] += 1
                    if r['win_payout']:
                        trainer_payouts[tr].append(r['win_payout'])

                if r['winner_sire']:
                    sire_wins[r['winner_sire']] += 1

                if r['winner_horse']:
                    horse_wins[r['winner_horse']] += 1

    return {
        'trainer_wins': trainer_wins, 'trainer_starts': trainer_starts,
        'trainer_payouts': trainer_payouts,
        'jockey_wins': jockey_wins,   'jockey_starts': jockey_starts,
        'jockey_payouts': jockey_payouts,
        'sire_wins': sire_wins,       'horse_wins': horse_wins,
        'total_races': total_races,   'total_files': total_files,
        'skipped': skipped,
    }

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def pct(wins, starts):
    return wins / starts * 100 if starts else 0.0

def avg(lst):
    return sum(lst) / len(lst) if lst else 0.0

SEP  = '=' * 72
DASH = '-' * 72

def print_trainer_section(s):
    tw = s['trainer_wins']
    ts = s['trainer_starts']
    tp = s['trainer_payouts']

    rows = []
    for name in set(list(tw.keys()) + list(ts.keys())):
        wins   = tw.get(name, 0)
        starts = ts.get(name, 0)
        if starts < MIN_STARTS:
            continue
        payouts = tp.get(name, [])
        rows.append((name, wins, starts, pct(wins, starts), avg(payouts), len(payouts)))

    rows.sort(key=lambda x: (-x[1], -x[3]))

    print(f"\n{DASH}")
    print(f"  1. TRAINER WIN STATS  (min {MIN_STARTS} starts)")
    print(f"{DASH}")

    if not rows:
        print("  (no trainers met the minimum starts threshold)")
        return

    hdr = f"  {'Trainer':<30}  {'Sts':>4}  {'W':>3}  {'Win%':>6}  {'Avg $Win':>9}"
    print(hdr)
    print(f"  {'-'*30}  {'-'*4}  {'-'*3}  {'-'*6}  {'-'*9}")
    for name, wins, starts, wp, avgp, npay in rows:
        pay_str = f"${avgp:.2f}" if avgp else "---"
        print(f"  {name:<30}  {starts:>4}  {wins:>3}  {wp:>5.1f}%  {pay_str:>9}")

    total_trainer_starts = sum(ts.values())
    if total_trainer_starts < s['total_races'] * 2:
        print(f"\n  NOTE: Win% may be understated if 'Trainers:' section was missing in some PDFs.")

def print_jockey_section(s):
    jw = s['jockey_wins']
    js = s['jockey_starts']
    jp = s['jockey_payouts']

    rows = []
    for name in set(list(jw.keys()) + list(js.keys())):
        wins   = jw.get(name, 0)
        starts = js.get(name, 0)
        if starts < MIN_STARTS:
            continue
        payouts = jp.get(name, [])
        rows.append((name, wins, starts, pct(wins, starts), avg(payouts), len(payouts)))

    rows.sort(key=lambda x: (-x[1], -x[3]))

    print(f"\n{DASH}")
    print(f"  2. JOCKEY WIN STATS  (min {MIN_STARTS} starts)")
    print(f"{DASH}")

    if not rows:
        print("  (no jockeys met the minimum starts threshold)")
        return

    hdr = f"  {'Jockey':<30}  {'Sts':>4}  {'W':>3}  {'Win%':>6}  {'Avg $Win':>9}"
    print(hdr)
    print(f"  {'-'*30}  {'-'*4}  {'-'*3}  {'-'*6}  {'-'*9}")
    for name, wins, starts, wp, avgp, npay in rows:
        pay_str = f"${avgp:.2f}" if avgp else "---"
        print(f"  {name:<30}  {starts:>4}  {wins:>3}  {wp:>5.1f}%  {pay_str:>9}")

def print_sire_section(s):
    print(f"\n{DASH}")
    print(f"  3. SIRE WIN COUNTS")
    print(f"{DASH}")

    rows = sorted(s['sire_wins'].items(), key=lambda x: -x[1])
    if not rows:
        print("  (no sire data found)")
        return

    print(f"  {'Sire':<35}  {'W':>3}")
    print(f"  {'-'*35}  {'-'*3}")
    for sire, wins in rows:
        print(f"  {sire:<35}  {wins:>3}")

def print_iron_horses(s):
    print(f"\n{DASH}")
    print(f"  4. IRON HORSES  ({MIN_HORSE_WINS}+ wins)")
    print(f"{DASH}")

    rows = [(h, w) for h, w in s['horse_wins'].items() if w >= MIN_HORSE_WINS]
    rows.sort(key=lambda x: -x[1])

    if not rows:
        print(f"  (no horse has {MIN_HORSE_WINS}+ wins in this dataset)")
        return

    print(f"  {'Horse':<35}  {'W':>3}")
    print(f"  {'-'*35}  {'-'*3}")
    for horse, wins in rows:
        print(f"  {horse:<35}  {wins:>3}")

def print_report(s):
    print(f"\n{SEP}")
    print(f"  FAIRMOUNT PARK -- COMPREHENSIVE RESULTS REPORT")
    print(f"  Sources : fp-results-2025  +  fp-results-2026")
    print(f"  Files   : {s['total_files']} processed  |  {s['skipped']} skipped")
    print(f"  Races   : {s['total_races']} total")
    print(f"{SEP}")

    print_trainer_section(s)
    print_jockey_section(s)
    print_sire_section(s)
    print_iron_horses(s)

    print(f"\n{SEP}\n")

# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print("Scanning Fairmount Park results...", file=sys.stderr)
    stats = build_stats()
    print_report(stats)
