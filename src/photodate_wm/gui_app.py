from __future__ import annotations

import os
import sys
import json
import threading
import json
from dataclasses import dataclass
from typing import List, Optional

from PIL import Image, ImageTk

try:
	# optional drag & drop support
	from tkinterdnd2 import DND_FILES, TkinterDnD
	import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
	except_import = None
except Exception as e:
	except_import = e
	import tkinter as tk
	from tkinter import ttk, filedialog, messagebox

from .cli import SUPPORTED_EXTENSIONS
from .exif_utils import extract_photo_date_string
from .render import draw_text_watermark, draw_image_watermark


SUPPORTED_INPUT_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
OUTPUT_FORMATS = ["JPEG", "PNG"]


@dataclass
class Item:
	path: str
	thumb: Optional[ImageTk.PhotoImage]
	label: str


class App:
	def __init__(self, root: tk.Tk):
		self.root = root
		self.root.title("Photo Date Watermark")

		self.items: List[Item] = []
		self.output_dir_var = tk.StringVar(value="")
		self.prefix_var = tk.StringVar(value="")
		self.suffix_var = tk.StringVar(value="_watermarked")
		self.format_var = tk.StringVar(value="JPEG")
		self.jpeg_quality_var = tk.IntVar(value=95)
		self.resize_mode_var = tk.StringVar(value="none")  # none|width|height|percent
		self.resize_value_var = tk.IntVar(value=100)

		self.position_var = tk.StringVar(value="br")
		self.font_size_var = tk.IntVar(value=32)
		self.color_var = tk.StringVar(value="#FFFFFF")
		self.opacity_var = tk.DoubleVar(value=1.0)
		self.font_path_var = tk.StringVar(value="")
		self.margin_x_var = tk.IntVar(value=24)
		self.margin_y_var = tk.IntVar(value=24)
		# text advanced
		self.stroke_width_var = tk.IntVar(value=0)
		self.stroke_color_var = tk.StringVar(value="#000000")
		self.shadow_dx_var = tk.IntVar(value=0)
		self.shadow_dy_var = tk.IntVar(value=0)
		self.shadow_color_var = tk.StringVar(value="#000000")
		self.shadow_opacity_var = tk.DoubleVar(value=0.5)

		# watermark type
		self.wm_type_var = tk.StringVar(value="date")  # date|text|image
		self.custom_text_var = tk.StringVar(value="")
		self.image_wm_path_var = tk.StringVar(value="")
		self.image_wm_scale_var = tk.IntVar(value=20)
		self.exif_only_var = tk.BooleanVar(value=False)
		self.fallback_mtime_var = tk.BooleanVar(value=True)

		self._build_ui()
		self._setup_dnd()
		self._cancel = False
		# load last settings on start
		try:
			self._load_last_settings()
		except Exception:
			pass
		self.root.protocol("WM_DELETE_WINDOW", self._on_close)
		# load last settings if available
		try:
			cfg = self._load_config()
			last = cfg.get("last_settings")
			if isinstance(last, dict):
				self._apply_settings(last)
		except Exception:
			pass
		self.root.protocol("WM_DELETE_WINDOW", self._on_close)

	def _build_ui(self):
		frm = ttk.Frame(self.root)
		frm.pack(fill=tk.BOTH, expand=True)

		# Top controls
		toolbar = ttk.Frame(frm)
		toolbar.pack(fill=tk.X)
		btn_add_files = ttk.Button(toolbar, text="添加图片", command=self.add_files)
		btn_add_dir = ttk.Button(toolbar, text="添加文件夹", command=self.add_folder)
		btn_choose_out = ttk.Button(toolbar, text="选择输出文件夹", command=self.choose_output_dir)
		btn_add_files.pack(side=tk.LEFT, padx=4, pady=4)
		btn_add_dir.pack(side=tk.LEFT, padx=4, pady=4)
		btn_choose_out.pack(side=tk.LEFT, padx=4, pady=4)
		# template management
		btn_save_tpl = ttk.Button(toolbar, text="保存模板", command=self.save_template)
		btn_load_tpl = ttk.Button(toolbar, text="加载模板", command=self.load_template)
		btn_del_tpl = ttk.Button(toolbar, text="删除模板", command=self.delete_template)
		btn_save_tpl.pack(side=tk.LEFT, padx=4, pady=4)
		btn_load_tpl.pack(side=tk.LEFT, padx=4, pady=4)
		btn_del_tpl.pack(side=tk.LEFT, padx=4, pady=4)
		# template buttons
		btn_save_tpl = ttk.Button(toolbar, text="保存模板", command=self.save_template)
		btn_load_tpl = ttk.Button(toolbar, text="加载模板", command=self.load_template)
		btn_mng_tpl = ttk.Button(toolbar, text="管理模板", command=self.manage_templates)
		btn_save_tpl.pack(side=tk.RIGHT, padx=4, pady=4)
		btn_load_tpl.pack(side=tk.RIGHT, padx=4, pady=4)
		btn_mng_tpl.pack(side=tk.RIGHT, padx=4, pady=4)

		# Preview canvas
		preview_frame = ttk.LabelFrame(frm, text="预览")
		preview_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
		self.preview_canvas = tk.Canvas(preview_frame, bg="#333333", height=320)
		self.preview_canvas.pack(fill=tk.BOTH, expand=True)
		self.preview_img_tk = None
		self.preview_origin = (0, 0)
		self._dragging = False
		self._drag_offset = (0, 0)

		# List area
		self.listbox = tk.Listbox(frm, height=10)
		self.listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
		self.listbox.bind("<<ListboxSelect>>", self.on_select_item)

		# Options (scrollable)
		opts_container = ttk.LabelFrame(frm, text="参数")
		opts_container.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
		canvas = tk.Canvas(opts_container, highlightthickness=0)
		sb_y = ttk.Scrollbar(opts_container, orient=tk.VERTICAL, command=canvas.yview)
		canvas.configure(yscrollcommand=sb_y.set)
		canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
		sb_y.pack(side=tk.RIGHT, fill=tk.Y)
		opts = ttk.Frame(canvas)
		win_id = canvas.create_window((0, 0), window=opts, anchor="nw")

		def _on_frame_configure(event):
			canvas.configure(scrollregion=canvas.bbox("all"))
		opts.bind("<Configure>", _on_frame_configure)

		def _on_canvas_configure(event):
			# Make inner frame width track canvas width
			canvas.itemconfigure(win_id, width=event.width)
		canvas.bind("<Configure>", _on_canvas_configure)

		# Mouse wheel scrolling
		def _on_mousewheel(event):
			# Windows delta is negative for scroll down
			canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
		canvas.bind_all("<MouseWheel>", _on_mousewheel)

		# grid row counter
		row = 0
		# watermark type selection
		ttk.Label(opts, text="水印类型").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		wm_cb = ttk.Combobox(opts, textvariable=self.wm_type_var, values=["date","text","image"], width=10, state="readonly")
		wm_cb.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		row += 1

		# custom text & image watermark selectors
		ttk.Label(opts, text="自定义文本").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		entry_text = ttk.Entry(opts, textvariable=self.custom_text_var, width=30)
		entry_text.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		row += 1

		ttk.Label(opts, text="图片水印路径").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		entry_img = ttk.Entry(opts, textvariable=self.image_wm_path_var, width=40)
		entry_img.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		btn_img = ttk.Button(opts, text="选择图片", command=self.choose_image_watermark)
		btn_img.grid(row=row, column=2, sticky=tk.W, padx=4, pady=4)
		row += 1

		ttk.Label(opts, text="图片水印比例(%)").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		img_scale = ttk.Scale(opts, from_=1, to=100, orient=tk.HORIZONTAL, variable=self.image_wm_scale_var)
		img_scale.grid(row=row, column=1, sticky=tk.W+tk.E, padx=4, pady=4)
		row += 1

		for label, var, width in [
			("输出文件夹", self.output_dir_var, 60),
			("文件名前缀", self.prefix_var, 20),
			("文件名后缀", self.suffix_var, 20),
			("字体文件", self.font_path_var, 40),
		]:
			ttk.Label(opts, text=label).grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
			entry = ttk.Entry(opts, textvariable=var, width=width)
			entry.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
			row += 1

		# format & quality
		ttk.Label(opts, text="输出格式").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		fmt_cb = ttk.Combobox(opts, textvariable=self.format_var, values=OUTPUT_FORMATS, width=10, state="readonly")
		fmt_cb.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		row += 1

		ttk.Label(opts, text="JPEG质量(0-100)").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		q_scale = ttk.Scale(opts, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.jpeg_quality_var)
		q_scale.grid(row=row, column=1, sticky=tk.W+tk.E, padx=4, pady=4)
		row += 1

		# resize
		ttk.Label(opts, text="调整尺寸").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		resize_modes = ["none","width","height","percent"]
		resize_cb = ttk.Combobox(opts, textvariable=self.resize_mode_var, values=resize_modes, width=10, state="readonly")
		resize_cb.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		row += 1

		ttk.Label(opts, text="尺寸值").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		resize_entry = ttk.Entry(opts, textvariable=self.resize_value_var, width=10)
		resize_entry.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		row += 1

		# watermark style
		ttk.Label(opts, text="位置").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		pos_cb = ttk.Combobox(opts, textvariable=self.position_var, values=["tl","tc","tr","cl","cc","cr","bl","bc","br"], width=10, state="readonly")
		pos_cb.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		row += 1

		# manual position & rotation for advanced control
		ttk.Label(opts, text="手动X,Y").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		self.manual_x_var = tk.IntVar(value=0)
		self.manual_y_var = tk.IntVar(value=0)
		entry_mx = ttk.Entry(opts, textvariable=self.manual_x_var, width=8)
		entry_my = ttk.Entry(opts, textvariable=self.manual_y_var, width=8)
		entry_mx.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		entry_my.grid(row=row, column=2, sticky=tk.W, padx=4, pady=4)
		row += 1

		ttk.Label(opts, text="旋转角度").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		self.rotation_var = tk.IntVar(value=0)
		rot_scale = ttk.Scale(opts, from_=0, to=359, orient=tk.HORIZONTAL, variable=self.rotation_var)
		rot_scale.grid(row=row, column=1, sticky=tk.W+tk.E, padx=4, pady=4)
		row += 1

		for label, var in [("字号", self.font_size_var),("边距X", self.margin_x_var),("边距Y", self.margin_y_var)]:
			ttk.Label(opts, text=label).grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
			entry = ttk.Entry(opts, textvariable=var, width=10)
			entry.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
			row += 1

		for label, var in [("颜色", self.color_var)]:
			ttk.Label(opts, text=label).grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
			entry = ttk.Entry(opts, textvariable=var, width=12)
			entry.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
			row += 1

		for label, var in [("透明度(0-1)", self.opacity_var)]:
			ttk.Label(opts, text=label).grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
			entry = ttk.Entry(opts, textvariable=var, width=10)
			entry.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
			row += 1

		# text advanced styles
		ttk.Label(opts, text="描边宽度").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		stroke_entry = ttk.Entry(opts, textvariable=self.stroke_width_var, width=10)
		stroke_entry.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		row += 1

		ttk.Label(opts, text="描边颜色").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		stroke_color_entry = ttk.Entry(opts, textvariable=self.stroke_color_var, width=12)
		stroke_color_entry.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		row += 1

		ttk.Label(opts, text="阴影偏移dx,dy").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		shadow_dx_entry = ttk.Entry(opts, textvariable=self.shadow_dx_var, width=6)
		shadow_dx_entry.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		shadow_dy_entry = ttk.Entry(opts, textvariable=self.shadow_dy_var, width=6)
		shadow_dy_entry.grid(row=row, column=2, sticky=tk.W, padx=4, pady=4)
		row += 1

		ttk.Label(opts, text="阴影颜色").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		shadow_color_entry = ttk.Entry(opts, textvariable=self.shadow_color_var, width=12)
		shadow_color_entry.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		row += 1

		ttk.Label(opts, text="阴影透明度(0-1)").grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		shadow_opacity_entry = ttk.Entry(opts, textvariable=self.shadow_opacity_var, width=10)
		shadow_opacity_entry.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		row += 1

		# exif-only & fallback
		chk1 = ttk.Checkbutton(opts, text="仅含EXIF日期", variable=self.exif_only_var)
		chk2 = ttk.Checkbutton(opts, text="无EXIF回退到修改时间", variable=self.fallback_mtime_var)
		chk1.grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		chk2.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		row += 1

		controls = ttk.Frame(frm)
		controls.pack(fill=tk.X, padx=6, pady=6)
		self.btn_run = ttk.Button(controls, text="开始处理并导出", command=self.run_export)
		self.btn_run.pack(side=tk.LEFT)
		self.btn_cancel = ttk.Button(controls, text="取消", command=self.cancel_export, state=tk.DISABLED)
		self.btn_cancel.pack(side=tk.LEFT, padx=8)
		self.progress = ttk.Progressbar(controls, mode="determinate")
		self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
		# Preview interactions
		self.preview_canvas.bind("<ButtonPress-1>", self._start_drag)
		self.preview_canvas.bind("<B1-Motion>", self._on_drag)
		self.preview_canvas.bind("<ButtonRelease-1>", self._end_drag)

		# realtime preview traces
		for v in [self.wm_type_var, self.custom_text_var, self.image_wm_path_var,
				self.image_wm_scale_var, self.position_var, self.font_size_var, self.color_var,
				self.opacity_var, self.margin_x_var, self.margin_y_var, self.rotation_var,
				self.stroke_width_var, self.stroke_color_var, self.shadow_dx_var, self.shadow_dy_var,
				self.shadow_color_var, self.shadow_opacity_var, self.manual_x_var, self.manual_y_var]:
			v.trace_add("write", lambda *_: self.update_preview())

	def _setup_dnd(self):
		# optional drag & drop listbox
		if 'TkinterDnD' in globals() and isinstance(self.root, TkinterDnD.Tk):
			self.listbox.drop_target_register(DND_FILES)
			self.listbox.dnd_bind('<<Drop>>', self._on_drop)

	def _on_drop(self, event):
		paths = self.root.splitlist(event.data)
		self._add_paths(paths)

	def add_files(self):
		paths = filedialog.askopenfilenames(title="选择图片", filetypes=[("Images","*.jpg;*.jpeg;*.png;*.bmp;*.tif;*.tiff")])
		if paths:
			self._add_paths(paths)

	def add_folder(self):
		folder = filedialog.askdirectory(title="选择文件夹")
		if folder:
			walked = []
			for dirpath, dirnames, filenames in os.walk(folder):
				for fn in filenames:
					ext = os.path.splitext(fn)[1].lower()
					if ext in SUPPORTED_INPUT_EXTS:
						walked.append(os.path.join(dirpath, fn))
			self._add_paths(walked)

	def choose_output_dir(self):
		path = filedialog.askdirectory(title="选择输出文件夹")
		if path:
			self.output_dir_var.set(path)

	def choose_image_watermark(self):
		path = filedialog.askopenfilename(title="选择图片水印", filetypes=[("PNG","*.png"),("Images","*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff")])
		if path:
			self.image_wm_path_var.set(path)

	def _add_paths(self, paths):
		added = 0
		for p in paths:
			if not os.path.isfile(p):
				continue
			ext = os.path.splitext(p)[1].lower()
			if ext not in SUPPORTED_INPUT_EXTS:
				continue
			try:
				thumb = self._make_thumb(p)
			except Exception:
				thumb = None
			self.items.append(Item(path=p, thumb=thumb, label=os.path.basename(p)))
			self.listbox.insert(tk.END, os.path.basename(p))
			added += 1
		if added == 0:
			messagebox.showinfo("提示", "未添加任何受支持的图片文件。")

	def _make_thumb(self, path: str) -> ImageTk.PhotoImage:
		with Image.open(path) as im:
			im.thumbnail((160, 160))
			return ImageTk.PhotoImage(im.copy())

	def _load_preview_image(self) -> Optional[Image.Image]:
		# Load the currently selected image or first item
		if not self.items:
			return None
		idxs = self.listbox.curselection()
		path = self.items[idxs[0]].path if idxs else self.items[0].path
		try:
			im = Image.open(path)
			return im
		except Exception:
			return None

	def on_select_item(self, _evt=None):
		self.update_preview()

	def update_preview(self):
		im = self._load_preview_image()
		if im is None:
			self.preview_canvas.delete("all")
			return
		# Fit preview to canvas width while keeping aspect ratio
		cw = max(1, self.preview_canvas.winfo_width())
		ch = max(1, self.preview_canvas.winfo_height())
		w, h = im.size
		scale = min(cw / w, ch / h)
		pw, ph = max(1, int(w * scale)), max(1, int(h * scale))
		im_preview = im.resize((pw, ph), Image.LANCZOS)
		self.preview_img_tk = ImageTk.PhotoImage(im_preview)
		self.preview_canvas.delete("all")
		xo = (cw - pw) // 2
		yo = (ch - ph) // 2
		self.preview_origin = (xo, yo)
		self.preview_canvas.create_image(xo, yo, anchor="nw", image=self.preview_img_tk)

		# draw watermark preview
		wm_type = self.wm_type_var.get()
		rotation = int(self.rotation_var.get())
		manual_xy = (int(self.manual_x_var.get()), int(self.manual_y_var.get()))
		margin_x = int(self.margin_x_var.get())
		margin_y = int(self.margin_y_var.get())
		position = self.position_var.get()

		if wm_type in ("date","text"):
			text_to_draw = ""
			if wm_type == "date":
				text_to_draw = "YYYY-MM-DD"
			else:
				text_to_draw = (self.custom_text_var.get() or "").strip() or "示例"
			font_size = int(self.font_size_var.get())
			color = self.color_var.get()
			opacity = float(self.opacity_var.get())
			sw = int(self.stroke_width_var.get())
			sc = self.stroke_color_var.get()
			sdx = int(self.shadow_dx_var.get())
			sdy = int(self.shadow_dy_var.get())
			sc2 = self.shadow_color_var.get()
			so = float(self.shadow_opacity_var.get())

			# Render watermark onto the preview image itself then display
			im_marked = draw_text_watermark(
				im_preview,
				text_to_draw,
				font_size=font_size,
				color=color,
				opacity=opacity,
				position=position,
				margin_x=margin_x,
				margin_y=margin_y,
				font_path=(self.font_path_var.get().strip() or None),
				stroke_width=sw,
				stroke_color=sc,
				shadow_offset=(sdx, sdy),
				shadow_color=sc2,
				shadow_opacity=so,
				rotation_deg=rotation,
				override_xy=manual_xy if position == "manual" else None,
			)
			self.preview_img_tk = ImageTk.PhotoImage(im_marked)
			self.preview_canvas.create_image(xo, yo, anchor="nw", image=self.preview_img_tk)
		else:
			img_path = (self.image_wm_path_var.get() or "").strip()
			if os.path.isfile(img_path):
				try:
					with Image.open(img_path) as wm:
						im_marked = draw_image_watermark(
							im_preview,
							wm,
							scale_percent=int(self.image_wm_scale_var.get()),
							opacity=float(self.opacity_var.get()),
							position=position,
							margin_x=margin_x,
							margin_y=margin_y,
							rotation_deg=rotation,
							override_xy=manual_xy if position == "manual" else None,
						)
						self.preview_img_tk = ImageTk.PhotoImage(im_marked)
						self.preview_canvas.create_image(xo, yo, anchor="nw", image=self.preview_img_tk)
				except Exception:
					pass

	def _canvas_to_image_coords(self, x: int, y: int) -> tuple[int, int]:
		xo, yo = self.preview_origin
		return max(0, x - xo), max(0, y - yo)

	def _start_drag(self, event):
		self._dragging = True
		x, y = self._canvas_to_image_coords(event.x, event.y)
		self.manual_x_var.set(x)
		self.manual_y_var.set(y)

	def _on_drag(self, event):
		if not self._dragging:
			return
		x, y = self._canvas_to_image_coords(event.x, event.y)
		self.manual_x_var.set(x)
		self.manual_y_var.set(y)

	def _end_drag(self, _event):
		self._dragging = False

	# ============ Templates & Settings ============
	def _config_dir(self) -> str:
		base = os.path.join(os.path.expanduser("~"), ".photodate_wm")
		os.makedirs(base, exist_ok=True)
		return base

	def _template_path(self, name: str) -> str:
		name = name.strip() or "default"
		return os.path.join(self._config_dir(), f"{name}.json")

	def _list_templates(self) -> list[str]:
		try:
			files = [f for f in os.listdir(self._config_dir()) if f.endswith(".json")]
			return sorted([os.path.splitext(f)[0] for f in files if f != "last.json"])
		except Exception:
			return []

	def _collect_settings(self) -> dict:
		return {
			"wm_type": self.wm_type_var.get(),
			"custom_text": self.custom_text_var.get(),
			"image_wm_path": self.image_wm_path_var.get(),
			"image_wm_scale": int(self.image_wm_scale_var.get()),
			"output_dir": self.output_dir_var.get(),
			"prefix": self.prefix_var.get(),
			"suffix": self.suffix_var.get(),
			"format": self.format_var.get(),
			"jpeg_quality": int(self.jpeg_quality_var.get()),
			"resize_mode": self.resize_mode_var.get(),
			"resize_value": int(self.resize_value_var.get()),
			"position": self.position_var.get(),
			"manual_x": int(self.manual_x_var.get()) if hasattr(self, "manual_x_var") else 0,
			"manual_y": int(self.manual_y_var.get()) if hasattr(self, "manual_y_var") else 0,
			"rotation": int(self.rotation_var.get()) if hasattr(self, "rotation_var") else 0,
			"font_size": int(self.font_size_var.get()),
			"color": self.color_var.get(),
			"opacity": float(self.opacity_var.get()),
			"font_path": self.font_path_var.get(),
			"margin_x": int(self.margin_x_var.get()),
			"margin_y": int(self.margin_y_var.get()),
			"stroke_width": int(self.stroke_width_var.get()),
			"stroke_color": self.stroke_color_var.get(),
			"shadow_dx": int(self.shadow_dx_var.get()),
			"shadow_dy": int(self.shadow_dy_var.get()),
			"shadow_color": self.shadow_color_var.get(),
			"shadow_opacity": float(self.shadow_opacity_var.get()),
			"exif_only": bool(self.exif_only_var.get()),
			"fallback_mtime": bool(self.fallback_mtime_var.get()),
		}

	def _apply_settings(self, cfg: dict):
		mset = {
			self.wm_type_var: cfg.get("wm_type", self.wm_type_var.get()),
			self.custom_text_var: cfg.get("custom_text", self.custom_text_var.get()),
			self.image_wm_path_var: cfg.get("image_wm_path", self.image_wm_path_var.get()),
			self.output_dir_var: cfg.get("output_dir", self.output_dir_var.get()),
			self.prefix_var: cfg.get("prefix", self.prefix_var.get()),
			self.suffix_var: cfg.get("suffix", self.suffix_var.get()),
			self.format_var: cfg.get("format", self.format_var.get()),
			self.resize_mode_var: cfg.get("resize_mode", self.resize_mode_var.get()),
			self.position_var: cfg.get("position", self.position_var.get()),
			self.color_var: cfg.get("color", self.color_var.get()),
			self.font_path_var: cfg.get("font_path", self.font_path_var.get()),
			self.stroke_color_var: cfg.get("stroke_color", self.stroke_color_var.get()),
			self.shadow_color_var: cfg.get("shadow_color", self.shadow_color_var.get()),
		}
		for var, val in mset.items():
			try:
				var.set(val)
			except Exception:
				pass
		# numeric
		for var, key in [
			(self.image_wm_scale_var, "image_wm_scale"),
			(self.jpeg_quality_var, "jpeg_quality"),
			(self.resize_value_var, "resize_value"),
			(self.manual_x_var, "manual_x"),
			(self.manual_y_var, "manual_y"),
			(self.rotation_var, "rotation"),
			(self.font_size_var, "font_size"),
			(self.opacity_var, "opacity"),
			(self.margin_x_var, "margin_x"),
			(self.margin_y_var, "margin_y"),
			(self.stroke_width_var, "stroke_width"),
			(self.shadow_dx_var, "shadow_dx"),
			(self.shadow_dy_var, "shadow_dy"),
			(self.shadow_opacity_var, "shadow_opacity"),
		]:
			try:
				val = cfg.get(key)
				if val is not None:
					var.set(val)
			except Exception:
				pass
		# bools
		for var, key in [
			(self.exif_only_var, "exif_only"),
			(self.fallback_mtime_var, "fallback_mtime"),
		]:
			try:
				val = cfg.get(key)
				if val is not None:
					var.set(bool(val))
			except Exception:
				pass
		self.update_preview()

	def save_template(self):
		from tkinter import simpledialog
		name = simpledialog.askstring("保存模板", "输入模板名称：", parent=self.root)
		if not name:
			return
		cfg = self._collect_settings()
		path = self._template_path(name)
		try:
			with open(path, "w", encoding="utf-8") as f:
				json.dump(cfg, f, ensure_ascii=False, indent=2)
			messagebox.showinfo("成功", f"已保存模板：{name}")
		except Exception as e:
			messagebox.showerror("错误", f"保存失败：{e}")

	def load_template(self):
		from tkinter import filedialog
		path = filedialog.askopenfilename(title="选择模板", initialdir=self._config_dir(), filetypes=[("JSON","*.json")])
		if not path:
			return
		try:
			with open(path, "r", encoding="utf-8") as f:
				cfg = json.load(f)
			self._apply_settings(cfg)
			messagebox.showinfo("成功", "模板已加载")
		except Exception as e:
			messagebox.showerror("错误", f"加载失败：{e}")

	def delete_template(self):
		from tkinter import filedialog
		path = filedialog.askopenfilename(title="删除模板", initialdir=self._config_dir(), filetypes=[("JSON","*.json")])
		if not path:
			return
		try:
			os.remove(path)
			messagebox.showinfo("成功", "模板已删除")
		except Exception as e:
			messagebox.showerror("错误", f"删除失败：{e}")

	def _save_last_settings(self):
		try:
			cfg = self._collect_settings()
			path = os.path.join(self._config_dir(), "last.json")
			with open(path, "w", encoding="utf-8") as f:
				json.dump(cfg, f, ensure_ascii=False, indent=2)
		except Exception:
			pass

	def _load_last_settings(self):
		path = os.path.join(self._config_dir(), "last.json")
		if not os.path.isfile(path):
			return
		with open(path, "r", encoding="utf-8") as f:
			cfg = json.load(f)
		self._apply_settings(cfg)

	def _on_close(self):
		self._save_last_settings()
		self.root.destroy()

	# ---------- Templates & Config ----------
	def _config_path(self) -> str:
		base = os.path.join(os.path.expanduser("~"), ".photodate_wm")
		os.makedirs(base, exist_ok=True)
		return os.path.join(base, "templates.json")

	def _load_config(self) -> dict:
		path = self._config_path()
		if not os.path.isfile(path):
			return {"templates": {}, "last_settings": None}
		with open(path, "r", encoding="utf-8") as f:
			return json.load(f)

	def _save_config(self, data: dict) -> None:
		path = self._config_path()
		with open(path, "w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)

	def _serialize_settings(self) -> dict:
		return {
			"wm_type": self.wm_type_var.get(),
			"custom_text": self.custom_text_var.get(),
			"image_wm_path": self.image_wm_path_var.get(),
			"image_wm_scale": int(self.image_wm_scale_var.get()),
			"position": self.position_var.get(),
			"manual_x": int(self.manual_x_var.get()) if hasattr(self, "manual_x_var") else 0,
			"manual_y": int(self.manual_y_var.get()) if hasattr(self, "manual_y_var") else 0,
			"rotation": int(self.rotation_var.get()) if hasattr(self, "rotation_var") else 0,
			"font_size": int(self.font_size_var.get()),
			"color": self.color_var.get(),
			"opacity": float(self.opacity_var.get()),
			"stroke_width": int(self.stroke_width_var.get()),
			"stroke_color": self.stroke_color_var.get(),
			"shadow_dx": int(self.shadow_dx_var.get()),
			"shadow_dy": int(self.shadow_dy_var.get()),
			"shadow_color": self.shadow_color_var.get(),
			"shadow_opacity": float(self.shadow_opacity_var.get()),
			"font_path": self.font_path_var.get(),
			"margin_x": int(self.margin_x_var.get()),
			"margin_y": int(self.margin_y_var.get()),
			"exif_only": bool(self.exif_only_var.get()),
			"fallback_mtime": bool(self.fallback_mtime_var.get()),
			"output_dir": self.output_dir_var.get(),
			"prefix": self.prefix_var.get(),
			"suffix": self.suffix_var.get(),
			"format": self.format_var.get(),
			"jpeg_quality": int(self.jpeg_quality_var.get()),
			"resize_mode": self.resize_mode_var.get(),
			"resize_value": int(self.resize_value_var.get()),
		}

	def _apply_settings(self, s: dict) -> None:
		self.wm_type_var.set(s.get("wm_type", self.wm_type_var.get()))
		self.custom_text_var.set(s.get("custom_text", self.custom_text_var.get()))
		self.image_wm_path_var.set(s.get("image_wm_path", self.image_wm_path_var.get()))
		self.image_wm_scale_var.set(s.get("image_wm_scale", self.image_wm_scale_var.get()))
		self.position_var.set(s.get("position", self.position_var.get()))
		if hasattr(self, "manual_x_var"): self.manual_x_var.set(s.get("manual_x", self.manual_x_var.get()))
		if hasattr(self, "manual_y_var"): self.manual_y_var.set(s.get("manual_y", self.manual_y_var.get()))
		if hasattr(self, "rotation_var"): self.rotation_var.set(s.get("rotation", self.rotation_var.get()))
		self.font_size_var.set(s.get("font_size", self.font_size_var.get()))
		self.color_var.set(s.get("color", self.color_var.get()))
		self.opacity_var.set(s.get("opacity", self.opacity_var.get()))
		self.stroke_width_var.set(s.get("stroke_width", self.stroke_width_var.get()))
		self.stroke_color_var.set(s.get("stroke_color", self.stroke_color_var.get()))
		self.shadow_dx_var.set(s.get("shadow_dx", self.shadow_dx_var.get()))
		self.shadow_dy_var.set(s.get("shadow_dy", self.shadow_dy_var.get()))
		self.shadow_color_var.set(s.get("shadow_color", self.shadow_color_var.get()))
		self.shadow_opacity_var.set(s.get("shadow_opacity", self.shadow_opacity_var.get()))
		self.font_path_var.set(s.get("font_path", self.font_path_var.get()))
		self.margin_x_var.set(s.get("margin_x", self.margin_x_var.get()))
		self.margin_y_var.set(s.get("margin_y", self.margin_y_var.get()))
		self.exif_only_var.set(s.get("exif_only", self.exif_only_var.get()))
		self.fallback_mtime_var.set(s.get("fallback_mtime", self.fallback_mtime_var.get()))
		self.output_dir_var.set(s.get("output_dir", self.output_dir_var.get()))
		self.prefix_var.set(s.get("prefix", self.prefix_var.get()))
		self.suffix_var.set(s.get("suffix", self.suffix_var.get()))
		self.format_var.set(s.get("format", self.format_var.get()))
		self.jpeg_quality_var.set(s.get("jpeg_quality", self.jpeg_quality_var.get()))
		self.resize_mode_var.set(s.get("resize_mode", self.resize_mode_var.get()))
		self.resize_value_var.set(s.get("resize_value", self.resize_value_var.get()))
		self.update_preview()

	def save_template(self):
		name = simpledialog.askstring("保存模板", "输入模板名称：", parent=self.root)
		if not name:
			return
		cfg = self._load_config()
		cfg.setdefault("templates", {})[name] = self._serialize_settings()
		cfg["last_settings"] = cfg["templates"][name]
		self._save_config(cfg)
		messagebox.showinfo("提示", f"已保存模板：{name}")

	def load_template(self):
		cfg = self._load_config()
		names = sorted(cfg.get("templates", {}).keys())
		if not names:
			messagebox.showinfo("提示", "暂无模板可加载")
			return
		choice = simpledialog.askstring("加载模板", f"可用模板：\n{', '.join(names)}\n\n输入要加载的模板名称：", parent=self.root)
		if not choice or choice not in cfg["templates"]:
			return
		self._apply_settings(cfg["templates"][choice])
		cfg["last_settings"] = cfg["templates"][choice]
		self._save_config(cfg)

	def manage_templates(self):
		cfg = self._load_config()
		names = sorted(cfg.get("templates", {}).keys())
		if not names:
			messagebox.showinfo("提示", "暂无模板")
			return
		name = simpledialog.askstring("删除模板", f"现有模板：\n{', '.join(names)}\n\n输入要删除的模板名称：", parent=self.root)
		if not name or name not in cfg["templates"]:
			return
		del cfg["templates"][name]
		self._save_config(cfg)
		messagebox.showinfo("提示", f"已删除模板：{name}")

	def _on_close(self):
		try:
			cfg = self._load_config()
			cfg["last_settings"] = self._serialize_settings()
			self._save_config(cfg)
		except Exception:
			pass
		self.root.destroy()

	def _resize_image(self, im: Image.Image) -> Image.Image:
		mode = self.resize_mode_var.get()
		val = max(1, int(self.resize_value_var.get() or 1))
		if mode == "none":
			return im
		w, h = im.size
		if mode == "width":
			new_w = val
			new_h = max(1, int(h * (new_w / w)))
		elif mode == "height":
			new_h = val
			new_w = max(1, int(w * (new_h / h)))
		elif mode == "percent":
			scale = val / 100.0
			new_w = max(1, int(w * scale))
			new_h = max(1, int(h * scale))
		else:
			return im
		return im.resize((new_w, new_h), Image.LANCZOS)

	def _set_running_state(self, running: bool, total: int = 0):
		def _apply():
			self.btn_run.configure(state=(tk.DISABLED if running else tk.NORMAL))
			self.btn_cancel.configure(state=(tk.NORMAL if running else tk.DISABLED))
			if running:
				self.progress.configure(maximum=max(1, total), value=0)
			else:
				self.progress.configure(value=0)
		self.root.after(0, _apply)

	def _inc_progress(self):
		def _apply():
			try:
				self.progress.step(1)
			except Exception:
				pass
		self.root.after(0, _apply)

	def cancel_export(self):
		self._cancel = True

	def run_export(self):
		out_dir = self.output_dir_var.get().strip()
		if not out_dir:
			messagebox.showerror("错误", "请先选择输出文件夹")
			return
		# 防止覆盖原图：默认禁止导出到原文件夹
		for it in self.items:
			if os.path.dirname(os.path.abspath(it.path)) == os.path.abspath(out_dir):
				messagebox.showerror("错误", "输出文件夹不能与源文件夹相同")
				return

		# start background worker
		items_to_process = list(self.items)
		self._cancel = False
		self._set_running_state(True, total=len(items_to_process))

		def _worker():
			fmt = self.format_var.get()
			prefix = self.prefix_var.get()
			suffix = self.suffix_var.get()
			jpeg_quality = int(self.jpeg_quality_var.get())

			os.makedirs(out_dir, exist_ok=True)
			success, skipped, failed, cancelled = 0, 0, 0, 0
			for it in items_to_process:
				if self._cancel:
					cancelled += 1
					break
				try:
					with Image.open(it.path) as im:
						im2 = self._resize_image(im)
						wm_type = self.wm_type_var.get()
						if wm_type == "date":
							date_str = extract_photo_date_string(it.path, fallback_mtime=self.fallback_mtime_var.get(), exif_only=self.exif_only_var.get())
							if not date_str:
								skipped += 1
								self._inc_progress()
								continue
							text_to_draw = date_str
						elif wm_type == "text":
							text_to_draw = (self.custom_text_var.get() or "").strip()
							if not text_to_draw:
								skipped += 1
								self._inc_progress()
								continue
						else:  # image watermark
							img_path = (self.image_wm_path_var.get() or "").strip()
							if not img_path or not os.path.isfile(img_path):
								skipped += 1
								self._inc_progress()
								continue

						if wm_type in ("date","text"):
							out_im = draw_text_watermark(
								im2,
								text_to_draw,
								font_size=int(self.font_size_var.get()),
								color=self.color_var.get(),
								opacity=float(self.opacity_var.get()),
								position=self.position_var.get(),
								margin_x=int(self.margin_x_var.get()),
								margin_y=int(self.margin_y_var.get()),
								font_path=(self.font_path_var.get().strip() or None),
								stroke_width=int(self.stroke_width_var.get()),
								stroke_color=self.stroke_color_var.get(),
								shadow_offset=(int(self.shadow_dx_var.get()), int(self.shadow_dy_var.get())),
								shadow_color=self.shadow_color_var.get(),
								shadow_opacity=float(self.shadow_opacity_var.get()),
							)
						else:
							with Image.open(img_path) as wm:
								out_im = draw_image_watermark(
									im2,
									wm,
									scale_percent=int(self.image_wm_scale_var.get()),
									opacity=float(self.opacity_var.get()),
									position=self.position_var.get(),
									margin_x=int(self.margin_x_var.get()),
									margin_y=int(self.margin_y_var.get()),
								)
						stem = os.path.splitext(os.path.basename(it.path))[0]
						out_name = f"{prefix}{stem}{suffix}"
						ext = ".jpg" if fmt == "JPEG" else ".png"
						out_path = os.path.join(out_dir, out_name + ext)
						if fmt == "JPEG":
							out_im = out_im.convert("RGB")
							out_im.save(out_path, format="JPEG", quality=jpeg_quality)
						else:
							out_im.save(out_path, format="PNG")
						success += 1
				except Exception as e:
					failed += 1
					print(f"Error: {it.path}: {e}", file=sys.stderr)
				finally:
					self._inc_progress()

			def _done():
				self._set_running_state(False)
				messagebox.showinfo("完成", f"成功: {success}\n跳过: {skipped}\n失败: {failed}\n取消: {cancelled}")
			self.root.after(0, _done)

		threading.Thread(target=_worker, daemon=True).start()


def run():
	# Try to use TkinterDnD when available
	if except_import is None and 'TkinterDnD' in globals():
		root = TkinterDnD.Tk()
	else:
		root = tk.Tk()
	App(root)
	root.mainloop()


