import { patch } from "@web/core/utils/patch";
import { TourInteractive } from "@web_tour/tour_interactive/tour_interactive";

// Same as REPLAY_CONFIG_KEY in tour_replay_plugin.js, which isn't imported so
// that this bundle keeps working where the plugin isn't loaded (unit tests).
const REPLAY_CONFIG_KEY = "tourManagerReplay";

patch(TourInteractive.prototype, {
    async finish() {
        if (this.config[REPLAY_CONFIG_KEY]) {
            // A replay doesn't chain into the next onboarding tour.
            this.onChainNextTour = () => {};
        }
        return super.finish(...arguments);
    },
});
