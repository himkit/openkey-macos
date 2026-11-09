# AGENTS.md

OpenKey is an open-source Vietnamese keyboard app for macOS and Windows (Linux is a placeholder). It is **not** an IME/input-method bundle: it captures keyboard events and rewrites text via the "backspace" technique using the macOS Accessibility API (win32: low-level keyboard hooks). It runs as a regular menu-bar/tray app and requires the macOS Accessibility permission, which shapes most of the macOS code.

## Layout

- `Sources/OpenKey/engine/` — shared C++ core (`Engine`, `Vietnamese`, `Macro`, `SmartSwitchKey`, `ConvertTool`). No build system of its own: each platform app compiles these `.cpp` files directly into its target. Engine changes affect both platforms.
- `Sources/OpenKey/engine/platforms/{mac,win32,linux}.h` — per-OS key-code maps; the rest of the engine is platform-agnostic.
- `Sources/OpenKey/macOS/` — Xcode project with a **single buildable target** `OpenKey` → `OpenKey.app`. App sources live in `macOS/ModernKey/` (internal product name "ModernKey" — don't rename). `OpenKey.mm` (Obj-C++) is the bridge to the C++ engine.
- `Sources/OpenKey/win32/` — Visual Studio solution at `win32/OpenKey/OpenKey.sln` (note the extra `OpenKey/` level) with two projects: `OpenKey` and `OpenKeyUpdate`. VS2017-era C++.
- Trap: the Xcode project contains `OpenKeyHelper/`, `OpenKeyUpdate/`, `OpenKeyTest/` source groups plus stale shared schemes `OpenKeyHelper.xcscheme` / `OpenKeyUpdate.xcscheme` whose targets no longer exist. Only the `OpenKey` scheme builds; the others are dead legacy.
- UI copy, comments, commit messages, and docs are mixed Vietnamese/English. Don't translate or "fix" Vietnamese strings.

## Building

macOS (no CI — built locally in Xcode):
- Open `Sources/OpenKey/macOS/OpenKey.xcodeproj`, scheme `OpenKey`. Release = Product > Archive (see `macOS_Build.md`).
- Target signing is Automatic with team `8S7348QV8Q`; outside contributors must switch to ad-hoc signing manually (project-level configs already use `CODE_SIGN_IDENTITY = "-"`).
- Known build error `invalid in C99` at `ModernKey/MJAccessibilityUtils.m:26` (`isEnabled = AXAPIEnabled();`): fix by adding `extern BOOL AXAPIEnabled();` at the top of the file.

Windows:
- CI (`.github/workflows/msbuild.yml`) runs on push/PR to `master`: `msbuild -p:Configuration=Release -p:Platform=x86|x64 Sources\OpenKey\win32\OpenKey\OpenKey.sln` on `windows-latest`. Replicate that locally; only Windows CI exists, macOS changes get no CI signal.

## Testing

No test targets, schemes, or suites anywhere. Verification = successful build plus manual typing checks in the running app.

## Releases & versioning

Root `version.json` is the auto-update feed fetched at runtime from `raw.githubusercontent.com` by all three updaters (`macOS/ModernKey/OpenKeyManager.m`, `win32/.../OpenKeyManager.cpp`, `win32/.../OpenKeyUpdate.cpp`). A version bump must touch every place, and they already drift (e.g. pbxproj says 2.0.4/48, version.json 2.0.3/47):
- macOS: `MARKETING_VERSION` / `CURRENT_PROJECT_VERSION` in `project.pbxproj`
- Windows: `FILEVERSION` / `PRODUCTVERSION` blocks in `OpenKey.rc` and `OpenKeyUpdate.rc`
- `version.json` at repo root: `latestVersion` (macOS) and `latestWinVersion` (Windows); Windows packs `versionCode` as `(major << 16) | minor` (2.0.2 → 131074), parsed in `win32/.../OpenKeyManager.cpp`.

## Conventions

- Default branch is `master`; PRs from forks are the norm.
- License is GPL: derivative distributions must stay open-source and credit OpenKey — don't introduce incompatible-license dependencies.
