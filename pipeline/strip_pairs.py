"""Regenerate paired stimuli and leak reports from cached originals; no network."""
import collections, csv, json
from config import DATA
from strip_cues import strip_cues, leak_scan

def main():
    matches=json.loads((DATA/'reference_matches.json').read_text())
    articles={a['url']:a for state,refs in matches for a in [state]+refs}
    rows=list(csv.DictReader((DATA/'pair_candidates.csv').open()))
    out=DATA/'articles/stripped'; out.mkdir(parents=True,exist_ok=True)
    counts=collections.Counter(texts=0,before=0,after=0,removals=0,medio_tokens=0)
    for row in rows:
        for role in ['state','ref']:
            article=articles[row[role+'_url']]
            original=article['title']+'\n\n'+article['text']
            clean,ledger=strip_cues(original); before=leak_scan(original); after=leak_scan(clean)
            counts.update(texts=1,before=len(before['remaining_cues']),after=len(after['remaining_cues']),removals=len(ledger),medio_tokens=after['medio_tokens'])
            name=f"{row['pair_id']}_{role}"
            (out/(name+'.txt')).write_text(clean)
            (out/(name+'.report.json')).write_text(json.dumps({'source_url':article['url'],'removals':ledger,'leaks_before':before['remaining_cues'],**after},ensure_ascii=False,indent=2))
    summary=json.loads((DATA/'run_summary.json').read_text()); summary['leak_counts']=dict(counts)
    (DATA/'run_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(dict(counts)))
if __name__=='__main__': main()
