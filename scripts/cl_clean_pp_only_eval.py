"""CL clean-data evaluation: train and CV on PP-source entries only.

The mixed training set (PP + RESULTS rows where post-race tote stands in
for ml_odds) inflates the overall ΔR² by letting the model memorize the
tote on results-only races, but the model trails public ML on the real
prediction setting (PP-source races with real morning lines).

This script answers: does the existing CL architecture produce a positive
ΔR² when trained only on entries with source='PP'? If yes — the data mix
was hiding the signal and the architecture is sound. If flat/negative on
clean data too — the architecture itself needs work.

Read-only: no edits to prob_model.CL_FEATURES. The Phase 3 feature set is
passed locally where tested.
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

PHASE3_2FEAT = pm.CL_FEATURES + ["lp_x_duel", "highE1_x_lone"]
PHASE3_3FEAT = pm.CL_FEATURES + ["lp_advantage_c", "lp_x_duel", "highE1_x_lone"]

# Same filter as prob_model.CL_SQL but restricted to source='PP'.
CL_SQL_PP_ONLY = """
SELECT
    e.race_id,
    e.track,
    e.race_date,
    e.race_num,
    e.horse_name,
    COALESCE(e.source, 'PP') AS source,
    e.ml_odds,
    e.final_odds,
    e.prime_power,
    e.days_off,
    e.best_spd,
    e.best_e1,
    e.best_e2,
    e.best_late,
    e.jt_winpct,
    e.beaten_lengths,
    e.class_delta,
    e.distance_delta,
    e.improving,
    e.jt_zero,
    e.signal_types,
    e.horse_starts,
    r.finish_pos
FROM entries e
JOIN results r ON r.race_id = e.race_id AND r.horse_name = e.horse_name
WHERE r.finish_pos IS NOT NULL
  AND e.ml_odds IS NOT NULL AND e.ml_odds > 0.05
  AND e.source = 'PP'
"""


def load_pp_only() -> pd.DataFrame:
    con = sqlite3.connect(pm.DB_PATH)
    df = pd.read_sql_query(CL_SQL_PP_ONLY, con)
    con.close()
    df["win"] = (df["finish_pos"] == 1).astype(int)
    # CL needs exactly one winner per race and ≥2 starters
    grp = df.groupby("race_id")["win"]
    keep = grp.transform("sum").eq(1) & grp.transform("size").ge(2)
    return df[keep].copy()


def cv_with_race_ids(df: pd.DataFrame, features: list[str],
                     n_folds: int = 5, seed: int = 42) -> pd.DataFrame:
    """Race-grouped CV that preserves race_id alongside predictions."""
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
                "race_id": race_ids[i],
                "n": len(p),
                "p_win_model": float(p[w]),
                "p_win_ml": float(ml[w]),
                "hit_model": int(np.argmax(p) == w),
                "hit_ml": int(np.argmax(ml) == w),
            })
    return pd.DataFrame(recs)


def summarize(recs: pd.DataFrame, label: str) -> None:
    if recs.empty:
        print(f"  {label}: empty")
        return
    ll_model = float(-np.log(np.maximum(recs["p_win_model"], 1e-12)).mean())
    ll_ml = float(-np.log(np.maximum(recs["p_win_ml"], 1e-12)).mean())
    ll_uniform = float(np.log(recs["n"]).mean())
    r2_model = 1.0 - ll_model / ll_uniform
    r2_ml = 1.0 - ll_ml / ll_uniform
    delta = r2_model - r2_ml
    print(f"  {label}")
    print(f"    n races = {len(recs)}   avg field = {recs['n'].mean():.1f}")
    print(f"    LL model {ll_model:.4f}   LL ml {ll_ml:.4f}   "
          f"LL uniform {ll_uniform:.4f}")
    print(f"    R²_model {r2_model:.4f}   R²_ml {r2_ml:.4f}   "
          f"ΔR² {delta:+.4f}")
    print(f"    hit rate: model {recs['hit_model'].mean():.1%}   "
          f"vs ML favorite {recs['hit_ml'].mean():.1%}")


def fit_full(df: pd.DataFrame, features: list[str]) -> np.ndarray:
    races = pm.cl_race_arrays(df, features=features)
    return pm.fit_conditional_logit(races)


def main() -> None:
    print("=" * 76)
    print("CL CLEAN-DATA EVALUATION — train on source='PP' only")
    print("=" * 76)

    # ── Reference: current mixed training (for comparison) ──────────────
    df_mixed = pm.load_cl_data()
    n_mixed_entries = len(df_mixed)
    n_mixed_races = df_mixed["race_id"].nunique()
    n_pp_in_mixed = (df_mixed["source"] == "PP").sum()
    print(f"\nMixed training set (current, for reference):")
    print(f"  entries: {n_mixed_entries}  ({n_pp_in_mixed} PP-source, "
          f"{n_mixed_entries - n_pp_in_mixed} RESULTS-source)")
    print(f"  races:   {n_mixed_races}")

    # ── PP-only training ────────────────────────────────────────────────
    df = load_pp_only()
    n_entries = len(df)
    n_races = df["race_id"].nunique()
    avg_field = n_entries / n_races
    print(f"\nPP-only training set:")
    print(f"  entries: {n_entries}")
    print(f"  races:   {n_races}")
    print(f"  avg field: {avg_field:.1f}")
    print(f"  by track:")
    for t, g in df.groupby("track")["race_id"].nunique().items():
        print(f"    {t:>4}: {g} races")

    pm.build_cl_features(df)

    # E1 coverage in this clean set
    df["_has_e1"] = pd.to_numeric(df["best_e1"], errors="coerce").notna()
    e1_per_race = df.groupby("race_id")["_has_e1"].sum()
    n_3plus = (e1_per_race >= 3).sum()
    print(f"  races with ≥3 horses having E1 data: "
          f"{n_3plus} ({100 * n_3plus / n_races:.0f}%)")

    # ── Run CV on three feature sets ────────────────────────────────────
    print()
    print("=" * 76)
    print("CROSS-VALIDATED ΔR²  (5-fold, race-grouped, seed=42)")
    print("=" * 76)
    for label, feats in (("CURRENT CL_FEATURES (baseline)", pm.CL_FEATURES),
                         ("+ Phase 3 (2 interactions)",      PHASE3_2FEAT),
                         ("+ Phase 3 (3 features)",          PHASE3_3FEAT)):
        recs = cv_with_race_ids(df, feats)
        summarize(recs, label)
        print()

    # ── Coefficients on the clean training set ──────────────────────────
    print("=" * 76)
    print("COEFFICIENTS  (full PP-only fit)")
    print("=" * 76)
    for label, feats in (("CURRENT CL_FEATURES", pm.CL_FEATURES),
                         ("+ Phase 3 (2 inter.)", PHASE3_2FEAT)):
        beta = fit_full(df, feats)
        order = np.argsort(-np.abs(beta))
        print(f"  {label}")
        for i in order[:15]:  # top 15 by magnitude
            print(f"    {feats[i]:<22} {beta[i]:+.3f}")
        print()


if __name__ == "__main__":
    main()
