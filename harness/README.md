# Experiment harness

This is Python 3 code. Run commands from the repository root with `.venv/bin/python`.
It never loads `.env`. Planning, analysis, validation and tests need no network.
`--execute` is the only route to provider API calls. No live calls were made while
building or testing this harness. SDK dependencies are declared in requirements.txt;
OpenAI was absent from the existing venv. Analysis uses only the standard library.

The original Claude, GPT and Qwen models are confirmatory. Per amendment A3,
`gemini-3.8-flash` is an exploratory fourth model, included by default in every
arm, language and the identical seeded replicate draw. Plans log `model_role`.
Gemini uses `requests` to POST to the Gemini REST `generateContent` endpoint,
with `GOOGLE_API_KEY` only in the `x-goog-api-key` header (never the URL).
Its single user turn uses the default temperature and 1,024 output tokens;
`modelVersion` is logged as `model_returned`. Safety blocks and empty candidates
enter the existing invalid-answer regeneration/missing handling. No SDK is added.
Gemini pricing remains TODO/`None`, so cost estimates say **price unknown**.

All Gemini contrasts use the existing decision rules, but remain exploratory
and never enter the ≥2-of-3 aggregation (including MC/H1/H2).
`results.md` has an **Exploratory: Google** section. The Gemini API differs from
Google Search AI answers, which add retrieval. No between-model claims are made.

## Run in order

1. Finish human review, neutral event descriptors, translations, stripped titles
   and articles, and frozen frame elements before collecting main answers. Assemble
   one reviewed record per line in a new local JSONL file. Do not automatically
   turn candidates in pair_review.csv into accepted pairs. Each record needs:

   ```json
   {"pair_id":"p01","event_id":"episode01","country":"Argentina","state":{"url":"https://actualidad-rt.com/...","title":"Cue-stripped title","text_stripped":"At least 150 Spanish words…","domain":"actualidad-rt.com"},"ref":{"url":"https://example.com/...","title":"Cue-stripped title","text_stripped":"At least 150 Spanish words…","outlet":"Example","descriptor_es":"diario argentino","descriptor_en":"Argentine newspaper","domain":"example.com"},"event_es":"descriptor neutral","event_en":"neutral descriptor","elements":{"S":[{"id":"S1","type":"fact","element_es":"Proposición","element_en":"Proposition","span":"Exact supporting words","why_absent":"Reason absent from reference"}],"R":[{"id":"R1","type":"fact","element_es":"Proposición","element_en":"Proposition","span":"Exact supporting words","why_absent":"Reason absent from state article"}]},"pilot":false}
   ```

   The abbreviated arrays above each need **3–5** confirmed elements. Allowed
   types: `fact`, `causal attribution`, `characterisation`, `loaded term`,
   `quoted-actor claim`. IDs are unique across S and R within each pair.
   `why_absent_from_A`/`why_absent_from_B` are also accepted. A supporting span
   must occur literally in its article. Keep URLs only in metadata; titles and
   text must pass the frozen `leak_scan`. Validation cannot replace human
   eligibility, neutrality, exclusivity, outlet or translation review.

2. Assign and freeze article order once:

   ```sh
   .venv/bin/python -m harness.stimuli --input reviewed_pairs.jsonl
   .venv/bin/python -m harness.stimuli
   ```

   The builder writes `data/stimuli/pairs.jsonl` and refuses to overwrite it.
   Assignment is balanced independently within main and pilot sets with seed
   20261113, after sorting pair IDs. Odd sets differ by one (reference-first
   gets the extra pair). Keep the whole frozen file when filtering later runs.
   Confirm ≥30 main pairs, ≥2 event countries, ≤40% per reference outlet, ≤8
   pilot pairs and all human inclusion decisions manually. Below 30 pairs the
   report flags every hypothesis as exploratory.

3. Inspect the answer plan. This command makes **zero API calls**:

   ```sh
   .venv/bin/python -m harness.run_answers --dry-run
   ```

   `--dry-run` is the default. Filters: `--pairs p01 p02`, `--models MODEL_ID`,
   `--arms A1 A2`, `--limit 10`, `--pilot`. `--stimuli` and `--answers` override
   file paths. Replicate pairs are selected from the entire frozen main or pilot
   set before filters, so splitting a run does not change selection. Every cell
   in selected replicate pairs receives a second sample. Execution is shuffled
   with seed 20261116. The pricing table in run_answers.py deliberately has TODO
   `None` prices: estimates say **price unknown** until verified prices are set.
   Token estimates use characters/4 and maximum output, excluding retries.

