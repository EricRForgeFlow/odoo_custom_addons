import { Component, proxy, signal, t, useProps } from "@odoo/owl";
import { useAutofocus } from "@web/core/utils/hooks";

/**
 * Asks for the hint shown to the user at a recorded step: before a click is
 * performed ("before" mode), after typing, selecting or dragging ("after"
 * mode), as the action has then already happened, or for an element picked
 * ("pick" mode: an info step, or the new element of a step).
 */
export class HintPopover extends Component {
    static template = "tour_manager.HintPopover";
    props = useProps({
        description: t.string(),
        isUnique: t.boolean(),
        mode: t.or([t.literal("before"), t.literal("after"), t.literal("pick")]),
        confirmLabel: t.string().optional(),
        initialContent: t.string().optional(),
        initialPosition: t.string().optional(),
        onConfirm: t.function(),
        onSkip: t.function(),
        onDiscard: t.function(),
        close: t.function().optional(),
    });

    hintRef = signal.ref();

    setup() {
        this.state = proxy({
            content: this.props.initialContent || "",
            tooltipPosition: this.props.initialPosition || "bottom",
        });
        useAutofocus({ ref: this.hintRef });
    }

    confirm() {
        this.props.onConfirm({
            content: this.state.content.trim(),
            tooltipPosition: this.state.tooltipPosition,
        });
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
            ev.preventDefault();
            this.confirm();
        }
    }
}
