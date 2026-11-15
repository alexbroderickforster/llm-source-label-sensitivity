# Experiment results

All effects are percentage points. S/R identify source exclusivity, not truth.

A3 uses deliberately false labels. A4 scores are experimental assignments, not outlet ratings.

All hypotheses exploratory: False. Provisional: True.

| Model | Test | Pairs | Effect (pp) | 95% CI | Outcome |
|---|---|---:|---:|---|---|
| claude-sonnet-5-5 | MC | 40 | 38.708 | [29.666, 47.979] | supported |
| claude-sonnet-5-5 | H1 | 40 | 17.042 | [11.458, 22.980] | supported |
| claude-sonnet-5-5 | H1_specificity | 40 | 0.271 | [-8.188, 8.417] | inconclusive |
| claude-sonnet-5-5 | H2_S | 40 | 4.271 | [-1.542, 9.834] | rejected |
| claude-sonnet-5-5 | H2_R | 40 | -0.292 | [-6.896, 6.104] | rejected |
| claude-sonnet-5-5 | H2_A3_vs_A1 | 40 | -12.771 | [-19.396, -6.292] | inconclusive |
| claude-sonnet-5-5 | H2_R_A3_vs_A1 | 40 | -16.479 | [-23.438, -9.667] | inconclusive |
| claude-sonnet-5-5 | H3_numeric | 40 | 18.938 | [11.374, 26.312] | inconclusive |
| claude-sonnet-5-5 | H3_comparison | 40 | 1.896 | [-3.667, 7.271] | inconclusive |
| claude-sonnet-5-5 | H4 | 40 | 9.417 | [-2.167, 20.917] | inconclusive |
| claude-sonnet-5-5 | H5 | 40 | 9.438 | [3.271, 16.292] | inconclusive |
| claude-sonnet-5-5 | H6_domain | 40 | 12.750 | [5.770, 19.938] | inconclusive |
| claude-sonnet-5-5 | H6_explicit_added | 40 | 4.292 | [-1.896, 10.646] | inconclusive |
| claude-sonnet-5-5 | H2 joint | — | — | — | rejected |
| gpt-5.4-mini-2026-03-17 | MC | 40 | 14.646 | [9.083, 20.542] | inconclusive |
| gpt-5.4-mini-2026-03-17 | H1 | 40 | 2.688 | [-2.438, 7.708] | uninterpretable (MC failed) |
| gpt-5.4-mini-2026-03-17 | H1_specificity | 40 | 5.208 | [-0.542, 10.855] | inconclusive |
| gpt-5.4-mini-2026-03-17 | H2_S | 40 | 1.167 | [-2.771, 5.188] | uninterpretable (MC failed) |
| gpt-5.4-mini-2026-03-17 | H2_R | 40 | 4.000 | [0.271, 7.667] | uninterpretable (MC failed) |
| gpt-5.4-mini-2026-03-17 | H2_A3_vs_A1 | 40 | -1.521 | [-5.333, 2.000] | inconclusive |
| gpt-5.4-mini-2026-03-17 | H2_R_A3_vs_A1 | 40 | -1.479 | [-5.500, 2.730] | inconclusive |
| gpt-5.4-mini-2026-03-17 | H3_numeric | 40 | 6.625 | [1.896, 11.417] | inconclusive |
| gpt-5.4-mini-2026-03-17 | H3_comparison | 40 | 3.938 | [-0.979, 9.167] | inconclusive |
| gpt-5.4-mini-2026-03-17 | H4 | 40 | -3.208 | [-11.751, 5.583] | inconclusive |
| gpt-5.4-mini-2026-03-17 | H5 | 40 | -2.000 | [-6.417, 2.750] | inconclusive |
| gpt-5.4-mini-2026-03-17 | H6_domain | 40 | 2.083 | [-1.313, 5.750] | inconclusive |
| gpt-5.4-mini-2026-03-17 | H6_explicit_added | 40 | 0.604 | [-4.167, 5.167] | inconclusive |
| gpt-5.4-mini-2026-03-17 | H2 joint | — | — | — | uninterpretable (MC failed) |
| qwen/qwen3.8-27b | MC | 40 | 53.333 | [44.958, 61.604] | supported |
| qwen/qwen3.8-27b | H1 | 40 | 8.917 | [3.583, 14.375] | inconclusive |
| qwen/qwen3.8-27b | H1_specificity | 40 | 7.188 | [-1.437, 15.729] | inconclusive |
| qwen/qwen3.8-27b | H2_S | 40 | 9.833 | [3.146, 16.625] | inconclusive |
| qwen/qwen3.8-27b | H2_R | 40 | -3.292 | [-10.687, 3.563] | rejected |
| qwen/qwen3.8-27b | H2_A3_vs_A1 | 40 | 0.917 | [-3.104, 4.917] | inconclusive |
| qwen/qwen3.8-27b | H2_R_A3_vs_A1 | 40 | 1.562 | [-4.333, 7.167] | inconclusive |
| qwen/qwen3.8-27b | H3_numeric | 40 | 12.271 | [5.896, 18.792] | inconclusive |
| qwen/qwen3.8-27b | H3_comparison | 40 | 3.354 | [-2.208, 8.833] | inconclusive |
| qwen/qwen3.8-27b | H4 | 40 | -1.250 | [-13.167, 10.833] | inconclusive |
| qwen/qwen3.8-27b | H5 | 40 | 5.125 | [-1.667, 11.771] | inconclusive |
| qwen/qwen3.8-27b | H6_domain | 40 | 6.292 | [0.271, 12.292] | inconclusive |
| qwen/qwen3.8-27b | H6_explicit_added | 40 | 2.625 | [-4.354, 9.792] | inconclusive |
| qwen/qwen3.8-27b | H2 joint | — | — | — | rejected |

