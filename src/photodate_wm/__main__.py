from .cli import main
import argparse
import sys

def _entry():
	parser = argparse.ArgumentParser(add_help=False)
	parser.add_argument("--gui", action="store_true")
	args, unknown = parser.parse_known_args(sys.argv[1:2])
	if args.gui:
		from .gui_app import run as run_gui
		run_gui()
		return
	# fallback to CLI
	from .cli import main as cli_main
	cli_main(sys.argv[1:])


if __name__ == "__main__":
	_entry()


