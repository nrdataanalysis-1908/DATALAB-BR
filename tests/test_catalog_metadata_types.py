import unittest

from brasil_eleitoral.ckan.catalog import normalize_dataset


class CatalogMetadataTypeTests(unittest.TestCase):
    def normalize(self, **overrides):
        dataset = {
            "id": "dataset-id",
            "name": "dataset-name",
            "organization": {"id": "org-id", "title": "Organization"},
            "groups": [{"name": "group-name", "title": "Group"}],
            "tags": [{"name": "tag-name"}],
            "resources": [{
                "id": "resource-id",
                "name": "Resource",
                "description": "Description",
                "format": "csv",
                "url": "https://example.test/data.csv",
                "created": "2026-01-01",
                "last_modified": "2026-01-02",
                "size": 12,
                "hash": "abc",
                "datastore_active": False,
                "mimetype": "text/csv",
            }],
        }
        dataset.update(overrides)
        return normalize_dataset(
            dataset,
            source_url="https://example.test",
            extracted_at="2026-11-16T00:00:00+00:00",
        )

    def test_rejects_non_text_group_labels(self):
        with self.assertRaisesRegex(ValueError, "group title"):
            self.normalize(groups=[{"title": {"unexpected": "object"}, "name": "group"}])

    def test_rejects_non_text_tag_names(self):
        with self.assertRaisesRegex(ValueError, "tag name"):
            self.normalize(tags=[{"name": ["not", "text"]}])

    def test_rejects_non_text_resource_format(self):
        with self.assertRaisesRegex(ValueError, "resource format"):
            self.normalize(resources=[{"format": {"csv": True}}])


if __name__ == "__main__":
    unittest.main()
