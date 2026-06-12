"""Score a FULL race card with the conditional-logit model (Phase 6b).

Usage:
    py cl_predict.py <pp_file.pdf> [TRACK]          # parse + score a PP file
    py cl_predict.py --db <TRACK> <YYYY-MM-DD>      # score a card already in entries
    ... [--bankroll 100]                            # add half-Kelly stakes on +EV horses

Win probabilities come from softmax(beta . x) over every starter in each
race (they sum to 1 within the race). Overlay ratio = model_prob * ml_odds
(decimal), i.e. the expected return per $1 win bet at the morning line;
> 1.00 is a positive-EV overlay.
"""

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

CL_MODEL_PATH = SCRIPT_DIR / "benter_model_cl.pkl"
DB_PATH = SCRIPT_DIR / "benter_model.db"

KELLY_MULTIPLIER = 0.5
MAX_BET_PCT = 0.10

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def rows_from_pp(pp_file, track):
    import brisnet_parser_v2 as bp

    text = bp.extract_text(pp_file)
    races = bp.parse_brisnet(text, track)
    rows = []
    for rn, race in sorted(races.items()):
        for h in race["horses"]:
            try:
                pp_power = float(h["prime_power"])
            except (ValueError, TypeError):
                pp_power = None
            rows.append({
                "race_id": rn, "race_num": rn, "pp": h["pp"],
                "horse_name": h["name"].replace(" ", ""),
                "ml_odds": bp.ml_to_float(h["ml"]),
                "prime_power": pp_power,
                "signal_types": ",".join(s[0] for s in h["signals"]) or None,
                "improving": int(bool(h.get("improving"))),
                "jt_zero": int(bool(h.get("jt_zero"))),
                "days_off": h.get("days_off") or None,
                "best_spd": h.get("best_spd"),
                "jt_winpct": h.get("jt_winpct"),
                "beaten_lengths": h.get("beaten_len"),
                "class_delta": h.get("class_delta"),
            })
    return pd.DataFrame(rows)


def rows_from_db(track, race_date):
    import sqlite3

    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """SELECT race_num AS race_id, race_num, post_pos AS pp, horse_name,
                  ml_odds, prime_power, days_off, best_spd, jt_winpct,
                  beaten_lengths, class_delta, signal_types, improving, jt_zero
           FROM entries WHERE track = ? AND race_date = ?
           ORDER BY race_num, post_pos""",
        con, params=(track.upper(), race_date),
    )
    con.close()
    return df


def main():
    ap = argparse.ArgumentParser(description="Score a full card with the conditional-logit model")
    ap.add_argument("source", help="PP file path, or TRACK when using --db")
    ap.add_argument("arg2", nargs="?", help="TRACK for a PP file (default GP), or YYYY-MM-DD with --db")
    ap.add_argument("--db", action="store_true", help="read the card from the entries table")
    ap.add_argument("--bankroll", type=float, default=0,
                    help="if > 0, print half-Kelly stakes for +EV overlays")
    args = ap.parse_args()

    if not CL_MODEL_PATH.exists():
        sys.exit(f"Model not found at {CL_MODEL_PATH} - run prob_model.py first.")
    with open(CL_MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)
    beta, features, stds = bundle["beta"], bundle["features"], bundle["stds"]

    if args.db:
        if not args.arg2:
            sys.exit("Usage: py cl_predict.py --db <TRACK> <YYYY-MM-DD>")
        track, label = args.source.upper(), f"{args.source.upper()} {args.arg2} (from entries)"
        df = rows_from_db(track, args.arg2)
    else:
        track = (args.arg2 or "GP").upper()
        label = f"{track} {Path(args.source).name}"
        df = rows_from_pp(args.source, track)

    if df.empty:
        sys.exit("No starters found for this card.")

    # Display copy of ML before any imputation
    df["ml_display"] = df["ml_odds"]
    # Horses with no ML get a race-neutral value for the model only
    df["ml_odds"] = df.groupby("race_id")["ml_odds"].transform(lambda s: s.fillna(s.median()))
    df["ml_odds"] = df["ml_odds"].fillna(6.0)

    import prob_model as pm

    pm.build_cl_features(df, stds=stds)

    df["win_prob"] = np.nan
    for _, idx in df.groupby("race_id").groups.items():
        X = df.loc[idx, features].to_numpy(float)
        df.loc[idx, "win_prob"] = pm.cl_predict(X, beta)

    df["overlay"] = df["win_prob"] * df["ml_display"]   # expected $ back per $1 at ML
    df["edge"] = df["overlay"] - 1.0

    print("=" * 78)
    print(f"CONDITIONAL LOGIT CARD   {label}")
    print(f"model: {bundle['n_races']} races trained, CV log loss "
          f"{bundle['cv_race_log_loss']:.3f} (public ML {bundle['cv_race_log_loss_ml']:.3f})")
    print("=" * 78)

    n_ev = 0
    for rn, g in df.groupby("race_id"):
        g = g.sort_values("win_prob", ascending=False)
        print(f"\nRACE {rn}")
        hdr = (f"  {'PP':<4}{'HORSE':<24}{'ML':>6}{'MODEL':>8}"
               f"{'OVERLAY':>9}{'EDGE':>8}  SIGNALS")
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
        for _, r in g.iterrows():
            ml = f"{r['ml_display']:.1f}" if pd.notna(r["ml_display"]) else "?"
            if pd.notna(r["ml_display"]):
                ov, edge = f"{r['overlay']:.2f}", f"{r['edge']:+.0%}"
                flag = " +EV" if r["overlay"] > 1.0 else ("  ~ " if r["overlay"] >= 0.75 else "")
                n_ev += int(r["overlay"] > 1.0)
            else:
                ov, edge, flag = "?", "?", ""
            sig = r["signal_types"] if pd.notna(r["signal_types"]) else ""
            print(f"  {int(r['pp']) if pd.notna(r['pp']) else '?':<4}"
                  f"{r['horse_name']:<24}{ml:>6}{r['win_prob']:>8.3f}"
                  f"{ov:>9}{edge:>8}{flag}  {sig}")

    print(f"\nPositive-EV overlays at ML (overlay > 1.00): {n_ev}")
    print("NOTE: morning lines, not live odds - re-check overlays against the tote.")

    if args.bankroll > 0:
        bets = df[(df["edge"] > 0) & df["ml_display"].notna() & (df["ml_display"] > 1.0)].copy()
        print(f"\nHALF-KELLY TICKET  bankroll ${args.bankroll:,.2f} "
              f"(cap {MAX_BET_PCT:.0%}/bet)")
        if bets.empty:
            print("  NO BETS - no positive-edge overlays on this card.")
        else:
            cap = MAX_BET_PCT * args.bankroll
            bets["kelly"] = bets["edge"] / (bets["ml_display"] - 1.0)
            bets["bet"] = np.minimum(bets["kelly"] * args.bankroll * KELLY_MULTIPLIER, cap)
            bets = bets.sort_values("bet", ascending=False)
            total = ev = 0.0
            for _, r in bets.iterrows():
                print(f"  R{int(r['race_num'])} {r['horse_name']:<24}{r['ml_display']:>5.1f} "
                      f"p={r['win_prob']:.3f}  edge {r['edge']:+.0%}  bet ${r['bet']:.2f}")
                total += r["bet"]
                ev += r["bet"] * r["edge"]
            print(f"  Total staked ${total:.2f} ({total / args.bankroll:.1%}), "
                  f"ticket EV ${ev:+.2f}")


if __name__ == "__main__":
    main()
