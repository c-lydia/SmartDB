"""Fit a planar RGB-to-thermal mapping from measured corresponding pixel centres.

No third-party Python packages. Points must already account for lens distortion;
this tool cannot estimate depth or lens distortion from a homography.
"""

import argparse
import json
import math
from pathlib import Path


def solve(a, b):
    rows = [list(row) + [value] for row, value in zip(a, b)]
    n = len(b)
    for col in range(n):
        pivot = max(range(col, n), key=lambda i: abs(rows[i][col]))
        if abs(rows[pivot][col]) < 1e-10:
            raise ValueError("Degenerate calibration: spread targets across both image axes")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        scale = rows[col][col]
        rows[col] = [v / scale for v in rows[col]]
        for i in range(n):
            if i != col:
                scale = rows[i][col]
                rows[i] = [x - scale * y for x, y in zip(rows[i], rows[col])]
    return [row[-1] for row in rows]


def fit(data):
    if data.get("rgb_size") != [320, 240] or data.get("thermal_size") != [32, 24]:
        raise ValueError("This firmware supports RGB 320x240 and thermal 32x24")
    points = data["points"]
    if len(points) < 6:
        raise ValueError("Provide at least six corresponding targets for a residual check")
    rows, values = [], []
    for point in points:
        x, y = point["rgb"]
        u, v = point["thermal"]
        if not all(math.isfinite(z) for z in (x, y, u, v)) or not (
            0 <= x <= 319 and 0 <= y <= 239 and 0 <= u <= 31 and 0 <= v <= 23
        ):
            raise ValueError("Point outside image or not finite")
        x, y, u, v = x / 319, y / 239, u / 31, v / 23
        rows.extend(([x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]))
        values.extend((u, v))
    a = [[sum(row[i] * row[j] for row in rows) for j in range(8)] for i in range(8)]
    b = [sum(row[i] * v for row, v in zip(rows, values)) for i in range(8)]
    h = solve(a, b) + [1]
    h = [
        31 * h[0] / 319,
        31 * h[1] / 239,
        31 * h[2],
        23 * h[3] / 319,
        23 * h[4] / 239,
        23 * h[5],
        h[6] / 319,
        h[7] / 239,
        1,
    ]
    denominators = [h[6] * x + h[7] * y + 1 for x, y in [(0, 0), (319, 0), (0, 239), (319, 239)]]
    if min(denominators) <= 1e-6:
        raise ValueError("Projective horizon intersects image")
    errors = []
    for point in points:
        x, y = point["rgb"]
        u, v = point["thermal"]
        d = h[6] * x + h[7] * y + 1
        errors.append(
            math.hypot((h[0] * x + h[1] * y + h[2]) / d - u, (h[3] * x + h[4] * y + h[5]) / d - v)
        )
    limit = data.get("max_fit_error_thermal_px", 0.5)
    if not math.isfinite(limit) or limit <= 0 or max(errors) > limit:
        raise ValueError(f"Calibration residual too large: {max(errors):.3f} thermal pixels")
    determinant = (
        h[0] * (h[4] - h[5] * h[7])
        - h[1] * (h[3] - h[5] * h[6])
        + h[2] * (h[3] * h[7] - h[4] * h[6])
    )
    if abs(determinant) < 1e-10:
        raise ValueError("Singular calibration")
    return h, max(errors)


def header(data):
    h, error = fit(data)
    version = data["version"]
    if (
        not isinstance(version, str)
        or not version
        or not all(c.isalnum() or c in "-_." for c in version)
    ):
        raise ValueError("Use a nonempty alphanumeric calibration version")
    regions = data["regions"]
    if not 1 <= len(regions) <= 8:
        raise ValueError("Define one to eight RGB regions")
    entries = []
    ids = set()
    for region in regions:
        name = region["id"]
        x0, y0, x1, y1 = region["rect"]
        minimum = region.get("min_samples", 4)
        if (
            not isinstance(name, str)
            or not name
            or name in ids
            or not all(c.isalnum() or c in "-_." for c in name)
        ):
            raise ValueError("Region IDs must be unique alphanumeric names")
        ids.add(name)
        if (
            not (0 <= x0 < x1 <= 319 and 0 <= y0 < y1 <= 239)
            or not isinstance(minimum, int)
            or not 1 <= minimum <= 768
        ):
            raise ValueError("Invalid region bounds or minimum sample count")
        entries.append(
            "    {%s, %s, %s, %s, %s, %d}," % (json.dumps(name), x0, y0, x1, y1, minimum)
        )
    matrix = ", ".join(format(v, ".10g") for v in h)
    return (
        '#pragma once\n#include "fusion_core.h"\n'
        f"/* Fit residual: {error:.6f} thermal pixels. This is not independent validation. */\n"
        "static const fc_calibration_t installation_calibration = {\n"
        f"    .enabled=true, .version={json.dumps(version)}, .width=320, .height=240,\n"
        f"    .rgb_to_thermal={{{matrix}}},\n"
        "    .display_min_c=20, .display_max_c=80, .opacity=.45f,\n};\n"
        "static const fc_region_t installation_regions[] = {\n" + "\n".join(entries) + "\n};\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("points", type=Path)
    parser.add_argument(
        "output", type=Path, help="Explicit destination; use config/calibration.h for live firmware"
    )
    args = parser.parse_args()
    args.output.write_text(header(json.loads(args.points.read_text())))
    print(f"Wrote {args.output}; fit is only valid for the specified fixed scene plane.")
