#!/usr/bin/env python3
"""Desktop clock + todo/reminder widget."""
import json, os, re, fcntl, sys, datetime as dt
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Gio, Pango

DIR = os.environ.get("DESKLET_DIR", os.path.expanduser("~/.local/share/desklet"))
DATA = os.path.join(DIR, "todos.json")
POS = os.path.join(DIR, "pos.json")
AUTOSTART = os.path.expanduser("~/.config/autostart/desklet.desktop")
COLLAPSED_LINES = 2  # long notes show this many lines until clicked
WIDTH = 300
MIN_WIDTH, MIN_HEIGHT = 220, 200
GRIP = 14  # px from any edge that resizes instead of moving
EDGES = {"n": Gdk.WindowEdge.NORTH, "s": Gdk.WindowEdge.SOUTH, "e": Gdk.WindowEdge.EAST,
         "w": Gdk.WindowEdge.WEST, "ne": Gdk.WindowEdge.NORTH_EAST, "nw": Gdk.WindowEdge.NORTH_WEST,
         "se": Gdk.WindowEdge.SOUTH_EAST, "sw": Gdk.WindowEdge.SOUTH_WEST}
DEFAULT_HEIGHT = 460

# libadwaita palette, so it looks like a native GNOME surface.
# Solid card: only the rounded corners are see-through, so it reads on any wallpaper.
PALETTES = {
    "dark":  dict(window="#222226", cardbg="rgba(255,255,255,0.05)", border="rgba(255,255,255,0.10)",
                  fg="#ffffff", destructive="#ff938c"),
    "light": dict(window="#fafafb", cardbg="#ffffff", border="rgba(0,0,6,0.12)",
                  fg="rgba(0,0,6,0.8)", destructive="#c30000"),
}
ACCENTS = {"blue": "#3584e4", "teal": "#2190a4", "green": "#3a944a", "yellow": "#c88800",
           "orange": "#ed5b00", "red": "#e62d42", "pink": "#d56199", "purple": "#9141ac",
           "slate": "#6f8396"}

CSS = """
window {{ background-color: transparent; }}
#card {{ background-color: {window}; color: {fg}; border: 1px solid {border}; border-radius: 14px; }}
.segment {{ padding: 14px 16px; }}
#clockbox {{ padding: 18px 18px 16px; }}
#clock {{ font-size: 46px; font-weight: 300; font-feature-settings: "tnum"; }}
#date {{ font-size: 13px; opacity: 0.6; }}
separator.seg {{ background-color: {border}; min-height: 1px; margin: 0; }}
#head {{ font-size: 13px; font-weight: bold; }}
#count {{ background-color: alpha({accent}, 0.18); color: {accent_fg}; border-radius: 99px;
          padding: 1px 8px; font-size: 11px; font-weight: bold; }}
.boxed {{ background-color: {cardbg}; border: 1px solid {border}; border-radius: 12px; }}
.boxed revealer:not(:last-child) .row {{ border-bottom: 1px solid {border}; }}
.boxed revealer:first-child .row {{ border-radius: 11px 11px 0 0; }}
.boxed revealer:last-child .row {{ border-radius: 0 0 11px 11px; }}
.boxed revealer:first-child:last-child .row {{ border-radius: 11px; }}
.row {{ padding: 7px 6px 7px 12px; min-height: 28px; }}
.row:hover {{ background-color: alpha({fg}, 0.04); }}
.row checkbutton {{ padding: 0; margin: 2px 4px 0 0; }}
.task-text {{ font-size: 13px; padding: 2px 4px; }}
.row.done .task-text {{ opacity: 0.5; text-decoration-line: line-through; }}
.row check {{ min-width: 14px; min-height: 14px; border-radius: 99px; border: 2px solid alpha({fg}, 0.3);
              background: none; box-shadow: none; -gtk-icon-source: none; }}
.row check:hover {{ border-color: {accent}; }}
.row check:checked {{ background-color: {accent}; border-color: {accent}; color: #ffffff;
                      -gtk-icon-source: -gtk-icontheme("object-select-symbolic"); }}
.row button {{ background: none; border: none; box-shadow: none; border-radius: 99px; padding: 4px;
               min-height: 0; min-width: 0; color: {fg}; opacity: 0; }}
.row:hover button {{ opacity: 0.55; }}
.row button:hover {{ opacity: 1; background-color: alpha({destructive}, 0.15); color: {destructive}; }}
.chip {{ background-color: alpha({accent}, 0.18); color: {accent_fg}; border-radius: 99px;
         padding: 2px 8px; font-size: 11px; font-weight: bold; font-feature-settings: "tnum"; }}
.chip.late {{ background-color: alpha({destructive}, 0.18); color: {destructive}; }}
#empty {{ opacity: 0.5; padding: 14px 12px; }}
entry {{ background-color: alpha({fg}, 0.08); color: {fg}; border: none; border-radius: 8px;
         box-shadow: none; padding: 8px 10px; caret-color: {accent}; }}
entry:focus {{ box-shadow: inset 0 0 0 2px alpha({accent}, 0.6); }}
entry image {{ opacity: 0.55; }}
entry selection {{ background-color: alpha({accent}, 0.3); }}
scrolledwindow, viewport {{ background: none; border: none; }}
scrollbar {{ background: none; border: none; }}
scrollbar slider {{ background-color: alpha({fg}, 0.25); min-width: 4px; border-radius: 4px; }}
"""

