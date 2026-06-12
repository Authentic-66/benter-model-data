import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import brisnet_parser_v2 as bp

pdf = Path(__file__).parent.parent / 'CharlesTown' / 'ct-pps-files' / 'ctx0611y.pdf'
text = bp.extract_text(pdf)
rd = bp.extract_file_date(pdf, 'CT', text)
races = bp.parse_brisnet(text, 'CT', rd)
print('race date:', rd)
for rn in sorted(races)[:2]:
    for h in races[rn]['horses']:
        print(f"R{rn} {h['name']:<24} days_off={h['days_off']}")
