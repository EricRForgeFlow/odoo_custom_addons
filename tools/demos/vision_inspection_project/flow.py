"""The complete Vision Inspection video, for odoo-demo-recorder.

    odoo-demo validate --flow flow.py
    odoo-demo record   --flow flow.py           # Kokoro, af_heart

Slides (deck/, from slides.yaml) open and close it. Between them, the live demo on the
database DEMO_DB (vision_project, see README.md): the configuration, then the real
conveyor of cv_quality_edge_demo (RF-DETR Nano on this machine's CPU) sending test boards
to Odoo while line.html shows them, then an inspection, its OCA quality inspection and
the reports.
"""

import json
import os
import pathlib
import re
import subprocess

import yaml
from odoo_demo_recorder.browser import click, goto, pick_autocomplete, type_text

HERE = pathlib.Path(__file__).resolve().parent
EDGE = pathlib.Path(os.environ.get("CV_EDGE_DIR", HERE / "../../../../cv_quality_edge_demo")).resolve()
URL = os.environ.get("DEMO_ODOO", "http://localhost:20069")
DB = os.environ.get("DEMO_DB", "vision_project")
TOKEN = "line1-demo-token"
DECK = (HERE / "deck" / "index.html").as_uri() + "?record"
LINE = (HERE / "line.html").as_uri()
BOARDS, SEED = 8, 7  # with this seed: defective and good boards, among them bent pins and melted solder
SLIDES = yaml.safe_load((HERE / "slides.yaml").read_text())
ORDER = [slide["id"] for slide in SLIDES["slides"]]
SAY = {slide["id"]: slide["say"] if isinstance(slide["say"], list) else [slide["say"]] for slide in SLIDES["slides"]}


def speakable(text):
    """A line as the voice should read it: acronyms spelled out."""
    for word, spoken in (("RF-DETR", "R F DETR"), ("OCA", "O C A"), ("VisA", "Visa"), ("CPU", "C P U"),
                         ("GPU", "G P U"), ("ONNX", "O N N X")):
        text = re.sub(rf"\b{re.escape(word)}\b", spoken, text)
    return text


LIVE = {
    "kanban": "This is the Vision Inspection app. Here is a week of circuit boards, inspected on line one by the "
              "trained model. Each card is a board, with its image and its verdict.",
    "source": "Line one is a source: one vision system. It sends its results to this endpoint, with its own token.",
    "adapter": "It uses our generic format. Other systems, like Roboflow Inference, are read in their own format.",
    "classes": "The four labels of the model are defect classes here. A missing component is critical. None of "
               "them is allowed on a board.",
    "qc_test": "Now, quality control. In the O C A Quality Control app, we create a test for these boards.",
    "qc_questions": "One click adds a question for each defect class. The camera will answer it with the number "
                    "of defects it found.",
    "thresholds": "The camera's station counts detections from forty percent confidence, the threshold the model "
                  "was measured at. Below sixty percent, a board goes to review.",
    "station_qc": "And every board that doesn't pass gets a quality inspection, with our new test.",
    "line_intro": "Now, the line. This console shows the camera of line one. The model runs on this laptop's "
                  "processor.",
    "line_1": "A board passes under the camera. The model finds its defects, and the results go straight to Odoo.",
    "line_2": "Each box is a defect the model found, with how sure it is. On the right, the verdict Odoo answered.",
    "line_3": "The defective boards fail. The good ones pass.",
    "line_4": "Eight boards later, every one of them is an inspection in Odoo.",
    "inspection": "Here is one of them in Odoo: melted solder, in four places. The boxes the model drew are on the "
                  "image, colored by severity.",
    "detections": "Every detection is stored, with its class, its confidence and its position.",
    "qc_open": "Because the board failed, Odoo created a quality inspection.",
    "qc_form": "It uses our test, answered by the camera: four melted solder defects, where none is allowed. It "
               "now waits for a quality manager.",
    "qc_approve": "The manager confirms it. Quality failed, and the board is out.",
    "report": "And the reports. Here, the defects found each day, by class.",
    "pivot": "Or as a table, to see which defects come back most.",
}

