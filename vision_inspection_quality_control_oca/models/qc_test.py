from odoo import models
from odoo.fields import Command


class QcTest(models.Model):
    _inherit = 'qc.test'

    def action_add_vision_questions(self):
        unit = self.env.ref('uom.product_uom_unit')
        defect_classes = self.env['vision.defect.class'].search([('is_defect', '=', True)])
        for test in self:
            existing = test.test_lines.vision_defect_class_id
            test.test_lines = [
                Command.create({
                    'name': defect_class.name,
                    'type': 'quantitative',
                    'min_value': 0,
                    'max_value': defect_class.max_allowed,
                    'uom_id': unit.id,
                    'vision_defect_class_id': defect_class.id,
                })
                for defect_class in defect_classes - existing
            ]
