from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import List, Optional

from PIL import Image, ImageTk

try:
	# optional drag & drop support
	from tkinterdnd2 import DND_FILES, TkinterDnD
	import tkinter as tk
	from tkinter import ttk, filedialog, messagebox
	except_import = None
except Exception as e:
	except_import = e
	import tkinter as tk
	from tkinter import ttk, filedialog, messagebox

from .cli import SUPPORTED_EXTENSIONS
from .exif_utils import extract_photo_date_string
from .render import draw_text_watermark


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
		self.exif_only_var = tk.BooleanVar(value=False)
		self.fallback_mtime_var = tk.BooleanVar(value=True)

		self._build_ui()
		self._setup_dnd()

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

		# List area
		self.listbox = tk.Listbox(frm, height=10)
		self.listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

		# Options
		opts = ttk.LabelFrame(frm, text="参数")
		opts.pack(fill=tk.X, padx=6, pady=6)

		row = 0
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

		# exif-only & fallback
		chk1 = ttk.Checkbutton(opts, text="仅含EXIF日期", variable=self.exif_only_var)
		chk2 = ttk.Checkbutton(opts, text="无EXIF回退到修改时间", variable=self.fallback_mtime_var)
		chk1.grid(row=row, column=0, sticky=tk.W, padx=4, pady=4)
		chk2.grid(row=row, column=1, sticky=tk.W, padx=4, pady=4)
		row += 1

		btn_run = ttk.Button(frm, text="开始处理并导出", command=self.run_export)
		btn_run.pack(pady=8)

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

		fmt = self.format_var.get()
		prefix = self.prefix_var.get()
		suffix = self.suffix_var.get()
		jpeg_quality = int(self.jpeg_quality_var.get())

		os.makedirs(out_dir, exist_ok=True)
		success, skipped, failed = 0, 0, 0
		for it in self.items:
			try:
				with Image.open(it.path) as im:
					# 读取日期文本
					date_str = extract_photo_date_string(it.path, fallback_mtime=self.fallback_mtime_var.get(), exif_only=self.exif_only_var.get())
					if not date_str:
						skipped += 1
						continue
					im2 = self._resize_image(im)
					out_im = draw_text_watermark(
						im2,
						date_str,
						font_size=int(self.font_size_var.get()),
						color=self.color_var.get(),
						opacity=float(self.opacity_var.get()),
						position=self.position_var.get(),
						margin_x=int(self.margin_x_var.get()),
						margin_y=int(self.margin_y_var.get()),
						font_path=(self.font_path_var.get().strip() or None),
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

		messagebox.showinfo("完成", f"成功: {success}\n跳过: {skipped}\n失败: {failed}")


def run():
	# Try to use TkinterDnD when available
	if except_import is None and 'TkinterDnD' in globals():
		root = TkinterDnD.Tk()
	else:
		root = tk.Tk()
	App(root)
	root.mainloop()


