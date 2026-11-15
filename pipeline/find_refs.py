"""Find up to three references per state article; retain the best above threshold."""
import argparse, collections, csv, json, re
from datetime import timedelta
from urllib.parse import urlencode, urlsplit
from xml.etree import ElementTree as ET
from dateutil.parser import parse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from config import DATA
from source_client import Client
from discover_refs import allowed, discover, slug_title
from match_events import STOP, norm
from strip_cues import strip_cues, leak_scan
FIELDS=['pair_id','country','state_outlet','state_url','state_title','state_date','ref_outlet','ref_url','ref_title','ref_date','score','state_words','ref_words','teleSUR_url']
EXTRA=set('rt sputnik mundo actualidad noticias video videos directo ultima hora latinoamerica latinoamérica'.split())
def doc(a): return a['title']+' '+' '.join(a['text'].split()[:300])
def keywords(title,idf):
    title=re.sub(r'ee\.\s*uu\.', 'eeuu',norm(title))
    title=re.sub(r'\bonu\b','naciones unidas',title)
    words=list(dict.fromkeys(w for w in re.findall(r'[^\W\d_]{3,}',title) if w not in set(map(norm,STOP))|EXTRA))
    selected=set(sorted(words,key=lambda w:idf.get(w,1),reverse=True)[:6])
    return [w for w in words if w in selected]
