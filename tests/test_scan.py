"""Tests for the readiness scanner. Standard library only.

Run from the repository root:
    python3 -m unittest discover -s tests -v
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_PY = os.path.join(REPO, "skills", "aem-cloud-readiness", "scripts", "scan.py")
FIXTURE = os.path.join(REPO, "tests", "fixtures", "legacy-65-project")
RULES_MD = os.path.join(REPO, "skills", "aem-cloud-readiness", "references", "rules.md")

spec = importlib.util.spec_from_file_location("scan", SCAN_PY)
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)

ALL_RULES = {f"AEMCS-{n:03d}" for n in range(1, 29)}


def write(root, relpath, text):
    path = os.path.join(root, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def rules_found(root):
    return [f["rule"] for f in scan.scan(root)]


class FixtureTest(unittest.TestCase):
    """The synthetic 6.5 project has at least one example of every rule."""

    @classmethod
    def setUpClass(cls):
        cls.findings = scan.scan(FIXTURE)

    def test_every_rule_fires(self):
        self.assertEqual({f["rule"] for f in self.findings}, ALL_RULES)

    def test_candidate_count_is_stable(self):
        self.assertEqual(len(self.findings), 37)

    def test_findings_have_relative_paths(self):
        for f in self.findings:
            self.assertFalse(os.path.isabs(f["file"]), f)
            self.assertNotIn("\\", f["file"])

    def test_every_rule_is_documented(self):
        with open(RULES_MD, encoding="utf-8") as fh:
            text = fh.read()
        for rule in ALL_RULES:
            self.assertIn(f"## {rule}:", text)


class JavaRulesTest(unittest.TestCase):
    JAVA = "package x;\nimport com.google.common.collect.ImmutableMap;\nclass A {}\n"

    def test_removed_api_in_main_code_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "core/src/main/java/x/A.java", self.JAVA)
            self.assertEqual(rules_found(root), ["AEMCS-011"])

    def test_unit_tests_are_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "core/src/test/java/x/A.java", self.JAVA)
            self.assertEqual(rules_found(root), [])

    def test_test_client_modules_are_skipped(self):
        for module in ("it.tests", "ui.tests", "it.tests.ui-js"):
            with tempfile.TemporaryDirectory() as root:
                write(root, f"{module}/src/main/java/x/A.java", self.JAVA)
                self.assertEqual(rules_found(root), [], module)

    def test_module_with_similar_name_is_not_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "it.testsuite/src/main/java/x/A.java", self.JAVA)
            self.assertEqual(rules_found(root), ["AEMCS-011"])

    def test_comment_lines_are_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "core/src/main/java/x/A.java",
                  "package x;\n// import com.google.common.collect.ImmutableMap;\nclass A {}\n")
            self.assertEqual(rules_found(root), [])

    def test_process_execution_split_over_lines(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "core/src/main/java/x/A.java",
                  "class A { void run() throws Exception {\n"
                  "  Runtime runtime = Runtime.getRuntime();\n"
                  "  runtime.exec(\"convert\");\n}}\n")
            self.assertIn("AEMCS-023", rules_found(root))

    def test_custom_replication_agent_code(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "core/src/main/java/x/A.java",
                  "import com.day.cq.replication.TransportHandler;\nclass A {}\n")
            self.assertIn("AEMCS-005", rules_found(root))


POM = "<project><dependencies>{deps}</dependencies>{profiles}</project>"
UBER = "<dependency><groupId>com.adobe.aem</groupId><artifactId>uber-jar</artifactId></dependency>"
SDK = "<dependency><groupId>com.adobe.aem</groupId><artifactId>aem-sdk-api</artifactId></dependency>"


class UberJarTest(unittest.TestCase):
    def check(self, pom):
        with tempfile.TemporaryDirectory() as root:
            write(root, "core/pom.xml", pom)
            return rules_found(root)

    def test_plain_uber_jar_is_flagged(self):
        self.assertEqual(self.check(POM.format(deps=UBER, profiles="")), ["AEMCS-014"])

    def test_uber_jar_in_optional_profile_next_to_sdk_is_not_flagged(self):
        profiles = (f"<profiles><profile><id>cloudservice</id><dependencies>{SDK}</dependencies></profile>"
                    f"<profile><id>classic</id><dependencies>{UBER}</dependencies></profile></profiles>")
        self.assertEqual(self.check(POM.format(deps="", profiles=profiles)), [])

    def test_uber_jar_in_profile_without_sdk_is_flagged(self):
        profiles = f"<profiles><profile><id>classic</id><dependencies>{UBER}</dependencies></profile></profiles>"
        self.assertEqual(self.check(POM.format(deps="", profiles=profiles)), ["AEMCS-014"])

    def test_uber_jar_outside_profiles_is_flagged_even_with_sdk(self):
        profiles = f"<profiles><profile><id>cloudservice</id><dependencies>{SDK}</dependencies></profile></profiles>"
        self.assertEqual(self.check(POM.format(deps=UBER, profiles=profiles)), ["AEMCS-014"])


INDEX = ('<?xml version="1.0" encoding="UTF-8"?>\n'
         '<jcr:root xmlns:jcr="http://www.jcp.org/jcr/1.0" xmlns:oak="http://jackrabbit.apache.org/oak/ns/1.0"\n'
         '    jcr:primaryType="oak:QueryIndexDefinition" type="{type}" async="{asy}"/>\n')


class IndexTest(unittest.TestCase):
    def check(self, name, **attrs):
        with tempfile.TemporaryDirectory() as root:
            write(root, f"ui.apps/src/main/content/jcr_root/_oak_index/{name}/.content.xml", INDEX.format(**attrs))
            return rules_found(root)

    def test_well_formed_custom_index_is_clean(self):
        self.assertEqual(self.check("acme.product-1-custom-1", type="lucene", asy="[async,nrt]"), [])

    def test_single_value_async_is_accepted(self):
        self.assertEqual(self.check("acme.product-1-custom-1", type="lucene", asy="async"), [])

    def test_property_index_blocks(self):
        self.assertEqual(self.check("acme.product-1-custom-1", type="property", asy="[async]"), ["AEMCS-019"])

    def test_bad_name_is_flagged(self):
        self.assertEqual(self.check("productIndex", type="lucene", asy="[async]"), ["AEMCS-006"])


class PackageAndConfigTest(unittest.TestCase):
    def test_mixed_package(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "ui.apps/src/main/content/META-INF/vault/filter.xml",
                  '<workspaceFilter><filter root="/apps/x"/><filter root="/content/x"/></workspaceFilter>')
            self.assertEqual(rules_found(root), ["AEMCS-001"])

    def test_apps_with_oak_index_is_not_mixed(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "ui.apps/src/main/content/META-INF/vault/filter.xml",
                  '<workspaceFilter><filter root="/apps/x"/><filter root="/oak:index/x-1-custom-1"/></workspaceFilter>')
            self.assertEqual(rules_found(root), [])

    def test_run_modes(self):
        base = "ui.config/src/main/content/jcr_root/apps/x/osgiconfig/"
        with tempfile.TemporaryDirectory() as root:
            for folder in ("config.author", "config.publish.prod", "config.rde", "config.uat", "config.dev.author"):
                write(root, f"{base}{folder}/a.cfg.json", "{}")
            details = sorted(f["detail"] for f in scan.scan(root) if f["rule"] == "AEMCS-003")
            self.assertEqual(details, ["Unsupported run mode folder: config.dev.author",
                                       "Unsupported run mode folder: config.uat"])

    def test_custom_log_file_in_cfg_json(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "ui.config/src/main/content/jcr_root/apps/x/osgiconfig/config/"
                        "org.apache.sling.commons.log.LogManager.factory.config~x.cfg.json",
                  '{"org.apache.sling.commons.log.file": "logs/x.log"}')
            self.assertEqual(rules_found(root), ["AEMCS-020"])

    def test_java_version(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "pom.xml", "<project/>")
            self.assertEqual(rules_found(root), ["AEMCS-015"])
            write(root, ".cloudmanager/java-version", "21\n")
            self.assertEqual(rules_found(root), [])
            write(root, ".cloudmanager/java-version", "11\n")
            self.assertEqual(rules_found(root), ["AEMCS-015"])


class CommandLineTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCAN_PY, *args], capture_output=True, text=True)

    def test_json_output(self):
        result = self.run_cli(FIXTURE, "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(sum(data["counts"].values()), len(data["findings"]))
        self.assertEqual(set(data["counts"]), ALL_RULES)

    def test_text_output_summary(self):
        result = self.run_cli(FIXTURE)
        self.assertIn("37 candidate(s) across 28 rule(s)", result.stdout)

    def test_clean_project(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.run_cli(root)
            self.assertEqual(result.returncode, 0)
            self.assertIn("No candidates found.", result.stdout)

    def test_missing_directory_fails(self):
        result = self.run_cli(os.path.join(REPO, "does-not-exist"))
        self.assertNotEqual(result.returncode, 0)


class PluginManifestTest(unittest.TestCase):
    def test_marketplace_points_at_the_skill(self):
        with open(os.path.join(REPO, ".claude-plugin", "marketplace.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        plugin = data["plugins"][0]
        skill_dir = os.path.normpath(os.path.join(REPO, plugin["source"]))
        self.assertTrue(os.path.isfile(os.path.join(skill_dir, "SKILL.md")))
        self.assertEqual(plugin["version"], data["metadata"]["version"])


if __name__ == "__main__":
    unittest.main()
