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
import { PLAY_UNTIL_CONFIG_KEY } from "./tour_replay/tour_replay_plugin";
import { tourCreatorState } from "./tour_creator_state";
import { forgetCurrentApp, openTourForm, openToursApp } from "./tours_app";

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
            // Don't let onboarding tours start and get in the way while
            // recording, but let the tour edited reach the step to record from.
            session.current_tour = false;
            if (!Number.isInteger(tourState.getCurrentConfig()?.[PLAY_UNTIL_CONFIG_KEY])) {
                tourState.clear();
            }
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
                onFinish: (tourId, title, edit) => this.onRecordingFinished(tourId, title, edit),
            },
            { sequence: 99999 }
        );
    }

    /**
     * Stops the recording and goes back to the Tours app.
     *
     * @param {Object} [context] additional context of the Tours action
     */
    async stopRecording(context = {}) {
        const editedTourId = tourCreatorState.get()?.edit?.tourId;
        tourCreatorState.clear();
        this.removeTourCreator();
        this.removeTourCreator = () => {};
        if (editedTourId) {
            // Back to the tour being edited
            return openTourForm(this.action, this.env, this.orm, editedTourId);
        }
        return openToursApp(this.action, this.env, context);
    }

    /**
     * @param {number} tourId
     * @param {string} title
     * @param {{ inserted?: number, picked?: number }} [edit] what was done to an
     *  existing tour: the number of steps inserted, or of the step picked again
     */
    async onRecordingFinished(tourId, title, edit) {
        if (edit) {
            await this.stopRecording();
            const message = edit.picked
                ? _t("Step %(step)s of “%(title)s” updated.", { step: edit.picked, title })
                : _t("%(count)s step(s) added to “%(title)s”.", { count: edit.inserted, title });
            this.notification.add(message, { type: "success" });
            return;
        }
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

registry.category("actions").add("tour_manager.edit_tour", (env, action) => {
    const { mode, tour_id, name, title, url, play_until, step } = action.params;
    tourCreatorState.set({
        title,
        name,
        url,
        steps: [],
        edit: { mode, tourId: tour_id, after: play_until, step: step || null },
        // The steps before are played automatically, to reach the screen to record from
        prelude: play_until > 0 ? { count: play_until } : null,
    });
    forgetCurrentApp();
    if (play_until > 0) {
        return env.services.tour_manager_replay.startReplay(name, { url, playUntil: play_until });
    }
    browser.location.assign(url);
});

registry.category("actions").add("tour_manager.start_recording", (env, action) => {
    const { title, name, url, rainbow_man_message, icon } = action.params;
    tourCreatorState.set({ title, name, url, rainbow_man_message, icon, steps: [] });
    forgetCurrentApp();
    browser.location.assign(url);
});
