"""fit_harville.py -- MLE fit of the Henery γ (2nd place) and δ (3rd place)
correction parameters on top of the trained conditional-logit win
probabilities.

Pulls each training race's win-prob vector from `prob_model` (using the
saved benter_model_cl.pkl) and the observed top-3 finishers from the
results table. Then maximizes the rank-ordering log-likelihood:

    log L(γ, δ) = Σ_races [ log p_winner
                          + γ log p_2nd  - log Σ_{k≠winner} p_k^γ
                          + δ log p_3rd  - log Σ_{m∉{1,2}} p_m^δ ]

The winner term doesn't depend on (γ, δ); we drop it from the objective.

Output: scripts/benter_model_harville.pkl  {gamma, delta, n_races,
loglik, baseline (Harville γ=δ=1) loglik for comparison}.

Usage:
    py scripts/fit_harville.py
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

import prob_model as pm  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

OUT_PATH = SCRIPT_DIR / "benter_model_harville.pkl"


def collect_races():
    """One row per race: (win_probs vector, indices of 1st/2nd/3rd)."""
    with open(pm.CL_MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)
    beta = bundle["beta"]
    features = bundle["features"]
    stds = bundle["stds"]

    df = pm.load_cl_data()
    pm.build_cl_features(df, stds=stds)

    df["win_prob"] = 0.0
    for _, idx in df.groupby("race_id").groups.items():
        X = df.loc[idx, features].to_numpy(float)
        df.loc[idx, "win_prob"] = pm.cl_predict(X, beta)

    races = []
    skipped = 0
    for _, g in df.groupby("race_id", sort=False):
        p = g["win_prob"].to_numpy(float)
        if not np.isclose(p.sum(), 1.0, atol=1e-3):
            p = p / p.sum()
        pos = g["finish_pos"].to_numpy()
        i1 = np.where(pos == 1)[0]
        i2 = np.where(pos == 2)[0]
        i3 = np.where(pos == 3)[0]
        if len(i1) != 1 or len(i2) != 1 or len(i3) != 1:
            skipped += 1
            continue
        races.append({"p": p, "i1": int(i1[0]), "i2": int(i2[0]),
                      "i3": int(i3[0])})
    return races, skipped


def neg_log_lik(params, races, l2=0.0):
    """NLL of (γ, δ) for the 2nd- and 3rd-place ranking terms."""
    gamma, delta = float(params[0]), float(params[1])
    if gamma <= 0 or delta <= 0:
        return 1e12
    nll = 0.0
    for r in races:
        p = r["p"]
        i1, i2, i3 = r["i1"], r["i2"], r["i3"]
        p_safe = np.clip(p, 1e-15, None)

        # 2nd-place term
        p_g = np.power(p_safe, gamma)
        p_g[i1] = 0.0
        denom_g = p_g.sum()
        if denom_g <= 0:
            return 1e12
        nll -= gamma * np.log(p_safe[i2]) - np.log(denom_g)

        # 3rd-place term
        p_d = np.power(p_safe, delta)
        p_d[i1] = 0.0
        p_d[i2] = 0.0
        denom_d = p_d.sum()
        if denom_d <= 0:
            return 1e12
        nll -= delta * np.log(p_safe[i3]) - np.log(denom_d)

    # L2 anchor around Harville (1, 1) to keep the fit numerically sane
    nll += 0.5 * l2 * ((gamma - 1.0) ** 2 + (delta - 1.0) ** 2)
    return nll


def main():
    print("=" * 64)
    print("PHASE 6c — HARVILLE/HENERY γ/δ FIT")
    print("=" * 64)

    races, skipped = collect_races()
    print(f"Training races collected: {len(races)}   "
          f"(skipped {skipped} for missing top-3 positions)")

    # Baseline: Harville (γ=δ=1)
    base = neg_log_lik([1.0, 1.0], races)
    print(f"Harville baseline NLL  (γ=δ=1): {base:.2f}")

    # Henery MLE — Nelder-Mead is robust enough for two scalars with no
    # closed-form gradient; L-BFGS-B with numeric jacobian also works.
    res = minimize(
        neg_log_lik, x0=[0.85, 0.7], args=(races, 0.0),
        method="Nelder-Mead", options={"xatol": 1e-5, "fatol": 1e-5}
    )
    gamma, delta = float(res.x[0]), float(res.x[1])
    final_nll = float(res.fun)
    print(f"Fitted γ = {gamma:.4f}    δ = {delta:.4f}")
    print(f"Henery NLL: {final_nll:.2f}   "
          f"(improvement over Harville: {base - final_nll:+.2f} nats total, "
          f"{(base - final_nll) / len(races):+.4f}/race)")

    # Per-race average log-likelihood (positive = better than uniform)
    avg_ll = -final_nll / len(races)
    print(f"Avg log-likelihood per race (2nd+3rd terms): {avg_ll:.4f}")

    # Quick interpretation
    interp = []
    if gamma < 0.95:
        interp.append(f"γ < 1 ({gamma:.2f}) — 2nd-place distribution is FLATTER "
                      "than win-probs suggest (long-shots more likely to place)")
    elif gamma > 1.05:
        interp.append(f"γ > 1 ({gamma:.2f}) — favorites are MORE likely to place "
                      "than Harville implies")
    else:
        interp.append(f"γ ≈ 1 ({gamma:.2f}) — Harville fits 2nd-place well")
    if delta < gamma:
        interp.append(f"δ < γ ({delta:.2f} vs {gamma:.2f}) — 3rd-place is "
                      "flatter still (typical pattern; long-shots even more "
                      "likely to show than to place)")
    print()
    for line in interp:
        print("  " + line)

    with open(OUT_PATH, "wb") as f:
        pickle.dump({
            "gamma": gamma,
            "delta": delta,
            "n_races": len(races),
            "nll_henery": final_nll,
            "nll_harville": base,
            "avg_loglik_per_race": avg_ll,
            "cl_model_n_races": pickle.load(open(pm.CL_MODEL_PATH, "rb")).get("n_races"),
        }, f)
    print(f"\nSaved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
