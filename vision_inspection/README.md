# Vision Inspection

Receives the results of computer vision quality inspections in Odoo. A camera system
(an RF-DETR model, Roboflow Inference, a vendor's smart camera…) analyses each sample,
then **pushes** what it found to Odoo over HTTP. Odoo stores the image and its detections,
decides whether the sample passes and reports on the defects.

The module only depends on `product` and `mail`. To feed OCA's quality control
inspections, install `vision_inspection_quality_control_oca` too.

## Concepts

| Model | What it is |
|---|---|
| Source (`vision.source`) | A system that sends results. It has its own endpoint, token, format (*adapter*) and the user its inspections are created as. |
| Station (`vision.station`) | An inspection point of a source, such as one camera on a line. It sets the default product and the confidences the verdict uses. |
| Defect class (`vision.defect.class`) | Maps a label of the model to a defect, with its severity and how many are allowed per sample. Unknown labels create a class, which allows none. |
| Inspection (`vision.inspection`) | One analysed sample: image, product, lot, detections and verdict. |
| Detection (`vision.detection`) | One box found by the model: class, confidence and position. |

## Verdict

With the station's verdict set to *Odoo Rules*:

1. Detections below the station's **minimum confidence**, and those of classes that aren't
   defects, are kept but not counted.
2. **Fail** if a class has more counted detections than it allows per sample.
3. Otherwise, **To Review** if a counted detection is below the station's **review confidence**.
4. Otherwise, **Pass**.

With *Sent by the Source*, the `verdict` in the results is used, and the rules above
apply when there's none. Users can always mark an inspection as pass or fail by hand.

## Sending results

```
POST /vision_inspection/<source code>/results
Authorization: Bearer <token of the source>
Content-Type: application/json
```

The source's form shows its endpoint and token. When the server hosts several databases
and no `dbfilter` picks one, add an `X-Odoo-Database: <database>` header. The response is
`{"inspection": "VIS/2026/000042", "verdict": "fail"}`, or `{"error": "…"}` with status
401 (wrong token), 403 (the source's user lacks rights), 404 (unknown source, station or
product), 415 (not sent as JSON) or 400 (invalid results). Sending results again with the same `external_id`
updates that inspection instead of creating another one, so a system can safely retry.

### Generic adapter

```json
{
  "external_id": "8f1c2a",
  "station": "line1-cam-a",
  "captured_at": "2026-10-27T10:15:00Z",
  "product_code": "PCB-001",
  "lot": "LOT-42",
  "model": {"name": "rf-detr-nano", "version": "visa-pcb-1"},
  "image": {"mime": "image/jpeg", "data": "<base64>"},
  "detections": [
    {"label": "scratch", "confidence": 0.91, "bbox": {"x": 0.12, "y": 0.40, "w": 0.05, "h": 0.03}}
  ],
  "verdict": "fail"
}
```

Only `detections` matters. The other keys are all optional:

- `station`: may be left out when the source has a single station.
- `product_code`: the internal reference of the product. Without it, the station's product is used.
- `captured_at`: ISO 8601, in UTC unless it has an offset. Defaults to the time Odoo receives it.
- `bbox`: relative to the image, from 0 to 1, from its top-left corner.
- `verdict`: `pass`, `review` or `fail`, only used by stations that trust their source.

### Roboflow adapter

Accepts what Roboflow Inference returns (`inference_id`, `image.width/height`,
`predictions[]` with box centres and sizes in pixels), as well as a Workflow's output
whose `predictions` key holds these results. The optional keys of the generic adapter
(`station`, `product_code`, `lot`, `captured_at`, `verdict`) can be added next to them,
and the image as `image_base64`.

### Another system

Add a value to the `adapter` selection of `vision.source` and a
`_parse_payload_<value>(payload)` method that returns the same dictionary as
`_parse_payload_generic`.

### Example

```bash
curl -X POST "http://localhost:8069/vision_inspection/line1/results" \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"station": "line1-cam-a", "detections": [{"label": "scratch", "confidence": 0.9,
          "bbox": {"x": 0.1, "y": 0.2, "w": 0.1, "h": 0.1}}]}'
```
