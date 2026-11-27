"""Typing tests for the OpenKey engine built for Linux (run: make test)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from openkey_core import Engine, TextBuffer  # noqa: E402

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "libopenkey.so")
engine = Engine(LIB)

DEFAULTS = dict(language=1, input_type=0, code_table=0, check_spelling=1, modern_orthography=1,
                quick_telex=0, restore_if_wrong_spelling=1, use_macro=0, use_macro_in_english=0,
                auto_caps_macro=0, upper_case_first_char=0, allow_consonant_zfwj=0,
                quick_start_consonant=0, quick_end_consonant=0)

failures = 0
count = 0


def check(keys, expected, **opts):
    global failures, count
    cfg = dict(DEFAULTS)
    cfg.update(opts)
    for k, v in cfg.items():
        engine.set(k, v)
    engine.new_session()
    got = TextBuffer(engine).type(keys)
    count += 1
    if got != expected:
        failures += 1
        print(f"FAIL {keys!r} {opts}: expected {expected!r}, got {got!r}")


# --- Telex ---
check("tieesng Vieejt ", "tiếng Việt ")
check("dduwowngf ", "đường ")
check("nguwowif ", "người ")
check("NGUWOWIF ", "NGƯỜI ")
check("Ddaay laf ", "Đây là ")
check("xin chaof cacs banj ", "xin chào các bạn ")
check("giuwax ", "giữa ")
check("quas ", "quá ")
check("gif ", "gì ")
check("khuyeens ", "khuyến ")
check("w ", "ư ")
check("[ ] ", "ơ ư ")
check("thuowr ", "thuở ")
check("hoaf ", "hoà ")                                # modern orthography
check("hoaf ", "hòa ", modern_orthography=0)          # old orthography
check("thuyr ", "thuỷ ")
check("thuyr ", "thủy ", modern_orthography=0)
check("aa ", "â ")
check("aaa ", "aa ")                                  # double press restores
check("ass ", "as ")
check("tieengs\b\b ", "tiế ")                          # backspace inside a word
check("tieengs\b\bn ", "tiến ")
check("vieet\bj ", "việ ")
check("ddi hocj ", "đi học ")
check("mootj hai ba ", "một hai ba ")
check("hello windows ", "hello windows ")             # English words untouched
check("text ", "text ")
check("Truwowngf ", "Trường ")
check("tooi\b\b\b\b", "")

# restore key when the word is not Vietnamese
check("wordf ", "wordf ")
check("tesst ", "test ")                             # ss cancels the mark

# --- quick telex: cc=ch, gg=gi, nn=ng, ... ---
check("nnuwowif ", "người ", quick_telex=1)
check("cca ", "cha ", quick_telex=1)

# --- quick start / end consonant: f->ph, j->gi, w->qu; g->ng, h->nh, k->ch ---
check("fan ", "phan ", quick_start_consonant=1)
check("hag ", "hang ", quick_end_consonant=1)

# --- VNI ---
check("tie61ng Vie65t ", "tiếng Việt ", input_type=1)
check("d9uo7ng2 ", "đường ", input_type=1)
check("nguo7i2 ", "người ", input_type=1)
check("a6 o7 u7 a8 ", "â ơ ư ă ", input_type=1)

# --- Simple Telex (no w -> ư) ---
check("w ", "w ", input_type=2)
check("tieesng ", "tiếng ", input_type=2)

# --- upper case first letter of a sentence ---
check("xin chaof. ban ", "xin chào. Ban ", upper_case_first_char=1)

# --- code tables: VNI Windows uses 2 bytes for some letters, backspace must remove both ---
check("tieesng ", "tie\u00e1ng ", code_table=2)             # VNI-Windows bytes as Latin-1
check("vieejt\b\b", "vi", code_table=2)
check("tieesng ", "ti\u00ea\u0301ng ", code_table=3)          # Unicode compound: ê + combining acute
check("vieejt\b\b", "vi", code_table=3)

# --- macros ---
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
    f.write(";Compatible OpenKey Macro Data file for UniKey*** version=1 ***\n")
    f.write("vn:Việt Nam\n")
    f.write("btw:by the way\n")
    f.write("smile:hi 😀\n")
    path = f.name
engine.macro_load(path)
os.unlink(path)
check("vn ", "Việt Nam ", use_macro=1)
check("btw, ", "by the way, ", use_macro=1)
check("smile ", "hi 😀 ", use_macro=1)
check("Btw ", "By the way ", use_macro=1, auto_caps_macro=1)
check("vn ", "vn ", use_macro=0)
check("btw ", "by the way ", use_macro=1, use_macro_in_english=1, language=0)
check("vieetj ", "vieetj ", language=0)                        # English mode

# --- convert tool (includes the Linux-port fixes in engine/ConvertTool.cpp) ---
def check_convert(src, f, t, flags, expected):
    global failures, count
    count += 1
    got = engine.convert(src, f, t, flags)
    if got != expected:
        failures += 1
        print(f"FAIL convert {src!r} {f}->{t} flags={flags}: expected {expected!r}, got {got!r}")


check_convert("Tiếng Việt ABC", 0, 0, 0, "Tiếng Việt ABC")      # case kept with no case option
check_convert("Tiếng Việt", 0, 0, 1, "TIẾNG VIỆT")
check_convert("TIẾNG", 0, 0, 2, "tiếng")
check_convert("tiếng việt. xin chào", 0, 0, 4, "Tiếng việt. Xin chào")
check_convert("Đi Tiếng", 0, 0, 16, "Di Tieng")                 # remove marks keeps capitals
check_convert("bê", 0, 2, 0, "be\u00e2")                        # last char split into 2 VNI bytes
check_convert(engine.convert("Tiếng Việt", 0, 2, 0), 2, 0, 0, "Tiếng Việt")
check_convert(engine.convert("Tiếng Việt", 0, 3, 0), 3, 0, 0, "Tiếng Việt")

print(f"{count - failures}/{count} passed")
sys.exit(1 if failures else 0)