def load(path, default):
    try:
        with open(path) as f: return json.load(f)
    except Exception: return default

def parse_time(text):
    """'buy milk @17:30' or 'call mom in 20m' / 'in 2h' -> (text, iso time or None)."""
    m = re.search(r"\s*@\s*(\d{1,2}):(\d{2})\s*$", text)
    now = dt.datetime.now()
    if m:
        t = now.replace(hour=int(m[1]), minute=int(m[2]), second=0, microsecond=0)
        if t <= now: t += dt.timedelta(days=1)
        return text[:m.start()].strip(), t.isoformat()
    m = re.search(r"\s+in\s+(\d+)\s*(m|min|h|hr)s?\s*$", text)
    if m:
        delta = dt.timedelta(hours=int(m[1])) if m[2].startswith("h") else dt.timedelta(minutes=int(m[1]))
        return text[:m.start()].strip(), (now + delta).replace(microsecond=0).isoformat()
    return text.strip(), None

def set_autostart(on):
    try:
        with open(AUTOSTART) as f: lines = f.read().splitlines()
    except OSError: return
    lines = [l for l in lines if not l.startswith("X-GNOME-Autostart-enabled=")]
    lines.append("X-GNOME-Autostart-enabled=" + ("true" if on else "false"))
    with open(AUTOSTART, "w") as f: f.write("\n".join(lines) + "\n")

def run(argv):
    # GLib reaps the child itself, so no zombie processes accumulate
    try: GLib.spawn_async(argv, flags=GLib.SpawnFlags.SEARCH_PATH
                          | GLib.SpawnFlags.STDOUT_TO_DEV_NULL | GLib.SpawnFlags.STDERR_TO_DEV_NULL)
    except GLib.Error: pass

