"""Backfill entries.ml_odds from results.odds.

Some entries rows were parsed from Brisnet PPs without a usable ML odds
value. Those races are excluded from the conditional-logit training set
(prob_model.py requires ml_odds IS NOT NULL AND > 1.0), even though the
final post-time odds for the same horse are already in the results table.

This script joins entries to results on (race_id, horse_name) and copies
results.odds -> entries.ml_odds wherever entries.ml_odds IS NULL. The
final odds are a strictly more efficient market than the morning line, so
using them as a fallback in-fills the anchor feature without distorting
relative-strength signals (log_ml is centered within each race anyway).

Usage:
    py scripts/backfill_ml_odds.py [--dry-run]
"""

import argparse
import sqlite3
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

DB_PATH = Path(__file__).parent / "benter_model.db"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would change without writing")
    args = ap.parse_args()

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    before_null = cur.execute(
        "SELECT COUNT(*) FROM entries WHERE ml_odds IS NULL"
    ).fetchone()[0]

    fillable = cur.execute("""
        SELECT COUNT(*) FROM entries e
        JOIN results r ON r.race_id = e.race_id AND r.horse_name = e.horse_name
        WHERE e.ml_odds IS NULL AND r.odds IS NOT NULL AND r.odds > 1.0
    """).fetchone()[0]

    by_track = cur.execute("""
        SELECT e.track, COUNT(*)
        FROM entries e
        JOIN results r ON r.race_id = e.race_id AND r.horse_name = e.horse_name
        WHERE e.ml_odds IS NULL AND r.odds IS NOT NULL AND r.odds > 1.0
        GROUP BY e.track ORDER BY 2 DESC
    """).fetchall()

    print(f"entries.ml_odds NULL before:      {before_null}")
    print(f"fillable from results.odds > 1.0: {fillable}")
    print(f"remaining NULL after backfill:    {before_null - fillable}")
    print("\nFillable by track:")
    for t, n in by_track:
        print(f"  {t:<5} {n}")

    if args.dry_run:
        print("\n--dry-run: no changes written.")
        con.close()
        return

    cur.execute("""
        UPDATE entries
        SET ml_odds = (
            SELECT r.odds FROM results r
            WHERE r.race_id = entries.race_id
              AND r.horse_name = entries.horse_name
              AND r.odds IS NOT NULL AND r.odds > 1.0
        )
        WHERE ml_odds IS NULL
          AND EXISTS (
            SELECT 1 FROM results r
            WHERE r.race_id = entries.race_id
              AND r.horse_name = entries.horse_name
              AND r.odds IS NOT NULL AND r.odds > 1.0
          )
    """)
    filled = cur.rowcount
    con.commit()

    after_null = cur.execute(
        "SELECT COUNT(*) FROM entries WHERE ml_odds IS NULL"
    ).fetchone()[0]

    print(f"\nFilled {filled} rows.")
    print(f"entries.ml_odds NULL after:       {after_null}")

    # Quick sanity check on how many training-eligible races this unlocks
    n_train = cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT e.race_id FROM entries e
            JOIN results r ON r.race_id = e.race_id AND r.horse_name = e.horse_name
            WHERE r.finish_pos IS NOT NULL
              AND e.ml_odds IS NOT NULL AND e.ml_odds > 1.0
            GROUP BY e.race_id
            HAVING SUM(CASE WHEN r.finish_pos = 1 THEN 1 ELSE 0 END) = 1
               AND COUNT(*) >= 2
        )
    """).fetchone()[0]
    print(f"CL training-eligible races now:   {n_train}")
    con.close()


if __name__ == "__main__":
    main()
