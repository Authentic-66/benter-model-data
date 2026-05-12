"""
Brisnet PP Parser v2.1 — Universal parser for TwinSpires/Brisnet 'y' format
Handles: GP, CT, FP and any other track
Key insight: 'Own:' line is the reliable anchor for each horse entry
Usage: python3 brisnet_parser_v2.py <pp_file.pdf|txt> [TRACK_CODE]
"""

import re, sys, subprocess
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

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
        "D'Angelo":  ('🔥 IRON GP #2','237W/3yr/22%'),
        'David':     ('🔥 IRON GP',   '175W/3yr/24%'),
        'Barboza':   ('🔥 IRON GP',   '150W/3yr'),
        'Casse':     ('🔥 IRON GP',   '138W/3yr/19%'),
        'Lynch':     ('🔥 IRON GP',   '64W/26%/chalk'),
        'Crichton':  ('🔥 IRON GP',   '110W/Jan-Apr best'),
        'Walsh':     ('🔥 IRON GP',   '31%/$13avg overlay'),
        'Cox':       ('🔥 IRON GP',   '34% — best rate at GP'),
        'Mott':      ('✅ POS GP',    '98W/29%'),
        'Pletcher':  ('✅ POS GP',    '98W/21%'),
        'Fawkes':    ('✅ POS GP',    '102W/3yr'),
        'Sano':      ('✅ OVR GP',    '99W/$12avg — bet 5/1+'),
        'Orseno':    ('✅ OVR GP',    '90W/$14avg overlay'),
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

IRON_SIRES = {
    # GP FL home-track sires
    'Khozan':         ('🔥 GP SIRE #1','106W/3yr — any price/surface GP'),
    'Bucchero':       ('🔥 GP FL SIRE','104W/3yr'),
    'Neolithic':      ('🔥 GP FL SIRE','99W/3yr — Abreu spe'),
    'Adios Charlie':  ('🔥 GP FL SIRE','81W/3yr'),
    'The Big Beast':  ('🔥 GP FL SIRE','73W/3yr'),
    'Awesome Slew':   ('🔥 GP FL SIRE','61W/3yr'),
    'Cajun Breeze':   ('✅ GP FL SIRE','49W/3yr'),
    # CT WV home-track sires
    'Juba':           ('🔥 CT SIRE #1','160W/3yr — WV home-track'),
    'Fiber Sonde':    ('🔥 CT SIRE #2','137W/3yr'),
    'Golden Years':   ('🔥 CT SIRE #3','94W/3yr'),
    'Windsor Castle': ('🔥 CT SIRE #4','90W/3yr'),
    'Uncle Lino':     ('✅ CT SIRE',   '69W/3yr'),
    'Great Notion':   ('✅ CT SIRE',   '62W/Jones Jr spe'),
    'Candygram':      ('✅ CT SIRE',   '46W/Sigler spe'),
    # FP IL home-track sires
    'Ghaaleb':        ('🔥 FP SIRE #1','29W — Becker spe'),
    'Cinco Charlie':  ('✅ FP+MVR',   'Cross-circuit positive'),
    # EVD/DD Louisiana sires
    'Star Guitar':    ('🔥 EVD SIRE #1','42W/3yr — any trainer'),
    'El Deal':        ('🔥 EVD+DD',   '28 EVD + 21 DD wins'),
    'Custom for Carlos':('🔥 EVD+DD', '25 EVD + 26 DD wins'),
    'Half Ours':      ('🔥 EVD SIRE', '27W/3yr'),
    'Astrology':      ('✅ EVD+DD',   '25W EVD'),
    # Cross-circuit sires
    'Curlin':         ('🔥 6-TRACK',  'Curlin+Casse GP = iron combo'),
    'Girvin':         ('🔥 3-TRACK',  'GP(80)+CT+EVD wins'),
    'Midshipman':     ('🔥 5-TRACK',  'CT+FP+EVD+MVR+DD'),
    'Goldencents':    ('🔥 4-TRACK',  'FP+EVD+MVR+DD'),
    'Union Rags':     ('🔥 7-TRACK',  'Universal iron sire'),
    'Mor Spirit':     ('✅ 3-TRACK',  'FP+MVR+DD'),
    'Into Mischief':  ('✅ GP SIRE',  '64W/3yr GP'),
    'Constitution':   ('✅ GP SIRE',  '66W/3yr GP'),
    'Temple City':    ('✅ TURF',     'Positive turf signal'),
    'Justify':        ('✅ GP SIRE',  'National positive'),
    'Not This Time':  ('✅ GP SIRE',  '17W GP'),
    # MVR Ohio sires
    'Drill':          ('🔥 MVR #1',   '16W full meet'),
    'Tale of Ekati':  ('🔥 MVR SIRE', '11W Ohio home-track'),
    'Kantharos':      ('🔥 MVR SIRE', '12W full meet'),
    'Rivers Run Deep':('✅ MVR SIRE', '12W full meet'),
    'Saturnalia':     ('✅ POS SIRE', 'International positive at GP'),
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
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text(layout=True) or '' for page in pdf.pages]
    return '\f'.join(pages)

