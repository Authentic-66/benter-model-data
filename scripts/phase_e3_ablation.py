"""Phase E3 ablation: form-trajectory features in the conditional logit.

Trains+evaluates the CL on (a) the full mixed dataset, and (b) the
PP-source-only subset (PP-rich), reporting ΔR² and top-pick hit rate
for the baseline CL_FEATURES set vs each candidate feature combination.

Ship threshold: PP-rich ΔR² gain > +0.001 over the current baseline.

Read-only on prob_model.py — does NOT mutate CL_FEATURES. Once a
combination clears the threshold, edit prob_model.CL_FEATURES manually
and rerun python prob_model.py.
"""

from __future__ import annotations

import sqlite3
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

BASELINE = list(pm.CL_FEATURES)

# Candidate per-feature additions, each paired with the missing flag where
# the source data has notable NULL coverage. trajectory_missing is shared
# across the slope columns (same root cause: <2 dated PP lines).
TRAJ_CANDIDATES = [
    ("speed_fig_slope_c",         ["speed_fig_slope_c", "trajectory_missing"]),
    ("beaten_lengths_slope_c",    ["beaten_lengths_slope_c"]),
    ("class_drop_count_c",        ["class_drop_count_c"]),
    ("figure_high_recent_c",      ["figure_high_recent_c"]),
    ("races_in_60d_c",            ["races_in_60d_c"]),
]

# Tested combinations beyond per-feature: the per-feature pass reveals which
# survive individually; the combo pass tests whether adding the survivors
# together still improves on the baseline (collinearity check).


def cv_records(df: pd.DataFrame, features: list[str],
               race_pp_rich: dict | None = None,
               n_folds: int = 5, seed: int = 42) -> pd.DataFrame:
    """Race-grouped 5-fold CV. Returns one record per held-out race with
    a pp_rich flag (race has ≥3 horses with E1 figures, matching
    phase3_stratified_eval's "PP-rich" stratum). Train uses the full
    mixed set; evaluation splits by stratum at report time."""
    races, race_ids = [], []
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
                "race_id":      race_ids[i],
                "pp_rich":      bool(race_pp_rich.get(race_ids[i], False))
                                if race_pp_rich else False,
                "n":            len(p),
                "p_win_model":  float(p[w]),
                "p_win_ml":     float(ml[w]),
                "hit_model":    int(np.argmax(p) == w),
                "hit_ml":       int(np.argmax(ml) == w),
            })
    return pd.DataFrame(recs)


def summarize(recs: pd.DataFrame) -> dict[str, float]:
    if recs.empty:
        return {"n": 0, "r2_model": float("nan"), "r2_ml": float("nan"),
                "delta_r2": float("nan"), "hit_model": float("nan"),
                "hit_ml": float("nan")}
    ll_model = float(-np.log(np.maximum(recs["p_win_model"], 1e-12)).mean())
    ll_ml = float(-np.log(np.maximum(recs["p_win_ml"], 1e-12)).mean())
    ll_uniform = float(np.log(recs["n"]).mean())
    return {
        "n":         len(recs),
        "r2_model":  1.0 - ll_model / ll_uniform,
        "r2_ml":     1.0 - ll_ml / ll_uniform,
        "delta_r2":  (1.0 - ll_model / ll_uniform) - (1.0 - ll_ml / ll_uniform),
        "hit_model": float(recs["hit_model"].mean()),
        "hit_ml":    float(recs["hit_ml"].mean()),
    }


