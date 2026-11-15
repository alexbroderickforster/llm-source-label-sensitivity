from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
UA = 'LabelContentResearchClient/1.0 (academic article comparison; Python requests)'
COUNTRIES = {
 'Argentina': ['argentina','argentino','argentina','buenos aires'],
 'Bolivia': ['bolivia','boliviano','la paz','sucre'],
 'Brasil': ['brasil','brasileño','brasilia'],
 'Chile': ['chile','chileno','santiago'],
 'Colombia': ['colombia','colombiano','bogotá'],
 'Costa Rica': ['costa rica','costarricense','san josé'],
 'Cuba': ['cuba','cubano','la habana'],
 'Ecuador': ['ecuador','ecuatoriano','quito'],
 'El Salvador': ['el salvador','salvadoreño','san salvador'],
 'Guatemala': ['guatemala','guatemalteco'],
 'Haití': ['haití','haitiano','puerto príncipe'],
 'Honduras': ['honduras','hondureño','tegucigalpa'],
 'México': ['méxico','mexicano','ciudad de méxico'],
 'Nicaragua': ['nicaragua','nicaragüense','managua'],
 'Panamá': ['panamá','panameño'],
 'Paraguay': ['paraguay','paraguayo','asunción'],
 'Perú': ['perú','peruano','lima'],
 'República Dominicana': ['república dominicana','dominicano','santo domingo'],
 'Uruguay': ['uruguay','uruguayo','montevideo'],
 'Venezuela': ['venezuela','venezolano','caracas'],
}

# Current source roles. State media must never enter the reference set.
STATE_DOMAINS = ['actualidad-rt.com', 'noticiaslatam.lat']
REFERENCE_DOMAINS = ['elpais.com', 'dw.com', 'infobae.com', 'lanacion.com.ar', 'eltiempo.com', 'elcomercio.pe', 'eluniversal.com.mx', 'biobiochile.cl', 'swissinfo.ch']
COMPARISON_DOMAINS = ['telesurtv.net']
LEADERS = {
 'Argentina':['milei'], 'Bolivia':['rodrigo paz','luis arce','evo morales'],
 'Brasil':['lula','bolsonaro'], 'Chile':['boric','kast'], 'Colombia':['petro'],
 'Costa Rica':['rodrigo chaves','laura fernandez'], 'Cuba':['diaz canel'],
 'Ecuador':['noboa'], 'El Salvador':['bukele'], 'Guatemala':['bernardo arevalo'],
 'Haití':['alix didier'], 'Honduras':['xiomara castro','nasry asfura'],
 'México':['sheinbaum','lopez obrador'], 'Nicaragua':['ortega','rosario murillo'],
 'Panamá':['mulino'], 'Paraguay':['santiago pena'], 'Perú':['boluarte','jeri'],
 'República Dominicana':['abinader'], 'Uruguay':['orsi','lacalle pou'], 'Venezuela':['maduro','delcy rodriguez','maria corina machado']}
for country, terms in LEADERS.items(): COUNTRIES[country].extend(terms)
