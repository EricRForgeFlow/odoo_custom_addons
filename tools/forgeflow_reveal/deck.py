#!/usr/bin/env python3
# Copyright 2026 ForgeFlow S.L. (https://www.forgeflow.com)
# License OPL-1.0 (https://www.odoo.com/documentation/master/legal/licenses.html).
# ruff: noqa: E501 (markup and drawing coordinates)
"""A ForgeFlow reveal.js deck from a list of slides.

    python deck.py slides.yaml OUT_DIR

writes OUT_DIR/index.html with the template beside it (OUT_DIR/forgeflow/:
theme, layouts, diagrams, reveal.js and the Inter font, all offline). Only
needs pyyaml for the command line; ``render(title, slides)`` takes the slides
as dicts.

The slides file::

    title: Name of the deck
    footer: "© Copyright 2026 Forgeflow S.L. (www.forgeflow.com)"   # optional
    slides:
      - id: cover
        kind: cover           # one of KINDS
        title: ...
        say: ...              # the narration: the speaker notes (a list: one
                              # item per animation step, see below)
        ...                   # the fields of its kind; a diagram's texts in
                              # ``labels`` (English defaults below)

Animation: most kinds build up in steps (reveal fragments): cards one by one,
the tasks of a chain, the dots of a fever chart... (``ForgeFlowDeck.steps(i)``
counts them in the browser). A list ``say`` gives the narration of each step:
item 0 on entry, item k with step k (a presenter reads it in the notes; a
recording says it).
"""

import html
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FOOTER = "© Copyright 2026 Forgeflow S.L. (www.forgeflow.com)"
# The template files a deck needs, copied into OUT_DIR/forgeflow
FILES = [
    "forgeflow.css",
    "layouts.css",
    "components.css",
    "forgeflow.js",
    "assets",
    "vendor",
]
PX = 192  # pixels per inch: the diagrams keep the geometry of a 10 x 5.625 in slide


def esc(value):
    return html.escape(str(value if value is not None else ""))


def lines(value):
    """A text with line breaks (``\\n``) or a list of paragraphs, as HTML."""
    if isinstance(value, list):
        return "".join(f"<p>{esc(v)}</p>" for v in value)
    return "<br/>".join(esc(part) for part in str(value or "").split("\n"))


def lab(d, key, default):
    return (d.get("labels") or {}).get(key, default)


def frag(effect="fade-up", index=None):
    """The classes of an animation step."""
    return f' class="fragment {effect}"' + (
        f' data-fragment-index="{index}"' if index is not None else ""
    )


def merge(cls, attrs):
    """The class of an element and its other attributes, with the classes of
    ``attrs`` (an animation step: ``frag()``) added to ``cls``."""
    match = re.search(r' class="([^"]*)"', attrs)
    if not match:
        return cls, attrs
    return f"{cls} {match.group(1)}", attrs.replace(match.group(0), "")


def box(x, y, w, h, inner="", cls="", style="", attrs=""):
    """An absolutely placed box, in inches of the 10 x 5.625 in slide."""
    cls, attrs = merge(f"ff-box {cls}", attrs)
    return (
        f'<div class="{cls}"{attrs} style="left:{x * PX:.0f}px;top:{y * PX:.0f}px;'
        f'width:{w * PX:.0f}px;height:{h * PX:.0f}px;{style}">{inner}</div>'
    )


def bar(x, y, w, h, color, content="", size=14, cls="", attrs=""):
    return box(
        x,
        y,
        w,
        h,
        f"<span>{lines(content)}</span>",
        f"ff-bar ff-fit ff-{color} {cls}",
        f"font-size:{size * 2.667:.0f}px;",
        attrs,
    )


def hatched(x, y, w, h, content="", size=12, cls="", attrs=""):
    return box(
        x,
        y,
        w,
        h,
        f"<span>{lines(content)}</span>",
        f"ff-hatched ff-fit {cls}",
        f"font-size:{size * 2.667:.0f}px;",
        attrs,
    )


