from odoo import fields, models


class VisionStation(models.Model):
    _inherit = 'vision.station'

    qc_test_id = fields.Many2one(
        'qc.test',
        string="Quality Test",
        check_company=True,
        help="Test of the quality control inspections created for the inspections of this station.",
    )
    qc_trigger = fields.Selection(
        selection=[
            ('always', "Every Inspection"),
            ('not_pass', "Inspections that Don't Pass"),
            ('never', "Never"),
        ],
        string="Create Quality Inspections For",
        required=True,
        default='not_pass',
    )
