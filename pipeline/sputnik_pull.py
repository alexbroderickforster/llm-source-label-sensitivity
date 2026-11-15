"""Collect Sputnik from public sitemaps and in-window article links.

Uses the shared robots-aware, cached, two-second HTTP client. No archive,
search, private endpoints, or alternate domains. Stops on access denial.
"""
import argparse
import collections
import json
import re
from datetime import date
from urllib.parse import urljoin, urlsplit, urldefrag
from lxml import html
from dateutil.parser import parse
from config import DATA
from source_client import Client
from state_pull import elements, NS, EXCLUDE
from match_events import countries

ORIGIN = 'https://noticiaslatam.lat'
ARTICLE = re.compile(r'^/(\d{8})/[^/]+\.html$')


def article_day(url):
    parts = urlsplit(url)
    match = ARTICLE.match(parts.path)
    if parts.scheme != 'https' or parts.netloc != 'noticiaslatam.lat' or not match:
        return None
    try:
        return date.fromisoformat(f'{match[1][:4]}-{match[1][4:6]}-{match[1][6:]}')
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', default='2026-09-15', type=date.fromisoformat)
    parser.add_argument('--end', default='2026-11-05', type=date.fromisoformat)
    parser.add_argument('--limit', default=60, type=int)
    parser.add_argument('--max-fetch', default=180, type=int)
    args = parser.parse_args()
    c = Client()
    stats = collections.Counter()
    errors, articles, discovered = [], [], {}
    queue, seen = [], set()
    blocked = None

    def enqueue(url, sitemap_date=None):
        url = urlsplit(urldefrag(url)[0])._replace(query='', fragment='').geturl()
        day = article_day(url)
        if day and args.start <= day <= args.end and not EXCLUDE.search(url):
            if url not in discovered:
                discovered[url] = {'url': url, 'sitemap_date': sitemap_date}
                queue.append(url)

    try:
        body, _ = c.get(ORIGIN + '/sitemap_article_index.xml')
        _, maps, _ = elements(body)
        for item in maps:
            url = item.findtext('s:loc', namespaces=NS) or ''
            match = re.search(r'date_start=(\d{6})', url)
            if not match or not args.start.strftime('%Y%m') <= match[1] <= args.end.strftime('%Y%m'):
                continue
            body, _ = c.get(url)
            _, _, entries = elements(body)
            stats['monthly_sitemaps'] += 1
            for entry in entries:
                stats['sitemap_urls'] += 1
                enqueue(entry.findtext('s:loc', namespaces=NS) or '',
                        entry.findtext('s:lastmod', namespaces=NS))
        stats['in_window_sitemap_seeds'] = len(queue)
        while queue and len(articles) < args.limit and len(seen) < args.max_fetch:
            # Prefer explicit country cues while allowing general LatAm seeds.
            queue.sort(key=lambda u: -max(countries(u.replace('-', ' ')).values()))
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                body, final = c.get(url)
                stats['article_pages'] += 1
                for href in html.fromstring(body).xpath('//a/@href'):
                    enqueue(urljoin(final, href))
                # Shared extraction uses trafilatura and enforces 150 words.
                article = c.article(url, min_words=150)
                if not article.get('date'):
                    raise ValueError('missing extracted publication date')
                if not args.start <= parse(article['date']).date() <= args.end:
                    raise ValueError('publication date outside window')
                if EXCLUDE.search(article['title']) or re.search(r'\b(?:videos?|fotogaler[ií]a)\b', article['title'], re.I):
                    raise ValueError('excluded genre')
                # Country lists late in unrelated stories are incidental cues.
                mentions = countries(article['title'] + ' ' + ' '.join(article['text'].split()[:200]))
                country = max(mentions, key=mentions.get)
                if not mentions[country]:
                    raise ValueError('no Latin American country cue in title or first 200 words')
                article.update(country=country, outlet='Sputnik',
                               sitemap_date=discovered[url]['sitemap_date'])
                articles.append(article)
            except ValueError as exc:
                if any(s in str(exc) for s in ('robots disallow', 'HTTP 403', 'HTTP 429', 'circuit breaker')):
                    raise
                errors.append({'url': url, 'error': str(exc)})
                stats['rejected'] += 1
            print(f'Sputnik fetched={len(seen)} discovered={len(discovered)} retained={len(articles)}', flush=True)
            (DATA / 'sputnik_articles.json').write_text(json.dumps(articles, ensure_ascii=False, indent=2))
    except Exception as exc:
        blocked = str(exc)
    stats['discovered'] = len(discovered)
    stats['retained'] = len(articles)
    report = {'window_start': str(args.start), 'window_end': str(args.end),
              'counts': dict(stats), 'per_country': dict(collections.Counter(a['country'] for a in articles)),
              'blocked': blocked, 'errors': errors,
              'target_achieved': len(articles) >= args.limit,
              'stop_reason': ('access_or_collection_error' if blocked else
                              'target_reached' if len(articles) >= args.limit else
                              'fetch_limit' if len(seen) >= args.max_fetch else 'article_links_exhausted'),
              'discovery': 'Monthly sitemaps, then same-domain in-window article links; linked articles have null sitemap_date.'}
    (DATA / 'sputnik_articles.json').write_text(json.dumps(articles, ensure_ascii=False, indent=2))
    (DATA / 'sputnik_discovered.json').write_text(json.dumps(list(discovered.values()), ensure_ascii=False, indent=2))
    (DATA / 'sputnik_pull_summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