def text(x, y, w, h, content, size=16, cls="", attrs=""):
    return box(
        x,
        y,
        w,
        h,
        lines(content),
        f"ff-text ff-fit {cls}",
        f"font-size:{size * 2.667:.0f}px;",
        attrs,
    )


def dot(x, y, d, color, content="", size=14, attrs=""):
    return box(
        x,
        y,
        d,
        d,
        esc(content),
        f"ff-dot ff-{color}",
        f"font-size:{size * 2.667:.0f}px;",
        attrs,
    )


def arrow(x1, y1, x2, y2, attrs="", color="grey"):
    """An arrow in an SVG over the whole slide."""
    cls, attrs = merge(f"ff-arrow ff-stroke-{color}", attrs)
    return (
        f'<svg class="{cls}"{attrs} viewBox="0 0 1920 1080">'
        f'<line x1="{x1 * PX:.0f}" y1="{y1 * PX:.0f}" x2="{x2 * PX:.0f}" y2="{y2 * PX:.0f}" '
        'marker-end="url(#ff-head)"/></svg>'
    )


def footer_line(d, default, y=None):
    content = d.get("footer", default)
    if not content:
        return ""
    top = f' style="top:{y * PX:.0f}px"' if y else ""
    return f'<div class="ff-takeaway ff-fit"{top}>{esc(content)}</div>'


# --------------------------------------------------------------------------
# Kinds: each returns (classes of the section, inner HTML)
# --------------------------------------------------------------------------


def kind_cover(d):
    return "ff-dark ff-cover", (
        '<div class="ff-wrap"><img class="ff-cover-logo" src="forgeflow/assets/forgeflow-logo-white.png" alt="ForgeFlow"/>'
        f'<h1 class="ff-fit">{esc(d["title"])}</h1>'
        f'<p class="ff-subtitle ff-fit">{esc(d.get("subtitle", ""))}</p></div>'
    )


def kind_section(d):
    return "ff-dark ff-section", (
        f'<div class="ff-wrap"><div class="ff-section-number">{esc(d.get("number", ""))}</div>'
        f'<div class="ff-section-text"><h1 class="ff-fit">{esc(d["title"])}</h1>'
        f'<p class="ff-subtitle ff-fit">{esc(d.get("subtitle", ""))}</p></div></div>'
    )


def kind_summary(d):
    points = "".join(f"<li{frag()}>{esc(p)}</li>" for p in d.get("points", []))
    return "ff-dark ff-summary", (
        f'<div class="ff-wrap"><h1 class="ff-fit">{esc(d["title"])}</h1><ul>{points}</ul></div>'
    )


def numbered(items, color_of, cls):
    rows = []
    for i, (head, body) in enumerate(items):
        rows.append(
            f'<li{frag()}><span class="ff-num ff-{color_of(i)}">{i + 1}</span>'
            f'<div><b class="ff-fit">{esc(head)}</b><span class="ff-sub ff-fit">{esc(body)}</span></div></li>'
        )
    return f'<ol class="{cls}">{"".join(rows)}</ol>'


def kind_cards(d):
    cards = "".join(
        f'<div{frag()}><div class="ff-card"><span class="ff-num ff-{"blue" if i % 2 == 0 else "coral"}">{esc(mark)}</span>'
        f'<div><b class="ff-fit">{esc(head)}</b><span class="ff-sub ff-fit">{esc(body)}</span></div></div></div>'
        for i, (head, body, mark) in enumerate(d["cards"])
    )
    return "ff-content", f'<div class="ff-cards">{cards}</div>' + footer_line(d, "")


def kind_people(d):
    people = []
    for i, (name, role) in enumerate(d["people"]):
        initials = "".join(part[0] for part in name.split()[:2])
        people.append(
            f'<div class="ff-person"><span class="ff-num ff-{"blue" if i % 2 == 0 else "coral"}">{esc(initials)}</span>'
            f'<div><b class="ff-fit">{esc(name)}</b><span class="ff-sub ff-fit">{esc(role)}</span></div></div>'
        )
    # two columns of four, each column one step
    columns = [people[:4], people[4:]]
    return "ff-content", '<div class="ff-people">' + "".join(
        f"<div{frag() if i else ''}>{''.join(c)}</div>"
        for i, c in enumerate(columns)
        if c
    ) + "</div>"


