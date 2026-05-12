# Benter Model Data Repository

## Project Overview

This repository stores the raw data inputs for a horse racing handicapping project inspired by the Benter Model — the quantitative wagering system developed by Bill Benter for Hong Kong racing. The goal is to build a statistical model that predicts horse race outcomes and identifies profitable wagering opportunities.

## Repository Structure

```
benter-model-data/
├── model-workbook-versions/          # Excel workbooks containing the model
│   ├── benter_model_master.xlsx
│   └── benter_model_master_2.xlsx
├── CharlesTown/                      # Charles Town Races (WV)
│   ├── ct-pps-files/                 # Past performance sheets (Equibase PPs)
│   ├── ct-results-2024/
│   ├── ct-results-2025/
│   └── ct-results-2026/
├── Delta Downs/                      # Delta Downs (LA)
│   ├── dd-results-2024/
│   └── dd-results-2025/
├── Evangeline Downs/                 # Evangeline Downs (LA)
│   ├── evd-pps-files/
│   ├── evd-results-2024/
│   ├── evd-results-2025/
│   └── evd-results-2026/
├── Fair Grounds/                     # Fair Grounds Race Course (LA)
│   ├── fg-results-2024/
│   ├── fg-results-2025/
│   └── fg-results-2026/
├── Fairmount Park/                   # Fairmount Park (IL)
│   ├── fp-pps-files/
│   ├── fp-results-2024/
│   ├── fp-results-2025/
│   └── fp-results-2026/
├── Gulfstream Park/                  # Gulfstream Park (FL)
│   ├── gp-pps-files/
│   ├── gp-results-2024/
│   ├── gp-results-2025/
│   └── gp-results-2026/
├── Hong Kong/                        # Hong Kong Jockey Club tracks
│   ├── happy-valley-results-2026/
│   └── sha-tin-results-2026/
└── Mahoning Valley/                  # Mahoning Valley Race Course (OH)
    ├── mvr-2025-results/
    └── mvr-2026-results/
```

## File Types

### Past Performance (PPS) Files
Equibase past performance PDFs for upcoming race cards. Used as model inputs before each race day.

**Naming conventions:**
- `ctx0507y.pdf` — Charles Town style: `[track-code][month][day][suffix].pdf`
- `gpx0508x.pdf` — Gulfstream style: `[track-code]x[month][day][suffix].pdf`
- `GP050826USA.pdf` — alternate Gulfstream style: `[TRACK][month][day][year]USA.pdf`
- `evd0509y.pdf` — Evangeline style: `[track-code][month][day][suffix].pdf`

The `x`/`y`/`a` suffixes on PPS files likely denote different PP format variants (e.g., condensed vs. full, or morning-line vs. final).

### Results Files
Official Equibase result charts for completed race cards.

**Naming conventions:**
- `20240103-usa-ct-a-d.standard.pdf` — standard format: `[YYYYMMDD]-usa-[track]-a-d.standard.pdf`
- `CT010226USA.pdf` — alternate format: `[TRACK][day][month][year]USA.pdf`
- `ST0506.pdf` — Hong Kong Sha Tin format: `[TRACK][month][day].pdf`

## Data Coverage

| Track | Results From | PPS Files |
|---|---|---|
| Charles Town | Jan 2024 | Yes |
| Delta Downs | 2024–2025 | No |
| Evangeline Downs | 2024–present | Yes |
| Fair Grounds | 2024–present | No |
| Fairmount Park | 2024–present | Yes |
| Gulfstream Park | Jan 2024 | Yes |
| Hong Kong (HV + ST) | 2026 | No |
| Mahoning Valley | 2025–present | No |

## Model Workbooks

The Excel workbooks in `model-workbook-versions/` are the core of the handicapping model. They likely contain:
- Factor definitions and weightings (speed figures, class ratings, jockey/trainer stats, etc.)
- Probability estimation and overlay calculations
- Wagering strategy logic (Kelly criterion sizing, exotic bet construction)

`benter_model_master_2.xlsx` is the current working version.

## Automation Scripts

Python scripts live in the `scripts/` folder and automate the core data pipeline.

### `brisnet_parser_v2.py`
Parses Brisnet past performance files and applies model signals to generate handicapping cards for a given race day. Output is a structured card with each horse's signal scores ready for the model workbook.

### `process_results.py`
Extracts Win/Place/Show payouts from Equibase result chart PDFs and writes them back into the model workbook. Automates the post-race data entry step.

### `roi_tracker.py`
Calculates ROI across all picks for a given race day. Reads picks and payouts from the model workbook and summarizes profit/loss by bet type and track.

## Key Model Signals

The model uses three primary iron signals, calibrated per track:

- **Iron Trainer Signal** — identifies trainers with statistically significant win rates in specific conditions (distance, surface, class level, post-freshening, etc.)
- **Iron Sire Signal** — flags sires whose offspring show consistent performance patterns under specific conditions (surface type, distance, going)
- **Iron Horse Signal** — marks individual horses with a demonstrated edge in recurring conditions based on their own past performance history

Each signal is tracked and weighted independently per track, as trainer/sire/horse patterns vary significantly by circuit.

## Workflow

1. Download Equibase PPs for an upcoming race card → place in the track's `*-pps-files/` folder
2. Extract relevant data from PPs → feed into the model workbook
3. Model outputs probability estimates and flags overlays vs. the pari-mutuel odds
4. After racing, download result charts → place in the track's `*-results-[year]/` folder
5. Use results to back-test and calibrate model parameters
