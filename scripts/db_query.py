"""
db_query.py -- Query helpers for benter_model.db

Usage (interactive):
    py -i scripts/db_query.py
    >>> roi_by_track('GP')
    >>> top_trainers('CT', min_wins=3)
    >>> search_horse('RuleSeventySix')

Or import in your own scripts:
    from db_query import roi_by_track, top_trainers
"""

import sqlite3, re
from pathlib import Path

DB_PATH = Path(__file__).parent / 'benter_model.db'


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _fmt_roi(invested, returned):
    if not invested:
        return 'n/a'
    pct = (returned - invested) / invested * 100
    sign = '+' if pct >= 0 else ''
    return f"{sign}{pct:.1f}%"


# ── roi_by_track ──────────────────────────────────────────────────────────────

def roi_by_track(track, start_date=None, end_date=None):
    """
    ROI summary for a track, optionally filtered by date range (YYYY-MM-DD).

    Returns dict: {track, start, end, n_picks, n_wins, invested, returned, pl, roi_pct}
    Also prints a formatted summary.
    """
    sql = """
        SELECT
            COUNT(*)                              AS n_picks,
            SUM(CASE WHEN finish_pos=1 THEN 1 ELSE 0 END) AS n_wins,
            SUM(invested)                         AS invested,
            SUM(returned)                         AS returned,
            SUM(pl)                               AS pl,
            MIN(race_date)                        AS start_date,
            MAX(race_date)                        AS end_date
        FROM roi_entries
        WHERE track = ?
          AND invested > 0
          {date_filter}
    """
    params = [track.upper()]
    date_filter = ''
    if start_date:
        date_filter += ' AND race_date >= ?'
        params.append(start_date)
    if end_date:
        date_filter += ' AND race_date <= ?'
        params.append(end_date)

    with _conn() as c:
        row = c.execute(sql.format(date_filter=date_filter), params).fetchone()

    if not row or not row['invested']:
        print(f"No ROI data found for {track.upper()}")
        return None

    result = {
        'track':    track.upper(),
        'start':    row['start_date'],
        'end':      row['end_date'],
        'n_picks':  row['n_picks'],
        'n_wins':   row['n_wins'],
        'invested': row['invested'],
        'returned': row['returned'],
        'pl':       row['pl'],
        'roi_pct':  (row['returned'] - row['invested']) / row['invested'] * 100,
    }

    pl_str = f"+${result['pl']:.2f}" if result['pl'] >= 0 else f"-${abs(result['pl']):.2f}"
    print(f"\n  ROI: {result['track']}  ({result['start']} to {result['end']})")
    print(f"  Picks: {result['n_picks']}  Wins: {result['n_wins']}")
    print(f"  Invested: ${result['invested']:.2f}  Returned: ${result['returned']:.2f}")
    print(f"  P/L: {pl_str}  ROI: {_fmt_roi(result['invested'], result['returned'])}\n")
    return result


# ── roi_by_trainer ────────────────────────────────────────────────────────────

