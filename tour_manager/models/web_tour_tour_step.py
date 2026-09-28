from odoo import api, fields, models


class Web_TourTourStep(models.Model):
    _inherit = 'web_tour.tour.step'

    check_failed = fields.Boolean(
        compute='_compute_check_failed',
        help="Whether the last check of the tour failed at this step.",
    )

    number = fields.Integer(
        string="#",
        compute='_compute_number',
        help="Number of the step, in the order the steps are played.",
    )

    @api.depends('tour_id.step_ids.sequence')
    def _compute_number(self):
        self.number = 0
        for tour in self.tour_id:
            for number, step in enumerate(tour._get_ordered_steps(), start=1):
                if step in self:
                    step.number = number

    @api.depends('tour_id.check_state', 'tour_id.check_step', 'tour_id.step_ids')
    def _compute_check_failed(self):
        self.check_failed = False
        for tour in self.tour_id.filtered(lambda tour: tour.check_state == 'failed' and tour.check_step):
            # check_step is the number of the step, in the order they're played
            steps = tour._get_ordered_steps()
            if tour.check_step <= len(steps):
                failed_step = steps[tour.check_step - 1]
                if failed_step in self:
                    failed_step.check_failed = True

    def action_pick_element(self):
        """Pick the element of the step again: its tour plays the steps before
        it automatically, to reach its screen, then the user clicks the element."""
        self.ensure_one()
        return self.tour_id._get_edit_action('pick', self.number - 1, step=self)

    def action_record_after(self):
        """Record new steps after this one: its tour plays the steps up to it
        automatically, to reach its screen, then the recording starts."""
        self.ensure_one()
        return self.tour_id._get_edit_action('insert', self.number)

    def tour_manager_update_target(self, trigger, content, tooltip_position):
        """Update the element (and hint) of the step, picked again."""
        self.ensure_one()
        self.write({
            'trigger': trigger,
            'content': content or False,
            'tooltip_position': tooltip_position,
        })
