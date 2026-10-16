# MapleDiscordBridge - KuroMS Web Client Documentation (`web.md`)

Tài liệu kỹ thuật tổng hợp toàn bộ kiến trúc, cơ chế hoạt động ngầm, hướng dẫn cấu hình, lịch sử tối ưu và giải quyết sự cố của phiên bản **KuroMS Web Client** (`web_client/`).

---

## 1. Tổng quan & Mục đích

Phiên bản Web Client (`web_client/MapleDiscordBridge_WebClient.py`) được thiết kế riêng cho người chơi game **KuroMS Web** (nền tảng HTML5 Canvas / WebGL tại `https://play.playkuro.com/`).

### Khác biệt cốt lõi so với bản Desktop Client:
* **Bản Desktop:** Dùng Windows API (`PostMessageW` gửi `WM_KEYDOWN`/`WM_KEYUP`/`WM_CHAR` trực tiếp vào `HWND` của cửa sổ game).
* **Bản Web:** Trình duyệt hiện đại chạy trong môi trường sandbox cô lập. Các sự kiện `PostMessageW` **không** được trình duyệt chuyển giao vào WebGL Canvas hoặc các thẻ input trong DOM. Nếu dùng `SendInput` (Win32), người dùng sẽ bị cướp chuột, liệt phím, kẹt phím khi chat Discord hoặc chuyển cửa sổ.
* **Giải pháp Web Client:** Điều khiển trực tiếp trình duyệt thông qua **Chrome DevTools Protocol (CDP)** qua cổng kết nối nội bộ `127.0.0.1:9222`.

---

## 2. Kiến trúc Điều khiển Ngầm qua Chrome DevTools Protocol (CDP)

```
[Discord User] 
      │  (Slash commands: /reply, /bot, /buff, /screen, /status)
      ▼
[Cloudflare Worker] (cf-worker/)
      │  (Pusher Realtime Event: channel machine-{name})
      ▼
[MapleDiscordBridge_Web.exe] (v56+)
      │
      ├──► CDP WebSocket (ws://127.0.0.1:9222/devtools/page/...)
      │     ├─► Input.dispatchKeyEvent (Xả skill đánh ngầm không cần focus)
      │     ├─► Runtime.evaluate (Gõ chat trực tiếp vào #chat-input & submit ngầm)
      │     └─► Page.captureScreenshot (Chụp canvas chuẩn 100%, không dính taskbar)
      │
      └──► Fallback Win32 API (Chỉ kích hoạt khi người dùng không mở game bằng Mo_KuroMS.bat)
```

---

## 3. Khởi chạy Trình duyệt: `Mo_KuroMS.bat`

Để mở cổng debug CDP 9222 và cách ly tài khoản chơi game khỏi trình duyệt chính của người dùng:

```batch
start "" "%EDGE_EXE%" --app=https://play.playkuro.com/ --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir=%LOCALAPPDATA%\KuroMS_Browser --disable-background-timer-throttling
```

### Giải thích các cờ (Flags):
1. `--app=https://play.playkuro.com/`: Mở game dưới dạng cửa sổ ứng dụng độc lập (không thanh URL, không tab bar rườm rà).
2. `--remote-debugging-port=9222`: Mở cổng WebSocket điều khiển nội bộ cho Python client.
3. `--remote-allow-origins=*`: Cho phép Python kết nối WebSocket nội bộ không bị chặn CORS.
4. `--user-data-dir=%LOCALAPPDATA%\KuroMS_Browser`: Sử dụng thư mục profile riêng. Điều này cho phép mở cổng 9222 độc lập mà không bị xung đột với trình duyệt Edge/Chrome chính người dùng đang lướt web hàng ngày.
5. `--disable-background-timer-throttling`: Ngăn Chromium bóp nghẽn các bộ đếm thời gian (`setInterval`/`setTimeout`) khi người dùng tab sang ứng dụng khác (Discord, YouTube...).

