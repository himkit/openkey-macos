//
//  openkey_api.cpp
//  OpenKey for Linux
//
//  Plain C API around the shared OpenKey C++ engine (Sources/OpenKey/engine),
//  so a Linux front end (the IBus engine in openkey_ibus.py) can drive it.
//  Compiled with -DLINUX so the engine uses the X11 key codes in platforms/linux.h.
//
//  The output logic mirrors SendNewCharString()/handleMacro() of the macOS
//  front end (macOS/ModernKey/OpenKey.mm), but instead of posting key events it
//  returns "delete N characters, then insert these characters".
//
//  License: GPL (same as OpenKey). Engine by Mai Vu Tuyen.
//

#include <string.h>
#include <string>
#include "Engine.h"

// ---------------------------------------------------------------------------
// Engine configuration variables (declared extern in Engine.h; each front end
// defines them). Defaults follow the macOS/Windows "load default config".
// ---------------------------------------------------------------------------
int vLanguage = 1;
int vInputType = 0;
int vFreeMark = 0;
int vCodeTable = 0;
int vSwitchKeyStatus = 0;
int vCheckSpelling = 1;
int vUseModernOrthography = 1;
int vQuickTelex = 0;
int vRestoreIfWrongSpelling = 1;
int vFixRecommendBrowser = 0;
int vUseMacro = 1;
int vUseMacroInEnglishMode = 0;
int vAutoCapsMacro = 0;
int vUseSmartSwitchKey = 0;
int vUpperCaseFirstChar = 0;
int vTempOffSpelling = 0;
int vAllowConsonantZFWJ = 0;
int vQuickStartConsonant = 0;
int vQuickEndConsonant = 0;
int vRememberCode = 0;
int vOtherLanguage = 0;
int vTempOffOpenKey = 0;

static vKeyHookState* pData = NULL;

struct OptionEntry {
    const char* name;
    int* ptr;
};

static OptionEntry _options[] = {
    {"language", &vLanguage},
    {"input_type", &vInputType},
    {"code_table", &vCodeTable},
    {"check_spelling", &vCheckSpelling},
    {"modern_orthography", &vUseModernOrthography},
    {"quick_telex", &vQuickTelex},
    {"restore_if_wrong_spelling", &vRestoreIfWrongSpelling},
    {"use_macro", &vUseMacro},
    {"use_macro_in_english", &vUseMacroInEnglishMode},
    {"auto_caps_macro", &vAutoCapsMacro},
    {"upper_case_first_char", &vUpperCaseFirstChar},
    {"temp_off_spelling", &vTempOffSpelling},
    {"allow_consonant_zfwj", &vAllowConsonantZFWJ},
    {"quick_start_consonant", &vQuickStartConsonant},
    {"quick_end_consonant", &vQuickEndConsonant},
    {"temp_off_openkey", &vTempOffOpenKey},
    {"free_mark", &vFreeMark},
    {NULL, NULL}
};

// ---------------------------------------------------------------------------
// Result handed back to the front end for one key press.
// ---------------------------------------------------------------------------
#define OK_MAX_ENTRIES 512
#define OK_MAX_CODEPOINTS 1024

enum {
    OK_PASS = 0,          // let the application receive the key unchanged
    OK_CONSUME = 1,       // swallow the key; apply delete/insert instead
    OK_REPLACE_PASS = 2,  // apply delete/insert, then let the key through
};

extern "C" {

typedef struct {
    int action;            // OK_PASS / OK_CONSUME / OK_REPLACE_PASS
    int backspaces;        // number of engine characters to delete before the cursor
    int ext_code;          // engine extCode (1 word break, 2 delete, 3 normal key, 4 no empty char)
    int engine_code;       // engine HookState.code
    int entry_count;       // number of inserted characters (engine units)
    int entry_len[OK_MAX_ENTRIES];      // code points per entry (1 or 2: VNI/TCVN3/compound)
    int codepoint_count;
    unsigned int codepoints[OK_MAX_CODEPOINTS];
} ok_result;

}

static void resetResult(ok_result* r) {
    r->action = OK_PASS;
    r->backspaces = 0;
    r->ext_code = 0;
    r->engine_code = 0;
    r->entry_count = 0;
    r->codepoint_count = 0;
}

