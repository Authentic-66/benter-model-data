"""Phase 6: win-probability models.

Part 1 — picks-level logistic regression: trains on historical picks
joined to results, evaluates with cross-validation, and saves the fitted
pipeline to benter_model_prob.pkl for use by prob_predict.py.

Part 2 — conditional logit (Benter-style): trains on FULL FIELDS from the
entries table joined to results. Win probability for horse i in race r is
softmax(beta . x_i) over every starter in r, fitted by maximum likelihood
with within-race centering of numeric features. Saved to
benter_model_cl.pkl.
"""

import os
import pickle
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "benter_model.db")
MODEL_PATH = os.path.join(SCRIPT_DIR, "benter_model_prob.pkl")
CL_MODEL_PATH = os.path.join(SCRIPT_DIR, "benter_model_cl.pkl")
CALIBRATION_PLOT_PATH = os.path.join(SCRIPT_DIR, "calibration_plot.png")
CL_CALIBRATION_PLOT_PATH = os.path.join(SCRIPT_DIR, "calibration_plot_cl.png")

NUMERIC_FEATURES = ["ml_odds", "pp_power", "days_off"]
CATEGORICAL_FEATURES = ["signal_type", "track", "surface"]

TRAINING_SQL = """
SELECT
    p.pick_id,
    p.track,
    p.signal_type,
    p.ml_odds,
    p.pp_power,
    p.days_off,
    COALESCE(rc.surface, 'Dirt')             AS surface,
    COALESCE(e.finish_pos, r.finish_pos)     AS finish_pos,
    r.odds                                   AS final_odds,
    fav.min_odds                             AS race_min_odds
FROM picks p
LEFT JOIN roi_entries e ON e.pick_id = p.pick_id
LEFT JOIN races rc       ON rc.race_id = p.race_id
LEFT JOIN results r      ON r.race_id = p.race_id AND r.horse_name = p.horse_name
LEFT JOIN (
    SELECT race_id, MIN(odds) AS min_odds
    FROM results
    WHERE odds IS NOT NULL
    GROUP BY race_id
) fav ON fav.race_id = p.race_id
WHERE COALESCE(e.finish_pos, r.finish_pos) IS NOT NULL
"""


def load_training_data():
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(TRAINING_SQL, con)
    con.close()
    df["win"] = (df["finish_pos"] == 1).astype(int)
    return df


