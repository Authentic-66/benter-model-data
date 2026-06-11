"""
db_migrate.py -- Build benter_model.db from existing results-logs, picks, and roi-logs.

Usage:
    py scripts/db_migrate.py           # build (skips existing data)
    py scripts/db_migrate.py --force   # drop and rebuild from scratch
"""

import re, sys, sqlite3
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

SCRIPTS  = Path(__file__).parent
DB_PATH  = SCRIPTS / 'benter_model.db'
LOGS_DIR = SCRIPTS / 'results-logs'
ROI_DIR  = SCRIPTS / 'roi-logs'
FORCE    = '--force' in sys.argv

# ── Schema ────────────────────────────────────────────────────────────────────

DDL = """
CREATE TABLE IF NOT EXISTS races (
    race_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    track      TEXT    NOT NULL,
    race_date  TEXT    NOT NULL,
    race_num   INTEGER NOT NULL,
    surface    TEXT,
    conditions TEXT,
    purse      REAL,
    UNIQUE(track, race_date, race_num)
);
CREATE TABLE IF NOT EXISTS results (
    result_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id    INTEGER NOT NULL REFERENCES races(race_id),
    finish_pos INTEGER,
    horse_name TEXT,
    trainer    TEXT,
    jockey     TEXT,
    sire       TEXT,
    odds       REAL,
    win_pay    REAL,
    place_pay  REAL,
    show_pay   REAL
);
CREATE TABLE IF NOT EXISTS picks (
    pick_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    track           TEXT,
    race_date       TEXT,
    race_num        INTEGER,
    race_id         INTEGER REFERENCES races(race_id),
    horse_name      TEXT,
    signal_type     TEXT,
    bets            TEXT,
    ml_odds         REAL,
    pp_power        REAL,
    win_prob        REAL,
    ev_ratio        REAL,
    kelly_bet       REAL,
    trainer_name    TEXT,
    trainer_exempt  INTEGER DEFAULT 0,
    filtered_reason TEXT,
    UNIQUE(track, race_date, race_num, horse_name)
);
CREATE TABLE IF NOT EXISTS roi_entries (
    roi_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    pick_id    INTEGER REFERENCES picks(pick_id),
    race_id    INTEGER REFERENCES races(race_id),
    track      TEXT,
    race_date  TEXT,
    race_num   INTEGER,
    horse_name TEXT,
    finish_pos INTEGER,
    invested   REAL,
    returned   REAL,
    pl         REAL,
    note       TEXT
);
CREATE TABLE IF NOT EXISTS entries (
    entry_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id       INTEGER REFERENCES races(race_id),
    track         TEXT NOT NULL,
    race_date     TEXT NOT NULL,
    race_num      INTEGER NOT NULL,
    post_pos      INTEGER,
    horse_name    TEXT NOT NULL,
    ml_odds       REAL,
    prime_power   REAL,
    pp_rank       INTEGER,
    trainer       TEXT,
    jockey        TEXT,
    sire          TEXT,
    days_off      INTEGER,
    claim_price   REAL,
    best_spd      INTEGER,
    best_spd_turf INTEGER,
    best_spd_aw   INTEGER,
    recent_spd    TEXT,
    improving     INTEGER,
    jt_zero       INTEGER,
    signal_types  TEXT,
    is_pick       INTEGER DEFAULT 0,
    UNIQUE(track, race_date, race_num, horse_name)
);
CREATE TABLE IF NOT EXISTS signals (
    signal_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    track        TEXT NOT NULL,
    signal_type  TEXT NOT NULL,
    entity_name  TEXT NOT NULL,
    entity_type  TEXT,
    wins         INTEGER,
    win_pct      REAL,
    sire_impact  REAL,
    updated_date TEXT,
    UNIQUE(track, signal_type, entity_name)
);
CREATE INDEX IF NOT EXISTS idx_races_track_date ON races(track, race_date);
CREATE INDEX IF NOT EXISTS idx_results_race_id  ON results(race_id);
CREATE INDEX IF NOT EXISTS idx_picks_race_id    ON picks(race_id);
CREATE INDEX IF NOT EXISTS idx_roi_race_id      ON roi_entries(race_id);
CREATE INDEX IF NOT EXISTS idx_entries_race_id  ON entries(race_id);
"""


