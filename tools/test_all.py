"""Configure, build and run every SS6 package's host tests plus the motor demo.

Usage: python tools/test_all.py [--build-dir DIR] [--compiler g++] [--fresh]

Requires CMake and Ninja (``pip install cmake ninja`` is enough) and a C++17
compiler. On Windows the default build directory lives under %TEMP% with a short
name, because deep OneDrive paths overflow MAX_PATH in generated object paths.
Nothing here touches hardware: every test uses a fake transport or fake IDF HAL.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ["can-device-core", "zdt-x-driver", "dji-motor-driver", "ss6-bsp"]


def tool(name):
    found = shutil.which(name)
    if not found:
        sys.exit(f"{name} not found on PATH; install it (for example: pip install cmake ninja)")
    return found


def run(command):
    print("+", " ".join(str(part) for part in command), flush=True)
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    default_build = Path(tempfile.gettempdir()) / "ss6-build" if os.name == "nt" else ROOT / "build"
    parser.add_argument("--build-dir", type=Path, default=default_build)
    parser.add_argument("--compiler", default=os.environ.get("CXX", "g++"))
    parser.add_argument("--fresh", action="store_true", help="delete the build directory first")
    args = parser.parse_args()

    missing = [name for name in PACKAGES if not (ROOT / "repos" / name / "CMakeLists.txt").exists()]
    if missing:
        sys.exit(f"missing submodules {missing}; run: git submodule update --init")
    cmake, ctest = tool("cmake"), tool("ctest")
    generator = ["-G", "Ninja"] if shutil.which("ninja") else []
    if args.fresh and args.build_dir.exists():
        shutil.rmtree(args.build_dir)

    run([cmake, "-S", ROOT, "-B", args.build_dir, *generator,
         f"-DCMAKE_CXX_COMPILER={args.compiler}", "-DSS6_BUILD_MOTOR_DEMO=ON"])
    run([cmake, "--build", args.build_dir])
    run([ctest, "--test-dir", args.build_dir, "--output-on-failure"])
    names = {"ss6_motor_demo", "ss6_motor_demo.exe"}
    demo = next((path for path in args.build_dir.rglob("ss6_motor_demo*")
                 if path.is_file() and path.name in names), None)
    if demo is None:
        sys.exit("ss6_motor_demo was not built")
    run([demo])
    print("All SS6 package tests and the motor demo passed (simulation only, no hardware).")


if __name__ == "__main__":
    main()
