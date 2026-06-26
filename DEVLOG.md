# Mac Sender — Nhật ký phát triển & kiến thức quan trọng

File này ghi lại toàn bộ lịch sử debug, quyết định kỹ thuật, và các thông tin cần
biết để làm việc tiếp với project này — tránh phải dò lại từ đầu ở mỗi session mới.

## Tổng quan project

`mac_sender.py` — app GUI (customtkinter) để chuyển file giữa các máy Mac trong
mạng LAN qua `rsync` + `ssh`/`sshpass`. Có 2 tab:
- **Gửi file**: chọn folder nguồn, scan máy đích online (.local mDNS), drill-down
  chọn folder đích trên máy đích, theo dõi tiến độ/tốc độ/ETA.
- **Cấu hình máy**: quản lý password SSH dùng chung + danh sách hostname các máy.

Config người dùng lưu ở `~/.mac_sender_config.json` (không nằm trong git).

## Repo & cách cài đặt cho máy khác

Repo: https://github.com/anhkienhoang2609-lang/mac-sender (Public)

3 file cốt lõi để deploy:
- `mac_sender.py` — code chính
- `install.sh` — cài Homebrew + sshpass + rsync + python-tk + venv + tạo launcher
- `bootstrap.sh` — tải code (tarball GitHub) + chạy `install.sh` + tự mở app

**Lệnh cài 1-dòng cho máy đích:**
```bash
curl -fsSL https://raw.githubusercontent.com/anhkienhoang2609-lang/mac-sender/main/bootstrap.sh | bash
```
Kết quả: tạo folder `~/MacSender`, venv riêng, file `Mac Sender.command` để
double-click mở app sau này.

## Danh sách bug đã tìm & sửa (theo thứ tự phát hiện)

1. **Tên folder nguồn bị cắt mất khoảng trắng cuối** — `src_entry.get().strip()`
   ở `_start()` strip cả khoảng trắng là 1 phần tên file thật (ví dụ folder tên
   `"... Colorado "` có dấu cách cuối). Sửa: chỉ `.rstrip("/")`, không `.strip()`.

2. **Màn hình app trắng (blank)** — chạy bằng Python hệ thống
   (`/usr/bin/python3`) có Tk **8.5** rất cũ, lỗi render trắng kinh điển trên
   macOS bản mới. Fix: luôn chạy bằng Python có Tk ≥ 8.6 (Homebrew python hoặc
   venv tạo từ `install.sh`, dùng `python-tk@3.12`).

