"""Generate empty live-odds templates from picks files.

For each picks file (TRACK + date) supplied (or every picks file matching
today's date by default), writes a template under scripts/live-odds/
with one row per picked horse and the ML pre-filled. Fill in the LIVE
column at 5 MTP, then run live_odds_flag.py to see drift signals.

Usage:
    py gen_live_odds_template.py                     # today's picks, all tracks
    py gen_live_odds_template.py picks_GP_06122026.txt
    py gen_live_odds_template.py 2026-06-12          # all tracks for a date
"""

import re
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

SCRIPT_DIR = Path(__file__).parent
TEMPLATE_DIR = SCRIPT_DIR / "live-odds"

PICKS_NAME_RE = re.compile(r"^picks_([A-Z]+)_(\d{8})\.txt$", re.IGNORECASE)

HEADER = (
    "# LIVE_ODDS_{track}_{mmddyyyy}.txt\n"
    "# Fill the LIVE column with current decimal odds at 5 MTP.\n"
    "# Lines starting with # are ignored. Blank LIVE -> skipped.\n"
    "# Run: py scripts/live_odds_flag.py {filename}\n"
    "#\n"
    "# {race:<5} {pp:<4} {horse:<32} {ml:<8} {live}\n"
)
ROW_FMT = "  {race:<5} {pp:<4} {horse:<32} {ml:<8}\n"


def parse_picks(picks_path):
    """Yield (race_num, horse, ml_odds_decimal) per pick row."""
    for raw in picks_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            race_num = int(re.sub(r"\D", "", parts[1]))
        except ValueError:
            continue
        horse = parts[2]
        try:
            ml = float(parts[5])
        except ValueError:
            ml = None
        yield race_num, horse, ml


def horse_pp_lookup(track, race_date):
    """Map horse_name -> post_pos using the entries table (for nicer PP
    display). Falls back to '?' if the row isn't in the DB yet."""
    import sqlite3
    db = SCRIPT_DIR / "benter_model.db"
    if not db.exists():
        return {}
    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT horse_name, post_pos FROM entries"
        " WHERE track=? AND race_date=?",
        (track.upper(), race_date),
    ).fetchall()
    con.close()
    return {h: pp for h, pp in rows if pp is not None}


def write_template(picks_path):
    m = PICKS_NAME_RE.match(picks_path.name)
    if not m:
        print(f"  skip (not a picks file): {picks_path.name}")
        return None
    track = m.group(1).upper()
    mmddyyyy = m.group(2)
    race_date = f"{mmddyyyy[4:8]}-{mmddyyyy[0:2]}-{mmddyyyy[2:4]}"

    picks = list(parse_picks(picks_path))
    if not picks:
        print(f"  skip (no picks): {picks_path.name}")
        return None

    pps = horse_pp_lookup(track, race_date)

    TEMPLATE_DIR.mkdir(exist_ok=True)
    out_name = f"LIVE_ODDS_{track}_{mmddyyyy}.txt"
    out_path = TEMPLATE_DIR / out_name

    if out_path.exists():
        print(f"  exists (preserving live values): {out_name}")
        return out_path

    with out_path.open("w", encoding="utf-8") as f:
        f.write(HEADER.format(
            track=track, mmddyyyy=mmddyyyy, filename=out_name,
            race=" RACE", pp=" PP", horse=" HORSE", ml=" ML", live=" LIVE",
        ))
        for race_num, horse, ml in sorted(picks):
            pp = pps.get(horse, "?")
            ml_str = f"{ml:.1f}" if ml is not None else "?"
            f.write(ROW_FMT.format(
                race=f"R{race_num}", pp=str(pp), horse=horse[:32], ml=ml_str,
            ))

    print(f"  wrote {len(picks)} rows -> live-odds/{out_name}")
    return out_path


def picks_for_date(d):
    """Return picks_*.txt files whose date == d (date object)."""
    target = d.strftime("%m%d%Y")
    return sorted(SCRIPT_DIR.glob(f"picks_*_{target}.txt"))


def main():
    args = sys.argv[1:]
    if not args:
        # Today, every track
        files = picks_for_date(date.today())
    elif len(args) == 1 and re.match(r"^\d{4}-\d{2}-\d{2}$", args[0]):
        y, m, d = args[0].split("-")
        files = picks_for_date(date(int(y), int(m), int(d)))
    else:
        files = []
        for a in args:
            p = Path(a) if Path(a).is_absolute() else SCRIPT_DIR / a
            if p.exists():
                files.append(p)
            else:
                print(f"  not found: {a}")

    if not files:
        print("No picks files to template.")
        return

    print(f"Generating templates for {len(files)} picks file(s):")
    for f in files:
        write_template(f)


if __name__ == "__main__":
    main()
