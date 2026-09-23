import { Component, signal, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { usePopover } from "@web/core/popover/popover_hook";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { ICON_SET_PREFIX, IconPickerPopover } from "./icon_picker_popover";

/**
 * Char field holding an icon: an icon of Odoo's icon set ("oi:<name>") or the
 * URL of an image (e.g. an app icon), chosen in a popover.
 */
export class IconPickerField extends Component {
    static template = "tour_manager.IconPickerField";
    props = useProps({ ...standardFieldProps });

    buttonRef = signal.ref();

    setup() {
        this.popover = usePopover(IconPickerPopover, { position: "bottom" });
    }

    get value() {
        return this.props.record.data[this.props.name] || "";
    }

    get iconName() {
        return this.value.startsWith(ICON_SET_PREFIX) ? this.value.slice(ICON_SET_PREFIX.length) : "";
    }

    open() {
        this.popover.open(this.buttonRef(), {
            value: this.value,
            onSelect: (value) => this.props.record.update({ [this.props.name]: value }),
        });
    }

    clear() {
        this.props.record.update({ [this.props.name]: false });
    }
}

registry.category("fields").add("tour_manager_icon_picker", {
    component: IconPickerField,
    displayName: _t("Icon"),
    supportedTypes: ["char"],
});