def kind_story(d):
    return "ff-content", numbered(
        d["items"], lambda i: "blue" if i < 3 else "coral", "ff-list ff-story"
    )


def kind_agenda(d):
    return "ff-content", numbered(d["items"], lambda i: "blue", "ff-list ff-agenda")


def kind_statement(d):
    return "ff-content", numbered(
        d["points"], lambda i: "blue" if i < 2 else "coral", "ff-list ff-statement"
    )


def kind_flow(d):
    steps = "".join(
        f'<div{frag()}><div class="ff-chevron ff-{"blue" if i % 2 == 0 else "lavender"}{" ff-first" if i == 0 else ""}">'
        f'<span>{esc(head)}</span></div><p class="ff-fit">{esc(body)}</p></div>'
        for i, (head, body) in enumerate(d["steps"])
    )
    return "ff-content", f'<div class="ff-flow">{steps}</div>' + footer_line(d, "")


def kind_promise(d):
    states = "".join(
        f'<div class="ff-state"><span class="ff-dot ff-{color}"></span><b>{esc(name)}</b></div>'
        for name, color in (
            (lab(d, "on_time", "On time"), "green-dot"),
            (lab(d, "at_risk", "At risk"), "yellow-dot"),
            (lab(d, "late", "Late"), "red-dot"),
        )
    )
    return "ff-content ff-diagram", (
        bar(0.5, 1.55, 2.3, 0.85, "blue", lab(d, "order", "Order\nconfirmed"), 15)
        + arrow(2.85, 1.98, 3.55, 1.98, frag("fade-in", 1))
        + bar(
            3.6,
            1.55,
            2.6,
            0.85,
            "coral",
            lab(d, "promise", "Committed date\n= promise"),
            15,
            attrs=frag("pop", 1),
        )
        + arrow(6.25, 1.98, 6.95, 1.98, frag("fade-in", 2))
        + bar(
            7.0,
            1.55,
            2.5,
            0.85,
            "navy",
            lab(d, "watch", "The system\nwatches it"),
            15,
            attrs=frag("pop", 2),
        )
        + '<div class="ff-states fragment fade-up" data-fragment-index="3">'
        + states
        + "</div>"
        + footer_line(d, "Each replan checks every promise.", 4.2)
    )


def kind_capacity(d):
    return "ff-content ff-diagram", (
        text(0.5, 1.4, 2.2, 0.4, lab(d, "resource", "Workstation"), 15, "ff-strong")
        + '<div class="ff-rule-line" style="left:96px;top:490px;width:1709px"></div>'
        + bar(2.6, 1.7, 3.0, 0.75, "blue", lab(d, "first", "First customer's work"), 14)
        + bar(
            5.7,
            1.7,
            3.0,
            0.75,
            "coral",
            lab(d, "second", "Second customer's work"),
            14,
            attrs=frag("slide-from-left", 1),
        )
        + hatched(
            2.6,
            2.75,
            3.0,
            0.6,
            lab(d, "waits", "The second one waits its turn"),
            13,
            attrs=frag("grow-x", 1),
        )
        + text(
            0.5,
            3.75,
            9.0,
            0.5,
            lab(d, "rule", "One workstation, one job at a time. Like every crew."),
            17,
            "ff-navy",
            frag("fade-up", 2),
        )
        + footer_line(d, "A date without capacity is only a wish.", 4.3)
    )


