"""Temperature-scaling sweep on the CL model — calibration fix experiment.

The clean PP-only eval showed the CL model picks winners at 38.8% vs the
public ML's 36.3% (+2.5pp hit rate edge), but log loss is worse (ΔR²
−0.0107). That pattern is overconfidence: the model concentrates too much
probability on its top pick. Temperature scaling spreads the probability
mass without changing the ranking — argmax is preserved, so hit rate is
T-invariant by construction.

For each race we recompute p_T = softmax((X·β) / T). Equivalent to
softmax(log(p_orig) / T) up to a race-constant shift that cancels in the
softmax. Sweep T ∈ {0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5} and report log
loss, ΔR², and average top-pick confidence.

Read-only analysis. No edits to prob_model.CL_FEATURES or model pickles.
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

CL_SQL_PP_ONLY = """
SELECT
    e.race_id, e.track, e.race_date, e.race_num, e.horse_name,
    COALESCE(e.source, 'PP') AS source,
    e.ml_odds, e.final_odds, e.prime_power, e.days_off,
    e.best_spd, e.best_e1, e.best_e2, e.best_late,
    e.jt_winpct, e.beaten_lengths, e.class_delta, e.distance_delta,
    e.improving, e.jt_zero, e.signal_types, e.horse_starts,
    r.finish_pos
FROM entries e
JOIN results r ON r.race_id = e.race_id AND r.horse_name = e.horse_name
WHERE r.finish_pos IS NOT NULL
  AND e.ml_odds IS NOT NULL AND e.ml_odds > 0.05
  AND e.source = 'PP'
