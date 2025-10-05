import os
import sys


def main() -> None:
	# In dev: add src to path; in frozen exe: rely on bundled modules
	if not getattr(sys, 'frozen', False):
		project_dir = os.path.dirname(os.path.abspath(__file__))
		src_dir = os.path.join(project_dir, "src")
		if src_dir not in sys.path:
			sys.path.insert(0, src_dir)

	from photodate_wm.gui_app import run as run_gui
	run_gui()


if __name__ == "__main__":
	main()

