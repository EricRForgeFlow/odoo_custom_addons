import { whenReady } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { redirect } from "@web/core/utils/urls";
import { replayState } from "./replay_state";

/**
 * Flag set in the tour config of tours started from the Tours app ("replays").
 * A replay doesn't switch the user to onboarding mode, and doesn't chain into
 * the next onboarding tour when it's done.
 */
// Also defined in tour_interactive_patch.js.
export const REPLAY_CONFIG_KEY = "tourManagerReplay";
export const CHECK_CONFIG_KEY = "tourManagerCheck";
/** Flag of the custom tours started by themselves (see tour_auto_start.js). */
export const AUTO_START_CONFIG_KEY = "tourManagerAutoStart";
/** Number of steps played automatically, to reach the step after (see TourCreator). */
export const PLAY_UNTIL_CONFIG_KEY = "tourManagerPlayUntil";

/** Lazy bundle of the tour engine, backported from web_tour 20.0 (see tour_engine/). */
const ENGINE_BUNDLE = "tour_manager.tour_engine";
const ENGINE_MODULE = "@tour_manager/tour_engine/tour_interactive";

const tourRegistry = registry.category("web_tour.tours");

/**
 * Plays the tours of the Tours app: replays, checks (played automatically, in
 * "robot" mode), and the steps played before recording new ones.
 *
 * In 19.0, web_tour's tour service only resumes a manual tour after a page
 * load in onboarding mode, switches the user to onboarding mode when a manual
 * tour starts, and its engine can't play steps by itself. So these tours are
 * played by an engine backported from web_tour 20.0, which keeps its state
 * apart (see replay_state.js) and is resumed by this service.
 */
export const tourReplayService = {
    // localization dependency to make sure translations used by tours are loaded
    dependencies: ["orm", "effect", "overlay", "localization"],

    start(env, { orm, effect, overlay }) {
        // "Stop Tour" switches onboarding mode off and reloads the page:
        // forget the tour first, which would be resumed otherwise.
        browser.addEventListener(
            "click",
            (ev) => {
                if (ev.target.closest?.(".o_tour_pointer_content button")) {
                    const name = replayState.getCurrentTour();
                    if (name && replayState.getCurrentConfig()?.[AUTO_START_CONFIG_KEY]) {
                        // Stopping a tour that started by itself: don't start it again
                        orm.silent.call("web_tour.tour", "tour_manager_dismiss", [name]);
                    }
                    replayState.clear();
                }
            },
            { capture: true }
        );

        async function getTour(name) {
            const tour = await orm.call("web_tour.tour", "get_tour_json_by_name", [name]);
            if (!tour) {
                console.error(`Tour '${name}' is not found in the database.`);
                return;
            }
            // The steps of the onboarding tours of apps come from the registry
            if (!tour.steps.length && tourRegistry.contains(tour.name)) {
                tour.steps = tourRegistry.get(tour.name).steps();
            }
            return tour;
        }

        async function resumeReplay() {
            const tour = await getTour(replayState.getCurrentTour());
            if (!tour || !tour.steps.length) {
                replayState.clear();
                return;
            }
            if (!odoo.loader.modules.get(ENGINE_MODULE)) {
                await loadBundle(ENGINE_BUNDLE);
            }
            const { TourInteractive } = odoo.loader.modules.get(ENGINE_MODULE);
            new TourInteractive(tour, {
                orm,
                effect,
                overlay,
                // Replays don't chain into the next onboarding tour
                onChainNextTour: () => {},
            }).start(env);
        }

        /**
         * @param {string} name
         * @param {Object} options
         * @param {string} options.url
         * @param {string} [options.rainbowManMessage]
         * @param {boolean} [options.check] whether to check the tour: play it automatically
         * @param {boolean} [options.autoStart] whether the tour starts by itself
         *  (without `url`, it starts on the current page)
         * @param {number} [options.playUntil] play only this number of steps,
         *  automatically, to reach the step after
         */
        async function startReplay(name, { url, rainbowManMessage, check = false, autoStart = false, playUntil }) {
            replayState.setCurrentConfig({
                stepDelay: 0,
                mode: "manual",
                showPointerDuration: 0,
                debug: false,
                redirect: true,
                robot: false,
                // The tours of the Tours app are records (their steps may come
                // from the registry, for the onboarding tours of apps)
                fromDB: true,
                url,
                rainbowManMessage,
                [REPLAY_CONFIG_KEY]: true,
                // A check plays the tour automatically ("robot" mode), finding
                // the element of each step the same way as for a user.
                ...(check && { robot: true, [CHECK_CONFIG_KEY]: true }),
                ...(autoStart && { [AUTO_START_CONFIG_KEY]: true }),
                ...(Number.isInteger(playUntil) && { robot: true, [PLAY_UNTIL_CONFIG_KEY]: playUntil }),
            });
            replayState.setCurrentTour(name);
            replayState.setCurrentIndex(0);
            if (url) {
                redirect(url);
            } else {
                await resumeReplay();
            }
        }

        whenReady(() => {
            if (!window.frameElement && replayState.getCurrentTour()) {
                resumeReplay();
            }
        });

        return { startReplay };
    },
};

registry.category("services").add("tour_manager_replay", tourReplayService);
