# Function Catalog

Dependencies: bash, ydotool, awk, librsvg2-bin (rsvg-convert), unzip, linux-libc-dev (input-event-codes.h), python3-dbus, python3-gi, systemd, KWin (Plasma 6), ulanzi-d200-linux (racerxdl); layout editor: PySide6-Essentials, PyYAML (`layout-editor/requirements.txt`, venv `layout-editor/.venv`).

## d200-key.sh

Translates `ctrl+shift+f1` or a sequence `m right up*3 enter` (one combination per argument, `*n` = repeat) into the
key events of one ydotool call (codes looked up in `/usr/include/linux/input-event-codes.h`, aliases
ctrl/shift/alt/altgr/super).

| Line | Function | Description |
|------|----------|-------------|
| 24 | `add_combination` | Appends the press events of one combination in order and the release events in reverse order to `args`; exits on unknown keys |

## d200-raise.py

| Line | Function | Description |
|------|----------|-------------|
| 65 | `ResultReceiver` | D-Bus object on `/` of the process's own (unique-name) connection; the one-shot KWin script calls its `result` method |
| 69 | `ResultReceiver.__init__` | Registers the object and keeps the main loop to stop |
| 77 | `ResultReceiver.result` | D-Bus method `io.github.paulsommer.D200Raise.result(b)`: stores whether a window was activated and quits the loop |
| 88 | `main` | Loads a one-shot KWin script that filters `workspace.stackingOrder` by window class (full or last dot component, like `layout_for` in d200-focus) and activates the topmost match – or, if a match is already active, lowers that one below all windows (`workspace.slotWindowLower`) and activates the next match below it (round robin); waits up to 2 s for the callback, unloads the script and starts the command (detached session) if no window matched; the daemon already runs command actions in an own systemd scope, so the daemon restart by d200-focus does not kill it |

## d200-icon.sh

No functions. Option `-b <colour>` sets the background (default black). Reads an SVG, PNG or JPG file (type by extension), an SVG from `archive.jar!path.svg` (via `unzip -p`), or
none with `-`, and builds a wrapper SVG (image as base64 data URI, scaled to fit with aspect ratio kept, plus optional
text lines split at `|`) that `rsvg-convert` renders as a
196×196 button image. Icon size and margins come from the layout values at the top of the script (marked `### <--- layout`); with two or
more text lines the text moves closer to the bottom edge (`text_bottom_multi`) and the icon grows by that difference;
text-only is centered.

## d200-layout-editor.sh

No functions. Bash starter: runs `layout-editor/main_window.py` with the Python of `layout-editor/.venv`
(follows the `~/.local/bin` symlink).

## layout-editor/config.py

No functions. Paths (`~/.config/ulanzi`, `apps/`, `~/.config/d200-focus/brightness.json` with its defaults, real `my-layouts/` folder as base for `./` paths, `d200-icon`,
`ulanzi-manager`, `~/.local/bin`) and sizes (14 buttons, wide index 13, preview key size).

## layout-editor/layout_file.py

| Line | Function | Description |
|------|----------|-------------|
| 30 | `Layout` | Dataclass: layout name, header comment lines, YAML data, one description per button |
| 40 | `Layout.buttons` | Button list of the YAML data (always 14 entries, `None` = unset) |
| 46 | `empty_layout` | New layout with the usual settings, 13 blank keys and the clock |
| 62 | `empty_button` | Disabled key with `blank.png` (like the free keys in the layouts) |
| 68 | `load` | Reads a layout with `yaml.safe_load`; header comment and `# n: description` comments via regex, because PyYAML drops comments |
| 95 | `dump` | Writes the layout in the hand-written format (top-level order kept, `# n:` per button, editor-internal `_` keys skipped); round trip of the existing layouts is byte-identical |
| 117 | `save` | Writes `dump()` to a file |
| 123 | `with_brightness` | Sets the global brightness in layout text for the daemon (replaces a leftover `brightness:` line); same as `write_layout` in `d200-focus` |
| 132 | `_dump_yaml` | `yaml.safe_dump` in block style, no line wrapping, Unicode kept |
| 138 | `_add_path_hints` | Appends `### <--- change this to your path` to `cmd` lines calling `~/.local/bin/d200-*` and to `d200_icon` sources in `~/` |
| 152 | `function_of` | Button → editor function (`empty`, `key`, `raise`, `command`) and its value; only single plain `d200-key` / `d200-raise` calls are split up, everything else stays a command |
| 177 | `split_raise` | d200-raise arguments → (window class, program) for the editor form; a single word is the program with empty class |
| 192 | `join_raise` | Window class and program → d200-raise arguments (inverse of `split_raise`); without class, a program with arguments gets its first word's name as class |
| 205 | `command_for` | Function and value → `cmd` string (inverse of `function_of`) |

## layout-editor/key_widget.py

