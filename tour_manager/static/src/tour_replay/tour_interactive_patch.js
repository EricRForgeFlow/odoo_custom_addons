import { click } from "@odoo/hoot-dom";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { TourInteractive } from "@web_tour/tour_interactive/tour_interactive";
import { TourStepInteractive } from "@web_tour/tour_interactive/tour_step_interactive";
import { pointerState } from "@web_tour/tour_pointer/tour_pointer";
import { tourState } from "@web_tour/tour_state";

/** Time (ms) a tour waits for a vanished element to come back before going back a step. */
const BACKWARD_DELAY = 1000;

// Same as REPLAY_CONFIG_KEY in tour_replay_plugin.js, which isn't imported so
// that this bundle keeps working where the plugin isn't loaded (unit tests).
const REPLAY_CONFIG_KEY = "tourManagerReplay";

/** Elements whose click, during a replay, leaves the tour unless it's the current step. */
const CLICKABLE_SELECTOR = [
    "button",
    "a",
    "[role='button']",
    "[role='menuitem']",
    "[role='menuitemcheckbox']",
    "[role='menuitemradio']",
    "[role='tab']",
    "[role='option']",
    ".dropdown-item",
    ".o_kanban_record",
    ".o_data_row",
].join(", ");

/** Parts of the page that never leave the tour: the tour's own UI, notifications. */
const IGNORED_SELECTOR = ".o_tour_pointer, .o_notification_manager";

patch(TourInteractive.prototype, {
    /** Whether the tour was started from the Tours app. */
    get isReplay() {
        return Boolean(this.config[REPLAY_CONFIG_KEY]);
    },

    /** Whether the tour is managed by the Tours app: a replay, or a custom tour. */
    get isManaged() {
        return this.isReplay || Boolean(this.custom);
    },

    start(env) {
        super.start(...arguments);
        if (this.isReplay) {
            this.env = env;
            this.addLeaveGuard();
        }
    },

    async finish() {
        this.removeLeaveGuard();
        if (this.isReplay) {
            // A replay doesn't chain into the next onboarding tour.
            this.onChainNextTour = () => {};
        }
        return super.finish(...arguments);
    },

    //--------------------------------------------------------------------------
    // Leaving a replay
    //--------------------------------------------------------------------------

    /**
     * During a replay, clicking something else than the element of the current
     * step asks whether to leave the tour, instead of leaving it half-done
     * (e.g. still running, but on a screen where it can't go on). When the
     * element of the current step isn't shown (e.g. the user went to another
     * screen through the URL), clicks are let through, so that the user can
     * go back to where the tour goes on.
     */
    addLeaveGuard() {
        this.removeLeaveGuard();
        const listener = (ev) => this.onLeaveGuardEvent(ev);
        for (const eventName of ["pointerdown", "mousedown", "click"]) {
            window.addEventListener(eventName, listener, { capture: true });
        }
        this.removeLeaveGuard = () => {
            for (const eventName of ["pointerdown", "mousedown", "click"]) {
                window.removeEventListener(eventName, listener, { capture: true });
            }
            this.removeLeaveGuard = () => {};
        };
    },

    removeLeaveGuard() {},

    /**
     * @param {PointerEvent|MouseEvent} ev
     */
    onLeaveGuardEvent(ev) {
        // Clicks replayed after leaving (through hoot) are not trusted.
        if (!ev.isTrusted || this.leaveDialogOpen) {
            return;
        }
        const target = ev.composedPath()[0];
        if (!(target instanceof Element) || target.closest(IGNORED_SELECTOR)) {
            return;
        }
        const clickable = target.closest(CLICKABLE_SELECTOR);
        if (!clickable || !this.currentAction?.findTrigger() || this.isPartOfCurrentStep(target, clickable)) {
            return;
        }
        ev.preventDefault();
        ev.stopImmediatePropagation();
        if (ev.type === "click") {
            this.openLeaveDialog(clickable);
        }
    },

    /**
     * @param {Element} target
     * @param {Element} clickable
     * @returns {boolean}
     */
    isPartOfCurrentStep(target, clickable) {
        const anchor = this.anchorEl;
        if (!anchor?.isConnected) {
            return false;
        }
        // The options of an autocomplete belong to the step typing in it.
        const autocomplete = anchor.closest(".o-autocomplete");
        return (
            anchor.contains(target) ||
            clickable.contains(anchor) ||
            Boolean(autocomplete?.contains(target))
        );
    },

    /**
     * @param {HTMLElement} clickable the element clicked outside of the tour
     */
    openLeaveDialog(clickable) {
        this.leaveDialogOpen = true;
        this.env.services.dialog.add(
            ConfirmationDialog,
            {
                title: _t("Leave the tour?"),
                body: _t(
                    "This isn't the next step of the tour “%s”. Do you want to leave the tour?",
                    this.title || this.name
                ),
                confirmLabel: _t("Leave tour"),
                cancelLabel: _t("Stay in the tour"),
                confirm: async () => {
                    this.stopReplay();
                    if (clickable.isConnected) {
                        await click(clickable);
                    }
                },
                cancel: () => {},
            },
            { onClose: () => (this.leaveDialogOpen = false) }
        );
    },

    /** Stops the tour for good, as if it had never been started. */
    stopReplay() {
        this.removeLeaveGuard();
        clearTimeout(this.backwardTimeout);
        this.removeListeners();
        TourInteractive.observer?.disconnect();
        TourInteractive.removePointer();
        pointerState.trigger = undefined;
        this.currentAction = undefined;
        tourState.clear();
    },

    //--------------------------------------------------------------------------
    // Vanishing elements
    //--------------------------------------------------------------------------

    /**
     * When the element of the current step disappears, interactive tours go
     * back to the previous step whose element is there. For managed tours,
     * wait a bit first: the element may only disappear while the page is
     * updated (e.g. a kanban record dropped in another column, until it's
     * saved). And if no step can be found, hide the pointer instead of leaving
     * it where the element was.
     */
    _onMutation() {
        if (!this.isManaged) {
            return super._onMutation(...arguments);
        }
        clearTimeout(this.backwardTimeout);
        if (this.currentAction && this.anchorEl && !this.currentAction.findTrigger()) {
            this.backwardTimeout = setTimeout(() => {
                super._onMutation();
                if (this.anchorEl && !this.anchorEl.isConnected) {
                    pointerState.trigger = undefined;
                }
            }, BACKWARD_DELAY);
            return;
        }
        return super._onMutation(...arguments);
    },

    //--------------------------------------------------------------------------
    // Step types
    //--------------------------------------------------------------------------

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
