import { click, waitFor } from "@odoo/hoot-dom";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { TourInteractive } from "@web_tour/tour_interactive/tour_interactive";
import { TourStepInteractive } from "@web_tour/tour_interactive/tour_step_interactive";
import { pointerState } from "@web_tour/tour_pointer/tour_pointer";
import { tourState } from "@web_tour/tour_state";

/** Time (ms) a tour waits for a vanished element to come back before going back a step. */
const BACKWARD_DELAY = 1000;

// Same as in tour_replay_plugin.js and tour_check.js, which aren't imported so
// that this bundle keeps working where they aren't loaded (unit tests).
const REPLAY_CONFIG_KEY = "tourManagerReplay";
const CHECK_CONFIG_KEY = "tourManagerCheck";
const AUTO_START_CONFIG_KEY = "tourManagerAutoStart";
const PLAY_UNTIL_CONFIG_KEY = "tourManagerPlayUntil";
// Same as in tour_creator_state.js and tour_creator.js
const TOUR_CREATOR_KEY = "tour_manager.tour_creator";
const PRELUDE_DONE_EVENT = "tour_manager:prelude-done";

/** Event of the hint of an info step being clicked, to go on. */
const NEXT_EVENT = "tour_manager:next";
const CHECK_RESULT_KEY = "tour_manager.check_result";
const CHECK_DONE_EVENT = "tour_manager:check-done";

/** Time (ms) a check waits for a step to be done before failing. */
const CHECK_TIMEOUT = 10000;
/** Time (ms) a passed check lets the page handle the last action before leaving it. */
const CHECK_SETTLE_DELAY = 1000;

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
    ".o_data_cell",
    ".o_data_row",
].join(", ");

/** Fields, in which a click only focuses them (what's typed in them makes the steps). */
const EDITABLE_SELECTOR = "input:not([type='checkbox'], [type='radio']), textarea, select, [contenteditable='true']";

/** Parts of the page that never leave the tour: the tour's own UI, notifications. */
const IGNORED_SELECTOR = ".o_tour_pointer, .o_notification_manager";

