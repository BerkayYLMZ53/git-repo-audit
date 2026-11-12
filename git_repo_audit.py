"""Report the status of multiple local Git working trees."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


SKIP_DIRECTORIES = {".git", ".venv", "__pycache__", "node_modules"}
GIT_LOCATION_VARIABLES = {
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE",
}


def discover(root, max_depth, on_error):
    for directory, subdirectories, files in os.walk(root, onerror=on_error):
        path = Path(directory)
        if ".git" in subdirectories or ".git" in files:
            yield path
        if len(path.relative_to(root).parts) >= max_depth:
            subdirectories.clear()
        else:
            subdirectories[:] = sorted(name for name in subdirectories if name not in SKIP_DIRECTORIES)


def parse_status(output):
    result = {
        "branch": None, "detached": False, "unborn": False, "upstream": None,
        "ahead": None, "behind": None, "staged": 0, "unstaged": 0, "untracked": 0, "conflicts": 0,
    }
    for record in output.split("\0"):
        if record.startswith("# branch.head "):
            branch = record.removeprefix("# branch.head ")
            result["detached"] = branch == "(detached)"
            if not result["detached"]:
                result["branch"] = branch
        elif record.startswith("# branch.oid "):
            result["unborn"] = record.endswith(" (initial)")
        elif record.startswith("# branch.upstream "):
            result["upstream"] = record.removeprefix("# branch.upstream ")
        elif record.startswith("# branch.ab "):
            ahead, behind = record.removeprefix("# branch.ab ").split()
            result["ahead"] = int(ahead[1:])
            result["behind"] = int(behind[1:])
        elif record.startswith("1 "):
            result["staged"] += record[2] != "."
            result["unstaged"] += record[3] != "."
        elif record.startswith("u "):
            result["conflicts"] += 1
        elif record.startswith("? "):
            result["untracked"] += 1
    return result


def read_status(path):
    environment = {key: value for key, value in os.environ.items() if key not in GIT_LOCATION_VARIABLES}
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_NO_LAZY_FETCH"] = "1"
    status = subprocess.run(
        [
            "git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(path),
            "status", "--porcelain=v2", "--branch", "--ahead-behind", "-z",
            "--untracked-files=normal", "--ignore-submodules=all", "--no-renames",
        ],
        capture_output=True, env=environment, timeout=15, check=True,
    )
    return parse_status(status.stdout.decode("utf-8", errors="replace"))


def inspect(root, max_depth):
    report = {"repositories": [], "errors": []}

    def on_error(error):
        report["errors"].append({"path": error.filename, "error": "Klasör okunamadı."})

    for path in discover(root, max_depth, on_error):
        try:
            status = read_status(path)
        except subprocess.TimeoutExpired:
            report["errors"].append({"path": str(path), "error": "Git durumu 15 saniyede okunamadı."})
        except (OSError, subprocess.CalledProcessError):
            report["errors"].append({"path": str(path), "error": "Git durumu okunamadı."})
        else:
            report["repositories"].append({"path": str(path), **status})
    return report


def has_changes(repository):
    return any(repository[field] for field in ("staged", "unstaged", "untracked", "conflicts", "ahead", "behind"))


def print_report(report):
    for repository in report["repositories"]:
        branch = repository["branch"] or "ayrık HEAD"
        if repository["unborn"]:
            branch += " (ilk commit bekleniyor)"
        upstream = repository["upstream"]
        if upstream and repository["ahead"] is not None:
            upstream += f' (+{repository["ahead"]}/-{repository["behind"]})'
        print(f'{repository["path"]} · {branch} · {upstream or "izlenen dal yok"}')
        print(
            f'  hazırlanan {repository["staged"]} · çalışma alanı {repository["unstaged"]}'
            f' · izlenmeyen {repository["untracked"]} · çakışma {repository["conflicts"]}'
        )
    for error in report["errors"]:
        print(f'{error["path"]}: {error["error"]}', file=sys.stderr)
    if not report["repositories"] and not report["errors"]:
        print("Bu derinlikte Git çalışma ağacı bulunamadı.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Yerel Git depolarının durumunu tek seferde göster.")
    parser.add_argument("root", nargs="?", type=Path, default=Path("."))
    parser.add_argument("--depth", type=int, default=3, help="Tarama derinliği. 0 yalnızca kökü denetler.")
    parser.add_argument("--json", action="store_true", help="Raporu JSON olarak yaz.")
    parser.add_argument("--check", action="store_true", help="Değişiklik veya dal farkı varsa 1 ile çık.")
    args = parser.parse_args(argv)
    if args.depth < 0:
        parser.error("--depth sıfır veya daha büyük olmalı")
    if not args.root.is_dir() or not shutil.which("git"):
        parser.error("Erişilebilir bir klasör ve PATH üzerinde Git gerekiyor")

    report = inspect(args.root.resolve(), args.depth)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    if report["errors"]:
        return 2
    return int(args.check and any(has_changes(item) for item in report["repositories"]))


if __name__ == "__main__":
    raise SystemExit(main())
