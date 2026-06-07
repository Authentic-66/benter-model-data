"""
ROI Tracker (file-based) — matches model picks against Equibase result PDFs
Imports parse_results / extract_text from process_results.py in the same folder.

picks.txt format  (one pick per line, # lines are comments):
    TRACK  RACE  HORSE  SIGNAL  [BETS]  [ML_ODDS]  [PP_POWER]
    CT     3     BigJoeB        TRAINER   WPS        3.0        92.5
    CT     4     HeyBoots       HORSE     WP         5.0        88.0
    GP     2     SomHorse       TRAINER                          75.0

  ML_ODDS  — morning-line odds as a decimal (2.0 = 2/1, 2.5 = 5/2).
             Omit to bypass the MIN_ODDS filter for that pick.
  PP_POWER — PP Power rating (numeric). Used to rank picks when a race
             exceeds MAX_PICKS_PER_RACE. Omit to default to 0.

  TRACK  — track code matching a result PDF (CT, GP, FP, EVD, MVR, DD, FG)
  RACE   — race number, or R3-style prefix
  HORSE  — concatenated name as it appears in Equibase (e.g. BigJoeB)
  SIGNAL — TRAINER | SIRE | HORSE  (display only, no effect on calc)
  BETS   — any combo of W P S; defaults to WPS if omitted

Track is inferred from the PDF filename (e.g. CT050926USA.pdf → CT,
20240103-usa-ct-a-d.standard.pdf → CT).

Usage: python roi_tracker.py <picks.txt> <result.pdf> [result.pdf ...]
  e.g. python roi_tracker.py picks.txt CT050926USA.pdf
"""

import re, sys
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

sys.path.insert(0, str(Path(__file__).parent))
from process_results import extract_text, parse_results, TRACK_NAMES

# ── Configuration ─────────────────────────────────────────────────────────────

MIN_ODDS = 2.0          # minimum morning-line odds (2.0 = 2/1); set to 0 to disable
MAX_PICKS_PER_RACE = 2  # max picks scored per race (ranked by PP Power); set to 0 to disable

# ── picks.txt loading ─────────────────────────────────────────────────────────

def load_picks(filepath):
    picks = []
    with open(filepath, encoding='utf-8', errors='replace') as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 4:
                print(f"  Warning: line {lineno} has fewer than 4 fields — skipped: {line!r}")
                continue
            track  = parts[0].upper()
            race   = int(re.sub(r'\D', '', parts[1]))   # "R3" or "3" → 3
            horse  = parts[2]
            signal = parts[3].upper()
            bets_raw = parts[4].upper() if len(parts) >= 5 else 'WPS'
            bets = list(dict.fromkeys(b for b in bets_raw if b in ('W', 'P', 'S')))
            if not bets:
                bets = ['W', 'P', 'S']
            try:
                ml_odds = float(parts[5]) if len(parts) >= 6 else None
            except ValueError:
                ml_odds = None
            try:
                pp_power = float(parts[6]) if len(parts) >= 7 else 0.0
            except ValueError:
                pp_power = 0.0
            picks.append({
                'track': track, 'race': race, 'horse': horse,
                'signal': signal, 'bets': bets,
                'ml_odds': ml_odds, 'pp_power': pp_power,
            })
    return picks

# ── Filters ───────────────────────────────────────────────────────────────────

