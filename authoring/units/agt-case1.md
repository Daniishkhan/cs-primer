# Unit: agt-case1

Course: **A4 Agents, Tools & Protocols** (id `agt`, folder `agents/`).

## Course brief
A4 teaches agents as engineering: the tool loop, tool design, function calling, MCP and A2A protocols, context engineering and memory, workflow patterns, multi-agent systems, durable execution, deep-research, computer-use and coding agents, agent security, sandboxes, frameworks and AI coding tools. Spine sources: Anthropic engineering posts ('Building effective agents' Dec 2024, 'Effective context engineering for AI agents', 'Writing effective tools for agents', 'How we built our multi-agent research system', 'Claude Code best practices'), OpenAI's 'A practical guide to building agents', the MCP specification (versions 2025-06-18, 2025-11-25; a 2026-07-28 revision removes the initialize handshake/sessions per its release-candidate post: VERIFY the final text at modelcontextprotocol.io before stating details), the A2A project (a2a-protocol.org, Linux Foundation), Simon Willison on the lethal trifecta (June 2025), METR's July 2025 RCT. Message format in examples: the content-block shape used by lab-support/llm.py (text, tool_use, tool_result blocks). Use the ScriptedModel/RuleModel stand-ins for runnable examples. Link track-1: networking ch 10 (HTTP), 12 (APIs), 16 (failure, retries); distributed ch 17 (exactly-once); architecture ch 15 (sagas); security ch 1, 7, 8, 9, 11.

## Your assignment: case studies

- `agents/cases/case-01-multi-agent-research.html` (data-case `C1`) · **A Multi-Agent Research System** · pattern: Orchestrator-workers · Anthropic's write-up of a lead agent spawning researchers, and what token usage explained. Related: 14, 16.
- `agents/cases/case-02-swe-agent.html` (data-case `C2`) · **SWE-agent and the Agent-Computer Interface** · pattern: Tools shaped for models · Why a purpose-built file viewer and editor beat a raw shell for a coding agent. Related: 05, 18.
- `agents/cases/case-03-metr-rct.html` (data-case `C3`) · **Measuring AI Coding Productivity** · pattern: Measure, don't assume · A randomised trial in which experienced developers were slower with AI and believed they were faster. Related: 22.
- `agents/cases/case-04-mcp-evolution.html` (data-case `C4`) · **How MCP Changed, 2024 to 2026** · pattern: Protocols evolve · From a local stdio protocol to remote servers, OAuth and a stateless redesign. Related: 07, 08.

Read the primary sources first (guide section 9). If a case's premise turns out to be wrong or unverifiable after research, write the best accurate version and flag it in your report.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/agt-case1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).