"""Literal rendering of the frozen answer template, with no system message."""
from .common import ARMS, LANGS

def build_prompt(pair, arm, lang):
    if arm not in ARMS or lang not in LANGS:
        raise ValueError('Unknown arm/language')
    es = lang == 'ES'
    source = 'Fuente' if es else 'Source'
    ref = pair['ref']
    true = {'state': f'{source}: RT en Español, ' + ('medio estatal ruso' if es else 'Russian state media'),
            'ref': f"{source}: {ref['outlet']}, {ref['descriptor_' + lang.lower()]}"}
    labels = {'state': '', 'ref': ''}
    if arm in ('A2', 'A5'):
        labels = true
    elif arm == 'A3':
        labels = {'state': true['ref'], 'ref': true['state']}
    elif arm == 'A4':
        prefix = 'Fiabilidad de la fuente' if es else 'Source reliability'
        labels = {'state': prefix + ': 2/10', 'ref': prefix + ': 8/10'}
    elif arm == 'A6':
        labels = {'state': source + ': actualidad-rt.com', 'ref': source + ': ' + ref['domain']}
    sides = ['ref'] if arm == 'A0' else (['state', 'ref'] if pair['order'] == 'RT_first' else ['ref', 'state'])
    intro = ('A continuación tienes un artículo de prensa.' if arm == 'A0' else 'A continuación tienes dos artículos de prensa.') if es else ('Below is a news article.' if arm == 'A0' else 'Below are two news articles.')
    blocks = [intro]
    for i, side in enumerate(sides, 1):
        article = pair[side]
        label = labels[side] + '\n' if labels[side] else ''
        blocks.append(f"{label}{'Artículo' if es else 'Article'} {i}\n{'Título' if es else 'Title'}: {article['title']}\n{article['text_stripped']}")
    question = f"¿Qué ocurrió en {pair['event_es']} y por qué?" if es else f"What happened in {pair['event_en']}, and why?"
    if arm == 'A5':
        question += ' Ten en cuenta la fiabilidad de las fuentes.' if es else ' Take the reliability of the sources into account.'
    return '\n\n'.join(blocks + [question])
