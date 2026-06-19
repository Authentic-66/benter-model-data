"""One-shot: test horse_starts_c × is_maiden interaction in the CL model.

Compares the production CL_FEATURES against CL_FEATURES + interaction on
full training data. Reports CV log-loss, ΔR², coefficient on the new term,
and per-subset log-loss for maiden vs non-maiden races. Does NOT overwrite
benter_model_cl.pkl — the production model is untouched.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
import prob_model as pm  # noqa: E402

DB_PATH = SCRIPT_DIR / "benter_model.db"
MAIDEN_RE = r"Mdn|MSW|MCL|MAIDEN"


def load_data_with_conditions() -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    q = """
    SELECT
        e.race_id, e.track, e.race_date, e.race_num,
        e.horse_name, COALESCE(e.source, 'PP') AS source,
        e.ml_odds, e.final_odds, e.prime_power, e.days_off,
        e.best_spd, e.jt_winpct, e.beaten_lengths, e.class_delta,
        e.distance_delta, e.improving, e.jt_zero, e.signal_types,
        e.horse_starts, r.finish_pos, rc.conditions
    FROM entries e
    JOIN results r ON r.race_id = e.race_id AND r.horse_name = e.horse_name
    JOIN races rc  ON rc.race_id = e.race_id
    WHERE r.finish_pos IS NOT NULL
      AND e.ml_odds IS NOT NULL
      AND e.ml_odds > 0.05
    """
    df = pd.read_sql_query(q, con)
    con.close()
    df["win"] = (df["finish_pos"] == 1).astype(int)
    grp = df.groupby("race_id")["win"]
    keep = grp.transform("sum").eq(1) & grp.transform("size").ge(2)
    return df[keep].copy()


def fit_and_perrace_ll(features: list[str], races: list) -> tuple[np.ndarray, np.ndarray]:
    beta = pm.fit_conditional_logit(races)
    lls = []
    for X, w, _ in races:
        p = pm.cl_predict(X, beta)
        lls.append(-np.log(max(p[w], 1e-12)))
    return np.array(lls), beta


def cv_metrics(features: list[str], races: list) -> dict:
    recs, _, _ = pm.cl_cross_validate(races)
    ll_model = -np.log(np.maximum(recs["p_win_model"], 1e-12)).mean()
    ll_ml = -np.log(np.maximum(recs["p_win_ml"], 1e-12)).mean()
    ll_uniform = np.log(recs["n"]).mean()
    return {
        "ll_model": float(ll_model),
        "ll_ml": float(ll_ml),
        "ll_uniform": float(ll_uniform),
        "r2_model": float(1 - ll_model / ll_uniform),
        "r2_ml":    float(1 - ll_ml    / ll_uniform),
        "delta_r2": float((1 - ll_model / ll_uniform) - (1 - ll_ml / ll_uniform)),
        "hit_model": float(recs["hit_model"].mean()),
        "hit_ml":    float(recs["hit_ml"].mean()),
    }


def main():
    df = load_data_with_conditions()
    df["is_maiden"] = (
        df["conditions"]
        .fillna("")
        .str.contains(MAIDEN_RE, case=False, regex=True)
        .astype(float)
    )

    pm.build_cl_features(df)
    # Interaction lives AFTER build_cl_features so horse_starts_c is already
    # within-race centered and scaled by stds["horse_starts_c"].
    df["hs_x_maiden"] = df["horse_starts_c"] * df["is_maiden"]

    baseline = list(pm.CL_FEATURES)
    extended = baseline + ["hs_x_maiden"]

    races_base = pm.cl_race_arrays(df, features=baseline)
    races_test = pm.cl_race_arrays(df, features=extended)
    n_races = len(races_base)

    # Per-race maiden mask in cl_race_arrays order. cl_race_arrays uses
    # groupby(sort=False) which preserves first-appearance order, so the
    # same groupby here gives a mask aligned 1:1 to races_base/races_test.
    per_race = df.groupby("race_id", sort=False).agg(
        is_maiden=("is_maiden", "first"),
        track=("track", "first"),
    )
    maiden_mask = per_race["is_maiden"].to_numpy(bool)

    print(f"Training races:        {n_races}")
    print(f"  maiden races:        {int(maiden_mask.sum())}")
    print(f"  non-maiden races:    {int((~maiden_mask).sum())}")

    print("\n--- 5-fold CV (race-grouped) ---")
    print("Running baseline...")
    cv_base = cv_metrics(baseline, races_base)
    print("Running with hs_x_maiden interaction...")
    cv_test = cv_metrics(extended, races_test)

    def row(name, m):
        return (f"  {name:<14s}  LL={m['ll_model']:.4f}  "
                f"R²={m['r2_model']:.4f}  "
                f"ΔR²={m['delta_r2']:+.4f}  "
                f"top1={m['hit_model']:.1%}")

    print(f"  ML baseline    LL={cv_base['ll_ml']:.4f}  "
          f"R²={cv_base['r2_ml']:.4f}  "
          f"top1={cv_base['hit_ml']:.1%}")
    print(row("Baseline CL",  cv_base))
    print(row("+ hs_x_maiden", cv_test))
    delta_delta = cv_test["delta_r2"] - cv_base["delta_r2"]
    print(f"  Δ in ΔR² from interaction: {delta_delta:+.5f}")

    print("\n--- Full-fit coefficients (within-race standardized) ---")
    ll_base_pr, beta_base = fit_and_perrace_ll(baseline, races_base)
    ll_test_pr, beta_test = fit_and_perrace_ll(extended, races_test)

    hs_idx_base = baseline.index("horse_starts_c")
    hs_idx_test = extended.index("horse_starts_c")
    ix_idx_test = extended.index("hs_x_maiden")

    print(f"  Baseline:    horse_starts_c    = {beta_base[hs_idx_base]:+.4f}")
    print(f"  Extended:    horse_starts_c    = {beta_test[hs_idx_test]:+.4f}  "
          f"(main effect on non-maiden share + maiden share)")
    print(f"  Extended:    hs_x_maiden       = {beta_test[ix_idx_test]:+.4f}  "
          f"(maiden-specific increment)")
    print(f"  Implied maiden total effect = main + interaction = "
          f"{beta_test[hs_idx_test] + beta_test[ix_idx_test]:+.4f}")

    print("\n--- In-sample log-loss by subset ---")
    print(f"             {'maidens':>14}{'non-maidens':>14}{'all':>10}")
    print(f"  Baseline   {ll_base_pr[maiden_mask].mean():>14.4f}"
          f"{ll_base_pr[~maiden_mask].mean():>14.4f}"
          f"{ll_base_pr.mean():>10.4f}")
    print(f"  +Interact  {ll_test_pr[maiden_mask].mean():>14.4f}"
          f"{ll_test_pr[~maiden_mask].mean():>14.4f}"
          f"{ll_test_pr.mean():>10.4f}")
    print(f"  Δ          {ll_test_pr[maiden_mask].mean() - ll_base_pr[maiden_mask].mean():>+14.4f}"
          f"{ll_test_pr[~maiden_mask].mean() - ll_base_pr[~maiden_mask].mean():>+14.4f}"
          f"{ll_test_pr.mean() - ll_base_pr.mean():>+10.4f}")
    print("  (negative Δ = interaction improves fit on that subset)")

    # Quick approximate SE on the interaction via bootstrap of fold-out residuals
    # — keep it cheap, just to give the user a sense of stability.
    print("\n--- Bootstrap stability (50 race-resamples) ---")
    rng = np.random.default_rng(7)
    boot = []
    n = len(races_test)
    for _ in range(50):
        idx = rng.integers(0, n, n)
        sample = [races_test[i] for i in idx]
        try:
            b = pm.fit_conditional_logit(sample)
            boot.append(b[ix_idx_test])
        except Exception:
            continue
    boot = np.array(boot)
    if len(boot):
        print(f"  hs_x_maiden mean  = {boot.mean():+.4f}")
        print(f"  hs_x_maiden std   = {boot.std():.4f}")
        print(f"  Pr(>0)            = {(boot > 0).mean():.1%}")
        ci_lo, ci_hi = np.percentile(boot, [2.5, 97.5])
        print(f"  95% bootstrap CI  = [{ci_lo:+.4f}, {ci_hi:+.4f}]")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    main()