### ⚠️ Lưu ý sống còn về GPU (Bài học tối ưu):
* **TUYỆT ĐỐI KHÔNG DÙNG:** `--disable-backgrounding-occluded-windows` và `--disable-renderer-backgrounding`.
* *Lý do:* Hai cờ này ép bộ xử lý đồ họa GPU của trình duyệt phải render WebGL 3D liên tục ở mức công suất tối đa (100% FPS / 144Hz) ngay cả khi bị cửa sổ khác che hoặc gập máy, dẫn đến hiện tượng **ngốn 80-100% GPU, nóng máy và quạt laptop kêu to**.

---

## 4. Các Tính Năng & Cơ Chế Hoạt Động

### 4.1. Tự Động Đánh Quái Ngầm (`auto_attack_thread`)
* **Chế độ:** Hỗ trợ `hold` (mặc định) và `spam`.
* **Cơ chế chống mất phím khi Unfocus (Tab ra ngoài):**
  * Trong trình duyệt web, khi người dùng click sang cửa sổ khác (như Discord), trình duyệt sẽ kích hoạt sự kiện `window.onblur`. Sự kiện này xóa toàn bộ trạng thái phím đè (`keysDown = {}`) trong game engine.
  * Vì vậy, ở chế độ `hold`, client gửi xung `keydown` đều đặn theo chu kỳ `interval_ms` (mặc định 50ms). Khi tab ra ngoài, dù có bị `blur`, xung `keydown` kế tiếp ngay sau đó sẽ lập tức duy trì trạng thái đánh liên tục mà **không bao giờ bị đứng yên**.
* **Ngắt phím an toàn:** Khi tắt bot (`F1` hoặc `/bot`), client gửi `is_down=False` để nhả phím cả CDP lẫn Win32.

### 4.2. Hệ Thống Điều Phối Auto-Buff (`run_auto_buff`)
* **Khóa an toàn độc lập (`buff_lock` & `is_buffing`):**
  * Bản cũ từng bị lỗi nghiêm trọng khi gán `auto_attack_running = False` trong luồng buff. Khi nhiều buff (F2, F7, F8) chạy đồng thời, chúng ghi đè cờ của nhau làm bot bị tắt hẳn.
  * Bản mới (v56+) sử dụng cờ riêng `is_buffing` và mutex `buff_lock`. **Tuyệt đối không đụng vào công tắc `auto_attack_running` của người dùng.**
* **Quy trình cast buff chuẩn (giống 100% desktop client):**
  1. Tạm nhả phím đánh (`send_key(attack_key, is_down=False)`).
  2. Chờ `0.5s` để nhân vật dừng hẳn động tác tấn công về trạng thái nhàn rỗi (idle).
  3. Gửi phím buff (nhấn giữ `80ms` qua CDP, chỉ gửi 1 lần để kích hoạt macro in-game).
  4. Chờ animation hoàn tất:
     * **Lệnh slash `/buff` Discord:** Chờ trọn vẹn **`3.5 giây`** để nhân vật múa xong trọn vẹn cả 3 skill của macro in-game (hoặc combo A-S-D của Fox) mà không bị phím đánh làm gián đoạn hay huỷ chiêu!
     * **Luồng Auto-buff theo chu kỳ:** Chờ `cast_delay = max(1.0, (delay_ms + 300) / 1000.0)`. Nếu người dùng gán macro 3 skill vào F2/F7/F8, chỉ cần cấu hình `autobuff_delay_ms = 3500` trong `config.ini`.
  5. Giải phóng `is_buffing = False` $\rightarrow$ Luồng đánh tự động tiếp tục xả skill tức thì!
* **Giãn cách thời gian buff ban đầu:**
  * Buff 1 (F2): Bắt đầu sau 2 giây kể từ khi bật.
  * Buff 2 (F8): Bắt đầu sau 5 giây.
  * Buff 3 (F7): Bắt đầu sau 8 giây.
  * Không bao giờ bị dồn các buff vào cùng một thời điểm gây nghẽn kỹ năng.

