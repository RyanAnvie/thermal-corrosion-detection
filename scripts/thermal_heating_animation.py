"""Recreate the early-heating animation from the included, unfiltered sample."""

from pathlib import Path
import csv
import json
import shutil
import subprocess

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
from matplotlib.patches import Rectangle

root = Path(__file__).resolve().parents[1]
input_path = root / "data/early_heating.npz"
output_folder = root / "outputs/animation"
manual_roi_top_left = ((26, 349), (97, 399))  # (x, y); origin at upper left.
size = 16
display_end_seconds = 2.5
acquisition_fps = 60.0
playback_speed = 0.25
video_fps = 30
end_hold_seconds = 1.5
curve_temperature_limits = (25.80, 26.45)
color_min, color_max = 25.0, 28.0
figure_width_cm, figure_height_cm = 16.0, 9.0
title_font_size, axis_font_size, annotation_font_size = 13, 10, 9
static_dpi = 600
video_dpi = 304.8  # 1920 x 1080 pixels.
gif_width, gif_fps = 960, 12
temperature_scale, temperature_offset = 1.0, 0.0  # Input is already in Celsius.
ignore_value, ignore_tolerance = 0.0, 1e-12
corroded_color, reference_color, outline_color = "#008C9E", "#AC4268", "#00DBE9"
use_local_rois = True  # This standalone demo uses the two fixed rectangles.

ffmpeg_path = shutil.which("ffmpeg")
ffprobe_path = shutil.which("ffprobe")
if ffmpeg_path is None or ffprobe_path is None:
    raise RuntimeError("Install FFmpeg and place ffmpeg and ffprobe on PATH.")
output_folder.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({
    "font.family": "DejaVu Sans", "axes.titlesize": title_font_size,
    "axes.labelsize": axis_font_size, "xtick.labelsize": axis_font_size,
    "ytick.labelsize": axis_font_size, "legend.fontsize": annotation_font_size,
    "font.size": annotation_font_size, "axes.linewidth": 0.7,
    "animation.ffmpeg_path": ffmpeg_path, "svg.fonttype": "none"})
with np.load(input_path, allow_pickle=False) as saved:
    recording = saved["cropped_images"]
with np.load(root / "data/roi_masks.npz", allow_pickle=False) as saved:
    analysis_mask = saved["analysis_mask"]
    corroded_mask = saved["corroded_mask"]
    reference_mask = saved["reference_mask"]
time_seconds = np.arange(len(recording), dtype=np.float64) / acquisition_fps
display_end_index = int(round(display_end_seconds * acquisition_fps))
if display_end_index >= len(recording):
    raise ValueError("Input is shorter than the configured display duration.")
corroded_column, corroded_row = manual_roi_top_left[0]
reference_column, reference_row = manual_roi_top_left[1]
curves = []
valid_pixel_counts = []
for column, row in manual_roi_top_left:
    values = recording[:, row:row + size, column:column + size].astype(np.float64)
    if values.shape[1:] != (size, size):
        raise ValueError("An ROI falls outside the image.")
    valid = np.isfinite(values) & ~np.isclose(values, ignore_value, atol=ignore_tolerance, rtol=0)
    counts = valid.sum(axis=(1, 2))
    sums = np.where(valid, values, 0.0).sum(axis=(1, 2))
    mean = np.full(len(recording), np.nan)
    np.divide(sums, counts, out=mean, where=counts > 0)
    curves.append(mean)
    valid_pixel_counts.append(counts)
corroded_temperature, reference_temperature = curves
with (output_folder / "regional_temperature_curves.csv").open("w", newline="", encoding="utf-8") as stream:
    writer = csv.writer(stream)
    writer.writerow(["source_frame", "recording_time_s", "corroded_temperature_C",
                     "non_corroded_temperature_C", "corroded_valid_pixels", "reference_valid_pixels"])
    for index in range(display_end_index + 1):
        writer.writerow([index, time_seconds[index], curves[0][index], curves[1][index],
                         valid_pixel_counts[0][index], valid_pixel_counts[1][index]])
curve_min, curve_max = curve_temperature_limits
plot_end_seconds = display_end_seconds

fig = plt.figure(figsize=(figure_width_cm / 2.54, figure_height_cm / 2.54), dpi=video_dpi)
fig.set_facecolor("white")
fig.text(0.05, 0.95, "Heating of coated specimen", fontsize=title_font_size, va="center")
time_text = fig.text(0.97, 0.95, "", fontsize=axis_font_size, ha="right", va="center")
thermal_axis = fig.add_axes([0.055, 0.20, 0.255, 0.61])
curve_axis = fig.add_axes([0.50, 0.23, 0.47, 0.58])
color_axis = fig.add_axes([0.275, 0.25, 0.014, 0.50])

