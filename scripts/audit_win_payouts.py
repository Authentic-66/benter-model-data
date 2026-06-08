"""
Comprehensive results-log audit.  Two detection passes:

  Pass 1 (log scan, fast):
    - Odds mismatch:   recorded WIN differs from (winner_SP+1)*2 by > $PAYOUT_TOL
                       Catches both the payout-table ordering bug AND the
                       finisher-table period-name bug (Dr.Jekyll type).
    - Low finisher:    fewer than MIN_FINISHERS listed in a race block.
                       Catches silently-dropped horses in small fields.

  Pass 2 (PDF re-parse, targeted):
    For every flagged race, find the source PDF, re-parse it with the
    fixed process_results.py parser, and compare:
      - winner name (position-1 horse)
      - finisher count
    Any difference confirms a stale/corrupted log.

  With --fix: automatically regenerates the log file for any PDF whose
  re-parse result differs from the stored log.

Usage:
    py scripts/audit_win_payouts.py
    py scripts/audit_win_payouts.py --fix
    py scripts/audit_win_payouts.py --payout-tol 1.00   (default 0.50)
    py scripts/audit_win_payouts.py --min-finishers 3   (default 4)
"""

import re, sys
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# ── Configuration ─────────────────────────────────────────────────────────────

PAYOUT_TOL     = 0.50   # flag races where |expected_win - recorded_win| > this
MIN_FINISHERS  = 4      # flag races with fewer finishers than this
FIX_MODE       = '--fix' in sys.argv

if '--payout-tol' in sys.argv:
    idx = sys.argv.index('--payout-tol')
    try:
        PAYOUT_TOL = float(sys.argv[idx + 1])
    except (IndexError, ValueError):
        pass

if '--min-finishers' in sys.argv:
    idx = sys.argv.index('--min-finishers')
    try:
        MIN_FINISHERS = int(sys.argv[idx + 1])
    except (IndexError, ValueError):
        pass

SCRIPTS  = Path(__file__).parent
LOGS_DIR = SCRIPTS / 'results-logs'
REPO     = SCRIPTS.parent

# ── PDF directory map (track → candidate subfolders, in priority order) ───────

TRACK_PDF_DIRS = {
    'CT':  ['CharlesTown/ct-results-2026', 'CharlesTown/ct-results-2025', 'CharlesTown/ct-results-2024'],
    'GP':  ['Gulfstream Park/gp-results-2026', 'Gulfstream Park/gp-results-2025', 'Gulfstream Park/gp-results-2024'],
    'FP':  ['Fairmount Park/fp-results-2026', 'Fairmount Park/fp-results-2025', 'Fairmount Park/fp-results-2024'],
    'EVD': ['Evangeline Downs/evd-results-2026', 'Evangeline Downs/evd-results-2025'],
    'DD':  ['Delta Downs/dd-results-2025', 'Delta Downs/dd-results-2024'],
    'FG':  ['Fair Grounds/fg-results-2026', 'Fair Grounds/fg-results-2025', 'Fair Grounds/fg-results-2024'],
    'MVR': ['Mahoning Valley/mvr-2026-results', 'Mahoning Valley/mvr-2025-results'],
    'LRL': ['Laurel Park/lrl-results-2026'],
    'ST':  ['Hong Kong/sha-tin-results-2026'],
    'HV':  ['Hong Kong/happy-valley-results-2026'],
}

# ── Log parsing ───────────────────────────────────────────────────────────────

_LOG_NAME_RE  = re.compile(r'RESULTS_([A-Z]+)_(\d{8})\.txt', re.IGNORECASE)
_SOURCE_RE    = re.compile(r'Source\s*:\s*(\S+\.pdf)', re.IGNORECASE)
_RACE_HDR_RE  = re.compile(r'\bRACE\s+(\d+)\b.*[|]')     # race header has pipe (meta columns)
_FINISH_RE    = re.compile(r'^\s{2,6}(\d+)\s+\d+\s+(\S+)\s+([\d.]+)\s*$')
_WIN_RE       = re.compile(r'\bWIN\s+\$([\d.]+)')


