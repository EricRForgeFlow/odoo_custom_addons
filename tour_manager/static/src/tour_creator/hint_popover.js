import { Component, proxy, signal, t, useProps } from "@odoo/owl";
import { useAutofocus } from "@web/core/utils/hooks";

/**
 * Asks for the hint shown to the user at a recorded step, before the click
 * on the step's element is performed.
 */
export class HintPopover extends Component {
    static template = "tour_manager.HintPopover";
    props = useProps({
        label: t.string(),
        isUnique: t.boolean(),
        onConfirm: t.function(),
        onSkip: t.function(),
        onDiscard: t.function(),
        close: t.function().optional(),
    });

    hintRef = signal.ref();

    setup() {
        this.state = proxy({ content: "", tooltipPosition: "bottom" });
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
