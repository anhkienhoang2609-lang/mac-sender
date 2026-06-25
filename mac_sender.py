import customtkinter as ctk
import subprocess
import threading
import tkinter.filedialog as fd
import re
import socket

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class MacSender(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Mac Sender")
        self.geometry("760x720")
        self.resizable(False, False)
        self.process = None
        self.paused = False
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.found_hosts = {}
        self.selected_ip = None
        self.drill_vars = []
        self.drill_menus = []
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 20, "pady": (10, 0)}
        ctk.CTkLabel(self, text="📁  Folder nguồn", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", **pad)
        src_row = ctk.CTkFrame(self, fg_color="transparent")
        src_row.pack(fill="x", padx=20, pady=(4, 0))
        self.src_entry = ctk.CTkEntry(src_row, placeholder_text="/Volumes/MY PASSPORT/footage")
        self.src_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(src_row, text="Chọn", width=70,
                      command=self._pick_src).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(self, text="🔑  Password SSH", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", padx=20, pady=(12, 0))
        pw_row = ctk.CTkFrame(self, fg_color="transparent")
        pw_row.pack(fill="x", padx=20, pady=(4, 0))
        self.pw_entry = ctk.CTkEntry(pw_row, placeholder_text="password", show="*", width=180)
        self.pw_entry.pack(side="left")
        self.pw_entry.insert(0, "1211")
        ctk.CTkLabel(pw_row, text="  Username:").pack(side="left", padx=(14, 4))
        self.user_entry = ctk.CTkEntry(pw_row, placeholder_text="editor4", width=130)
        self.user_entry.pack(side="left")
        self.user_entry.insert(0, "editor4")
        ctk.CTkLabel(self, text="🖥  Máy đích", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", padx=20, pady=(12, 0))
        scan_row = ctk.CTkFrame(self, fg_color="transparent")
        scan_row.pack(fill="x", padx=20, pady=(4, 0))
        self.scan_btn = ctk.CTkButton(scan_row, text="🔍 Scan LAN", width=110, command=self._scan_lan)
        self.scan_btn.pack(side="left")
        self.scan_status = ctk.CTkLabel(scan_row, text="", anchor="w")
        self.scan_status.pack(side="left", padx=10)
        self.host_var = ctk.StringVar(value="-- Chưa scan --")
        self.host_menu = ctk.CTkOptionMenu(self, variable=self.host_var,
                                           values=["-- Chưa scan --"],
                                           command=self._on_host_select,
                                           dynamic_resizing=False)
        self.host_menu.pack(fill="x", padx=20, pady=(6, 0))
        ctk.CTkLabel(self, text="📂  Folder đích", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", padx=20, pady=(12, 0))
        self.drill_frame = ctk.CTkFrame(self, fg_color="transparent")
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
        self.dst_display = ctk.CTkLabel(self, text="Đích: --", anchor="w",
                                        font=ctk.CTkFont(family="Menlo", size=11),
                                        text_color="#aaaaaa")
        self.dst_display.pack(fill="x", padx=20, pady=(4, 0))
        ctk.CTkLabel(self, text="Tiến độ", anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", padx=20, pady=(12, 0))
        self.progress_bar = ctk.CTkProgressBar(self, height=14)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(4, 0))
        info_row = ctk.CTkFrame(self, fg_color="transparent")
        info_row.pack(fill="x", padx=20, pady=(3, 0))
        self.pct_label = ctk.CTkLabel(info_row, text="0%", width=50, anchor="w")
        self.pct_label.pack(side="left")
        self.speed_label = ctk.CTkLabel(info_row, text="", anchor="center")
        self.speed_label.pack(side="left", expand=True)
        self.eta_label = ctk.CTkLabel(info_row, text="ETA: --", anchor="e")
        self.eta_label.pack(side="right")
        self.log_box = ctk.CTkTextbox(self, height=90, font=ctk.CTkFont(family="Menlo", size=11))
        self.log_box.pack(fill="x", padx=20, pady=(8, 0))
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=12)
        self.start_btn = ctk.CTkButton(btn_row, text="▶  Bắt đầu", width=140,
                                        fg_color="#2a7d4f", hover_color="#1f5e3a", command=self._start)
        self.start_btn.pack(side="left", padx=8)
        self.pause_btn = ctk.CTkButton(btn_row, text="⏸  Tạm dừng", width=140,
                                        state="disabled", command=self._toggle_pause)
        self.pause_btn.pack(side="left", padx=8)
        self.stop_btn = ctk.CTkButton(btn_row, text="⏹  Dừng", width=140,
                                       fg_color="#8b1a1a", hover_color="#5e1111", state="disabled",
                                       command=self._stop)
        self.stop_btn.pack(side="left", padx=8)

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

    def _ssh(self, cmd_str):
        user = self.user_entry.get().strip()
        pw = self.pw_entry.get().strip()
        cmd = ["sshpass", "-p", pw, "ssh", "-o", "StrictHostKeyChecking=no",
               "-o", "ConnectTimeout=5", f"{user}@{self.selected_ip}", cmd_str]
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
        self.dst_display.configure(text=f"Đích: {self._current_dst()}")

    def _scan_lan(self):
        self.scan_btn.configure(state="disabled")
        self.scan_status.configure(text="Đang scan...")
        self.found_hosts = {}
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "192.168.1.1"
        subnet = ".".join(local_ip.split(".")[:3])
        found_ips = []
        lock = threading.Lock()
        def ping(i):
            ip = f"{subnet}.{i}"
            if ip == local_ip: return
            r = subprocess.run(["ping", "-c1", "-W1", ip], capture_output=True)
            if r.returncode == 0:
                with lock: found_ips.append(ip)
        threads = [threading.Thread(target=ping, args=(i,), daemon=True) for i in range(1, 255)]
        for t in threads: t.start()
        for t in threads: t.join()
        found = {}
        def resolve(ip):
            pw = self.pw_entry.get().strip()
            user = self.user_entry.get().strip()
            cmd = ["sshpass", "-p", pw, "ssh", "-o", "StrictHostKeyChecking=no",
                   "-o", "ConnectTimeout=3", f"{user}@{ip}",
                   "scutil --get ComputerName 2>/dev/null || hostname"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            name = r.stdout.strip().split("\n")[0] or ip
            with lock: found[f"{name}  ({ip})"] = ip
        rthreads = [threading.Thread(target=resolve, args=(ip,), daemon=True) for ip in found_ips]
        for t in rthreads: t.start()
        for t in rthreads: t.join()
        self.after(0, self._scan_done, found)

    def _scan_done(self, found):
        self.found_hosts = found
        self.scan_btn.configure(state="normal")
        if found:
            labels = list(found.keys())
            self.host_menu.configure(values=labels)
            self.host_var.set(labels[0])
            self.selected_ip = found[labels[0]]
            self.scan_status.configure(text=f"✅ Tìm thấy {len(found)} máy")
            self._fetch_level(0, None)
        else:
            self.scan_status.configure(text="❌ Không tìm thấy máy nào")

    def _on_host_select(self, label):
        self.selected_ip = self.found_hosts.get(label)
        if self.selected_ip:
            for var, menu in zip(self.drill_vars, self.drill_menus):
                var.set("--"); menu.configure(values=["--"])
            self._fetch_level(0, None)

    def _on_drill_select(self, level, val):
        if val in ("--", "[ dừng ở đây ]", "Đang tải..."): 
            self._update_dst_display(); return
        for i in range(level + 1, len(self.drill_vars)):
            self.drill_vars[i].set("--"); self.drill_menus[i].configure(values=["--"])
        self._update_dst_display()
        if level + 1 < len(self.drill_vars):
            self._fetch_level(level + 1, val)

    def _fetch_level(self, level, val):
        if not self.selected_ip: return
        self.drill_vars[level].set("Đang tải...")
        threading.Thread(target=self._do_fetch_level, args=(level,), daemon=True).start()

    def _do_fetch_level(self, level):
        try:
            if level == 0:
                out = self._ssh("ls /Volumes && echo ---HOME--- && ls /Users")
                items, in_home = [], False
                for line in out.splitlines():
                    if line == "---HOME---": in_home = True; continue
                    n = line.strip()
                    if n: items.append(f"/Users/{n}" if in_home else f"/Volumes/{n}")
            else:
                parts = []
                for i in range(level):
                    v = self.drill_vars[i].get()
                    if v and v not in ("--", "[ dừng ở đây ]", "Đang tải..."): parts.append(v)
                if not parts: return
                base = parts[0]
                for p in parts[1:]: base = base.rstrip("/") + "/" + p
                out = self._ssh(f"ls -d \"{base}\"/*/ 2>/dev/null | xargs -I{{}} basename {{}} 2>/dev/null | head -40")
                items = [l.strip() for l in out.splitlines() if l.strip()]
            self.after(0, self._set_level_items, level, ["[ dừng ở đây ]"] + items)
        except:
            self.after(0, self._set_level_items, level, ["[ dừng ở đây ]"])

    def _set_level_items(self, level, items):
        self.drill_menus[level].configure(values=items)
        self.drill_vars[level].set(items[1] if len(items) > 1 else items[0])
        self._update_dst_display()
        val = self.drill_vars[level].get()
        if val not in ("--", "[ dừng ở đây ]") and level + 1 < len(self.drill_vars):
            self._fetch_level(level + 1, val)

    def _start(self):
        src = self.src_entry.get().strip().rstrip("/") + "/"
        user = self.user_entry.get().strip()
        pw = self.pw_entry.get().strip()
        dst = self._current_dst()
        if not src or not user or not pw or not self.selected_ip or not dst:
            self._log("⚠️  Điền đủ thông tin trước."); return
        dest = f"{user}@{self.selected_ip}:{dst}"
        import shlex
        ip = self.selected_ip
        cmd = ["sshpass", "-p", pw,
               "/opt/homebrew/bin/rsync", "-ah", "--info=progress2", "--inplace", "--stats",
               "-e", "ssh -o StrictHostKeyChecking=no",
               src, f"{user}@{ip}:{dst}"]
        self._log(f"CMD: {cmd}")
        self._log(f"→ {src}  →  {dest}")
        self.progress_bar.set(0)
        self.pct_label.configure(text="0%")
        self.eta_label.configure(text="ETA: --")
        self.speed_label.configure(text="")
        self.paused = False
        self.pause_event.set()
        self._set_buttons(True)
        threading.Thread(target=self._run, args=(cmd,), daemon=True).start()

    def _run(self, cmd):
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, bufsize=1)
        pct_re = re.compile(r"(\d+)%")
        speed_re = re.compile(r"(\d+[\.,]\d+\w+/s)")
        eta_re = re.compile(r"(\d+:\d+:\d+)\s*$")
        for line in self.process.stdout:
            self.pause_event.wait()
            line = line.rstrip()
            if not line: continue
            m = pct_re.search(line)
            if m:
                pct = int(m.group(1))
                self.progress_bar.set(pct / 100)
                self.pct_label.configure(text=f"{pct}%")
            ms = speed_re.search(line)
            if ms: self.speed_label.configure(text=ms.group(1))
            me = eta_re.search(line)
            if me: self.eta_label.configure(text=f"ETA: {me.group(1)}")
            if not m: self._log(line)
        self.process.wait()
        rc = self.process.returncode
        if rc == 0:
            self.progress_bar.set(1)
            self.pct_label.configure(text="100%")
            self.eta_label.configure(text="ETA: 00:00:00")
            self._log("✅  Hoàn thành!")
        elif rc == -15: self._log("🛑  Đã dừng.")
        else: self._log(f"❌  Lỗi (exit code {rc})")
        self._set_buttons(False)

    def _toggle_pause(self):
        import signal
        if not self.paused:
            self.paused = True
            if self.process:
                self.process.send_signal(signal.SIGSTOP)
            self.pause_btn.configure(text="▶  Tiếp tục")
            self._log("⏸  Tạm dừng...")
        else:
            self.paused = False
            if self.process:
                self.process.send_signal(signal.SIGCONT)
            self.pause_btn.configure(text="⏸  Tạm dừng")
            self._log("▶  Tiếp tục...")

    def _stop(self):
        if self.process: self.pause_event.set(); self.process.terminate()
        self._set_buttons(False)

if __name__ == "__main__":
    MacSender().mainloop()
