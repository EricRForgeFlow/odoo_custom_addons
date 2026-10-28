"""Tune a demo database to the trained circuit board model (cv_quality_edge_demo):

    docker compose run --rm -T odoo odoo shell -d DB --no-http --stop-after-init < tune_db.py

(from the sandbox). The four classes of the model with their names and severities, none
allowed per board (VisA counts any of them as a defect), and the station counting the
detections the model was evaluated at (0.4) and sending uncertain ones to review.
"""

CLASSES = {
    "bent": ("Bent Pin", "major"),
    "melt": ("Melted Solder", "major"),
    "scratch": ("Scratch", "minor"),
    "missing": ("Missing Component", "critical"),
}

DefectClass = env["vision.defect.class"].with_context(active_test=False)  # noqa: F821 (odoo shell)
for code, (name, severity) in CLASSES.items():
    values = {"name": name, "severity": severity, "max_allowed": 0, "is_defect": True, "active": True}
    defect_class = DefectClass.search([("code", "=", code)])
    if defect_class:
        defect_class.write(values)
    else:
        DefectClass.create({**values, "code": code})
station = env.ref("vision_inspection.station_demo")  # noqa: F821
station.write({"min_confidence": 0.4, "review_confidence": 0.6})
env.cr.commit()  # noqa: F821
print("classes:", [(c.code, c.name, c.severity, c.max_allowed) for c in DefectClass.search([("code", "in", list(CLASSES))])])
print("station:", station.name, station.min_confidence, station.review_confidence)
