from odoo import api, fields, models


class Web_TourTourStep(models.Model):
    _inherit = 'web_tour.tour.step'

    check_failed = fields.Boolean(
        compute='_compute_check_failed',
        help="Whether the last check of the tour failed at this step.",
    )

    @api.depends('tour_id.check_state', 'tour_id.check_step', 'tour_id.step_ids')
    def _compute_check_failed(self):
        self.check_failed = False
        for tour in self.tour_id.filtered(lambda tour: tour.check_state == 'failed' and tour.check_step):
            # check_step is the number of the step, in the order they're played
            steps = tour.step_ids.sorted(lambda step: (step.sequence, step.id))
            if tour.check_step <= len(steps):
                failed_step = steps[tour.check_step - 1]
                if failed_step in self:
                    failed_step.check_failed = True
