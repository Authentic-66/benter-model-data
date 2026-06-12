"""
Brisnet PP Parser v2.1 — Universal parser for TwinSpires/Brisnet 'y' format
Handles: GP, CT, FP and any other track
Key insight: 'Own:' line is the reliable anchor for each horse entry
Usage: python3 brisnet_parser_v2.py <pp_file.pdf|txt> [TRACK_CODE]
"""

import re, sys, subprocess
from datetime import date
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# ── CONFIG ────────────────────────────────────────────────────────────────────
# Phase 5: bankroll for Kelly bet sizing. When > 0, kelly_sizing.py auto-runs
# after prob_predict.py annotates the picks file. 0 = disabled.
BANKROLL = 0

# ── MODEL SIGNAL DATABASES ────────────────────────────────────────────────────
IRON_TRAINERS = {
    'CT': {
        'Farrior':   ('🔥 IRON CT #1','287W/3yr/31%'),
        'Brown':     ('🔥 IRON CT #2','272W/3yr/31%'),
        'Runco':     ('🔥 IRON CT #3','209W/3yr/32%'),
        'Joy':       ('🔥 IRON CT',   '95W/growing'),
        'Grams':     ('🔥 IRON CT',   '110W/Fiber Sonde spe'),
        'Sigler':    ('🔥 IRON CT',   '66W/Candygram spe'),
        'McKee':     ('🔥 IRON CT',   '68W/iron horses'),
        'Contreras': ('✅ POS CT',    '104W/Musical Entourage'),
        'Shanley':   ('✅ POS CT',    '60W/$16avg overlay'),
        'Jones':     ('⚠️ PRICE CT', 'Fade <1.5|Board 2-6/1|Bet 7/1+'),
        'Petty':     ('✅ POS CT',    '54W'),
        'Murdock':   ('✅ CHALK CT',  '49W/$4.94avg'),
        'Walters':   ('✅ OVR CT',    '48W/$10.19avg'),
        'Collins':   ('✅ POS CT',    'Positive signal'),
        'Stidham':   ('⚠️ SHIPPER',  'National — watch late money'),
    },
    'FP': {
        'Becker':     ('🔥 IRON FP',  '31% — FADE sealed fast!'),
        'Rivelli':    ('🔥 IRON FP',  '50% rate'),
        'Rodriguez':  ('🔥 IRON FP',  '42% rate'),
        'Watkins':    ('🔥 IRON FP',  '35W iron'),
        'Manley':     ('🔥 IRON FP',  '35W iron'),
        'Durham':     ('🔥 IRON FP',  'Upgraded to iron'),
        'Catalano':   ('✅ POS FP',   'R1 winner'),
        'Essenpreis': ('✅ POS FP',   'R3 winner'),
        'Martinez':   ('✅ POS FP',   'Positive'),
        'Plasters':   ('✅ POS FP',   'Boards consistently'),
        'Irion':      ('✅ POS FP',   '25% rate'),
    },
    'GP': {
        'Joseph':    ('🔥 IRON GP #1','405W/3yr/30%'),
        'Angelo':    ('🔥 IRON GP #2','237W/3yr/22%'),
        'Carlos':    ('⚠️ MONITOR GP', '0W/11picks -- fade'),  # Carlos A. David
        'Barboza':   ('🔥 IRON GP',   '150W/3yr'),
        'Casse':     ('🔥 IRON GP',   '138W/3yr/19% — public overplays, wait 5/1+'),
        'Catanese':  ('🔥 IRON GP',   'new signal — 3picks insufficient sample'),
        'Lynch':     ('🔥 IRON GP',   '64W/26%/chalk'),
        'Crichton':  ('🔥 IRON GP',   '110W/Jan-Apr best'),
        'Walsh':     ('🔥 IRON GP',   '31%/$13avg overlay'),
        'Cox':       ('🔥 IRON GP',   '34% — best rate at GP'),
        'Mott':      ('✅ POS GP',    '98W/29%'),
        'Pletcher':  ('✅ POS GP',    '98W/21%'),
        'Fawkes':    ('🔥 IRON GP',   '102W/3yr'),
        'Sano':      ('✅ OVR GP',    '99W/$12avg — bet 5/1+'),
        'Orseno':    ('🔥 IRON GP',   '90W/$14avg overlay'),
        'Abreu':     ('🔥 TURF GP',   'Turf specialist/Neolithic spe'),
        'Spatz':     ('✅ POS GP',    'Winter specialist'),
        'Sweezey':   ('✅ POS GP',    'Overlay/Girvin spe'),
        'Delgado':   ('✅ POS GP',    '26% rate'),
        'Walden':    ('✅ OVR GP',    '29%/$13avg'),
        'Drexler':   ('✅ OVR GP',    '$20avg — bet 8/1+'),
        'Romans':    ('✅ POS GP',    'National trainer fires at GP'),
        'Weaver':    ('✅ POS GP',    'National trainer positive'),
    },
    'EVD': {
        'Landry':    ('🔥 IRON EVD',  '73W/3yr/24%'),
        'Larrosa':   ('🔥 IRON EVD',  '71W/3yr/24%'),
        'Breaux':    ('🔥 IRON EVD',  '67W/3yr/23%'),
        'Bourgeois': ('🔥 IRON EVD',  '47W/chalk'),
        'Thomas':    ('✅ IRON EVD',  '46W/Sassicaia spe'),
        'Cano':      ('🔥 IRON EVD',  '36W/Mr McGregor'),
        'Calhoun':   ('✅ POS EVD',   '41W/chalk'),
        'Wong':      ('🔥 CHALK EVD', '28%/$3.93avg'),
        'Brinkman':  ('✅ OVR EVD',   'Overlay — 5/1+'),
        'Ward':      ('✅ OVR EVD',   'El Deal specialty'),
        'Mojica':    ('🔥 EVD+DD',    'Cross-circuit iron'),
        'Degeyter':  ('🔥 IRON EVD',  '32% win rate'),
        'Wilson':    ('✅ POS EVD',   'Clearly Now 2026'),
        'Gonzalez':  ('✅ OVR EVD',   '$14avg — bet 5/1+'),
        'David':     ('✅ POS EVD',   'David Jr positive'),
    },
    'MVR': {
        'Bernardini':('🔥 IRON MVR',  '48W/29%'),
        'Rivera':    ('🔥 IRON MVR',  '47W/26%'),
        'Farrior':   ('🔥 IRON MVR',  '28% — same as CT'),
        'Guciardo':  ('🔥 IRON MVR',  '54% rate'),
        'Ibarra':    ('🔥 IRON MVR',  '35% rate'),
        'Gorham':    ('✅ POS MVR',   '25% all season'),
        'Cline':     ('✅ POS MVR',   'Gets stronger late'),
        'Radosevich':('✅ POS MVR',   'Jeffrey=fall/Justin=all year'),
    },
    'DD': {
        'Landry':    ('🔥 IRON DD',   '45W/28%'),
        'Ramirez-Rodriguez':('🔥 DD+EVD','Cross-circuit'),
        'Wong':      ('🔥 CHALK DD',  '25%/$4.84avg'),
        'Mojica':    ('🔥 DD+EVD',    'Cross-circuit'),
        'Brinkman':  ('✅ OVR DD',    'Overlay 5/1+'),
        'Gonzalez':  ('✅ OVR DD',    '$14avg overlay'),
    }
}

