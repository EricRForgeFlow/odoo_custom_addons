from odoo import api, fields, models
from odoo.exceptions import ValidationError


class VisionStation(models.Model):
    _name = 'vision.station'
    _description = "Vision Station"
    _order = 'source_id, name, id'

    name = fields.Char(required=True)
    code = fields.Char(required=True, help="Identifies the station in the results its source sends.")
    active = fields.Boolean(default=True)
    source_id = fields.Many2one('vision.source', string="Source", required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='source_id.company_id', store=True)
    product_id = fields.Many2one(
        'product.product',
        string="Product",
        help="Product inspected when the results don't say which one.",
    )
    min_confidence = fields.Float(
        string="Minimum Confidence",
        default=0.5,
        help="Detections below this confidence are kept but ignored.",
    )
    review_confidence = fields.Float(
        default=0.7,
        help="Detections between the minimum and this confidence send the inspection to review.",
    )
    verdict_mode = fields.Selection(
        selection=[('odoo', "Odoo Rules"), ('source', "Sent by the Source")],
        string="Verdict",
        required=True,
        default='odoo',
        help="Odoo Rules: Odoo decides from the detections and the defect classes.\n"
             "Sent by the Source: the verdict in the results is used when there is one.",
    )
    inspection_count = fields.Integer(compute='_compute_inspection_count')

    _code_uniq = models.Constraint('unique(source_id, code)', "The code of a station must be unique per source.")

    @api.constrains('min_confidence', 'review_confidence')
    def _check_confidence(self):
        for station in self:
            if not 0.0 <= station.min_confidence <= station.review_confidence <= 1.0:
                raise ValidationError(self.env._(
                    "Confidences must be between 0 and 1, the minimum one not above the review one.",
                ))

    def _compute_inspection_count(self):
        counts = dict(self.env['vision.inspection']._read_group(
            [('station_id', 'in', self.ids)], ['station_id'], ['__count'],
        ))
        for station in self:
            station.inspection_count = counts.get(station, 0)

    def action_view_inspections(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('vision_inspection.vision_inspection_action')
        action['domain'] = [('station_id', '=', self.id)]
        return action