static void pushEntry(ok_result* r, unsigned int cp1, unsigned int cp2 = 0) {
    if (r->entry_count >= OK_MAX_ENTRIES || r->codepoint_count + 2 > OK_MAX_CODEPOINTS)
        return;
    r->codepoints[r->codepoint_count++] = cp1;
    int len = 1;
    if (cp2) {
        r->codepoints[r->codepoint_count++] = cp2;
        len = 2;
    }
    r->entry_len[r->entry_count++] = len;
}

// Convert one engine data word into real characters (see SendNewCharString in OpenKey.mm).
static void pushEngineChar(ok_result* r, Uint32 data) {
    if (data & PURE_CHARACTER_MASK) {
        // macro text that is not a Vietnamese letter: a UTF-16 unit
        pushEntry(r, data & 0xFFFF);
        return;
    }
    if (!(data & CHAR_CODE_MASK)) {
        Uint16 ch = keyCodeToCharacter(data);
        if (ch != 0)
            pushEntry(r, ch);
        return;
    }
    Uint16 code = (Uint16)data;
    if (vCodeTable == 0) {                    // Unicode
        pushEntry(r, code);
    } else if (vCodeTable == 1 || vCodeTable == 2 || vCodeTable == 4) { // TCVN3, VNI-Windows, CP1258
        Uint16 lo = LOBYTE(code);
        Uint16 hi = HIBYTE(code);
        if (hi > 32)
            pushEntry(r, lo, hi);
        else
            pushEntry(r, lo);
    } else if (vCodeTable == 3) {             // Unicode compound (base + combining mark)
        Uint16 hi = code >> 13;
        Uint16 base = code & 0x1FFF;
        if (hi > 0)
            pushEntry(r, base, _unicodeCompoundMark[hi - 1]);
        else
            pushEntry(r, base);
    }
}

// Merge UTF-16 surrogate pairs produced by the engine's UTF-8 -> wstring conversion
// of macro text (emoji etc.) into single code points.
static void mergeSurrogates(ok_result* r) {
    int out = 0, outEntry = 0, cp = 0;
    for (int e = 0; e < r->entry_count; e++) {
        int len = r->entry_len[e];
        if (len == 1 && e + 1 < r->entry_count && r->entry_len[e + 1] == 1) {
            unsigned int a = r->codepoints[cp], b = r->codepoints[cp + 1];
            if (a >= 0xD800 && a <= 0xDBFF && b >= 0xDC00 && b <= 0xDFFF) {
                r->codepoints[out++] = 0x10000 + ((a - 0xD800) << 10) + (b - 0xDC00);
                r->entry_len[outEntry++] = 1;
                cp += 2;
                e++;
                continue;
            }
        }
        for (int k = 0; k < len; k++)
            r->codepoints[out++] = r->codepoints[cp++];
        r->entry_len[outEntry++] = len;
    }
    r->codepoint_count = out;
    r->entry_count = outEntry;
}

static void fillMacro(ok_result* r) {
    r->backspaces = pData->backspaceCount;
    for (size_t i = 0; i < pData->macroData.size(); i++)
        pushEngineChar(r, pData->macroData[i]);
    mergeSurrogates(r);
    r->action = OK_REPLACE_PASS; // the break key (space, punctuation, enter) follows the macro text
}

