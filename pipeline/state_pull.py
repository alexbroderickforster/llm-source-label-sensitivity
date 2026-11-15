"""Discover recent state articles from publisher sitemaps, then stratify by country."""
import argparse, collections, json, re, random
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from dateutil.parser import parse
from config import DATA
from match_events import countries
from source_client import Client
NS={'s':'http://www.sitemaps.org/schemas/sitemap/0.9','n':'http://www.google.com/schemas/sitemap-news/0.9'}
EXCLUDE=re.compile(r'(?:/opinion/|/video/|/videos/|/en-vivo/|/live/|en-directo|minuto-a-minuto|\bopini[oó]n\b|\ben vivo\b|\ben directo\b)',re.I)
def elements(body):
    root=ET.fromstring(body)
    return root, root.findall('s:sitemap',NS),root.findall('s:url',NS)
def main():
    p=argparse.ArgumentParser(); p.add_argument('--days',type=int,default=60); p.add_argument('--limit',type=int,default=150); p.add_argument('--end'); a=p.parse_args()
    end=parse(a.end).replace(tzinfo=timezone.utc) if a.end else datetime.now(timezone.utc)
    start=end-timedelta(days=a.days); c=Client(); pool=[]; stats=collections.Counter(); errors=[]
    for outlet,index in [('RT','https://actualidad-rt.com/sitemap.xml'),('Sputnik','https://noticiaslatam.lat/sitemap_article_index.xml')]:
        queue=[index]; seen=set()
        while queue:
            url=queue.pop(0)
            if url in seen: continue
            seen.add(url)
            try:
                body,_=c.get(url); root,maps,entries=elements(body); stats[outlet+'_sitemaps']+=1
                for item in maps:
                    loc=item.findtext('s:loc',namespaces=NS) or ''
                    if outlet=='RT' and any('sitemap_'+str(y)+'.xml' in loc for y in range(start.year,end.year+1)): queue.append(loc)
                    if outlet=='Sputnik':
                        match=re.search(r'date_start=(\d{8})',loc)
                        if match and start.strftime('%Y%m')<=match[1][:6]<=end.strftime('%Y%m'): queue.append(loc)
                for item in entries:
                    stats[outlet+'_listed']+=1
                    loc=item.findtext('s:loc',namespaces=NS) or ''
                    title=item.findtext('.//n:title',namespaces=NS) or ''
                    dt=item.findtext('.//n:publication_date',namespaces=NS) or item.findtext('s:lastmod',namespaces=NS)
                    if not dt: stats['missing_date']+=1; continue
                    try: day=parse(dt).replace(tzinfo=timezone.utc)
                    except (ValueError,TypeError): continue
                    if not start<=day<=end: continue
                    stats[outlet+'_in_window']+=1
                    if EXCLUDE.search(loc+' '+title): continue
                    if outlet=='RT' and not re.search(r'/actualidad/\d+-',loc): continue
                    # URL slugs generally carry the title; avoid speculative article requests.
                    mentions=countries(loc.replace('-',' ')+' '+title)
                    country=max(mentions,key=mentions.get)
                    if not mentions[country]: continue
                    pool.append({'url':loc,'title':title,'date':day.isoformat(),'country':country,'outlet':outlet})
            except Exception as e: errors.append({'url':url,'error':str(e)}); print(str(e),flush=True)
    pool=list({r['url']:r for r in pool}.values()); stats['geographic_pool']=len(pool)
    (DATA/'state_discovered.json').write_text(json.dumps(pool,ensure_ascii=False,indent=2))
    buckets=collections.defaultdict(list)
    for row in pool: buckets[row['country']].append(row)
    rng=random.Random(20261113)
    for bucket in buckets.values(): rng.shuffle(bucket)
    chosen=[]
    while buckets and len(chosen)<min(a.limit,150):
        for country in sorted(list(buckets)):
            if len(chosen)>=min(a.limit,150): break
            chosen.append(buckets[country].pop())
            if not buckets[country]: del buckets[country]
    stats['sampled']=len(chosen); articles=[]
    (DATA/'state_sample.json').write_text(json.dumps(chosen,ensure_ascii=False,indent=2))
    for i,row in enumerate(chosen):
        try:
            article=c.article(row['url'])
            if EXCLUDE.search(article['title']): raise ValueError('excluded genre')
            article.update(country=row['country'],outlet=row['outlet'],sitemap_date=row['date'])
            article['date']=article.get('date') or row['date']
            if not start.date()<=parse(article['date']).date()<=end.date(): raise ValueError('extracted date outside window')
            articles.append(article); stats['extracted']+=1
        except Exception as e: errors.append({'url':row['url'],'error':str(e)}); stats['fetch_rejected']+=1
        print(f"state {i+1}/{len(chosen)} retained={len(articles)}",flush=True)
        (DATA/'state_articles.json').write_text(json.dumps(articles,ensure_ascii=False,indent=2))
    report={'window_start':start.isoformat(),'window_end':end.isoformat(),'counts':dict(stats),'per_outlet':dict(collections.Counter(x['outlet'] for x in articles)),'per_country':dict(collections.Counter(x['country'] for x in articles)),'errors':errors}
    (DATA/'state_pull_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (DATA/'state_articles.json').write_text(json.dumps(articles,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__': main()
