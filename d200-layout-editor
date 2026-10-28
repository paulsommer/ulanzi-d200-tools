#!/bin/bash
# d200-layout-editor - graphical editor for the Ulanzi D200 layouts in ~/.config/ulanzi/apps/.
#
# Starts layout-editor/main_window.py with the Python of layout-editor/.venv
# (PySide6, PyYAML from layout-editor/requirements.txt).

dir=$(dirname "$(readlink -f "$0")")/layout-editor
exec "$dir/.venv/bin/python" "$dir/main_window.py" "$@"
