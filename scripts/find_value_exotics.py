"""Find positive-EV exotic bets on a card.

Compares model probabilities (cl_predict + Henery γ/δ Harville correction)
against ML-implied market probabilities. For each combo at each race:

    market_prob   = harville(normalized 1 / ml_decimal)
    model_prob    = harville(softmax(beta·x))
    fair_payout   = cost / model_prob
    EV            = (model_prob / market_prob) * (1 - takeout)

Caveat: model EVs on Santa Anita can be inflated because the CL model was
trained on post-race tote (in lieu of ML) for SA — the model's win_prob
diverges further from live ML than it does for PP-trained tracks.

Usage:
    py scripts/find_value_exotics.py <TRACK> <YYYY-MM-DD> [--min-ev 1.10]
       [--min-prob 0.001] [--mandatory]
"""

from __future__ import annotations

import argparse
import pickle
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

CL_MODEL_PATH = SCRIPT_DIR / "benter_model_cl.pkl"
HARVILLE_PATH = SCRIPT_DIR / "benter_model_harville.pkl"
OUTPUT_DIR = SCRIPT_DIR / "exotic-evs"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# PP folder per track, relative to SCRIPT_DIR
TRACK_PP_FOLDERS = {
    "CT":  "../CharlesTown/ct-pps-files",
    "GP":  "../Gulfstream Park/gp-pps-files",
    "FP":  "../Fairmount Park/fp-pps-files",
    "EVD": "../Evangeline Downs/evd-pps-files",
    "SA":  "../Santa Anita/sa-pps-files",
    "SAR": "../Saratoga/sar-pps-files",
    "DD":  "../Delta Downs/dd-pps-files",
    "MVR": "../Mahoning Valley/mvr-pps-files",
    "FG":  "../Fair Grounds/fg-pps-files",
    "LRL": "../Laurel Park/laurel-pp-files",
}
RESULTS_ONLY_TRAINING = {"SA"}

# US tote averages — adjust per track if known
TAKEOUT = {
    "WIN": 0.16, "PLACE": 0.16, "SHOW": 0.16,
    "EXACTA": 0.22, "TRIFECTA": 0.22, "SUPERFECTA": 0.22,
    "PICK_N": 0.20,
}
BET_SIZE = {
    "WIN": 2.0, "PLACE": 2.0, "SHOW": 2.0,
    "EXACTA": 1.0, "TRIFECTA": 0.50, "SUPERFECTA": 0.10,
    "PICK_N": 2.0,
}


# ── data ──────────────────────────────────────────────────────────────────────

def find_pp_file(track: str, race_date) -> Path | None:
    """Locate a PP PDF matching the date in the track's PP folder."""
    rel = TRACK_PP_FOLDERS.get(track)
    if not rel:
        return None
    folder = (SCRIPT_DIR / rel).resolve()
    if not folder.exists():
        return None
    mmdd = race_date.strftime("%m%d")
    yyyymmdd = race_date.strftime("%Y%m%d")
    # Brisnet "y" file first (full PPs), then any PDF matching the date
    candidates = (
        list(folder.glob(f"*{mmdd}y*.pdf"))
        + list(folder.glob(f"*{mmdd}*.pdf"))
        + list(folder.glob(f"*{yyyymmdd}*.pdf"))
    )
    return candidates[0] if candidates else None


