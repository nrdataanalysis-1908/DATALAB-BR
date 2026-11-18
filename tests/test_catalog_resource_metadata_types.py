import unittest

from brasil_eleitoral.ckan.catalog import normalize_dataset


class CatalogResourceMetadataTypeTests(unittest.TestCase):
    def normalize_resource(self, **overrides):
        resource = {
            "id": "resource-id",
            "name": "Resource",
            "format": "csv",
            "url": "https://example.test/data.csv",
            "size": 12,
            "datastore_active": False,
        }
        resource.update(overrides)
        return normalize_dataset(
            {
                "name": "dataset-name",
                "resources": [resource],
            },
            source_url="https://example.test",
            extracted_at="2026-11-16T00:00:00+00:00",
        )

    def test_rejects_boolean_resource_size(self):
        with self.assertRaisesRegex(ValueError, "resource size"):
            self.normalize_resource(size=True)

    def test_rejects_negative_resource_size(self):
        with self.assertRaisesRegex(ValueError, "resource size"):
            self.normalize_resource(size=-1)

    def test_rejects_non_boolean_datastore_flag(self):
        with self.assertRaisesRegex(ValueError, "datastore_active"):
            self.normalize_resource(datastore_active="yes")


if __name__ == "__main__":
    unittest.main()
