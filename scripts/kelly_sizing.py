"""Phase 5: Kelly criterion bet sizing from a probability-annotated picks file.

Usage:
    py kelly_sizing.py picks_FP_06092026.txt 100

Reads a 10-column picks file (cols 9-10 = WIN_PROB EV_RATIO, written by
prob_predict.py --in-place) and a bankroll, then sizes win bets:

    edge      = win_prob * decimal_odds - 1     (= EV_RATIO - 1)
    kelly     = edge / (decimal_odds - 1)
    full bet  = kelly * bankroll
    half bet  = full bet * 0.5                  (recommended)

Only positive-edge picks are recommended; any single bet is capped at
10% of bankroll. Recommended stakes are also written to picks.kelly_bet
in benter_model.db when the pick rows exist there.
"""

import os
import re
import sqlite3
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "benter_model.db")

KELLY_MULTIPLIER = 0.5   # half Kelly
MAX_BET_PCT = 0.10       # single-bet cap as fraction of bankroll

_FNAME_RE = re.compile(r"picks_([A-Z]+)_(\d{8})\.txt", re.IGNORECASE)


def _num(s):
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def parse_picks_file(path):
    picks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 8:
                continue
            picks.append({
                "track": parts[0].upper(),
                "race": int(re.sub(r"\D", "", parts[1])),
                "horse": parts[2],
                "signal": parts[3],
                "ml_odds": _num(parts[5]),
                "win_prob": _num(parts[8]) if len(parts) >= 9 else None,
                "ev_ratio": _num(parts[9]) if len(parts) >= 10 else None,
            })
    return picks


def size_bets(picks, bankroll):
    """Returns (recommended, n_negative, n_unsizable). Each recommended pick
    gains edge/kelly/full_bet/bet/capped keys; non-recommended sizable picks
    gain kelly_bet = 0.0 for DB storage."""
    recommended, n_negative, n_unsizable = [], 0, 0
    cap = MAX_BET_PCT * bankroll
    for p in picks:
        wp, odds = p["win_prob"], p["ml_odds"]
        if wp is None or odds is None or odds <= 1.0:
            p["kelly_bet"] = None
            n_unsizable += 1
            continue
        edge = wp * odds - 1.0
        if edge <= 0:
            p["kelly_bet"] = 0.0
            n_negative += 1
            continue
        kelly = edge / (odds - 1.0)
        full_bet = kelly * bankroll
        bet = min(full_bet * KELLY_MULTIPLIER, cap)
        p.update({
            "edge": edge, "kelly": kelly, "full_bet": full_bet,
            "bet": bet, "capped": full_bet * KELLY_MULTIPLIER > cap,
            "kelly_bet": round(bet, 2),
        })
        recommended.append(p)
    return recommended, n_negative, n_unsizable


def write_kelly_to_db(picks, picks_path):
    m = _FNAME_RE.match(os.path.basename(picks_path))
    if not m or not os.path.exists(DB_PATH):
        return 0
    raw = m.group(2)  # MMDDYYYY
    race_date = f"{raw[4:8]}-{raw[0:2]}-{raw[2:4]}"
    con = sqlite3.connect(DB_PATH)
    n = 0
    for p in picks:
        if p.get("kelly_bet") is None:
            continue
        cur = con.execute(
            "UPDATE picks SET kelly_bet=?"
            " WHERE track=? AND race_date=? AND race_num=? AND horse_name=?",
            (p["kelly_bet"], p["track"], race_date, p["race"], p["horse"]),
        )
        n += cur.rowcount
    con.commit()
    con.close()
    return n


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: py kelly_sizing.py <picks_file> <bankroll>")
    picks_path = sys.argv[1]
    try:
        bankroll = float(sys.argv[2])
    except ValueError:
        sys.exit(f"Invalid bankroll: {sys.argv[2]!r}")
    if bankroll <= 0:
        sys.exit("Bankroll must be positive.")

    picks = parse_picks_file(picks_path)
    if not picks:
        sys.exit(f"No pick rows found in {picks_path}")

    recommended, n_negative, n_unsizable = size_bets(picks, bankroll)
    recommended.sort(key=lambda p: -p["bet"])

    track = picks[0]["track"]
    print("=" * 70)
    print(f"PHASE 5 - KELLY BETTING TICKET   {track}   bankroll ${bankroll:,.2f}")
    print(f"Half Kelly ({KELLY_MULTIPLIER:.0%}), single-bet cap {MAX_BET_PCT:.0%} of bankroll")
    print("=" * 70)

    if recommended:
        hdr = (f"{'RACE':<5}{'HORSE':<22}{'ODDS':>6}{'WIN_PROB':>9}"
               f"{'EDGE':>8}{'EV_RATIO':>9}{'BET':>9}")
        print(hdr)
        print("-" * len(hdr))
        total = total_ev = 0.0
        for p in recommended:
            cap_tag = " (capped)" if p["capped"] else ""
            print(f"{p['race']:<5}{p['horse']:<22}{p['ml_odds']:>6.1f}"
                  f"{p['win_prob']:>9.3f}{p['edge']:>7.1%}{p['ev_ratio']:>9.2f}"
                  f"{p['bet']:>9.2f}{cap_tag}")
            total += p["bet"]
            total_ev += p["bet"] * p["edge"]
        print("-" * len(hdr))
        print(f"Bets recommended:   {len(recommended)}")
        print(f"Total staked:       ${total:.2f}  ({total / bankroll:.1%} of bankroll)")
        print(f"Ticket EV:          ${total_ev:+.2f}  ({total_ev / total:+.1%} per $ staked)")
    else:
        print("NO BETS — no positive-edge picks on this card.")
        print("(The model prices every pick at or below its ML-implied probability.)")

    print(f"\nSkipped: {n_negative} negative/zero edge, {n_unsizable} missing prob/odds data")

    n_db = write_kelly_to_db(picks, picks_path)
    if n_db:
        print(f"kelly_bet written to DB for {n_db} picks")


if __name__ == "__main__":
    main()