def apply_filters(picks):
    """Apply MIN_ODDS and MAX_PICKS_PER_RACE filters.

    Returns (active_picks, skipped_rows, n_odds_filtered, n_race_filtered).
    skipped_rows are pre-built row dicts ready for print_summary.
    """
    skipped = []
    active  = []
    n_odds = 0

    for p in picks:
        ml = p.get('ml_odds')
        if MIN_ODDS > 0 and ml is not None and ml < MIN_ODDS:
            skipped.append({**p, 'status': 'BELOW ODDS THRESHOLD', 'filtered': True,
                            'fin': '—', 'invested': 0.0, 'returned': 0.0})
            n_odds += 1
        else:
            active.append(p)

    n_race = 0
    if MAX_PICKS_PER_RACE > 0:
        by_race = defaultdict(list)
        for p in active:
            by_race[(p['track'], p['race'])].append(p)
        active = []
        for race_picks in by_race.values():
            if len(race_picks) > MAX_PICKS_PER_RACE:
                ranked = sorted(race_picks, key=lambda x: x.get('pp_power', 0.0), reverse=True)
                active.extend(ranked[:MAX_PICKS_PER_RACE])
                for p in ranked[MAX_PICKS_PER_RACE:]:
                    skipped.append({**p, 'status': 'RACE PICK LIMIT', 'filtered': True,
                                    'fin': '—', 'invested': 0.0, 'returned': 0.0})
                    n_race += 1
            else:
                active.extend(race_picks)

    return active, skipped, n_odds, n_race

# ── PDF loading ───────────────────────────────────────────────────────────────

def infer_track(filepath):
    name = Path(filepath).stem.upper()
    # Longer codes first to avoid 'FG' matching before 'FGS' etc.
    for code in sorted(TRACK_NAMES, key=len, reverse=True):
        if name.startswith(code):
            return code
        if f'-{code}-' in name or f'_{code}_' in name:
            return code
    return None

def load_results(pdf_files):
    """Returns {track_code: {race_num: race_dict}}."""
    all_results = {}
    for pdf_path in pdf_files:
        track = infer_track(pdf_path)
        if track is None:
            print(f"  Warning: cannot infer track from '{Path(pdf_path).name}' — skipped")
            print(f"    Rename to start with a track code (e.g. CT..., GP...) or add -ct- in the name")
            continue
        print(f"  Parsing {Path(pdf_path).name} [{track}]...")
        text  = extract_text(pdf_path)
        races = parse_results(text)
        all_results.setdefault(track, {}).update(races)
        print(f"    {len(races)} race(s) loaded")
    return all_results

# ── Matching ──────────────────────────────────────────────────────────────────

def normalize(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())

def find_finisher(horse_name, finishers):
    """Case/punctuation-insensitive match; partial fallback."""
    needle = normalize(horse_name)
    for f in finishers:
        if normalize(f['horse']) == needle:
            return f
    for f in finishers:
        hay = normalize(f['horse'])
        if needle in hay or hay in needle:
            return f
    return None

# ── Return calculation ────────────────────────────────────────────────────────

def to_float(payout_str):
    return float(payout_str.lstrip('$')) if payout_str else 0.0

def calc_return(finisher, race, bets):
    pos      = finisher['pos']
    invested = len(bets) * 2.0
    returned = 0.0
    if 'W' in bets and pos == 1: returned += to_float(race['win'])
    if 'P' in bets and pos <= 2: returned += to_float(race['place'])
    if 'S' in bets and pos <= 3: returned += to_float(race['show'])
    return invested, returned

# ── Output ────────────────────────────────────────────────────────────────────

def pl_fmt(v):
    return f"+${v:.2f}" if v >= 0 else f"-${abs(v):.2f}"

def roi_fmt(invested, returned):
    if invested == 0:
        return 'n/a'
    pct = (returned - invested) / invested * 100
    return f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"

