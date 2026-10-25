"""Tests for the generated site.

These guard the claims the pages make: that every link works, that the rule
file in the repository is the one the contract hashed, and that the pages say
what they are (testnet, sandbox) and carry no secrets.

Run:  python -m unittest web.test_build
"""

from __future__ import annotations

import base64
import json
import re
import unittest

from backtest.pipeline.keccak import keccak256
from backtest.pipeline.rule import ROOT, thresholds_hash
from web import build

WEB = ROOT / "web"


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pages, cls.config = build.render_all()
        cls.deployment = (
            json.loads(build.DEPLOYMENT.read_text(encoding="utf-8")) if build.DEPLOYMENT.exists() else None
        )

    def test_every_place_has_a_claim_page(self) -> None:
        for slug in build.PLACES:
            self.assertIn(f"claim-{slug}.html", self.pages)

    def test_every_workspace_exists(self) -> None:
        for name in (
            "workspaces.html",
            "for-insurer.html",
            "for-reinsurer.html",
            "for-responder.html",
            "for-data.html",
            "for-research.html",
            "for-farmer.html",
        ):
            self.assertIn(name, self.pages)

    def test_reinsurer_page_is_one_event_not_a_cat_model(self) -> None:
        html = self.pages["for-reinsurer.html"]
        self.assertIn("Not a catastrophe model", html)
        self.assertNotRegex(html, r"(?i)\baverage annual loss\b.*\d")
        self.assertNotRegex(html, r"(?i)\bprobable maximum loss\b.*\d")
        self.assertNotRegex(html, r"(?i)\breturn period of\b")

    def test_reinsurer_damage_function_is_labelled_not_measured(self) -> None:
        html = self.pages["for-reinsurer.html"]
        self.assertIn("waist-high", html)
        self.assertIn("adapted", html)
        self.assertIn("assumption", html)
        self.assertIn("not a measured flood-depth map", html)
        self.assertIn("Radar open-water fraction is not depth", html)
        self.assertIn("id=\"vulnerability\"", html)

    def test_internal_links_resolve(self) -> None:
        """Every local href and src points at a page or file that exists, and every #fragment exists."""
        pattern = re.compile(r'(?:href|src)="([^"]+)"')
        for name, html in self.pages.items():
            for target in pattern.findall(html):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                path, _, fragment = target.partition("#")
                if path in ("", None):
                    path = name
                if path in self.pages:
                    if fragment:
                        self.assertIn(f'id="{fragment}"', self.pages[path], f"{name} links to {target}")
                else:
                    self.assertTrue((WEB / path).exists() or path == "chain-config.js", f"{name} links to missing {target}")

    def test_rule_file_bytes_match_the_hash(self) -> None:
        """The browser hashes these exact bytes. They must equal config/rule.yaml and the deployed hash."""
        embedded = base64.b64decode(self.config["ruleYamlB64"])
        self.assertEqual(embedded, (ROOT / "config" / "rule.yaml").read_bytes())
        self.assertEqual("0x" + keccak256(embedded).hex(), "0x" + thresholds_hash().hex())
        if self.deployment:
            self.assertEqual(self.deployment["thresholds_hash"].lower(), "0x" + thresholds_hash().hex())

    def test_claim_ids_match_the_deployment_record(self) -> None:
        if not self.deployment:
            self.skipTest("no deployment record")
        for claim in self.deployment["claims"]:
            self.assertEqual(claim["trigger_id"].lower(), self.config["zones"][claim["zone"]]["claimId"])

    def test_config_holds_no_secrets(self) -> None:
        text = json.dumps(self.config).lower()
        self.assertNotIn("private", text)
        self.assertNotIn("mnemonic", text)

    def test_every_page_says_what_it_is(self) -> None:
        for name, html in self.pages.items():
            self.assertIn("Testnet only", html, name)
            self.assertIn("M-PESA is a sandbox", html, name)

    def test_no_accuracy_percentage_is_published(self) -> None:
        for name, html in self.pages.items():
            self.assertNotRegex(html, r"(?i)\baccuracy of \d", name)
            self.assertNotRegex(html, r"(?i)\bprecision of \d", name)

    def test_live_script_holds_no_keys_and_loads_nothing_remote(self) -> None:
        js = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertNotRegex(js, r"0x[0-9a-fA-F]{64}")  # no hard-coded key or hash
        for name, html in self.pages.items():
            for src in re.findall(r'<script[^>]+src="([^"]+)"', html):
                self.assertFalse(src.startswith("http"), f"{name} loads {src} from the network")


if __name__ == "__main__":
    unittest.main()
