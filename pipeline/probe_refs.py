"""Read reference robots and advertised sitemaps, without bypassing exclusions."""
from source_client import Client
from config import REFERENCE_DOMAINS, DATA
import json
c=Client(); results=[]
for host in REFERENCE_DOMAINS:
    url='https://'+host+'/robots.txt'
    m,b=c.raw(url)
    for _ in range(6):
        if m['status'] not in (301,302,303,307,308) or not m.get('location'): break
        from urllib.parse import urljoin
        url=urljoin(url,m['location']); m,b=c.raw(url)
    maps=[line.split(':',1)[1].strip() for line in b.splitlines() if line.lower().startswith('sitemap:')]
    result={'domain':host,'robots_status':m['status'],'sitemaps':maps}
    print(json.dumps(result),flush=True)
    for sm in maps[:2]:
        try:
            content,final=c.get(sm); print(final,content[:2200],flush=True)
        except Exception as e: print(str(e),flush=True)
    results.append(result)
(DATA/'reference_sources.json').write_text(json.dumps(results,indent=2))