def roi_by_trainer(trainer, track=None):
    """
    All ROI entries for picks associated with a trainer (partial match on trainer_name).
    Optionally filter by track.

    Returns list of dicts and prints a summary table.
    """
    sql = """
        SELECT e.track, e.race_date, e.race_num, e.horse_name,
               e.finish_pos, e.invested, e.returned, e.pl, e.note,
               p.trainer_name, p.ml_odds
        FROM roi_entries e
        LEFT JOIN picks p ON p.pick_id = e.pick_id
        WHERE e.invested > 0
          AND (p.trainer_name LIKE ? OR e.note LIKE ?)
          {track_filter}
        ORDER BY e.race_date, e.track, e.race_num
    """
    like   = f"%{trainer}%"
    params = [like, like]
    track_filter = ''
    if track:
        track_filter = 'AND e.track = ?'
        params.append(track.upper())

    with _conn() as c:
        rows = c.execute(sql.format(track_filter=track_filter), params).fetchall()

    if not rows:
        print(f"No picks found for trainer matching '{trainer}'")
        return []

    results  = [dict(r) for r in rows]
    invested = sum(r['invested'] for r in results)
    returned = sum(r['returned'] for r in results)

    print(f"\n  Trainer search: '{trainer}'  ({len(results)} picks)")
    print(f"  {'Date':<12} {'Track':<5} {'Race':>4}  {'Horse':<26} {'Fin':>3}  {'Inv':>6}  {'Ret':>6}  {'P/L':>8}")
    print(f"  {'-'*80}")
    for r in results:
        pl_str = f"+${r['pl']:.2f}" if r['pl'] >= 0 else f"-${abs(r['pl']):.2f}"
        fin    = str(r['finish_pos']) if r['finish_pos'] else '?'
        print(f"  {r['race_date']:<12} {r['track']:<5} R{r['race_num']:<3}  "
              f"{r['horse_name']:<26} {fin:>3}  ${r['invested']:>4.2f}  ${r['returned']:>4.2f}  {pl_str:>8}")
    print(f"  {'-'*80}")
    pl_total = returned - invested
    pl_str   = f"+${pl_total:.2f}" if pl_total >= 0 else f"-${abs(pl_total):.2f}"
    print(f"  {'TOTAL':<48}  ${invested:>4.2f}  ${returned:>4.2f}  {pl_str:>8}  ROI: {_fmt_roi(invested, returned)}\n")
    return results


# ── top_trainers ──────────────────────────────────────────────────────────────

def top_trainers(track, min_wins=5):
    """
    Trainers ranked by win rate at a track, based on ROI entry data.
    Includes only trainers with >= min_wins wins.

    Returns list of dicts and prints a ranked table.
    """
    sql = """
        SELECT
            p.trainer_name,
            COUNT(*) AS starts,
            SUM(CASE WHEN e.finish_pos = 1 THEN 1 ELSE 0 END) AS wins,
            SUM(e.invested)  AS invested,
            SUM(e.returned)  AS returned,
            SUM(e.pl)        AS pl
        FROM roi_entries e
        JOIN picks p ON p.pick_id = e.pick_id
        WHERE e.track = ?
          AND e.invested > 0
          AND p.trainer_name IS NOT NULL
        GROUP BY p.trainer_name
        HAVING wins >= ?
        ORDER BY CAST(wins AS REAL) / starts DESC, wins DESC
    """
    with _conn() as c:
        rows = c.execute(sql, (track.upper(), min_wins)).fetchall()

    if not rows:
        print(f"No trainer data found for {track.upper()} (min_wins={min_wins})")
        return []

    results = [dict(r) for r in rows]

    print(f"\n  Top Trainers: {track.upper()}  (min {min_wins} tracked wins)")
    print(f"  {'#':<3}  {'Trainer':<28}  {'Starts':>6}  {'Wins':>4}  {'Win%':>6}  {'ROI':>8}")
    print(f"  {'-'*64}")
    for i, r in enumerate(results, 1):
        pct = r['wins'] / r['starts'] * 100 if r['starts'] else 0
        print(f"  {i:<3}  {(r['trainer_name'] or '?'):<28}  {r['starts']:>6}  {r['wins']:>4}  "
              f"{pct:>5.1f}%  {_fmt_roi(r['invested'], r['returned']):>8}")
    print()
    return results


# ── recent_results ────────────────────────────────────────────────────────────