def kind_ctp(d):
    return "ff-content ff-diagram", (
        box(
            0.5,
            1.5,
            2.6,
            1.6,
            f"<b>{esc(lab(d, 'plan', 'Real plan'))}</b><span>{esc(lab(d, 'plan_body', 'Committed work, materials and calendars'))}</span>",
            "ff-panel ff-fit ff-tint",
        )
        + box(3.2, 2.0, 0.5, 0.6, "+", "ff-plus", attrs=frag("fade-in", 1))
        + box(
            3.75,
            1.5,
            2.3,
            1.6,
            f"<b>{esc(lab(d, 'new', 'New order'))}</b><span>{esc(lab(d, 'new_body', 'Simulated, nothing reserved'))}</span>",
            "ff-panel ff-fit ff-lavender ff-dashed",
            attrs=frag("pop", 1),
        )
        + arrow(6.15, 2.3, 6.85, 2.3, frag("fade-in", 2), "blue")
        + bar(
            6.95,
            1.5,
            2.5,
            1.6,
            "blue",
            lab(d, "result", "Delivery date\nand its reasons"),
            16,
            attrs=frag("pop", 2),
        )
        + footer_line(
            d, "A date that can be kept without delaying another customer.", 3.75
        )
    )


def chain(d, default=None):
    return lab(
        d,
        "chain",
        default
        or [
            ["Survey", 1.2],
            ["Drawings", 1.5],
            ["Approval", 2.4],
            ["Installation", 1.8],
            ["Handover", 1.3],
        ],
    )


def draw_chain(d, y, dim_branch=False, slack=False, step_tasks=True):
    """The tasks of the example project, one step each (``step_tasks``), and
    the branch in parallel to the third task, joining the fourth."""
    parts, xs, x = [], [], 0.5
    for i, (name, w) in enumerate(chain(d)):
        attrs = frag("slide-from-left", i) if step_tasks and i else ""
        parts.append(bar(x, y, w, 0.75, "coral", name, 15, attrs=attrs))
        xs.append((x, x + w))
        x += w + 0.2
    tasks = len(xs) - 1 if step_tasks else 0
    bx0, inst = xs[2][0], xs[3][0]
    branch = lab(d, "branch", "Graphics")
    parts.append(
        bar(
            bx0,
            y + 1.25,
            1.15,
            0.65,
            "lavender" if dim_branch else "blue",
            branch,
            14,
            attrs=frag("pop", tasks + 1),
        )
    )
    if slack:
        parts.append(
            hatched(
                bx0 + 1.2,
                y + 1.25,
                inst - bx0 - 1.25,
                0.65,
                lab(d, "float", "float"),
                13,
                attrs=frag("grow-x", tasks + 2),
            )
        )
    else:
        parts.append(
            f"<div{frag('fade-in', tasks + 1)}>"
            + box(bx0 + 1.15, y + 1.57, inst - 0.02 - bx0 - 1.15, 0.02, "", "ff-link")
            + "</div>"
        )
    parts.append(
        arrow(inst - 0.02, y + 1.58, inst + 0.3, y + 0.8, frag("fade-in", tasks + 1))
    )
    return "".join(parts), tasks + (2 if slack else 1)


def definition(d, term, body, color, index):
    return (
        f'<div class="ff-definition ff-fit"{frag("fade-up", index)}><b class="ff-{color}-text">{esc(lab(d, "term", term))}</b>'
        f"{esc(lab(d, 'definition', body))}</div>"
    )


def kind_critical(d):
    drawn, last = draw_chain(d, 1.5)
    return "ff-content ff-diagram ff-critical", (
        drawn
        + definition(
            d,
            "Critical path: ",
            "the longest chain; each task waits for the one before.",
            "coral",
            last + 1,
        )
        + footer_line(
            d, "If a task on the critical path is late, the project is late.", 4.35
        )
    )


def kind_float(d):
    drawn, last = draw_chain(d, 1.5, dim_branch=True, slack=True, step_tasks=False)
    return "ff-content ff-diagram", (
        drawn
        + definition(
            d,
            "Float: ",
            "how late a task can be without moving the end.",
            "blue",
            last + 1,
        )
        + footer_line(d, "The graphics have float; the installation has none.", 4.35)
    )


