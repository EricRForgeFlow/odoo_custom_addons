import json
import logging

from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class VisionInspectionController(http.Controller):

    @http.route(
        '/vision_inspection/<string:source_code>/results',
        type='http', auth='public', methods=['POST'], csrf=False, save_session=False,
    )
    def post_results(self, source_code):
        source = request.env['vision.source'].sudo().search([('code', '=', source_code)], limit=1)
        if not source:
            return self._error(404, f"Unknown source: {source_code}")
        token = request.httprequest.headers.get('Authorization', '').removeprefix('Bearer ').strip()
        if not source._check_token(token):
            return self._error(401, "Invalid token")
        if request.httprequest.mimetype != 'application/json':
            return self._error(415, "Send the results with 'Content-Type: application/json'")
        try:
            payload = json.loads(request.httprequest.get_data())
        except ValueError:
            return self._error(400, "The body isn't valid JSON")
        try:
            with request.env.cr.savepoint():
                inspection = source.with_user(source.user_id).with_company(source.company_id)._ingest(payload)
        except MissingError as error:
            return self._error(404, str(error))
        except AccessError as error:
            return self._error(403, str(error))
        except (UserError, ValidationError) as error:
            return self._error(400, str(error))
        return request.make_json_response({'inspection': inspection.name, 'verdict': inspection.verdict})

    def _error(self, status, message):
        _logger.info("Vision results rejected (%s): %s", status, message)
        return request.make_json_response({'error': message}, status=status)
