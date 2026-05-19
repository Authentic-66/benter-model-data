"""
All-Tracks Comprehensive Results Report
Auto-discovers every *-results-* folder under the repo root and runs the
same trainer / jockey / sire / iron-horse analysis used for Fairmount Park.

Skips: Hong Kong (HKJC format, incompatible), Laurel Park (no results yet)
Output: printed to stdout AND saved to scripts/results-logs/ALL_TRACKS_REPORT_<date>.txt
"""

import re, sys, subprocess
from pathlib import Path
from collections import defaultdict
from datetime import date

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

SCRIPTS = Path(__file__).parent
BASE    = SCRIPTS.parent

MIN_STARTS     = 5
MIN_HORSE_WINS = 3

SKIP_TRACKS = {'Hong Kong', 'Laurel Park'}    # incompatible or no data

SEP  = '=' * 72
DASH = '-' * 72

# ---------------------------------------------------------------------------
# Discovery: find every results folder under each track directory
# ---------------------------------------------------------------------------

def discover_result_dirs():
    """
    Returns dict: {track_folder_name: [Path, ...]} sorted track name → dirs.
    Only includes directories whose name contains 'results'.
    """
    track_dirs = {}
    for track_dir in sorted(BASE.iterdir()):
        if not track_dir.is_dir():
            continue
        if track_dir.name.startswith('.') or track_dir.name in ('scripts', 'model-workbook-versions'):
            continue
        if track_dir.name in SKIP_TRACKS:
            continue
        result_dirs = sorted([d for d in track_dir.iterdir()
                              if d.is_dir() and 'result' in d.name.lower()])
        if result_dirs:
            track_dirs[track_dir.name] = result_dirs
    return track_dirs

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
        print(f"    [WARN] Cannot extract {path.name}: {e}", file=sys.stderr)
        return ''

# ---------------------------------------------------------------------------
# Per-file parser  (same logic as fp_comprehensive_report, track-agnostic)
# ---------------------------------------------------------------------------

def parse_file(path):
    text = extract_text(path)
    if not text:
        return []

    pages  = text.split('\f')
    races  = []

    for page in pages:
        if len(page.strip()) < 50:
            continue
        lines = page.split('\n')

        # ── race number ───────────────────────────────────────────────────
        race_num = None
        for line in lines[:6]:
            m = re.search(r'- Race (\d+)', line)
            if m:
                race_num = int(m.group(1))
                break
        if race_num is None:
            continue

        race = {
            'race_num': race_num,
            'winner_horse': '', 'winner_jockey': '',
            'winner_trainer': '', 'winner_sire': '',
            'win_payout': None,
            'all_jockeys': [],   # [(horse, jockey), ...]
            'all_trainers': [],  # [trainer_str, ...]
        }

        # ── finisher table ────────────────────────────────────────────────
        in_table = False
        fin_pos  = 0
        for line in lines:
            if re.search(r'Last\s+Raced.*Pgm.*Horse', line):
                in_table = True
                fin_pos  = 0
                continue
            if in_table:
                if 'Fractional' in line and 'Times' in line:
                    in_table = False
                    continue
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
        for line in lines:
            if 'Winner:' in line:
                sm = re.search(r'\bby\s+([A-Z][A-Za-z\.\s]+?)\s+out\s+of\b', line, re.IGNORECASE)
                if sm:
                    race['winner_sire'] = sm.group(1).strip().rstrip('.')
                break

        # ── winner trainer ────────────────────────────────────────────────
        for line in lines:
            if re.match(r'^\s*Trainer:', line):
                trm = re.search(r'Trainer:\s*([^\n\r]+)', line)
                if trm:
                    race['winner_trainer'] = trm.group(1).strip()
                break

        # ── all trainers from "Trainers: N - Name; ..." ───────────────────
        flat = ' '.join(lines)
        tm = re.search(r'Trainers:\s*(.*?)(?:Owners:|Footnotes|Copyright)', flat)
        if tm:
            entries = re.findall(
                r'\d+\s*-\s*([A-Za-z][A-Za-z ,\.\'III]+?)(?:\s*;|$)',
                tm.group(1)
            )
            race['all_trainers'] = [e.strip() for e in entries if len(e.strip()) > 3]

        if not race['all_trainers'] and race['winner_trainer']:
            race['all_trainers'] = [race['winner_trainer']]

        # ── win payout ────────────────────────────────────────────────────
        wps_idx = None
        for i, line in enumerate(lines):
            if 'Total WPS Pool' in line:
                wps_idx = i
                break

        if wps_idx is not None:
            for j in range(wps_idx + 1, min(wps_idx + 8, len(lines))):
                l = lines[j]
                if re.match(r'\s*Pgm\s+Horse', l):
                    cut  = re.split(r'\$\d+\.\d+[A-Z]', l)[0]
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
# Aggregate for one track (all its result dirs combined)
# ---------------------------------------------------------------------------