SIRE_SIGNALS = {
    # Universal cross-circuit positives — applied at every track
    'ALL': {
        'Curlin':         ('🔥 6-TRACK',  'Curlin+Casse GP = iron combo'),
        'Girvin':         ('🔥 3-TRACK',  'GP(80)+CT+EVD wins'),
        'Midshipman':     ('🔥 5-TRACK',  'CT+FP+EVD+MVR+DD'),
        'Goldencents':    ('🔥 4-TRACK',  'FP+EVD+MVR+DD'),
        'Union Rags':     ('🔥 7-TRACK',  'Universal iron sire'),
        'Mor Spirit':     ('✅ 3-TRACK',  'FP+MVR+DD'),
        'Khozan':         ('🔥 MULTI',    '106W/3yr — fires multiple circuits'),
        'Into Mischief':  ('✅ MULTI',    '64W/3yr GP + national'),
        'Constitution':   ('✅ MULTI',    '66W/3yr GP + national'),
        'Temple City':    ('✅ TURF',     'Positive turf signal'),
        'Justify':        ('✅ MULTI',    'National positive'),
        'Not This Time':  ('✅ MULTI',    '17W GP + growing'),
    },
    # GP Florida track-specific sires
    'GP': {
        'Bucchero':       ('🔥 GP FL SIRE','104W/3yr'),
        'Neolithic':      ('🔥 GP FL SIRE','99W/3yr — Abreu spe'),
        'Adios Charlie':  ('🔥 GP FL SIRE','81W/3yr'),
        'The Big Beast':  ('🔥 GP FL SIRE','73W/3yr'),
        'Awesome Slew':   ('🔥 GP FL SIRE','61W/3yr'),
        'Cajun Breeze':   ('✅ GP FL SIRE','49W/3yr'),
        'Saturnalia':     ('✅ POS SIRE', 'International positive at GP'),
        'Maxfield':       ('⚠️ FADE GP',  '-100% impact at GP — skip'),
    },
    # CT Charles Town WV home-track sires
    'CT': {
        'Juba':           ('🔥 CT SIRE #1','160W/3yr — WV home-track'),
        'Fiber Sonde':    ('🔥 CT SIRE #2','137W/3yr'),
        'Golden Years':   ('🔥 CT SIRE #3','94W/3yr'),
        'Windsor Castle': ('🔥 CT SIRE #4','90W/3yr'),
        'Uncle Lino':     ('✅ CT SIRE',   '69W/3yr'),
        'Great Notion':   ('✅ CT SIRE',   '62W/Jones Jr spe'),
        'Candygram':      ('✅ CT SIRE',   '46W/Sigler spe'),
    },
    # FP Fairmount Park IL home-track sires
    'FP': {
        'Ghaaleb':        ('🔥 FP SIRE #1','29W — Becker spe'),
        'Cinco Charlie':  ('✅ FP+MVR',   'Cross-circuit positive'),
        'Shaman Ghost':   ('🔥 FP SIRE',  'Joyful Ghost W 6/9/26'),
    },
    # EVD Evangeline Downs LA sires
    'EVD': {
        'Star Guitar':    ('🔥 EVD SIRE #1','42W/3yr — any trainer'),
        'El Deal':        ('🔥 EVD+DD',   '28 EVD + 21 DD wins'),
        'Custom for Carlos':('🔥 EVD+DD', '25 EVD + 26 DD wins'),
        'Half Ours':      ('🔥 EVD SIRE', '27W/3yr'),
        'Astrology':      ('✅ EVD+DD',   '25W EVD'),
    },
    # DD Delta Downs LA sires
    'DD': {
        'El Deal':        ('🔥 EVD+DD',   '28 EVD + 21 DD wins'),
        'Custom for Carlos':('🔥 EVD+DD', '25 EVD + 26 DD wins'),
        'Astrology':      ('✅ EVD+DD',   '25W EVD'),
    },
    # MVR Mahoning Valley OH sires
    'MVR': {
        'Drill':          ('🔥 MVR #1',   '16W full meet'),
        'Tale of Ekati':  ('🔥 MVR SIRE', '11W Ohio home-track'),
        'Kantharos':      ('🔥 MVR SIRE', '12W full meet'),
        'Rivers Run Deep':('✅ MVR SIRE', '12W full meet'),
        'Cinco Charlie':  ('✅ FP+MVR',   'Cross-circuit positive'),
    },
}

