"""Paths and constants of the D200 layout editor."""

from pathlib import Path

VERSION = "1.1.0"

ULANZI_DIR = Path.home() / ".config/ulanzi"  ### <--- change this to your path (where ~/.config/ulanzi/ is set up)
APPS_DIR = ULANZI_DIR / "apps"
CONFIG_FILE = ULANZI_DIR / "config.yaml"
# Must live next to config.yaml so that relative image paths (./icons/...) resolve
TEST_FILE = ULANZI_DIR / ".d200-layout-test.yaml"
# Relative paths in layouts (./icons/..., ./svg/...) are resolved against the
# real folder that holds apps/ (my-layouts/ in this repository)
LAYOUT_ROOT = APPS_DIR.resolve().parent
ICONS_DIR = LAYOUT_ROOT / "icons"
BLANK_IMAGE = "./icons/blank.png"

BIN_DIR = "~/.local/bin"  ### <--- change this to your path (where d200-key and d200-raise are linked)
D200_ICON = Path(__file__).resolve().parent.parent / "d200-icon"
VALIDATOR = Path.home() / ".local/ulanzi/venv/bin/ulanzi-manager"  ### <--- change this to your path (venv of ulanzi-d200-linux install.sh)

BUTTON_COUNT = 14  # 13 keys + wide display
WIDE_INDEX = 13
KEY_SIZE = 98      # preview size of a key in the editor (half the device image)
