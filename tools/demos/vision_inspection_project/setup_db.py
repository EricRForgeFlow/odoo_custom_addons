"""Prepare the database of the project video, on top of the modules' demo data:

    docker compose run --rm -T odoo odoo shell -d vision_project --no-http --stop-after-init < setup_db.py

(from the sandbox), then tune_db.py. One line, whose camera runs the trained RF-DETR Nano
model of cv_quality_edge_demo; the demo inspections without images are removed, as the
history comes from the real model (seed_history.py).
"""

env.user.tz = "Europe/Madrid"  # noqa: F821 (odoo shell)
source = env.ref("vision_inspection.source_demo")  # noqa: F821
source.write({"name": "Line 1 · RF-DETR Nano", "token": "line1-demo-token"})
source.station_ids.name = "Line 1 · Camera A"
env["vision.inspection"].search([("image", "=", False)]).unlink()  # noqa: F821
env.ref("vision_inspection.product_demo_pcb").name = "Sensor Circuit Board"  # noqa: F821
env.cr.commit()  # noqa: F821
print("source:", source.name, "| inspections left:", env["vision.inspection"].search_count([]))  # noqa: F821
