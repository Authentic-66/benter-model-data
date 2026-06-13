"""Revert the ml_odds backfill, then create entries.final_odds as a
separate column populated from results.odds for every entry that has a
matching result.

Background: backfill_ml_odds.py earlier copied results.odds (the final
tote price) into entries.ml_odds where the latter was NULL. CV showed
final odds and ML are different signals - using the final tote price as
ML degraded model performance. This restores the distinction and gives
us both columns to experiment with.

Revert heuristic: any entry where ml_odds equals the matching
results.odds is treated as a backfill artifact and set to NULL. This
will over-revert ~10 entries where the real morning line coincidentally
equaled the final tote price; for those rows, the model can median-fill
ml_odds within the race, so the impact is negligible.

Idempotent: safe to run repeatedly.
"""

import sqlite3
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

DB_PATH = Path(__file__).parent / "benter_model.db"


def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # 1. Revert ml_odds where it equals the matching results.odds
    cur.execute("""
        UPDATE entries
        SET ml_odds = NULL
        WHERE ml_odds IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM results r
              WHERE r.race_id = entries.race_id
                AND r.horse_name = entries.horse_name
                AND r.odds = entries.ml_odds
                AND r.odds > 1.0
          )
    """)
    reverted = cur.rowcount
    print(f"Reverted ml_odds -> NULL on {reverted} entries "
          f"(rows where ml_odds == matching results.odds)")

    # 2. Add entries.final_odds column if missing
    cols = {r[1] for r in cur.execute("PRAGMA table_info(entries)")}
    if "final_odds" not in cols:
        cur.execute("ALTER TABLE entries ADD COLUMN final_odds REAL")
        print("Added entries.final_odds column")
    else:
        print("entries.final_odds column already present")

    # 3. Populate final_odds from results.odds for every entry with a
    #    valid matching result.
    cur.execute("""
        UPDATE entries
        SET final_odds = (
            SELECT r.odds FROM results r
            WHERE r.race_id = entries.race_id
              AND r.horse_name = entries.horse_name
              AND r.odds IS NOT NULL AND r.odds > 1.0
        )
        WHERE EXISTS (
            SELECT 1 FROM results r
            WHERE r.race_id = entries.race_id
              AND r.horse_name = entries.horse_name
              AND r.odds IS NOT NULL AND r.odds > 1.0
        )
    """)
    filled = cur.rowcount
    print(f"Populated final_odds on {filled} entries")

    con.commit()

    print("\n--- After ---")
    n_ml = cur.execute("SELECT COUNT(*) FROM entries WHERE ml_odds IS NOT NULL").fetchone()[0]
    n_fin = cur.execute("SELECT COUNT(*) FROM entries WHERE final_odds IS NOT NULL").fetchone()[0]
    n_both = cur.execute(
        "SELECT COUNT(*) FROM entries WHERE ml_odds IS NOT NULL AND final_odds IS NOT NULL"
    ).fetchone()[0]
    print(f"entries with ml_odds:    {n_ml}")
    print(f"entries with final_odds: {n_fin}")
    print(f"entries with both:       {n_both}")

    # Training-eligible races: where both odds are present + clean winner
    n_train = cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT e.race_id FROM entries e
            JOIN results r ON r.race_id = e.race_id AND r.horse_name = e.horse_name
            WHERE r.finish_pos IS NOT NULL
              AND e.ml_odds IS NOT NULL AND e.ml_odds > 1.0
              AND e.final_odds IS NOT NULL AND e.final_odds > 1.0
            GROUP BY e.race_id
            HAVING SUM(CASE WHEN r.finish_pos = 1 THEN 1 ELSE 0 END) = 1
               AND COUNT(*) >= 2
        )
    """).fetchone()[0]
    print(f"races with both odds + clean winner: {n_train}")

    con.close()


if __name__ == "__main__":
    main()
