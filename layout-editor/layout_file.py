"""Read and write D200 layout files in the format of my-layouts/apps/*.yaml.

The layouts are hand-readable YAML with comments: a header comment, one
"# n: description" comment per button and path hints ("### <--- change this
to your path") behind commands of this repository's scripts. PyYAML drops
comments, so they are extracted separately when reading and the file is
written in exactly this format again.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from config import BIN_DIR, BLANK_IMAGE, BUTTON_COUNT, WIDE_INDEX

DESCRIPTION_RE = re.compile(r"^# (\d+):\s?(.*)$")
PATH_HINT = "  ### <--- change this to your path (where {} is linked)"
SOURCE_HINT = "  ### <--- change this to your path (your installation)"
SCRIPT_RE = re.compile(rf"{re.escape(BIN_DIR)}/(d200-[a-z]+)")
KEY_RE = re.compile(rf"^{re.escape(BIN_DIR)}/d200-key (\S+)$")
RAISE_RE = re.compile(rf"^{re.escape(BIN_DIR)}/d200-raise (.+)$")

# Function kinds shown in the editor
EMPTY, KEY, RAISE, COMMAND = "empty", "key", "raise", "command"


@dataclass
class Layout:
    """One layout file: settings, buttons and the comments around them."""

    name: str
    header: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    descriptions: list[str] = field(default_factory=lambda: [""] * BUTTON_COUNT)

    # --------------------------------------------------------------------------
    @property
    def buttons(self) -> list:
        """Button list of the layout (always BUTTON_COUNT entries, None = unset)."""
        return self.data["buttons"]


# --------------------------------------------------------------------------
def empty_layout(name: str) -> Layout:
    """Return a layout with the usual settings, blank keys and the clock.

    Used for "new layout"; the settings are the same as in all existing layouts.
    """
    data = {
        "brightness": 100,
        "label_style": {"Align": "bottom", "Color": 0xFFFFFF, "FontName": "Roboto",
                        "ShowTitle": False, "Size": 10, "Weight": 80},
        "obs": {"host": "localhost", "port": 4444, "password": None},
        "buttons": [empty_button() for _ in range(WIDE_INDEX)] + [None],
        "background": None,
    }
    return Layout(name, data=data)


# --------------------------------------------------------------------------
def empty_button() -> dict:
    """Return a disabled key with a black image, like the free keys in the layouts."""
    return {"enabled": False, "background_tile": BLANK_IMAGE}


# --------------------------------------------------------------------------
def load(path: Path) -> Layout:
    """Read a layout file including its header and button comments.

    Args:
        path: Layout file (apps/<name>.yaml).

    Returns:
        The layout; missing buttons are filled up with None.
    """
    text = path.read_text()
    data = yaml.safe_load(text) or {}
    buttons = list(data.get("buttons") or [])
    data["buttons"] = (buttons + [None] * BUTTON_COUNT)[:BUTTON_COUNT]
    layout = Layout(path.stem, data=data)
    lines = text.splitlines()
    for line in lines:
        if not line.startswith("#"):
            break
        layout.header.append(line)
    for line in lines:
        match = DESCRIPTION_RE.match(line.strip())
        if match and int(match[1]) < BUTTON_COUNT:
            layout.descriptions[int(match[1])] = match[2]
    return layout


# --------------------------------------------------------------------------
def dump(layout: Layout) -> str:
    """Return the layout as text in the format of the hand-written layouts.

    Top-level keys keep their order; every button gets a "# n: description"
    comment and commands calling d200-* scripts get the path hint. Button
    keys starting with "_" are editor-internal (e.g. "_preview") and skipped.
    """
    out = [*layout.header]
    for key, value in layout.data.items():
        if key != "buttons":
            out.append(_dump_yaml({key: value}))
            continue
        out.append("buttons:\n")
        for index, button in enumerate(layout.buttons):
            if button:
                button = {k: v for k, v in button.items() if not k.startswith("_")}
            out.append(f"# {index}: {layout.descriptions[index]}".rstrip())
            out.append(_add_path_hints(_dump_yaml([button])) + ("" if index == BUTTON_COUNT - 1 else "\n"))
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
def save(layout: Layout, path: Path) -> None:
    """Write the layout to a file."""
    path.write_text(dump(layout))


# --------------------------------------------------------------------------
def _dump_yaml(value) -> str:
    """Dump a value in block style without line wrapping and trailing newline."""
    return yaml.safe_dump(value, sort_keys=False, allow_unicode=True, width=1000).rstrip("\n")


# --------------------------------------------------------------------------
def _add_path_hints(text: str) -> str:
    """Append path hints to cmd lines calling d200-* scripts and to icon sources in the home folder."""
    lines = []
    for line in text.splitlines():
        match = SCRIPT_RE.search(line)
        if line.lstrip().startswith("cmd:") and match:
            line += PATH_HINT.format(match[1])
        elif line.lstrip().startswith("source: ~/"):
            line += SOURCE_HINT
        lines.append(line)
    return "\n".join(lines)


# --------------------------------------------------------------------------
def function_of(button: dict | None) -> tuple[str, str]:
    """Return the editor's function kind and its parameter for a button.

    Only plain single calls are shown as "key" or "raise"; anything else
    (e.g. two d200-key calls joined with &&) stays a free command, so the
    editor never changes a command it does not fully understand.

    Returns:
        (kind, value): value is the key combination, the d200-raise arguments
        or the command; empty for EMPTY.
    """
    if not button or not button.get("enabled", True):
        return EMPTY, ""
    cmd = str((button.get("params") or {}).get("cmd", ""))
    if button.get("action", "command") == "app":
        return COMMAND, str(button["params"].get("name", ""))
    if "&&" not in cmd and ";" not in cmd:
        if match := KEY_RE.match(cmd):
            return KEY, match[1]
        if match := RAISE_RE.match(cmd):
            return RAISE, match[1]
    return COMMAND, cmd


# --------------------------------------------------------------------------
def command_for(kind: str, value: str) -> str:
    """Return the cmd string for a function kind (inverse of function_of)."""
    if kind == KEY:
        return f"{BIN_DIR}/d200-key {value}"
    if kind == RAISE:
        return f"{BIN_DIR}/d200-raise {value}"
    return value
