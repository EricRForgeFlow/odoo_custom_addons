import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { imageUrl } from "@web/core/utils/urls";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, t, useProps } from "@odoo/owl";

const percent = (value) => `${(Math.min(Math.max(value, 0), 1) * 100).toFixed(2)}%`;

/**
 * Image of a vision inspection, with the boxes of its detections drawn over it.
 */
export class ImageAnnotationsField extends Component {
    static template = "vision_inspection.ImageAnnotationsField";
    props = useProps({
        ...standardFieldProps,
        detectionsField: t.string().optional("detection_ids"),
    });

    get imageSrc() {
        const { record, name } = this.props;
        return imageUrl(record.resModel, record.resId, name, {
            unique: record.data[name]?.checksum || record.data.write_date,
        });
    }

    get boxes() {
        const detections = this.props.record.data[this.props.detectionsField]?.records || [];
        return detections.map(({ id, data }) => ({
            id,
            label: `${data.defect_class_id?.display_name || data.label} ${Math.round(data.confidence * 100)}%`,
            className: `o_vision_box o_vision_box_${data.counted ? data.severity : "ignored"}`,
            style: [
                `left: ${percent(data.bbox_x)}`,
                `top: ${percent(data.bbox_y)}`,
                `width: ${percent(data.bbox_w)}`,
                `height: ${percent(data.bbox_h)}`,
            ].join("; "),
        }));
    }
}

export const imageAnnotationsField = {
    component: ImageAnnotationsField,
    displayName: _t("Image with Detections"),
    supportedTypes: ["binary"],
    supportedOptions: [
        {
            label: _t("Detections field"),
            name: "detections_field",
            type: "field",
            availableTypes: ["one2many"],
        },
    ],
    fieldDependencies: [{ name: "write_date", type: "datetime" }],
    extractProps: ({ options }) => ({
        detectionsField: options.detections_field,
    }),
};

registry.category("fields").add("vision_image_annotations", imageAnnotationsField);
