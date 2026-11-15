---
name: aem-migration-audit
description: Assess an AEM 6.x Maven project's readiness for AEM as a Cloud Service from the code repository alone, and write a prioritised report with impact, Adobe quality-rule mapping, effort and next steps. Use when someone asks to check, assess, audit or estimate an AEM 6.5 → AEM as a Cloud Service migration, or asks "what breaks on Cloud Service" for an AEM codebase.
---

# AEM Cloud Service readiness assessment

You are assessing an on-premise or AMS AEM 6.x codebase (usually a Maven multi-module project) for things that will fail, or need rework, on AEM as a Cloud Service (AEMaaCS). Work like a senior AEM tech lead preparing a migration estimate: precise, practical, no scare-mongering.

This assessment needs only the Git repository. It doesn't need a running AEM instance or a Best Practices Analyzer (BPA) report. It is the step **before** fixing: where Adobe's AEM Cloud Migration skill has a pattern for a finding, hand the fix to it.

## Workflow

1. **Locate the project root.** Look for the root `pom.xml` and modules such as `core`, `ui.apps`, `ui.content`, `ui.config`, `all`, `dispatcher`. Note the AEM version or uber-jar / SDK API dependency in the POMs.

2. **Run the fast scan first.** It is cheap, deterministic and finds candidates:

   ```bash
   python3 scripts/scan.py <project-root> --format json > /tmp/aem-scan.json
   ```

   The script only flags *candidates*. It does not decide what is a real problem.

3. **Read `references/rules.md`.** Every finding ID (`AEMCS-xxx`) is explained there: impact, the matching Adobe quality rule, whether Adobe documents the constraint or it is inferred, the fix, and the Adobe skill pattern that can apply it.

4. **Verify each candidate in context.** Open the flagged files. Drop false positives (a match in a comment, test code or a vendored library) and say briefly why. Look around each real hit for related problems the scan cannot see. Use the "What to check" notes in the rule.

5. **Set the impact** for each finding, starting from the rule's default:
   - **Blocker**: stops the Cloud Manager pipeline, or the feature can't work on AEMaaCS.
   - **High**: must be fixed before go-live.
   - **Medium**: rework needed, timing flexible.
   - **Low**: advisory.

   Keep Adobe's own rule severity separate. Many Cloud Service compatibility rules are only `Minor` in Cloud Manager, so the pipeline passes code whose feature is gone. Report both.

6. **Check the deprecated-API deadline.** If rules AEMCS-011 to 013 have findings, state the dates from `rules.md` and how long the team has.

7. **Write the report** using the template below. Save it as `aem-migration-report.md` in the project root unless the user asks otherwise.

## Report template

```markdown
# AEM as a Cloud Service readiness assessment: <project name>

**Assessed:** <date> · **AEM baseline:** <version found in POMs> · **Modules:** <list>
**Basis:** code repository only. No running instance or BPA report was used.

## Summary
<3–5 sentences: overall readiness, the biggest risks, rough effort band (S/M/L/XL) with the reasoning.>

| Impact | Count |
| --- | --- |
| Blocker | n |
| High | n |
| Medium | n |
| Low | n |

## Deadlines
<Only if AEMCS-011–013 apply: which APIs, which date, what happens.>

## Findings
### [Blocker] AEMCS-019: <short title>
- **Where:** `path/to/file:line` (and N similar)
- **What we found:** <one or two sentences, quote the code if short>
- **Why it matters on Cloud Service:** <plain explanation>
- **Adobe rule:** <rule key, type, severity, or "none">
- **Evidence:** <Documented | Inferred, with one line on what is uncertain>
- **Fix:** <concrete steps>
- **Fix with:** <Adobe Cloud Migration skill pattern, Adobe tool, or "manual">
- **Effort:** <S/M/L>

<repeat, ordered Blocker → High → Medium → Low>

## Not assessed
<things that need a running instance or Adobe tooling: content repository size, users and groups, production indexes, integrations, BPA/CAM results. See "Not covered by the scanner" in rules.md.>

## Recommended next steps
<ordered list: quick wins, what to hand to Adobe's migration skill, what needs BPA on a real instance>
```

## Rules of engagement

- Never modify project files during an assessment.
- Quote file paths exactly. Group repeated findings (one entry, with "and N similar", plus a list in an appendix if long).
- Mark inferred claims as inferred. If something might be a problem depending on runtime behaviour, say so and say how to check (usually: test on the local Cloud SDK).
- Dates and rule severities come from `rules.md`, which records when it was last checked against Adobe's docs. If that date is more than a few months old, tell the user to re-check the linked pages.
- This assessment complements Adobe's Best Practices Analyzer, Cloud Acceleration Manager and AEM Cloud Migration skill. It doesn't replace them.
