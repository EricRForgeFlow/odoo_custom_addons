from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTourCreateWizard(TransactionCase):

    def _create_wizard(self, **values):
        return self.env['tour_manager.tour.create.wizard'].create({'title': "My First Quote", **values})

    def test_start_recording_home(self):
        action = self._create_wizard().action_start_recording()
        self.assertEqual(action['tag'], 'tour_manager.start_recording')
        self.assertEqual(action['params']['title'], "My First Quote")
        self.assertEqual(action['params']['name'], 'tour_manager_my_first_quote')
        self.assertEqual(action['params']['url'], '/odoo')

    def test_unique_name(self):
        self.env['web_tour.tour'].create({'name': 'tour_manager_my_first_quote', 'custom': True})
        self.env['web_tour.tour'].create({'name': 'tour_manager_my_first_quote_2', 'custom': True, 'active': False})
        action = self._create_wizard().action_start_recording()
        self.assertEqual(action['params']['name'], 'tour_manager_my_first_quote_3')

    def test_start_url_app(self):
        root = self.env.ref('tour_manager.menu_tour_manager_root')
        action = self._create_wizard(start='app', menu_id=root.id).action_start_recording()
        tours_action = self.env.ref('tour_manager.web_tour_tour_action')
        self.assertEqual(action['params']['url'], f"/odoo/{tours_action.path or f'action-{tours_action.id}'}")

    def test_start_url_custom(self):
        action = self._create_wizard(start='url', url='/odoo/contacts').action_start_recording()
        self.assertEqual(action['params']['url'], '/odoo/contacts')
        with self.assertRaises(ValidationError):
            self._create_wizard(start='url', url='https://example.com')
        with self.assertRaises(ValidationError):
            self._create_wizard(start='app')
