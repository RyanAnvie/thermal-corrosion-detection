"""Extract the first 151 recorded frames without changing measured values."""

from pathlib import Path
import hashlib
import json
import zipfile

import numpy as np

root = Path(__file__).resolve().parents[1]
input_path = root / "data/raw/cropped_images.npz"
output_path = root / "outputs/extracted/early_heating.npz"
source_key = "cropped_images"
first_frame, end_frame = 0, 151  # End is exclusive.

if not input_path.is_file():
    raise FileNotFoundError("Place the full recording at data/raw/cropped_images.npz or edit input_path.")
if output_path.exists():
    raise FileExistsError("Choose a new output_path to preserve the existing extraction.")

with zipfile.ZipFile(input_path) as archive:
    entry = archive.getinfo(source_key + ".npy")
    with archive.open(entry) as member:
        version = np.lib.format.read_magic(member)
        if version == (1, 0):
            shape, fortran_order, dtype = np.lib.format.read_array_header_1_0(member)
        elif version == (2, 0):
            shape, fortran_order, dtype = np.lib.format.read_array_header_2_0(member)
        else:
            raise ValueError("Unsupported NPY header version.")
        array_header_bytes = member.tell()
    if entry.compress_type == zipfile.ZIP_STORED:
        # The original archive is uncompressed: memory-map instead of loading 2.7 GB.
        with input_path.open("rb") as stream:
            stream.seek(entry.header_offset + 26)
            lengths = np.frombuffer(stream.read(4), dtype="<u2")
        offset = entry.header_offset + 30 + int(lengths.sum()) + array_header_bytes
        recording = np.memmap(input_path, mode="r", dtype=dtype, shape=shape,
                              offset=offset, order="F" if fortran_order else "C")
    else:
        # Compressed NPZ members require decompression into memory.
        with np.load(input_path, allow_pickle=False) as saved:
            recording = saved[source_key]
    if end_frame > len(recording):
        raise ValueError("Input recording is shorter than the selected frame range.")
    sample = np.array(recording[first_frame:end_frame], copy=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, **{source_key: sample})
    with np.load(output_path, allow_pickle=False) as saved:
        if not np.array_equal(saved[source_key], sample, equal_nan=True):
            raise RuntimeError("Lossless extraction verification failed.")
    metadata = {"source_filename": input_path.name, "source_key": source_key,
                "source_member_crc32": entry.CRC, "source_shape": list(shape),
                "frame_range_end_exclusive": [first_frame, end_frame],
                "sample_shape": list(sample.shape), "dtype": str(sample.dtype),
                "array_sha256": hashlib.sha256(sample.tobytes()).hexdigest(),
                "processing": "Lossless subset only; no filtering, rescaling, or unit conversion"}
output_path.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print("Saved:", output_path)
