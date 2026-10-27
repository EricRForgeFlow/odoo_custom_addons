{
    'name': 'Vision Inspection - Quality Control OCA',
    'version': '20.0.1.0.0',
    'category': 'Supply Chain/Quality',
    'summary': 'Turn vision inspections into OCA quality control inspections',
    'description': """
Vision Inspection - Quality Control OCA
=======================================

Creates a quality control inspection (OCA) for the vision inspections of a
station, with the number of defects of each class as the values of the test's
questions. Inspections that don't pass wait for the approval of a quality
manager.
""",
    'depends': ['vision_inspection', 'quality_control_oca'],
    'data': [
        'views/qc_inspection_views.xml',
        'views/qc_test_views.xml',
        'views/vision_inspection_views.xml',
        'views/vision_station_views.xml',
    ],
    'icon': '/vision_inspection_quality_control_oca/static/description/icon.svg',
    'auto_install': True,
    'author': 'ForgeFlow',
    'license': 'LGPL-3',
}
