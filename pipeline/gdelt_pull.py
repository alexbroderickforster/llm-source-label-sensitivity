"""Polite, resumable GDELT discovery; cache failures as well as successes."""
import argparse, hashlib, json, time
from datetime import datetime, timedelta, timezone
import pandas as pd
import requests
from config import DATA, STATE_DOMAINS, REFERENCE_DOMAINS, UA
ENDPOINT = 'https://api.gdeltproject.org/api/v2/doc/doc'
FIELDS = ['url','domain','title','seendate','language','sourcecountry']

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--days',type=int,default=90)
    p.add_argument('--window-days',type=int,default=7)
    p.add_argument('--domains',nargs='+',default=STATE_DOMAINS+REFERENCE_DOMAINS)
    p.add_argument('--end',default=datetime.now(timezone.utc).strftime('%Y-%m-%d'))
    p.add_argument('--max-errors',type=int,default=3)
    a=p.parse_args(); cache=DATA/'cache/gdelt'; cache.mkdir(parents=True,exist_ok=True)
    end=datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc); start=end-timedelta(days=a.days)
    rows={}; errors=0
    clock=cache/'last_request.json'
    pending=[]
    # Window-major order ensures each domain is checked before expanding history.
    right=end
    while right>start:
        left=max(start,right-timedelta(days=a.window_days))
        pending.extend((domain,left,right) for domain in a.domains)
        right=left
    while pending:
        domain,left,right=pending.pop(0)
        params={'query':f'domain:{domain} sourcelang:spanish','mode':'ArtList','format':'json','maxrecords':250,'startdatetime':left.strftime('%Y%m%d%H%M%S'),'enddatetime':right.strftime('%Y%m%d%H%M%S'),'sort':'DateDesc'}
        key=hashlib.sha256(json.dumps(params,sort_keys=True).encode()).hexdigest(); path=cache/f'{key}.json'
        if path.exists(): record=json.loads(path.read_text())
        else:
            previous=json.loads(clock.read_text()).get('timestamp',0) if clock.exists() else 0
            time.sleep(max(0,6-(time.time()-previous)))
            clock.write_text(json.dumps({'timestamp':time.time()}))
            try:
                r=requests.get(ENDPOINT,params=params,headers={'User-Agent':UA},timeout=60)
                record={'params':params,'status':r.status_code,'raw':r.text,'fetched_at':datetime.now(timezone.utc).isoformat()}
                try: record['payload']=r.json()
                except ValueError: pass
            except requests.RequestException as e: record={'params':params,'error':str(e)}
            path.write_text(json.dumps(record,ensure_ascii=False,indent=2))
        payload=record.get('payload',{}); articles=payload.get('articles',[]) if isinstance(payload,dict) else []
        bad=record.get('status')!=200 or not isinstance(payload,dict) or 'articles' not in payload
        print(f'{domain} {left.date()}..{right.date()}: {len(articles)} articles'+(' ERROR' if bad else ''),flush=True)
        if bad or not articles:
            errors+=1
            # Never retry identical cached queries. Back off before any next query.
            time.sleep(min(120,6*2**errors))
        else: errors=0
        for article in articles:
            url=article.get('url','')
            if url: rows[url]={k:article.get(k,'') for k in FIELDS}; rows[url]['domain']=domain
        if len(articles)==250 and (right-left)>timedelta(days=1):
            middle=left+(right-left)/2
            pending[0:0]=[(domain,left,middle),(domain,middle,right)]
            print('CAP: automatically subdividing window',flush=True)
        if errors>=a.max_errors:
            print('Stopping after consecutive empty/error responses; cached queries will not be retried.',flush=True)
            write(rows); return
    write(rows)

def write(rows):
    path=DATA/'candidates.csv'
    if path.exists():
        for row in pd.read_csv(path).fillna('').to_dict('records'): rows.setdefault(row['url'],row)
    pd.DataFrame(list(rows.values()),columns=FIELDS).to_csv(path,index=False)
    print(f'Saved {len(rows)} unique candidates',flush=True)
if __name__=='__main__': main()
