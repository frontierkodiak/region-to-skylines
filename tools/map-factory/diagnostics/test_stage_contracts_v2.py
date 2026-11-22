import json
import unittest

import numpy as np

from stage_contracts import merge_intervals
from stage_contracts_v2 import json_scalars


class JsonTests(unittest.TestCase):
    def test_extended_interval_numpy_high_serializes_without_changing_value(self):
        intervals = merge_intervals([(1, 2), (np.int32(2), np.int32(5))])
        result = {"intervals": intervals, "count": np.int64(3), "fit": np.bool_(True)}
        self.assertEqual(
            json.loads(json.dumps(json_scalars(result))),
            {"intervals": [[1, 5]], "count": 3, "fit": True},
        )

    def test_nonfinite_remains_rejected_unknown_not_fabricated_zero(self):
        with self.assertRaises(ValueError):
            json.dumps(json_scalars({"value": np.float64(np.nan)}), allow_nan=False)


if __name__ == "__main__":
    unittest.main()
