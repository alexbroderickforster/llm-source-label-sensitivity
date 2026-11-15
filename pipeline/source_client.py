"""Cached, robots-aware HTTP. Run one collector at a time."""
import hashlib, json, time, re, fcntl
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser
import requests
import trafilatura
from config import DATA, UA

class Robots:
    def __init__(self,body):
        self.groups=[]; agents=[]; rules=[]
        for line in body.splitlines()+['User-agent: end-marker']:
            line=line.split('#',1)[0].strip()
            if ':' not in line: continue
            k,v=[x.strip() for x in line.split(':',1)]; k=k.lower()
            if k=='user-agent':
                if rules: self.groups.append((agents,rules)); agents=[]; rules=[]
                agents.append(v.lower())
            elif k in ('allow','disallow') and v: rules.append((k,v))
    def can_fetch(self,ua,url):
        specific=[g for g in self.groups if any(a!='*' and a in ua.lower() for a in g[0])]
        groups=specific or [g for g in self.groups if '*' in g[0]]
        path=urlsplit(url).path or '/'
        if urlsplit(url).query: path+='?'+urlsplit(url).query
        matches=[]
        for _,rules in groups:
            for kind,value in rules:
                pattern='^'+re.escape(value.rstrip('$')).replace(r'\*','.*')+('$' if value.endswith('$') else '')
                if re.search(pattern,path): matches.append((len(value.replace('*','').rstrip('$')),kind=='allow'))
        return max(matches)[1] if matches else True

class Client:
    def __init__(self):
        self.root=DATA/'cache/sources'; self.root.mkdir(parents=True,exist_ok=True)
        self.session=requests.Session(); self.session.headers['User-Agent']=UA
        self.robots={}; self.blocked=set(); self.errors=[]
        self.clock=self.root/'last_requests.json'
        self.last=json.loads(self.clock.read_text()) if self.clock.exists() else {}
    def key(self,url): return hashlib.sha256(url.encode()).hexdigest()
    def raw(self,url):
        key=self.key(url); meta=self.root/(key+'.json'); body=self.root/(key+'.body')
        if meta.exists():
            m=json.loads(meta.read_text()); return m,body.read_text() if body.exists() else ''
        host=urlsplit(url).hostname.removeprefix('www.'); delay=5 if host=='news.google.com' else 2
        with (self.root/'request.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if self.clock.exists(): self.last.update(json.loads(self.clock.read_text()))
            time.sleep(max(0,delay-(time.time()-self.last.get(host,0))))
            self.last[host]=time.time(); self.clock.write_text(json.dumps(self.last))
            fcntl.flock(lock,fcntl.LOCK_UN)
        try:
            r=self.session.get(url,timeout=45,allow_redirects=False)
            m={'url':url,'status':r.status_code,'location':r.headers.get('Location'),'fetched_at':time.time()}; content=r.text
            try: content=r.content.decode('utf-8')
            except UnicodeDecodeError: pass
        except requests.RequestException as e: m={'url':url,'status':0,'error':str(e)}; content=''
        body.write_text(content); meta.write_text(json.dumps(m)); return m,content
    def allowed(self,url):
        origin='{0.scheme}://{0.netloc}'.format(urlsplit(url))
        if origin not in self.robots:
            robots_url=origin+'/robots.txt'
            for _ in range(6):
                m,b=self.raw(robots_url)
                if m['status'] in (301,302,303,307,308) and m.get('location'):
                    robots_url=urljoin(robots_url,m['location'])
                else: break
            rp=RobotFileParser(); rp.set_url(origin+'/robots.txt')
            if m['status']==200: rp=Robots(b)
            elif m['status'] in (404,410): rp.parse([])
            else: rp.disallow_all=True
            self.robots[origin]=rp
        return self.robots[origin].can_fetch(UA,url)
    def get(self,url):
        for _ in range(8):
            host=urlsplit(url).hostname
            if host in self.blocked: raise ValueError('domain circuit breaker: '+host)
            if not self.allowed(url): raise ValueError('robots disallow: '+url)
            m,b=self.raw(url)
            if m['status'] in (301,302,303,307,308) and m.get('location'):
                url=urljoin(url,m['location']); continue
            if m['status'] in (403,429): self.blocked.add(host)
            if m['status']!=200: raise ValueError('HTTP '+str(m['status'])+': '+url)
            return b,url
        raise ValueError('redirect limit')
    def article(self,url,min_words=150):
        dest=DATA/'articles'/(self.key(url)+'.json'); dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            cached=json.loads(dest.read_text())
            if cached['words']<min_words: raise ValueError(f'under {min_words} words')
            return cached
        html,final=self.get(url)
        a=trafilatura.bare_extraction(html,url=final,with_metadata=True,include_comments=False,favor_precision=True)
        if re.search(r'LiveBlogPosting',html,re.I): raise ValueError('live blog')
        if not a: raise ValueError('empty extraction')
        if not isinstance(a,dict): a=a.as_dict()
        text=a.get('text') or ''
        if len(text.split())<min_words: raise ValueError(f'under {min_words} words')
        if any(t in text.lower() for t in ('suscríbete para seguir leyendo','suscríbete para continuar leyendo','contenido exclusivo para suscriptores')): raise ValueError('paywall')
        result={'url':final,'title':a.get('title') or '', 'date':a.get('date'),'text':text,'words':len(text.split()),'domain':urlsplit(final).hostname}
        dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)); return result
