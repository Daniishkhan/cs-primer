# Unit: evl-lab3

Course: **A6 Evals, Guardrails & Safe Operation** (id `evl`, folder `evals/`).

## Course brief
A6 is the deepest course of the path: evaluation as the core skill (error analysis, harnesses, LLM judges, statistics, human labels), benchmarks (construction, contamination, agent evals, leaderboards), truthfulness (hallucination causes, grounding/abstention, fact-checking and citation verification), adversaries (prompt injection, architectural defences, guardrail classifiers, red teaming), operations (tracing/OpenTelemetry GenAI conventions, the improvement flywheel, cost/latency/quality, incidents) and governance (NIST AI RMF, ISO/IEC 42001, EU AI Act timelines, privacy). Spine sources: Hamel Husain and Shreya Shankar's evals writing and FAQ, Shankar et al. 'Who Validates the Validators?' (2024), Zheng et al. MT-Bench/LLM-as-judge (2023), Evan Miller 'Adding Error Bars to Evals' (2024), tau-bench (2024), OpenAI 'Why language models hallucinate' (Sept 2025), 'The Attacker Moves Second' (Oct 2025), CaMeL (2025), Meta's Agents Rule of Two, OWASP Top 10 for LLM Applications and for Agentic Applications, NIST AI RMF and its Generative AI Profile, EU AI Act text and the Digital Omnibus proposal (verify status), UK AISI Inspect. Several of these were only seen via snippets during planning: fetch and verify before citing specifics. Link track-1 reliability ch 2, 4, 5, 6, 7, 16, 17 and security ch 1, 9, 15, 17.

## Your assignment: labs

- Page `evals/labs/lab-05-citations-abstention.html` (data-lab `L5`, after Part 3) with code in `evals/labs/code/lab05/` · **Lab 5: Citation Checking & Abstention**: Verify quoted spans, score claim support, then sweep an abstention threshold on a risk-coverage curve. Related chapters: 11, 12.
- Page `evals/labs/lab-06-red-team.html` (data-lab `L6`, after Part 4) with code in `evals/labs/code/lab06/` · **Lab 6: Red-Team a RAG Agent**: Forty injection payloads against four defences, with attack success rates and utility costs. Related chapters: 13, 14, 15.
  - Design notes: A small RAG agent with tools over a document set; forty injection payloads across families (direct override, role-play, encoded, indirect in retrieved docs, tool-output injection). Defences: none, keyword/regex guardrail, delimiting/spotlighting, classifier stand-in, capability restriction (no outbound tools after untrusted reads). Report attack success rate with confidence intervals and the utility cost on benign tasks. Include an adaptive-attacker milestone that mutates payloads against the best detector.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `evals/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/evl-lab3/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).