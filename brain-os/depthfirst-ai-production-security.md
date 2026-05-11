# depthfirst — AI-Native Production Security

_Source: [depthfirst.com](https://depthfirst.com/), [TechCrunch Series A announcement](https://techcrunch.com/2026/01/14/ai-security-firm-depthfirst-announces-40-million-series-a/), January 2026_

## What it is

depthfirst is an AI-native security platform built on a concept they call **General Security Intelligence** — AI agents that build context on a company's code, infrastructure, and business logic to find complex vulnerabilities, triage them, and provide ready-to-merge fixes.

Founded 2024 by technical leaders from Google DeepMind, Databricks, and Faire. $40M Series A led by Accel (Jan 2026). Customers include Lovable, Supabase, Moveworks, and AngelList.

## Why it matters

The core thesis: software is being written faster than it can be secured. AI coding tools (Cursor, Claude Code, Copilot) are accelerating code production, while threats are becoming automated and autonomous. Traditional static analysis can't keep up — it produces too many false positives and misses logic-level vulnerabilities.

## How it works

### Multi-agent architecture
- Custom AI agents continuously analyze codebases, infrastructure, and workflows
- Not pattern-matching — builds understanding of how systems are structured and operate
- Catches logic flaws, insecure configurations, and emergent threats from component interactions
- Agents assess severity, reduce false positives, and generate actionable fixes (sometimes ready-to-merge PRs)

### Key design insight
On the CyberGym vulnerability-exploitation benchmark, depthfirst achieved ~90% improvement over baseline by redesigning the system around the model rather than naive prompting:
- Added accurate situational context
- Real-time runtime instrumentation
- Modular multi-agent architecture
- Raised success rates from 20-28% to 53%

**Takeaway:** LLM capability is often bottlenecked by system design, not model quality. Thoughtfully engineered agents unlock far more performance than model upgrades alone.

## Performance claims

- **8x more true-positive vulnerabilities** than traditional static analysis tools
- **85% reduction in false positives**
- State-of-the-art on CyberGym (leading cybersecurity evaluation framework)

## How AngelList uses it

- Weekly cadence: scans repos, analyzes application code + dependencies, surfaces vulnerabilities as actionable findings
- General Security Intelligence became the **source of truth** for security issues — consolidating knowledge previously scattered across Linear tickets, historical notes, and team memory
- Day-one value: surfaced 15 vulnerabilities with zero false positives

## Relevance to data work

As AI agents (like Genie Code) take autonomous actions in production — writing pipelines, modifying infrastructure, deploying models — the security surface area expands. depthfirst's approach of understanding business logic and system interactions (not just pattern-matching code) is relevant for:
- **Securing AI-generated data pipelines** — catching logic flaws in auto-generated ETL code
- **Infrastructure security for data platforms** — misconfigurations in Spark clusters, storage permissions, network policies
- **Audit trail for autonomous agents** — when Genie Code or similar tools make changes, security agents need to verify those changes
- **Continuous security for fast-moving data teams** — weekly automated scans rather than periodic manual reviews

## Open questions

- How does it handle data-platform-specific vulnerabilities (Spark, Delta Lake, Unity Catalog misconfigurations)?
- Integration with Databricks or other data platforms directly?
- How does the agent triage interact with existing SIEM/SOAR tools?
- Pricing model — the $40M raise suggests enterprise pricing, but no public details yet
