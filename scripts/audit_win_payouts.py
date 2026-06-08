"""
Audit previously processed results logs for the payout_rows ordering bug.

The bug: Equibase WPS tables are sometimes ordered by program number, not finish
position. The old parser blindly took payout_rows[0] as the winner, so a 2nd-place
horse could have its Place payout mistakenly recorded as the Win payout.

Detection strategy (two-pass):
  1. Flag any race where WIN < $3.00 (basic threshold).
  2. Cross-check: derive expected WIN from the winner's listed SP odds:
       expected = (sp_odds + 1.0) * 2.0    (i.e. a $2 WIN ticket)
     If the recorded WIN is < threshold AND the winner's odds imply the payout
     should be >= $3.00, that is a likely parser bug rather than a legitimate
     short-priced winner.

Legitimate sub-$3.00 WIN payouts exist (e.g. 4/5 horse pays $3.60, 1/2 pays
$3.00, heavier chalk like 1/5 pays $2.40). Cross-checking odds eliminates most
of these false positives.

Usage: py scripts/audit_win_payouts.py [--threshold 3.00] [--show-all]
  --threshold N  : override WIN threshold (default 3.00)
  --show-all     : also print races where WIN is low but odds match (likely genuine)
"""

import re
import sys
from pathlib import Path

THRESHOLD = 3.00
SHOW_ALL  = '--show-all' in sys.argv

if '--threshold' in sys.argv:
    idx = sys.argv.index('--threshold')
    try:
        THRESHOLD = float(sys.argv[idx + 1])
    except (IndexError, ValueError):
        pass

LOGS_DIR = Path(__file__).parent / 'results-logs'

# Payout line:  "  WIN  $X.XX   PLC  $Y.YY ..."
WIN_RE    = re.compile(r'\bWIN\s+\$(\d+\.\d+)')
# Race header:  "  RACE N  —  ..."
RACE_RE   = re.compile(r'\bRACE\s+(\d+)\b')
# Source PDF:   "  Source  : filename.pdf"
SOURCE_RE = re.compile(r'Source\s*:\s*(\S+\.pdf)', re.IGNORECASE)
# Finisher row: "    1  PP  HorseName  Odds"  — pos 1, any pp, any horse, trailing decimal
WINNER_RE = re.compile(r'^\s{2,6}1\s+\d+\s+\S.*?(\d+\.\d+)\s*$')


def audit_log(path):
    """
    Yields dicts for each race where WIN < THRESHOLD, with keys:
      source, race, win, winner_odds, expected_win, likely_bug
    """
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        print(f"  [SKIP] {path.name}: {e}")
        return

    source_pdf = '(unknown)'
    m = SOURCE_RE.search(text)
    if m:
        source_pdf = m.group(1)

    lines = text.splitlines()
    current_race  = None
    winner_odds   = None

    for i, line in enumerate(lines):
        rm = RACE_RE.search(line)
        if rm:
            current_race = int(rm.group(1))
            winner_odds  = None   # reset per race

        # Capture winner SP odds from the finisher table (pos 1 row)
        if current_race is not None and winner_odds is None:
            wm = WINNER_RE.match(line)
            if wm:
                try:
                    winner_odds = float(wm.group(1))
                except ValueError:
                    pass

        pw = WIN_RE.search(line)
        if pw:
            win_val = float(pw.group(1))
            if win_val < THRESHOLD:
                expected = None
                likely_bug = False
                if winner_odds is not None:
                    expected = round((winner_odds + 1.0) * 2.0, 2)
                    # Likely bug if expected payout is notably higher than recorded
                    likely_bug = expected >= THRESHOLD
                yield {
                    'source':       source_pdf,
                    'race':         current_race,
                    'win':          win_val,
                    'winner_odds':  winner_odds,
                    'expected_win': expected,
                    'likely_bug':   likely_bug,
                }


def main():
    log_files = sorted(LOGS_DIR.glob('RESULTS_*.txt'))
    if not log_files:
        print(f"No results logs found in {LOGS_DIR}")
        sys.exit(1)

    print(f"\nAudit: {len(log_files)} results logs  |  WIN threshold: ${THRESHOLD:.2f}")
    print(f"Log dir: {LOGS_DIR}\n")

    all_flagged   = []
    likely_bugs   = []
    genuine_chalk = []

    for lf in log_files:
        for rec in audit_log(lf):
            rec['log'] = lf.name
            all_flagged.append(rec)
            if rec['likely_bug']:
                likely_bugs.append(rec)
            else:
                genuine_chalk.append(rec)

    # ── Likely bugs (win < threshold AND winner odds imply higher payout) ──────
    print(f"LIKELY PARSER BUGS  ({len(likely_bugs)} races)")
    print("  (recorded WIN is low but winner's SP odds imply a higher payout)")
    print("-" * 80)
    if likely_bugs:
        print(f"  {'Log file':<36}  {'PDF':<24}  Race  {'WIN':>5}  {'SP odds':>7}  {'Expected':>8}")
        print(f"  {'-'*36}  {'-'*24}  {'----'}  {'-----':>5}  {'-------':>7}  {'--------':>8}")
        for r in likely_bugs:
            rstr = f"R{r['race']}" if r['race'] else 'R?'
            sp   = f"{r['winner_odds']:.2f}" if r['winner_odds'] is not None else '  ?  '
            exp  = f"${r['expected_win']:.2f}" if r['expected_win'] is not None else '    ?'
            print(f"  {r['log']:<36}  {r['source']:<24}  {rstr:<5}  ${r['win']:.2f}  {sp:>7}  {exp:>8}")
    else:
        print("  None found.")

    # ── Genuine short-priced winners (low WIN but odds-consistent) ────────────
    if SHOW_ALL or not likely_bugs:
        print()
        print(f"LIKELY GENUINE CHALK  ({len(genuine_chalk)} races with WIN < ${THRESHOLD:.2f} but odds-consistent)")
        print("-" * 80)
        if genuine_chalk:
            print(f"  {'Log file':<36}  {'PDF':<24}  Race  {'WIN':>5}  {'SP odds':>7}  {'Expected':>8}")
            print(f"  {'-'*36}  {'-'*24}  {'----'}  {'-----':>5}  {'-------':>7}  {'--------':>8}")
            for r in genuine_chalk:
                rstr = f"R{r['race']}" if r['race'] else 'R?'
                sp   = f"{r['winner_odds']:.2f}" if r['winner_odds'] is not None else '  ?  '
                exp  = f"${r['expected_win']:.2f}" if r['expected_win'] is not None else '    ?'
                print(f"  {r['log']:<36}  {r['source']:<24}  {rstr:<5}  ${r['win']:.2f}  {sp:>7}  {exp:>8}")
        else:
            print("  None found.")

    print()
    print("=" * 80)
    print(f"  Total WIN < ${THRESHOLD:.2f}  :  {len(all_flagged):>4} races")
    print(f"  Likely parser bugs :  {len(likely_bugs):>4} races  (winner odds inconsistent with WIN)")
    print(f"  Genuine chalk      :  {len(genuine_chalk):>4} races  (odds-consistent, or odds unknown)")
    print("=" * 80)
    print()
    if likely_bugs:
        print("  ACTION: Re-run process_results.py on the PDFs listed above (now fixed)")
        print("          and update those results-log entries.\n")


if __name__ == '__main__':
    main()
