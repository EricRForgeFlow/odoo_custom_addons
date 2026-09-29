import io
import json

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools.binary import BinaryBytes
from odoo.tools.convert import convert_xml_import


@tagged('post_install', '-at_install')
class TestTourTransfer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.custom_group = cls.env['res.groups'].create({'name': "Tour Manager Transfer Group"})
        cls.tour = cls.env['web_tour.tour'].create({
            'name': 'tm_transfer_tour',
            'title': "Transfer tour",
            'custom': True,
            'url': '/odoo/crm',
            'icon': 'oi:rocket_launch',
            'sequence': 7,
            'auto_start': True,
            'rainbow_man_message': "<b>Well done!</b>",
            'group_ids': [(6, 0, [cls.env.ref('base.group_system').id, cls.custom_group.id])],
            'step_ids': [
                (0, 0, {'sequence': 20, 'trigger': '.second', 'run': 'edit Hello & "you"', 'tooltip_position': 'top'}),
                (0, 0, {'sequence': 10, 'trigger': ".o_app[data-menu-xmlid='crm.crm_menu_root']", 'run': 'click',
                        'content': "Open CRM"}),
                (0, 0, {'sequence': 30, 'trigger': '.third', 'run': 'next', 'content': "An info step"}),
            ],
        })

    def _export(self, tours=None):
        return (tours or self.tour)._tour_manager_export()

    def test_export(self):
        [data] = self._export()
        self.assertEqual(data['name'], 'tm_transfer_tour')
        self.assertEqual((data['title'], data['url'], data['icon'], data['sequence'], data['auto_start']),
                         ("Transfer tour", '/odoo/crm', 'oi:rocket_launch', 7, True))
        self.assertEqual(data['groups'][0]['xmlid'], 'base.group_system')
        self.assertIsNone(data['groups'][1]['xmlid'])
        self.assertEqual([step['trigger'] for step in data['steps']],
                         [".o_app[data-menu-xmlid='crm.crm_menu_root']", '.second', '.third'])
        # Onboarding tours of apps aren't exported
        onboarding = self.env['web_tour.tour'].create({'name': 'tm_transfer_onboarding'})
        self.assertEqual(len(self._export(self.tour | onboarding)), 1)

    def test_json_round_trip(self):
        exported = json.loads(self.tour._tour_manager_export_json())
        original = self._export()
        self.tour.unlink()
        result = self.env['web_tour.tour']._tour_manager_import(exported)
        self.assertEqual(result['created'], ['tm_transfer_tour'])
        imported = self.env['web_tour.tour'].search([('name', '=', 'tm_transfer_tour')])
        self.assertEqual(self._export(imported), original)
        self.assertTrue(imported.custom)

    def test_import_existing(self):
        exported = json.loads(self.tour._tour_manager_export_json())
        exported['tours'][0]['title'] = "Changed"
        exported['tours'][0]['steps'] = [{'trigger': '.only', 'run': 'click', 'tooltip_position': 'nowhere'}]
        result = self.env['web_tour.tour']._tour_manager_import(exported, update_existing=False)
        self.assertEqual(result['skipped'], ['tm_transfer_tour'])
        self.assertEqual(self.tour.title, "Transfer tour")
        result = self.env['web_tour.tour']._tour_manager_import(exported)
        self.assertEqual(result['updated'], ['tm_transfer_tour'])
        self.assertEqual(self.tour.title, "Changed")
        self.assertEqual(self.tour.step_ids.mapped('trigger'), ['.only'])
        self.assertEqual(self.tour.step_ids.tooltip_position, 'bottom')  # invalid position replaced

    def test_import_onboarding_tour_name(self):
        self.env['web_tour.tour'].create({'name': 'tm_transfer_app_tour'})
        exported = json.loads(self.tour._tour_manager_export_json())
        exported['tours'][0]['name'] = 'tm_transfer_app_tour'
        result = self.env['web_tour.tour']._tour_manager_import(exported)
        self.assertEqual(result['skipped'], ['tm_transfer_app_tour'])
        self.assertIn("onboarding tour of an app", result['warnings'][0])

    def test_import_groups(self):
        exported = json.loads(self.tour._tour_manager_export_json())
        exported['tours'][0]['groups'].append({'xmlid': 'nowhere.group_missing', 'name': "Missing Group"})
        self.tour.unlink()
        result = self.env['web_tour.tour']._tour_manager_import(exported)
        imported = self.env['web_tour.tour'].search([('name', '=', 'tm_transfer_tour')])
        # By external ID, or by name for the groups without one
        self.assertEqual(imported.group_ids, self.env.ref('base.group_system') | self.custom_group)
        self.assertEqual(len(result['warnings']), 1)
        self.assertIn("Missing Group", result['warnings'][0])

    def test_import_invalid(self):
        Tour = self.env['web_tour.tour']
        with self.assertRaises(UserError):
            Tour._tour_manager_import({'tours': []})
        with self.assertRaises(UserError):
            Tour._tour_manager_import({'format': 'tour_manager', 'tours': [{'steps': []}]})

    def test_xml_export_loads_as_module_data(self):
        original = self._export()
        xml = self.tour._tour_manager_export_xml()
        self.assertIn('noupdate="1"', xml)
        self.tour.unlink()
        xml_file = io.BytesIO(xml.encode())
        xml_file.name = 'tours.xml'
        convert_xml_import(self.env, 'tour_manager', xml_file)
        loaded = self.env.ref('tour_manager.tour_tm_transfer_tour')
        exported = self._export(loaded)[0]
        # The group without external ID isn't exported to XML
        self.assertEqual([group['xmlid'] for group in exported['groups']], ['base.group_system'])
        self.assertEqual({**exported, 'groups': []}, {**original[0], 'groups': []})

    def test_wizards(self):
        export = self.env['tour_manager.tour.export.wizard'].with_context(
            active_model='web_tour.tour', active_ids=self.tour.ids).create({})
        self.assertEqual(export.tour_ids, self.tour)
        action = export.action_export()
        self.assertEqual(action['target'], 'download')
        self.assertEqual(export.filename, 'tm_transfer_tour.json')
        content = export.file.content
        self.tour.unlink()
        importer = self.env['tour_manager.tour.import.wizard'].create({
            'file': BinaryBytes(content), 'filename': 'tm_transfer_tour.json'})
        importer.action_import()
        self.assertEqual(importer.state, 'done')
        self.assertIn("Created (1): tm_transfer_tour", importer.summary)
        with self.assertRaises(UserError):
            self.env['tour_manager.tour.import.wizard'].create({
                'file': BinaryBytes(b'not json'), 'filename': 'tours.json'}).action_import()
