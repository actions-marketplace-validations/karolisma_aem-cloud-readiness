#!/usr/bin/env python3
"""Fast candidate scan for AEM 6.x -> AEM as a Cloud Service blockers.

Flags *candidates* only; the audit skill verifies each one in context
against references/rules.md. Every signal here is a heuristic.
Usage: python3 scan.py <project-root> [--format json|text]
Standard library only.
"""
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

SKIP_DIRS = {".git", "node_modules", "target", ".idea", ".vscode", "dist", "build"}
# /oak:index is deliberately absent: index definitions ship with the code package.
MUTABLE_ROOTS = ("/content", "/conf", "/etc", "/var", "/home", "/system", "/tmp")
SERVICES = ("author", "publish")
ENVS = ("dev", "rde", "stage", "prod")
ALLOWED_RUNMODES = set(SERVICES) | set(ENVS) | {f"{s}.{e}" for s in SERVICES for e in ENVS}

INDEX_NAME_OK = re.compile(r"-\d+-custom-\d+$")
# FileVault writes a single-value property without brackets, so accept both forms.
ASYNC_OK = {"[async]", "[async,nrt]", "[fulltext-async]", "async", "fulltext-async"}
# Test-client modules (archetype names it.tests, ui.tests and variants) run outside AEM
# and are never deployed, so the runtime API rules don't apply to their Java code.
TEST_MODULE = re.compile(r"^(it|ui)\.tests(\..+)?$")
PROFILES_BLOCK = re.compile(r"<profiles>.*?</profiles>", re.S)
UBER_JAR = re.compile(r"<artifactId>\s*uber-jar\s*</artifactId>")


RULE_TITLES = {
    "AEMCS-001": "Mutable and immutable content in one package",
    "AEMCS-002": "OSGi configuration in a superseded format",
    "AEMCS-003": "Unsupported run modes",
    "AEMCS-004": "Administrative sessions and resource resolvers",
    "AEMCS-005": "Replication agents and the Replication API",
    "AEMCS-006": "Custom Oak index naming and placement",
    "AEMCS-007": "Writing to the local filesystem",
    "AEMCS-008": "Customised DAM Update Asset workflow",
    "AEMCS-009": "Classic UI dialogs",
    "AEMCS-010": "Dispatcher configuration not in Cloud Service format",
    "AEMCS-011": "API packages already removed",
    "AEMCS-012": "APIs removed on 31 March 2027",
    "AEMCS-013": "APIs removed on 31 December 2027 (tentative)",
    "AEMCS-014": "Uber-jar dependency",
    "AEMCS-015": "Java version for the build",
    "AEMCS-016": "HTTP clients without timeouts",
    "AEMCS-017": "Sling Commons Scheduler",
    "AEMCS-018": "Content under /libs",
    "AEMCS-019": "Index properties that block the pipeline",
    "AEMCS-020": "Custom log files and logging frameworks",
    "AEMCS-021": "Static templates and foundation components",
    "AEMCS-022": "Reverse replication",
    "AEMCS-023": "Native binaries and process execution",
    "AEMCS-024": "Dispatcher in legacy mode",
    "AEMCS-025": "JCR observation listeners",
    "AEMCS-026": "Purge and maintenance as OSGi config",
    "AEMCS-027": "Mail service configuration",
    "AEMCS-028": "Run-mode checks in code",
}
# Named groups for --rules and --fail-on. "deadline" = API use that already breaks the build
# or stops deploying when Adobe removes the 31 March 2027 batch.
RULE_GROUPS = {
    "deadline": ("AEMCS-011", "AEMCS-012"),
    "deprecated-apis": ("AEMCS-011", "AEMCS-012", "AEMCS-013"),
}
RULES_URL = "https://github.com/karolisma/aem-cloud-readiness/blob/main/skills/aem-cloud-readiness/references/rules.md"


def imports(*prefixes):
    return re.compile(r"^\s*import\s+(static\s+)?(" + "|".join(re.escape(p) for p in prefixes) + r")")


