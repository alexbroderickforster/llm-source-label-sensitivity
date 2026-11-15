"""Conservative regex de-identification with an auditable removal ledger.

Review the output: removal may affect substantive attribution or quotations.
"""
import argparse, json, re
from pathlib import Path
# Scoped case flags keep ordinary phrases and acronyms unambiguous.
PHRASE_OUTLETS = r'El\s+Tiempo|El\s+Comercio|El\s+Universal|El\s+País|La\s+Nación|La\s+Tercera|La\s+República|El\s+Deber|Última\s+Hora|El\s+Universo|La\s+Prensa|Semana|Milenio|Primicias'
OUTLETS = (r'(?-i:RT\s+en\s+Español|' + PHRASE_OUTLETS + r'|EFE|AFP|DW|RT)'
           r'|(?i:Russia Today|Deutsche\s+Welle|Sputnik(?:\s+Mundo)?|actualidad[.-]rt\.com|noticiaslatam\.lat|sputniknews\.lat|France\s*24|teleSUR|Swissinfo(?:\.ch)?|Infobae|Clarín|Clarin|BioBioChile|Bio\s*Bío\s*Chile)')
CUE = re.compile(r'(?<!\w)(?:'+OUTLETS+r')(?!\w)')
PATTERNS = [
 ('url',r'https?://[^\s)]+|www\.[^\s)]+'),
 ('copyright',r'(?im)^.*©[^\n]*$'),
 ('social_boilerplate',r'(?im)^.*(?:síguenos|siguenos|suscríbete|suscribete|únete a nuestro|unete a nuestro)[^\n]*(?:Telegram|WhatsApp|redes sociales|canal|YouTube)[^\n]*$'),
 ('byline',r'(?im)^\s*(?:por|autor(?:a)?|redacción|redaccion)\s*[:\s][^\n]+$'),
 ('dateline',r'(?im)^\s*[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ .,/\d-]{1,70}\s*\((?:'+OUTLETS+r')\)\s*[–—:.-]*\s*'),
 ('self_reference',r'(?i)\b(?:'+OUTLETS+r')\s+(?:pudo saber|ha podido saber|informa|informó|reporta|reportó|publicó|señala)\b'),
 ('agency_self_reference',r'(?i)\b(?:según informa esta agencia|informa esta agencia|esta agencia pudo saber)\b'),
 ('parenthetical_source',r'\(\s*(?:'+OUTLETS+r')\s*\)'),
 ('outlet',CUE.pattern),
]
def leak_scan(text):
    return {'remaining_cues': [{'term':m.group(),'start':m.start(),'end':m.end()} for m in CUE.finditer(text)],
            'medio_tokens': text.count('[medio]')}
def strip_cues(text):
    report=[]
    for kind,pattern in PATTERNS:
        def remove(m):
            replacement = '[medio]' if kind in ('outlet','self_reference','parenthetical_source') else ''
            report.append({'kind':kind,'removed':m.group(),'replacement':replacement,'start':m.start(),'end':m.end(),'coordinates':'input to this sequential rule'})
            return replacement
        text=re.sub(pattern,remove,text)
    text=re.sub(r'[ \t]{2,}',' ',text)
    text=re.sub(r'\n{3,}','\n\n',text).strip()
    return text,report

def main():
    p=argparse.ArgumentParser(); p.add_argument('input',type=Path); p.add_argument('--output',required=True,type=Path); a=p.parse_args()
    text,report=strip_cues(a.input.read_text()); a.output.write_text(text)
    a.output.with_suffix(a.output.suffix+'.report.json').write_text(json.dumps({'removals':report,**leak_scan(text)},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
