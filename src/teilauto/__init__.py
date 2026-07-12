from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("teilauto-cli")
except PackageNotFoundError:  # running from a checkout without install
    __version__ = "0.0.0.dev0"
