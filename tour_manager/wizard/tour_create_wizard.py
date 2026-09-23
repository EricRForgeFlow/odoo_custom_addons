import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TourManagerTourCreateWizard(models.TransientModel):
    _name = 'tour_manager.tour.create.wizard'
    _description = "Create a custom tour"

    title = fields.Char(required=True)
    start = fields.Selection(
        selection=[
            ('home', "Home Screen"),
            ('app', "An App"),
            ('url', "Custom URL"),
        ],
        string="Starting Point",
        required=True,
        default='home',
    )
    menu_id = fields.Many2one('ir.ui.menu', string="App", domain=[('parent_id', '=', False)])
    url = fields.Char(string="URL", default='/odoo')
    rainbow_man_message = fields.Html(
        string="Completion Message",
        default=lambda self: self.env['web_tour.tour']._fields['rainbow_man_message'].default(self),
    )

    @api.constrains('start', 'menu_id', 'url')
    def _check_start(self):
        for wizard in self:
            if wizard.start == 'app' and not wizard.menu_id:
                raise ValidationError(self.env._("Select the app where the tour starts."))
            if wizard.start == 'url' and not (wizard.url or '').startswith('/odoo'):
                raise ValidationError(self.env._("The starting URL must be a backend URL starting with /odoo."))

    def _get_start_url(self):
        self.ensure_one()
        if self.start == 'url':
            return self.url
        if self.start == 'app':
            action = self._get_menu_action(self.menu_id)
            if action:
                return f"/odoo/{action.path or f'action-{action.id}'}"
        return '/odoo'

    def _get_menu_action(self, menu):
        """Return the action opened by clicking ``menu`` on the home screen: its
        own action, or the first one found among its submenus."""
        if menu.action:
            return menu.action
        for child in menu.child_id:
            if action := self._get_menu_action(child):
                return action
        return False

    def _get_tour_name(self):
        """Return a unique technical name derived from the title."""
        self.ensure_one()
        base = 'tour_manager_' + (re.sub(r'\W+', '_', self.title.lower()).strip('_') or 'tour')
        Tour = self.env['web_tour.tour'].with_context(active_test=False)
        name, index = base, 1
        while Tour.search_count([('name', '=', name)], limit=1):
            index += 1
            name = f'{base}_{index}'
        return name

    def action_start_recording(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'tour_manager.start_recording',
            'params': {
                'title': self.title,
                'name': self._get_tour_name(),
                'url': self._get_start_url(),
                'rainbow_man_message': self.rainbow_man_message or '',
            },
        }