JAVA_PATTERNS = [
    ("AEMCS-004", re.compile(r"\b(loginAdministrative|getAdministrativeResourceResolver|getAdministrativeSession)\s*\("),
     "Administrative login"),
    ("AEMCS-005", re.compile(r"\bcom\.day\.cq\.replication\.(Replicator|AgentManager|Agent|AgentConfig|ReplicationQueue)\b"),
     "Classic replication API"),
    ("AEMCS-005", re.compile(r"\bcom\.day\.cq\.replication\.(TransportHandler|ContentBuilder|ReplicationContent)\b"),
     "Custom replication agent code"),
    ("AEMCS-007", re.compile(r"new\s+(FileOutputStream|FileWriter)\s*\(|Files\.(write|newOutputStream|newBufferedWriter)\s*\(|File\.createTempFile\s*\("),
     "Local filesystem write"),
    ("AEMCS-011", imports("com.google.common.", "org.apache.abdera.", "com.mongodb.", "ch.qos.logback.",
                          "org.apache.log4j.", "org.apache.felix.scr.", "org.apache.felix.webconsole.",
                          "org.eclipse.jetty.", "com.day.crx."),
     "API package already removed"),
    ("AEMCS-012", imports("org.bson.", "com.github.jknack.handlebars.", "com.day.cq.xss.",
                          "com.day.cq.wcm.commons.utils.", "org.apache.tika.", "org.apache.commons.fileupload.",
                          "opennlp.tools.", "com.day.cq.commons.predicate."),
     "API removed 31 Mar 2027"),
    ("AEMCS-013", imports("org.apache.commons.lang.", "org.apache.commons.collections.", "org.json.",
                          "org.apache.sling.commons.json.", "com.adobe.granite.xss.", "org.osgi.service.http.",
                          "org.apache.sling.runmode."),
     "API removed 31 Dec 2027 (tentative)"),
    ("AEMCS-016", re.compile(r"HttpClients\.createDefault\s*\(|HttpClientBuilder\.create\s*\(\s*\)\s*\.build\s*\("),
     "HTTP client without explicit timeouts"),
    ("AEMCS-017", re.compile(r"org\.apache\.sling\.commons\.scheduler\.|scheduler\.expression"),
     "Sling Commons Scheduler"),
    ("AEMCS-028", re.compile(r"\bgetRunModes\s*\("), "Run-mode check in code"),
    ("AEMCS-025", imports("javax.jcr.observation."), "JCR observation listener"),
    ("AEMCS-023", re.compile(r"Runtime\.getRuntime\s*\(|new\s+ProcessBuilder\s*\(|System\.loadLibrary\s*\("),
     "Native binary or process execution"),
]


def norm(path):
    return path.replace("\\", "/")


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            yield dirpath, name, os.path.join(dirpath, name)


def in_test_code(path, root):
    parts = norm(os.path.relpath(path, root)).split("/")
    return "/src/test/" in norm(path) or any(TEST_MODULE.match(part) for part in parts[:-1])


def finding(rule, path, root, line=None, detail=""):
    return {"rule": rule, "file": norm(os.path.relpath(path, root)), "line": line, "detail": detail}


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def scan_java(path, root, out):
    for i, text in enumerate(read(path).splitlines(), 1):
        stripped = text.strip()
        if stripped.startswith(("//", "*", "/*")):
            continue
        for rule, pat, label in JAVA_PATTERNS:
            if pat.search(text):
                out.append(finding(rule, path, root, i, f"{label}: {stripped[:160]}"))


def scan_filter(path, root, out):
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError):
        return
    roots = [f.get("root", "") for f in tree.getroot().iter("filter")]
    has_apps = any(r == "/apps" or r.startswith("/apps/") for r in roots)
    mutable = [r for r in roots if r.startswith(MUTABLE_ROOTS)]
    if has_apps and mutable:
        out.append(finding("AEMCS-001", path, root, detail=f"/apps mixed with {', '.join(mutable[:5])}"))
    for r in roots:
        if r == "/libs" or r.startswith("/libs/"):
            out.append(finding("AEMCS-018", path, root, detail=f"Filter root under /libs: {r}"))
        if r.startswith("/etc/replication"):
            out.append(finding("AEMCS-005", path, root, detail=f"Replication agent config root: {r}"))


def config_folder(dirpath):
    base = os.path.basename(dirpath)
    return base if base == "config" or base.startswith("config.") else None


