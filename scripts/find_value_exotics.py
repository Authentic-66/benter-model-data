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
       [--min-prob 0.001] [--mandatory] [--scratches "R4:3,R7:7"]
       [--live-odds "R1:1=2.5,3=4.0;R2:5=3.0"]
       [--live-odds-file live_odds_GP.txt] [--use-live-odds]
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


# ── scratches ─────────────────────────────────────────────────────────────────

def parse_scratches(s: str) -> dict[int, set[int]]:
    """Parse 'R4:3,R7:7' → {4: {3}, 7: {7}}. Also accepts 'R4:3+5' for
    multiple PPs in one race."""
    result: dict[int, set[int]] = {}
    if not s:
        return result
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if ":" not in tok:
            raise ValueError(
                f"Bad scratch token '{tok}' — expected R<race>:<pp>"
            )
        race_part, pp_part = tok.split(":", 1)
        race_part = race_part.strip().lstrip("Rr")
        try:
            race = int(race_part)
            for pp_str in pp_part.replace("+", " ").split():
                result.setdefault(race, set()).add(int(pp_str))
        except ValueError:
            raise ValueError(
                f"Bad scratch token '{tok}' — race and pp must be integers"
            )
    return result


def apply_scratches(df: pd.DataFrame,
                    scratches: dict[int, set[int]]) -> tuple[pd.DataFrame, list[str]]:
    """Drop scratched horses; renormalization happens downstream because
    evaluate_race re-normalizes model_w and market_w on the surviving field.
    Returns (filtered_df, info_lines for the report header)."""
    info: list[str] = []
    if not scratches:
        return df, info
    df_pp = pd.to_numeric(df["pp"], errors="coerce")
    drop_mask = pd.Series(False, index=df.index)
    for race, pps in sorted(scratches.items()):
        race_rows = df[df["race_id"] == race]
        if race_rows.empty:
            info.append(f"  ! Race {race}: not on card — scratch ignored")
            continue
        for pp in sorted(pps):
            hit = race_rows[df_pp.loc[race_rows.index] == pp]
            if hit.empty:
                info.append(
                    f"  ! Race {race} PP {pp}: not in field — scratch ignored"
                )
                continue
            name = str(hit["horse_name"].iloc[0])
            info.append(f"  SCR  Race {race}  PP {pp}  {name}")
            drop_mask |= (df["race_id"] == race) & (df_pp == pp)
    return df[~drop_mask].reset_index(drop=True), info


# ── live odds drift ───────────────────────────────────────────────────────────

# Drift = live_implied_prob / ml_implied_prob. Both are raw 1/decimal — the
# overround on tote vs ML is similar enough that the ratio is mostly real
# movement, not bookkeeping.
SHARP_THRESHOLD = 1.30
DRIFT_THRESHOLD = 0.70


def parse_live_odds_inline(s: str) -> dict[int, dict[int, float]]:
    """Parse 'R1:1=2.5,3=4.0;R2:5=3.0' → {1: {1: 2.5, 3: 4.0}, 2: {5: 3.0}}."""
    result: dict[int, dict[int, float]] = {}
    if not s:
        return result
    for race_block in s.split(";"):
        race_block = race_block.strip()
        if not race_block:
            continue
        if ":" not in race_block:
            raise ValueError(
                f"Bad live-odds block '{race_block}' — "
                f"expected R<race>:<pp>=<odds>,..."
            )
        race_part, entries = race_block.split(":", 1)
        try:
            race = int(race_part.strip().lstrip("Rr"))
        except ValueError:
            raise ValueError(f"Bad race in '{race_block}' — must be integer")
        for entry in entries.split(","):
            entry = entry.strip()
            if not entry:
                continue
            if "=" not in entry:
                raise ValueError(
                    f"Bad live-odds entry '{entry}' in R{race} — "
                    f"expected <pp>=<odds>"
                )
            pp_str, odds_str = entry.split("=", 1)
            try:
                pp = int(pp_str.strip().lstrip("Pp"))
                odds = float(odds_str.strip())
            except ValueError:
                raise ValueError(
                    f"Bad live-odds entry '{entry}' in R{race} — "
                    f"pp must be int, odds decimal"
                )
            if odds <= 1.0:
                raise ValueError(
                    f"Bad odds {odds} for R{race} PP{pp} — "
                    f"must be decimal >1.0"
                )
            result.setdefault(race, {})[pp] = odds
    return result