thermal_cmap = plt.get_cmap("inferno").copy()
thermal_cmap.set_bad("#EEEEEE")
thermal_image = thermal_axis.imshow(np.ma.masked_where(~analysis_mask, recording[0]),
                                    origin="upper", cmap=thermal_cmap,
                                    vmin=color_min, vmax=color_max, interpolation="nearest")
if use_local_rois:
    for column, row, color, label, line_style in [(corroded_column, corroded_row, outline_color, "A", "-"),
                                                  (reference_column, reference_row, "#FF80B0", "B", "--")]:
        thermal_axis.add_patch(Rectangle((column - 0.5, row - 0.5), size, size,
                                         facecolor="none", edgecolor=color,
                                         linewidth=1.0, linestyle=line_style))
        thermal_axis.text(column + size / 2, row - 9, label, ha="center", va="bottom",
                          color=color, fontsize=annotation_font_size, fontweight="bold",
                          bbox={"facecolor": "#181818", "alpha": 0.85, "edgecolor": "none", "pad": 1})
else:
    thermal_axis.contour(corroded_mask.astype(float), levels=[0.5], colors=[outline_color], linewidths=0.4)
thermal_axis.set_title("Thermal image", pad=9)
thermal_axis.set_axis_off()
colorbar = fig.colorbar(thermal_image, cax=color_axis)
colorbar.set_label("Temperature (°C)", labelpad=5)
color_tick_step = 0.5 if color_max - color_min <= 3.0 else 2.0
colorbar.set_ticks(np.arange(color_min, color_max + 0.1, color_tick_step))
colorbar.outline.set_linewidth(0.5)
thermal_caption = "A / B: selected local ROIs" if use_local_rois else "Cyan outline: corroded ROI"
fig.text(0.1825, 0.125, thermal_caption, ha="center", fontsize=annotation_font_size)

curve_axis.set_title("Regional heating curves", pad=9)
curve_axis.set_xlabel("Recording time (s)", labelpad=4)
curve_axis.set_ylabel("Mean temperature (°C)", labelpad=5)
curve_axis.set_xlim(0, plot_end_seconds * 1.02)
curve_axis.set_ylim(curve_min - 0.15, curve_max + 0.15)
if curve_temperature_limits is not None:
    curve_axis.set_ylim(*curve_temperature_limits)
    curve_axis.set_yticks([25.8, 26.0, 26.2, 26.4])
curve_axis.set_xticks(np.linspace(0, plot_end_seconds, 6))
curve_axis.grid(True, color="#DDE2E6", linewidth=0.5)
curve_axis.spines["top"].set_visible(False)
curve_axis.spines["right"].set_visible(False)
corroded_label = "A: Corroded ROI" if use_local_rois else "Corroded region"
reference_label = "B: Non-corroded ROI" if use_local_rois else "Non-corroded reference"
corroded_line, = curve_axis.plot([], [], color=corroded_color, linewidth=1.5, label=corroded_label)
reference_line, = curve_axis.plot([], [], color=reference_color, linewidth=1.35,
                                 linestyle="--", label=reference_label)
corroded_marker, = curve_axis.plot([], [], "o", color=corroded_color, markersize=4, markeredgewidth=0)
reference_marker, = curve_axis.plot([], [], "o", color=reference_color, markersize=4, markeredgewidth=0)
cursor = curve_axis.axvline(0, color="#82909C", linewidth=0.7, linestyle=":")
curve_axis.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="none",
                  framealpha=0.95, handlelength=1.8, borderpad=0.2)
corroded_readout = fig.text(0.50, 0.075, "", color=corroded_color, fontsize=annotation_font_size)
reference_readout = fig.text(0.97, 0.075, "", color=reference_color,
                             fontsize=annotation_font_size, ha="right")
footer = "Paper-defined thermal ROIs; reference matched by vertical position."
if use_local_rois:
    footer = f"Selected high-contrast example: two {size} × {size} px ROIs at the same height."
    if manual_roi_top_left is not None:
        footer = f"User-selected {size} × {size} px ROIs: A moved up 50 px; B moved left 16 px."
    difference_text = curve_axis.text(0.04, 0.76, "", transform=curve_axis.transAxes,
                                      fontsize=annotation_font_size,
                                      bbox={"facecolor": "white", "alpha": 0.95, "edgecolor": "none"})
    if display_end_seconds is not None:
        footer = f"First {display_end_seconds:g} s; fixed {size} × {size} px ROIs; raw regional means."
        difference_text.set_position((0.96, 0.40))
        difference_text.set_horizontalalignment("right")
fig.text(0.05, 0.02, footer,
         fontsize=annotation_font_size, color="#56616B")