def report(label: str, recs: pd.DataFrame, baseline: dict | None = None) -> dict:
    overall = summarize(recs)
    pp_recs = recs[recs["pp_rich"]]
    pp = summarize(pp_recs)
    bo = baseline["overall"] if baseline else None
    bp_ = baseline["pp"] if baseline else None

    def fmt_diff(cur, base, fmt="+.4f"):
        if base is None or np.isnan(cur) or np.isnan(base):
            return ""
        return f" ({(cur - base):{fmt}})"

    print(f"\n--- {label} ---")
    print(f"  overall: n={overall['n']:4d}  ΔR² {overall['delta_r2']:+.4f}"
          f"{fmt_diff(overall['delta_r2'], bo['delta_r2'] if bo else None)}"
          f"   hit {overall['hit_model']:.1%}"
          f" (ml {overall['hit_ml']:.1%})")
    print(f"  PP-rich: n={pp['n']:4d}  ΔR² {pp['delta_r2']:+.4f}"
          f"{fmt_diff(pp['delta_r2'], bp_['delta_r2'] if bp_ else None)}"
          f"   hit {pp['hit_model']:.1%}"
          f" (ml {pp['hit_ml']:.1%})")
    return {"overall": overall, "pp": pp}


def fit_beta(df: pd.DataFrame, features: list[str]) -> np.ndarray:
    races = pm.cl_race_arrays(df, features=features)
    return pm.fit_conditional_logit(races)


