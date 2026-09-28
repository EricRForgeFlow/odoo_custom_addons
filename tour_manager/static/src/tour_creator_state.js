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
 * @property {{ mode: "insert"|"pick", tourId: number, after: number, step: Object|null }} [edit]
 *  editing an existing tour: inserting new steps after the first `after` ones,
 *  or picking the element of `step` again
 * @property {{ count: number, done?: boolean, reached?: boolean, message?: string }} [prelude]
 *  the first `count` steps of the edited tour, played automatically first
 * @property {boolean} [paused] whether the recording is paused
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
