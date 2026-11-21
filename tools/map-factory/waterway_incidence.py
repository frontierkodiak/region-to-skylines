"""Exact incidence on the declared projected1um model, not hydraulic topology."""

from fractions import Fraction

import numpy as np

SCALE = 1_000_000


def micro(points):
    values = np.asarray(points, float)
    if (
        values.ndim != 2
        or values.shape[1] != 2
        or not len(values)
        or not np.isfinite(values).all()
    ):
        raise ValueError("Expected finite projected point geometry")
    if np.max(np.abs(values)) > 1e8:
        raise ValueError("Projected geometry outside supported integer range")
    return np.rint(values * SCALE).astype(np.int64)


def cross(a, b):
    return int(a[0]) * int(b[1]) - int(a[1]) * int(b[0])


def on_segment(p, a, b):
    return cross(p - a, b - a) == 0 and bool(
        np.all(p >= np.minimum(a, b)) and np.all(p <= np.maximum(a, b))
    )


def point_record(point):
    rationals = [Fraction(v) for v in point]
    return {
        "xz_m": [float(v / SCALE) for v in rationals],
        "xz_micro_rational": [[v.numerator, v.denominator] for v in rationals],
    }


def segment_incidence(a, b, c, d):
    """Integer/rational arithmetic, including zero-length and overlap evidence."""
    a, b, c, d = [np.asarray(v, np.int64) for v in (a, b, c, d)]
    if np.array_equal(a, b):
        return {"kind": "point", **point_record(a)} if on_segment(a, c, d) else None
    if np.array_equal(c, d):
        return {"kind": "point", **point_record(c)} if on_segment(c, a, b) else None
    r, s, delta = b - a, d - c, c - a
    denominator = cross(r, s)
    if denominator:
        t, u = (
            Fraction(cross(delta, s), denominator),
            Fraction(cross(delta, r), denominator),
        )
        if 0 <= t <= 1 and 0 <= u <= 1:
            return {
                "kind": "point",
                **point_record([int(a[i]) + t * int(r[i]) for i in (0, 1)]),
            }
        return None
    if cross(delta, r):
        return None
    common = sorted(
        {
            tuple(map(int, p))
            for p in (a, b, c, d)
            if on_segment(p, a, b) and on_segment(p, c, d)
        }
    )
    if not common:
        return None
    if len(common) == 1:
        return {"kind": "point", **point_record(common[0])}
    return {
        "kind": "overlap",
        "endpoints_xz_micro": [list(common[0]), list(common[-1])],
    }


def segments(points, closed=False):
    points = np.asarray(points, np.int64)
    if len(points) == 1:
        return points.copy(), points.copy()
    return (
        (points, np.roll(points, -1, axis=0)) if closed else (points[:-1], points[1:])
    )


def intersections(a, b, closed_b=False, self_pair=False):
    aa, ab = segments(a)
    ba, bb = segments(b, closed_b)
    low, high = np.minimum(ba, bb), np.maximum(ba, bb)
    result = []
    for i, (start, end) in enumerate(zip(aa, ab)):
        candidates = np.flatnonzero(
            np.all(high >= np.minimum(start, end), axis=1)
            & np.all(low <= np.maximum(start, end), axis=1)
        )
        for j in candidates:
            if self_pair and j <= i + 1:
                continue
            hit = segment_incidence(start, end, ba[j], bb[j])
            if hit:
                result.append({"a_segment": i, "b_segment": int(j), **hit})
    return result


def point_distances(points, line, closed=False):
    """All point-to-polyline distances; no nearest-endpoint topology inference."""
    starts, ends = segments(line, closed)
    a, vector = starts / SCALE, (ends - starts) / SCALE
    length = np.einsum("ij,ij->i", vector, vector)
    result = []
    for start in range(0, len(points), 128):
        delta = np.asarray(points[start : start + 128])[:, None, :] / SCALE - a
        t = np.divide(
            np.einsum("ijk,jk->ij", delta, vector),
            length,
            out=np.zeros(delta.shape[:2]),
            where=length > 0,
        ).clip(0, 1)
        result.extend(
            np.linalg.norm(delta - t[:, :, None] * vector, axis=2).min(axis=1).tolist()
        )
    return result


def minimum_distance(a, b, closed_b=False):
    return min(min(point_distances(a, b, closed_b)), min(point_distances(b, a)))


def in_ring(point, ring):
    """Boundary versus interior on integer geometry, without tolerance merging."""
    p = np.asarray(point, np.int64)
    inside = False
    a, b = segments(ring, closed=True)
    for start, end in zip(a, b):
        if on_segment(p, start, end):
            return "boundary"
        if (start[1] > p[1]) != (end[1] > p[1]):
            dx, dy = int(end[0] - start[0]), int(end[1] - start[1])
            lhs, rhs = int(p[0] - start[0]) * dy, int(p[1] - start[1]) * dx
            if (lhs < rhs) if dy > 0 else (lhs > rhs):
                inside = not inside
    return "inside" if inside else "outside"


def in_polygon(point, rings):
    results = [in_ring(point, ring) for ring in rings]
    if "boundary" in results:
        return "boundary"
    return (
        "inside"
        if results[0] == "inside" and all(r == "outside" for r in results[1:])
        else "outside"
    )


def near_boxes(a, b, radius=128):
    return bool(
        np.all(a.max(axis=0) + radius * SCALE >= b.min(axis=0))
        and np.all(b.max(axis=0) + radius * SCALE >= a.min(axis=0))
    )
