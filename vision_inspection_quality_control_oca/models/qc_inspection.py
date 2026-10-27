from odoo import api, fields, models


class QcInspection(models.Model):
    _inherit = 'qc.inspection'

    vision_inspection_id = fields.Many2one(
        'vision.inspection',
        string="Vision Inspection",
        readonly=True,
        index='btree_not_null',
    )
    vision_image = fields.Image(related='vision_inspection_id.image_256', string="Vision Image")

    def object_selection_values(self):
        return super().object_selection_values() + [('vision.inspection', "Vision Inspection")]

    @api.depends('object_id')
    def _compute_product_id(self):
        super()._compute_product_id()
        for inspection in self:
            if inspection.object_id and inspection.object_id._name == 'vision.inspection':
                inspection.product_id = inspection.object_id.product_id

    @api.depends('vision_inspection_id.verdict')
    def _compute_success(self):
        """The verdict of the vision inspection decides, as it may come from the source or a user."""
        super()._compute_success()
        for inspection in self.filtered('vision_inspection_id'):
            inspection.success = inspection.vision_inspection_id.verdict == 'pass'

    def _fill_vision_counts(self):
        for inspection in self:
            counted = inspection.vision_inspection_id.detection_ids.filtered('counted')
            for line in inspection.inspection_lines.filtered('test_line.vision_defect_class_id'):
                line.quantitative_value = len(counted.filtered(
                    lambda detection: detection.defect_class_id == line.test_line.vision_defect_class_id,
                ))

    def _can_confirm_from_vision(self):
        """Only tests whose questions are all answered by the vision inspection are confirmed automatically."""
        self.ensure_one()
        return all(line.test_line.vision_defect_class_id for line in self.inspection_lines)

    def action_open_vision_inspection(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'vision.inspection',
            'res_id': self.vision_inspection_id.id,
            'view_mode': 'form',
        }
