"""Phase 1 filter pass: apply TB-flat inclusion rules and rebuild stats.

Rules:
  - BREED = 'TB'
  - COURSE_DESC in {Dirt, Turf, All Weather Track, Inner turf, Outer turf, Downhill turf}
  - Exclude track code 'cmr' (Camarero / Puerto Rico)
"""
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"C:/Users/bornr/OneDrive/Documents/GitHub Files/benter-model-data")
RESULTS_DIR = ROOT / "2023 Result Charts"
OUT_DIR = ROOT / "scripts"

EXCLUDE_TRACK = {"cmr"}
FLAT_COURSES = {"Dirt", "Turf", "All Weather Track", "Inner turf",
                "Outer turf", "Downhill turf"}

RESULT_FNAME = re.compile(r"^([a-z]{2,4})(\d{8})tch\.xml$")


def main():
    files = sorted(os.listdir(RESULTS_DIR))
    track_day_races_kept = defaultdict(int)
    track_day_races_dropped = defaultdict(int)
    track_day_entries_kept = defaultdict(int)
    field_size_hist = Counter()
    surface_hist = Counter()
    course_hist = Counter()
    race_type_hist = Counter()
    total_files = 0
    total_races_in = 0
    total_races_kept = 0
    total_entries_in = 0
    total_entries_kept = 0
    breed_in = Counter()
    drop_reason = Counter()

    for fn in files:
        m = RESULT_FNAME.match(fn)
        if not m:
            continue
        track, ymd = m.group(1), m.group(2)
        date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
        total_files += 1

        if track in EXCLUDE_TRACK:
            # Even if we drop, we still need to count races dropped
            try:
                tree = ET.parse(RESULTS_DIR / fn)
            except ET.ParseError:
                continue
            for race in tree.getroot().findall("RACE"):
                total_races_in += 1
                entries = race.findall("ENTRY")
                total_entries_in += len(entries)
                track_day_races_dropped[(track, date)] += 1
                drop_reason["cmr_track"] += 1
                breed_in[(race.findtext("BREED") or "").strip()] += 1
            continue

        try:
            tree = ET.parse(RESULTS_DIR / fn)
        except ET.ParseError:
            continue

        for race in tree.getroot().findall("RACE"):
            total_races_in += 1
            entries = race.findall("ENTRY")
            total_entries_in += len(entries)
            breed = (race.findtext("BREED") or "").strip()
            breed_in[breed] += 1
            course = (race.findtext("COURSE_DESC") or "").strip()
            if breed != "TB":
                drop_reason[f"breed_{breed}"] += 1
                continue
            if course not in FLAT_COURSES:
                drop_reason[f"course_{course}"] += 1
                continue

            # Kept
            total_races_kept += 1
            total_entries_kept += len(entries)
            track_day_races_kept[(track, date)] += 1
            track_day_entries_kept[(track, date)] += len(entries)
            field_size_hist[len(entries)] += 1
            surface_hist[(race.findtext("SURFACE") or "").strip()] += 1
            course_hist[course] += 1
            race_type_hist[(race.findtext("TYPE") or "").strip()] += 1

    # Reduce track-day matrix
    track_days_kept = defaultdict(int)
    track_races_kept = defaultdict(int)
    track_entries_kept = defaultdict(int)
    for (t, d), n in track_day_races_kept.items():
        track_days_kept[t] += 1
        track_races_kept[t] += n
        track_entries_kept[t] += track_day_entries_kept[(t, d)]

    out = {
        "total_files": total_files,
        "total_races_in": total_races_in,
        "total_races_kept": total_races_kept,
        "total_entries_in": total_entries_in,
        "total_entries_kept": total_entries_kept,
        "field_size_hist": dict(field_size_hist),
        "surface_hist": dict(surface_hist),
        "course_hist": dict(course_hist),
        "race_type_hist": dict(race_type_hist),
        "breed_in": dict(breed_in),
        "drop_reason": dict(drop_reason),
        "track_days_kept": dict(track_days_kept),
        "track_races_kept": dict(track_races_kept),
        "track_entries_kept": dict(track_entries_kept),
    }
    (OUT_DIR / "phase1_filtered.json").write_text(json.dumps(out, indent=2))
    print(f"Files surveyed: {total_files}")
    print(f"Races in: {total_races_in} -> kept: {total_races_kept} "
          f"({100*total_races_kept/total_races_in:.1f}%)")
    print(f"Entries in: {total_entries_in} -> kept: {total_entries_kept} "
          f"({100*total_entries_kept/total_entries_in:.1f}%)")
    print(f"\nDrop reasons:")
    for r, c in sorted(out["drop_reason"].items(), key=lambda x: -x[1]):
        print(f"  {c:>6}  {r}")
    print(f"\nTop kept tracks (by race-days):")
    for t, n in sorted(track_days_kept.items(), key=lambda x: -x[1])[:30]:
        print(f"  {t:<5} {n:>4} days  {track_races_kept[t]:>5} races  {track_entries_kept[t]:>6} entries")
    print(f"\nKept field size:")
    fs_total = sum(field_size_hist.values())
    for k in sorted(field_size_hist.keys()):
        n = field_size_hist[k]
        print(f"  {k:>3}: {n:>5} ({100*n/fs_total:5.1f}%)")
    print(f"\nKept course:")
    for k, v in sorted(course_hist.items(), key=lambda x: -x[1]):
        print(f"  {v:>6}  {k}")
    print(f"\nWrote {OUT_DIR / 'phase1_filtered.json'}")


if __name__ == "__main__":
    main()
