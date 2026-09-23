from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from odoo import api, fields, models


class Web_TourTour(models.Model):
    _inherit = 'web_tour.tour'

    # Module information is stored as plain values rather than a Many2one to
    # ir.module.module, which only administrators can read.
    module = fields.Char(compute='_compute_module_info', store=True, readonly=True)
    module_name = fields.Char(string="App", compute='_compute_module_info', store=True, readonly=True)
    module_icon = fields.Char(compute='_compute_module_info', store=True, readonly=True)
    is_done = fields.Boolean(string="Done", compute='_compute_is_done')

    def _compute_module_info(self):
        xmlids = self.sudo()._get_external_ids()
        module_names = {tour.id: xmlids[tour.id][0].split('.')[0] for tour in self if xmlids.get(tour.id)}
        modules = self.env['ir.module.module'].sudo().search([('name', 'in', list(module_names.values()))])
        modules_by_name = {module.name: module for module in modules}
        for tour in self:
            module = modules_by_name.get(module_names.get(tour.id), self.env['ir.module.module'])
            tour.module = module.name
            tour.module_name = module.shortdesc
            tour.module_icon = module.icon

    @api.depends_context('uid')
    @api.depends('user_consumed_ids')
    def _compute_is_done(self):
        for tour in self:
            tour.is_done = self.env.user in tour.user_consumed_ids

    def _load_records(self, data_list, update=False):
        records = super()._load_records(data_list, update=update)
        # The XMLIDs, from which the module is computed, are only assigned
        # after the records are created.
        for fname in ('module', 'module_name', 'module_icon'):
            self.env.add_to_compute(self._fields[fname], records)
        return records

    def action_start_tour(self):
        self.ensure_one()
        url = urlsplit(self.url or '/odoo')
        query = urlencode([*parse_qsl(url.query), ('tour', self.name)])
        return {
            'type': 'ir.actions.act_url',
            'url': urlunsplit(url._replace(query=query)),
            'target': 'self',
        }