def kind_safety(d):
    parts, y = [], 1.5
    for i, name in enumerate(lab(d, "tasks", ["Drawings", "Approval", "Installation"])):
        parts.append(text(0.5, y + 0.12, 1.5, 0.4, name, 15, "ff-strong"))
        parts.append(bar(2.1, y, 2.6, 0.6, "coral", lab(d, "work", "work: 5 days"), 13))
        parts.append(
            hatched(
                4.75,
                y,
                2.6,
                0.6,
                lab(d, "margin", "margin: 5 days"),
                13,
                attrs=frag("grow-x", i + 1),
            )
        )
        y += 0.82
    parts.append(
        text(
            7.6,
            1.6,
            1.9,
            1.9,
            lab(d, "note", "Estimated with a 'just in case' inside"),
            15,
            attrs=frag("fade-up", 4),
        )
    )
    return "ff-content ff-diagram", "".join(parts) + footer_line(
        d, "Estimating with a margin is normal and sensible.", 4.15
    )


def kind_parkinson(d):
    cards = lab(
        d,
        "cards",
        [
            ["Work stretches", "Given ten days, ten days are used."],
            ["Late starts", "Like the student, the night before the exam."],
            ["Lost gains", "Delays pass to the next task; early finishes don't."],
        ],
    )
    inner = "".join(
        f'<div{frag()}><div class="ff-card ff-column"><span class="ff-num ff-coral">{i + 1}</span>'
        f'<b class="ff-fit">{esc(head)}</b><span class="ff-sub ff-fit">{esc(body)}</span></div></div>'
        for i, (head, body) in enumerate(cards)
    )
    return "ff-content", f'<div class="ff-columns">{inner}</div>' + footer_line(
        d, "With all that margin, the project is late anyway.", 4.1
    )


def kind_pool(d):
    unit, parts = 0.165, []
    parts.append(
        text(0.5, 1.53, 1.3, 0.4, lab(d, "before", "Before"), 16, "ff-grey ff-strong")
    )
    x = 1.55
    for _ in range(4):
        parts.append(bar(x, 1.45, 5 * unit - 0.03, 0.6, "coral", "5", 13))
        parts.append(hatched(x + 5 * unit, 1.45, 5 * unit - 0.03, 0.6, "5", 13))
        x += 10 * unit
    parts.append(
        text(
            x + 0.12, 1.53, 1.1, 0.4, lab(d, "before_total", "40 days"), 16, "ff-strong"
        )
    )
    now = [
        text(0.5, 2.48, 1.3, 0.4, lab(d, "now", "Now"), 16, "ff-blue-text ff-strong")
    ]
    x = 1.55
    for _ in range(4):
        now.append(bar(x, 2.4, 5 * unit - 0.03, 0.6, "coral", "5", 13))
        x += 5 * unit
    parts.append(f"<div{frag('fade-in', 1)}>" + "".join(now) + "</div>")
    parts.append(
        bar(
            x,
            2.4,
            10 * unit - 0.03,
            0.6,
            "blue",
            lab(d, "buffer", "buffer 10"),
            13,
            attrs=frag("grow-x", 2),
        )
    )
    parts.append(
        text(
            x + 10 * unit + 0.12,
            2.48,
            1.2,
            0.4,
            lab(d, "now_total", "30 days"),
            16,
            "ff-blue-text ff-strong",
            frag("fade-in", 2),
        )
    )
    explanation = lab(
        d,
        "explanation",
        [
            "Each task with just its work: the plan uses half.",
            "Half of the margin taken off goes to a shared buffer, at the end.",
        ],
    )
    parts.append(text(0.5, 3.3, 9.0, 1.0, explanation, 16, attrs=frag("fade-up", 3)))
    return "ff-content ff-diagram", "".join(parts) + footer_line(
        d, "Shorter and better protected: not everything goes wrong at once.", 4.4
    )


