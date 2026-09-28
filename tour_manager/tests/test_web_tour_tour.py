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
        self.assertEqual(action['tag'], 'tour_manager.start_tour')
        self.assertEqual(action['params']['name'], 'tour_manager_test_tour')
        self.assertEqual(action['params']['url'], '/odoo/action-studio?mode=home_menu')
        self.tour.url = False
        self.assertEqual(self.tour.action_start_tour()['params']['url'], '/odoo')

    def test_action_check_tour(self):
        action = self.tour.action_check_tour()
        self.assertEqual(action['tag'], 'tour_manager.check_tour')
        self.assertEqual(action['params']['name'], 'tour_manager_test_tour')

    def test_save_check_result(self):
        Tour = self.env['web_tour.tour']
        tour_id = Tour.tour_manager_save_check_result(self.tour.name, False, "Step 2 of 3 failed", 2)
        self.assertEqual(tour_id, self.tour.id)
        self.assertEqual(self.tour.check_state, 'failed')
        self.assertEqual(self.tour.check_step, 2)
        self.assertEqual(self.tour.check_message, "Step 2 of 3 failed")
        self.assertTrue(self.tour.check_date)
        Tour.tour_manager_save_check_result(self.tour.name, True, "All 3 steps work", 3)
        self.assertEqual(self.tour.check_state, 'passed')
        self.assertEqual(self.tour.check_step, 0)

    def test_check_failed_step(self):
        tour = self.env['web_tour.tour'].create({'name': 'tour_manager_checked_tour', 'custom': True, 'step_ids': [
            (0, 0, {'sequence': 10, 'trigger': '.first', 'run': 'click'}),
            (0, 0, {'sequence': 20, 'trigger': '.second', 'run': 'click'}),
        ]})
        first, second = tour.step_ids.sorted('sequence')
        self.assertFalse(any((first | second).mapped('check_failed')))
        tour.tour_manager_save_check_result(tour.name, False, "Step 2 of 2 failed", 2)
        self.assertEqual((first.check_failed, second.check_failed), (False, True))
        tour.tour_manager_save_check_result(tour.name, True, "All 2 steps work", 2)
        self.assertFalse(second.check_failed)

    def test_display_name(self):
        tour = self.env['web_tour.tour'].create({'name': 'tour_manager_custom_tour', 'custom': True})
        self.assertEqual(tour.display_name, 'tour_manager_custom_tour')
        tour.title = "My Custom Tour"
        self.assertEqual(tour.display_name, "My Custom Tour")

    def test_tour_json_title(self):
        self.assertEqual(self.tour._get_tour_json()['title'], 'Tour Manager')
        self.tour.title = "My Tour"
        self.assertEqual(self.tour._get_tour_json()['title'], "My Tour")

    def test_search_icons(self):
        Tour = self.env['web_tour.tour']
        all_icons = Tour.tour_manager_search_icons()
        self.assertIn('signpost', all_icons)
        # Icons are also matched on their tags
        money_icons = Tour.tour_manager_search_icons('money')
        self.assertTrue(money_icons)
        self.assertLess(len(money_icons), len(all_icons))

    def test_get_app_icons(self):
        app_icons = self.env['web_tour.tour'].tour_manager_get_app_icons()
        self.assertIn({'name': "Tours", 'url': '/tour_manager/static/description/icon.png'}, app_icons)

    def test_action_edit_tour(self):
        tour = self.env['web_tour.tour'].create({'name': 'tour_manager_custom_tour', 'custom': True})
        action = tour.action_edit_tour()
        self.assertEqual(action['res_id'], tour.id)
        self.assertEqual(action['views'], [(self.env.ref('tour_manager.web_tour_tour_view_form').id, 'form')])