3. **rsync tạo folder rác có ký tự `\` trong tên** (ví dụ
   `KEO\ FILE\ CHO\ SAM\ DI` thay vì đi vào `KEO FILE CHO SAM DI` có sẵn) —
   code tự thêm `dst.replace(" ", "\\ ")` để escape khoảng trắng, nhưng lệnh
   chạy qua `subprocess.Popen` với list args (không qua shell) nên `\` bị hiểu
   là ký tự thật trong tên path. **Không cần escape gì cả** khi dùng list args
   — rsync tự xử lý path có khoảng trắng đúng nếu để nguyên string.

4. **Tiến trình "ma" chạy code cũ** — nhiều lần sửa code nhưng lỗi vẫn tái
   diễn vì có tiến trình Python cũ (đôi khi chạy từ file đã bị xoá ở
   `~/Downloads`) vẫn đang chạy trong RAM. Luôn `pkill -f mac_sender.py` trước
   khi chạy lại để test sau khi sửa code.

5. **ETA không hiện / cập nhật** — regex `eta_re = r"(\d+:\d+:\d+)\s*$"` ép ETA
   phải ở cuối dòng, nhưng dòng progress của rsync khi 1 file vừa xong có thêm
   `(xfr#N, to-chk=M/N)` sau giờ ETA → không match được. Bỏ anchor `$`.

6. **Tiến độ/tốc độ/ETA hoàn toàn không cập nhật real-time** (bug nặng nhất,
   2 lớp):
   - Lớp 1: `self.process.stdout.read(1024)` (buffered read) **chờ tích đủ
     1024 byte mới trả về**, không trả ngay khi có dữ liệu — output ngắn của
     rsync (vài chục byte/lần) gần như không bao giờ đủ. Fix: dùng
     `os.read(fd, 4096)` (unbuffered) — trả về ngay khi có dữ liệu.
   - Lớp 2: rsync `--info=progress2` redraw bằng `\r` (không phải `\n`), nhưng
     code cũ chỉ tách dòng theo `\n` (`for line in stdout`) → các bản cập nhật
     bị dồn cục. Fix: tự tách buffer theo cả `\r` và `\n`.

7. **customtkinter `configure(dict)` không áp dụng** — gọi
   `widget.configure({"text": "50%"})` (dict truyền theo vị trí) **không lỗi
   nhưng cũng không cập nhật UI thật** — CTkLabel override `configure()` theo
   cách riêng, không tương thích kiểu gọi dict-positional của tkinter gốc.
   Phải gọi bằng kwarg: `widget.configure(text="50%")`. Khi cần gọi qua
   `self.after(0, ...)`, dùng `lambda: widget.configure(text=value)` (capture
   giá trị bằng default-arg để tránh late-binding closure bug).

8. **SSH "Too many authentication failures" / lỡ route qua IPv6** —
   `editor1.local` resolve ra cả IPv4 (`192.168.1.17`) và IPv6 link-local
   (`fe80::...`) qua mDNS. SSH có lúc chọn nhầm IPv6 gây lỗi xác thực. Fix:
   thêm cờ `-4` vào mọi lệnh `ssh`/`rsync -e ssh` để ép luôn dùng IPv4.

9. **SSH host key đổi → bị chặn cả password auth** — khi máy đích cài lại OS
   hoặc đổi SSH key, client báo "REMOTE HOST IDENTIFICATION HAS CHANGED" và
   **tự tắt password/keyboard-interactive auth** dù có
   `StrictHostKeyChecking=no` (cơ chế chống MITM của OpenSSH, không bị bypass
   bởi StrictHostKeyChecking). Fix thủ công khi gặp:
   `ssh-keygen -R <hostname>.local` để xoá key cũ trong `known_hosts`.

10. **Máy đích dùng `openrsync`** (rsync giả lập, bản built-in cũ của macOS,
    tương đương rsync 2.6.9 / protocol 29) — không hiểu `--info=name` (modern
    GNU rsync flag) khi bị forward qua remote, làm rsync protocol lỗi luôn.
    Phải dùng cờ cổ điển `-v` (verbose) để log tên file, tương thích cả hai
    phía.

11. **Hardcode path `/opt/homebrew/bin/sshpass`, `/opt/homebrew/bin/rsync`** —
    không chạy được trên Intel Mac (Homebrew ở `/usr/local/bin`) hoặc máy có
    setup khác. Fix: hàm `_find_bin()` tự dò theo thứ tự
    `/opt/homebrew/bin` → `/usr/local/bin` → `shutil.which()`.

12. **`install.sh` lỗi "Need sudo access... needs to be an Administrator"
    dù tài khoản đó THỰC SỰ là admin** — do set `NONINTERACTIVE=1` cho
    Homebrew installer. Cờ này khiến Homebrew **không cho phép hỏi password
    sudo**, chỉ check xem đã có sudo ticket cache sẵn chưa (`sudo -n`) — nếu
    chưa có thì báo lỗi y như không phải admin, dù thực ra chỉ cần nhập
    password 1 lần. Fix: chạy `sudo -v` (hỏi password, cache ticket) **trước
    khi** set `NONINTERACTIVE=1`, và giữ ticket sống bằng vòng lặp
    `sudo -n true` chạy ngầm suốt quá trình cài.

## Đóng gói thành .app/.dmg (không cần Homebrew trên máy đích)

Ngoài cách cài qua `bootstrap.sh` (cần Homebrew), còn có bản đóng gói sẵn
hoàn toàn standalone, không cần Homebrew/Python gì trên máy đích — chỉ kéo
`.app` vào `Applications`.

**Tải về:** xem GitHub Releases của repo, ví dụ tag `v1.0-dmg` ->
`MacSender.dmg`. **Chỉ chạy trên Apple Silicon (arm64)** — đã xác nhận
editor1, editor3, editor5 đều arm64.

### Cách build lại khi cần (trên máy editor4 - máy dev)

1. Bundle `sshpass` + `rsync` (kèm toàn bộ dylib phụ thuộc) thành bản
   standalone, không phụ thuộc Homebrew nữa:
   ```bash
   brew install dylibbundler   # 1 lần
   mkdir -p vendor/bin vendor/libs
   cp /opt/homebrew/bin/sshpass /opt/homebrew/bin/rsync vendor/bin/
   chmod +w vendor/bin/*
   dylibbundler -od -b -x vendor/bin/rsync -d vendor/libs/ \
       -p "@executable_path/../libs/"
   ```
   (`sshpass` không cần dylibbundler vì chỉ phụ thuộc `libSystem` — luôn có
   sẵn trên mọi macOS.)

2. Build `.app` bằng PyInstaller, nhúng `vendor/` vào:
   ```bash
   python3.12 -m venv build_env && source build_env/bin/activate
   pip install pyinstaller customtkinter
   pyinstaller --noconfirm --windowed --name "MacSender" \
       --add-data "vendor:vendor" mac_sender.py
   ```
   PyInstaller đặt `--add-data` vào `Contents/Frameworks/`, KHÔNG phải
   `Contents/MacOS/` — code `_find_bin()` trong `mac_sender.py` dùng
   `sys._MEIPASS` (PyInstaller tự set đúng giá trị này lúc runtime) để tìm
   `vendor/bin/<name>`, không hardcode theo `dirname(sys.executable)` vì sẽ
   trỏ sai vị trí.

3. Đóng gói `.dmg`:
   ```bash
   mkdir -p dist/dmg_staging
   cp -R dist/MacSender.app dist/dmg_staging/
   ln -s /Applications dist/dmg_staging/Applications
   hdiutil create -volname "Mac Sender" -srcfolder dist/dmg_staging \
       -ov -format UDZO dist/MacSender.dmg
   ```

4. Đăng lên GitHub Releases (KHÔNG commit file `.dmg`/`.app` thẳng vào git —
   file binary lớn (~17MB) sẽ làm phình repo):
   ```bash
   gh release create v1.0-dmg dist/MacSender.dmg --title "..." --notes "..."
   ```

### Lưu ý khi build lại
- App chưa ký Apple Developer ID (chữ ký ad-hoc) → máy đích lần đầu mở phải
  chuột phải → Open để qua Gatekeeper.
- Nếu sau này thêm máy đích là Intel Mac, phải build thêm bản riêng (bundle
  `sshpass`/`rsync` bản Intel từ `/usr/local/bin`, build PyInstaller trên máy
  Intel hoặc cross-build) — file đã build hiện tại CHỈ chạy được trên arm64.

## Lưu ý bảo mật

- `DEFAULT_CONFIG["password"]` trong code hiện là `"1211"` — **đây là password
  SSH thật đang dùng cho các máy editor1-5** (theo xác nhận của user). Repo
  này đang để **Public**, password này nằm cả trong code hiện tại và trong git
  history. User đã được hỏi & **chủ động chấp nhận rủi ro** này (mạng LAN nội
  bộ, không expose ra internet) — không cần tự ý xoá/đổi nếu không được yêu cầu.

## Danh sách máy trong mạng (từ `~/.mac_sender_config.json` lúc khảo sát)

| hostname | username |
|---|---|
| editor1 | editor1 |
| editor2 | quan |
| editor3 | chaosnguyen |
| editor5 | k |
| tuoi | tranthihongtuoi |

(editor4 là máy hiện đang dùng để phát triển/test — không có trong list máy đích)

## Quy ước khi sửa code/test trên máy editor4 (máy dev)

- Python đúng để chạy (có Tk hiện đại): venv tạo bởi `install.sh`, hoặc trực
  tiếp: `/opt/homebrew/Cellar/python@3.12/3.12.13_4/Frameworks/Python.framework/Versions/3.12/bin/python3.12`
- **Luôn `pkill -f mac_sender.py` trước khi chạy lại** sau khi sửa code (xem
  bug #4) — process cũ không tự reload code.
- sshpass/rsync dùng trên máy dev: `/opt/homebrew/bin/sshpass`,
  `/opt/homebrew/bin/rsync` (qua Homebrew, KHÔNG dùng rsync hệ thống
  `/usr/bin/rsync` vì đó là `openrsync` cũ).
