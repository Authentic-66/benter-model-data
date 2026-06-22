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
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

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

NUMERIC_FEATURES = ["ml_odds", "pp_power", "days_off", "best_speed", "jt_winpct",
                    "beaten_lengths", "class_delta"]
# distance_delta is captured in entries/picks but held out of the active model:
# ablation showed it hurts CV log loss in both the picks logistic (0.4123 -> 0.4195)
# and the conditional logit (1.4540 -> 1.4574). Distance changes are already
# efficiently priced by the public ML.
CATEGORICAL_FEATURES = ["signal_type", "track", "surface"]

TRAINING_SQL = """
SELECT
    p.pick_id,
    p.track,
    p.signal_type,
    p.ml_odds,
    p.pp_power,
    p.days_off,
    p.best_speed,
    p.jt_winpct,
    p.beaten_lengths,
    p.class_delta,
    p.distance_delta,
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
    print(f"  best_speed present: {df['best_speed'].notna().sum()}/{n}")
    print(f"  jt_winpct present: {df['jt_winpct'].notna().sum()}/{n}")
    print(f"  beaten_lengths present: {df['beaten_lengths'].notna().sum()}/{n}")
    print(f"  class_delta present: {df['class_delta'].notna().sum()}/{n}")
    print(f"  distance_delta present: {df['distance_delta'].notna().sum()}/{n}")
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

    # McFadden's pseudo-R²: 1 - LL_model / LL_null. The null model here
    # predicts the constant base rate (win_rate); LL_null is the entropy
    # of a Bernoulli at that base rate.
    win_rate = float(y.mean())
    ll_null = -(win_rate * np.log(max(win_rate, 1e-12)) +
                (1 - win_rate) * np.log(max(1 - win_rate, 1e-12)))
    r2_picks = 1.0 - ll / ll_null

    print("\n--- Cross-validated performance (5-fold) ---")
    print(f"Accuracy @0.5:        {acc:.3f}")
    print(f"  (majority baseline 'never wins': {majority_acc:.3f} - with a")
    print(f"   {n_wins / n:.0%} win rate, accuracy is a weak metric; log loss matters more)")
    print(f"Log loss:             {ll:.4f}")
    print(f"Brier score:          {brier:.4f}")
    print(f"McFadden's pseudo-R²: {r2_picks:.4f}  (vs Bernoulli base-rate null)")

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
    print("* No beaten lengths, class, or distance features - these are in")
    print("  the Brisnet PPs and worth parsing next.")
    print("* All races are Dirt; surface adds nothing until turf tracks are added.")


# ════════════════════════════════════════════════════════════════════════
# Part 2 — conditional logit on full fields (entries ⋈ results)
# ════════════════════════════════════════════════════════════════════════

CL_FEATURES = ["log_ml_pp", "log_ml_results",
               "prime_power_c", "pp_missing",
               "days_off_c", "best_spd_c", "spd_missing",
               "best_e1_c",
               "bullet_count_60d_c", "workout_missing",
               "days_since_workout_c",
               "workout_count_60d_c",
               # Phase 3 race-level pace scenarios (lp_x_duel, highE1_x_lone,
               # lp_advantage_c) were tested 2026-06-20 and held out: 92.7%
               # of training races have ZERO horses with E1 data (RESULTS-
               # sourced rows dominate), so the speed-duel scenario fires
               # in only 43 of 4693 races (0.9%) — the test is underpowered.
               # The fitted lp_x_duel coefficient was +0.082 (a real signal
               # in those 43 races) but global ΔR² stayed flat at +0.0094.
               # build_cl_features still computes these columns so the
               # experiment can be re-enabled once PP coverage grows.
               "jt_winpct_c", "jt_missing", "beaten_c", "class_delta_c",
               "horse_starts_c", "starts_missing",
               "improving",
               "jt_zero", "sig_trainer", "sig_sire", "sig_horse", "sig_hotjt"]
# Pace figures (E1, E2, LP) extracted by extract_pace_figures in
# brisnet_parser_v2.py. Only best_e1_c is active in the fitted model:
# within-race correlations on the PP-row subset (n=2760) show best_e2_c
# is 0.72 colinear with best_e1_c and best_late_c is 0.66 colinear with
# best_spd_c, so E2 and LATE add noise without signal at the per-horse
# level. best_e1_c is the only pace column orthogonal to best_spd_c
# (within-race ρ=0.23) and carries the independent "early-speed
# dimension." All three pace columns are still stored in entries so the
# race-level Phase 3 features (count_high_e1, speed_duel_flag, lone-
# speed) can be built without re-parsing. No per-pace missing flags —
# they were ~95% colinear with spd_missing on PP rows and the three
# flags fought for the same "no PP data" signal that spd_missing
# already captures.
# horse_starts: count of PP race lines in the horse's Brisnet block
# (Brisnet displays up to ~10; zero = FTS). Within-race centering means
# the coefficient up-weights the experienced horse most in FTS-heavy fields
# (e.g. 2yo MSW) and barely at all in fields of seasoned horses —
# automatically capturing the "experience advantage" pattern.
# log_ml is split by entries.source — 'PP' rows came from Brisnet past-
# performance PDFs and carry the real morning line; 'RESULTS' rows are
# synthetic entries built from Equibase result charts where post-race
# tote stands in for ml_odds (no morning line is available in the chart).
# Fitting one log_ml mixes signals of very different predictive strength
# and pulls the coefficient toward the stronger post-race signal,
# polluting live (PP-driven) predictions. Each split column is centered
# within race and z-scored against the std of its own bucket so the two
# coefficients are directly comparable. Live prediction always uses PP,
# so at score time log_ml_pp is the only one that matters.
# dist_delta_c held out: CV ablation showed every transform of distance_delta
# (raw, abs, clip[-2,+2], clip[-1,+1]) hurt log loss vs dropping it. The bucket
# data confirms distance changes are efficiently priced by the public ML.
# log_final / odds_drift held out: scripts/cl_odds_experiment.py shows both
# would lower CV log loss by ~0.05 nats vs log_ml alone (n=175 races), but
# entries.final_odds is the post-time tote price - unknown at live predict
# time. build_cl_features still computes them so the experiment can be re-run
# and cl_evaluate can score historical cards with the final odds baseline.
CL_L2 = 1.0

CL_SQL = """
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
    e.bullet_count_60d,
    e.days_since_last_workout,
    e.workout_avg_pace,
    e.workout_count_60d,
    e.has_recent_bullet,
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
WHERE r.finish_pos IS NOT NULL AND e.ml_odds IS NOT NULL AND e.ml_odds > 0.05
"""
# 0.05 (was 1.0): allows legitimate odds-on chalk into training. The
# old > 1.0 filter dropped any horse priced below even-money — including
# the actual winners of races where the favorite went off odds-on. With
# `RESULTS`-sourced entries using post-race tote as ml_odds, those
# sub-evens prices are real, not parser noise, and we shouldn't filter
# winners out of training data.


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
    df["log_ml"] = df["log_ml"] - df.groupby("race_id")["log_ml"].transform("mean")

    # Source-aware split: 'RESULTS' rows are synthetic entries (post-race
    # tote standing in for ml_odds); 'PP' rows have the real morning line.
    # Zero outside the bucket so each coefficient is fit independently.
    # At predict time the source column may be absent — default to 'PP'.
    if "source" not in df.columns:
        df["source"] = "PP"
    df["source"] = df["source"].fillna("PP")
    is_results = (df["source"] == "RESULTS").astype(float)
    df["log_ml_results"] = df["log_ml"] * is_results
    df["log_ml_pp"]      = df["log_ml"] * (1.0 - is_results)

    # log_final and odds_drift use the final tote price. At predict time
    # this column is NULL (race hasn't run yet); fall back to ml_odds so
    # log_final degrades to log_ml and odds_drift to zero. Coerce to float
    # because an all-None final_odds column arrives as object dtype and
    # np.log on an object Series raises AttributeError.
    final_filled = df["final_odds"].where(
        df["final_odds"].notna(), df["ml_odds"]).astype(float)
    df["log_final"] = np.log(1.0 / final_filled)
    df["log_final"] = df["log_final"] - df.groupby("race_id")["log_final"].transform("mean")

    drift = np.log(final_filled / df["ml_odds"])
    df["odds_drift"] = drift - drift.groupby(df["race_id"]).transform("mean")

    def center(col, name, missing_name=None):
        v = pd.to_numeric(df[col], errors="coerce")
        if missing_name is not None:
            df[missing_name] = v.isna().astype(float)
        race_mean = v.groupby(df["race_id"]).transform("mean")
        filled = v.fillna(race_mean).fillna(v.median())
        df[name] = (filled - filled.groupby(df["race_id"]).transform("mean")).fillna(0.0)

    center("prime_power", "prime_power_c", "pp_missing")
    # no separate days_off missing flag: it coincides with spd_missing
    # (both come from PP race lines, absent only for first-time starters)
    center("days_off", "days_off_c")
    center("best_spd", "best_spd_c", "spd_missing")
    # No separate pace-missing flags: spd_missing already captures the
    # "no PP data" indicator at near-perfect colinearity (best_spd absent
    # ⇒ E1/E2/LP all absent on the same row).
    center("best_e1",  "best_e1_c")
    center("best_e2",  "best_e2_c")
    center("best_late","best_late_c")

    # ── Workout features ─────────────────────────────────────────────────
    # Within-race centering of bullet count and workout count surfaces the
    # relative fitness signal (most-worked horse in the field, freshest
    # bullet, etc.) rather than absolute counts that vary by track culture.
    # workout_avg_pace is sec/furlong — LOWER is faster; coefficient will be
    # negative if faster works correlate with wins.
    center("bullet_count_60d",        "bullet_count_60d_c", "workout_missing")
    center("days_since_last_workout", "days_since_workout_c")
    center("workout_avg_pace",        "workout_pace_c")
    center("workout_count_60d",       "workout_count_60d_c")
    # has_recent_bullet is already 0/1 — center to surface the within-race
    # contrast (one bullet horse in a field of non-bullet rivals).
    df["has_recent_bullet"] = pd.to_numeric(
        df["has_recent_bullet"], errors="coerce").fillna(0.0)
    df["has_recent_bullet_c"] = (
        df["has_recent_bullet"]
        - df.groupby("race_id")["has_recent_bullet"].transform("mean")
    ).fillna(0.0)

    # ── Race-level pace scenario features (Phase 3) ─────────────────────
    # Per-horse pace columns describe ability; the scenario lives at the
    # race level — multiple speed horses = duel = closers win; one lone
    # speed horse = wire-to-wire candidate. Conditional logit is invariant
    # to race-constant features, so the flags only matter via interactions
    # with per-horse signals.
    rid = df["race_id"]
    e1_raw = pd.to_numeric(df["best_e1"], errors="coerce")
    lp_raw = pd.to_numeric(df["best_late"], errors="coerce")
    e1_med = e1_raw.groupby(rid).transform("median")
    # Race std on E1; small fields (<3 finite values) get NaN — fall back to 0
    # so the threshold is just the race median in those cases.
    e1_std = e1_raw.groupby(rid).transform("std").fillna(0.0)
    high_e1_thresh = e1_med + 0.5 * e1_std
    df["is_high_e1"] = (e1_raw > high_e1_thresh).fillna(False).astype(float)
    df["count_high_e1"] = df.groupby("race_id")["is_high_e1"].transform("sum")
    df["speed_duel_flag"] = (df["count_high_e1"] >= 3).astype(float)
    df["lone_speed_flag"] = (df["count_high_e1"] == 1).astype(float)

    # lp_advantage_c: best_late centered on race MEDIAN (best_late_c above
    # uses race mean). Median is more robust when one horse skews the field.
    lp_med = lp_raw.groupby(rid).transform("median")
    df["lp_advantage_c"] = (lp_raw - lp_med).fillna(0.0)

    # Interactions — these are what the CL model actually sees:
    #   lp_x_duel:      closers benefit when a speed duel is projected
    #   highE1_x_lone:  the lone speed horse gets the wire-to-wire edge
    df["lp_x_duel"] = df["lp_advantage_c"] * df["speed_duel_flag"]
    df["highE1_x_lone"] = df["is_high_e1"] * df["lone_speed_flag"]

    center("jt_winpct", "jt_winpct_c", "jt_missing")
    # beaten lengths capped at 5: CV ablation showed the close-loss signal
    # lives under ~5 lengths (the public prices big losses correctly, and
    # raw values reach 87 for eased horses, swamping the linear term).
    # No separate missing flag: coincides with spd_missing.
    df["beaten_capped"] = pd.to_numeric(df["beaten_lengths"], errors="coerce").clip(upper=5)
    center("beaten_capped", "beaten_c")
    # class_delta = today_class - last_class; today_class is race-constant,
    # so within-race centering leaves the relative class-drop signal
    center("class_delta", "class_delta_c")
    # horse_starts: a count, NULL when the entry came from results (no PP),
    # 0 for first-time starters. Within-race centering brings out the
    # experience contrast (huge in 2yo MSW fields, small in open allowances).
    center("horse_starts", "horse_starts_c", "starts_missing")

    if stds is None:
        stds = {}
        pp_mask = df["source"] == "PP"

        # log_ml_pp / log_ml_results are z-scored against the std of their
        # OWN bucket — otherwise the zero rows from the other bucket would
        # deflate the scale and the fitted coefficients would no longer be
        # comparable across the two groups.
        pp_std  = float(df.loc[ pp_mask, "log_ml"].std()) if  pp_mask.any() else 0.0
        res_std = float(df.loc[~pp_mask, "log_ml"].std()) if (~pp_mask).any() else 0.0
        stds["log_ml_pp"]      = pp_std  or 1.0
        stds["log_ml_results"] = res_std or 1.0

        # Every PP-derived numeric feature is 0 on RESULTS-sourced rows
        # after within-race centering (synthetic rows share the same NULL
        # → race mean), so RESULTS carries no information for them but its
        # many zero rows still deflate the global std and shrink the
        # fitted PP coefficient. Bucket the std to PP-only. At predict
        # time the same stds are applied — RESULTS-centered-to-0 stays
        # zero either way.
        # spd_missing / jt_missing / pp_missing aren't naturally on the
        # same scale as the *_c features, so add them here too so the
        # printed coefficients are directly comparable.
        for c in ("prime_power_c", "days_off_c",
                  "best_spd_c", "best_e1_c", "best_e2_c", "best_late_c",
                  # Phase 3 scenario columns: still bucketed so the same
                  # stds are available when the experiment is rerun, even
                  # though none of these are in CL_FEATURES today.
                  "lp_advantage_c", "lp_x_duel", "highE1_x_lone",
                  "bullet_count_60d_c", "days_since_workout_c",
                  "workout_pace_c", "workout_count_60d_c",
                  "has_recent_bullet_c",
                  "jt_winpct_c", "beaten_c",
                  "class_delta_c", "horse_starts_c",
                  "pp_missing", "spd_missing", "jt_missing", "starts_missing",
                  "workout_missing"):
            v = df.loc[pp_mask, c] if pp_mask.any() else df[c]
            stds[c] = float(v.std()) or 1.0

        # log_final / odds_drift are well-defined on every row; full std.
        for c in ("log_final", "odds_drift"):
            stds[c] = float(df[c].std()) or 1.0
    for c, sd in stds.items():
        df[c] = df[c] / sd
    return stds


def cl_race_arrays(df, features=None):
    """Returns a list of (X, winner_idx, ml_implied_norm) per race.
    `features` defaults to the module-level CL_FEATURES; pass a different
    list to score the same data with a different feature subset (used by
    cl_odds_experiment.py)."""
    cols = features if features is not None else CL_FEATURES
    races = []
    for _, g in df.groupby("race_id", sort=False):
        X = g[cols].to_numpy(float)
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
    print(f"best_spd present:    {(df['spd_missing'] == 0).sum()}/{n_starters}")
    print(f"jt_winpct present:   {(df['jt_missing'] == 0).sum()}/{n_starters}")
    print(f"beaten_len present:  {df['beaten_lengths'].notna().sum()}/{n_starters}")
    print(f"class_delta present: {df['class_delta'].notna().sum()}/{n_starters}")
    print(f"dist_delta present:  {df['distance_delta'].notna().sum()}/{n_starters}")

    recs, y_flat, p_flat = cl_cross_validate(races)
    ll_model = -np.log(np.maximum(recs["p_win_model"], 1e-12)).mean()
    ll_ml = -np.log(np.maximum(recs["p_win_ml"], 1e-12)).mean()
    ll_uniform = np.log(recs["n"]).mean()

    # McFadden's pseudo-R²: 1 - LL_model / LL_null. The "null" is the
    # uniform 1/n model over each race's field. Benter quoted ~0.07-0.10
    # on Hong Kong cards; anything beating zero means the model adds info
    # over a coin-flip-by-field-size baseline. ΔR² over the public ML is
    # the cleaner read for a Benter-style overlay program — it shows how
    # much the model improves on the market itself.
    r2_model = 1.0 - ll_model / ll_uniform
    r2_ml    = 1.0 - ll_ml    / ll_uniform
    delta_r2 = r2_model - r2_ml

    print("\n--- Cross-validated performance (5-fold, grouped by race) ---")
    print("Race-level log loss (-ln P(winner), lower is better):")
    print(f"  Conditional logit:     {ll_model:.4f}")
    print(f"  ML-implied (public):   {ll_ml:.4f}")
    print(f"  Uniform (1/n):         {ll_uniform:.4f}")
    print("McFadden's pseudo-R² (vs uniform 1/n null; higher = more info):")
    print(f"  Model R² : {r2_model:.4f}")
    print(f"  ML R²    : {r2_ml:.4f}")
    print(f"  ΔR²      : {delta_r2:+.4f}   (model vs public ML)")
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
                "mcfadden_r2": float(r2_model),
                "mcfadden_r2_ml": float(r2_ml),
                "delta_r2": float(delta_r2),
            },
            f,
        )
    print(f"\nModel saved -> {CL_MODEL_PATH}")

    print("\n--- Notes ---")
    print("* Probabilities sum to 1 within each race by construction - this is")
    print("  the Benter formulation (relative strength, not pick-vs-not-pick).")
    print(f"* log_ml (public ML odds) anchors the model; beating ll_ml={ll_ml:.4f}")
    print("  means the other factors add information beyond the morning line.")
    print("* speed figures are noisy in condensed y-format PPs -")
    print("  full-format PPs would unlock the strongest Benter factors.")


def main():
    train_picks_model()
    train_conditional_logit()


if __name__ == "__main__":
    main()
