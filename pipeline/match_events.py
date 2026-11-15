"""Propose text-similar, time-adjacent pairs for human review only."""
import argparse, json, re, unicodedata
from datetime import timezone
import pandas as pd
from dateutil.parser import parse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from config import DATA, STATE_DOMAINS, REFERENCE_DOMAINS, COUNTRIES
# Spanish function words, with accents retained by the vectorizer.
STOP = 'a al algo algunas algunos ante antes como con contra cual cuando de del desde donde dos el ella ellas ellos en entre era es esa esas ese eso esos esta estaba estamos estan estar estas este esto estos fue ha hacia hasta hay la las le les lo los mas me mi mientras muy ni no nos nosotros o otra otras otro otros para pero por porque que quien se sea ser si sin sobre son su sus también te tiene todo todos tu un una unas uno unos y ya él ésta más qué sí está están'.split()
def norm(s): return ''.join(c for c in unicodedata.normalize('NFD',s.lower()) if unicodedata.category(c)!='Mn')
def countries(text):
    text=norm(text)
    return {c:sum(len(re.findall(r'\b'+re.escape(norm(t))+r'\b',text)) for t in terms) for c,terms in COUNTRIES.items()}
def date(article):
    # Missing publication dates use GDELT first-seen as an explicit proxy.
    try: return parse(article.get('date') or article.get('seendate')).replace(tzinfo=timezone.utc)
    except (ValueError,TypeError): return None

def main():
    p=argparse.ArgumentParser(); p.add_argument('--threshold',type=float,default=.18); a=p.parse_args()
    articles=[json.loads(f.read_text()) for f in sorted((DATA/'articles').glob('*.json'))]
    articles=[x for x in articles if date(x)]
    states=[x for x in articles if x['domain'] in STATE_DOMAINS]; refs=[x for x in articles if x['domain'].removeprefix('www.') in REFERENCE_DOMAINS]
    rows=[]
    if states and refs:
        docs=states+refs
        vectors=TfidfVectorizer(stop_words=STOP,strip_accents='unicode',ngram_range=(1,2),sublinear_tf=True).fit_transform([x['title']+' '+' '.join(x['text'].split()[:300]) for x in docs])
        scores=cosine_similarity(vectors[:len(states)],vectors[len(states):])
        for i,state in enumerate(states):
            mentioned=countries(state['title']+' '+state['text']); country=max(mentioned,key=mentioned.get)
            if not mentioned[country]: continue
            eligible=[j for j,ref in enumerate(refs) if abs((date(state)-date(ref)).total_seconds())<=3*86400 and scores[i,j]>=a.threshold and countries(ref['title']+' '+ref['text'])[country]>0]
            for j in sorted(eligible,key=lambda j:scores[i,j],reverse=True)[:3]:
                rows.append({'state_url':state['url'],'ref_url':refs[j]['url'],'score':float(scores[i,j]),'country':country,'state_title':state['title'],'ref_title':refs[j]['title']})
    pd.DataFrame(rows,columns=['state_url','ref_url','score','country','state_title','ref_title']).to_csv(DATA/'pair_candidates.csv',index=False)
    print(json.dumps({'state_articles':len(states),'reference_articles':len(refs),'pairs':len(rows),'by_country':pd.Series([r['country'] for r in rows],dtype=str).value_counts().to_dict()},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
