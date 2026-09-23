from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWebTourTour(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tour = cls.env['web_tour.tour']._load_records([{
            'xml_id': 'tour_manager.test_tour',
            'values': {'name': 'tour_manager_test_tour', 'url': '/odoo/action-studio?mode=home_menu'},
        }])

    def test_module_info(self):
        self.assertEqual(self.tour.module, 'tour_manager')
        self.assertEqual(self.tour.module_name, 'Tour Manager')
        self.assertEqual(self.tour.module_icon, '/tour_manager/static/description/icon.png')

    def test_module_info_without_xmlid(self):
        tour = self.env['web_tour.tour'].create({'name': 'tour_manager_custom_tour', 'custom': True})
        self.assertFalse(tour.module)
        self.assertFalse(tour.module_name)

    def test_is_done(self):
        # consume() only records internal users
        tour = self.tour.with_user(self.env.ref('base.user_admin'))
        self.assertFalse(tour.is_done)
        tour.consume(tour.name)
        tour.invalidate_recordset(['is_done'])
        self.assertTrue(tour.is_done)
        self.assertFalse(self.tour.is_done, "Done status is per user")

    def test_action_start_tour(self):
        action = self.tour.action_start_tour()
        self.assertEqual(action['url'], '/odoo/action-studio?mode=home_menu&tour=tour_manager_test_tour')
        self.tour.url = False
        self.assertEqual(self.tour.action_start_tour()['url'], '/odoo?tour=tour_manager_test_tour')

    def test_display_name(self):
        tour = self.env['web_tour.tour'].create({'name': 'tour_manager_custom_tour', 'custom': True})
        self.assertEqual(tour.display_name, 'tour_manager_custom_tour')
        tour.title = "My Custom Tour"
        self.assertEqual(tour.display_name, "My Custom Tour")

    def test_action_edit_tour(self):
        tour = self.env['web_tour.tour'].create({'name': 'tour_manager_custom_tour', 'custom': True})
        action = tour.action_edit_tour()
        self.assertEqual(action['res_id'], tour.id)
        self.assertEqual(action['views'], [(self.env.ref('tour_manager.web_tour_tour_view_form').id, 'form')])
