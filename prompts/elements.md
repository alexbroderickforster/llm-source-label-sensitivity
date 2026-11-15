# Frame-element drafting prompt (DRAFT, frozen with PREREG.md)
Model: Claude Opus 5.5 (run via Claude Code). Input: the two cue-stripped articles, called A and B in random order (the drafter is not told which is state media). Output is checked and edited by a human before freezing.

```
You will read two news articles (A and B) about the same event. List the content that appears in ONE article but not in the other.

For each article, list 3–5 elements that are present in it and absent from the other article. Each element must be:
- one atomic proposition, relevant to "what happened and why";
- of one type: fact | causal attribution | characterisation | loaded term | quoted-actor claim;
- genuinely absent from the other article in meaning, not just worded differently.
Prefer elements that change how a reader would understand the event (causes, blame, motives, characterisation of actors, key omitted facts).

Return JSON:
{"A": [{"id": "A1", "type": "...", "element_es": "...", "element_en": "...", "span": "<exact quote from A>", "why_absent_from_B": "<≤20 words>"}], "B": [ ... ]}
```