### 4.3. Chat Ngầm Siêu Tốc (`/reply` & `send_chat`) - Chuẩn 100% Client
1. **Tạm dừng Auto-Attack & Auto-Buff:** Nhả phím tấn công và dừng 0.4s để tránh xung đột phím hay lọt phím đánh vào khung chat.
2. **Nạp nội dung:** Nạp chuỗi tin nhắn vào `chat-input` và kích hoạt sự kiện `input`.
3. **Gửi Enter lần 1:** Nộp tin nhắn vào kênh chat game.
4. **Gửi Enter lần 2 (Cực kỳ quan trọng - giống client desktop line 198):** Đóng khung chat, đưa nhân vật thoát khỏi trạng thái chatbar để tiếp tục đánh và di chuyển.
5. **Blur input & Focus Game Canvas:** Đảm bảo `canvas#game` nhận lại tiêu điểm bàn phím hoàn toàn.
6. **Bật lại Auto-Attack:** Luồng tự đánh tự động tiếp tục bắn ngay lập tức mà không cần người dùng thao tác gì thêm!

### 4.4. Chụp Màn Hình (`/screen`)
* Gọi trực tiếp CDP `Page.captureScreenshot` để chụp lại chính xác canvas của game, lưu thành file `screenshot_{machine}.png` và gửi lên Discord.
* Fallback qua thư viện `mss` nếu CDP chưa kết nối.

---

## 5. Cấu Trúc Thư Mục `web_client/`

```
web_client/
├── MapleDiscordBridge_WebClient.py   # Mã nguồn chính (v1.0 Web)
├── build.bat                         # Script PyInstaller tự động đóng gói
├── Mo_KuroMS.bat                     # Script mở KuroMS trên Edge/Chrome có port 9222
├── config.ini                        # File cấu hình mẫu
├── templates/                        # Thư mục chứa mẫu ảnh GM detector
└── dist/                             # Thư mục thành phẩm để giao cho người dùng:
    ├── MapleDiscordBridge_Web.exe    # File thực thi độc lập (Admin)
    ├── Mo_KuroMS.bat                 # File bat mở game
    ├── config.ini                    # File cấu hình hoạt động
    └── templates/                    # Mẫu ảnh nhận diện
```

---

## 6. Hướng Dẫn Đóng Gói (Build Process)

Khi chỉnh sửa code trong `MapleDiscordBridge_WebClient.py`:
1. Tắt tiến trình `MapleDiscordBridge_Web.exe` đang chạy (nếu có).
2. Chạy lệnh đóng gói qua PyInstaller:
   ```cmd
   cd /d d:\Down\s\MapleDiscordBridge\web_client
   py -m PyInstaller --onefile --console --uac-admin --add-data "templates;templates" --distpath dist --workpath build --name MapleDiscordBridge_Web MapleDiscordBridge_WebClient.py
   ```
3. Đảm bảo copy đồng bộ `Mo_KuroMS.bat` và `config.ini` vào thư mục `dist/`.

---

## 7. Cấu Hình Chuẩn `config.ini`

```ini
[bridge]
# Tên máy tính định danh trên Discord (dutch, fox, jira, dao, bae, fan, peo, sin)
machine_name = dutch

# Cho phép nhận lệnh /reply từ Discord vào game (true/false)
reply_enabled = true

# ==================================================
# AUTO ATTACK (Đánh quái ngầm)
# ==================================================
attack_hotkey = f1
attack_key = ctrl
attack_interval_ms = 50
attack_mode = hold

# ==================================================
# AUTO BUFF 1
# ==================================================
autobuff_hotkey = f2
autobuff_key = t
autobuff_interval_ms = 240000
autobuff_delay_ms = 900

# ==================================================
# AUTO BUFF 2
# ==================================================
autobuff2_hotkey = f8
autobuff2_key = pageup
autobuff2_interval_ms = 601000
autobuff2_delay_ms = 900

# ==================================================
# AUTO BUFF 3
# ==================================================
autobuff3_hotkey = f7
autobuff3_key = v
autobuff3_interval_ms = 31500
autobuff3_delay_ms = 500

# ==================================================
# AUTO ANCHOR
# ==================================================
anchor_enabled = false

[detector]
enabled = false
ntfy_server = https://ntfy.sh
ntfy_topic = your_topic_name_here
scan_interval = 0.5
threshold = 0.86
cooldown = 30.0

# ==================================================
# VÙNG QUÉT KHUNG CHAT (FLEXIBLE ROI - TÙY CHỈNH SIZE)
# Tự động thích ứng theo Canvas Game, không phụ thuộc size trình duyệt
# ==================================================
# Khoảng cách từ đáy màn hình game lên đỉnh khung chat (pixel)
chat_roi_bottom = 180
# Chiều rộng vùng quét (pixel)
chat_roi_width = 550
# Chiều cao vùng quét (pixel) - đã nhích lên để không dính thanh gõ chatbar ở đáy
chat_roi_height = 115
# Khoảng cách lệch từ mép trái (pixel, mặc định 0)
chat_roi_left = 0
```

