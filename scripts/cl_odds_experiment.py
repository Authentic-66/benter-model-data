"""Compare four conditional-logit feature variants that differ only in
how they express the public price signal:

  A: log_ml only            (deployable as-is)
  B: log_final only         (uses post-time tote price)
  C: log_ml + log_final     (both prices side by side)
  D: log_ml + odds_drift    (ML + log(final/ml))

CAUSALITY WARNING: variants B, C, and D use entries.final_odds, which is
the actual tote price at post time. At live predict time (before the
race) final_odds is unknown - so any gain shown by B/C/D over A is at
best an upper bound on what's achievable when betting before post. The
deployable feature is log_ml; the others tell us how much information
the tote aggregates beyond the ML and whether the drift is a leading or
trailing indicator.

All variants are trained on the SAME apples-to-apples race set: every
race where every starter has both ml_odds > 1.0 AND final_odds > 1.0,
plus a clean single winner. 5-fold race-grouped CV.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

import prob_model as pm
from prob_model import (
    DB_PATH, build_cl_features, cl_race_arrays, cl_cross_validate,
    fit_conditional_logit,
)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# Features common to every variant - the non-price predictors
BASE = ["prime_power_c", "pp_missing",
        "days_off_c", "best_spd_c", "spd_missing",
        "jt_winpct_c", "jt_missing", "beaten_c", "class_delta_c",
        "improving", "jt_zero",
        "sig_trainer", "sig_sire", "sig_horse", "sig_hotjt"]

VARIANTS = {
    "A: log_ml only":         BASE + ["log_ml"],
    "B: log_final only":      BASE + ["log_final"],
    "C: log_ml + log_final":  BASE + ["log_ml", "log_final"],
    "D: log_ml + drift":      BASE + ["log_ml", "odds_drift"],
}


def load_both_odds():
    """Apples-to-apples set: every starter has both ml_odds and final_odds."""
    import sqlite3
    sql = """
        SELECT
            e.race_id, e.track, e.race_date, e.race_num, e.horse_name,
            e.ml_odds, e.final_odds,
            e.prime_power, e.days_off, e.best_spd, e.jt_winpct,
            e.beaten_lengths, e.class_delta, e.distance_delta,
            e.improving, e.jt_zero, e.signal_types,
            r.finish_pos
        FROM entries e
        JOIN results r ON r.race_id = e.race_id AND r.horse_name = e.horse_name
        WHERE r.finish_pos IS NOT NULL
          AND e.ml_odds   IS NOT NULL AND e.ml_odds   > 1.0
          AND e.final_odds IS NOT NULL AND e.final_odds > 1.0
    """
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(sql, con)
    con.close()
    df["win"] = (df["finish_pos"] == 1).astype(int)
    grp = df.groupby("race_id")["win"]
    keep = grp.transform("sum").eq(1) & grp.transform("size").ge(2)
    return df[keep].copy()


def run_variant(df, features):
    races = cl_race_arrays(df, features=features)
    recs, _, _ = cl_cross_validate(races)
    ll_model = float(-np.log(np.maximum(recs["p_win_model"], 1e-12)).mean())
    ll_ml = float(-np.log(np.maximum(recs["p_win_ml"], 1e-12)).mean())
    hit_model = float(recs["hit_model"].mean())
    hit_ml = float(recs["hit_ml"].mean())
    # Final beta fit on full data for coefficient inspection
    beta = fit_conditional_logit(races)
    return {
        "ll_model": ll_model, "ll_ml": ll_ml,
        "hit_model": hit_model, "hit_ml": hit_ml,
        "beta": beta, "features": features,
    }


def main():
    df = load_both_odds()
    n_races = df["race_id"].nunique()
    n_starters = len(df)
    print("=" * 76)
    print("CL ODDS-FEATURE EXPERIMENT")
    print("=" * 76)
    print(f"Apples-to-apples set: {n_races} races, {n_starters} starters "
          f"(avg field {n_starters / n_races:.1f})")
    print(f"Tracks: " + ", ".join(
        f"{t} {n}" for t, n in df.groupby("track")["race_id"].nunique().items()
    ))
    print("CAUSALITY: variants B/C/D use post-time tote price (anti-causal")
    print("           for live betting). See top-of-file note.")
    print()

    build_cl_features(df)  # adds log_ml, log_final, odds_drift, etc.

    results = {}
    for name, feats in VARIANTS.items():
        results[name] = run_variant(df, feats)

    # ── Comparison table ────────────────────────────────────────────────
    print(f"{'VARIANT':<28}{'#feat':>6}{'CV ll':>10}{'vs ML':>10}"
          f"{'hit%':>8}{'ML hit%':>10}")
    print("-" * 76)
    for name, r in results.items():
        delta = r["ll_model"] - r["ll_ml"]
        print(f"{name:<28}{len(r['features']):>6}"
              f"{r['ll_model']:>10.4f}{delta:>+10.4f}"
              f"{r['hit_model']:>8.1%}{r['hit_ml']:>10.1%}")

    best = min(results.items(), key=lambda kv: kv[1]["ll_model"])
    print()
    print(f"Best by CV log loss: {best[0]}   ({best[1]['ll_model']:.4f})")

    # ── Coefficients for the price features in each variant ─────────────
    print("\n--- Price-feature coefficients (within-race standardized) ---")
    for name, r in results.items():
        price_feats = [(f, b) for f, b in zip(r["features"], r["beta"])
                       if f in ("log_ml", "log_final", "odds_drift")]
        coef_str = "   ".join(f"{f}={b:+.3f}" for f, b in price_feats)
        print(f"  {name:<28} {coef_str}")

    # ── Sanity: is the log_ml -> log_final swap stat-significant? ───────
    print("\n--- Notes ---")
    a = results["A: log_ml only"]["ll_model"]
    b = results["B: log_final only"]["ll_model"]
    c = results["C: log_ml + log_final"]["ll_model"]
    d = results["D: log_ml + drift"]["ll_model"]
    print(f"* log_ml vs log_final alone: {a:.4f} vs {b:.4f} "
          f"({'final wins' if b < a else 'ML wins'} by {abs(a - b):.4f})")
    print(f"* both vs ML alone:    {c:.4f} vs {a:.4f} "
          f"(gain {a - c:+.4f})")
    print(f"* drift vs ML alone:   {d:.4f} vs {a:.4f} "
          f"(gain {a - d:+.4f})")
    print("* On race-level log loss, 0.001-0.003 is small; 0.01+ is meaningful")
    print(f"  given n={n_races} races.")


if __name__ == "__main__":
    main()