| Line | Function | Description |
|------|----------|-------------|
| 18 | `KeyWidget` | Promoted QLabel in `main_window.ui`: key preview with signals `clicked`, `swapped`, `menu_requested`; never touches layout data |
| 26 | `KeyWidget.__init__` | Centered label, accepts drops, custom context menu |
| 39 | `KeyWidget.index` | Button index (getter) |
| 45 | `KeyWidget.index` (setter) | Sets index; the wide display (13) gets 458:196 size and takes no drops |
| 52 | `KeyWidget.set_image` | Shows an image scaled to the key, or an empty key |
| 62 | `KeyWidget.set_selected` | Blue border for the key shown in the properties panel |
| 68 | `KeyWidget.mousePressEvent` | Emits `clicked`, remembers the drag start |
| 76 | `KeyWidget.mouseMoveEvent` | Starts a drag (MIME `application/x-d200-key` with the index) after the drag distance; not for the wide display |
| 91 | `KeyWidget.dragEnterEvent` | Accepts only drags of editor keys |
| 97 | `KeyWidget.dropEvent` | Emits `swapped(source, target)` |

## layout-editor/new_layout_dialog.py

| Line | Function | Description |
|------|----------|-------------|
| 24 | `layout_name` | Window class → layout name as `d200-focus` matches it (`org.kde.okular` → `okular`) |
| 30 | `recent_window_classes` | Layout names of recently active windows without own layout, newest first, from `journalctl --user -u d200-focus` (`focus: <class> ->` lines) |
| 44 | `ask_layout_name` | Loads `new_layout_dialog.ui`, offers the recent classes in an editable combo box, shows the target file and disables OK for empty or existing names |
| 60 | `ask_layout_name.show_file` | Updates the file hint and the OK button while typing |

## layout-editor/main_window.py

| Line | Function | Description |
|------|----------|-------------|
| 61 | `resolve` | Layout path (`./...`, `~/...`, absolute) → file; `./` relative to the real `my-layouts/` folder |
| 68 | `layout_path` | Chosen file → path as written into a layout (`./` inside `my-layouts/`, `~/` inside home) |
| 110 | `render_icon` | Runs `d200-icon` for a `d200_icon` entry (source with `~`/`./` resolved, also before `!` of JAR paths; empty source = text only; `background` → `-b`); returns the error text |
| 132 | `validate` | Writes the layout next to `config.yaml` (so `./icons/` resolves) and runs `ulanzi-manager validate`, like `d200-focus` |
| 148 | `with_previews` | Copy of a layout that uses the unsaved preview images; for test and validation before saving |
| 82 | `load_key_names` | Linux key code → name table from `input-event-codes.h`; the recorder uses physical keys like `d200-key` |
| 98 | `compress_keys` | Recorded combinations → d200-key arguments, repeats as `up*3` |
| 180 | `set_icon` | Sets the `d200_icon` entry directly after `image`, or removes it |
| 162 | `load_brightness` | Global brightness settings from `brightness.json`, defaults if the file does not exist |
| 168 | `send_config` | Replaces `config.yaml` and restarts `ulanzi-daemon` (test button, brightness change) |
| 189 | `MainWindow` | Logic of the window loaded from `main_window.ui` with `QUiLoader` (`KeyWidget` registered as custom widget) |
| 193 | `MainWindow.__init__` | Loads the UI, connects keys, toolbar, form and menu, sets the brightness controls from the saved settings, opens `default` |
| 258 | `MainWindow.show_mode` | Labels the day/night button `< day` or `night >`; the arrow points at the spin box in use |
| 263 | `MainWindow.active_brightness` | Value selected by the day/night button |
| 269 | `MainWindow.brightness_changed` | Writes `brightness.json` right away (not part of a layout, so no unsaved-changes flag) and starts the 500 ms timer for `send_brightness` |
| 282 | `MainWindow.send_brightness` | If the active value changed: sets it in the current `config.yaml` and restarts the daemon, so a layout sent with **Test** stays |
| 296 | `MainWindow.eventFilter` | Asks about unsaved changes before the window closes; while recording, takes key presses in the value field (also shortcut overrides like Ctrl+Q) |
| 317 | `MainWindow.record_keys` | ● Record toggled: starts recording (value field cleared, read-only, event filter) or stops and stores the sequence |
| 337 | `MainWindow.record_key` | Adds a pressed key as `ctrl+shift+c` (name from the scan code, modifier aliases); skips auto-repeat and lone modifiers |
| 350 | `MainWindow.status` | Status bar message |
| 355 | `MainWindow.set_dirty` | Unsaved-changes flag, shown as `*` in the window title |
| 361 | `MainWindow.confirm_discard` | Save / Discard / Cancel question; True if it is fine to continue |
| 377 | `MainWindow.fill_layout_combo` | Lists `apps/*.yaml` and opens the given layout |
| 389 | `MainWindow.open_layout` | Loads a layout after `confirm_discard`, refreshes all keys |
| 405 | `MainWindow.refresh_key` | Shows preview, image or blank tile of a button |
| 413 | `MainWindow.select` | Marks a key and fills the properties panel (key form or wide display form); stops a running recording first |
| 446 | `MainWindow.show_value_hint` | Enables and explains the value field for the selected function; shows the class field and the label "Class / Program" for *Program*, the ● Record button for *Key* |
| 462 | `MainWindow.apply_form` | Builds the selected button from the form on every edit; keeps fields the editor does not show; new keys start with `blank.png` (the validator needs an image) |
| 505 | `MainWindow.icon_changed` | Stores icon fields and starts the 400 ms render timer |
| 511 | `MainWindow.render_preview` | Renders the selected key with `d200-icon` into the temporary preview folder (`_preview`) |
| 529 | `MainWindow.browse_icon` | File dialog for the icon source (SVG/PNG/JPG) |
| 539 | `MainWindow.choose_background` | Qt colour dialog for the background colour of the selected key (stored as `d200_icon.background`) |
| 548 | `MainWindow.browse_wide_image` | File dialog for the wide display image |
| 557 | `MainWindow.swap` | Exchanges two keys and their descriptions (drag & drop) |
| 568 | `MainWindow.show_key_menu` | Context menu: copy key into the editor clipboard, paste (also in another layout), clear |
| 596 | `MainWindow.create_layout` | New blank layout or copy of the current one, written right away so `d200-focus` can use it |
| 621 | `MainWindow.image_in_use` | True if another key (any layout) uses the image with a different `d200_icon`; such shared images are not overwritten |
| 635 | `MainWindow.new_image_name` | Unused path `./icons/<layout>-<description>.png` |
| 647 | `MainWindow.save` | Validates (with previews), copies previews to `icons/` (own file for shared or blank images), writes the layout |
| 670 | `MainWindow.test` | Validates the current layout with previews and sends it with the active brightness via `send_config` |
| 686 | `MainWindow.render_all` | Renders every image with a `d200_icon` entry in all layouts again (replaces `make-icons.sh`) |
| 709 | `main` | Creates the QApplication (desktop file name `d200-layout-editor`) and shows the window |

