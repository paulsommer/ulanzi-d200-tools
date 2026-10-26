#!/bin/bash
# make-icons.sh - recreate the key images in icons/ with d200-icon.
#
# Lists every d200-icon call behind the existing key images, so they can be
# rebuilt after a change in d200-icon (font, sizes) or with other texts, and
# serves as a template for new keys. Existing images are overwritten.
# Images that were not made with d200-icon are listed at the end.
#
# Usage:  make-icons.sh
# Needs:  d200-icon (this repository), PyCharm, GIMP 3, KDE Breeze icons, Firefox.

VERSION="1.0.0"
dir=$(dirname "$(readlink -f "$0")")
icon="$dir/../d200-icon"
out="$dir/icons"
svg="$dir/svg"
pycharm=~/apps/pycharm/lib/app-client.jar   ### <--- change this to your path (your PyCharm installation)
gimp=/usr/share/gimp/3.0/icons              ### <--- change this to your path (GIMP 3 icon themes)
breeze=/usr/share/icons/breeze-dark
hicolor=/usr/share/icons/hicolor

# PyCharm: debugger and navigation (layout jetbrains-pycharm.yaml)
"$icon" "$pycharm!expui/general/left_dark.svg"               "$out/pycharm-back.png"      "Back"
"$icon" "$pycharm!expui/general/right_dark.svg"              "$out/pycharm-forward.png"   "Forward"
"$icon" "$pycharm!expui/run/debug_dark.svg"                  "$out/pycharm-debug.png"     "Debug"
"$icon" "$pycharm!expui/run/resume_dark.svg"                 "$out/pycharm-resume.png"    "Resume"
"$icon" "$pycharm!expui/run/stepOver_dark.svg"               "$out/pycharm-step-over.png" "Step Over"
"$icon" "$svg/pycharm-step-into-my-code.svg"                 "$out/pycharm-step-into.png" "Step Into|My Code"
"$icon" "$pycharm!expui/run/stepOut_dark.svg"                "$out/pycharm-step-out.png"  "Step Out"
"$icon" "$pycharm!expui/general/search_dark.svg"             "$out/pycharm-search.png"    "Search"
"$icon" "$pycharm!actions/findEntireFile_dark.svg"           "$out/pycharm-usages.png"    "Find Usages"
"$icon" "$pycharm!expui/gutter/implementedMethod_dark.svg"   "$out/pycharm-impl.png"      "Go to Impl."

# GIMP: tools and edit functions (layout gimp.yaml)
"$icon" "$gimp/Legacy/scalable/apps/gimp-tool-crop.svg"        "$out/gimp-crop.png"        "Zuschneiden"
"$icon" "$gimp/Legacy/scalable/apps/gimp-tool-eraser.svg"      "$out/gimp-eraser.png"      "Radierer"
"$icon" "$gimp/Legacy/scalable/apps/gimp-tool-move.svg"        "$out/gimp-move.png"        "Verschieben"
"$icon" "$gimp/Legacy/scalable/apps/gimp-tool-paintbrush.svg"  "$out/gimp-paintbrush.png"  "Pinsel"
"$icon" "$gimp/Legacy/scalable/apps/gimp-tool-rect-select.svg" "$out/gimp-rect-select.png" "Rechteck-|auswahl"
"$icon" "$gimp/Legacy/scalable/apps/gimp-tool-text.svg"        "$out/gimp-text.png"        "Text"
"$icon" "$gimp/Default/scalable/apps/edit-undo.svg"            "$out/gimp-undo.png"        "Rückgängig"
"$icon" "$gimp/Default/scalable/apps/edit-redo.svg"            "$out/gimp-redo.png"        "Wiederholen"
"$icon" "$gimp/Default/scalable/apps/gimp-selection-none.svg"  "$out/gimp-select-none.png" "Nichts|auswählen"
"$icon" "$gimp/Default/scalable/apps/zoom-fit-best.svg"        "$out/gimp-zoom-fit.png"    "Bild|einpassen"

# General keys (default.yaml, konsole.yaml)
"$icon" "$breeze/actions/22/edit-copy-symbolic.svg"  "$out/copy.png"     "Kopieren"
"$icon" "$breeze/actions/22/edit-paste.svg"          "$out/paste.png"    "Einfügen"
"$icon" "$breeze/apps/48/utilities-terminal.svg"     "$out/terminal.png" "Konsole"
"$icon" "$hicolor/256x256/apps/firefox.png"          "$out/firefox.png"  "Firefox"

# Not made with d200-icon:
#   back, camera, custom, keyboard, obs, record, scene, stream, vscode
#       copied unchanged from ulanzi-d200-linux/icons/
#   media-previous, media-playpause, media-next, ctrl-shift-f1
#       rendered by ulanzi-daemon from an icon_spec and renamed (see README, "Pitfalls")
#   blank.png (196x196), blank-wide.png (458x196)
#       plain black images
