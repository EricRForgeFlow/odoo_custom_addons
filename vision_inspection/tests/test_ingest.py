from odoo.exceptions import MissingError, ValidationError
from odoo.tests import tagged

from .common import VisionInspectionCommon


@tagged('post_install', '-at_install')
class TestIngest(VisionInspectionCommon):

    def _ingest(self, payload, source=None):
        source = source or self.source
        return source.with_user(source.user_id)._ingest(payload)

    def test_generic_payload(self):
        inspection = self._ingest(self._generic_payload(
            [self._detection('t_crack', 0.95, x=0.25, y=0.5, w=0.1, h=0.05)],
            external_id='generic-1',
            lot='LOT-1',
            captured_at='2026-10-27T10:15:00+02:00',
        ))
        self.assertEqual(inspection.station_id, self.station)
        self.assertEqual(inspection.product_id, self.product)
        self.assertEqual(inspection.lot_name, 'LOT-1')
        self.assertEqual(inspection.external_id, 'generic-1')
        self.assertEqual(str(inspection.captured_at), '2026-10-27 08:15:00')
        self.assertEqual(inspection.model_name, 'rf-detr-nano')
        self.assertTrue(inspection.image)
        self.assertNotIn('data', inspection.raw_payload['image'])
        detection = inspection.detection_ids
        self.assertEqual(detection.defect_class_id, self.crack)
        self.assertEqual(
            [detection.bbox_x, detection.bbox_y, detection.bbox_w, detection.bbox_h],
            [0.25, 0.5, 0.1, 0.05],
        )
        self.assertEqual(inspection.create_uid, self.ingest_user)

    def test_roboflow_payload(self):
        source = self._create_source(code='roboflow', adapter='roboflow', user_id=self.ingest_user.id)
        station = self._create_station(source_id=source.id, code='rf-cam')
        inspection = self._ingest({
            'inference_id': 'rf-123',
            'station': 'rf-cam',
            'image': {'width': 640, 'height': 480},
            'predictions': [{
                'x': 320, 'y': 240, 'width': 64, 'height': 48,
                'confidence': 0.9, 'class': 't_crack', 'class_id': 1, 'detection_id': 'a',
            }],
        }, source)
        self.assertEqual(inspection.station_id, station)
        self.assertEqual(inspection.external_id, 'rf-123')
        detection = inspection.detection_ids
        self.assertAlmostEqual(detection.bbox_x, 0.45)
        self.assertAlmostEqual(detection.bbox_y, 0.45)
        self.assertAlmostEqual(detection.bbox_w, 0.1)
        self.assertAlmostEqual(detection.bbox_h, 0.1)
        self.assertEqual(inspection.verdict, 'fail')

    def test_roboflow_workflow_payload(self):
        source = self._create_source(code='rf-workflow', adapter='roboflow', user_id=self.ingest_user.id)
        self._create_station(source_id=source.id)
        inspection = self._ingest({'predictions': {
            'inference_id': 'wf-1',
            'image': {'width': 100, 'height': 100},
            'predictions': [{'x': 50, 'y': 50, 'width': 10, 'height': 10, 'confidence': 0.8, 'class': 't_scratch'}],
        }}, source)
        self.assertEqual(inspection.external_id, 'wf-1')
        self.assertAlmostEqual(inspection.detection_ids.bbox_x, 0.45)

    def test_roboflow_without_image_size(self):
        source = self._create_source(code='rf-bad', adapter='roboflow', user_id=self.ingest_user.id)
        self._create_station(source_id=source.id)
        with self.assertRaises(ValidationError):
            self._ingest({'predictions': []}, source)

    def test_product_code(self):
        inspection = self._ingest(self._generic_payload(product_code='VIS-OTHER'))
        self.assertEqual(inspection.product_id, self.other_product)
        with self.assertRaises(MissingError):
            self._ingest(self._generic_payload(product_code='UNKNOWN'))

    def test_station(self):
        with self.assertRaises(MissingError):
            self._ingest(self._generic_payload(station='unknown'))
        inspection = self._ingest(self._generic_payload(station=None))
        self.assertEqual(inspection.station_id, self.station, "The only station of the source is used")
        self._create_station(source_id=self.source.id, code='second')
        with self.assertRaises(MissingError):
            self._ingest(self._generic_payload(station=None))

    def test_invalid_payloads(self):
        for payload in (
            [],
            self._generic_payload([{'confidence': 0.9}]),
            self._generic_payload([self._detection('t_crack', confidence='high')]),
            self._generic_payload(verdict='maybe'),
            self._generic_payload(captured_at='yesterday'),
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                self._ingest(payload)

    def test_unknown_label_creates_class(self):
        inspection = self._ingest(self._generic_payload([self._detection('t_dent')]))
        dent = self.DefectClass.search([('code', '=', 't_dent')])
        self.assertTrue(dent)
        self.assertEqual(inspection.detection_ids.defect_class_id, dent)
        self.assertIn('t_dent', inspection.message_ids[0].body)
        self.assertEqual(inspection.verdict, 'fail', "A new class allows no defect by default")

    def test_archived_class_is_reused(self):
        self.crack.active = False
        inspection = self._ingest(self._generic_payload([self._detection('t_crack')]))
        self.assertEqual(inspection.detection_ids.defect_class_id, self.crack)

    def test_idempotent_external_id(self):
        first = self._ingest(self._generic_payload([self._detection('t_crack')], external_id='same'))
        second = self._ingest(self._generic_payload([], external_id='same'))
        self.assertEqual(first, second)
        self.assertFalse(second.detection_ids)
        self.assertEqual(second.verdict, 'pass')
        self.assertEqual(self.Inspection.search_count([('external_id', '=', 'same')]), 1)

    def test_verdict_rules(self):
        cases = [
            ([], 'pass'),
            ([self._detection('t_scratch', 0.9)], 'pass'),
            ([self._detection('t_scratch', 0.9), self._detection('t_scratch', 0.9)], 'fail'),
            ([self._detection('t_crack', 0.9)], 'fail'),
            ([self._detection('t_crack', 0.3)], 'pass'),
            ([self._detection('t_scratch', 0.6)], 'review'),
            ([self._detection('t_part', 0.99), self._detection('t_part', 0.99)], 'pass'),
        ]
        for detections, verdict in cases:
            with self.subTest(detections=detections):
                inspection = self._ingest(self._generic_payload(detections))
                self.assertEqual(inspection.verdict, verdict)
                self.assertEqual(inspection.verdict_origin, 'computed')

    def test_counted_detections(self):
        inspection = self._ingest(self._generic_payload([
            self._detection('t_crack', 0.3),
            self._detection('t_scratch', 0.8),
            self._detection('t_part', 0.9),
        ]))
        self.assertEqual(inspection.defect_count, 1)
        self.assertEqual(inspection.detection_ids.filtered('counted').defect_class_id, self.scratch)

    def test_source_verdict(self):
        inspection = self._ingest(self._generic_payload([self._detection('t_crack')], verdict='pass'))
        self.assertEqual(inspection.verdict, 'fail', "Odoo rules ignore the verdict of the source")
        self.station.verdict_mode = 'source'
        inspection = self._ingest(self._generic_payload([self._detection('t_crack')], verdict='pass'))
        self.assertEqual(inspection.verdict, 'pass')
        self.assertEqual(inspection.verdict_origin, 'source')
        inspection = self._ingest(self._generic_payload([self._detection('t_crack')]))
        self.assertEqual(inspection.verdict, 'fail', "Without a verdict, Odoo rules apply")

    def test_manual_verdict(self):
        inspection = self._ingest(self._generic_payload([self._detection('t_crack')]))
        inspection.with_user(self.ingest_user).action_mark_pass()
        self.assertEqual(inspection.verdict, 'pass')
        self.assertEqual(inspection.verdict_origin, 'manual')
        inspection.action_mark_fail()
        self.assertEqual(inspection.verdict, 'fail')

    def test_station_confidences(self):
        with self.assertRaises(ValidationError):
            self.station.write({'min_confidence': 0.8, 'review_confidence': 0.6})

    def test_token(self):
        self.assertTrue(self.source._check_token('test-token'))
        self.assertFalse(self.source._check_token('wrong'))
        self.assertFalse(self.source._check_token(''))
        self.source.action_regenerate_token()
        self.assertFalse(self.source._check_token('test-token'))
        self.assertTrue(self.source._check_token(self.source.token))