def parse_live_odds_file(path: Path) -> dict[int, dict[int, float]]:
    """Parse a file of 'R1 PP1 2.5' or 'R1 1 2.5' lines. '#' starts a comment."""
    if not path.exists():
        raise ValueError(f"Live-odds file not found: {path}")
    result: dict[int, dict[int, float]] = {}
    for lineno, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 3:
            raise ValueError(
                f"{path.name}:{lineno}: expected 'R<race> [PP]<pp> <odds>', "
                f"got '{raw}'"
            )
        try:
            race = int(parts[0].lstrip("Rr"))
            pp = int(parts[1].lstrip("Pp"))
            odds = float(parts[2])
        except ValueError:
            raise ValueError(
                f"{path.name}:{lineno}: race/pp must be int, odds decimal — "
                f"got '{raw}'"
            )
        if odds <= 1.0:
            raise ValueError(
                f"{path.name}:{lineno}: odds {odds} must be decimal >1.0"
            )
        result.setdefault(race, {})[pp] = odds
    return result


def merge_live_odds(*sources: dict[int, dict[int, float]]) -> dict[int, dict[int, float]]:
    """Merge multiple {race: {pp: odds}} dicts; later sources override earlier."""
    merged: dict[int, dict[int, float]] = {}
    for src in sources:
        for race, pps in src.items():
            merged.setdefault(race, {}).update(pps)
    return merged


def classify_drift(ml_decimal: float, live_decimal: float) -> tuple[str, str, float]:
    """Return (icon, label, ratio). ratio = live_implied / ml_implied."""
    ml_p = 1.0 / ml_decimal
    live_p = 1.0 / live_decimal
    ratio = live_p / ml_p
    if ratio >= SHARP_THRESHOLD:
        return "📉", "SHARP MONEY", ratio
    if ratio <= DRIFT_THRESHOLD:
        return "📈", "DRIFTING", ratio
    return "➡️", "STABLE", ratio


# ── scratch / live-odds collisions ────────────────────────────────────────────