class Desklet(Gtk.Window):
    def __init__(self):
        super().__init__(title="Desklet")
        self.todos = [t for t in load(DATA, []) if not t.get("done")]
        self.expanded = set()  # id() of tasks whose full text is shown
        self.set_decorated(False)
        self.set_keep_below(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.stick()
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual: self.set_visual(visual)
        self.set_app_paintable(True)

        # follow the system light/dark setting, live
        self.css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_screen(screen, self.css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.iface = Gio.Settings.new("org.gnome.desktop.interface")
        for key in ("color-scheme", "accent-color"):
            self.iface.connect("changed::" + key, lambda *a: self.apply_theme())
        self.apply_theme()

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="card", margin=2)
        card.set_size_request(MIN_WIDTH, -1)
        ev = Gtk.EventBox(); ev.add(card)
        ev.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        ev.connect("button-press-event", self.on_press)
        ev.connect("motion-notify-event", self.on_motion)
        self.cursors = {}
        self.add(ev)

        # segment 1: clock
        clockbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="clockbox")
        self.clock = Gtk.Label(name="clock", xalign=0)
        self.date = Gtk.Label(name="date", xalign=0)
        clockbox.add(self.clock); clockbox.add(self.date)
        card.add(clockbox)
        card.add(self.separator())

        # segment 2: tasks, as a GNOME-style boxed list
        tasks = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, vexpand=True)
        tasks.get_style_context().add_class("segment")
        head = Gtk.Box()
        head.pack_start(Gtk.Label(label="Tasks", name="head", xalign=0), False, False, 0)
        self.count = Gtk.Label(name="count", no_show_all=True)  # update_count owns its visibility
        head.pack_end(self.count, False, False, 0)
        tasks.add(head)

        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # boxed frame hugs its rows and scrolls once they outgrow the widget
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                    vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                    propagate_natural_height=True)
        scroll.add(self.list)
        frame = Gtk.Box(valign=Gtk.Align.START)
        frame.get_style_context().add_class("boxed")
        frame.pack_start(scroll, True, True, 0)
        tasks.add(frame)
        card.add(tasks)
        card.add(self.separator())

        # segment 3: add task
        addbox = Gtk.Box()
        addbox.get_style_context().add_class("segment")
        self.entry = Gtk.Entry(placeholder_text="Add task…  @17:30 or in 10m", hexpand=True)
        self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "list-add-symbolic")
        self.entry.connect("activate", self.on_add)
        addbox.add(self.entry)
        card.add(addbox)

        geo = load(POS, [60, 60])
        self.move(geo[0], geo[1])
        if len(geo) == 4: self.set_default_size(max(geo[2], MIN_WIDTH), max(geo[3], MIN_HEIGHT))
        else: self.set_default_size(WIDTH, DEFAULT_HEIGHT)
        self._pos_timer = 0
        self.connect("configure-event", self.on_configure)
        self.refresh(); self.tick()
        self.connect("destroy", Gtk.main_quit)
        self.show_all()

    def apply_theme(self):
        dark = self.iface.get_string("color-scheme") == "prefer-dark"
        try: accent = ACCENTS.get(self.iface.get_string("accent-color"), ACCENTS["blue"])
        except GLib.Error: accent = ACCENTS["blue"]
        # accent tinted toward the background so text on it stays readable
        accent_fg = f"mix({accent}, #ffffff, 0.3)" if dark else f"mix({accent}, #000000, 0.15)"
        self.css.load_from_data(CSS.format(accent=accent, accent_fg=accent_fg,
                                           **PALETTES["dark" if dark else "light"]).encode())

    @staticmethod
    def separator():
        sep = Gtk.Separator()
        sep.get_style_context().add_class("seg")
        return sep

    def edge(self, w, e):
        """Resize edge under the pointer, or None to move the window."""
        a = w.get_allocation()
        ns = "n" if e.y <= GRIP else "s" if e.y >= a.height - GRIP else ""
        ew = "w" if e.x <= GRIP else "e" if e.x >= a.width - GRIP else ""
        return (ns + ew) or None

    def on_motion(self, w, e):
        edge = self.edge(w, e)
        name = edge + "-resize" if edge else "default"
        if name not in self.cursors:
            self.cursors[name] = Gdk.Cursor.new_from_name(w.get_display(), name)
        w.get_window().set_cursor(self.cursors[name])

    def on_press(self, w, e):
        if e.button == 3: return self.show_menu(e)
        if e.button != 1: return
        edge = self.edge(w, e)
        if edge is None: self.begin_move_drag(e.button, int(e.x_root), int(e.y_root), e.time)
        else: self.begin_resize_drag(EDGES[edge], e.button, int(e.x_root), int(e.y_root), e.time)

    def show_menu(self, e):
        menu = Gtk.Menu()
        for label, cb in (("Close", lambda *a: self.destroy()),
                          ("Remove from desktop", lambda *a: (set_autostart(False), self.destroy()))):
            item = Gtk.MenuItem(label=label); item.connect("activate", cb); menu.append(item)
        menu.attach_to_widget(self, None)
        menu.show_all(); menu.popup_at_pointer(e)
        self._menu = menu  # keep a reference so it isn't collected while open
        return True

    def on_configure(self, w, e):
        # debounce: save position once, 2s after the window stops moving
        if self._pos_timer: GLib.source_remove(self._pos_timer)
        self._pos_timer = GLib.timeout_add_seconds(2, self.save_pos)

    def save_pos(self):
        self._pos_timer = 0
        with open(POS, "w") as f: json.dump(list(self.get_position()) + list(self.get_size()), f)
        return False

    def save(self):
        with open(DATA, "w") as f: json.dump(self.todos, f, indent=1)

    def refresh(self):
        for c in self.list.get_children(): c.destroy()
        now = dt.datetime.now()
        for t in self.todos:
            row = Gtk.Box(spacing=6)
            row.get_style_context().add_class("row")
            # revealer lets the row slide shut before it's removed
            rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_UP,
                               transition_duration=300, reveal_child=True)
            rev.add(row)
            # circle marks done; the text is separate so clicking it expands instead
            cb = Gtk.CheckButton(valign=Gtk.Align.START)
            cb.connect("toggled", self.on_done, t, rev)
            row.pack_start(cb, False, False, 0)
            row.pack_start(self.task_text(t), True, True, 0)
            rm = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
            rm.set_valign(Gtk.Align.START)
            rm.set_tooltip_text("Delete"); rm.connect("clicked", lambda b, t=t, rev=rev: self.dismiss(t, rev))
            row.pack_end(rm, False, False, 0)
            if t.get("due"):
                due = dt.datetime.fromisoformat(t["due"])
                fmt = "%H:%M" if due.date() == now.date() else "%a %H:%M"
                chip = Gtk.Label(label=due.strftime(fmt), valign=Gtk.Align.START)
                chip.get_style_context().add_class("chip")
                if due <= now: chip.get_style_context().add_class("late")
                row.pack_end(chip, False, False, 0)
            self.list.add(rev)
        self.update_count()
        self.list.show_all()

    def task_text(self, t):
        # tiny width request + hexpand: wraps to whatever width the widget is resized to
        lbl = Gtk.Label(label=t["text"], xalign=0, wrap=True, width_chars=1, max_width_chars=1,
                        wrap_mode=Pango.WrapMode.WORD_CHAR)
        lbl.get_style_context().add_class("task-text")
        ev = Gtk.EventBox(); ev.add(lbl)
        ev.connect("realize", lambda w: w.get_window().set_cursor(
            Gdk.Cursor.new_from_name(w.get_display(), "pointer")))
        ev.connect("button-press-event", self.on_text_click, t, lbl)
        self.set_expanded(lbl, id(t) in self.expanded)
        return ev

    def set_expanded(self, lbl, open_):
        lbl.set_lines(-1 if open_ else COLLAPSED_LINES)
        lbl.set_ellipsize(Pango.EllipsizeMode.NONE if open_ else Pango.EllipsizeMode.END)

    def on_text_click(self, w, e, t, lbl):
        if e.button != 1: return False
        key = id(t)
        open_ = key not in self.expanded
        self.expanded.add(key) if open_ else self.expanded.discard(key)
        self.set_expanded(lbl, open_)
        return True  # don't start a window drag

    def update_count(self):
        self.count.set_visible(bool(self.todos))
        self.count.set_text(str(len(self.todos)))
        if not self.todos:
            if not self.list.get_children():
                empty = Gtk.Label(label="Nothing to do 🎉", name="empty", xalign=0)
                self.list.add(empty); empty.show()

    def on_add(self, e):
        text, due = parse_time(e.get_text())
        if text:
            self.todos.append({"text": text, "due": due, "notified": False})
            self.save(); self.refresh()
        e.set_text("")

    def on_done(self, cb, t, rev):
        if not cb.get_active(): return
        cb.set_sensitive(False)
        rev.get_child().get_style_context().add_class("done")  # strike through first
        GLib.timeout_add(450, lambda: self.dismiss(t, rev) and False)

    def dismiss(self, t, rev):
        if t not in self.todos: return
        self.todos.remove(t); self.save()
        rev.connect("notify::child-revealed", self.on_hidden)
        rev.set_reveal_child(False)

    def on_hidden(self, rev, _):
        rev.destroy()
        self.update_count()

    def tick(self):
        now = dt.datetime.now()
        # only touch labels when text changes, so GTK skips needless redraws
        for lbl, txt in ((self.clock, now.strftime("%H:%M")), (self.date, now.strftime("%A, %d %B"))):
            if lbl.get_text() != txt: lbl.set_text(txt)
        fired = False
        for t in self.todos:
            if t.get("due") and not t.get("notified") \
               and dt.datetime.fromisoformat(t["due"]) <= now:
                run(["notify-send", "-u", "critical", "-i", "alarm-symbolic", "⏰ Reminder", t["text"]])
                run(["canberra-gtk-play", "-i", "alarm-clock-elapsed"])
                t["notified"] = fired = True
        if fired: self.save(); self.refresh()
        # sleep until the next minute boundary instead of polling every second
        GLib.timeout_add_seconds(60 - dt.datetime.now().second, self.tick)
        return False

if __name__ == "__main__":
    # one desklet at a time: a second launch just exits
    lock = open(os.path.join(DIR, ".lock"), "w")
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: sys.exit(0)
    set_autostart(True)  # launching it again from the app grid brings it back at login too
    Desklet(); Gtk.main()