def main() -> None:
    print("=" * 76)
    print("PHASE E3 ABLATION — form trajectory features")
    print("=" * 76)

    df = pm.load_cl_data()
    pm.build_cl_features(df)
    n_races = df["race_id"].nunique()

    # "PP-rich" matches phase3_stratified_eval: races with ≥3 horses
    # having a parsed E1 figure. Train on the full mixed set; report
    # ΔR² stratified by this flag so the live-performance metric
    # (PP-rich) is comparable to Phase E1/E2 memory entries.
    has_e1 = pd.to_numeric(df["best_e1"], errors="coerce").notna()
    e1_count_per_race = has_e1.groupby(df["race_id"]).transform("sum")
    pp_rich_per_race = (e1_count_per_race >= 3)
    race_pp_rich = (df.drop_duplicates("race_id")
                      .assign(pp=pp_rich_per_race.loc[df.drop_duplicates("race_id").index])
                      .set_index("race_id")["pp"].to_dict())
    n_pp_rich = sum(race_pp_rich.values())
    print(f"races: {n_races} total, {n_pp_rich} PP-rich (≥3 horses with E1)")

    print("\nTrajectory coverage on PP-source entries:")
    pp = df[df["source"] == "PP"]
    for col in ("speed_fig_slope", "beaten_lengths_slope", "class_drop_count",
                "figure_high_recent", "races_in_60d"):
        n = pp[col].notna().sum()
        print(f"  {col:<24} {n}/{len(pp)}  ({100 * n / len(pp):.0f}%)")

    print("\n" + "=" * 76)
    print(f"BASELINE  ({len(BASELINE)} features) — full mixed train, "
          f"PP-rich slice for evaluation")
    print("=" * 76)
    base_recs = cv_records(df, BASELINE, race_pp_rich)
    base_metrics = report("baseline (current CL_FEATURES)", base_recs)

    print("\n" + "=" * 76)
    print("PER-FEATURE  (baseline + ONE candidate)")
    print("=" * 76)
    per_feat_metrics = {}
    for name, addcols in TRAJ_CANDIDATES:
        feats = BASELINE + addcols
        recs = cv_records(df, feats, race_pp_rich)
        per_feat_metrics[name] = report(f"+ {name} {addcols}", recs,
                                        baseline=base_metrics)

    # Cherry-pick survivors (PP-rich ΔR² gain > +0.001) for combo test
    survivors = [name for name, m in per_feat_metrics.items()
                 if m["pp"]["delta_r2"] - base_metrics["pp"]["delta_r2"] > 0.001]
    print("\n" + "=" * 76)
    print(f"SURVIVORS (PP-rich ΔR² > baseline + 0.001): {survivors}")
    print("=" * 76)

    if len(survivors) >= 2:
        # Combo of all survivors together
        combo_cols = []
        seen = set()
        for name, addcols in TRAJ_CANDIDATES:
            if name not in survivors:
                continue
            for c in addcols:
                if c not in seen:
                    combo_cols.append(c)
                    seen.add(c)
        feats = BASELINE + combo_cols
        recs = cv_records(df, feats, race_pp_rich)
        report(f"+ ALL SURVIVORS {combo_cols}", recs, baseline=base_metrics)

    # The user wanted to test whether continuous slope makes the binary
    # `improving` redundant — so try the strongest single survivor with
    # `improving` removed.
    if survivors:
        # Pick the strongest by PP-rich ΔR² gain
        top = max(survivors,
                  key=lambda n: per_feat_metrics[n]["pp"]["delta_r2"])
        top_addcols = dict(TRAJ_CANDIDATES)[top]
        feats_no_improving = [f for f in BASELINE if f != "improving"] + top_addcols
        print(f"\n+ {top} WITHOUT binary `improving`")
        recs = cv_records(df, feats_no_improving, race_pp_rich)
        report(f"+ {top} – improving", recs, baseline=base_metrics)

    # Print coefficients for the strongest single survivor (or top combo).
    if survivors:
        top = max(survivors,
                  key=lambda n: per_feat_metrics[n]["pp"]["delta_r2"])
        top_addcols = dict(TRAJ_CANDIDATES)[top]
        feats = BASELINE + top_addcols
        beta = fit_beta(df, feats)
        order = np.argsort(-np.abs(beta))
        print(f"\n--- Coefficients (full fit, baseline + {top}) ---")
        for i in order[:20]:
            print(f"  {feats[i]:<24s} {beta[i]:+.3f}")

    # ── Variation pass: try the "least-bad" features under transforms ───
    # Even when no candidate cleared the ship threshold, a transform
    # (outlier cap, smaller window, replace `improving`) may reveal the
    # signal IS there but the raw column wasn't the right encoding.
    print("\n" + "=" * 76)
    print("VARIATIONS")
    print("=" * 76)

    # 1) Clip beaten_lengths_slope: raw max was 37 (one disastrous loss
    #    in a streak); clip at ±5 to match the existing beaten_capped cap.
    df["bls_capped"] = pd.to_numeric(df["beaten_lengths_slope"],
                                     errors="coerce").clip(-5, 5)
    df["bls_capped"] = df["bls_capped"].fillna(
        df.groupby("race_id")["bls_capped"].transform("mean")).fillna(0.0)
    df["bls_capped_c"] = (df["bls_capped"]
                          - df.groupby("race_id")["bls_capped"].transform("mean"))
    bls_std = float(df.loc[df["source"] == "PP", "bls_capped_c"].std()) or 1.0
    df["bls_capped_c"] = df["bls_capped_c"] / bls_std
    feats = BASELINE + ["bls_capped_c"]
    recs = cv_records(df, feats, race_pp_rich)
    report("+ beaten_lengths_slope CAPPED ±5", recs, baseline=base_metrics)

    # 2) class_drop_count had the highest hit rate; try it alongside
    #    races_in_60d (the second-best ΔR² regression of -0.0009).
    feats = BASELINE + ["class_drop_count_c", "races_in_60d_c"]
    recs = cv_records(df, feats, race_pp_rich)
    report("+ class_drop_count + races_in_60d", recs, baseline=base_metrics)

    # 3) Swap binary `improving` for continuous speed_fig_slope.
    #    Does the continuous form subsume the binary?
    swap = [f for f in BASELINE if f != "improving"] + [
        "speed_fig_slope_c", "trajectory_missing"]
    recs = cv_records(df, swap, race_pp_rich)
    report("swap: drop `improving`, add speed_fig_slope_c", recs,
           baseline=base_metrics)

    # 4) ALL FIVE candidates combined (last-resort: maybe individual
    #    regressions cancel under a multi-dimensional add).
    feats = BASELINE + [
        "speed_fig_slope_c", "trajectory_missing",
        "beaten_lengths_slope_c",
        "class_drop_count_c",
        "figure_high_recent_c",
        "races_in_60d_c",
    ]
    recs = cv_records(df, feats, race_pp_rich)
    report("+ ALL FIVE trajectory features", recs, baseline=base_metrics)


if __name__ == "__main__":
    main()