## Exploratory: Google

Gemini API results are exploratory and excluded from the ≥2-of-3 aggregation. The Gemini API differs from Google Search AI answers, which add retrieval.

| Model | Test | Pairs | Effect (pp) | 95% CI | Outcome |
|---|---|---:|---:|---|---|
| gemini-3.8-flash | MC | 40 | 54.438 | [45.833, 62.959] | supported |
| gemini-3.8-flash | H1 | 40 | 6.917 | [0.333, 13.063] | inconclusive |
| gemini-3.8-flash | H1_specificity | 40 | 2.000 | [-4.625, 8.167] | inconclusive |
| gemini-3.8-flash | H2_S | 40 | 1.146 | [-4.271, 6.647] | rejected |
| gemini-3.8-flash | H2_R | 40 | -4.000 | [-8.188, 0.313] | rejected |
| gemini-3.8-flash | H2_A3_vs_A1 | 40 | -5.771 | [-12.667, 1.563] | inconclusive |
| gemini-3.8-flash | H2_R_A3_vs_A1 | 40 | -0.917 | [-6.125, 4.042] | inconclusive |
| gemini-3.8-flash | H3_numeric | 40 | 31.458 | [23.479, 39.417] | inconclusive |
| gemini-3.8-flash | H3_comparison | 40 | 24.542 | [17.500, 31.833] | inconclusive |
| gemini-3.8-flash | H4 | 40 | -2.250 | [-11.543, 6.833] | inconclusive |
| gemini-3.8-flash | H5 | 40 | 15.917 | [8.167, 23.855] | inconclusive |
| gemini-3.8-flash | H6_domain | 40 | 8.396 | [3.292, 13.729] | inconclusive |
| gemini-3.8-flash | H6_explicit_added | 40 | -1.479 | [-8.083, 5.208] | inconclusive |
| gemini-3.8-flash | H2 joint | — | — | — | rejected |

claude-sonnet-5-5: H1 specificity: non-selective (general hedging).


gpt-5.4-mini-2026-03-17: H1 has a floor problem (A1 S endorsement below 20%).


gpt-5.4-mini-2026-03-17: H1 specificity: not applicable.


qwen/qwen3.8-27b: H1 specificity: not applicable.


gemini-3.8-flash: H1 specificity: not applicable.


Overall (≥2 of 3 original confirmatory models): MC: supported, H1: inconclusive, H1_specificity: inconclusive, H2_S: inconclusive, H2_R: rejected, H2: rejected.

Full secondary outcomes, missingness, validation and pair effects are in results.json. No between-model effect comparisons are made.
