import { browser } from "@web/core/browser/browser";

const TOUR_CREATOR_LOCAL_STORAGE_KEY = "tour_manager.tour_creator";

/**
 * @typedef TourCreatorStep
 * @property {string} trigger
 * @property {string} run
 * @property {string} [content]
 * @property {"top"|"bottom"|"left"|"right"} tooltip_position
 *
 * @typedef TourCreatorData
 * @property {string} title
 * @property {string} name technical name of the tour to create
 * @property {string} url starting URL
 * @property {string} rainbow_man_message
 * @property {string} [icon]
 * @property {TourCreatorStep[]} steps
 */

/**
 * Wrapper around localStorage keeping the tour being recorded, so that the
 * recording survives page reloads.
 */
export const tourCreatorState = {
    /** @returns {TourCreatorData|null} */
    get() {
        try {
            return JSON.parse(browser.localStorage.getItem(TOUR_CREATOR_LOCAL_STORAGE_KEY));
        } catch {
            return null;
        }
    },
    /** @param {TourCreatorData} data */
    set(data) {
        browser.localStorage.setItem(TOUR_CREATOR_LOCAL_STORAGE_KEY, JSON.stringify(data));
    },
    clear() {
        browser.localStorage.removeItem(TOUR_CREATOR_LOCAL_STORAGE_KEY);
    },
};
