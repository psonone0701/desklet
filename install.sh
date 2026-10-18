#!/bin/sh
# Installs Desklet for the current user and starts it.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/desklet"
mkdir -p "$DEST" "$HOME/.local/share/applications" "$HOME/.config/autostart"
install -m 755 "$SRC/desklet.py" "$DEST/desklet.py"

ENTRY="[Desktop Entry]
Type=Application
Name=Desklet
Comment=Desktop clock and todo/reminders
Exec=env GDK_BACKEND=x11 MALLOC_ARENA_MAX=2 python3 $DEST/desklet.py
Icon=alarm-symbolic
X-GNOME-Autostart-enabled=true"
printf '%s\n' "$ENTRY" > "$HOME/.local/share/applications/desklet.desktop"
printf '%s\n' "$ENTRY" > "$HOME/.config/autostart/desklet.desktop"

# start it now (a second copy exits on its own if one is already running)
env GDK_BACKEND=x11 MALLOC_ARENA_MAX=2 nohup python3 "$DEST/desklet.py" >/dev/null 2>&1 &
echo "Desklet installed. Right-click it for Close / Remove from desktop."
