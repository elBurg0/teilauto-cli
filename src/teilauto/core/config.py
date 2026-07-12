from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from pathlib import Path

import platformdirs
import tomli_w

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

DEFAULTS: dict = {
    "location": {"lat": 51.33853, "lng": 12.39163, "radius_m": 500},
    "defaults": {"min_fuel": 0.0, "window_min": 30, "interval_sec": 120},
    "api": {"prov_id": "118"},
    "notify": {
        "channels": [],
        "telegram": {"chat_id": ""},
        "ntfy": {"topic": "", "server": "https://ntfy.sh"},
    },
}


def _leaf_keys(tree: dict, prefix: str = "") -> list[str]:
    keys: list[str] = []
    for name, value in tree.items():
        dotted = f"{prefix}{name}"
        if isinstance(value, dict):
            keys.extend(_leaf_keys(value, f"{dotted}."))
        else:
            keys.append(dotted)
    return keys


KNOWN_KEYS: tuple[str, ...] = tuple(_leaf_keys(DEFAULTS))


def config_dir() -> Path:
    override = os.getenv("TEILAUTO_CONFIG_DIR")
    if override:
        return Path(override)
    return platformdirs.user_config_path("teilauto")


def config_file() -> Path:
    return config_dir() / "config.toml"


def read_raw(path: Path | None = None) -> dict:
    path = path or config_file()
    if not path.is_file():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def write_raw(data: dict, path: Path | None = None) -> None:
    path = path or config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        tomli_w.dump(data, fh)


def get_value(data: dict, key: str):
    node = data
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def set_value(data: dict, key: str, value: object) -> None:
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def unset_value(data: dict, key: str) -> None:
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return
    node.pop(parts[-1], None)


def coerce_value(text: str) -> object:
    low = text.strip().lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    if "," in text:
        return [part.strip() for part in text.split(",") if part.strip()]
    return text


def _merged(path: Path | None = None) -> dict:
    merged = copy.deepcopy(DEFAULTS)

    def deep_update(base: dict, extra: dict) -> None:
        for name, value in extra.items():
            if isinstance(value, dict) and isinstance(base.get(name), dict):
                deep_update(base[name], value)
            else:
                base[name] = value

    deep_update(merged, read_raw(path))
    for key in KNOWN_KEYS:
        env_name = "TEILAUTO_" + key.replace(".", "_").upper()
        raw = os.getenv(env_name)
        if raw is None:
            continue
        default = get_value(DEFAULTS, key)
        value: object
        if isinstance(default, list):
            value = [part.strip() for part in raw.split(",") if part.strip()]
        elif isinstance(default, float):
            value = float(raw)
        elif isinstance(default, int):
            value = int(raw)
        else:
            value = raw
        set_value(merged, key, value)
    return merged


def effective_config(path: Path | None = None) -> dict[str, object]:
    merged = _merged(path)
    return {key: get_value(merged, key) for key in KNOWN_KEYS}


@dataclass(frozen=True)
class Settings:
    lat: float
    lng: float
    radius_m: int
    min_fuel: float
    window_min: int
    interval_sec: int
    prov_id: str
    channels: tuple[str, ...]
    tg_chat_id: str
    ntfy_topic: str
    ntfy_server: str


def load_settings(path: Path | None = None) -> Settings:
    merged = _merged(path)
    channels = get_value(merged, "notify.channels")
    if isinstance(channels, str):
        channels = [channels]
    return Settings(
        lat=float(get_value(merged, "location.lat")),
        lng=float(get_value(merged, "location.lng")),
        radius_m=int(get_value(merged, "location.radius_m")),
        min_fuel=float(get_value(merged, "defaults.min_fuel")),
        window_min=int(get_value(merged, "defaults.window_min")),
        interval_sec=int(get_value(merged, "defaults.interval_sec")),
        prov_id=str(get_value(merged, "api.prov_id")),
        channels=tuple(channels or ()),
        tg_chat_id=str(get_value(merged, "notify.telegram.chat_id") or ""),
        ntfy_topic=str(get_value(merged, "notify.ntfy.topic") or ""),
        ntfy_server=str(get_value(merged, "notify.ntfy.server") or "https://ntfy.sh"),
    )
