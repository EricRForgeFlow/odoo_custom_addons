from unittest.mock import patch

from odoo.tests import HttpCase, tagged
from odoo.tools import config

from .common import VisionInspectionCommon


@tagged('post_install', '-at_install')
class TestUi(VisionInspectionCommon, HttpCase):

    def setUp(self):
        super().setUp()
        # The test browser may close before its screencast stops, failing a passed test
        self.startPatcher(patch.dict(config.options, {'screencasts': None}))

    def test_image_annotations(self):
        inspection = self.source._ingest(self._generic_payload([
            self._detection('t_crack', 0.9),
            self._detection('t_scratch', 0.3),
        ]))
        self.browser_js(
            f'/odoo/action-vision_inspection.vision_inspection_action/{inspection.id}',
            """
            const boxes = document.querySelectorAll('.o_vision_image_frame .o_vision_box');
            const critical = document.querySelector('.o_vision_box_critical .o_vision_box_label');
            if (boxes.length === 2 && document.querySelector('.o_vision_box_ignored')
                    && critical.textContent.includes('Crack 90%')) {
                console.log('test successful');
            } else {
                console.error('Unexpected boxes: ' + document.querySelector('.o_vision_image_annotations').outerHTML);
            }
            """,
            ready="!!document.querySelector('.o_vision_box')",
            login='admin',
        )
