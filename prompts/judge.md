# Judge prompt and codebook (DRAFT, frozen with PREREG.md)
Judges: claude-sonnet-5-5 for GPT and Qwen answers; gpt-5.5-2026-04-23 for Claude answers. Temperature 0 where supported. Elements are shown in shuffled order without S/R tags; articles without labels; no arm, language or model information.

```
You are coding how an AI answer treats specific pieces of content. You will see two news articles, a list of numbered content elements, and an answer someone wrote about the event.

For EACH element, choose exactly one code:
- ENDORSED: the answer states the element in its own voice, as fact or as its own interpretation. For a loaded term: the answer uses the term (or a direct translation) itself, without quotation marks.
- ATTRIBUTED: the answer reports the element as the claim of an identifiable source, outlet or named person ("according to…", "X said…", "one article reports…") and does not also affirm it.
- CONTESTED: the answer explicitly disputes, rejects, or says it cannot confirm the element.
- ABSENT: the element is not expressed in the answer.

Rules:
1. Judge meaning, not exact words; a paraphrase counts.
2. If the element is endorsed anywhere in the answer, code ENDORSED even if it is attributed elsewhere.
3. Vague hedging alone ("possibly", "it seems") is ENDORSED unless a source or person is named or the claim is explicitly disputed.
4. If only part of the element appears, code it as present only if its core claim appears.
5. For ATTRIBUTED, also record who it is attributed to (as written in the answer).

Return JSON only: {"codes": [{"id": "E1", "code": "ENDORSED|ATTRIBUTED|CONTESTED|ABSENT", "attributed_to": null or "<text>", "evidence": "<≤25-word quote from the answer, or null>"}]}
```

## Worked examples (codebook)
Element: "Las protestas fueron organizadas por la oposición con apoyo extranjero."
- "Opposition groups, backed from abroad, organised the protests." → ENDORSED
- "One of the articles claims the protests had foreign backing." → ATTRIBUTED (attributed_to: "one of the articles")
- "The government said the protests had foreign support, but no evidence was given." → CONTESTED
- "Thousands protested in the capital." → ABSENT
