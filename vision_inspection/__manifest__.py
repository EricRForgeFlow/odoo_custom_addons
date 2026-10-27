{
    'name': 'Vision Inspection',
    'version': '20.0.1.0.0',
    'category': 'Supply Chain/Quality',
    'sequence': 310,
    'summary': 'Receive the results of computer vision quality inspections',
    'description': """
Vision Inspection
=================

Connects computer vision systems (RF-DETR, Roboflow Inference, vendor
cameras...) to Odoo. Each system pushes the defects it detected on an image to
an HTTP endpoint, and Odoo stores the image with its detections and decides
whether the sample passes.
""",
    'depends': ['product', 'mail'],
    'data': [
        'security/vision_inspection_security.xml',
        'security/ir.access.csv',
        'data/ir_sequence_data.xml',
        'views/vision_source_views.xml',
        'views/vision_station_views.xml',
        'views/vision_defect_class_views.xml',
        'views/vision_detection_views.xml',
        'views/vision_inspection_views.xml',
        'views/vision_inspection_menus.xml',
    ],
    'demo': ['demo/vision_inspection_demo.xml'],
    'assets': {
        'web.assets_backend': [
            'vision_inspection/static/src/**/*',
        ],
    },
    'icon': '/vision_inspection/static/description/icon.svg',
    'application': True,
    'author': 'ForgeFlow',
    'license': 'LGPL-3',
}