def ensure_prob_columns(conn):
    """Add Phase 6 probability columns to an existing picks table."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(picks)")}
    for col in ('win_prob', 'ev_ratio', 'kelly_bet'):
        if col not in existing:
            conn.execute(f"ALTER TABLE picks ADD COLUMN {col} REAL")
            print(f"  schema: added picks.{col}")
    conn.commit()


def ensure_results_unique(conn):
    """Remove duplicate results (keep lowest result_id), then enforce
    uniqueness — one row per horse per race."""
    cur = conn.execute(
        "DELETE FROM results WHERE result_id NOT IN ("
        " SELECT MIN(result_id) FROM results GROUP BY race_id, horse_name)"
    )
    if cur.rowcount:
        print(f"  schema: removed {cur.rowcount} duplicate results")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_results_unique"
        " ON results(race_id, horse_name)"
    )
    conn.commit()


def ensure_roi_unique(conn):
    """Remove duplicate roi_entries (keep lowest roi_id), then enforce
    uniqueness so re-running the migration can never duplicate ROI rows."""
    cur = conn.execute(
        "DELETE FROM roi_entries WHERE roi_id NOT IN ("
        " SELECT MIN(roi_id) FROM roi_entries"
        " GROUP BY track, race_date, race_num, horse_name)"
    )
    if cur.rowcount:
        print(f"  schema: removed {cur.rowcount} duplicate roi_entries")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_roi_unique"
        " ON roi_entries(track, race_date, race_num, horse_name)"
    )
    conn.commit()

# ── Results log parsing ───────────────────────────────────────────────────────

_LOG_NAME_RE    = re.compile(r'RESULTS_([A-Z]+)_(\d{8})\.txt', re.IGNORECASE)
_RACE_HDR_RE    = re.compile(r'\bRACE\s+(\d+)\b.*[|]')
_RACE_META_RE   = re.compile(r'\bRACE\s+\d+\b[^\|]*[—\-]+\s*(.*)')
_FINISHER_RE    = re.compile(r'^\s{2,6}(\d+)\s+\d+\s+(\S+)\s+([\d.]+)\s*$')
_TRAINER_RE     = re.compile(r'^\s+Trainer\s*:\s*(.+)')
_SIRE_RE        = re.compile(r'^\s+Sire\s*:\s*(.+)')
_WIN_RE         = re.compile(r'\bWIN\s+\$([\d.]+)')
_PLC_RE         = re.compile(r'\bPLC\s+\$([\d.]+)')
_SHW_RE         = re.compile(r'\bSHW\s+\$([\d.]+)')


def _purse(s):
    try:
        return float(re.sub(r'[^\d.]', '', s)) if s and re.search(r'\d', s) else None
    except (ValueError, TypeError):
        return None


def _parse_results_log(path):
    """Returns (date_str 'YYYY-MM-DD', track, [race_dicts])."""
    m = _LOG_NAME_RE.match(path.name)
    if not m:
        return None, None, []
    track    = m.group(1).upper()
    raw      = m.group(2)
    date_str = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"

    lines  = path.read_text(encoding='utf-8', errors='replace').splitlines()
    races  = {}
    cur    = None

    for line in lines:
        # Race header must have a pipe separator (meta columns)
        if _RACE_HDR_RE.search(line):
            hm = re.search(r'\bRACE\s+(\d+)\b', line)
            rnum = int(hm.group(1))
            mm = _RACE_META_RE.search(line)
            parts = [p.strip() for p in mm.group(1).split('|')] if mm else []
            cur = {
                'race_num':   rnum,
                'conditions': parts[0] if parts else '',
                'surface':    parts[2] if len(parts) > 2 else 'Dirt',
                'purse':      _purse(parts[3]) if len(parts) > 3 else None,
                'finishers':  [],
                'trainer': None, 'sire': None,
                'win': None, 'place': None, 'show': None,
            }
            races[rnum] = cur
            continue

        if cur is None:
            continue

        fm = _FINISHER_RE.match(line)
        if fm:
            cur['finishers'].append({
                'pos':   int(fm.group(1)),
                'horse': fm.group(2),
                'odds':  float(fm.group(3)),
            })
            continue

        tm = _TRAINER_RE.match(line)
        if tm:
            cur['trainer'] = tm.group(1).strip()
            continue
        sm = _SIRE_RE.match(line)
        if sm:
            cur['sire'] = sm.group(1).strip()
            continue

        if wm := _WIN_RE.search(line):
            cur['win'] = float(wm.group(1))
        if pm := _PLC_RE.search(line):
            cur['place'] = float(pm.group(1))
        if shm := _SHW_RE.search(line):
            cur['show'] = float(shm.group(1))

    return date_str, track, list(races.values())


def import_results(conn):
    cur = conn.cursor()
    n_races = n_results = 0

    for lf in sorted(LOGS_DIR.glob('RESULTS_*.txt')):
        date_str, track, races = _parse_results_log(lf)
        if not date_str:
            continue
        for r in races:
            cur.execute(
                "INSERT OR IGNORE INTO races(track,race_date,race_num,surface,conditions,purse)"
                " VALUES(?,?,?,?,?,?)",
                (track, date_str, r['race_num'], r['surface'], r['conditions'], r['purse'])
            )
            # Capture before the SELECT below resets rowcount to -1 (truthy!)
            race_inserted = bool(cur.rowcount)
            if race_inserted:
                n_races += 1
            cur.execute(
                "SELECT race_id FROM races WHERE track=? AND race_date=? AND race_num=?",
                (track, date_str, r['race_num'])
            )
            race_id = cur.fetchone()[0]

            # Only insert finishers for newly added races
            if race_inserted or not list(cur.execute("SELECT 1 FROM results WHERE race_id=? LIMIT 1", (race_id,))):
                for f in r['finishers']:
                    is_win = f['pos'] == 1
                    cur.execute(
                        "INSERT OR IGNORE INTO results"
                        "(race_id,finish_pos,horse_name,trainer,sire,odds,win_pay,place_pay,show_pay)"
                        " VALUES(?,?,?,?,?,?,?,?,?)",
                        (race_id, f['pos'], f['horse'],
                         r['trainer'] if is_win else None,
                         r['sire']    if is_win else None,
                         f['odds'],
                         r['win']   if f['pos'] == 1 else None,
                         r['place'] if f['pos'] <= 2 else None,
                         r['show']  if f['pos'] <= 3 else None)
                    )
                    if cur.rowcount:
                        n_results += 1

    conn.commit()
    return n_races, n_results


# ── Picks parsing ─────────────────────────────────────────────────────────────

_PICKS_DATE_RE = re.compile(r'picks_([A-Z]+)_(\d{8})\.txt', re.IGNORECASE)
_PICKS_CODE_RE = re.compile(r'picks_([A-Z]+)_[A-Za-z]*(\d{4})[A-Za-z]*\.txt', re.IGNORECASE)


def _picks_date(path):
    """Returns (track, 'YYYY-MM-DD') or (track, None) if date can't be parsed."""
    m = _PICKS_DATE_RE.match(path.name)
    if m:
        raw = m.group(2)   # MMDDYYYY
        return m.group(1).upper(), f"{raw[4:8]}-{raw[0:2]}-{raw[2:4]}"
    m2 = _PICKS_CODE_RE.match(path.name)
    if m2:
        mmdd = m2.group(2)
        return m2.group(1).upper(), f"2026-{mmdd[:2]}-{mmdd[2:4]}"
    return None, None


