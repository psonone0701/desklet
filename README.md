# Desklet

A small clock + to-do widget that sits on your GNOME desktop, with timed reminders.

- Big clock and date
- To-do list: tick a task to complete it, hover for the delete button, click long tasks to expand
- Reminders: end a task with `@17:30` or `in 10m` / `in 2h` and you get a notification and a sound when it's due
- Follows the system light/dark mode and accent color
- Drag to move, drag the edges to resize; position and size are remembered
- Starts at login; right-click for **Close** or **Remove from desktop**

## Install

1. Download `desklet-vX.Y.Z.tar.gz` from the [latest release](../../releases/latest).
2. Extract it and run the installer:

```sh
tar xzf desklet-*.tar.gz
cd desklet-*/
./install.sh
```

It installs for your user only (no sudo needed), into `~/.local/share/desklet`.

### Requirements

Ubuntu / Debian with GNOME. These are usually already installed:

```sh
sudo apt install python3-gi gir1.2-gtk-3.0 libnotify-bin gnome-session-canberra
```

On Wayland it runs through XWayland (`GDK_BACKEND=x11`), so it can stay below other windows.

## Usage

| Do this | To |
|---|---|
| Type in the box and press Enter | Add a task |
| `water plants @18:00` | Reminder at 18:00 (tomorrow if that time has passed) |
| `stretch in 20m`, `call back in 2h` | Reminder after a delay |
| Click the circle | Complete the task |
| Click the task text | Expand / collapse a long task |
| Right-click the widget | Close, or remove it from the desktop |

Removed it and want it back? Open **Desklet** from the app grid.

## Uninstall

```sh
./uninstall.sh          # keeps your tasks
./uninstall.sh --purge  # deletes everything
```

## License

MIT
