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
    def test_discovers_all_pages_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=FakeClient(); result=discover_catalog(client,Path(tmp),page_size=1)
            self.assertEqual(result["dataset_count"],2); self.assertTrue(result["complete"])
            self.assertTrue((Path(tmp)/"manifest.json").exists()); self.assertTrue((Path(tmp)/"resultado-2022.json").exists())
            self.assertEqual(client.calls,[(0,1),(1,1)])
    def test_resume_uses_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/".ckan_checkpoint.json").write_text(json.dumps({"next_start":1,"total":2,"seen":{"resultado-2022":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}))
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
            with self.assertRaises(ValueError): discover_catalog(FakeClient(),Path(tmp),page_size=0)
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
