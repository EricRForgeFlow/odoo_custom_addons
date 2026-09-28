import { onWillStart, Plugin, usePlugin, whenReady } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { services } from "@web/core/services";
import { useEnv } from "@web/owl2/utils";
import { session } from "@web/session";
import { tourState } from "@web_tour/tour_state";
import { tourCreatorState } from "@tour_manager/tour_creator_state";
import { TourReplayPlugin } from "./tour_replay_plugin";

/**
 * Starts the custom tours set to start automatically, visible to the user and
 * not done nor dismissed by them yet (listed in the session), when the user
 * reaches their starting page: on page load, or when navigating in the web
 * client. A tour started this way doesn't switch the user to onboarding mode,
 * like a replay.
 */
export class TourAutoStartPlugin extends Plugin {
    env = useEnv();
    replay = usePlugin(TourReplayPlugin);

    setup() {
        /** @type {{ name: string, url: string, rainbow_man_message: string }[]} */
        this.tours = [...(session.tour_manager_auto_tours || [])];
        if (!this.tours.length) {
            return;
        }
        onWillStart(async () => {
            await whenReady();
            // Also dispatched once the first screen is loaded
            this.env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", () => this.startTourOfPage());
        });
    }

    startTourOfPage() {
        if (!this.tours.length || tourState.getCurrentTour() || tourCreatorState.get()) {
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

services.add(TourAutoStartPlugin);