def build_pipeline():
    numeric = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]
    )
    categorical = OneHotEncoder(handle_unknown="ignore")
    pre = ColumnTransformer(
        [
            ("num", numeric, NUMERIC_FEATURES),
            ("cat", categorical, CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline(
        [
            ("pre", pre),
            ("clf", LogisticRegression(max_iter=1000, C=1.0)),
        ]
    )


def implied_prob(ml_odds):
    """Win probability implied by decimal ML odds (no takeout adjustment).
    ml_odds in the DB/picks files are decimal: '2/1' is stored as 3.0."""
    return 1.0 / ml_odds


def favorite_baseline(df):
    """Accuracy of the rule 'predict win iff the pick is the race favorite'."""
    mask = df["final_odds"].notna() & df["race_min_odds"].notna()
    sub = df[mask]
    if sub.empty:
        return None, 0
    pred = (sub["final_odds"] <= sub["race_min_odds"]).astype(int)
    return accuracy_score(sub["win"], pred), len(sub)


def save_calibration_plot(y_true, y_prob, path,
                          label="Logistic model (CV)",
                          title="Calibration: Phase 6 win-probability model"):
    frac_pos, mean_pred = calibration_curve(y_true, y_prob, n_bins=8, strategy="quantile")
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], "k--", label="Perfectly calibrated")
    ax.plot(mean_pred, frac_pos, "o-", label=label)
    ax.set_xlabel("Mean predicted win probability")
    ax.set_ylabel("Observed win fraction")
    ax.set_title(title)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def train_picks_model():
    df = load_training_data()
    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df["win"]
    n, n_wins = len(df), int(y.sum())

    print("=" * 64)
    print("PHASE 6 - LOGISTIC REGRESSION WIN-PROBABILITY MODEL")
    print("=" * 64)
    print(f"Training samples: {n}  (wins: {n_wins}, win rate: {n_wins / n:.1%})")
    print(f"  ml_odds present:  {df['ml_odds'].notna().sum()}/{n}")
    print(f"  pp_power present: {df['pp_power'].notna().sum()}/{n}")
    print(f"  days_off present: {df['days_off'].notna().sum()}/{n}")
    print("  surface: constant ('Dirt' for every race in DB) - no signal")

    pipe = build_pipeline()

    # Cross-validated out-of-fold probabilities for honest evaluation
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    y_prob_cv = cross_val_predict(pipe, X, y, cv=cv, method="predict_proba")[:, 1]
    y_pred_cv = (y_prob_cv >= 0.5).astype(int)

    acc = accuracy_score(y, y_pred_cv)
    ll = log_loss(y, y_prob_cv)
    brier = brier_score_loss(y, y_prob_cv)
    majority_acc = max(y.mean(), 1 - y.mean())

    print("\n--- Cross-validated performance (5-fold) ---")
    print(f"Accuracy @0.5:        {acc:.3f}")
    print(f"  (majority baseline 'never wins': {majority_acc:.3f} - with a")
    print(f"   {n_wins / n:.0%} win rate, accuracy is a weak metric; log loss matters more)")
    print(f"Log loss:             {ll:.4f}")
    print(f"Brier score:          {brier:.4f}")

    # Log-loss baseline from ML-implied probabilities where available
    has_ml = df["ml_odds"].notna()
    if has_ml.sum() >= 20:
        p_ml = implied_prob(df.loc[has_ml, "ml_odds"])
        ll_ml = log_loss(df.loc[has_ml, "win"], p_ml, labels=[0, 1])
        ll_model_sub = log_loss(df.loc[has_ml, "win"], y_prob_cv[has_ml.values], labels=[0, 1])
        print(f"\nLog loss vs ML-implied prob (n={has_ml.sum()}):")
        print(f"  ML-implied baseline: {ll_ml:.4f}")
        print(f"  Model (same rows):   {ll_model_sub:.4f}")

    fav_acc, fav_n = favorite_baseline(df)
    if fav_acc is not None:
        print(f"\nFavorite baseline (predict win iff pick is race favorite, n={fav_n}):")
        print(f"  Baseline accuracy: {fav_acc:.3f}   Model accuracy: {acc:.3f}")

    save_calibration_plot(y, y_prob_cv, CALIBRATION_PLOT_PATH)
    print(f"\nCalibration plot saved -> {CALIBRATION_PLOT_PATH}")

    # Fit on all data and report coefficients
    pipe.fit(X, y)
    feat_names = pipe.named_steps["pre"].get_feature_names_out()
    coefs = pipe.named_steps["clf"].coef_[0]
    order = np.argsort(-np.abs(coefs))
    print("\n--- Feature importances (logistic coefficients, standardized) ---")
    for i in order:
        print(f"  {feat_names[i]:<40s} {coefs[i]:+.3f}")

    # Positive-EV spots within the training data (out-of-fold probs)
    ev_mask = has_ml.values & (y_prob_cv > implied_prob(df["ml_odds"].fillna(np.inf)).values)
    print(f"\nPositive-EV spots in training data (model prob > ML-implied): {ev_mask.sum()}")

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(
            {
                "pipeline": pipe,
                "numeric_features": NUMERIC_FEATURES,
                "categorical_features": CATEGORICAL_FEATURES,
                "n_train": n,
                "cv_log_loss": ll,
            },
            f,
        )
    print(f"Model saved -> {MODEL_PATH}")

    print("\n--- Caveats / what would improve this most ---")
    print(f"* Only {n} labeled picks ({n_wins} wins) - far below the thousands of")
    print("  races per factor Benter used; coefficient estimates are noisy.")
    print("* ml_odds/pp_power are missing on most older picks - backfilling them")
    print("  from archived PP files is the single highest-value data fix.")
    print("* The DB only contains horses we PICKED, not full fields. A true Benter")
    print("  model is conditional-logit over every starter in a race; ingesting")
    print("  full-field PP data (all ~21k results rows have finish/odds but no")
    print("  pp_power/signals) would let the model learn relative strength.")
    print("* No beaten lengths, speed figures, class, distance, jockey/")
    print("  trainer stats - these are in the Brisnet PPs and worth parsing next.")
    print("* All races are Dirt; surface adds nothing until turf tracks are added.")


# ════════════════════════════════════════════════════════════════════════
# Part 2 — conditional logit on full fields (entries ⋈ results)
# ════════════════════════════════════════════════════════════════════════

CL_FEATURES = ["log_ml", "prime_power_c", "pp_missing", "improving",
               "jt_zero", "sig_trainer", "sig_sire", "sig_horse", "sig_hotjt"]
CL_L2 = 1.0

CL_SQL = """
SELECT
    e.race_id,
    e.track,
    e.race_date,
    e.race_num,
    e.horse_name,
    e.ml_odds,
    e.prime_power,
    e.improving,
    e.jt_zero,
    e.signal_types,
    r.finish_pos
FROM entries e
JOIN results r ON r.race_id = e.race_id AND r.horse_name = e.horse_name
WHERE r.finish_pos IS NOT NULL AND e.ml_odds IS NOT NULL AND e.ml_odds > 1.0
"""


def load_cl_data():
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(CL_SQL, con)
    con.close()
    df["win"] = (df["finish_pos"] == 1).astype(int)
    grp = df.groupby("race_id")["win"]
    keep = grp.transform("sum").eq(1) & grp.transform("size").ge(2)
    return df[keep].copy()


def build_cl_features(df, stds=None):
    """Adds CL_FEATURES columns in place. Numeric features are centered
    within each race (a conditional logit is invariant to race-constant
    shifts, so only relative values carry signal) and scaled by the global
    std. Pass the training stds when transforming new data at predict
    time; returns the stds used."""
    sig = df["signal_types"].fillna("")
    df["sig_trainer"] = sig.str.contains("TRAINER").astype(float)
    df["sig_sire"] = sig.str.contains("SIRE").astype(float)
    df["sig_horse"] = sig.str.contains("HORSE").astype(float)
    df["sig_hotjt"] = sig.str.contains("HOT_JT").astype(float)
    df["improving"] = df["improving"].fillna(0).astype(float)
    df["jt_zero"] = df["jt_zero"].fillna(0).astype(float)

    df["log_ml"] = np.log(1.0 / df["ml_odds"])
    pp = pd.to_numeric(df["prime_power"], errors="coerce")
    df["pp_missing"] = pp.isna().astype(float)
    race_mean = pp.groupby(df["race_id"]).transform("mean")
    pp_filled = pp.fillna(race_mean).fillna(pp.median())

    df["log_ml"] = df["log_ml"] - df.groupby("race_id")["log_ml"].transform("mean")
    df["prime_power_c"] = pp_filled - pp_filled.groupby(df["race_id"]).transform("mean")

    if stds is None:
        stds = {c: float(df[c].std()) or 1.0 for c in ("log_ml", "prime_power_c")}
    for c, sd in stds.items():
        df[c] = df[c] / sd
    return stds


def cl_race_arrays(df):
    """Returns a list of (X, winner_idx, ml_implied_norm) per race."""
    races = []
    for _, g in df.groupby("race_id", sort=False):
        X = g[CL_FEATURES].to_numpy(float)
        w = int(np.flatnonzero(g["win"].to_numpy())[0])
        implied = (1.0 / g["ml_odds"]).to_numpy(float)
        races.append((X, w, implied / implied.sum()))
    return races


def fit_conditional_logit(races, lam=CL_L2):
    d = races[0][0].shape[1]

    def nll_grad(beta):
        nll = 0.5 * lam * float(beta @ beta)
        g = lam * beta.copy()
        for X, w, _ in races:
            s = X @ beta
            s -= s.max()
            e = np.exp(s)
            p = e / e.sum()
            nll -= np.log(max(p[w], 1e-12))
            g += X.T @ p - X[w]
        return nll, g

    res = minimize(nll_grad, np.zeros(d), jac=True, method="L-BFGS-B")
    return res.x


def cl_predict(X, beta):
    s = X @ beta
    s -= s.max()
    e = np.exp(s)
    return e / e.sum()


def cl_cross_validate(races, n_folds=5, seed=42):
    """Race-grouped CV. Returns out-of-fold per-race records and flat
    (y, p) arrays over all starters for calibration."""
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(races))
    folds = np.array_split(order, n_folds)
    recs, ys, ps = [], [], []
    for k in range(n_folds):
        test_idx = set(folds[k].tolist())
        train = [races[i] for i in range(len(races)) if i not in test_idx]
        beta = fit_conditional_logit(train)
        for i in sorted(test_idx):
            X, w, ml = races[i]
            p = cl_predict(X, beta)
            recs.append({
                "n": len(p),
                "p_win_model": p[w],
                "p_win_ml": ml[w],
                "hit_model": int(np.argmax(p) == w),
                "hit_ml": int(np.argmax(ml) == w),
            })
            y = np.zeros(len(p))
            y[w] = 1.0
            ys.append(y)
            ps.append(p)
    return pd.DataFrame(recs), np.concatenate(ys), np.concatenate(ps)


