# AEM as a Cloud Service readiness assessment: WKND Sites Project

**Assessed:** 16 November 2026 · **AEM baseline:** `aem-sdk-api` 2026.8.27830 (default profile), `uber-jar` 6.6.0 (optional `classic` profile) · **Modules:** `core`, `ui.apps`, `ui.apps.structure`, `ui.config`, `ui.content`, `ui.content.sample`, `ui.frontend`, `dispatcher`, `it.tests`, `ui.tests`, `all`
**Source:** [adobe/aem-guides-wknd](https://github.com/adobe/aem-guides-wknd) at commit `503c333` (15 October 2026), MIT licence
**Basis:** code repository only. No running instance or BPA report was used.

> This is a sample report. WKND is Adobe's reference project and is built for Cloud Service, so it is the control case: a readiness check should find nothing to fix here. For a project with real findings, see the [We.Retail report](we-retail-report.md).

## Summary

WKND is ready for AEM as a Cloud Service, as expected. The scanner raised 3 candidates across 3 rules. All 3 were checked by hand and dismissed, with the reasons below. No effort is needed.

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

The scanner only flags candidates. These three show why each one is read in context before it becomes a finding.

### AEMCS-009: Classic UI dialog
- **Where:** `ui.apps/src/main/content/jcr_root/apps/msm/wknd_blueprint/_jcr_content/dialog.xml`
- **What it is:** a `cq:Dialog` node with three `cqinclude` widgets that point to `/libs/wcm/msm/templates/blueprint/defaults/`.
- **Why it is dismissed:** this is not a component dialog. It is part of a Multi Site Manager blueprint configuration, and it has the structure the product itself writes when a blueprint configuration is created. No author edits content through it.
- **Evidence:** Inferred. Adobe's docs don't describe this node. If Best Practices Analyzer reports it under "Legacy UI" on a real instance, treat that the same way.

### AEMCS-011: API package already removed
- **Where:** `it.tests/src/main/java/com/adobe/aem/guides/wknd/it/tests/PublishPageValidationIT.java:29`
- **What it is:** `import org.eclipse.jetty.client.HttpResponse;`
- **Why it is dismissed:** two reasons. The `it.tests` module is an integration-test client that runs outside AEM and is never deployed, so the API regions of the AEM runtime don't apply to it. And the import is unused: the class only uses `org.apache.http.HttpResponse` and `SlingHttpResponse`.
- **Optional tidy-up:** delete the unused import.

### AEMCS-014: Uber-jar dependency
- **Where:** `core/pom.xml`
- **What it is:** a `com.adobe.aem:uber-jar` dependency.
- **Why it is dismissed:** it sits inside the optional `classic` Maven profile, which exists so the same code can also be built for AEM 6.5. The `cloudservice` profile is active by default and uses `aem-sdk-api`.

## Fix plan

Nothing to hand to Adobe's AEM Cloud Migration skill.

## Not assessed

Things that need a running instance or Adobe tooling: content repository size, users and groups, production indexes, integrations, and BPA or Cloud Acceleration Manager results. Front-end code in `ui.frontend` and the UI tests were not reviewed.

## Notes on the scanner

This run shows two places where the scanner could be stricter, so that a clean project gives a clean scan:

- Skip Java API rules in test-client modules such as `it.tests` and `ui.tests`.
- Don't flag `uber-jar` when it is declared only in a non-default profile next to `aem-sdk-api`.
