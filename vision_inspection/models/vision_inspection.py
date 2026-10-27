from odoo import api, fields, models
from odoo.exceptions import MissingError
from odoo.fields import Command

VERDICTS = [('pass', "Pass"), ('review', "To Review"), ('fail', "Fail")]


class VisionInspection(models.Model):
    _name = 'vision.inspection'
    _description = "Vision Inspection"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'captured_at desc, id desc'

    name = fields.Char(string="Reference", required=True, readonly=True, copy=False, default=lambda self: self.env._("New"))
    station_id = fields.Many2one('vision.station', string="Station", required=True, ondelete='restrict', index=True)
    source_id = fields.Many2one(related='station_id.source_id', store=True, index=True)
    company_id = fields.Many2one(related='station_id.company_id', store=True)
    external_id = fields.Char(string="External ID", readonly=True, copy=False, help="Identifier given by the source.")
    captured_at = fields.Datetime(string="Captured On", required=True, default=fields.Datetime.now)
    product_id = fields.Many2one('product.product', string="Product", index=True)
    lot_name = fields.Char(string="Lot/Serial Number")
    image = fields.Image(max_width=1920, max_height=1920)
    image_256 = fields.Image(string="Thumbnail", related='image', max_width=256, max_height=256, store=True)
    model_name = fields.Char(string="Model", readonly=True)
    model_version = fields.Char(readonly=True)
    detection_ids = fields.One2many('vision.detection', 'inspection_id', string="Detections")
    defect_count = fields.Integer(string="Defects", compute='_compute_defect_count', store=True)
    verdict = fields.Selection(selection=VERDICTS, required=True, default='pass', tracking=True)
    verdict_origin = fields.Selection(
        selection=[('computed', "Odoo Rules"), ('source', "Source"), ('manual', "Manual")],
        readonly=True,
    )
    raw_payload = fields.Json(string="Received Results", readonly=True, copy=False)

    _external_id_uniq = models.Constraint(
        'unique(source_id, external_id)',
        "A source can't send two inspections with the same external ID.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', self.env._("New")) == self.env._("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('vision.inspection') or self.env._("New")
        return super().create(vals_list)

    @api.depends('detection_ids.counted')
    def _compute_defect_count(self):
        for inspection in self:
            inspection.defect_count = len(inspection.detection_ids.filtered('counted'))

    def action_mark_pass(self):
        self._set_manual_verdict('pass')

    def action_mark_fail(self):
        self._set_manual_verdict('fail')

    def _set_manual_verdict(self, verdict):
        self.write({'verdict': verdict, 'verdict_origin': 'manual'})
        self._after_verdict_override()

    @api.model
    def _ingest(self, source, values):
        station = self._find_station(source, values.get('station_code'))
        product = station.product_id
        if values.get('product_code'):
            product = self.env['product.product'].search([('default_code', '=', values['product_code'])], limit=1)
            if not product:
                raise MissingError(self.env._("Unknown product: %s", values['product_code']))
        labels = {detection['label'] for detection in values['detections']}
        classes, new_classes = self.env['vision.defect.class'].sudo()._get_for_labels(labels)
        detection_commands = [Command.clear()]
        for detection in values['detections']:
            defect_class = classes[detection['label']]
            detection_commands.append(Command.create({
                **detection,
                'defect_class_id': defect_class.id,
                'counted': defect_class.is_defect and detection['confidence'] >= station.min_confidence,
            }))
        vals = {
            'station_id': station.id,
            'captured_at': values['captured_at'],
            'product_id': product.id,
            'lot_name': values.get('lot_name'),
            'model_name': values.get('model_name'),
            'model_version': values.get('model_version'),
            'detection_ids': detection_commands,
            'raw_payload': values.get('raw_payload'),
        }
        if values.get('image'):
            vals['image'] = values['image']
        inspection = values.get('external_id') and self.search([
            ('source_id', '=', source.id),
            ('external_id', '=', values['external_id']),
        ], limit=1)
        if inspection:
            inspection.write(vals)
        else:
            inspection = self.create({**vals, 'external_id': values.get('external_id')})
        inspection._apply_verdict(values.get('verdict'))
        if new_classes:
            inspection.message_post(body=self.env._(
                "New defect classes created from the labels of the model: %s",
                ", ".join(new_classes.mapped('code')),
            ))
        inspection._after_ingest()
        return inspection

    @api.model
    def _find_station(self, source, code):
        stations = source.station_ids
        station = stations.filtered(lambda s: s.code == code) if code else len(stations) == 1 and stations
        if not station:
            raise MissingError(self.env._("Unknown station for source %(source_code)s: %(code)s", source_code=source.code, code=code))
        return station

    def _apply_verdict(self, source_verdict=None):
        for inspection in self:
            if inspection.station_id.verdict_mode == 'source' and source_verdict:
                inspection.write({'verdict': source_verdict, 'verdict_origin': 'source'})
            else:
                inspection.write({'verdict': inspection._get_rule_verdict(), 'verdict_origin': 'computed'})

    def _get_rule_verdict(self):
        self.ensure_one()
        counted = self.detection_ids.filtered('counted')
        for defect_class, detections in counted.grouped('defect_class_id').items():
            if len(detections) > defect_class.max_allowed:
                return 'fail'
        if any(detection.confidence < self.station_id.review_confidence for detection in counted):
            return 'review'
        return 'pass'

    def _after_ingest(self):
        """Hook called once the results of a source are stored."""

    def _after_verdict_override(self):
        """Hook called when a user changes the verdict."""