NARRATION = {}
for slide_id in SLIDES["video"]["intro"]:
    for k, line in enumerate(SAY[slide_id]):
        NARRATION[f"{slide_id}.{k}"] = speakable(line)
NARRATION.update(LIVE)
for slide_id in SLIDES["video"]["outro"]:
    for k, line in enumerate(SAY[slide_id]):
        NARRATION[f"{slide_id}.{k}"] = speakable(line)


def login(page):
    """Authenticate without showing the login page: the video opens on the deck.

    Tried a few times: after reset_db.sh, the server's first connections to the
    recreated database fail.
    """
    for _attempt in range(10):
        response = page.request.post(
            f"{URL}/web/session/authenticate",
            data=json.dumps({"jsonrpc": "2.0", "params": {"db": DB, "login": "admin", "password": "admin"}}),
            headers={"Content-Type": "application/json"},
        )
        if response.ok and "error" not in response.json():
            break
        page.wait_for_timeout(1000)
    assert response.ok and "error" not in response.json(), response.text()
    page.goto(DECK, wait_until="domcontentloaded")
    page.wait_for_function("window.ForgeFlowDeck && Reveal.isReady()")
    page.wait_for_timeout(800)


def slides(page, beat, narrate, shot, ids):
    """The slides ``ids``: each step appears with its line."""
    if not page.url.startswith(DECK.split("?")[0]):
        page.goto(DECK, wait_until="domcontentloaded")
        page.wait_for_function("window.ForgeFlowDeck && Reveal.isReady()")
    for slide_id in ids:
        page.evaluate("i => ForgeFlowDeck.goTo(i)", ORDER.index(slide_id))
        page.wait_for_timeout(700)
        shot(f"slide_{slide_id}")
        beat(NARRATION[f"{slide_id}.0"])
        for k in range(1, len(SAY[slide_id])):
            with narrate(NARRATION[f"{slide_id}.{k}"]):
                page.evaluate("ForgeFlowDeck.step()")
                page.wait_for_timeout(600)
        if len(SAY[slide_id]) > 1:
            shot(f"slide_{slide_id}_done")


def action(name, record=None):
    return f"{URL}/odoo/action-{name}" + (f"/{record}" if record else "")


def open_row(page, text):
    click(page, page.locator(".o_data_row", has_text=text).first)
    page.wait_for_selector(".o_form_view")
    page.wait_for_timeout(600)


def start_conveyor():
    """The real conveyor, on the test boards, printing one JSON line per board."""
    env = {
        **os.environ,
        "CV_ODOO_URL": URL, "CV_ODOO_DB": DB, "CV_ODOO_SOURCE": "line1",
        "CV_ODOO_TOKEN": TOKEN, "CV_ODOO_STATION": "line1-cam-a",
    }
    env.pop("VIRTUAL_ENV", None)
    return subprocess.Popen(
        ["uv", "run", "--quiet", "cv-conveyor", "--jsonl", "--limit", str(BOARDS), "--seed", str(SEED),
         "--interval", "3"],
        cwd=EDGE, env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )


def show_boards(page, conveyor, until, events):
    """Put the boards the conveyor sends on the console, up to board number ``until``."""
    while not events or events[-1].get("number", 0) < until:
        line = conveyor.stdout.readline()
        if not line:
            raise RuntimeError("The conveyor stopped before sending all its boards")
        event = json.loads(line)
        if "summary" in event:
            break
        if event.get("verdict") is None:
            raise RuntimeError(f"Odoo refused {event['board']}: {event.get('error')}")
        event["annotated_url"] = pathlib.Path(event["annotated"]).as_uri()
        page.evaluate("e => addBoard(e)", event)
        events.append(event)


