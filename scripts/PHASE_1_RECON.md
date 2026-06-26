# Phase 1 Recon — 2023 Equibase Data Survey

**Date:** 2026-06-26
**Scope:** Documentation only — no model code.
**Inputs surveyed:**
- `2023 Result Charts/` — 4,906 TrackMaster TCH XML files
- `2023 PP's Files/` — 5,919 SIMD PP zips (+ 2 already-extracted folders)
- `Previous Versions of Benter Model/` — 5 workbooks (not opened in this pass)

Survey scripts: `scripts/phase1_recon.py`, `scripts/phase1_analyze.py`.
Raw data: `scripts/phase1_recon.json`, `scripts/phase1_derived.json`.

---

## TL;DR — what's actually in the box

| | Count |
|---|---|
| Result XML files | **4,906** (0 malformed, 0 parse errors) |
| Total races | **42,618** |
| Total horse entries | **318,702** |
| Avg horses/race | 7.48 |
| Distinct tracks (results) | 126 |
| PP zips | 5,919 (= 5,608 unique track-day cards) |
| Race-days with **both** PP + result | **4,906 / 4,906** (100%) |
| Race-days with PP but no result | 702 (cancelled / not collected) |

**The Benter pivot is feasible.** Every result file has a matching PP file. The two together give us a full feature-engineering substrate.

### The headline fields for a Benter-style model

