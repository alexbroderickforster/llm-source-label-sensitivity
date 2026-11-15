"""Report observed counts separately from unqueried domains."""
import json
from collections import Counter, defaultdict
from config import DATA, STATE_DOMAINS, REFERENCE_DOMAINS
import pandas as pd

def main():
    articles=[json.loads(p.read_text()) for p in (DATA/'articles').glob('*.json')]
    success=Counter(a['domain'] for a in articles)
    queries=defaultdict(list)
    for path in (DATA/'cache/gdelt').glob('*.json'):
        item=json.loads(path.read_text())
        if 'params' in item: queries[item['params']['query'].split()[0].split(':',1)[1]].append(item)
    pairs=pd.read_csv(DATA/'pair_candidates.csv')
    result={'state_articles':sum(success[d] for d in STATE_DOMAINS),'reference_articles':sum(success[d] for d in REFERENCE_DOMAINS),'successful_fetches_per_domain':{d:success[d] for d in STATE_DOMAINS+REFERENCE_DOMAINS},'pair_candidates':len(pairs),'pairs_per_country':pairs.country.value_counts().to_dict(),'domain_discovery':{d: {'queries':len(queries[d]),'statuses':[q.get('status',q.get('error')) for q in queries[d]],'articles_returned':sum(len(q.get('payload',{}).get('articles',[])) for q in queries[d])} for d in STATE_DOMAINS+REFERENCE_DOMAINS}}
    (DATA/'run_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)); print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
