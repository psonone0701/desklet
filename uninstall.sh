#!/bin/sh
# Removes Desklet. Your tasks are kept unless you pass --purge.
pkill -f "$HOME/.local/share/desklet/desklet.py" 2>/dev/null || true
rm -f "$HOME/.local/share/applications/desklet.desktop" "$HOME/.config/autostart/desklet.desktop"
if [ "$1" = "--purge" ]; then
    rm -rf "$HOME/.local/share/desklet"
else
    rm -f "$HOME/.local/share/desklet/desklet.py"
    echo "Tasks kept in ~/.local/share/desklet (use --purge to delete them)."
fi
echo "Desklet uninstalled."
