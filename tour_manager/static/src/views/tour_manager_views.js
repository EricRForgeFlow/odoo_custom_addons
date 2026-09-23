import { registry } from "@web/core/registry";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { OnboardingModeToggle } from "./onboarding_mode_toggle";

export class TourManagerKanbanController extends KanbanController {
    static template = "tour_manager.KanbanView";
    static components = { ...KanbanController.components, OnboardingModeToggle };
}

export class TourManagerListController extends ListController {
    static template = "tour_manager.ListView";
    static components = { ...ListController.components, OnboardingModeToggle };
}

registry.category("views").add("tour_manager_kanban", {
    ...kanbanView,
    Controller: TourManagerKanbanController,
});
registry.category("views").add("tour_manager_list", {
    ...listView,
    Controller: TourManagerListController,
});
