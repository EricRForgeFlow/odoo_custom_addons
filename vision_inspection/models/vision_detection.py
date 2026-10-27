from odoo import fields, models


class VisionDetection(models.Model):
    _name = 'vision.detection'
    _description = "Vision Detection"
    _order = 'inspection_id, confidence desc, id'

    inspection_id = fields.Many2one('vision.inspection', required=True, ondelete='cascade', index=True)
    defect_class_id = fields.Many2one('vision.defect.class', string="Class", required=True, ondelete='restrict')
    label = fields.Char(readonly=True, help="Label given by the vision model.")
    confidence = fields.Float(digits=(3, 3))
    bbox_x = fields.Float(string="Left", digits=(4, 4), help="Relative to the width of the image, from 0 to 1.")
    bbox_y = fields.Float(string="Top", digits=(4, 4), help="Relative to the height of the image, from 0 to 1.")
    bbox_w = fields.Float(string="Width", digits=(4, 4))
    bbox_h = fields.Float(string="Height", digits=(4, 4))
    counted = fields.Boolean(
        readonly=True,
        help="A defect above the minimum confidence of the station, which the verdict takes into account.",
    )
    severity = fields.Selection(related='defect_class_id.severity', store=True)
    is_defect = fields.Boolean(related='defect_class_id.is_defect')
    station_id = fields.Many2one(related='inspection_id.station_id', store=True)
    product_id = fields.Many2one(related='inspection_id.product_id', store=True)
    captured_at = fields.Datetime(related='inspection_id.captured_at', store=True)
    company_id = fields.Many2one(related='inspection_id.company_id', store=True)
