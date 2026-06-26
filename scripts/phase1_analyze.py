"""Phase 1 analysis: turn recon JSON into report-ready tables and cross-references."""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"C:/Users/bornr/OneDrive/Documents/GitHub Files/benter-model-data")
OUT = ROOT / "scripts"

data = json.loads((OUT / "phase1_recon.json").read_text())
res = data["results"]
pp = data["pps"]

# --- Track code mapping table ---
# Lowercase 2023 result codes vs. uppercase PP codes (mostly the same)
result_tracks = Counter()
for key in res["track_day_races"]:
    trk, _ = key.split("|")
    result_tracks[trk] += 1
pp_tracks = Counter()
for key in pp["track_date_pp"]:
    trk, _ = key.split("|")
    pp_tracks[trk] += 1

# Build matched/orphan summary
result_keys = set(res["track_day_races"].keys())  # "track|date" lowercase
pp_keys = set(pp["track_date_pp"].keys())  # "TRACK|date" uppercase

# Normalize for cross-reference: lowercase track + date
def norm_pp(k):
    t, d = k.split("|")
    return f"{t.lower()}|{d}"
def norm_res(k):
    return k  # already lowercase

result_norm = {norm_res(k) for k in result_keys}
pp_norm = {norm_pp(k) for k in pp_keys}

both = result_norm & pp_norm
res_only = result_norm - pp_norm  # races we have results for but no PP
pp_only = pp_norm - result_norm  # PP cards with no result file

print(f"Result race-days: {len(result_norm)}")
print(f"PP race-days: {len(pp_norm)}")
print(f"Both (PP + result): {len(both)}")
print(f"Result only (no PP): {len(res_only)}")
print(f"PP only (no result): {len(pp_only)}")

# Sample 10 res_only and 10 pp_only
print("\nSample 10 'result only' (no PP found):")
for k in sorted(res_only)[:10]:
    print(f"  {k}")
print("\nSample 10 'PP only' (no result found):")
for k in sorted(pp_only)[:10]:
    print(f"  {k}")

# Track coverage for Doug's tracks + majors
DOUG = ["gp", "ct", "evd", "fp", "fg", "mnr", "mvr", "sa", "sar", "dmr", "op"]
MAJORS = ["aqu", "bel", "cd", "kee", "lrl", "del", "tam", "haw", "lad", "lrc", "pim", "prx", "tdn", "wo", "ind", "mth", "prm", "rp", "tp"]

print("\n=== Doug's tracks — race-day counts ===")
print(f"{'track':<6} {'result_days':<13} {'pp_days':<10} {'matched':<10} {'res_only':<10} {'pp_only':<10}")
for trk in DOUG + MAJORS:
    res_days = sum(1 for k in result_norm if k.startswith(f"{trk}|"))
    pp_days = sum(1 for k in pp_norm if k.startswith(f"{trk}|"))
    matched_days = sum(1 for k in both if k.startswith(f"{trk}|"))
    ro = sum(1 for k in res_only if k.startswith(f"{trk}|"))
    po = sum(1 for k in pp_only if k.startswith(f"{trk}|"))
    print(f"{trk:<6} {res_days:<13} {pp_days:<10} {matched_days:<10} {ro:<10} {po:<10}")

# Field size histogram summary
print("\n=== Field size distribution ===")
fs = res["field_size_hist"]
total_races = sum(int(v) for v in fs.values())
for k in sorted(fs.keys(), key=int):
    n = fs[k]
    pct = 100 * n / total_races
    print(f"  {int(k):>3} horses: {n:>6} races ({pct:5.1f}%)")

# Race type distribution (top 25)
print("\n=== Top 25 race types ===")
rt = res["race_type_hist"]
for k, v in sorted(rt.items(), key=lambda x: -x[1])[:25]:
    print(f"  {v:>6}  {k}")

# Surface distribution
print("\n=== Surface distribution ===")
for k, v in sorted(res["surface_hist"].items(), key=lambda x: -x[1]):
    print(f"  {v:>6}  {repr(k)}")

# Course distribution
print("\n=== Course distribution ===")
for k, v in sorted(res["course_hist"].items(), key=lambda x: -x[1]):
    print(f"  {v:>6}  {repr(k)}")

# Breed distribution
print("\n=== Breed distribution ===")
for k, v in sorted(res["breed_hist"].items(), key=lambda x: -x[1]):
    print(f"  {v:>6}  {repr(k)}")

# DOLLAR_ODDS coverage
total_entries = res["total_entries"]
print(f"\n=== Tote-odds coverage ===")
print(f"  Entries with DOLLAR_ODDS > 0: {res['entries_with_dollar_odds_nonzero']} / {total_entries} "
      f"({100*res['entries_with_dollar_odds_nonzero']/total_entries:.1f}%)")
print(f"  Entries with POINT_OF_CALL block: {res['entries_with_point_of_call']} / {total_entries}")
print(f"  Entries with non-zero SPEED_RATING: {res['entries_with_nonzero_speed_rating']} / {total_entries} "
      f"({100*res['entries_with_nonzero_speed_rating']/total_entries:.1f}%)")
print(f"  Races with non-empty PACE_CALL1: {res['races_with_pace_call']} / {res['total_races']} "
      f"({100*res['races_with_pace_call']/res['total_races']:.1f}%)")

# Schema sample
print(f"\n=== Sample RACE fields ({len(res['sample_fields_per_race'])}) ===")
print(", ".join(res["sample_fields_per_race"]))
print(f"\n=== Sample ENTRY fields ({len(res['sample_fields_per_entry'])}) ===")
print(", ".join(res["sample_fields_per_entry"]))

# Malformed files
print(f"\n=== Malformed files: {len(res['malformed_files'])} ===")
for fn, err in res["malformed_files"][:20]:
    print(f"  {fn}: {err}")

# Save derived data
derived = {
    "result_days": len(result_norm),
    "pp_days": len(pp_norm),
    "both_days": len(both),
    "res_only_days": len(res_only),
    "pp_only_days": len(pp_only),
    "doug_coverage": {},
    "majors_coverage": {},
    "result_only_sample": sorted(res_only)[:25],
    "pp_only_sample": sorted(pp_only)[:25],
}
for trk in DOUG:
    derived["doug_coverage"][trk] = {
        "result_days": sum(1 for k in result_norm if k.startswith(f"{trk}|")),
        "pp_days": sum(1 for k in pp_norm if k.startswith(f"{trk}|")),
        "matched_days": sum(1 for k in both if k.startswith(f"{trk}|")),
    }
for trk in MAJORS:
    derived["majors_coverage"][trk] = {
        "result_days": sum(1 for k in result_norm if k.startswith(f"{trk}|")),
        "pp_days": sum(1 for k in pp_norm if k.startswith(f"{trk}|")),
        "matched_days": sum(1 for k in both if k.startswith(f"{trk}|")),
    }
(OUT / "phase1_derived.json").write_text(json.dumps(derived, indent=2))
print(f"\nWrote {OUT / 'phase1_derived.json'}")
