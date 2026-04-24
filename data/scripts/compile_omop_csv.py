import json, re, csv
from pathlib import Path
from collections import Counter

CACHE_DIR = Path(r"C:\Users\data1\.claude\projects\g---------KHNMC-atlas-auto-with-claude\c13e49b5-2fda-484d-a1ba-98d059692eee\tool-results")
SCRIPTS_DIR = Path(r"G:\내 드라이브\KHNMC\atlas_auto_with_claude\data\scripts")
DOCS_DIR = Path(r"G:\내 드라이브\KHNMC\atlas_auto_with_claude\studies\appendectomy\docs")

COUNTRY_PATTERNS = [
    ('Korea', r'\bKorea\b|\bSeoul\b|\bSuwon\b|\bBucheon\b|\bDaegu\b|\bBusan\b|\bIncheon\b|\bGwangju\b|\bUlsan\b|\bDaejeon\b|\bCheonan\b|\bGyeonggi\b|\bSeongnam\b|\bJinju\b|\bPohang\b'),
    ('USA', r'\bUSA\b|\bUnited States\b|\bU\.S\.A\b|\bNew York\b|\bBoston\b|\bStanford\b|\bColumbia\b|\bHarvard\b|\bPennsylvania\b|\bMichigan\b|\bMassachusetts\b|\bIllinois\b|\bTexas\b|\bPittsburgh\b|\bBaltimore\b|\bChicago\b|\bSeattle\b|\bNashville\b|\bAtlanta\b|\bOhio\b|\bFlorida\b|\bIndiana\b|\bDurham\b|\bMaryland\b|\bYale\b|\bJohns Hopkins\b|\bBethesda\b|\bCalifornia\b|\bLos Angeles\b|\bSan Francisco\b|\bSan Diego\b|\bPhiladelphia\b|\bProvidence\b|\bColumbus\b|\bNorth Carolina\b|\bMemphis\b|\bPortland\b|\bOregon\b|\bNew Jersey\b|\bGalveston\b|\bKansas\b|\bMissouri\b|\bHouston\b'),
    ('UK', r'\bUnited Kingdom\b|\bEngland\b|\bLondon\b|\bOxford\b|\bCambridge\b|\bManchester\b|\bEdinburgh\b|\bScotland\b|\bWales\b|\bBirmingham\b|\bNottingham\b|\bBristol\b|\bLeeds\b|\bLiverpool\b|\bBelfast\b|\bSwansea\b|\bDundee\b|\bUxbridge\b'),
    ('Germany', r'\bGermany\b|\bBerlin\b|\bMunich\b|\bHamburg\b|\bFrankfurt\b|\bHeidelberg\b|\bErlangen\b|\bLeipzig\b|\bDresden\b|\bKiel\b|\bAachen\b|\bBonn\b|\bMannheim\b|\bOsnabr|\bSaarbr|\bBremen\b|\bHannover\b'),
    ('France', r'\bFrance\b|\bParis\b|\bLyon\b|\bMarseille\b|\bStrasbourg\b|\bBordeaux\b|\bToulouse\b|\bAmiens\b|\bNancy\b|\bRouen\b|\bLille\b'),
    ('Spain', r'\bSpain\b|\bMadrid\b|\bBarcelona\b|\bValencia\b|\bSevill|\bBadalona\b'),
    ('Netherlands', r'\bNetherlands\b|\bAmsterdam\b|\bRotterdam\b|\bUtrecht\b|\bLeiden\b|\bErasmus\b|\bMaastricht\b|\bHolland\b'),
    ('Belgium', r'\bBelgium\b|\bBrussels\b|\bLeuven\b|\bGhent\b'),
    ('Italy', r'\bItaly\b|\bRome\b|\bMilan\b|\bBologna\b|\bNaples\b|\bFlorence\b|\bTurin\b'),
    ('China', r'\bChina\b|\bShanghai\b|\bBeijing\b|\bWuhan\b|\bGuangzhou\b'),
    ('Japan', r'\bJapan\b|\bTokyo\b|\bOsaka\b|\bKyoto\b'),
    ('Taiwan', r'\bTaiwan\b|\bTaipei\b|\bKaohsiung\b|\bHsinchu\b'),
    ('Singapore', r'\bSingapore\b'),
    ('Australia', r'\bAustralia\b|\bSydney\b|\bMelbourne\b|\bBrisbane\b|\bQueensland\b|\bAdelaide\b|\bPerth\b'),
    ('Canada', r'\bCanada\b|\bToronto\b|\bMontreal\b|\bVancouver\b|\bOttawa\b|\bOntario\b|\bQuebec\b'),
    ('Switzerland', r'\bSwitzerland\b|\bZurich\b|\bGeneva\b|\bBasel\b|\bLausanne\b'),
    ('Norway', r'\bNorway\b|\bOslo\b|\bBergen\b'),
    ('Sweden', r'\bSweden\b|\bStockholm\b|\bKarolinska\b'),
    ('Denmark', r'\bDenmark\b|\bCopenhagen\b|\bAarhus\b'),
    ('Finland', r'\bFinland\b|\bHelsinki\b'),
    ('Estonia', r'\bEstonia\b|\bTartu\b|\bTallinn\b'),
    ('Israel', r'\bIsrael\b|\bBeer Sheva\b|\bHaifa\b|\bJerusalem\b'),
    ('India', r'\bIndia\b|\bNew Delhi\b|\bMumbai\b|\bBangalore\b|\bChennai\b'),
    ('Portugal', r'\bPortugal\b|\bLisbon\b|\bPorto\b'),
    ('Austria', r'\bAustria\b|\bVienna\b|\bGraz\b|\bInnsbruck\b|\bSalzburg\b|\bTirol\b'),
    ('Ireland', r'\bIreland\b|\bDublin\b'),
    ('Poland', r'\bPoland\b|\bWarsaw\b|\bKrakow\b'),
    ('Greece', r'\bGreece\b|\bAthens\b|\bThessaloniki\b|\bHellas\b'),
    ('Turkey', r'\bTurkey\b|\bIstanbul\b|\bAnkara\b'),
    ('Brazil', r'\bBrazil\b|\bSao Paulo\b|\bRio de Janeiro\b'),
    ('Kenya', r'\bKenya\b|\bNairobi\b'),
    ('Luxembourg', r'\bLuxembourg\b|\bEsch-sur-Alzette\b'),
]

