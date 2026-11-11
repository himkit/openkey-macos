# AGENTS.md

OpenKey is an open-source Vietnamese keyboard app for macOS and Windows (Linux is a placeholder). It is **not** an IME/input-method bundle: it captures keyboard events and rewrites text via the "backspace" technique using the macOS Accessibility API (win32: low-level keyboard hooks). It runs as a regular menu-bar/tray app and requires the macOS Accessibility permission, which shapes most of the macOS code.

This repo is `himkit/openkey-macos`, a fork of upstream `tuyenvm/OpenKey` that ships **macOS only**. Its releases are distributed through the Homebrew tap `himkit/homebrew-tap` (see Releases). The `win32/` and `linux/` trees are upstream code kept as-is: not built, released, or maintained here.

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
- Command-line build: `xcodebuild -project OpenKey.xcodeproj -scheme OpenKey -configuration Release CODE_SIGN_IDENTITY=- CODE_SIGNING_REQUIRED=NO DEVELOPMENT_TEAM= MACOSX_DEPLOYMENT_TARGET=10.13 ARCHS="arm64 x86_64" ONLY_ACTIVE_ARCH=NO`. The target's own deployment target (10.10) fails on current Xcode with `SDK does not contain 'libarclite'`; the override fixes it. Release builds are universal (`lipo -archs` shows `x86_64 arm64`).
- A rebuilt, ad-hoc signed app counts as a new app for macOS: re-grant Accessibility (remove the old entry, add the new `.app`) or it quits right after launch.
- Known build error `invalid in C99` at `ModernKey/MJAccessibilityUtils.m:26` (`isEnabled = AXAPIEnabled();`): fix by adding `extern BOOL AXAPIEnabled();` at the top of the file.

Windows:
- CI (`.github/workflows/msbuild.yml`) runs on push/PR to `master`: `msbuild -p:Configuration=Release -p:Platform=x86|x64 Sources\OpenKey\win32\OpenKey\OpenKey.sln` on `windows-latest`. Replicate that locally; only Windows CI exists, macOS changes get no CI signal.

## Testing

No test targets, schemes, or suites anywhere. Verification = successful build plus manual typing checks in the running app.

## Releases & versioning

Release flow for this fork (Homebrew is the update channel):
1. Bump `MARKETING_VERSION` / `CURRENT_PROJECT_VERSION` in `project.pbxproj` (both configs), commit, push `master`.
2. Build Release (command above), have the user test-type it, then zip: `ditto -c -k --keepParent OpenKey.app OpenKey-X.Y.Z.zip`.
3. `gh release create vX.Y.Z OpenKey-X.Y.Z.zip -R himkit/openkey-macos --target master`.
4. In `himkit/homebrew-tap`, set `version` and `sha256` in `Casks/openkey.rb` (the `url` derives from `#{version}`). Push the tap only after the release asset downloads, or installs fail.

The in-app updater does not see fork releases: `OpenKeyManager.m` reads `version.json` from upstream `tuyenvm/OpenKey`, so `version.json` here is upstream data and stays untouched. The bundled `OpenKeyUpdate.app` no longer exists; accepting an update prompt opens `himkit/openkey-macos/releases/latest`.

## Conventions

- Default branch is `master`.
- License is GPL: derivative distributions must stay open-source and credit OpenKey — don't introduce incompatible-license dependencies.
