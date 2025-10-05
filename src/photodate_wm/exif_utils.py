from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import piexif


def _parse_exif_datetime_string(dt_str: str) -> Optional[datetime]:
	# Expected EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
	try:
		return datetime.strptime(dt_str.strip(), "%Y:%m:%d %H:%M:%S")
	except Exception:
		return None


def _read_exif_datetime_bytes(image_path: str) -> Optional[str]:
	try:
		exif_dict = piexif.load(image_path)
	except Exception:
		return None

	# Priority: DateTimeOriginal -> DateTimeDigitized (CreateDate) -> DateTime
	try_order = [
		(lambda d: d.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)),
		(lambda d: d.get("Exif", {}).get(piexif.ExifIFD.DateTimeDigitized)),
		(lambda d: d.get("0th", {}).get(piexif.ImageIFD.DateTime)),
	]
	for getter in try_order:
		val = getter(exif_dict)
		if isinstance(val, bytes):
			try:
				return val.decode("utf-8", errors="ignore")
			except Exception:
				continue
		elif isinstance(val, str):
			return val
	return None


def extract_photo_date_string(image_path: str, fallback_mtime: bool = True, exif_only: bool = False) -> Optional[str]:
	"""Extract shooting date as YYYY-MM-DD string.

	Returns None when no date can be determined AND exif_only is True.
	When exif_only is False, falls back to file mtime if fallback_mtime is True.
	"""
	# 1) Try EXIF
	exif_dt_raw = _read_exif_datetime_bytes(image_path)
	if exif_dt_raw:
		dt = _parse_exif_datetime_string(exif_dt_raw)
		if dt is not None:
			return dt.strftime("%Y-%m-%d")

	# 2) If only EXIF requested, stop here
	if exif_only:
		return None

	# 3) Fallback to mtime
	if fallback_mtime:
		try:
			mtime = os.path.getmtime(image_path)
			local_dt = datetime.fromtimestamp(mtime)
			return local_dt.strftime("%Y-%m-%d")
		except Exception:
			return None

	return None



