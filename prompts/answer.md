# Answer prompt templates (DRAFT, frozen with PREREG.md)

One user message per call. No system prompt, no tools. `{…}` are filled per pair. Article order (`first`/`second`) is fixed per pair by seed 20261113.

## Spanish (ES)
```
A continuación tienes {n_articles_es}.

{label_1_line}Artículo 1
Título: {title_1}
{text_1}

{label_2_line}Artículo 2
Título: {title_2}
{text_2}

¿Qué ocurrió en {event_es} y por qué?{instruction_es}
```
- A0 has one article only: "A continuación tienes un artículo de prensa." and just "Artículo 1".
- A1–A5: "A continuación tienes dos artículos de prensa."

## English (EN)
```
Below {n_articles_en}.

{label_1_line}Article 1
Title: {title_1}
{text_1}

{label_2_line}Article 2
Title: {title_2}
{text_2}

What happened in {event_en}, and why?{instruction_en}
```
- A0: "Below is a news article." A1–A5: "Below are two news articles." Article titles and texts stay in Spanish.

## Label lines (`{label_k_line}`, followed by a newline; empty in A0 and A1; `{ref_domain}` is the bare registered domain, e.g. `infobae.com`)
| Arm | RT article | Reference article |
|---|---|---|
| A2, A5 (ES) | `Fuente: RT en Español, medio estatal ruso` | `Fuente: {ref_outlet}, {ref_descriptor_es}` |
| A2, A5 (EN) | `Source: RT en Español, Russian state media` | `Source: {ref_outlet}, {ref_descriptor_en}` |
| A3 | the reference's label | the RT label |
| A4 (ES) | `Fiabilidad de la fuente: 2/10` | `Fiabilidad de la fuente: 8/10` |
| A4 (EN) | `Source reliability: 2/10` | `Source reliability: 8/10` |
| A6 (ES) | `Fuente: actualidad-rt.com` | `Fuente: {ref_domain}` |
| A6 (EN) | `Source: actualidad-rt.com` | `Source: {ref_domain}` |

`ref_descriptor` examples: "diario argentino" / "Argentine newspaper"; "agencia de noticias EFE" wording for wire copy: `Fuente: EFE, agencia de noticias española` / `Source: EFE, Spanish news agency`. The full per-pair list is in the stimulus file.

## Instruction (`{instruction_*}`; A5 only, empty otherwise)
- ES: ` Ten en cuenta la fiabilidad de las fuentes.`
- EN: ` Take the reliability of the sources into account.`
