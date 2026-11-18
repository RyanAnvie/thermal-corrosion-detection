"""Fit the paper's sigmoid response model and cluster the thermal parameters."""

from pathlib import Path
import json
import platform

import cv2
import joblib
import matplotlib
import numpy as np
import scipy
import sklearn
from joblib import Parallel, delayed
from scipy.optimize import curve_fit
from sklearn.mixture import GaussianMixture

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap


root = Path(__file__).resolve().parents[1]
input_path = root / "data/early_heating.npz"
output_folder = root / "outputs/sigmoid_gmm"
fps = 60.0
start_idx, end_idx = 1, 150  # Source frame indices; end is exclusive.
use_denoise = True  # Original per-frame uint8 non-local means preprocessing.
denoise_h = 20
template_window = 7
search_window = 21
n_jobs = 4  # The original script also used joblib parallel fitting; 1 is serial.
random_seed = 42
lower_bounds = [0.0, 0.01, 0.0, 20.0]
amplitude_upper_bound = 2.0
rate_upper_bound = 5.0
baseline_upper_bound = 30.0
max_evaluations = 5000
ignore_value = 0.0
ignore_tolerance = 1e-12
figure_width_cm = 16.0
figure_height_cm = 14.0
title_font_size = 13
axis_font_size = 10
annotation_font_size = 9
export_dpi = 600


def sigmoid_model(t, A, k, t0, B):
    return A / (1.0 + np.exp(-k * (t - t0))) + B


def fit_sigmoid(series, time_seconds):
    # Match the original zero-sentinel rule; missing observations are not filled.
    values = np.asarray(series, dtype=np.float64)
    valid = np.isfinite(values)
    valid &= ~np.isclose(values, ignore_value, atol=ignore_tolerance)
    if np.count_nonzero(valid) < 5:
        return [np.nan] * 5, 1
    t_fit = time_seconds[valid]
    y_fit = values[valid]
    initial = [float(y_fit.max() - y_fit.min()), 1.0,
               float(np.median(t_fit)), float(y_fit.min())]
    upper_bounds = [amplitude_upper_bound, rate_upper_bound,
                    float(t_fit.max()), baseline_upper_bound]
    try:
        parameters, covariance = curve_fit(
            sigmoid_model, t_fit, y_fit, p0=initial,
            bounds=(lower_bounds, upper_bounds), maxfev=max_evaluations)
    except (RuntimeError, ValueError):
        # Failures remain NaN and receive an explicit status in the output.
        return [np.nan] * 5, 2
    predicted = sigmoid_model(t_fit, *parameters)
    rmse = float(np.sqrt(np.mean((y_fit - predicted) ** 2)))
    return [*parameters, rmse], 0


