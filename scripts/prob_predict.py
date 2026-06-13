"""Phase 6: score a picks file with the trained win-probability model.

Usage:
    py prob_predict.py picks_FP_06092026.txt [-o output.txt]

Reads a picks file (TRACK RACE HORSE SIGNAL BETS ML_ODDS PP_POWER
TRAINER [WIN_PROB EV_RATIO DAYS_OFF BEST_SPD SPD1 SPD2 SPD3 JT_WINPCT
BEATEN_LEN CLASS_DELTA DIST_DELTA]) and
appends WIN_PROB, EV_RATIO, an EV flag, and RANK, writing
<input>_prob.txt unless -o is given.

With --in-place, the picks file itself is rewritten with WIN_PROB and
EV_RATIO filled in as cols 9-10 (the format the ROI tracker and
database ingest). Re-running is safe: existing probability columns are
replaced, not duplicated, and all columns from DAYS_OFF (col 11)
onward are preserved verbatim.

EV_RATIO = model_prob / ML-implied prob (1.0 = model agrees with public).
Flags: "+EV" when EV_RATIO > 1.0, "~EV" (soft) when EV_RATIO >= 0.75.
RANK = model-probability rank within the race (1 = model's top pick).
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
                raw_lines.append((line, None, None))
                continue
            parts = line.split()
            if len(parts) < 8:
                raw_lines.append((line, "", None))
                continue
            # cols 11+ (DAYS_OFF BEST_SPD SPD1 SPD2 SPD3 ...) pass through verbatim
            raw_lines.append((" ".join(parts[:8]), " ".join(parts[10:]), len(rows)))
            row = dict(zip(COLUMNS, parts[:8]))
            row["days_off"] = parts[10] if len(parts) >= 11 else "?"
            row["best_speed"] = parts[11] if len(parts) >= 12 else "?"
            row["jt_winpct"] = parts[15] if len(parts) >= 16 else "?"
            row["beaten_lengths"] = parts[16] if len(parts) >= 17 else "?"
            row["class_delta"] = parts[17] if len(parts) >= 18 else "?"
            row["distance_delta"] = parts[18] if len(parts) >= 19 else "?"
            rows.append(row)
    df = pd.DataFrame(rows)
    for col in ("ml_odds", "pp_power", "days_off", "best_speed", "jt_winpct",
                "beaten_lengths", "class_delta", "distance_delta"):
        df[col] = pd.to_numeric(df[col].replace("?", np.nan), errors="coerce")
    return df, raw_lines


def main():
    ap = argparse.ArgumentParser(description="Score a picks file with the Phase 6 model")
    ap.add_argument("picks_file")
    ap.add_argument("-o", "--output", help="output path (default: <input>_prob.txt)")
    ap.add_argument(
        "--in-place",
        action="store_true",
        help="rewrite the picks file itself with WIN_PROB and EV_RATIO as cols 9-10",
    )
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
    # ml_odds are decimal odds (ml_to_float: '2/1' -> 3.0), so implied = 1/odds
    df["implied"] = 1.0 / df["ml_odds"]
    df["ev_ratio"] = df["win_prob"] / df["implied"]
    df["ev_flag"] = np.select(
        [df["ev_ratio"] > 1.0, df["ev_ratio"] >= 0.75],
        ["+EV", "~EV"],
        default="-",
    )
    df.loc[df["ml_odds"].isna(), "ev_flag"] = "-"
    df["rank"] = (
        df.groupby(["track", "race"])["win_prob"]
        .rank(ascending=False, method="min")
        .astype(int)
    )

    if args.in_place:
        out_path = args.picks_file
    else:
        out_path = args.output or os.path.splitext(args.picks_file)[0] + "_prob.txt"
    fmt_base = ("# Format: TRACK RACE HORSE SIGNAL BETS ML_ODDS PP_POWER TRAINER"
                " WIN_PROB EV_RATIO DAYS_OFF BEST_SPD SPD1 SPD2 SPD3 JT_WINPCT"
                " BEATEN_LEN CLASS_DELTA DIST_DELTA")
    with open(out_path, "w", encoding="utf-8") as f:
        for line, tail, idx in raw_lines:
            if idx is None:
                if line.lstrip().startswith("# Format:"):
                    line = fmt_base if args.in_place else fmt_base + " EV RANK"
                f.write(line + "\n")
            else:
                r = df.iloc[idx]
                ratio = f"{r['ev_ratio']:.2f}" if pd.notna(r["ev_ratio"]) else "?"
                out = f"{line} {r['win_prob']:.3f} {ratio}"
                if tail:
                    out += f" {tail}"
                if not args.in_place:
                    out += f" {r['ev_flag']} {r['rank']}"
                f.write(out + "\n")

    n_ev = int((df["ev_flag"] == "+EV").sum())
    n_soft = int((df["ev_flag"] == "~EV").sum())
    print(f"Scored {len(df)} picks from {args.picks_file}")
    print(f"Output -> {out_path}\n")
    hdr = (
        f"{'TRACK':<6}{'RACE':<5}{'HORSE':<22}{'SIGNAL':<9}"
        f"{'ML':>5}{'IMPLIED':>9}{'MODEL':>8}{'EVRATIO':>9}{'RANK':>6}  EV"
    )
    print(hdr)
    print("-" * len(hdr))
    for _, r in df.iterrows():
        ml = f"{r['ml_odds']:.1f}" if pd.notna(r["ml_odds"]) else "?"
        imp = f"{r['implied']:.3f}" if pd.notna(r["implied"]) else "?"
        ratio = f"{r['ev_ratio']:.2f}" if pd.notna(r["ev_ratio"]) else "?"
        print(
            f"{r['track']:<6}{r['race']:<5}{r['horse']:<22}{r['signal_type']:<9}"
            f"{ml:>5}{imp:>9}{r['win_prob']:>8.3f}{ratio:>9}{r['rank']:>6}  {r['ev_flag']}"
        )
    print(f"\nPositive-EV spots (EV_RATIO > 1.00):       {n_ev}")
    print(f"Soft value spots (EV_RATIO 0.75 - 1.00):   {n_soft}")


if __name__ == "__main__":
    main()