def import_picks(conn):
    cur = conn.cursor()
    n_picks = 0

    for pf in sorted(SCRIPTS.glob('picks_*.txt')):
        track, date_str = _picks_date(pf)
        if not track:
            continue
        for raw in pf.read_text(encoding='utf-8', errors='replace').splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            p_track  = parts[0].upper()
            p_race   = int(re.sub(r'\D', '', parts[1]))
            p_horse  = parts[2]
            p_signal = parts[3].upper()
            bets     = parts[4].upper() if len(parts) >= 5 else 'WPS'
            # Validate bets field (some files omit it; old format is 4 fields)
            if not all(b in 'WPS' for b in bets):
                bets = 'WPS'
            try:    ml_odds  = float(parts[5]) if len(parts) >= 6 else None
            except: ml_odds  = None
            try:    pp_power = float(parts[6]) if len(parts) >= 7 else None
            except: pp_power = None
            trainer_name = parts[7].replace('_', ' ') if len(parts) >= 8 else None
            # Phase 6 optional probability columns (added by prob_predict.py --in-place)
            try:    win_prob = float(parts[8]) if len(parts) >= 9 else None
            except: win_prob = None
            try:    ev_ratio = float(parts[9]) if len(parts) >= 10 else None
            except: ev_ratio = None

            cur.execute(
                "SELECT race_id FROM races WHERE track=? AND race_date=? AND race_num=?",
                (p_track, date_str, p_race)
            )
            row     = cur.fetchone()
            race_id = row[0] if row else None

            cur.execute(
                "INSERT OR IGNORE INTO picks"
                "(track,race_date,race_num,race_id,horse_name,signal_type,bets,"
                "ml_odds,pp_power,win_prob,ev_ratio,trainer_name)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (p_track, date_str, p_race, race_id, p_horse, p_signal, bets,
                 ml_odds, pp_power, win_prob, ev_ratio, trainer_name)
            )
            if cur.rowcount:
                n_picks += 1
            elif win_prob is not None:
                # Pick imported before its file was annotated (or re-annotated
                # after a model fix) — sync probs from the file
                cur.execute(
                    "UPDATE picks SET win_prob=?, ev_ratio=?"
                    " WHERE track=? AND race_date=? AND race_num=? AND horse_name=?",
                    (win_prob, ev_ratio, p_track, date_str, p_race, p_horse)
                )

    conn.commit()
    return n_picks