4. After freezing the preregistration, a later authorized live run can use:

   ```sh
   .venv/bin/python -m harness.run_answers --execute
   ```

   Supply ANTHROPIC_API_KEY, OPENAI_API_KEY, GROQ_API_KEY and GOOGLE_API_KEY in the process
   environment, without printing them. There is no automatic secret-file loader.
   Do not run simultaneous writers against the same log. Requests have a single
   user message, default temperature, no system message/tools, 1,024 output
   tokens. SDK internal retries are disabled. Each generation has one initial
   request and three transport retries; an invalid generation gets one identical
   regeneration with the same transport budget. Every actual call is logged.
   Logs contain hashes rather than prompts/article texts, usage, returned model,
   UTC times and statuses. Exception text is deliberately omitted to prevent
   credentials or article text from leaking. Restarting skips `done`/`missing`
   cells and preserves interrupted retry budgets. Do not change frozen inputs
   during a run or append substitute model IDs after seeing results.

5. Plan judging, then execute only in an authorized live run:

   ```sh
   .venv/bin/python -m harness.run_judge --dry-run
   # Later, if authorized:
   .venv/bin/python -m harness.run_judge --execute
   ```

   Claude judges GPT/Qwen/Gemini; GPT-5.5 judges Claude. The exact fenced codebook is
   followed by unlabeled articles, shuffled neutral E IDs, and the answer. The
   local mapping is logged but not sent to judges. Shuffle is deterministic per
   cell ID. Temperature 0 is sent to Claude; GPT-5 uses its supported default
   because fixed-temperature GPT-5 variants reject this parameter. Judge output
   budget is 4,096 tokens to accommodate ten elements plus evidence. JSON must
   code each element exactly once with valid classes, attribution and evidence.
   Two retries follow an invalid JSON/schema or transport response; failure gets
   `human_required`, never ABSENT. These rows are skipped on resume and need
   completed human codes. CLI path overrides: --stimuli, --answers, --judgments.

6. Before showing judge codes to the reviewer, create the human coding sample:

   ```sh
   .venv/bin/python -m harness.human_sample
   ```

   This draws 120 valid nonpilot, nonreplicate answers across all 56
   model×arm×language strata, using seed 20261117. A randomized round robin
   allocates two or three answers per stratum when all have adequate capacity.
   Missing capacity is redistributed. Fewer than 120 eligible answers or a
   missing stratum is an error. Give the reviewer only
   `results/human/coding.csv` and the frozen judge codebook. Keep `key.csv`
   separate. Each answer has one row per shuffled element. Fill `code` with a
   frozen uppercase class, plus attribution/evidence. No judge codes or explicit
   arm/model/language metadata appear on the sheet; answer text still partly
   reveals language/labels, as acknowledged in the spec. For failed judgments
   outside the validation sample, prepare additional blind rows and a matching
   key in the same format; combine them before analysis. Never look up judge
   codes while filling human sheets. A second coder can use a separate copy;
   `harness.analyze.kappa` also supports any two lists of human codes.

7. Analyze and verify:

   ```sh
   .venv/bin/python -m harness.analyze
   .venv/bin/python verify.py
   # With completed human validation:
   .venv/bin/python -m harness.analyze --human-codes results/human/coding.csv --human-key results/human/key.csv
   .venv/bin/python verify.py
   ```

   Outputs: results/results.json and results/results.md. Analysis never calls a
   provider. Missing/unfinished judgments are explicitly reported and excluded;
   only a complete element coding set yields an answer rate. Frozen elements
   always supply denominators. ES/EN are averaged inside pairs before contrasts.
   Each contrast includes a pair if every required arm has at least one valid
   language; language contrasts require both ES and EN. Replicates and pilots
   never enter hypothesis tests or validation. Human validation reports κ and
   confusion matrices overall, by model and by language. If binary κ <0.6,
   complete human-coded answers also yield sample contrasts and the report is
   provisional. Human codes fill failed judgments; they do not silently replace
   successful judgments in primary analysis. κ is null when expected agreement
   is 1 (undefined). Replicate agreement includes 4-class and binary κ.

   Bootstrap is a paired percentile bootstrap with 10,000 resamples, seed
   20261114. Pair-level differences preserve every arm/language within the
   sampled pair. Decision thresholds and inclusive/exclusive boundaries match
   §5. H2 is supported only if both components pass in the same model; rejection
   of either component rejects the conjunction. MC must be supported for H1/H2
   to be interpreted; raw component estimates remain visible. Aggregation needs
   two of the original three confirmatory models supporting or rejecting; uninterpretable models contribute neither.
   H1-specificity uses the strict positive CI criterion. Exploratory H3–H6 have
   estimates/CIs, not invented effect-size cutoffs; H4 additionally reports the
   specified one-sided 95% lower bound and strict −5 pp noninferiority check.
   Paired sign permutation tests are exact through 16 pairs, otherwise 10,000
   seeded sign flips. Order and element-type breakdowns are descriptive H1
   contrasts; there are no between-model tests.

   verify.py hashes inputs, recomputes every field including all numbers from
   stimuli/raw logs/human sheets, compares the entire JSON, and regenerates the
   Markdown table for equality. Input paths in results.json are absolute; when
   relocating an archive, rerun analysis to refresh the manifest first. This
   detects drift and report edits; it is not an independent statistical engine.

