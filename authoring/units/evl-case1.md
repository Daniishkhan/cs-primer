# Unit: evl-case1

Course: **A6 Evals, Guardrails & Safe Operation** (id `evl`, folder `evals/`).

## Course brief
A6 is the deepest course of the path: evaluation as the core skill (error analysis, harnesses, LLM judges, statistics, human labels), benchmarks (construction, contamination, agent evals, leaderboards), truthfulness (hallucination causes, grounding/abstention, fact-checking and citation verification), adversaries (prompt injection, architectural defences, guardrail classifiers, red teaming), operations (tracing/OpenTelemetry GenAI conventions, the improvement flywheel, cost/latency/quality, incidents) and governance (NIST AI RMF, ISO/IEC 42001, EU AI Act timelines, privacy). Spine sources: Hamel Husain and Shreya Shankar's evals writing and FAQ, Shankar et al. 'Who Validates the Validators?' (2024), Zheng et al. MT-Bench/LLM-as-judge (2023), Evan Miller 'Adding Error Bars to Evals' (2024), tau-bench (2024), OpenAI 'Why language models hallucinate' (Sept 2025), 'The Attacker Moves Second' (Oct 2025), CaMeL (2025), Meta's Agents Rule of Two, OWASP Top 10 for LLM Applications and for Agentic Applications, NIST AI RMF and its Generative AI Profile, EU AI Act text and the Digital Omnibus proposal (verify status), UK AISI Inspect. Several of these were only seen via snippets during planning: fetch and verify before citing specifics. Link track-1 reliability ch 2, 4, 5, 6, 7, 16, 17 and security ch 1, 9, 15, 17.

## Your assignment: case studies

- `evals/cases/case-01-swe-bench-verified.html` (data-case `C1`) · **Retiring SWE-bench Verified** · pattern: Benchmark lifecycle · A widely reported coding benchmark, an audit of its hardest tasks, and why its main sponsor stopped using it. Related: 07, 08.
- `evals/cases/case-02-cuda-engineer.html` (data-case `C2`) · **The AI CUDA Engineer** · pattern: Evaluator hacking · Claimed kernel speedups that came from loopholes in the evaluation harness. Related: 02, 07, oe:15.
- `evals/cases/case-03-mata-avianca.html` (data-case `C3`) · **Fake Citations in Court** · pattern: Unverified generation · Lawyers who filed a brief citing cases a chatbot had invented, and the court's response. Related: 10, 12.
- `evals/cases/case-04-attacker-moves-second.html` (data-case `C4`) · **The Attacker Moves Second** · pattern: Adaptive attacks · Published prompt-injection defences re-tested against attackers who adapt, and what survived. Related: 13, 14.

Read the primary sources first (guide section 9). If a case's premise turns out to be wrong or unverifiable after research, write the best accurate version and flag it in your report.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/evl-case1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).