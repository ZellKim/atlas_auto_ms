"""
Correct TSH (3009201) + Vit D (3020149, 40765040, 42529187) concepts
— vocab-verified, re-survey with right IDs.
"""
import csv, json, os, sys, time, functools
print = functools.partial(print, flush=True)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from atlas_auto.client import FedernetClient

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(DATA_DIR, 'v4_tsh_vitd_survey.csv')
RAW = os.path.join(DATA_DIR, 'v4_tsh_vitd_raw.json')

CONCEPTS = [
    (3009201,  'TSH',        'mIU/L',   'Tier1'),
    (3020149,  'VitD_D3',    'ng/mL',   'Tier1'),
    (40765040, 'VitD_total', 'ng/mL',   'Tier1'),
    (42529187, 'VitD_totIA', 'ng/mL',   'Tier1'),
]

SITES = [
    {'code':'AUMC','group_id':9,'site_id':191,'sourceKey':'cdmpv53_251128'},
    {'code':'CHNUH','group_id':95,'site_id':227,'sourceKey':'cdm'},
    {'code':'DCMC','group_id':16,'site_id':196,'sourceKey':'cdmpv53_251128'},
    {'code':'DSMC','group_id':103,'site_id':235,'sourceKey':'cdmpv53_251128'},
    {'code':'EUMC','group_id':5,'site_id':197,'sourceKey':'cdmpv53_251128'},
    {'code':'GNUCH','group_id':86,'site_id':224,'sourceKey':'cdmpv53_251128'},
    {'code':'GNUH','group_id':88,'site_id':198,'sourceKey':'cdmpv53_251128'},
    {'code':'HUMC','group_id':117,'site_id':256,'sourceKey':'cdmpv53_251128'},
    {'code':'ISH','group_id':81,'site_id':222,'sourceKey':'cdmpv53_251128'},
    {'code':'JCMJ','group_id':93,'site_id':226,'sourceKey':'cdmpv53_250317'},
    {'code':'KCCH','group_id':91,'site_id':225,'sourceKey':'cdmpv53_251128'},
    {'code':'KDH','group_id':4,'site_id':201,'sourceKey':'cdmpv53_251128'},
    {'code':'KHMC','group_id':11,'site_id':202,'sourceKey':'cdmpv53_251128'},
    {'code':'KHNMC','group_id':7,'site_id':203,'sourceKey':'cdmpv53_251128'},
    {'code':'KWMC','group_id':10,'site_id':213,'sourceKey':'cdmpv53_251128'},
    {'code':'MJH','group_id':67,'site_id':204,'sourceKey':'cdmpv53_251128'},
    {'code':'PNUH','group_id':3,'site_id':190,'sourceKey':'cdmpv53_251128'},
    {'code':'SCHBC','group_id':29,'site_id':206,'sourceKey':'cdmpv533'},
    {'code':'SCHCA','group_id':28,'site_id':207,'sourceKey':'cdmpv533'},
    {'code':'SCHGM','group_id':30,'site_id':208,'sourceKey':'cdmpv533'},
    {'code':'SCHSU','group_id':27,'site_id':209,'sourceKey':'cdmpv533'},
    {'code':'UUH','group_id':99,'site_id':243,'sourceKey':'cdm_0023'},
    {'code':'WKUH','group_id':13,'site_id':188,'sourceKey':'cdmpv53_251126'},
]


def extract(raw):
    if not isinstance(raw, dict): return []
    unit_counts = {u.get('conceptName','?'): (u.get('conceptId',0), u.get('countValue',0))
                    for u in (raw.get('recordsByUnit') or [])}
    out = []
    for d in (raw.get('measurementValueDistribution') or []):
        u = d.get('category','?')
        uc, cnt = unit_counts.get(u, (0, 0))
        out.append({'unit_concept_id':uc, 'unit_name':u, 'count':cnt,
                    'min':d.get('minValue'), 'p10':d.get('p10Value'),
                    'p25':d.get('p25Value'), 'median':d.get('medianValue'),
                    'p75':d.get('p75Value'), 'p90':d.get('p90Value'),
                    'max':d.get('maxValue')})
    seen_units = {d.get('category') for d in (raw.get('measurementValueDistribution') or [])}
    for u, (uc, cnt) in unit_counts.items():
        if u not in seen_units:
            out.append({'unit_concept_id':uc,'unit_name':u,'count':cnt,
                        'min':None,'p10':None,'p25':None,'median':None,
                        'p75':None,'p90':None,'max':None})
    return out


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--email', required=True)
    p.add_argument('--password', required=True)
    args = p.parse_args()
    c = FedernetClient()
    c.login_portal(args.email, args.password)

    results = []
    raw_all = {}
    for si, site in enumerate(SITES):
        print(f"[{si+1}/{len(SITES)}] {site['code']}")
        if not c.connect_site(group_id=site['group_id'], site_id=site['site_id']):
            print('  SKIP'); continue
        for cid, bm, unit, tier in CONCEPTS:
            try:
                raw = c.get_achilles_drilldown(site['sourceKey'], 'measurement', int(cid))
                raw_all[f"{site['code']}_{cid}"] = raw
                entries = extract(raw)
                if not entries:
                    results.append({'site':site['code'],'concept_id':cid,'biomarker':bm,
                                     'expected_unit':unit,'tier':tier,
                                     'unit_concept_id':0,'unit_name':'NO_DATA','count':0,
                                     'min':'','p10':'','p25':'','median':'','p75':'','p90':'','max':''})
                else:
                    for e in entries:
                        row = {'site':site['code'],'concept_id':cid,'biomarker':bm,
                               'expected_unit':unit,'tier':tier}
                        row.update(e)
                        results.append(row)
            except Exception:
                pass
            time.sleep(0.2)

    with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['site','concept_id','biomarker','expected_unit','tier',
                                            'unit_concept_id','unit_name','count',
                                            'min','p10','p25','median','p75','p90','max'])
        w.writeheader(); w.writerows(results)
    print(f"Saved {len(results)} rows -> {OUT}")
    with open(RAW,'w',encoding='utf-8') as f: json.dump(raw_all, f, ensure_ascii=False)


if __name__ == '__main__':
    main()
