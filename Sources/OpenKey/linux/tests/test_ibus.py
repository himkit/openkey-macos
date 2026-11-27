"""End-to-end test of the IBus engine on a private ibus-daemon (does not touch the
desktop's running IBus). Run: python3 -I tests/test_ibus.py

A fake text field is driven through a real IBusInputContext: keys go to the daemon,
which runs openkey_ibus.py; commit / preedit / delete-surrounding signals are applied
to the fake field.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from openkey_core import CHAR_TO_KEY  # noqa: E402

tmp = tempfile.mkdtemp(prefix="openkey-ibus-test-", dir=os.environ.get("OPENKEY_TEST_TMP"))
address = "unix:abstract=openkey-test-%d" % os.getpid()  # short: socket paths are limited to 108 bytes
comp_dir = os.path.join(tmp, "component")
os.makedirs(comp_dir)
with open(os.path.join(comp_dir, "openkey.xml"), "w") as f:
    f.write(f"""<?xml version="1.0" encoding="utf-8"?>
<component>
  <name>org.freedesktop.IBus.OpenKey</name>
  <description>OpenKey test</description>
  <exec>{sys.executable} -I {ROOT}/src/openkey_ibus.py --ibus</exec>
  <version>test</version><author>test</author><license>GPL</license><homepage>x</homepage><textdomain>openkey</textdomain>
  <engines><engine><name>openkey</name><language>vi</language><license>GPL</license><author>t</author>
  <icon></icon><layout>us</layout><longname>OpenKey</longname><description>t</description><rank>0</rank><symbol>V</symbol>
  </engine></engines>
