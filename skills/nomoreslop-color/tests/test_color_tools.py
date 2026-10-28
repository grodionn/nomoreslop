import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/color_tools.py"
spec = importlib.util.spec_from_file_location("color_tools", SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
BASE = "https://colorsinspo.com/color-palettes"


def palette(slug="test-palette", colors=("123456", "aBcDeF"), title="Test palette"):
    buttons = "".join(f'<button aria-label="Copy {color}" style="background-color:#{color}"></button>' for color in colors)
    return f'<article>{buttons}<a href="/color-palettes/{slug}">{title}</a></article>'


class ColorToolsTests(unittest.TestCase):
    def test_black_white_reference_ratio(self):
        self.assertEqual(tool.contrast("#000000", "#ffffff")["ratio"], 21.0)

    def test_identical_pair_and_symmetry(self):
        self.assertEqual(tool.contrast("#abc", "#aabbcc")["ratio"], 1.0)
        self.assertAlmostEqual(tool.contrast("#123456", "#abc")["ratio"], tool.contrast("#abc", "#123456")["ratio"])

    def test_primary_reference_luminance(self):
        self.assertAlmostEqual(tool.luminance("#ff0000"), 0.2126)
        self.assertAlmostEqual(tool.contrast("#f00", "#000")["ratio"], 5.252)

    def test_no_rounding_to_threshold(self):
        result = tool.contrast("#777777", "#ffffff")
        self.assertGreater(result["ratio"], 4.4)
        self.assertLess(result["ratio"], 4.5)
        self.assertFalse(result["meets_4_5_to_1"])

    def test_reject_ambiguous_formats_and_alpha(self):
        for value in ("#0000", "#00000080", "red", "rgb(0 0 0)", "oklch(0.5 0.1 0)", "#gggggg"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                tool.rgb(value)

    def test_public_url_boundaries(self):
        for value in ("http://colorsinspo.com/gradients", "https://elsewhere.test/gradients", "https://colorsinspo.com:443/gradients", "https://colorsinspo.com/api/palettes", "https://colorsinspo.com/color-palettes?q=red", "https://colorsinspo.com/color-palettes#x", "https://user@colorsinspo.com/gradients"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                tool.allowed_url(value)
        self.assertEqual(tool.allowed_url(BASE + "/temperature/neutral/2"), BASE + "/temperature/neutral/2")

    def test_palette_has_provenance_and_ignores_ui_colors(self):
        html = '<html><nav style="color:#112233">Navigation</nav>' + palette() + '</html>'
        result = tool.extract(html.encode(), BASE, "saved-html-not-live-request")
        self.assertEqual(result["items"][0]["colors"], ["#123456", "#ABCDEF"])
        self.assertEqual(result["items"][0]["url"], BASE + "/test-palette")
        self.assertEqual(result["items"][0]["name"], "Test palette")
        self.assertEqual(result["channel"], "saved-html-not-live-request")

    def test_gradient_comes_from_card_not_navigation(self):
        html = '<html><nav style="background:linear-gradient(red,blue)"></nav><article><a href="/gradients/test-gradient" title="Inspect Quiet Space gradient"></a><div style="background:linear-gradient(60deg, rgb(1,2,3) 0%, rgb(4,5,6) 100%);"></div></article></html>'
        result = tool.extract(html.encode(), "https://colorsinspo.com/gradients", "fixture")
        self.assertEqual(result["item_count"], 1)
        self.assertEqual(result["items"][0]["name"], "Quiet Space")
        self.assertIn("rgb(1,2,3)", result["items"][0]["gradient_css"])

    def test_duplicates_and_repeated_pages_have_same_fingerprint(self):
        one = tool.extract(("<html>" + palette() + "</html>").encode(), BASE, "fixture")
        two = tool.extract(("<html>" + palette() + palette() + "</html>").encode(), BASE + "/2", "fixture")
        self.assertEqual(two["item_count"], 1)
        self.assertEqual(one["items_fingerprint"], two["items_fingerprint"])

    def test_distinct_palette_does_not_collapse(self):
        one = tool.extract(("<html>" + palette() + "</html>").encode(), BASE, "fixture")
        two = tool.extract(("<html>" + palette(colors=("000000", "ffffff")) + "</html>").encode(), BASE, "fixture")
        self.assertNotEqual(one["items_fingerprint"], two["items_fingerprint"])

    def test_category_hub_is_not_empty_catalog_claim(self):
        result = tool.extract(b'<html><a href="/color-palettes/hue/red">Red</a></html>', BASE + "/hue", "fixture")
        self.assertEqual(result["item_count"], 0)
        self.assertIn(BASE + "/hue/red", result["discovered_links"])
        self.assertTrue(any("not evidence" in message for message in result["warnings"]))

    def test_external_item_and_non_palette_buttons_are_not_candidates(self):
        html = '<html><article><button aria-label="Copy 123456"></button><button aria-label="Copy abcdef"></button><a href="https://elsewhere.test/color-palettes/test">Wrong</a></article></html>'
        self.assertEqual(tool.extract(html.encode(), BASE, "fixture")["item_count"], 0)

    def test_css_with_url_not_returned_as_simple_gradient(self):
        self.assertIsNone(tool.gradient_value('background:linear-gradient(red,blue),url(https://example.test/a)'))

    def test_large_or_non_html_input_rejected(self):
        for data in (b"[]", b"x" * (tool.MAX_BYTES + 1)):
            with self.assertRaises(ValueError):
                tool.extract(data, BASE, "fixture")

    def test_item_limit(self):
        html = '<html>' + ''.join(palette(slug=f'palette-{i}') for i in range(80)) + '</html>'
        self.assertEqual(tool.extract(html.encode(), BASE, "fixture")["item_count"], tool.MAX_ITEMS)

    def test_saved_html_requires_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.html"
            path.write_text('<html>' + palette() + '</html>', encoding="utf-8")
            from contextlib import redirect_stderr
            from io import StringIO
            buffer = StringIO()
            with redirect_stderr(buffer):
                result = tool.main(["extract", "--html", str(path)])
            self.assertEqual(result, 1)
            self.assertIn("requires --source-url", json.loads(buffer.getvalue())["error"])

    def test_solid_color_parent_link_and_named_value(self):
        html = '<html><a href="/color/4c4f56" aria-label="Open Dark Slate Gray"><article><div style="color:#ffffff;background-color:#4c4f56"><button aria-label="Copy #4c4f56"></button></div><p>Dark Slate Gray</p></article></a></html>'
        result = tool.extract(html.encode(), "https://colorsinspo.com/solid-color", "fixture")
        self.assertEqual(result["item_count"], 1)
        self.assertEqual(result["items"][0]["kind"], "solid-color")
        self.assertEqual(result["items"][0]["colors"], ["#4C4F56"])
        self.assertEqual(result["items"][0]["name"], "Dark Slate Gray")
        self.assertEqual(result["items"][0]["url"], "https://colorsinspo.com/color/4c4f56")

    def test_solid_hubs_and_detail_url_boundaries(self):
        for path in ("/solid-color", "/solid-color/saturation/muted", "/color/4c4f56"):
            self.assertEqual(tool.allowed_url("https://colorsinspo.com" + path), "https://colorsinspo.com" + path)
        with self.assertRaises(ValueError):
            tool.allowed_url("https://colorsinspo.com/color/not-a-color")

    def test_one_swatch_is_not_a_palette(self):
        html = '<html>' + palette(colors=("123456",)) + '</html>'
        self.assertEqual(tool.extract(html.encode(), BASE, "fixture")["item_count"], 0)


if __name__ == "__main__":
    unittest.main()