def save(rows):
    with (DATA/'pair_candidates.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
def main():
    p=argparse.ArgumentParser(); p.add_argument('--threshold',type=float,default=.18); p.add_argument('--refresh-discovery',action='store_true'); a=p.parse_args()
    states=json.loads((DATA/'state_articles.json').read_text()); c=Client(); stats=collections.Counter(); errors=[]; queries=[]; matches=[]
    vectorizer=TfidfVectorizer(strip_accents='unicode',stop_words=STOP)
    vectorizer.fit([s['title'] for s in states]); idf=dict(zip(vectorizer.get_feature_names_out(),vectorizer.idf_))
    google='https://news.google.com/rss/search'
    google_allowed=c.allowed(google+'?q=test'); stats['google_robots_allowed']=int(google_allowed)
    fallback=[]
    if not google_allowed:
        fallback=discover(c) if a.refresh_discovery or not (DATA/'reference_pool.json').exists() else json.loads((DATA/'reference_pool.json').read_text())
    for ref in fallback:
        if not ref.get('title') or re.fullmatch(r'a[ -]\d+',ref['title']): ref['title']=slug_title(ref['url'])
    fallback_dates=[parse(r['date']).date() for r in fallback]
    title_vectors=None
    if fallback:
        tv=TfidfVectorizer(stop_words=STOP,strip_accents='unicode',ngram_range=(1,2))
        title_vectors=tv.fit_transform([s['title'] for s in states]+[r['title'] for r in fallback])
        rankings=cosine_similarity(title_vectors[:len(states)],title_vectors[len(states):])
    for i,state in enumerate(states):
        day=parse(state['date']).date(); lo=day-timedelta(days=3); hi=day+timedelta(days=3)
        words=keywords(state['title'],idf); query=' '.join(words)+f' after:{lo.isoformat()} before:{(hi+timedelta(days=1)).isoformat()}'
        query_url=google+'?'+urlencode({'q':query,'hl':'es-419','gl':'US','ceid':'US:es-419'})
        queries.append({'state_url':state['url'],'keywords':words,'query':query,'url':query_url,'status':'attempted' if google_allowed else 'robots_disallowed'})
        candidates=[]
        if google_allowed:
            try:
                body,_=c.get(query_url); stats['rss_responses']+=1
                for item in ET.fromstring(body).findall('.//item'):
                    link=item.findtext('link') or ''; source=item.find('source')
                    try:
                        _,resolved=c.get(link)
                        if allowed(resolved): candidates.append({'url':resolved,'date':item.findtext('pubDate'),'title':item.findtext('title') or ''})
                        elif source is not None:
                            # Source URLs usually identify the homepage, not the article.
                            source_url=source.get('url','')
                            if allowed(source_url) and len(urlsplit(source_url).path.strip('/'))>10: candidates.append({'url':source_url,'date':item.findtext('pubDate'),'title':item.findtext('title') or ''})
                    except Exception as e: errors.append({'url':link,'error':str(e)})
                    if len(candidates)>=3: break
            except Exception as e: errors.append({'url':query_url,'error':str(e)})
        elif fallback:
            eligible=[j for j,ref_day in enumerate(fallback_dates) if lo<=ref_day<=hi and rankings[i,j]>.035]
            ranked=[fallback[j] for j in sorted(eligible,key=lambda j:rankings[i,j],reverse=True)]
            first=[]; rest=[]; domains=set()
            for candidate in ranked:
                domain=candidate['domain']
                if domain in domains: rest.append(candidate)
                else: first.append(candidate); domains.add(domain)
            candidates=first+rest
        refs=[]; attempts=0
        for ref in candidates:
            if attempts>=3: break
            if urlsplit(ref['url']).hostname in c.blocked: continue
            attempts+=1
            stats['reference_fetch_attempts']+=1
            try:
                article=c.article(ref['url'])
                if not allowed(article['url']): raise ValueError('redirect to non-reference domain')
                article['date']=article.get('date') or ref['date']
                if not article['date'] or not lo<=parse(article['date']).date()<=hi: raise ValueError('reference date outside window')
                refs.append(article); stats['references_extracted']+=1
            except Exception as e: errors.append({'url':ref['url'],'error':str(e)}); stats['reference_rejected']+=1
        matches.append((state,refs)); stats['states_searched']+=1
        (DATA/'reference_matches.json').write_text(json.dumps(matches,ensure_ascii=False,indent=2))
        (DATA/'reference_queries.json').write_text(json.dumps(queries,ensure_ascii=False,indent=2))
        print(f'references {i+1}/{len(states)} extracted={stats["references_extracted"]}',flush=True)
    # One common IDF corpus makes similarities comparable across proposals.
    unique={r['url']:r for _,rs in matches for r in rs}; corpus=states+list(unique.values()); rows=[]; leaks=collections.Counter()
    if unique:
        vec=TfidfVectorizer(stop_words=STOP,strip_accents='unicode',ngram_range=(1,2),sublinear_tf=True).fit([doc(x) for x in corpus])
        out=DATA/'articles/stripped'; out.mkdir(parents=True,exist_ok=True)
        for state,refs in matches:
            if not refs: continue
            scores=cosine_similarity(vec.transform([doc(state)]),vec.transform([doc(r) for r in refs]))[0]
            best=max(range(len(refs)),key=lambda j:scores[j]); ref=refs[best]; score=float(scores[best])
            if score<a.threshold: continue
            pair_id=f'pair_{len(rows)+1:04d}'
            rows.append(dict(zip(FIELDS,[pair_id,state['country'],state['outlet'],state['url'],state['title'],state['date'],ref['domain'],ref['url'],ref['title'],ref['date'],round(score,6),state['words'],ref['words'],''])))
            for role,article in [('state',state),('ref',ref)]:
                # Include titles in stripped stimuli and scanning.
                original=article['title']+'\n\n'+article['text']; clean,ledger=strip_cues(original)
                before=leak_scan(original); after=leak_scan(clean)
                leaks['texts']+=1; leaks['before']+=len(before['remaining_cues']); leaks['after']+=len(after['remaining_cues']); leaks['removals']+=len(ledger); leaks['medio_tokens']+=after['medio_tokens']
                (out/f'{pair_id}_{role}.txt').write_text(clean)
                (out/f'{pair_id}_{role}.report.json').write_text(json.dumps({'source_url':article['url'],'removals':ledger,'leaks_before':before['remaining_cues'],**after},ensure_ascii=False,indent=2))
    save(rows)
    summary={'threshold':a.threshold,'discovery_method':'google_news_rss' if google_allowed else 'publisher_sitemaps_fallback','google_news_blocker':None if google_allowed else 'robots.txt Disallow: /; /rss/search has no Allow exception','counts':dict(stats),'unique_reference_articles':len(unique),'pair_candidates':len(rows),'pairs_per_country':dict(collections.Counter(r['country'] for r in rows)),'pairs_per_state_outlet':dict(collections.Counter(r['state_outlet'] for r in rows)),'pairs_per_reference_outlet':dict(collections.Counter(r['ref_outlet'] for r in rows)),'leak_counts':dict(leaks),'errors':errors,'human_confirmation_required':True,'target_achieved':len(rows)>=60 and len({r['country'] for r in rows})>=3}
    summary['references_per_outlet']={d:sum(r['domain'].removeprefix('www.')==d for r in unique.values()) for d in __import__('config').REFERENCE_DOMAINS}
    summary['references_per_country']=dict(collections.Counter(country for country,url in {(s['country'],r['url']) for s,rs in matches for r in rs}))
    summary['state_collection']=json.loads((DATA/'state_pull_summary.json').read_text())
    summary['reference_discovery']=json.loads((DATA/'reference_discovery_summary.json').read_text()) if (DATA/'reference_discovery_summary.json').exists() else {}
    (DATA/'run_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)); print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__': main()
