import { animationFrame, click, queryFirst } from "@odoo/hoot-dom";
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
    // Inputs opening a menu or a picker when clicked
    ".o_select_menu input",
    ".o_datetime_input",
].join(", ");

/** Elements that can be dragged (same as the ones tours know how to drag). */
const DRAGGABLE_SELECTOR = ".o_draggable, .o-draggable, .ui-draggable, .o_we_draggable, .o_row_handle";

/** Elements in which typing is recorded as a tour step. */
const EDITABLE_SELECTOR = [
    "input:not([type='checkbox'], [type='radio'], [type='button'], [type='submit'], [type='reset'], [type='file'], [type='range'], [type='color'], [type='hidden'])",
    "textarea",
    "[contenteditable='true']",
].join(", ");

/** Pointer events blocked on a clickable element so that its click is not performed. */
const BLOCKED_EVENTS = ["pointerdown", "mousedown", "pointerup", "mouseup", "click", "dblclick"];

/** Distance (px) the pointer must move after pressing a draggable element to start a drag. */
const DRAG_THRESHOLD = 8;

/**
 * Turns a typed or selected value into the argument of a step's `run`
 * command, which is parsed as `<command> <argument>` or `<command> (<argument>)`,
 * and split on "&&".
 *
 * @param {string} value
 * @returns {string}
 */
function formatRunArgument(value) {
    const text = value.replace(/\s+/g, " ").replaceAll("&&", "&").trim();
    return /^\(|\)$/.test(text) ? `(${text})` : text;
}

/**
 * @param {string} text
 * @param {number} [length]
 * @returns {string}
 */
function shorten(text, length = 60) {
    text = text.trim().replace(/\s+/g, " ");
    return text.length > length ? `${text.slice(0, length - 1)}…` : text;
}

