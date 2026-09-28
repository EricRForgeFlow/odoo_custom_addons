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
 * Time (ms) after which a result that was shown isn't shown again. A result is
 * kept until its dialog is closed, in case the page is reloaded right after it
 * was shown, but the user may also leave without closing it.
 */
const SHOWN_RESULT_LIFETIME = 10000;

/** Time (ms) a result waits for the first screen of the web client, before being shown anyway. */
const FIRST_SCREEN_TIMEOUT = 10000;

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
        this.processing = false;
        useListener(window, CHECK_DONE_EVENT, (ev) => {
            ev.preventDefault(); // handled: the tour doesn't need to go to the Tours app
            this.processCheckResult();
        });
        // A check whose result couldn't be shown yet: the page was reloaded
        // (e.g. by the last action of the tour), or the check ended on a page
        // without the Tours app (e.g. of the website), which came back to it.
        onWillStart(async () => {
            await whenReady();
            if (browser.localStorage.getItem(CHECK_RESULT_KEY)) {
                this.processCheckResultOnceLoaded();
            }
        });
    }

    /**
     * Shows the result once the web client has loaded its first screen, which
     * would otherwise close the dialog showing the result.
     */
    processCheckResultOnceLoaded() {
        let done = false;
        const process = () => {
            if (!done) {
                done = true;
                this.env.bus.removeEventListener("ACTION_MANAGER:UI-UPDATED", process);
                this.processCheckResult();
            }
        };
        this.env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", process);
        // In case no screen is loaded
        setTimeout(process, FIRST_SCREEN_TIMEOUT);
    }

    /**
     * Saves the result of the check kept in the browser, if any, and shows it.
     * It's kept until the user closes the dialog showing it, in case the page
     * is reloaded in the meantime.
     */
    async processCheckResult() {
        const rawResult = browser.localStorage.getItem(CHECK_RESULT_KEY);
        if (!rawResult || this.processing) {
            return;
        }
        let result;
        try {
            result = JSON.parse(rawResult);
        } catch {
            browser.localStorage.removeItem(CHECK_RESULT_KEY);
            return;
        }
        if (result.shownAt && Date.now() - result.shownAt > SHOWN_RESULT_LIFETIME) {
            browser.localStorage.removeItem(CHECK_RESULT_KEY);
            return;
        }
        this.processing = true;
        const { name, passed, message, step, leftLastScreen } = result;
        const tourId = await this.orm.call("web_tour.tour", "tour_manager_save_check_result", [
            name,
            passed,
            message,
            step || 0,
        ]);
        browser.localStorage.setItem(CHECK_RESULT_KEY, JSON.stringify({ ...result, shownAt: Date.now() }));
        const title = passed ? _t("Check passed") : _t("Check failed");
        const onClose = () => {
            browser.localStorage.removeItem(CHECK_RESULT_KEY);
            this.processing = false;
        };
        if (leftLastScreen) {
            this.dialog.add(AlertDialog, { title, body: message }, { onClose });
            return;
        }
        this.dialog.add(
            ConfirmationDialog,
            {
                title,
                body: message,
                confirmLabel: _t("Back to Tours"),
                confirm: () => openToursApp(this.action, this.env, { tour_manager_highlight_id: tourId }),
                cancelLabel: _t("Stay here"),
                cancel: () => {},
            },
            { onClose }
        );
    }
}

services.add(TourCheckPlugin);