IRON_HORSES = {
    # CT mega horses
    'Gran Andrews':      ('🔥 CT MEGA','16W/3yr Shanley'),
    'Hey Boots':         ('🔥 CT MEGA','11W Jones Jr — BET ANY PRICE'),
    'No Love for Juba':  ('🔥 CT MEGA','10W Jones Jr — BET ANY PRICE'),
    'Duncan Idaho':      ('🔥 CT MEGA','10W Jones Jr — BET ANY PRICE'),
    'Restless':          ('🔥 CT IRON','9W Brown/Girvin'),
    'Im the Director':   ('🔥 CT IRON','9W McKee/Juba'),
    'Overnight Pow Wow': ('🔥 CT IRON','11W McKee'),
    'Petingas Twin':     ('🔥 CT IRON','Farrior iron horse'),
    'Musical Entourage': ('🔥 CT IRON','4W Contreras'),
    'Maskedandmummed':   ('🔥 CT IRON','4W Sigler/Stakes winner'),
    'Blameitonthefun':   ('🔥 CT IRON','6W Shanley'),
    'Play It Loud':      ('🔥 CT IRON','6W McKee'),
    'Zachamundo':        ('✅ CT IRON','5W Runco'),
    'Chasing Colton':    ('🔥 CROSS',  'MVR+CT wins Farrior'),
    # GP mega horses
    'Ashima':            ('🔥 GP MEGA','10W SJJ'),
    'Misprint':          ('🔥 GP IRON','9W active 2026'),
    'Light Fury':        ('🔥 GP IRON','9W active 2026'),
    'Speed Figures':     ('🔥 GP IRON','5W VBJ'),
    'Commandment':       ('🔥 GP IRON','4W Cox/Into Mischief'),
    'Viable Asset':      ('🔥 GP IRON','4W Abreu/Neolithic'),
    'Chicken Dance':     ('🔥 GP IRON','4W Abreu/Neolithic'),
    'Souper Zonda':      ('🔥 GP IRON','3W Casse/Curlin'),
    'Private Thoughts':  ('🔥 GP IRON','7W Spatz'),
    'Sister Troienne':   ('🔥 GP IRON','4W Lynch'),
    'Thousandsticks':    ('🔥 GP IRON','4W Lynch'),
    "Lucy's Cookie":     ('🔥 GP IRON','Abreu/Adios Charlie'),
    'Happy Ride':        ('🔥 GP IRON','Orseno/Curlin cross'),
    # EVD horses
    'Highly Wicked':     ('🔥 EVD IRON','6W David Jr'),
    'Mr McGregor':       ('🔥 EVD IRON','4W Cano'),
    "Avery's Gem":       ('🔥 EVD IRON','3W Bourgeois'),
    'Astrologysprotege': ('🔥 EVD IRON','5W/3yr'),
    'Begforforgiveness': ('🔥 EVD IRON','4W Brinkman'),
    # MVR horses
    'Coastland':         ('🔥 MVR IRON','4W full meet Ibarra'),
    'Colonel Vargo':     ('🔥 MVR IRON','4W Farrior'),
    # FP horses
    'Cookin the Books':  ('🔥 FP IRON', '2W Watkins'),
    'Too Much Tuesday':  ('🔥 FP IRON', '4W Watkins'),
}

# Special trainer rules
TRAINER_RULES = {
    'FP': {
        'Becker': 'SEALED FAST = FADE. Dual entry = use IGNORED (longer) horse.',
    },
    'CT': {
        'Jones': 'Price band: Fade <1.5. Board 2-6/1. Bet 7/1+. EXCEPTION: Hey Boots/Duncan Idaho/No Love for Juba = any price.',
    },
    'GP': {
        'David': 'DUAL ENTRY = back the LONGER price horse.',
        'Joseph': 'DUAL ENTRY = board both.',
        'Barboza': 'DUAL ENTRY = board both.',
    }
}

def get_sire_signal(sire, track_code):
    """Return (sig, desc) for a sire at the given track, or None.
    Track-specific entries take priority over ALL."""
    for source in [SIRE_SIGNALS.get(track_code, {}), SIRE_SIGNALS.get('ALL', {})]:
        for key, (sig, desc) in source.items():
            if key.lower() in sire.lower():
                return sig, desc
    return None


def extract_text(filepath):
    path = Path(filepath)
    if path.suffix.lower() != '.pdf':
        return path.read_text(errors='replace')
    try:
        result = subprocess.run(['pdftotext', '-layout', str(path), '-'],
                               capture_output=True, text=True, errors='replace')
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except FileNotFoundError:
        pass
    import pdfplumber
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            full = page.extract_text(layout=True) or ''
            left = page.crop((0, 0, page.width * 0.52, page.height)).extract_text() or ''
            pages.append(full + '\n' + left)
    return '\f'.join(pages)

# PP race lines start "DDMonYYTRK" (e.g. '18Apr26CT'); Brisnet spells July 'Jly'
_PP_LINE_DATE_RE = re.compile(r'^\s*(\d{1,2})([A-Za-z]{3})(\d{2})[A-Za-z]')
_PP_MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5,
              'jun': 6, 'jne': 6, 'jul': 7, 'jly': 7, 'aug': 8,
              'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
_PP_PACE_TOKEN_RE = re.compile(r'\d{2,3}/$')
_PP_VARIANT_RE = re.compile(r'^[+-]\d+$')
_TURF_GOING_RE = re.compile(r'\b(fm|yl|sf)\b')


def _pp_line_date(line):
    """Race date of a condensed PP race line, or None."""
    m = _PP_LINE_DATE_RE.match(line)
    if not m:
        return None
    mon = _PP_MONTHS.get(m.group(2).lower())
    if not mon:
        return None
    try:
        return date(2000 + int(m.group(3)), mon, int(m.group(1)))
    except ValueError:
        return None


