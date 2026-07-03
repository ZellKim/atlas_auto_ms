import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'automation'))
from credentials import get_feedernet_credentials

"""
Update data/site_mapping/site_summary_23.csv:
- Fill UUH missing data from feedernet dashboard API
- Add source_key column (queried DB name, from source_key_mapping.csv)
"""
import os, csv, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.stdout.reconfigure(encoding='utf-8')

from atlas_auto.client import FedernetClient

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data')
SUMMARY = os.path.join(ROOT, 'site_mapping', 'site_summary_23.csv')
SOURCE_KEY_MAP = os.path.join(ROOT, 'site_mapping', 'source_key_mapping.csv')
FULL_MAP = os.path.join(ROOT, 'site_mapping', 'site_id_mapping_full.csv')

# Load source_key mapping
sk_by_code = {}
with open(SOURCE_KEY_MAP, encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        sk_by_code[r['code'].strip()] = r['sourceKey'].strip()

# Load Korean institution names
inst_by_code = {}
with open(FULL_MAP, encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        inst_by_code[r['code'].strip()] = r['institution'].strip()

# Load current summary
with open(SUMMARY, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    orig_fields = reader.fieldnames or []

print(f'Loaded {len(rows)} sites from {SUMMARY}')
print(f'Current columns: {orig_fields}')

# Fetch UUH via dashboard
client = FedernetClient()
client.login_portal(*get_feedernet_credentials())
cdms = client.get_available_cdms()
by_name = {c.get('cdmName'): c for c in cdms}

uuh_info = by_name.get('UUH_5.3.0_04')
if uuh_info:
    pc = uuh_info.get('patientCount')
    period = uuh_info.get('period', '')
    print(f'UUH fetched: patientCount={pc}, period={period!r}')
    # parse period "YYYY/MM ~ YYYY/MM"
    if '~' in period:
        start_s, end_s = [s.strip() for s in period.split('~', 1)]
        start_y = start_s.split('/')[0] if '/' in start_s else start_s
        end_y = end_s.split('/')[0] if '/' in end_s else end_s
    else:
        start_y, end_y = '?', '?'
    for row in rows:
        if row['code'] == 'UUH':
            row['period_start'] = start_y
            row['period_end'] = end_y
            row['total_persons'] = f'{pc:,}' if pc else '?'
            print(f'UUH row updated: {row}')
            break
else:
    print('⚠️ UUH not found in dashboard')

# Add source_key column (after 'source')
new_fields = list(orig_fields)
if 'source_key' not in new_fields:
    insert_at = new_fields.index('source') + 1 if 'source' in new_fields else len(new_fields)
    new_fields.insert(insert_at, 'source_key')

# Add Korean institution name column (after 'code')
if 'institution' not in new_fields:
    insert_at = new_fields.index('code') + 1 if 'code' in new_fields else 1
    new_fields.insert(insert_at, 'institution')

for row in rows:
    row['source_key'] = sk_by_code.get(row['code'], '?')
    row['institution'] = inst_by_code.get(row['code'], '?')

# Write back
with open(SUMMARY, 'w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=new_fields)
    w.writeheader()
    w.writerows(rows)

print(f'\nUpdated: {SUMMARY}')
print(f'New columns: {new_fields}')
