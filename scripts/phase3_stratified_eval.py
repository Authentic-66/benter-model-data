"""Phase 3 stratified evaluation — measure pace-scenario impact on the
subset of races where the features actually fire.

The original Phase 3 test reverted because the global CV ΔR² was flat.
Diagnosis was that 92.7% of CL training races have ZERO horses with E1
data (RESULTS-source dominance), so the speed_duel/lone_speed scenarios
fire on only 0.9% / 2.6% of races. This script splits the CV results by
stratum (number of horses in the race with E1 data) and recomputes
ΔR² inside each stratum to see if the model adds value on the
PP-rich population.

Read-only analysis: prob_model.CL_FEATURES is untouched. The Phase 3
feature set is passed locally into cl_race_arrays() via its `features`
argument.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import prob_model as pm  # noqa: E402

# Two Phase 3 configs to test:
#   3-feat: original spec — lp_advantage_c + lp_x_duel + highE1_x_lone
#   2-feat: minimal — drop the noise-level lp_advantage_c main effect
PHASE3_3FEAT = pm.CL_FEATURES + ["lp_advantage_c", "lp_x_duel", "highE1_x_lone"]
PHASE3_2FEAT = pm.CL_FEATURES + ["lp_x_duel", "highE1_x_lone"]


def cv_with_strata(df: pd.DataFrame, features: list[str],
                   n_folds: int = 5, seed: int = 42) -> pd.DataFrame:
    """Race-grouped CV that preserves race_id per record so callers can
    join in race-level metadata for stratified analysis.

    Mirrors prob_model.cl_cross_validate but returns race_id alongside the
    prediction columns. Train/test split is the same seed=42 used by the
    canonical training run, so comparisons are apples-to-apples.
    """
    races = []
    race_ids: list = []
    for rid, g in df.groupby("race_id", sort=False):
        X = g[features].to_numpy(float)
        w = int(np.flatnonzero(g["win"].to_numpy())[0])
        implied = (1.0 / g["ml_odds"]).to_numpy(float)
        races.append((X, w, implied / implied.sum()))
        race_ids.append(rid)

    rng = np.random.default_rng(seed)
    order = rng.permutation(len(races))
    folds = np.array_split(order, n_folds)

    recs = []
    for k in range(n_folds):
        test_idx = set(folds[k].tolist())
        train = [races[i] for i in range(len(races)) if i not in test_idx]
        beta = pm.fit_conditional_logit(train)
        for i in sorted(test_idx):
            X, w, ml = races[i]
            p = pm.cl_predict(X, beta)
            recs.append({
                "race_id": race_ids[i],
                "n": len(p),
                "p_win_model": float(p[w]),
                "p_win_ml": float(ml[w]),
                "hit_model": int(np.argmax(p) == w),
                "hit_ml": int(np.argmax(ml) == w),
            })
    return pd.DataFrame(recs)


def strat_r2(recs: pd.DataFrame) -> dict:
    """Compute ll_model, ll_ml, ll_uniform, ΔR² on a recs subset."""
    if recs.empty:
        return {"n": 0, "ll_model": np.nan, "ll_ml": np.nan,
                "ll_uniform": np.nan, "r2_model": np.nan, "r2_ml": np.nan,
                "delta_r2": np.nan, "hit_model": np.nan, "hit_ml": np.nan}
    ll_model = float(-np.log(np.maximum(recs["p_win_model"], 1e-12)).mean())
    ll_ml = float(-np.log(np.maximum(recs["p_win_ml"], 1e-12)).mean())
    ll_uniform = float(np.log(recs["n"]).mean())
    r2_model = 1.0 - ll_model / ll_uniform
    r2_ml = 1.0 - ll_ml / ll_uniform
    return {
        "n": len(recs),
        "ll_model": ll_model,
        "ll_ml": ll_ml,
        "ll_uniform": ll_uniform,
        "r2_model": r2_model,
        "r2_ml": r2_ml,
        "delta_r2": r2_model - r2_ml,
        "hit_model": float(recs["hit_model"].mean()),
        "hit_ml": float(recs["hit_ml"].mean()),
    }


def fit_on_subset(df: pd.DataFrame, features: list[str],
                  race_id_subset: set) -> np.ndarray:
    """Refit conditional logit on a race_id subset — used to compare
    coefficients when the model only 'sees' races where the scenario
    features actually fire."""
    sub = df[df["race_id"].isin(race_id_subset)].copy()
    races = []
    for _, g in sub.groupby("race_id", sort=False):
        X = g[features].to_numpy(float)
        w = int(np.flatnonzero(g["win"].to_numpy())[0])
        implied = (1.0 / g["ml_odds"]).to_numpy(float)
        races.append((X, w, implied / implied.sum()))
    return pm.fit_conditional_logit(races)


def main() -> None:
    print("=" * 72)
    print("PHASE 3 STRATIFIED EVALUATION")
    print("=" * 72)

    df = pm.load_cl_data()
    pm.build_cl_features(df)

    # Stratum = number of horses in this race that have a parsed E1
    df["_has_e1"] = pd.to_numeric(df["best_e1"], errors="coerce").notna()
    e1_count = df.groupby("race_id")["_has_e1"].transform("sum")
    df["_e1_count_in_race"] = e1_count.astype(int)
    df["_stratum"] = pd.cut(
        df["_e1_count_in_race"],
        bins=[-1, 0, 2, 100],
        labels=["0 E1 horses", "1-2 E1 horses", "3+ E1 horses (PP-rich)"],
    )
    race_stratum = df.drop_duplicates("race_id").set_index("race_id")["_stratum"]
    race_e1count = df.drop_duplicates("race_id").set_index("race_id")["_e1_count_in_race"]

    n_races = df["race_id"].nunique()
    print(f"\nCL training races: {n_races}")
    print(f"Field distribution by stratum:")
    print(race_stratum.value_counts().sort_index().to_string())
    print()

    for label, feats in (("BASELINE (current CL_FEATURES)", pm.CL_FEATURES),
                         ("PHASE 3 — 2 interactions only",  PHASE3_2FEAT),
                         ("PHASE 3 — 3 features (orig spec)", PHASE3_3FEAT)):
        print("─" * 72)
        print(f"  {label}    n_features = {len(feats)}")
        print("─" * 72)
        recs = cv_with_strata(df, feats)
        recs["stratum"] = recs["race_id"].map(race_stratum)

        overall = strat_r2(recs)
        print(f"  Overall (all {overall['n']} races):")
        print(f"    ΔR² = {overall['delta_r2']:+.4f}   "
              f"R²_model = {overall['r2_model']:.4f}   "
              f"R²_ml = {overall['r2_ml']:.4f}")
        print(f"    Hit rate: model {overall['hit_model']:.1%}  "
              f"vs ML {overall['hit_ml']:.1%}")

        for stratum in ("0 E1 horses", "1-2 E1 horses", "3+ E1 horses (PP-rich)"):
            s = strat_r2(recs[recs["stratum"] == stratum])
            if s["n"] == 0:
                print(f"    [{stratum:<24}] n=0 (no races)")
                continue
            print(f"    [{stratum:<24}] n={s['n']:<5} "
                  f"ΔR² = {s['delta_r2']:+.4f}   "
                  f"R²_model = {s['r2_model']:.4f}   "
                  f"R²_ml = {s['r2_ml']:.4f}   "
                  f"hit model/ML = {s['hit_model']:.1%} / {s['hit_ml']:.1%}")
        print()

    # ── Coefficient comparison: full fit vs PP-rich-only fit ────────────
    # Are lp_x_duel and highE1_x_lone fitting consistent values across
    # samples? If yes — signal is real, just diluted by zero-info rows.
    # If they swing wildly — fragile noise.
    print("=" * 72)
    print("COEFFICIENT COMPARISON: full fit vs PP-rich-subset fit")
    print("=" * 72)
    pp_rich_race_ids = set(race_e1count[race_e1count >= 3].index.tolist())
    print(f"PP-rich subset: {len(pp_rich_race_ids)} races (≥3 horses with E1)")
    print(f"Full set:       {n_races} races")
    print()

    for label, feats in (("PHASE 3 — 2 interactions", PHASE3_2FEAT),
                         ("PHASE 3 — 3 features",     PHASE3_3FEAT)):
        print("─" * 72)
        print(f"  {label}")
        print("─" * 72)
        # Full fit (no CV — just fit the model on everything)
        races_full = pm.cl_race_arrays(df, features=feats)
        beta_full = pm.fit_conditional_logit(races_full)
        beta_subset = fit_on_subset(df, feats, pp_rich_race_ids)
        print(f"    {'feature':<22} {'full β':>10} {'PP-rich β':>12} {'Δ':>10}")
        # Show pace-related rows + a few anchors
        for f in feats:
            if (f.startswith(("lp_", "highE1", "best_e", "best_spd",
                              "best_late")) or f in ("log_ml_pp",)):
                idx = feats.index(f)
                bf, bs = beta_full[idx], beta_subset[idx]
                print(f"    {f:<22} {bf:>+10.3f} {bs:>+12.3f} {bs - bf:>+10.3f}")
        print()


if __name__ == "__main__":
    main()