---

## 8. Lịch Sử Sự Cố & Giải Pháp (Troubleshooting Log)

| Vấn đề gặp phải | Nguyên nhân | Giải pháp triệt để |
|---|---|---|
| **Dữ liệu game phải tải lại khi mở `Mo_KuroMS.bat`** | Do cờ `--user-data-dir=%LOCALAPPDATA%\KuroMS_Browser` tạo một profile mới để tránh xung đột với trình duyệt chính. Lần đầu mở game phải tải ~226MB cache. | Sau lần chạy đầu tiên, toàn bộ dữ liệu (~900MB gồm Service Worker & CacheStorage) đã được lưu vĩnh viễn trên SSD. Các lần mở tiếp theo game load tức thì. |
| **Card màn hình (GPU) bị ngốn 80-100%, quạt hú to** | Trong `Mo_KuroMS.bat` có cờ `--disable-backgrounding-occluded-windows` và `--disable-renderer-backgrounding`, ép GPU vẽ 3D liên tục ở 144Hz kể cả khi bị che/unfocus. | Gỡ bỏ 2 cờ ép GPU này, chỉ giữ lại `--disable-background-timer-throttling`. Khi tab ra ngoài, GPU tự hạ tải về gần 0%, máy mát và quạt êm. |
| **Tab ra ngoài (Unfocus) bị mất đánh** | Trình duyệt kích hoạt sự kiện `window.blur` khi mất focus, xóa sạch các phím đang đè (`hold`) trong game engine nếu chỉ gửi keydown 1 lần. | Trong `auto_attack_thread`, gửi xung `keydown` theo chu kỳ 50ms liên tục. Dù có bị `blur`, nhịp kế tiếp sẽ giữ cho nhân vật xả đạn liên tục không ngừng. |
| **Bật F2/F7 thì bị gián đoạn, mất hẳn auto đánh** | 1. Các luồng buff cùng can thiệp biến cờ `auto_attack_running = False` gây xung đột chết cờ.<br>2. Thiếu delay buffer animation sau khi cast buff.<br>3. Bản cũ gửi keydown 1 lần bị animation nuốt mất. | Tách cờ riêng `is_buffing`, đồng bộ hóa bằng `buff_lock`. Thêm buffer 300ms cho animation cast skill. Tự động phục hồi nhịp đánh ngay sau khi cast xong. |
| **Lệnh slash `/buff` từ Discord không hoạt động** | Discord gửi mã hex phím dạng chuỗi (`0x46`, `0x41`...). Bản cũ đưa thẳng chuỗi `0x46` vào CDP khiến Chrome không nhận diện được phím, đồng thời không tạm dừng phím đánh khiến game bị kẹt động tác xả đạn không cast được buff. | Thêm bộ giải mã `parse_buff_key` (chuyển `0x46` $\rightarrow$ `f`, `0x41` $\rightarrow$ `a`), kết hợp `buff_lock` tạm nhả attack, chờ 0.25s idle, nhấn giữ phím 80ms, chờ trọn 0.9s animation và tự động tiếp tục xả skill. Hỗ trợ combo A-S-D cho máy Fox. |
| **Treo máy qua đêm / Tắt màn hình đi ngủ** | Nếu máy rơi vào chế độ **Sleep / Hibernate**, Windows sẽ ngắt Wi-Fi/LAN làm mất kết nối game và dừng bot. | **Tuyệt đối KHÔNG chọn Sleep**. Để tắt màn hình: Chỉnh trong Windows Power Options: Khi gập nắp (Close the lid) $\rightarrow$ **Do nothing**, và cắm sạc. Hoặc cài đặt tự tắt màn hình sau 1-2 phút. |
| **Tắt exe nhưng nhân vật vẫn tiếp tục đánh trong game** | 1. Khi chạy phím ở chế độ `hold`, CDP gửi `rawKeyDown` cho Chromium. Nếu tắt exe đột ngột (bấm nút X, tắt terminal, Ctrl+C), kết nối socket bị đứt trước khi gửi `keyUp`, khiến Chrome lưu trạng thái phím Ctrl đè mãi trong bộ nhớ.<br>2. Các tiến trình `MapleDiscordBridge_Web.exe` chạy ngầm cũ chưa bị đóng. | 1. Đăng ký hàm `cleanup_on_exit()` qua cả `atexit` và `SetConsoleCtrlHandler` của Windows. Khi bấm X hoặc tắt exe, client tự động gửi sự kiện `keyUp` cho phím đánh và các phím di chuyển, nhả cả Win32 Virtual Key, rồi mới ngắt kết nối CDP an toàn.<br>2. Tích hợp `kill_other_instances()` lúc khởi động để tự động dọn sạch các tiến trình cũ chạy ngầm. |
| **Thiếu file `config.ini` hoặc config không có hướng dẫn** | Bản cũ ghi trực tiếp các cặp key thô vào file khi thiếu config, không có chú thích và không có menu chọn máy. | Bổ sung hàm `generate_formatted_config` và menu chọn máy tính (1-8: dutch, fox, jira, dao, bae, fan, peo, sin) giống 100% bản desktop client. Tự động đồng bộ các trường còn thiếu với đầy đủ chú thích chi tiết. |

