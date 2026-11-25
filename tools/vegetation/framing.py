"""Conservative pair envelope, including each prefab's native random scale."""

import itertools
import math


def pair_framing(left, right, *, low=False):
    sizes = [[v * max(t["scale_range"]) for v in t["main"]["size_m"]] for t in (left, right)]
    height = max(s[1] for s in sizes)
    gap = max(s[0] for s in sizes) * 1.5 + (0.5 if low else 12)
    # Invert the perspective-frustum inequalities for every envelope corner.
    # The close camera uses 25° pitch, 45° vertical FOV and a 16:9 frame.
    pitch, tangent, padding = math.radians(55 if low else 25), math.tan(math.radians(22.5)), 0.85
    distance = 3 if low else 35
    for sign, (width, tall, deep) in zip((-1, 1), sizes):
        for x, y, z in itertools.product((-width / 2, width / 2), (0, tall), (-deep / 2, deep / 2)):
            x += sign * gap / 2
            y -= height * 0.4
            forward = z * math.cos(pitch) - y * math.sin(pitch)
            up = y * math.cos(pitch) + z * math.sin(pitch)
            distance = max(
                distance,
                abs(x) / (tangent * 16 / 9 * padding) - forward,
                abs(up) / (tangent * padding) - forward,
            )
    return {"height": height, "gap": gap, "size": distance}