</component>
""")

env = dict(os.environ)
env.pop("WAYLAND_DISPLAY", None)
env.update({
    "IBUS_COMPONENT_PATH": comp_dir,
    "XDG_CONFIG_HOME": os.path.join(tmp, "config"),
    "XDG_CACHE_HOME": os.path.join(tmp, "cache"),
    "DISPLAY": ":97",
    "IBUS_ADDRESS": address,
    "OPENKEY_DEBUG": os.environ.get("OPENKEY_DEBUG", ""),
})
daemon = subprocess.Popen(["ibus-daemon", "--single", "--panel=disable", "--emoji-extension=disable",
                           "--config=disable", "--cache=none", "--address=" + address],
                          env=env, stdout=subprocess.DEVNULL, stderr=open(os.path.join(tmp, "daemon.log"), "w"))
for k in ("IBUS_ADDRESS", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "DISPLAY"):
    os.environ[k] = env[k]
os.environ.pop("WAYLAND_DISPLAY", None)

failures = 0
count = 0


def pump(seconds=0.05):
    ctx = GLib.MainContext.default()
    end = time.time() + seconds
    while time.time() < end:
        while ctx.pending():
            ctx.iteration(False)
        time.sleep(0.005)


class FakeField:
    def __init__(self, bus, surrounding):
        self.text = ""
        self.preedit = ""
        self.surrounding = surrounding
        self.ic = bus.create_input_context("openkey-test")
        caps = IBus.Capabilite.PREEDIT_TEXT | IBus.Capabilite.FOCUS
        if surrounding:
            caps |= IBus.Capabilite.SURROUNDING_TEXT
        self.ic.set_capabilities(caps)
        self.ic.connect("commit-text", self.on_commit)
        self.ic.connect("update-preedit-text", self.on_preedit)
        self.ic.connect("hide-preedit-text", lambda *_: setattr(self, "preedit", ""))
        self.ic.connect("delete-surrounding-text", self.on_delete)
        self.ic.connect("forward-key-event", self.on_forward)
        self.ic.focus_in()
        bus.set_global_engine("openkey")
        pump(1.0)
        for _ in range(50):
            e = self.ic.get_engine()
            if e and e.get_name() == "openkey":
                break
            pump(0.1)
        self.sync()

    def sync(self):
        if self.surrounding:
            n = len(self.text)
            self.ic.set_surrounding_text(IBus.Text.new_from_string(self.text), n, n)

    def on_commit(self, ic, text):
        self.text += text.get_text()
        self.preedit = ""
        self.sync()

    def on_preedit(self, ic, text, cursor, visible):
        self.preedit = text.get_text() if visible else ""

    def on_delete(self, ic, offset, n):
        assert offset == -n, (offset, n)
        self.text = self.text[:len(self.text) - n]
        self.sync()

    def on_forward(self, ic, keyval, keycode, state):
        if keyval == IBus.KEY_BackSpace:
            self.text = self.text[:-1]
            self.sync()

    def press(self, keyval, keycode, state=0):
        handled = self.ic.process_key_event(keyval, keycode, state)
        self.ic.process_key_event(keyval, keycode, state | IBus.ModifierType.RELEASE_MASK)
        pump(0.03)
        if not handled:  # the application handles the key itself
            if keyval == IBus.KEY_BackSpace:
                self.text = self.text[:-1]
            elif keyval == IBus.KEY_Return:
                self.text += "\n"
            else:
                self.text += IBus.keyval_to_unicode(keyval)
            self.sync()

    def type(self, s):
        for ch in s:
            if ch == "\b":
                self.press(IBus.KEY_BackSpace, 14)
            elif ch == "\n":
                self.press(IBus.KEY_Return, 28)
            else:
                xkc, shift = CHAR_TO_KEY[ch]
                self.press(IBus.unicode_to_keyval(ch), xkc - 8, IBus.ModifierType.SHIFT_MASK if shift else 0)
        pump(0.1)
        return self.text, self.preedit

    def tap_modifiers(self, *keys):
        for kv, kc in keys:
            self.ic.process_key_event(kv, kc, 0)
        for kv, kc in reversed(keys):
            self.ic.process_key_event(kv, kc, IBus.ModifierType.RELEASE_MASK)
        pump(0.1)


def check(name, got, expected):
    global failures, count
    count += 1
    if got != expected:
        failures += 1
        print(f"FAIL {name}: expected {expected!r}, got {got!r}")
    else:
        print(f"ok   {name}: {got!r}")


try:
    IBus.init()
    # IBusBus is a singleton: wait until the daemon listens before creating it
    name = "@" + address.split("=", 1)[1]
    for _ in range(100):
        if any(line.rstrip().endswith(name) for line in open("/proc/net/unix")):
            break
        time.sleep(0.1)
    bus = IBus.Bus()
    if not (bus and bus.is_connected()):
        print(open(os.path.join(tmp, "daemon.log")).read(), daemon.poll())
        raise SystemExit("private ibus-daemon did not start")

    # --- preedit mode (default) ---
    f = FakeField(bus, surrounding=False)
    check("preedit while typing", f.type("tieesng"), ("", "tiếng"))
    check("commit on space", f.type(" Vieejt Nam "), ("tiếng Việt Nam ", ""))
    check("punctuation commits", f.type("dduwowngf, "), ("tiếng Việt Nam đường, ", ""))
    check("backspace in preedit", f.type("nguwowif\b\bi"), ("tiếng Việt Nam đường, ", "ngưi"))
    check("enter commits then acts", f.type("\n"), ("tiếng Việt Nam đường, ngưi\n", ""))
    check("macro vn", f.type("vn "), ("tiếng Việt Nam đường, ngưi\nViệt Nam ", ""))
    f.text = ""
    check("english word", f.type("windows "), ("windows ", ""))
    check("uppercase", f.type("NGUWOWIF "), ("windows NGƯỜI ", ""))

    # V/E toggle with Ctrl+Shift
    f.text = ""
    f.tap_modifiers((IBus.KEY_Control_L, 29), (IBus.KEY_Shift_L, 42))
    check("english mode after ctrl+shift", f.type("vieetj "), ("vieetj ", ""))
    f.tap_modifiers((IBus.KEY_Control_L, 29), (IBus.KEY_Shift_L, 42))
    check("back to vietnamese", f.type("vieetj "), ("vieetj việt ", ""))

    # Ctrl shortcuts pass through and do not leave preedit behind
    f.text = ""
    f.type("hoaf")
    handled = f.ic.process_key_event(IBus.KEY_c, 46, IBus.ModifierType.CONTROL_MASK)
    pump(0.1)
    check("ctrl+c commits word and passes", (f.text, f.preedit, handled), ("hoà", "", False))

    # Home (a key the engine does not know) finishes the word and passes through
    f.text = ""
    f.type("vieetj")
    handled = f.ic.process_key_event(IBus.KEY_Home, 102, 0)
    pump(0.1)
    check("home commits word and passes", (f.text, f.preedit, handled), ("việt", "", False))

    # password fields get raw keys
    f.text = ""
    f.ic.set_content_type(IBus.InputPurpose.PASSWORD, 0)
    pump(0.1)
    check("password field is not converted", f.type("aas"), ("aas", ""))
    f.ic.set_content_type(IBus.InputPurpose.FREE_FORM, 0)
    pump(0.1)

    # --- surrounding-text mode (no underline, OpenKey "backspace" technique) ---
    f2 = FakeField(bus, surrounding=True)
    f2.ic.property_activate("output_mode.surrounding", IBus.PropState.CHECKED)
    pump(0.2)
    check("surrounding: in-place edit", f2.type("tieesng "), ("tiếng ", ""))
    check("surrounding: more words", f2.type("Vieejt dduwowngf "), ("tiếng Việt đường ", ""))
    check("surrounding: backspace into word", f2.type("\b\bs"), ("tiếng Việt đướn", ""))
    f2.text = ""
    f2.sync()
    f2.ic.reset()  # what a click in the text field does
    check("surrounding: macro", f2.type("vn."), ("Việt Nam.", ""))
    # client without surrounding text falls back to preedit automatically
    f2.ic.focus_out()
    f3 = FakeField(bus, surrounding=False)
    check("fallback to preedit", f3.type("chaof"), ("", "chào"))
finally:
    daemon.terminate()
    try:
        daemon.wait(5)
    except subprocess.TimeoutExpired:
        daemon.kill()
    log = open(os.path.join(tmp, "daemon.log")).read()
    if failures or "openkey: error" in log or "Traceback" in log:
        print(log[-3000:])
        failures += 1
    shutil.rmtree(tmp, ignore_errors=True)

print(f"{count - failures}/{count} passed")
sys.exit(1 if failures else 0)
