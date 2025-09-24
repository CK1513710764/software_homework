from __future__ import annotations

import os
from typing import Tuple

from PIL import Image, ImageColor, ImageDraw, ImageFont


def _load_font(font_path: str | None, font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
	if font_path:
		try:
			return ImageFont.truetype(font_path, font_size)
		except Exception:
			pass
	# Try common default
	for candidate in ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf"]:
		try:
			return ImageFont.truetype(candidate, font_size)
		except Exception:
			continue
	return ImageFont.load_default()


def _parse_rgba(color: str, opacity: float) -> Tuple[int, int, int, int]:
	# Pillow handles #RRGGBB, names, and #RRGGBBAA in RGBA mode
	r, g, b, a = ImageColor.getcolor(color, "RGBA")
	if a == 255:
		# Apply opacity only when alpha not provided explicitly in color
		alpha = max(0, min(255, int(round(opacity * 255))))
		return r, g, b, alpha
	return r, g, b, a


def _compute_anchor_xy(img_w: int, img_h: int, text_w: int, text_h: int, position: str, margin_x: int, margin_y: int) -> Tuple[int, int]:
	pos = position.lower()
	if pos not in {"tl","tc","tr","cl","cc","cr","bl","bc","br"}:
		raise ValueError(f"Invalid position: {position}")

	if pos[1] == "l":
		x = margin_x
	elif pos[1] == "c":
		x = (img_w - text_w) // 2
	else:  # 'r'
		x = img_w - text_w - margin_x

	if pos[0] == "t":
		y = margin_y
	elif pos[0] == "c":
		y = (img_h - text_h) // 2
	else:  # 'b'
		y = img_h - text_h - margin_y

	return max(0, x), max(0, y)


def draw_text_watermark(image: Image.Image, text: str, font_size: int = 32, color: str = "#FFFFFF", opacity: float = 1.0,
						  position: str = "br", margin_x: int = 24, margin_y: int = 24, font_path: str | None = None) -> Image.Image:
	base_mode = image.mode
	img_rgba = image.convert("RGBA")
	overlay = Image.new("RGBA", img_rgba.size, (0, 0, 0, 0))
	draw = ImageDraw.Draw(overlay)
	font = _load_font(font_path, font_size)

	# Measure text
	bbox = draw.textbbox((0, 0), text, font=font)
	text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
	x, y = _compute_anchor_xy(img_rgba.width, img_rgba.height, text_w, text_h, position, margin_x, margin_y)

	r, g, b, a = _parse_rgba(color, opacity)
	draw.text((x, y), text, font=font, fill=(r, g, b, a))

	composited = Image.alpha_composite(img_rgba, overlay)
	if base_mode == "RGBA":
		return composited
	# For formats like JPEG, convert back to RGB
	return composited.convert("RGB")