## d200-focus.py

| Line | Function | Description |
|------|----------|-------------|
| 67 | `layout_for` | Maps a window to a layout name: tries the full window class, its last dot component (`org.kde.konsole` → `konsole`), then the KWin desktop file name and its last component in `~/.config/ulanzi/apps/`, else `default` |
| 91 | `current_brightness` | Active brightness (day or night value) from `~/.config/d200-focus/brightness.json`, 100 without the file; read on every layout switch |
| 103 | `write_layout` | Copies a layout and sets the global brightness in the copy (replaces a leftover `brightness:` line) |
| 118 | `FocusService` | D-Bus object `io.github.paulsommer.D200Focus` on the session bus, called by the KWin script and by `d200-wide-black.service` |
| 122 | `FocusService.__init__` | Registers the bus name and object path `/` |
| 133 | `FocusService.activated` | D-Bus method `activated(ss)` (window class, desktop file name) called on every window activation; stores the wanted layout and restarts the 300 ms debounce timer; logs `focus: <class> -> <layout> ...` (parsed by the layout editor) |
| 150 | `FocusService.prime` | D-Bus method (start, resume, USB plug-in): holds back layout switches and sends the black wide display background after 2 s, so the firmware clock is not drawn on the Ulanzi logo |
| 164 | `FocusService.on_sleep` | logind `PrepareForSleep` handler on the system bus; calls `prime` after resume |
| 174 | `FocusService.send_wide_black` | Copies `~/.config/ulanzi/wide-black.yaml` (link to `my-layouts/`) to config.yaml with `write_layout`, restarts ulanzi-daemon and schedules `prime_done` after 1 s |
| 183 | `FocusService.prime_done` | Ends priming and applies the pending layout again |
| 190 | `FocusService.apply` | If the layout changed (and no priming is running): validates it with `ulanzi-manager validate` (copy next to config.yaml so `./icons/` resolves), rejects broken layouts with a log message, otherwise replaces config.yaml and restarts ulanzi-daemon |
| 221 | `load_kwin_script` | Writes the KWin script (reports `resourceClass` and `desktopFileName` of `workspace.windowActivated` via `callDBus`) to `$XDG_RUNTIME_DIR` and loads it, unloading a leftover instance first |
| 238 | `unload_kwin_script` | Unloads the KWin script when the service stops |
| 245 | `watch_kwin` | Loads the KWin script if `org.kde.KWin` is on the bus and again on every `NameOwnerChanged` with a new owner (KWin restart, KWin starting after d200-focus); idea from Ulanzi-Deck-Linux `focus/kwin.rs` |
| 253 | `watch_kwin.on_owner_changed` | Signal handler: loads the script when KWin got a new owner |
| 267 | `main` | Sets up the GLib D-Bus main loop, primes the wide display, subscribes to logind `PrepareForSleep`, starts `watch_kwin`, quits on SIGTERM/SIGINT |
