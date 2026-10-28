"""The Vision Inspection video (phase 1), for odoo-demo-recorder.

    odoo-demo validate --flow flow.py
    odoo-demo record   --flow flow.py --voice af_heart     # Kokoro (kokoro-say)

Slides of the deck (deck/, built from slides.yaml) open and close the video;
between them, the live demo in Odoo on the database DEMO_DB, prepared with
setup_db.py and `python edge.py history` (see README.md). The two boards sent
live go through edge.py, as a camera on the line would send them.
"""

import json
import os
import pathlib
import re
import sys

import yaml
from odoo_demo_recorder.browser import click, goto, pick_autocomplete, type_text

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import edge  # noqa: E402

URL = edge.ODOO
DB = edge.DB
DECK = (HERE / "deck" / "index.html").as_uri() + "?record"
CAMERA = (HERE / "camera.html").as_uri()
SLIDES = yaml.safe_load((HERE / "slides.yaml").read_text())
ORDER = [slide["id"] for slide in SLIDES["slides"]]
SAY = {slide["id"]: slide["say"] if isinstance(slide["say"], list) else [slide["say"]] for slide in SLIDES["slides"]}


def speakable(text):
    """A line as the voice should read it: acronyms spelled out."""
    for word, spoken in (("RF-DETR", "R F DETR"), ("OCA", "O C A"), ("HTTP", "H T T P"), ("VisA", "Visa")):
        text = re.sub(rf"\b{re.escape(word)}\b", spoken, text)
    return text