def run(page, beat, shot, narrate, pause):
    slides(page, beat, narrate, shot, SLIDES["video"]["intro"])

    # The app, with a week of boards from the model
    goto(page, action("vision_inspection.vision_inspection_action"), wait_selector=".o_kanban_record")
    shot("kanban")
    beat(NARRATION["kanban"])

    # Configuration: the source, the defect classes
    goto(page, action("vision_inspection.vision_source_action"), wait_selector=".o_data_row")
    open_row(page, "Line 1")
    shot("source")
    beat(NARRATION["source"], focus="div[name='endpoint_url']", label="Endpoint")
    beat(NARRATION["adapter"], focus="div[name='adapter']", label="Format")
    goto(page, action("vision_inspection.vision_defect_class_action"), wait_selector=".o_data_row")
    shot("classes")
    beat(NARRATION["classes"], focus=".o_list_table")

    # Quality control: a test whose questions are the defect classes, used by the station
    goto(page, action("quality_control_oca.action_qc_test", "new"), wait_selector="div[name='name'] input")
    with narrate(NARRATION["qc_test"], focus="div[name='name']"):
        type_text(page, "div[name='name'] input", "Circuit board visual inspection")
    with narrate(NARRATION["qc_questions"], focus="button[name='action_add_vision_questions']", label="Add questions"):
        click(page, "button[name='action_add_vision_questions']")
        page.wait_for_selector("div[name='test_lines'] .o_data_row")
        page.wait_for_timeout(1200)
    shot("qc_test")
    goto(page, action("vision_inspection.vision_station_action"), wait_selector=".o_data_row")
    open_row(page, "Line 1")
    beat(NARRATION["thresholds"], focus="div[name='min_confidence']", label="Minimum confidence")
    with narrate(NARRATION["station_qc"], focus="div[name='qc_test_id']", label="Quality test"):
        pick_autocomplete(page, "qc_test_id", "Circuit board", exact_text="Circuit board visual inspection")
        click(page, ".o_form_button_save")
        page.locator(".o_form_button_save").wait_for(state="hidden", timeout=10000)
    shot("station")

    # The line: the real model sends test boards to Odoo
    page.goto(LINE, wait_until="domcontentloaded")
    conveyor = start_conveyor()
    events = []
    try:
        beat(NARRATION["line_intro"])
        for key, until in (("line_1", 2), ("line_2", 4), ("line_3", 6), ("line_4", BOARDS)):
            with narrate(NARRATION[key]):
                show_boards(page, conveyor, until, events)
            shot(f"line_{until}")
        page.evaluate("() => setStatus('Line stopped')")
    finally:
        conveyor.wait(timeout=60)
    pause(1.0)

    # One of the failed boards in Odoo: the one with the most defects
    failed = max((e for e in events if e["verdict"] == "fail"), key=lambda e: len(e["detections"]))
    assert [d["label"] for d in failed["detections"]] == ["melt"] * 4, f"the narration describes {failed}"
    goto(page, action("vision_inspection.vision_inspection_action"), wait_selector=".o_kanban_record")
    click(page, page.locator(".o_kanban_record", has_text=failed["inspection"]).first)
    page.wait_for_selector(".o_vision_image_frame .o_vision_box")
    page.wait_for_timeout(1000)
    shot("inspection")
    beat(NARRATION["inspection"], focus=".o_vision_image_frame")
    with narrate(NARRATION["detections"]):
        click(page, page.locator(".o_notebook .nav-link", has_text="Detections").first)
        page.wait_for_timeout(600)
    shot("detections")
    with narrate(NARRATION["qc_open"], focus="button[name='action_view_qc_inspections']", label="Quality"):
        click(page, "button[name='action_view_qc_inspections']")
        page.wait_for_selector("button[name='action_approve']")
        page.wait_for_timeout(600)
    shot("qc_inspection")
    beat(NARRATION["qc_form"], focus="div[name='inspection_lines']")
    with narrate(NARRATION["qc_approve"], focus="button[name='action_approve']", label="Approve"):
        click(page, "button[name='action_approve']")
        page.wait_for_selector("button[name='action_approve']", state="hidden")
        page.wait_for_timeout(800)
    shot("qc_failed")

    # Reporting
    goto(page, action("vision_inspection.vision_detection_action_report"), wait_selector=".o_graph_renderer canvas")
    shot("report")
    beat(NARRATION["report"])
    with narrate(NARRATION["pivot"]):
        click(page, ".o_switch_view.o_pivot")
        page.wait_for_selector(".o_pivot table")
        page.wait_for_timeout(800)
    shot("pivot")

    slides(page, beat, narrate, shot, SLIDES["video"]["outro"])
    pause(1.5)
    return {"boards": [(e["board"], e["verdict"]) for e in events]}