def recent_results(track, n=10):
    """
    Last N race results for a track (by race_date desc).

    Returns list of race dicts and prints a formatted table.
    """
    sql = """
        SELECT ra.race_date, ra.race_num, ra.conditions, ra.surface, ra.purse,
               re.finish_pos, re.horse_name, re.odds, re.trainer, re.sire,
               re.win_pay, re.place_pay, re.show_pay
        FROM races ra
        JOIN results re ON re.race_id = ra.race_id
        WHERE ra.track = ?
        ORDER BY ra.race_date DESC, ra.race_num DESC, re.finish_pos
        LIMIT ?
    """
    with _conn() as c:
        rows = c.execute(sql, (track.upper(), n * 12)).fetchall()  # ~12 starters per race

    if not rows:
        print(f"No results found for {track.upper()}")
        return []

    # Group by (date, race_num)
    from collections import OrderedDict
    races = OrderedDict()
    for r in rows:
        key = (r['race_date'], r['race_num'])
        if len(races) >= n and key not in races:
            break
        races.setdefault(key, []).append(dict(r))

    for (date, rnum), finishers in list(races.items())[:n]:
        f0   = finishers[0]
        meta = '  |  '.join(filter(None, [f0['conditions'], f0['surface'],
                                           f"${f0['purse']:,.0f}" if f0['purse'] else '']))
        print(f"\n  {date}  RACE {rnum}  --  {meta}")
        print(f"  {'Pos':>3}  {'Horse':<28}  {'Odds':>6}  {'Trainer':<22}")
        print(f"  {'-'*64}")
        for f in sorted(finishers, key=lambda x: x['finish_pos'] or 99):
            trainer = (f['trainer'] or '')[:22]
            print(f"  {f['finish_pos']:>3}  {f['horse_name']:<28}  {f['odds']:>6.2f}  {trainer}")
        w, p, s = finishers[0]['win_pay'], finishers[0]['place_pay'], finishers[0]['show_pay']
        payouts = []
        if w: payouts.append(f"WIN ${w:.2f}")
        if p: payouts.append(f"PLC ${p:.2f}")
        if s: payouts.append(f"SHW ${s:.2f}")
        if payouts:
            print(f"  {'  '.join(payouts)}")

    print()
    return [f for group in races.values() for f in group]


# ── search_horse ──────────────────────────────────────────────────────────────

def search_horse(horse_name):
    """
    Find all results for a horse (case-insensitive partial match).
    Also shows any model picks and ROI entries for that horse.

    Returns list of result dicts.
    """
    like = f"%{horse_name}%"

    with _conn() as c:
        results = c.execute("""
            SELECT ra.track, ra.race_date, ra.race_num, ra.conditions, ra.surface,
                   re.finish_pos, re.horse_name, re.odds, re.trainer, re.sire,
                   re.win_pay, re.place_pay, re.show_pay
            FROM results re
            JOIN races ra ON ra.race_id = re.race_id
            WHERE re.horse_name LIKE ?
            ORDER BY ra.race_date DESC
        """, (like,)).fetchall()

        roi = c.execute("""
            SELECT e.track, e.race_date, e.race_num, e.horse_name,
                   e.finish_pos, e.invested, e.returned, e.pl, e.note
            FROM roi_entries e
            WHERE e.horse_name LIKE ?
              AND e.invested > 0
            ORDER BY e.race_date DESC
        """, (like,)).fetchall()

    if not results and not roi:
        print(f"No data found for horse matching '{horse_name}'")
        return []

    if results:
        print(f"\n  Race results for '{horse_name}'  ({len(results)} entries)")
        print(f"  {'Date':<12} {'Track':<5} {'Race':>4}  {'Horse':<26} {'Pos':>3}  {'Odds':>6}  {'Trainer'}")
        print(f"  {'-'*72}")
        for r in results:
            trainer = (r['trainer'] or '')[:20]
            fin     = str(r['finish_pos']) if r['finish_pos'] else '?'
            print(f"  {r['race_date']:<12} {r['track']:<5} R{r['race_num']:<3}  "
                  f"{r['horse_name']:<26} {fin:>3}  {r['odds']:>6.2f}  {trainer}")

    if roi:
        invested = sum(r['invested'] for r in roi)
        returned = sum(r['returned'] for r in roi)
        print(f"\n  Model picks for '{horse_name}'  ({len(roi)} entries)")
        print(f"  {'Date':<12} {'Track':<5} {'Race':>4}  {'Fin':>3}  {'Inv':>6}  {'Ret':>6}  {'P/L':>8}  Note")
        print(f"  {'-'*72}")
        for r in roi:
            fin    = str(r['finish_pos']) if r['finish_pos'] else '?'
            pl     = r['returned'] - r['invested']
            pl_str = f"+${pl:.2f}" if pl >= 0 else f"-${abs(pl):.2f}"
            print(f"  {r['race_date']:<12} {r['track']:<5} R{r['race_num']:<3}  "
                  f"{fin:>3}  ${r['invested']:>4.2f}  ${r['returned']:>4.2f}  {pl_str:>8}  {r['note']}")
        pl_total = returned - invested
        pl_str   = f"+${pl_total:.2f}" if pl_total >= 0 else f"-${abs(pl_total):.2f}"
        print(f"  TOTAL ROI: {_fmt_roi(invested, returned)}  ({pl_str})")

    print()
    return [dict(r) for r in results]