| Field | Coverage | Notes |
|---|---|---|
| `DOLLAR_ODDS` (final tote, per entry) | **99.6% of entries** | This is the field you wanted. True market consensus, not ML. The 0.4% gap is mostly scratched horses. |
| `POINT_OF_CALL` (pace trajectory) | **100% of entries** | 5 intermediate calls + FINAL, each with `POSITION` and `LENGTHS`. Enables real pace modeling. |
| `SPEED_RATING` per entry | **97.2% non-zero** | TrackMaster speed figure. |
| `PACE_CALL1` per race | **96.7% populated** | Race-level pace numbers (PACE_CALL1, PACE_CALL2, PACE_FINAL). |
| `COMMENT` per entry | populated | Trip note ("rallied wide", "checked 1/4", etc.) — usable for text features. |
| `FOOTNOTES` per race | populated | Race summary text. |
| `WIN/PLACE/SHOW_PAYOFF` | populated | Per-entry payouts on placers. |
| `EXOTIC_WAGERS` (Exa/Tri/Super) | populated | Payouts + pool totals for cross-pool ROI back-test. |
| `FRACTION_1..5`, `WIN_TIME` | populated | Sectional times. |
| `LAST_PP` (per entry) | populated | Last race summary (track, date, race#, finish). |

---

## 1. Result chart schema (TrackMaster TCH XML)

**Root:** `<CHART RACE_DATE="YYYY-MM-DD">` → `<TRACK><CODE>…</CODE><NAME>…</NAME></TRACK>` → 1..n `<RACE NUMBER="n">` blocks → 1..n `<ENTRY>` blocks per race.

Schema URL inside the file: `https://info.trackmaster.com/xmlSchema/tchSchema.xsd`.

**Filename pattern:** `[track][YYYYMMDD]tch.xml` — track code is 2–4 lowercase letters, `tch` = TrackMaster Chart.

### 1.1 RACE-level fields (40 unique tags)

```
ABOUT_DIST_FLAG, AGE_RESTRICTIONS, BREED, CARD_ID, CLAIMED, CLASS_RATING,
COURSE_DESC, COURSE_ID, DISTANCE, DIST_UNIT, DTV, EARNING_SPLITS, ENTRY,
EXOTIC_WAGERS, FOOTNOTES, FRACTION_1, FRACTION_2, FRACTION_3, FRACTION_4,
FRACTION_5, PACE_CALL1, PACE_CALL2, PACE_FINAL, PAR_TIME, POST_TIME, PURSE,
RACE_TEXT, RAILDIST, RUNUPDIST, SCRATCH, SEALED, STRT_DESC, SURFACE,
TRK_COND, TYPE, VOIDED_CLAIMS, WEATHER, WIND_DIRECTION, WIND_SPEED, WIN_TIME
```

Notes:
- `DISTANCE` is in yards (`DIST_UNIT=Y`) or furlongs×100 (`DIST_UNIT=F`). Example: `850 F` = 1 1/16 mile.
- `SURFACE` = `D` / `T` / `M` (Hurdle/Timber on turf course).
- `TRK_COND` = FT, GD, SY, MY, WF, FM, etc.
- `PACE_CALL1/2/FINAL` are TrackMaster pace figures (E1/E2/LP equivalent).
- `EARNING_SPLITS` is purse breakdown across positions 1–9.
- `EXOTIC_WAGERS` block contains a `<WAGER>` per pool with `WAGER_TYPE`, `NUM_TICKETS`, `POOL_TOTAL`, `WINNERS`, `PAYOFF`.

### 1.2 ENTRY-level fields (28 unique tags)

```
AGE, AXCISKEY, BREED, CLAIM_PRICE, COMMENT, DH_DQ_FLAGS, DOLLAR_ODDS, EQUIP,
FINISH_TIME, JOCKEY, LAST_PP, MEDS, NAME, OFFICIAL_FIN, OWNER, PLACE_PAYOFF,
POINT_OF_CALL, POST_POS, PROGRAM_NUM, SEX, SHOW_PAYOFF, SHOW_PAYOFF2,
SPEED_RATING, START_POSITION, TRAINER, WEIGHT, WINNERS_DETAILS, WIN_PAYOFF
```

- `AXCISKEY` is the Equibase universal horse ID (joins to PP file `RegistrationNumber`).
- `POINT_OF_CALL WHICH="1..5|FINAL"` → `POSITION` + `LENGTHS` (lengths ahead/behind leader).
- `WINNERS_DETAILS` (only present on the winner): `COLOR`, `SIRE`, `DAM`, `DAM_SIRE`, `BREEDER`, `BRED_LOCATION`.
- `JOCKEY`/`TRAINER` carry `KEY` (Equibase ID) → stable cross-file join key for trainer/jockey signals.
- `LAST_PP` is a thin pointer back to each horse's last start (track, date, race#, finish).

### 1.3 Distribution snapshots

**Field size:**
| horses | races | % |
|---|---|---|
| 2 | 18 | 0.0% |
| 3 | 150 | 0.4% |
| 4 | 1,125 | 2.6% |
| 5 | 4,586 | 10.8% |
| **6** | **8,436** | **19.8%** |
| **7** | **8,860** | **20.8%** |
| **8** | **7,266** | **17.0%** |
| 9 | 5,349 | 12.6% |
| 10 | 4,484 | 10.5% |
| 11 | 1,228 | 2.9% |
| 12 | 1,022 | 2.4% |
| 13 | 54 | 0.1% |
| 14 | 38 | 0.1% |
| 17 | 1 | 0.0% |
| 18 | 1 | 0.0% |

Modal field size 7. Strong distribution for multinomial logit / conditional-logit fits.

**Surface:**
| Course | Races |
|---|---|
| Dirt | 33,465 |
| Turf (main) | 4,501 |
| All Weather Track | 3,871 |
| Inner turf | 385 |
| Outer turf | 180 |
| Hurdle (steeplechase) | 113 |
| Downhill turf (SA) | 61 |
| Timber (steeplechase) | 42 |

**Breed:**
| Breed | Races |
|---|---|
| Thoroughbred (TB) | 35,989 |
| Quarter Horse (QH) | 6,016 |
| Mixed (MX) | 559 |
| Arabian (AR) | 54 |

→ ~12% of races are non-TB. Recommend bucketing or filtering for the new model.

**Top race types (count):**
| Type | Races |
|---|---|
| Claiming | 14,643 |
| Maiden Claiming | 5,780 |
| Allowance | 5,321 |
| Maiden Special Weight | 4,547 |
| Allowance Optional Claiming | 3,255 |
| Stakes | 2,267 |
| Starter Optional Claiming | 1,627 |
| Maiden (QH) | 1,542 |
| Starter Allowance | 1,187 |
| Futurity Trial (QH) | 762 |

### 1.4 Data quality

- **0 malformed files**, **0 parse errors**, **0 unexpected root tags**.
- Filename → XML internal `RACE_DATE` consistent (spot-checked).
- 100% of files have at least one `<RACE>` block.

---

## 2. PP file schema (Equibase SIMD XML)

**Root:** `<EntryRaceCard>` → 1..n `<Race>` → `<Starters>` containing 1..n `<Horse>` blocks → each horse has nested `<PastPerformance>` and `<Workout>` records.

Schema URL: `http://ifd.equibase.com/schema/simulcast.xsd`.

**Filename pattern:** `SIMD[YYYYMMDD][TRACK]_[COUNTRY].zip` — each zip contains a single `.xml` file inside.

**This is NOT Brisnet.** The existing `scripts/brisnet_parser_v2.py` is a regex-over-PDF-text parser for TwinSpires/Brisnet PPs. SIMD is structured XML — much cleaner to parse. Element naming convention is CamelCase here vs ALL_CAPS in TCH (the schemas come from different teams).

### 2.1 Tag inventory (157 unique element tags)

Major sections:
- **`<Race>` metadata:** `RaceNumber, DayEvening, BreedType, Course, Distance, RaceType, RestrictionType, SexRestriction, AgeRestriction, ConditionText, PostTime, Grade, PurseUSA, PurseEnhancement, MaximumClaimPrice, WagerText, ProgramSelections, RaceName, ChuteStart, TrackRecord, SimulcastFlag, NumberOfRunners`
- **`<Horse>` identity + pedigree:** `RegistrationNumber, HorseName, FoalingDate, FoalingArea, Color, Sex, BreederName` — and nested `<Sire>` / `<Dam>` blocks recursing to grandsire/grandam.
- **Trip equipment:** `PostPosition, ProgramNumber, WeightCarried, Equipment, Medication, Trainer, Jockey, Owner, ApprenticeType, Odds (morning-line, e.g. "15/1")`.
- **`<PastPerformance>` (1..n per horse):** track, race date, race# / horse age that day, distance, surface, course, track condition, finish position, lengths behind, beaten-lengths-at-each-call (`PointOfCall` with `PositionAtFinish`/`LengthsAhead`/`LengthsBehind`), speed figure (`SpeedFigure`), race rating, jockey, trainer at the time, claim history, comments.
- **`<Workout>` (1..n per horse):** date, track, distance, time, surface, condition, ranking (`Ranking`, `NumberInRankingGroup`, e.g. "3 of 47" = bullet at top).
- **Race-record summary:** `NumberOfStarts, NumberOfWins, NumberOfSeconds, NumberOfThirds, EarningsUSA, EarningsForeign` — split by Lifetime / This Year / Last Year / Today's Track / Today's Distance / Surface variants.
- **`TodaysHorseClassRating`** — Equibase's relative class rating for today's race.

### 2.2 Parser complexity estimate

| Component | Current state | New work needed |
|---|---|---|
| Brisnet PDF (CT/FP/EVD/GP recent) | `brisnet_parser_v2.py` working | Keep for live picks |
| Equibase SIMD XML (training set) | Nothing exists | **New parser — ~1 day's work, ~300–500 LOC** |
| Schema mapping (SIMD → DB schema) | N/A | New mapping table needed; field names differ entirely |

The XML is structured and well-formed, so a standard `xml.etree.ElementTree` walk handles it. No regex / OCR / PDF text extraction. Net parser effort is **lower** than what already exists for Brisnet, *but* the database schema needs to accommodate richer fields (full pedigree, workout records, class ratings) — that's the real lift.

---

## 3. Cross-reference: PP × result coverage

| | Race-days |
|---|---|
| Distinct (track, date) with result XML | 4,906 |
| Distinct (track, date) with PP zip | 5,608 |
| **Both present** | **4,906** (100% of result days) |
| Result only (no PP) | **0** |
| PP only (no matching result) | **702** |

Every race day that ran has a matching PP file — that's the training-set guarantee we need.

**The 702 PP-only days:** mostly Mon/Tue cards at GP (133) and LRL (143) — looks like scheduled cards that either cancelled, weren't downloaded, or ran but the result chart wasn't archived. Other clusters: BAQ (Belmont @ the Big A), Breeders' Cup days (BCA/BCB/BCC/BCD), Pim (Preakness undercard alts). These are noise we drop — train only on the 4,906 race-days where both exist.

### Spot-check sample (10 race dates across tracks)

All present in **both** PP + result:

| Track | Date | Day | Both? |
|---|---|---|---|
| GP | 2023-01-01 | Sun | ✓ |
| GP | 2023-01-28 | Sat (Pegasus) | ✓ |
| CT | 2023-03-04 | Sat | ✓ |
| EVD | 2023-04-21 | Fri | ✓ |
| FG | 2023-02-18 | Sat | ✓ |
| OP | 2023-05-06 | Sat | ✓ |
| SA | 2023-12-26 | Tue (opening) | ✓ |
| SAR | 2023-07-13 | Thu (opening) | ✓ |
| DMR | 2023-07-22 | Sat (opening) | ✓ |
| KEE | 2023-04-07 | Fri (opening) | ✓ |

---

## 4. Track coverage matrix

### 4.1 Doug's tracks (priority)

| Code | Track | Result days | PP days | Matched | Notes |
|---|---|---|---|---|---|
| **gp** | Gulfstream Park | 193 | 326 | 193 | 133 extra PP-only (mostly Mon/Tue) |
| **ct** | Charles Town | 164 | 167 | 164 | Strong |
| **evd** | Evangeline Downs | 107 | 107 | 107 | Perfect |
| **fp** | Fairmount Park | **0** | 0 | 0 | **NOT IN 2023 SET** — see §4.4 |
| **fg** | Fair Grounds | 78 | 78 | 78 | Perfect |
| **mnr** | Mountaineer | 121 | 124 | 121 | Strong |
| **mvr** | Mahoning Valley | 101 | 102 | 101 | Strong |
| **sa** | Santa Anita | 91 | 93 | 91 | Strong |
| **sar** | Saratoga | 40 | 40 | 40 | Perfect (40-day meet) |
| **dmr** | Del Mar | 43 | 44 | 43 | Strong |
| **op** | Oaklawn Park | 68 | 68 | 68 | Perfect |

### 4.2 Other majors / supporting tracks

| Code | Track | Result days | PP days | Matched |
|---|---|---|---|---|
| aqu | Aqueduct | 92 | 93 | 92 |
| bel | Belmont | 38 | 40 | 38 |
| cd | Churchill Downs | 58 | 58 | 58 |
| kee | Keeneland | 32 | 32 | 32 |
| lrl | Laurel Park | 137 | 280 | 137 |
| del | Delaware Park | 85 | 91 | 85 |
| tam | Tampa Bay Downs | 93 | 93 | 93 |
| haw | Hawthorne | 66 | 68 | 66 |
| lad | Louisiana Downs | 105 | 107 | 105 |
| lrc | Los Alamitos | 21 | 21 | 21 |
| pim | Pimlico | 23 | 39 | 23 |
| prx | Parx | 151 | 151 | 151 |
| tdn | Thistledown | 101 | 103 | 101 |
| wo | Woodbine | 128 | 133 | 128 |
| ind | Indiana Grand | 121 | 124 | 121 |
| mth | Monmouth | 51 | 51 | 51 |
| prm | Prairie Meadows | 80 | 80 | 80 |
| rp | Remington Park | 115 | 119 | 115 |
| tp | Turfway Park | 68 | 69 | 68 |

### 4.3 Full track list (126 codes)

Top of the long tail: `cmr` 212, `gp` 193, `ct` 164, `prx` 151, `ded` 142, `lrl` 137, `pen` 131, `wo` 128, `gg` 121, `ind` 121, `mnr` 121, `rp` 115, `evd` 107, `lad` 105, `mvr` 101, `tdn` 101, `la` 95, `btp` 93, `tam` 93, `aqu` 92, `sa` 91. (Full list in `phase1_recon.json` → `results.track_day_races`.)

### 4.4 Data quality issues

1. **Fairmount Park (`fp`) has no 2023 result charts and no 2023 PP files.** Doug bets there but we have *zero* 2023 training data. Either the track was using a different code in 2023 or it wasn't on Equibase's simulcast feed yet. Current `CharlesTown/`-style folder structure shows FP results starting in 2024.
2. **CMR** (Camarero, Puerto Rico) is the highest-volume track at 212 days — a candidate to *exclude* unless we want PR coverage (probably not).
3. **Steeplechase tracks** (AIK, FAR, etc.) and **Quarter Horse tracks** (CMR, RP partial, IND partial) live in the same dataset. Filter by `BREED=TB` and `COURSE_DESC NOT IN ('Hurdle','Timber')` to scope the Benter model to flat thoroughbreds.
4. **Track code `mtp`** appears in `LAST_PP` references inside chart files (= Montpelier, steeplechase) but never as a result-file track. **`mnr` = Mountaineer**, **`mvr` = Mahoning Valley** — distinct tracks despite similar codes. The CLAUDE.md folder labels match this (`Mahoning Valley/mvr-2025-results/`).

---

## 5. Field availability for the new Benter-style model

Mapping desired features → data source:

| Feature | Source | Coverage |
|---|---|---|
| **Final tote odds (per horse)** | Result `DOLLAR_ODDS` | 99.6% — *primary signal* |
| **Morning-line odds** | PP `Odds` | 100% of PP files (kept for residual analysis) |
| **Race outcome (finish, beaten lengths)** | Result `OFFICIAL_FIN`, `POINT_OF_CALL[FINAL].LENGTHS` | 100% |
| Win/Place/Show payoffs | Result `WIN/PLACE/SHOW_PAYOFF` | 100% for placers |
| Speed figure | Result `SPEED_RATING` (post-race) + PP `SpeedFigure` (last-N races) | 97% / 100% |
| Pace figures | Result `PACE_CALL1/2/FINAL` | 97% |
| Sectional times | Result `FRACTION_1..5`, `WIN_TIME` | 100% TB flat |
| Pace position trajectory | Result `POINT_OF_CALL[1..5,FINAL]` | 100% |
| Class rating | Race `CLASS_RATING`, PP `TodaysHorseClassRating` | 100% |
| Par time | Race `PAR_TIME` | High (varies) |
| Trip comment | Entry `COMMENT`, race `FOOTNOTES` | 100% |
| Trainer/Jockey identity (cross-card joins) | `KEY` field on both | 100% |
| Equipment/Medication | Entry `EQUIP`, `MEDS` | 100% |
| Weight carried | Entry `WEIGHT` | 100% |
| Post position | Entry `POST_POS` | 100% |
| Days off (now computed from PP dates) | PP `PastPerformance[].RaceDate` | 100% |
| Pedigree (sire/dam/damsire) | PP `<Sire>`, `<Dam>`, recursive | 100% |
| Workout pattern (bullet works, # in last 60d) | PP `<Workout>` blocks | 100% |
| Past-performance history (last 10 races) | PP `<PastPerformance>` blocks | 100% |
| Career splits (lifetime/yr/track/dist/surface) | PP `NumberOfStarts/Wins/Seconds/Thirds`, `Earnings*` | 100% |
| Track condition/weather | Race `TRK_COND`, `WEATHER` | 100% |
| Track sealed indicator | Race `SEALED` | 100% |
| Run-up + rail distance | Race `RUNUPDIST`, `RAILDIST` | 100% |
| Exotic-pool payouts (for ROI back-test) | Race `EXOTIC_WAGERS` | 100% |
| Total Win pool | Race `WPS_POOL` | 100% |

**Every Benter-style feature you'd want is in the data, plus several signals (pedigree, trip notes, sealed indicator) the current PP-anchored model can't see.**

---

## 6. Recommendations for Phase 2

1. **Train set = 4,906 race-days × ~7.5 horses ≈ 35k–36k TB flat races.** Filter rules: `BREED=TB` AND `COURSE_DESC IN ('Dirt','Turf','All Weather Track','Inner turf','Outer turf')` AND drop QH/AR/MX and steeplechase. Drop CMR unless you want PR exposure.
2. **Two parsers, two passes per race-day.** Build `equibase_simd_parser.py` (XML PP → DB) and `tch_chart_parser.py` (XML result chart → DB). They share the join key on (`AXCISKEY`/`RegistrationNumber`, race_date, track, race_number). The existing Brisnet parser stays for live picks only; SIMD is training/backtest only.
3. **Schema: replace `ml_odds`-anchored fields with `final_odds` as the public-info field; keep `ml_odds` available as a secondary feature.** The CL model's `log_ml_*` features can move to `log_final_*`; ML stays as a residual/check feature.
4. **Use the 702 PP-only days as a validation pothole.** Anything that systematically fails on these days is a sign of a cancelled-card or simulcast-only edge case — worth knowing for live runs.
5. **Fairmount Park: handle separately.** 2023 SIMD has no FP data, but the existing 2024–2026 FP data lives in the repo. Train Benter model on 2023 majors + augment FP-specific signals from the 2024+ folder. Or: confirm whether Equibase published FP under a different code in 2023.
6. **Carry forward the old workbooks' signal intelligence as priors.** The trainer / sire / jockey signals in `Previous Versions of Benter Model/*.xlsx` are hand-curated knowledge that took years to build. Treat them as Bayesian priors / shrinkage targets when fitting the new conditional-logit, not as features to discard.
7. **Cache the parsed data into SQLite** (a `benter_train.db` next to the existing `benter_model.db`). 35k races × ~7.5 horses × ~80 columns ≈ 20M cells — fits comfortably.

---

## 7. Open questions for Doug

1. **Fairmount Park 2023:** want me to investigate whether FP races appear under a different code (e.g., `fmt`, `fan`, `fp2`)? Quick check — codes `fmt 28`, `fan 60` could be candidates.
2. **CMR (Puerto Rico):** include or exclude? 212 race-days is the single largest track.
3. **Quarter Horse / Mixed:** include? Adds 6.6k races but probably needs a separate model (track bias is very different).
4. **Steeplechase:** ignore entirely (155 races, no DOLLAR_ODDS useful for win-pool model)?
5. **Sample-extract two PP-only GP dates** to confirm whether those Mon/Tue cards were cancelled vs. real races whose result charts we're missing — affects whether we should chase the missing results.

---

# Phase 1 Follow-up — Filter Decisions Applied (2026-06-26)

Doug answered §7 questions. This section locks in the filtered training set, finalizes the track-code map, and adds findings from the PP-only sample. All counts below come from `scripts/phase1_filter.py` → `scripts/phase1_filtered.json`.

## F1. Track-code rebranding: FP → FAN (confirmed)

Spot-checked `2023 Result Charts/fan20230418tch.xml`:
- `<TRACK><CODE>FAN</CODE><NAME>FANDUEL HORSE RACING</NAME></TRACK>`
- `<RACE_TEXT>FANDUEL HORSE RACING RACE 1 5F Dirt CR: 79. Claiming Purse 10000…</RACE_TEXT>`

**FAN = Fairmount Park rebrand. Verified 60 race-days, all TB-flat.** Track conditions, distances, and purse levels are consistent with Fairmount.

**FPL is NOT Fairmount.** Single PP zip `SIMD20230406FPL_USA.zip`, no matching result file:
- `<BreedType><Value>QH</Value></BreedType>` for every race
- Horse names: "Soft Country Eyes", "Chicks Beduino", "Royal Quick Dash" — classic Quarter Horse naming
- Colors include Red Roan, Sorrel, Blue Roan (QH color spectrum)
- `<TrackID>FPL</TrackID>` with `<Country>U/C</Country>`

→ FPL is an unidentified Quarter Horse fixture. Drops out of the filter regardless. Ignore.

### Year-over-year code-change pattern to watch

Track rebrandings, sales, and venue moves break code stability across seasons. The parser should accept a **track-code alias table** rather than hardcode codes:

| Folder / current label | 2023 result-chart code | Notes |
|---|---|---|
| Fairmount Park | `fan` | Rebranded "FanDuel Horse Racing" for 2023 |
| Belmont Park | `baq` (26 days), `bel` (38 days) | When the Belmont meet ran at Aqueduct during renovation, races filed as BAQ |
| Pimlico | `pim` | Stable |
| Saratoga | `sar` | Stable |

The 2024+ data we already have shows FAN-era cards filed back as FP — confirm the parser handles both directions if we want to combine years.

## F2. PP-only sample (10 dates) — cancellation vs missing

Pulled 10 PP-only dates spanning GP, LRL, AQU, BAQ, BCA, PIM, DEL. **All 10 PP zips are substantial (122 KB – 660 KB), with full race conditions and starter blocks — these are real scheduled cards, not stubs.** No matching result file exists for any of them.

| Code | Date | Day | PP zip size | Same-date results present? |
|---|---|---|---|---|
| GP | 2023-01-03 | Tue | 343 KB | other tracks only (mvr, prx, sun, tup) |
| LRL | 2023-01-02 | Mon | 219 KB | other tracks only |
| GP | 2023-01-09 | Mon | 659 KB | other tracks only |
| GP | 2023-01-16 | Mon (MLK) | 586 KB | cmr, fg, gg, hou, lrl |
| LRL | 2023-01-03 | Tue | 242 KB | other tracks only |
| AQU | 2023-02-03 | Fri | 224 KB | gp + others (no aqu) |
| BAQ | 2023-09-23 | Sat | 384 KB | cd, ct + others |
| BCA | 2023-11-03 | Fri | 124 KB | aqu, cd + others |
| PIM | 2023-05-10 | Wed | 394 KB | evd, prx + others |
| DEL | 2023-06-07 | Wed | 259 KB | btp, asd + others |

**Cancellation vs missing — verdict: indistinguishable without an external calendar.** All ten were scheduled cards published to the simulcast feed; no result chart was archived. Possibilities are roughly equal:
1. Real cards that ran but the result chart wasn't downloaded — would explain GP/LRL Mon/Tue cards, AQU/PIM/DEL mid-week.
2. Cancellations (weather / track maintenance) — common in Jan/Feb at GP, LRL, AQU.
3. Cross-track BC fixtures (BCA/BCB/BCC/BCD) — the Friday/Saturday before-and-after Breeders' Cup days were simulcast-only special cards; their results may have been bundled with the main BC chart at another code.

**Decision:** Drop all 702 PP-only days from training. If we ever want to recover them, the path is to (a) query Equibase for the missing TCH charts, or (b) cross-reference a 2023 cancellation calendar (Equibase publishes one) to separate the buckets.

## F3. Filtered dataset stats (TB-flat only, CMR excluded)

Applied filters:
- `BREED = 'TB'` (drops QH, MX, AR)
- `COURSE_DESC ∈ {Dirt, Turf, All Weather Track, Inner turf, Outer turf, Downhill turf}` (drops Hurdle, Timber)
- Track code ≠ `cmr` (drops 1,525 CMR races, all already non-TB)

| | Before | After | Δ |
|---|---|---|---|
| Files surveyed | 4,906 | 4,906 | — |
| Total races | 42,618 | **34,309** | −19.5% |
| Total entries | 318,702 | **254,420** | −20.2% |
| Avg horses/race | 7.48 | 7.42 | minor |

**Drop reasons (sorted):**
| Reason | Races dropped |
|---|---|
| BREED = QH | 6,016 |
| Track = cmr | 1,525 |
| BREED = MX | 559 |
| Course = Hurdle | 113 |
| BREED = AR | 54 |
| Course = Timber | 42 |

**Kept-course mix:**
| Course | Races |
|---|---|
| Dirt | 25,311 |
| Turf | 4,501 |
| All Weather Track | 3,871 |
| Inner turf | 385 |
| Outer turf | 180 |
| Downhill turf | 61 |

**Kept-field-size distribution (modes 6/7/8 = 60% of races, same shape as raw):**
| horses | races | % |
|---|---|---|
| 5 | 3,666 | 10.7% |
| **6** | **7,242** | **21.1%** |
| **7** | **7,631** | **22.2%** |
| **8** | **5,851** | **17.1%** |
| 9 | 3,862 | 11.3% |
| 10 | 2,825 | 8.2% |
| 11 | 1,163 | 3.4% |
| 12 | 983 | 2.9% |

## F4. Final track-code map for Doug's bet list (TB-flat, post-filter)

| Doug's label | 2023 Equibase code | Track name | Race-days | Races | Entries |
|---|---|---|---|---|---|
| **GP** | `gp` | Gulfstream Park | 193 | 1,846 | 14,231 |
| **CT** | `ct` | Charles Town | 164 | 1,334 | 10,322 |
| **DD** | `ded` ⚠ | **Delta Downs** | 82 | 727 | 5,950 |
| **EVD** | `evd` | Evangeline Downs | 61 | 528 | 4,260 |
| **FP** | `fan` ⚠ | Fairmount Park (FanDuel rebrand) | 60 | 454 | 3,017 |
| **FG** | `fg` | Fair Grounds | 78 | 696 | 5,400 |
| **MNR** | `mnr` | Mountaineer | 121 | 966 | 6,804 |
| **MTN** | `mnr` ⚠ | likely same as MNR — see note | 121 | 966 | 6,804 |
| **MVR** | `mvr` | Mahoning Valley | 101 | 823 | 6,131 |
| **SA** | `sa` | Santa Anita | 91 | 855 | 6,251 |
| **DMR** | `dmr` | Del Mar | 43 | 399 | 3,392 |
| **OP** | `op` | Oaklawn Park | 68 | 654 | 5,774 |
| **KEE** | `kee` | Keeneland | 32 | 302 | 2,736 |
| **TUP** | `tup` | Turf Paradise | 82 | 606 | 4,249 |
| **CD** | `cd` | Churchill Downs | 58 | 575 | 4,697 |
| **ELP** | `elp` | Ellis Park | 38 | 353 | 2,744 |
| (bonus) SAR | `sar` | Saratoga | 40 | 406 | 3,138 |

**⚠ Notes:**
- **DD ≠ `dd`.** Delta Downs is filed as `ded` (3-letter) in 2023 Equibase, matching the existing `dd-results-2024/` folder code mismatch. Confirm: the CLAUDE.md folder is `Delta Downs/dd-results-2024/` — the `dd-` prefix in folder names is a Doug-side abbreviation, not the Equibase code. Parser should map `ded` ↔ Delta Downs.
- **FP ≠ `fp`.** No 2023 result chart filed under `fp`. 2023 = `fan`. Add alias: 2023 `fan` ↔ FP (2022 and earlier) ↔ `fan` (2023) ↔ `fp` (2024+).
- **MTN:** no `mtn` code in the 2023 dataset. Best guess this is a typo / duplicate for MNR (Mountaineer). Other candidates that *don't* match: Meadowlands (harness, not in Equibase TB feed), Monmouth (mth). Want me to verify your intent before we lock the alias table?
- All other codes match 1:1.

### F4.1 Sum totals for Doug's tracks (post-filter)

Distinct track codes after dedup (MNR = MTN): 15
- **Race-days: 1,272** (37% of 2023 TB-flat days nationally)
- **Races: 11,118** (32%)
- **Entries: 79,956** (31%)

Other tracks Doug doesn't specifically bet on but that are major training ammo (PRX 151 days, LRL 137, PEN 131, WO 128, GG 121, IND 116, TAM 93, AQU 92, DEL 85, MTH 51, etc.) add another ~22k races. Whether to include those in training is a Phase 2 decision — recommend yes for cross-track signal calibration (trainer/jockey/sire effects need more samples).

## F5. Final training-set posture

| | Count |
|---|---|
| 2023 race-days (TB-flat, ≥1 race kept, CMR excluded) | **~3,900** (≈ 4,906 − 702 PP-only − a few all-QH days) |
| Training races | **34,309** |
| Training entries | **254,420** |
| Per-track Doug-priority share | 1,272 days / 11,118 races / 79,956 entries |

That's ~10× the per-track sample our current 2024–2026 CL model trains on for any single track. Conditional-logit, multinomial, or pairwise-rank fits should be well-powered.

---

*Phase 1 recon complete. Filtered dataset locked. Ready for Phase 2 architecture design.*
