import argparse
import os
import sys
from typing import Iterable, List, Set

from .exif_utils import extract_photo_date_string


SUPPORTED_EXTENSIONS: Set[str] = {
	".jpg",
	".jpeg",
	".png",
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
		description="Batch add shooting-date watermark to photos (dry-run enumerates files).",
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
	return parser


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

	# Placeholder for future processing steps
	if args.verbose:
		print(f"Found {len(files)} file(s) to process")

	# For v0 minimal CLI, we do nothing unless dry-run; return 0 to indicate success
	return 0


if __name__ == "__main__":
	sys.exit(main())