def kind_feeding(d):
    parts, xs, x = [], [], 0.5
    for name, w in chain(
        d,
        [
            ["Drawings", 1.35],
            ["Approval", 2.6],
            ["Installation", 1.6],
            ["Handover", 1.15],
        ],
    ):
        parts.append(bar(x, 1.5, w, 0.75, "coral", name, 15))
        xs.append((x, x + w))
        x += w + 0.15
    parts.append(
        bar(
            x,
            1.5,
            9.5 - x,
            0.75,
            "blue",
            lab(d, "project_buffer", "Project\nbuffer"),
            12,
        )
    )
    bx, inst = xs[1][0], xs[2][0]
    parts.append(
        bar(
            bx,
            2.75,
            1.25,
            0.7,
            "blue",
            lab(d, "branch", "Graphics"),
            14,
            attrs=frag("pop", 1),
        )
    )
    parts.append(
        hatched(
            bx + 1.3,
            2.75,
            inst - bx - 1.35,
            0.7,
            lab(d, "feeding_buffer", "feeding\nbuffer"),
            12,
            attrs=frag("grow-x", 2),
        )
    )
    parts.append(arrow(inst - 0.03, 3.1, inst + 0.3, 2.3, frag("fade-in", 2)))
    parts.append(
        text(
            0.5,
            3.75,
            9.0,
            0.5,
            lab(
                d,
                "explanation",
                "The branch finishes before it joins the chain, with its own margin.",
            ),
            16,
            attrs=frag("fade-up", 3),
        )
    )
    return "ff-content ff-diagram", "".join(parts) + footer_line(
        d, "If the graphics are late, the installation does not move.", 4.35
    )


def kind_fever(d):
    x0, y0, w, h = 1.3, 1.35, 4.6, 2.9

    def pt(cx, cy):
        return ((x0 + w * cx / 100.0) * PX, (y0 + h * (1 - cy / 110.0)) * PX)

    def poly(points, cls):
        coords = " ".join(f"{px:.0f},{py:.0f}" for px, py in (pt(*p) for p in points))
        return f'<polygon class="{cls}" points="{coords}"/>'

    zones = (
        poly([(0, 0), (100, 0), (100, 60), (0, 0)], "ff-zone-green")
        + poly([(0, 0), (100, 60), (100, 90), (0, 20)], "ff-zone-yellow")
        + poly([(0, 20), (100, 90), (100, 110), (0, 110)], "ff-zone-red")
    )
    ox, oy = x0 * PX, (y0 + h) * PX
    axes = (
        f'<line class="ff-axis" x1="{ox:.0f}" y1="{oy:.0f}" x2="{ox + w * PX:.0f}" y2="{oy:.0f}"/>'
        f'<line class="ff-axis" x1="{ox:.0f}" y1="{y0 * PX:.0f}" x2="{ox:.0f}" y2="{oy:.0f}"/>'
    )
    dots, trail = [], []
    previous = pt(0, 0)
    for i, ((cx, cy), color) in enumerate(
        (((23, 11), "green"), ((66, 59), "yellow"), ((67, 78), "red")), start=1
    ):
        px, py = pt(cx, cy)
        trail.append(
            f'<line class="ff-trail fragment fade-in" data-fragment-index="{i}" x1="{previous[0]:.0f}" y1="{previous[1]:.0f}" x2="{px:.0f}" y2="{py:.0f}"/>'
        )
        dots.append(
            f'<circle class="ff-point ff-{color}-fill fragment pop" data-fragment-index="{i}" cx="{px:.0f}" cy="{py:.0f}" r="26"/>'
        )
        previous = (px, py)
    svg = f'<svg class="ff-chart" viewBox="0 0 1920 1080">{zones}{axes}{"".join(trail)}{"".join(dots)}</svg>'
    explanation = lab(
        d,
        "explanation",
        [
            "A healthy project uses buffer at the pace it progresses.",
            "If it uses it faster, it climbs to the red: it has a fever.",
        ],
    )
    return "ff-content ff-diagram", (
        svg
        + text(
            x0,
            y0 + h + 0.08,
            w,
            0.35,
            lab(d, "x_axis", "Chain done →"),
            13,
            "ff-center",
        )
        + text(
            0.25, y0 + 0.9, 1.0, 1.2, lab(d, "y_axis", "Buffer used ↑"), 13, "ff-center"
        )
        + text(6.3, 1.5, 3.2, 2.6, explanation, 16, attrs=frag("fade-up", 4))
    )


