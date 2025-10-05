import argparse
import os
import sys
from typing import Iterable, List, Set

from .exif_utils import extract_photo_date_string
from .render import draw_text_watermark


SUPPORTED_EXTENSIONS: Set[str] = {
	".jpg",
	".jpeg",
	".png",
	".bmp",
	".tif",
	".tiff",
	".heic",
	".heif",
}


def enumerate_candidate_files(root_path: str, recursive: bool, include_ext: Iterable[str]) -> List[str]:
	valid_ext = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in include_ext}
	result: List[str] = []
	if os.path.isfile(root_path):
		ext = os.path.splitext(root_path)[1].lower()
		if not valid_ext or ext in valid_ext:
			result.append(os.path.abspath(root_path))
		return result

	if not os.path.isdir(root_path):
		raise FileNotFoundError(f"Path does not exist or not accessible: {root_path}")

	for dirpath, dirnames, filenames in os.walk(root_path):
		for filename in filenames:
			ext = os.path.splitext(filename)[1].lower()
			if not valid_ext or ext in valid_ext:
				result.append(os.path.abspath(os.path.join(dirpath, filename)))
		if not recursive:
			break
	return result


def build_arg_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		prog="photodate-wm",
		description="Batch add shooting-date watermark to photos.",
	)
	parser.add_argument("--path", required=True, help="File or directory path to process")
	parser.add_argument("--dry-run", action="store_true", help="List files that would be processed without writing outputs")
	parser.add_argument("--verbose", action="store_true", help="Enable verbose logs")
	parser.add_argument("--recursive", action="store_true", help="Recurse into subdirectories when a directory is provided")
	parser.add_argument(
		"--include-ext",
		help="Comma-separated list of extensions to include (e.g., .jpg,.jpeg,.png)",
		default=",".join(sorted(SUPPORTED_EXTENSIONS)),
	)
	parser.add_argument("--exif-only", action="store_true", help="Only process files with EXIF shooting date; skip others")
	parser.add_argument("--fallback-mtime", action="store_true", default=True, help="Use file modification time if EXIF shooting date missing")
	parser.add_argument("--no-fallback-mtime", dest="fallback_mtime", action="store_false", help="Do not fallback to mtime when EXIF missing")
	# Rendering options
	parser.add_argument("--font-size", type=int, default=32, help="Font size in pixels")
	parser.add_argument("--color", type=str, default="#FFFFFF", help="Text color (#RRGGBB, #RRGGBBAA, or named)")
	parser.add_argument("--opacity", type=float, default=1.0, help="Opacity (0-1). Ignored if color includes alpha")
	parser.add_argument("--position", type=str, default="br", help="Anchor: tl,tc,tr,cl,cc,cr,bl,bc,br")
	parser.add_argument("--margin-x", type=int, default=24, help="Horizontal margin in pixels from anchor")
	parser.add_argument("--margin-y", type=int, default=24, help="Vertical margin in pixels from anchor")
	parser.add_argument("--font-path", type=str, default=None, help="Path to .ttf/.otf font file")
	# Output options
	parser.add_argument("--output-dir-name", type=str, default=None, help="Override output subdirectory name; default <dirname>_watermark")
	parser.add_argument("--suffix", type=str, default=None, help="Optional filename suffix (without dot)")
	parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files")
	return parser


def _derive_output_root(input_path: str, override_name: str | None) -> str:
	if os.path.isfile(input_path):
		parent = os.path.dirname(os.path.abspath(input_path))
		base_dir = os.path.basename(parent)
	else:
		parent = os.path.abspath(input_path)
		base_dir = os.path.basename(parent)
	name = override_name if override_name else f"{base_dir}_watermark"
	return os.path.join(parent, name)


def _map_output_path(file_path: str, root_input: str, root_output: str, suffix: str | None) -> str:
	if os.path.isfile(root_input):
		# single file mode: put into output root directly
		rel = os.path.basename(file_path)
	else:
		rel = os.path.relpath(file_path, start=root_input)
	out_path = os.path.join(root_output, rel)
	if suffix:
		stem, ext = os.path.splitext(out_path)
		out_path = f"{stem}_{suffix}{ext}"
	os.makedirs(os.path.dirname(out_path), exist_ok=True)
	return out_path


def main(argv: List[str] | None = None) -> int:
	argv = sys.argv[1:] if argv is None else argv
	parser = build_arg_parser()
	args = parser.parse_args(argv)

	include_ext = [e.strip() for e in args.include_ext.split(",") if e.strip()]

	try:
		files = enumerate_candidate_files(args.path, args.recursive, include_ext)
	except FileNotFoundError as exc:
		print(str(exc), file=sys.stderr)
		return 2

	if args.dry_run:
		print(f"DRY RUN: {len(files)} file(s) would be processed")
		for f in files:
			date_str = extract_photo_date_string(f, fallback_mtime=args.fallback_mtime, exif_only=args.exif_only)
			status = date_str if date_str else ("SKIP: no date" if args.exif_only else "no date")
			print(f"{f} -> {status}")
		return 0

	if args.verbose:
		print(f"Processing {len(files)} file(s)...")

	root_output = _derive_output_root(args.path, args.output_dir_name)
	ok = 0
	skipped = 0
	errors = 0
	for f in files:
		try:
			date_str = extract_photo_date_string(f, fallback_mtime=args.fallback_mtime, exif_only=args.exif_only)
			if not date_str:
				skipped += 1
				if args.verbose:
					print(f"Skip {f}: no date")
				continue
			from PIL import Image
			with Image.open(f) as im:
				out_im = draw_text_watermark(
					im,
					date_str,
					font_size=args.font_size,
					color=args.color,
					opacity=args.opacity,
					position=args.position,
					margin_x=args.margin_x,
					margin_y=args.margin_y,
					font_path=args.font_path,
				)
				out_path = _map_output_path(f, os.path.abspath(args.path), root_output, args.suffix)
				if os.path.exists(out_path) and not args.overwrite:
					if args.verbose:
						print(f"Exists, skip write: {out_path}")
					ok += 1
					continue
				# Choose format from original extension and attempt to keep EXIF for JPEG
				_, ext = os.path.splitext(f)
				fmt = "JPEG" if ext.lower() in {".jpg", ".jpeg"} else None
				if fmt == "JPEG":
					try:
						import piexif
						exif_bytes = piexif.dump(piexif.load(f))
						out_im.save(out_path, format=fmt, exif=exif_bytes, quality=95)
					except Exception:
						out_im.save(out_path, format=fmt, quality=95)
				else:
					out_im.save(out_path, format=fmt)
				ok += 1
		except Exception as e:
			errors += 1
			print(f"Error processing {f}: {e}", file=sys.stderr)

	if errors > 0 or skipped > 0:
		return 1
	return 0


if __name__ == "__main__":
	sys.exit(main())

