from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        result = super().session_info()
        result['tour_manager_auto_tours'] = self.env['web_tour.tour']._get_auto_start_tours()
        return result
