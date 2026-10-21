# SPDX-License-Identifier: MIT
"""Sonde de rendu : exécutée par `python -I` dans l'env bim ; imprime un JSON."""

import hashlib
import io
import json

import numpy as np
from deskgate_bim import render
from deskgate_bim.bcfdoc import camera_pose
from PIL import Image

FACES = np.array(
    [
        [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
        [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7],
    ],
    dtype=np.int32,
)  # fmt: skip
BASE = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float64)


def box(x: float, y: float, z: float, sx: float, sy: float, sz: float):
    low = np.column_stack([BASE * [sx, sy] + [x, y], np.full(4, z)])
    high = np.column_stack([BASE * [sx, sy] + [x, y], np.full(4, z + sz)])
    return np.vstack([low, high]), FACES


def pixels(png: bytes):
    return list(Image.open(io.BytesIO(png)).convert("RGB").getdata())


def is_red(p):
    return p[0] > 150 and p[1] < 110 and p[2] < 110


def is_blue(p):
    return p[2] > 150 and p[0] < 110


def is_grey(p):
    return abs(p[0] - p[1]) <= 2 and abs(p[1] - p[2]) <= 2 and 180 <= p[0] <= 250


RED, BLUE = (229, 57, 53, 255), (30, 136, 229, 255)
A, B, CTX = box(0, 0, 0, 1, 1, 1), box(0.5, 0, 0, 1, 1, 1), box(-3, 0, 0, 4, 1, 1)
FLOOR = box(-500, -500, -1.2, 1000, 1000, 0.2)
cam = camera_pose([0.5, 0.5, 0.5], 1.5)
opaque = [(RED, A), (BLUE, B)]

p1 = render.render_view(cam, opaque)
p1b = render.render_view(cam, opaque)
p2 = render.render_view(cam, opaque, [CTX])
px1, px2 = pixels(p1), pixels(p2)
floor_cam = {
    "position": [0, 0, 1],
    "direction": [1, 1, -0.5],
    "up": [0, 0, 1],
    "field_of_view": 60.0,
}
pf = pixels(render.render_view(floor_cam, [(RED, FLOOR)]))
try:
    render.render_view(cam, opaque, size=(0, 0))
    bad = False
except ValueError:
    bad = True
print(
    json.dumps(
        {
            "sig": p1[:8].hex(),
            "size": list(Image.open(io.BytesIO(p1)).size),
            "red": sum(map(is_red, px1)),
            "blue": sum(map(is_blue, px1)),
            "red2": sum(map(is_red, px2)),
            "blue2": sum(map(is_blue, px2)),
            "grey": sum(map(is_grey, px2)),
            "floor_ratio": sum(1 for p in pf if p != (255, 255, 255)) / len(pf),
            "sha_1": hashlib.sha256(p1).hexdigest(),
            "sha_1_bis": hashlib.sha256(p1b).hexdigest(),
            "bad_size_error": bad,
        }
    )
)
