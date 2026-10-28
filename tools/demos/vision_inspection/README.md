# Vision Inspection video (phase 1)

A narrated video of `vision_inspection` and `vision_inspection_quality_control_oca`:
ForgeFlow slides (`slides.yaml`, made with [`../../forgeflow_reveal`](../../forgeflow_reveal))
open and close it, and the live demo in Odoo sits between them. It is recorded with
[odoo-demo-recorder](https://gitlab.forgeflow.io/forgeflow/odoo-demo-recorder) and
narrated offline by Kokoro.

| File | |
| --- | --- |
| `slides.yaml` | the slides, their narration (`say`) and which open and close the video (`video`) |
| `flow.py` | the recorder's flow: slides, then the live demo in Odoo, then the closing slides |
| `make_images.py` | draws the circuit boards and their defects (`images/`): no dataset, no camera, no licence |
| `edge.py` | sends a board's results to Odoo as a line camera would, in the generic or Roboflow format |
| `camera.html` | the line camera's console, shown in the video while it sends its results |
| `setup_db.py` | adds the second line (Roboflow) and the time zone to a database with the modules' demo data |
| `reset_db.sh` | recreates `vision_demo` from `vision_demo_base` before each run |

## Requirements

- The slide template `tools/forgeflow_reveal/`, which lives on `master` (it doesn't depend on
  the Odoo version). On a version branch, extract it from the repository root, untracked and
  ignored there: `git archive master tools/forgeflow_reveal | tar -x`.
- The `odoo-sandbox-20` sandbox running, with both modules mounted (`http://localhost:20069`).
- odoo-demo-recorder installed in its own checkout (`uv venv && uv pip install -e . pyyaml`),
  and Chromium for Playwright.
- The recorder narrates with Kokoro, built in. `DEMO_KOKORO_DIR` reuses a model already
  downloaded elsewhere (e.g. `~/.cache/aps-demo-media/kokoro`).

## Prepare the database (once)

From the sandbox:

```bash
docker compose run --rm odoo click-odoo-initdb -n vision_demo --demo --no-cache \
    -m vision_inspection_quality_control_oca
docker compose run --rm -T odoo odoo shell -d vision_demo --no-http --stop-after-init \
    < ../odoo_custom_addons/tools/demos/vision_inspection/setup_db.py
```

Then from this folder, the boards and a week of results from both lines, and the copy
every run starts from:

```bash
uv run --no-project --with pillow python make_images.py
python3 edge.py history
docker compose -f ../../../../odoo-sandbox-20/docker-compose.yml run --rm odoo \
    odoo db duplicate vision_demo vision_demo_base
```

## Record

```bash
uv run --no-project --with pyyaml python ../../forgeflow_reveal/deck.py slides.yaml deck/
./reset_db.sh
RECORDER=../../../../odoo-demo-recorder/.venv/bin/odoo-demo
$RECORDER validate --flow flow.py                         # screenshots in shots/
./reset_db.sh
$RECORDER record --flow flow.py --tts kokoro --voice af_heart   # out/demo.mp4
```

Validating also sends results and approves inspections, so reset the database before
recording. After a reset, the server's first connections to `vision_demo` fail; the
flow's login retries until they succeed.

The narration of the slides is their `say` in `slides.yaml`; that of the live demo is
`LIVE` in `flow.py`. `speakable()` spells out the acronyms Kokoro would read as words.
