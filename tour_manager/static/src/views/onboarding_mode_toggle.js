import { Component, onWillStart, proxy, usePlugin, useProps } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";
import { ORM } from "@web/core/orm_plugin";
import { user } from "@web/core/user";
import { tourState } from "@web_tour/tour_state";
import { REPLAY_CONFIG_KEY } from "@tour_manager/tour_replay/tour_replay_plugin";

/**
 * Debug tool showing whether the user is in onboarding mode, in which the
 * onboarding tours they haven't done start by themselves, and which tour is in
 * progress, if any. Only shown in debug mode.
 */
export class OnboardingModeToggle extends Component {
    static template = "tour_manager.OnboardingModeToggle";
    props = useProps({});

    setup() {
        this.debug = usePlugin(DebugModePlugin);
        this.orm = usePlugin(ORM);
        this.state = proxy({ enabled: false });
        this.currentTour = tourState.getCurrentTour();
        this.isReplay = Boolean(tourState.getCurrentConfig()?.[REPLAY_CONFIG_KEY]);
        onWillStart(async () => {
            if (!this.debug.isActive()) {
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

    stopCurrentTour() {
        tourState.clear();
        browser.location.reload();
    }
}
