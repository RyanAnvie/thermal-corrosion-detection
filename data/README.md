# Included experimental data

`early_heating.npz` contains the key `cropped_images`, a float32 array with shape **151 × 505 × 151**, ordered as **frame, row, column**. These are original frames 0–150 inclusive from the same cropped recording used for the animation. The frame values are bit-for-bit preserved. Compression is lossless; there is no temporal subsampling, spatial resizing, denoising, smoothing, or temperature conversion in this file.

Temperatures are already in degrees Celsius. Zero is the existing out-of-specimen sentinel, not a valid measured 0 °C for this dataset. Image coordinates use an upper-left origin: x is column, y is row, and y increases downward.

The configured analysis rate is 60 fps. The example spans 0–2.5 s. The original archive contains 9,000 frames and spans approximately 150 s; its size is approximately 2.7 GB and it is not included here. No public download location is currently specified in this repository.

`roi_masks.npz` contains the existing `analysis_mask`, `corroded_mask`, and `reference_mask`, all Boolean arrays of shape 505 × 151. They belong to this specimen and coordinate frame. The latter two are thermal region definitions retained from the working project, not independent ground-truth annotations. The animation calculates means over the fixed rectangles, without clipping the rectangles to these semantic masks.

| ROI | x range | y range | Pixel count |
|---|---|---|---:|
| A | 26 ≤ x < 42 | 349 ≤ y < 365 | 256 |
| B | 97 ≤ x < 113 | 399 ≤ y < 415 | 256 |

`regional_temperature_curves.csv` is copied unchanged from the existing full-record analysis. It contains 9,000 rows, including source frame index, recording time in seconds, both ROI means in °C, valid pixel counts, and reference coverage. Its first 151 rows correspond to the bundled example. The CSV can be inspected without the full recording.

`animation_metadata.json` records the original recording dimensions and member CRC, example array SHA-256, temperature limits, selected coordinates, and video timing. The local source drive path has been replaced with a portable filename description.

To extract another copy from the full archive, place it at `data/raw/cropped_images.npz`, then run:

```bash
python scripts/prepare_sample.py
```

The script writes to `outputs/extracted/`, reads the source without modifying it, and refuses to overwrite an existing extraction. Edit its path and frame settings as needed. It does not recalibrate arbitrary camera data or generate new specimen masks.
