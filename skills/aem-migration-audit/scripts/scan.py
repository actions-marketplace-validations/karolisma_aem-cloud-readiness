#!/usr/bin/env python3
"""Fast candidate scan for AEM 6.x -> AEM as a Cloud Service blockers.

Flags *candidates* only; the audit skill verifies each one in context.
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
MUTABLE_ROOTS = ("/content", "/conf", "/etc", "/var", "/home", "/oak:index")
IMMUTABLE_ROOTS = ("/apps", "/libs")
ALLOWED_RUNMODES = {
    "author", "publish", "dev", "stage", "prod",
    "author.dev", "author.stage", "author.prod",
    "publish.dev", "publish.stage", "publish.prod",
}

JAVA_PATTERNS = [
    ("AEMCS-004", re.compile(r"\b(loginAdministrative|getAdministrativeResourceResolver|getAdministrativeSession)\s*\("),
     "Administrative login"),
    ("AEMCS-005", re.compile(r"\bcom\.day\.cq\.replication\.(Replicator|AgentManager|Agent|ReplicationQueue)\b"),
     "Classic replication API"),
    ("AEMCS-007", re.compile(r"new\s+(FileOutputStream|FileWriter)\s*\(|Files\.(write|newOutputStream|newBufferedWriter)\s*\(|File\.createTempFile\s*\("),
     "Local filesystem write"),
]


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            yield dirpath, name, os.path.join(dirpath, name)


def rel(path, root):
    return os.path.relpath(path, root)


def finding(rule, path, root, line=None, detail=""):
    return {"rule": rule, "file": rel(path, root), "line": line, "detail": detail}


def scan_java(path, root, out):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for i, text in enumerate(fh, 1):
                stripped = text.strip()
                if stripped.startswith(("//", "*", "/*")):
                    continue
                for rule, pat, label in JAVA_PATTERNS:
                    if pat.search(text):
                        out.append(finding(rule, path, root, i, f"{label}: {stripped[:160]}"))
    except OSError:
        pass


def scan_filter(path, root, out):
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError):
        return
    roots = [f.get("root", "") for f in tree.getroot().iter("filter")]
    has_imm = any(r.startswith(IMMUTABLE_ROOTS) for r in roots)
    has_mut = [r for r in roots if r.startswith(MUTABLE_ROOTS)]
    if has_imm and has_mut:
        out.append(finding("AEMCS-001", path, root, detail=f"Mixed roots: /apps|/libs with {', '.join(has_mut[:5])}"))
    for r in roots:
        if r.startswith("/etc/replication"):
            out.append(finding("AEMCS-005", path, root, detail=f"Replication agent config root: {r}"))


def config_folder(dirpath):
    base = os.path.basename(dirpath)
    if base == "config" or base.startswith("config."):
        return base
    return None


def scan_xml(path, root, out, dirpath, name):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return
    if "sling:OsgiConfig" in text and config_folder(dirpath):
        out.append(finding("AEMCS-002", path, root, detail="OSGi config as sling:OsgiConfig node"))
    if "oak:QueryIndexDefinition" in text:
        names = re.findall(r"<([\w.\-:]+)[^>]*jcr:primaryType=\"oak:QueryIndexDefinition\"", text)
        bad = [n for n in names if not re.search(r"-custom-\d+$", n)]
        detail = "Oak index definition(s)"
        if names:
            detail += f": {', '.join(names[:5])}"
        if bad or not names:
            out.append(finding("AEMCS-006", path, root, detail=detail))
    if 'jcr:primaryType="cq:Dialog"' in text or name in ("dialog.xml", "design_dialog.xml"):
        out.append(finding("AEMCS-009", path, root, detail="Classic UI dialog"))
    if "dam/update_asset" in text or "update_asset" in path.replace("\\", "/"):
        if "/workflow" in path.replace("\\", "/") or "cq:WorkflowModel" in text or "cq:WorkflowLauncher" in text:
            out.append(finding("AEMCS-008", path, root, detail="DAM Update Asset workflow customisation"))


def scan_runmodes(root, out):
    seen = set()
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        base = os.path.basename(dirpath)
        if base.startswith("config.") and "/jcr_root/" in dirpath.replace("\\", "/") + "/":
            mode = base[len("config."):]
            if mode not in ALLOWED_RUNMODES and dirpath not in seen:
                seen.add(dirpath)
                out.append(finding("AEMCS-003", dirpath, root, detail=f"Unsupported run mode folder: {base}"))


def scan_legacy_osgi_files(path, root, out, dirpath, name):
    if config_folder(dirpath) and (name.endswith(".config") or name.endswith(".cfg")):
        out.append(finding("AEMCS-002", path, root, detail=f"Legacy OSGi config file: {name}"))


def scan_dispatcher(root, out):
    candidates = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if "dispatcher.any" in filenames:
            out.append(finding("AEMCS-010", os.path.join(dirpath, "dispatcher.any"), root,
                               detail="Legacy single dispatcher.any file"))
        if os.path.basename(dirpath) == "dispatcher" and "pom.xml" in filenames:
            candidates.append(dirpath)
    for d in candidates:
        src = os.path.join(d, "src")
        if not (os.path.isdir(os.path.join(src, "conf.d")) and os.path.isdir(os.path.join(src, "conf.dispatcher.d"))):
            out.append(finding("AEMCS-010", d, root, detail="Dispatcher module lacks src/conf.d + src/conf.dispatcher.d layout"))


def scan(root):
    out = []
    for dirpath, name, path in walk(root):
        if name.endswith(".java") and "/src/test/" not in path.replace("\\", "/"):
            scan_java(path, root, out)
        elif name == "filter.xml" and "META-INF" in path:
            scan_filter(path, root, out)
        elif name.endswith(".xml"):
            scan_xml(path, root, out, dirpath, name)
        else:
            scan_legacy_osgi_files(path, root, out, dirpath, name)
    scan_runmodes(root, out)
    scan_dispatcher(root, out)
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
        for r in sorted(results, key=lambda r: (r["rule"], r["file"])):
            loc = f"{r['file']}:{r['line']}" if r["line"] else r["file"]
            print(f"{r['rule']}  {loc}  {r['detail']}")
        print(f"\n{len(results)} candidate(s). Verify each one against references/rules.md.")


if __name__ == "__main__":
    main()