if __name__ == "__main__":
    with np.load(input_path, allow_pickle=False) as saved:
        frames = saved["cropped_images"][start_idx:end_idx].copy()
    if len(frames) != end_idx - start_idx:
        raise ValueError("Input does not contain the configured fitting window.")
    # The original fit zeroed time AFTER selecting source frames [1:150].
    time_seconds = np.arange(len(frames), dtype=np.float64) / fps
    missing_before_processing = int(np.count_nonzero(~np.isfinite(frames)))
    print("Fitting source frames", start_idx, "through", end_idx - 1, flush=True)

    if use_denoise:
        denoised_frames = np.zeros_like(frames, dtype=np.float32)
        for frame_index, frame in enumerate(frames):
            mask = np.isfinite(frame) & (frame > 0)
            denoised_frames[frame_index][~np.isfinite(frame)] = np.nan
            if not np.any(mask):
                continue
            vmin, vmax = frame[mask].min(), frame[mask].max()
            if vmax == vmin:
                denoised_frames[frame_index][mask] = frame[mask]
                continue
            normalized = np.zeros_like(frame, dtype=np.uint8)
            normalized[mask] = ((frame[mask] - vmin) / (vmax - vmin) * 255).astype(np.uint8)
            filtered = cv2.fastNlMeansDenoising(
                normalized, None, h=denoise_h,
                templateWindowSize=template_window, searchWindowSize=search_window)
            denoised_frames[frame_index][mask] = (
                filtered[mask].astype(np.float32) / 255.0 * (vmax - vmin) + vmin)
        frames = denoised_frames

    height, width = frames.shape[1:]
    valid_observations = np.isfinite(frames)
    valid_observations &= ~np.isclose(frames, ignore_value, atol=ignore_tolerance)
    valid_counts = np.sum(valid_observations, axis=0)
    rows, columns = np.where(valid_counts >= 5)
    print("Pixels with at least five observations:", len(rows), flush=True)
    results = Parallel(n_jobs=n_jobs, verbose=5)(
        delayed(fit_sigmoid)(frames[:, row, column], time_seconds)
        for row, column in zip(rows, columns))

    maps = np.full((5, height, width), np.nan, dtype=np.float32)
    fit_status = np.ones((height, width), dtype=np.uint8)
    for index, (row, column) in enumerate(zip(rows, columns)):
        parameters, status = results[index]
        maps[:, row, column] = parameters
        fit_status[row, column] = status
    A_map, k_map, t0_map, B_map, rmse_map = maps
    features = np.stack([A_map.ravel(), k_map.ravel(), t0_map.ravel()], axis=1)
    valid_fits = np.isfinite(features).all(axis=1)
    X = features[valid_fits]
    if len(X) < 2:
        raise RuntimeError("Fewer than two valid fits; inspect fit status and bounds.")
    gmm = GaussianMixture(n_components=2, covariance_type="full", reg_covar=1e-6,
                          random_state=random_seed, max_iter=500)
    gmm.fit(X)  # Original method uses unstandardized (A, k, t0).
    labels = np.full(height * width, -1, dtype=np.int8)
    labels[valid_fits] = gmm.predict(X)
    label_map = labels.reshape(height, width)
    output_folder.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_folder / "parameter_maps.npz", A_map=A_map, k_map=k_map,
        t0_map=t0_map, B_map=B_map, rmse_map=rmse_map, label_map=label_map,
        fit_status=fit_status, valid_counts=valid_counts, fit_time_s=time_seconds,
        gmm_means=gmm.means_, gmm_covariances=gmm.covariances_, gmm_weights=gmm.weights_)

    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.titlesize": title_font_size,
                         "axes.labelsize": axis_font_size, "xtick.labelsize": axis_font_size,
                         "ytick.labelsize": axis_font_size, "font.size": annotation_font_size,
                         "legend.fontsize": annotation_font_size, "svg.fonttype": "none"})
    fig, axes = plt.subplots(2, 3, figsize=(figure_width_cm / 2.54, figure_height_cm / 2.54),
                             layout="constrained", dpi=100)
    titles = ["Amplitude A", "Rate coefficient k", "Inflection time t₀",
              "Lower asymptote B", "Fit RMSE", "GMM clusters"]
    units = ["°C", "s⁻¹", "s", "°C", "°C"]
    for index, axis in enumerate(axes.flat):
        axis.set_title(titles[index], pad=6)
        axis.set_axis_off()
        if index < 5:
            cmap = plt.get_cmap("inferno" if index < 4 else "viridis").copy()
            cmap.set_bad("#eeeeee")
            artist = axis.imshow(np.ma.masked_invalid(maps[index]), origin="upper",
                                 cmap=cmap, interpolation="nearest")
            colorbar = fig.colorbar(artist, ax=axis, fraction=0.08, pad=0.03)
            colorbar.set_label(units[index], fontsize=axis_font_size, labelpad=3)
            colorbar.ax.tick_params(labelsize=annotation_font_size)
        else:
            cmap = ListedColormap(["#D55E00", "#0072B2"])
            cmap.set_bad("#eeeeee")
            artist = axis.imshow(np.ma.masked_where(label_map < 0, label_map), origin="upper",
                                 cmap=cmap, norm=BoundaryNorm([-0.5, 0.5, 1.5], 2),
                                 interpolation="nearest")
            colorbar = fig.colorbar(artist, ax=axis, fraction=0.08, pad=0.03, ticks=[0, 1])
            colorbar.ax.set_yticklabels(["0", "1"], fontsize=annotation_font_size)
    fig.savefig(output_folder / "parameter_maps.png", dpi=export_dpi, facecolor="white")
    fig.savefig(output_folder / "parameter_maps.svg", facecolor="white")
    plt.close(fig)

    report = {
        "input": input_path.name, "source_frame_range_end_exclusive": [start_idx, end_idx],
        "fps": fps, "fit_time_origin": "First frame in selected fitting window",
        "temperature_unit": "degree Celsius", "denoising_enabled": use_denoise,
        "denoising": {"method": "per-frame positive-pixel min-max to uint8; OpenCV NLM; inverse scaling",
                      "h": denoise_h, "template_window": template_window, "search_window": search_window},
        "bounds_lower_A_k_t0_B": lower_bounds,
        "bounds_upper_A_k_t0_B": [amplitude_upper_bound, rate_upper_bound,
                                   float(time_seconds[-1]), baseline_upper_bound],
        "missing_input_samples": missing_before_processing,
        "fit_status_codes": {"0": "success", "1": "fewer than five valid samples", "2": "fit failed"},
        "fit_status_counts": {str(code): int(np.count_nonzero(fit_status == code)) for code in [0, 1, 2]},
        "GMM_features": ["A", "k", "t0"], "feature_standardization": False,
        "random_seed": random_seed, "GMM_converged": bool(gmm.converged_),
        "GMM_means_A_k_t0": gmm.means_.tolist(),
        "cluster_labels": "Arbitrary cluster IDs; no independent corrosion truth supplied",
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "scipy": scipy.__version__, "scikit-learn": sklearn.__version__,
                     "opencv": cv2.__version__, "joblib": joblib.__version__,
                     "matplotlib": matplotlib.__version__}}
    (output_folder / "run_summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Saved:", output_folder, flush=True)
    print("Fit status:", report["fit_status_counts"], "GMM converged:", gmm.converged_, flush=True)
