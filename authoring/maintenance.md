# Maintenance: claims to refresh

Dated claims the artifact track leans on. Re-check each from its primary source on the schedule given, update the page's "State of play" box (the ones marked with a `refresh-pill` are quarterly), and add the date you checked below.

## Quarterly

| Topic | Pages | What to re-check |
|---|---|---|
| Kernel-benchmark validity | `open-ended/chapters/15-evaluator-hacking.html`, `harness-eng/chapters/04-kernels-for-agents.html` | KernelBench and its verified variants, robust-kbench, any new hidden-test results or retractions |
| Harness-evolution methods | `open-ended/chapters/10`, `11`, `13`, `21`; `harness-eng/chapters/01-harness-engineering.html`, `02-aide-tree-search.html` | ShinkaEvolve, OpenEvolve, LEVI, ACE, Meta-Harness, AIDE and AIDE²; FML-Bench results |
| Self-improvement claims and lab automation indices | `open-ended/chapters/14`, `21`; `rsi-measurement/chapters/01`, `02`, `03` | Weco's Level-1 claim, Anthropic's AL4 share, Epoch's AL taxonomy, any OpenAI statement on automated research; mark every figure self-reported |
| Successors of the Darwin Gödel Machine | `open-ended/chapters/13`, `cases/case-06-darwin-godel-machine.html`, `chapters/21` | Huxley-Gödel Machine, HyperAgents, Red Queen Gödel Machine, and anything that beats them |

## On each artifact gate

- Re-read the artifact's `read` and `open` lists in `CS_ARTIFACTS` (`assets/js/catalog.js`): links still resolve, repositories still maintained.
- `contributing.html`: maintainers and activity of each repository.
- `lab-machine.html`: instance types, prices and quotas in the dated box.

## Unverified at the October 2026 rewrite

- OpenAI's post on the Hugging Face incident and its research-intern milestone returned HTTP 403 to authors; pages say so and do not rely on them.
- Lilian Weng's harness-engineering post was read only through a summary page (lilithai.dev); find the original.

## Log

- 2026-10-15: artifact-first overhaul (A5 and A8 removed, A9 to A12 added, A7 claims refreshed).
