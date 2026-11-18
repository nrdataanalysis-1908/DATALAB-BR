import unittest

from brasil_eleitoral.ckan.catalog import normalize_dataset


class CatalogResourceTextFieldTests(unittest.TestCase):
    def normalize(self, **overrides):
        resource = {
            "id": "resource-id",
            "name": "resource",
            "description": "Public dataset",
            "format": "csv",
            "url": "https://example.test/data.csv",
            "created": "2026-01-01T00:00:00Z",
            "last_modified": "2026-01-02T00:00:00Z",
            "size": 12,
            "hash": "abc123",
            "datastore_active": False,
            "mimetype": "text/csv",
        }
        resource.update(overrides)
        return normalize_dataset(
            {"name": "dataset", "resources": [resource]},
            source_url="https://example.test",
            extracted_at="2026-11-17T00:00:00+00:00",
        )

    def test_rejects_non_text_resource_identity_and_description_fields(self):
        for field in ("id", "name", "description"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, f"resource {field}"):
                    self.normalize(**{field: {"unexpected": "object"}})

    def test_rejects_non_text_resource_location_and_timestamp_fields(self):
        expected_labels = {
            "url": "resource URL",
            "created": "resource creation timestamp",
            "last_modified": "resource modification timestamp",
        }
        for field, expected_label in expected_labels.items():
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, expected_label):
                    self.normalize(**{field: ["not", "text"]})

    def test_rejects_non_text_resource_hash_and_mimetype(self):
        expected_labels = {
            "hash": "resource hash",
            "mimetype": "resource MIME type",
        }
        for field, expected_label in expected_labels.items():
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, expected_label):
                    self.normalize(**{field: 123})

    def test_accepts_null_optional_resource_text_fields(self):
        normalized = self.normalize(**{
            field: None
            for field in (
                "id", "name", "description", "url", "created",
                "last_modified", "hash", "mimetype",
            )
        })
        resource = normalized["resources"][0]
        self.assertTrue(all(resource[field] is None for field in (
            "id", "name", "description", "url", "created",
            "last_modified", "hash", "mimetype",
        )))


if __name__ == "__main__":
    unittest.main()
