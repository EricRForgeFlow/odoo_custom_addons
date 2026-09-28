import { usePlugin } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { forgetCurrentApp } from "@tour_manager/tours_app";
import { TourReplayPlugin } from "./tour_replay_plugin";

// Exposes the replay plugin to client actions, which only get the env.
registry.category("services").add("tour_manager_replay", {
    dependencies: ["tour_service"],
    start() {
        return usePlugin(TourReplayPlugin);
    },
});

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
