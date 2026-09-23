import { Plugin, useListener, usePlugin } from "@odoo/owl";
import { services } from "@web/core/services";
import { TourPlugin } from "@web_tour/tour_plugin";
import { tourState } from "@web_tour/tour_state";

/**
 * Flag set in the tour config of tours started from the Tours app ("replays").
 * A replay doesn't switch the user to onboarding mode, and doesn't chain into
 * the next onboarding tour when it's done.
 */
// Also defined in tour_interactive_patch.js.
export const REPLAY_CONFIG_KEY = "tourManagerReplay";

/**
 * web_tour only resumes a manual tour after a page load when the user is in
 * onboarding mode. While a replay runs, the tour plugin is told onboarding
 * mode is on, for the current page only, so that the replay goes on.
 */
export class TourReplayPlugin extends Plugin {
    tour = usePlugin(TourPlugin);

    setup() {
        if (tourState.getCurrentTour() && tourState.getCurrentConfig()?.[REPLAY_CONFIG_KEY]) {
            this.tour.toursEnabled = true;
        }
        // "Stop Tour" switches onboarding mode off and reloads the page,
        // counting on the reload to drop the tour, but a replay would be
        // resumed as it doesn't depend on onboarding mode: forget it first.
        useListener(
            window,
            "click",
            (ev) => {
                if (ev.target.closest?.(".o_tour_pointer_content button")) {
                    tourState.clear();
                }
            },
            { capture: true }
        );
    }

    /**
     * @param {string} name
     * @param {Object} options
     * @param {string} options.url
     * @param {string} [options.rainbowManMessage]
     */
    startReplay(name, { url, rainbowManMessage }) {
        // startTour() switches the user to onboarding mode unless it's already on.
        this.tour.toursEnabled = true;
        return this.tour.startTour(name, {
            mode: "manual",
            url,
            rainbowManMessage,
            [REPLAY_CONFIG_KEY]: true,
        });
    }
}

services.add(TourReplayPlugin);
