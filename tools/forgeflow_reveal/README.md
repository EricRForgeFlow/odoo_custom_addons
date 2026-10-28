# ForgeFlow reveal.js template

Slide decks in ForgeFlow's style, made with [reveal.js](https://revealjs.com) 5.1.0. The
look is ForgeFlow's corporate slides (logo, Inter, palette, footer) at 1920 × 1080, and
the diagrams build up in steps. Everything a deck needs is in this folder, so a deck can
be presented, printed or recorded offline.

## Use it in another project

```bash
scripts/export_reveal_template.sh ~/my-project/forgeflow_reveal   # from the demo factory repo
```

That copies this folder anywhere, without anything from the demo factory. It needs
Python 3 and pyyaml (`uv run --with pyyaml`) only to build a deck from YAML. The theme
also works by hand, in any reveal.js page.

## A deck from YAML

```bash
uv run --no-project --with pyyaml python deck.py slides.yaml out/
# then open out/index.html (press S for the speaker notes, F for full screen)
```

`deck.py` writes `out/index.html` and copies the template into `out/forgeflow/`. The
format, the slide kinds and their fields are in its docstring, and
[`example/slides.yaml`](example/slides.yaml) uses every one of them:

| Kinds | |
| --- | --- |
| Text | `cover`, `section`, `summary` (dark slides); `cards`, `people`, `story`, `agenda`, `flow`, `statement` |
| Planning diagrams | `promise`, `capacity`, `ctp`, `critical`, `float`, `safety`, `parkinson`, `pool`, `feeding`, `fever`, `zones`, `priority`, `quote` |

- **Diagram texts:** in `labels`, with English defaults; `footer` is the takeaway under
  a slide.
- **Narration:** `say` goes to the speaker notes. As a list, it holds one item per
  animation step: item 0 on entry, item k with step k.

## By hand

Link `vendor/reveal.js/dist/reset.css`, `reveal.css`, `forgeflow.css`, `layouts.css` and
`components.css`. Then load `vendor/reveal.js/dist/reveal.js` and `forgeflow.js` and call
`ForgeFlowDeck.init()`.

- **A content slide:** `<section class="ff-content">` with an `h2.ff-title`, the logo
  `img.ff-logo` and a `div.ff-footer`.
- **A dark slide:** `ff-dark ff-cover`, `ff-section` or `ff-summary`, with its content
  in a `div.ff-wrap`.
- **Animation steps:** reveal fragments with the template's effects: `fade-up`, `pop`,
  `grow-x` (a bar that grows from its left edge) and `slide-from-left`.

## Driving a deck from outside

`ForgeFlowDeck` is a small API for a recording or a print:

- `ready()`;
- `slides()`, which gives `[{id, kind, steps}]`;
- `goTo(i)`, `step()` and `complete(i)`.

Two URL options change the page:

- `?record` hides the controls and the progress bar;
- `?print-pdf` lays out one page per slide with every step shown, for a browser's
  print to PDF.

## Files

| File | |
| --- | --- |
| `forgeflow.css` | theme, slide chrome, fragment effects |
| `layouts.css` | text slides |
| `components.css` | diagram pieces: bars, hatched margins, panels, dots, arrows, fever chart |
| `forgeflow.js` | `ForgeFlowDeck` |
| `deck.py` | YAML → deck |
| `assets/` | ForgeFlow logos (blue, white) |
| `vendor/` | reveal.js 5.1.0 (MIT) and Inter (SIL OFL); `fetch_vendor.sh` downloads them again |
