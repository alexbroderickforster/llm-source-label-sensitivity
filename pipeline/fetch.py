"""Download candidate HTML and extract Spanish article text, with per-host pacing."""
import argparse, hashlib, json, time
from urllib.parse import urlparse
import pandas as pd
import requests
import trafilatura
from config import DATA, UA

def main():
    p=argparse.ArgumentParser(); p.add_argument('--limit-per-domain',type=int,default=120); a=p.parse_args()
    html_dir=DATA/'cache/html'; out=DATA/'articles'; html_dir.mkdir(parents=True,exist_ok=True); out.mkdir(parents=True,exist_ok=True)
    last={}; counts={}; session=requests.Session(); session.headers['User-Agent']=UA
    for row in pd.read_csv(DATA/'candidates.csv').fillna('').to_dict('records'):
        url=row['url']; domain=urlparse(url).netloc.lower(); key=hashlib.sha256(url.encode()).hexdigest()
        dest=out/f'{key}.json'; raw=html_dir/f'{key}.html'; meta=html_dir/f'{key}.json'
        if dest.exists(): continue
        counts[domain]=counts.get(domain,0)+1
        if counts[domain]>a.limit_per_domain: continue
        try:
            if meta.exists() and json.loads(meta.read_text()).get('status',200)>=400: continue
            if raw.exists(): html=raw.read_text()
            elif meta.exists(): continue  # Cached failed fetch; do not hammer it.
            else:
                time.sleep(max(0,2-(time.monotonic()-last.get(domain,0)))); last[domain]=time.monotonic()
                r=session.get(url,timeout=40); meta.write_text(json.dumps({'url':url,'status':r.status_code,'final_url':r.url}))
                html=r.text; raw.write_text(html); r.raise_for_status()
            article=trafilatura.bare_extraction(html,url=url,with_metadata=True,include_comments=False, favor_precision=True)
            if not article: raise ValueError('empty extraction')
            if not isinstance(article,dict): article=article.as_dict()
            text=article.get('text') or ''
            if len(text.split())<80: raise ValueError('empty/short or paywalled article')
            if any(x in text.lower() for x in ['suscríbete para seguir leyendo','suscríbete para continuar leyendo','contenido exclusivo para suscriptores']): raise ValueError('paywall')
            result={'url':url,'domain':row['domain'],'title':article.get('title') or row['title'],'date':article.get('date'),'seendate':row['seendate'],'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest()}
            dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)); print(f'OK {domain}',flush=True)
        except Exception as e:
            with (DATA/'fetch_failures.jsonl').open('a') as f: f.write(json.dumps({'url':url,'error':str(e)},ensure_ascii=False)+'\n')
    print('Fetch complete',flush=True)
if __name__=='__main__': main()
