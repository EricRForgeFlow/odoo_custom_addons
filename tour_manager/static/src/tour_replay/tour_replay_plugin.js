import { Plugin, useListener, usePlugin } from "@odoo/owl";
import { ORM } from "@web/core/orm_plugin";
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
export const CHECK_CONFIG_KEY = "tourManagerCheck";
/** Flag of the custom tours started by themselves (see TourAutoStartPlugin). */
export const AUTO_START_CONFIG_KEY = "tourManagerAutoStart";

/**
 * web_tour only resumes a manual tour after a page load when the user is in
 * onboarding mode. While a replay runs, the tour plugin is told onboarding
 * mode is on, for the current page only, so that the replay goes on.
 */
export class TourReplayPlugin extends Plugin {
    orm = usePlugin(ORM);
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
                    const name = tourState.getCurrentTour();
                    if (name && tourState.getCurrentConfig()?.[AUTO_START_CONFIG_KEY]) {
                        // Stopping a tour that started by itself: don't start it again
                        this.orm.silent.call("web_tour.tour", "tour_manager_dismiss", [name]);
                    }
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
     * @param {boolean} [options.check] whether to check the tour: play it automatically
     * @param {boolean} [options.autoStart] whether the tour starts by itself
     *  (without `url`, it starts on the current page)
     */
    startReplay(name, { url, rainbowManMessage, check = false, autoStart = false }) {
        // startTour() switches the user to onboarding mode unless it's already on.
        this.tour.toursEnabled = true;
        return this.tour.startTour(name, {
            mode: "manual",
            url,
            rainbowManMessage,
            [REPLAY_CONFIG_KEY]: true,
            // A check plays the tour automatically ("robot" mode), finding the
            // element of each step the same way as for a user.
            ...(check && { robot: true, [CHECK_CONFIG_KEY]: true }),
            ...(autoStart && { [AUTO_START_CONFIG_KEY]: true }),
        });
    }
}

services.add(TourReplayPlugin);