"""

T_GRID = (0.5, 0.8, 1.0, 1.1, 1.2, 1.3, 1.5, 2.0, 2.5)


def load_pp_only() -> pd.DataFrame:
    con = sqlite3.connect(pm.DB_PATH)
    df = pd.read_sql_query(CL_SQL_PP_ONLY, con)
    con.close()
    df["win"] = (df["finish_pos"] == 1).astype(int)
    grp = df.groupby("race_id")["win"]
    keep = grp.transform("sum").eq(1) & grp.transform("size").ge(2)
    return df[keep].copy()


def cv_oof_logits(df: pd.DataFrame, features: list[str],
                  n_folds: int = 5, seed: int = 42):
    """Race-grouped CV that returns per-race OOF logits (X·β) and
    metadata. Temperature scaling is then applied per race outside CV.

    Returns list of dicts {race_id, logits, win_idx, ml_norm, n}.
    """
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

    oof = []
    for k in range(n_folds):
        test_idx = set(folds[k].tolist())
        train = [races[i] for i in range(len(races)) if i not in test_idx]
        beta = pm.fit_conditional_logit(train)
        for i in sorted(test_idx):
            X, w, ml = races[i]
            logits = X @ beta  # un-softmaxed scores
            oof.append({
                "race_id": race_ids[i],
                "logits": logits,
                "win_idx": w,
                "ml_norm": ml,
                "n": len(logits),
            })
    return oof


def softmax_T(logits: np.ndarray, T: float) -> np.ndarray:
    """Numerically stable softmax with temperature."""
    s = logits / T
    s = s - s.max()
    e = np.exp(s)
    return e / e.sum()


def evaluate_T(oof: list[dict], T: float) -> dict:
    """Compute per-race calibrated p and aggregate metrics at temperature T."""
    p_winner = []          # model's probability assigned to the actual winner
    p_winner_ml = []       # public ML's probability assigned to the actual winner
    top_conf = []          # confidence the model places on its top pick
    top_conf_ml = []       # public ML's confidence in its favorite
    hits_model = 0
    hits_ml = 0
    sizes = []
    for r in oof:
        p = softmax_T(r["logits"], T)
        p_winner.append(p[r["win_idx"]])
        p_winner_ml.append(r["ml_norm"][r["win_idx"]])
        top_conf.append(p.max())
        top_conf_ml.append(r["ml_norm"].max())
        if int(np.argmax(p)) == r["win_idx"]:
            hits_model += 1
        if int(np.argmax(r["ml_norm"])) == r["win_idx"]:
            hits_ml += 1
        sizes.append(r["n"])

    p_winner = np.asarray(p_winner)
    p_winner_ml = np.asarray(p_winner_ml)
    n = len(oof)
    ll_model = float(-np.log(np.maximum(p_winner, 1e-12)).mean())
    ll_ml = float(-np.log(np.maximum(p_winner_ml, 1e-12)).mean())
    ll_uniform = float(np.log(sizes).mean())
    return {
        "T": T,
        "n": n,
        "ll_model": ll_model,
        "ll_ml": ll_ml,
        "ll_uniform": ll_uniform,
        "r2_model": 1.0 - ll_model / ll_uniform,
        "r2_ml": 1.0 - ll_ml / ll_uniform,
        "delta_r2": (1.0 - ll_model / ll_uniform) - (1.0 - ll_ml / ll_uniform),
        "hit_model": hits_model / n,
        "hit_ml": hits_ml / n,
        "top_conf_model": float(np.mean(top_conf)),
        "top_conf_ml": float(np.mean(top_conf_ml)),
    }


def calibration_by_bin(oof: list[dict], T: float,
                       n_bins: int = 8) -> pd.DataFrame:
    """Per-bin calibration: bucket horses by predicted P(win), compare
    mean predicted to actual win rate. Used to visualize over/under-
    confidence after T scaling.
    """
    rows = []
    for r in oof:
        p = softmax_T(r["logits"], T)
        win_idx = r["win_idx"]
        for i, pi in enumerate(p):
            rows.append({"p": float(pi), "win": int(i == win_idx)})
    df = pd.DataFrame(rows)
    df["bin"] = pd.qcut(df["p"], q=n_bins, duplicates="drop")
    grp = df.groupby("bin", observed=True)
    out = grp.agg(n=("p", "size"),
                  predicted=("p", "mean"),
                  actual=("win", "mean")).reset_index(drop=True)
    out["delta"] = out["actual"] - out["predicted"]
    return out


def main() -> None:
    print("=" * 76)
    print("CL TEMPERATURE-SCALING SWEEP — clean PP-only training")
    print("=" * 76)

    df = load_pp_only()
    pm.build_cl_features(df)
    n_races = df["race_id"].nunique()
    print(f"\nClean PP-only training set: {len(df)} entries, "
          f"{n_races} races, avg field {len(df)/n_races:.1f}")

    print("\nGenerating CV out-of-fold logits...")
    oof = cv_oof_logits(df, pm.CL_FEATURES)
    print(f"  {len(oof)} race predictions")

    # ── Sweep T ─────────────────────────────────────────────────────────
    print()
    print("=" * 76)
    print("TEMPERATURE SWEEP")
    print("=" * 76)
    print(f"  {'T':>5}  {'ΔR²':>8}  {'R²_model':>9}  {'R²_ml':>7}  "
          f"{'Hit%':>5}  {'top_conf_model':>14}  {'top_conf_ml':>12}  "
          f"{'LL_model':>8}")
    print("  " + "─" * 74)
    rows = []
    for T in T_GRID:
        m = evaluate_T(oof, T)
        rows.append(m)
        mark = "  ← T=1 baseline" if T == 1.0 else ""
        print(f"  {T:>5.2f}  {m['delta_r2']:>+8.4f}  {m['r2_model']:>9.4f}  "
              f"{m['r2_ml']:>7.4f}  {m['hit_model']:>5.1%}  "
              f"{m['top_conf_model']:>14.1%}  {m['top_conf_ml']:>12.1%}  "
              f"{m['ll_model']:>8.4f}{mark}")

    # ── Best T by ΔR² ──────────────────────────────────────────────────
    best = max(rows, key=lambda r: r["delta_r2"])
    print()
    print(f"  Best T by ΔR²: T = {best['T']:.2f}   ΔR² = {best['delta_r2']:+.4f}   "
          f"R²_model = {best['r2_model']:.4f}")
    print(f"  Public ML R² = {best['r2_ml']:.4f}   "
          f"Hit rate (T-invariant): {best['hit_model']:.1%} model vs "
          f"{best['hit_ml']:.1%} ML")
    print()

    # ── Calibration plot data at T=1.0 vs T=best ───────────────────────
    print("=" * 76)
    print("PER-BIN CALIBRATION  (predicted P(win) vs actual)")
    print("=" * 76)
    for T_label, T in (("T = 1.0 (uncalibrated)", 1.0),
                       (f"T = {best['T']:.2f} (best)", best["T"])):
        print(f"\n  {T_label}")
        cal = calibration_by_bin(oof, T)
        print(f"    {'bin':>5}  {'n':>6}  {'predicted':>10}  "
              f"{'actual':>8}  {'Δ':>7}")
        print("    " + "─" * 44)
        for i, row in cal.iterrows():
            print(f"    {i + 1:>5}  {int(row['n']):>6}  "
                  f"{row['predicted']:>10.3%}  {row['actual']:>8.3%}  "
                  f"{row['delta']:>+7.3%}")

    # ── Same sweep on the MIXED training set for comparison ────────────
    print()
    print("=" * 76)
    print("REFERENCE: same sweep on MIXED training (current production data)")
    print("=" * 76)
    df_mixed = pm.load_cl_data()
    pm.build_cl_features(df_mixed)
    print(f"  Mixed training: {df_mixed['race_id'].nunique()} races")
    oof_mixed = cv_oof_logits(df_mixed, pm.CL_FEATURES)
    print(f"  {'T':>5}  {'ΔR²':>8}  {'R²_model':>9}  {'Hit%':>5}  "
          f"{'top_conf_model':>14}  {'LL_model':>8}")
    print("  " + "─" * 60)
    for T in T_GRID:
        m = evaluate_T(oof_mixed, T)
        mark = "  ← T=1 baseline" if T == 1.0 else ""
        print(f"  {T:>5.2f}  {m['delta_r2']:>+8.4f}  {m['r2_model']:>9.4f}  "
              f"{m['hit_model']:>5.1%}  {m['top_conf_model']:>14.1%}  "
              f"{m['ll_model']:>8.4f}{mark}")


if __name__ == "__main__":
    main()
