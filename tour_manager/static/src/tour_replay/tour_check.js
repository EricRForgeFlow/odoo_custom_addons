import { onWillStart, Plugin, useListener, usePlugin, whenReady } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { DialogPlugin } from "@web/core/dialog/dialog_plugin";
import { _t } from "@web/core/l10n/translation";
import { ORM } from "@web/core/orm_plugin";
import { services } from "@web/core/services";
import { useEnv } from "@web/owl2/utils";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";
import { openToursApp } from "@tour_manager/tours_app";

// Also defined in tour_interactive_patch.js, which reports the result.
const CHECK_RESULT_KEY = "tour_manager.check_result";
const CHECK_DONE_EVENT = "tour_manager:check-done";

/**
 * Saves the result of the check of a tour, which the tour reports when it
 * passed or failed, and shows it on the last screen of the tour (where it
 * failed, if it did), from where the user can go back to the Tours app.
 */
export class TourCheckPlugin extends Plugin {
    env = useEnv();
    action = usePlugin(ActionPlugin);
    dialog = usePlugin(DialogPlugin);
    orm = usePlugin(ORM);

    setup() {
        useListener(window, CHECK_DONE_EVENT, () => this.processCheckResult({ onLastScreen: true }));
        // A check that ended on a page without the Tours app (e.g. of the
        // website) comes back to the Tours app, which then handles its result.
        onWillStart(async () => {
            await whenReady();
            await this.processCheckResult({ onLastScreen: false });
        });
    }

    /**
     * @param {Object} params
     * @param {boolean} params.onLastScreen whether the user is still on the
     *  last screen of the tour (otherwise, in the Tours app)
     */
    async processCheckResult({ onLastScreen }) {
        const rawResult = browser.localStorage.getItem(CHECK_RESULT_KEY);
        if (!rawResult) {
            return;
        }
        // Handled here: the tour doesn't need to go to the Tours app itself.
        browser.localStorage.removeItem(CHECK_RESULT_KEY);
        let result;
        try {
            result = JSON.parse(rawResult);
        } catch {
            return;
        }
        const { name, passed, message, step } = result;
        const tourId = await this.orm.call("web_tour.tour", "tour_manager_save_check_result", [
            name,
            passed,
            message,
            step || 0,
        ]);
        const title = passed ? _t("Check passed") : _t("Check failed");
        if (!onLastScreen) {
            this.dialog.add(AlertDialog, { title, body: message });
            return;
        }
        this.dialog.add(ConfirmationDialog, {
            title,
            body: message,
            confirmLabel: _t("Back to Tours"),
            confirm: () => openToursApp(this.action, this.env, { tour_manager_highlight_id: tourId }),
            cancelLabel: _t("Stay here"),
            cancel: () => {},
        });
    }
}

services.add(TourCheckPlugin);
