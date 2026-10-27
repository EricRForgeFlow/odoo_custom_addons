from odoo.tests import TransactionCase, new_test_user

# 1x1 transparent PNG
PNG_PIXEL = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='


class VisionInspectionCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Models
        cls.Source = cls.env['vision.source']
        cls.Station = cls.env['vision.station']
        cls.DefectClass = cls.env['vision.defect.class']
        cls.Inspection = cls.env['vision.inspection']
        # Instances
        cls.ingest_user = new_test_user(cls.env, login='vision_ingest', groups='vision_inspection.group_vision_user')
        cls.product = cls.env['product.product'].create({'name': "Vision Part", 'default_code': 'VIS-PART'})
        cls.other_product = cls.env['product.product'].create({'name': "Other Part", 'default_code': 'VIS-OTHER'})
        cls.source = cls._create_source(user_id=cls.ingest_user.id)
        cls.station = cls._create_station(source_id=cls.source.id)
        cls.scratch = cls._create_defect_class(name="Scratch", code='t_scratch', severity='minor', max_allowed=1)
        cls.crack = cls._create_defect_class(name="Crack", code='t_crack', severity='critical')
        cls.part = cls._create_defect_class(name="Part", code='t_part', is_defect=False)

    @classmethod
    def _create_source(cls, **kwargs):
        return cls.Source.create({
            'name': "Test Source",
            'code': 'test-source',
            'token': 'test-token',
            **kwargs,
        })

    @classmethod
    def _create_station(cls, **kwargs):
        return cls.Station.create({
            'name': "Test Station",
            'code': 'test-station',
            'product_id': cls.product.id,
            'min_confidence': 0.5,
            'review_confidence': 0.7,
            **kwargs,
        })

    @classmethod
    def _create_defect_class(cls, **kwargs):
        return cls.DefectClass.create(kwargs)

    @classmethod
    def _detection(cls, label, confidence=0.9, x=0.1, y=0.1, w=0.2, h=0.2):
        return {'label': label, 'confidence': confidence, 'bbox': {'x': x, 'y': y, 'w': w, 'h': h}}

    @classmethod
    def _generic_payload(cls, detections=(), **kwargs):
        return {
            'station': 'test-station',
            'model': {'name': 'rf-detr-nano', 'version': 'test'},
            'image': {'mime': 'image/png', 'data': PNG_PIXEL},
            'detections': list(detections),
            **kwargs,
        }
