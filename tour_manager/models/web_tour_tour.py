from odoo import api, fields, models
from odoo.fields import Domain

from odoo.addons.web.icons import search_icons


class Web_TourTour(models.Model):
    _inherit = 'web_tour.tour'

    # Module information is stored as plain values rather than a Many2one to
    # ir.module.module, which only administrators can read.
    module = fields.Char(compute='_compute_module_info', store=True, readonly=True)
    module_name = fields.Char(string="App", compute='_compute_module_info', store=True, readonly=True)
    module_icon = fields.Char(compute='_compute_module_info', store=True, readonly=True)
    is_done = fields.Boolean(string="Done", compute='_compute_is_done')
    # Result of the last check, which plays the tour automatically
    check_state = fields.Selection(
        selection=[('passed', "Passed"), ('failed', "Failed")],
        string="Last Check",
        readonly=True,
    )
    check_date = fields.Datetime(string="Checked On", readonly=True)
    check_message = fields.Text(string="Check Result", readonly=True)
    check_step = fields.Integer(string="Failed Step", readonly=True, help="Number of the step the last check failed at.")
    title = fields.Char(help="Name shown in the Tours app instead of the technical name.")
    # Visibility: what users are shown in the Tours app and what starts by
    # itself, not a security barrier (tours are guidance, not sensitive data)
    group_ids = fields.Many2many(
        'res.groups',
        'tour_manager_tour_group_rel',
        'tour_id',
        'group_id',
        string="Visible to",
        help="Groups whose users see the tour in the Tours app, and for whom it can start automatically. "
             "Empty: everyone.",
    )
    auto_start = fields.Boolean(
        string="Start Automatically",
        help="The tour plays by itself for the users who can see it and haven't done it yet. "
             "(The onboarding tours of apps start by themselves in onboarding mode.)",
    )
    user_dismissed_ids = fields.Many2many(
        'res.users',
        'tour_manager_tour_dismissed_rel',
        'tour_id',
        'user_id',
        string="Dismissed By",
        help="Users who stopped the tour when it started by itself: it doesn't start by itself for them anymore.",
    )
    is_visible = fields.Boolean(
        string="Visible to Me",
        compute='_compute_is_visible',
        search='_search_is_visible',
        help="Whether the current user sees the tour in the Tours app. Administrators see all tours.",
    )
    icon = fields.Char(
        help="Icon shown in the Tours app: an icon of Odoo's icon set (prefixed by \"oi:\") "
             "or the URL of an image, e.g. an app icon.",
    )

    @api.depends('title', 'name')
    def _compute_display_name(self):
        for tour in self:
            tour.display_name = tour.title or tour.name

    @api.model
    def _get_visible_domain(self, user=None):
        """Domain of the tours visible to `user` (the current user by default)."""
        user = user or self.env.user
        return Domain('group_ids', '=', False) | Domain('group_ids', 'in', user.all_group_ids.ids)

    @api.depends_context('uid')
    @api.depends('group_ids')
    def _compute_is_visible(self):
        is_admin = self.env.user.has_group('base.group_system')
        user_groups = self.env.user.all_group_ids
        for tour in self:
            tour.is_visible = is_admin or not tour.group_ids or bool(tour.group_ids & user_groups)

    def _search_is_visible(self, operator, value):
        if operator not in ('in', 'not in'):
            return NotImplemented
        visible = Domain.TRUE if self.env.user.has_group('base.group_system') else self._get_visible_domain()
        return visible if (True in value) == (operator == 'in') else ~visible

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

    @api.model
    def tour_manager_search_icons(self, needle=''):
        """Return the names of the icons of Odoo's icon set matching `needle`
        (all of them if it's empty), matched against their names and tags."""
        return [name for name, _has_fill in search_icons(needle or '')]

    @api.model
    def tour_manager_get_app_icons(self):
        """Return the icons of the apps of the home screen the user can see."""
        menus = self.env['ir.ui.menu'].search([('parent_id', '=', False), ('web_icon', '!=', False)])
        app_icons = []
        for menu in menus:
            # web_icon is "<module>,<path of the icon in the module>"
            module, _sep, path = menu.web_icon.partition(',')
            if path.lower().endswith(('.png', '.svg', '.jpg', '.jpeg', '.gif', '.webp')):
                app_icons.append({'name': menu.name, 'url': f'/{module}/{path}'})
        return app_icons

    @api.model
    def get_current_tour(self):
        """The onboarding tours of apps start by themselves in onboarding mode
        (as web_tour does), only for the users they're visible to. Custom tours
        starting automatically are handled apart (see `_get_auto_start_tours`)."""
        user = self.env.user
        if not (user and user.tour_enabled and user._is_internal()):
            return super().get_current_tour()
        tour = self.search(
            Domain('custom', '=', False)
            & self._get_visible_domain(user)
            & Domain('user_consumed_ids', 'not in', user.id),
            limit=1,
        )
        return tour._get_tour_json() if tour else False

    @api.model
    def _get_auto_start_tours(self):
        """Return the custom tours to start by themselves for the current user,
        when they reach their starting page: the ones visible to them that they
        haven't done nor dismissed."""
        user = self.env.user
        if not (user and user._is_internal()):
            return []
        tours = self.search(
            Domain('custom', '=', True)
            & Domain('auto_start', '=', True)
            & self._get_visible_domain(user)
            & Domain('user_consumed_ids', 'not in', user.id)
            & Domain('user_dismissed_ids', 'not in', user.id),
        )
        return [
            {
                'name': tour.name,
                'url': tour.url or '/odoo',
                'rainbow_man_message': tour.rainbow_man_message or '',
            }
            for tour in tours
        ]

    @api.model
    def tour_manager_dismiss(self, name):
        """The current user stopped the tour named `name`: if it started by
        itself, don't start it by itself for them anymore."""
        tour = self.search([('name', '=', name), ('custom', '=', True), ('auto_start', '=', True)], limit=1)
        if tour:
            tour.sudo().user_dismissed_ids = [fields.Command.link(self.env.user.id)]

    def _load_records(self, data_list, update=False):
        records = super()._load_records(data_list, update=update)
        # The XMLIDs, from which the module is computed, are only assigned
        # after the records are created.
        for fname in ('module', 'module_name', 'module_icon'):
            self.env.add_to_compute(self._fields[fname], records)
        return records

    def _get_tour_json(self):
        tour_json = super()._get_tour_json()
        # Name shown to the user, e.g. when asked whether to leave the tour
        tour_json['title'] = self.title or self.module_name or self.name
        return tour_json

    def action_edit_tour(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('tour_manager.web_tour_tour_view_form').id, 'form')],
            'target': 'current',
        }

    def action_check_tour(self):
        """Play the tour automatically, to check that all its steps still work."""
        self.ensure_one()
        action = self.action_start_tour()
        action['tag'] = 'tour_manager.check_tour'
        return action

    @api.model
    def tour_manager_save_check_result(self, name, passed, message, step=0):
        """Save the result of the check of the tour named `name`.

        :return: the id of the tour
        """
        tour = self.search([('name', '=', name)], limit=1)
        tour.write({
            'check_state': 'passed' if passed else 'failed',
            'check_date': fields.Datetime.now(),
            'check_message': message,
            'check_step': 0 if passed else step,
        })
        return tour.id

    def action_start_tour(self):
        """Replay the tour, without switching the user to onboarding mode."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'tour_manager.start_tour',
            'params': {
                'name': self.name,
                'url': self.url or '/odoo',
                'rainbow_man_message': self.rainbow_man_message or '',
            },
        }
