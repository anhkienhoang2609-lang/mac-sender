import customtkinter as ctk
import subprocess
import threading
import tkinter.filedialog as fd
import re
import json
import os
import shutil
import sys

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def _find_bin(name):
    # When packaged as a standalone .app (PyInstaller), prefer the
    # sshpass/rsync copies bundled inside the app — fully self-contained,
    # no Homebrew needed on the target Mac.
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        bundled = os.path.join(base, "vendor", "bin", name)
        if os.path.exists(bundled):
            return bundled
    # Otherwise (running mac_sender.py directly), prefer Homebrew's
    # binaries over the very old rsync/ssh that ship with macOS (e.g.
    # system rsync is openrsync, too old for --info=).
    for candidate in (f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}"):
        if os.path.exists(candidate):
            return candidate
    found = shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(
        f"Không tìm thấy '{name}'. Cài bằng: brew install {name}")

SSHPASS_BIN = _find_bin("sshpass")
RSYNC_BIN = _find_bin("rsync")

CONFIG_FILE = os.path.expanduser("~/.mac_sender_config.json")

DEFAULT_CONFIG = {
    "password": "1211",
    "machines": [
        {"hostname": "editor1", "username": ""},
        {"hostname": "editor2", "username": ""},
        {"hostname": "editor3", "username": ""},
        {"hostname": "editor4", "username": ""},
        {"hostname": "editor5", "username": ""},
    ]
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except:
            pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


class MacSender(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Mac Sender")
        self.geometry("780x760")
        self.resizable(False, False)
        self.config = load_config()
        self.process = None
        self.paused = False
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.online_machines = []
        self.selected_machine = None
        self.drill_vars = []
        self.drill_menus = []
        self._machine_rows = []   # list of (frame, h_entry, u_entry)
        self._build_ui()

    # ─────────────────────────────────────────────
    #  UI BUILD
    # ─────────────────────────────────────────────
    def _build_ui(self):
        self.tabview = ctk.CTkTabview(self, width=760, height=750)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        self.tabview.add("📤  Gửi file")
        self.tabview.add("⚙️  Cấu hình máy")
        self._build_send_tab(self.tabview.tab("📤  Gửi file"))
        self._build_config_tab(self.tabview.tab("⚙️  Cấu hình máy"))

    # ── CONFIG TAB ────────────────────────────────
    def _build_config_tab(self, parent):
        self._cfg_parent = parent
        pad = {"padx": 20, "pady": (10, 0)}

        ctk.CTkLabel(parent, text="🔑  Password SSH (dùng chung cho tất cả máy)",
                     anchor="w", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", **pad)
        self.cfg_pw = ctk.CTkEntry(parent, show="*", width=220)
        self.cfg_pw.pack(anchor="w", padx=20, pady=(4, 0))
        self.cfg_pw.insert(0, self.config.get("password", ""))

        # Header row
        hdr_frame = ctk.CTkFrame(parent, fg_color="transparent")
        hdr_frame.pack(fill="x", padx=20, pady=(16, 0))
        ctk.CTkLabel(hdr_frame, text="🖥  Danh sách máy",
                     anchor="w", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        col_hdr = ctk.CTkFrame(parent, fg_color="transparent")
        col_hdr.pack(fill="x", padx=20, pady=(6, 0))
        ctk.CTkLabel(col_hdr, text="", width=28).pack(side="left")  # spacer for delete btn
        ctk.CTkLabel(col_hdr, text="Hostname (.local)", width=170, anchor="w",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(4,0))
        ctk.CTkLabel(col_hdr, text="Username SSH", width=150, anchor="w",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(10,0))

        # Scrollable area for machine rows
        self._machine_scroll = ctk.CTkScrollableFrame(parent, height=220, fg_color="transparent")
        self._machine_scroll.pack(fill="x", padx=20, pady=(4, 0))

        # Load existing machines
        machines = self.config.get("machines", DEFAULT_CONFIG["machines"])
        for m in machines:
            self._add_machine_row(m.get("hostname",""), m.get("username",""))

        # Add machine button
        add_row = ctk.CTkFrame(parent, fg_color="transparent")
        add_row.pack(fill="x", padx=20, pady=(8, 0))
        ctk.CTkButton(add_row, text="＋  Thêm máy", width=130,
                      fg_color="#1a4a7a", hover_color="#0f3358",
                      command=self._add_machine_row).pack(side="left")

        ctk.CTkLabel(parent,
                     text="💡  Đặt Local Hostname trong System Settings → General → Sharing → Local Hostname",
                     anchor="w", text_color="#888",
                     font=ctk.CTkFont(size=11)).pack(fill="x", padx=20, pady=(10, 0))

        self.cfg_save_btn = ctk.CTkButton(parent, text="💾  Lưu cấu hình", width=160,
                                           fg_color="#2a7d4f", hover_color="#1f5e3a",
                                           command=self._save_config)
        self.cfg_save_btn.pack(anchor="w", padx=20, pady=(14, 0))
        self.cfg_status = ctk.CTkLabel(parent, text="", anchor="w", text_color="#4caf50")
        self.cfg_status.pack(anchor="w", padx=20, pady=(6, 0))

    def _add_machine_row(self, hostname="", username=""):
        row = ctk.CTkFrame(self._machine_scroll, fg_color="transparent")
        row.pack(fill="x", pady=3)

        # Delete button
        del_btn = ctk.CTkButton(row, text="✕", width=28, height=28,
                                fg_color="#5e1111", hover_color="#8b1a1a",
                                font=ctk.CTkFont(size=11))
        del_btn.pack(side="left")

        h_entry = ctk.CTkEntry(row, placeholder_text="editorX", width=165)
        h_entry.pack(side="left", padx=(6, 0))
        if hostname:
            h_entry.insert(0, hostname)

        u_entry = ctk.CTkEntry(row, placeholder_text="username", width=150)
        u_entry.pack(side="left", padx=(10, 0))
        if username:
            u_entry.insert(0, username)

        entry = (row, h_entry, u_entry)
        self._machine_rows.append(entry)

        def do_delete():
            self._machine_rows.remove(entry)
            row.destroy()

        del_btn.configure(command=do_delete)

    def _save_config(self):
        self.config["password"] = self.cfg_pw.get().strip()
        machines = []
        for (_, h_entry, u_entry) in self._machine_rows:
            hn = h_entry.get().strip()
            un = u_entry.get().strip()
            if hn:
                machines.append({"hostname": hn, "username": un})
        self.config["machines"] = machines
        save_config(self.config)
        self.cfg_status.configure(text=f"✅ Đã lưu {len(machines)} máy!")
        self.after(2000, lambda: self.cfg_status.configure(text=""))

    # ── SEND TAB ──────────────────────────────────
    def _build_send_tab(self, parent):
        pad = {"padx": 20, "pady": (10, 0)}

        ctk.CTkLabel(parent, text="📁  Folder nguồn", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", **pad)
        src_row = ctk.CTkFrame(parent, fg_color="transparent")
        src_row.pack(fill="x", padx=20, pady=(4, 0))
        self.src_entry = ctk.CTkEntry(src_row, placeholder_text="/Volumes/MY PASSPORT/footage")
        self.src_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(src_row, text="Chọn", width=70,
                      command=self._pick_src).pack(side="left", padx=(8, 0))

        ctk.CTkLabel(parent, text="🖥  Máy đích", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", padx=20, pady=(14, 0))
        scan_row = ctk.CTkFrame(parent, fg_color="transparent")
        scan_row.pack(fill="x", padx=20, pady=(4, 0))
        self.scan_btn = ctk.CTkButton(scan_row, text="🔍 Scan", width=100,
                                      command=self._scan)
        self.scan_btn.pack(side="left")
        self.scan_status = ctk.CTkLabel(scan_row, text="Bấm Scan để tìm máy online",
                                        anchor="w", text_color="#888")
        self.scan_status.pack(side="left", padx=10)

        self.machine_var = ctk.StringVar(value="-- Chưa scan --")
        self.machine_menu = ctk.CTkOptionMenu(parent, variable=self.machine_var,
                                              values=["-- Chưa scan --"],
                                              command=self._on_machine_select,
                                              dynamic_resizing=False)
        self.machine_menu.pack(fill="x", padx=20, pady=(6, 0))

        ctk.CTkLabel(parent, text="📂  Folder đích", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", padx=20, pady=(14, 0))
        self.drill_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.drill_frame.pack(fill="x", padx=20, pady=(4, 0))
        for i, lbl in enumerate(["Ổ / Root", "Cấp 1", "Cấp 2", "Cấp 3"]):
            row = ctk.CTkFrame(self.drill_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=lbl, width=52, anchor="w",
                         font=ctk.CTkFont(size=11)).pack(side="left")
            var = ctk.StringVar(value="--")
            menu = ctk.CTkOptionMenu(row, variable=var, values=["--"],
                                     command=lambda val, i=i: self._on_drill_select(i, val),
                                     dynamic_resizing=False)
            menu.pack(side="left", fill="x", expand=True)
            self.drill_vars.append(var)
            self.drill_menus.append(menu)

        self.dst_display = ctk.CTkLabel(parent, text="Đích: --", anchor="w",
                                        font=ctk.CTkFont(family="Menlo", size=11),
                                        text_color="#aaaaaa")
        self.dst_display.pack(fill="x", padx=20, pady=(4, 0))

        ctk.CTkLabel(parent, text="Tiến độ", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", padx=20, pady=(12, 0))
        self.progress_bar = ctk.CTkProgressBar(parent, height=14)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(4, 0))
        info_row = ctk.CTkFrame(parent, fg_color="transparent")
        info_row.pack(fill="x", padx=20, pady=(3, 0))
        self.pct_label = ctk.CTkLabel(info_row, text="0%", width=50, anchor="w")
        self.pct_label.pack(side="left")
        self.speed_label = ctk.CTkLabel(info_row, text="-- MB/s", anchor="center",
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        text_color="#4caf50")
        self.speed_label.pack(side="left", expand=True)
        self.eta_label = ctk.CTkLabel(info_row, text="ETA: --", anchor="e")
        self.eta_label.pack(side="right")

        self.log_box = ctk.CTkTextbox(parent, height=90,
                                       font=ctk.CTkFont(family="Menlo", size=11))
        self.log_box.pack(fill="x", padx=20, pady=(8, 0))

        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(pady=12)
        self.start_btn = ctk.CTkButton(btn_row, text="▶  Bắt đầu", width=140,
                                        fg_color="#2a7d4f", hover_color="#1f5e3a",
                                        command=self._start)
        self.start_btn.pack(side="left", padx=8)
        self.pause_btn = ctk.CTkButton(btn_row, text="⏸  Tạm dừng", width=140,
                                        state="disabled", command=self._toggle_pause)
        self.pause_btn.pack(side="left", padx=8)
        self.stop_btn = ctk.CTkButton(btn_row, text="⏹  Dừng", width=140,
                                       fg_color="#8b1a1a", hover_color="#5e1111",
                                       state="disabled", command=self._stop)
        self.stop_btn.pack(side="left", padx=8)

    # ─────────────────────────────────────────────
    #  SCAN .local
    # ─────────────────────────────────────────────
    def _scan(self):
        self.scan_btn.configure(state="disabled")
        self.scan_status.configure(text="⏳ Đang scan...", text_color="#ffcc44")
        self.online_machines = []
        self.machine_menu.configure(values=["-- Đang scan... --"])
        self.machine_var.set("-- Đang scan... --")
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        machines = self.config.get("machines", [])
        pw = self.config.get("password", "")
        found = []
        lock = threading.Lock()

        def check(m):
            hn = m.get("hostname", "").strip()
            un = m.get("username", "").strip()
            if not hn or not un:
                return
            fqdn = f"{hn}.local"
            r = subprocess.run(["ping", "-c1", "-W2", fqdn], capture_output=True)
            if r.returncode != 0:
                return
            try:
                import socket
                ip = socket.gethostbyname(fqdn)
            except:
                ip = fqdn
            cmd = [SSHPASS_BIN, "-p", pw, "ssh", "-4",
                   "-o", "StrictHostKeyChecking=no",
                   "-o", "ConnectTimeout=4",
                   f"{un}@{fqdn}", "echo ok"]
            r2 = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
            if "ok" in r2.stdout:
                label = f"{hn}  ({un}@{ip})"
                with lock:
                    found.append({"label": label, "hostname": hn,
                                  "fqdn": fqdn, "username": un, "ip": ip})

        threads = [threading.Thread(target=check, args=(m,), daemon=True)
                   for m in machines]
        for t in threads: t.start()
        for t in threads: t.join()
        self.after(0, self._scan_done, found)

    def _scan_done(self, found):
        self.scan_btn.configure(state="normal")
        total = len(self.config.get("machines", []))
        if not found:
            self.scan_status.configure(text="❌ Không tìm thấy máy nào online", text_color="#ff5555")
            self.machine_menu.configure(values=["-- Không tìm thấy --"])
            self.machine_var.set("-- Không tìm thấy --")
            return
        self.online_machines = found
        labels = [m["label"] for m in found]
        self.machine_menu.configure(values=labels)
        self.machine_var.set(labels[0])
        self.selected_machine = found[0]
        self.scan_status.configure(
            text=f"✅ {len(found)}/{total} máy online",
            text_color="#4caf50")
        self._reset_drill()
        self._fetch_level(0)

    def _on_machine_select(self, label):
        for m in self.online_machines:
            if m["label"] == label:
                self.selected_machine = m
                self._reset_drill()
                self._fetch_level(0)
                break

    # ─────────────────────────────────────────────
    #  DRILL DOWN
    # ─────────────────────────────────────────────
    def _reset_drill(self):
        for var, menu in zip(self.drill_vars, self.drill_menus):
            var.set("--")
            menu.configure(values=["--"])
        self.dst_display.configure(text="Đích: --")

    def _ssh(self, cmd_str):
        m = self.selected_machine
        pw = self.config.get("password", "")
        cmd = [SSHPASS_BIN, "-p", pw,
               "ssh", "-4", "-o", "StrictHostKeyChecking=no",
               "-o", "ConnectTimeout=5",
               f"{m['username']}@{m['fqdn']}", cmd_str]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        return r.stdout.strip()

    def _current_dst(self):
        parts = []
        for var in self.drill_vars:
            v = var.get()
            if v and v not in ("--", "[ dừng ở đây ]", "Đang tải..."):
                parts.append(v)
            else:
                break
        if not parts:
            return ""
        path = parts[0]
        for p in parts[1:]:
            path = path.rstrip("/") + "/" + p
        return path.rstrip("/") + "/"

    def _update_dst_display(self):
        self.dst_display.configure(text=f"Đích: {self._current_dst() or '--'}")

    def _fetch_level(self, level):
        if not self.selected_machine:
            return
        self.drill_vars[level].set("Đang tải...")
        threading.Thread(target=self._do_fetch_level, args=(level,), daemon=True).start()

    def _do_fetch_level(self, level):
        try:
            if level == 0:
                vols_raw = self._ssh("ls /Volumes")
                items = []
                for vol in vols_raw.splitlines():
                    n = vol.strip()
                    if not n:
                        continue
                    chk = self._ssh(
                        f"diskutil info '/Volumes/{n}' 2>/dev/null | grep -i 'removable\\|external'")
                    if chk.strip():
                        items.append(f"/Volumes/{n}")
                if not items:
                    items = [f"/Volumes/{v.strip()}"
                             for v in vols_raw.splitlines() if v.strip()]
            else:
                parts = []
                for i in range(level):
                    v = self.drill_vars[i].get()
                    if v and v not in ("--", "[ dừng ở đây ]", "Đang tải..."):
                        parts.append(v)
                if not parts:
                    return
                base = parts[0]
                for p in parts[1:]:
                    base = base.rstrip("/") + "/" + p
                out = self._ssh(
                    f'ls -d "{base}"/*/  2>/dev/null | xargs -I{{}} basename {{}} 2>/dev/null | head -60')
                items = [l.strip() for l in out.splitlines() if l.strip()]

            self.after(0, self._set_level_items, level, ["[ dừng ở đây ]"] + items)
        except:
            self.after(0, self._set_level_items, level, ["[ dừng ở đây ]"])

    def _set_level_items(self, level, items):
        self.drill_menus[level].configure(values=items)
        default = items[1] if len(items) > 1 else items[0]
        self.drill_vars[level].set(default)
        self._update_dst_display()
        val = self.drill_vars[level].get()
        if val not in ("--", "[ dừng ở đây ]") and level + 1 < len(self.drill_vars):
            self._fetch_level(level + 1)

    def _on_drill_select(self, level, val):
        if val in ("--", "[ dừng ở đây ]", "Đang tải..."):
            self._update_dst_display()
            return
        for i in range(level + 1, len(self.drill_vars)):
            self.drill_vars[i].set("--")
            self.drill_menus[i].configure(values=["--"])
        self._update_dst_display()
        if level + 1 < len(self.drill_vars):
            self._fetch_level(level + 1)

    # ─────────────────────────────────────────────
    #  TRANSFER
    # ─────────────────────────────────────────────
    def _pick_src(self):
        path = fd.askdirectory()
        if path:
            self.src_entry.delete(0, "end")
            self.src_entry.insert(0, path)

    def _log(self, msg):
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")

    def _set_buttons(self, running):
        self.start_btn.configure(state="disabled" if running else "normal")
        self.pause_btn.configure(state="normal" if running else "disabled")
        self.stop_btn.configure(state="normal" if running else "disabled")

    def _start(self):
        src = self.src_entry.get().rstrip("/")
        dst = self._current_dst()
        m = self.selected_machine
        pw = self.config.get("password", "")
        if not src:
            self._log("⚠️  Chọn folder nguồn trước."); return
        if not m:
            self._log("⚠️  Scan và chọn máy đích trước."); return
        if not dst:
            self._log("⚠️  Chọn folder đích trước."); return

        dest_str = f"{m['username']}@{m['fqdn']}:{dst}"
        cmd = [SSHPASS_BIN, "-p", pw,
               RSYNC_BIN, "-ahv", "--info=progress2",
               "--inplace", "--stats",
               "-e", "ssh -4 -o StrictHostKeyChecking=no",
               src, f"{m['username']}@{m['fqdn']}:{dst}"]

        self._log(f"→ {src}")
        self._log(f"→ {dest_str}")
        self.progress_bar.set(0)
        self.pct_label.configure(text="0%")
        self.eta_label.configure(text="ETA: --")
        self.speed_label.configure(text="-- MB/s")
        self.paused = False
        self.pause_event.set()
        self._set_buttons(True)
        threading.Thread(target=self._run, args=(cmd,), daemon=True).start()

    def _run(self, cmd):
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT,
                                         bufsize=0)
        pct_re = re.compile(r"(\d+)%")
        speed_re = re.compile(r"([\d.,]+)\s*(\w?B)/s")
        eta_re = re.compile(r"(\d+:\d+:\d+)")
        speed_units = {"B": 1 / (1024 * 1024), "KB": 1 / 1024, "MB": 1, "GB": 1024}

        def to_mbps(num_str, unit):
            try:
                val = float(num_str.replace(",", "."))
            except ValueError:
                return None
            return val * speed_units.get(unit.upper(), 1)

        def handle_line(line):
            self.pause_event.wait()
            line = line.rstrip()
            if not line:
                return
            m = pct_re.search(line)
            if m:
                pct = int(m.group(1))
                self.after(0, self.progress_bar.set, pct / 100)
                self.after(0, lambda pct=pct: self.pct_label.configure(text=f"{pct}%"))
            ms = speed_re.search(line)
            if ms:
                mbps = to_mbps(ms.group(1), ms.group(2))
                if mbps is not None:
                    if mbps >= 50:
                        color = "#4caf50"   # nhanh
                    elif mbps >= 10:
                        color = "#ffcc44"   # trung bình
                    else:
                        color = "#ff5555"   # chậm / có thể đang lag
                    self.after(0, lambda mbps=mbps, color=color:
                               self.speed_label.configure(text=f"{mbps:.2f} MB/s", text_color=color))
            me = eta_re.search(line)
            if me:
                eta = me.group(1)
                self.after(0, lambda eta=eta: self.eta_label.configure(text=f"ETA: {eta}"))
            if not m:
                self.after(0, self._log, line)

        # rsync's progress2 redraws using \r (no newline), while filenames
        # (-v) are newline-terminated. Splitting only on \n would buffer all
        # the \r updates of one file into a single chunk, so split on both.
        # os.read() (unbuffered) is used instead of file.read(n), which
        # blocks until n bytes accumulate instead of returning what's
        # already available — that delay was hiding all progress updates.
        fd = self.process.stdout.fileno()
        buf = ""
        while True:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            while True:
                idx_n = buf.find("\n")
                idx_r = buf.find("\r")
                candidates = [i for i in (idx_n, idx_r) if i != -1]
                if not candidates:
                    break
                idx = min(candidates)
                handle_line(buf[:idx])
                buf = buf[idx + 1:]
        if buf:
            handle_line(buf)
        self.process.wait()
        rc = self.process.returncode
        if rc == 0:
            self.after(0, self.progress_bar.set, 1)
            self.after(0, lambda: self.pct_label.configure(text="100%"))
            self.after(0, lambda: self.eta_label.configure(text="✅ Hoàn thành!"))
            self.after(0, self._log, "✅  Hoàn thành!")
        elif rc == -15:
            self.after(0, self._log, "🛑  Đã dừng.")
        else:
            self.after(0, self._log, f"❌  Lỗi (exit code {rc})")
        self.after(0, self._set_buttons, False)

    def _toggle_pause(self):
        import signal
        if not self.paused:
            self.paused = True
            self.pause_event.clear()
            if self.process:
                self.process.send_signal(signal.SIGSTOP)
            self.pause_btn.configure(text="▶  Tiếp tục")
            self._log("⏸  Tạm dừng...")
        else:
            self.paused = False
            self.pause_event.set()
            if self.process:
                self.process.send_signal(signal.SIGCONT)
            self.pause_btn.configure(text="⏸  Tạm dừng")
            self._log("▶  Tiếp tục...")

    def _stop(self):
        if self.process:
            self.pause_event.set()
            self.process.terminate()
        self._set_buttons(False)


if __name__ == "__main__":
    MacSender().mainloop()
