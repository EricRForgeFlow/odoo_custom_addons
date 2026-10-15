# Tour engine (backport of web_tour 20.0)

In 19.0, `web_tour`'s interactive engine lacks what the Tours app relies on:
robot mode (used by checks, and to play the steps before recording new
ones), the tour config, `finish()`, `findTrigger()` and the step errors.
Its tour service also switches the user to onboarding mode when a manual
tour starts, and drops a manual tour after a page load unless onboarding
mode is on.

So the tours of the Tours app (replays, checks, tours starting by
themselves, steps played before recording) are played by this copy of the
engine of `web_tour` 20.0 (Odoo S.A., LGPL-3). Odoo's own onboarding tours
are still played by `web_tour`.

| File | Source in `web_tour` 20.0 | Changes |
|---|---|---|
| `tour_step.js` | `static/src/tour_step.js` | imports |
| `tour_step_interactive.js` | `static/src/tour_interactive/tour_step_interactive.js` | imports |
| `tour_interactive_observer.js` | `static/src/tour_interactive/tour_interactive_observer.js` | none |
| `tour_interactive.js` | `static/src/tour_interactive/tour_interactive.js` | imports, the pointer is mounted through `pointer_state.js`, the state is `replayState` |
| `pointer_state.js` | — | drives 19.0's tour pointer with the API of 20.0's `pointerState` |
| `tour_interactive_patch.js` | — | tour_manager's own changes to the engine, same as on 20.0 |

The state of the tours played here is kept under the `tour_manager.current_tour`
keys of localStorage (see `../tour_replay/replay_state.js`), apart from
`web_tour`'s, and they're started and resumed by the `tour_manager_replay`
service (see `../tour_replay/tour_replay_service.js`).

To update the copy, diff these files with the ones of `web_tour` 20.0 and
keep the changes listed above.
