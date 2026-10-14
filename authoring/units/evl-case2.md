# Unit: evl-case2

Course: **A6 Evals, Guardrails & Safe Operation** (id `evl`, folder `evals/`).

## Course brief
A6 is the deepest course of the path: evaluation as the core skill (error analysis, harnesses, LLM judges, statistics, human labels), benchmarks (construction, contamination, agent evals, leaderboards), truthfulness (hallucination causes, grounding/abstention, fact-checking and citation verification), adversaries (prompt injection, architectural defences, guardrail classifiers, red teaming), operations (tracing/OpenTelemetry GenAI conventions, the improvement flywheel, cost/latency/quality, incidents) and governance (NIST AI RMF, ISO/IEC 42001, EU AI Act timelines, privacy). Spine sources: Hamel Husain and Shreya Shankar's evals writing and FAQ, Shankar et al. 'Who Validates the Validators?' (2024), Zheng et al. MT-Bench/LLM-as-judge (2023), Evan Miller 'Adding Error Bars to Evals' (2024), tau-bench (2024), OpenAI 'Why language models hallucinate' (Sept 2025), 'The Attacker Moves Second' (Oct 2025), CaMeL (2025), Meta's Agents Rule of Two, OWASP Top 10 for LLM Applications and for Agentic Applications, NIST AI RMF and its Generative AI Profile, EU AI Act text and the Digital Omnibus proposal (verify status), UK AISI Inspect. Several of these were only seen via snippets during planning: fetch and verify before citing specifics. Link track-1 reliability ch 2, 4, 5, 6, 7, 16, 17 and security ch 1, 9, 15, 17.

## Your assignment: case studies

- `evals/cases/case-05-tau-bench.html` (data-case `C5`) · **tau-bench: Agents with Simulated Users** · pattern: End-state grading · Grading an agent by the database it leaves behind, and reliability measured as pass^k. Related: 08.
- `evals/cases/case-06-leaderboard-illusion.html` (data-case `C6`) · **The Leaderboard Illusion** · pattern: Rankings can be gamed · Private testing, selective disclosure and sampling rates behind a popular model arena. Related: 09.
- `evals/cases/case-07-ai-overviews.html` (data-case `C7`) · **Glue on Pizza: Search Answers Go Wrong** · pattern: Bad sources, confident answers · AI-generated search summaries that repeated jokes and satire as fact, and the fixes that followed. Related: 11, 17, ret:17.

Read the primary sources first (guide section 9). If a case's premise turns out to be wrong or unverifiable after research, write the best accurate version and flag it in your report.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/evl-case2/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).