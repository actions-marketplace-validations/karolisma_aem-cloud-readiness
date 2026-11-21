# AEM Cloud Readiness Assessment

**Find out what in an AEM 6.5 codebase will break on AEM as a Cloud Service, from the Git repository alone.** It needs no running AEM instance and no BPA report.

[![Tests](https://github.com/karolisma/aem-cloud-readiness/actions/workflows/tests.yml/badge.svg)](https://github.com/karolisma/aem-cloud-readiness/actions/workflows/tests.yml)

## Two ways to use it

| | What you get | Needs |
| --- | --- | --- |
| **[GitHub Action](#use-it-in-ci-github-action)** | A quick check on every pull request: structure and configuration blockers and deprecated API use, marked on the affected lines. No build needed, so it also works on legacy 6.x code. | A GitHub workflow. Nothing else. |
| **[Claude skill](#install-in-claude-code)** | A full assessment: every candidate read in context, an impact per finding, an effort estimate and a fix plan. | Claude Code |

Both run the same scanner and the same 28 rules. The quickest start is the action:

```yaml
- uses: actions/checkout@v4
- uses: karolisma/aem-cloud-readiness@v0.4.3
  with:
    rules: deprecated-apis
    fail-on: deadline
```

> Status: **v0.4.3.** 28 rules, checked against Adobe's documentation in November 2026. Feedback and issues are welcome.

## What it answers

The questions that come *before* a migration starts:

- What in this codebase will fail or need rework on Cloud Service?
- Which findings will stop the Cloud Manager pipeline, and which will pass the quality step but break in production?
- Which API removals have a deadline?
- How much effort is this, and what should be fixed first?

## Where it fits

Adobe ships its own tools for this work, and for some jobs they are the better choice. Use the right one:

| Your situation | Use |
| --- | --- |
| A legacy 6.x codebase that doesn't build against the Cloud SDK yet, and you need a first look, an estimate or a pre-sales assessment | **This project** |
| Project structure and configuration: mixed packages, run modes, OSGi config formats, index naming, Dispatcher layout, custom logs | **This project** |
| A quick check on pull requests, with no build and no setup | **This project** (the GitHub Action) |
| Deprecated and removed APIs in a project that already builds against `aem-sdk-api` | Adobe's `aemanalyser-maven-plugin`, which is the same check Cloud Manager runs, and the [`code-assessment`](https://github.com/adobe/skills/tree/main/plugins/aem/cloud-service/skills/code-assessment) skill, which reads its rules from that plugin and fixes the code |
| Code quality in a Cloud Service project: `@Inject` in Sling Models, outdated dependencies, HTTP timeouts, unbounded queries | Adobe's `code-assessment` skill |
| A running instance: content, users, production indexes | Adobe Best Practices Analyzer, Cloud Acceleration Manager |
| Fixing the code, pattern by pattern | Adobe's [AEM Cloud Migration skill](https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/migration-journey/cloud-migration-skill/using-cloud-migration-skill), Dispatcher Converter, AEM Modernization Tools |

On deprecated APIs, Adobe's analyser is the authority. This project's API rules are a list compiled from Adobe's documentation and matched against imports. That is useful where the analyser can't run yet, and as an early signal on a pull request. It is not a substitute once your build includes the analyser.

The two overlap less than the names suggest. Run on the same two public projects in November 2026, Adobe's `code-assessment` scanner (v1.0.1, without its deprecated-API step, which needs a Maven build) and this scanner reported different things:

| Project | Adobe's `code-assessment` scanner | This scanner |
| --- | --- | --- |
| We.Retail (legacy 6.x) | 6 findings: `@Inject` in Sling Models, an outdated dependency, a query index | 38 candidates, 10 verified findings: packaging, build setup, removed libraries, logging, configuration |
| WKND (Cloud Service) | 9 findings: query indexes, outdated dependencies | 1 candidate, dismissed |

Each finding in a report names the Adobe skill pattern or tool that can fix it, where one exists, and the report ends with a fix plan: ready-to-run prompts for Adobe's skill, with the pattern and file paths filled in.

Tried on a real 6.5 codebase: the assessment flagged a JCR observation listener, and Adobe's skill (plugin `aem-cloud-service` 1.3.1, manual flow) migrated it from the file path alone, moving the heavy work into a Sling Job. It offered three approaches, and picking one took someone who knew the project. That review is the part no tool does for you.

## How it works

1. **A fast, deterministic scan** (`scripts/scan.py`, standard-library Python) finds *candidates*.
2. **Claude verifies each candidate in context** against the [rule catalogue](skills/aem-cloud-readiness/references/rules.md): it drops false positives, sets the impact and proposes fixes.
3. **You get a report** (`aem-migration-report.md`) with a summary, deadlines, an effort band and ordered findings.

Each rule records:

- **Impact:** what breaks in practice.
- **Adobe rule:** the Cloud Manager quality rule and its severity. Most Cloud Service compatibility rules are only `Minor`, so the pipeline passes code whose feature is gone. The report shows both.
- **Evidence:** whether Adobe documents the constraint or it is inferred.

## What it checks

| Area | Rules |
| --- | --- |
| Packages and config | Mixed mutable/immutable packages · superseded OSGi formats · unsupported run modes · content under `/libs` · uber-jar · Java version · custom log files · purge configs · mail service |
| Java code | Admin logins · replication API and agents · reverse replication · filesystem writes · removed and soon-removed APIs · HTTP clients without timeouts · Sling scheduler · JCR observation listeners · run-mode checks · native processes |
| Content and authoring | Oak index naming and blocking properties · DAM Update Asset customisations · Classic UI dialogs · static templates and foundation components |
| Dispatcher | Cloud layout · legacy vs flexible mode |

## Install in Claude Code

Inside Claude Code, run these two commands, one at a time:

```
/plugin marketplace add karolisma/aem-cloud-readiness
/plugin install aem-cloud-readiness@aem-cloud-readiness
```

On Claude Code 2.1.275 or later, one line does both:

```
/plugin install aem-cloud-readiness --marketplace karolisma/aem-cloud-readiness
```

Then, in your AEM project:

```
Assess this project's readiness for AEM as a Cloud Service
```

To fix what it finds, install Adobe's skill next to it and follow the fix plan in the report:

```
/plugin marketplace add adobe/skills
/plugin install aem-cloud-service@adobe-skills
```

### Without the plugin system

Copy the skill folder by hand:

```bash
git clone https://github.com/karolisma/aem-cloud-readiness.git
mkdir -p ~/.claude/skills
cp -r aem-cloud-readiness/skills/* ~/.claude/skills/
```

Or run the scanner on its own. It needs only Python 3 and has no dependencies:

```bash
python3 skills/aem-cloud-readiness/scripts/scan.py /path/to/aem-project
```

## Use it in CI: GitHub Action

The scanner also runs as a GitHub Action, with no Claude involved. It takes seconds, needs no build, and works on projects that don't compile against the Cloud SDK yet.

Adobe removes another set of deprecated APIs on 31 March 2027. Cloud Manager pipelines that use them pause at Code Quality from December 2026 and fail from January 2027. This workflow gives an early signal on a pull request that adds such code:

```yaml
name: AEM readiness
on: [pull_request]

jobs:
  readiness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: karolisma/aem-cloud-readiness@v0.4.3
        with:
          rules: deprecated-apis
          fail-on: deadline
```

Findings show up as annotations on the changed files and as a table in the job summary.

| Input | Default | Meaning |
| --- | --- | --- |
| `path` | `.` | Folder of the AEM project, relative to the repository root. |
| `rules` | `any` | What to report: `any`, rule ids such as `AEMCS-011,AEMCS-012`, or a group. |
| `fail-on` | `none` | What fails the job: `none`, `any`, rule ids, or a group. |

Groups: `deadline` is APIs already removed plus the 31 March 2027 batch (AEMCS-011, AEMCS-012). `deprecated-apis` adds the December 2027 batch (AEMCS-013).

Outputs: `candidates` and `failing`, the two counts.

Start with the default `fail-on: none` to see what a project has, then tighten. The scanner matches patterns and does not understand code, so a hit is a candidate to read, not a verdict.

If your Maven build already runs `aemanalyser-maven-plugin`, as projects from the current AEM Project Archetype do, that plugin is the authoritative check for deprecated APIs, and this action adds little on that point. It earns its place on legacy codebases, on repositories without the analyser, and for the structure and configuration rules the analyser doesn't cover.

## Try it on the test fixture

```bash
python3 skills/aem-cloud-readiness/scripts/scan.py tests/fixtures/legacy-65-project
```

The fixture is a tiny synthetic AEM 6.5 project with at least one example of each rule.

Run the tests:

```bash
python3 -m unittest discover -s tests -v
```

They check the scanner against the fixture and against small cases for each known false positive. GitHub Actions runs them on every push.

## Example reports

Two reports on public Adobe projects, so you can see the output before you run anything:

- [We.Retail](examples/we-retail-report.md): Adobe's archived AEM 6.x reference site. 38 scanner candidates became 10 verified findings, 3 of them blockers, plus a fix plan.
- [WKND](examples/wknd-report.md): Adobe's current reference site, built for Cloud Service. The control case: 1 candidate, dismissed with the reason, nothing to fix.

## Scope and honesty

- The assessment is **read-only**. It never changes your code.
- Scanner signals are heuristics. Claude verifies them, and you should too.
- Rules were checked against Adobe's documentation on 15 November 2026. Adobe changes the platform often, so check the linked pages before you rely on a date or severity.
- A repo-only assessment can't see content size, users, production indexes or integrations. Run BPA on a real instance for those.
- The API rules are a list taken from Adobe's documentation. Adobe's `aemanalyser-maven-plugin` is the source of truth, so prefer it wherever your build can run it.
- Not affiliated with or endorsed by Adobe or Anthropic.

## Author

Built by **Karolis Mackevicius**, Senior AEM Developer and Tech Lead with 12+ years of enterprise AEM work.
[karolis.pro](https://karolis.pro) · [LinkedIn](https://www.linkedin.com/in/karolis-mackevicius/)

## License

[Apache License 2.0](LICENSE)