# ── roi_summary_all ───────────────────────────────────────────────────────────

def roi_summary_all():
    """Overall ROI summary across all tracks."""
    sql = """
        SELECT
            track,
            COUNT(*) AS n_picks,
            SUM(CASE WHEN finish_pos = 1 THEN 1 ELSE 0 END) AS n_wins,
            SUM(invested)  AS invested,
            SUM(returned)  AS returned,
            SUM(pl)        AS pl,
            MIN(race_date) AS first_date,
            MAX(race_date) AS last_date
        FROM roi_entries
        WHERE invested > 0
        GROUP BY track
        ORDER BY track
    """
    with _conn() as c:
        rows = c.execute(sql).fetchall()

    if not rows:
        print("No ROI data found.")
        return []

    total_inv = total_ret = 0.0

    print(f"\n  {'='*72}")
    print(f"  BENTER MODEL  --  ROI SUMMARY ALL TRACKS")
    print(f"  {'='*72}")
    print(f"  {'Track':<6}  {'Picks':>5}  {'Wins':>4}  {'Win%':>6}  {'Invested':>9}  {'Returned':>9}  {'ROI':>8}  Date range")
    print(f"  {'-'*72}")

    results = []
    for r in rows:
        pct    = r['n_wins'] / r['n_picks'] * 100 if r['n_picks'] else 0
        roi    = _fmt_roi(r['invested'], r['returned'])
        total_inv += r['invested']
        total_ret += r['returned']
        print(f"  {r['track']:<6}  {r['n_picks']:>5}  {r['n_wins']:>4}  {pct:>5.1f}%  "
              f"${r['invested']:>8.2f}  ${r['returned']:>8.2f}  {roi:>8}  "
              f"{r['first_date']} - {r['last_date']}")
        results.append(dict(r))

    print(f"  {'-'*72}")
    pl = total_ret - total_inv
    pl_str = f"+${pl:.2f}" if pl >= 0 else f"-${abs(pl):.2f}"
    print(f"  {'OVERALL':<6}  {'':>5}  {'':>4}  {'':>6}  ${total_inv:>8.2f}  ${total_ret:>8.2f}  "
          f"{_fmt_roi(total_inv, total_ret):>8}  P/L: {pl_str}")
    print(f"  {'='*72}\n")
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage:")
        print("  py scripts/db_query.py summary")
        print("  py scripts/db_query.py track GP [start_date] [end_date]")
        print("  py scripts/db_query.py trainer Joseph [track]")
        print("  py scripts/db_query.py top CT [min_wins]")
        print("  py scripts/db_query.py recent CT [n]")
        print("  py scripts/db_query.py horse RuleSeventySix")
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd == 'summary':
        roi_summary_all()
    elif cmd == 'track' and len(sys.argv) >= 3:
        roi_by_track(sys.argv[2],
                     sys.argv[3] if len(sys.argv) > 3 else None,
                     sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == 'trainer' and len(sys.argv) >= 3:
        roi_by_trainer(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == 'top' and len(sys.argv) >= 3:
        top_trainers(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 5)
    elif cmd == 'recent' and len(sys.argv) >= 3:
        recent_results(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 10)
    elif cmd == 'horse' and len(sys.argv) >= 3:
        search_horse(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
