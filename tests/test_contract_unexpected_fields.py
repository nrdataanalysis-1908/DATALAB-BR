import unittest

from brasil_eleitoral.validation.contracts import DataContract, FieldContract, validate_records


class ContractUnexpectedFieldTests(unittest.TestCase):
    def test_record_with_uncontracted_field_is_invalid(self):
        contract = DataContract(
            name="strict", version=1,
            fields=(FieldContract("candidate_id", "string"), FieldContract("votes", "integer")),
        )
        report = validate_records(
            [{"candidate_id": "123", "votes": 10, "unreviewed": "extra"}], contract
        )
        self.assertFalse(report.valid)
        self.assertIn(
            {"row": 1, "field": "unreviewed", "code": "unexpected_field"},
            report.errors,
        )


if __name__ == "__main__":
    unittest.main()
