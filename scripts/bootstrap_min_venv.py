#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创建当前项目的最小可用虚拟环境。"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VENV = PROJECT_ROOT / ".venv"
DEFAULT_REQUIREMENTS = PROJECT_ROOT / "requirements.min.txt"


def run(command: list[str], env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, check=True, env=env)


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def venv_site_packages(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Lib" / "site-packages"

    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return venv_dir / "lib" / version / "site-packages"


def ensure_local_temp(project_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    tmp_dir = project_root / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    env["TMP"] = str(tmp_dir)
    env["TEMP"] = str(tmp_dir)
    env["TMPDIR"] = str(tmp_dir)
    return env


def create_venv(venv_dir: Path) -> None:
    builder = venv.EnvBuilder(with_pip=False, clear=False, symlinks=(os.name != "nt"))
    builder.create(str(venv_dir))


def try_ensurepip(venv_python_path: Path, env: dict[str, str]) -> bool:
    try:
        run([str(venv_python_path), "-m", "ensurepip", "--default-pip"], env=env)
        return True
    except subprocess.CalledProcessError:
        return False


def install_min_requirements(venv_dir: Path, requirements_file: Path, env: dict[str, str]) -> None:
    site_packages = venv_site_packages(venv_dir)
    site_packages.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--target",
            str(site_packages),
            "-r",
            str(requirements_file),
        ],
        env=env,
    )


def install_pip_into_venv(venv_dir: Path, env: dict[str, str]) -> bool:
    site_packages = venv_site_packages(venv_dir)
    try:
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--target",
                str(site_packages),
                "pip",
            ],
            env=env,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="创建项目最小可用虚拟环境")
    parser.add_argument("--venv", default=str(DEFAULT_VENV), help="虚拟环境目录，默认 .venv")
    parser.add_argument("--requirements", default=str(DEFAULT_REQUIREMENTS), help="依赖清单文件")
    args = parser.parse_args()

    venv_dir = Path(args.venv).expanduser().resolve()
    requirements_file = Path(args.requirements).expanduser().resolve()

    if not requirements_file.exists():
        print(f"❌ 依赖文件不存在：{requirements_file}")
        return 1

    env = ensure_local_temp(PROJECT_ROOT)

    print(f"创建虚拟环境：{venv_dir}")
    create_venv(venv_dir)

    python_path = venv_python(venv_dir)
    if not python_path.exists():
        print(f"❌ 未找到虚拟环境 Python：{python_path}")
        return 1

    pip_ready = try_ensurepip(python_path, env)
    if pip_ready:
        run([str(python_path), "-m", "pip", "install", "-r", str(requirements_file)], env=env)
        print("✅ 虚拟环境已创建，并通过 ensurepip 安装依赖")
        return 0

    print("⚠️ ensurepip 失败，改用宿主 pip 直接向虚拟环境 site-packages 安装依赖")
    install_min_requirements(venv_dir, requirements_file, env)
    pip_installed = install_pip_into_venv(venv_dir, env)

    print("✅ 虚拟环境已创建，并安装最小依赖")
    if pip_installed:
        print("✅ 已补装 pip，可使用 '.venv python -m pip'")
    else:
        print("⚠️ 未补装 pip，但虚拟环境已经可运行项目脚本")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
