# Phase 2 Architecture — Benter-style Results-Based Model

**Date:** 2026-06-26
**Scope:** Design document only. No code build. Doug reviews before build phase.
**Inputs locked from Phase 1:**
- Training universe: 34,309 TB-flat races / 254,420 entries from 2023 Equibase
- Doug's 16-track betting universe: 1,340 race-days / 11,697 races / 85,690 entries
- Two XML sources per race-day: SIMD PP zip + TCH result chart
- Public-info anchor: `DOLLAR_ODDS` (final tote), not `ml_odds`
- Hybrid posture: global signal aggregates from all 34k races; race-level model trained on Doug's 16 tracks

This document tracks parallel with the current production CL (`scripts/prob_model.py`). The new model is a **second model**, not a replacement of the live one — see §6 cross-reference plan.

---

## 1. Model Architecture Spec

### 1.1 The two-stage Benter blend

Bill Benter's HK system was not a single regression. It was two models combined:

- **Fundamental model `f(x)`** — a conditional logit over horse-level features (form, class, connections, pedigree, pace, equipment) that explicitly *excludes* market information. Output: a within-race probability vector `p_f`.
- **Market model `g(o)`** — the implied probabilities from the public tote, takeout-corrected, smoothed. Output: `p_m`.
- **Blend** — a learned mixture `p_final = softmax(α · logit(p_f) + β · logit(p_m))`. The coefficients α, β are fit on held-out data to maximize log-likelihood; in practice both are positive and similar in magnitude.

**Why two stages and not one CL with `log_final_odds` as a feature?** A single-stage fit (what the current `prob_model.py` does with `log_ml_pp`/`log_ml_results`) gives the same calibrated final probabilities, but it does *not* surface the most important wagering primitive: **fundamental edge** = `logit(p_f) − logit(p_m)`. That number is what Benter bet on. We need it cleanly separable.

### 1.2 The fundamental model `f(x)`

**Form:** within-race conditional logit (multinomial over the field of N starters per race).

For race `r` with horses `i = 1…N_r`:

```
P(winner = i | r) = exp(β · x_i) / Σ_j exp(β · x_j)
```

`x_i` is a vector of within-race-centered horse features. Within-race centering is critical (already used in the current CL): it removes race-level confounders (track, day, surface, condition) without needing fixed effects.

**Fit:** maximum likelihood with L2 regularization. Loss is per-race categorical cross-entropy summed across the training set. Optimizer: scipy `minimize` with L-BFGS-B (matches current pipeline).

**Regularization:** L2 with λ chosen by 5-fold temporal CV on Doug's 16 tracks. Start at λ = 1.0 (matches `LogisticRegression(C=1.0)` in current code) and sweep λ ∈ {0.1, 0.3, 1.0, 3.0, 10.0}.

**Calibration:** post-fit temperature scaling on the held-out validation fold. The current model is calibration-honest at T = 1.0 ([[project-cl-calibration]]); we expect the new one to be at T ≈ 1.0 as well, but verify.

### 1.3 The market model `g(o)`

`o_i` = the final tote decimal odds for horse i. Convert to a probability:

```
p_raw_i = 1 / o_i
p_m_i   = p_raw_i / Σ_j p_raw_j        # remove takeout via row-normalization
```

This is the "Harville-naive" market estimate. It's already well-calibrated empirically because the win pool is large and efficient. We do not add a smoothing step in v1; revisit if calibration suggests it.

### 1.4 The blend layer

Fit α, β on held-out validation:

```
logit_blend_i = α · logit(p_f_i) + β · logit(p_m_i)
p_blend       = softmax(logit_blend) within race
```

Free parameters: 2 scalars. Trivial to fit; pick the (α, β) that minimize negative log-likelihood on validation.

