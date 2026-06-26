"""Phase 1 recon: survey 2023 Equibase data.

Walks all 4,906 result chart XMLs and ~5,918 PP zips to produce
the inputs for scripts/PHASE_1_RECON.md. Read-only. No model code.
"""
import os
import re
import json
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"C:/Users/bornr/OneDrive/Documents/GitHub Files/benter-model-data")
RESULTS_DIR = ROOT / "2023 Result Charts"
PP_DIR = ROOT / "2023 PP's Files"
OUT_DIR = ROOT / "scripts"

# Filename pattern: [track][YYYYMMDD]tch.xml — track is 2-4 lowercase letters
RESULT_FNAME = re.compile(r"^([a-z]{2,4})(\d{8})tch\.xml$")
# PP zip: SIMD[YYYYMMDD][TRACK]_[COUNTRY].zip — track is 2-4 uppercase letters
PP_FNAME = re.compile(r"^SIMD(\d{8})([A-Z]{2,4})_([A-Z]{2,3})\.zip$")


def survey_results():
    files = sorted(os.listdir(RESULTS_DIR))
    rows = []
    malformed = []
    field_size_hist = Counter()
    race_type_hist = Counter()
    surface_hist = Counter()
    course_hist = Counter()
    breed_hist = Counter()
    track_day_races = defaultdict(int)  # (track, date) -> race count
    track_day_starters = defaultdict(int)
    has_dollar_odds = 0
    has_point_of_call = 0
    has_pace_call = 0
    has_speed_rating = 0
    nonzero_speed_count = 0
    sample_fields_per_race = None
    sample_fields_per_entry = None
    nonthoroughbred_skipped = 0
    bad_pattern = []

    for fn in files:
        m = RESULT_FNAME.match(fn)
        if not m:
            bad_pattern.append(fn)
            continue
        track, ymd = m.group(1), m.group(2)
        date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
        path = RESULTS_DIR / fn
        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except ET.ParseError as e:
            malformed.append((fn, f"ParseError: {e}"))
            continue

        # CHART root
        if root.tag != "CHART":
            malformed.append((fn, f"unexpected root tag: {root.tag}"))
            continue

        races = root.findall("RACE")
        if not races:
            malformed.append((fn, "no RACE elements"))
            continue

        track_day_races[(track, date)] = len(races)

        for race in races:
            if sample_fields_per_race is None:
                sample_fields_per_race = sorted({c.tag for c in race})
            breed = (race.findtext("BREED") or "").strip()
            breed_hist[breed] += 1
            rtype = (race.findtext("TYPE") or "").strip()
            race_type_hist[rtype] += 1
            surf = (race.findtext("SURFACE") or "").strip()
            surface_hist[surf] += 1
            crs = (race.findtext("COURSE_DESC") or "").strip()
            course_hist[crs] += 1

            entries = race.findall("ENTRY")
            field_size_hist[len(entries)] += 1
            track_day_starters[(track, date)] += len(entries)

            for ent in entries:
                if sample_fields_per_entry is None:
                    sample_fields_per_entry = sorted({c.tag for c in ent})
                do = ent.findtext("DOLLAR_ODDS")
                if do and do not in ("0.00", "0", ""):
                    has_dollar_odds += 1
                if ent.find("POINT_OF_CALL") is not None:
                    has_point_of_call += 1
                sr = ent.findtext("SPEED_RATING")
                if sr is not None:
                    has_speed_rating += 1
                    try:
                        if float(sr) != 0:
                            nonzero_speed_count += 1
                    except ValueError:
                        pass

            if race.findtext("PACE_CALL1") and race.findtext("PACE_CALL1") not in ("", "0", "-97"):
                has_pace_call += 1

    return {
        "file_count": len(files),
        "bad_pattern_count": len(bad_pattern),
        "malformed_files": malformed,
        "total_races": sum(field_size_hist.values()),
        "total_entries": sum(k * v for k, v in field_size_hist.items()),
        "field_size_hist": dict(field_size_hist),
        "race_type_hist": dict(race_type_hist),
        "surface_hist": dict(surface_hist),
        "course_hist": dict(course_hist),
        "breed_hist": dict(breed_hist),
        "track_day_races": {f"{t}|{d}": n for (t, d), n in track_day_races.items()},
        "track_day_starters": {f"{t}|{d}": n for (t, d), n in track_day_starters.items()},
        "sample_fields_per_race": sample_fields_per_race,
        "sample_fields_per_entry": sample_fields_per_entry,
        "entries_with_dollar_odds_nonzero": has_dollar_odds,
        "entries_with_point_of_call": has_point_of_call,
        "entries_with_speed_rating_field": has_speed_rating,
        "entries_with_nonzero_speed_rating": nonzero_speed_count,
        "races_with_pace_call": has_pace_call,
    }


def survey_pps():
    files = sorted(os.listdir(PP_DIR))
    zips, dirs, others = [], [], []
    for fn in files:
        p = PP_DIR / fn
        if p.is_dir():
            dirs.append(fn)
        elif fn.endswith(".zip"):
            zips.append(fn)
        else:
            others.append(fn)

    track_date_pp = defaultdict(list)  # (TRACK, date) -> [country]
    countries = Counter()
    bad_pattern = []
    for fn in zips:
        m = PP_FNAME.match(fn)
        if not m:
            bad_pattern.append(fn)
            continue
        ymd, trk, country = m.group(1), m.group(2), m.group(3)
        date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
        track_date_pp[(trk, date)].append(country)
        countries[country] += 1

    return {
        "total_entries": len(files),
        "zip_count": len(zips),
        "dir_count": len(dirs),
        "other_count": len(others),
        "bad_pattern": bad_pattern,
        "countries": dict(countries),
        "track_date_pp": {f"{t}|{d}": cs for (t, d), cs in track_date_pp.items()},
    }


def main():
    print("Surveying results...")
    res = survey_results()
    print(f"  files={res['file_count']} races={res['total_races']} entries={res['total_entries']}")

    print("Surveying PPs...")
    pp = survey_pps()
    print(f"  entries={pp['total_entries']} zips={pp['zip_count']} dirs={pp['dir_count']}")

    out = {"results": res, "pps": pp}
    (OUT_DIR / "phase1_recon.json").write_text(json.dumps(out, indent=2))
    print(f"Wrote {OUT_DIR / 'phase1_recon.json'}")


if __name__ == "__main__":
    main()
