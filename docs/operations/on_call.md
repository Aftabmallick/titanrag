# TitanRAG Enterprise — On-Call Incident Response Playbook

## 1. Incident Severity Matrix & Response SLAs

| Severity | Definition | Response SLA | Resolution Target | Escalation Protocol |
|----------|------------|--------------|-------------------|---------------------|
| **P1 — Critical** | Complete platform outage, cross-tenant data leak, or severe security compromise | **< 15 minutes** | **< 2 hours** | Page Primary On-Call + Lead Architect + Security Officer |
| **P2 — Major** | Degraded search/generation, ingestion stalled, or upstream LLM provider outage | **< 30 minutes** | **< 4 hours** | Page Primary On-Call; escalate to Tech Lead if unmitigated after 1h |
| **P3 — Moderate** | Single workspace failure, non-critical connector sync delay, or metric ingestion lag | **< 2 hours** | **< 1 business day** | Normal ticketing queue with automated assignment |
| **P4 — Minor** | UI visual glitch, documentation typo, or minor performance variance | **Next business day** | **Sprint backlog** | Log in issue tracker |

---

## 2. Incident Commander Protocol

1. **Acknowledge PagerDuty / Alert**: Within 15 minutes.
2. **Open Incident Slack Channel**: `#inc-YYYYMMDD-<incident-name>`.
3. **Appoint Roles**: Incident Commander (IC), Communications Lead, Operations Lead.
4. **Determine Triage Runbook**: Match alert to `docs/runbooks/` (RB-01 through RB-06).
5. **Mitigate First, Diagnose Second**: Scale workers, switch LLM failover, or activate Blue-Green rollback.
6. **Publish Resolution**: Post resolution notice in status channel.
7. **Initiate Post-Mortem**: Schedule blameless review within 48 hours.

---

## 3. Blameless Post-Mortem Template

```markdown
# Post-Mortem: [Incident Title] - [Date]

## Incident Summary
- **Duration**: [Start Time] - [End Time] (Total: X minutes)
- **Impact**: [Users / Workspaces / Queries affected]
- **Severity**: [P1 / P2]

## Timeline (UTC)
- HH:MM - Alert triggered
- HH:MM - Primary acknowledged
- HH:MM - Mitigation applied
- HH:MM - All systems operational

## Root Cause Analysis (5 Whys)
1. Why did the service fail?
2. Why did that condition occur?
3. Why was it not caught in CI?
4. Why did monitoring not preempt it?
5. Why was the architecture vulnerable?

## Corrective Action Items
| Action Item | Owner | Priority | Target Date |
|-------------|-------|----------|-------------|
| [Action 1]  | [Name]| High     | YYYY-MM-DD  |
```
