"""
ROI Tracker — calculates W/P/S ROI for a model race day
All bets are $2 standard units
Usage: python roi_tracker.py <TRACK_CODE> <YYYYMMDD>
  e.g. python roi_tracker.py CT 20240103
"""

import sys

TRACK_NAMES = {
    'GP':  'Gulfstream Park',   'CT':  'Charles Town',
    'FP':  'Fairmount Park',    'EVD': 'Evangeline Downs',
    'MVR': 'Mahoning Valley',   'DD':  'Delta Downs',
    'FG':  'Fair Grounds',      'ST':  'Sha Tin',
    'HV':  'Happy Valley',
}

# ── Input helpers ─────────────────────────────────────────────────────────────

def ask(msg):
    return input(msg).strip()

def ask_float(msg):
    while True:
        raw = input(msg).strip().lstrip('$')
        if not raw:
            return 0.0
        try:
            return float(raw)
        except ValueError:
            print("    Enter a number (e.g. 4.80)")

def ask_int(msg):
    while True:
        raw = input(msg).strip()
        if raw.upper() in ('SCR', ''):
            return 0
        try:
            v = int(raw)
            if 0 <= v <= 30:
                return v
        except ValueError:
            pass
        print("    Enter a finishing position number (or SCR)")

def ask_bets(msg):
    while True:
        raw = input(msg).strip().upper().replace(' ', '')
        bets = [b for b in raw if b in ('W', 'P', 'S')]
        # Deduplicate, preserve order
        seen = set()
        bets = [b for b in bets if not (b in seen or seen.add(b))]
        if bets:
            return bets
        print("    Enter at least one of W, P, S  (e.g. WPS or W or WP)")

# ── Data collection ───────────────────────────────────────────────────────────

def collect_picks(track_name, date_str):
    picks = []
    print(f"\n{track_name.upper()} — {date_str}")
    print("Enter each model pick. Leave race number blank when done.\n")

    while True:
        race_raw = ask("Race #: ")
        if not race_raw:
            break
        try:
            race_num = int(race_raw)
        except ValueError:
            print("  Invalid — enter a race number")
            continue

        horse = ask("Horse  : ")
        if not horse:
            continue

        bets   = ask_bets("Bets   : [W/P/S — e.g. WPS or W] ")
        finish = ask_int ("Finish : [position, or SCR] ")

        # Only prompt for payouts that could have cashed
        win_pay = place_pay = show_pay = 0.0
        if finish == 1 and 'W' in bets:
            win_pay   = ask_float("  Win payout   ($2): $")
        if finish in (1, 2) and 'P' in bets:
            place_pay = ask_float("  Place payout ($2): $")
        if finish in (1, 2, 3) and 'S' in bets:
            show_pay  = ask_float("  Show payout  ($2): $")

        picks.append({
            'race':       race_num,
            'horse':      horse,
            'bets':       bets,
            'finish':     finish,
            'win_pay':    win_pay,
            'place_pay':  place_pay,
            'show_pay':   show_pay,
        })
        print()

    return picks

# ── Calculation ───────────────────────────────────────────────────────────────

def calc(pick):
    fin = pick['finish']
    if fin == 0:            # scratched — refund, don't count
        return 0.0, 0.0

    invested = len(pick['bets']) * 2.0
    returned = 0.0
    if 'W' in pick['bets']: returned += pick['win_pay']   if fin == 1     else 0.0
    if 'P' in pick['bets']: returned += pick['place_pay'] if fin <= 2     else 0.0
    if 'S' in pick['bets']: returned += pick['show_pay']  if fin <= 3     else 0.0
    return invested, returned

# ── Output ────────────────────────────────────────────────────────────────────

def print_summary(picks, track_name, date_str):
    rows = [(p, *calc(p)) for p in picks]

    total_inv = sum(r[1] for r in rows)
    total_ret = sum(r[2] for r in rows)
    total_pl  = total_ret - total_inv
    roi       = (total_pl / total_inv * 100) if total_inv > 0 else 0.0

    def pl_fmt(v):
        return f"+${v:.2f}" if v >= 0 else f"-${abs(v):.2f}"

    roi_str = f"+{roi:.1f}%" if roi >= 0 else f"{roi:.1f}%"

    print(f"\n{'='*70}")
    print(f"  {track_name.upper()}  —  ROI SUMMARY  {date_str}")
    print(f"{'='*70}")
    print(f"  {'Race':<5} {'Horse':<26} {'Bets':<5} {'Fin':>3}  "
          f"{'Invested':>8}  {'Returned':>8}  {'P/L':>9}")
    print(f"  {'─'*66}")

    for pick, inv, ret in sorted(rows, key=lambda x: x[0]['race']):
        pl       = ret - inv
        fin_str  = 'SCR' if pick['finish'] == 0 else str(pick['finish'])
        bets_str = ''.join(pick['bets'])
        print(
            f"  R{pick['race']:<4} {pick['horse']:<26} {bets_str:<5} {fin_str:>3} "
            f" ${inv:>6.2f}   ${ret:>6.2f}  {pl_fmt(pl):>9}"
        )

    print(f"  {'─'*66}")
    active = sum(1 for _, inv, _ in rows if inv > 0)
    print(
        f"  {'TOTAL':<35} {active:>3} pick(s)"
        f"  ${total_inv:>6.2f}   ${total_ret:>6.2f}  {pl_fmt(total_pl):>9}"
    )
    print(f"\n  ROI: {roi_str}  (${total_inv:.2f} invested, ${total_ret:.2f} returned)")
    print(f"{'='*70}\n")

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python roi_tracker.py <TRACK_CODE> <YYYYMMDD>")
        print("  e.g. python roi_tracker.py CT 20240103")
        sys.exit(1)

    track    = sys.argv[1].upper()
    date_raw = sys.argv[2]
    date_str = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}" if len(date_raw) == 8 else date_raw

    picks = collect_picks(TRACK_NAMES.get(track, track), date_str)

    if not picks:
        print("No picks entered.")
        sys.exit(0)

    print_summary(picks, TRACK_NAMES.get(track, track), date_str)