def extract_speed_figures(block_lines):
    """Extract Brisnet speed figures from condensed PP race lines.

    Figure block reads "E1 E2/ LP [±var ±var] SPD" before the post/start
    positions, so SPD is the LAST 25-130 number in the run that follows
    the "NN/" pace token (e.g. '88 82/ 61 -1 -4 59 6 5 ...' -> 59).
    Returns [(figure, surface), ...] most recent first, deduped by race
    date (extracted text repeats some lines). surface is 'T', 'AW', 'D'.
    """
    races = {}
    for line in block_lines:
        d = _pp_line_date(line)
        if d is None or d in races:
            continue
        toks = line.split()
        slash_i = next((i for i, t in enumerate(toks)
                        if _PP_PACE_TOKEN_RE.fullmatch(t)), None)
        if slash_i is None:
            continue
        fig = None
        for t in toks[slash_i + 1:]:
            if _PP_VARIANT_RE.fullmatch(t):
                continue
            if not t.isdigit():
                break
            v = int(t)
            if 25 <= v <= 130:
                fig = v
            else:
                break
        if fig is None:
            continue
        if '(T)' in line or _TURF_GOING_RE.search(line):
            surf = 'T'
        elif re.search(r'\bAW\b|Tapeta|Polytrack|All.?Weather', line):
            surf = 'AW'
        else:
            surf = 'D'
        races[d] = (fig, surf)
    return [races[d] for d in sorted(races, reverse=True)]


def last_race_date_from_block(block):
    """Most recent past-race date in a horse's PP block, or None
    (first-time starters have no PP lines)."""
    dates = [d for d in (_pp_line_date(line) for line in block) if d]
    return max(dates, default=None)


