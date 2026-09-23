{
    'name': 'Tour Manager',
    'version': '20.0.1.0.0',
    'category': 'Productivity',
    'sequence': 300,
    'summary': 'Browse and replay the onboarding tours of your installed apps',
    'description': """
Tour Manager
============

Odoo only plays each app's onboarding tour once. This app lists the tours
available for the installed apps so they can be started again at any time,
and lets administrators record their own custom tours.
""",
    'depends': ['web_tour'],
    'data': [
        'security/ir.access.csv',
        'wizard/tour_create_wizard_views.xml',
        'views/web_tour_tour_views.xml',
        'views/tour_manager_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'tour_manager/static/src/tour_creator_state.js',
            'tour_manager/static/src/tour_creator_plugin.js',
            'tour_manager/static/src/tour_creator.scss',
            'tour_manager/static/src/tour_replay/tour_replay_plugin.js',
            'tour_manager/static/src/tour_replay/tour_replay_action.js',
            'tour_manager/static/src/views/**/*',
        ],
        'web.assets_frontend': [
            'tour_manager/static/src/tour_replay/tour_replay_plugin.js',
        ],
        'web_tour.interactive': [
            'tour_manager/static/src/tour_replay/tour_interactive_patch.js',
        ],
        'tour_manager.tour_creator': [
            ('include', 'web_tour.common'),
            'tour_manager/static/src/tour_creator/**/*',
        ],
    },
    'application': True,
    'author': 'ForgeFlow',
    'license': 'LGPL-3',
}
