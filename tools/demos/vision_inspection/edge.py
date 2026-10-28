"""What a camera on the line sends to Odoo, for the boards of images/.

    python edge.py history          # a week of results from both lines
    python edge.py send NAME LINE   # one board, as line1 (generic) or line2 (Roboflow)

Standard library only: the flow of the video imports it too.
"""

import base64
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ODOO = os.environ.get("DEMO_ODOO", "http://localhost:20069")
DB = os.environ.get("DEMO_DB", "vision_demo")
LINES = {
    "line1": {"token": "line1-demo-token", "station": "line1-cam-a"},
    "line2": {"token": "line2-demo-token", "station": "line2-cam-b"},
}
W, H = 960, 640
HISTORY = [
    "board_ok_1", "board_missing", "board_ok_2", "board_scratch_minor", "board_ok_3",
    "board_scratch_unsure", "board_bent", "board_two_scratches", "board_ok_4",
    "board_missing_bent", "board_scratch_faint", "board_bent_unsure",
]


def samples():
    with open(os.path.join(HERE, "images", "samples.json")) as handle:
        return json.load(handle)


def image_b64(name):
    with open(os.path.join(HERE, "images", f"{name}.jpg"), "rb") as handle:
        return base64.b64encode(handle.read()).decode()


def payload(name, line, captured_at=None, external_id=None):
    """The results of board ``name`` in the format of ``line``'s system."""
    detections = samples()[name]
    captured_at = (captured_at or datetime.datetime.now(datetime.UTC)).isoformat(timespec="seconds")
    common = {
        "station": LINES[line]["station"],
        "captured_at": captured_at,
        "lot": "LOT-2610",
    }
    if line == "line2":
        return {
            **common,
            "inference_id": external_id or f"{name}-{captured_at}",
            "model_id": "pcb-defects/3",
            "image": {"width": W, "height": H},
            "image_base64": image_b64(name),
            "predictions": [
                {
                    "x": round((d["bbox"]["x"] + d["bbox"]["w"] / 2) * W, 1),
                    "y": round((d["bbox"]["y"] + d["bbox"]["h"] / 2) * H, 1),
                    "width": round(d["bbox"]["w"] * W, 1),
                    "height": round(d["bbox"]["h"] * H, 1),
                    "confidence": d["confidence"],
                    "class": d["label"],
                }
                for d in detections
            ],
        }
    return {
        **common,
        "external_id": external_id or f"{name}-{captured_at}",
        "model": {"name": "rf-detr-nano", "version": "pcb-1"},
        "image": {"mime": "image/jpeg", "data": image_b64(name)},
        "detections": detections,
    }


def send(line, body):
    """POST the results; returns (status, response as a dict)."""
    request = urllib.request.Request(
        f"{ODOO}/vision_inspection/{line}/results",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LINES[line]['token']}",
            "X-Odoo-Database": DB,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def history():
    now = datetime.datetime.now(datetime.UTC)
    for index, name in enumerate(HISTORY):
        line = "line1" if index % 3 else "line2"
        captured_at = now - datetime.timedelta(days=6 - index // 2, hours=index % 2 * 3 + 1)
        print(name, line, *send(line, payload(name, line, captured_at, external_id=name)))


if __name__ == "__main__":
    if sys.argv[1:2] == ["history"]:
        history()
    elif sys.argv[1:2] == ["send"]:
        print(*send(sys.argv[3], payload(sys.argv[2], sys.argv[3])))
    else:
        sys.exit(__doc__)
