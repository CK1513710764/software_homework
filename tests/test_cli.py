import os
import sys
import subprocess


def run_module(args, cwd):
	env = os.environ.copy()
	# Ensure src is importable for `python -m photodate_wm`
	src_path = os.path.join(cwd, "src")
	env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")
	cmd = [sys.executable, "-m", "photodate_wm"] + args
	return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)


def test_help_shows_usage(tmp_path):
	project_root = os.getcwd()
	result = run_module(["-h"], cwd=project_root)
	assert result.returncode == 0
	assert "usage:" in result.stdout.lower()


def test_dry_run_enumerates_files(tmp_path):
	project_root = os.getcwd()
	images_dir = tmp_path / "images"
	images_dir.mkdir(parents=True, exist_ok=True)
	(img1 := images_dir / "a.jpg").write_bytes(b"test")
	(img2 := images_dir / "b.PNG").write_bytes(b"test")
	(img3 := images_dir / "c.txt").write_text("nope")

	result = run_module(["--path", str(images_dir), "--dry-run"], cwd=project_root)
	assert result.returncode == 0
	out = result.stdout
	assert "DRY RUN:" in out
	# Should include .jpg and .png (case-insensitive), exclude .txt
	assert str(img1) in out
	assert str(img2) in out or str(img2).lower() in out.lower()
	assert str(img3) not in out

