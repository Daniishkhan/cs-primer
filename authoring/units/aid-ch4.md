# Unit: aid-ch4

Course: **A8 Applied AI Delivery Studio** (id `aid`, folder `ai-delivery/`).

## Course brief
A8 is the capstone: the applied / forward-deployed AI engineer's job. Discovery (interviews about past behaviour, requirements under ambiguity, capturing expert knowledge, feasibility triage), building the proof (riskiest-assumption prototypes, evaluation plans customers trust, choosing models under constraints), domains (finance, healthcare, legal, public sector: what each requires and forbids, with real regulation named and dated), delivery (PoC to production, restricted/on-prem/air-gapped environments, cost and ROI, security reviews), productisation and communication (research to product, writing for customers, take-homes, portfolios, interviews). It is broad, not tied to one employer. Good sources: Rob Fitzpatrick 'The Mom Test' (customer interviews), Hamel Husain on evals and on AI consulting, Chip Huyen 'AI Engineering' (2025), Palantir and OpenAI/Anthropic writing on forward-deployed engineering, Sakana AI's public 'Unofficial Guide' and its MUFG lending interview as one example among many, regulators' guidance (US Fed SR 11-7 model risk management, FDA AI-enabled device guidance, EU AI Act, HIPAA, GDPR). Lean heavily on links to A4-A7 and track-1 security/reliability chapters rather than re-teaching.

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `ai-delivery/chapters/12-poc-to-production.html` · chapter 12 · **deep** · Part 4 (Delivery) · **From Proof of Concept to Production**: Why most pilots stall, production gates, integration, support and change management.  → glossary `glossary-src/aid-12.json`
- `ai-delivery/chapters/13-restricted-environments.html` · chapter 13 · **core** · Part 4 (Delivery) · **Restricted Environments**: On-premises and air-gapped deployment, data residency and a limited menu of approved models.  → glossary `glossary-src/aid-13.json`
- `ai-delivery/chapters/14-cost-roi.html` · chapter 14 · **core** · Part 4 (Delivery) · **Cost Models & Return on Investment**: Unit economics per task, total cost of ownership and an honest return-on-investment case.  → glossary `glossary-src/aid-14.json`
- `ai-delivery/chapters/15-security-review.html` · chapter 15 · **core** · Part 4 (Delivery) · **Security Reviews for AI Systems**: The questions a customer's security team will ask, and the evidence pack that answers them.  → glossary `glossary-src/aid-15.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

For each deep chapter add at least one stepper or small interactive widget (guide section 6).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/aid-ch4/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).