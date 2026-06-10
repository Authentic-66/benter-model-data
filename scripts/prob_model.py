"""Phase 6: logistic regression win-probability model.

Trains on historical picks joined to results in benter_model.db,
evaluates with cross-validation, and saves the fitted pipeline to
benter_model_prob.pkl for use by prob_predict.py.
"""

import os
import pickle
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
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
CALIBRATION_PLOT_PATH = os.path.join(SCRIPT_DIR, "calibration_plot.png")

NUMERIC_FEATURES = ["ml_odds", "pp_power"]
CATEGORICAL_FEATURES = ["signal_type", "track", "surface"]

TRAINING_SQL = """
SELECT
    p.pick_id,
    p.track,
    p.signal_type,
    p.ml_odds,
    p.pp_power,
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


def save_calibration_plot(y_true, y_prob, path):
    frac_pos, mean_pred = calibration_curve(y_true, y_prob, n_bins=8, strategy="quantile")
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], "k--", label="Perfectly calibrated")
    ax.plot(mean_pred, frac_pos, "o-", label="Logistic model (CV)")
    ax.set_xlabel("Mean predicted win probability")
    ax.set_ylabel("Observed win fraction")
    ax.set_title("Calibration: Phase 6 win-probability model")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main():
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
    print("  surface: constant ('Dirt' for every race in DB) - no signal")
    print("  days_off: NOT in the database schema - feature skipped")

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
    print("* No days_off, beaten lengths, speed figures, class, distance, jockey/")
    print("  trainer stats - these are in the Brisnet PPs and worth parsing next.")
    print("* All races are Dirt; surface adds nothing until turf tracks are added.")


if __name__ == "__main__":
    main()
