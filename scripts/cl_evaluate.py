"""Replay conditional-logit tickets against actual results — the feedback
loop for retraining the Phase 6b model.

Usage:
    py cl_evaluate.py 2026-05-05 [2026-06-09] [--bankroll 100]

For every card in the entries table within the date range (joined to
results), this rebuilds the cl_predict scoring — softmax win probabilities,
ML overlays, +EV/~EV flags, half-Kelly ticket — and settles it with the
actual finish and payout:

    payout per $1 win bet = win_pay/2 when the chart payout is stored,
                            else final odds-to-1 + 1

Reported:
  * realized ROI vs predicted EV, by flag group (+EV / ~EV / no flag)
  * Kelly ticket replay per card (same sizing as cl_predict)
  * prime_power vs ml_odds as a practical predictor
  * calibration: did p=0.20 horses win ~20% of the time?

Scratched horses (in entries but not results) are excluded and the softmax
is renormalized over actual starters, matching how the model is trained.
"""

import argparse
import pickle
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

DB_PATH = SCRIPT_DIR / "benter_model.db"
CL_MODEL_PATH = SCRIPT_DIR / "benter_model_cl.pkl"

KELLY_MULTIPLIER = 0.5
MAX_BET_PCT = 0.10

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

EVAL_SQL = """
SELECT
    e.race_id,
    e.track,
    e.race_date,
    e.race_num,
    e.horse_name,
    e.ml_odds,
    e.prime_power,
    e.days_off,
    e.best_spd,
    e.jt_winpct,
    e.signal_types,
    e.improving,
    e.jt_zero,
    r.finish_pos,
    r.odds      AS final_odds,
    r.win_pay
FROM entries e
JOIN results r ON r.race_id = e.race_id AND r.horse_name = e.horse_name
WHERE r.finish_pos IS NOT NULL
  AND e.race_date BETWEEN ? AND ?
"""


def load_eval_data(start, end):
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(EVAL_SQL, con, params=(start, end))
    con.close()
    df["win"] = (df["finish_pos"] == 1).astype(int)
    grp = df.groupby("race_id")["win"]
    keep = grp.transform("sum").eq(1) & grp.transform("size").ge(2)
    n_dropped = df.loc[~keep, "race_id"].nunique()
    return df[keep].copy(), n_dropped


def payout_per_dollar(row):
    """Realized win-bet return per $1 staked (0 if the horse lost)."""
    if row["win"] != 1:
        return 0.0
    if pd.notna(row["win_pay"]) and row["win_pay"] > 0:
        return row["win_pay"] / 2.0
    if pd.notna(row["final_odds"]):
        return row["final_odds"] + 1.0
    return np.nan


def kelly_replay(df, bankroll):
    """Per-card half-Kelly ticket, settled with actual payouts.
    Returns (staked, returned, predicted_ev) totals."""
    staked = returned = pred_ev = 0.0
    for _, card in df.groupby(["track", "race_date"]):
        bets = card[(card["edge"] > 0) & card["ml_odds_raw"].notna()
                    & (card["ml_odds_raw"] > 1.0)]
        cap = MAX_BET_PCT * bankroll
        for _, r in bets.iterrows():
            kelly = r["edge"] / (r["ml_odds_raw"] - 1.0)
            bet = min(kelly * bankroll * KELLY_MULTIPLIER, cap)
            staked += bet
            returned += bet * r["payout"]
            pred_ev += bet * r["edge"]
    return staked, returned, pred_ev


def per_race_rank_corr(df, col, ascending):
    """Mean within-race Spearman correlation between a feature's rank and
    the finish position (1 = won). Lower finish is better, so a feature
    where 'better' should rank first uses ascending=False on the value."""
    corrs = []
    for _, g in df.groupby("race_id"):
        v = g[col]
        if v.notna().sum() < 3 or v.nunique() < 2:
            continue
        fr = g["finish_pos"].rank()
        vr = v.rank(ascending=ascending)
        c = np.corrcoef(fr[v.notna()], vr[v.notna()])[0, 1]
        if not np.isnan(c):
            corrs.append(c)
    return (float(np.mean(corrs)), len(corrs)) if corrs else (np.nan, 0)


