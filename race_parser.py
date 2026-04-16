import re, math, pdfplumber

MONTH_RE  = re.compile(r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b')
DIST_RE   = re.compile(r'(\d{2})m[A-Za-z0-9]*')
RTIME_RE  = re.compile(r'\b\d-\d{2}\.\d{2}\b')
DMET_RE   = re.compile(r'(\d{4})\s*Mts\.')
HORSE_RE  = re.compile(r'^(\d+)\.\s+([A-Z][A-Z\s\.\-\/\']+?)\s+(\d+\.?\d*)\s+[A-Z]')

def parse_odds(token):
    if not token: return 0
    token = re.sub(r'^[xXsS]', '', token.strip())
    if '/' in token:
        p = token.split('/')
        try: return round(float(p[0]) / float(p[1]), 2)
        except: return 0
    try: return float(token)
    except: return 0

def horse_time_to_sec(s):
    s = s.rstrip('f').strip()
    try:
        v = float(s)
        return round(60 + v, 2)
    except: return 0

def parse_record(line):
    if not MONTH_RE.search(line): return None
    dm = DIST_RE.search(line)
    if not dm: return None
    if not RTIME_RE.search(line): return None

    date_m = MONTH_RE.search(line)
    between = line[date_m.end():dm.start()].strip()
    tokens = between.split()
    odds_tok = None
    for t in tokens:
        if re.match(r'^[a-zA-Z]+$', t) and len(t) <= 3: continue
        if re.match(r'^[xXsS]?\d', t):
            odds_tok = t; break
    odds = parse_odds(odds_tok)

    distance = int(dm.group(1)) * 100
    rest = line[dm.end():].strip()
    wm = re.match(r'(\d+\.?\d*)', rest)
    if not wm: return None
    weight = float(wm.group(1))

    rt_m = RTIME_RE.search(line)
    after_rt = line[rt_m.end():].strip()
    pnr_m = re.match(r'(\d+\.\d+)', after_rt)
    if not pnr_m: return None
    pnr = float(pnr_m.group(1))

    after_pnr = after_rt[pnr_m.end():].strip()
    ht_m = re.match(r'(\d{2}\.\d{2})f?', after_pnr)
    if not ht_m: return None
    horse_time = horse_time_to_sec(ht_m.group(1))

    return {'distance': distance, 'weight': weight,
            'pnr': pnr, 'horse_time': horse_time, 'odds': odds}

def parse_pdf(file_path):
    races, current_race, current_horse = [], None, None

    def save_horse():
        if current_horse and current_race:
            current_race['horses'].append(current_horse)

    def save_race():
        save_horse()
        if current_race:
            races.append(current_race)

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            lines = text.split('\n')
            for i, raw in enumerate(lines):
                line = raw.strip()
                dm = DMET_RE.search(line)
                if dm and current_race:
                    current_race['current_dist'] = int(dm.group(1))

                rh = re.match(r'^(\d+)\s*$', line)
                if rh and i + 1 < len(lines) and lines[i+1].strip().startswith('('):
                    save_race()
                    current_race = {'race_num': int(rh.group(1)),
                                    'race_name': lines[i+1].strip(),
                                    'current_dist': 1100, 'horses': []}
                    current_horse = None
                    continue

                hm = HORSE_RE.match(line)
                if hm and current_race:
                    save_horse()
                    current_horse = {'num': int(hm.group(1)),
                                     'name': hm.group(2).strip(),
                                     'new_weight': float(hm.group(3)),
                                     'records': []}
                    continue

                if current_horse:
                    rec = parse_record(line)
                    if rec:
                        current_horse['records'].append(rec)

    save_race()
    return races

def compute_race(race, std_pnr=3.5):
    cur_dist = race['current_dist']
    rows = []
    for h in race['horses']:
        recs = h['records']
        if not recs:
            rows.append({'Sl.No': h['num'], 'Name': h['name'] + ' ⚠️ First Timer',
                         'Old Weight': 'NA', 'New Weight': h['new_weight'],
                         'Old Distance': 'NA', 'Current Distance': cur_dist,
                         'Old Time(sec)': 'NA', 'PNR Race': 'NA',
                         'Standard PNR': 'NA', 'Adjusted Time': 'NA',
                         'Speed Rating': 'NA', 'ODDS': 'NA',
                         'Final Rating': 'NA', 'Speed Rank': 'NA',
                         'Odds Rank': 'NA', 'Value Score': 'NA'})
            continue
        last3 = recs[-3:]
        avg_w  = round(sum(r['weight'] for r in last3) / len(last3), 2)
        avg_d  = round(sum(r['distance'] for r in last3) / len(last3), 0)
        avg_t  = round(sum(r['horse_time'] for r in last3) / len(last3), 2)
        avg_p  = round(sum(r['pnr'] for r in last3) / len(last3), 2)
        odds   = recs[-1]['odds']
        adj_t  = round(avg_t - (avg_d - cur_dist)*0.0625 - (avg_w - h['new_weight'])/10 - (avg_p - std_pnr)*2, 2)
        sr     = math.ceil((cur_dist / adj_t)*100 - 1000) if adj_t > 0 else 0
        rows.append({'Sl.No': h['num'], 'Name': h['name'],
                     'Old Weight': avg_w, 'New Weight': h['new_weight'],
                     'Old Distance': avg_d, 'Current Distance': cur_dist,
                     'Old Time(sec)': avg_t, 'PNR Race': avg_p,
                     'Standard PNR': std_pnr, 'Adjusted Time': adj_t,
                     'Speed Rating': sr, 'ODDS': odds,
                     'Final Rating': 0, 'Speed Rank': 0, 'Odds Rank': 0, 'Value Score': 0})

    valid = [r for r in rows if isinstance(r['Speed Rating'], (int, float)) and r['Speed Rating'] != 0]
    speeds = sorted(set(r['Speed Rating'] for r in valid), reverse=True)
    odds_s = sorted(set(r['ODDS'] for r in valid))
    for r in valid:
        r['Speed Rank'] = speeds.index(r['Speed Rating']) + 1
        r['Odds Rank']  = odds_s.index(r['ODDS']) + 1
        r['Final Rating'] = round(r['Speed Rating'] * (1/(r['ODDS']+1)), 2) if r['ODDS'] else 0
        r['Value Score']  = round(r['Speed Rank']/r['Odds Rank'], 2) if r['Odds Rank'] else 0
    return rows
