# AEM as a Cloud Service readiness assessment: WKND Sites Project

**Assessed:** 16 November 2026 · **AEM baseline:** `aem-sdk-api` 2026.8.27830 (default profile), `uber-jar` 6.6.0 (optional `classic` profile) · **Modules:** `core`, `ui.apps`, `ui.apps.structure`, `ui.config`, `ui.content`, `ui.content.sample`, `ui.frontend`, `dispatcher`, `it.tests`, `ui.tests`, `all`
**Source:** [adobe/aem-guides-wknd](https://github.com/adobe/aem-guides-wknd) at commit `503c333` (15 October 2026), MIT licence
**Basis:** code repository only. No running instance or BPA report was used.

> This is a sample report. WKND is Adobe's reference project and is built for Cloud Service, so it is the control case: a readiness check should find nothing to fix here. For a project with real findings, see the [We.Retail report](we-retail-report.md).

## Summary

WKND is ready for AEM as a Cloud Service, as expected. The scanner raised 1 candidate. It was checked by hand and dismissed, with the reason below. No effort is needed.

| Impact | Count |
| --- | --- |
| Blocker | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |

## Deadlines

None apply. No code in a deployed module imports an API from Adobe's removal lists.

## Findings

None.

## Candidates checked and dismissed

The scanner only flags candidates. This one shows why each is read in context before it becomes a finding.

### AEMCS-009: Classic UI dialog
- **Where:** `ui.apps/src/main/content/jcr_root/apps/msm/wknd_blueprint/_jcr_content/dialog.xml`
- **What it is:** a `cq:Dialog` node with three `cqinclude` widgets that point to `/libs/wcm/msm/templates/blueprint/defaults/`.
- **Why it is dismissed:** this is not a component dialog. It is part of a Multi Site Manager blueprint configuration, and it has the structure the product itself writes when a blueprint configuration is created. No author edits content through it.
- **Evidence:** Inferred. Adobe's docs don't describe this node. If Best Practices Analyzer reports it under "Legacy UI" on a real instance, treat that the same way.

## Fix plan

Nothing to hand to Adobe's AEM Cloud Migration skill.

## Not assessed

Things that need a running instance or Adobe tooling: content repository size, users and groups, production indexes, integrations, and BPA or Cloud Acceleration Manager results. Front-end code in `ui.frontend` and the UI tests were not reviewed.

## Notes on the scanner

An earlier run of this project raised two more candidates, both false: an unused import in the `it.tests` client module, and an `uber-jar` dependency that sits in the optional `classic` Maven profile next to `aem-sdk-api`. The scanner was changed in v0.3 so that neither is flagged, and both cases are now covered by tests.
