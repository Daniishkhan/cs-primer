# Unit: aid-case1

Course: **A8 Applied AI Delivery Studio** (id `aid`, folder `ai-delivery/`).

## Course brief
A8 is the capstone: the applied / forward-deployed AI engineer's job. Discovery (interviews about past behaviour, requirements under ambiguity, capturing expert knowledge, feasibility triage), building the proof (riskiest-assumption prototypes, evaluation plans customers trust, choosing models under constraints), domains (finance, healthcare, legal, public sector: what each requires and forbids, with real regulation named and dated), delivery (PoC to production, restricted/on-prem/air-gapped environments, cost and ROI, security reviews), productisation and communication (research to product, writing for customers, take-homes, portfolios, interviews). It is broad, not tied to one employer. Good sources: Rob Fitzpatrick 'The Mom Test' (customer interviews), Hamel Husain on evals and on AI consulting, Chip Huyen 'AI Engineering' (2025), Palantir and OpenAI/Anthropic writing on forward-deployed engineering, Sakana AI's public 'Unofficial Guide' and its MUFG lending interview as one example among many, regulators' guidance (US Fed SR 11-7 model risk management, FDA AI-enabled device guidance, EU AI Act, HIPAA, GDPR). Lean heavily on links to A4-A7 and track-1 security/reliability chapters rather than re-teaching.

## Your assignment: case studies

- `ai-delivery/cases/case-01-klarna.html` (data-case `C1`) · **Klarna's AI Assistant** · pattern: Automation claims meet customers · An assistant said to do the work of hundreds of agents, and the later decision to bring humans back. Related: 06, 12.
- `ai-delivery/cases/case-02-morgan-stanley.html` (data-case `C2`) · **A Research Assistant for Financial Advisers** · pattern: Evals before rollout · An assistant over a firm's own research library, gated by an evaluation framework built with experts. Related: 06, 08.
- `ai-delivery/cases/case-03-nyc-mycity.html` (data-case `C3`) · **A City's Chatbot Gives Illegal Advice** · pattern: Public-sector accountability · A government business-advice chatbot that told owners they could break the law. Related: 11, 04.
- `ai-delivery/cases/case-04-forward-deployed.html` (data-case `C4`) · **The Forward-Deployed Engineer** · pattern: Engineers embedded with customers · How embedding engineers with customers became a model for AI companies. Related: 01, 12.

Read the primary sources first (guide section 9). If a case's premise turns out to be wrong or unverifiable after research, write the best accurate version and flag it in your report.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/aid-case1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).