extern "C" {

void ok_init(void) {
    pData = (vKeyHookState*)vKeyInit();
}

int ok_set_option(const char* name, int value) {
    for (int i = 0; _options[i].name; i++) {
        if (strcmp(_options[i].name, name) == 0) {
            *_options[i].ptr = value;
            if (_options[i].ptr == &vCheckSpelling)
                vSetCheckSpelling();
            if (_options[i].ptr == &vCodeTable)
                onTableCodeChange();
            return 1;
        }
    }
    return 0;
}

int ok_get_option(const char* name) {
    for (int i = 0; _options[i].name; i++) {
        if (strcmp(_options[i].name, name) == 0)
            return *_options[i].ptr;
    }
    return -1;
}

// Forget the current word and the saved word history (like a mouse click).
void ok_new_session(void) {
    if (!pData) ok_init();
    if (vLanguage == 0)
        vEnglishMode(vKeyEventState::MouseDown, 0, false, false);
    else
        vKeyHandleEvent(vKeyEvent::Mouse, vKeyEventState::MouseDown, 0);
    startNewSession();
}

void ok_temp_off_spelling(void) { vTempOffSpellChecking(); }
void ok_temp_off_engine(void) { vTempOffEngine(true); }

// keycode: X11 key code (evdev + 8), see engine/platforms/linux.h
// caps_status: 0 none, 1 shift held, 2 caps lock
// other_control: ctrl / alt / super held
int ok_process_key(int keycode, int caps_status, int other_control, ok_result* r) {
    if (!pData) ok_init();
    resetResult(r);
    const Uint16 key = (Uint16)keycode;
    const bool anyCaps = caps_status != 0;

    if (vLanguage == 0) {
        if (vUseMacro && vUseMacroInEnglishMode) {
            vEnglishMode(vKeyEventState::KeyDown, key, anyCaps, other_control != 0);
            r->engine_code = pData->code;
            if (pData->code == vReplaceMaro)
                fillMacro(r);
        }
        return r->action;
    }

    vKeyHandleEvent(vKeyEvent::Keyboard, vKeyEventState::KeyDown, key, (Uint8)caps_status, other_control != 0);
    r->engine_code = pData->code;
    r->ext_code = pData->extCode;

    if (pData->code == vDoNothing) {
        r->action = OK_PASS;
    } else if (pData->code == vWillProcess || pData->code == vRestore || pData->code == vRestoreAndStartNewSession) {
        r->action = OK_CONSUME;
        if (pData->backspaceCount > 0 && pData->backspaceCount < MAX_BUFF)
            r->backspaces = pData->backspaceCount;
        if (pData->newCharCount > 0 && pData->newCharCount <= MAX_BUFF) {
            for (int i = pData->newCharCount - 1; i >= 0; i--)
                pushEngineChar(r, pData->charData[i]);
        }
        if (pData->code == vRestore || pData->code == vRestoreAndStartNewSession) {
            Uint16 ch = keyCodeToCharacter(key | (anyCaps ? CAPS_MASK : 0));
            if (ch != 0)
                pushEntry(r, ch);       // restored word + the key just pressed
            else
                r->action = OK_REPLACE_PASS; // e.g. TAB / arrows: restore word then let the key act
        }
        if (pData->code == vRestoreAndStartNewSession)
            startNewSession();
    } else if (pData->code == vReplaceMaro) {
        fillMacro(r);
    }
    return r->action;
}

// ----- macros (gõ tắt). File format is the UniKey/OpenKey text format "name:content" -----
void ok_macro_load(const char* path) { readFromFile(path, false); }
void ok_macro_save(const char* path) { saveToFile(path); }
int ok_macro_add(const char* name, const char* content) { return addMacro(name, content) ? 1 : 0; }
int ok_macro_delete(const char* name) { return deleteMacro(name) ? 1 : 0; }
int ok_macro_count(void) {
    vector<vector<Uint32>> keys;
    vector<string> texts, contents;
    getAllMacro(keys, texts, contents);
    return (int)texts.size();
}

// ----- convert tool (chuyển mã) -----
// flags: bit0 all caps, bit1 all lower, bit2 caps first letter, bit3 caps each word, bit4 remove marks
int ok_convert(const char* src, int from_code, int to_code, int flags, char* out, int out_size) {
    convertToolFromCode = (Uint8)from_code;
    convertToolToCode = (Uint8)to_code;
    convertToolToAllCaps = flags & 1;
    convertToolToAllNonCaps = flags & 2;
    convertToolToCapsFirstLetter = flags & 4;
    convertToolToCapsEachWord = flags & 8;
    convertToolRemoveMark = flags & 16;
    string result = convertUtil(src);
    // convertUtil() appends a terminating NUL into the string itself
    size_t len = strnlen(result.c_str(), result.size());
    if ((int)len + 1 > out_size)
        return -(int)(len + 1);
    memcpy(out, result.c_str(), len);
    out[len] = 0;
    return (int)len;
}

}
