from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools.binary import BinaryBytes


class TourManagerTourExportWizard(models.TransientModel):
    _name = 'tour_manager.tour.export.wizard'
    _description = "Export tours"

    tour_ids = fields.Many2many(
        'web_tour.tour',
        string="Tours",
        domain=[('custom', '=', True)],
        help="The custom tours to export. The onboarding tours of apps come with their apps.",
    )
    file_format = fields.Selection(
        selection=[
            ('json', "JSON file, to import in another database"),
            ('xml', "XML data file, to add to a module"),
        ],
        string="Format",
        required=True,
        default='json',
    )
    file = fields.Binary(readonly=True, attachment=False)
    filename = fields.Char(readonly=True)

    @api.model
    def default_get(self, fields):
        values = super().default_get(fields)
        if 'tour_ids' in fields:
            Tour = self.env['web_tour.tour']
            if self.env.context.get('active_model') == 'web_tour.tour' and self.env.context.get('active_ids'):
                tours = Tour.browse(self.env.context['active_ids']).filtered('custom')
            else:
                tours = Tour.search([('custom', '=', True)])
            values['tour_ids'] = [Command.set(tours.ids)]
        return values

    def action_export(self):
        self.ensure_one()
        if not self.tour_ids:
            raise UserError(self.env._("Select the tours to export."))
        if self.file_format == 'json':
            content, extension = self.tour_ids._tour_manager_export_json(), 'json'
        else:
            content, extension = self.tour_ids._tour_manager_export_xml(), 'xml'
        filename = f"tours.{extension}" if len(self.tour_ids) > 1 else f"{self.tour_ids.name}.{extension}"
        self.write({'file': BinaryBytes(content.encode(), filename), 'filename': filename})
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/file/{self.filename}?download=true',
            'target': 'download',
        }
