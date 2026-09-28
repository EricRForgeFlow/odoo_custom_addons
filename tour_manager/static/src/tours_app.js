/**
 * Helpers to leave the Tours app for a tour, and to come back to it after
 * recording or checking a tour.
 */

import { browser } from "@web/core/browser/browser";

const TOURS_ACTION = "tour_manager.web_tour_tour_action";
const TOURS_MENU = "tour_manager.menu_tour_manager_root";

/**
 * The record shown may have been changed while recording or checking a tour,
 * and may not even be valid (e.g. a quotation without customer), which would
 * prevent leaving it: discard its unsaved changes.
 */
export async function discardFormChanges() {
    const getDiscardButton = () => {
        const button = document.querySelector(".o_form_view .o_form_button_cancel");
        return button?.offsetParent ? button : null;
    };
    // Changes still being applied (e.g. by the last action) can make the
    // record dirty again right after it's discarded: try a few times.
    for (let attempt = 0; attempt < 3 && getDiscardButton(); attempt++) {
        getDiscardButton().click();
        const start = Date.now();
        while (getDiscardButton() && Date.now() - start < 2000) {
            await wait(50);
        }
        await wait(300);
    }
}

/**
 * @param {number} delay ms
 */
function wait(delay) {
    return new Promise((resolve) => setTimeout(resolve, delay));
}

/**
 * Leaves the current screen (discarding its unsaved changes) for the Tours app.
 *
 * @param {import("@web/webclient/actions/action_plugin").ActionPlugin} action
 * @param {Object} env
 * @param {Object} [context] additional context of the Tours action, e.g.
 *  `tour_manager_highlight_id` to highlight a tour
 */
export async function openToursApp(action, env, context = {}) {
    await discardFormChanges();
    const menuService = env.services.menu;
    const menu = menuService?.getAll().find((menu) => menu.xmlid === TOURS_MENU);
    return action.doAction(TOURS_ACTION, {
        clearBreadcrumbs: true,
        additionalContext: context,
        onActionReady: () => menu && menuService.setCurrentMenu(menu),
    });
}

/**
 * Leaves the current screen (discarding its unsaved changes) for the form of
 * a tour, in the Tours app.
 *
 * @param {import("@web/webclient/actions/action_plugin").ActionPlugin} action
 * @param {Object} env
 * @param {import("@web/core/orm_plugin").ORM} orm
 * @param {number} tourId
 */
export async function openTourForm(action, env, orm, tourId) {
    await openToursApp(action, env, { tour_manager_highlight_id: tourId });
    const formAction = await orm.call("web_tour.tour", "action_edit_tour", [[tourId]]);
    return action.doAction(formAction);
}

/**
 * Forgets the app remembered by the web client, before going to the starting
 * URL of a tour. The web client shows the app of the page's action, but falls
 * back to the remembered app when the action isn't in any menu of the user
 * (e.g. quotations without the Sales app): it would show the Tours app, from
 * where tours are started.
 */
export function forgetCurrentApp() {
    browser.sessionStorage.removeItem("menu_id");
}
