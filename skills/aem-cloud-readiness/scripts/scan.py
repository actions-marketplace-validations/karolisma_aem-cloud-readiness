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
ASYNC_OK = {"[async]", "[async,nrt]", "[fulltext-async]"}


def imports(*prefixes):
    return re.compile(r"^\s*import\s+(static\s+)?(" + "|".join(re.escape(p) for p in prefixes) + r")")


JAVA_PATTERNS = [
    ("AEMCS-004", re.compile(r"\b(loginAdministrative|getAdministrativeResourceResolver|getAdministrativeSession)\s*\("),
     "Administrative login"),
    ("AEMCS-005", re.compile(r"\bcom\.day\.cq\.replication\.(Replicator|AgentManager|Agent|ReplicationQueue)\b"),
     "Classic replication API"),
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
    ("AEMCS-023", re.compile(r"Runtime\.getRuntime\(\)\.exec\s*\(|new\s+ProcessBuilder\s*\(|System\.loadLibrary\s*\("),
     "Native binary or process execution"),
]


def norm(path):
    return path.replace("\\", "/")


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            yield dirpath, name, os.path.join(dirpath, name)


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
    if "oak:QueryIndexDefinition" in text:
        scan_index_definitions(text, path, root, out)
    if 'jcr:primaryType="cq:Dialog"' in text or name in ("dialog.xml", "design_dialog.xml"):
        out.append(finding("AEMCS-009", path, root, detail="Classic UI dialog"))
    if "update_asset" in text or "update_asset" in p:
        if "/workflow" in p or "cq:WorkflowModel" in text or "cq:WorkflowLauncher" in text:
            out.append(finding("AEMCS-008", path, root, detail="DAM Update Asset workflow customisation"))
    if 'jcr:primaryType="cq:Template"' in text and "/jcr_root/apps/" in p:
        out.append(finding("AEMCS-021", path, root, detail="Static template under /apps"))
    if 'sling:resourceSuperType="foundation/components/' in text:
        out.append(finding("AEMCS-021", path, root, detail="Component extends a foundation component"))
    if re.search(r"reverseReplication=\"\{Boolean\}true\"|rev-agent|/var/replication/outbox", text):
        out.append(finding("AEMCS-022", path, root, detail="Reverse replication agent or outbox"))
    if name == "logback.xml":
        out.append(finding("AEMCS-020", path, root, detail="logback.xml"))
    if name == "pom.xml" and re.search(r"<artifactId>\s*uber-jar\s*</artifactId>", text):
        out.append(finding("AEMCS-014", path, root, detail="uber-jar dependency"))


def scan_osgi_file(path, root, out, dirpath, name):
    if not config_folder(dirpath):
        return
    if name.endswith((".config", ".cfg")):
        out.append(finding("AEMCS-002", path, root, detail=f"Superseded OSGi config format: {name}"))
    if "LogManager.factory.writer" in name:
        out.append(finding("AEMCS-020", path, root, detail="Custom log writer config"))
    elif "LogManager.factory.config" in name:
        m = re.search(r"org\.apache\.sling\.commons\.log\.file\"?\s*[:=]\s*\"?([^\"\s,}]+)", read(path))
        if m and m.group(1) != "logs/error.log":
            out.append(finding("AEMCS-020", path, root, detail=f"Custom log file: {m.group(1)}"))


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
            if "/src/test/" not in norm(path):
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


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root")
    ap.add_argument("--format", choices=["json", "text"], default="text")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        sys.exit(f"Not a directory: {root}")
    results = scan(root)
    if args.format == "json":
        counts = {}
        for r in results:
            counts[r["rule"]] = counts.get(r["rule"], 0) + 1
        json.dump({"root": root, "counts": counts, "findings": results}, sys.stdout, indent=2)
        print()
    else:
        if not results:
            print("No candidates found.")
        for r in sorted(results, key=lambda r: (r["rule"], r["file"], r["line"] or 0)):
            loc = f"{r['file']}:{r['line']}" if r["line"] else r["file"]
            print(f"{r['rule']}  {loc}  {r['detail']}")
        rules = len({r["rule"] for r in results})
        print(f"\n{len(results)} candidate(s) across {rules} rule(s). Verify each one against references/rules.md.")


if __name__ == "__main__":
    main()
