"""Prepare a database for the demo, on top of the module's demo data:

    docker compose run --rm -T odoo odoo shell -d vision_demo --no-http --stop-after-init < setup_db.py

(from the sandbox). Adds a second source sending Roboflow Inference results, and
sets the admin's time zone so the dates of the video are local.
"""

env.user.tz = "Europe/Madrid"  # noqa: F821 (odoo shell)
line1 = env.ref("vision_inspection.source_demo")  # noqa: F821
line1.write({"name": "Line 1 · RF-DETR detector", "token": "line1-demo-token"})
line1.station_ids.name = "Line 1 · Camera A"
line2 = env["vision.source"].search([("code", "=", "line2")])  # noqa: F821
if not line2:
    line2 = env["vision.source"].create({  # noqa: F821
        "name": "Line 2 · Roboflow Inference",
        "code": "line2",
        "adapter": "roboflow",
        "token": "line2-demo-token",
    })
    env["vision.station"].create({  # noqa: F821
        "name": "Line 2 · Camera B",
        "code": "line2-cam-b",
        "source_id": line2.id,
        "product_id": line1.station_ids.product_id.id,
    })
env.cr.commit()  # noqa: F821
print("sources:", env["vision.source"].search([]).mapped("name"))  # noqa: F821
