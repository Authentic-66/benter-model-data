"""
Backfill ML_ODDS, PP_POWER, and TRAINER into picks files that only have the
old format (fewer than 8 fields).

Old format (4-5 fields): TRACK RACE HORSE SIGNAL [BETS]
New format (8 fields):   TRACK RACE HORSE SIGNAL BETS ML_ODDS PP_POWER TRAINER

For each picks file, finds the corresponding handicap card log in
scripts/handicap-logs/ and extracts ML, PP Power, and trainer name for
each pick.

Usage: python backfill_picks.py [--dry-run]
"""

import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

SCRIPTS  = Path(__file__).parent
HCAP_DIR = SCRIPTS / 'handicap-logs'
DRY_RUN  = '--dry-run' in sys.argv

# Matches horse rows in a full handicap card:
#   {optional_flag} {pp:>2}: {name:<27}{ml:>5}  {pp_str:>10}  {trainer}
# The ⭐/· flag is a single non-space char; without it the prefix is all spaces.
_HORSE_ROW_RE = re.compile(
    r'^\s*\S?\s+(\d+):\s+'          # skip optional flag, capture PP#
    r'(.+?)\s{2,}'                  # horse name, lazy stop at 2+ spaces
    r'([0-9]+(?:/[0-9]+)?|\?)\s+'  # ML odds (integer, fraction, or ?)
    r'([0-9]+\.[0-9]+\(\d+\)|\?)'  # PP power "NNN.N(rank)" or ?
    r'\s{2,}(.+?)\s*$'             # trainer name
)

_RACE_HDR_RE = re.compile(r'^RACE\s+(\d+)\b')


def _ml_to_float(s):
    """'8/5' → 2.6, '5' → 6.0, '?' → None"""
    if not s or s == '?':
        return None
    if '/' in s:
        try:
            n, d = s.split('/')
            return round(int(n) / int(d) + 1, 2)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return round(float(s) + 1, 2)
    except ValueError:
        return None


def _load_card(hcap_path):
    """
    Parse a full handicap card and return:
      {race_num: {norm_horse_name: {'ml': float|None, 'pp': float|None}}}
    Returns empty dict if the log is the short picks-only format.
    """
    data = {}
    cur_race = None

    for line in hcap_path.read_text(encoding='utf-8', errors='replace').splitlines():
        m = _RACE_HDR_RE.match(line.strip())
        if m:
            cur_race = int(m.group(1))
            data.setdefault(cur_race, {})
            continue

        if cur_race is None:
            continue

        hm = _HORSE_ROW_RE.match(line)
        if not hm:
            continue

        _, horse_raw, ml_raw, pp_raw, trainer_raw = hm.groups()
        norm = horse_raw.strip().replace(' ', '').lower()

        ml_val = _ml_to_float(ml_raw)
        pp_val = None
        if pp_raw != '?':
            try:
                pp_val = float(pp_raw.split('(')[0])
            except ValueError:
                pass
        trainer_val = trainer_raw.strip().replace(' ', '_') if trainer_raw.strip() not in ('', '?') else '?'

        data[cur_race][norm] = {'ml': ml_val, 'pp': pp_val, 'trainer': trainer_val}

    return data


def _picks_to_hcap(picks_path):
    """
    Map picks_TRACK_MMDDYYYY.txt → (track, handicap_path|None).
    Also handles picks_TRACK_CODEDATE.txt fallbacks.
    """
    name = picks_path.name

    # Standard: picks_TRACK_MMDDYYYY.txt
    m = re.match(r'picks_([A-Za-z]+)_(\d{2})(\d{2})(\d{4})\.txt', name, re.IGNORECASE)
    if m:
        track = m.group(1).upper()
        mm, dd, yyyy = m.group(2), m.group(3), m.group(4)
        hcap_name = f'HANDICAP_{track}_{yyyy}{mm}{dd}.txt'
        p = HCAP_DIR / hcap_name
        return track, (p if p.exists() else None)

    # Fallback: pick out 4-digit year + preceding 4 digits as MMDD
    # e.g. picks_FP_FPK0519Y.txt → search for any 4-digit run adjacent to year
    m2 = re.match(r'picks_([A-Za-z]+)_[A-Za-z]*(\d{2})(\d{2})[A-Za-z]*\.txt', name, re.IGNORECASE)
    if m2:
        track = m2.group(1).upper()
        mm, dd = m2.group(2), m2.group(3)
        # Try both plausible years for non-standard names
        for yyyy in ('2026', '2025'):
            hcap_name = f'HANDICAP_{track}_{yyyy}{mm}{dd}.txt'
            p = HCAP_DIR / hcap_name
            if p.exists():
                return track, p
        return track, None

    return None, None


