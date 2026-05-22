#!/usr/bin/env python3

import os
import socket
import sys
import time
import shutil
import threading
import json
import ipaddress
import urllib.request
import re
from urllib.parse import urlparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
TOR_HOST = "127.0.0.1"
TOR_PORT = 9050
BUFFER_SIZE = 16384  
MAX_WORKERS = 150    
SPOOFED_UA = "Mozilla/5.0 (Windows NT 10.0; rv:115.0) Gecko/20100101 Firefox/115.0"

ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')

def rgb(r, g, b):
    return f"\033[38;2;{r};{g};{b}m"

def fmt_bytes(b):
    if b < 1024: return f"{b:.0f} B"
    if b < 1024**2: return f"{b/1024:.1f} KB"
    return f"{b/(1024**2):.2f} MB"

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    P_VD = rgb(50, 10, 80)     
    P_D  = rgb(110, 30, 160)   
    P_M  = rgb(180, 50, 255)  
    P_L  = rgb(225, 130, 255) 
    P_VL = rgb(250, 210, 255) 
    
    ACCENT_1 = rgb(255, 0, 150) 
    ACCENT_2 = rgb(0, 255, 255) 
    WARN     = rgb(255, 70, 100) 
    OK       = rgb(50, 255, 150) 

METHOD_THEME = {
    "GET": (Colors.P_VL, "■"),
    "POST": (Colors.P_L, "▲"),
    "PUT": (Colors.P_M, "◆"),
    "DELETE": (Colors.WARN, "▼"),
    "HEAD": (Colors.P_L, "●"),
    "OPTIONS": (Colors.P_M, "◩"),
    "CONNECT": (Colors.ACCENT_1, "⬢"),
    "SYSTEM": (Colors.ACCENT_2, "⚙"),
}

BANNED_HEADERS = frozenset({
    "x-forwarded-for", "via", "proxy-connection", "x-real-ip",
    "forwarded", "x-forwarded-host", "x-forwarded-proto"
})

class Track:
    tx = 0
    rx = 0
    conn_active = 0
    conn_total = 0