def warn_missing_live_odds(df: pd.DataFrame,
                           live_odds: dict[int, dict[int, float]]) -> list[str]:
    """Return warning lines for live-odds entries that reference races or
    PPs not present in the (post-scratch) field."""
    if not live_odds:
        return []
    warnings: list[str] = []
    df_pp = pd.to_numeric(df["pp"], errors="coerce")
    races_in_df = set(df["race_id"].unique().tolist())
    for race, pps in sorted(live_odds.items()):
        if race not in races_in_df:
            warnings.append(
                f"  ! Live odds for R{race}: race not on card — ignored"
            )
            continue
        race_pps = set(df_pp[df["race_id"] == race].dropna().astype(int).tolist())
        for pp in sorted(pps):
            if pp not in race_pps:
                warnings.append(
                    f"  ! Live odds for R{race} PP{pp}: not in field "
                    f"(scratched?) — ignored"
                )
    return warnings


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
                "horse_starts": h.get("horse_starts"),
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
           top_per_race: int = 5,
           scratch_info: list[str] | None = None,
           live_odds: dict[int, dict[int, float]] | None = None,
           use_live_odds: bool = False,
           live_odds_warnings: list[str] | None = None) -> str:
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
    if scratch_info:
        out.append("")
        out.append("Scratches applied (field reduced before Harville):")
        out.extend(scratch_info)
    if live_odds:
        n_entries = sum(len(v) for v in live_odds.values())
        mode = ("EVs recalculated with live odds where provided"
                if use_live_odds
                else "Drift only — EVs still use ML (pass --use-live-odds to swap)")
        out.append("")
        out.append(f"Live odds: {n_entries} entries across "
                   f"{len(live_odds)} race(s) — {mode}")
        if live_odds_warnings:
            out.extend(live_odds_warnings)

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
        race_live = (live_odds or {}).get(int(rn), {})

        # Snapshot ML before any swap so the drift block always compares
        # against the original morning line.
        ml_snapshot = race_df.set_index(
            pd.to_numeric(race_df["pp"], errors="coerce").astype("Int64")
        )["ml_odds"].to_dict()

        if use_live_odds and race_live:
            df_pp = pd.to_numeric(race_df["pp"], errors="coerce")
            for pp, live_dec in race_live.items():
                race_df.loc[df_pp == pp, "ml_odds"] = live_dec

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
        market_label = "live" if (use_live_odds and race_live) else "ML"
        out.append(f"  Model favorite: PP {pps[top1]} {horses[top1]}  "
                   f"model {model_w[top1] * 100:.1f}%  vs  "
                   f"market({market_label}) {market_w[top1] * 100:.1f}%")

        if race_live:
            out.append("  Live drift:")
            top1_drift = None
            for i in range(len(race_df)):
                pp_i = pps[i]
                if not isinstance(pp_i, int) or pp_i not in race_live:
                    continue
                ml_dec = ml_snapshot.get(pp_i)
                if ml_dec is None or pd.isna(ml_dec):
                    continue
                live_dec = race_live[pp_i]
                icon, label, ratio = classify_drift(float(ml_dec), live_dec)
                ml_pct = (1.0 / float(ml_dec)) * 100
                live_pct = (1.0 / live_dec) * 100
                out.append(
                    f"    PP {pp_i:<3d}{horses[i]:<20}"
                    f"ML {float(ml_dec):>5.1f} → live {live_dec:>5.1f}  "
                    f"({ml_pct:>4.1f}% → {live_pct:>4.1f}%)  "
                    f"×{ratio:.2f}  {icon} {label}"
                )
                if i == top1:
                    top1_drift = (label, ratio)
            if top1_drift is not None:
                label, ratio = top1_drift
                if label == "SHARP MONEY":
                    out.append(f"  ⚠️  Top pick PP {pps[top1]} hammered by "
                               f"public (×{ratio:.2f}) — edge likely captured")
                elif label == "DRIFTING":
                    out.append(f"  🔥 Top pick PP {pps[top1]} drifting "
                               f"(×{ratio:.2f}) — public fading, "
                               f"value increasing if model right")

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
    ap.add_argument("--scratches", default="",
                    help="Comma-separated scratches as R<race>:<pp> pairs, "
                         "e.g. 'R4:7,R7:3'. Use '+' for multiple in one race: "
                         "'R4:3+5'. Removes horses before EV calc; remaining "
                         "win/exotic/Pick N probs renormalize over the "
                         "reduced field.")
    ap.add_argument("--live-odds", default="",
                    help="Inline live decimal odds: 'R1:1=2.5,3=4.0;R2:5=3.0'. "
                         "Drift is flagged vs ML in the PP file.")
    ap.add_argument("--live-odds-file", default="",
                    help="Path to live-odds file. One entry per line: "
                         "'R1 PP1 2.5' (or 'R1 1 2.5'). '#' starts a comment. "
                         "Merged with --live-odds; inline overrides file.")
    ap.add_argument("--use-live-odds", action="store_true",
                    help="Substitute live odds for ML in the EV calc for any "
                         "horse with a live entry. Horses without live data "
                         "keep their ML odds.")
    args = ap.parse_args()

    try:
        scratches = parse_scratches(args.scratches)
    except ValueError as e:
        sys.exit(str(e))

    try:
        live_from_file = (parse_live_odds_file(Path(args.live_odds_file))
                          if args.live_odds_file else {})
        live_from_inline = parse_live_odds_inline(args.live_odds)
    except ValueError as e:
        sys.exit(str(e))
    live_odds = merge_live_odds(live_from_file, live_from_inline)

    if args.use_live_odds and not live_odds:
        sys.exit("--use-live-odds requires --live-odds or --live-odds-file.")

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

    df, scratch_info = apply_scratches(df, scratches)
    if df.empty:
        sys.exit("All horses scratched — nothing left to evaluate.")
    if scratch_info:
        for line in scratch_info:
            print(line.strip())

    live_odds_warnings = warn_missing_live_odds(df, live_odds)
    for line in live_odds_warnings:
        print(line.strip())

    report = render(track, race_date, pp_file, bundle, df,
                    args.min_ev, args.min_prob, args.mandatory, args.top,
                    scratch_info=scratch_info,
                    live_odds=live_odds,
                    use_live_odds=args.use_live_odds,
                    live_odds_warnings=live_odds_warnings)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"EXOTICS_{track}_{race_date.strftime('%Y%m%d')}.txt"
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"Saved → {out_path.relative_to(SCRIPT_DIR.parent)}")


if __name__ == "__main__":
    main()
