# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


import os
proj_dir = os.path.dirname(__file__)
src_dir = os.path.join(proj_dir, 'src')

a = Analysis(
	['run_gui.py'],
	pathex=[proj_dir, src_dir],
	binaries=[],
	datas=[],
	hiddenimports=['PIL._tkinter_finder', 'tkinterdnd2'],
	hookspath=[],
	runtime_hooks=[],
	excludes=[],
	noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
	pyz,
	a.scripts,
	a.binaries,
	a.zipfiles,
	a.datas,
	name='PhotoDateWatermark',
	debug=False,
	bootloader_ignore_signals=False,
	strip=False,
	upx=True,
	console=False,
)

