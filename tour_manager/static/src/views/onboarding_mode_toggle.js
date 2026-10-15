import { Component, onWillStart, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { tourState } from "@web_tour/js/tour_state";
import { replayState } from "@tour_manager/tour_replay/replay_state";

/**
 * Debug tool showing whether the user is in onboarding mode, in which the
 * onboarding tours they haven't done start by themselves, and which tour is in
 * progress, if any. Only shown in debug mode.
 */
export class OnboardingModeToggle extends Component {
    static template = "tour_manager.OnboardingModeToggle";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({ enabled: false });
        // Tours of the Tours app (replays) are played apart from web_tour's (see replay_state.js)
        this.isReplay = Boolean(replayState.getCurrentTour());
        this.currentTour = replayState.getCurrentTour() || tourState.getCurrentTour();
        onWillStart(async () => {
            if (!this.isDebug) {
                return;
            }
            // Read from the server: the session may be outdated.
            const [{ tour_enabled }] = await this.orm.read("res.users", [user.userId], ["tour_enabled"]);
            this.state.enabled = tour_enabled;
        });
    }

    async toggle() {
        await this.orm.call("res.users", "switch_tour_enabled", [!this.state.enabled]);
        // Reload, as web_tour only reads onboarding mode when the page loads.
        browser.location.reload();
    }

    get isDebug() {
        return Boolean(this.env.debug);
    }

    stopCurrentTour() {
        replayState.clear();
        tourState.clear();
        browser.location.reload();
    }
}