def parse_brisnet(text, track_code='GP', race_date=None):
    pages = text.split('\f')
    races = defaultdict(lambda: {'conditions': '', 'purse': '', 'surface': '', 'horses': []})
    current_race = 1

    for i, page in enumerate(pages):
        if len(page.strip()) < 50:
            continue

        lines = page.split('\n')
        header = lines[0]

        # ── Race number from header (check first 10 lines; pdfplumber may offset) ─
        for hline in lines[:10]:
            race_m = re.search(r'\bRace\s+(\d+)\b', hline)
            if race_m:
                current_race = int(race_m.group(1))
                break

        # ── Race conditions from header ───────────────────────────────────────
        if current_race and not races[current_race]['conditions']:
            # Extract class/distance from header
            cond_m = re.search(
                r'((?:MC|OC|ALW|CLM|MDN|STR|MSW|STK)\s+[\d,.k]+[^\d][\d½¾¼]+\s*(?:Furlongs?|Miles?|F\s|M\s)[^R]*)',
                header, re.IGNORECASE
            )
            if cond_m:
                races[current_race]['conditions'] = cond_m.group(0).strip()[:70]
            # Surface
            if '(T)' in header or 'Turf' in header:
                races[current_race]['surface'] = 'Turf'
            elif 'AW' in header or 'Tapeta' in header or 'All Weather' in header:
                races[current_race]['surface'] = 'AW'
            else:
                races[current_race]['surface'] = 'Dirt'

        # ── Is this a horse page? (has 'Own:') ────────────────────────────────
        if 'Own:' not in page:
            purse_m = re.search(r'Purse\s+\$([\d,]+)', page)
            if purse_m and current_race:
                races[current_race]['purse'] = f"${purse_m.group(1)}"
            continue

        # ── Prime Power map: keyed by PP# from full-page horse-name lines ─────
        # Full-page format: "{PP}  {Name} ... Prime Power: {val} ({rank})"
        pp_power_map = {}
        for line in lines:
            pm = re.match(r'^\s*(\d{1,2})\s+[A-Z][A-Za-z].*?Prime Power:\s*([\d.]+)\s*\((\d+)', line)
            if pm:
                pp_power_map[int(pm.group(1))] = (pm.group(2), pm.group(3))
        # CT-style fallback: Prime Power in page header without PP# prefix
        if not pp_power_map:
            ppm = re.search(r'Prime\s+P(?:ower)?[:\s]*([\d.]+)\s*\((\d+)', lines[0])
            if ppm:
                pp_power_map[-1] = (ppm.group(1), ppm.group(2))

        # ── Find every Own: line on this page ─────────────────────────────────
        own_indices = [j for j, line in enumerate(lines)
                       if re.match(r'^(\d+)\s+Own:', line) or re.match(r'^\s*Own:', line)]

        for oi, own_idx in enumerate(own_indices):
            # ── Per-horse state ───────────────────────────────────────────────
            horse = '?'; pp_num = 0; ml = '?'; trainer = '?'; trainer_stats = ''
            jockey = '?'; sire = '?'; prime_power = '?'; pp_rank = '?'
            days_off = 0; pos_angles = []; neg_angles = []; claim_price = None
            jt_winpct = None

            # ── PP# from Own: line or backward search ─────────────────────────
            own_line = lines[own_idx]
            om = re.match(r'^(\d+)\s+Own:', own_line)
            if om:
                pp_num = int(om.group(1))
            else:
                for k in range(own_idx - 1, max(0, own_idx - 8), -1):
                    nm = re.match(r'^\s*(\d+)\s+[A-Z][a-z]', lines[k])
                    if nm:
                        pp_num = int(nm.group(1))
                        break

            # ── Horse name: search backward from Own: ─────────────────────────
            for k in range(own_idx - 1, max(0, own_idx - 6), -1):
                prev = lines[k]
                # Country-of-origin suffix like "(Ire)" or "(GB)" may appear between
                # the horse name and the class condition "(CLM 5000)".  The optional
                # non-capturing group consumes it so group 1 holds only the bare name.
                hm = re.search(r'([A-Z][A-Za-z\'"\-\. ]+?)(?:\s*\([A-Z][A-Za-z]{0,3}\))?\s+\([A-Z/EP]+\s+\d+\)', prev)
                if hm:
                    horse = hm.group(1).strip()
                    claim_m = re.search(r'\$(\d{1,3},?\d{3})', prev)
                    if claim_m:
                        claim_price = claim_m.group(1)
                    break

            # ── Prime Power from pre-built map ────────────────────────────────
            if pp_num in pp_power_map:
                prime_power, pp_rank = pp_power_map[pp_num]
            elif -1 in pp_power_map:
                prime_power, pp_rank = pp_power_map[-1]

            # ── Block: own_idx-4 to next Own: (exclusive) ────────────────────
            block_start = max(0, own_idx - 4)
            block_end = own_indices[oi + 1] if oi + 1 < len(own_indices) else len(lines)
            block = lines[block_start:block_end]

            # ── Scan block for remaining fields ───────────────────────────────
            for bi, line in enumerate(block):

                # Prime Power fallback (block may include it for some formats)
                if prime_power == '?':
                    ppm = re.search(r'Prime Power:\s*([\d.]+)\s*\((\d+)', line)
                    if ppm:
                        prime_power = ppm.group(1)
                        pp_rank = ppm.group(2)

                # ML odds: silks line starts with fraction/integer then color word.
                # Horse header lines ("1 Army Medic (E 7) ...") also start with an
                # integer + capitalized word — the running-style parens "(E 7)"
                # distinguish them, so exclude any line containing that pattern.
                if ml == '?':
                    stripped = line.strip()
                    ml_m = re.match(r'^(\d+/\d+|\d+)\s+[A-Z][a-z]', stripped)
                    if (ml_m and 'Own:' not in line and 'Trnr:' not in line
                            and 'Sire' not in line
                            and not re.search(r'\([A-Z/EP]+\s+\d+\)', stripped)):
                        val = ml_m.group(1)
                        if '/' in val or (val.isdigit() and 1 <= int(val) <= 99):
                            ml = val

                # Trainer: "(N/N N%)", "(N N-N-N N%)", or name-only fallback
                if trainer == '?':
                    tm = re.search(r'Trnr:\s*([^\n(]+?)\s*\((\d+)\s*/\s*(\d+)\s+(\d+)%\)', line)
                    if tm:
                        trainer = tm.group(1).strip()
                        trainer_stats = f"{tm.group(2)} sts {tm.group(4)}%"
                    else:
                        tm2 = re.search(r'Trnr:\s*([^\n(]+?)\s*\((\d+)\s+(\d+)-(\d+)-(\d+)\s+(\d+)%\)', line)
                        if tm2:
                            trainer = tm2.group(1).strip()
                            trainer_stats = f"{tm2.group(2)} sts {tm2.group(3)}-{tm2.group(4)}-{tm2.group(5)} {tm2.group(6)}%"
                        else:
                            # Fallback: grab name before stats even if stat format is unrecognized.
                            # Ensures signal matching fires even when the stats parens use a novel layout.
                            tm3 = re.search(r'Trnr:\s*([A-Za-z][^\n(]+?)\s*\(', line)
                            if tm3:
                                trainer = tm3.group(1).strip()

                # Jockey: "LASTNAME FIRSTNAME (N N-N-N N%)" or "(N/ N N%)"
                if jockey == '?':
                    jm = re.search(r'^([A-Z]{2,}(?:\s+[A-Z]+){0,3})\s+\(\d+[\s/]', line)
                    if jm:
                        jockey = jm.group(1).title()

                # J/T combo win rate. Condensed PPs carry it as
                # "JKYw/ Trn L60 <starts> <win%> <itm%> <roi>"; full PPs may
                # use a "J/T" or "Jky/Trn" stats line instead.
                if jt_winpct is None:
                    jt_m = re.search(r'JKYw/\s*Trn\s+L60\s+\d+\s+(\d+)%', line, re.IGNORECASE)
                    if jt_m:
                        jt_winpct = int(jt_m.group(1))
                    elif re.search(r'\bJ/?T\b|Jky/Trn', line, re.IGNORECASE):
                        pct_m = re.search(r'(\d+)%', line)
                        if pct_m:
                            jt_winpct = int(pct_m.group(1))

                # Sire
                if sire == '?':
                    sm = re.search(r'Sire\s*:\s*=?([A-Z][A-Za-z\'"\-\. \(\)]+?)\s*\(', line)
                    if sm:
                        sire_raw = sm.group(1).strip()
                        sire = re.sub(r'\s*\([^)]*\)\s*$', '', sire_raw).strip()
                    elif re.search(r'Sire\s*:\s*$', line.strip()):
                        abs_next = block_start + bi + 1
                        if abs_next < len(lines):
                            nxt = lines[abs_next].strip().lstrip('=')
                            sn = re.match(r'([A-Z][A-Za-z\'"\-\. ]+?)\s*[\($]', nxt)
                            if sn:
                                sire = sn.group(1).strip()

                # Days off
                if days_off == 0:
                    dm = re.search(r'(\d+)\s+days\s+away', line)
                    if dm:
                        days_off = int(dm.group(1))

                # Angles
                if 'ñ' in line:
                    for ang in re.findall(r'ñ\s*([^ñ×\n]+)', line):
                        a = ang.strip()
                        if len(a) > 4:
                            pos_angles.append(a[:65])
                if '×' in line:
                    for ang in re.findall(r'×\s*([^ñ×\n]+)', line):
                        a = ang.strip()
                        if len(a) > 4:
                            neg_angles.append(a[:65])

            # ── Days off from the most recent PP race-line date ──────────────
            # ('N days away' text above is absent from condensed PPs, so this
            # computed value is the real source)
            last_race = last_race_date_from_block(block)
            if race_date and last_race and last_race < race_date:
                days_off = (race_date - last_race).days

            # ── Speed figures from PP lines in block ──────────────────────────
            spd_figs   = extract_speed_figures(block)  # [(figure, surface), ...]
            recent_spd = [f for f, _ in spd_figs[:5]]
            best_spd   = max((f for f, _ in spd_figs), default=None)
            best_spd_turf = max((f for f, s in spd_figs if s == 'T'),  default=None)
            best_spd_aw   = max((f for f, s in spd_figs if s == 'AW'), default=None)
            improving = (len(recent_spd) >= 3 and
                         recent_spd[0] > recent_spd[1] > recent_spd[2])

            # ── Hot J/T and 0% J/T from angles ────────────────────────────────
            _HOT_JT_RE = re.compile(r'hot.*?(?:trainer|jockey|j/?t|combo)', re.IGNORECASE)
            hot_jt = any(_HOT_JT_RE.search(a) for a in pos_angles)
            # Angle fallback for 0% when no dedicated J/T stats line was found
            if jt_winpct is None:
                for _a in neg_angles:
                    if re.search(r'j/?t\b|trainer.*jockey|jockey.*trainer', _a, re.IGNORECASE) \
                            and '0%' in _a:
                        jt_winpct = 0
                        break
            jt_zero = (jt_winpct == 0)

            if horse == '?' or pp_num == 0:
                continue

            # ── Apply model signals ───────────────────────────────────────────
            signals = []
            track_trainers = IRON_TRAINERS.get(track_code, {})

            for key, (sig, desc) in track_trainers.items():
                if key.lower() in trainer.lower():
                    signals.append(('TRAINER', sig, desc))
                    break

            sire_match = get_sire_signal(sire, track_code)
            if sire_match:
                signals.append(('SIRE', sire_match[0], sire_match[1]))

            for key, (sig, desc) in IRON_HORSES.items():
                if key.lower() in horse.lower():
                    signals.append(('HORSE', sig, desc))
                    break

            # Hot J/T combo — extract record from angle text when available
            if hot_jt:
                _record = ''
                for _a in pos_angles:
                    _m = re.search(r'(?:14\s*days?|combo)\s*\(([^)]+)\)', _a, re.IGNORECASE)
                    if _m:
                        _record = f' ({_m.group(1)})'
                        break
                signals.append(('HOT_JT', '🔥 HOT J/T', f'Hot combo 14d{_record}'))

            trainer_rules = TRAINER_RULES.get(track_code, {})
            special_rule = ''
            for key, rule in trainer_rules.items():
                if key.lower() in trainer.lower():
                    special_rule = rule
                    break

            horse_data = {
                'pp': pp_num, 'name': horse, 'ml': ml,
                'trainer': trainer, 'trainer_stats': trainer_stats,
                'jockey': jockey, 'sire': sire,
                'prime_power': prime_power, 'pp_rank': pp_rank,
                'days_off': days_off, 'claim': claim_price,
                'pos_angles': pos_angles[:4], 'neg_angles': neg_angles[:3],
                'signals': signals, 'special_rule': special_rule,
                'recent_spd': recent_spd, 'best_spd': best_spd,
                'best_spd_turf': best_spd_turf, 'best_spd_aw': best_spd_aw,
                'improving': improving, 'jt_zero': jt_zero,
                'jt_winpct': jt_winpct,
            }

            if not any(h['name'] == horse for h in races[current_race]['horses']):
                races[current_race]['horses'].append(horse_data)

    return dict(races)