---

## 9. Quy Chuẩn Push Cập Nhật & Thông Báo (Release Guidelines)

### 9.1. Quản Lý Source & Đóng Gói
* **Kho lưu trữ chính thức (GitHub):** `https://github.com/dutch25/MapleBridgeWeb.git`
  * Bản Web Client được quản lý độc lập tại repository này, hoàn toàn tách biệt với repo Desktop Client (`MapleBridge`).
* **Đóng gói file nén `MapleDiscordBridge_Web.zip`:**
  * Chỉ nén duy nhất file `MapleDiscordBridge_Web.exe` có sẵn trong `dist/`.
  * Đặt file `MapleDiscordBridge_Web.zip` trực tiếp tại repo để tải về qua GitHub:
    `https://raw.githubusercontent.com/dutch25/MapleBridgeWeb/main/MapleDiscordBridge_Web.zip`
* **Lệnh slash `/download` trên Discord:**
  * Dẫn link trực tiếp tới GitHub repo bản Web: `https://github.com/dutch25/MapleBridgeWeb`.

### 9.2. Quy Tắc Thông Báo Lên Discord (Changelog Format)
* **Tuyệt đối không thêm icon, emoji linh tinh (không dùng 🚀✨⚡🛑👤⏰...).**
* **Chỉ ghi ngắn gọn, chính xác những thứ ĐÃ ĐƯỢC CẬP NHẬT (UPD).**
* Format súc tích, chuyên nghiệp, đi thẳng vào các thay đổi thực tế:
  ```text
  [THÔNG BÁO CẬP NHẬT: KUROMS WEB CLIENT]

  Cập nhật:
  - Bổ sung máy: Jen & Minh
  - Lệnh /kill an toàn (chỉ tắt port 9222 KuroMS, bảo vệ port 9223 Market)
  - Thêm timestamp [HH:MM:SS] trong console
  - Hiển thị danh tính người bấm kill
  - Chống tắt màn hình và tối ưu giữ phím
  ```