def aggregate_track(result_dirs, track_name):
    trainer_wins    = defaultdict(int)
    trainer_starts  = defaultdict(int)
    trainer_payouts = defaultdict(list)
    jockey_wins     = defaultdict(int)
    jockey_starts   = defaultdict(int)
    jockey_payouts  = defaultdict(list)
    sire_wins       = defaultdict(int)
    horse_wins      = defaultdict(int)

    total_races = 0
    total_files = 0
    skipped     = 0

    for d in result_dirs:
        pdfs = sorted(d.glob("*.pdf"))
        print(f"    {d.name}: {len(pdfs)} PDFs", file=sys.stderr)
        for pdf in pdfs:
            races = parse_file(pdf)
            if not races:
                skipped += 1
                continue
            total_files += 1
            for r in races:
                total_races += 1

                for _, jk in r['all_jockeys']:
                    if jk:
                        jockey_starts[jk] += 1
                for tr in r['all_trainers']:
                    if tr:
                        trainer_starts[tr] += 1

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
# Print helpers
# ---------------------------------------------------------------------------

def pct(wins, starts):
    return wins / starts * 100 if starts else 0.0

def avg(lst):
    return sum(lst) / len(lst) if lst else 0.0

def trainer_rows(s):
    tw, ts, tp = s['trainer_wins'], s['trainer_starts'], s['trainer_payouts']
    rows = []
    for name in set(list(tw) + list(ts)):
        wins   = tw.get(name, 0)
        starts = ts.get(name, 0)
        if starts < MIN_STARTS:
            continue
        rows.append((name, wins, starts, pct(wins, starts), avg(tp.get(name, []))))
    return sorted(rows, key=lambda x: (-x[1], -x[3]))

def jockey_rows(s):
    jw, js, jp = s['jockey_wins'], s['jockey_starts'], s['jockey_payouts']
    rows = []
    for name in set(list(jw) + list(js)):
        wins   = jw.get(name, 0)
        starts = js.get(name, 0)
        if starts < MIN_STARTS:
            continue
        rows.append((name, wins, starts, pct(wins, starts), avg(jp.get(name, []))))
    return sorted(rows, key=lambda x: (-x[1], -x[3]))

COL_HDR  = f"  {'Name':<32}  {'Sts':>4}  {'W':>3}  {'Win%':>6}  {'Avg $Win':>9}"
COL_DIV  = f"  {'-'*32}  {'-'*4}  {'-'*3}  {'-'*6}  {'-'*9}"

def print_person_rows(rows):
    print(COL_HDR)
    print(COL_DIV)
    for name, wins, starts, wp, avgp in rows:
        pay = f"${avgp:.2f}" if avgp else "---"
        print(f"  {name:<32}  {starts:>4}  {wins:>3}  {wp:>5.1f}%  {pay:>9}")