def update_frame(source_index):
    image = recording[source_index].astype(float)
    image = image * temperature_scale + temperature_offset
    image_valid = analysis_mask & np.isfinite(image)
    image_valid &= ~np.isclose(image, ignore_value, atol=ignore_tolerance, rtol=0)
    thermal_image.set_data(np.ma.masked_where(~image_valid, image))
    end = source_index + 1
    corroded_line.set_data(time_seconds[:end], corroded_temperature[:end])
    reference_line.set_data(time_seconds[:end], reference_temperature[:end])
    current_time = time_seconds[source_index]
    corroded_marker.set_data([current_time], [corroded_temperature[source_index]])
    reference_marker.set_data([current_time], [reference_temperature[source_index]])
    cursor.set_xdata([current_time, current_time])
    time_text.set_text(f"t = {current_time:6.2f} s   |   {playback_speed:g}× speed")
    corroded_readout.set_text(f"Corroded: {corroded_temperature[source_index]:.2f} °C")
    reference_readout.set_text(f"Reference: {reference_temperature[source_index]:.2f} °C")
    if use_local_rois:
        difference = corroded_temperature[source_index] - reference_temperature[source_index]
        difference_text.set_text(f"A − B = {difference:.2f} °C")


# Agg has no interactive window. The baseline dimensions and typography are
# constant throughout rendering, independently of the video export resolution.
for name, index in [("start", 0), ("middle", display_end_index // 2), ("final", display_end_index)]:
    update_frame(index)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    if color_axis.yaxis.label.get_window_extent(renderer).overlaps(
            curve_axis.yaxis.label.get_window_extent(renderer)):
        raise RuntimeError("The colorbar and curve temperature labels overlap.")
    x_label_bounds = curve_axis.xaxis.label.get_window_extent(renderer)
    for readout in [corroded_readout, reference_readout]:
        if x_label_bounds.overlaps(readout.get_window_extent(renderer)):
            raise RuntimeError("The time-axis label overlaps a temperature readout.")
    fig.savefig(output_folder / f"thermal_heating_{name}.png", dpi=static_dpi, facecolor="white")
fig.savefig(output_folder / "thermal_heating_final.svg", facecolor="white")
print("Saved the three still previews.", flush=True)

source_step = acquisition_fps * playback_speed / video_fps
# Repeated source indices implement slow motion without interpolating measurements.
display_indices = np.floor(np.arange(0, display_end_index, source_step) + 1e-9).astype(int)
display_indices = np.append(display_indices, display_end_index)
hold_frames = int(round(end_hold_seconds * video_fps))
output_stem = "thermal_heating_local_rois" if use_local_rois else "thermal_heating_comparison"
if use_local_rois and manual_roi_top_left is not None:
    output_stem = "thermal_heating_local_rois_shifted"
if display_end_seconds is not None:
    output_stem = "thermal_heating_first_2p5s_slow"
video_path = output_folder / (output_stem + ".mp4")
writer = FFMpegWriter(fps=video_fps, codec="libx264",
                     extra_args=["-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
with writer.saving(fig, str(video_path), dpi=video_dpi):
    for video_index, source_index in enumerate(display_indices):
        update_frame(int(source_index))
        writer.grab_frame(facecolor="white")
        if video_index % 90 == 0:
            print(f"Rendered video: {video_index + 1}/{len(display_indices)} frames", flush=True)
    for index in range(hold_frames):
        writer.grab_frame(facecolor="white")
plt.close(fig)

gif_path = output_folder / (output_stem + ".gif")
gif_filter = (f"fps={gif_fps},scale={gif_width}:-1:flags=lanczos,split[s0][s1];"
              "[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=sierra2_4a")
subprocess.run([ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_path),
                "-filter_complex", gif_filter, "-loop", "0", str(gif_path)], check=True)
probe = subprocess.run([ffprobe_path, "-v", "error", "-count_frames", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames,duration",
                        "-of", "json", str(video_path)], check=True, capture_output=True, text=True)
video_info = json.loads(probe.stdout)["streams"][0]
if int(video_info["nb_read_frames"]) != len(display_indices) + hold_frames:
    raise RuntimeError("Encoded frame count differs from the expected animation length.")

metadata = {
    "input": input_path.name, "source_frame_range_inclusive": [0, display_end_index],
    "fps": acquisition_fps, "playback_speed": playback_speed,
    "roi_top_left_xy": manual_roi_top_left, "roi_size_pixels": size,
    "time_origin": "First recorded frame, not a verified heater trigger",
    "temperature_unit": "degree Celsius", "curve_limits_C": curve_temperature_limits,
    "thermal_limits_C": [color_min, color_max],
    "processing": "Ordinary spatial means; omit nonfinite and zero-sentinel pixels; save counts; no temporal smoothing or interpolation",
    "labels": "Selected thermal regions; independent corrosion truth is unverified",
    "source_frame_for_each_video_frame": display_indices.tolist() + [display_end_index] * hold_frames,
    "encoded_video": video_info, "video_size_bytes": video_path.stat().st_size}
(output_folder / "animation_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print("Saved:", video_path, flush=True)
