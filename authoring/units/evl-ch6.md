# Unit: evl-ch6

Course: **A6 Evals, Guardrails & Safe Operation** (id `evl`, folder `evals/`).

## Course brief
A6 is the deepest course of the path: evaluation as the core skill (error analysis, harnesses, LLM judges, statistics, human labels), benchmarks (construction, contamination, agent evals, leaderboards), truthfulness (hallucination causes, grounding/abstention, fact-checking and citation verification), adversaries (prompt injection, architectural defences, guardrail classifiers, red teaming), operations (tracing/OpenTelemetry GenAI conventions, the improvement flywheel, cost/latency/quality, incidents) and governance (NIST AI RMF, ISO/IEC 42001, EU AI Act timelines, privacy). Spine sources: Hamel Husain and Shreya Shankar's evals writing and FAQ, Shankar et al. 'Who Validates the Validators?' (2024), Zheng et al. MT-Bench/LLM-as-judge (2023), Evan Miller 'Adding Error Bars to Evals' (2024), tau-bench (2024), OpenAI 'Why language models hallucinate' (Sept 2025), 'The Attacker Moves Second' (Oct 2025), CaMeL (2025), Meta's Agents Rule of Two, OWASP Top 10 for LLM Applications and for Agentic Applications, NIST AI RMF and its Generative AI Profile, EU AI Act text and the Digital Omnibus proposal (verify status), UK AISI Inspect. Several of these were only seen via snippets during planning: fetch and verify before citing specifics. Link track-1 reliability ch 2, 4, 5, 6, 7, 16, 17 and security ch 1, 9, 15, 17.

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `evals/chapters/19-cost-latency-quality.html` · chapter 19 · **core** · Part 5 (Operations) · **Cost, Latency & Quality Trade-offs**: Pareto fronts, model routing, caching and deciding what 'good enough' costs.  → glossary `glossary-src/evl-19.json`
- `evals/chapters/20-ai-incidents.html` · chapter 20 · **intro** · Part 5 (Operations) · **AI Incident Response**: Detecting, containing and learning from an AI system that misbehaves in production.  → glossary `glossary-src/evl-20.json`
- `evals/chapters/21-governance.html` · chapter 21 · **core** · Part 6 (Governance) · **Governance Frameworks & Regulation**: NIST AI RMF, ISO/IEC 42001 and the EU AI Act, read as engineering requirements.  → glossary `glossary-src/evl-21.json`
- `evals/chapters/22-privacy-data.html` · chapter 22 · **core** · Part 6 (Governance) · **Privacy & Data Handling for AI**: PII in prompts and logs, retention, training on customer data, and data residency.  → glossary `glossary-src/evl-22.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/evl-ch6/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).