class UI:
    TITLE_LINES = [
        "  ██████╗██╗     ███████╗█████╗ ██████╗    ██╗   ██╗██╗███████╗██╗    ██╗",
        " ██╔════╝██║     ██╔════╝██╔══██╗██╔══██╗  ██║   ██║██║██╔════╝██║    ██║",
        " ██║     ██║     █████╗  ███████║██████╔╝  ██║   ██║██║█████╗  ██║ █╗ ██║",
        " ██║     ██║     ██╔══╝  ██╔══██║██╔══██╗  ╚██╗ ██╔╝██║██╔══╝  ██║███╗██║",
        " ╚██████╗███████╗███████╗██║  ██║██║  ██║   ╚████╔╝ ██║███████╗╚███╔███╔╝",
        "  ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝    ╚═══╝  ╚═╝╚══════╝ ╚══╝╚══╝ "
    ]

    @staticmethod
    def clear_screen():
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    @staticmethod
    def hide_cursor():
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    @staticmethod
    def show_cursor():
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    @classmethod
    def show_title(cls):
        cols = shutil.get_terminal_size().columns
        for line in cls.TITLE_LINES:
            pad = max(0, (cols - len(line)) // 2)
            print(" " * pad + Colors.BOLD + Colors.P_M + line + Colors.RESET)
        
        sub = "m a d e   b y   a y v e e a i t o r"
        pad_sub = max(0, (cols - len(sub)) // 2)
        print(" " * pad_sub + Colors.DIM + Colors.P_L + sub + Colors.RESET)
        print()

    @classmethod
    def boot_sequence(cls, listen_host, listen_port, tor_host, tor_port):
        cls.clear_screen()
        print("\n\n\n")
        cls.show_title()
        
        cols = shutil.get_terminal_size().columns
        press_msg = "[ PRESS ENTER TO INITIALIZE ]"
        pad = max(0, (cols - len(press_msg)) // 2)
        print("\n\n" + " " * pad + Colors.BOLD + Colors.P_VL + press_msg + Colors.RESET)
        
        cls.show_cursor()
        input()
        cls.hide_cursor()
        
        cls.clear_screen()
        print("\n\n\n")
        cls.show_title()
        print("\n")
        
        steps = [
            ("Initializing secure networking modules...", 0.2),
            ("Applying RFC1918 local network blocks...", 0.1),
            (f"Binding listener to {listen_host}:{listen_port}...", 0.3),
            (f"Testing SOCKS5 route to {tor_host}:{tor_port}...", 0.4),
            ("Mounting Clear View interface...", 0.3)
        ]
        
        frames = ["✧", "✦", "⟡", "◈", "◇", "◈", "⟡", "✦"]
        pad_step = max(0, (cols - 45) // 2)
        
        for step_text, delay in steps:
            end_time = time.time() + delay
            frame_index = 0
            while time.time() < end_time:
                sys.stdout.write(f"\r{' ' * pad_step} {Colors.P_L}{frames[frame_index % len(frames)]}{Colors.RESET} {Colors.P_M}{step_text}{Colors.RESET}   ")
                sys.stdout.flush()
                time.sleep(0.05)
                frame_index += 1
            sys.stdout.write(f"\r{' ' * pad_step} {Colors.P_VL}✓{Colors.RESET} {Colors.P_L}{step_text}{Colors.RESET}   \n")
            sys.stdout.flush()
            
        time.sleep(0.2)
        cls.clear_screen()

    @classmethod
    def draw_hud(cls, listen_host, listen_port, tor_host, tor_port, proxy_ip):
        cls.clear_screen()
        cols = shutil.get_terminal_size().columns
        print("\n")
        cls.show_title()
        
        box_width = 46
        pad = max(0, (cols - box_width) // 2)
        indent = " " * pad
        
        display_ip = proxy_ip if proxy_ip else "AWAITING UPLINK..."
        
        print(indent + f"{Colors.BOLD}{Colors.P_VL}SYSTEM DASHBOARD{Colors.RESET}")
        print(indent + f"{Colors.P_D}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}")
        print(indent + f"{Colors.P_M}PROXY IP    :{Colors.RESET} {Colors.WARN}{display_ip}{Colors.RESET}")
        print(indent + f"{Colors.P_M}LOCAL PROXY :{Colors.RESET} {Colors.P_L}{listen_host}:{listen_port}{Colors.RESET}")
        print(indent + f"{Colors.P_M}TOR PROXY   :{Colors.RESET} {Colors.P_L}{tor_host}:{tor_port}{Colors.RESET}")
        print(indent + f"{Colors.P_D}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}\n")

class ProxyLogger:
    def __init__(self):
        self.lock = threading.Lock()

    def log(self, method, host, path, current_exit_ip, keyword_filter="", dump_file="", note=""):
        if keyword_filter:
            kw = keyword_filter.lower()
            if kw not in host.lower() and kw not in path.lower():
                return

        with self.lock:
            sys.stdout.write("\r\033[K")
            timestamp = datetime.now().strftime("%H:%M:%S")
            method_color, icon = METHOD_THEME.get(method, (Colors.P_M, "◈"))
            
            time_str = f"{Colors.DIM}{Colors.P_L}{timestamp}{Colors.RESET}"
            method_str = f"{icon} {Colors.BOLD}{method_color}{method:<7}{Colors.RESET}"
            host_str = f"{Colors.P_VL}{host}{Colors.RESET}"
            proxy_ip = current_exit_ip if current_exit_ip else "AWAITING UPLINK"
            telemetry = f"{Colors.P_M}EXIT:{Colors.RESET} {Colors.ACCENT_2}{proxy_ip}{Colors.RESET}"
            
            if method == "CONNECT":
                telemetry += f"  {Colors.P_D}│{Colors.RESET}  {Colors.ACCENT_1}TLS SECURE{Colors.RESET}"
            elif path and path not in ("/", ""):
                display_path = path[:50] + "..." if len(path) > 50 else path
                telemetry += f"  {Colors.P_D}│{Colors.RESET}  {Colors.P_L}PATH: {display_path}{Colors.RESET}"
                
            if note and "err" not in note:
                telemetry += f"  {Colors.P_D}│{Colors.RESET}  {Colors.P_VL}{note}{Colors.RESET}"
            elif note and "err" in note:
                telemetry += f"  {Colors.P_D}│{Colors.RESET}  {Colors.WARN}ERROR: {note}{Colors.RESET}"

            log_top = f" {time_str}  {method_str} ⮞ {host_str}"
            log_bot = f"           {Colors.P_D}└─{Colors.RESET} {telemetry}"
            
            print(log_top)
            print(f"{log_bot}\n")

            if dump_file:
                try:
                    clean_top = ANSI_ESCAPE.sub('', log_top)
                    clean_bot = ANSI_ESCAPE.sub('', log_bot)
                    with open(dump_file, "a", encoding="utf-8") as f:
                        f.write(f"{clean_top}\n{clean_bot}\n\n")
                except Exception:
                    pass

class ClearViewProxy:
    def __init__(self, listen_host, listen_port, tor_host, tor_port):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.tor_host = tor_host
        self.tor_port = tor_port
        self.logger = ProxyLogger()
        
        self.proxy_ip = ""
        self.ip_lock = threading.Lock()
        
        self.keyword_filter = ""
        self.dump_file = ""
        
        self.prompt_mode = None
        self.prompt_title = ""
        self.prompt_text = ""
        
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.show_menu = False
        self.trigger_clear = False
        self.running = True

    def is_safe_target(self, host):
        try:
            ip_obj = ipaddress.ip_address(host)
            if ip_obj.is_private or ip_obj.is_loopback:
                return False
        except ValueError: pass
        return True

    def fetch_proxy_ip(self):
        while self.running:
            self.pause_event.wait()
            try:
                conn = socket.create_connection((self.tor_host, self.tor_port), timeout=10)
                conn.sendall(b"\x05\x01\x00")
                if conn.recv(2) == b"\x05\x00":
                    host_payload = b"ip-api.com"
                    conn.sendall(b"\x05\x01\x00\x03" + bytes([len(host_payload)]) + host_payload + (80).to_bytes(2, "big"))
                    if conn.recv(10)[1] == 0x00:
                        conn.sendall(b"GET /json/ HTTP/1.1\r\nHost: ip-api.com\r\nConnection: close\r\n\r\n")
                        response = b""
                        while chunk := conn.recv(BUFFER_SIZE):
                            response += chunk
                        body = response.split(b"\r\n\r\n", 1)[-1].decode().strip()
                        try:
                            data = json.loads(body)
                            current_ip = data.get("query", "")
                            country_name = data.get("countryCode", "??")
                            if current_ip:
                                new_ip = f"{current_ip} [{country_name}]"
                                with self.ip_lock:
                                    if self.proxy_ip != new_ip:
                                        self.proxy_ip = new_ip
                                        self.trigger_clear = True 
                        except Exception: pass
            except Exception: pass
            finally:
                try: conn.close()
                except Exception: pass
            
            for _ in range(60):
                if not self.running: break
                time.sleep(1)

    def tor_connect(self, target_host, target_port):
        if not self.is_safe_target(target_host):
            raise ConnectionError("RFC1918 Blocked")
            
        conn = socket.create_connection((self.tor_host, self.tor_port), timeout=15)
        conn.sendall(b"\x05\x01\x00")
        if conn.recv(2) != b"\x05\x00":
            conn.close()
            raise ConnectionError("SOCKS5 failed")
            
        encoded_host = target_host.encode()
        conn.sendall(b"\x05\x01\x00\x03" + bytes([len(encoded_host)]) + encoded_host + target_port.to_bytes(2, "big"))
        response_data = conn.recv(10)
        
        if len(response_data) < 2 or response_data[1] != 0x00:
            conn.close()
            raise ConnectionError(f"SOCKS5 code={response_data[1] if len(response_data)>1 else '?'}")
        return conn

    def pipe_data(self, client_socket, target_socket):
        client_socket.settimeout(60)
        target_socket.settimeout(60)
        
        def forward(source, destination, is_tx):
            try:
                while self.running:
                    self.pause_event.wait()
                    data = source.recv(BUFFER_SIZE)
                    if not data: break
                    
                    data_length = len(data)
                    if is_tx: Track.tx += data_length
                    else: Track.rx += data_length
                    destination.sendall(data)
            except Exception: pass
            finally:
                try: source.shutdown(socket.SHUT_RD)
                except Exception: pass
                try: destination.shutdown(socket.SHUT_WR)
                except Exception: pass
                    
        thread_a = threading.Thread(target=forward, args=(client_socket, target_socket, True), daemon=True)
        thread_b = threading.Thread(target=forward, args=(target_socket, client_socket, False), daemon=True)
        thread_a.start()
        thread_b.start()
        thread_a.join()
        thread_b.join()

    def handle_client(self, client_socket):
        self.pause_event.wait()
        Track.conn_active += 1
        Track.conn_total += 1
        try:
            raw_request = client_socket.recv(BUFFER_SIZE)
            if not raw_request or len(raw_request) > BUFFER_SIZE: return
            
            headers = raw_request.decode(errors="replace").split("\r\n")
            if not headers or not headers[0]: return
            
            request_parts = headers[0].split(" ")
            if len(request_parts) < 2: return
            
            method, url = request_parts[0].upper(), request_parts[1]
            if method not in METHOD_THEME:
                client_socket.sendall(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                return

            with self.ip_lock:
                current_exit_ip = self.proxy_ip

            if method == "CONNECT":
                host, _, port_string = url.rpartition(":")
                target_port = int(port_string) if port_string.isdigit() else 443
                
                self.logger.log("CONNECT", f"{host}:{target_port}", "", current_exit_ip, self.keyword_filter, self.dump_file)
                
                try: 
                    target_socket = self.tor_connect(host, target_port)
                    client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    self.pipe_data(client_socket, target_socket)
                except Exception as error_msg:
                    self.logger.log("CONNECT", host, "", current_exit_ip, self.keyword_filter, self.dump_file, f"err {error_msg}")
                    client_socket.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                finally:
                    try: target_socket.close()
                    except Exception: pass
            else:
                parsed_url = urlparse(url if url.startswith("http") else f"http://{url}")
                host = parsed_url.hostname or url
                target_port = parsed_url.port or 80
                path_and_query = f"{parsed_url.path or '/'}{'?' + parsed_url.query if parsed_url.query else ''}"
                
                sanitized_headers = [f"{method} {path_and_query} HTTP/1.1"]
                has_ua = False
                
                for header_line in headers[1:]:
                    if not header_line: continue
                    header_key = header_line.split(":", 1)[0].lower().strip()
                    if header_key in BANNED_HEADERS or header_key == "connection": continue 
                    if header_key == "user-agent":
                        sanitized_headers.append(f"User-Agent: {SPOOFED_UA}")
                        has_ua = True
                        continue
                    sanitized_headers.append(header_line)
                
                if not has_ua: sanitized_headers.append(f"User-Agent: {SPOOFED_UA}")
                sanitized_headers.append("Connection: close\r\n") 
                rebuilt_request = "\r\n".join(sanitized_headers).encode(errors="replace")
                
                self.logger.log(method, host, path_and_query, current_exit_ip, self.keyword_filter, self.dump_file)
                
                try: 
                    target_socket = self.tor_connect(host, target_port)
                    target_socket.sendall(rebuilt_request)
                    self.pipe_data(client_socket, target_socket)
                except Exception as error_msg:
                    self.logger.log(method, host, path_and_query, current_exit_ip, self.keyword_filter, self.dump_file, f"err {error_msg}")
                    client_socket.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                finally:
                    try: target_socket.close()
                    except Exception: pass
        except Exception: pass
        finally:
            Track.conn_active -= 1
            try: client_socket.close()
            except Exception: pass

    def update_inline_prompt(self):
        cols = shutil.get_terminal_size().columns
        prompt_str = f"  {Colors.P_M}► {self.prompt_title}:{Colors.RESET} {Colors.P_VL}{self.prompt_text}{Colors.RESET}"
        pad = max(0, (cols - len(ANSI_ESCAPE.sub('', prompt_str))) // 2)
        sys.stdout.write(f"\r\033[K{' '*pad}{prompt_str}")
        sys.stdout.flush()

    def handle_keypress(self, char):
        if self.prompt_mode:
            if char in ('\r', '\n'):
                if self.prompt_mode == 'keyword':
                    self.keyword_filter = self.prompt_text.strip()
                elif self.prompt_mode == 'dump':
                    self.dump_file = self.prompt_text.strip()
                self.prompt_mode = None
                self.prompt_text = ""
                self.trigger_clear = True
            elif char in ('\x08', '\x7f'): 
                self.prompt_text = self.prompt_text[:-1]
                self.update_inline_prompt()
            elif char == '\x03': 
                self.prompt_mode = None
                self.prompt_text = ""
                self.trigger_clear = True
            elif char.isprintable():
                self.prompt_text += char
                self.update_inline_prompt()
            return

        if char == ' ':  
            if self.pause_event.is_set():
                self.pause_event.clear()
            else:
                self.pause_event.set()
        elif char == 'k':
            self.prompt_mode = 'keyword'
            self.prompt_title = "ENTER KEYWORD (Leave blank to clear)"
            self.prompt_text = ""
            self.update_inline_prompt()
        elif char == 'd':
            self.prompt_mode = 'dump'
            self.prompt_title = "ENTER FILENAME (Leave blank to clear)"
            self.prompt_text = ""
            self.update_inline_prompt()
        elif char == 'l':
            self.show_menu = True
        elif char == 'c':
            self.trigger_clear = True
        elif char == '\x03': 
            self.shutdown()

    def keyboard_listener(self):
        try:
            import msvcrt
            while self.running:
                if msvcrt.kbhit():
                    char = msvcrt.getch().decode('utf-8', 'ignore')
                    self.handle_keypress(char)
                time.sleep(0.05)
        except ImportError:
            import tty, termios
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                while self.running:
                    import select
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        char = sys.stdin.read(1)
                        self.handle_keypress(char)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def shutdown(self):
        self.running = False
        sys.stdout.write("\r\033[K")
        UI.show_cursor()
        print(f"\n  {Colors.P_D}TERMINATING CLEAR VIEW PROTOCOLS.{Colors.RESET}\n")
        os._exit(0)

    def start(self):
        if self.listen_host not in ("127.0.0.1", "::1", "localhost"):
            print(f"\n  {Colors.WARN}[!] CRITICAL: Binding to {self.listen_host} exposes your node.{Colors.RESET}")
            time.sleep(2)

        UI.boot_sequence(self.listen_host, self.listen_port, self.tor_host, self.tor_port)
        UI.draw_hud(self.listen_host, self.listen_port, self.tor_host, self.tor_port, self.proxy_ip)
        
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try: 
            server_socket.bind((self.listen_host, self.listen_port))
        except OSError as bind_error:
            print(f"\n  {Colors.WARN}BIND FAILURE: {self.listen_host}:{self.listen_port} — {bind_error}{Colors.RESET}\n")
            sys.exit(1)
            
        server_socket.listen(256) 
        server_socket.settimeout(0.2) 
        
        threading.Thread(target=self.fetch_proxy_ip, daemon=True).start()
        threading.Thread(target=self.keyboard_listener, daemon=True).start()

        frames = ["✧", "✦", "⟡", "◈", "◇", "◈", "⟡", "✦"]
        frame_index = 0
        cols = shutil.get_terminal_size().columns
        last_tx = 0
        last_rx = 0
        last_time = time.time()

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            while self.running:
                try:
                    client_socket, _ = server_socket.accept()
                    client_socket.settimeout(5.0)
                    executor.submit(self.handle_client, client_socket)
                except socket.timeout:
                    current_time = time.time()
                    dt = current_time - last_time
                    tx_speed = (Track.tx - last_tx) / dt if dt > 0 else 0
                    rx_speed = (Track.rx - last_rx) / dt if dt > 0 else 0
                    last_tx = Track.tx
                    last_rx = Track.rx
                    last_time = current_time

                    if self.trigger_clear:
                        UI.draw_hud(self.listen_host, self.listen_port, self.tor_host, self.tor_port, self.proxy_ip)
                        self.trigger_clear = False

                    if self.show_menu:
                        with self.logger.lock:
                            sys.stdout.write("\r\033[K")
                            print(f"\n  {Colors.P_D}┌─ {Colors.BOLD}{Colors.P_L}SYSTEM OVERLAY{Colors.RESET} {'─'*(cols - 23)}")
                            print(f"  {Colors.P_D}│{Colors.RESET} {Colors.P_M}Total Connections :{Colors.RESET} {Colors.P_VL}{Track.conn_total}{Colors.RESET}")
                            print(f"  {Colors.P_D}│{Colors.RESET} {Colors.P_M}Active Threads    :{Colors.RESET} {Colors.P_VL}{Track.conn_active}{Colors.RESET}")
                            print(f"  {Colors.P_D}│{Colors.RESET} {Colors.P_M}Data Transmitted  :{Colors.RESET} {Colors.P_VL}{fmt_bytes(Track.tx)}{Colors.RESET}")
                            print(f"  {Colors.P_D}│{Colors.RESET} {Colors.P_M}Data Received     :{Colors.RESET} {Colors.P_VL}{fmt_bytes(Track.rx)}{Colors.RESET}")
                            print(f"  {Colors.P_D}└{'─'*(cols - 3)}\n")
                        self.show_menu = False

                    if self.prompt_mode:
                        continue

                    spin_char = frames[frame_index % len(frames)]
                    is_paused = not self.pause_event.is_set()
                    
                    status_text = f"{Colors.WARN}PAUSED{Colors.RESET}" if is_paused else f"{Colors.OK}ACTIVE{Colors.RESET}"
                    kw_text = f"{Colors.P_VL}ON{Colors.RESET}" if self.keyword_filter else f"{Colors.DIM}OFF{Colors.RESET}"
                    dump_text = f"{Colors.P_VL}ON{Colors.RESET}" if self.dump_file else f"{Colors.DIM}OFF{Colors.RESET}"
                    
                    hud = (
                        f"{Colors.P_D}║{Colors.RESET} "
                        f"{Colors.P_L}{spin_char}{Colors.RESET} "
                        f"{Colors.P_D}│{Colors.RESET} {Colors.P_M}TX:{Colors.RESET} {Colors.P_VL}{fmt_bytes(tx_speed):>8}/s{Colors.RESET} "
                        f"{Colors.P_D}│{Colors.RESET} {Colors.P_M}RX:{Colors.RESET} {Colors.P_VL}{fmt_bytes(rx_speed):>8}/s{Colors.RESET} "
                        f"{Colors.P_D}│{Colors.RESET} {Colors.P_M}[SPACE] {status_text}{Colors.RESET} "
                        f"{Colors.P_D}│{Colors.RESET} {Colors.P_M}[K]W:{Colors.RESET} {kw_text} "
                        f"{Colors.P_D}│{Colors.RESET} {Colors.P_M}[D]UMP:{Colors.RESET} {dump_text} "
                        f"{Colors.P_D}║{Colors.RESET}"
                    )
                    
                    raw_len = len(ANSI_ESCAPE.sub('', hud))
                    pad = max(0, (cols - raw_len) // 2)
                    
                    with self.logger.lock:
                        sys.stdout.write(f"\r{' ' * pad}{hud}\033[K")
                        sys.stdout.flush()
                    frame_index += 1
                except KeyboardInterrupt:
                    self.shutdown()

if __name__ == "__main__":
    UI.hide_cursor()
    try:
        proxy = ClearViewProxy(LISTEN_HOST, LISTEN_PORT, TOR_HOST, TOR_PORT)
        proxy.start()
    except Exception as e:
        UI.show_cursor()
        print(f"\n{Colors.WARN}FATAL ERROR: {e}{Colors.RESET}\n")
