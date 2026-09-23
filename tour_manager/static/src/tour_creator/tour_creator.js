import { click, queryFirst } from "@odoo/hoot-dom";
import { Component, proxy, t, useListener, usePlugin, useProps } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { DialogPlugin } from "@web/core/dialog/dialog_plugin";
import { _t } from "@web/core/l10n/translation";
import { NotificationPlugin } from "@web/core/notifications/notification_plugin";
import { ORM } from "@web/core/orm_plugin";
import { PopoverPlugin } from "@web/core/popover/popover_plugin";
import { tourCreatorState } from "@tour_manager/tour_creator_state";
import { HintPopover } from "./hint_popover";
import { getShortestSelector, isSelectorUnique } from "./selector";

/** Elements whose click is recorded as a tour step. */
const CLICKABLE_SELECTOR = [
    "button",
    "a",
    "[role='button']",
    "[role='menuitem']",
    "[role='menuitemcheckbox']",
    "[role='menuitemradio']",
    "[role='tab']",
    "[role='option']",
    "[role='checkbox']",
    "[role='switch']",
    ".dropdown-item",
    "input[type='checkbox']",
    "input[type='radio']",
    ".o_kanban_record",
    ".o_data_row",
].join(", ");

/** Events blocked on a clickable element so that its click is not performed. */
const BLOCKED_EVENTS = ["pointerdown", "mousedown", "pointerup", "mouseup", "click", "dblclick"];

/**
 * Records a custom tour: each click on a clickable element is stopped, a hint
 * is asked for it, then the click is performed and recorded as a step.
 */
export class TourCreator extends Component {
    static template = "tour_manager.TourCreator";
    props = useProps({
        onCancel: t.function(),
        onFinish: t.function(),
    });

    setup() {
        this.dialog = usePlugin(DialogPlugin);
        this.notification = usePlugin(NotificationPlugin);
        this.orm = usePlugin(ORM);
        this.popover = usePlugin(PopoverPlugin);
        this.state = proxy({
            data: tourCreatorState.get(),
            pending: false,
            saving: false,
        });
        this.closeHintPopover = () => {};
        // Set while the recorder's own dialogs are open, so that their buttons work.
        this.paused = false;
        // Listening on window during the capture phase runs before Odoo's own
        // listeners, so that clicks can be stopped before they have any effect.
        for (const eventName of BLOCKED_EVENTS) {
            useListener(window, eventName, (ev) => this.onPointerEvent(ev), { capture: true });
        }
    }

    get steps() {
        return this.state.data.steps;
    }

    /**
     * @param {PointerEvent|MouseEvent} ev
     */
    onPointerEvent(ev) {
        // Clicks replayed by the recorder (through hoot) are not trusted.
        if (!ev.isTrusted || this.state.saving || this.paused) {
            return;
        }
        const target = ev.composedPath()[0];
        if (!(target instanceof Element)) {
            return;
        }
        if (target.closest(".o_notification_manager")) {
            return;
        }
        if (target.closest(".o_tour_manager_ui")) {
            // Keep popovers (e.g. an open dropdown whose item is being recorded)
            // from closing because of a click in the recorder's own UI.
            if (ev.type === "pointerdown") {
                ev.stopImmediatePropagation();
            }
            return;
        }
        const clickable = target.closest(CLICKABLE_SELECTOR);
        if (!clickable && !this.state.pending) {
            return;
        }
        ev.preventDefault();
        ev.stopImmediatePropagation();
        if (clickable && ev.type === "click" && !this.state.pending) {
            this.askHint(clickable);
        }
    }

    /**
     * @param {HTMLElement} element
     */
    askHint(element) {
        const selector = getShortestSelector(element);
        this.state.pending = true;
        const done = () => {
            this.closeHintPopover();
            this.state.pending = false;
        };
        this.closeHintPopover = this.popover.add(
            element,
            HintPopover,
            {
                label: this.getElementLabel(element),
                isUnique: isSelectorUnique(selector, element),
                onConfirm: ({ content, tooltipPosition }) => {
                    done();
                    this.addStep(element, selector, content, tooltipPosition);
                },
                onSkip: () => {
                    done();
                    this.addStep(element, selector, "", "bottom");
                },
                onDiscard: done,
            },
            {
                closeOnClickAway: false,
                closeOnEscape: false,
                popoverClass: "o_tour_manager_ui",
                position: "bottom",
            }
        );
    }

    /**
     * @param {HTMLElement} element
     * @returns {string}
     */
    getElementLabel(element) {
        const label =
            element.getAttribute("aria-label") ||
            element.getAttribute("title") ||
            element.getAttribute("data-tooltip") ||
            element.innerText;
        return label?.trim().replace(/\s+/g, " ").slice(0, 80) || element.tagName.toLowerCase();
    }

    /**
     * Records the step, then performs its click the same way a tour does.
     */
    async addStep(element, selector, content, tooltipPosition) {
        const step = { trigger: selector, run: "click", tooltip_position: tooltipPosition };
        if (content) {
            step.content = content;
        }
        this.steps.push(step);
        this.save();
        const target = element.isConnected ? element : queryFirst(selector);
        if (!target) {
            this.notification.add(
                _t("The step was recorded, but its element disappeared before it could be clicked."),
                { type: "warning" }
            );
            return;
        }
        await click(target);
    }

    save() {
        tourCreatorState.set(this.state.data);
    }

    undo() {
        this.steps.pop();
        this.save();
    }

    cancel() {
        this.paused = true;
        this.dialog.add(
            ConfirmationDialog,
            {
                title: _t("Cancel the recording?"),
                body: _t("The tour and all its recorded steps will be lost."),
                confirmLabel: _t("Cancel recording"),
                cancelLabel: _t("Continue recording"),
                confirm: () => {
                    this.closeHintPopover();
                    this.props.onCancel();
                },
                cancel: () => {},
            },
            { onClose: () => (this.paused = false) }
        );
    }

    async finish() {
        if (!this.steps.length) {
            this.notification.add(_t("Click on at least one element before finishing the tour."), {
                type: "warning",
            });
            return;
        }
        this.state.saving = true;
        const { title, name, url, rainbow_man_message, steps } = this.state.data;
        let tourId;
        try {
            [tourId] = await this.orm.create("web_tour.tour", [
                {
                    title,
                    name,
                    url,
                    rainbow_man_message,
                    custom: true,
                    step_ids: steps.map((step, index) => [0, 0, { ...step, sequence: index + 1 }]),
                },
            ]);
        } finally {
            this.state.saving = false;
        }
        this.closeHintPopover();
        this.props.onFinish(tourId, title);
    }
}
