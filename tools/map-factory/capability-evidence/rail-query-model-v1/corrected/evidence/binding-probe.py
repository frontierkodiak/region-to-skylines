"""Mutate one predicted request without its observation and ask the evaluator to score.

Read-only evidence for the binding-correction review. On the reviewed head the
mutated prediction is still scored; on the corrected tree the evaluator refuses.
Run it from either prefix's `corrected/evidence/`; it prints one JSON line.
"""

import copy
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE.parents[1]
sys.path.insert(0, str(SOURCE))

import evaluate  # noqa: E402

openings = json.loads((SOURCE / "openings.json").read_text())
frozen = SOURCE / "corrected" / "predictions.json"
predictions_path = frozen if frozen.exists() else SOURCE / "predictions.json"
predictions = json.loads(predictions_path.read_text())
observations = evaluate.collect(openings)
altered = copy.deepcopy(predictions)
altered["queries"][0]["request"]["from"][0] = -123456789
result = {"predictions": str(predictions_path.relative_to(SOURCE))}
try:
    before = evaluate.evaluate(predictions, observations, openings)["rules"]
    after = evaluate.evaluate(altered, observations, openings)["rules"]
    result["evaluator"] = "scored the mutated request"
    result["identical_rules"] = after == before
except Exception as error:  # noqa: BLE001 - which error is the evidence
    result["evaluator"] = type(error).__name__
    result["message"] = str(error)[:200]
print(json.dumps(result, sort_keys=True))
