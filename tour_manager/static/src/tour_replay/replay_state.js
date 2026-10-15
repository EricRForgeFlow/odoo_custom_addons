import { browser } from "@web/core/browser/browser";

// Same keys as web_tour's tourState, prefixed: in 19.0, web_tour's tour service
// drops (or resumes, with its own engine) any tour of its keys when a page
// loads, so the tours played by tour_manager's engine (see tour_engine/) are
// kept apart.
const CURRENT_TOUR_KEY = "tour_manager.current_tour";
const CURRENT_TOUR_CONFIG_KEY = "tour_manager.current_tour.config";
const CURRENT_TOUR_INDEX_KEY = "tour_manager.current_tour.index";

/**
 * Wrapper around localStorage keeping the tour played by tour_manager's engine
 * (a replay, a check or the steps played before recording), so that it's
 * resumed when the page is reloaded. Same API as web_tour's tourState.
 */
export const replayState = {
    getCurrentTour() {
        return browser.localStorage.getItem(CURRENT_TOUR_KEY);
    },
    setCurrentTour(tourName) {
        browser.localStorage.setItem(CURRENT_TOUR_KEY, tourName);
    },
    getCurrentIndex() {
        return parseInt(browser.localStorage.getItem(CURRENT_TOUR_INDEX_KEY) || "0", 10);
    },
    setCurrentIndex(index) {
        browser.localStorage.setItem(CURRENT_TOUR_INDEX_KEY, index.toString());
    },
    getCurrentConfig() {
        try {
            return JSON.parse(browser.localStorage.getItem(CURRENT_TOUR_CONFIG_KEY) || "{}");
        } catch {
            return {};
        }
    },
    setCurrentConfig(config) {
        browser.localStorage.setItem(CURRENT_TOUR_CONFIG_KEY, JSON.stringify(config));
    },
    clear() {
        browser.localStorage.removeItem(CURRENT_TOUR_CONFIG_KEY);
        browser.localStorage.removeItem(CURRENT_TOUR_INDEX_KEY);
        browser.localStorage.removeItem(CURRENT_TOUR_KEY);
    },
};
