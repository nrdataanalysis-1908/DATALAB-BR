import json
import tempfile
import unittest
from pathlib import Path

from generate_report import build_report, load_datasets


class HtmlReportTests(unittest.TestCase):
    def test_report_escapes_metadata_and_summarizes_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.json").write_text(json.dumps({
                "name": "dataset",
                "title": "<script>alert(1)</script>",
                "organization": "TSE",
                "metadata_modified": "2026-10-30",
                "resources": [{"format": "CSV"}],
            }), encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "source_url": "https://dadosabertos.tse.jus.br/",
                "discovered_at": "2026-10-30T00:00:00Z",
                "datasets": [{"path": "sample.json"}],
            }), encoding="utf-8")
            output = root / "report" / "index.html"
            build_report(manifest, output)
            content = output.read_text(encoding="utf-8")
            self.assertIn("CONJUNTOS CARREGADOS</span><strong>1", content)
            self.assertIn("RECURSOS CATALOGADOS</span><strong>1", content)
            self.assertIn("&lt;script&gt;", content)
            self.assertNotIn("<script>alert(1)</script>", content)

    def test_missing_manifest_generates_honest_empty_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = build_report(root / "missing.json", root / "index.html")
            content = output.read_text(encoding="utf-8")
            self.assertIn("AGUARDANDO DESCOBERTA", content)
            self.assertIn("CONJUNTOS CARREGADOS</span><strong>0", content)

    def test_manifest_rejects_parent_traversal_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside.json"
            outside.write_text(json.dumps({"title": "must not load"}), encoding="utf-8")
            catalog = root / "catalog"
            catalog.mkdir()
            manifest = catalog / "manifest.json"
            manifest.write_text(json.dumps({"datasets": [{"path": "../outside.json"}]}), encoding="utf-8")
            _, datasets = load_datasets(manifest)
            self.assertEqual(datasets, [])


if __name__ == "__main__":
    unittest.main()