def score_card(pp_file: Path, track: str) -> pd.DataFrame:
    """Parse PP and apply the CL model. Mirrors cl_predict.rows_from_pp."""
    import brisnet_parser_v2 as bp
    import prob_model as pm

    with open(CL_MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)
    beta, features, stds = bundle["beta"], bundle["features"], bundle["stds"]

    text = bp.extract_text(str(pp_file))
    races = bp.parse_brisnet(text, track)

    rows = []
    for rn, race in sorted(races.items()):
        for h in race["horses"]:
            try:
                pp_power = float(h["prime_power"])
            except (ValueError, TypeError):
                pp_power = None
            rows.append({
                "race_id": rn, "race_num": rn, "pp": h["pp"],
                "horse_name": h["name"].replace(" ", ""),
                "source": "PP",
                "ml_odds": bp.ml_to_float(h["ml"]),
                "final_odds": None,
                "prime_power": pp_power,
                "signal_types": ",".join(s[0] for s in h["signals"]) or None,
                "improving": int(bool(h.get("improving"))),
                "jt_zero": int(bool(h.get("jt_zero"))),
                "days_off": h.get("days_off") or None,
                "best_spd": h.get("best_spd"),
                "jt_winpct": h.get("jt_winpct"),
                "beaten_lengths": h.get("beaten_len"),
                "class_delta": h.get("class_delta"),
                "distance_delta": h.get("distance_delta"),
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Coerce numeric columns out of object dtype — when final_odds is all
    # None (PP rows), build_cl_features feeds an object Series into np.log
    # and crashes. cl_predict has the same latent bug.
    for col in ("ml_odds", "final_odds", "prime_power", "days_off",
                "best_spd", "jt_winpct", "beaten_lengths",
                "class_delta", "distance_delta"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["ml_display"] = df["ml_odds"]
    df["ml_odds"] = df.groupby("race_id")["ml_odds"].transform(
        lambda s: s.fillna(s.median())
    )
    df["ml_odds"] = df["ml_odds"].fillna(6.0)

    pm.build_cl_features(df, stds=stds)
    df["win_prob"] = np.nan
    for _, idx in df.groupby("race_id").groups.items():
        X = df.loc[idx, features].to_numpy(float)
        df.loc[idx, "win_prob"] = pm.cl_predict(X, beta)
    return df, bundle


# ── per-race EV ───────────────────────────────────────────────────────────────

def _market_win_probs(ml_decimal: np.ndarray) -> np.ndarray:
    """Normalize 1/decimal-odds to sum to 1 (remove overround)."""
    raw = 1.0 / np.asarray(ml_decimal, dtype=float)
    return raw / raw.sum()


def _ev(model_p: float, market_p: float, takeout: float) -> float:
    """EV ratio against tote. >1 = positive expected value."""
    if market_p <= 0:
        return float("inf")
    return (model_p / market_p) * (1.0 - takeout)


def evaluate_race(race_df: pd.DataFrame, gamma: float, delta: float,
                  min_ev: float, min_prob: float, mandatory: bool):
    """Returns (positive_ev_bets, model_win_probs, market_win_probs).
    bets are dicts sorted by EV descending."""
    import harville

    g = race_df.reset_index(drop=True)
    n = len(g)

    model_w = g["win_prob"].to_numpy(float)
    model_w = model_w / model_w.sum()
    market_w = _market_win_probs(g["ml_odds"].to_numpy(float))

    model_ex = harville.race_exotics(model_w, gamma, delta)
    market_ex = harville.race_exotics(market_w, gamma, delta)

    horses = g["horse_name"].tolist()
    pps = [int(x) if pd.notna(x) else f"#{i + 1}" for i, x in enumerate(g["pp"])]

    bets: list[dict] = []

    def add(bet_type: str, combo: str, mp: float, marketp: float):
        if mp < min_prob:
            return
        takeout = TAKEOUT[bet_type]
        # Mandatory pools redistribute carryover; treat takeout as 0 to
        # avoid suppressing EV. Caller still warns about model risk.
        if mandatory and bet_type in ("EXACTA", "TRIFECTA", "SUPERFECTA"):
            takeout = 0.0
        cost = BET_SIZE[bet_type]
        ev = _ev(mp, marketp, takeout)
        bets.append({
            "bet_type": bet_type, "combo": combo, "cost": cost,
            "model_prob": mp, "market_prob": marketp,
            "fair_payout": cost / mp if mp > 0 else float("inf"),
            "ev": ev,
        })

    for i in range(n):
        add("WIN",   str(pps[i]), float(model_ex.win[i]),   float(market_ex.win[i]))
        add("PLACE", str(pps[i]), float(model_ex.place[i]), float(market_ex.place[i]))
        add("SHOW",  str(pps[i]), float(model_ex.show[i]),  float(market_ex.show[i]))

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            add("EXACTA", f"{pps[i]}-{pps[j]}",
                float(model_ex.exacta[i, j]), float(market_ex.exacta[i, j]))

    if model_ex.trifecta is not None and market_ex.trifecta is not None:
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                for k in range(n):
                    if k in (i, j):
                        continue
                    add("TRIFECTA", f"{pps[i]}-{pps[j]}-{pps[k]}",
                        float(model_ex.trifecta[i, j, k]),
                        float(market_ex.trifecta[i, j, k]))

    if model_ex.superfecta is not None and market_ex.superfecta is not None:
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                for k in range(n):
                    if k in (i, j):
                        continue
                    for l in range(n):
                        if l in (i, j, k):
                            continue
                        add("SUPERFECTA", f"{pps[i]}-{pps[j]}-{pps[k]}-{pps[l]}",
                            float(model_ex.superfecta[i, j, k, l]),
                            float(market_ex.superfecta[i, j, k, l]))

    bets.sort(key=lambda b: -b["ev"])
    pos = [b for b in bets if b["ev"] >= min_ev]
    # Diversify: best of each bet type, then fill with next-best overall.
    # Without this, 5 near-identical superfecta permutations crowd out the
    # WIN/PLACE/EXACTA picks for the same race.
    by_type: dict[str, dict] = {}
    rest: list[dict] = []
    for b in pos:
        if b["bet_type"] not in by_type:
            by_type[b["bet_type"]] = b
        else:
            rest.append(b)
    diversified = sorted(by_type.values(), key=lambda b: -b["ev"]) + rest
    return diversified, model_w, market_w, horses, pps


# ── pick N ────────────────────────────────────────────────────────────────────

def pick_n_block(name: str, race_nums: list[int],
                 model_probs: list[np.ndarray], market_probs: list[np.ndarray],
                 mandatory: bool) -> list[str]:
    """Top-1/2/3 per leg table for a Pick N. Cost = base × top^N tickets."""
    import harville

    base = BET_SIZE["PICK_N"]
    takeout = 0.0 if mandatory else TAKEOUT["PICK_N"]

    lines = []
    lines.append("")
    lines.append(f"  {name}  (races {race_nums[0]}–{race_nums[-1]})")
    lines.append(f"  {'STRAT':<10}{'COMBOS':>8}{'COST':>11}"
                 f"{'HIT %':>9}{'FAIR PAY':>14}{'E[RETURN]':>13}{'EV':>8}")
    for top in (1, 2, 3):
        choices = []
        for p in model_probs:
            k = min(top, len(p))
            choices.append(list(np.argsort(-p)[:k]))
        n_combos = int(np.prod([len(c) for c in choices]))
        cost = base * n_combos
        hit_model = harville.pick_n_prob(model_probs, choices)
        hit_market = harville.pick_n_prob(market_probs, choices)
        if hit_market > 0:
            fair = cost / hit_market * (1.0 - takeout)
            ev = (hit_model / hit_market) * (1.0 - takeout)
        else:
            fair = float("inf")
            ev = float("inf")
        exp_ret = hit_model * fair
        lines.append(f"  TOP-{top:<6d}{n_combos:>8d}{f'${cost:,.2f}':>11}"
                     f"{hit_model * 100:>8.3f}%{f'${fair:,.2f}':>14}"
                     f"{f'${exp_ret:,.2f}':>13}{ev:>8.2f}")
    return lines


# ── output ────────────────────────────────────────────────────────────────────

def _fmt_bet_row(b: dict) -> str:
    label_map = {
        "WIN": "WIN", "PLACE": "PLACE", "SHOW": "SHOW",
        "EXACTA": "$1 EXACTA", "TRIFECTA": "$.50 TRIF",
        "SUPERFECTA": "$.10 SUPER",
    }
    label = label_map[b["bet_type"]]
    flag = "+EV" if b["ev"] >= 1.0 else "pass"
    return (f"    {label:<11}{b['combo']:<14}"
            f"prob: {b['model_prob'] * 100:>5.2f}%  "
            f"mkt: {b['market_prob'] * 100:>5.2f}%  "
            f"fair: ${b['fair_payout']:>8.2f}  "
            f"EV: {b['ev']:>4.2f}  {flag}")


def render(track: str, race_date, pp_file: Path, bundle, races_df,
           min_ev: float, min_prob: float, mandatory: bool,
           top_per_race: int = 5) -> str:
    with open(HARVILLE_PATH, "rb") as f:
        hv = pickle.load(f)
    gamma, delta = hv["gamma"], hv["delta"]

    out: list[str] = []
    bar = "=" * 78
    out.append(bar)
    out.append(f"FIND VALUE EXOTICS  —  {track}  {race_date.isoformat()}")
    out.append(bar)
    out.append(f"PP file: {pp_file.name}")
    out.append(f"Model:   {bundle['n_races']} races trained  "
               f"(γ={gamma:.3f}  δ={delta:.3f}  fitted on {hv['n_races']} races)")
    out.append(f"Filters: EV ≥ {min_ev:.2f}, prob ≥ {min_prob:.4f}, "
               f"top {top_per_race} per race")
    if mandatory:
        out.append("MODE:    --mandatory  (exotic & pick-N takeouts set to 0%)")

    if track in RESULTS_ONLY_TRAINING:
        out.append("")
        out.append("⚠️  Honest caveat: this track was CL-trained on results-only "
                   "(post-race tote in")
        out.append("   place of ML). EVs derived from live ML on this card may "
                   "be inflated.")
    else:
        out.append("")
        out.append(f"✅ {track} CL model is PP-trained — higher confidence in EVs.")

    # Per-race
    per_race_model: dict[int, np.ndarray] = {}
    per_race_market: dict[int, np.ndarray] = {}
    all_pos_bets: list[dict] = []

    for rn, race_df in races_df.groupby("race_id"):
        race_df = race_df.reset_index(drop=True)
        pos, model_w, market_w, horses, pps = evaluate_race(
            race_df, gamma, delta, min_ev, min_prob, mandatory
        )
        per_race_model[int(rn)] = model_w
        per_race_market[int(rn)] = market_w

        out.append("")
        out.append("-" * 78)
        out.append(f"RACE {int(rn)}  ({len(race_df)} starters)   "
                   f"top {top_per_race} +EV opportunities")
        out.append("-" * 78)

        # Always show the model's top win contender for orientation
        order = np.argsort(-model_w)
        top1 = order[0]
        out.append(f"  Model favorite: PP {pps[top1]} {horses[top1]}  "
                   f"model {model_w[top1] * 100:.1f}%  vs  "
                   f"market {market_w[top1] * 100:.1f}%")

        if not pos:
            out.append("  (no combinations clear EV threshold)")
            continue
        for b in pos[:top_per_race]:
            out.append(_fmt_bet_row(b))
            all_pos_bets.append({**b, "race": int(rn)})

    # Pick N
    out.append("")
    out.append(bar)
    out.append("MULTI-RACE (Pick N)")
    out.append(bar)
    race_nums = sorted(per_race_model)
    model_list = [per_race_model[r] for r in race_nums]
    market_list = [per_race_market[r] for r in race_nums]
    for legs, name in ((6, "LATE PICK 6"), (5, "LATE PICK 5"),
                       (4, "LATE PICK 4"), (3, "LATE PICK 3")):
        if len(race_nums) < legs:
            continue
        sel = race_nums[-legs:]
        m = [per_race_model[r] for r in sel]
        k = [per_race_market[r] for r in sel]
        out.extend(pick_n_block(name, sel, m, k, mandatory))

    # Summary
    out.append("")
    out.append(bar)
    out.append("SUMMARY")
    out.append(bar)
    if all_pos_bets:
        total_cost = sum(b["cost"] for b in all_pos_bets)
        # Expected return at the *market* price is ev × cost (since EV is
        # already (model/market) × (1−takeout) per dollar staked).
        total_er = sum(b["ev"] * b["cost"] for b in all_pos_bets)
        edge = (total_er - total_cost) / total_cost if total_cost > 0 else 0.0
        out.append(f"Total +EV single-race bets: {len(all_pos_bets)}")
        out.append(f"Estimated bankroll required for full +EV ticket: "
                   f"${total_cost:,.2f}")
        out.append(f"Total expected return: ${total_er:,.2f}")
        out.append(f"Implied edge: {edge * 100:+.1f}%")
    else:
        out.append("No +EV single-race bets on this card.")
    out.append(bar)

    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(
        description="Find positive-EV exotic bets using model vs ML.")
    ap.add_argument("track", help="Track code (CT, GP, FP, EVD, SA, ...)")
    ap.add_argument("date", help="Race date YYYY-MM-DD")
    ap.add_argument("--min-ev", type=float, default=1.10,
                    help="Minimum EV ratio to display (default 1.10)")
    ap.add_argument("--min-prob", type=float, default=0.001,
                    help="Minimum model probability to display (default 0.001)")
    ap.add_argument("--mandatory", action="store_true",
                    help="Mandatory-payout mode: treat exotic/pick-N takeouts "
                         "as 0% (carryover redistributes the pool).")
    ap.add_argument("--top", type=int, default=5,
                    help="Top N +EV opportunities per race (default 5)")
    args = ap.parse_args()

    track = args.track.upper()
    try:
        race_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        sys.exit(f"Bad date '{args.date}' — use YYYY-MM-DD")

    if not CL_MODEL_PATH.exists() or not HARVILLE_PATH.exists():
        sys.exit("Model pickle(s) missing — run prob_model.py and "
                 "fit_harville.py first.")

    pp_file = find_pp_file(track, race_date)
    if pp_file is None:
        sys.exit(f"No PP file for {track} on {race_date} — "
                 f"cannot score card. (Checked {TRACK_PP_FOLDERS.get(track)})")

    print(f"Scoring {pp_file.name}...")
    df, bundle = score_card(pp_file, track)
    if df.empty:
        sys.exit("No starters parsed from PP — aborting.")

    report = render(track, race_date, pp_file, bundle, df,
                    args.min_ev, args.min_prob, args.mandatory, args.top)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"EXOTICS_{track}_{race_date.strftime('%Y%m%d')}.txt"
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"Saved → {out_path.relative_to(SCRIPT_DIR.parent)}")


if __name__ == "__main__":
    main()