def scan_index_definitions(text, path, root, out):
    for m in re.finditer(r"<([\w.\-:]+)\b([^>]*jcr:primaryType=\"oak:QueryIndexDefinition\"[^>]*)>", text, re.S):
        name, attrs = m.group(1), m.group(2)
        if name == "jcr:root":
            name = os.path.basename(os.path.dirname(path))
        if not INDEX_NAME_OK.search(name):
            out.append(finding("AEMCS-006", path, root,
                               detail=f"Index name lacks -<productVersion>-custom-<n>: {name}"))
        typ = re.search(r"\btype=\"([^\"]*)\"", attrs)
        if not typ or typ.group(1) != "lucene":
            out.append(finding("AEMCS-019", path, root,
                               detail=f"Index {name}: type is {typ.group(1) if typ else 'missing'}, not lucene"))
        asy = re.search(r"\basync=\"([^\"]*)\"", attrs)
        if not asy or asy.group(1).replace(" ", "") not in ASYNC_OK:
            out.append(finding("AEMCS-019", path, root,
                               detail=f"Index {name}: async is {asy.group(1) if asy else 'missing'}"))


def scan_xml(path, root, out, dirpath, name):
    text = read(path)
    p = norm(path)
    if "sling:OsgiConfig" in text and config_folder(dirpath):
        out.append(finding("AEMCS-002", path, root, detail="OSGi config as sling:OsgiConfig node"))
        scan_osgi_pid(path, root, out, name, text)
    if "oak:QueryIndexDefinition" in text:
        scan_index_definitions(text, path, root, out)
    if 'jcr:primaryType="cq:Dialog"' in text or name in ("dialog.xml", "design_dialog.xml"):
        out.append(finding("AEMCS-009", path, root, detail="Classic UI dialog"))
    if "update_asset" in text or "update_asset" in p:
        if "/workflow" in p or "cq:WorkflowModel" in text or "cq:WorkflowLauncher" in text:
            steps = sorted({m.rsplit(".", 1)[-1] for m in re.findall(r'PROCESS="([^"]+)"', text)})
            detail = "DAM Update Asset workflow customisation"
            if steps:
                detail += ". Steps: " + ", ".join(steps)
            out.append(finding("AEMCS-008", path, root, detail=detail))
    if 'jcr:primaryType="cq:Template"' in text and "/jcr_root/apps/" in p:
        out.append(finding("AEMCS-021", path, root, detail="Static template under /apps"))
    if 'sling:resourceSuperType="foundation/components/' in text:
        out.append(finding("AEMCS-021", path, root, detail="Component extends a foundation component"))
    if re.search(r"reverseReplication=\"\{Boolean\}true\"|rev-agent|/var/replication/outbox", text):
        out.append(finding("AEMCS-022", path, root, detail="Reverse replication agent or outbox"))
    if name == "logback.xml":
        out.append(finding("AEMCS-020", path, root, detail="logback.xml"))
    if name == "pom.xml" and UBER_JAR.search(text):
        # A project built for both targets keeps uber-jar in an optional profile next to
        # aem-sdk-api. That is by design, so only flag uber-jar outside profiles, or with no SDK.
        outside_profiles = UBER_JAR.search(PROFILES_BLOCK.sub("", text))
        if outside_profiles or "aem-sdk-api" not in text:
            out.append(finding("AEMCS-014", path, root, detail="uber-jar dependency"))


LOG_FILE = re.compile(r"org\.apache\.sling\.commons\.log\.file\"?\s*[:=]\s*\"?([^\"\s,}]+)")
PURGE_PIDS = ("com.day.cq.wcm.core.impl.VersionPurgeTask", "com.adobe.granite.workflow.purge.Scheduler",
              "com.adobe.cq.audit.purge.")


def scan_osgi_pid(path, root, out, name, text):
    """Checks keyed on the OSGi PID in the file name, whatever the config format."""
    if "LogManager.factory.writer" in name:
        out.append(finding("AEMCS-020", path, root, detail="Custom log writer config"))
    elif "LogManager.factory.config" in name:
        m = LOG_FILE.search(text)
        if m and m.group(1) != "logs/error.log":
            out.append(finding("AEMCS-020", path, root, detail=f"Custom log file: {m.group(1)}"))
    elif name.startswith("org.apache.sling.commons.log.LogManager."):
        out.append(finding("AEMCS-020", path, root, detail="Global LogManager config"))
    if name.startswith(PURGE_PIDS):
        out.append(finding("AEMCS-026", path, root, detail="Purge or maintenance config as OSGi config"))
    if name.startswith("com.day.cq.mailer.DefaultMailService"):
        out.append(finding("AEMCS-027", path, root, detail="Mail service config"))