def is_trainer_hotjt(h):
    """True when the horse has both a TRAINER signal and a HOT_JT angle.
    Phase 6 finding: HOT_JT alone is heavily overpriced (EV_RATIO 0.06-0.20),
    but it upgrades an existing TRAINER signal to TRAINER+HOT_JT."""
    sig_types = {s[0] for s in h['signals']}
    return 'TRAINER' in sig_types and 'HOT_JT' in sig_types


def is_strong_pick(h):
    """True for 🔥 trainer (always), positive trainer+sire double, 🔥 horse,
    or TRAINER+HOT_JT upgrade. HOT_JT alone is display-only, NOT a pick
    (Phase 6: standalone HOT_JT EV_RATIO 0.06-0.20 = public overbets it).
    Iron trainer signals are never suppressed by negative/FADE sire flags.
    FADE sires (⚠️) do not qualify for the trainer+sire double pick."""
    signals = h['signals']
    if not signals:
        return False
    sig_types = {s[0] for s in signals}
    # 🔥 trainer always generates a pick regardless of sire
    for sig_type, sig, desc in signals:
        if sig_type == 'TRAINER' and '🔥' in sig:
            return True
    # trainer + positive sire double — ⚠️ FADE sires excluded
    if 'TRAINER' in sig_types:
        for sig_type, sig, desc in signals:
            if sig_type == 'SIRE' and ('🔥' in sig or '✅' in sig):
                return True
    for sig_type, sig, desc in signals:
        if sig_type == 'HORSE' and '🔥' in sig:
            return True
    # HOT_JT upgrades any TRAINER signal to a pick; alone it is display-only
    if is_trainer_hotjt(h):
        return True
    return False


