"""backfill_results_to_entries.py -- Create synthetic entries rows from
result charts for every non-SA track that has a result but no PP-derived
entry.

Tracks with PP files (CT, EVD, FP, GP, SAR) contribute real morning-line
entries via brisnet_parser_v2 + backfill_entries.py. Tracks with no PP
files (DD, FG, MVR) and any cards on other tracks where the PP file was
missing currently have zero entries — those races are invisible to the
conditional-logit model. This script fills the gap from the results table:
post-race odds substitute for ml_odds, prime_power and the signals are
NULL/empty, and the new rows are tagged source='RESULTS' so the CL model
buckets them away from real morning-line rows. The earlier SA backfill
already follows the same convention.

Idempotent via the entries unique index on
(track, race_date, race_num, horse_name).

Usage:
    py scripts/backfill_results_to_entries.py
"""

import sqlite3, sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

DB_PATH = Path(__file__).parent / 'benter_model.db'

# SA already has its own backfill (backfill_sa_entries.py); skip it here so
# the two scripts stay independent and we don't double-write SA.
SELECT_GAPS = """
SELECT ra.track, ra.race_id, ra.race_date, ra.race_num,
       res.finish_pos, res.horse_name,
       res.trainer, res.jockey, res.sire, res.odds
FROM races ra
JOIN results res ON res.race_id = ra.race_id
WHERE ra.track != 'SA'
  AND res.odds IS NOT NULL AND res.odds > 1.0
"""

INSERT_ENTRY = """
INSERT OR IGNORE INTO entries
(race_id, track, race_date, race_num, post_pos, horse_name, source,
 ml_odds, final_odds, prime_power, pp_rank,
 trainer, jockey, sire,
 signal_types, is_pick, improving, jt_zero)
VALUES (?, ?, ?, ?, NULL, ?, 'RESULTS', ?, ?, NULL, NULL, ?, ?, ?, '', 0, 0, 0)
"""


def main():
    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}")
        sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    rows = cur.execute(SELECT_GAPS).fetchall()
    inserted = 0
    for track, race_id, race_date, race_num, finish_pos, horse, trainer, jockey, sire, odds in rows:
        cur.execute(INSERT_ENTRY,
                    (race_id, track, race_date, race_num, horse,
                     odds, odds, trainer, jockey, sire))
        if cur.rowcount:
            inserted += 1
    con.commit()

    print(f"Inserted {inserted} new RESULTS-sourced entries")
    print("\nPer-track entries breakdown (after backfill):")
    print(f"  {'TRACK':<5} {'PP':>6} {'RESULTS':>8} {'TOTAL':>6}")
    for row in con.execute("""
        SELECT track,
               SUM(CASE WHEN source='PP'      THEN 1 ELSE 0 END) AS pp,
               SUM(CASE WHEN source='RESULTS' THEN 1 ELSE 0 END) AS res,
               COUNT(*) AS total
        FROM entries GROUP BY track ORDER BY track
    """):
        print(f"  {row[0]:<5} {row[1]:>6} {row[2]:>8} {row[3]:>6}")

    cl_races = con.execute("""
        SELECT COUNT(DISTINCT e.race_id) FROM entries e
        JOIN results r ON r.race_id = e.race_id AND r.horse_name = e.horse_name
        WHERE r.finish_pos IS NOT NULL AND e.ml_odds IS NOT NULL AND e.ml_odds > 1.0
    """).fetchone()[0]
    print(f"\nCL training races eligible (entries x results, ml_odds>1.0): {cl_races}")
    con.close()


if __name__ == '__main__':
    main()
