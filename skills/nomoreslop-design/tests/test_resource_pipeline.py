"""Fixture tests exercise receipt delivery, static closure and honest coverage states."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "resource_pipeline.py"
SPEC = importlib.util.spec_from_file_location("resource_pipeline", SCRIPT)
rp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rp)


def registry(files=None, **extra):
    return {"name": "fixture", "type": "registry:component", "files": files or [
        {"path": "Panel.tsx", "content": "export const Panel = () => 'fixture';"}
    ], **extra}


def response(data, content_type="application/json"):
    raw = json.dumps(data).encode() if not isinstance(data, bytes) else data
    return {"requested_url": "https://example.com/r/fixture.json", "canonical_url": "https://example.com/r/fixture.json",
            "checked_at": "2026-10-21T00:00:00Z", "status": 200, "content_type": content_type,
            "response_sha256": rp.digest(raw), "bytes": len(raw), "body": raw}


def selection_fixture():
    profile = {"origin": "derived", "basis": "Fixture brief: editorial image archive, browsing and comparison, web touch support",
               "tags": {"style": ["editorial"], "composition": ["image-led index"], "ux": ["compare collection"], "platform": ["web", "touch"]}}
    candidates = [{"id": "a", "url": "https://example.com/author/collection", "status": "considered"},
                  {"id": "b", "url": "https://example.com/author/alternate", "status": "considered"}]
    inspections = [{"candidate_id": cid, "evidence": ["fixture-source/" + cid],
                    "observations": {"style": "Caption hierarchy is compatible with the stated editorial archive",
                                     "composition": composition, "ux": "Selection stays visible with item details",
                                     "material": "Known six images fit without fabricated items", "feasibility": "Open web implementation has inspectable dependencies"},
                    "prior_use": {"status": "unknown"}} for cid, composition in (("a", "Simultaneous index with an adjacent detail"), ("b", "Sequential full-width inspection with return to the index"))]
    research = {"queries": [{"id": "q1", "source_url": "https://example.com/catalog", "channel": "api", "scope": "tag",
                             "query": "editorial archive comparison image-led", "tags": ["editorial", "compare collection"],
                             "status": "results", "result_ids": ["a", "b"], "evidence": ["fixture-response/search"]}],
                "inspections": inspections,
                "comparison": {"alternative_ids": ["b"], "choice_reason": "Index preserves simultaneous comparison under the current six-item brief",
                               "tradeoffs": "Sequential candidate gives larger individual images but loses simultaneous context",
                               "structure_difference": "Adjacent overview-detail versus sequential individual frames"},
                "closure": {"status": "compared"}}
    return profile, candidates, research


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
    def tearDown(self):
        self.temp.cleanup()
    def write(self, name, content):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target
    def receive(self, data=None, output="vendor/fixture"):
        with patch.object(rp, "retrieve", return_value=response(data or registry())):
            return rp.fetch_registry("https://example.com/r/fixture.json", self.root, output)
    def decision(self, status="own_implementation"):
        self.write("src/Panel.tsx", "export const Panel = () => 'fixture';")
        self.write("src/main.tsx", "import {Panel} from './Panel'; Panel();")
        digest = rp.digest((self.root / "src/Panel.tsx").read_bytes())
        profile, candidates, research = selection_fixture()
        return {"id": "overview", "section": "overview", "intent": "Browse the real collection",
                "state": "verified", "reason": "The requested native data format needs a custom binding after reviewing this source",
                "candidates": candidates, "research": research,
                "selection": {"status": status, "candidate_id": "a", "property": "Selection retains the active item while browsing"},
                "implementation": {"paths": ["src/Panel.tsx"], "entrypoints": ["src/main.tsx"]},
                "checks": [{"kind": "source_property", "status": "passed", "action": "Select one item, browse, return",
                            "observation": "The same selection remains visible", "evidence": ["evidence/selection.png"],
                            "environment": {"method": "browser-render", "viewport": [1280, 800]},
                            "files": {"src/Panel.tsx": digest}}]}
    def cover(self, decision):
        return rp.structural_coverage({"schema_version": 1, "mode": "new", "research_profile": selection_fixture()[0], "decisions": [decision]}, self.root)
    def codes(self, result):
        return {finding["code"] for finding in result["findings"]}

    def test_html_200_shell_is_not_source_and_fetch_writes_nothing(self):
        shell = response(b'<!doctype html><html><title>Library</title><div id="root"></div><script>bootstrap()</script></html>', "text/html")
        inspected, source = rp.inspect_response(shell)
        self.assertEqual(inspected["access"], "spa_shell")
        self.assertIsNone(source)
        with patch.object(rp, "retrieve", return_value=shell):
            fetched = rp.fetch_registry("https://example.com/mcp", self.root, "received")
        self.assertFalse(fetched["written"])
        self.assertFalse((self.root / "received").exists())

    def test_metadata_manifest_is_not_received_source(self):
        inspected, source = rp.inspect_response(response({"items": [{"name": "Pro Panel"}]}))
        self.assertEqual(inspected["access"], "metadata_only")
        self.assertIsNone(source)

    def test_challenge_and_auth_pages_do_not_report_source(self):
        for html, expected in [(b"<html><title>Just a moment</title><p>Checking your browser</p></html>", "challenge"),
                               (b'<html><title>Login</title><input type="password"></html>', "auth_required")]:
            inspected, source = rp.inspect_response(response(html, "text/html"))
            self.assertEqual(inspected["access"], expected)
            self.assertIsNone(source)

    def test_missing_dependency_metadata_and_local_helper_are_detected(self):
        result = self.receive(registry([{"path": "Panel.tsx", "content": 'import {motion} from "motion/react"; import {cn} from "@/lib/utils"; export {motion, cn};'}]))
        check = result["package_check"]
        self.assertEqual(check["dependency_declaration_gaps"], ["motion"])
        self.assertEqual(check["unresolved_local_imports"][0]["specifier"], "@/lib/utils")
        self.assertEqual(check["static_status"], "gaps")

    def test_transitive_helpers_and_asset_edges_are_scanned(self):
        self.write("src/main.ts", "import './Panel';")
        self.write("src/Panel.ts", "export {a} from './helpers';")
        self.write("src/helpers/index.ts", "export {a} from '../leaf';")
        self.write("src/leaf.ts", "export const a = 1;")
        check = rp.check_package(self.root)
        self.assertEqual(check["graph"]["src/Panel.ts"], ["src/helpers/index.ts"])
        self.assertEqual(check["graph"]["src/helpers/index.ts"], ["src/leaf.ts"])
        self.assertEqual(check["static_status"], "no_static_gaps_observed")

    def test_literal_assets_are_edges_and_navigation_links_are_not_packages(self):
        self.write("index.html", '<a href="?app">App</a><a href="/objects/42">Object</a><link rel="stylesheet" href="./src/theme.css"><script src="./src/main.ts"></script>')
        self.write("src/theme.css", "body {background:url('./image.svg')}")
        self.write("src/image.svg", '<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.write("src/main.ts", 'export const image = <img src="./image.svg"/>;')
        check = rp.check_package(self.root)
        self.assertEqual(set(check["graph"]["index.html"]), {"src/theme.css", "src/main.ts"})
        self.assertIn("src/image.svg", check["graph"]["src/theme.css"])
        self.assertEqual(check["static_status"], "no_static_gaps_observed")
        self.write("src/theme.css", "body {background:url('./missing.svg')}")
        self.assertIn("./missing.svg", [item["specifier"] for item in rp.check_package(self.root)["unresolved_local_imports"]])

    def test_unsafe_registry_paths_fail_before_writing(self):
        for bad in ("../escape.ts", "/absolute.ts", "C:/escape.ts", ".source", ".source/receipt.json", "CON.txt", "a/../bad.ts"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.receive(registry([{"path": bad, "content": "untrusted"}]), "new-output")
                self.assertFalse((self.root / "new-output").exists())

    def test_prefix_collision_and_case_duplicate_fail_before_write(self):
        for paths in (["a", "a/b.ts"], ["A.ts", "a.ts"]):
            with self.assertRaises(ValueError):
                self.receive(registry([{"path": name, "content": "untrusted"} for name in paths]), "output")
            self.assertFalse((self.root / "output").exists())

    def test_output_escape_and_overwrite_are_rejected_before_network(self):
        marker = self.write("existing/marker.txt", "preserve")
        with patch.object(rp, "retrieve") as network:
            for output in ("../outside", "existing"):
                with self.assertRaises(ValueError):
                    rp.fetch_registry("https://example.com/r/item.json", self.root, output)
            network.assert_not_called()
        self.assertEqual(marker.read_text(), "preserve")

    def test_received_integrity_and_adapted_changes_are_distinguished(self):
        result = self.receive()
        package = Path(result["output"])
        initial = rp.check_package(package)
        self.assertEqual(initial["receipt_integrity"]["status"], "consistent_received")
        self.assertEqual(initial["received_file_integrity"][0]["status"], "matches_received")
        (package / "Panel.tsx").write_text("export const Panel = () => 'adapted';", encoding="utf-8")
        changed = rp.check_package(package)
        self.assertEqual(changed["receipt_integrity"]["status"], "consistent_received")
        self.assertEqual(changed["received_file_integrity"][0]["status"], "changed_since_received")

    def test_cached_response_and_receipt_manifest_tampering_are_reported(self):
        package = Path(self.receive()["output"])
        cached = package / rp.RESPONSE
        cached.write_bytes(cached.read_bytes() + b" ")
        self.assertIn("cached_response_hash_mismatch", rp.check_package(package)["receipt_integrity"]["problems"])
        receipt = package / rp.RECEIPT
        value = json.loads(receipt.read_text())
        value["files"][0]["sha256"] = "0" * 64
        receipt.write_text(json.dumps(value), encoding="utf-8")
        self.assertIn("receipt_manifest_differs_from_cached_response", rp.check_package(package)["receipt_integrity"]["problems"])

    def test_downloaded_package_scripts_are_never_executed(self):
        marker = self.root / "executed.txt"
        payload = registry([{"path": "package.json", "content": json.dumps({"scripts": {"postinstall": "echo BAD > executed.txt"}})},
                            {"path": "Panel.ts", "content": "export const panel = 1;"}])
        self.receive(payload)
        self.assertFalse(marker.exists())

    def test_rejected_candidate_does_not_close_decision(self):
        decision = self.decision()
        decision["candidates"][0].update(status="rejected", reason="Wrong interaction", alternative="Inspect another catalog")
        decision.pop("selection")
        result = self.cover(decision)
        self.assertEqual(result["structural_status"], "gaps")
        self.assertIn("selection_status_missing", self.codes(result))

    def test_static_import_without_property_review_does_not_pass(self):
        decision = self.decision()
        decision["checks"] = []
        result = self.cover(decision)
        self.assertEqual(result["decisions"][0]["static_reachability"], "reachable_static")
        self.assertIn("property_review_missing", self.codes(result))

    def test_passed_word_and_stale_hashes_are_not_evidence(self):
        decision = self.decision()
        decision["checks"] = [{"kind": "source_property", "status": "passed"}]
        self.assertIn("passed_check_incomplete", self.codes(self.cover(decision)))
        decision = self.decision()
        self.write("src/Panel.tsx", "export const Panel = () => 'changed';")
        self.assertIn("property_review_missing", self.codes(self.cover(decision)))

    def test_dynamic_application_branch_stays_unknown(self):
        decision = self.decision()
        self.write("src/main.tsx", "const selected = './Panel'; import(selected);")
        result = self.cover(decision)
        self.assertEqual(result["decisions"][0]["static_reachability"], "unknown_edges")
        self.assertIn("dynamic_edges_unknown", self.codes(result))
        self.assertEqual(result["structural_status"], "gaps")

    def test_closed_own_branch_is_structural_only(self):
        result = self.cover(self.decision())
        self.assertEqual(result["structural_status"], "structurally_recorded")
        self.assertIn("self_reported", result["decisions"][0]["evidence_status"])
        self.assertIn("branches execute", result["limitation"])

    def test_unreachable_candidate_dependencies_do_not_block_current_branch(self):
        decision = self.decision()
        self.write("vendor/unselected.tsx", 'import "orphan-package";')
        self.assertIn("orphan-package", rp.check_package(self.root)["dependency_declaration_gaps"])
        self.assertEqual(self.cover(decision)["structural_status"], "structurally_recorded")
        self.write("src/Panel.tsx", 'import "orphan-package"; export const panel = 1;')
        self.assertIn("dependency_declarations_missing", self.codes(self.cover(decision)))

    def test_receipt_and_current_files_do_not_replace_selection_research(self):
        self.receive()
        decision = self.decision("adapted")
        decision["implementation"].update(receipt="vendor/fixture/.source/receipt.json", source_map={"Panel.tsx": "src/Panel.tsx"})
        del decision["research"]
        result = self.cover(decision)
        self.assertEqual(result["decisions"][0]["static_reachability"], "reachable_static")
        self.assertIn("research_missing", self.codes(result))

    def test_external_authorized_provenance_is_supported_and_freshness_checked(self):
        decision = self.decision("adapted")
        self.write("evidence/export.txt", "Captured authorized export response; reported by agent")
        decision["implementation"]["provenance"] = {
            "kind": "mcp", "source_url": "https://example.com/item", "evidence": ["evidence/export.txt"],
            "files": decision["checks"][0]["files"], "source_version": None}
        result = self.cover(decision)
        self.assertEqual(result["structural_status"], "structurally_recorded")
        self.assertEqual(result["decisions"][0]["provenance_status"], "external_self_reported")
        decision["implementation"]["provenance"]["evidence"] = ["../outside.txt"]
        self.assertIn("provenance_evidence_invalid", self.codes(self.cover(decision)))

    def test_unrelated_receipt_needs_explicit_adaptation_mapping(self):
        received = self.receive()
        decision = self.decision("adapted")
        decision["implementation"]["receipt"] = "vendor/fixture/.source/receipt.json"
        self.assertIn("source_map_missing", self.codes(self.cover(decision)))
        decision["implementation"]["source_map"] = {"Panel.tsx": "src/Panel.tsx"}
        self.assertEqual(self.cover(decision)["structural_status"], "structurally_recorded")

    def test_pending_check_and_selected_decision_do_not_close(self):
        decision = self.decision()
        decision["checks"].append({"kind": "visual", "status": "unverified", "reason": "Browser unavailable"})
        self.assertIn("check_pending", self.codes(self.cover(decision)))
        decision["state"] = "selected"
        self.assertIn("decision_open", self.codes(self.cover(decision)))

    def test_empty_scope_modes_and_explicit_directive(self):
        self.assertEqual(rp.structural_coverage({"schema_version": 1, "mode": "local", "decisions": []}, self.root)["structural_status"], "not_applicable")
        self.assertEqual(rp.structural_coverage({"schema_version": 1, "mode": "new", "decisions": []}, self.root)["structural_status"], "gaps")
        state = {"schema_version": 1, "mode": "new", "decisions": [], "resource_scope": {"status": "no_external_research", "reason": "User requested exact own design",
                 "basis": {"type": "prompt", "reference": "user message", "text": "Use only my supplied design"}}}
        self.assertEqual(rp.structural_coverage(state, self.root)["structural_status"], "not_applicable")

    def test_malformed_nested_entries_report_gaps_without_traceback(self):
        state = {"schema_version": 1, "mode": "new", "decisions": [None, {"id": [], "section": [], "intent": {}, "state": [],
                 "candidates": [None, {"id": [], "status": "rejected"}], "selection": [], "implementation": 42, "checks": [None]}]}
        result = rp.structural_coverage(state, self.root)
        self.assertEqual(result["structural_status"], "gaps")
        self.assertIn("decision_invalid", self.codes(result))
        self.assertIn("candidate_identity", self.codes(result))

    def test_local_cli_gap_exit_is_nonzero_and_json(self):
        self.write("src/main.ts", 'import "missing-package";')
        with patch("sys.argv", ["resource_pipeline.py", "check-package", str(self.root)]), redirect_stdout(io.StringIO()) as output:
            code = rp.main()
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["dependency_declaration_gaps"], ["missing-package"])

    def test_public_url_rejects_credentials_and_private_hosts_without_network(self):
        for url in ("http://example.com/item", "https://user:secret@example.com/item", "https://127.0.0.1/item",
                    "https://example.com/item?token=secret", "https://example.local/item", "https://example.com:444/item"):
            with self.assertRaises(ValueError):
                rp.public_url(url, resolve_dns=False)

    def test_all_saved_sources_remain_and_no_mcp_is_declared_connected(self):
        sources = rp.source_list()
        self.assertEqual(sources["count"], 37)
        self.assertEqual(len({item["id"] for item in sources["sources"]}), 37)
        self.assertEqual(rp.source_list(source_id="awwwards")["count"], 1)
        self.assertIn("not connected", sources["note"])


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.profile, self.candidates, research = selection_fixture()
        self.decision = {"selection": {"candidate_id": "a"}, "research": research}
    def review(self):
        return rp.selection_review(self.profile, self.decision, {item["id"]: item for item in self.candidates})
    def codes(self):
        return {item["code"] for item in self.review()["findings"]}
    def test_task_tag_search_and_inspected_structural_alternative_close(self):
        self.assertEqual(self.review()["status"], "comparison_recorded")
    def test_two_homepages_do_not_close_selection(self):
        query = self.decision["research"]["queries"][0]
        query.update(scope="homepage", tags=[])
        second = copy.deepcopy(query); second.update(id="q2", source_url="https://another.example/")
        self.decision["research"]["queries"].append(second)
        self.assertIn("research_tag_search_missing", self.codes())
    def test_derived_tags_and_planned_queries_are_not_execution(self):
        self.decision["research"]["queries"][0]["status"] = "planned"
        self.assertIn("research_tag_search_missing", self.codes())
        self.assertIn("research_winner_not_discovered", self.codes())
    def test_exact_familiar_name_queries_are_not_task_discovery(self):
        self.decision["research"]["queries"][0].update(scope="exact_item", query="magnetic dock")
        self.assertIn("research_tag_search_missing", self.codes())
    def test_query_tags_must_refer_to_the_current_project_profile(self):
        self.decision["research"]["queries"][0]["tags"] = ["trending", "popular widgets"]
        self.assertIn("research_query_tags_unlinked", self.codes())
        self.assertIn("research_tag_search_missing", self.codes())
    def test_first_working_candidate_still_requires_an_alternative(self):
        self.decision["research"]["comparison"]["alternative_ids"] = []
        self.assertIn("research_alternative_missing", self.codes())
    def test_same_structure_color_variants_are_not_a_declared_alternative(self):
        for candidate in self.candidates:
            candidate["cosmetic_variant_of"] = "author/collection/color-only"
        self.assertIn("research_structure_not_distinct", self.codes())
    def test_same_layout_with_materially_different_ux_is_a_valid_comparison(self):
        first, second = self.decision["research"]["inspections"]
        first["observations"]["composition"] = second["observations"]["composition"] = "Search field in existing header"
        first["observations"]["ux"] = "Arrow keys select inline suggestions"
        second["observations"]["ux"] = "Enter opens keyboard-navigable results dialog"
        self.decision["research"]["comparison"]["structure_difference"] = "Shared header placement, inline suggestion flow versus a separate results dialog"
        self.assertEqual(self.review()["status"], "comparison_recorded")
    def test_other_project_cache_must_requalify_and_is_not_current_basis(self):
        self.decision["research"]["inspections"][0]["prior_use"] = {"status": "other_project", "reference": "Old brand component"}
        self.assertIn("research_reuse_basis_missing", self.codes())
        self.decision["research"]["closure"] = {"status": "current_project_basis", "basis": {"type": "project", "reference": "approved layout", "text": "Use the approved system"}}
        self.assertIn("research_current_project_mismatch", self.codes())
    def test_exact_user_reference_has_a_scoped_single_candidate_route(self):
        research = self.decision["research"]
        research["queries"] = []; research["inspections"] = research["inspections"][:1]
        research["closure"] = {"status": "exact_user_reference", "basis": {"type": "prompt", "reference": "User request", "text": "Use exactly the linked collection component"}}
        self.assertEqual(self.review()["status"], "scoped_basis_recorded")
        research["closure"]["basis"]["type"] = "project"
        self.assertIn("research_exception_basis_missing", self.codes())
    def test_current_product_basis_does_not_require_a_new_style_search(self):
        research = self.decision["research"]
        research["queries"] = []; research["inspections"] = research["inspections"][:1]
        research["inspections"][0]["prior_use"] = {"status": "same_project", "reference": "src/current/Collection.tsx"}
        research["closure"] = {"status": "current_project_basis", "basis": {"type": "project", "reference": "approved current interface", "text": "Existing collection and tokens are approved for this product"}}
        self.assertEqual(self.review()["status"], "scoped_basis_recorded")
    def test_blocked_access_stays_unresolved(self):
        self.decision["research"]["queries"][0].update(status="blocked", result_ids=[])
        self.decision["research"]["closure"] = {"status": "unresolved", "reason": "Provider returned access denied; next public author route remains unavailable"}
        self.assertIn("research_unresolved", self.codes())
    def test_inspection_needs_style_composition_ux_material_and_feasibility(self):
        del self.decision["research"]["inspections"][0]["observations"]["ux"]
        self.assertIn("research_fit_missing", self.codes())
    def test_missing_profile_and_bad_refinement_remain_explicit(self):
        self.profile = None
        self.decision["research"]["queries"][0]["refines"] = "not-previous"
        self.assertIn("research_profile_missing", self.codes())
        self.assertIn("research_query_refinement", self.codes())
    def test_malformed_research_does_not_crash(self):
        self.decision["research"] = {"queries": [None, {"id": [], "result_ids": [{}]}], "inspections": [None, {"candidate_id": []}], "comparison": [], "closure": []}
        self.assertEqual(self.review()["status"], "gaps")
    def test_malformed_nested_statuses_produce_findings_not_tracebacks(self):
        self.profile["origin"] = []
        self.decision["research"]["closure"]["status"] = []
        self.decision["research"]["inspections"][0]["prior_use"]["status"] = []
        self.decision["research"]["queries"][0].update(scope=[], status={}, channel=[])
        self.assertEqual(self.review()["status"], "gaps")


if __name__ == "__main__":
    unittest.main()