def print_card(races, track_name, date_str, track_conditions, scratches=None, track_code='GP'):
    if scratches is None:
        scratches = {}

    print(f"\n{'='*76}")
    print(f"🏇 {track_name.upper()} — {date_str}")
    print(f"   {track_conditions}")
    print(f"{'='*76}")

    if scratches:
        print("\n📋 SCRATCHES:")
        for rn in sorted(scratches.keys()):
            for h in scratches[rn]:
                print(f"   R{rn}: {h} — SCR")

    all_picks = []

    for rn in sorted(races.keys()):
        race = races[rn]
        horses = sorted(race['horses'], key=lambda x: x['pp'])
        scr = scratches.get(rn, [])
        active = [h for h in horses if h['name'] not in scr]
        if not active:
            continue

        surf = race.get('surface', '')
        cond = race.get('conditions', '')[:50]
        purse = race.get('purse', '')

        print(f"\n{'─'*76}")
        print(f"RACE {rn}  {cond}  {surf}  {purse}")
        print(f"{'─'*76}")
        print(f"  {'PP':>3} {'Horse':<27} {'ML':>5}  {'PP Pwr':>8}  {'Trainer'}")

        race_picks = []

        for h in active:
            has_signal = bool(h['signals'])
            strong = is_strong_pick(h)
            flag = '⭐' if strong else ('·' if has_signal else '  ')
            pp_str = f"{h['prime_power']}({h['pp_rank']})" if h['prime_power'] != '?' else '?'

            print(f"\n  {flag} {h['pp']:>2}: {h['name']:<27} {h['ml']:>5}  {pp_str:>10}  {h['trainer'][:28]}")
            print(f"        Sire: {h['sire']:<30}  J: {h['jockey'][:20]}")
            if h.get('recent_spd'):
                recent_str = ', '.join(str(s) for s in h['recent_spd'])
                if surf == 'Turf' and h.get('best_spd_turf') is not None:
                    best_str = f"{h['best_spd_turf']} (Turf)"
                elif surf == 'AW' and h.get('best_spd_aw') is not None:
                    best_str = f"{h['best_spd_aw']} (AW)"
                else:
                    best_str = str(h['best_spd']) if h['best_spd'] else '—'
                trend = '  ✅ IMPROVING FORM' if h.get('improving') else ''
                print(f"        Recent SPD: {recent_str}   Best: {best_str}{trend}")
            if h['trainer_stats']:
                print(f"        Stats: {h['trainer_stats']}")
            if h['days_off'] >= 60:
                print(f"        ⏰ {h['days_off']} days off")
            if h['claim']:
                print(f"        Claim: ${h['claim']}")
            for sig_type, sig, desc in h['signals']:
                print(f"        🎯 [{sig_type}] {sig} — {desc}")
            if h['special_rule']:
                print(f"        ⚠️  RULE: {h['special_rule']}")
            for ang in h['pos_angles'][:2]:
                print(f"        ✅ {ang}")
            for ang in h['neg_angles'][:1]:
                print(f"        ❌ {ang}")

            if strong:
                race_picks.append(h)
                all_picks.append((rn, h))

        if race_picks:
            print(f"\n  ★ MODEL PICKS R{rn}:")
            # TRAINER+HOT_JT upgrades sort first, then by signal count
            for h in sorted(race_picks,
                            key=lambda x: (is_trainer_hotjt(x), len(x['signals'])),
                            reverse=True):
                base_sigs = ' + '.join(s[1] for s in h['signals'] if s[0] != 'HOT_JT')
                hot_tag  = '  🔥 TRAINER+HOT_JT' if is_trainer_hotjt(h) else ''
                warn_tag = '  ⚠️ 0% J/T'  if h.get('jt_zero') else ''
                print(f"    PP{h['pp']:>2}: {h['name']:<27} ({h['ml']:>5})  {base_sigs[:45]}{hot_tag}{warn_tag}")
        else:
            print(f"\n  ⚪ No primary model signals")

    # Summary
    print(f"\n{'='*76}")
    print(f"📊 MODEL SUMMARY — {len(all_picks)} ITM picks across {len(races)} races")
    print(f"{'='*76}")
    for rn, h in sorted(all_picks, key=lambda x: x[0]):
        sigs     = ' | '.join(s[1] for s in h['signals'] if s[0] != 'HOT_JT')
        hot_tag  = ' 🔥 TRAINER+HOT_JT' if is_trainer_hotjt(h) else ''
        warn_tag = ' ⚠️ 0% J/T'  if h.get('jt_zero') else ''
        print(f"  R{rn} PP{h['pp']:>2}: {h['name']:<27} ({h['ml']:>5})  {sigs[:40]}{hot_tag}{warn_tag}")
    print(f"{'='*76}\n")
    return all_picks


def extract_file_date(filepath, track_code, text=''):
    """Return the race date from the filename pattern or file text; None if not found."""
    stem = Path(filepath).stem.upper()
    tc = track_code.upper()

    # TRACKMMDDDYYUSA  e.g. CT050926USA, GP050826USA
    m = re.match(rf'^{re.escape(tc)}(\d{{2}})(\d{{2}})(\d{{2}})USA$', stem)
    if m:
        try:
            return date(2000 + int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass

    # TRACKx?MMDD...  e.g. CTX0507Y, GPX0508X, EVD0509Y, FPK0519Y
    m = re.match(rf'^{re.escape(tc)}[A-Z]?(\d{{2}})(\d{{2}})', stem)
    if m:
        try:
            return date(date.today().year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass

    # Fall back: scan first 3 000 chars of extracted text
    if text:
        sample = text[:3000]
        dm = re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b', sample)
        if dm:
            month, day, year = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
            if year < 100:
                year += 2000
            try:
                return date(year, month, day)
            except ValueError:
                pass
        MONTHS = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
        }
        dm = re.search(
            r'\b(January|February|March|April|May|June|July|August|'
            r'September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b',
            sample, re.IGNORECASE,
        )
        if dm:
            try:
                return date(int(dm.group(3)), MONTHS[dm.group(1).lower()], int(dm.group(2)))
            except ValueError:
                pass

    return None


def ml_to_float(ml_str):
    """Convert morning-line odds string to decimal odds (fractional + 1).

    US ML odds are expressed as 'to-1' fractions: '8/5' means 8-to-5, which
    pays 8/5 + 1 = 2.6 per unit stake. Plain integers ('5') mean 5-to-1 = 6.0.

    Examples: '15/1' → 16.0, '8/5' → 2.6, '7/2' → 4.5, '1/1' → 2.0, '5' → 6.0
    """
    if not ml_str or ml_str == '?':
        return None
    if '/' in ml_str:
        try:
            num, den = ml_str.split('/')
            return round(int(num) / int(den) + 1, 2)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(ml_str) + 1
    except ValueError:
        return None


def write_entries_db(races, track_code, race_date):
    """Persist every parsed starter (full field, not just picks) to the
    entries table in benter_model.db. This is the training data for the
    conditional-logit model — every card parsed without it is lost data.
    Returns rows written, or None if the DB write failed (non-fatal)."""
    try:
        import sqlite3
        import db_migrate

        conn = sqlite3.connect(Path(__file__).parent / 'benter_model.db')
        conn.executescript(db_migrate.DDL)
        tc = track_code.upper()
        date_str = race_date.isoformat()
        cur = conn.cursor()
        n = 0
        for rn, race in sorted(races.items()):
            cur.execute(
                "INSERT OR IGNORE INTO races(track,race_date,race_num,surface,conditions,purse)"
                " VALUES(?,?,?,?,?,?)",
                (tc, date_str, rn, race.get('surface') or None,
                 race.get('conditions') or '', db_migrate._purse(race.get('purse')))
            )
            race_id = cur.execute(
                "SELECT race_id FROM races WHERE track=? AND race_date=? AND race_num=?",
                (tc, date_str, rn)
            ).fetchone()[0]

            for h in race['horses']:
                try:
                    claim = float(h['claim'].replace(',', '')) if h['claim'] else None
                except (ValueError, AttributeError):
                    claim = None
                cur.execute(
                    "INSERT OR REPLACE INTO entries"
                    "(race_id,track,race_date,race_num,post_pos,horse_name,"
                    "ml_odds,prime_power,pp_rank,trainer,jockey,sire,"
                    "days_off,claim_price,best_spd,best_spd_turf,best_spd_aw,"
                    "recent_spd,improving,jt_zero,jt_winpct,signal_types,is_pick)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (race_id, tc, date_str, rn, h['pp'],
                     h['name'].replace(' ', ''),
                     ml_to_float(h['ml']),
                     float(h['prime_power']) if h['prime_power'] != '?' else None,
                     int(h['pp_rank']) if h['pp_rank'] != '?' else None,
                     h['trainer'] if h['trainer'] != '?' else None,
                     h['jockey'] if h['jockey'] != '?' else None,
                     h['sire'] if h['sire'] != '?' else None,
                     h['days_off'] or None,
                     claim,
                     h.get('best_spd'),
                     h.get('best_spd_turf'),
                     h.get('best_spd_aw'),
                     ','.join(str(s) for s in h.get('recent_spd', [])) or None,
                     int(bool(h.get('improving'))),
                     int(bool(h.get('jt_zero'))),
                     h.get('jt_winpct'),
                     ','.join(s[0] for s in h['signals']) or None,
                     int(is_strong_pick(h)))
                )
                n += 1
        conn.commit()
        conn.close()
        return n
    except Exception as e:
        print(f"WARNING: entries DB write failed — {e}")
        return None


