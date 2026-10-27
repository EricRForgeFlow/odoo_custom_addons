from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.vision_inspection.tests.common import VisionInspectionCommon


@tagged('post_install', '-at_install')
class TestQcBridge(VisionInspectionCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Instances
        cls.qc_test = cls.env['qc.test'].create({'name': "Vision Test"})
        cls.qc_test.action_add_vision_questions()
        # Setup
        cls.station.qc_test_id = cls.qc_test

    def _ingest(self, detections=(), **kwargs):
        inspection = self.source.with_user(self.ingest_user)._ingest(self._generic_payload(detections, **kwargs))
        return inspection.with_env(self.env)

    def test_add_vision_questions(self):
        questions = self.qc_test.test_lines
        self.assertIn(self.scratch, questions.vision_defect_class_id)
        self.assertIn(self.crack, questions.vision_defect_class_id)
        self.assertNotIn(self.part, questions.vision_defect_class_id, "Classes that aren't defects aren't asked")
        scratch_question = questions.filtered(lambda q: q.vision_defect_class_id == self.scratch)
        self.assertEqual(scratch_question.type, 'quantitative')
        self.assertEqual(scratch_question.max_value, 1)
        self.qc_test.action_add_vision_questions()
        self.assertEqual(self.qc_test.test_lines, questions, "Classes already asked aren't added again")

    def test_pass_creates_nothing_by_default(self):
        inspection = self._ingest()
        self.assertEqual(inspection.verdict, 'pass')
        self.assertFalse(inspection.qc_inspection_ids)

    def test_fail_waits_for_approval(self):
        inspection = self._ingest([self._detection('t_crack'), self._detection('t_scratch')])
        qc = inspection.qc_inspection_ids
        self.assertEqual(len(qc), 1)
        self.assertEqual(qc.state, 'waiting')
        self.assertEqual(qc.object_id, inspection)
        self.assertEqual(qc.product_id, self.product)
        self.assertEqual(qc.test, self.qc_test)
        values = {line.test_line.vision_defect_class_id: line.quantitative_value for line in qc.inspection_lines}
        self.assertEqual(values[self.crack], 1)
        self.assertEqual(values[self.scratch], 1)
        qc.action_approve()
        self.assertEqual(qc.state, 'failed')

    def test_review_waits_for_approval(self):
        inspection = self._ingest([self._detection('t_scratch', 0.6)])
        self.assertEqual(inspection.verdict, 'review')
        self.assertEqual(inspection.qc_inspection_ids.state, 'waiting')
        self.assertFalse(inspection.qc_inspection_ids.success, "Odoo follows the verdict, not only the counts")

    def test_always(self):
        self.station.qc_trigger = 'always'
        inspection = self._ingest()
        self.assertEqual(inspection.qc_inspection_ids.state, 'success')

    def test_never(self):
        self.station.qc_trigger = 'never'
        self.assertFalse(self._ingest([self._detection('t_crack')]).qc_inspection_ids)

    def test_manual_verdict(self):
        inspection = self._ingest([self._detection('t_crack')])
        qc = inspection.qc_inspection_ids
        inspection.with_user(self.ingest_user).action_mark_pass()
        self.assertEqual(qc.state, 'success', "An open quality inspection follows the new verdict")
        inspection.action_mark_fail()
        self.assertEqual(inspection.qc_inspection_ids, qc, "A done quality inspection isn't replaced")
        self.assertEqual(qc.state, 'success')
        passed = self._ingest()
        passed.action_mark_fail()
        self.assertEqual(passed.qc_inspection_ids.state, 'waiting')

    def test_resent_results(self):
        inspection = self._ingest([self._detection('t_crack')], external_id='resent')
        qc = inspection.qc_inspection_ids
        self._ingest([], external_id='resent')
        self.assertEqual(inspection.qc_inspection_ids, qc)
        self.assertEqual(qc.state, 'success')
        self.assertFalse(any(qc.inspection_lines.mapped('quantitative_value')))

    def test_test_with_other_questions(self):
        self.qc_test.test_lines = [Command.create({
            'name': "Label readable",
            'type': 'qualitative',
            'ql_values': [Command.create({'name': "Yes", 'ok': True}), Command.create({'name': "No", 'ok': False})],
        })]
        inspection = self._ingest([self._detection('t_crack')])
        qc = inspection.qc_inspection_ids
        self.assertEqual(qc.state, 'ready', "An operator answers the other questions")
        crack_line = qc.inspection_lines.filtered(lambda line: line.test_line.vision_defect_class_id == self.crack)
        self.assertEqual(crack_line.quantitative_value, 1)
