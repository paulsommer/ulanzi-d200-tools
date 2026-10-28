"""Dialog for "new layout" and "copy layout": asks for the layout name.

The layout name is the window class as d200-focus matches it (last dot
component, lower case). Recently active window classes are read from the
d200-focus journal, so d200-focus itself needs no extra interface for this.
"""

import re
import subprocess
from pathlib import Path

from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QDialog, QWidget

from config import APPS_DIR

UI_FILE = Path(__file__).with_name("new_layout_dialog.ui")
FOCUS_RE = re.compile(r"^focus: (\S+) ->")
# How many journal lines of d200-focus are searched for window classes
JOURNAL_LINES = 5000


# --------------------------------------------------------------------------
def layout_name(window_class: str) -> str:
    """Return the layout name d200-focus uses for a window class (org.kde.okular -> okular)."""
    return window_class.strip().lower().rsplit(".", 1)[-1]


# --------------------------------------------------------------------------
def recent_window_classes() -> list[str]:
    """Return layout names of recently active windows without an own layout, newest first."""
    result = subprocess.run(["journalctl", "--user", "-u", "d200-focus", "-o", "cat", "-n", str(JOURNAL_LINES)],
                            capture_output=True, text=True)
    names = []
    for line in reversed(result.stdout.splitlines()):
        if match := FOCUS_RE.match(line):
            name = layout_name(match[1])
            if name not in names and not (APPS_DIR / f"{name}.yaml").exists():
                names.append(name)
    return names


# --------------------------------------------------------------------------
def ask_layout_name(parent: QWidget, title: str) -> str | None:
    """Show the dialog and return the chosen, not yet existing layout name.

    Args:
        parent: Main window.
        title: Dialog title ("New layout" or "Copy layout").

    Returns:
        Layout name, or None if cancelled or empty.
    """
    dialog: QDialog = QUiLoader().load(str(UI_FILE), parent)
    dialog.setWindowTitle(title)
    dialog.nameCombo.addItems(recent_window_classes())
    dialog.nameCombo.setCurrentText("")

    # --------------------------------------------------------------------------
    def show_file(text: str) -> None:
        """Show which file will be created, or that it exists already."""
        name = layout_name(text)
        exists = (APPS_DIR / f"{name}.yaml").exists()
        ok = dialog.buttonBox.button(dialog.buttonBox.StandardButton.Ok)
        ok.setEnabled(bool(name) and not exists)
        dialog.fileLabel.setText(f"apps/{name}.yaml" + (" exists already" if exists else "") if name else "")

    dialog.nameCombo.currentTextChanged.connect(show_file)
    show_file("")
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return layout_name(dialog.nameCombo.currentText()) or None
