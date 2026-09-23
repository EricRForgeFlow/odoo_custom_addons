import { Component, onWillStart, proxy, t, usePlugin, useProps } from "@odoo/owl";
import { ORM } from "@web/core/orm_plugin";
import { useDebounced } from "@web/core/utils/timing";

/** Prefix of the icons of Odoo's icon set; other values are image URLs. */
export const ICON_SET_PREFIX = "oi:";

/**
 * Lets the user choose an icon among the app icons of the home screen and
 * Odoo's icon set, which can be searched by name or by tags (e.g. "money").
 */
export class IconPickerPopover extends Component {
    static template = "tour_manager.IconPickerPopover";
    props = useProps({
        value: t.string().optional(),
        onSelect: t.function(),
        close: t.function().optional(),
    });

    setup() {
        this.orm = usePlugin(ORM);
        this.state = proxy({
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
