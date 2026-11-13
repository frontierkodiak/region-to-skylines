"""Rejected coupled arm's physical classifier, retained for the causal trace only."""

import numpy as np
from region import raster


def portal_gravity_status(path, banks, geometry, features, channel, max_lowering=3.0):
    """Physical/profile evidence for an infeasible finite daylighted connector."""
    from collections import Counter

    ends = Counter()
    selected = []
    for feature in features:
        if (raster(geometry["sq"], [feature]) & channel).any():
            selected.append(feature)
            ends.update([tuple(feature["pts"][0]), tuple(feature["pts"][-1])])
    open_ends = [p for p, count in ends.items() if count == 1]
    tunnels = {
        tuple(point)
        for feature in geometry.get("undergroundWaterways", [])
        for point in [feature["pts"][0], feature["pts"][-1]]
    }
    linked = len(open_ends) == 2 and all(p in tunnels for p in open_ends)
    y, x = path.T
    # Existing incision bound and minimum modeled metre of supply headroom.
    lower = banks[y, x] - max_lowering + 1.0
    ceiling = banks[y, x] - 0.25
    required = np.maximum.accumulate(lower[::-1])[::-1]
    excess = float((required - ceiling).max())
    return {
        "explicit_tunnel_bounded": linked,
        "minimum_gravity_profile_above_bank_ceiling_m": excess,
        "defer_browser_cut": linked and excess > 1 / 64,
        "source_features": selected,
    }
