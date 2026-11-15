#!/usr/bin/env python3
"""
OLLTATERFX MX — Direct-to-MX email sender, GUI edition.
Zero auth. Threaded. Multi-recipient. Attachments. MX cache.
IPv4 forced (avoids Gmail IPv6 PTR reject). Dark hacking theme.
"""

import os
import sys
import time
import queue
import socket
import threading
import smtplib
import argparse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from email.utils import formatdate, make_msgid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from datetime import datetime

try:
    import dns.resolver
    DNS_OK = True
except ImportError:
    DNS_OK = False


# ─────────────────────────── colors ───────────────────────────
BG       = "#0a0e0a"
PANEL    = "#0f1510"
FG       = "#33ff66"
FG_DIM   = "#1a8c3a"
ACCENT   = "#00ffcc"
WARN     = "#ff3333"
BORDER   = "#1f4d2a"
SEL      = "#0d3315"
BTN_BG   = "#0d1f12"
BTN_ACT  = "#1a4025"

FONT_MONO = ("Consolas", 10)
FONT_MONO_SM = ("Consolas", 9)
FONT_TITLE = ("Consolas", 14, "bold")


# ─────────────────────────── MX logic ───────────────────────────
class MXCache:
    def __init__(self, ttl=3600):
        self._d = {}
        self.ttl = ttl

    def get(self, domain):
        hit = self._d.get(domain)
        if hit and time.time() - hit[1] < self.ttl:
            return hit[0]
        return None

    def put(self, domain, hosts):
        self._d[domain] = (hosts, time.time())


_MX = MXCache()


def lookup_mx(domain):
    cached = _MX.get(domain)
    if cached is not None:
        return cached

    if not DNS_OK:
        return []

    try:
        answers = dns.resolver.resolve(domain, "MX")
        hosts = [str(r.exchange).rstrip(".") for r in
                 sorted(answers, key=lambda r: r.preference)]
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        try:
            dns.resolver.resolve(domain, "A")
            hosts = [domain]
        except Exception:
            hosts = []
    except Exception:
        hosts = []

    _MX.put(domain, hosts)
    return hosts


def resolve_ipv4(host, port=25):
    """Force IPv4 resolution. Returns IP string or None."""
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_INET,
                                   socket.SOCK_STREAM)
        if infos:
            return infos[0][4][0]
    except socket.gaierror:
        pass
    return None


def check_ptr(ip):
    """Reverse DNS for our sending IP. Returns PTR hostname or None."""
    try:
        name, aliases, _ = socket.gethostbyaddr(ip)
        return name
    except (socket.herror, socket.gaierror):
        return None


