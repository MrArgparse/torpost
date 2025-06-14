import argparse
import msgspec
from _typeshed import Incomplete
from pathlib import Path
from rich.text import Text
from typing import TypeVar

PLATFORMDIRS: Incomplete
CONFIG_FOLDER: Incomplete
DEFAULT_CONFIGURATION_PATH: Incomplete
DEFAULT_ENCODING: str
T = TypeVar('T')
ERROR_MESSAGES: Incomplete

class ConfigError(Exception): ...

class Style(msgspec.Struct, kw_only=True):
	open: str = ...
	poster: str = ...
	info: str = ...
	video_stats: str = ...
	collage: str = ...
	screens: str = ...
	close: str = ...

class Styles(msgspec.Struct, kw_only=True):
	default: dict[str, Style] = msgspec.field(default_factory=dict)

CATEGORIES: Incomplete

class DefaultConfig(msgspec.Struct, kw_only=True):
	styles: dict[str, Style] = msgspec.field(default_factory=Incomplete)
	desc_path: Path = ...
	torrents_path: Path = ...

def encode_hook(obj: Path | str) -> str: ...
def decode_hook(type_: type[Path], value: Path | str) -> Path | str: ...
def get_config_path(path: Path | None = None) -> Path: ...
def load_config(path: Path | None = None) -> DefaultConfig: ...
def save_config(configuration: DefaultConfig, path: Path | None = None) -> None: ...
def load_or_create_config(path: Path | None = None) -> DefaultConfig: ...

CONFIG: Incomplete
STYLES: Incomplete

def parse_torpost() -> argparse.ArgumentParser: ...
def valid_collage(value: str) -> str: ...
def make_bbcode(
	desc_path: Path, desc: dict[str, str | dict[str, str]], style: str
) -> tuple[str, list[str]]: ...
def preview_desc(desc: dict[str, str | dict[str, str]], text: list[str]) -> Text: ...
def post_torrent(
	bbcode: str,
	desc: dict[str, str | dict[str, str]],
	name: str,
	tracker: str,
	collages: list[str] | None = None,
	no_prompts: bool = False,
) -> None: ...
def main() -> None: ...
