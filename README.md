# AEM Cloud Readiness Assessment for Claude

**A Claude Agent Skill that assesses an AEM 6.5 codebase for AEM as a Cloud Service from the Git repository alone.** It needs no running AEM instance and no BPA report.

It answers the questions that come *before* a migration starts:

- What in this codebase will fail or need rework on Cloud Service?
- Which findings will stop the Cloud Manager pipeline, and which will pass the quality step but break in production?
- Which API removals have a deadline?
- How much effort is this, and what should be fixed first?

> Status: **v0.2.** 24 rules, checked against Adobe's documentation in November 2026. Feedback and issues are welcome.

## Where it fits

| Step | Tool |
| --- | --- |
| **1. Assess from the repo** (pre-sales, estimates, first look) | **This skill** |
| 2. Analyse a running instance | Adobe Best Practices Analyzer, Cloud Acceleration Manager |
| 3. Fix the code, pattern by pattern | Adobe's [AEM Cloud Migration skill](https://experienceleague.adobe.com/en/docs/experience-manager-cloud-service/content/migration-journey/cloud-migration-skill/using-cloud-migration-skill), Dispatcher Converter, AEM Modernization Tools |

Each finding names the Adobe skill pattern or tool that can fix it, where one exists.

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
| Packages and config | Mixed mutable/immutable packages · superseded OSGi formats · unsupported run modes · content under `/libs` · uber-jar · Java version · custom log files |
| Java code | Admin logins · replication API and agents · reverse replication · filesystem writes · removed and soon-removed APIs · HTTP clients without timeouts · Sling scheduler · native processes |
| Content and authoring | Oak index naming and blocking properties · DAM Update Asset customisations · Classic UI dialogs · static templates and foundation components |
| Dispatcher | Cloud layout · legacy vs flexible mode |

## Use it with Claude Code

```bash
git clone https://github.com/karolisma/aem-cloud-readiness.git
mkdir -p ~/.claude/skills
cp -r aem-cloud-readiness/skills/* ~/.claude/skills/
```

Then, in your AEM project:

```
claude "Assess this project's readiness for AEM as a Cloud Service"
```

You can also run the scanner on its own:

```bash
python3 skills/aem-cloud-readiness/scripts/scan.py /path/to/aem-project
```

## Try it on the test fixture

```bash
python3 skills/aem-cloud-readiness/scripts/scan.py tests/fixtures/legacy-65-project
```

The fixture is a tiny synthetic AEM 6.5 project with at least one example of each rule.

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