patch(TourInteractive.prototype, {
    /** Whether the tour was started from the Tours app. */
    get isReplay() {
        return Boolean(this.config[REPLAY_CONFIG_KEY]);
    },

    /** Whether the tour is checked: played automatically, to check its steps. */
    get isCheck() {
        return Boolean(this.config[CHECK_CONFIG_KEY]);
    },

    /** Whether the tour is managed by the Tours app: a replay, or a custom tour. */
    get isManaged() {
        return this.isReplay || Boolean(this.custom);
    },

    start(env) {
        super.start(...arguments);
        this.env = env;
        // Not while reaching a step to record from: the recorder waits for it
        if (this.isReplay && !this.isPrelude) {
            this.addLeaveGuard();
        }
    },

    /**
     * Whether the tour is played automatically only to reach one of its steps
     * (e.g. to record new steps from there): the steps before are played, and
     * the tour stops before it.
     */
    get isPrelude() {
        return Number.isInteger(this.config[PLAY_UNTIL_CONFIG_KEY]);
    },

    play() {
        if (this.isPrelude && this.hasReachedPlayUntil()) {
            this.endPrelude({ reached: true });
            return;
        }
        const result = super.play(...arguments);
        if (this.isPrelude && this.currentAction) {
            clearTimeout(this.robotWatchdog);
            const actionAtCall = this.currentAction;
            this.robotWatchdog = setTimeout(() => {
                if (this.currentAction === actionAtCall) {
                    this.endPrelude({ reached: false, message: this.getFailureMessage(actionAtCall) });
                }
            }, CHECK_TIMEOUT);
        }
        if (this.isCheck && this.currentAction) {
            // Replace the watchdog of robot mode, which only throws an error,
            // by one reporting which step failed and why.
            clearTimeout(this.robotWatchdog);
            const actionAtCall = this.currentAction;
            this.robotWatchdog = setTimeout(() => {
                if (this.currentAction === actionAtCall) {
                    this.failCheck(actionAtCall);
                }
            }, CHECK_TIMEOUT);
        }
        return result;
    },

    async finish() {
        if (this.isPrelude) {
            this.endPrelude({ reached: true });
            return;
        }
        if (this.isCheck) {
            // All steps were done. The tour isn't marked as done for the user
            // who checks it, nor chained into the next onboarding tour.
            this.stopReplay();
            // Saved right away: the last action may reload the page (e.g.
            // saving preferences), after which the Tours app shows the result.
            this.saveCheckResult({
                passed: true,
                message: _t("All %s steps work.", this.steps.length),
            });
            // Let the page handle the last action (e.g. a line opened for edition)
            await new Promise((resolve) => setTimeout(resolve, CHECK_SETTLE_DELAY));
            this.reportCheck();
            return;
        }
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
        if (target.closest(EDITABLE_SELECTOR)) {
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
                    if (this.config[AUTO_START_CONFIG_KEY]) {
                        // Leaving a tour that started by itself: don't start it again
                        this.env.services.orm.silent.call("web_tour.tour", "tour_manager_dismiss", [this.name]);
                    }
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

    //--------------------------------------------------------------------------
    // Checking a tour
    //--------------------------------------------------------------------------

    /**
     * @param {Object} action the action of a step that made no progress
     */
    failCheck(action) {
        clearTimeout(this.robotWatchdog);
        this.stopReplay();
        this.saveCheckResult({
            passed: false,
            step: this.steps.indexOf(action.step) + 1,
            message: this.getFailureMessage(action),
        });
        this.reportCheck();
    },

    /**
     * @param {Object} action the action of a step that made no progress
     * @returns {string} which step failed and why
     */
    getFailureMessage(action) {
        const step = action.step;
        const reasons = step.error.length ? step.error : [_t("The step couldn't be done.")];
        return _t("Step %(step)s of %(count)s%(hint)s failed: %(reasons)s", {
            step: this.steps.indexOf(step) + 1,
            count: this.steps.length,
            hint: step.content ? ` (“${step.content}”)` : "",
            reasons: reasons.join(" "),
        });
    },

    //--------------------------------------------------------------------------
    // Playing the steps before the one to reach
    //--------------------------------------------------------------------------

    /** Whether the next action to play belongs to the step to reach. */
    hasReachedPlayUntil() {
        const action = this.actions.at(this.currentActionIndex);
        return (
            this.currentActionIndex >= this.actions.length ||
            this.steps.indexOf(action.step) >= this.config[PLAY_UNTIL_CONFIG_KEY]
        );
    },

    /**
     * Stops the tour and tells the tour creator, which waits for it, whether
     * the step was reached. Also kept in its state in the browser, as it may
     * not be listening yet (e.g. the page is loading).
     *
     * @param {{ reached: boolean, message?: string }} result
     */
    endPrelude(result) {
        clearTimeout(this.robotWatchdog);
        this.stopReplay();
        const rawData = localStorage.getItem(TOUR_CREATOR_KEY);
        if (rawData) {
            const data = JSON.parse(rawData);
            data.prelude = { ...data.prelude, ...result, done: true };
            localStorage.setItem(TOUR_CREATOR_KEY, JSON.stringify(data));
        }
        window.dispatchEvent(new CustomEvent(PRELUDE_DONE_EVENT));
    },

    /**
     * Keeps the result in the browser until the Tours app has shown it, as the
     * page may be reloaded before (e.g. by the last action of the tour).
     *
     * @param {{ passed: boolean, message: string, step?: number }} result
     */
    saveCheckResult(result) {
        localStorage.setItem(CHECK_RESULT_KEY, JSON.stringify({ name: this.name, ...result }));
    },

    /**
     * Tells the Tours app the check is done, so that it shows the result on
     * the current screen. On a page without the Tours app (e.g. of the
     * website), go to the Tours app, which shows it when loaded.
     */
    reportCheck() {
        const handled = !window.dispatchEvent(new CustomEvent(CHECK_DONE_EVENT, { cancelable: true }));
        if (!handled) {
            const result = JSON.parse(localStorage.getItem(CHECK_RESULT_KEY) || "{}");
            localStorage.setItem(CHECK_RESULT_KEY, JSON.stringify({ ...result, leftLastScreen: true }));
            window.location.assign("/odoo/tour_manager");
        }
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
     * The hint of an info step (which has no action) is shown right away, and
     * clicking it goes on with the tour.
     */
    updatePointer() {
        super.updatePointer(...arguments);
        const isInfoStep = this.custom && this.currentAction?.event === "next" && this.anchorEl;
        if (isInfoStep) {
            pointerState.content = [this.currentAction.content, _t("Click this message to continue.")]
                .filter(Boolean)
                .join(" ");
            pointerState.onClick = this.goToNextStep;
            if (this.infoStepShownFor !== this.anchorEl) {
                this.infoStepShownFor = this.anchorEl;
                const anchor = this.anchorEl;
                // The pointer opens its hint when its element is hovered
                setTimeout(() => anchor.dispatchEvent(new MouseEvent("mouseenter")), 300);
            }
        } else if (pointerState.onClick === this.goToNextStep) {
            pointerState.onClick = undefined;
        }
    },

    goToNextStep() {
        document.dispatchEvent(new Event(NEXT_EVENT));
    },

    /**
     * Interactive tours skip the steps they can't wait for. Let custom tours
     * wait for the choice of an option in a select, and for typing in an editor.
     */
    getConsumeEventType(element, runCommand) {
        const consumeEvents = super.getConsumeEventType(...arguments);
        if (this.custom && element) {
            if (runCommand === "next") {
                // An info step: done when its hint is clicked
                consumeEvents.push({ name: NEXT_EVENT, target: element.ownerDocument });
            } else if (runCommand === "select") {
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
    async doAction() {
        if (this.tour.custom && this.run === "next") {
            // An info step played automatically (e.g. by a check): go on
            await waitFor(".o_tour_pointer", { timeout: this.timeout || 10000 });
            document.dispatchEvent(new Event(NEXT_EVENT));
            return;
        }
        return super.doAction(...arguments);
    },

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
