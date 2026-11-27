//
//  ConvertTool.cpp
//  OpenKey
//
//  Created by Tuyen on 9/4/19.
//  Copyright © 2019 Tuyen Mai. All rights reserved.
//
#include <locale>
#include <codecvt>
#include <algorithm>
#include "ConvertTool.h"
#include "Engine.h"
#include <iostream>
#include <memory.h>

//option
bool convertToolDontAlertWhenCompleted = false;
bool convertToolToAllCaps = false;
bool convertToolToAllNonCaps = false;
bool convertToolToCapsFirstLetter = false;
bool convertToolToCapsEachWord = false;
bool convertToolRemoveMark = false;
Uint8 convertToolFromCode = 0;
Uint8 convertToolToCode = 0;
int convertToolHotKey = 0;

static vector<Uint8> _breakCode = {'.', '?', '!'};

static bool findKeyCode(const Uint32& charCode, const Uint8& code, int& j, int& k) {
    //find character which has tone/mark
    for (map<Uint32, vector<Uint16>>::iterator it = _codeTable[code].begin(); it != _codeTable[code].end(); ++it) {
        for (int z = 0; z < it->second.size(); z++) {
            if (charCode == it->second[z]) {
                j = it->first;
                k = z;
                return true;
            }//end if
        }
    }
    return false;
}

static Uint16 getUnicodeCompoundMarkIndex(const Uint16& mark) {
    for (int i = 0; i < 5; i++) {
        if (mark == _unicodeCompoundMark[i]) {
            return ((i + 1) << 13);
        }
    }
    return 0;
}

static bool hasCaseOption() {
    return convertToolToAllCaps || convertToolToAllNonCaps || convertToolToCapsFirstLetter || convertToolToCapsEachWord;
}

//pick the target character; k: even = upper case, odd = lower case
static Uint16 pickTarget(const int& j, int k, const bool& shouldUpperCase) {
    //fix: only change case when a case option is selected
    //(before, a plain conversion turned the whole text into lower case)
    if (hasCaseOption()) {
        if ((convertToolToAllCaps || shouldUpperCase) && k % 2 != 0) {
            k--;
        } else if ((convertToolToAllNonCaps || !shouldUpperCase) && k % 2 == 0) {
            k++;
        }
    }
    if (convertToolRemoveMark) {
        //fix: keep upper case letters (Đ -> D, not d)
        Uint16 c = keyCodeToCharacter((Uint8)j | (k % 2 == 0 ? CAPS_MASK : 0));
        if (c != 0)
            return c;
    }
    return _codeTable[convertToolToCode][j][k];
}

static void emitTarget(vector<wchar_t>& out, const Uint16& target) {
    if (convertToolToCode == 0 || convertToolToCode == 1) { //Unicode, TCVN3
        out.push_back(target);
    } else if (convertToolToCode == 2 || convertToolToCode == 4) { //VNI, VN Locale 1258
        out.push_back((Uint8)target);
        if (HIBYTE(target) > 32)
            out.push_back(target>>8);
    } else if (convertToolToCode == 3) { //Unicode Compound
        if ((target >> 13) > 0) {
            out.push_back(target & 0x1FFF);
            out.push_back(_unicodeCompoundMark[(target>>13) - 1]);
        } else {
            out.push_back(target);
        }
    }
}

string convertUtil(const string& sourceString) {
    wstring data = utf8ToWideString(sourceString);
    Uint16 t = 0, target;
    int j, k, p;
    vector<wchar_t> _temp;
    bool hasBreak = false;
    bool shouldUpperCase = false;
    if (convertToolToCapsFirstLetter || convertToolToCapsEachWord)
        shouldUpperCase = true;
    if (convertToolToAllNonCaps)
        shouldUpperCase = false;
    
    for (int i = 0; i < data.size(); i++) {
        p = 0;
        //find char with tone/mark
        if (i < data.size() - 1) {
            switch (convertToolFromCode) {
                case 2: //VNI
                case 4: //1258
                    t = (Uint16)data[i] | (data[i+1] << 8);
                    p = 1;
                    break;
                case 3:{ //Unicode Compound
                    target = getUnicodeCompoundMarkIndex(data[i+1]);
                    if (target > 0){
                        t = (Uint16)data[i] | target;
                        p = 1;
                    } else {
                        t = (Uint16)data[i];
                    }
                    break;
                }
                default:
                    t = (Uint16)data[i];
                    break;
            }
            
            if (findKeyCode(t, convertToolFromCode, j, k)) {
                i += p;
                emitTarget(_temp, pickTarget(j, k, shouldUpperCase));
                shouldUpperCase = false;
                hasBreak = false;
                continue;
            }
        }
        
        //find primary keycode first
        t = (Uint16)data[i];
        if (findKeyCode(t, convertToolFromCode, j, k)) {
            //fix: this branch (used for the last character) pushed the target
            //without splitting 2-byte VNI / compound characters
            emitTarget(_temp, pickTarget(j, k, shouldUpperCase));
            shouldUpperCase = false;
            hasBreak = false;
            continue;
        }
        
        //if dont find => normal char
        //fix: keep the original case when no case option is selected
        if (!hasCaseOption())
            _temp.push_back(data[i]);
        else if (convertToolToAllCaps || shouldUpperCase)
            _temp.push_back(towupper(data[i]));
        else
            _temp.push_back(towlower(data[i]));
        
        if (t == '\n' || (hasBreak && t == ' ')) {
            if (convertToolToCapsFirstLetter || convertToolToCapsEachWord)
                shouldUpperCase = true;
        } else if (t == ' ' && convertToolToCapsEachWord) {
            shouldUpperCase = true;
        } else if (std::find(_breakCode.begin(), _breakCode.end(), t) != _breakCode.end()) {
            hasBreak = true;
        } else {
            shouldUpperCase = false;
            hasBreak = false;
        }
    }
    _temp.push_back(0);
    wstring str(_temp.begin(), _temp.end());
    return wideStringToUtf8(str);
}

