"""One-off diagnostic: aggregate +EV picks across 5 out-of-sample dates and
break down model edge vs noise by track / EV bin / final-odds bin.

Reads picks files from handicap-logs/ and matches against result PDFs in each
track's results folder. No model changes — pure post-hoc analysis.
"""

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from process_results import extract_text, parse_results
from roi_tracker import find_finisher, to_float

REPO = SCRIPT_DIR.parent

# (track, picks_file, result_pdf, label_date)
JOBS = [
    ('GP',  SCRIPT_DIR / 'handicap-logs' / 'picks_GP_06142026.txt',
            REPO / 'Gulfstream Park' / 'gp-results-2026' / 'GP061426USA.pdf', '6/14 Sat'),
    ('SA',  SCRIPT_DIR / 'handicap-logs' / 'picks_SA_06142026.txt',
            REPO / 'Santa Anita' / 'sa-results-2026' / 'SA061426USA.pdf', '6/14 Sat'),
    ('SA',  SCRIPT_DIR / 'handicap-logs' / 'picks_SA_06152026.txt',
            REPO / 'Santa Anita' / 'sa-results-2026' / 'SA061526USA.pdf', '6/15 Sun'),
    ('FP',  SCRIPT_DIR / 'handicap-logs' / 'picks_FP_06162026.txt',
            REPO / 'Fairmount Park' / 'fp-results-2026' / 'FP061626USA.pdf', '6/16 Mon'),
    ('CT',  SCRIPT_DIR / 'handicap-logs' / 'picks_CT_06182026.txt',
            REPO / 'CharlesTown' / 'ct-results-2026' / 'CT061826USA.pdf', '6/18 Thu'),
    ('EVD', SCRIPT_DIR / 'handicap-logs' / 'picks_EVD_06182026.txt',
            REPO / 'Evangeline Downs' / 'evd-results-2026' / 'EVD061826USA.pdf', '6/18 Thu'),
    ('CT',  SCRIPT_DIR / 'handicap-logs' / 'picks_CT_06192026.txt',
            REPO / 'CharlesTown' / 'ct-results-2026' / 'CT061926USA.pdf', '6/19 Fri'),
    ('GP',  SCRIPT_DIR / 'handicap-logs' / 'picks_GP_06192026.txt',
            REPO / 'Gulfstream Park' / 'gp-results-2026' / 'GP061926USA.pdf', '6/19 Fri'),
]

EV_THRESHOLD = 1.10  # +EV picks per user spec


