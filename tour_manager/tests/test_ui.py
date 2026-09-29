from odoo.tests import tagged

from .browser import TourManagerBrowserCase

POINTER = '.o_tour_pointer_tip, .o_tour_pointer_content'
USERS_URL = '/odoo/action-base.action_res_users'


@tagged('post_install', '-at_install')
class TestTourManagerUi(TourManagerBrowserCase):

    def hint(self, browser, text, description):
        """Answers the hint popover of the recorder."""
        browser.wait_for('.o_tour_manager_hint_popover .o_tour_manager_description', description)
        browser.click('.o_tour_manager_hint_popover textarea')
        browser.type(text)
        browser.click('.o_tour_manager_hint_popover .o_tour_manager_next')
        browser.wait_until(
            "![...document.querySelectorAll('.o_tour_manager_hint_popover .o_tour_manager_description')]"
            f".some((el) => el.innerText.includes({description!r}))")

    def start_recording(self, browser, title, url):
        browser.goto('/odoo/tour_manager')
        browser.click('.o-kanban-button-new')
        browser.click('.modal div[name=title] input')
        browser.type(title)
        browser.click('.modal div[name=start] input[data-value=url]')
        browser.click('.modal div[name=url] input')
        browser.select_all()
        browser.type(url)
        browser.click('.modal button[name=action_start_recording]')
        browser.wait_for('.o_tour_manager_bar')

    def test_record_and_replay(self):
        with self.browser() as browser:
            self.start_recording(browser, "Create a user", USERS_URL)
            browser.wait_for('.o_list_button_add')
            browser.click('.o_list_button_add')
            self.hint(browser, "Create a user.", "Clicked")
            browser.wait_for('.o_form_view div[name=name] input')
            browser.click('.o_form_view div[name=name] input')
            self.assertEqual(browser.count('.o_tour_manager_hint_popover'), 0, "clicking in a field is recorded")
            browser.type("Tour User")
            browser.press('Tab')
            self.hint(browser, "Type their name.", "Typed “Tour User”")
            browser.click('.o_tour_manager_finish')
            browser.wait_for('.o_tour_manager_highlight')

            tour = self.env['web_tour.tour'].search([('title', '=', "Create a user")])
            self.assertEqual([(step.run, step.content) for step in tour._get_ordered_steps()],
                             [('click', "Create a user."), ('edit Tour User', "Type their name.")])
            self.assertFalse(self.env['res.users'].search([('name', '=', "Tour User")]),
                             "the example user was saved")

            # Replayed by hand
            browser.click('.o_tour_manager_highlight button[name=action_start_tour]')
            browser.wait_for('.o_list_button_add')
            browser.wait_for(POINTER)
            browser.click('.o_list_button_add')
            browser.wait_for('.o_form_view div[name=name] input')
            browser.click('.o_form_view div[name=name] input')
            browser.type("Tour User")
            browser.wait_for('.o_reward_rainbow_man')
            admin = self.env.ref('base.user_admin')
            self.assertIn(admin, tour.user_consumed_ids)
            self.assertFalse(admin.tour_enabled, "the replay switched onboarding mode on")

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref('base.user_admin')
        self.admin.tour_enabled = False
        self.Tour = self.env['web_tour.tour']

    def make_tour(self, name, url, steps, **values):
        return self.Tour.create({
            'name': name, 'title': name.replace('_', ' ').capitalize(), 'custom': True, 'url': url,
            'step_ids': [(0, 0, {'sequence': number, 'tooltip_position': 'bottom', **step})
                         for number, step in enumerate(steps, start=1)],
            **values,
        })

    def card_button(self, browser, title, button):
        """Click a button of the card of a tour in the Tours app."""
        browser.goto('/odoo/tour_manager')
        browser.click('.o_kanban_record', title, inner=f'button[name={button}]')

    def test_typing_and_autocomplete(self):
        company = self.env.company
        company.write({'email': False, 'country_id': False})
        with self.browser() as browser:
            self.start_recording(browser, "Fill the company", f'/odoo/action-base.action_res_company_form/{company.id}')
            browser.wait_for('.o_form_view div[name=email] input')
            browser.click('.o_form_view div[name=email] input')
            browser.type("tm@example.com")
            browser.press('Tab')
            self.hint(browser, "Type the email.", "Typed “tm@example.com” in Email")
            # Typing in an autocomplete and choosing an option: one step, with one hint
            browser.click('.o_form_view div[name=country_id] input')
            browser.type("Belg")
            browser.click('.o-autocomplete--dropdown-item > a', "Belgium")
            self.hint(browser, "Choose the country.", "Selected “Belgium” in Country")
            self.assertIn("3 step", browser.text('.o_tour_manager_step_count'))
            # Undo removes both steps of the choice
            browser.click('.o_tour_manager_undo')
            browser.wait_for('.o_tour_manager_step_count', "1 step")
            # Choosing with the keyboard
            browser.click('.o_form_view div[name=country_id] input')
            browser.select_all()
            browser.type("Belg")
            browser.wait_for('.o-autocomplete--dropdown-item .ui-state-active', "Belgium")
            browser.press('Enter')
            self.hint(browser, "Choose the country.", "Selected “Belgium”")
            browser.click('.o_tour_manager_finish')
            browser.wait_for('.o_tour_manager_highlight')
        tour = self.Tour.search([('title', '=', "Fill the company")])
        self.assertEqual([step.run for step in tour._get_ordered_steps()], ['edit tm@example.com', 'edit Belg', 'click'])
        self.assertIn("Belgium", tour._get_ordered_steps()[2].trigger)
        self.assertFalse(company.email, "the example changes were saved")

    def test_drag_and_drop_and_editor(self):
        demo = self.make_tour('tm_ui_dnd_demo', '/odoo', [
            {'trigger': '.first', 'run': 'click'}, {'trigger': '.second', 'run': 'click'},
            {'trigger': '.third', 'run': 'click'},
        ])
        rows = '.o_form_view div[name=step_ids] .o_data_row'
        with self.browser() as browser:
            self.start_recording(browser, "Reorder steps", f'/odoo/action-web_tour.tour_action/{demo.id}')
            browser.wait_for(f'{rows} .o_row_handle')
            browser.drag(f'{rows}:nth-child(1) .o_row_handle', f'{rows}:nth-child(3)')
            self.hint(browser, "Move the step.", "Dragged")
            browser.wait_for(f'{rows}:nth-child(1)', '.second')
            browser.click('div[name=rainbow_man_message] .odoo-editor-editable')
            browser.type("Bravo")
            browser.click('.o_form_button_save')
            self.hint(browser, "Write a message.", "Bravo")
            self.hint(browser, "Save.", "Clicked")
            browser.click('.o_tour_manager_finish')
            browser.wait_for('.o_tour_manager_highlight')
        tour = self.Tour.search([('title', '=', "Reorder steps")])
        runs = [step.run for step in tour._get_ordered_steps()]
        # Dropped after the third row (as before the drag)
        self.assertRegex(runs[0], r"^drag_and_drop \(.*o_data_row:nth-child\(3\).*\)$")
        self.assertIn('editor ', ' '.join(runs))
        self.assertEqual(runs[-1], 'click')
        # The recorded save was performed: put the steps back in their order to replay it
        for sequence, trigger in enumerate(['.first', '.second', '.third'], start=1):
            demo.step_ids.filtered(lambda step, trigger=trigger: step.trigger == trigger).sequence = sequence

        # Replayed by hand: the drop is waited for, then the typing in the editor
        with self.browser() as browser:
            self.card_button(browser, "Reorder steps", 'action_start_tour')
            browser.wait_for(f'{rows} .o_row_handle')
            browser.wait_for(POINTER)
            browser.drag(f'{rows}:nth-child(1) .o_row_handle', f'{rows}:nth-child(3)')
            browser.wait_until("localStorage.getItem('current_tour.index') === '2'",
                               message="the drop wasn't waited for")
            browser.click('div[name=rainbow_man_message] .odoo-editor-editable')
            browser.type("Bravo")
            browser.click('.o_form_button_save')
            browser.wait_for('.o_reward_rainbow_man')

    def test_check(self):
        self.make_tour('tm_ui_passing', USERS_URL, [{'trigger': '.o_list_button_add', 'run': 'click', 'content': "New"}])
        failing = self.make_tour('tm_ui_failing', USERS_URL, [
            {'trigger': '.o_list_button_add', 'run': 'click'},
            {'trigger': '.o_does_not_exist', 'run': 'click', 'content': "The missing button"},
        ])
        with self.browser() as browser:
            for title, expected in (("Tm ui passing", "All 1 steps work."), ("Tm ui failing", "Step 2 of 2")):
                self.card_button(browser, title, 'action_check_tour')
                browser.click('.modal .modal-footer .btn-primary')  # confirm
                browser.wait_for('.modal', "Check ", timeout=40)
                self.assertIn(expected, browser.text('.modal', "Check "))
                # Shown on the last screen of the tour
                self.assertNotIn('/odoo/tour_manager', browser.evaluate('location.pathname'))
                browser.click('.modal button', "Back to Tours")
                browser.wait_for('.o_tour_manager_highlight')
        self.assertEqual(failing.check_state, 'failed')
        self.assertEqual(failing.check_step, 2)
        self.assertIn(".o_does_not_exist", failing.check_message)
        self.assertEqual(self.Tour.search([('name', '=', 'tm_ui_passing')]).check_state, 'passed')
        self.assertNotIn(self.admin, self.Tour.search([('name', '=', 'tm_ui_passing')]).user_consumed_ids)

    def test_leave_warning_and_stop_tour(self):
        self.make_tour('tm_ui_leave', USERS_URL, [
            {'trigger': '.o_list_button_add', 'run': 'click', 'content': "Create a user"},
            {'trigger': '.o_form_button_save', 'run': 'click'},
        ])
        with self.browser() as browser:
            self.card_button(browser, "Tm ui leave", 'action_start_tour')
            browser.wait_for(POINTER)
            # Clicking in a field doesn't ask; a button does
            browser.click('.o_searchview_input')
            self.assertEqual(browser.count('.modal'), 0)
            browser.click('.o_searchview_dropdown_toggler')
            browser.wait_for('.modal', "Leave the tour?")
            browser.click('.modal button', "Stay in the tour")
            browser.wait_for_absent('.modal')
            self.assertEqual(browser.local_storage('current_tour'), 'tm_ui_leave')
            browser.click('.o_searchview_dropdown_toggler')
            browser.wait_for('.modal', "Leave the tour?")
            browser.click('.modal button', "Leave tour")
            browser.wait_until("localStorage.getItem('current_tour') === null")
            browser.wait_for_absent(POINTER)
            # Stop Tour stops a replay for good
            self.card_button(browser, "Tm ui leave", 'action_start_tour')
            browser.wait_for(POINTER)
            browser.hover('.o_list_button_add')
            browser.click('.o_tour_pointer_content button', "Stop Tour")
            browser.wait_for('.o_list_button_add')
            browser.wait_until("localStorage.getItem('current_tour') === null")

    def test_visibility_and_auto_start(self):
        group = self.env['res.groups'].create({'name': "Tour Manager UI Group"})
        self.env['res.users'].create({
            'name': "Emma", 'login': 'tm_emma', 'password': 'tm_emma',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        welcome = self.make_tour('tm_ui_welcome', '/odoo/tour_manager', [
            {'trigger': '.o_searchview_input', 'run': 'click', 'content': "Search the tours"},
        ], auto_start=True, sequence=1)
        self.make_tour('tm_ui_restricted', '/odoo/tour_manager', [{'trigger': 'body', 'run': 'click'}],
                       group_ids=[(6, 0, group.ids)])
        with self.browser(login='tm_emma', path='/odoo/tour_manager') as browser:
            browser.wait_for('.o_kanban_record')
            browser.wait_until("localStorage.getItem('current_tour') === 'tm_ui_welcome'")
            self.assertTrue(browser.count('.o_kanban_record', "Tm ui welcome"))
            self.assertFalse(browser.count('.o_kanban_record', "Tm ui restricted"))
            # Leaving it dismisses it
            browser.wait_for(POINTER)
            browser.click('.o_switch_view.o_list')
            browser.wait_for('.modal', "Leave the tour?")
            browser.click('.modal button', "Leave tour")
            browser.wait_until("localStorage.getItem('current_tour') === null")
            browser.goto('/odoo/tour_manager')
            browser.wait_for('.o_kanban_record, .o_list_view')
            browser.wait_until("localStorage.getItem('current_tour') === null")
        emma = self.env['res.users'].search([('login', '=', 'tm_emma')])
        self.assertIn(emma, welcome.user_dismissed_ids)
        self.assertFalse(emma.tour_enabled)

    def test_step_editor(self):
        tour = self.make_tour('tm_ui_editor', USERS_URL, [
            {'trigger': '.o_list_button_add', 'run': 'click', 'content': "Create a user"},
            {'trigger': '.o_broken_field', 'run': 'click', 'content': "Their login"},
        ])
        rows = '.o_form_view div[name=step_ids] .o_data_row'

        def step_button(browser, number, button):
            self.card_button(browser, "Tm ui editor", 'action_edit_tour')
            browser.wait_for(rows)
            browser.click(f'{rows}:nth-child({number}) button[name={button}]')
            browser.click('.modal .modal-footer .btn-primary')  # confirm

        with self.browser() as browser:
            # Record an info step after step 1: step 1 is played first
            step_button(browser, 1, 'action_record_after')
            browser.wait_for('.o_tour_manager_bar', "after step 1")
            browser.wait_for('.o_form_view div[name=name] input')
            browser.wait_for_absent('.o_tour_manager_prelude')
            browser.click('.o_tour_manager_add_info')
            browser.click('.o_form_view div[name=name]')
            self.hint(browser, "Their name goes here.", "Info step on")
            browser.click('.o_tour_manager_finish')
            browser.wait_for('.o_notification', "1 step(s) added")
            # Pick the element of the broken step again: steps 1 and 2 are played first
            step_button(browser, 3, 'action_pick_element')
            browser.wait_for('.o_tour_manager_picking', "Click the new element of step 3", timeout=40)
            browser.click('.o_form_view div[name=login] input')
            browser.wait_for('.o_tour_manager_hint_popover')
            self.assertEqual(browser.value('.o_tour_manager_hint_popover textarea'), "Their login")
            browser.click('.o_tour_manager_hint_popover .o_tour_manager_next')
            browser.wait_for('.o_notification', "Step 3 of")
        steps = tour._get_ordered_steps()
        self.assertEqual([step.run for step in steps], ['click', 'next', 'click'])
        self.assertIn("name", steps[1].trigger)
        self.assertIn("login", steps[2].trigger)

    def test_icon_picker(self):
        with self.browser(path='/odoo/tour_manager') as browser:
            browser.click('.o-kanban-button-new')
            browser.click('.modal .o_tour_manager_icon_choose')
            browser.click('.o_tour_manager_icon_tab_icons')
            browser.click('.o_tour_manager_icon_search')
            browser.type("money")
            browser.wait_until("document.querySelectorAll('.o_tour_manager_set_icon').length < 100")
            name = browser.evaluate("document.querySelector('.o_tour_manager_set_icon').dataset.name")
            browser.click('.o_tour_manager_set_icon')
            browser.wait_for(f".modal .o_tour_manager_icon_preview i[data-icon='{name}']")

    def test_kanban_drag_and_drop(self):
        """Dragging a card to another column of a kanban (only when CRM is installed)."""
        if 'crm.lead' not in self.env:
            self.skipTest("CRM isn't installed")
        stages = self.env['crm.stage'].search([], limit=2)
        if len(stages) < 2:
            self.skipTest("CRM has less than two stages")
        self.env['crm.lead'].search([('user_id', '=', self.admin.id)]).write({'user_id': False})
        lead = self.env['crm.lead'].create({
            'name': "Drag me", 'type': 'opportunity', 'stage_id': stages[0].id, 'user_id': self.admin.id,
        })
        card = ".o_kanban_record"
        with self.browser() as browser:
            self.start_recording(browser, "Move an opportunity", '/odoo/crm')
            browser.wait_for(card, "Drag me")
            browser.drag(card, '.o_kanban_group:nth-child(2)')
            self.hint(browser, "Move it to the next stage.", "Dragged")
            self.assertEqual(lead.stage_id, stages[1])
            browser.click('.o_tour_manager_finish')
            browser.wait_for('.o_tour_manager_highlight')
            tour = self.Tour.search([('title', '=', "Move an opportunity")])
            self.assertRegex(tour.step_ids.run, r"^drag_and_drop \(.*o_kanban_group.*\)$")
            # Replayed by hand
            lead.stage_id = stages[0]
            browser.click('.o_tour_manager_highlight button[name=action_start_tour]')
            browser.wait_for(card, "Drag me")
            browser.wait_for(POINTER)
            browser.drag(card, '.o_kanban_group:nth-child(2)')
            browser.wait_for('.o_reward_rainbow_man')