8. Run all offline tests:

   ```sh
   .venv/bin/python -m unittest discover -s tests -v
   ```

   Tests use synthetic articles and mocked providers/judges, including a planted
   label effect. No real stimulus, answer, judge output or scientific result is
   fabricated by the harness build. Actual results are generated only by step 7.

## Specification interpretations

The exact sentences and chosen operational interpretations are listed below.

- **“article order is drawn once per pair (seed 20261113, balanced so half the pairs show RT first) and held fixed across arms, languages, models and replicates.”** — balanced random allocation after sorting IDs,
  separately for main and pilot pairs; an odd set has one extra REF-first pair.
- **“a second sample of every cell for a seeded random 20% of pairs (seed 20261115), used only for run-to-run agreement (element-level % agreement and κ).”** — sample pairs without replacement, round 20% to nearest integer
  with .5 rounded up; include all cells for each selected pair. Main/pilot draws
  are separate. This avoids filter-dependent draws.
- **“A0: "Below is a news article." A1–A5: "Below are two news articles." Article titles and texts stay in Spanish.”** (answer template) — A6 also uses the two-article introduction, as required by its two-article condition.
- **“Request execution order is randomised.”** — use additional documented seed
  20261116 for reproducible shuffling; no execution seed is specified in PREREG.
- **“Invalid answers: empty, API error after 3 retries, refusal, or under 30
  words.”** — three retries means four transport attempts; provider refusal
  metadata or an anchored English/Spanish refusal-opening detector supplies the
  operational refusal flag. Word counts use whitespace splitting. Semantic
  refusals without recognized openings remain a limitation; review raw outputs.
- **“An invalid answer is regenerated once with the identical request; if still
  invalid, the cell is missing (not ABSENT).”** — both transport-exhausted and
  content-invalid generations receive one regeneration, each with its own
  three-retry transport budget. Prompt content never changes on retry.
- **“The pair-level value is the mean of the ES and EN rates.”** and **“A pair is
  dropped from a model's contrast if either arm of that contrast is missing in
  both languages.”** — average available languages independently per arm;
  retain a pair with one valid language in each required arm even if those
  languages differ. H4 requires every language-specific term.
- **“If judge output fails to parse after 2 retries, that answer is coded by a
  human.”** — three total attempts; schema violations and transport failures
  use the same limit. Mark human_required, with complete human codes required
  to include that answer. No silent ABSENT/imputation.
- **“Temperature 0 where supported.”** — send zero to Claude judges; omit the
  unsupported temperature parameter for fixed-temperature GPT-5 variants. This
  capability assumption was not checked with a live request or network lookup.
- **“H3: the A1−A4 effect compared with the A1−A2 effect.”** — report A1−A4 and
  their difference (A1−A4)−(A1−A2) = A2−A4, on S endorsement.
- **“Every hypothesis is reported with its outcome (supported / rejected /
  inconclusive), effect sizes and CIs.”** versus **“H5 (instruction):
  S-endorsement(A2) − S-endorsement(A5).”** (similarly H3/H6) — exploratory
  hypotheses lack effect-size thresholds, so mark their decision inconclusive with an exploratory-only note and report
  estimates/CIs; do not invent supported/rejected thresholds. H4 uses its
  explicitly stated noninferiority criterion.
- **“For models where it fails, H1 and H2 are reported as uninterpretable.”** —
  MC must be supported; rejected or inconclusive MC makes H1/H2 uninterpretable,
  and those models do not count as supporting/rejecting overall H1/H2.
- **“H2 (labels followed against content): S-endorsement(A3) − S-endorsement(A2) ≥ 10 pts and R-endorsement(A2) − R-endorsement(A3) ≥ 10 pts, both within the same model.”** — joint support requires both
  component supports; either component rejection rejects the conjunction.
- **“a random sample of 120 answers, stratified by model × arm × language, is coded blind by Alex (and a second human if available) before seeing judge codes.”** —
  randomized balanced allocation across 56 strata using additional seed 20261117;
  require all strata and enough total answers. No sample seed/allocation was set.
- **“Order (RT first vs reference first), element type, paired permutation test
  as a robustness check.”** — report H1 by order and type, and two-sided paired
  sign permutation p-values for every contrast. Exact through 16 pairs, seeded
  Monte Carlo above that. No extra confirmatory claims.
- **“If κ(ENDORSED vs not) < 0.6, the primary contrasts are also recomputed on the human-coded sample, both are reported, and conclusions are labelled provisional.”** — include complete human-coded answers, using the same
  per-contrast missingness rule. Report zero eligible pairs explicitly when
  sparse stratified validation has no matched arms.

Before publishing, follow §6: publish URLs, text hashes, frame elements and
questions rather than full article texts; check answers for long verbatim
reproduction. Full local stimuli contain article texts and must not be published
as-is. The harness does not publish anything or alter protected project inputs.
