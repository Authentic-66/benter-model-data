"""backfill_sa_entries.py -- Synthesise entries rows for Santa Anita from
results PDFs.

The Benter-style conditional logit in prob_model.py trains on the entries
table (full fields per starter). Tracks with Brisnet PPs get rich entries
from brisnet_parser_v2.py / backfill_entries.py. Santa Anita has only result
charts in this repo, so we create entries from results: post-race odds stand
in for ml_odds, prime_power and the signals are NULL/empty, and the model's
pp_missing flag (CL coefficient -0.919) absorbs the absent PP factors.

Idempotent via the (track, race_date, race_num, horse_name) unique index on
entries; re-running after new SA result PDFs land only inserts the new rows.

Usage:
    py scripts/backfill_sa_entries.py
"""

import sqlite3, sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

DB_PATH = Path(__file__).parent / 'benter_model.db'

SELECT_SA = """
SELECT ra.race_id, ra.race_date, ra.race_num,
       res.finish_pos, res.horse_name,
       res.trainer, res.jockey, res.sire, res.odds
FROM races ra
JOIN results res ON res.race_id = ra.race_id
WHERE ra.track = 'SA'
  AND res.odds IS NOT NULL AND res.odds > 1.0
"""

INSERT_ENTRY = """
INSERT OR IGNORE INTO entries
(race_id, track, race_date, race_num, post_pos, horse_name, source,
 ml_odds, final_odds, prime_power, pp_rank,
 trainer, jockey, sire,
 signal_types, is_pick, improving, jt_zero)
VALUES (?, 'SA', ?, ?, ?, ?, 'RESULTS', ?, ?, NULL, NULL, ?, ?, ?, '', 0, 0, 0)
"""


def main():
    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}")
        sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    rows = cur.execute(SELECT_SA).fetchall()
    inserted = 0
    for race_id, race_date, race_num, finish_pos, horse, trainer, jockey, sire, odds in rows:
        # post_pos isn't preserved in results; leave NULL — not a CL feature
        cur.execute(INSERT_ENTRY,
                    (race_id, race_date, race_num, None, horse,
                     odds, odds, trainer, jockey, sire))
        if cur.rowcount:
            inserted += 1
    con.commit()

    # Sanity summary
    total = cur.execute("SELECT COUNT(*) FROM entries WHERE track='SA'").fetchone()[0]
    races = cur.execute("SELECT COUNT(DISTINCT race_id) FROM entries WHERE track='SA'").fetchone()[0]
    print(f"Inserted {inserted} new SA entries (table now has {total} rows across {races} races)")

    # Verify CL training would pick up SA
    cl = cur.execute("""
        SELECT COUNT(DISTINCT e.race_id) FROM entries e
        JOIN results r ON r.race_id = e.race_id AND r.horse_name = e.horse_name
        WHERE r.finish_pos IS NOT NULL AND e.ml_odds IS NOT NULL AND e.ml_odds > 1.0
          AND e.track = 'SA'
    """).fetchone()[0]
    print(f"SA races eligible for CL training: {cl}")

    con.close()


if __name__ == '__main__':
    main()
