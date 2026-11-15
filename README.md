# AEM Cloud Migration Skills for Claude

**Claude Agent Skills that help AEM teams move from AEM 6.5 to AEM as a Cloud Service.**

Adobe's Best Practices Analyzer and Cloud Acceleration Manager tell you *what* is wrong. These skills let Claude **read your codebase, explain each blocker in context, and help you fix it**, the way a senior AEM tech lead would during a migration assessment.

> Status: **v0.1, early.** The audit skill and its first 10 rules work. Restructuring and Dispatcher skills are next. Feedback and issues are welcome.

## Skills

| Skill | What it does | Status |
| --- | --- | --- |
| [`aem-migration-audit`](skills/aem-migration-audit/) | Scans an AEM 6.x Maven project for Cloud Service blockers and writes a prioritised report with fixes | ✅ v0.1 |
| `aem-repo-restructure` | Guides the split into `ui.apps` / `ui.content` / `ui.config` and converts OSGi configs to `.cfg.json` | 🔜 planned |
| `aem-dispatcher-check` | Validates Dispatcher config against the Cloud Service layout and explains each error | 🔜 planned |

## How it works

1. **A fast, deterministic scan** (`scripts/scan.py`, standard-library Python) finds *candidates*: admin sessions, mixed mutable/immutable packages, custom run modes, legacy OSGi configs and more.
2. **Claude verifies each candidate in context** against the [blocker catalogue](skills/aem-migration-audit/references/rules.md): it drops false positives, assigns severity and proposes concrete fixes.
3. **You get a report** (`aem-migration-report.md`) with a summary, an effort band and an ordered list of findings.

Current rules: mutable content in code packages · legacy OSGi config formats · custom run modes · administrative logins · replication agents · custom Oak indexes · local filesystem writes · DAM Update Asset customisations · Classic UI dialogs · legacy Dispatcher layout.

## Use it with Claude Code

```bash
git clone https://github.com/karolisma/aem-cloud-migration-skills.git
mkdir -p ~/.claude/skills
cp -r aem-cloud-migration-skills/skills/* ~/.claude/skills/
```

Then, in your AEM project:

```
claude "Audit this project for AEM as a Cloud Service migration blockers"
```

You can also run the scanner on its own:

```bash
python3 skills/aem-migration-audit/scripts/scan.py /path/to/aem-project
```

## Try it on the test fixture

```bash
python3 skills/aem-migration-audit/scripts/scan.py tests/fixtures/legacy-65-project
```

The fixture is a tiny synthetic AEM 6.5 project with one example of each rule.

## Scope and honesty

- These skills **complement** Adobe's own tools (Best Practices Analyzer, Cloud Acceleration Manager, the AEM Modernization Tools, the Dispatcher Converter). They don't replace them.
- The audit is **read-only**. It never changes your code.
- Rules are written from hands-on migration experience. Always check against Adobe's current AEM as a Cloud Service documentation.
- Not affiliated with or endorsed by Adobe or Anthropic.

## Author

Built by **Karolis Mackevicius**, Senior AEM Developer and Tech Lead with 12+ years of enterprise AEM work.
[karolis.pro](https://karolis.pro) · [LinkedIn](https://www.linkedin.com/in/karolis-mackevicius/)

## License

[Apache License 2.0](LICENSE)
