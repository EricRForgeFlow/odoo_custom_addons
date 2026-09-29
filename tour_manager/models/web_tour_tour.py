import json
import re

from lxml import etree

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command, Domain

from odoo.addons.web.icons import search_icons

# Format of the files tours are exported to, and imported from
EXPORT_FORMAT = 'tour_manager'
EXPORT_VERSION = 1
TOOLTIP_POSITIONS = ('top', 'bottom', 'left', 'right')


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

    def _get_ordered_steps(self):
        """Return the steps of the tour, in the order they're played."""
        self.ensure_one()
        return self.step_ids.sorted(lambda step: (step.sequence, step.id))

    def action_record_more(self):
        """Record new steps at the end of the tour."""
        self.ensure_one()
        return self._get_edit_action('insert', len(self.step_ids))

    def _get_edit_action(self, mode, play_until, step=None):
        """Return the action editing the tour in the recorder.

        :param str mode: 'insert' to record new steps after the first
            `play_until` ones, or 'pick' to pick the element of `step` again
        :param int play_until: number of steps played automatically first, to
            reach the screen where the recording starts
        :param step: the step whose element is picked again
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'tour_manager.edit_tour',
            'params': {
                'mode': mode,
                'tour_id': self.id,
                'name': self.name,
                'title': self.display_name,
                'url': self.url or '/odoo',
                'play_until': play_until,
                'step': step and {
                    'id': step.id,
                    'number': step.number,
                    'content': step.content or '',
                    'tooltip_position': step.tooltip_position or 'bottom',
                },
            },
        }

    def tour_manager_insert_steps(self, after, steps):
        """Insert the recorded `steps` after the first `after` steps of the tour.

        :param int after: number of steps to insert the new ones after
        :param list steps: values of the new steps (trigger, run, content, tooltip_position)
        :return: the number of steps inserted
        """
        self.ensure_one()
        existing = self._get_ordered_steps()
        new_steps = self.env['web_tour.tour.step'].create([{**values, 'tour_id': self.id} for values in steps])
        ordered = existing[:after] + new_steps + existing[after:]
        for sequence, step in enumerate(ordered, start=1):
            step.sequence = sequence
        return len(new_steps)

    # ------------------------------------------------------------------
    # Export and import
    # ------------------------------------------------------------------

    def _tour_manager_export(self):
        """Return the custom tours of `self` as data (e.g. to write them to a
        JSON file): their definition and steps, and the groups they're visible
        to by external ID, as ids differ from one database to another.

        :rtype: list[dict]
        """
        group_xmlids = self.group_ids.get_external_id()
        tours = []
        for tour in self.filtered('custom'):
            tours.append({
                'name': tour.name,
                'title': tour.title or None,
                'url': tour.url or None,
                'icon': tour.icon or None,
                'rainbow_man_message': tour.rainbow_man_message or None,
                'sequence': tour.sequence,
                'auto_start': tour.auto_start,
                'groups': [
                    {'xmlid': group_xmlids.get(group.id) or None, 'name': group.full_name}
                    for group in tour.group_ids
                ],
                'steps': [
                    {
                        'trigger': step.trigger,
                        'run': step.run or None,
                        'content': step.content or None,
                        'tooltip_position': step.tooltip_position or 'bottom',
                    }
                    for step in tour._get_ordered_steps()
                ],
            })
        return tours

    def _tour_manager_export_json(self):
        """:return: the custom tours of `self`, as the content of a JSON file"""
        return json.dumps(
            {'format': EXPORT_FORMAT, 'version': EXPORT_VERSION, 'tours': self._tour_manager_export()},
            indent=2,
            ensure_ascii=False,
        )

    def _tour_manager_export_xml(self):
        """:return: the custom tours of `self`, as the content of an XML data
        file to add to a module, loaded when the module is installed or updated.
        Tours are not updated afterwards (noupdate), so that they can be edited
        in the database."""
        root = etree.Element('odoo', noupdate='1')
        for tour_data in self._tour_manager_export():
            xmlid = 'tour_' + re.sub(r'\W', '_', tour_data['name'])
            record = etree.SubElement(root, 'record', id=xmlid, model='web_tour.tour')
            for field_name in ('name', 'title', 'url', 'icon', 'rainbow_man_message'):
                if tour_data[field_name]:
                    etree.SubElement(record, 'field', name=field_name).text = tour_data[field_name]
            etree.SubElement(record, 'field', name='sequence').text = str(tour_data['sequence'])
            etree.SubElement(record, 'field', name='custom', eval='True')
            etree.SubElement(record, 'field', name='auto_start', eval=str(bool(tour_data['auto_start'])))
            group_refs = [f"ref({group['xmlid']!r})" for group in tour_data['groups'] if group['xmlid']]
            for group in tour_data['groups']:
                if not group['xmlid']:
                    record.append(etree.Comment(f" Group {group['name']!r} has no external ID: not exported "))
            if group_refs:
                etree.SubElement(record, 'field', name='group_ids', eval=f"[Command.set([{', '.join(group_refs)}])]")
            for number, step_data in enumerate(tour_data['steps'], start=1):
                step = etree.SubElement(root, 'record', id=f'{xmlid}_step_{number}', model='web_tour.tour.step')
                etree.SubElement(step, 'field', name='tour_id', ref=xmlid)
                etree.SubElement(step, 'field', name='sequence').text = str(number)
                for field_name in ('trigger', 'run', 'content', 'tooltip_position'):
                    if step_data[field_name]:
                        etree.SubElement(step, 'field', name=field_name).text = step_data[field_name]
        return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='utf-8').decode()

    @api.model
    def _tour_manager_import(self, data, update_existing=True):
        """Create (or update) the tours of `data`, as exported by `_tour_manager_export_json`.

        Tours are matched by their technical name. The groups they're visible
        to are matched by external ID, or else by name.

        :param dict data: the content of an exported JSON file
        :param bool update_existing: whether to update the existing tours (and
            replace their steps), or to skip them
        :return: the names of the tours created, updated and skipped, and warnings
        :rtype: dict
        """
        if not isinstance(data, dict) or data.get('format') != EXPORT_FORMAT or not isinstance(data.get('tours'), list):
            raise UserError(self.env._("This file doesn't contain tours exported from the Tours app."))
        result = {'created': [], 'updated': [], 'skipped': [], 'warnings': []}
        for tour_data in data['tours']:
            name = tour_data.get('name') if isinstance(tour_data, dict) else None
            steps_data = tour_data.get('steps') if isinstance(tour_data, dict) else None
            if not name or not isinstance(steps_data, list):
                raise UserError(self.env._("A tour of the file has no technical name or steps."))
            existing = self.with_context(active_test=False).search([('name', '=', name)], limit=1)
            if existing and not existing.custom:
                result['skipped'].append(name)
                result['warnings'].append(self.env._(
                    "“%s” is the onboarding tour of an app: it wasn't changed.", name))
                continue
            if existing and not update_existing:
                result['skipped'].append(name)
                continue
            values = {
                'title': tour_data.get('title') or False,
                'url': tour_data.get('url') or '/odoo',
                'icon': tour_data.get('icon') or False,
                'sequence': tour_data.get('sequence') or 1000,
                'auto_start': bool(tour_data.get('auto_start')),
                'custom': True,
                'group_ids': [Command.set(self._tour_manager_find_groups(name, tour_data.get('groups') or [], result))],
                'step_ids': [
                    Command.create({
                        'sequence': number,
                        'trigger': step_data.get('trigger') or '',
                        'run': step_data.get('run') or False,
                        'content': step_data.get('content') or False,
                        'tooltip_position': step_data.get('tooltip_position')
                        if step_data.get('tooltip_position') in TOOLTIP_POSITIONS else 'bottom',
                    })
                    for number, step_data in enumerate(steps_data, start=1)
                    if isinstance(step_data, dict)
                ],
            }
            if tour_data.get('rainbow_man_message'):
                values['rainbow_man_message'] = tour_data['rainbow_man_message']
            if existing:
                existing.step_ids.unlink()
                existing.write({**values, 'active': True})
                result['updated'].append(name)
            else:
                self.create({**values, 'name': name})
                result['created'].append(name)
        return result

    @api.model
    def _tour_manager_find_groups(self, tour_name, groups_data, result):
        """:return: the ids of the groups of `groups_data` (see `_tour_manager_export`),
        adding a warning to `result` for the ones not found"""
        group_ids = []
        for group_data in groups_data:
            if not isinstance(group_data, dict):
                continue
            group = group_data.get('xmlid') and self.env.ref(group_data['xmlid'], raise_if_not_found=False)
            if not (group and group._name == 'res.groups') and group_data.get('name'):
                group = self.env['res.groups'].search([]).filtered(lambda g: g.full_name == group_data['name'])[:1]
            if group:
                group_ids.append(group.id)
            else:
                result['warnings'].append(self.env._(
                    "The group “%(group)s” of “%(tour)s” doesn't exist here: the tour isn't visible to it.",
                    group=group_data.get('name') or group_data.get('xmlid'),
                    tour=tour_name,
                ))
        return group_ids

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

        :return: the id of the tour and the message saved, to show
        :rtype: dict
        """
        tour = self.search([('name', '=', name)], limit=1)
        if not passed and tour.check_state == 'passed':
            # Checks perform the steps for real: the previous one may have
            # changed the data the tour depends on (e.g. bookmarked a message
            # the tour bookmarks)
            message = self.env._(
                "%(message)s It passed the previous time it was checked: the previous check may have "
                "changed the data the tour depends on (checks perform the steps for real).",
                message=message,
            )
        tour.write({
            'check_state': 'passed' if passed else 'failed',
            'check_date': fields.Datetime.now(),
            'check_message': message,
            'check_step': 0 if passed else step,
        })
        return {'id': tour.id, 'message': message}

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
