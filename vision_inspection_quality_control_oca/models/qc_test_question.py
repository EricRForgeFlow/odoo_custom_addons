from odoo import fields, models


class QcTestQuestion(models.Model):
    _inherit = 'qc.test.question'

    vision_defect_class_id = fields.Many2one(
        'vision.defect.class',
        string="Defect Class",
        help="Quantitative question answered with the number of defects of this class a vision inspection found.",
    )
