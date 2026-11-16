import unittest

from brasil_eleitoral.ckan.catalog import normalize_dataset


class CatalogTopLevelMetadataTypeTests(unittest.TestCase):
    def normalize(self, **overrides):
        dataset = {
            "id": "dataset-id",
            "name": "dataset-name",
            "title": "Dataset title",
            "notes": "Description",
            "organization": {"id": "org-id", "title": "Organization"},
            "resources": [],
        }
        dataset.update(overrides)
        return normalize_dataset(
            dataset,
            source_url="https://example.test",
            extracted_at="2026-11-16T00:00:00+00:00",
        )

    def test_rejects_non_text_dataset_title(self):
        with self.assertRaisesRegex(ValueError, "dataset title"):
            self.normalize(title=["not", "text"])

    def test_rejects_non_text_organization_title(self):
        with self.assertRaisesRegex(ValueError, "organization title"):
            self.normalize(organization={"title": {"unexpected": "object"}})


if __name__ == "__main__":
    unittest.main()
