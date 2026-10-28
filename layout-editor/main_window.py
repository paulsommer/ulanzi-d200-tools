"""Main window of the D200 layout editor.

The window itself comes from main_window.ui (Qt Designer); this module loads it
and holds the logic: loading/saving layouts, the properties panel, previews
rendered with d200-icon, swapping and copying keys, and the test button.

Key images of the layouts are made with d200-icon; source and text are kept
in the layout (button field "d200_icon"), so every image can be rendered
again. While editing, images are rendered into a temporary folder ("_preview");
they are copied to my-layouts/icons/ on saving.
"""

import copy
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtUiTools import QUiLoader
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QColorDialog, QFileDialog, QMainWindow, QMenu, QMessageBox

import layout_file as lf
from config import (APPS_DIR, BUTTON_COUNT, CONFIG_FILE, D200_ICON, ICONS_DIR, LAYOUT_ROOT, TEST_FILE,
                    ULANZI_DIR, VALIDATOR, VERSION, WIDE_INDEX)
from key_widget import KeyWidget
from new_layout_dialog import ask_layout_name

UI_FILE = Path(__file__).with_name("main_window.ui")
DEFAULT_LAYOUT = "default"
# Function combo box entries, in the order of main_window.ui
KINDS = [lf.EMPTY, lf.KEY, lf.RAISE, lf.COMMAND]
VALUE_HINTS = {
    lf.EMPTY: "",
    lf.KEY: "Key combination, e.g. ctrl+shift+c, f9, playpause (US key names, see d200-key)",
    lf.RAISE: "Window class (e.g. dolphin), optionally followed by the command to start it",
    lf.COMMAND: "Any shell command",
}
# Wait for typing to pause before rendering a preview with d200-icon
RENDER_DELAY_MS = 400


# --------------------------------------------------------------------------
def resolve(path: str) -> Path:
    """Return the file for a layout path (./icons/x.png, ~/x.svg or absolute)."""
    expanded = Path(path).expanduser()
    return expanded if expanded.is_absolute() else LAYOUT_ROOT / expanded


# --------------------------------------------------------------------------
def layout_path(path: str) -> str:
    """Return a chosen file as it is written into a layout.

    Files in my-layouts/ become ./relative, files in the home folder ~/...,
    so the layouts stay usable for other users and clones.
    """
    file = Path(path)
    for base, prefix in ((LAYOUT_ROOT, "./"), (Path.home(), "~/")):
        if file.is_relative_to(base):
            return prefix + str(file.relative_to(base))
    return str(file)


# --------------------------------------------------------------------------
def render_icon(icon: dict, out: Path) -> str:
    """Render a key image with d200-icon from a d200_icon entry.

    Args:
        icon: d200_icon entry: source (icon file, archive.jar!path.svg, or empty
            for text only), text ("|" = new line), optional background colour.
        out: Output PNG.

    Returns:
        Error message of d200-icon, empty on success.
    """
    source = icon["source"]
    if source:
        file, sep, inner = source.partition("!")
        source = str(resolve(file)) + sep + inner
    background = ["-b", icon["background"]] if icon.get("background") else []
    result = subprocess.run([str(D200_ICON), *background, source or "-", str(out), icon["text"]],
                            capture_output=True, text=True)
    return result.stderr.strip() if result.returncode else ""


# --------------------------------------------------------------------------
def validate(layout: lf.Layout) -> str:
    """Check a layout with ulanzi-manager validate, like d200-focus does before switching.

    Returns:
        The error lines, empty if the layout is valid.
    """
    check = ULANZI_DIR / ".d200-layout-check.yaml"
    check.write_text(lf.dump(layout))
    result = subprocess.run([str(VALIDATOR), "validate", str(check)], capture_output=True, text=True)
    check.unlink()
    if result.returncode == 0:
        return ""
    return "\n".join(line for line in result.stderr.splitlines() if "ERROR" in line) or result.stderr


# --------------------------------------------------------------------------
def with_previews(layout: lf.Layout) -> lf.Layout:
    """Return a copy of the layout that uses the rendered previews as images.

    Used for the test button and for validating before saving, so keys whose
    image is not saved yet are checked and shown as they will look.
    """
    layout = copy.deepcopy(layout)
    for button in layout.buttons:
        if button and button.get("_preview"):
            button["image"] = button["_preview"]
    return layout