/**
 * Records a custom tour. Clicks are stopped, a hint is asked for them, then
 * they're performed. Typing, selecting and dragging are left to happen, then a
 * hint is asked for them. Each hint is saved as a step of the tour.
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
            /** Label of the field being typed in, if any. */
            editingLabel: "",
            pending: false,
            saving: false,
        });
        this.closeHintPopover = () => {};
        // Set while the recorder's own dialogs are open, so that their buttons work.
        this.paused = false;
        /** @type {{ element: HTMLElement, selector: string, command: string, isAutocomplete: boolean }|null} */
        this.editing = null;
        /** @type {{ element: HTMLElement, selector: string, isUnique: boolean, x: number, y: number, dragging: boolean }|null} */
        this.drag = null;
        // Set from pressing a draggable element until the click that follows,
        // so that a possible drag isn't prevented.
        this.passPointerEvents = false;
        // A drag can be followed by a click, which must not be recorded.
        this.ignoreClicksUntil = 0;
        // Listening on window during the capture phase runs before Odoo's own
        // listeners, so that clicks can be stopped before they have any effect.
        for (const eventName of BLOCKED_EVENTS) {
            useListener(window, eventName, (ev) => this.onPointerEvent(ev), { capture: true });
        }
        useListener(window, "pointermove", (ev) => this.onPointerMove(ev), { capture: true });
        useListener(window, "input", (ev) => this.onInput(ev), { capture: true });
        useListener(window, "change", (ev) => this.onChange(ev), { capture: true });
        useListener(window, "keydown", (ev) => this.onKeydown(ev), { capture: true });
        useListener(window, "focusout", (ev) => this.onFocusOut(ev), { capture: true });
    }

    get steps() {
        return this.state.data.steps;
    }

    //--------------------------------------------------------------------------
    // Event handlers
    //--------------------------------------------------------------------------

    /**
     * Returns the target of a user event that should be recorded, if any.
     *
     * @param {Event} ev
     * @returns {Element|null}
     */
    getRecordableTarget(ev) {
        // Actions replayed by the recorder (through hoot) are not trusted.
        if (!ev.isTrusted || this.state.saving || this.paused) {
            return null;
        }
        const target = ev.composedPath()[0];
        if (!(target instanceof Element) || target.closest(".o_notification_manager")) {
            return null;
        }
        if (target.closest(".o_tour_manager_ui")) {
            // Keep popovers (e.g. an open dropdown whose item is being recorded)
            // from closing because of a click in the recorder's own UI.
            if (ev.type === "pointerdown") {
                ev.stopImmediatePropagation();
            }
            return null;
        }
        return target;
    }

    /**
     * @param {PointerEvent|MouseEvent} ev
     */
    onPointerEvent(ev) {
        const target = this.getRecordableTarget(ev);
        if (!target) {
            return;
        }
        const block = () => {
            ev.preventDefault();
            ev.stopImmediatePropagation();
        };
        if (this.state.pending) {
            block();
            return;
        }
        if (ev.type === "click" && Date.now() < this.ignoreClicksUntil) {
            block();
            return;
        }
        if (ev.type === "pointerdown") {
            const draggable = target.closest(DRAGGABLE_SELECTOR);
            if (draggable) {
                const selector = getShortestSelector(draggable);
                this.drag = {
                    element: draggable,
                    selector,
                    // Computed before the drop moves the element.
                    isUnique: isSelectorUnique(selector, draggable),
                    x: ev.clientX,
                    y: ev.clientY,
                    dragging: false,
                };
                this.passPointerEvents = true;
                return;
            }
        }
        if (ev.type === "pointerup" && this.drag) {
            const drag = this.drag;
            this.drag = null;
            if (drag.dragging) {
                this.passPointerEvents = false;
                this.ignoreClicksUntil = Date.now() + 500;
                this.onDrop(drag, ev);
                return;
            }
        }
        const clickable = target.closest(CLICKABLE_SELECTOR);
        if (this.passPointerEvents && ev.type !== "click" && ev.type !== "dblclick") {
            return;
        }
        this.passPointerEvents = false;
        if (!clickable) {
            return;
        }
        block();
        if (ev.type !== "click") {
            return;
        }
        if (clickable.closest(".o-autocomplete--dropdown-item")) {
            this.onAutocompleteOptionClick(clickable);
        } else {
            // Typing in a field ends when something else is clicked.
            this.commitEditing(() => clickable.isConnected && this.askClickHint(clickable));
        }
    }

    /**
     * @param {PointerEvent} ev
     */
    onPointerMove(ev) {
        if (this.drag && !this.drag.dragging) {
            const distance = Math.hypot(ev.clientX - this.drag.x, ev.clientY - this.drag.y);
            this.drag.dragging = distance > DRAG_THRESHOLD;
        }
    }

    /**
     * @param {InputEvent} ev
     */
    onInput(ev) {
        const target = this.getRecordableTarget(ev);
        const editable = target?.closest(EDITABLE_SELECTOR);
        if (!editable || this.state.pending || this.editing?.element === editable) {
            return;
        }
        this.commitEditing();
        const isEditor = editable.matches("[contenteditable='true']");
        this.editing = {
            element: editable,
            selector: getShortestSelector(editable),
            command: isEditor ? "editor" : "edit",
            isAutocomplete: editable.classList.contains("o-autocomplete--input"),
        };
        this.state.editingLabel = this.getFieldLabel(editable);
    }

    /**
     * @param {Event} ev
     */
    onChange(ev) {
        const target = this.getRecordableTarget(ev);
        if (!target || this.state.pending) {
            return;
        }
        if (target.tagName === "SELECT") {
            this.onSelectChange(target);
        } else if (this.editing?.element === target) {
            this.commitEditing();
        }
    }

    /**
     * @param {KeyboardEvent} ev
     */
    onKeydown(ev) {
        const target = this.getRecordableTarget(ev);
        const editing = this.editing;
        if (!target || !editing || editing.element !== target || !["Enter", "Tab"].includes(ev.key)) {
            return;
        }
        if (editing.isAutocomplete) {
            const activeOption = queryFirst(".o-autocomplete--dropdown-item .ui-state-active", {
                root: target.closest(".o-autocomplete"),
            });
            if (activeOption) {
                // Let the autocomplete select the option, then ask for the hint.
                const typed = target.value;
                this.stopEditing();
                this.waitForAutocompleteSelection(target, typed).then(() =>
                    // What ends up in the input is what was actually selected.
                    this.askAutocompleteHint(editing, typed, target.value || activeOption.textContent)
                );
                return;
            }
        }
        if (ev.key === "Enter") {
            // Enter may validate the value right away (e.g. a search), without
            // any change event.
            this.commitEditing();
        }
    }

    /**
     * @param {FocusEvent} ev
     */
    onFocusOut(ev) {
        const editing = this.editing;
        if (
            editing?.command === "editor" &&
            editing.element.contains(ev.target) &&
            !editing.element.contains(ev.relatedTarget) &&
            !ev.relatedTarget?.closest(".o_tour_manager_ui") &&
            !this.state.pending
        ) {
            this.commitEditing();
        }
    }

    //--------------------------------------------------------------------------
    // Recorded actions
    //--------------------------------------------------------------------------

    /**
     * @param {HTMLElement} element
     */
    askClickHint(element) {
        const selector = getShortestSelector(element);
        this.openHintPopover(element, {
            description: _t("Clicked: %s", this.getElementLabel(element)),
            isUnique: isSelectorUnique(selector, element),
            mode: "before",
            onRecord: async (hint) => {
                this.addSteps([{ trigger: selector, run: "click", ...hint }]);
                // Perform the click the same way a tour does.
                const target = element.isConnected ? element : queryFirst(selector);
                if (target) {
                    await click(target);
                } else {
                    this.notification.add(
                        _t("The step was recorded, but its element disappeared before it could be clicked."),
                        { type: "warning" }
                    );
                }
            },
        });
    }

    /**
     * Ends the typing in the current field, asking for the hint of the typed
     * value if there's one.
     *
     * @param {() => void} [then] called once the typing is recorded (or not)
     */
    commitEditing(then = () => {}) {
        const editing = this.editing;
        if (!editing) {
            return then();
        }
        this.stopEditing();
        const { element, selector, command } = editing;
        const value = command === "editor" ? element.textContent : element.value;
        if (!element.isConnected || !value.trim()) {
            return then();
        }
        this.openHintPopover(element, {
            description: _t("Typed “%(value)s” in %(field)s", {
                value: shorten(value),
                field: this.getFieldLabel(element),
            }),
            isUnique: isSelectorUnique(selector, element),
            mode: "after",
            onRecord: (hint) =>
                this.addSteps([{ trigger: selector, run: `${command} ${formatRunArgument(value)}`, ...hint }]),
            onDone: then,
        });
    }

    stopEditing() {
        this.editing = null;
        this.state.editingLabel = "";
    }

    /**
     * An option of an autocomplete (e.g. a many2one field) is clicked: select
     * it first, as the autocomplete closes as soon as it loses the focus (e.g.
     * to the hint popover), then ask for the hint.
     *
     * @param {HTMLElement} option
     */
    async onAutocompleteOptionClick(option) {
        const input = option.closest(".o-autocomplete")?.querySelector(".o-autocomplete--input");
        if (!input) {
            return this.commitEditing(() => option.isConnected && this.askClickHint(option));
        }
        const editing =
            this.editing?.element === input
                ? this.editing
                : { element: input, selector: getShortestSelector(input) };
        // Typing in the autocomplete is recorded along with the selection.
        const typed = this.editing?.element === input ? input.value : "";
        if (this.editing?.element === input) {
            this.stopEditing();
        }
        const label = option.textContent;
        await click(option);
        this.commitEditing(() => this.askAutocompleteHint(editing, typed, label));
    }

    /**
     * @param {HTMLInputElement} input
     * @param {string} typed
     * @returns {Promise<void>} resolved once an option of the autocomplete of
     *  `input` has been selected (the autocomplete is closed and the input
     *  shows something else than what was typed), or after 2 seconds
     */
    async waitForAutocompleteSelection(input, typed) {
        const root = input.closest(".o-autocomplete");
        const start = Date.now();
        do {
            await animationFrame();
        } while (
            (root.querySelector(".o-autocomplete--dropdown-menu") || input.value === typed) &&
            Date.now() - start < 2000
        );
    }

    /**
     * Records the typing in an autocomplete (or the click opening it, when
     * nothing was typed) and the choice of one of its options, which is how
     * web_tour's recorder saves it.
     *
     * @param {{ element: HTMLElement, selector: string }} editing
     * @param {string} typed
     * @param {string} optionLabel
     */
    askAutocompleteHint(editing, typed, optionLabel) {
        const { element, selector } = editing;
        const label = optionLabel.trim().replace(/\s+/g, " ");
        const anchor = element.isConnected ? element : queryFirst(selector);
        if (!anchor) {
            return;
        }
        this.openHintPopover(anchor, {
            description: _t("Selected “%(option)s” in %(field)s", {
                option: shorten(label),
                field: this.getFieldLabel(anchor),
            }),
            isUnique: isSelectorUnique(selector, anchor),
            mode: "after",
            onRecord: (hint) =>
                this.addSteps([
                    {
                        trigger: selector,
                        run: typed ? `edit ${formatRunArgument(typed)}` : "click",
                        ...hint,
                    },
                    {
                        trigger: `.o-autocomplete--dropdown-item > a:contains('${label.replaceAll("'", "\\'")}')`,
                        run: "click",
                        ...hint,
                    },
                ]),
        });
    }

    /**
     * @param {HTMLSelectElement} select
     */
    onSelectChange(select) {
        this.commitEditing(() => {
            const selector = getShortestSelector(select);
            const option = select.selectedOptions[0];
            this.openHintPopover(select, {
                description: _t("Selected “%(option)s” in %(field)s", {
                    option: shorten(option?.textContent || select.value),
                    field: this.getFieldLabel(select),
                }),
                isUnique: isSelectorUnique(selector, select),
                mode: "after",
                onRecord: (hint) =>
                    this.addSteps([{ trigger: selector, run: `select ${formatRunArgument(select.value)}`, ...hint }]),
            });
        });
    }

    /**
     * @param {{ element: HTMLElement, selector: string, isUnique: boolean }} drag
     * @param {PointerEvent} ev the pointerup event ending the drag
     */
    onDrop(drag, ev) {
        // Find the element under the pointer, below the dragged element.
        const dropElement = document
            .elementsFromPoint(ev.clientX, ev.clientY)
            .find((el) => !drag.element.contains(el) && !el.closest(".o_tour_manager_ui"));
        if (!dropElement) {
            return;
        }
        // Drop on the whole column or row, which the tour highlights while playing.
        const dropTarget =
            dropElement.closest(".o_kanban_group") || dropElement.closest(".o_data_row") || dropElement;
        const dropSelector = getShortestSelector(dropTarget);
        const label = this.getElementLabel(drag.element);
        // Let the drop happen before asking for the hint.
        setTimeout(async () => {
            await animationFrame();
            const anchor = [dropTarget, drag.element].find((el) => el.isConnected);
            if (!anchor) {
                return;
            }
            this.commitEditing(() =>
                this.openHintPopover(anchor, {
                    description: _t("Dragged: %s", label),
                    isUnique: drag.isUnique,
                    mode: "after",
                    onRecord: (hint) =>
                        this.addSteps([
                            { trigger: drag.selector, run: `drag_and_drop ${formatRunArgument(dropSelector)}`, ...hint },
                        ]),
                })
            );
        }, 100);
    }

    //--------------------------------------------------------------------------
    // Helpers
    //--------------------------------------------------------------------------

    /**
     * @param {HTMLElement} anchor
     * @param {Object} params
     * @param {string} params.description
     * @param {boolean} params.isUnique
     * @param {"before"|"after"} params.mode
     * @param {(hint: { content?: string, tooltip_position: string }) => any} params.onRecord
     * @param {() => void} [params.onDone] called once the popover is closed, whatever the choice
     */
    openHintPopover(anchor, { description, isUnique, mode, onRecord, onDone = () => {} }) {
        this.state.pending = true;
        const done = () => {
            this.closeHintPopover();
            this.closeHintPopover = () => {};
            this.state.pending = false;
            // A click following a drag comes right after it, not after its hint.
            this.ignoreClicksUntil = 0;
        };
        this.closeHintPopover = this.popover.add(
            anchor,
            HintPopover,
            {
                description,
                isUnique,
                mode,
                onConfirm: async ({ content, tooltipPosition }) => {
                    done();
                    const hint = { tooltip_position: tooltipPosition };
                    if (content) {
                        hint.content = content;
                    }
                    await onRecord(hint);
                    onDone();
                },
                onSkip: async () => {
                    done();
                    await onRecord({ tooltip_position: "bottom" });
                    onDone();
                },
                onDiscard: () => {
                    done();
                    onDone();
                },
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
        return label ? shorten(label, 80) : element.tagName.toLowerCase();
    }

    /**
     * @param {HTMLElement} element an input, select or editor
     * @returns {string}
     */
    getFieldLabel(element) {
        const label = element.id && document.querySelector(`label[for="${CSS.escape(element.id)}"]`);
        return shorten(
            label?.innerText ||
                element.getAttribute("aria-label") ||
                element.getAttribute("placeholder") ||
                element.closest("[name]")?.getAttribute("name") ||
                _t("the field")
        );
    }

    /**
     * Adds the steps of one recorded action, which Undo removes together.
     *
     * @param {Object[]} steps
     */
    addSteps(steps) {
        const group = (this.steps.at(-1)?.group ?? 0) + 1;
        this.steps.push(...steps.map((step) => ({ ...step, group })));
        this.save();
    }

    save() {
        tourCreatorState.set(this.state.data);
    }

    undo() {
        this.stopEditing();
        const group = this.steps.at(-1)?.group;
        while (this.steps.length && this.steps.at(-1).group === group) {
            this.steps.pop();
        }
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

    finish() {
        // Record the typing in progress first, if any.
        this.commitEditing(() => this.saveTour());
    }

    async saveTour() {
        if (!this.steps.length) {
            this.notification.add(_t("Record at least one step before finishing the tour."), {
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
                    step_ids: steps.map(({ group, ...step }, index) => [
                        0,
                        0,
                        { ...step, sequence: index + 1 },
                    ]),
                },
            ]);
        } finally {
            this.state.saving = false;
        }
        this.closeHintPopover();
        this.props.onFinish(tourId, title);
    }
}