def write_picks_file(all_picks, track_code, filepath):
    """Write picks_TRACK_DATE.txt next to this script for roi_tracker.py."""
    tc = track_code.upper()
    date_str = date.today().strftime('%m%d%Y')
    out_path = Path(__file__).parent / f"picks_{tc}_{date_str}.txt"
    lines = [
        f"# Benter Model Picks - {tc} {date_str}",
        "# Format: TRACK RACE HORSE SIGNAL BETS ML_ODDS PP_POWER TRAINER WIN_PROB EV_RATIO DAYS_OFF BEST_SPD SPD1 SPD2 SPD3 JT_WINPCT",
    ]
    for rn, h in sorted(all_picks, key=lambda x: x[0]):
        if is_trainer_hotjt(h):
            sig_type = 'TRAINER+HOT_JT'
        else:
            sig_type = h['signals'][0][0]
        horse_name = h['name'].replace(' ', '')
        ml_f       = ml_to_float(h['ml'])
        ml_col     = str(ml_f) if ml_f is not None else '?'
        pp_col     = h['prime_power'] if h['prime_power'] != '?' else '?'
        trainer_col = h['trainer'].replace(' ', '_') if h['trainer'] != '?' else '?'
        do_col     = str(h['days_off']) if h['days_off'] else '?'
        best_col   = str(h['best_spd']) if h.get('best_spd') else '?'
        recent     = h.get('recent_spd') or []
        spd_cols   = ' '.join(str(recent[i]) if i < len(recent) else '?' for i in range(3))
        jt_col     = str(h['jt_winpct']) if h.get('jt_winpct') is not None else '?'
        # WIN_PROB/EV_RATIO (cols 9-10) are '?' until prob_predict.py --in-place fills them
        lines.append(f"{tc} {rn} {horse_name} {sig_type} WPS {ml_col} {pp_col} {trainer_col}"
                     f" ? ? {do_col} {best_col} {spd_cols} {jt_col}")

    out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return out_path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 brisnet_parser_v2.py <file.pdf|txt> [TRACK]")
        sys.exit(1)

    filepath = sys.argv[1]
    track = sys.argv[2].upper() if len(sys.argv) > 2 else 'GP'
    track_names = {
        'GP': 'Gulfstream Park', 'CT': 'Charles Town',
        'FP': 'Fairmount Park',  'EVD': 'Evangeline Downs',
        'MVR': 'Mahoning Valley','DD': 'Delta Downs'
    }

    print(f"Parsing {filepath} for {track}...")
    text = extract_text(filepath)

    race_date = extract_file_date(filepath, track, text)
    today = date.today()
    if race_date is None:
        print(f"WARNING: Could not determine race date for {Path(filepath).name} — proceeding anyway.")
    elif race_date != today:
        print(f"SKIP: {Path(filepath).name} is dated {race_date.strftime('%m/%d/%Y')} — not today ({today.strftime('%m/%d/%Y')}). Skipping.")
        sys.exit(0)

    races = parse_brisnet(text, track, race_date or today)
    total = sum(len(r['horses']) for r in races.values())
    print(f"Found {len(races)} races, {total} horses\n")
    all_picks = print_card(races, track_names.get(track, track), 'Today', 'Fast', track_code=track)

    n_entries = write_entries_db(races, track, race_date or today)
    if n_entries:
        print(f"full-field entries → DB ({n_entries} horses)")

    if all_picks:
        out = write_picks_file(all_picks, track, filepath)
        print(f"picks file → {out.name}")

        # Phase 6: annotate picks with WIN_PROB / EV_RATIO (cols 9-10) if the
        # trained probability model is available. Failure is non-fatal.
        model_pkl = Path(__file__).parent / 'benter_model_prob.pkl'
        if model_pkl.exists():
            predict_script = Path(__file__).parent / 'prob_predict.py'
            r = subprocess.run([sys.executable, str(predict_script),
                                str(out), '--in-place'],
                               capture_output=True, text=True)
            if r.returncode == 0:
                print(f"win probabilities added → {out.name} (cols 9-10)")
                if BANKROLL > 0:
                    kelly_script = Path(__file__).parent / 'kelly_sizing.py'
                    k = subprocess.run([sys.executable, str(kelly_script),
                                        str(out), str(BANKROLL)],
                                       capture_output=True, text=True)
                    if k.returncode == 0:
                        print(k.stdout)
                    else:
                        print(f"WARNING: kelly_sizing.py failed")
                        if k.stderr.strip():
                            print(f"  {k.stderr.strip().splitlines()[-1]}")
            else:
                print(f"WARNING: prob_predict.py failed — picks file left without probabilities")
                if r.stderr.strip():
                    print(f"  {r.stderr.strip().splitlines()[-1]}")
