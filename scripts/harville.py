"""Harville-Henery model for converting win probabilities into place,
show, and exotic-combination probabilities.

The basic Harville (1973) model assumes finishing positions are drawn
sequentially in proportion to remaining win probabilities — equivalently,
a Plackett-Luce model with strengths λ_i = log p_i. Empirically this
over-prices the favorite to place and under-prices long-shots; Henery
(1981) and others fix it with position-specific exponents:

    P(j is 2nd | i wins) ∝ p_j^γ
    P(k is 3rd | i, j)   ∝ p_k^δ

Typical fits put γ in [0.7, 0.95] and δ < γ (more flattening as we move
down the field). When γ = δ = 1 the model reduces to Harville.

This module is pure-numpy and vectorised on a single race; loop over
races in the caller.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from itertools import permutations

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


# ── core formulas ─────────────────────────────────────────────────────────────

def pair_prob(p: np.ndarray, gamma: float, i: int, j: int) -> float:
    """P(horse i wins AND horse j is 2nd) under Henery γ."""
    if i == j:
        return 0.0
    p = np.asarray(p, dtype=float)
    p_gamma = np.power(np.clip(p, 1e-15, None), gamma)
    p_gamma[i] = 0.0
    denom = p_gamma.sum()
    if denom <= 0:
        return 0.0
    return float(p[i] * p_gamma[j] / denom)


def triple_prob(p: np.ndarray, gamma: float, delta: float,
                i: int, j: int, k: int) -> float:
    """P(i wins, j 2nd, k 3rd) under Henery γ/δ."""
    if len({i, j, k}) != 3:
        return 0.0
    p = np.asarray(p, dtype=float)
    p_g = np.power(np.clip(p, 1e-15, None), gamma)
    p_g[i] = 0.0
    g_denom = p_g.sum()
    if g_denom <= 0:
        return 0.0
    p_d = np.power(np.clip(p, 1e-15, None), delta)
    p_d[i] = 0.0
    p_d[j] = 0.0
    d_denom = p_d.sum()
    if d_denom <= 0:
        return 0.0
    return float(p[i] * (p_g[j] / g_denom) * (p_d[k] / d_denom))


# ── marginal place / show ─────────────────────────────────────────────────────

def place_probs(p: np.ndarray, gamma: float) -> np.ndarray:
    """Vector of marginal P(horse j finishes 1st or 2nd)."""
    p = np.asarray(p, dtype=float)
    n = len(p)
    p_g = np.power(np.clip(p, 1e-15, None), gamma)
    out = p.copy()  # contribution from winning
    # Add contribution from finishing 2nd: ∑_i P(i wins) * p_j^γ / (Σ_k≠i p_k^γ)
    for i in range(n):
        denom = p_g.sum() - p_g[i]
        if denom <= 0:
            continue
        for j in range(n):
            if j == i:
                continue
            out[j] += p[i] * p_g[j] / denom
    return out


def show_probs(p: np.ndarray, gamma: float, delta: float) -> np.ndarray:
    """Vector of marginal P(horse k finishes 1st, 2nd, or 3rd)."""
    p = np.asarray(p, dtype=float)
    n = len(p)
    p_g = np.power(np.clip(p, 1e-15, None), gamma)
    p_d = np.power(np.clip(p, 1e-15, None), delta)
    out = place_probs(p, gamma).copy()
    # Add contribution from finishing 3rd: ∑_{i,j} P(i wins, j 2nd) * p_k^δ / (Σ_m≠i,j p_m^δ)
    for i in range(n):
        g_denom_i = p_g.sum() - p_g[i]
        if g_denom_i <= 0:
            continue
        for j in range(n):
            if j == i:
                continue
            pair_w = p[i] * p_g[j] / g_denom_i
            d_denom = p_d.sum() - p_d[i] - p_d[j]
            if d_denom <= 0:
                continue
            for k in range(n):
                if k == i or k == j:
                    continue
                out[k] += pair_w * p_d[k] / d_denom
    return out


# ── exotic combinations ──────────────────────────────────────────────────────

@dataclass
class ExoticPrices:
    """Fair-price summary for one race. All probs are in [0, 1]; the fair
    decimal payoff per $1 wagered, before takeout, is 1 / prob."""
    win:       np.ndarray              # shape (n,) — same as input win probs
    place:     np.ndarray              # shape (n,) — top-2 marginal
    show:      np.ndarray              # shape (n,) — top-3 marginal
    exacta:    np.ndarray              # shape (n, n)
    trifecta:  np.ndarray | None       # shape (n, n, n) — None if n_horses > 12
    superfecta: np.ndarray | None      # shape (n, n, n, n) — None if n > 9


def race_exotics(p: np.ndarray, gamma: float, delta: float,
                 eta: float | None = None,
                 max_trifecta_n: int = 12,
                 max_superfecta_n: int = 9) -> ExoticPrices:
    """All standard exotics for one race. eta (for 4th place) defaults to
    delta if not provided. Combination tensors are skipped when the field
    grows too large (otherwise n=14 trifecta = 2,744 cells and superfecta
    explodes); the larger races still get win/place/show."""
    p = np.asarray(p, dtype=float)
    p = p / p.sum()
    n = len(p)
    if eta is None:
        eta = delta

    exacta = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            exacta[i, j] = pair_prob(p, gamma, i, j)

    trifecta = None
    if n <= max_trifecta_n:
        trifecta = np.zeros((n, n, n))
        for i, j, k in permutations(range(n), 3):
            trifecta[i, j, k] = triple_prob(p, gamma, delta, i, j, k)

    superfecta = None
    if n <= max_superfecta_n:
        p_g = np.power(np.clip(p, 1e-15, None), gamma)
        p_d = np.power(np.clip(p, 1e-15, None), delta)
        p_e = np.power(np.clip(p, 1e-15, None), eta)
        superfecta = np.zeros((n, n, n, n))
        for i, j, k, l in permutations(range(n), 4):
            g_denom = p_g.sum() - p_g[i]
            if g_denom <= 0:
                continue
            d_denom = p_d.sum() - p_d[i] - p_d[j]
            if d_denom <= 0:
                continue
            e_denom = p_e.sum() - p_e[i] - p_e[j] - p_e[k]
            if e_denom <= 0:
                continue
            superfecta[i, j, k, l] = (
                p[i] * (p_g[j] / g_denom) * (p_d[k] / d_denom) * (p_e[l] / e_denom)
            )

    return ExoticPrices(
        win=p, place=place_probs(p, gamma), show=show_probs(p, gamma, delta),
        exacta=exacta, trifecta=trifecta, superfecta=superfecta,
    )


# ── multi-race (Pick N) ──────────────────────────────────────────────────────

def pick_n_prob(race_probs: list[np.ndarray], choices: list[list[int]]) -> float:
    """P of hitting a Pick N where `choices[r]` is the list of horse indices
    bet in race r. Each race is independent under the model."""
    out = 1.0
    for r, picks in enumerate(choices):
        out *= float(race_probs[r][picks].sum())
    return out


# ── sanity / smoke test ──────────────────────────────────────────────────────

def _sanity_check():
    """Verify normalization: place probs sum to 2.0, show to 3.0, and
    the exacta matrix sums to 1.0."""
    rng = np.random.default_rng(0)
    p = rng.dirichlet(np.ones(8))
    place = place_probs(p, gamma=0.85)
    show  = show_probs(p, gamma=0.85, delta=0.70)
    exotics = race_exotics(p, gamma=0.85, delta=0.70)

    print(f"Σ win    = {p.sum():.4f}  (expected 1.00)")
    print(f"Σ place  = {place.sum():.4f}  (expected 2.00)")
    print(f"Σ show   = {show.sum():.4f}  (expected 3.00)")
    print(f"Σ exacta = {exotics.exacta.sum():.4f}  (expected 1.00)")
    if exotics.trifecta is not None:
        print(f"Σ trif   = {exotics.trifecta.sum():.4f}  (expected 1.00)")
    if exotics.superfecta is not None:
        print(f"Σ super  = {exotics.superfecta.sum():.4f}  (expected 1.00)")


if __name__ == "__main__":
    _sanity_check()
