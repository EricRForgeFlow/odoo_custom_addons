"""A week of inspections from the trained model, so the reports have a history:

    uv run --project ../../../../cv_quality_edge_demo python seed_history.py

The validation boards of cv_quality_edge_demo go through its detector and are sent to
Odoo with capture times spread over the last six days. The test boards stay for the live
part of the video.
"""

import datetime
import os
import random
import sys

from PIL import Image

from cv_quality_edge import odoo
from cv_quality_edge.detector import Detector
from cv_quality_edge.evaluate import load_split

EDGE = os.environ.get("CV_EDGE_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "../../../../cv_quality_edge_demo"))
URL = os.environ.get("DEMO_ODOO", "http://localhost:20069")
DB = os.environ.get("DEMO_DB", "vision_project")


def main():
    detector = Detector(os.path.join(EDGE, "models", "pcb_nano.pth"), threshold=0.4)
    client = odoo.Odoo(URL, "line1", "line1-demo-token", db=DB)
    boards = load_split(os.path.join(EDGE, "dataset"), "valid")
    random.Random(11).shuffle(boards)
    now = datetime.datetime.now(datetime.UTC).replace(minute=0, second=0, microsecond=0)
    verdicts = {}
    for index, (path, _boxes) in enumerate(boards):
        name = os.path.basename(path)
        captured_at = now - datetime.timedelta(days=6 - index * 6 // len(boards), hours=8 - index % 8)
        image = Image.open(path)
        status, response = client.send(odoo.payload(
            image,
            detector.detect(image),
            external_id=f"history-{name}",
            station="line1-cam-a",
            product_code="PCB-001",
            lot=name.split("_")[0].upper(),
            model_version=detector.version,
            captured_at=captured_at,
        ))
        if status != 200:
            sys.exit(f"{name}: Odoo answered {status} {response}")
        verdicts[response["verdict"]] = verdicts.get(response["verdict"], 0) + 1
        print(f"\r{index + 1}/{len(boards)} sent", end="", flush=True)
    print(f"\nverdicts: {verdicts}")


if __name__ == "__main__":
    main()
