"""Phase 6: score a picks file with the trained win-probability model.

Usage:
    py prob_predict.py picks_FP_06092026.txt [-o output.txt]

Reads an 8-column picks file (TRACK RACE HORSE SIGNAL BETS ML_ODDS
PP_POWER TRAINER), appends WIN_PROB as a 9th column and an EV flag as a
10th, and writes <input>_prob.txt unless -o is given. A pick is flagged
+EV when the model probability exceeds the probability implied by its
morning-line odds.
"""

import argparse
import os
import pickle
import sys

import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, "benter_model_prob.pkl")

COLUMNS = ["track", "race", "horse", "signal_type", "bets", "ml_odds", "pp_power", "trainer"]


def parse_picks_file(path):
    rows, raw_lines = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                raw_lines.append((line, None))
                continue
            parts = line.split()
            if len(parts) < 8:
                raw_lines.append((line, None))
                continue
            raw_lines.append((line, len(rows)))
            rows.append(dict(zip(COLUMNS, parts[:8])))
    df = pd.DataFrame(rows)
    for col in ("ml_odds", "pp_power"):
        df[col] = pd.to_numeric(df[col].replace("?", np.nan), errors="coerce")
    return df, raw_lines


def main():
    ap = argparse.ArgumentParser(description="Score a picks file with the Phase 6 model")
    ap.add_argument("picks_file")
    ap.add_argument("-o", "--output", help="output path (default: <input>_prob.txt)")
    args = ap.parse_args()

    if not os.path.exists(MODEL_PATH):
        sys.exit(f"Model not found at {MODEL_PATH} - run prob_model.py first.")
    with open(MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)
    pipe = bundle["pipeline"]

    df, raw_lines = parse_picks_file(args.picks_file)
    if df.empty:
        sys.exit("No pick rows found in the input file.")

    # All current tracks race on dirt; the DB has no surface info per pick
    df["surface"] = "Dirt"
    X = df[bundle["numeric_features"] + bundle["categorical_features"]]
    df["win_prob"] = pipe.predict_proba(X)[:, 1]
    df["implied"] = 1.0 / (df["ml_odds"] + 1.0)
    df["ev_flag"] = np.where(
        df["ml_odds"].notna() & (df["win_prob"] > df["implied"]), "+EV", "-"
    )

    out_path = args.output or os.path.splitext(args.picks_file)[0] + "_prob.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        for line, idx in raw_lines:
            if idx is None:
                if line.lstrip().startswith("# Format:"):
                    line += " WIN_PROB EV"
                f.write(line + "\n")
            else:
                r = df.iloc[idx]
                f.write(f"{line} {r['win_prob']:.3f} {r['ev_flag']}\n")

    n_ev = int((df["ev_flag"] == "+EV").sum())
    print(f"Scored {len(df)} picks from {args.picks_file}")
    print(f"Output -> {out_path}\n")
    hdr = f"{'TRACK':<6}{'RACE':<5}{'HORSE':<22}{'SIGNAL':<9}{'ML':>5}{'IMPLIED':>9}{'MODEL':>8}  EV"
    print(hdr)
    print("-" * len(hdr))
    for _, r in df.iterrows():
        ml = f"{r['ml_odds']:.1f}" if pd.notna(r["ml_odds"]) else "?"
        imp = f"{r['implied']:.3f}" if pd.notna(r["implied"]) else "?"
        print(
            f"{r['track']:<6}{r['race']:<5}{r['horse']:<22}{r['signal_type']:<9}"
            f"{ml:>5}{imp:>9}{r['win_prob']:>8.3f}  {r['ev_flag']}"
        )
    print(f"\nPositive-EV spots (model prob > ML-implied prob): {n_ev}")


if __name__ == "__main__":
    main()
