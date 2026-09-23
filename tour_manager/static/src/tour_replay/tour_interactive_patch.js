import { patch } from "@web/core/utils/patch";
import { TourInteractive } from "@web_tour/tour_interactive/tour_interactive";
import { TourStepInteractive } from "@web_tour/tour_interactive/tour_step_interactive";

/** Time (ms) a custom tour waits for a vanished element to come back before going back a step. */
const BACKWARD_DELAY = 1000;

// Same as REPLAY_CONFIG_KEY in tour_replay_plugin.js, which isn't imported so
// that this bundle keeps working where the plugin isn't loaded (unit tests).
const REPLAY_CONFIG_KEY = "tourManagerReplay";

patch(TourInteractive.prototype, {
    async finish() {
        if (this.config[REPLAY_CONFIG_KEY]) {
            // A replay doesn't chain into the next onboarding tour.
            this.onChainNextTour = () => {};
        }
        return super.finish(...arguments);
    },

    /**
     * When the element of the current step disappears, interactive tours go
     * back to the previous step whose element is there. For custom tours, wait
     * a bit first: the element may only disappear while the page is updated
     * (e.g. a kanban record dropped in another column, until it's saved).
     */
    _onMutation() {
        if (this.custom) {
            clearTimeout(this.backwardTimeout);
            if (this.currentAction && this.anchorEl && !this.currentAction.findTrigger()) {
                this.backwardTimeout = setTimeout(() => super._onMutation(), BACKWARD_DELAY);
                return;
            }
        }
        return super._onMutation(...arguments);
    },

    /**
     * Interactive tours skip the steps they can't wait for. Let custom tours
     * wait for the choice of an option in a select, and for typing in an editor.
     */
    getConsumeEventType(element, runCommand) {
        const consumeEvents = super.getConsumeEventType(...arguments);
        if (this.custom && element) {
            if (runCommand === "select") {
                consumeEvents.push({ name: "change", target: element });
            } else if (runCommand === "editor") {
                consumeEvents.push({
                    name: "input",
                    target: element.closest("[contenteditable='true']") || element,
                });
            }
        }
        return consumeEvents;
    },
});

patch(TourStepInteractive.prototype, {
    get actions() {
        const actions = super.actions;
        if (this.tour.custom) {
            for (const action of actions) {
                // The argument of "select" is the value to select, not a selector.
                if (action.event === "select") {
                    action.anchor = this.trigger;
                    action.findTrigger = () => this.findTrigger(this.trigger, "select");
                }
            }
        }
        return actions;
    },
});
