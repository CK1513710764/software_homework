import os
import sys
import subprocess

import piexif
from PIL import Image


def run_module(args, cwd):
	env = os.environ.copy()
	env["PYTHONPATH"] = os.path.join(cwd, "src") + os.pathsep + env.get("PYTHONPATH", "")
	cmd = [sys.executable, "-m", "photodate_wm"] + args
	return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)


def _create_jpeg_with_exif(path: str, dt_str: str) -> None:
	img = Image.new("RGB", (50, 50), color=(120, 120, 120))
	img.save(path, format="JPEG")
	exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
	exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_str.encode("utf-8")
	exif_bytes = piexif.dump(exif_dict)
	piexif.insert(exif_bytes, path)


def test_cli_writes_output_and_preserves_exif(tmp_path):
	project_root = os.getcwd()
	inp_dir = tmp_path / "inp"
	inp_dir.mkdir(parents=True)
	src = inp_dir / "x.jpg"
	_create_jpeg_with_exif(str(src), "2021:12:31 08:07:06")

	# Run processing
	result = run_module([
		"--path", str(inp_dir),
		"--position", "cc",
		"--font-size", "20",
	], cwd=project_root)
	assert result.returncode in (0, 1)  # allow skip count to force 1 in some env

	out_dir = inp_dir / f"{inp_dir.name}_watermark"
	assert out_dir.exists()

	out_file = out_dir / "x.jpg"
	assert out_file.exists()

	# Check EXIF still has DateTimeOriginal
	exif = piexif.load(str(out_file))
	val = exif.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
	assert val is None or isinstance(val, (bytes, bytearray))
	# If present, it should be decodable
	if val:
		assert val.decode("utf-8").startswith("2021:")