def parse_log_races(path):
    """
    Returns (track, source_pdf, [race_dicts]).
    Each race_dict: {race_num, finishers:[(pos,horse,odds)], win_pay}
    """
    m = _LOG_NAME_RE.match(path.name)
    if not m:
        return None, None, []
    track = m.group(1).upper()

    text  = path.read_text(encoding='utf-8', errors='replace')
    sm    = _SOURCE_RE.search(text)
    source_pdf = sm.group(1) if sm else None

    lines  = text.splitlines()
    races  = {}
    cur    = None

    for line in lines:
        if _RACE_HDR_RE.search(line):
            hm = re.search(r'\bRACE\s+(\d+)\b', line)
            if hm:
                rnum = int(hm.group(1))
                cur = {'race_num': rnum, 'finishers': [], 'win_pay': None}
                races[rnum] = cur
            continue
        if cur is None:
            continue
        fm = _FINISH_RE.match(line)
        if fm:
            cur['finishers'].append((int(fm.group(1)), fm.group(2), float(fm.group(3))))
            continue
        wm = _WIN_RE.search(line)
        if wm:
            cur['win_pay'] = float(wm.group(1))

    return track, source_pdf, list(races.values())


# ── Pass 1: scan all logs ─────────────────────────────────────────────────────

def scan_logs():
    """
    Returns list of flag dicts:
      {log, track, source_pdf, race_num, reason, winner, winner_odds,
       win_pay, expected_win, finisher_count}
    """
    flags = []
    for lf in sorted(LOGS_DIR.glob('RESULTS_*.txt')):
        track, source_pdf, races = parse_log_races(lf)
        if not track:
            continue
        for r in races:
            fins   = r['finishers']
            win    = r['win_pay']
            reasons = []

            # Check 1: odds mismatch
            if fins and win is not None:
                pos1_odds = fins[0][2] if fins[0][0] == 1 else None
                if pos1_odds is not None:
                    expected = round((pos1_odds + 1.0) * 2.0, 2)
                    if abs(expected - win) > PAYOUT_TOL:
                        reasons.append(
                            f'ODDS_MISMATCH  winner={fins[0][1]}  SP={pos1_odds:.2f}'
                            f'  expected_WIN=${expected:.2f}  recorded_WIN=${win:.2f}'
                        )

            # Check 2: low finisher count
            if len(fins) < MIN_FINISHERS and win is not None:
                reasons.append(f'LOW_FINISHERS  count={len(fins)}')

            for reason in reasons:
                flags.append({
                    'log':            lf,
                    'track':          track,
                    'source_pdf':     source_pdf,
                    'race_num':       r['race_num'],
                    'reason':         reason,
                    'winner':         fins[0][1] if fins else None,
                    'winner_odds':    fins[0][2] if fins else None,
                    'win_pay':        win,
                    'finisher_count': len(fins),
                })
    return flags


# ── Pass 2: PDF re-parse for flagged races ────────────────────────────────────

def find_pdf(track, source_name):
    """Locate the source PDF on disk."""
    if not source_name:
        return None
    for subdir in TRACK_PDF_DIRS.get(track, []):
        p = REPO / subdir / source_name
        if p.exists():
            return p
    # Fallback: recursive search (slower)
    for subdir in TRACK_PDF_DIRS.get(track, []):
        d = REPO / subdir
        if d.is_dir():
            for f in d.iterdir():
                if f.name.lower() == source_name.lower():
                    return f
    return None


def reparse_pdf(pdf_path, track):
    """Run the fixed parser and return {race_num: {winner, finisher_count, win_pay}}."""
    sys.path.insert(0, str(SCRIPTS))
    from process_results import extract_text, parse_results
    try:
        text  = extract_text(str(pdf_path))
        races = parse_results(text)
    except Exception as e:
        print(f"    [ERROR] could not re-parse {pdf_path.name}: {e}")
        return {}
    result = {}
    for rnum, r in races.items():
        winner = r['finishers'][0]['horse'] if r['finishers'] else None
        result[rnum] = {
            'winner':         winner,
            'finisher_count': len(r['finishers']),
            'win_pay':        float(r['win'].lstrip('$')) if r['win'] else None,
        }
    return result