# ── ROI log parsing ───────────────────────────────────────────────────────────

_KNOWN_CODES    = {'CT', 'FP', 'GP', 'EVD', 'DD', 'FG', 'MVR', 'LRL', 'ST', 'HV', 'HK'}
_SECTION_RE     = re.compile(r'\(([A-Z]{2,4})\)\s*$')
_PICKS_REF_RE   = re.compile(r'Picks:\s*picks_[A-Z]+_(\d{8})\.txt', re.IGNORECASE)
_ROI_ACTIVE_RE  = re.compile(
    r'^\s+R(\d+)\s+'
    r"([\w'./-]+)\s+"
    r'([A-Z_]+)\s+'
    r'([WPS]+)\s+'
    r'(\d+|[?])\s+'
    r'\$([\d.]+)\s+'
    r'\$\s*([\d.]+)\s+'
    r'([+\-]\$[\d.]+)'
    r'(?:\s+\[([^\]]+)\])?'
)
_ROI_FILTERED_RE = re.compile(
    r'^\s+R(\d+)\s+'
    r"([\w'./-]+)\s+"
    r'([A-Z_]+)\s+'
    r'[^\[]*\[([^\]]+)\]'
)


def _parse_roi_log(path):
    """Yields (track, date_str, entry_dict) for each scored or filtered pick row."""
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    current_track = None
    current_date  = None

    for line in lines:
        # Section header: "  CHARLES TOWN (CT)"
        sm = _SECTION_RE.search(line)
        if sm and sm.group(1) in _KNOWN_CODES:
            current_track = sm.group(1)
            current_date  = None
            continue

        # Picks file reference sets the race date for this section
        pm = _PICKS_REF_RE.search(line)
        if pm:
            raw = pm.group(1)   # MMDDYYYY
            current_date = f"{raw[4:8]}-{raw[0:2]}-{raw[2:4]}"
            continue

        if current_track is None or current_date is None:
            continue

        am = _ROI_ACTIVE_RE.match(line)
        if am:
            pl_str = am.group(8)
            pl_val = float(re.sub(r'[^\d.]', '', pl_str))
            if pl_str.startswith('-'):
                pl_val = -pl_val
            fin_raw = am.group(5)
            yield current_track, current_date, {
                'race_num': int(am.group(1)),
                'horse':    am.group(2),
                'fin':      int(fin_raw) if fin_raw.isdigit() else None,
                'invested': float(am.group(6)),
                'returned': float(am.group(7)),
                'pl':       pl_val,
                'note':     am.group(9) or '',
                'filtered': False,
            }
            continue

        fm = _ROI_FILTERED_RE.match(line)
        if fm:
            yield current_track, current_date, {
                'race_num': int(fm.group(1)),
                'horse':    fm.group(2),
                'fin':      None,
                'invested': 0.0,
                'returned': 0.0,
                'pl':       0.0,
                'note':     fm.group(4),
                'filtered': True,
            }


