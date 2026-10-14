# Unit: evl-studio1

Course: **A6 Evals, Guardrails & Safe Operation** (id `evl`, folder `evals/`).

## Course brief
A6 is the deepest course of the path: evaluation as the core skill (error analysis, harnesses, LLM judges, statistics, human labels), benchmarks (construction, contamination, agent evals, leaderboards), truthfulness (hallucination causes, grounding/abstention, fact-checking and citation verification), adversaries (prompt injection, architectural defences, guardrail classifiers, red teaming), operations (tracing/OpenTelemetry GenAI conventions, the improvement flywheel, cost/latency/quality, incidents) and governance (NIST AI RMF, ISO/IEC 42001, EU AI Act timelines, privacy). Spine sources: Hamel Husain and Shreya Shankar's evals writing and FAQ, Shankar et al. 'Who Validates the Validators?' (2024), Zheng et al. MT-Bench/LLM-as-judge (2023), Evan Miller 'Adding Error Bars to Evals' (2024), tau-bench (2024), OpenAI 'Why language models hallucinate' (Sept 2025), 'The Attacker Moves Second' (Oct 2025), CaMeL (2025), Meta's Agents Rule of Two, OWASP Top 10 for LLM Applications and for Agentic Applications, NIST AI RMF and its Generative AI Profile, EU AI Act text and the Digital Omnibus proposal (verify status), UK AISI Inspect. Several of these were only seen via snippets during planning: fetch and verify before citing specifics. Link track-1 reliability ch 2, 4, 5, 6, 7, 16, 17 and security ch 1, 9, 15, 17.

## Your assignment: design studios

- `evals/studios/studio-01-eval-program.html` (data-studio `S1`, after Part 2) · **Design the Eval Program for an Assistant**: Who labels, what is measured, how often, which numbers block a release and who signs off. Related chapters: 01, 03, 06.
- `evals/studios/studio-02-agent-guardrails.html` (data-studio `S2`, after Part 4) · **Design Guardrails for an Agent with Tools**: An agent that reads email and can send it: threat model, capability limits, classifiers and monitoring. Related chapters: 13, 14, 15.
- `evals/studios/studio-03-llm-observability.html` (data-studio `S3`, after Part 5) · **Design LLM Observability & Continuous Evaluation**: Traces at scale, online evaluators, sampling, dashboards, alerts and the path from failure to fix. Related chapters: 17, 18, 19.
- The course toolbox `evals/toolbox.html` (data-page toolbox) with one tool card per catalog tool, ids: `inspect` (Inspect), `promptfoo` (promptfoo), `tracing` (Langfuse & Phoenix), `redteam` (garak & PyRIT), `labelling` (Annotation tools), `presidio` (Presidio). See guide section 11.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/evl-studio1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).