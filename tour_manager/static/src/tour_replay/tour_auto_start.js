import { whenReady } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { tourState } from "@web_tour/js/tour_state";
import { tourCreatorState } from "@tour_manager/tour_creator_state";
import { replayState } from "./replay_state";

/**
 * Starts the custom tours set to start automatically, visible to the user and
 * not done nor dismissed by them yet (listed in the session), when the user
 * reaches their starting page: on page load, or when navigating in the web
 * client. A tour started this way doesn't switch the user to onboarding mode,
 * like a replay.
 */
export class TourAutoStart {
    /**
     * @param {Object} env
     * @param {Object} services
     */
    constructor(env, { tour_manager_replay }) {
        this.replay = tour_manager_replay;
        /** @type {{ name: string, url: string, rainbow_man_message: string }[]} */
        this.tours = [...(session.tour_manager_auto_tours || [])];
        if (!this.tours.length) {
            return;
        }
        whenReady(() => {
            // Also dispatched once the first screen is loaded
            env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", () => this.startTourOfPage());
        });
    }

    startTourOfPage() {
        if (
            !this.tours.length ||
            tourState.getCurrentTour() ||
            replayState.getCurrentTour() ||
            tourCreatorState.get()
        ) {
            return;
        }
        const path = browser.location.pathname;
        const tour = this.tours.find(
            (tour) => new URL(tour.url, browser.location.origin).pathname === path
        );
        if (!tour) {
            return;
        }
        // Started once per page load at most (done or dismissed, it isn't listed again)
        this.tours = this.tours.filter((other) => other !== tour);
        this.replay.startReplay(tour.name, {
            rainbowManMessage: tour.rainbow_man_message,
            autoStart: true,
        });
    }
}

registry.category("services").add("tour_manager_auto_start", {
    dependencies: ["tour_manager_replay"],
    start(env, services) {
        return new TourAutoStart(env, services);
    },
});
