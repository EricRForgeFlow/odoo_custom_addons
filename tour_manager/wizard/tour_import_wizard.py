import json

from odoo import fields, models
from odoo.exceptions import UserError


class TourManagerTourImportWizard(models.TransientModel):
    _name = 'tour_manager.tour.import.wizard'
    _description = "Import tours"

    file = fields.Binary(string="File", attachment=False, help="A JSON file of tours exported from the Tours app.")
    filename = fields.Char()
    update_existing = fields.Boolean(
        string="Update Existing Tours",
        default=True,
        help="Tours are matched by technical name. When updated, the steps of an existing tour are replaced; "
             "otherwise, it's left as is.",
    )
    state = fields.Selection(selection=[('upload', "Upload"), ('done', "Done")], default='upload')
    summary = fields.Text(readonly=True)

    def action_import(self):
        self.ensure_one()
        if not self.file:
            raise UserError(self.env._("Choose the file to import."))
        if (self.filename or '').lower().endswith('.xml'):
            raise UserError(self.env._(
                "XML data files are loaded by the module they're added to, when it's installed or updated. "
                "Import a JSON file here."))
        try:
            data = json.loads(self.file.content)
        except ValueError as error:
            raise UserError(self.env._("This file isn't a valid JSON file: %s", error)) from error
        result = self.env['web_tour.tour']._tour_manager_import(data, update_existing=self.update_existing)
        lines = []
        for key, label in (
            ('created', self.env._("Created")),
            ('updated', self.env._("Updated")),
            ('skipped', self.env._("Skipped (already existing)")),
        ):
            if result[key]:
                lines.append(f"{label} ({len(result[key])}): {', '.join(result[key])}")
        lines.extend(f"⚠ {warning}" for warning in result['warnings'])
        self.write({'state': 'done', 'summary': '\n'.join(lines) or self.env._("The file contains no tours.")})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
            'name': self.env._("Import Tours"),
        }

    def action_open_tours(self):
        return self.env['ir.actions.act_window']._for_xml_id('tour_manager.web_tour_tour_action')
