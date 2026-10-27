import hmac
import secrets
from datetime import UTC, datetime

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .vision_inspection import VERDICTS


def _generate_token():
    return secrets.token_urlsafe(32)


class VisionSource(models.Model):
    _name = 'vision.source'
    _description = "Vision Source"
    _order = 'name, id'

    name = fields.Char(required=True)
    code = fields.Char(
        required=True,
        copy=False,
        help="Identifies the source in the URL of its endpoint.",
    )
    active = fields.Boolean(default=True)
    adapter = fields.Selection(
        selection=[('generic', "Generic"), ('roboflow', "Roboflow Inference")],
        required=True,
        default='generic',
        help="Format of the results the system sends.",
    )
    token = fields.Char(
        copy=False,
        default=lambda self: _generate_token(),
        groups='vision_inspection.group_vision_manager',
        help="Sent by the system as 'Authorization: Bearer <token>'.",
    )
    user_id = fields.Many2one(
        'res.users',
        string="Run As",
        required=True,
        default=lambda self: self.env.user,
        help="User the inspections are created as.",
    )
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    station_ids = fields.One2many('vision.station', 'source_id', string="Stations")
    endpoint_url = fields.Char(string="Endpoint", compute='_compute_endpoint_url')
    inspection_count = fields.Integer(compute='_compute_inspection_count')

    _code_uniq = models.Constraint('unique(code)', "The code of a vision source must be unique.")

    @api.depends('code')
    def _compute_endpoint_url(self):
        for source in self:
            source.endpoint_url = source.code and f'{source.get_base_url()}/vision_inspection/{source.code}/results'

    def _compute_inspection_count(self):
        counts = dict(self.env['vision.inspection']._read_group(
            [('source_id', 'in', self.ids)], ['source_id'], ['__count'],
        ))
        for source in self:
            source.inspection_count = counts.get(source, 0)

    def action_regenerate_token(self):
        for source in self:
            source.token = _generate_token()

    def action_view_inspections(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('vision_inspection.vision_inspection_action')
        action['domain'] = [('source_id', '=', self.id)]
        action['context'] = {'default_source_id': self.id}
        return action

    def _check_token(self, token):
        self.ensure_one()
        expected = self.sudo().token
        return bool(expected and token) and hmac.compare_digest(expected.encode(), token.encode())

    def _ingest(self, payload):
        """Store the results sent by the system and return the inspection."""
        self.ensure_one()
        if not isinstance(payload, dict):
            raise ValidationError(self.env._("The results must be a JSON object."))
        values = getattr(self, f'_parse_payload_{self.adapter}')(payload)
        values['raw_payload'] = self._strip_image_data(payload)
        return self.env['vision.inspection']._ingest(self, values)

    def _strip_image_data(self, payload):
        raw = {key: value for key, value in payload.items() if key != 'image_base64'}
        if isinstance(raw.get('image'), dict):
            raw['image'] = {key: value for key, value in raw['image'].items() if key != 'data'}
        return raw

    def _parse_common(self, payload):
        captured_at = payload.get('captured_at')
        if captured_at:
            try:
                captured_at = datetime.fromisoformat(captured_at)
            except (TypeError, ValueError):
                raise ValidationError(self.env._("Invalid date: %s", captured_at)) from None
            if captured_at.tzinfo:
                captured_at = captured_at.astimezone(UTC).replace(tzinfo=None)
        verdict = payload.get('verdict')
        if verdict and verdict not in dict(VERDICTS):
            raise ValidationError(self.env._("Invalid verdict: %s", verdict))
        return {
            'external_id': payload.get('external_id') and str(payload['external_id']),
            'station_code': payload.get('station'),
            'captured_at': captured_at or fields.Datetime.now(),
            'product_code': payload.get('product_code'),
            'lot_name': payload.get('lot'),
            'verdict': verdict,
        }

    def _parse_payload_generic(self, payload):
        values = self._parse_common(payload)
        model = payload.get('model') or {}
        image = payload.get('image') or {}
        values.update({
            'model_name': model.get('name'),
            'model_version': model.get('version'),
            'image': image.get('data'),
            'detections': [],
        })
        for detection in payload.get('detections') or []:
            bbox = detection.get('bbox') or {}
            try:
                values['detections'].append({
                    'label': str(detection['label']),
                    'confidence': float(detection.get('confidence', 1.0)),
                    'bbox_x': float(bbox.get('x', 0.0)),
                    'bbox_y': float(bbox.get('y', 0.0)),
                    'bbox_w': float(bbox.get('w', 0.0)),
                    'bbox_h': float(bbox.get('h', 0.0)),
                })
            except (KeyError, TypeError, ValueError):
                raise ValidationError(self.env._("Invalid detection: %s", detection)) from None
        return values

    def _parse_payload_roboflow(self, payload):
        """Roboflow Inference results: boxes in pixels, centered on (x, y).

        Workflows nest them one level deeper, in their 'predictions' output.
        """
        values = self._parse_common(payload)
        results = payload
        predictions = payload.get('predictions')
        if isinstance(predictions, dict):
            results, predictions = predictions, predictions.get('predictions')
        image = results.get('image') or {}
        try:
            width, height = float(image['width']), float(image['height'])
        except (KeyError, TypeError, ValueError):
            raise ValidationError(self.env._("The results don't give the size of the image.")) from None
        values.update({
            'external_id': values['external_id'] or results.get('inference_id') or payload.get('inference_id'),
            'model_name': payload.get('model_id'),
            'image': payload.get('image_base64'),
            'detections': [],
        })
        for prediction in predictions or []:
            try:
                w, h = float(prediction['width']), float(prediction['height'])
                values['detections'].append({
                    'label': str(prediction['class']),
                    'confidence': float(prediction['confidence']),
                    'bbox_x': (float(prediction['x']) - w / 2) / width,
                    'bbox_y': (float(prediction['y']) - h / 2) / height,
                    'bbox_w': w / width,
                    'bbox_h': h / height,
                })
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                raise ValidationError(self.env._("Invalid prediction: %s", prediction)) from None
        return values
