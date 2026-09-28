from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStepEditor(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tour = cls.env['web_tour.tour'].create({
            'name': 'tm_editor_tour', 'title': "Editor tour", 'custom': True, 'url': '/odoo/crm',
            'step_ids': [
                (0, 0, {'sequence': 10, 'trigger': '.first', 'run': 'click', 'content': "First"}),
                (0, 0, {'sequence': 20, 'trigger': '.second', 'run': 'click', 'content': "Second"}),
                (0, 0, {'sequence': 30, 'trigger': '.third', 'run': 'click'}),
            ],
        })
        cls.first, cls.second, cls.third = cls.tour._get_ordered_steps()

    def test_step_numbers(self):
        self.assertEqual((self.first.number, self.second.number, self.third.number), (1, 2, 3))

    def test_edit_actions(self):
        action = self.second.action_pick_element()
        self.assertEqual(action['tag'], 'tour_manager.edit_tour')
        self.assertEqual(action['params']['mode'], 'pick')
        self.assertEqual(action['params']['play_until'], 1)  # the steps before it
        self.assertEqual(action['params']['step'], {
            'id': self.second.id, 'number': 2, 'content': "Second", 'tooltip_position': 'bottom',
        })
        self.assertEqual(action['params']['url'], '/odoo/crm')
        action = self.second.action_record_after()
        self.assertEqual((action['params']['mode'], action['params']['play_until']), ('insert', 2))
        action = self.tour.action_record_more()
        self.assertEqual((action['params']['mode'], action['params']['play_until']), ('insert', 3))

    def test_insert_steps(self):
        count = self.tour.tour_manager_insert_steps(1, [
            {'trigger': '.new_a', 'run': 'click', 'content': "A", 'tooltip_position': 'top'},
            {'trigger': '.new_b', 'run': 'next', 'content': "B", 'tooltip_position': 'bottom'},
        ])
        self.assertEqual(count, 2)
        self.assertEqual(self.tour._get_ordered_steps().mapped('trigger'),
                         ['.first', '.new_a', '.new_b', '.second', '.third'])
        self.assertEqual(self.tour._get_ordered_steps().mapped('sequence'), [1, 2, 3, 4, 5])
        # At the end
        self.tour.tour_manager_insert_steps(5, [{'trigger': '.last', 'run': 'click', 'tooltip_position': 'bottom'}])
        self.assertEqual(self.tour._get_ordered_steps()[-1].trigger, '.last')

    def test_update_target(self):
        self.second.tour_manager_update_target('.better', "Better hint", 'right')
        self.assertEqual((self.second.trigger, self.second.content, self.second.tooltip_position),
                         ('.better', "Better hint", 'right'))
        self.second.tour_manager_update_target('.best', "", 'bottom')
        self.assertFalse(self.second.content)
