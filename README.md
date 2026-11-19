# AEM Cloud Readiness Assessment for Claude

**A Claude Agent Skill that assesses an AEM 6.5 codebase for AEM as a Cloud Service from the Git repository alone.** It needs no running AEM instance and no BPA report.

It answers the questions that come *before* a migration starts:

- What in this codebase will fail or need rework on Cloud Service?
- Which findings will stop the Cloud Manager pipeline, and which will pass the quality step but break in production?
- Which API removals have a deadline?
- How much effort is this, and what should be fixed first?

[![Tests](https://github.com/karolisma/aem-cloud-readiness/actions/workflows/tests.yml/badge.svg)](https://github.com/karolisma/aem-cloud-readiness/actions/workflows/tests.yml)

> Status: **v0.4.** 28 rules, checked against Adobe's documentation in November 2026. Feedback and issues are welcome.

## Where it fits

| Step | Tool |
| --- | --- |
| **1. Assess from the repo** (pre-sales, estimates, first look) | **This skill** |
| 2. Analyse a running instance | Adobe Best Practices Analyzer, Cloud Acceleration Manager |
| 3. Fix the code, pattern by pattern | Adobe's [AEM Cloud Migration skill](https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/migration-journey/cloud-migration-skill/using-cloud-migration-skill), Dispatcher Converter, AEM Modernization Tools |

Each finding names the Adobe skill pattern or tool that can fix it, where one exists, and the report ends with a fix plan: ready-to-run prompts for Adobe's skill, with the pattern and file paths filled in.

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

The scanner also runs as a GitHub Action, with no Claude involved. Use it to catch deprecated API use in pull requests before Adobe's removal date does it for you.

Adobe removes another set of deprecated APIs on 31 March 2027. Cloud Manager pipelines that use them pause at Code Quality from December 2026 and fail from January 2027. This workflow fails a pull request that adds such code:

```yaml
name: AEM readiness
on: [pull_request]

jobs:
  readiness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: karolisma/aem-cloud-readiness@v0.4.0
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

Start with the default `fail-on: none` to see what a project has, then tighten. The scanner matches patterns and does not understand code, so a hit is a candidate to read, not a verdict. The API rules are the most reliable ones, because an import either is on Adobe's list or isn't.

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
- Not affiliated with or endorsed by Adobe or Anthropic.

## Author

Built by **Karolis Mackevicius**, Senior AEM Developer and Tech Lead with 12+ years of enterprise AEM work.
[karolis.pro](https://karolis.pro) · [LinkedIn](https://www.linkedin.com/in/karolis-mackevicius/)

## License

[Apache License 2.0](LICENSE)
