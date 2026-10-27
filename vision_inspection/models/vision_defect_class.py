from odoo import fields, models

SEVERITIES = [('minor', "Minor"), ('major', "Major"), ('critical', "Critical")]


class VisionDefectClass(models.Model):
    _name = 'vision.defect.class'
    _description = "Vision Defect Class"
    _order = 'name, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, help="Label the vision model gives to this class.")
    active = fields.Boolean(default=True)
    is_defect = fields.Boolean(
        string="Defect",
        default=True,
        help="Uncheck for classes that aren't defects, such as the inspected part itself.",
    )
    severity = fields.Selection(selection=SEVERITIES, required=True, default='major')
    max_allowed = fields.Integer(
        string="Allowed per Sample",
        help="A sample with more detections of this class fails.",
    )

    _code_uniq = models.Constraint('unique(code)', "The code of a defect class must be unique.")

    def _get_for_labels(self, labels):
        """Return the classes of the labels by label, creating the missing ones, and the created ones."""
        classes = self.with_context(active_test=False).search([('code', 'in', list(labels))])
        new_classes = self.create([{'name': label, 'code': label} for label in labels - set(classes.mapped('code'))])
        return {defect_class.code: defect_class for defect_class in classes | new_classes}, new_classes
