from PIL import Image

from photodate_wm.render import draw_text_watermark


def test_draw_text_positions(tmp_path):
	img = Image.new("RGB", (200, 100), color=(10, 10, 10))
	for pos in ["tl","tc","tr","cl","cc","cr","bl","bc","br"]:
		out = draw_text_watermark(img, "2024-01-02", font_size=20, color="#FFFFFF", opacity=1.0, position=pos, margin_x=10, margin_y=10)
		# Basic sanity: output size equals input size, and mode ok for saving as JPEG
		assert out.size == img.size
		assert out.mode in ("RGB", "RGBA")




