"""Optional visual checks on screenshots with blade's resident Clef-Flash.

Clef answers typed questions about an image with a probability per option in
one pass. These checks cover what the game's state can't report: frames that
aren't the game at all, black or garbled frames, terraced terrain, and water
that looks wrong. Its answers are advisory. Wherever the mod reads the truth
(water depth, population, paths), that wins, and JOURNAL.md records how Clef
did against labelled screenshots before anyone relies on it.
"""

from __future__ import annotations

import base64
import io
import json
import os
import pathlib
import urllib.request

from PIL import Image

ENDPOINT = os.environ.get("CS1_HARNESS_CLEF", "http://127.0.0.1:9120/v1/systemone")

STATE = (
    "A screenshot captured by an automated test of the city-building game Cities: Skylines 1. "
    "Normal frames show the game's 3D terrain or city from above, sometimes with the game's own menus or panels."
)

QUESTIONS = {
    "frame": {
        "type": "choice",
        "instructions": "What does this screenshot show?",
        "criteria": {
            "world": "The game's 3D terrain, map or city view (game UI panels may be visible)",
            "menu": "A game menu, dialog or loading screen covering most of the view",
            "desktop": "An operating system desktop, error dialog or something other than the game",
            "blank": "A black, white or single-colour frame with no scene",
        },
    },
    "glitched": {
        "type": "noul",
        "instructions": "Is the image corrupted or garbled: noise, torn or shifted blocks, stripes, "
        "missing textures, or large solid areas where a scene should be?",
    },
    "terraced": {
        "type": "noul",
        "instructions": "Does the terrain show artificial stair-steps: flat terraces separated by many "
        "parallel contour-like ridges, rather than smooth natural slopes?",
    },
    "water_wrong": {
        "type": "noul",
        "instructions": "Does the water look wrong: a flat sheet of water spread over land or hills, "
        "water that ends in straight edges or walls, or a sea bed left bare where water should be?",
    },
    "buildable": {
        "type": "score",
        "instructions": "How much broad, gently sloping open land is visible that a city could be built on?",
        "criteria": ["none", "a little", "a fair amount", "a lot"],
    },
}


def data_url(path: pathlib.Path, max_side: int = 768) -> str:
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def ask(path: pathlib.Path, questions: dict = QUESTIONS, timeout: float = 120) -> dict:
    body = {"model": "clef-flash", "state": STATE, "questions": questions, "images": [data_url(path)]}
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def summarize(reply: dict) -> dict:
    """Flatten a SystemOne reply to {question: value}: P(true), the chosen option, or the expected score."""
    out = {}
    answers = reply.get("answers") or reply.get("results") or reply
    for qid in QUESTIONS:
        a = answers.get(qid) if isinstance(answers, dict) else None
        if a is None:
            continue
        if isinstance(a, (int, float)):
            out[qid] = round(float(a), 3)
        elif "choice" in a:
            out[qid] = a["choice"]
            out[qid + "_p"] = round(float(a.get("confidence", 0)), 3)
        elif "noul" in a:
            out[qid] = round(float(a["noul"]), 3)
        elif "score" in a:
            out[qid] = round(float(a["score"]), 2)
        elif "probability" in a:
            out[qid] = round(float(a["probability"]), 3)
        else:
            out[qid] = a
    return out


def available() -> bool:
    try:
        with urllib.request.urlopen(ENDPOINT, timeout=5) as r:
            return bool(json.loads(r.read()).get("ready"))
    except (OSError, ValueError):
        return False
