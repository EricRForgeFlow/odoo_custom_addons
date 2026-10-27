from odoo import fields, models

OPEN_QC_STATES = ('plan', 'draft', 'ready', 'waiting')


class VisionInspection(models.Model):
    _inherit = 'vision.inspection'

    qc_inspection_ids = fields.One2many('qc.inspection', 'vision_inspection_id', string="Quality Inspections")
    qc_inspection_count = fields.Integer(compute='_compute_qc_inspection_count')

    def _compute_qc_inspection_count(self):
        for inspection in self:
            inspection.qc_inspection_count = len(inspection.qc_inspection_ids)

    def action_view_qc_inspections(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('quality_control_oca.action_qc_inspection')
        action['domain'] = [('vision_inspection_id', '=', self.id)]
        action['context'] = {}
        if len(self.qc_inspection_ids) == 1:
            action.update({'view_mode': 'form', 'views': [(False, 'form')], 'res_id': self.qc_inspection_ids.id})
        return action

    def _after_ingest(self):
        super()._after_ingest()
        self._sync_qc_inspections()

    def _after_verdict_override(self):
        super()._after_verdict_override()
        self._sync_qc_inspections()

    def _needs_qc_inspection(self):
        self.ensure_one()
        station = self.station_id
        if not station.qc_test_id or station.qc_trigger == 'never':
            return False
        return station.qc_trigger == 'always' or self.verdict != 'pass'

    def _sync_qc_inspections(self):
        """Create the quality inspection the station asks for, or bring the open ones up to date.

        Quality inspections are system records: sources and users of the vision app
        don't need rights on quality control to trigger them.
        """
        for inspection in self.sudo():
            open_qc = inspection.qc_inspection_ids.filtered(lambda qc: qc.state in OPEN_QC_STATES)
            if not open_qc and not inspection.qc_inspection_ids and inspection._needs_qc_inspection():
                open_qc = inspection._create_qc_inspection()
            open_qc._fill_vision_counts()
            for qc in open_qc.filtered(lambda qc: qc.state in ('ready', 'waiting') and qc._can_confirm_from_vision()):
                qc.action_confirm()

    def _create_qc_inspection(self):
        self.ensure_one()
        test = self.station_id.qc_test_id
        QcInspection = self.env['qc.inspection']
        return QcInspection.create({
            'object_id': f'{self._name},{self.id}',
            'vision_inspection_id': self.id,
            'test': test.id,
            'date': self.captured_at,
            'state': 'ready',
            'auto_generated': True,
            'company_id': self.company_id.id,
            'inspection_lines': QcInspection._prepare_inspection_lines(test),
        })
