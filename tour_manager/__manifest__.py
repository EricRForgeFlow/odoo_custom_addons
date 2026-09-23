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
available for the installed apps so they can be started again at any time.
""",
    'depends': ['web_tour'],
    'data': [
        'views/web_tour_tour_views.xml',
        'views/tour_manager_menus.xml',
    ],
    'application': True,
    'author': 'ForgeFlow',
    'license': 'LGPL-3',
}
