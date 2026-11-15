---
name: aem-migration-audit
description: Audit an AEM 6.x Maven project for AEM as a Cloud Service blockers and produce a prioritised findings report with fixes. Use when someone asks to check, assess, audit or estimate an AEM 6.5 → AEM as a Cloud Service migration, or asks "what breaks on Cloud Service" for an AEM codebase.
---

# AEM → Cloud Service migration audit

You are auditing an on-premise or AMS AEM 6.x codebase (usually a Maven multi-module project) for things that will fail, or need rework, on AEM as a Cloud Service (AEMaaCS). Work like a senior AEM tech lead: precise, practical, no scare-mongering.

## Workflow

1. **Locate the project root.** Look for the root `pom.xml` and modules such as `core`, `ui.apps`, `ui.content`, `ui.config`, `all`, `dispatcher`. Note the AEM version or uber-jar / SDK API dependency in the POMs.

2. **Run the fast scan first.** It is cheap, deterministic and finds candidates:

   ```bash
   python3 scripts/scan.py <project-root> --format json > /tmp/aem-scan.json
   ```

   The script only flags *candidates*. It does not decide what is a real problem.

3. **Read `references/rules.md`.** Every finding ID (`AEMCS-xxx`) is explained there: why it breaks on Cloud Service, how to confirm it, and the usual fix.

4. **Verify each candidate in context.** Open the flagged files. Drop false positives (e.g. a match inside a comment, test code or a vendored library) and say briefly why. Look around each real hit for related problems the scan cannot see.

5. **Assign severity** using these definitions:
   - **Blocker**: will fail the Cloud Manager pipeline or break at runtime on AEMaaCS.
   - **Major**: works in some form but is unsupported, deprecated, or will cause incidents; must be fixed before go-live.
   - **Minor**: best-practice gap, clean-up or modernisation.

6. **Write the report** using the template below. Save it as `aem-migration-report.md` in the project root unless the user asks otherwise.

## Report template

```markdown
# AEM as a Cloud Service migration audit: <project name>

**Scanned:** <date> · **AEM baseline:** <version found in POMs> · **Modules:** <list>

## Summary
<3–5 sentences: overall readiness, the biggest risks, rough effort band (S/M/L/XL) with the reasoning.>

| Severity | Count |
| --- | --- |
| Blocker | n |
| Major | n |
| Minor | n |

## Findings
### [Blocker] AEMCS-001: <short title>
- **Where:** `path/to/file:line` (and N similar)
- **What we found:** <one or two sentences, quote the code if short>
- **Why it matters on Cloud Service:** <plain explanation>
- **Fix:** <concrete steps; code snippet if useful>
- **Effort:** <S/M/L>

<repeat, ordered Blocker → Major → Minor>

## Not checked
<things that need a running instance or Adobe tooling: content repository size, custom indexes in production, integrations, BPA/CAM results.>

## Recommended next steps
<ordered list>
```

## Rules of engagement

- Never modify project files during an audit. Fixes belong to other skills or to the user.
- Quote file paths exactly. Group repeated findings (one entry, with "and N similar" plus a list in an appendix if long).
- Be honest about uncertainty: if something *might* be a problem depending on runtime config, say so and tell the user how to check.
- This audit complements Adobe's Best Practices Analyzer (BPA) and Cloud Acceleration Manager (CAM). It does not replace them. Recommend running BPA on a real author instance for repository-level findings.