# ─────────────────────────── message build ───────────────────────────
def build_message(from_name, from_addr, to_addr, subject, body,
                  reply_to=None, attachments=None):
    msg = MIMEMultipart()
    msg["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
    msg["To"] = to_addr
    msg["Subject"] = Header(subject, "utf-8").encode()
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg["X-Mailer"] = "OlltaterFX/1.1"
    if reply_to:
        msg["Reply-To"] = reply_to

    text = MIMEText(body, "plain", "utf-8")
    html = MIMEText(
        f"<html><body><p>{body.replace(chr(10), '<br>')}</p></body></html>",
        "html", "utf-8")
    msg.attach(text)
    msg.attach(html)

    for path in attachments or []:
        try:
            with open(path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition",
                            f'attachment; filename="{os.path.basename(path)}"')
            msg.attach(part)
        except Exception:
            pass

    return msg


# ─────────────────────────── send ───────────────────────────
def send_one(from_name, from_addr, to_addr, subject, body,
             reply_to=None, attachments=None, helo="mail.localhost",
             retries=2, log=None, timeout=30, force_ipv4=True):
    to_domain = to_addr.split("@")[-1].lower()
    mx_hosts = lookup_mx(to_domain)

    if not mx_hosts:
        if log: log(f"[!] {to_addr}: no MX for {to_domain}", "warn")
        return False

    msg = build_message(from_name, from_addr, to_addr, subject, body,
                        reply_to, attachments)
    last_err = None

    for mx in mx_hosts:
        # resolve once per MX, prefer IPv4
        connect_host = mx
        if force_ipv4:
            ip4 = resolve_ipv4(mx, 25)
            if not ip4:
                if log: log(f"[!] {mx}: no IPv4, skipping", "warn")
                continue
            connect_host = ip4

        for attempt in range(retries):
            try:
                if log:
                    log(f"[*] {to_addr} -> {mx} ({connect_host}):25 "
                        f"(try {attempt+1})", "dim")
                server = smtplib.SMTP(connect_host, 25, timeout=timeout,
                                      local_hostname=helo)
                server.ehlo(helo)
                if server.has_extn("starttls"):
                    try:
                        server.starttls()
                        server.ehlo(helo)
                    except smtplib.SMTPException:
                        pass
                server.sendmail(from_addr, [to_addr], msg.as_string())
                server.quit()
                if log: log(f"[+] {to_addr} delivered via {mx}", "ok")
                return True
            except smtplib.SMTPResponseException as e:
                last_err = e
                code = e.smtp_code
                err_txt = e.smtp_error.decode(errors="replace") if isinstance(
                    e.smtp_error, bytes) else str(e.smtp_error)
                # 550 PTR / auth failure — no point retrying this MX
                if code == 550 and ("PTR" in err_txt or "authentication" in err_txt
                                    or "IPv6" in err_txt):
                    if log: log(f"[-] {mx}: 550 policy reject: {err_txt[:120]}",
                                "err")
                    break
                if log: log(f"[-] {mx} try {attempt+1}: {e}", "err")
                time.sleep(min(2 ** attempt, 4))
            except Exception as e:
                last_err = e
                if log: log(f"[-] {mx} try {attempt+1}: {e}", "err")
                time.sleep(min(2 ** attempt, 4))

    if log: log(f"[-] {to_addr} FAILED: {last_err}", "err")
    return False


# ─────────────────────────── GUI ───────────────────────────
class OlltaterFXApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OLLTATERFX MX — direct-to-MX sender")
        self.root.configure(bg=BG)
        self.root.geometry("1100x760")
        self.root.minsize(900, 600)

        self.attachments = []
        self.send_thread = None
        self.stop_flag = threading.Event()
        self.log_q = queue.Queue()
        self.stats = {"sent": 0, "fail": 0, "total": 0}

        self._style()
        self._build()
        self._pump_log()

    # ── style ──
    def _style(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=PANEL, foreground=FG_DIM,
                    padding=(14, 6), font=FONT_MONO)
        s.map("TNotebook.Tab",
              background=[("selected", BTN_ACT)],
              foreground=[("selected", FG)])
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, foreground=FG, font=FONT_MONO)
        s.configure("TEntry", fieldbackground=PANEL, foreground=FG,
                    insertcolor=FG, bordercolor=BORDER)
        s.configure("Horizontal.TProgressbar",
                    troughcolor=PANEL, background=ACCENT,
                    bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT)

    def _entry(self, parent, var, width=None, show=None):
        e = tk.Entry(parent, textvariable=var, bg=PANEL, fg=FG,
                     insertbackground=FG, relief="flat", font=FONT_MONO,
                     highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=ACCENT, show=show)
        if width: e.config(width=width)
        return e

    def _label(self, parent, text, fg=FG, font=FONT_MONO):
        return tk.Label(parent, text=text, bg=BG, fg=fg, font=font,
                        anchor="w")

    def _btn(self, parent, text, cmd, fg=FG):
        return tk.Button(parent, text=text, command=cmd, bg=BTN_BG, fg=fg,
                         activebackground=BTN_ACT, activeforeground=ACCENT,
                         relief="flat", font=FONT_MONO, bd=0, padx=14, pady=6,
                         cursor="hand2", highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=ACCENT)

    # ── layout ──
    def _build(self):
        hdr = tk.Frame(self.root, bg=BG, pady=10)
        hdr.pack(fill="x", padx=16)
        tk.Label(hdr, text="◤ OLLTATERFX MX ◢", bg=BG, fg=ACCENT,
                 font=FONT_TITLE).pack(side="left")
        tk.Label(hdr, text="direct-to-MX · IPv4 · no auth · threaded",
                 bg=BG, fg=FG_DIM, font=FONT_MONO_SM).pack(side="left",
                                                          padx=(12, 0))
        self.status_lbl = tk.Label(hdr, text="● idle", bg=BG, fg=FG_DIM,
                                   font=FONT_MONO)
        self.status_lbl.pack(side="right")

        sep = tk.Frame(self.root, bg=BORDER, height=1)
        sep.pack(fill="x", padx=16, pady=(0, 8))

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self.tab_send = tk.Frame(nb, bg=BG)
        self.tab_opts = tk.Frame(nb, bg=BG)
        self.tab_log  = tk.Frame(nb, bg=BG)
        nb.add(self.tab_send, text=" SEND ")
        nb.add(self.tab_opts, text=" OPTIONS ")
        nb.add(self.tab_log,  text=" LOG ")

        self._build_send_tab()
        self._build_opts_tab()
        self._build_log_tab()
        self._build_footer()

    def _build_send_tab(self):
        f = self.tab_send
        left = tk.Frame(f, bg=BG, padx=8, pady=8)
        left.pack(side="left", fill="both", expand=True)

        self._label(left, "▸ FROM (header — no auth)").grid(
            row=0, column=0, sticky="w", pady=(0, 2))
        self.var_from_name = tk.StringVar(value="Support")
        self.var_from_addr = tk.StringVar(value="support@random.com")
        fr = tk.Frame(left, bg=BG)
        fr.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self._entry(fr, self.var_from_name, width=18).pack(side="left")
        tk.Label(fr, text=" < ", bg=BG, fg=FG_DIM,
                 font=FONT_MONO).pack(side="left")
        self._entry(fr, self.var_from_addr, width=34).pack(side="left",
                                                           padx=(4, 0))

        self._label(left, "▸ REPLY-TO (optional)").grid(
            row=2, column=0, sticky="w", pady=(0, 2))
        self.var_reply_to = tk.StringVar()
        self._entry(left, self.var_reply_to, width=55).grid(
            row=3, column=0, sticky="ew", pady=(0, 8))

        self._label(left, "▸ TO (one per line, or use file)").grid(
            row=4, column=0, sticky="w", pady=(0, 2))
        self.txt_to = scrolledtext.ScrolledText(
            left, height=6, bg=PANEL, fg=FG, insertbackground=FG,
            relief="flat", font=FONT_MONO, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT, wrap="none")
        self.txt_to.grid(row=5, column=0, sticky="ew", pady=(0, 8))
        self.txt_to.insert("1.0", "victim1@gmail.com\nvictim2@yahoo.com\n")

        to_btns = tk.Frame(left, bg=BG)
        to_btns.grid(row=6, column=0, sticky="w", pady=(0, 8))
        self._btn(to_btns, "load file", self._load_recipients).pack(
            side="left", padx=(0, 6))
        self._btn(to_btns, "clear",
                  lambda: self.txt_to.delete("1.0", "end")).pack(side="left")

        self._label(left, "▸ SUBJECT").grid(
            row=7, column=0, sticky="w", pady=(0, 2))
        self.var_subject = tk.StringVar(value="Your account notice")
        self._entry(left, self.var_subject, width=55).grid(
            row=8, column=0, sticky="ew", pady=(0, 8))

        self._label(left, "▸ BODY").grid(
            row=9, column=0, sticky="w", pady=(0, 2))
        self.txt_body = scrolledtext.ScrolledText(
            left, height=10, bg=PANEL, fg=FG, insertbackground=FG,
            relief="flat", font=FONT_MONO, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT, wrap="word")
        self.txt_body.grid(row=10, column=0, sticky="nsew", pady=(0, 8))
        self.txt_body.insert("1.0",
                             "Hello,\n\nThis is a notice.\n\n— Support")
        left.grid_rowconfigure(10, weight=1)
        left.grid_columnconfigure(0, weight=1)

        right = tk.Frame(f, bg=BG, padx=8, pady=8, width=280)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self._label(right, "▸ ATTACHMENTS").pack(anchor="w")
        self.lst_att = tk.Listbox(
            right, height=8, bg=PANEL, fg=FG, selectbackground=SEL,
            selectforeground=ACCENT, relief="flat", font=FONT_MONO_SM,
            highlightthickness=1, highlightbackground=BORDER)
        self.lst_att.pack(fill="x", pady=(2, 6))

        ab = tk.Frame(right, bg=BG)
        ab.pack(fill="x", pady=(0, 12))
        self._btn(ab, "attach", self._attach).pack(side="left", padx=(0, 6))
        self._btn(ab, "remove", self._remove_att).pack(side="left")

        self._label(right, "▸ STATS").pack(anchor="w")
        self.stat_lbl = tk.Label(right, text="sent 0 / 0\nfail 0",
                                 bg=PANEL, fg=ACCENT, font=FONT_MONO,
                                 justify="left", anchor="w",
                                 relief="flat", padx=8, pady=8,
                                 highlightthickness=1,
                                 highlightbackground=BORDER)
        self.stat_lbl.pack(fill="x", pady=(2, 8))

        self.prog = ttk.Progressbar(right, mode="determinate")
        self.prog.pack(fill="x", pady=(0, 12))

        self._btn(right, "▶ SEND", self._start_send, fg=ACCENT).pack(
            fill="x", pady=(0, 6))
        self._btn(right, "■ STOP", self._stop_send, fg=WARN).pack(fill="x")

    def _build_opts_tab(self):
        f = self.tab_opts
        box = tk.Frame(f, bg=BG, padx=16, pady=16)
        box.pack(fill="both", expand=True)

        self.var_helo = tk.StringVar(value="mail.localhost")
        self.var_retries = tk.IntVar(value=2)
        self.var_timeout = tk.IntVar(value=30)
        self.var_delay = tk.DoubleVar(value=0.0)
        self.var_threads = tk.IntVar(value=1)
        self.var_force_ipv4 = tk.BooleanVar(value=True)

        self._label(box, "▸ HELO hostname (your VPS FQDN for best delivery)"
                    ).grid(row=0, column=0, sticky="w", pady=(0, 2))
        self._entry(box, self.var_helo, width=50).grid(
            row=1, column=0, sticky="w", pady=(0, 12))

        rows = [
            ("Retries per MX", self.var_retries),
            ("SMTP timeout (sec)", self.var_timeout),
            ("Delay between sends (sec)", self.var_delay),
            ("Concurrent threads", self.var_threads),
        ]
        r = 2
        for label, var in rows:
            self._label(box, f"▸ {label}").grid(
                row=r, column=0, sticky="w", pady=(0, 2))
            inc = 1 if isinstance(var.get(), int) else 0.1
            tk.Spinbox(box, from_=0, to=999, increment=inc,
                       textvariable=var, bg=PANEL, fg=FG,
                       insertbackground=FG, relief="flat", font=FONT_MONO,
                       highlightthickness=1, highlightbackground=BORDER,
                       buttonbackground=BTN_BG, width=8).grid(
                row=r+1, column=0, sticky="w", pady=(0, 12))
            r += 2

        tk.Checkbutton(
            box, text="▸ Force IPv4 (avoids Gmail IPv6 PTR reject)",
            variable=self.var_force_ipv4, bg=BG, fg=FG,
            activebackground=BG, activeforeground=ACCENT,
            selectcolor=PANEL, font=FONT_MONO, anchor="w"
        ).grid(row=r, column=0, sticky="w", pady=(4, 12))

        self._btn(box, "check my PTR", self._check_ptr).grid(
            row=r+2, column=0, sticky="w")

    def _build_log_tab(self):
        f = self.tab_log
        self.log_txt = scrolledtext.ScrolledText(
            f, bg="#050805", fg=FG, insertbackground=FG, relief="flat",
            font=FONT_MONO_SM, highlightthickness=0, wrap="word")
        self.log_txt.pack(fill="both", expand=True, padx=8, pady=8)
        self.log_txt.tag_config("ok",   foreground=ACCENT)
        self.log_txt.tag_config("err",  foreground=WARN)
        self.log_txt.tag_config("warn", foreground="#ffaa00")
        self.log_txt.tag_config("dim",  foreground=FG_DIM)
        self.log_txt.configure(state="disabled")

        bar = tk.Frame(f, bg=BG)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        self._btn(bar, "clear log", self._clear_log).pack(side="left")
        self._btn(bar, "copy", self._copy_log).pack(side="left", padx=(6, 0))

    def _build_footer(self):
        foot = tk.Frame(self.root, bg=PANEL, height=26)
        foot.pack(fill="x", side="bottom")
        self.foot_lbl = tk.Label(
            foot, text=" olltaterfx · direct-to-MX · IPv4 · zero auth ",
            bg=PANEL, fg=FG_DIM, font=FONT_MONO_SM, anchor="w")
        self.foot_lbl.pack(side="left", padx=8)
        self.clock = tk.Label(foot, text="", bg=PANEL, fg=FG_DIM,
                              font=FONT_MONO_SM)
        self.clock.pack(side="right", padx=8)
        self._tick_clock()

    def _tick_clock(self):
        self.clock.config(text=datetime.now().strftime(" %H:%M:%S "))
        self.root.after(1000, self._tick_clock)

    # ── attachments ──
    def _attach(self):
        for p in filedialog.askopenfilenames(title="attach files"):
            if p not in self.attachments:
                self.attachments.append(p)
                self.lst_att.insert("end", os.path.basename(p))

    def _remove_att(self):
        sel = self.lst_att.curselection()
        if not sel: return
        idx = sel[0]
        self.lst_att.delete(idx)
        del self.attachments[idx]

    def _load_recipients(self):
        p = filedialog.askopenfilename(
            title="recipients file", filetypes=[("text", "*.txt"),
                                                ("all", "*.*")])
        if not p: return
        try:
            with open(p, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            self.txt_to.delete("1.0", "end")
            self.txt_to.insert("1.0", "\n".join(lines))
        except Exception as e:
            messagebox.showerror("read failed", str(e))

    # ── PTR check ──
    def _check_ptr(self):
        def run():
            self._log("[*] checking outbound IP + PTR", "dim")
            # find our public IPv4: use a route probe (no packet sent)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 53))
                ip = s.getsockname()[0]
                s.close()
            except Exception as e:
                self._log(f"[-] could not determine local IP: {e}", "err")
                return
            self._log(f"[*] local IPv4: {ip}", "dim")
            ptr = check_ptr(ip)
            if ptr:
                self._log(f"[+] PTR: {ptr}", "ok")
                try:
                    fwd = resolve_ipv4(ptr, 80)
                    if fwd == ip:
                        self._log(f"[+] forward DNS matches: {fwd}", "ok")
                    else:
                        self._log(f"[!] forward DNS mismatch: {ptr} -> {fwd}",
                                  "warn")
                except Exception:
                    pass
            else:
                self._log(f"[-] no PTR for {ip} — Gmail will 550 on IPv6, "
                          f"and often on IPv4 without PTR too", "err")
                self._log("[!] use a VPS with rDNS, or switch to an "
                          "authenticated relay (SES/Brevo)", "warn")
        threading.Thread(target=run, daemon=True).start()

    # ── log ──
    def _log(self, msg, tag=None):
        self.log_q.put((msg, tag))

    def _pump_log(self):
        while True:
            try:
                msg, tag = self.log_q.get_nowait()
            except queue.Empty:
                break
            self.log_txt.configure(state="normal")
            ts = datetime.now().strftime("[%H:%M:%S] ")
            self.log_txt.insert("end", ts, "dim")
            self.log_txt.insert("end", msg + "\n", tag or "dim")
            self.log_txt.see("end")
            self.log_txt.configure(state="disabled")
        self.root.after(80, self._pump_log)

    def _clear_log(self):
        self.log_txt.configure(state="normal")
        self.log_txt.delete("1.0", "end")
        self.log_txt.configure(state="disabled")

    def _copy_log(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log_txt.get("1.0", "end"))

    # ── send ──
    def _collect_recipients(self):
        return [l.strip() for l in self.txt_to.get("1.0", "end").splitlines()
                if l.strip() and "@" in l]

    def _start_send(self):
        if self.send_thread and self.send_thread.is_alive():
            self._log("[!] already sending", "warn")
            return

        from_addr = self.var_from_addr.get().strip()
        if "@" not in from_addr:
            messagebox.showerror("invalid", "From address required")
            return

        recips = self._collect_recipients()
        if not recips:
            messagebox.showerror("invalid", "no recipients")
            return

        subject = self.var_subject.get().strip()
        body = self.txt_body.get("1.0", "end").rstrip()
        from_name = self.var_from_name.get().strip()
        reply_to = self.var_reply_to.get().strip() or None
        helo = self.var_helo.get().strip() or "mail.localhost"
        retries = max(1, int(self.var_retries.get()))
        timeout = max(5, int(self.var_timeout.get()))
        delay = max(0.0, float(self.var_delay.get()))
        threads = max(1, int(self.var_threads.get()))
        attachments = list(self.attachments)
        force_ipv4 = bool(self.var_force_ipv4.get())

        self.stats = {"sent": 0, "fail": 0, "total": len(recips)}
        self._update_stats()
        self.prog["value"] = 0
        self.prog["maximum"] = len(recips)
        self.status_lbl.config(text="● sending", fg=ACCENT)
        self.stop_flag.clear()

        self._log(
            f"=== start: {len(recips)} recipients, {threads} thread(s), "
            f"IPv4={force_ipv4} ===", "ok")

        self.send_thread = threading.Thread(
            target=self._worker,
            args=(from_name, from_addr, recips, subject, body, reply_to,
                  attachments, helo, retries, timeout, delay, threads,
                  force_ipv4),
            daemon=True)
        self.send_thread.start()

    def _stop_send(self):
        if self.send_thread and self.send_thread.is_alive():
            self.stop_flag.set()
            self._log("[!] stop requested", "warn")
            self.status_lbl.config(text="● stopping", fg="#ffaa00")

    def _worker(self, from_name, from_addr, recips, subject, body, reply_to,
                attachments, helo, retries, timeout, delay, threads,
                force_ipv4):
        idx_lock = threading.Lock()
        idx = 0
        done = 0

        def worker():
            nonlocal idx, done
            while not self.stop_flag.is_set():
                with idx_lock:
                    if idx >= len(recips):
                        return
                    to_addr = recips[idx]
                    idx += 1
                ok = send_one(from_name, from_addr, to_addr, subject, body,
                              reply_to, attachments, helo, retries,
                              self._log, timeout, force_ipv4)
                with idx_lock:
                    done += 1
                    if ok: self.stats["sent"] += 1
                    else:  self.stats["fail"] += 1
                    d = done
                self.root.after(0, self._update_stats)
                self.root.after(0, lambda v=d: self.prog.configure(value=v))
                if delay > 0:
                    time.sleep(delay)

        ts = [threading.Thread(target=worker, daemon=True)
              for _ in range(threads)]
        for t in ts: t.start()
        for t in ts: t.join()

        self.root.after(0, self._finish)

    def _finish(self):
        self.status_lbl.config(text="● done", fg=ACCENT)
        self._log(
            f"=== done: {self.stats['sent']} sent, "
            f"{self.stats['fail']} failed ===", "ok")

    def _update_stats(self):
        s = self.stats
        self.stat_lbl.config(
            text=f"sent {s['sent']} / {s['total']}\nfail {s['fail']}")


# ─────────────────────────── main ───────────────────────────
def cli_mode(args):
    recips = [l.strip() for l in args.to.split(",") if "@" in l]
    for r in recips:
        send_one(args.from_name, args.from_addr, r, args.subject, args.body,
                 args.reply_to, [], args.helo, args.retries,
                 log=lambda m, t=None: print(m), timeout=args.timeout,
                 force_ipv4=not args.no_ipv4)


def main():
    if "--cli" in sys.argv:
        p = argparse.ArgumentParser()
        p.add_argument("--cli", action="store_true")
        p.add_argument("--from-name", default="Support")
        p.add_argument("--from", dest="from_addr", required=True)
        p.add_argument("--to", required=True)
        p.add_argument("--subject", required=True)
        p.add_argument("--body", required=True)
        p.add_argument("--reply-to", default=None)
        p.add_argument("--helo", default="mail.localhost")
        p.add_argument("--retries", type=int, default=2)
        p.add_argument("--timeout", type=int, default=30)
        p.add_argument("--no-ipv4", action="store_true")
        args = p.parse_args()
        cli_mode(args)
        return

    root = tk.Tk()
    OlltaterFXApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
