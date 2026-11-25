"""Explicit specimen references, independent of the candidate's authoring route."""

import json


def load_plan(names, control, path=None):
    """Validate overrides before taking the native slot; preserve the v8 defaults."""
    overrides = json.loads(path.read_text()) if path else {}
    if not isinstance(overrides, dict) or set(overrides) - set(names):
        raise ValueError("Comparison plan must map known candidate package stems")
    plan = {}
    for name in names:
        tilia = name.startswith("KudzuTilia")
        row = overrides.get(
            name,
            {
                "prefab": "mp9-YoungLinden" if tilia else control,
                "basis": "Named Tilia age-class match"
                if tilia
                else "Generic stock control, not a vetted genus match",
                "evidence": "PL-1328 native v8 stock comparison; not best-supply certification",
            },
        )
        if not isinstance(row, dict) or set(row) != {"prefab", "basis", "evidence"}:
            raise ValueError(f"{name}: expected prefab, basis and evidence fields")
        if any(
            not isinstance(value, str) or not value.strip() for value in row.values()
        ):
            raise ValueError(f"{name}: comparison fields must be nonempty strings")
        plan[name] = dict(row)
    return plan


def resolve_plan(plan, trees):
    """Bind exact catalog names and mesh metrics, without fuzzy prefab substitution."""
    catalog = {tree["name"]: tree for tree in trees}
    missing = {row["prefab"] for row in plan.values()} - catalog.keys()
    if missing:
        raise ValueError(f"Comparison prefabs did not load: {sorted(missing)}")
    return {
        name: {**row, "catalog": catalog[row["prefab"]]} for name, row in plan.items()
    }


def specimen_references(pairs):
    """Use actual placed names for gallery labels, including retained v8 receipts."""
    return {
        pair["specimens"][0]["name"].split(".")[0]: {
            "prefab": pair["specimens"][1]["name"],
            "basis": pair["comparison_basis"],
            "evidence": pair.get("comparison_evidence"),
        }
        for pair in pairs
    }
