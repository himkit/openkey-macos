"""ctypes binding for libopenkey.so (the OpenKey C++ engine + src/openkey_api.cpp).

Shared by the IBus engine (openkey_ibus.py) and the tests.
"""
import ctypes
import os

OK_PASS = 0
OK_CONSUME = 1
OK_REPLACE_PASS = 2

MAX_ENTRIES = 512
MAX_CODEPOINTS = 1024

# X11 key codes used by the engine on Linux (engine/platforms/linux.h)
KEY_ESC = 9
KEY_DELETE = 22  # BackSpace
KEY_TAB = 23
KEY_ENTER = 36
KEY_SPACE = 65
KEY_LEFT = 113
KEY_RIGHT = 114
KEY_DOWN = 116
KEY_UP = 111

# character -> (keycode, needs shift) on a US layout
_ROWS = {
    'a': 38, 'b': 56, 'c': 54, 'd': 40, 'e': 26, 'f': 41, 'g': 42, 'h': 43, 'i': 31,
    'j': 44, 'k': 45, 'l': 46, 'm': 58, 'n': 57, 'o': 32, 'p': 33, 'q': 24, 'r': 27,
    's': 39, 't': 28, 'u': 30, 'v': 55, 'w': 25, 'x': 53, 'y': 29, 'z': 52,
    '1': 10, '2': 11, '3': 12, '4': 13, '5': 14, '6': 15, '7': 16, '8': 17, '9': 18, '0': 19,
    '`': 49, '-': 20, '=': 21, '[': 34, ']': 35, '\\': 51, ';': 47, "'": 48, ',': 59, '.': 60, '/': 61,
    ' ': KEY_SPACE,
}
_SHIFTED = {
    '!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7', '*': '8', '(': '9', ')': '0',
    '~': '`', '_': '-', '+': '=', '{': '[', '}': ']', '|': '\\', ':': ';', '"': "'", '<': ',', '>': '.', '?': '/',
}
CHAR_TO_KEY = {}
for _c, _k in _ROWS.items():
    CHAR_TO_KEY[_c] = (_k, False)
    if _c.isalpha():
        CHAR_TO_KEY[_c.upper()] = (_k, True)
for _c, _base in _SHIFTED.items():
    CHAR_TO_KEY[_c] = (_ROWS[_base], True)

# keys after which the engine starts a new word (engine _breakCode + space)
BREAK_KEYS = {KEY_ESC, KEY_TAB, KEY_ENTER, KEY_LEFT, KEY_RIGHT, KEY_DOWN, KEY_UP,
              59, 60, 61, 47, 48, 51, 20, 21, 49}


class OkResult(ctypes.Structure):
    _fields_ = [
        ("action", ctypes.c_int),
        ("backspaces", ctypes.c_int),
        ("ext_code", ctypes.c_int),
        ("engine_code", ctypes.c_int),
        ("entry_count", ctypes.c_int),
        ("entry_len", ctypes.c_int * MAX_ENTRIES),
        ("codepoint_count", ctypes.c_int),
        ("codepoints", ctypes.c_uint * MAX_CODEPOINTS),
    ]

    def entries(self):
        """Inserted characters as a list of strings (one per engine character)."""
        out, cp = [], 0
        for i in range(self.entry_count):
            n = self.entry_len[i]
            out.append("".join(chr(self.codepoints[cp + k]) for k in range(n)))
            cp += n
        return out


def _find_library():
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.environ.get("OPENKEY_LIB"),
                 os.path.join(here, "libopenkey.so"),
                 os.path.join(here, "..", "build", "libopenkey.so")):
        if cand and os.path.exists(cand):
            return cand
    raise OSError("libopenkey.so not found (set OPENKEY_LIB)")


class Engine:
    OPTIONS = (
        "language", "input_type", "code_table", "check_spelling", "modern_orthography",
        "quick_telex", "restore_if_wrong_spelling", "use_macro", "use_macro_in_english",
        "auto_caps_macro", "upper_case_first_char", "temp_off_spelling", "allow_consonant_zfwj",
        "quick_start_consonant", "quick_end_consonant", "temp_off_openkey",
    )

    def __init__(self, path=None):
        lib = ctypes.CDLL(path or _find_library())
        lib.ok_init.restype = None
        lib.ok_set_option.argtypes = [ctypes.c_char_p, ctypes.c_int]
        lib.ok_get_option.argtypes = [ctypes.c_char_p]
        lib.ok_process_key.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(OkResult)]
        lib.ok_new_session.restype = None
        lib.ok_temp_off_spelling.restype = None
        lib.ok_temp_off_engine.restype = None
        lib.ok_macro_load.argtypes = [ctypes.c_char_p]
        lib.ok_macro_save.argtypes = [ctypes.c_char_p]
        lib.ok_macro_add.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib.ok_macro_delete.argtypes = [ctypes.c_char_p]
        lib.ok_convert.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_char_p, ctypes.c_int]
        self.lib = lib
        self.result = OkResult()
        lib.ok_init()

    def set(self, name, value):
        if not self.lib.ok_set_option(name.encode(), int(value)):
            raise KeyError(name)

    def get(self, name):
        return self.lib.ok_get_option(name.encode())

    def process(self, keycode, caps_status=0, other_control=False):
        self.lib.ok_process_key(keycode, caps_status, 1 if other_control else 0, ctypes.byref(self.result))
        return self.result

    def new_session(self):
        self.lib.ok_new_session()

    def temp_off_spelling(self):
        self.lib.ok_temp_off_spelling()

    def temp_off_engine(self):
        self.lib.ok_temp_off_engine()

    def macro_load(self, path):
        self.lib.ok_macro_load(path.encode())

    def macro_save(self, path):
        self.lib.ok_macro_save(path.encode())

    def macro_add(self, name, content):
        return bool(self.lib.ok_macro_add(name.encode(), content.encode()))

    def convert(self, text, from_code, to_code, flags=0):
        data = text.encode()
        size = len(data) * 4 + 16
        buf = ctypes.create_string_buffer(size)
        n = self.lib.ok_convert(data, from_code, to_code, flags, buf, size)
        if n < 0:
            buf = ctypes.create_string_buffer(-n)
            n = self.lib.ok_convert(data, from_code, to_code, flags, buf, -n)
        return buf.value.decode("utf-8", "replace")


class TextBuffer:
    """Simulated text field: applies engine results the way the "backspace" front end does.

    `cells` holds one string per character the engine knows about, so a backspace count
    (in engine characters) maps to the right number of code points for VNI/TCVN3/compound.
    """

    def __init__(self, engine):
        self.engine = engine
        self.cells = []

    @property
    def text(self):
        return "".join(self.cells)

    def key(self, keycode, char=None, caps_status=0, other_control=False):
        r = self.engine.process(keycode, caps_status, other_control)
        if r.action != OK_PASS:
            for _ in range(r.backspaces):
                if self.cells:
                    self.cells.pop()
            self.cells.extend(r.entries())
        if r.action != OK_CONSUME:
            if keycode == KEY_DELETE:
                if self.cells:
                    self.cells.pop()
            elif char is not None:
                self.cells.append(char)
        return r

    def type(self, s, caps_lock=False):
        """Type s; caps_lock=True sends the raw CapsLock status (2) for unshifted keys."""
        for ch in s:
            if ch == "\b":
                self.key(KEY_DELETE)
                continue
            if ch == "\n":
                self.key(KEY_ENTER, "\n")
                continue
            keycode, shift = CHAR_TO_KEY[ch]
            self.key(keycode, ch, 1 if shift else (2 if caps_lock else 0))
        return self.text