def _f(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return None


def load_picks(path):
    picks = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 10:
                continue
            picks.append({
                'track': parts[0].upper(),
                'race': int(re.sub(r'\D', '', parts[1])),
                'horse': parts[2],
                'ml_odds': _f(parts[5]),
                'win_prob': _f(parts[8]),
                'ev_ratio': _f(parts[9]),
            })
    return picks


def load_result(pdf_path):
    return parse_results(extract_text(str(pdf_path)))


def ev_bin(ev):
    if ev < 1.10:
        return None
    if ev < 1.30:
        return '1.10–1.30'
    if ev < 1.50:
        return '1.30–1.50'
    return '1.50+'


def odds_bin(odds):
    if odds is None:
        return 'unknown'
    if odds < 3.0:    # < 2/1
        return 'favorite (<3.0)'
    if odds < 6.0:    # 2/1 – 5/1
        return 'midprice (3.0–6.0)'
    if odds < 12.0:   # 5/1 – 11/1
        return 'longshot (6.0–12.0)'
    return 'bomb (12.0+)'


def main():
    rows = []
    for track, picks_path, pdf_path, date_label in JOBS:
        if not picks_path.exists():
            print(f"WARN missing picks: {picks_path}")
            continue
        if not pdf_path.exists():
            print(f"WARN missing pdf: {pdf_path}")
            continue
        picks = load_picks(picks_path)
        races = load_result(pdf_path)
        for p in picks:
            if p['ev_ratio'] is None or p['ev_ratio'] < EV_THRESHOLD:
                continue
            race = races.get(p['race'])
            if race is None:
                continue
            fin = find_finisher(p['horse'], race['finishers'])
            if fin is None:
                continue
            try:
                final_odds = float(fin['odds'])
            except (ValueError, TypeError):
                final_odds = None
            pos = fin['pos']
            invested = 6.0  # WPS = $2 * 3
            ret = 0.0
            if pos == 1:
                ret += to_float(race['win'])
            if pos <= 2:
                ret += to_float(race['place'])
            if pos <= 3:
                ret += to_float(race['show'])
            rows.append({
                'date': date_label,
                'track': track,
                'race': p['race'],
                'horse': p['horse'],
                'ml_odds': p['ml_odds'],
                'final_odds': final_odds,
                'win_prob': p['win_prob'],
                'ev_ratio': p['ev_ratio'],
                'pos': pos,
                'invested': invested,
                'returned': ret,
                'won': pos == 1,
            })

    if not rows:
        print("NO +EV picks matched. Aborting.")
        return

    # ── overall totals ───────────────────────────────────────────────────
    n = len(rows)
    n_wins = sum(1 for r in rows if r['won'])
    pred_wins = sum(r['win_prob'] for r in rows)
    inv = sum(r['invested'] for r in rows)
    ret = sum(r['returned'] for r in rows)
    pred_roi_ratio = sum(r['ev_ratio'] for r in rows) / n  # avg EV_RATIO
    actual_roi = (ret - inv) / inv

    print("=" * 78)
    print(f"  COMBINED +EV DIAGNOSTIC — {len(JOBS)} cards, EV_RATIO >= {EV_THRESHOLD}")
    print("=" * 78)
    print(f"  Bets matched:     {n}")
    print(f"  Win rate:         {n_wins}/{n} = {n_wins/n:.1%}   "
          f"(model predicted {pred_wins:.1f} wins = {pred_wins/n:.1%})")
    print(f"  Win-prob delta:   actual − predicted = "
          f"{(n_wins/n) - (pred_wins/n):+.1%}")
    print(f"  WPS ROI:          ${inv:.0f} in / ${ret:.2f} out = {actual_roi:+.1%}")
    print(f"  Avg EV_RATIO:     {pred_roi_ratio:.3f}   "
          f"(model expects ~{pred_roi_ratio-1:+.1%} return on win bets)")
    print()

    def _block(title, key_fn, sort_key=None):
        groups = defaultdict(list)
        for r in rows:
            k = key_fn(r)
            if k is None:
                continue
            groups[k].append(r)
        print(f"── BREAKDOWN BY {title} {'─' * (40 - len(title))}")
        print(f"  {'group':<24} {'N':>4} {'Wins':>5} {'Win%':>7} "
              f"{'PredW%':>8} {'Δ':>7} {'Inv':>7} {'Ret':>8} {'ROI':>8}")
        print("  " + "·" * 80)
        keys = sorted(groups.keys(), key=sort_key) if sort_key else sorted(groups.keys())
        for k in keys:
            grp = groups[k]
            gn = len(grp)
            gw = sum(1 for r in grp if r['won'])
            gpw = sum(r['win_prob'] for r in grp) / gn
            gi = sum(r['invested'] for r in grp)
            gr = sum(r['returned'] for r in grp)
            groi = (gr - gi) / gi if gi else 0
            delta = (gw/gn) - gpw
            print(f"  {str(k):<24} {gn:>4} {gw:>5} {gw/gn:>6.1%} "
                  f"{gpw:>7.1%} {delta:>+7.1%} ${gi:>5.0f} ${gr:>7.2f} {groi:>+7.1%}")
        print()

    _block('TRACK', lambda r: r['track'])
    _block('DATE',  lambda r: r['date'],
           sort_key=lambda k: (k.split()[0]))
    _block('EV BIN',
           lambda r: ev_bin(r['ev_ratio']),
           sort_key=lambda k: ('1.10' in k, '1.30' in k, '1.50' in k))
    _block('FINAL-ODDS BIN', lambda r: odds_bin(r['final_odds']),
           sort_key=lambda k: ('favorite' not in k,
                               'midprice' not in k,
                               'longshot' not in k,
                               'bomb' not in k))

    # ── joint EV x odds heatmap ──────────────────────────────────────────
    print("── JOINT (EV BIN × FINAL ODDS BIN) — ROI ───────────────────────────")
    cells = defaultdict(list)
    for r in rows:
        eb = ev_bin(r['ev_ratio'])
        ob = odds_bin(r['final_odds'])
        if eb and ob != 'unknown':
            cells[(eb, ob)].append(r)
    evs = ['1.10–1.30', '1.30–1.50', '1.50+']
    obs_order = ['favorite (<3.0)', 'midprice (3.0–6.0)',
                 'longshot (6.0–12.0)', 'bomb (12.0+)']
    header = f"  {'EV \\ ODDS':<14}" + ''.join(f"{ob:>22}" for ob in obs_order)
    print(header)
    for eb in evs:
        line = f"  {eb:<14}"
        for ob in obs_order:
            grp = cells.get((eb, ob), [])
            if not grp:
                line += f"{'—':>22}"
                continue
            gi = sum(r['invested'] for r in grp)
            gr = sum(r['returned'] for r in grp)
            roi = (gr - gi) / gi if gi else 0
            line += f"  n={len(grp):<2} ROI={roi:>+6.1%}".rjust(22)
        print(line)
    print()

    # ── per-bet sanity dump (sorted by EV desc) ─────────────────────────
    print("── ALL +EV BETS (sorted by EV ratio descending) ────────────────────")
    print(f"  {'date':<10} {'trk':<4} {'R':>2} {'horse':<22} "
          f"{'ML':>5} {'Fin$':>6} {'p':>5} {'EV':>5} {'pos':>3} {'P/L':>7}")
    for r in sorted(rows, key=lambda x: -x['ev_ratio']):
        pl = r['returned'] - r['invested']
        fo = f"{r['final_odds']:.1f}" if r['final_odds'] is not None else '?'
        ml = f"{r['ml_odds']:.1f}" if r['ml_odds'] is not None else '?'
        print(f"  {r['date']:<10} {r['track']:<4} {r['race']:>2} "
              f"{r['horse'][:22]:<22} {ml:>5} {fo:>6} "
              f"{r['win_prob']:>5.2f} {r['ev_ratio']:>5.2f} "
              f"{r['pos']:>3} {pl:>+7.2f}")


if __name__ == '__main__':
    main()