def scan_osgi_file(path, root, out, dirpath, name):
    if not config_folder(dirpath):
        return
    if name.endswith((".config", ".cfg")):
        out.append(finding("AEMCS-002", path, root, detail=f"Superseded OSGi config format: {name}"))
    scan_osgi_pid(path, root, out, name, read(path))


def scan_dirs(root, out):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        base = os.path.basename(dirpath)
        p = norm(dirpath) + "/"
        if base.startswith("config.") and "/jcr_root/" in p:
            mode = base[len("config."):]
            if mode not in ALLOWED_RUNMODES:
                out.append(finding("AEMCS-003", dirpath, root, detail=f"Unsupported run mode folder: {base}"))
        if p.endswith("/jcr_root/libs/"):
            out.append(finding("AEMCS-018", dirpath, root, detail="Content under /libs"))
        if "dispatcher.any" in filenames and base != "conf.dispatcher.d":
            out.append(finding("AEMCS-010", os.path.join(dirpath, "dispatcher.any"), root,
                               detail="Customer-written dispatcher.any outside conf.dispatcher.d"))
        src = os.path.join(dirpath, "src")
        cloud_layout = os.path.isdir(os.path.join(src, "conf.d")) and os.path.isdir(os.path.join(src, "conf.dispatcher.d"))
        if cloud_layout:
            if not os.path.isfile(os.path.join(src, "opt-in", "USE_SOURCES_DIRECTLY")):
                out.append(finding("AEMCS-024", dirpath, root,
                                   detail="Dispatcher in legacy mode: no opt-in/USE_SOURCES_DIRECTLY"))
        elif base == "dispatcher" and "pom.xml" in filenames:
            out.append(finding("AEMCS-010", dirpath, root,
                               detail="Dispatcher module lacks src/conf.d + src/conf.dispatcher.d layout"))


def scan_java_version(root, out):
    if not os.path.isfile(os.path.join(root, "pom.xml")):
        return
    path = os.path.join(root, ".cloudmanager", "java-version")
    if not os.path.isfile(path):
        out.append(finding("AEMCS-015", root, root, detail="No .cloudmanager/java-version file"))
    elif read(path).strip() not in ("17", "21"):
        out.append(finding("AEMCS-015", path, root, detail=f"java-version is {read(path).strip()!r}, expected 17 or 21"))


def scan(root):
    out = []
    for dirpath, name, path in walk(root):
        if name.endswith(".java"):
            if not in_test_code(path, root):
                scan_java(path, root, out)
        elif name == "filter.xml" and "META-INF" in path:
            scan_filter(path, root, out)
        elif name.endswith(".xml"):
            scan_xml(path, root, out, dirpath, name)
        else:
            scan_osgi_file(path, root, out, dirpath, name)
    scan_dirs(root, out)
    scan_java_version(root, out)
    return out


def parse_rules(value, option):
    """Turn 'AEMCS-011, deadline' into a set of rule ids. 'any' = every rule, 'none' or '' = no rule."""
    value = (value or "").strip()
    if value.lower() in ("", "none"):
        return set()
    if value.lower() in ("any", "all"):
        return set(RULE_TITLES)
    rules = set()
    for item in re.split(r"[,\s]+", value):
        if not item:
            continue
        if item.lower() in RULE_GROUPS:
            rules.update(RULE_GROUPS[item.lower()])
        elif item.upper() in RULE_TITLES:
            rules.add(item.upper())
        else:
            sys.exit(f"{option}: unknown rule or group '{item}'. Use rule ids such as AEMCS-012, "
                     f"or one of: any, none, {', '.join(sorted(RULE_GROUPS))}.")
    return rules


def gh_escape(text, prop=False):
    text = str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return text.replace(":", "%3A").replace(",", "%2C") if prop else text