def _process(picks_path):
    """
    Returns (updated_lines, n_backfilled, n_question) or (None, 0, 0) if nothing to do.
    n_backfilled: lines where at least one of ML/PP was resolved from the card.
    n_question:   lines where both stayed as ?.
    """
    track, hcap_path = _picks_to_hcap(picks_path)
    if not track:
        return None, 0, 0

    card = _load_card(hcap_path) if hcap_path else {}

    lines = picks_path.read_text(encoding='utf-8', errors='replace').splitlines()
    out = []
    n_backfilled = 0
    n_question   = 0
    changed      = False

    for line in lines:
        stripped = line.strip()

        # Preserve blank lines and comments (update format comment if needed)
        if not stripped:
            out.append(line)
            continue
        if stripped.startswith('#'):
            if stripped.startswith('# Format:') and 'TRAINER' not in stripped:
                out.append('# Format: TRACK RACE HORSE SIGNAL BETS ML_ODDS PP_POWER TRAINER')
                changed = True
            else:
                out.append(line)
            continue

        parts = stripped.split()
        if len(parts) < 4:
            out.append(line)
            continue

        # Already fully backfilled (8 fields) — leave it alone
        if len(parts) >= 8:
            out.append(line)
            continue

        p_track  = parts[0].upper()
        p_race   = int(re.sub(r'\D', '', parts[1]))
        p_horse  = parts[2]
        p_signal = parts[3].upper()
        bets     = parts[4].upper() if len(parts) >= 5 else 'WPS'
        if not all(b in 'WPS' for b in bets):
            bets = 'WPS'
        # Preserve existing ML/PP if present (7-field lines only need trainer added)
        ml_col = parts[5] if len(parts) >= 6 else None
        pp_col = parts[6] if len(parts) >= 7 else None

        norm = p_horse.lower()
        horse_data = card.get(p_race, {}).get(norm, {})

        if ml_col is None:
            ml_val = horse_data.get('ml')
            ml_col = str(ml_val) if ml_val is not None else '?'
        if pp_col is None:
            pp_val = horse_data.get('pp')
            pp_col = str(pp_val) if pp_val is not None else '?'
        trainer_val = horse_data.get('trainer')
        trainer_col = trainer_val if trainer_val else '?'

        if ml_col != '?' or pp_col != '?':
            n_backfilled += 1
        else:
            n_question += 1

        out.append(f"{p_track} {p_race} {p_horse} {p_signal} {bets} {ml_col} {pp_col} {trainer_col}")
        changed = True

    return (out if changed else None), n_backfilled, n_question


def main():
    picks_files = sorted(SCRIPTS.glob('picks_*.txt'))
    total_files      = 0
    total_backfilled = 0
    total_question   = 0

    for pf in picks_files:
        updated_lines, n_bf, n_q = _process(pf)
        if updated_lines is None:
            continue

        if not DRY_RUN:
            pf.write_text('\n'.join(updated_lines) + '\n', encoding='utf-8')

        total_files      += 1
        total_backfilled += n_bf
        total_question   += n_q

        status = 'dry-run' if DRY_RUN else 'updated'
        print(f"  {pf.name}  [{status}]  {n_bf} backfilled  {n_q} left as ?")

    print()
    print(f"{'(dry-run) ' if DRY_RUN else ''}"
          f"{total_files} picks file(s) updated, "
          f"{total_backfilled} field(s) backfilled, "
          f"{total_question} pick(s) left as ?")


if __name__ == '__main__':
    main()