def detect_country(affs):
    if not affs: return 'Unknown'
    text = ' '.join(affs)
    hits = Counter()
    for country, pat in COUNTRY_PATTERNS:
        hits[country] += len(re.findall(pat, text, re.IGNORECASE))
    hits = {k: v for k, v in hits.items() if v > 0}
    if not hits: return 'Unknown'
    return max(hits.items(), key=lambda x: x[1])[0]

def detect_feedernet(article):
    text = (article.get('title','') or '') + ' ' + (article.get('abstract','') or '')
    for a in article.get('authors', []):
        for aff in a.get('affiliations', []):
            text += ' ' + (aff or '')
    return bool(re.search(r'feedernet|FEEDER-NET|feeder-net', text, re.IGNORECASE))

all_articles = {}
# Scan all json-like files in cache dir (skip the hook file)
for p in sorted(CACHE_DIR.iterdir()):
    if p.suffix != '.txt': continue
    if 'hook' in p.name: continue
    try:
        with open(p, encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        continue
    if not isinstance(data, dict): continue
    for art in data.get('articles', []):
        pmid = art.get('identifiers',{}).get('pmid','')
        if pmid: all_articles[pmid] = art

rows_cached = []
for pmid, art in all_articles.items():
    affs = []
    for a in art.get('authors', []):
        affs.extend(a.get('affiliations', []))
    rows_cached.append({
        'pmid': pmid,
        'doi': art.get('identifiers',{}).get('doi',''),
        'year': (art.get('publication_date') or {}).get('year',''),
        'journal': (art.get('journal') or {}).get('title',''),
        'title': (art.get('title','') or '').replace('\n',' ').strip(),
        'country': detect_country(affs),
        'feedernet': 'Yes' if detect_feedernet(art) else 'No',
    })

with open(SCRIPTS_DIR / 'omop_inline_metadata.json', encoding='utf-8') as f:
    rows_inline = json.load(f)

by_pmid = {r['pmid']: r for r in rows_cached}
for r in rows_inline:
    by_pmid[r['pmid']] = r

all_rows = sorted(by_pmid.values(), key=lambda r: (-(int(r['year']) if r['year'] and r['year'].isdigit() else 0), r['country'], r['title']))

out = DOCS_DIR / 'omop_cdm_papers_2021-2026.csv'
with open(out, 'w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['pmid','year','journal','country','feedernet','title','doi'])
    w.writeheader()
    for r in all_rows:
        w.writerow({'pmid':r['pmid'],'year':r['year'],'journal':r['journal'],'country':r['country'],
                    'feedernet':r['feedernet'],'title':r['title'],'doi':r['doi']})

print(f'Wrote {len(all_rows)} rows to {out}')
print('\n=== Country distribution ===')
for country, n in Counter(r['country'] for r in all_rows).most_common():
    print(f'  {country:15s} {n:3d}')
print('\n=== Feedernet distribution ===')
for flag, n in Counter(r['feedernet'] for r in all_rows).most_common():
    print(f'  {flag}: {n}')
print('\n=== Feedernet papers ===')
for r in all_rows:
    if r['feedernet']=='Yes':
        print(f'  [{r["year"]}] {r["country"]:10s} PMID {r["pmid"]}  {r["journal"]}')
        print(f'         {r["title"][:110]}')
print('\n=== Year distribution ===')
for y, n in sorted(Counter(r['year'] for r in all_rows).items()):
    print(f'  {y}: {n}')
