import os
from datetime import datetime

import piexif
from PIL import Image

from photodate_wm.exif_utils import extract_photo_date_string


def _create_temp_jpeg_with_exif(path: str, dt_str: str) -> None:
	img = Image.new("RGB", (10, 10), color=(255, 0, 0))
	img.save(path, format="JPEG")
	exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
	exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_str.encode("utf-8")
	exif_bytes = piexif.dump(exif_dict)
	piexif.insert(exif_bytes, path)


def test_extracts_date_from_exif(tmp_path):
	file_path = tmp_path / "exif.jpg"
	_create_temp_jpeg_with_exif(str(file_path), "2023:08:15 12:34:56")
	assert extract_photo_date_string(str(file_path), fallback_mtime=False, exif_only=True) == "2023-08-15"


def test_fallback_to_mtime_when_no_exif(tmp_path):
	file_path = tmp_path / "noexif.jpg"
	# Create simple jpeg without exif
	Image.new("RGB", (10, 10), color=(0, 255, 0)).save(file_path, format="JPEG")
	# Set mtime to a known value
	known_ts = datetime(2022, 1, 2, 3, 4, 5).timestamp()
	os.utime(file_path, (known_ts, known_ts))
	assert extract_photo_date_string(str(file_path), fallback_mtime=True, exif_only=False) == "2022-01-02"


def test_returns_none_when_exif_only_and_no_exif(tmp_path):
	file_path = tmp_path / "noexif2.jpg"
	Image.new("RGB", (10, 10)).save(file_path, format="JPEG")
	assert extract_photo_date_string(str(file_path), fallback_mtime=True, exif_only=True) is None