def print_track_report(track_name, s, out):
    dirs_label = ', '.join(str(d.parent.name) + '/' + d.name
                           for d in [])   # placeholder; printed in caller

    print(f"\n{SEP}", file=out)
    print(f"  TRACK: {track_name.upper()}", file=out)
    print(f"  Files : {s['total_files']} processed  |  {s['skipped']} skipped", file=out)
    print(f"  Races : {s['total_races']}", file=out)
    print(f"{SEP}", file=out)

    # 1. Trainers
    tr = trainer_rows(s)
    print(f"\n  -- TRAINER WIN STATS (min {MIN_STARTS} starts) --", file=out)
    if tr:
        print(COL_HDR, file=out)
        print(COL_DIV, file=out)
        for name, wins, starts, wp, avgp in tr:
            pay = f"${avgp:.2f}" if avgp else "---"
            print(f"  {name:<32}  {starts:>4}  {wins:>3}  {wp:>5.1f}%  {pay:>9}", file=out)
    else:
        print("  (no trainers met threshold)", file=out)

    # 2. Jockeys
    jk = jockey_rows(s)
    print(f"\n  -- JOCKEY WIN STATS (min {MIN_STARTS} starts) --", file=out)
    if jk:
        print(COL_HDR, file=out)
        print(COL_DIV, file=out)
        for name, wins, starts, wp, avgp in jk:
            pay = f"${avgp:.2f}" if avgp else "---"
            print(f"  {name:<32}  {starts:>4}  {wins:>3}  {wp:>5.1f}%  {pay:>9}", file=out)
    else:
        print("  (no jockeys met threshold)", file=out)

    # 3. Sires
    sire_list = sorted(s['sire_wins'].items(), key=lambda x: -x[1])
    print(f"\n  -- SIRE WIN COUNTS --", file=out)
    if sire_list:
        print(f"  {'Sire':<36}  {'W':>3}", file=out)
        print(f"  {'-'*36}  {'-'*3}", file=out)
        for sire, wins in sire_list:
            print(f"  {sire:<36}  {wins:>3}", file=out)
    else:
        print("  (no sire data)", file=out)

    # 4. Iron horses
    iron = sorted([(h, w) for h, w in s['horse_wins'].items() if w >= MIN_HORSE_WINS],
                  key=lambda x: -x[1])
    print(f"\n  -- IRON HORSES ({MIN_HORSE_WINS}+ wins) --", file=out)
    if iron:
        print(f"  {'Horse':<36}  {'W':>3}", file=out)
        print(f"  {'-'*36}  {'-'*3}", file=out)
        for horse, wins in iron:
            print(f"  {horse:<36}  {wins:>3}", file=out)
    else:
        print(f"  (none with {MIN_HORSE_WINS}+ wins)", file=out)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    log_dir  = SCRIPTS / 'results-logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"ALL_TRACKS_REPORT_{date.today().strftime('%Y%m%d')}.txt"

    track_map = discover_result_dirs()
    print(f"Tracks found: {list(track_map.keys())}", file=sys.stderr)

    # Write to both stdout and log file simultaneously
    with open(log_file, 'w', encoding='utf-8') as flog:
        outputs = [sys.stdout, flog]

        header = (
            f"\n{SEP}\n"
            f"  ALL-TRACKS COMPREHENSIVE RESULTS REPORT\n"
            f"  Generated : {date.today()}\n"
            f"  Tracks    : {', '.join(track_map.keys())}\n"
            f"  Min starts: {MIN_STARTS} (trainers/jockeys) | "
            f"{MIN_HORSE_WINS}+ wins (iron horses)\n"
            f"{SEP}\n"
        )
        for out in outputs:
            print(header, file=out)

        for track_name, result_dirs in track_map.items():
            print(f"\n  Processing: {track_name}", file=sys.stderr)
            s = aggregate_track(result_dirs, track_name)
            for out in outputs:
                print_track_report(track_name, s, out)
                print(file=out)   # blank line between tracks

        footer = f"\n{SEP}\n  Report saved: {log_file}\n{SEP}\n"
        for out in outputs:
            print(footer, file=out)

    print(f"\nDone. Log: {log_file}", file=sys.stderr)
