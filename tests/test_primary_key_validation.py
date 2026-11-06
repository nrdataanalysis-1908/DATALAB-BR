import unittest

from brasil_eleitoral.validation.contracts import DataContract, FieldContract, validate_records


class PrimaryKeyValidationTests(unittest.TestCase):
    def test_unhashable_invalid_primary_key_values_are_reported_not_raised(self):
        contract = DataContract(
            name="strict_keys",
            version=1,
            fields=(FieldContract("candidate_id", "string"),),
            primary_key=("candidate_id",),
        )
        report = validate_records(
            [{"candidate_id": ["invalid"]}, {"candidate_id": ["invalid"]}],
            contract,
        )

        self.assertFalse(report.valid)
        self.assertEqual(
            sum(error["code"] == "invalid_type" for error in report.errors),
            2,
        )
        self.assertNotIn(
            "duplicate_primary_key",
            {error["code"] for error in report.errors},
        )


if __name__ == "__main__":
    unittest.main()