def kind_zones(d):
    cards = [
        (
            lab(d, "green", "Green"),
            lab(d, "green_body", "All fine.\nNothing to do."),
            "green",
        ),
        (
            lab(d, "yellow", "Yellow"),
            lab(d, "yellow_body", "Prepare a plan,\njust in case."),
            "yellow",
        ),
        (
            lab(d, "red", "Red"),
            lab(d, "red_body", "Act now: overtime,\nanother person, another order."),
            "red",
        ),
    ]
    inner = "".join(
        f'<div{frag()}><div class="ff-card ff-column ff-zone-{color}"><span class="ff-dot ff-{color}-dot"></span>'
        f'<b class="ff-fit">{esc(head)}</b><span class="ff-sub ff-fit">{lines(body)}</span></div></div>'
        for head, body, color in cards
    )
    return "ff-content", f'<div class="ff-columns">{inner}</div>' + footer_line(
        d, "The project manager steps in only when needed.", 4.2
    )


def kind_priority(d):
    def project(y, zone, color, name, note):
        return box(
            0.5,
            y,
            3.2,
            0.8,
            f'<span class="ff-dot ff-{color}-dot"></span><div><b class="ff-fit">{esc(name)}</b><span class="ff-sub ff-fit">{esc(note)}</span></div>',
            f"ff-project ff-zone-{zone}",
        )

    return "ff-content ff-diagram", (
        project(
            1.45,
            "red",
            "red",
            lab(d, "red_project", "Project A"),
            lab(d, "red_note", "buffer nearly used up"),
        )
        + project(
            2.55,
            "green",
            "green",
            lab(d, "green_project", "Project B"),
            lab(d, "green_note", "buffer almost intact"),
        )
        + arrow(3.8, 1.85, 4.6, 2.3, frag("fade-in", 1))
        + arrow(3.8, 2.95, 4.6, 2.5, frag("fade-in", 1))
        + bar(
            4.7,
            1.95,
            1.7,
            0.9,
            "blue",
            lab(d, "shared", "Shared\nteam"),
            13,
            attrs=frag("pop", 1),
        )
        + arrow(6.5, 2.4, 7.0, 2.4, frag("fade-in", 2))
        + bar(
            7.1,
            1.55,
            2.3,
            0.6,
            "coral",
            lab(d, "first", "1st Project A"),
            14,
            attrs=frag("slide-from-left", 2),
        )
        + bar(
            7.1,
            2.65,
            2.3,
            0.6,
            "lavender",
            lab(d, "second", "2nd Project B"),
            14,
            attrs=frag("slide-from-left", 3),
        )
        + footer_line(
            d, "First the project closest to the red zone, or deepest into it.", 3.85
        )
    )


def kind_quote(d):
    return "ff-content ff-diagram", (
        bar(
            0.5,
            1.7,
            4.8,
            0.7,
            "coral",
            lab(d, "chain", "Chain of tasks (planned hours)"),
            13,
        )
        + bar(
            5.35,
            1.7,
            2.0,
            0.7,
            "blue",
            lab(d, "buffer", "Buffer"),
            14,
            attrs=frag("grow-x", 1),
        )
        + box(5.32, 1.35, 0.02, 1.4, "", "ff-dash", attrs=frag("fade-in", 2))
        + text(
            4.2,
            2.85,
            2.3,
            0.6,
            lab(d, "available", "Available date"),
            14,
            "ff-center ff-strong",
            frag("fade-up", 2),
        )
        + box(7.36, 1.35, 0.02, 1.4, "", "ff-dash", attrs=frag("fade-in", 3))
        + text(
            6.3,
            2.85,
            2.2,
            0.6,
            lab(d, "quote", "Date to quote"),
            14,
            "ff-center ff-strong ff-blue-text",
            frag("fade-up", 3),
        )
        + text(
            0.5,
            3.45,
            9.0,
            0.5,
            lab(
                d,
                "explanation",
                "If the customer asks for a date inside the buffer: a tight date.",
            ),
            16,
            attrs=frag("fade-up", 4),
        )
        + footer_line(
            d, "The date to quote is promised: the one that can be kept.", 4.15
        )
    )