# --------------------------------------------------------------------------
def set_icon(button: dict, icon: dict | None) -> dict:
    """Return the button with its d200_icon entry set (directly after "image") or removed."""
    items = [(k, v) for k, v in button.items() if k != "d200_icon"]
    if icon:
        position = next((i + 1 for i, (k, _) in enumerate(items) if k == "image"), 0)
        items.insert(position, ("d200_icon", icon))
    return dict(items)


class MainWindow(QObject):
    """Logic of the editor window loaded from main_window.ui."""

    # --------------------------------------------------------------------------
    def __init__(self):
        """Load the window, connect all widgets and open the default layout."""
        super().__init__()
        loader = QUiLoader()
        loader.registerCustomWidget(KeyWidget)
        self.ui: QMainWindow = loader.load(str(UI_FILE))
        self.ui.setWindowTitle(f"D200 Layout Editor {VERSION}")
        self.preview_dir = tempfile.TemporaryDirectory(prefix="d200-layout-editor-")
        self.layout: lf.Layout | None = None
        self.selected = 0
        self.dirty = False
        self.clipboard = None      # (button, description) for "paste key"
        self.updating_form = False
        self.render_timer = QTimer(singleShot=True, interval=RENDER_DELAY_MS)
        self.render_timer.timeout.connect(self.render_preview)

        self.keys: list[KeyWidget] = [self.ui.findChild(KeyWidget, f"key{i}") for i in range(BUTTON_COUNT)]
        for index, key in enumerate(self.keys):
            key.index = index
            key.clicked.connect(self.select)
            key.swapped.connect(self.swap)
            key.menu_requested.connect(self.show_key_menu)

        ui = self.ui
        ui.layoutCombo.currentTextChanged.connect(self.open_layout)
        ui.newButton.clicked.connect(lambda: self.create_layout(copy_current=False))
        ui.copyLayoutButton.clicked.connect(lambda: self.create_layout(copy_current=True))
        ui.saveButton.clicked.connect(self.save)
        ui.testButton.clicked.connect(self.test)
        ui.actionRenderAll.triggered.connect(self.render_all)
        ui.actionQuit.triggered.connect(ui.close)
        for edit in (ui.descriptionEdit, ui.valueEdit, ui.wideImageEdit):
            edit.textEdited.connect(self.apply_form)
        for edit in (ui.iconSourceEdit, ui.iconTextEdit, ui.backgroundEdit):
            edit.textEdited.connect(self.icon_changed)
        ui.functionCombo.currentIndexChanged.connect(self.apply_form)
        ui.clockRadio.toggled.connect(self.apply_form)
        ui.iconSourceBrowse.clicked.connect(self.browse_icon)
        ui.backgroundBrowse.clicked.connect(self.choose_background)
        ui.wideImageBrowse.clicked.connect(self.browse_wide_image)
        ui.installEventFilter(self)

        self.fill_layout_combo(DEFAULT_LAYOUT)

    # --------------------------------------------------------------------------
    def eventFilter(self, obj, event) -> bool:
        """Ask about unsaved changes before the window closes."""
        if obj is self.ui and event.type() == QEvent.Type.Close and not self.confirm_discard():
            event.ignore()
            return True
        return False

    # --------------------------------------------------------------------------
    def status(self, text: str) -> None:
        """Show a message in the status bar."""
        self.ui.statusbar.showMessage(text, 8000)

    # --------------------------------------------------------------------------
    def set_dirty(self, dirty: bool = True) -> None:
        """Remember unsaved changes and show them in the window title."""
        self.dirty = dirty
        self.ui.setWindowTitle(f"D200 Layout Editor {VERSION} – {self.layout.name}{' *' if dirty else ''}")

    # --------------------------------------------------------------------------
    def confirm_discard(self) -> bool:
        """Ask whether unsaved changes may be dropped (Save / Discard / Cancel).

        Returns:
            True if it is fine to continue (saved or discarded).
        """
        if not self.dirty:
            return True
        answer = QMessageBox.question(
            self.ui, "Unsaved changes", f"Save the changes in layout '{self.layout.name}'?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return answer == QMessageBox.StandardButton.Discard

    # --------------------------------------------------------------------------
    def fill_layout_combo(self, select: str) -> None:
        """List all layouts in apps/ and open `select`."""
        combo = self.ui.layoutCombo
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(sorted(p.stem for p in APPS_DIR.glob("*.yaml")))
        combo.blockSignals(False)
        combo.setCurrentText(select)
        if self.layout is None or self.layout.name != select:
            self.open_layout(select)

    # --------------------------------------------------------------------------
    def open_layout(self, name: str) -> None:
        """Load a layout into the editor; asks about unsaved changes first."""
        if not name or (self.layout and name == self.layout.name):
            return
        if not self.confirm_discard():
            self.ui.layoutCombo.blockSignals(True)
            self.ui.layoutCombo.setCurrentText(self.layout.name)
            self.ui.layoutCombo.blockSignals(False)
            return
        self.layout = lf.load(APPS_DIR / f"{name}.yaml")
        self.set_dirty(False)
        for index in range(BUTTON_COUNT):
            self.refresh_key(index)
        self.select(0)

    # --------------------------------------------------------------------------
    def refresh_key(self, index: int) -> None:
        """Show the current image of a button (preview, image or blank tile)."""
        button = self.layout.buttons[index] or {}
        path = button.get("_preview") or (button.get("image") if button.get("enabled", True) else None) \
            or button.get("background_tile")
        self.keys[index].set_image(str(resolve(path)) if path else None)

    # --------------------------------------------------------------------------
    def select(self, index: int) -> None:
        """Mark a key and fill the properties panel with its values."""
        self.selected = index
        for key in self.keys:
            key.set_selected(key.index == index)
        ui = self.ui
        wide = index == WIDE_INDEX
        ui.keyGroup.setVisible(not wide)
        ui.wideGroup.setVisible(wide)
        button = self.layout.buttons[index]
        self.updating_form = True
        if wide:
            ui.clockRadio.setChecked(not button)
            ui.wideImageRadio.setChecked(bool(button))
            ui.wideImageEdit.setText((button or {}).get("image") or "")
        else:
            ui.keyGroup.setTitle(f"Key {index}")
            ui.descriptionEdit.setText(self.layout.descriptions[index])
            icon = (button or {}).get("d200_icon") or {}
            ui.iconSourceEdit.setText(icon.get("source", ""))
            ui.iconTextEdit.setText(icon.get("text", ""))
            ui.backgroundEdit.setText(icon.get("background", ""))
            kind, value = lf.function_of(button)
            ui.functionCombo.setCurrentIndex(KINDS.index(kind))
            ui.valueEdit.setText(value)
            self.show_value_hint(kind)
        self.updating_form = False

    # --------------------------------------------------------------------------
    def show_value_hint(self, kind: str) -> None:
        """Enable the value field and explain it for the selected function."""
        self.ui.valueEdit.setEnabled(kind != lf.EMPTY)
        self.ui.valueHint.setText(VALUE_HINTS[kind])

    # --------------------------------------------------------------------------
    def apply_form(self) -> None:
        """Build the selected button from the properties panel.

        Called on every edit. Existing fields of the button that the editor
        does not show (label, icon_scale, ...) are kept. The icon fields are
        stored even for "Empty", so switching the function back keeps them.
        """
        if self.updating_form:
            return
        ui = self.ui
        index = self.selected
        old = self.layout.buttons[index]
        if index == WIDE_INDEX:
            image = ui.wideImageEdit.text().strip()
            self.layout.buttons[index] = None if ui.clockRadio.isChecked() or not image else \
                {"image": image, "label": "", "display_mode": "background", "action_enabled": False}
        else:
            kind = KINDS[ui.functionCombo.currentIndex()]
            self.show_value_hint(kind)
            self.layout.descriptions[index] = ui.descriptionEdit.text().strip()
            if kind == lf.EMPTY:
                button = lf.empty_button()
            elif old and old.get("enabled", True):
                button = dict(old)
            else:
                button = {"image": lf.BLANK_IMAGE, "label": "", "action": "command", "params": {}}
            icon = {"source": ui.iconSourceEdit.text().strip(), "text": ui.iconTextEdit.text().strip()}
            if background := ui.backgroundEdit.text().strip():
                icon["background"] = background
            if kind != lf.EMPTY:
                button = set_icon(button, icon if any(icon.values()) else None)
                button["action"] = "command"
                button["params"] = {"cmd": lf.command_for(kind, ui.valueEdit.text().strip())}
                if old and old.get("_preview"):
                    button["_preview"] = old["_preview"]
            self.layout.buttons[index] = button
        self.refresh_key(index)
        self.set_dirty()

    # --------------------------------------------------------------------------
    def icon_changed(self) -> None:
        """Store the icon fields and render the preview once typing pauses."""
        self.apply_form()
        self.render_timer.start()

    # --------------------------------------------------------------------------
    def render_preview(self) -> None:
        """Render the selected key's image with d200-icon into the preview folder."""
        index = self.selected
        button = self.layout.buttons[index]
        if not button or not button.get("d200_icon"):
            if button:
                button.pop("_preview", None)
            self.refresh_key(index)
            return
        out = Path(self.preview_dir.name) / f"{uuid.uuid4().hex}.png"
        error = render_icon(button["d200_icon"], out)
        if error:
            self.status(error)
            return
        button["_preview"] = str(out)
        self.refresh_key(index)

    # --------------------------------------------------------------------------
    def browse_icon(self) -> None:
        """Choose an icon file for the selected key."""
        current = self.ui.iconSourceEdit.text().partition("!")[0]
        start = str(resolve(current).parent) if current else "/usr/share/icons"
        path, _ = QFileDialog.getOpenFileName(self.ui, "Icon", start, "Images (*.svg *.png *.jpg *.jpeg)")
        if path:
            self.ui.iconSourceEdit.setText(layout_path(path))
            self.icon_changed()

    # --------------------------------------------------------------------------
    def choose_background(self) -> None:
        """Pick the background colour of the selected key with the Qt colour dialog."""
        current = QColor(self.ui.backgroundEdit.text().strip() or "black")
        color = QColorDialog.getColor(current, self.ui, "Background colour")
        if color.isValid():
            self.ui.backgroundEdit.setText(color.name())
            self.icon_changed()

    # --------------------------------------------------------------------------
    def browse_wide_image(self) -> None:
        """Choose the background image of the wide display."""
        path, _ = QFileDialog.getOpenFileName(self.ui, "Wide display image", str(ICONS_DIR), "PNG (*.png)")
        if path:
            self.ui.wideImageEdit.setText(layout_path(path))
            self.ui.wideImageRadio.setChecked(True)
            self.apply_form()

    # --------------------------------------------------------------------------
    def swap(self, source: int, target: int) -> None:
        """Exchange two keys (drag & drop), including their descriptions."""
        buttons, descriptions = self.layout.buttons, self.layout.descriptions
        buttons[source], buttons[target] = buttons[target], buttons[source]
        descriptions[source], descriptions[target] = descriptions[target], descriptions[source]
        self.refresh_key(source)
        self.refresh_key(target)
        self.select(target)
        self.set_dirty()

    # --------------------------------------------------------------------------
    def show_key_menu(self, index: int, pos) -> None:
        """Context menu of a key: copy, paste (also into another layout), clear."""
        if index == WIDE_INDEX:
            return
        self.select(index)
        menu = QMenu(self.ui)
        copy_action = menu.addAction("Copy key")
        paste_action = menu.addAction("Paste key")
        paste_action.setEnabled(self.clipboard is not None)
        clear_action = menu.addAction("Clear key")
        chosen = menu.exec(pos)
        if chosen == copy_action:
            self.clipboard = (copy.deepcopy(self.layout.buttons[index]), self.layout.descriptions[index])
            self.status(f"Key {index} copied")
            return
        if chosen == paste_action:
            button, description = copy.deepcopy(self.clipboard)
        elif chosen == clear_action:
            button, description = lf.empty_button(), ""
        else:
            return
        self.layout.buttons[index] = button
        self.layout.descriptions[index] = description
        self.refresh_key(index)
        self.select(index)
        self.set_dirty()

    # --------------------------------------------------------------------------
    def create_layout(self, copy_current: bool) -> None:
        """Create a new layout (blank or as copy of the current one) and open it.

        The file is written right away, so it shows up in the layout list and
        d200-focus can use it.
        """
        if not self.confirm_discard():
            return
        name = ask_layout_name(self.ui, "Copy layout" if copy_current else "New layout")
        if not name:
            return
        if copy_current:
            layout = copy.deepcopy(self.layout)
            layout.name = name
            for button in layout.buttons:
                if button:
                    button.pop("_preview", None)
        else:
            layout = lf.empty_layout(name)
        lf.save(layout, APPS_DIR / f"{name}.yaml")
        self.set_dirty(False)
        self.fill_layout_combo(name)
        self.status(f"Layout {name} created")

    # --------------------------------------------------------------------------
    def image_in_use(self, image: str, index: int, icon: dict) -> bool:
        """Check whether an image file is used by another key with a different look.

        Shared images (e.g. firefox.png in default and konsole) may only be
        overwritten if every user has the same d200_icon entry; otherwise the
        changed key gets an own file.
        """
        others = [b for i, b in enumerate(self.layout.buttons) if i != index]
        for path in APPS_DIR.glob("*.yaml"):
            if path.stem != self.layout.name:
                others += lf.load(path).buttons
        return any(b and b.get("image") == image and b.get("d200_icon") != icon for b in others)

    # --------------------------------------------------------------------------
    def new_image_name(self, index: int) -> str:
        """Return an unused image path ./icons/<layout>-<description>.png for a key."""
        icon = self.layout.buttons[index]["d200_icon"]
        base = self.layout.descriptions[index] or icon["text"] or f"key{index}"
        slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or f"key{index}"
        name, number = f"{self.layout.name}-{slug}", 1
        while (ICONS_DIR / f"{name}.png").exists():
            number += 1
            name = f"{self.layout.name}-{slug}-{number}"
        return f"./icons/{name}.png"

    # --------------------------------------------------------------------------
    def save(self) -> bool:
        """Validate the layout, copy rendered previews to icons/ and write the file.

        Returns:
            True if saved.
        """
        error = validate(with_previews(self.layout))
        if error:
            QMessageBox.warning(self.ui, "Invalid layout", error)
            return False
        for index, button in enumerate(self.layout.buttons):
            if not button or not button.get("_preview"):
                continue
            image = button.get("image")
            if not image or image == lf.BLANK_IMAGE or self.image_in_use(image, index, button["d200_icon"]):
                image = button["image"] = self.new_image_name(index)
            shutil.copyfile(button.pop("_preview"), resolve(image))
        lf.save(self.layout, APPS_DIR / f"{self.layout.name}.yaml")
        self.set_dirty(False)
        self.status(f"Layout {self.layout.name} saved")
        return True

    # --------------------------------------------------------------------------
    def test(self) -> None:
        """Send the current, possibly unsaved layout to the D200.

        Same steps as FocusService.apply() in d200-focus: validate, replace
        config.yaml, restart ulanzi-daemon. Previews are used directly from the
        temporary folder. d200-focus only switches again on the next window
        change to an application with another layout.
        """
        layout = with_previews(self.layout)
        error = validate(layout)
        if error:
            QMessageBox.warning(self.ui, "Invalid layout", error)
            return
        TEST_FILE.write_text(lf.dump(layout))
        os.replace(TEST_FILE, CONFIG_FILE)
        subprocess.run(["systemctl", "--user", "--no-block", "restart", "ulanzi-daemon.service"])
        self.status("Layout sent to the D200")

    # --------------------------------------------------------------------------
    def render_all(self) -> None:
        """Render the image of every key with a d200_icon entry in all layouts again.

        Replaces make-icons.sh: needed after changing the layout values
        (sizes, font) in d200-icon.
        """
        done, errors = set(), []
        for path in sorted(APPS_DIR.glob("*.yaml")):
            for button in lf.load(path).buttons:
                if not button or not button.get("d200_icon") or not button.get("image") or button["image"] in done:
                    continue
                done.add(button["image"])
                icon = button["d200_icon"]
                if error := render_icon(icon, resolve(button["image"])):
                    errors.append(f"{button['image']}: {error}")
        for index in range(BUTTON_COUNT):
            self.refresh_key(index)
        if errors:
            QMessageBox.warning(self.ui, "Rendering failed", "\n".join(errors))
        self.status(f"{len(done) - len(errors)} key images rendered")


# --------------------------------------------------------------------------
def main() -> None:
    """Start the editor application."""
    app = QApplication(sys.argv)
    app.setDesktopFileName("d200-layout-editor")
    window = MainWindow()
    window.ui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