LIVE = {
    "kanban": "This is the Vision Inspection app. Each card is a board inspected by a camera on the line, "
              "with its image and its verdict. A week of results from two production lines is already here.",
    "source": "A source is one vision system. It has its own endpoint, and its own secret token.",
    "adapter": "And a format. This line sends our generic format. The second line runs Roboflow Inference, "
               "and Odoo reads its format as it is.",
    "stations": "Each camera of the line is a station, with its own confidence thresholds.",
    "classes": "The labels of the model are mapped to defect classes. A missing component is critical: "
               "none is allowed on a board. One small scratch is tolerated.",
    "qc_test": "Now, quality control. In the O C A Quality Control app, we create a test for our boards.",
    "qc_questions": "One click adds a question for each defect class. Its answer will be the number of defects "
                    "the camera found, and the allowed range comes from the class.",
    "station_qc": "Then we tell the first station to use this test, for every board that doesn't pass.",
    "camera1": "Back on the line. The camera has just captured this board. The model found a missing chip, "
               "a scratch, and maybe a bent pin, but only with thirty one percent confidence.",
    "send1": "The machine sends these results to Odoo, with its token.",
    "sent1": "Odoo answers at once: the board fails.",
    "inspection": "Here is the inspection in Odoo. The boxes are drawn over the image, colored by severity. "
                  "The bent pin is dashed: below the minimum confidence, it is kept but not counted.",
    "detections": "Every detection is stored, with its class, its confidence and its position.",
    "qc_open": "Because the board failed, Odoo created a quality inspection.",
    "qc_form": "It uses our test, and the camera answered its questions: one missing component, where none "
               "is allowed. The inspection now waits for the approval of a quality manager.",
    "qc_approve": "The manager confirms it. Quality failed, and the board is out.",
    "camera2": "Line two runs a different system, Roboflow Inference, with its own format. This board has "
               "one scratch, found with sixty four percent confidence.",
    "send2": "The same endpoint takes it.",
    "sent2": "One scratch is allowed, but the model wasn't sure enough: the board goes to review.",
    "review": "A person checks the image.",
    "mark_pass": "It is just a reflection. The operator marks the board as pass, and the change is tracked.",
    "report": "Finally, the reports. Here, the defects found each day, by class.",
    "pivot": "Or in a pivot table, to see which defects come back, and from which line.",
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

    Tried a few times: after reset_db.sh, the server's first connection to the
    recreated database fails once.
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
    page.locator(".o_data_row", has_text=text).first.click()
    page.wait_for_selector(".o_form_view")
    page.wait_for_timeout(800)


def camera(page, beat, narrate, shot, name, line, intro, send, sent):
    """The console of the camera of ``line`` sending board ``name`` to Odoo."""
    body = edge.payload(name, line)
    shown = json.loads(json.dumps(body))
    if "image_base64" in shown:
        shown["image_base64"] = shown["image_base64"][:24] + "…"
    else:
        shown["image"]["data"] = shown["image"]["data"][:24] + "…"
    page.goto(CAMERA, wait_until="domcontentloaded")
    page.evaluate("s => showSample(s)", {
        "title": "Line 1 · Camera A" if line == "line1" else "Line 2 · Camera B",
        "model": "RF-DETR Nano · pcb-1" if line == "line1" else "Roboflow Inference · pcb-defects/3",
        "adapter": "Generic format" if line == "line1" else "Roboflow format",
        "endpoint": f"/vision_inspection/{line}/results",
        "image": (HERE / "images" / f"{name}.jpg").as_uri(),
        "detections": edge.samples()[name],
        "payloadText": json.dumps(shown, indent=2, ensure_ascii=False),
    })
    page.wait_for_selector("#frame .box" if edge.samples()[name] else "#image")
    page.wait_for_timeout(600)
    shot(f"camera_{line}")
    beat(NARRATION[intro])
    with narrate(NARRATION[send], focus="#send", label="Send"):
        click(page, "#send")
        status, response = edge.send(line, body)
        page.wait_for_timeout(500)
        page.evaluate("([s, b]) => showResponse(s, b)", [status, response])
    assert status == 200, response
    beat(NARRATION[sent], focus="#response")
    return response


def open_latest_inspection(page):
    goto(page, action("vision_inspection.vision_inspection_action"), wait_selector=".o_kanban_record")
    page.locator(".o_kanban_record").first.click()
    page.wait_for_selector(".o_vision_image_frame .o_vision_box, .o_vision_image_frame img")
    page.wait_for_timeout(1200)


def run(page, beat, shot, narrate, pause):
    slides(page, beat, narrate, shot, SLIDES["video"]["intro"])

    # The app, with a week of history
    goto(page, action("vision_inspection.vision_inspection_action"), wait_selector=".o_kanban_record")
    shot("kanban")
    beat(NARRATION["kanban"])

    # Configuration: source, stations, defect classes
    goto(page, action("vision_inspection.vision_source_action"), wait_selector=".o_data_row")
    open_row(page, "Line 1")
    shot("source")
    beat(NARRATION["source"], focus="div[name='endpoint_url']", label="Endpoint")
    beat(NARRATION["adapter"], focus="div[name='adapter']", label="Format")
    beat(NARRATION["stations"], focus="div[name='station_ids']")
    goto(page, action("vision_inspection.vision_defect_class_action"), wait_selector=".o_data_row")
    shot("classes")
    beat(NARRATION["classes"], focus=".o_list_table")

    # Quality control: a test whose questions are the defect classes
    goto(page, action("quality_control_oca.action_qc_test", "new"), wait_selector="div[name='name'] input")
    with narrate(NARRATION["qc_test"], focus="div[name='name']"):
        type_text(page, "div[name='name'] input", "PCB visual inspection", delay=70)
    with narrate(NARRATION["qc_questions"], focus="button[name='action_add_vision_questions']", label="Add questions"):
        click(page, "button[name='action_add_vision_questions']")
        page.wait_for_selector("div[name='test_lines'] .o_data_row")
        page.wait_for_timeout(1500)
    shot("qc_test")
    goto(page, action("vision_inspection.vision_station_action"), wait_selector=".o_data_row")
    open_row(page, "Line 1")
    with narrate(NARRATION["station_qc"], focus="div[name='qc_test_id']", label="Quality test"):
        pick_autocomplete(page, "qc_test_id", "PCB visual", exact_text="PCB visual inspection")
        click(page, ".o_form_button_save")
        page.locator(".o_form_button_save").wait_for(state="hidden", timeout=10000)
    shot("station")

    # Line 1 sends a board with defects
    camera(page, beat, narrate, shot, "board_live_fail", "line1", "camera1", "send1", "sent1")
    open_latest_inspection(page)
    shot("inspection_fail")
    beat(NARRATION["inspection"], focus=".o_vision_image_frame")
    with narrate(NARRATION["detections"]):
        click(page, ".o_notebook .nav-link:has-text('Detections')")
        page.wait_for_timeout(800)
    shot("detections")
    with narrate(NARRATION["qc_open"], focus="button[name='action_view_qc_inspections']", label="Quality"):
        click(page, "button[name='action_view_qc_inspections']")
        page.wait_for_selector("button[name='action_approve']")
        page.wait_for_timeout(800)
    shot("qc_inspection")
    beat(NARRATION["qc_form"], focus="div[name='inspection_lines']")
    with narrate(NARRATION["qc_approve"], focus="button[name='action_approve']", label="Approve"):
        click(page, "button[name='action_approve']")
        page.wait_for_selector("button[name='action_approve']", state="hidden")
        page.wait_for_timeout(1000)
    shot("qc_failed")

    # Line 2 sends a doubtful board in Roboflow's format
    camera(page, beat, narrate, shot, "board_live_review", "line2", "camera2", "send2", "sent2")
    open_latest_inspection(page)
    shot("inspection_review")
    beat(NARRATION["review"], focus=".o_vision_image_frame")
    page.evaluate("document.querySelector('.o_content').scrollTo({top: 0, behavior: 'smooth'})")
    page.wait_for_timeout(700)
    with narrate(NARRATION["mark_pass"], focus="button[name='action_mark_pass']", label="Mark as Pass"):
        click(page, "button[name='action_mark_pass']")
        page.wait_for_selector(".o_widget_web_ribbon .text-bg-success, .ribbon:has-text('Pass')", timeout=10000)
        page.wait_for_timeout(1200)
    shot("marked_pass")

    # Reporting
    goto(page, action("vision_inspection.vision_detection_action_report"), wait_selector=".o_graph_renderer canvas")
    shot("report")
    beat(NARRATION["report"])
    with narrate(NARRATION["pivot"]):
        click(page, ".o_switch_view.o_pivot")
        page.wait_for_selector(".o_pivot table")
        page.wait_for_timeout(1000)
    shot("pivot")

    slides(page, beat, narrate, shot, SLIDES["video"]["outro"])
    pause(1.5)
    return {"slides": len(ORDER), "lines": len(NARRATION)}
