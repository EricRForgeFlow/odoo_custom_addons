import { registry } from "@web/core/registry";
import { forgetCurrentApp } from "@tour_manager/tours_app";

registry.category("actions").add("tour_manager.check_tour", (env, action) => {
    const { name, url, rainbow_man_message } = action.params;
    forgetCurrentApp();
    return env.services.tour_manager_replay.startReplay(name, {
        url,
        rainbowManMessage: rainbow_man_message,
        check: true,
    });
});

registry.category("actions").add("tour_manager.start_tour", (env, action) => {
    const { name, url, rainbow_man_message } = action.params;
    forgetCurrentApp();
    return env.services.tour_manager_replay.startReplay(name, {
        url,
        rainbowManMessage: rainbow_man_message,
    });
});