KINDS = {
    "cover": kind_cover,
    "section": kind_section,
    "summary": kind_summary,
    "cards": kind_cards,
    "people": kind_people,
    "story": kind_story,
    "agenda": kind_agenda,
    "flow": kind_flow,
    "statement": kind_statement,
    "promise": kind_promise,
    "capacity": kind_capacity,
    "ctp": kind_ctp,
    "critical": kind_critical,
    "float": kind_float,
    "safety": kind_safety,
    "parkinson": kind_parkinson,
    "pool": kind_pool,
    "feeding": kind_feeding,
    "fever": kind_fever,
    "zones": kind_zones,
    "priority": kind_priority,
    "quote": kind_quote,
}


def notes(say):
    if isinstance(say, list):
        return "".join(f"<p>{esc(s)}</p>" for s in say)
    return esc(say or "")


def section(d, number, footer):
    if d["kind"] not in KINDS:
        raise ValueError(
            f"slide {d['id']}: unknown kind {d['kind']!r} (kinds: {', '.join(KINDS)})"
        )
    classes, inner = KINDS[d["kind"]](d)
    chrome = ""
    if "ff-content" in classes:
        chrome = (
            f'<h2 class="ff-title ff-fit">{esc(d["title"])}</h2>'
            '<img class="ff-logo" src="forgeflow/assets/forgeflow-logo.png" alt="ForgeFlow"/>'
        )
    chrome_footer = (
        f'<div class="ff-footer"><span>{esc(footer)}</span><b>{number}</b></div>'
    )
    return (
        f'<section class="{classes}" data-id="{esc(d["id"])}" data-kind="{esc(d["kind"])}">'
        f"{chrome}{inner}{chrome_footer}"
        f'<aside class="notes">{notes(d.get("say"))}</aside></section>'
    )


PAGE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<link rel="stylesheet" href="forgeflow/vendor/reveal.js/dist/reset.css"/>
<link rel="stylesheet" href="forgeflow/vendor/reveal.js/dist/reveal.css"/>
<link rel="stylesheet" href="forgeflow/forgeflow.css"/>
<link rel="stylesheet" href="forgeflow/layouts.css"/>
<link rel="stylesheet" href="forgeflow/components.css"/>
</head>
<body>
<svg width="0" height="0" style="position:absolute"><defs>
<marker id="ff-head" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z"/></marker>
</defs></svg>
<div class="reveal"><div class="slides">
{sections}
</div></div>
<script src="forgeflow/vendor/reveal.js/dist/reveal.js"></script>
<script src="forgeflow/vendor/reveal.js/plugin/notes/notes.js"></script>
<script src="forgeflow/forgeflow.js"></script>
<script>ForgeFlowDeck.init();</script>
</body>
</html>
"""


def render(title, slides, footer=FOOTER, lang="en"):
    """The HTML of the deck."""
    sections = "\n".join(section(d, i, footer) for i, d in enumerate(slides, start=1))
    return PAGE.format(title=esc(title), sections=sections, lang=esc(lang[:2]))


def write(out_dir, title, slides, footer=FOOTER, lang="en"):
    """index.html in ``out_dir`` and the template beside it (forgeflow/)."""
    target = os.path.join(out_dir, "forgeflow")
    os.makedirs(target, exist_ok=True)
    for name in FILES:
        source = os.path.join(HERE, name)
        dest = os.path.join(target, name)
        if os.path.isdir(source):
            shutil.copytree(source, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(source, dest)
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(render(title, slides, footer, lang))
    return path


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    import yaml

    with open(sys.argv[1], encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    path = write(
        sys.argv[2],
        data.get("title", "ForgeFlow"),
        data.get("slides", []),
        data.get("footer", FOOTER),
        data.get("lang", "en"),
    )
    print(f"{len(data.get('slides', []))} slides -> {path}")


if __name__ == "__main__":
    main()
