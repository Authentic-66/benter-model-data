"""One-off backfill: run every archived PP PDF through the parser and
persist full-field starters to the entries table in benter_model.db.

Usage:
    py backfill_entries.py

Idempotent: entries uses INSERT OR REPLACE keyed on
(track, race_date, race_num, horse_name), so re-runs and duplicate
format variants of the same card (e.g. gpx0509*.pdf) collapse cleanly.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import brisnet_parser_v2 as bp

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

ROOT = Path(__file__).parent.parent
DB_PATH = Path(__file__).parent / "benter_model.db"

FOLDERS = [
    ("CharlesTown/ct-pps-files", "CT"),
    ("Evangeline Downs/evd-pps-files", "EVD"),
    ("Fairmount Park/fp-pps-files", "FP"),
    ("Gulfstream Park/gp-pps-files", "GP"),
    ("Saratoga/sar-pps-files", "SAR"),
]


def main():
    total_written = 0
    n_files = n_failed = 0
    print("=" * 72)
    print("BACKFILL: archived PP PDFs -> entries table")
    print("=" * 72)

    for folder, tc in FOLDERS:
        pdfs = sorted((ROOT / folder).glob("*.pdf"))
        if not pdfs:
            continue
        print(f"\n[{tc}] {folder}  ({len(pdfs)} files)")
        for pdf in pdfs:
            n_files += 1
            try:
                text = bp.extract_text(pdf)
                race_date = bp.extract_file_date(pdf, tc, text)
                if race_date is None:
                    print(f"  {pdf.name:<18} SKIP - no race date found")
                    n_failed += 1
                    continue
                races = bp.parse_brisnet(text, tc, race_date)
                n_horses = sum(len(r["horses"]) for r in races.values())
                if not n_horses:
                    print(f"  {pdf.name:<18} {race_date}  SKIP - no horses parsed")
                    n_failed += 1
                    continue
                n = bp.write_entries_db(races, tc, race_date)
                if n is None:
                    n_failed += 1
                    continue
                total_written += n
                print(f"  {pdf.name:<18} {race_date}  {len(races):>2} races  {n:>3} horses")
            except Exception as e:
                print(f"  {pdf.name:<18} FAILED - {e}")
                n_failed += 1

    print("\n" + "=" * 72)
    print(f"Files processed: {n_files}  (failed/skipped: {n_failed})")
    print(f"Entry rows written this run: {total_written}")

    # ── Coverage report ──────────────────────────────────────────────────
    con = sqlite3.connect(DB_PATH)
    total = con.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    print(f"\nentries table total: {total}")

    print("\nPer track/date join coverage (entries matched to results):")
    rows = con.execute("""
        SELECT e.track, e.race_date, COUNT(*) AS n,
               SUM(CASE WHEN r.result_id IS NOT NULL THEN 1 ELSE 0 END) AS matched,
               SUM(CASE WHEN r.finish_pos = 1 THEN 1 ELSE 0 END) AS winners
        FROM entries e
        LEFT JOIN results r
          ON r.race_id = e.race_id AND r.horse_name = e.horse_name
        GROUP BY e.track, e.race_date
        ORDER BY e.track, e.race_date
    """).fetchall()
    print(f"  {'TRACK':<6}{'DATE':<12}{'ENTRIES':>8}{'MATCHED':>9}{'WINNERS':>9}")
    no_results = []
    for tc, d, n, matched, winners in rows:
        print(f"  {tc:<6}{d:<12}{n:>8}{matched:>9}{winners:>9}")
        if matched == 0:
            no_results.append(f"{tc} {d}")

    joined, total_e = con.execute("""
        SELECT SUM(CASE WHEN r.result_id IS NOT NULL THEN 1 ELSE 0 END), COUNT(*)
        FROM entries e
        LEFT JOIN results r
          ON r.race_id = e.race_id AND r.horse_name = e.horse_name
    """).fetchone()
    con.close()

    print(f"\nOverall join coverage: {joined}/{total_e} entries matched to results"
          f" ({joined / total_e:.1%})" if total_e else "\nentries table is empty")
    if no_results:
        print(f"Dates with NO results in DB ({len(no_results)}): " + ", ".join(no_results))


if __name__ == "__main__":
    main()
