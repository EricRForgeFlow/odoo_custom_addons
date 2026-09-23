import { onWillStart, Plugin, usePlugin, whenReady } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { NotificationPlugin } from "@web/core/notifications/notification_plugin";
import { ORM } from "@web/core/orm_plugin";
import { OverlayPlugin } from "@web/core/overlay/overlay_plugin";
import { registry } from "@web/core/registry";
import { services } from "@web/core/services";
import { useEnv } from "@web/owl2/utils";
import { session } from "@web/session";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";
import { tourState } from "@web_tour/tour_state";
import { tourCreatorState } from "./tour_creator_state";

const TOURS_ACTION = "tour_manager.web_tour_tour_action";
const TOURS_MENU = "tour_manager.menu_tour_manager_root";

/**
 * Shows the tour creator on every page load while a tour is being recorded.
 * The creator itself lives in a lazy bundle, only loaded when needed.
 */
export class TourCreatorPlugin extends Plugin {
    env = useEnv();
    action = usePlugin(ActionPlugin);
    notification = usePlugin(NotificationPlugin);
    orm = usePlugin(ORM);
    overlay = usePlugin(OverlayPlugin);
    removeTourCreator = () => {};

    setup() {
        if (tourCreatorState.get()) {
            // Don't let onboarding tours start and get in the way while recording.
            session.current_tour = false;
            tourState.clear();
        }
        onWillStart(() => this.bootstrap());
    }

    async bootstrap() {
        await whenReady();
        if (!window.frameElement && !session.is_public && tourCreatorState.get()) {
            await this.addTourCreatorToOverlay();
        }
    }

    async addTourCreatorToOverlay() {
        if (!odoo.loader.modules.get("@tour_manager/tour_creator/tour_creator")) {
            await loadBundle("tour_manager.tour_creator");
        }
        const { TourCreator } = odoo.loader.modules.get("@tour_manager/tour_creator/tour_creator");
        this.removeTourCreator = this.overlay.add(
            TourCreator,
            {
                onCancel: () => this.stopRecording(),
                onFinish: (tourId, title) => this.onRecordingFinished(tourId, title),
            },
            { sequence: 99999 }
        );
    }

    /**
     * Stops the recording and goes back to the Tours app.
     *
     * @param {Object} [context] additional context of the Tours action
     */
    stopRecording(context = {}) {
        tourCreatorState.clear();
        this.removeTourCreator();
        this.removeTourCreator = () => {};
        const menuService = this.env.services.menu;
        const menu = menuService?.getAll().find((menu) => menu.xmlid === TOURS_MENU);
        return this.action.doAction(TOURS_ACTION, {
            clearBreadcrumbs: true,
            additionalContext: context,
            onActionReady: () => menu && menuService.setCurrentMenu(menu),
        });
    }

    /**
     * @param {number} tourId
     * @param {string} title
     */
    async onRecordingFinished(tourId, title) {
        await this.stopRecording({ tour_manager_highlight_id: tourId });
        this.notification.add(_t("Tour “%s” created.", title), {
            type: "success",
            sticky: true,
            buttons: [
                {
                    name: _t("Try it"),
                    primary: true,
                    onClick: async () => {
                        const action = await this.orm.call("web_tour.tour", "action_start_tour", [
                            [tourId],
                        ]);
                        await this.action.doAction(action);
                    },
                },
            ],
        });
    }
}

services.add(TourCreatorPlugin);

registry.category("actions").add("tour_manager.start_recording", (env, action) => {
    const { title, name, url, rainbow_man_message, icon } = action.params;
    tourCreatorState.set({ title, name, url, rainbow_man_message, icon, steps: [] });
    browser.location.assign(url);
});
