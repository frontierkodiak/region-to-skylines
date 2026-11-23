import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "scoring_repair", Path(__file__).with_name("evaluate.py")
)
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class WireSchema(unittest.TestCase):
    def test_requires_exact_success_envelope_and_body(self):
        body = {"id": 5, "complete": True}
        self.assertTrue(repair.wire_schema_matches(dict(body, ok=True), body))
        for row in [
            body,
            dict(body, ok=False),
            dict(body, ok=1),
            dict(body, ok=True, unexpected=1),
            {"ok": True},
        ]:
            self.assertFalse(repair.wire_schema_matches(row, body))


if __name__ == "__main__":
    unittest.main()
