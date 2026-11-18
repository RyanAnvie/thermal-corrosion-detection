# Reproduction and provenance

## What was carried over

- `scripts/sigmoid_gmm.py` was extracted from the sigmoid section of `AMPP_2026/2d_GMM.py` (original lines 586–804). It retains the four-parameter model, initial guesses, fit bounds, 149-frame fitting window, denoising settings, unstandardized feature triplet, full-covariance two-component GMM, regularization, and random seed.
- `scripts/thermal_heating_animation.py` uses the accepted layout and encoding section from `ampp_2027/thermal_heating_animation.py`. Its inputs are now the bundled frame excerpt and masks. The portable script uses DejaVu Sans instead of Arial; original homepage video files are copied unchanged.
- `scripts/prepare_sample.py` uses the existing uncompressed-NPZ memory-mapping approach to avoid loading the entire original recording. Compressed source archives fall back to in-memory decompression.
- The setup photograph, six-map PNG/SVG, animation GIF/MP4, preview, and full-record CSV were copied byte-for-byte. Their source identifiers and hashes are listed in [asset_manifest.json](asset_manifest.json).

The original working directories were not edited. Acquisition programs, exploratory alternatives, interactive polygon experiments, point-cloud reconstruction, caches, and the full raw recording are outside this focused release. This repository covers the thermal fitting, clustering, and visualization workflow.

## Processing details

The sigmoid fitting stage selects source frames 1–149 inclusive. Fitting time starts at zero at source frame 1, so fitted t₀ is relative to the selected window, not the start of the recording.

With `use_denoise = True`, each frame's finite positive pixels are min-max mapped to uint8, passed through OpenCV `fastNlMeansDenoising` with h=20, template window 7, and search window 21, and mapped back to the original frame's temperature range. This quantization and spatial denoising alter pixel values and are explicit parts of the inherited fitting workflow. The included input file itself remains unfiltered. Constant-valued frames are retained without a divide-by-zero operation; nonfinite values remain missing.

Per-pixel initial guesses are A=max(T)−min(T), k=1, t₀=median(t), and B=min(T). Bounds are A ∈ [0,2] °C, k ∈ [0.01,5] s⁻¹, t₀ ∈ [0,max(t)] s, and B ∈ [20,30] °C. These are specimen-specific original settings, not universal bounds for other experiments.

Pixels with fewer than five usable measurements are not fitted. Fit failures remain NaN. `parameter_maps.npz` records observation counts and status codes: 0=success, 1=insufficient observations, 2=failed fit. `run_summary.json` reports totals. No outlier rejection, temporal interpolation, or added temporal smoothing is used.

GMM input is the finite `(A,k,t₀)` triplet without standardization. Settings are `n_components=2`, `covariance_type="full"`, `reg_covar=1e-6`, `random_state=42`, and `max_iter=500`. IDs can exchange between runs or software versions. The curated script therefore labels new results as clusters 0 and 1, instead of automatically asserting Rust/Normal semantics. The existing homepage map retains its original interpreted labels.

## Animation and interpretation

The animation uses raw source frames 0–150 and ordinary means of two fixed 16 × 16 pixel rectangles. Invalid and zero-sentinel pixels are omitted from spatial means, valid counts are exported, and an empty ROI would remain NaN. All 256 pixels in each displayed ROI are valid in the included example. The selected rectangles are illustrative local regions and are not an unbiased whole-specimen comparison.

At 30 output fps and 0.25× playback, source frames are repeated rather than interpolated. The final frame is held for 1.5 s. The copied video contains 346 frames and lasts 11.533 s. Thermal image limits are fixed at 25–28 °C, while the curve limits are fixed at 25.80–26.45 °C. Fixed limits apply throughout the animation.

The original figure is a preserved presentation result, not an assertion of pixel-identical regeneration. The original interactive selections and complete original environment were not archived, and no independent corrosion ground-truth file is supplied. A fresh run exposes all current numerical outputs and software versions for inspection; no accuracy score is inferred from the cluster labels.

## Running and exports

Run the scripts from an activated Python environment. On Windows, invoking an unactivated Conda interpreter by its full path can leave required native DLL directories unavailable; use an activated environment for the listed commands. Dependencies are declared in `requirements.txt`; this is not a complete environment lock.

Figures use the noninteractive Agg backend. Static exports retain a 16 cm width, 13 pt titles, 10 pt axis labels/ticks, 9 pt annotations, 600 dpi PNG output, and SVG output. There is no interactive resize window in these scripts. The animation encoder requires FFmpeg and FFprobe on PATH.

New results go under `outputs/`, which is ignored by Git. Curated homepage assets remain unchanged. No license was selected automatically during repository preparation.

## Paper metadata

The DOI was supplied by the author. The title and author order were checked against the [official AMPP conference listing](https://aceampp2026.eventscribe.net/fsPopup.asp?PresentationID=1763237&mode=presInfo). This preparation did not retrieve or redistribute the full published article.