def import_roi(conn):
    cur    = conn.cursor()
    n_roi  = 0
    done   = set()   # (track, date_str) combos already inserted

    # Newest file first; first file wins for any (track, date) combo
    for rf in sorted(ROI_DIR.glob('ROI_ALL_*.txt'), reverse=True):
        by_combo = defaultdict(list)
        for track, date_str, entry in _parse_roi_log(rf):
            by_combo[(track, date_str)].append(entry)

        for combo, entries in by_combo.items():
            if combo in done:
                continue
            done.add(combo)
            track, date_str = combo

            for e in entries:
                cur.execute(
                    "SELECT race_id FROM races WHERE track=? AND race_date=? AND race_num=?",
                    (track, date_str, e['race_num'])
                )
                row     = cur.fetchone()
                race_id = row[0] if row else None

                cur.execute(
                    "SELECT pick_id FROM picks"
                    " WHERE track=? AND race_date=? AND race_num=? AND horse_name=?",
                    (track, date_str, e['race_num'], e['horse'])
                )
                row     = cur.fetchone()
                pick_id = row[0] if row else None

                # idx_roi_unique makes re-runs and repeated log sections no-ops
                cur.execute(
                    "INSERT OR IGNORE INTO roi_entries"
                    "(pick_id,race_id,track,race_date,race_num,horse_name,"
                    "finish_pos,invested,returned,pl,note)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (pick_id, race_id, track, date_str, e['race_num'], e['horse'],
                     e['fin'], e['invested'], e['returned'], e['pl'], e['note'])
                )
                if cur.rowcount:
                    n_roi += 1

    conn.commit()
    return n_roi


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if FORCE and DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Dropped existing database.")

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(DDL)
    conn.commit()
    ensure_prob_columns(conn)
    ensure_results_unique(conn)
    ensure_roi_unique(conn)
    print(f"Database: {DB_PATH}\n")

    print("Importing results logs...")
    n_races, n_results = import_results(conn)
    print(f"  {n_races} races, {n_results} finishers")

    print("Importing picks files...")
    n_picks = import_picks(conn)
    print(f"  {n_picks} picks")

    print("Importing ROI logs...")
    n_roi = import_roi(conn)
    print(f"  {n_roi} ROI entries")

    # Summary
    cur = conn.cursor()
    cur.execute("SELECT track, MIN(race_date), MAX(race_date), COUNT(DISTINCT race_date) FROM races GROUP BY track ORDER BY track")
    rows = cur.fetchall()
    cur.execute("SELECT MIN(race_date), MAX(race_date) FROM races")
    date_range = cur.fetchone()

    print(f"\n{'='*56}")
    print(f"  Imported: {n_races} races, {n_results} results, {n_picks} picks, {n_roi} roi entries")
    print(f"  Date range: {date_range[0]} to {date_range[1]}")
    print(f"  Tracks:")
    for track, min_d, max_d, n_days in rows:
        print(f"    {track:<5}  {n_days:>3} race days  ({min_d} to {max_d})")
    print(f"{'='*56}\n")

    conn.close()


if __name__ == '__main__':
    main()
