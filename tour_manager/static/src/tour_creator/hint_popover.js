import { Component, useState } from "@odoo/owl";
import { useAutofocus } from "@web/core/utils/hooks";

/**
 * Asks for the hint shown to the user at a recorded step: before a click is
 * performed ("before" mode), after typing, selecting or dragging ("after"
 * mode), as the action has then already happened, or for an element picked
 * ("pick" mode: an info step, or the new element of a step).
 */
export class HintPopover extends Component {
    static template = "tour_manager.HintPopover";
    static props = {
        description: String,
        isUnique: Boolean,
        mode: { validate: (mode) => ["before", "after", "pick"].includes(mode) },
        confirmLabel: { type: String, optional: true },
        initialContent: { type: String, optional: true },
        initialPosition: { type: String, optional: true },
        onConfirm: Function,
        onSkip: Function,
        onDiscard: Function,
        close: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({
            content: this.props.initialContent || "",
            tooltipPosition: this.props.initialPosition || "bottom",
        });
        useAutofocus({ refName: "hint" });
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
