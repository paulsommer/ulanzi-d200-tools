#!/bin/bash
# d200-key - send a key combination or a sequence of them via ydotool (works on Wayland and X11).
#
# Used by the Ulanzi D200 manager (~/.config/ulanzi/config.yaml) as a
# "command" action, because its built-in "key" action needs xdotool (X11 only).
#
# Usage:  d200-key ctrl+shift+f1
#         d200-key alt+tab
#         d200-key m right up*3 enter 6     (sequence: one combination per argument,
#                                            *n repeats it n times)
# Key names are the KEY_* names from linux/input-event-codes.h (case-insensitive),
# plus the aliases ctrl, shift, alt, altgr, super/meta/win.

VERSION="1.1.0"
header=/usr/include/linux/input-event-codes.h

if [ $# -lt 1 ]; then
    echo "Usage: d200-key <key>[+<key>...][*<count>] ...   e.g. d200-key ctrl+shift+f1, d200-key m right up*3 enter" >&2
    exit 2
fi

# --------------------------------------------------------------------------
# Append the press and release events of one combination (e.g. CTRL+SHIFT+C) to "args".
add_combination() {
    local codes=() key code keys i
    IFS='+' read -ra keys <<< "$1"
    for key in "${keys[@]}"; do
        case "$key" in
            CTRL)            key=LEFTCTRL ;;
            SHIFT)           key=LEFTSHIFT ;;
            ALT)             key=LEFTALT ;;
            ALTGR)           key=RIGHTALT ;;
            SUPER|META|WIN)  key=LEFTMETA ;;
        esac
        code=$(awk -v name="KEY_$key" '$1 == "#define" && $2 == name { print $3; exit }' "$header")
        if [[ ! "$code" =~ ^[0-9]+$ ]]; then
            echo "d200-key: unknown key '$key'" >&2
            exit 1
        fi
        codes+=("$code")
    done
    # Press all keys in order, release in reverse order
    for code in "${codes[@]}"; do args+=("$code:1"); done
    for (( i=${#codes[@]}-1; i>=0; i-- )); do args+=("${codes[i]}:0"); done
}

# All events go into one ydotool call, so a sequence is sent without gaps
args=()
for combination in "${@^^}"; do
    count=1
    if [[ "$combination" == *'*'* ]]; then
        count=${combination##*'*'}
        combination=${combination%'*'*}
        if [[ ! "$count" =~ ^[0-9]+$ ]]; then
            echo "d200-key: invalid repeat count in '$combination*$count'" >&2
            exit 1
        fi
    fi
    # Resolve the key codes once, then repeat the events
    start=${#args[@]}
    add_combination "$combination"
    events=("${args[@]:start}")
    for (( n=1; n<count; n++ )); do args+=("${events[@]}"); done
done

exec ydotool key "${args[@]}"
