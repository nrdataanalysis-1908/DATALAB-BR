import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from brasil_eleitoral.ckan.catalog import discover_catalog, normalize_dataset
from brasil_eleitoral.ckan.client import CKANClient

class FakeClient:
    base_url = "https://dadosabertos.tse.jus.br"
    def __init__(self): self.calls = []
    def search_page(self, *, start, rows):
        self.calls.append((start, rows))
        records = [
          {"id":"id-1","name":"resultado-2022","title":"Resultados 2022","license_id":"cc-by",
           "organization":{"title":"TSE","id":"tse"},"groups":[{"title":"Resultados"}],
           "tags":[{"name":"eleicoes"}],"resources":[{"id":"r1","name":"CSV","format":"csv","url":"https://example.test/data.csv"}]},
          {"id":"id-2","name":"candidaturas-2022","title":"Candidaturas 2022","resources":[]}]
        return {"count":2,"results":records[start:start+rows]}

class CatalogTests(unittest.TestCase):
    def test_normalize_keeps_license_and_resource_metadata(self):
        item=normalize_dataset({"name":"x","license_id":"cc-by","resources":[{"format":"csv"}]},source_url="https://tse.test",extracted_at="2026-01-01T00:00:00+00:00")
        self.assertEqual(item["license_id"],"cc-by"); self.assertEqual(item["resources"][0]["format"],"CSV")
    def test_normalize_rejects_malformed_nested_metadata(self):
        with self.assertRaisesRegex(ValueError, "resources"):
            normalize_dataset(
                {"name": "broken", "resources": [None]},
                source_url="https://tse.test",
                extracted_at="2026-01-01T00:00:00+00:00",
            )

    def test_discovery_skips_non_string_dataset_names(self):
        class NonStringNameClient(FakeClient):
            def search_page(self, *, start, rows):
                return {"count": 1, "results": [{"name": 42, "resources": []}]}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = discover_catalog(NonStringNameClient(), root, page_size=1)
            self.assertEqual(result["dataset_count"], 0)
            self.assertFalse(result["complete"])
            self.assertEqual(list(root.glob("*.json")), [root / "manifest.json"])

    def test_discovery_skips_malformed_dataset_without_aborting_page(self):
        class MixedClient(FakeClient):
            def search_page(self, *, start, rows):
                return {
                    "count": 2,
                    "results": [
                        {"name": "malformed", "resources": [None]},
                        {"name": "valid-dataset", "resources": []},
                    ][start:start + rows],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = discover_catalog(MixedClient(), root, page_size=2)
            self.assertEqual(result["dataset_count"], 1)
            self.assertFalse(result["complete"])
            self.assertTrue((root / "valid-dataset.json").is_file())
            self.assertFalse((root / "malformed.json").exists())

    def test_discovers_all_pages_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=FakeClient(); result=discover_catalog(client,Path(tmp),page_size=1)
            self.assertEqual(result["dataset_count"],2); self.assertTrue(result["complete"])
            self.assertTrue((Path(tmp)/"manifest.json").exists()); self.assertTrue((Path(tmp)/"resultado-2022.json").exists())
            self.assertEqual(client.calls,[(0,1),(1,1)])
    def test_resume_uses_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cached = root / "resultado-2022.json"
            cached.write_text(json.dumps({"name": "resultado-2022"}), encoding="utf-8")
            digest = hashlib.sha256(cached.read_bytes()).hexdigest()
            (root / ".ckan_checkpoint.json").write_text(
                json.dumps({
                    "next_start": 1,
                    "total": 2,
                    "seen": {"resultado-2022": digest},
                }),
                encoding="utf-8",
            )
            client=FakeClient(); result=discover_catalog(client,root,page_size=1)
            self.assertEqual(client.calls,[(1,1)]); self.assertEqual(result["dataset_count"],2)
    def test_skips_path_traversal_slug(self):
        class UnsafeClient(FakeClient):
            def search_page(self,*,start,rows): return {"count":1,"results":[{"name":"../escape","resources":[]}]}
        with tempfile.TemporaryDirectory() as tmp:
            result=discover_catalog(UnsafeClient(),Path(tmp),page_size=10)
            self.assertEqual(result["dataset_count"],0); self.assertFalse((Path(tmp).parent/"escape.json").exists())
    def test_rejects_invalid_page_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            for value in (0, True, 1.5, "10"):
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        discover_catalog(FakeClient(), Path(tmp), page_size=value)
    @patch("brasil_eleitoral.ckan.client.urlopen")
    @patch("brasil_eleitoral.ckan.client.time.sleep")
    def test_retries_transient_http_error(self,sleep,urlopen):
        from urllib.error import HTTPError
        import io
        response=type("Response",(),{"__enter__":lambda s:s,"__exit__":lambda *a:None,"read":lambda s:b'{"success":true,"result":{"ok":true}}'})()
        urlopen.side_effect=[HTTPError("https://x",503,"busy",{},io.BytesIO()),response]
        client=CKANClient("https://x",retries=1,backoff=0)
        self.assertEqual(client.action("package_search"),{"ok":True}); self.assertEqual(urlopen.call_count,2)

if __name__=="__main__": unittest.main()
