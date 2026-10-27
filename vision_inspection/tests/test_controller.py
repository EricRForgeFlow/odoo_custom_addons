import json

from odoo.tests import HttpCase, tagged

from .common import VisionInspectionCommon


@tagged('post_install', '-at_install')
class TestController(VisionInspectionCommon, HttpCase):

    def _post(self, data, code='test-source', token='test-token', content_type='application/json'):
        headers = {'Content-Type': content_type, 'X-Odoo-Database': self.env.cr.dbname}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        if not isinstance(data, str):
            data = json.dumps(data)
        return self.url_open(f'/vision_inspection/{code}/results', data=data, headers=headers)

    def test_post_results(self):
        response = self._post(self._generic_payload([self._detection('t_crack')], external_id='http-1'))
        self.assertEqual(response.status_code, 200)
        inspection = self.Inspection.search([('external_id', '=', 'http-1')])
        self.assertEqual(response.json(), {'inspection': inspection.name, 'verdict': 'fail'})
        self.assertEqual(inspection.create_uid, self.ingest_user)
        self.assertEqual(inspection.detection_ids.defect_class_id, self.crack)

    def test_authentication(self):
        payload = self._generic_payload()
        self.assertEqual(self._post(payload, token=None).status_code, 401)
        self.assertEqual(self._post(payload, token='wrong').status_code, 401)
        self.assertEqual(self._post(payload, code='unknown').status_code, 404)

    def test_invalid_requests(self):
        self.assertEqual(self._post('{not json').status_code, 400)
        self.assertEqual(self._post(self._generic_payload(), content_type='application/x-www-form-urlencoded').status_code, 415)
        self.assertEqual(self._post(self._generic_payload(verdict='maybe')).status_code, 400)
        self.assertEqual(self._post(self._generic_payload(station='unknown')).status_code, 404)

    def test_access_error(self):
        self.ingest_user.group_ids = self.env.ref('base.group_user')
        response = self._post(self._generic_payload([self._detection('t_new_label')]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            self.DefectClass.search([('code', '=', 't_new_label')]),
            "Nothing of rejected results is stored",
        )
