# Vision Inspection video (complete project)

The narrated video of the whole project: the Odoo modules `vision_inspection` and
`vision_inspection_quality_control_oca` (phase 1), fed by the RF-DETR circuit board
detector of [cv_quality_edge_demo](https://github.com/EricRForgeFlow/cv_quality_edge_demo)
(phase 2). ForgeFlow slides open and close it; in between, the live demo, where the real
model runs on this machine's CPU and sends test boards to Odoo while the video shows them.

| File | |
| --- | --- |
| `slides.yaml` | the slides, their narration (`say`), and which open and close the video (`video`) |
| `flow.py` | the recorder's flow: slides, configuration, live line, inspection, OCA approval, reports, slides |
| `line.html` | the console of the line, filled by the flow with each board the conveyor sends |
| `setup_db.py` | prepares a database with the modules' demo data: one line, no imageless inspections |
| `tune_db.py` | the defect classes and thresholds of the trained model (also for other demo databases) |
| `seed_history.py` | a week of inspections from the model, on the validation boards |
| `reset_db.sh` | recreates `vision_project` from `vision_project_base` and warms the server up |

The video for phase 1 alone, with drawn boards, is in [`../vision_inspection`](../vision_inspection).

## Requirements

- The `odoo-sandbox-20` sandbox running, with both modules mounted (`http://localhost:20069`).
- `../cv_quality_edge_demo` next to this repository, set up (`uv sync`, `uv run cv-prepare`),
  with the trained weights in `models/pcb_nano.pth` (its Colab notebook makes them).
- [odoo-demo-recorder](https://gitlab.forgeflow.io/forgeflow/odoo-demo-recorder) in its
  own checkout (`uv venv && uv pip install -e . pyyaml`). It narrates with Kokoro; set
  `DEMO_KOKORO_DIR` to reuse a downloaded model.

## Prepare the database (once)

From the sandbox:

```bash
docker compose run --rm odoo click-odoo-initdb -n vision_project --demo --no-cache \
    -m vision_inspection_quality_control_oca
for f in setup_db.py tune_db.py; do
    docker compose run --rm -T odoo odoo shell -d vision_project --no-http --stop-after-init \
        < ../odoo_custom_addons/tools/demos/vision_inspection_project/$f
done
```

Then from this folder, the history and the copy every run starts from:

```bash
uv run --project ../../../../cv_quality_edge_demo python seed_history.py
docker compose -f ../../../../odoo-sandbox-20/docker-compose.yml run --rm odoo \
    odoo db duplicate vision_project vision_project_base
```

## Record

```bash
uv run --no-project --with pyyaml python ../../forgeflow_reveal/deck.py slides.yaml deck/
RECORDER=../../../../odoo-demo-recorder/.venv/bin/odoo-demo
./reset_db.sh && $RECORDER validate --flow flow.py        # screenshots in shots/
./reset_db.sh && $RECORDER record --flow flow.py --size 1600x900   # out/demo.mp4, 16:9
```

`--size 1600x900` records in 16:9, the shape of the slides (the recorder's default window
is 1440x900, 16:10, which puts bands around them).

Both runs send boards and approve an inspection, so reset before each. The live part
uses a fixed shuffle of the test boards (`SEED` in `flow.py`), so the narration can say
what the opened board has; the flow checks it and stops if the model's answer changed.

If a mounted module's files went missing in the container (after a rebase or a branch
switch removed and recreated its folder, the bind mount still points to the old one),
`docker compose restart odoo` in the sandbox mounts it again.
