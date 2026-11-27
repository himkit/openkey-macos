# OpenKey cho Linux (IBus)

Bản Linux của bộ gõ tiếng Việt [OpenKey](https://github.com/tuyenvm/OpenKey) (tác giả Mai Vũ Tuyên),
dựng từ mã nguồn fork [himkit/openkey-macos](https://github.com/himkit/openkey-macos) (bản 2.0.7).

Dùng **nguyên engine C++ gốc** của OpenKey (`engine/`), biên dịch thành `libopenkey.so`, chạy qua
**IBus**, nên dùng được trên cả **Wayland** (GNOME, KDE) lẫn X11.

## Cài đặt

Cần: `g++`, `make`, `python3-gi`, `gir1.2-ibus-1.0`, `ibus` (Ubuntu có sẵn IBus).

```bash
sudo apt install build-essential python3-gi gir1.2-ibus-1.0
cd Sources/OpenKey/linux
make            # build build/libopenkey.so từ engine chung ../engine
make test       # 61 test gõ phím cho engine
./install.sh    # cài vào ~/.local/share/openkey, cần sudo 1 lần để chép file component của IBus
```

Sau đó: **Settings → Keyboard → Input Sources → + → Vietnamese → OpenKey**
(hoặc `./install.sh --add-source` để tự thêm). Đổi bộ gõ bằng `Super+Space`.

Gỡ: `./uninstall.sh`.

## Sử dụng

- **Chuyển Việt/Anh:** `Ctrl+Shift` (nhấn rồi thả), hoặc bấm mục đầu tiên trong menu biểu tượng **V/E**
  trên thanh trên cùng. Đổi phím tắt trong `~/.config/openkey/config.json` (`"switch_key"`, ví dụ
  `"alt+z"`, `"ctrl+space"`, `""` để tắt).
- **Menu V/E:** Kiểu gõ (Telex, VNI, Simple Telex 1/2), Bảng mã (Unicode, TCVN3, VNI Windows,
  Unicode tổ hợp, CP1258), Cách hiển thị, các tuỳ chọn (kiểm tra chính tả, khôi phục phím, đặt dấu
  oà/uý, gõ nhanh, viết hoa đầu câu, z/f/w/j, gõ tắt phụ âm đầu/cuối, gõ tắt...).
- **Gõ tắt (macro):** menu → *Sửa bảng gõ tắt...* mở `~/.config/openkey/macros.txt`
  (định dạng `tắt:nội dung`, giống UniKey/OpenKey), sửa xong chọn *Nạp lại bảng gõ tắt*.
- Ô mật khẩu tự động gõ thô (không bỏ dấu).

### Cách hiển thị

| Chế độ | Cách làm | Dùng được ở |
|---|---|---|
| **Gạch chân** (mặc định) | từ đang gõ hiện gạch chân (preedit), chốt khi gõ dấu cách/dấu câu/Enter | mọi ứng dụng, kể cả terminal |
| **Không gạch chân** | kỹ thuật "backspace" như OpenKey trên macOS: xoá và thay chữ ngay tại con trỏ (IBus surrounding text) | ứng dụng GTK/Qt hỗ trợ surrounding text; ứng dụng không hỗ trợ (terminal...) tự chuyển về gạch chân |

Ở chế độ gạch chân, sau khi đã chốt từ thì không sửa dấu lại được bằng cách xoá lùi vào từ cũ
(bên chế độ không gạch chân thì được, giống macOS).

## Cấu trúc

```
../engine/           engine C++ dùng chung với macOS/Windows (Telex/VNI, chính tả, gõ tắt, chuyển mã)
src/openkey_api.cpp  C API bọc engine: nhận keycode, trả về "xoá N ký tự, chèn các ký tự này"
src/openkey_core.py  binding ctypes cho libopenkey.so
src/openkey_ibus.py  engine IBus: menu, cấu hình, preedit / surrounding text, phím tắt
tests/               test_engine.py (engine), test_ibus.py (end-to-end qua ibus-daemon riêng)
```

`make dist` tạo tarball tự chứa (có sẵn engine và libopenkey.so) để cài trên máy khác.
`make test-ibus` chạy test end-to-end trên một `ibus-daemon` riêng (socket và thư mục cấu hình
riêng), không ảnh hưởng IBus đang chạy trên máy.

## Ghi chú

Đã sửa trong engine chung `../engine/ConvertTool.cpp` (công cụ chuyển mã, ảnh hưởng cả macOS/Windows):
- thiếu `#include <algorithm>` nên không biên dịch được bằng GCC;
- khi không chọn tuỳ chọn hoa/thường nào, toàn bộ văn bản bị đổi thành chữ thường;
- ký tự có dấu ở cuối chuỗi khi chuyển sang VNI Windows / Unicode tổ hợp ra ký tự rác (không tách 2 byte);
- "bỏ dấu" làm mất chữ hoa (`Đi` → `di`).

Phần logic gõ của engine được giữ nguyên; engine nhận keycode X11 (`engine/platforms/linux.h`),
các phím engine không biết (Home, End, F1...) được front end xử lý như ngắt từ. Chưa có trên Linux: cửa sổ cài đặt đồ hoạ (dùng menu
IBus + file JSON), chuyển chế độ thông minh theo từng ứng dụng, giao diện công cụ chuyển mã (đã có
hàm `ok_convert` trong thư viện), fcitx5.

## Giấy phép

GPL, giống OpenKey. Mọi bản phân phối lại phải giữ mã nguồn mở và ghi nguồn OpenKey.