def main():
    ap = argparse.ArgumentParser(description="Replay CL tickets against results")
    ap.add_argument("start_date", help="YYYY-MM-DD")
    ap.add_argument("end_date", nargs="?", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--bankroll", type=float, default=100.0,
                    help="per-card bankroll for the Kelly replay (default 100)")
    args = ap.parse_args()

    if not CL_MODEL_PATH.exists():
        sys.exit(f"Model not found at {CL_MODEL_PATH} - run prob_model.py first.")
    with open(CL_MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)
    beta, features, stds = bundle["beta"], bundle["features"], bundle["stds"]

    df, n_dropped = load_eval_data(args.start_date, args.end_date)
    if df.empty:
        sys.exit(f"No joinable entries+results between {args.start_date} and {args.end_date}.")

    # Model inputs (same handling as cl_predict)
    df["ml_odds_raw"] = df["ml_odds"]
    df["ml_odds"] = df.groupby("race_id")["ml_odds"].transform(lambda s: s.fillna(s.median()))
    df["ml_odds"] = df["ml_odds"].fillna(6.0)

    import prob_model as pm

    pm.build_cl_features(df, stds=stds)
    df["win_prob"] = np.nan
    for _, idx in df.groupby("race_id").groups.items():
        X = df.loc[idx, features].to_numpy(float)
        df.loc[idx, "win_prob"] = pm.cl_predict(X, beta)

    df["overlay"] = df["win_prob"] * df["ml_odds_raw"]
    df["edge"] = df["overlay"] - 1.0
    df["payout"] = df.apply(payout_per_dollar, axis=1)
    df["flag"] = np.select(
        [df["overlay"] > 1.0, df["overlay"] >= 0.75],
        ["+EV", "~EV"], default="no flag",
    )
    df.loc[df["ml_odds_raw"].isna(), "flag"] = "no ML"

    n_races = df["race_id"].nunique()
    n_cards = df.groupby(["track", "race_date"]).ngroups
    print("=" * 74)
    print(f"CL TICKET REPLAY   {args.start_date} .. {args.end_date}")
    print(f"Cards: {n_cards}   Races: {n_races}   Starters: {len(df)}"
          f"   (dropped {n_dropped} races without a clean winner join)")
    print("=" * 74)

    # ── 1. Flag groups: hit rate, predicted EV, realized ROI ($1 flat) ──
    print("\n--- Flat $1 win bet on every starter, grouped by flag ---")
    hdr = (f"{'FLAG':<9}{'BETS':>6}{'WINS':>6}{'HIT%':>7}"
           f"{'PRED EV/$':>11}{'REAL ROI/$':>12}")
    print(hdr)
    print("-" * len(hdr))
    for flag in ("+EV", "~EV", "no flag"):
        g = df[df["flag"] == flag]
        if g.empty:
            continue
        staked = len(g)
        ret = g["payout"].sum()
        print(f"{flag:<9}{staked:>6}{g['win'].sum():>6}{g['win'].mean():>7.1%}"
              f"{g['edge'].mean():>+11.1%}{(ret - staked) / staked:>+12.1%}")

    # ── 2. Kelly ticket replay (mirrors cl_predict --bankroll) ──────────
    staked, returned, pred_ev = kelly_replay(df, args.bankroll)
    print(f"\n--- Half-Kelly ticket replay (${args.bankroll:,.0f}/card, "
          f"cap {MAX_BET_PCT:.0%}/bet) ---")
    if staked > 0:
        print(f"Staked:        ${staked:,.2f}  across {n_cards} cards")
        print(f"Returned:      ${returned:,.2f}")
        print(f"Realized P/L:  ${returned - staked:+,.2f}  ({(returned - staked) / staked:+.1%} ROI)")
        print(f"Predicted EV:  ${pred_ev:+,.2f}  ({pred_ev / staked:+.1%} per $ staked)")
    else:
        print("No +EV bets in this period.")

    # ── 3. prime_power vs ml_odds in practice ───────────────────────────
    print("\n--- prime_power vs ml_odds as predictors ---")
    hits_pp = hits_ml = hits_fo = n_pp = n_ml = n_fo = 0
    for _, g in df.groupby("race_id"):
        if g["prime_power"].notna().sum() >= 2:
            n_pp += 1
            hits_pp += int(g.loc[g["prime_power"].idxmax(), "win"] == 1)
        if g["ml_odds_raw"].notna().sum() >= 2:
            n_ml += 1
            hits_ml += int(g.loc[g["ml_odds_raw"].idxmin(), "win"] == 1)
        if g["final_odds"].notna().sum() >= 2:
            n_fo += 1
            hits_fo += int(g.loc[g["final_odds"].idxmin(), "win"] == 1)
    if n_pp:
        print(f"Top prime_power horse won:  {hits_pp}/{n_pp} = {hits_pp / n_pp:.1%}")
    if n_ml:
        print(f"ML favorite won:            {hits_ml}/{n_ml} = {hits_ml / n_ml:.1%}")
    if n_fo:
        print(f"Final-odds favorite won:    {hits_fo}/{n_fo} = {hits_fo / n_fo:.1%}  (market reference)")
    c_pp, npp = per_race_rank_corr(df, "prime_power", ascending=False)
    c_ml, nml = per_race_rank_corr(df, "ml_odds_raw", ascending=True)
    print(f"Mean within-race rank corr with finish (1.0 = perfect):")
    print(f"  prime_power rank:  {c_pp:+.3f}  (n={npp} races)")
    print(f"  ml_odds rank:      {c_ml:+.3f}  (n={nml} races)")
    if not np.isnan(c_pp) and not np.isnan(c_ml):
        better = "prime_power" if c_pp > c_ml else "ml_odds"
        print(f"  => {better} ordered finishers better in this period")

    # ── 4. Calibration ──────────────────────────────────────────────────
    print("\n--- Calibration: model probability vs observed win rate ---")
    bins = [0, 0.05, 0.10, 0.15, 0.20, 0.30, 1.01]
    labels = ["0-5%", "5-10%", "10-15%", "15-20%", "20-30%", "30%+"]
    df["bin"] = pd.cut(df["win_prob"], bins=bins, labels=labels, right=False)
    hdr = f"{'BIN':<9}{'N':>6}{'PREDICTED':>11}{'OBSERVED':>10}{'DIFF':>8}"
    print(hdr)
    print("-" * len(hdr))
    for lab in labels:
        g = df[df["bin"] == lab]
        if g.empty:
            continue
        pred, obs = g["win_prob"].mean(), g["win"].mean()
        print(f"{lab:<9}{len(g):>6}{pred:>11.1%}{obs:>10.1%}{obs - pred:>+8.1%}")

    # ── 5. Feedback loop ────────────────────────────────────────────────
    con = sqlite3.connect(DB_PATH)
    n_avail = con.execute("""
        SELECT COUNT(*) FROM (
            SELECT e.race_id FROM entries e
            JOIN results r ON r.race_id = e.race_id AND r.horse_name = e.horse_name
            WHERE r.finish_pos IS NOT NULL
            GROUP BY e.race_id
            HAVING SUM(CASE WHEN r.finish_pos = 1 THEN 1 ELSE 0 END) = 1
               AND COUNT(*) >= 2
        )
    """).fetchone()[0]
    con.close()
    print("\n--- Feedback loop ---")
    print(f"Model was trained on {bundle['n_races']} races; "
          f"{n_avail} are now available ({n_avail - bundle['n_races']:+d}).")
    if n_avail > bundle["n_races"]:
        print("Run prob_model.py to fold the new races into the conditional logit.")
    print("CAUTION: races inside the model's training window are IN-SAMPLE here;")
    print("ROI/calibration on those dates is optimistic. Trust this report most")
    print("for dates parsed AFTER the last prob_model.py run.")


if __name__ == "__main__":
    main()