def generate_log(pdf_path, track, log_path):
    """Re-run process_results.py and write the output to log_path."""
    import subprocess
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / 'process_results.py'), str(pdf_path), track],
        capture_output=True, text=True, errors='replace'
    )
    output = result.stdout
    log_path.write_text(output, encoding='utf-8')
    return output


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\nPhase 1 — scanning {len(list(LOGS_DIR.glob('RESULTS_*.txt')))} result logs")
    print(f"  Payout tolerance: ${PAYOUT_TOL:.2f}  |  Min finishers: {MIN_FINISHERS}")
    print(f"  Fix mode: {'ON (--fix)' if FIX_MODE else 'OFF'}\n")

    flags = scan_logs()

    # Group flags by (log_path, source_pdf) to avoid re-parsing same PDF twice
    by_pdf = defaultdict(list)
    for f in flags:
        by_pdf[(f['log'], f['source_pdf'])].append(f)

    print(f"Phase 1 results: {len(flags)} flag(s) across {len(by_pdf)} PDF(s)\n")

    if not flags:
        print("  Clean — no suspicious races found in any log.")
        print()
    else:
        print(f"  {'Log file':<36}  {'PDF':<26}  {'Race':<5}  Reason")
        print(f"  {'-'*36}  {'-'*26}  {'-'*5}  {'-'*40}")
        for f in flags:
            print(f"  {f['log'].name:<36}  {(f['source_pdf'] or '?'):<26}  "
                  f"R{f['race_num']:<4}  {f['reason']}")

    # ── Phase 2: re-parse flagged PDFs ────────────────────────────────────────
    if not flags:
        needs_fix = []
    else:
        print(f"\nPhase 2 — re-parsing {len(by_pdf)} PDF(s) with fixed parser...")
        needs_fix = []

        for (log_path, source_pdf), group in sorted(by_pdf.items(), key=lambda x: str(x[0][0])):
            track = group[0]['track']
            pdf_path = find_pdf(track, source_pdf)

            if pdf_path is None:
                print(f"  [SKIP] PDF not found: {source_pdf} (track={track})")
                continue

            print(f"  Re-parsing {pdf_path.name}...")
            reparsed = reparse_pdf(pdf_path, track)

            race_nums = sorted({f['race_num'] for f in group})
            diff_found = False
            for rnum in race_nums:
                log_race  = next((f for f in group if f['race_num'] == rnum), None)
                new_race  = reparsed.get(rnum)
                if not log_race or not new_race:
                    continue

                log_winner = log_race['winner']
                new_winner = new_race['winner']
                log_fins   = log_race['finisher_count']
                new_fins   = new_race['finisher_count']
                log_win    = log_race['win_pay']
                new_win    = new_race['win_pay']

                win_pay_diff = (
                    new_win is not None and log_win is not None
                    and abs(new_win - log_win) > 0.05
                )
                if new_winner != log_winner or new_fins != log_fins or win_pay_diff:
                    diff_found = True
                    print(f"    R{rnum}: STALE LOG")
                    if new_winner != log_winner:
                        print(f"      Winner:     {log_winner} -> {new_winner}")
                    if new_fins != log_fins:
                        print(f"      Finishers:  {log_fins} -> {new_fins}")
                    if win_pay_diff:
                        print(f"      WIN payout: ${log_win:.2f} -> ${new_win:.2f}")
                else:
                    pay_note = f"WIN ${new_win:.2f}" if new_win else "WIN n/a"
                    print(f"    R{rnum}: matches re-parse ({new_winner}, "
                          f"{new_fins} finishers, {pay_note}) -- log is current")

            if diff_found:
                needs_fix.append((log_path, pdf_path, track))

    # ── Fix mode: regenerate stale logs ───────────────────────────────────────
    print()
    if needs_fix:
        print(f"Stale logs: {len(needs_fix)} file(s) need regeneration")
        for log_path, pdf_path, track in needs_fix:
            if FIX_MODE:
                print(f"  Regenerating {log_path.name}...")
                generate_log(pdf_path, track, log_path)
                print(f"    Done.")
            else:
                print(f"  {log_path.name}  <-- re-run with --fix to update")
        if not FIX_MODE:
            print("\n  Re-run with --fix to regenerate stale logs automatically.")
    else:
        if flags:
            print("Phase 2: all flagged races re-parsed correctly -- no stale logs.")
        print()

    print("=" * 68)
    print(f"  Flags (log scan):  {len(flags):>4}")
    print(f"  PDFs re-parsed:    {len(by_pdf):>4}")
    print(f"  Stale logs found:  {len(needs_fix):>4}{'  (regenerated)' if FIX_MODE and needs_fix else ''}")
    print("=" * 68)
    print()


if __name__ == '__main__':
    main()
