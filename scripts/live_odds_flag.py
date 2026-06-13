"""Read a filled live-odds template, print drift flags, write live_odds to DB.

Drift = live_odds / ml_odds (decimal odds ratio). Flag thresholds:

    drift < 0.80   📉 SHARP MONEY   (bet down >20% from ML - positive signal)
    drift > 1.20   📈 DRIFTING       (drifted up >20% - public fading or overlay)
    otherwise      ➡️  STABLE        (within +/-20% of ML)

Usage:
    py live_odds_flag.py                       # process every template for today
    py live_odds_flag.py LIVE_ODDS_GP_06122026.txt
    py live_odds_flag.py 2026-06-12            # all tracks for that date

Lines starting with # are skipped. Rows missing a LIVE value are listed
under '(no live odds yet)' so it's clear what's still to fill.
"""

import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

SCRIPT_DIR = Path(__file__).parent
TEMPLATE_DIR = SCRIPT_DIR / "live-odds"
DB_PATH = SCRIPT_DIR / "benter_model.db"

TEMPLATE_NAME_RE = re.compile(r"^LIVE_ODDS_([A-Z]+)_(\d{8})\.txt$", re.IGNORECASE)
ROW_RE = re.compile(
    r"^\s*R(\d+)\s+(\S+)\s+(\S+)\s+([\d.?]+)(?:\s+([\d.]+))?\s*$"
)

SHARP_THRESHOLD = 0.80
DRIFT_THRESHOLD = 1.20


def classify(ratio):
    if ratio < SHARP_THRESHOLD:
        return "📉 SHARP MONEY"
    if ratio > DRIFT_THRESHOLD:
        return "📈 DRIFTING"
    return "➡️  STABLE"


def parse_template(path):
    """Yield (race, pp, horse, ml, live or None) per row."""
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = ROW_RE.match(raw)
        if not m:
            continue
        race = int(m.group(1))
        pp = m.group(2)
        horse = m.group(3)
        try:
            ml = float(m.group(4))
        except ValueError:
            ml = None
        live = float(m.group(5)) if m.group(5) else None
        yield race, pp, horse, ml, live


def process(path):
    m = TEMPLATE_NAME_RE.match(path.name)
    if not m:
        print(f"skip (not a template): {path.name}")
        return
    track, mmddyyyy = m.group(1).upper(), m.group(2)
    race_date = f"{mmddyyyy[4:8]}-{mmddyyyy[0:2]}-{mmddyyyy[2:4]}"

    rows = list(parse_template(path))
    filled = [r for r in rows if r[3] is not None and r[4] is not None]
    pending = [r for r in rows if r[4] is None]

    print(f"\n{'=' * 76}")
    print(f"LIVE-ODDS DRIFT - {track} {race_date}    ({path.name})")
    print(f"{'=' * 76}")
    print(f"  Filled {len(filled)}/{len(rows)} picks - "
          f"thresholds: <{SHARP_THRESHOLD:.2f} sharp | >{DRIFT_THRESHOLD:.2f} drifting")
    print()

    if filled:
        hdr = (f"  {'RACE':<5}{'PP':<4}{'HORSE':<32}{'ML':>6}{'LIVE':>8}"
               f"{'RATIO':>8}{'%':>8}   FLAG")
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
        for race, pp, horse, ml, live in sorted(filled, key=lambda r: (r[0], r[1])):
            # Round before classifying so display and threshold agree
            # (2.4/3.0 = 0.7999... but prints as 0.80, same as 3.2/4.0).
            ratio = round(live / ml, 2)
            pct = (ratio - 1.0) * 100.0
            print(f"  R{race:<4}{pp:<4}{horse[:32]:<32}"
                  f"{ml:>6.1f}{live:>8.1f}{ratio:>8.2f}{pct:>+7.0f}%   {classify(ratio)}")

    if pending:
        print(f"\n  (no live odds yet, {len(pending)})")
        for race, pp, horse, ml, _ in sorted(pending, key=lambda r: (r[0], r[1])):
            ml_str = f"{ml:.1f}" if ml is not None else "?"
            print(f"    R{race:<4}{pp:<4}{horse[:32]:<32}  ML {ml_str}")

    # Persist live_odds to DB so cl_evaluate / future tooling can read it
    if filled and DB_PATH.exists():
        con = sqlite3.connect(DB_PATH)
        n = 0
        for race, _pp, horse, _ml, live in filled:
            cur = con.execute(
                "UPDATE entries SET live_odds=?"
                " WHERE track=? AND race_date=? AND race_num=? AND horse_name=?",
                (live, track, race_date, race, horse),
            )
            n += cur.rowcount
        con.commit()
        con.close()
        print(f"\n  Wrote live_odds to {n} entries rows in DB.")


def templates_for_date(d):
    target = d.strftime("%m%d%Y")
    return sorted(TEMPLATE_DIR.glob(f"LIVE_ODDS_*_{target}.txt"))


def main():
    args = sys.argv[1:]
    if not args:
        files = templates_for_date(date.today())
    elif len(args) == 1 and re.match(r"^\d{4}-\d{2}-\d{2}$", args[0]):
        y, m, d = args[0].split("-")
        files = templates_for_date(date(int(y), int(m), int(d)))
    else:
        files = []
        for a in args:
            p = Path(a)
            if not p.is_absolute():
                p = TEMPLATE_DIR / a if (TEMPLATE_DIR / a).exists() else SCRIPT_DIR / a
            if p.exists():
                files.append(p)
            else:
                print(f"  not found: {a}")

    if not files:
        print("No templates to process.")
        return

    for f in files:
        process(f)


if __name__ == "__main__":
    main()