**Output triplet per horse:**
1. `p_f` — fundamental probability (the model's opinion ignoring the market)
2. `p_m` — market probability (what the public says)
3. `p_blend` — calibrated final estimate
4. `edge = logit(p_f) − logit(p_m)` — the Benter wagering primitive

`edge > 0` and large → overlay (model thinks horse is undervalued).

### 1.5 What this fixes

The current `prob_model.py` CL puts `log_ml_*` and `prime_power_c` and form features all in one regression. The fitted `log_ml_*` coefficient is positive (~+0.7 in production), meaning the model trusts ML odds heavily. **This is the architectural flaw Doug flagged:** ML odds encode one handicapper's opinion, so the model's win probability is contaminated by that handicapper. By isolating fundamental from market and using *final tote* (true consensus) for the market term, we get:

- A clean fundamental signal that doesn't lean on ML bias
- A market signal anchored on true consensus, not one person's opinion
- An explicit edge number that's the right primitive for wagering decisions

---

## 2. Feature Engineering Plan

The fundamental model needs `x_i` features. We organize them in five buckets, with explicit data sources and shrinkage strategies. The v10 workbook signal database (see [[project-benter-pivot]] — 5 workbooks under `Previous Versions of Benter Model/`) supplies hand-curated track-specific priors that we treat as Bayesian shrinkage targets, not direct features.

### 2.1 Public-info bucket (1 feature — excluded from `f(x)`, used only in `g(o)`)

| Feature | Source | Notes |
|---|---|---|
| `final_odds` | TCH `DOLLAR_ODDS` | Powers `g(o)` only; not in `f(x)` |

The PP `Odds` (morning-line) is still parsed and stored for diagnostic/residual analysis but does *not* enter the fundamental model.

### 2.2 Form bucket (per-horse, computed from SIMD `<PastPerformance>` blocks)

| Feature | Definition | Coverage |
|---|---|---|
| `prime_power_c` | TodaysHorseClassRating, race-centered | 100% |
| `best_spd_last3_c` | Max `SpeedFigure` over last 3 PP rows | High (drops on first-time starters) |
| `avg_spd_last3_c` | Mean `SpeedFigure` over last 3 PP rows | Same |
| `last_spd_c` | `SpeedFigure` of most recent PP | Same |
| `spd_trajectory_c` | (last 3 mean) − (prior 3 mean) | Drops for ≤6 PP rows |
| `days_off_c` | (today − most recent PP `RaceDate`) | High |
| `best_e1_c` | Max early-pace fig E1 over last 3 (TCH-derived equivalents in PP) | Per current model; carries forward |
| `class_delta_c` | (today's CR) − (avg CR of last 3 PP races) | 100% |
| `beaten_lengths_last_c` | `LengthsBehind` at finish in last PP | 100% |
| `improving_c` | Boolean: last finish ≤ 2nd, prior 2 finishes ≥ 4th | Discrete; binary |

**SIMD advantage over Brisnet:** `<PastPerformance>` is structured XML, so we get exact `SpeedFigure` per past race (not regex-scraped from a PDF column). No OCR errors.

### 2.3 Pedigree bucket (per-horse, computed from SIMD `<Sire>`/`<Dam>`/`<DamSire>` blocks)

This is a brand-new feature class — the current CL has *none* of it.

Two-level approach. For each (sire, surface) cell across the **full 34,309-race universe** we compute:

```
win_rate(sire, surface) = wins / starts
```

Then apply Bayesian shrinkage toward the breed-wide prior with strength `k = 10`:

```
sire_surf_winpct = (wins + k · prior_winpct) / (starts + k)
```

Same construction for:
- `sire_distance_winpct` (distance bucketed: ≤6f, 7–8.5f, ≥9f)
- `damsire_surface_winpct` (the maternal grandsire is a strong tell on turf)
- `sire_off_turf_winpct` (off-turf events as a separate cell)

These aggregates are computed once per training run, joined onto each horse's row, then within-race centered.

**Why shrinkage?** Without it, a sire with 1 start and 1 win shows 100% win rate. Shrinkage pulls thin cells toward the prior; cells with many starts dominate their own value. `k = 10` is the standard Brisnet/Trakus default; we'll tune it as a hyperparameter.

### 2.4 Connection bucket (per-horse, computed from TCH `KEY` fields cross-card)

Trainer and jockey effects use the `KEY` field (Equibase party ID) which is stable across cards and tracks.

| Feature | Definition | Shrinkage |
|---|---|---|
| `trn_winpct_track_c` | Trainer's win rate at this track, 2023 | k = 20 toward trainer-overall |
| `trn_winpct_surface_c` | Trainer's win rate on this surface | k = 20 toward trainer-overall |
| `jky_winpct_track_c` | Jockey's win rate at this track | k = 30 toward jockey-overall |
| `jky_trn_combo_c` | This jky+trn pairing's win rate | k = 10 toward jockey-alone |
| `trn_intent_c` | Days off ≤ 14 + same-class drop (binary "intent" signal) | None (binary) |

**Bayesian prior source:** the v10 workbook's hand-curated trainer/jockey signal database supplies the **prior win rate per track** for each named trainer/jockey. These are not features themselves — they enter the shrinkage formula:

```
trn_winpct_track_c = (wins + k · workbook_prior) / (starts + k)
```

If the workbook has a curated value for "Joseph at GP" of 0.30 (from Doug's `IRON_TRAINERS` table in `brisnet_parser_v2.py`), that becomes the shrinkage target for low-sample trainers and the regularizer for high-sample ones. **This is the right way to fold Doug's years of signal intelligence into the new model** — as Bayesian priors, not as one-hot indicator features.

### 2.5 Trip / pace bucket (per-horse, from SIMD PP history + race-level TCH)

| Feature | Definition |
|---|---|
| `pace_match_c` | Today's race pace shape (lone speed / duel / closer's race) × horse's running style |
| `bias_match_c` | Today's bias (rail/outside, speed/closer) × horse's style (from prior pace positions) |
| `troubled_trip_recent` | Binary: any of last 3 races has trip flag in `LongComment` |
| `class_drop_c` | (today's purse) − (max prior purse, last 3) |

Pace shape derivation: parse each horse's `<PointOfCall>` positions across last 3 PP rows. Categorize into "early speed" (positions 1–2 at calls 1–2), "presser" (3–4), "closer" (5+). Today's race pace shape: count of E1-style horses in the field. The interaction `pace_match_c` is the well-known "lone speed" / "no early speed" advantage.

### 2.6 Workout / fitness bucket (per-horse, from SIMD `<Workout>` blocks)

The current CL has these already (commit 268a517, shipped 2026-06-22 per [[project-workout-features]]) but only from Brisnet text scrape. SIMD gives us structured Workout records with `Ranking` ("3 of 47" = bullet at top).

| Feature | Definition | Source |
|---|---|---|
| `bullet_count_60d_c` | Count of workouts where rank/total ≤ 0.1 in last 60 days | `<Workout>` × `<Ranking>` |
| `workout_count_60d_c` | Total workouts last 60 days | `<Workout>` |
| `days_since_workout_c` | Days since most recent workout | `<Workout>` |
| `gate_works_c` | Count of `<Workout><GateIndicator>G` in last 60d | `<Workout>` |
| `bullet_at_distance_c` | Bullet works at today's distance | join Workout × Race.Distance |

### 2.7 Race-level race-bias bucket (one row per race, broadcast to all entries)

| Feature | Source | Use |
|---|---|---|
| `surface_today` | Race `SURFACE` | One-hot in `f(x)` |
| `course_today` | Race `COURSE_ID` | One-hot if not redundant with surface |
| `trk_cond_today` | Race `TRK_COND` | Ordinal: FT < GD < SY < MY < SL |
| `sealed_indicator` | Race `SEALED` | Binary; sealed track = closer-friendly |
| `runup_distance` | Race `RUNUPDIST` | Continuous; long run-up favors speed |
| `rail_distance` | Race `RAILDIST` | Turf only; rail-out helps closers |
| `par_time_delta_c` | Avg field speed-fig minus `PAR_TIME`-derived expected | Diagnostic; might enter as feature |
| `field_size` | Count of starters | Often left as one-hot for ≤ 5 / 6-8 / 9+ |

These are **race-level**, so once broadcast they have zero within-race variance and get dropped by the centering step. The way they enter the model is **as interactions** with horse-level features (e.g., `pace_match × field_size`, `sealed × early_speed`). v1 keeps the interactions hand-coded; v2 could fit them automatically with gradient boosting on residuals.

### 2.8 Held-out for v1 (parsed and stored, not in `f(x)` yet)

Features that ablation already showed regressed PP-rich ΔR² in the current model ([[project-form-trajectory]], [[project-connection-features]], [[project-dist-surface-features]]) start out **held out** in v1 of the new model. We re-test them against the new (richer) training set and re-decide.

---

## 3. SIMD XML Parser Design

### 3.1 Scope

One script: `scripts/equibase_simd_parser.py`. Input: a SIMD PP zip (or pre-extracted XML). Output: rows inserted into `benter_train.db`.

**Estimated size:** 400–500 LOC including tests. The XML is well-formed and the schema (`https://ifd.equibase.com/schema/simulcast.xsd`) is published; no regex on text required.

### 3.2 Output schema (new SQLite db: `scripts/benter_train.db`)

```
races_pp                  one row per race per race-day
├── race_pk PRIMARY KEY      (track, race_date, race_number)
├── track_code              "GP", "CT", …
├── race_date              YYYY-MM-DD
├── race_number            1..n
├── breed                  "TB"
├── race_type              "MCL", "ALW", …
├── condition_text         full RaceText
├── distance_yards         normalized to yards
├── surface                "D" / "T" / "AW"
├── course_desc            "Dirt", "Turf", …
├── purse_usa              decimal
├── age_restriction        "03U", "04U", …
├── sex_restriction        "F", "M", …
├── post_time              HH:MM
├── number_of_runners      int
├── grade                  G1/G2/G3 or NULL
└── parsed_at              timestamp

entries_pp                one row per horse per race
├── entry_pk PRIMARY KEY    (race_pk, program_number)
├── race_pk FK
├── program_number         "1", "1A", "2", …
├── post_position          int
├── horse_name             string
├── registration_number    Equibase ID (axcis_key compat)
├── foaling_date           date
├── foaling_area           "KY", "FL", "ON" …
├── color                  string
├── sex                    "G", "H", "M", "F", "C", "R"
├── weight_carried         int
├── medication             "L" / "B" / …
├── equipment              "b" / "v" / …
├── ml_odds                "15/1" (string for now, parsed to decimal later)
├── ml_odds_decimal        float (parsed)
├── claim_price            decimal
├── scratched              boolean
├── trainer_key            Equibase party ID
├── trainer_name           "Last, First"
├── jockey_key             Equibase party ID
├── jockey_name            "Last, First"
├── owner_name             string
├── apprentice_weight      int
└── todays_class_rating    int

pedigree                  one row per horse (deduped by registration_number)
├── horse_id PRIMARY KEY    (registration_number)
├── sire_id                FK pedigree
├── sire_name
├── dam_id                 FK pedigree
├── dam_name
├── damsire_id             FK pedigree
├── damsire_name

past_performances         one row per prior race per horse-day
├── pp_pk PRIMARY KEY      (entry_pk, sequence)
├── entry_pk FK
├── sequence              1 = most recent
├── pp_race_date          date
├── pp_track_code         string
├── pp_race_number        int
├── pp_horse_age          int (at that race)
├── pp_distance_yards     int
├── pp_surface            "D"/"T"/"AW"
├── pp_course             "Dirt", …
├── pp_track_condition    "FT"/"GD"/…
├── pp_finish_position    int
├── pp_lengths_behind     float
├── pp_speed_figure       int
├── pp_race_rating        int
├── pp_position_call1     int
├── pp_lengths_call1      float
├── pp_position_call2     int
├── pp_lengths_call2      float
├── pp_position_stretch   int
├── pp_lengths_stretch    float
├── pp_jockey_key         party id
├── pp_trainer_key        party id
├── pp_comment            short comment
├── pp_long_comment       full chart comment
├── pp_purse              decimal
├── pp_claim_price        decimal
└── pp_field_size         int

workouts                  one row per workout per horse-day
├── work_pk PRIMARY KEY    (entry_pk, work_sequence)
├── entry_pk FK
├── work_sequence         1 = most recent
├── work_date            date
├── work_track_code      string
├── work_distance        float (furlongs)
├── work_time_seconds    float
├── work_surface        "D"/"T"/"AW"
├── work_condition      "FT"/"GD"/…
├── work_ranking_position int
├── work_ranking_total   int
├── work_workout_type   "B" / "G" / NULL  (Breezing / Gate)
└── work_comment        string

career_stats              denormalized career splits, one row per horse-day
├── entry_pk PK FK
├── lifetime_starts/wins/seconds/thirds/earnings
├── ytd_starts/wins/seconds/thirds/earnings
├── prev_year_starts/wins/seconds/thirds/earnings
├── today_track_starts/wins/…
├── today_distance_starts/wins/…
├── today_surface_starts/wins/…
├── fast_starts/wins/…
├── off_track_starts/wins/…
├── turf_starts/wins/…
└── all_weather_starts/wins/…
```

### 3.3 Parser shape

```python
# pseudocode
def parse_simd(zip_path: Path) -> ParsedCard:
    with zipfile.ZipFile(zip_path) as z:
        xml_name = next(n for n in z.namelist() if n.endswith(".xml"))
        with z.open(xml_name) as f:
            tree = ET.parse(f)
    root = tree.getroot()
    track_code = derive_track_from_filename(zip_path.name)
    race_date  = derive_date_from_filename(zip_path.name)
    races, entries, pps, works, careers, pedigrees = [], [], [], [], [], []
    for race_el in root.findall("Race"):
        race_row = build_race_row(race_el, track_code, race_date)
        races.append(race_row)
        for horse_el in race_el.findall("Starters/Horse"):
            entry_row = build_entry_row(horse_el, race_row)
            entries.append(entry_row)
            entries_pk = entry_row["entry_pk"]
            for pp_el in horse_el.findall("PastPerformance"):
                pps.append(build_pp_row(pp_el, entries_pk))
            for w_el in horse_el.findall("Workout"):
                works.append(build_workout_row(w_el, entries_pk))
            careers.append(build_career_row(horse_el, entries_pk))
            pedigrees.append(build_pedigree_row(horse_el))
    return ParsedCard(races, entries, pps, works, careers, pedigrees)
```

Then a thin DB writer wraps `INSERT OR REPLACE` for each table, scoped to one transaction per card so re-runs are idempotent.

### 3.4 Filename → track/date

Filename pattern is `SIMD[YYYYMMDD][TRACK]_[COUNTRY].zip`. The track code in the filename is the canonical key — we don't trust the inner `<TrackID>` (it disagrees occasionally — saw FPL with `<TrackID>FPL` but content was QH).

```python
PP_FNAME = re.compile(r"^SIMD(\d{8})([A-Z]{2,4})_([A-Z]{2,3})\.zip$")
```

### 3.5 Track-code alias table

Phase 1 follow-up identified two known aliases:

```python
TRACK_ALIASES = {
    # (year, file_code) -> canonical_code
    (2023, "FAN"): "FP",   # Fairmount Park 2023 rebrand
    (2023, "BAQ"): "BEL",  # Belmont meet ran at Aqueduct during reno
}
```

The alias table is **versioned by year**, so the 2024+ data (filed as FP again) joins cleanly with 2023 (filed as FAN). The parser applies the alias before any DB write.

### 3.6 Companion: TCH chart parser

`scripts/tch_chart_parser.py` — same shape but for the result XML. Smaller in scope: one race-day per file, one root `<CHART>`, races as `<RACE NUMBER="n">`, entries as `<ENTRY>`. Output table: `results_chart` and `entry_results` joined back to `entries_pp` on (`registration_number`, race_pk). Estimated 250 LOC.

### 3.7 Joining the two

After both parsers run, the train DB has:
- `entries_pp` from SIMD (pre-race info)
- `entry_results` from TCH (final tote, finish position, payouts)

Join key: `(track_code, race_date, race_number, registration_number)`. `registration_number` (SIMD) = `AXCISKEY` (TCH) — both are the 24-char Equibase universal horse ID, spot-checked to match.

For the ~5% of entries with no match (likely scratched horses present in PP but absent from result), we drop from training (scratched horses don't have a finish).

### 3.8 Estimated build effort

| Component | LOC | Effort |
|---|---|---|
| SIMD parser | 400 | 1 day |
| TCH parser | 250 | 0.5 day |
| Schema + migrations | 100 | 0.5 day |
| Feature builder (joins → training matrix) | 500 | 1 day |
| Tests + edge cases | 300 | 0.5 day |
| **Total parser+ingest** | **~1550 LOC** | **~3.5 days** |

Model fit + validation is on top of this; see §4.

---

## 4. Training Pipeline Design

Six stages, each a separate script that writes to disk and can be re-run independently.

### Stage 1 — Ingest

`scripts/ingest_2023.py` — wraps both parsers. Walks `2023 PP's Files/*.zip` and `2023 Result Charts/*.xml`, calls SIMD parser then TCH parser, writes to `benter_train.db`. Idempotent (uses `INSERT OR REPLACE`). One-time run; takes ~30 minutes wall clock for 10k zip+XML pairs.

Validation hooks: file count, row count per table, % of entries with matched results, % with `final_odds > 0`. Compare against Phase 1 numbers as a regression check.

### Stage 2 — Cross-track aggregates (global signal layer)

`scripts/build_aggregates.py` — computes the shrinkage targets for every (sire, surface), (sire, distance), (damsire, surface), (trainer, track), (trainer, surface), (jockey, track), (jockey, trainer) cell across **all 34,309 TB-flat races** (not Doug's 16 only).

Stored as `aggregates_*` tables. Re-runnable; we expect to iterate on shrinkage strength `k` per cell type.

### Stage 3 — Feature builder

`scripts/build_features.py` — joins `entries_pp` + `past_performances` + `workouts` + `career_stats` + `aggregates_*` + `entry_results` into a single training matrix (`features_train` table). One row per (race, horse). All within-race centering happens here so the next stage can fit on a flat dataframe.

Output also: a `pp_only_holdout` view for the 702 PP-only days, in case we get the missing TCH charts later.

### Stage 4 — Fundamental fit

`scripts/fit_fundamental.py` — fits the conditional logit on Doug's 16-track subset of `features_train` (`WHERE track_code IN (16 codes)`). Saves to `benter_fundamental.pkl`. Reports:
- Coefficient table with stderrs (from inverse Hessian)
- 5-fold temporal CV log-loss (train Jan–Aug, test Sep–Dec; train Jan–Jun, test Jul–Dec; etc.)
- Per-feature ablation table (matches the current model's [[project-trainer-angles]] style)
- Calibration plot at T=1.0 + temperature sweep

### Stage 5 — Market term + blend

`scripts/fit_blend.py` — computes `p_m` from `final_odds`, fits the two blend coefficients (α, β) on the validation fold, saves to `benter_blend.pkl`. Outputs a 4-column prediction table: `p_f`, `p_m`, `p_blend`, `edge`.

### Stage 6 — Calibration + serialization

`scripts/calibrate.py` — temperature-scales `p_blend` if the reliability diagram shows miscalibration. Saves the final triple to `benter_v2.pkl` (a dict with `fundamental_model`, `blend_coefs`, `temperature`, `feature_list`, `aggregates_snapshot`).

### Pipeline runtime estimate

| Stage | Inputs | Wall clock |
|---|---|---|
| 1 ingest | ~10k XML files | 30 min |
| 2 aggregates | 254k entry rows | 5 min |
| 3 features | join+center | 5 min |
| 4 fundamental fit | 11k races, ~25 features | 15 min |
| 5 blend | 11k races | <1 min |
| 6 calibrate | 11k races | <1 min |

Full pipeline re-run: ~1 hour. Cheap enough to iterate freely.

---

## 5. Validation Strategy

### 5.1 Train/val/test split (temporal)

Random split leaks information (a horse's Jan races leak into its Feb model). Use a **strict temporal split**:

- **Train:** 2023-01-01 → 2023-09-30 (9 months, ~75% of races)
- **Validation:** 2023-10-01 → 2023-11-30 (2 months, ~17%)
- **Test:** 2023-12-01 → 2023-12-31 (1 month, ~8%) — touched once at the end

Within the training window, run rolling-origin 4-fold CV (Jan–Mar→Apr, Jan–Jun→Jul, Jan–Sep→Oct, etc.) for hyperparameter selection. This matches how the model will actually be used in production: train on the past, predict the future.

### 5.2 Primary metrics

| Metric | Why |
|---|---|
| **Per-race log-loss** | The proper scoring rule for probabilistic forecasting. Compare against market-only baseline. |
| **Brier score** | Secondary check; quadratic version of log-loss. |
| **Hit rate top-1** | Did the model's top pick win? Compare against market favorite hit rate. |
| **Hit rate top-3** | Place/show context. |
| **ROI at $2 win** | The bottom-line bet. Compute at multiple confidence thresholds. |
| **ECE (Expected Calibration Error)** | Bucketed by predicted prob, measure |observed − predicted|. Should be < 2% if calibration is honest. |

### 5.3 Stratified diagnostic metrics

Run all primary metrics also by:
- **Field size** (6, 7, 8, 9, 10+) — small fields are easier; need to be calibrated separately
- **Surface** (D, T, AW) — turf has more variance
- **Race type** (Claiming, MSW, Stakes) — class-call accuracy varies
- **Track** (each of Doug's 16) — track-specific edge varies
- **Favorite vs longshot** (post-hoc bins by `final_odds`) — overlay detection happens at longshots
- **Field has pace duel?** (race-level pace structure) — pace effects show up here

### 5.4 Benchmarks

| Benchmark | What it measures |
|---|---|
| **Market-only** `p = 1/odds_norm` | The bar. Beating this is the whole point. |
| **ML-only** `p = 1/ml_odds_norm` | Sanity check on PP morning line. Should be *worse* than market — that's the whole bias story. |
| **Current production CL** (`benter_model_cl.pkl`) | Cross-trained on 2023 SIMD: predict 2023 races with the current model's coefficients to compare apples-to-apples |
| **Naive Harville** from `final_odds` only | What `g(o)` looks like in isolation. |
| **Fundamental-only `p_f`** | What the model thinks before seeing the market. |
| **Blend `p_blend`** | The shipped output. |

The publishable result is: `p_blend` log-loss < market-only log-loss on the 2023-12 test set, and hit-rate top-1 is positive vs market favorite.

### 5.5 Wagering simulation (back-test)

Beyond calibration, simulate Doug's actual bet sizing on the test set:
- **Flat $2 win** on every horse with `edge > threshold` — sweep threshold ∈ {0.2, 0.4, 0.6}
- **Kelly fraction** with bankroll = $5000, fractional = 0.25 (Doug's existing `kelly_sizing.py` convention)
- Report cumulative ROI, max drawdown, sharpe, # bets, % bets won
- Include exotic-pool back-tests using TCH `EXOTIC_WAGERS` (Exa/Tri/Super pool payouts and pool sizes are in the data) — repurposes Doug's existing `find_value_exotics.py`

### 5.6 Honesty checks

- **Out-of-sample sanity:** randomly hold out 2023-12 entirely and never look at it during model dev. Touch only at end.
- **Train-test contamination:** verify no horse appears in both train and test (only a problem for ~3% of horses; flag at QA).
- **Code leak guard:** automate a CI check that the test-set queries can't include any race with date ≤ training cutoff.

### 5.7 Pass/fail criteria

The new model **ships** if all hold:
1. Test-set log-loss is at least 1% lower than market-only log-loss
2. Test-set ROI@flat-$2-edge>0.4 is positive
3. Calibration ECE on test set < 3%
4. Per-track hit rate is positive vs market favorite on at least 11 of Doug's 16 tracks

The model **does not ship** if any fail. Iterate features / regularization / blend until they pass.

---

## 6. Cross-Reference with Current PP-Based Model

### 6.1 Feature mapping

| Current CL feature | New model equivalent | Source change |
|---|---|---|
| `log_ml_pp` | (dropped from `f(x)`; ML carried as diagnostic only) | — |
| `log_ml_results` | (dropped from `f(x)`; final_odds powers `g(o)` separately) | — |
| `prime_power_c` | same, but computed from SIMD `TodaysHorseClassRating` (cleaner) | SIMD |
| `pp_missing` | `pp_missing` (still binary; some horses are first-time) | SIMD |
| `days_off_c` | same, from SIMD `PastPerformance[0].RaceDate` | SIMD |
| `best_spd_c`, `spd_missing` | `best_spd_last3_c`, `avg_spd_last3_c`, `last_spd_c` | SIMD richer |
| `best_e1_c` | rebuild from PP `PointOfCall` block (positions at calls 1–2) | SIMD |
| `bullet_count_60d_c`, `workout_count_60d_c`, `days_since_workout_c`, `workout_missing` | same; SIMD `<Workout>` has structured Ranking | SIMD |
| `equipment_change_c` | same; compare `Equipment` today vs last PP | SIMD |
| `weight_change_c`, `weight_change_missing` | same; `WeightCarried` today vs last PP | SIMD |
| `count_positive_angles_c`, `trainer_angle_missing` | **upgraded** with v10 workbook prior — trainer angles now Bayes-shrunk to workbook win-rates | SIMD + workbook |
| `jky_angle_winpct_c`, `jky_angle_missing` | same upgrade path | SIMD + workbook |
| — | **NEW** `sire_surface_winpct`, `sire_distance_winpct`, `damsire_surface_winpct` | SIMD pedigree |
| — | **NEW** `trn_winpct_track_c`, `jky_winpct_track_c`, `jky_trn_combo_c` | TCH KEY joins |
| — | **NEW** pace shape × bias features | TCH `POINT_OF_CALL` + race-level |
| — | **NEW** `sealed_indicator`, `runup_distance`, `rail_distance` | TCH race-level |

### 6.2 Held-out features re-test

These features were tested and held out of the current CL ([[project-dist-surface-features]], [[project-form-trajectory]], [[project-connection-features]]). They get a clean re-test in the new model on the 11k Doug-track training set:
- Distance/surface career records — redundant with `prime_power_c` in current model; SIMD's structured career stats may resolve differently
- Form trajectory slope — current sample too thin; 11k races may unlock it
- Connection-change features (jockey first time, hot J/T combo) — current ML pre-prices them; with ML removed from `f(x)`, they might add signal

Re-test protocol: each feature ablated individually, ship threshold ΔR² ≥ +0.001.

### 6.3 What stays in production

The current `benter_model_cl.pkl` **remains live** until the new model passes §5.7 criteria. Live picks continue from Brisnet PDF → current CL. The new model is back-test-only until it's proven on the 2023-12 test set and at least one full month of 2024+ Doug-data shadow runs.

### 6.4 Shadow run plan

Once the new model passes 2023 validation:

1. Backfill SIMD-style features for 2024–2026 (the data we have results for already) using whatever PP source is available — may need a separate parser for live Brisnet → SIMD-schema-equivalent mapping
2. Score every race the current model scored in 2024–2026 with the new model, store side-by-side
3. Compare ROI over 6 months of shadow data
4. If new model wins, swap. If not, keep iterating.

### 6.5 What never happens

- The new model does **not** retrain on the same data as the current model. Different sources, different schema, different anchors. Separate dev tracks.
- The current `prob_model.py` does **not** get refactored to use the new architecture. It stays as-is.
- The Brisnet parser (`brisnet_parser_v2.py`) is **not** touched. Live picks pipeline is untouched until shadow validation completes.

### 6.6 Live picks transition (Phase 4, future)

When the new model is ready for live use, we need a SIMD-equivalent live feed. Two paths:

1. **Equibase paid feed** — Doug subscribes to Equibase Simulcast Information Data, parser reuses `equibase_simd_parser.py` unchanged.
2. **Brisnet → SIMD adapter** — keep current Brisnet PDF parser, transform its output rows into SIMD-schema rows. Loses pedigree and some PP detail but is free.

Decision deferred to Phase 4. Phase 2 (this doc) and Phase 3 (build) operate entirely on 2023 archive data.

---

## 7. Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| SIMD format varies across tracks (different schema versions) | Medium | Phase 1 found 0 parse errors, but parser tests cover all 5,919 zips. Fail loudly on unknown elements. |
| Aggregate cells too thin to converge (e.g., Sire-X at Surface-T in 2023 alone) | High | Shrinkage with reasonable priors; consider blending in workbook hand-curated values when n < 5 |
| Final tote odds noisy on small pools | Medium | Filter races with `WPS_POOL < $20k` from validation; report metrics with/without |
| Test set too small (1 month) | Medium | Use temporal CV across 4 folds in training; test set is the final honest check |
| Workbook signal extraction is brittle (5 .xlsx files, hand-curated) | High | Extract once into `signals_workbook.json`; treat as a static asset. Don't re-parse on every run. |
| Held-out features re-show same pattern (regression) | Medium | Pre-register ablation tests; if v1 doesn't ship features, that's a clean negative result, not a failure |
| 2023 has weird year-effects (Pegasus Cup, BC, etc.) | Low | Stratify by month in validation; check for outlier months |
| Live picks pipeline accidentally swapped to new model before shadow validation | Low (process risk) | New model writes to `benter_v2.pkl` (different filename); live code only loads `benter_model_cl.pkl` |

---

## 8. Out of Scope for Phase 2

These come later (Phase 4+):
- Live odds integration (currently in `scripts/live-odds/`)
- Multi-year training (combine 2023 + 2024 SIMD when available)
- Harville extension to exotic exotic place/show probabilities (the existing `harville.py` adapts)
- Exotic-pool optimal bet construction (Phase 5 — `find_value_exotics.py` upgrade)
- Real-time tote scraping for in-race updates
- Mobile / API layer

---

## 9. What this design commits to

- **One conditional logit fundamental model** + **one market term** + **one blend layer**. Three components, all linear. No gradient boosting in v1. Keep interpretability while we're still validating the architectural pivot.
- **Bayesian shrinkage with workbook priors** as the canonical way to fold in Doug's curated signal intelligence. No one-hot trainer/jockey features.
- **Strict temporal validation** with one untouched test set.
- **Edge** = `logit(p_f) − logit(p_m)` as the wagering primitive — the model's output is *not just probabilities*, it's an edge signal Doug can size bets against.
- **The current model stays live until the new one beats it in shadow.** No flag day.

---

## 10. Decisions for Doug (need answers before build kicks off)

1. **Shrinkage strengths `k`** for sire/trainer/jockey cells — start at the defaults in §2.3/2.4 or do you want specific numbers?
2. **Workbook prior extraction** — should I extract the trainer/jockey/sire tables from `benter_model_v10_master.xlsx` into a flat JSON in Phase 3, or do you want to curate them by hand first?
3. **Test-set window** — happy with December as the untouched test, or want to slice differently (e.g., last 4 weeks of each meet)?
4. **Wagering simulation parameters** — flat $2 + Kelly 0.25 with $5000 bankroll matches your existing tools. Confirm or change.
5. **The 702 PP-only days** — do you want me to chase the missing TCH charts during Phase 3 ingest, or accept the 4,906-day training base?
6. **Live picks transition path (§6.6)** — Equibase paid feed vs Brisnet→SIMD adapter — any preference now, or defer to Phase 4?

---

*Design document complete. Awaiting Doug's review before greenlighting Phase 3 build.*
