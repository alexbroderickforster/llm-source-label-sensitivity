"""Fallback discovery from publisher sitemaps when Google RSS is robots-blocked."""
import collections, json, re
from datetime import timedelta, datetime, timezone
from urllib.parse import urlsplit, unquote
from dateutil.parser import parse
from config import DATA, REFERENCE_DOMAINS
from source_client import Client
from state_pull import elements, NS, EXCLUDE

def discover(client=None,max_maps=35):
    c=client or Client()
    window=json.loads((DATA/'state_pull_summary.json').read_text()) if (DATA/'state_pull_summary.json').exists() else {'window_start':(datetime.now(timezone.utc)-timedelta(days=60)).isoformat(),'window_end':datetime.now(timezone.utc).isoformat()}
    start=parse(window['window_start'])-timedelta(days=3); end=parse(window['window_end'])+timedelta(days=3)
    sources=json.loads((DATA/'reference_sources.json').read_text()); pool={}; errors=[]; counts=collections.Counter()
    for source in sources:
        domain=source['domain']; queue=[]
        maps=source['sitemaps']
        if domain=='elpais.com': maps=['https://elpais.com/sitemaps/sitemap.xml','https://elpais.com/sitemap.xml']
        for u in maps:
            if domain=='swissinfo.ch' and u not in ('https://www.swissinfo.ch/spa/sitemap.xml','https://www.swissinfo.ch/spa/sitemap-news.xml'): continue
            if any(t in u for t in ['video','images','teleshow','espana','deporte','gastronomia','luces','tvmas','wuf','viu','vamos','ruedas','casa','dominical','publirreportaje','somos','lifweek','/mag/']): continue
            queue.append((u,0))
        seen=set()
        while queue and counts[domain+'_sitemaps']<max_maps:
            url,depth=queue.pop(0)
            if url in seen: continue
            seen.add(url)
            try:
                b,_=c.get(url); root,children,entries=elements(b); counts[domain+'_sitemaps']+=1
                for child in children:
                    loc=child.findtext('s:loc',namespaces=NS) or ''
                    if depth>=4: continue
                    if domain=='dw.com' and '/es/' not in loc: continue
                    if any(t in loc.lower() for t in ['video','image','gallery','person-','topic-','navigation','opinion','deporte','teleshow','2025','2024','2023']): continue
                    dt=child.findtext('s:lastmod',namespaces=NS)
                    if dt:
                        try:
                            if parse(dt).date()<start.date(): continue
                        except ValueError: pass
                    # Dated archive maps outside this window are unnecessary.
                    dates=re.findall(r'(20\d{2})[-/](\d{2})[-/](\d{2})',loc)
                    if dates:
                        day='-'.join(dates[-1])
                        if not start.date().isoformat()<=day<=end.date().isoformat(): continue
                    queue.append((loc,depth+1))
                for entry in entries:
                    loc=entry.findtext('s:loc',namespaces=NS) or ''
                    if not allowed(loc): continue
                    if domain=='elpais.com' and '/america/' not in loc: continue
                    if domain=='dw.com' and '/es/' not in loc: continue
                    if domain=='swissinfo.ch' and '/spa/' not in loc: continue
                    title=entry.findtext('.//n:title',namespaces=NS) or ''
                    if EXCLUDE.search(loc+' '+title): continue
                    dt=entry.findtext('.//n:publication_date',namespaces=NS) or entry.findtext('s:lastmod',namespaces=NS)
                    # Prefer publication day embedded in URL over modification time.
                    dateurl=re.search(r'/(20\d{2})/(\d{2})/(\d{2})/',loc)
                    if dateurl: dt='-'.join(dateurl.groups())
                    if not dt: continue
                    try: day=parse(dt).date()
                    except ValueError: continue
                    if not start.date()<=day<=end.date(): continue
                    pool[loc]={'url':loc,'title':title or slug_title(loc),'date':day.isoformat(),'domain':domain}
                print(f'refs {domain} maps={counts[domain+"_sitemaps"]} pool={len(pool)}',flush=True)
            except Exception as e:
                errors.append({'url':url,'error':str(e)}); print(str(e),flush=True)
                if urlsplit(url).hostname in c.blocked: break
        counts[domain+'_discovered']=sum(x['domain']==domain for x in pool.values())
        (DATA/'reference_pool.json').write_text(json.dumps(list(pool.values()),ensure_ascii=False,indent=2))
    (DATA/'reference_discovery_summary.json').write_text(json.dumps({'counts':dict(counts),'errors':errors,'method':'publisher_sitemaps_fallback'},ensure_ascii=False,indent=2))
    return list(pool.values())
def slug_title(url):
    parts=unquote(urlsplit(url).path).strip('/').split('/')
    if parts and re.fullmatch(r'a-\d+',parts[-1]): parts=parts[:-1]
    return parts[-1].replace('-',' ') if parts else ''

def allowed(url):
    host=(urlsplit(url).hostname or '').removeprefix('www.')
    return host in REFERENCE_DOMAINS
if __name__=='__main__': discover()
