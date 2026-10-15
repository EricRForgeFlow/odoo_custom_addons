import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";

/** Prefix of the Font Awesome icons; other values are image URLs. */
export const ICON_SET_PREFIX = "fa:";

/**
 * Lets the user choose an icon among the app icons of the home screen and
 * the Font Awesome icons, which can be searched by name (e.g. "money").
 */
export class IconPickerPopover extends Component {
    static template = "tour_manager.IconPickerPopover";
    static props = {
        value: { type: String, optional: true },
        onSelect: Function,
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            tab: this.props.value?.startsWith(ICON_SET_PREFIX) ? "icons" : "apps",
            search: "",
            apps: [],
            icons: [],
        });
        this.searchIcons = useDebounced(async () => {
            this.state.icons = await this.orm.call("web_tour.tour", "tour_manager_search_icons", [
                this.state.search,
            ]);
        }, 250);
        onWillStart(async () => {
            [this.state.apps, this.state.icons] = await Promise.all([
                this.orm.call("web_tour.tour", "tour_manager_get_app_icons"),
                this.orm.call("web_tour.tour", "tour_manager_search_icons", [""]),
            ]);
        });
    }

    /**
     * @param {string} value
     */
    select(value) {
        this.props.onSelect(value);
        this.props.close?.();
    }
}