def train_conditional_logit():
    print("\n" + "=" * 64)
    print("PHASE 6b - CONDITIONAL LOGIT ON FULL FIELDS (entries x results)")
    print("=" * 64)

    df = load_cl_data()
    if df.empty or df["race_id"].nunique() < 30:
        print(f"Not enough full-field races ({df['race_id'].nunique() if not df.empty else 0}) "
              "- run backfill_entries.py / keep parsing cards.")
        return

    stds = build_cl_features(df)
    races = cl_race_arrays(df)
    n_races, n_starters = len(races), len(df)
    avg_field = n_starters / n_races
    print(f"Races: {n_races}   Starters: {n_starters}   Avg field: {avg_field:.1f}")
    print(f"Tracks: {', '.join(f'{t} {n}' for t, n in df.groupby('track')['race_id'].nunique().items())}")
    print(f"prime_power present: {(df['pp_missing'] == 0).sum()}/{n_starters}")

    recs, y_flat, p_flat = cl_cross_validate(races)
    ll_model = -np.log(np.maximum(recs["p_win_model"], 1e-12)).mean()
    ll_ml = -np.log(np.maximum(recs["p_win_ml"], 1e-12)).mean()
    ll_uniform = np.log(recs["n"]).mean()

    print("\n--- Cross-validated performance (5-fold, grouped by race) ---")
    print("Race-level log loss (-ln P(winner), lower is better):")
    print(f"  Conditional logit:     {ll_model:.4f}")
    print(f"  ML-implied (public):   {ll_ml:.4f}")
    print(f"  Uniform (1/n):         {ll_uniform:.4f}")
    print(f"Top-pick hit rate:       model {recs['hit_model'].mean():.1%}  "
          f"vs ML favorite {recs['hit_ml'].mean():.1%}  (n={n_races})")

    save_calibration_plot(
        y_flat, p_flat, CL_CALIBRATION_PLOT_PATH,
        label="Conditional logit (CV)",
        title="Calibration: conditional logit, full fields",
    )
    print(f"Calibration plot saved -> {CL_CALIBRATION_PLOT_PATH}")

    beta = fit_conditional_logit(races)
    order = np.argsort(-np.abs(beta))
    print("\n--- Coefficients (within-race standardized) ---")
    for i in order:
        print(f"  {CL_FEATURES[i]:<16s} {beta[i]:+.3f}")

    with open(CL_MODEL_PATH, "wb") as f:
        pickle.dump(
            {
                "beta": beta,
                "features": CL_FEATURES,
                "stds": stds,
                "l2": CL_L2,
                "n_races": n_races,
                "cv_race_log_loss": float(ll_model),
                "cv_race_log_loss_ml": float(ll_ml),
            },
            f,
        )
    print(f"\nModel saved -> {CL_MODEL_PATH}")

    print("\n--- Notes ---")
    print("* Probabilities sum to 1 within each race by construction - this is")
    print("  the Benter formulation (relative strength, not pick-vs-not-pick).")
    print(f"* log_ml (public ML odds) anchors the model; beating ll_ml={ll_ml:.4f}")
    print("  means the other factors add information beyond the morning line.")
    print("* days_off / speed figures are absent from condensed y-format PPs -")
    print("  full-format PPs would unlock the strongest Benter factors.")


def main():
    train_picks_model()
    train_conditional_logit()


if __name__ == "__main__":
    main()