def github_report(results, failing, prefix):
    """Annotations on stdout, a summary table in the job summary, counts in the step outputs."""
    prefix = norm(prefix).strip("/")
    prefix = "" if prefix in ("", ".") else prefix + "/"
    ordered = sorted(results, key=lambda r: (r["rule"] not in failing, r["rule"], r["file"], r["line"] or 0))
    for r in ordered:
        level = "error" if r["rule"] in failing else "warning"
        props = [f"file={gh_escape(prefix + r['file'], True)}"]
        if r["line"]:
            props.append(f"line={r['line']}")
        props.append(f"title={gh_escape(r['rule'] + ': ' + RULE_TITLES[r['rule']], True)}")
        print(f"::{level} {','.join(props)}::{gh_escape(r['detail'] or RULE_TITLES[r['rule']])}")

    counts = {}
    for r in results:
        counts[r["rule"]] = counts.get(r["rule"], 0) + 1
    n_fail = sum(1 for r in results if r["rule"] in failing)
    lines = ["## AEM Cloud Service readiness", ""]
    if not results:
        lines.append("No candidates found.")
    else:
        lines += [f"{len(results)} candidate(s) across {len(counts)} rule(s)."
                  + (f" **{n_fail} fail this check.**" if n_fail else ""), "",
                  "| Rule | What | Candidates | Fails the check |", "| --- | --- | --- | --- |"]
        for rule in sorted(counts, key=lambda k: (k not in failing, k)):
            anchor = (rule + "-" + re.sub(r"[^a-z0-9 -]", "", RULE_TITLES[rule].lower()).replace(" ", "-")).lower()
            lines.append(f"| [{rule}]({RULES_URL}#{anchor}) | {RULE_TITLES[rule]} | {counts[rule]} | "
                         f"{'yes' if rule in failing else 'no'} |")
        lines += ["", "<details><summary>All candidates</summary>", "", "| Rule | Location | Detail |", "| --- | --- | --- |"]
        for r in ordered[:200]:
            loc = f"{prefix}{r['file']}" + (f":{r['line']}" if r["line"] else "")
            detail = (r["detail"] or "").replace("|", "\\|")
            lines.append(f"| {r['rule']} | `{loc}` | {detail} |")
        if len(ordered) > 200:
            lines.append(f"| | | ... and {len(ordered) - 200} more |")
        lines += ["", "</details>", "",
                  "These are candidates found by pattern matching. Read each one in context before treating it as a "
                  f"finding: [rule catalogue]({RULES_URL})."]
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"candidates={len(results)}\nfailing={n_fail}\n")
    print(f"{len(results)} candidate(s) across {len(counts)} rule(s); {n_fail} fail this check.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root")
    ap.add_argument("--format", choices=["json", "text", "github"], default="text")
    ap.add_argument("--max-per-rule", type=int, default=10, help="text output: lines shown per rule")
    ap.add_argument("--rules", default="any",
                    help="rules to report: 'any', rule ids (AEMCS-012,AEMCS-014) or a group (deadline, deprecated-apis)")
    ap.add_argument("--fail-on", default="none",
                    help="exit with status 1 when one of these rules has a candidate: 'none', 'any', rule ids or a group")
    ap.add_argument("--path-prefix", default="",
                    help="github output: path of ROOT inside the repository, so annotations land on the right files")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        sys.exit(f"Not a directory: {root}")
    wanted = parse_rules(args.rules, "--rules")
    failing = parse_rules(args.fail_on, "--fail-on")
    results = [r for r in scan(root) if r["rule"] in wanted]
    failed = any(r["rule"] in failing for r in results)
    if args.format == "github":
        github_report(results, failing, args.path_prefix)
    elif args.format == "json":
        counts = {}
        for r in results:
            counts[r["rule"]] = counts.get(r["rule"], 0) + 1
        json.dump({"root": root, "counts": counts, "findings": results}, sys.stdout, indent=2)
        print()
    else:
        if not results:
            print("No candidates found.")
        shown = {}
        for r in sorted(results, key=lambda r: (r["rule"], r["file"], r["line"] or 0)):
            shown[r["rule"]] = shown.get(r["rule"], 0) + 1
            if shown[r["rule"]] > args.max_per_rule:
                continue
            loc = f"{r['file']}:{r['line']}" if r["line"] else r["file"]
            print(f"{r['rule']}  {loc}  {r['detail']}")
        for rule, n in sorted(shown.items()):
            if n > args.max_per_rule:
                print(f"{rule}  ... and {n - args.max_per_rule} more (use --format json for all)")
        rules = len({r["rule"] for r in results})
        print(f"\n{len(results)} candidate(s) across {rules} rule(s). Verify each one against references/rules.md.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