def print_summary(rows):
    if not rows:
        print("\nNo picks to summarize.")
        return

    by_track = defaultdict(list)
    for row in rows:
        by_track[row['track']].append(row)

    grand_inv = grand_ret = 0.0

    print(f"\n{'='*76}")
    print(f"  BENTER MODEL  —  ROI SUMMARY")
    print(f"{'='*76}")

    for track in sorted(by_track):
        track_rows = by_track[track]
        track_name = TRACK_NAMES.get(track, track)

        print(f"\n  ── {track_name.upper()} ({track}) {'─'*(56 - len(track_name))}")
        print(f"  {'Race':<5} {'Horse':<24} {'Signal':<9} {'Bets':<5} {'Fin':>3}  {'Inv':>6}  {'Ret':>7}  {'P/L':>9}")
        print(f"  {'·'*68}")

        t_inv = t_ret = 0.0
        for r in sorted(track_rows, key=lambda x: x['race']):
            if r.get('filtered'):
                print(
                    f"  R{r['race']:<4} {r['horse'][:24]:<24} {r['signal'][:9]:<9} "
                    f"{'':5} {'—':>3}  {'':>6}  {'':>7}  {'':>9}  [{r['status']}]"
                )
                continue
            fin_str  = str(r['fin']) if r.get('fin') not in (None, '-', '?') else '?'
            bets_str = ''.join(r['bets'])
            pl       = r['returned'] - r['invested']
            note     = f"  [{r['status']}]" if r.get('status') not in ('OK', None) else ''
            print(
                f"  R{r['race']:<4} {r['horse'][:24]:<24} {r['signal'][:9]:<9} "
                f"{bets_str:<5} {fin_str:>3}  ${r['invested']:>4.2f}  "
                f"${r['returned']:>5.2f}  {pl_fmt(pl):>9}{note}"
            )
            t_inv += r['invested']
            t_ret += r['returned']

        print(f"  {'·'*68}")
        print(
            f"  {'SUBTOTAL':<48} ${t_inv:>5.2f}  ${t_ret:>6.2f}  "
            f"{pl_fmt(t_ret - t_inv):>9}  ROI: {roi_fmt(t_inv, t_ret)}"
        )
        grand_inv += t_inv
        grand_ret += t_ret

    print(f"\n{'='*76}")
    print(
        f"  {'OVERALL TOTAL':<48} ${grand_inv:>5.2f}  ${grand_ret:>6.2f}  "
        f"{pl_fmt(grand_ret - grand_inv):>9}  ROI: {roi_fmt(grand_inv, grand_ret)}"
    )
    print(f"{'='*76}\n")

# ── Main ──────────────────────────────────────────────────────────────────────

def run(picks_file, pdf_files):
    print(f"\nLoading picks from {picks_file}...")
    picks = load_picks(picks_file)
    print(f"  {len(picks)} pick(s) loaded")

    active_picks, skipped_rows, n_odds, n_race = apply_filters(picks)
    total_filtered = n_odds + n_race
    if total_filtered:
        print(f"  {total_filtered} pick(s) filtered before scoring "
              f"({n_odds} odds threshold, {n_race} race pick limit)")

    print(f"\nLoading result PDFs...")
    results = load_results(pdf_files)

    rows = []
    for pick in active_picks:
        track    = pick['track']
        race_num = pick['race']
        race     = results.get(track, {}).get(race_num)

        if race is None:
            rows.append({**pick, 'status': 'NO RESULT', 'fin': '?',
                         'invested': len(pick['bets']) * 2.0, 'returned': 0.0})
            continue

        finisher = find_finisher(pick['horse'], race['finishers'])
        if finisher is None:
            rows.append({**pick, 'status': 'NOT FOUND', 'fin': '?',
                         'invested': len(pick['bets']) * 2.0, 'returned': 0.0})
            continue

        invested, returned = calc_return(finisher, race, pick['bets'])
        rows.append({
            **pick, 'status': 'OK',
            'fin': finisher['pos'], 'odds': finisher['odds'],
            'invested': invested, 'returned': returned,
        })

    print_summary(rows + skipped_rows)

    if n_odds or n_race:
        print(f"  Filter summary:")
        if n_odds:
            print(f"    Below odds threshold (ML < {MIN_ODDS}):  {n_odds} pick(s) not scored")
        if n_race:
            print(f"    Race pick limit (> {MAX_PICKS_PER_RACE}/race):         {n_race} pick(s) not scored")
        print()


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python roi_tracker.py <picks.txt> <result.pdf> [result.pdf ...]")
        print()
        print("picks.txt format (one pick per line):")
        print("  TRACK  RACE  HORSE  SIGNAL  [BETS]  [ML_ODDS]  [PP_POWER]")
        print("  CT     3     BigJoeB        TRAINER   WPS        3.0        92.5")
        print("  CT     4     HeyBoots       HORSE     WP         5.0        88.0")
        print("  GP     2     SomHorse       TRAINER   W")
        sys.exit(1)

    run(sys.argv[1], sys.argv[2:])
