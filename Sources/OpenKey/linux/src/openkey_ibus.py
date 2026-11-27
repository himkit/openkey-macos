#!/usr/bin/env python3
"""OpenKey for Linux - IBus input method engine.

Drives the original OpenKey C++ engine (libopenkey.so) from IBus, so it works on
both X11 and Wayland (GNOME, KDE, ...).

Two output modes:
  preedit      - the word being typed is shown underlined and committed at the end of
                 the word. Works in every application, terminals included. (default)
  surrounding  - OpenKey's "backspace" technique: no underline, the characters before
                 the cursor are replaced in place through IBus surrounding text. Only for
                 applications that support it (GTK, Qt); others fall back to preedit.

License: GPL (same as OpenKey). Engine by Mai Vu Tuyen.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gi  # noqa: E402

gi.require_version("IBus", "1.0")
from gi.repository import GLib, GObject, IBus  # noqa: E402

from openkey_core import (BREAK_KEYS, CHAR_TO_KEY, KEY_DELETE, KEY_DOWN, KEY_ENTER,  # noqa: E402
                          KEY_ESC, KEY_LEFT, KEY_RIGHT, KEY_SPACE, KEY_TAB, KEY_UP,
                          OK_CONSUME, OK_PASS, OK_REPLACE_PASS, Engine)

VERSION = "2.0.7-linux2"
CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "openkey")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
MACRO_FILE = os.path.join(CONFIG_DIR, "macros.txt")
MACRO_HEADER = ";Compatible OpenKey Macro Data file for UniKey*** version=1 ***\n"

DEFAULT_CONFIG = {
    "language": 1,                     # 1 Tiếng Việt, 0 English
    "input_type": 0,                   # 0 Telex, 1 VNI, 2 Simple Telex 1, 3 Simple Telex 2
    "code_table": 0,                   # 0 Unicode, 1 TCVN3, 2 VNI-Windows, 3 Unicode tổ hợp, 4 CP1258
    "check_spelling": 1,
    "modern_orthography": 1,
    "quick_telex": 0,
    "restore_if_wrong_spelling": 1,
    "use_macro": 1,
    "use_macro_in_english": 0,
    "auto_caps_macro": 0,
    "upper_case_first_char": 0,
    "temp_off_spelling": 0,
    "allow_consonant_zfwj": 0,
    "quick_start_consonant": 0,
    "quick_end_consonant": 0,
    "temp_off_openkey": 0,
    "output_mode": "preedit",          # "preedit" or "surrounding"
    "switch_key": "ctrl+shift",        # V/E toggle, e.g. "ctrl+shift", "alt+z", "ctrl+space"; "" disables
}

INPUT_TYPES = [("Telex", 0), ("VNI", 1), ("Simple Telex 1", 2), ("Simple Telex 2", 3)]
CODE_TABLES = [("Unicode", 0), ("TCVN3 (ABC)", 1), ("VNI Windows", 2), ("Unicode tổ hợp", 3), ("Vietnamese Locale CP 1258", 4)]
OUTPUT_MODES = [("Gạch chân (mọi ứng dụng)", "preedit"), ("Không gạch chân (surrounding text)", "surrounding")]
TOGGLES = [
    ("check_spelling", "Kiểm tra chính tả"),
    ("restore_if_wrong_spelling", "Tự khôi phục phím với từ sai"),
    ("modern_orthography", "Đặt dấu oà, uý (thay vì òa, úy)"),
    ("quick_telex", "Gõ nhanh (cc=ch, gg=gi, kk=kh, nn=ng, ...)"),
    ("upper_case_first_char", "Viết hoa chữ cái đầu câu"),
    ("allow_consonant_zfwj", "Cho phép phụ âm đầu z, f, w, j"),
    ("quick_start_consonant", "Gõ tắt phụ âm đầu: f→ph, j→gi, w→qu"),
    ("quick_end_consonant", "Gõ tắt phụ âm cuối: g→ng, h→nh, k→ch"),
    ("use_macro", "Bật gõ tắt (macro)"),
    ("use_macro_in_english", "Gõ tắt cả khi ở chế độ tiếng Anh"),
    ("auto_caps_macro", "Tự viết hoa gõ tắt (Btw → By the way)"),
    ("temp_off_spelling", "Tạm tắt kiểm tra chính tả bằng phím Ctrl"),
    ("temp_off_openkey", "Tạm tắt OpenKey bằng phím Alt"),
]

SPECIAL_KEYS = {
    IBus.KEY_BackSpace: KEY_DELETE,
    IBus.KEY_Tab: KEY_TAB,
    IBus.KEY_ISO_Left_Tab: KEY_TAB,
    IBus.KEY_Return: KEY_ENTER,
    IBus.KEY_KP_Enter: KEY_ENTER,
    IBus.KEY_Escape: KEY_ESC,
    IBus.KEY_Left: KEY_LEFT,
    IBus.KEY_Right: KEY_RIGHT,
    IBus.KEY_Up: KEY_UP,
    IBus.KEY_Down: KEY_DOWN,
}

MODIFIER_KEYS = {
    IBus.KEY_Shift_L: "shift", IBus.KEY_Shift_R: "shift",
    IBus.KEY_Control_L: "ctrl", IBus.KEY_Control_R: "ctrl",
    IBus.KEY_Alt_L: "alt", IBus.KEY_Alt_R: "alt", IBus.KEY_Meta_L: "alt", IBus.KEY_Meta_R: "alt",
    IBus.KEY_Super_L: "super", IBus.KEY_Super_R: "super", IBus.KEY_Hyper_L: "super", IBus.KEY_Hyper_R: "super",
    IBus.KEY_ISO_Level3_Shift: None, IBus.KEY_Caps_Lock: None, IBus.KEY_Num_Lock: None,
}

M = IBus.ModifierType
SUPER_MASKS = M.SUPER_MASK | M.MOD4_MASK | M.HYPER_MASK


def log(*args):
    if os.environ.get("OPENKEY_DEBUG"):
        print("[openkey]", *args, file=sys.stderr, flush=True)


class Settings:
    """Configuration shared by all engine instances (the C++ engine state is global too)."""

    def __init__(self):
        self.data = dict(DEFAULT_CONFIG)
        self.engine = Engine(os.path.join(HERE, "libopenkey.so") if os.path.exists(os.path.join(HERE, "libopenkey.so")) else None)
        self.load()

    def load(self):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                saved = json.load(f)
            for k in DEFAULT_CONFIG:
                if k in saved:
                    self.data[k] = saved[k]
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as e:
            print("openkey: cannot read config:", e, file=sys.stderr)
        self.apply()
        self.load_macros()

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)

    def apply(self):
        for name in Engine.OPTIONS:
            if name in self.data:
                self.engine.set(name, int(self.data[name]))

    def set(self, name, value):
        self.data[name] = value
        if name in Engine.OPTIONS:
            self.engine.set(name, int(value))
        self.save()

    def load_macros(self):
        if not os.path.exists(MACRO_FILE):
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(MACRO_FILE, "w", encoding="utf-8") as f:
                f.write(MACRO_HEADER)
                f.write("vn:Việt Nam\n")
        self.engine.macro_load(MACRO_FILE)

    def parse_switch_key(self):
        spec = str(self.data.get("switch_key") or "").lower().replace(" ", "")
        if not spec:
            return None
        mods, key = set(), None
        for tok in spec.split("+"):
            if tok in ("ctrl", "control"):
                mods.add("ctrl")
            elif tok in ("shift",):
                mods.add("shift")
            elif tok in ("alt", "option", "meta"):
                mods.add("alt")
            elif tok in ("super", "win", "cmd"):
                mods.add("super")
            elif tok:
                kv = IBus.keyval_from_name(tok)
                if kv == IBus.KEY_VoidSymbol and len(tok) == 1:
                    kv = IBus.unicode_to_keyval(tok)
                key = IBus.keyval_to_lower(kv)
        return (frozenset(mods), key)


SETTINGS = None


class OpenKeyEngine(IBus.Engine):
    __gtype_name__ = "OpenKeyEngine"

    def __init__(self):
        super().__init__()
        self.s = SETTINGS
        self.ok = SETTINGS.engine
        self.cells = []            # one string per character the engine may still edit
        self.preedit_active = False
        self.caps = 0
        self.purpose = IBus.InputPurpose.FREE_FORM
        self.mods_down = set()     # modifiers held right now
        self.chord = set()         # modifiers pressed since all were released
        self.chord_dirty = False   # a non-modifier key was pressed during the chord
        self.prop_list = None
        self._build_properties()

    # ------------------------------------------------------------------ helpers
    @property
    def surrounding_ok(self):
        return (self.s.data.get("output_mode") == "surrounding"
                and bool(self.caps & IBus.Capabilite.SURROUNDING_TEXT))

    @property
    def use_preedit(self):
        return not self.surrounding_ok and bool(self.caps & IBus.Capabilite.PREEDIT_TEXT or self.caps == 0)

    def _reset_word(self):
        self.cells = []
        self.ok.new_session()

    def _show_preedit(self):
        text = "".join(self.cells)
        if not text:
            self._hide_preedit()
            return
        t = IBus.Text.new_from_string(text)
        n = len(text)
        attrs = IBus.AttrList()
        attrs.append(IBus.Attribute.new(IBus.AttrType.UNDERLINE, IBus.AttrUnderline.SINGLE, 0, n))
        t.set_attributes(attrs)
        self.update_preedit_text_with_mode(t, n, True, IBus.PreeditFocusMode.COMMIT)
        self.preedit_active = True

    def _hide_preedit(self):
        if self.preedit_active:
            self.update_preedit_text_with_mode(IBus.Text.new_from_string(""), 0, False, IBus.PreeditFocusMode.CLEAR)
            self.preedit_active = False

    def _commit(self, text):
        if text:
            self.commit_text(IBus.Text.new_from_string(text))

    def _commit_preedit(self, extra=""):
        text = "".join(self.cells) + extra
        self._hide_preedit()
        self._commit(text)
        self.cells = []

    def _flush_preedit(self):
        """Commit the underlined word, if one is shown (cells tracked in direct mode are not)."""
        if self.preedit_active:
            self._commit_preedit()
        self.cells = []

    def _pop_cells(self, n):
        """Remove n engine characters from the end; return how many code points that is."""
        cps = 0
        for _ in range(n):
            cps += len(self.cells.pop()) if self.cells else 1
        return cps

    def _delete_before_cursor(self, ncp):
        if ncp <= 0:
            return
        if self.caps & IBus.Capabilite.SURROUNDING_TEXT:
            self.get_surrounding_text()
            self.delete_surrounding_text(-ncp, ncp)
        else:
            for _ in range(ncp):
                self.forward_key_event(IBus.KEY_BackSpace, 14, 0)

    @staticmethod
    def _map_key(keyval):
        if keyval in SPECIAL_KEYS:
            return SPECIAL_KEYS[keyval], None
        ch = IBus.keyval_to_unicode(keyval)  # a str ('' when there is no character)
        if ch and ch in CHAR_TO_KEY:
            return CHAR_TO_KEY[ch][0], ch
        return None, None

    # ------------------------------------------------------------------ V/E switching
    def _toggle_language(self):
        self._flush_preedit()
        self.s.set("language", 0 if self.s.data["language"] else 1)
        self._reset_word()
        self._update_language_prop()

    def _modifier_event(self, keyval, released):
        name = MODIFIER_KEYS.get(keyval)
        if name is None:
            return
        if not released:
            if not self.mods_down:
                self.chord = set()
                self.chord_dirty = False
            self.mods_down.add(name)
            self.chord.add(name)
            return
        self.mods_down.discard(name)
        if self.mods_down or self.chord_dirty:
            return
        hotkey = self.s.parse_switch_key()
        if hotkey and hotkey[1] is None and set(hotkey[0]) == self.chord:
            self._toggle_language()
        elif self.chord == {"ctrl"} and self.s.data.get("temp_off_spelling"):
            self.ok.temp_off_spelling()
        elif self.chord == {"alt"} and self.s.data.get("temp_off_openkey"):
            self.ok.temp_off_engine()
        self.chord = set()

    def _is_key_hotkey(self, keyval, state):
        hotkey = self.s.parse_switch_key()
        if not hotkey or hotkey[1] is None:
            return False
        mods = set()
        if state & M.CONTROL_MASK:
            mods.add("ctrl")
        if state & M.SHIFT_MASK:
            mods.add("shift")
        if state & M.MOD1_MASK:
            mods.add("alt")
        if state & SUPER_MASKS:
            mods.add("super")
        return mods == set(hotkey[0]) and IBus.keyval_to_lower(keyval) == hotkey[1]

    # ------------------------------------------------------------------ key handling
    def do_process_key_event(self, keyval, keycode, state):
        try:
            return self._process_key(keyval, keycode, state)
        except Exception as e:  # never break typing because of a bug here
            print("openkey: error:", repr(e), file=sys.stderr)
            self.cells = []
            return False

    def _process_key(self, keyval, keycode, state):
        released = bool(state & M.RELEASE_MASK)
        if keyval in MODIFIER_KEYS:
            self._modifier_event(keyval, released)
            return False
        if released:
            return False
        self.chord_dirty = True

        if self._is_key_hotkey(keyval, state):
            self._toggle_language()
            return True

        if self.purpose in (IBus.InputPurpose.PASSWORD, IBus.InputPurpose.PIN):
            return False

        okkey, ch = self._map_key(keyval)
        other = bool(state & (M.CONTROL_MASK | M.MOD1_MASK | SUPER_MASKS))
        if okkey is None:
            # Home/End/PageUp/Delete/F-keys/numpad/non-Latin: finish the word, let the key act
            self._flush_preedit()
            self._reset_word()
            return False

        # Take the case from the character XKB produced, not from the modifier state:
        # CapsLock+Shift gives lower case on Linux, CapsLock does not shift digits or
        # punctuation, and some layouts (AZERTY) need Shift for plain digits.
        if ch is None:
            caps_status = 1 if state & M.SHIFT_MASK else 0
        elif ch.isalpha():
            caps_status = 1 if ch.isupper() else 0
        else:
            caps_status = 1 if CHAR_TO_KEY[ch][1] else 0

        if self.use_preedit and self.s.data["language"] == 1:
            return self._process_preedit(okkey, ch, caps_status, other)
        return self._process_direct(okkey, ch, caps_status, other)

    def _process_preedit(self, okkey, ch, caps_status, other):
        if other:  # Ctrl/Alt/Super shortcut: finish the word first
            self._flush_preedit()
            self._reset_word()
            return False

        if okkey == KEY_DELETE:
            if not self.cells:
                self._reset_word()
                return False
            r = self.ok.process(okkey, caps_status, False)
            if r.action == OK_PASS:
                self.cells.pop()
            else:
                self._pop_cells(r.backspaces)
                self.cells.extend(r.entries())
            if self.cells:
                self._show_preedit()
            else:
                self._hide_preedit()
                self._reset_word()
            return True

        r = self.ok.process(okkey, caps_status, False)
        log("key", okkey, repr(ch), "->", r.action, r.backspaces, r.entries())
        if r.action != OK_PASS:
            self._pop_cells(r.backspaces)
            self.cells.extend(r.entries())

        is_break = okkey == KEY_SPACE or okkey in BREAK_KEYS or (ch is not None and ch in "!@#$%^&*()")
        if is_break:
            # The engine has already ended the word for this key. No full reset here:
            # ok_new_session() would also drop its sentence state (upper case first letter).
            # Edits never reach back into committed text: a BackSpace with an empty
            # preedit resets the engine before passing through.
            if ch is not None:
                # space / punctuation: commit the word together with the character
                self._commit_preedit("" if r.action == OK_CONSUME else ch)
                return True
            self._commit_preedit()     # Enter, Tab, arrows, Esc: let the key act afterwards
            return False

        if r.action != OK_CONSUME and ch is not None:
            self.cells.append(ch)
        self._show_preedit()
        return True

    def _process_direct(self, okkey, ch, caps_status, other):
        """Surrounding-text ("backspace") mode, and English mode."""
        r = self.ok.process(okkey, caps_status, other)
        if r.action == OK_PASS:
            if other or (okkey in BREAK_KEYS and ch is None):
                self.cells = []
            elif okkey == KEY_DELETE:
                if self.cells:
                    self.cells.pop()
            elif ch is not None:
                self.cells.append(ch)
            return False

        log("replace", r.action, r.backspaces, r.entries())
        self._delete_before_cursor(self._pop_cells(r.backspaces))
        entries = r.entries()
        self.cells.extend(entries)
        text = "".join(entries)
        if r.action == OK_REPLACE_PASS and ch is not None and okkey != KEY_DELETE:
            # macro / restore followed by a printable key: send it in the same commit
            text += ch
            self.cells.append(ch)
            self._commit(text)
            return True
        self._commit(text)
        return r.action == OK_CONSUME

    # ------------------------------------------------------------------ IBus life cycle
    def _clear_modifiers(self):
        # a release can go to another window (Alt+Tab, Super): never keep a stale "held" key
        self.mods_down = set()
        self.chord = set()
        self.chord_dirty = False

    def do_focus_in(self):
        self._clear_modifiers()
        self.register_properties(self.prop_list)
        self._update_language_prop()
        self._reset_word()
        self.preedit_active = False

    def do_focus_out(self):
        # preedit is committed by the client (PreeditFocusMode.COMMIT)
        self._clear_modifiers()
        self.cells = []
        self.preedit_active = False
        self.ok.new_session()

    def do_reset(self):
        self._clear_modifiers()
        self.cells = []
        self.preedit_active = False
        self.ok.new_session()

    def do_enable(self):
        self.get_surrounding_text()  # ask the client to send surrounding text

    def do_disable(self):
        self.do_reset()

    def do_set_capabilities(self, caps):
        self.caps = caps

    def do_set_content_type(self, purpose, hints):
        self.purpose = purpose

    # ------------------------------------------------------------------ menu
    def _text(self, s):
        return IBus.Text.new_from_string(s)

    def _language_label(self):
        return "Tiếng Việt (V)" if self.s.data["language"] else "English (E)"

    def _build_properties(self):
        d = self.s.data
        props = IBus.PropList()
        self.lang_prop = IBus.Property(key="language", prop_type=IBus.PropType.NORMAL,
                                       label=self._text(self._language_label()),
                                       symbol=self._text("V" if d["language"] else "E"),
                                       tooltip=self._text("Bấm để chuyển Việt/Anh (phím tắt: %s)" % (d.get("switch_key") or "không")),
                                       sensitive=True, visible=True)
        props.append(self.lang_prop)

        def radio_menu(key, title, items, current):
            sub = IBus.PropList()
            for label, value in items:
                sub.append(IBus.Property(key="%s.%s" % (key, value), prop_type=IBus.PropType.RADIO,
                                         label=self._text(label), sensitive=True, visible=True,
                                         state=IBus.PropState.CHECKED if value == current else IBus.PropState.UNCHECKED))
            props.append(IBus.Property(key=key, prop_type=IBus.PropType.MENU, label=self._text(title),
                                       sensitive=True, visible=True, sub_props=sub))

        radio_menu("input_type", "Kiểu gõ", INPUT_TYPES, d["input_type"])
        radio_menu("code_table", "Bảng mã", CODE_TABLES, d["code_table"])
        radio_menu("output_mode", "Cách hiển thị", OUTPUT_MODES, d["output_mode"])

        sub = IBus.PropList()
        for key, label in TOGGLES:
            sub.append(IBus.Property(key="opt." + key, prop_type=IBus.PropType.TOGGLE, label=self._text(label),
                                     sensitive=True, visible=True,
                                     state=IBus.PropState.CHECKED if d.get(key) else IBus.PropState.UNCHECKED))
        props.append(IBus.Property(key="options", prop_type=IBus.PropType.MENU, label=self._text("Tuỳ chọn"),
                                   sensitive=True, visible=True, sub_props=sub))

        props.append(IBus.Property(key="macro.edit", prop_type=IBus.PropType.NORMAL,
                                   label=self._text("Sửa bảng gõ tắt..."), sensitive=True, visible=True))
        props.append(IBus.Property(key="macro.reload", prop_type=IBus.PropType.NORMAL,
                                   label=self._text("Nạp lại bảng gõ tắt"), sensitive=True, visible=True))
        props.append(IBus.Property(key="config.edit", prop_type=IBus.PropType.NORMAL,
                                   label=self._text("Mở file cấu hình..."), sensitive=True, visible=True))
        props.append(IBus.Property(key="about", prop_type=IBus.PropType.NORMAL,
                                   label=self._text("OpenKey %s" % VERSION), sensitive=False, visible=True))
        self.prop_list = props

    def _update_language_prop(self):
        self.lang_prop.set_label(self._text(self._language_label()))
        self.lang_prop.set_symbol(self._text("V" if self.s.data["language"] else "E"))
        self.update_property(self.lang_prop)

    def do_property_activate(self, name, state):
        log("property", name, state)
        if name == "language":
            self._toggle_language()
            return
        if name in ("macro.edit", "config.edit"):
            path = MACRO_FILE if name == "macro.edit" else CONFIG_FILE
            if not os.path.exists(path):
                self.s.save()
            try:
                subprocess.Popen(["xdg-open", path], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError as e:
                print("openkey: cannot open", path, e, file=sys.stderr)
            return
        if name == "macro.reload":
            self.s.load()
            self._build_properties()
            self.register_properties(self.prop_list)
            return
        if name.startswith("opt."):
            self.s.set(name[4:], 1 if state == IBus.PropState.CHECKED else 0)
            self._reset_word()
            return
        for key in ("input_type", "code_table", "output_mode"):
            if name.startswith(key + ".") and state == IBus.PropState.CHECKED:
                value = name[len(key) + 1:]
                self.s.set(key, value if key == "output_mode" else int(value))
                self._reset_word()
                return


class Application:
    def __init__(self, exec_by_ibus):
        self.loop = GLib.MainLoop()
        self.bus = IBus.Bus()
        if not self.bus.is_connected():
            print("openkey: cannot connect to ibus-daemon", file=sys.stderr)
            sys.exit(1)
        self.bus.connect("disconnected", lambda *_: self.loop.quit())
        self.factory = IBus.Factory.new(self.bus.get_connection())
        self.factory.add_engine("openkey", GObject.type_from_name("OpenKeyEngine"))
        if exec_by_ibus:
            self.bus.request_name("org.freedesktop.IBus.OpenKey", 0)
        else:  # manual run for development: register the component ourselves
            component = IBus.Component(name="org.freedesktop.IBus.OpenKey", description="OpenKey",
                                       version=VERSION, license="GPL", author="OpenKey",
                                       homepage="https://github.com/himkit/openkey-macos",
                                       command_line="", textdomain="openkey")
            component.add_engine(IBus.EngineDesc(name="openkey", longname="OpenKey", description="OpenKey",
                                                 language="vi", license="GPL", author="OpenKey",
                                                 icon="", layout="us", symbol="V", rank=0))
            self.bus.register_component(component)

    def run(self):
        self.loop.run()


def main():
    global SETTINGS
    if "--version" in sys.argv:
        print(VERSION)
        return
    IBus.init()
    SETTINGS = Settings()
    Application("--ibus" in sys.argv).run()


if __name__ == "__main__":
    main()
