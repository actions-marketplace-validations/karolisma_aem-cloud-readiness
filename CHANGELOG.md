# Changelog

## v0.4.0 (19 November 2026)

- The scanner runs as a GitHub Action: annotations on the affected lines, a job summary, and an optional failing check.
- `--rules` and `--fail-on` select rules by id or by group (`deadline`, `deprecated-apis`).
- `--format github` and `--path-prefix` for use in CI.
- 42 automated tests. CI runs the action against the test project.

## v0.3 (16 November 2026)

- Installs as a Claude Code plugin with `/plugin marketplace add karolisma/aem-cloud-readiness`.
- Fewer false positives: Java in test-client modules (`it.tests`, `ui.tests`) is skipped, and an uber-jar kept in an optional Maven profile next to `aem-sdk-api` is no longer flagged.
- Sample reports on two public Adobe projects, We.Retail and WKND.
- First automated tests and a GitHub Actions workflow.

## v0.2 (15 November 2026)

- Rule catalogue rewritten after checking every rule against Adobe's documentation: 28 rules, each with impact, Adobe's own rule and severity, and an evidence level.
- Repositioned as a readiness assessment that hands fixes to Adobe's AEM Cloud Migration skill.
- Scanner fixes from a run on a real codebase: custom replication agents, process execution split over lines, custom log files in XML configurations, and a false positive on single-value `async`.

## v0.1 (November 2026)

- First version: migration rules, a Python scanner and a synthetic AEM 6.5 test project.