def parse_brisnet(text, track_code='GP'):
    pages = text.split('\f')
    races = defaultdict(lambda: {'conditions': '', 'purse': '', 'surface': '', 'horses': []})
    current_race = 1

    for i, page in enumerate(pages):
        if len(page.strip()) < 50:
            continue

        lines = page.split('\n')
        header = lines[0]

        # ── Race number from header ───────────────────────────────────────────
        race_m = re.search(r'Race\s+(\d+)', header)
        if race_m:
            current_race = int(race_m.group(1))

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
            # Summary/stats page — grab purse if available
            purse_m = re.search(r'Purse\s+\$([\d,]+)', page)
            if purse_m and current_race:
                races[current_race]['purse'] = f"${purse_m.group(1)}"
            continue

        # ── Extract horse data using 'Own:' as anchor ─────────────────────────
        horse = '?'
        pp_num = 0
        ml = '?'
        trainer = '?'
        trainer_stats = ''
        jockey = '?'
        sire = '?'
        prime_power = '?'
        pp_rank = '?'
        days_off = 0
        pos_angles = []
        neg_angles = []
        claim_price = None

        # Find Own: line → PP# is at start of that line
        for j, line in enumerate(lines):
            om = re.match(r'^(\d+)\s+Own:', line)
            if om:
                pp_num = int(om.group(1))

                # Horse name: search backwards from Own: line
                for k in range(j-1, max(0, j-4), -1):
                    prev = lines[k]
                    # Pattern: spaces + HorseName (Type N) + optional $claim + breed info
                    hm = re.search(r'([A-Z][A-Za-z\'"\-\. ]+?)\s+\([A-Z/EP]+\s+\d+\)', prev)
                    if hm:
                        horse = hm.group(1).strip()
                        # Claim price
                        claim_m = re.search(r'\$(\d{1,3},?\d{3})', prev)
                        if claim_m:
                            claim_price = claim_m.group(1)
                        break
                break

        # Prime Power: check header line and early lines
        ppm = re.search(r'Prime\s+P(?:ower)?[:\s]*([\d.]+)\s*\((\d+)', lines[0])
        if ppm:
            prime_power = ppm.group(1)
            pp_rank = ppm.group(2)

        # Scan all lines for remaining fields
        for j, line in enumerate(lines):

            # Prime Power (in body)
            if prime_power == '?':
                ppm = re.search(r'Prime Power:\s*([\d.]+)\s*\((\d+)', line)
                if ppm:
                    prime_power = ppm.group(1)
                    pp_rank = ppm.group(2)

            # ML odds: "9/2  White, Red..." — silks line
            if ml == '?':
                ml_m = re.match(r'^(\d+/\d+|\d+)\s+[A-Z][a-z]', line.strip())
                if ml_m and 'Own:' not in line and 'Trnr:' not in line and 'Sire' not in line:
                    val = ml_m.group(1)
                    if '/' in val or (val.isdigit() and 1 <= int(val) <= 99):
                        ml = val

            # Trainer
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

            # Jockey: "LASTNAME FIRSTNAME (N/ N N%)"
            if jockey == '?':
                jm = re.search(r'^([A-Z]{2,}(?:\s+[A-Z]+){0,3})\s+\(\d+/\s*\d+\s+\d+%\)', line)
                if jm:
                    jockey = jm.group(1).title()

            # Sire: multiple formats
            if sire == '?':
                sm = re.search(r'Sire\s*:\s*=?([A-Z][A-Za-z\'"\-\. \(\)]+?)\s*\(', line)
                if sm:
                    sire_raw = sm.group(1).strip()
                    # Remove sale info etc
                    sire = re.sub(r'\s*\([^)]*\)\s*$', '', sire_raw).strip()
                elif re.search(r'Sire\s*:\s*$', line.strip()):
                    # Sire on next line
                    if j+1 < len(lines):
                        next_line = lines[j+1].strip().lstrip('=')
                        sn = re.match(r'([A-Z][A-Za-z\'"\-\. ]+?)\s*[\($]', next_line)
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

        if horse == '?' or pp_num == 0:
            continue

        # ── Apply model signals ───────────────────────────────────────────────
        signals = []
        track_trainers = IRON_TRAINERS.get(track_code, {})

        for key, (sig, desc) in track_trainers.items():
            if key.lower() in trainer.lower():
                signals.append(('TRAINER', sig, desc))
                break

        for key, (sig, desc) in IRON_SIRES.items():
            if key.lower() in sire.lower():
                signals.append(('SIRE', sig, desc))
                break

        for key, (sig, desc) in IRON_HORSES.items():
            if key.lower() in horse.lower():
                signals.append(('HORSE', sig, desc))
                break

        # Special rules
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
        }

        if not any(h['name'] == horse for h in races[current_race]['horses']):
            races[current_race]['horses'].append(horse_data)

    return dict(races)


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
            flag = '⭐' if has_signal else '  '
            pp_str = f"{h['prime_power']}({h['pp_rank']})" if h['prime_power'] != '?' else '?'

            print(f"\n  {flag} {h['pp']:>2}: {h['name']:<27} {h['ml']:>5}  {pp_str:>10}  {h['trainer'][:28]}")
            print(f"        Sire: {h['sire']:<30}  J: {h['jockey'][:20]}")
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

            if has_signal:
                race_picks.append(h)
                all_picks.append((rn, h))

        if race_picks:
            print(f"\n  ★ MODEL PICKS R{rn}:")
            for h in sorted(race_picks, key=lambda x: len(x['signals']), reverse=True):
                sigs = ' + '.join([s[1] for s in h['signals']])
                print(f"    PP{h['pp']:>2}: {h['name']:<27} ({h['ml']:>5})  {sigs[:50]}")
        else:
            print(f"\n  ⚪ No primary model signals")

    # Summary
    print(f"\n{'='*76}")
    print(f"📊 MODEL SUMMARY — {len(all_picks)} ITM picks across {len(races)} races")
    print(f"{'='*76}")
    for rn, h in sorted(all_picks, key=lambda x: x[0]):
        sigs = ' | '.join([s[1] for s in h['signals']])
        print(f"  R{rn} PP{h['pp']:>2}: {h['name']:<27} ({h['ml']:>5})  {sigs[:45]}")
    print(f"{'='*76}\n")
    return all_picks


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
    races = parse_brisnet(text, track)
    total = sum(len(r['horses']) for r in races.values())
    print(f"Found {len(races)} races, {total} horses\n")
    print_card(races, track_names.get(track, track), 'Today', 'Fast', track_code=track)
