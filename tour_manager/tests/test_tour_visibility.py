from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTourVisibility(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sales_group = cls.env['res.groups'].create({'name': "Tour Manager Test Sales"})
        cls.salesman = cls.env['res.users'].create({
            'name': "Sam Seller",
            'login': 'tour_manager_sam',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.sales_group.id])],
        })
        cls.employee = cls.env['res.users'].create({
            'name': "Emma Employee",
            'login': 'tour_manager_emma',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        Tour = cls.env['web_tour.tour']
        cls.everyone_tour = Tour.create({'name': 'tm_everyone', 'custom': True, 'auto_start': True, 'sequence': 1})
        cls.sales_tour = Tour.create({
            'name': 'tm_sales', 'custom': True, 'auto_start': True, 'sequence': 2,
            'group_ids': [(6, 0, cls.sales_group.ids)],
        })
        cls.manual_tour = Tour.create({'name': 'tm_manual', 'custom': True, 'sequence': 3})

    TEST_TOURS = ['tm_everyone', 'tm_sales', 'tm_manual']

    def _visible_names(self, user, visible=True):
        tours = self.env['web_tour.tour'].with_user(user).search(
            [('is_visible', '=', visible), ('name', 'in', self.TEST_TOURS)])
        return set(tours.mapped('name'))

    def _auto_start_names(self, user):
        return [tour['name'] for tour in self.env['web_tour.tour'].with_user(user)._get_auto_start_tours()
                if tour['name'] in self.TEST_TOURS]

    def test_visible_to_groups(self):
        self.assertEqual(self._visible_names(self.salesman), {'tm_everyone', 'tm_sales', 'tm_manual'})
        self.assertEqual(self._visible_names(self.employee), {'tm_everyone', 'tm_manual'})
        # Administrators see all tours, to manage them
        self.assertEqual(self._visible_names(self.env.ref('base.user_admin')), {'tm_everyone', 'tm_sales', 'tm_manual'})
        self.assertTrue(self.sales_tour.with_user(self.env.ref('base.user_admin')).is_visible)
        self.assertFalse(self.sales_tour.with_user(self.employee).is_visible)
        self.assertEqual(self._visible_names(self.employee, visible=False), {'tm_sales'})

    def test_auto_start_tours(self):
        # Only the tours starting automatically and visible to the user, in order
        self.assertEqual(self._auto_start_names(self.salesman), ['tm_everyone', 'tm_sales'])
        self.assertEqual(self._auto_start_names(self.employee), ['tm_everyone'])
        # Not once done, nor once dismissed
        self.everyone_tour.with_user(self.salesman).consume('tm_everyone')
        self.assertEqual(self._auto_start_names(self.salesman), ['tm_sales'])
        self.env['web_tour.tour'].with_user(self.salesman).tour_manager_dismiss('tm_sales')
        self.assertEqual(self._auto_start_names(self.salesman), [])
        self.assertEqual(self._auto_start_names(self.employee), ['tm_everyone'])

    def test_dismiss_only_auto_start_tours(self):
        self.env['web_tour.tour'].with_user(self.employee).tour_manager_dismiss('tm_manual')
        self.assertFalse(self.manual_tour.user_dismissed_ids)

    def test_onboarding_tours_visibility(self):
        """App onboarding tours still start in onboarding mode only, for the users they're visible to."""
        Tour = self.env['web_tour.tour']
        Tour.search([('custom', '=', False)]).write({'user_consumed_ids': [(4, self.employee.id)]})
        onboarding = Tour.create({'name': 'tm_onboarding', 'sequence': 0, 'group_ids': [(6, 0, self.sales_group.ids)]})
        self.employee.tour_enabled = True
        self.assertFalse(Tour.with_user(self.employee).get_current_tour())
        onboarding.group_ids = False
        self.assertEqual(Tour.with_user(self.employee).get_current_tour()['name'], 'tm_onboarding')
        self.employee.tour_enabled = False
        self.assertFalse(Tour.with_user(self.employee).get_current_tour())
        # Custom tours starting automatically don't come from get_current_tour
        self.employee.tour_enabled = True
        Tour.search([('custom', '=', False)]).write({'user_consumed_ids': [(4, self.employee.id)]})
        self.assertFalse(Tour.with_user(self.employee).get_current_tour())
        self.assertEqual(self._auto_start_names(self.employee), ['tm_everyone'])
