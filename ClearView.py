#!/usr/bin/env python3

import os
import socket
import sys
import time
import shutil
import threading
import json
import ipaddress
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
    if b < 1048576: return f"{b/1024:.1f} KB"
    return f"{b/1048576:.2f} MB"

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    P_VD = rgb(50, 10, 80)     
    P_D  = rgb(110, 30, 160)   
    P_M  = rgb(180, 50, 255)  
    P_L  = rgb(225, 130, 255) 
    P_VL = rgb(250, 210, 255) 
    
    ACCENT_1 = rgb(255, 0, 150)   # Pink for Header Keys
    ACCENT_2 = rgb(0, 255, 255)   # Cyan for Header Values
    ACCENT_3 = rgb(255, 150, 0)   # Orange
    WARN     = rgb(255, 70, 100) 
    OK       = rgb(50, 255, 150) 

METHOD_THEME = {
    "GET": (Colors.P_VL, "■"),
    "POST": (Colors.P_L, "▲"),
    "PUT": (Colors.ACCENT_3, "◆"),
    "DELETE": (Colors.WARN, "▼"),
    "HEAD": (Colors.P_L, "●"),
    "OPTIONS": (Colors.P_M, "◩"),
    "CONNECT": (Colors.ACCENT_1, "⬢"),
    "SYSTEM": (Colors.ACCENT_2, "⚙"),
}

SOCKS_ERRORS = {
    1: "General SOCKS server failure",
    2: "Connection not allowed by ruleset",
    3: "Network Unreachable",
    4: "Host Unreachable (DNS Failure / Domain doesn't exist)",
    5: "Connection Refused (Target server offline)",
    6: "TTL Expired",
    7: "Command Not Supported",
    8: "Address Type Not Supported"
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
            sys.stdout.write("\r\033[K" + " " * pad + Colors.BOLD + Colors.P_M + line + Colors.RESET + "\n")
        
        sub = "m a d e   b y   a y v e e a i t o r"
        pad_sub = max(0, (cols - len(sub)) // 2)
        sys.stdout.write("\r\033[K" + " " * pad_sub + Colors.DIM + Colors.P_L + sub + Colors.RESET + "\n\n")
        sys.stdout.flush()

    @classmethod
    def boot_sequence(cls, listen_host, listen_port, tor_host, tor_port):
        cls.clear_screen()
        sys.stdout.write("\n\n\n")
        cls.show_title()
        
        cols = shutil.get_terminal_size().columns
        press_msg = "[ PRESS ENTER TO INITIALIZE ]"
        pad = max(0, (cols - len(press_msg)) // 2)
        sys.stdout.write("\n\n" + " " * pad + Colors.BOLD + Colors.P_VL + press_msg + Colors.RESET + "\n")
        sys.stdout.flush()
        
        cls.show_cursor()
        try:
            input()
        except EOFError:
            time.sleep(1.5)  
        cls.hide_cursor()
        
        cls.clear_screen()
        sys.stdout.write("\n\n\n")
        cls.show_title()
        sys.stdout.write("\n")
        
        steps = [
            ("Initializing secure networking modules...", 0.2),
            ("Applying RFC1918 & WPAD filters...", 0.1),
            (f"Binding listener to {listen_host}:{listen_port}...", 0.3),
            (f"Testing SOCKS5 route to {tor_host}:{tor_port}...", 0.4),
            ("Mounting Clear View interface...", 0.3)
        ]
        
        frames = ["✯", "✰", "✱", "✲", "✳", "✴", "✵", "✶", "✷", "✸", "✹", "✺", "✹", "✸", "✷", "✶", "✵", "✴"]
        
        for step_text, delay in steps:
            end_time = time.time() + delay
            frame_index = 0
            while time.time() < end_time:
                cols = shutil.get_terminal_size().columns
                pad_step = max(0, (cols - len(step_text) - 4) // 2)
                sys.stdout.write(f"\r\033[K{' ' * pad_step} {Colors.P_L}{frames[frame_index % len(frames)]}{Colors.RESET} {Colors.P_M}{step_text}{Colors.RESET}   ")
                sys.stdout.flush()
                time.sleep(0.05)
                frame_index += 1
            sys.stdout.write(f"\r\033[K{' ' * pad_step} {Colors.P_VL}✓{Colors.RESET} {Colors.P_L}{step_text}{Colors.RESET}   \n")
            sys.stdout.flush()
            
        time.sleep(0.2)
        cls.clear_screen()

    @classmethod
    def draw_hud(cls, listen_host, listen_port, tor_host, tor_port):
        cls.clear_screen()
        cols = shutil.get_terminal_size().columns
        sys.stdout.write("\n")
        cls.show_title()
        
        box_width = 46
        pad = max(0, (cols - box_width) // 2)
        indent = " " * pad
        
        sys.stdout.write(indent + f"{Colors.BOLD}{Colors.P_VL}SYSTEM DASHBOARD{Colors.RESET}\n")
        sys.stdout.write(indent + f"{Colors.P_D}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}\n")
        sys.stdout.write(indent + f"{Colors.P_M}LOCAL PROXY :{Colors.RESET} {Colors.P_L}{listen_host}:{listen_port}{Colors.RESET}\n")
        sys.stdout.write(indent + f"{Colors.P_M}TOR PROXY   :{Colors.RESET} {Colors.P_L}{tor_host}:{tor_port}{Colors.RESET}\n")
        sys.stdout.write(indent + f"{Colors.P_D}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}\n\n")
        sys.stdout.flush()

class ProxyLogger:
    def __init__(self):
        self.lock = threading.Lock()

    def log(self, method, host, path, target_info, inspect_mode=False, raw_headers="", dump_file="", note=""):
        with self.lock:
            sys.stdout.write("\r\033[K")
            timestamp = datetime.now().strftime("%H:%M:%S")
            method_color, icon = METHOD_THEME.get(method, (Colors.P_M, "◈"))
            
            time_str = f"{Colors.DIM}{Colors.P_L}{timestamp}{Colors.RESET}"
            method_str = f"{icon} {Colors.BOLD}{method_color}{method:<7}{Colors.RESET}"
            host_str = f"{Colors.ACCENT_2}{host}{Colors.RESET}"
            telemetry = f"{Colors.P_M}TARGET:{Colors.RESET} {Colors.P_VL}{target_info}{Colors.RESET}"
            
            if method == "CONNECT":
                telemetry += f"  {Colors.DIM}•{Colors.RESET}  {Colors.ACCENT_1}TLS SECURE{Colors.RESET}"
            elif path and path not in ("/", ""):
                display_path = path[:50] + "..." if len(path) > 50 else path
                telemetry += f"  {Colors.DIM}•{Colors.RESET}  {Colors.P_L}PATH: {display_path}{Colors.RESET}"
                
            if note and "err" not in note:
                telemetry += f"  {Colors.DIM}•{Colors.RESET}  {Colors.P_VL}{note}{Colors.RESET}"
            elif note and "err" in note:
                telemetry += f"  {Colors.DIM}•{Colors.RESET}  {Colors.WARN}ERROR: {note.replace('err ', '')}{Colors.RESET}"

            log_top = f" {time_str}  {method_str} ⮞ {host_str}"
            log_bot = f"           {Colors.P_D}└─{Colors.RESET} {telemetry}"
            
            sys.stdout.write(f"{log_top}\n{log_bot}\n")
            
            if inspect_mode and raw_headers:
                sys.stdout.write(f"           {Colors.P_D}╭─── RAW REQUEST ────────────────────{Colors.RESET}\n")
                for line in raw_headers.split("\r\n"):
                    if line.strip():
                        if ":" in line:
                            key, val = line.split(":", 1)
                            sys.stdout.write(f"           {Colors.P_D}│{Colors.RESET} {Colors.BOLD}{Colors.ACCENT_1}{key}:{Colors.RESET}{Colors.ACCENT_2}{val}{Colors.RESET}\n")
                        else:
                            sys.stdout.write(f"           {Colors.P_D}│{Colors.RESET} {Colors.P_VL}{line.strip()}{Colors.RESET}\n")
                sys.stdout.write(f"           {Colors.P_D}╰────────────────────────────────────{Colors.RESET}\n")

            sys.stdout.write("\n")
            sys.stdout.flush()

            if dump_file:
                try:
                    clean_top = ANSI_ESCAPE.sub('', log_top)
                    clean_bot = ANSI_ESCAPE.sub('', log_bot)
                    with open(dump_file, "a", encoding="utf-8") as f:
                        f.write(f"{clean_top}\n{clean_bot}\n")
                        if raw_headers:
                            f.write("           [HTTP HEADERS]\n")
                            for line in raw_headers.split("\r\n"):
                                if line.strip():
                                    f.write(f"             {line.strip()}\n")
                        f.write("\n")
                except Exception:
                    pass

class ClearViewProxy:
    def __init__(self, listen_host, listen_port, tor_host, tor_port):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.tor_host = tor_host
        self.tor_port = tor_port
        self.logger = ProxyLogger()
        
        self.target_cache = {}
        self.pending_targets = set()
        
        self.inspect_mode = False
        self.dump_file = ""
        
        self.prompt_mode = None
        self.prompt_title = ""
        self.prompt_text = ""
        
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.show_menu = False
        self.trigger_ui = False
        self.running = True

    def is_noise(self, host, path=""):
        host_lower = host.lower()
        if "wpad" in host_lower or host_lower.endswith(".local"):
            return True
        if "wpad.dat" in path.lower():
            return True
        if "." not in host and ":" not in host and host_lower != "localhost":
            return True
        return False

    def is_safe_target(self, host):
        try:
            ip_obj = ipaddress.ip_address(host)
            if ip_obj.is_private or ip_obj.is_loopback:
                return False
        except ValueError: pass
        return True

    def fetch_target_info(self, host):
        if host in self.target_cache or host in self.pending_targets:
            return
        
        self.pending_targets.add(host)
        
        if host.endswith(".onion"):
            self.target_cache[host] = "TOR HIDDEN SERVICE"
            return
            
        if not self.is_safe_target(host):
            self.target_cache[host] = "LOCAL NETWORK"
            return

        try:
            conn = socket.create_connection((self.tor_host, self.tor_port), timeout=10)
            conn.sendall(b"\x05\x01\x00")
            if conn.recv(2) == b"\x05\x00":
                api_host = b"ip-api.com"
                conn.sendall(b"\x05\x01\x00\x03" + bytes([len(api_host)]) + api_host + (80).to_bytes(2, "big"))
                
                resp_auth = b""
                while len(resp_auth) < 10:
                    chunk = conn.recv(10 - len(resp_auth))
                    if not chunk: break
                    resp_auth += chunk
                    
                if len(resp_auth) == 10 and resp_auth[1] == 0x00:
                    req = f"GET /json/{host}?fields=query,countryCode,status HTTP/1.1\r\nHost: ip-api.com\r\nConnection: close\r\n\r\n"
                    conn.sendall(req.encode())
                    resp = b""
                    while chunk := conn.recv(4096):
                        resp += chunk
                    
                    body = resp.split(b"\r\n\r\n", 1)[-1].decode()
                    data = json.loads(body)
                    
                    if data.get("status") == "success":
                        self.target_cache[host] = f"{data.get('query', 'Unknown')} [{data.get('countryCode', '??')}]"
                    else:
                        raise ValueError("API Failed")
        except Exception:
            try:
                ip = socket.gethostbyname(host)
                self.target_cache[host] = f"{ip} [LOCAL FALLBACK]"
            except Exception:
                self.target_cache[host] = "Unresolvable"
        finally:
            try: conn.close()
            except Exception: pass

    def tor_connect(self, target_host, target_port):
        target_host = target_host.strip().rstrip('.')
        
        if not self.is_safe_target(target_host):
            raise ConnectionError("RFC1918 Blocked")
            
        conn = socket.create_connection((self.tor_host, self.tor_port), timeout=45)
        conn.sendall(b"\x05\x01\x00")
        
        auth_resp = conn.recv(2)
        if not auth_resp or len(auth_resp) < 2 or auth_resp[1] != 0x00:
            conn.close()
            raise ConnectionError("SOCKS5 Proxy Failed")
            
        try:
            # Prevents double encoding if the browser already punycodes it
            if target_host.isascii():
                encoded_host = target_host.encode('ascii')
            else:
                encoded_host = target_host.encode('idna') 
        except Exception:
            encoded_host = target_host.encode('utf-8', errors='ignore')
            
        conn.sendall(b"\x05\x01\x00\x03" + bytes([len(encoded_host)]) + encoded_host + target_port.to_bytes(2, "big"))
        
        response_data = b""
        while len(response_data) < 10:
            chunk = conn.recv(10 - len(response_data))
            if not chunk: break
            response_data += chunk
        
        if len(response_data) < 10 or response_data[1] != 0x00:
            conn.close()
            err_code = response_data[1] if len(response_data) > 1 else 0
            err_msg = SOCKS_ERRORS.get(err_code, f"Tor SOCKS Code {err_code}")
            raise ConnectionError(err_msg)
            
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
        client_socket.settimeout(10.0)
        self.pause_event.wait()
        Track.conn_active += 1
        Track.conn_total += 1
        try:
            # FIX: Loop until the full HTTP header block is received.
            # Prevents partial-header reads which cause random 502/SOCKS timeouts.
            raw_request = b""
            while b"\r\n\r\n" not in raw_request:
                chunk = client_socket.recv(8192)
                if not chunk: break
                raw_request += chunk
                if len(raw_request) > 65536: break
                
            if not raw_request: return
            
            parts = raw_request.split(b"\r\n\r\n", 1)
            headers_bytes = parts[0]
            body_bytes = parts[1] if len(parts) > 1 else b""
            
            headers_str = headers_bytes.decode(errors="replace")
            headers = headers_str.split("\r\n")
            if not headers or not headers[0]: return
            
            request_parts = headers[0].split(" ")
            if len(request_parts) < 2: return
            
            method, url = request_parts[0].upper(), request_parts[1]

            if method not in METHOD_THEME:
                client_socket.sendall(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                return

            if method == "CONNECT":
                host, _, port_string = url.rpartition(":")
                target_port = int(port_string) if port_string.isdigit() else 443
                
                if self.is_noise(host):
                    client_socket.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                    return

                threading.Thread(target=self.fetch_target_info, args=(host,), daemon=True).start()
                target_info = self.target_cache.get(host, "Awaiting Resolution...")
                
                self.logger.log("CONNECT", f"{host}:{target_port}", "", target_info, self.inspect_mode, headers_str, self.dump_file)
                
                try: 
                    target_socket = self.tor_connect(host, target_port)
                    client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    self.pipe_data(client_socket, target_socket)
                except Exception as error_msg:
                    self.logger.log("CONNECT", host, "", target_info, self.inspect_mode, headers_str, self.dump_file, f"err {error_msg}")
                    # Include the Tor error directly in the browser's Proxy response header
                    client_socket.sendall(f"HTTP/1.1 502 Bad Gateway\r\nProxy-Error: {error_msg}\r\n\r\n".encode())
                finally:
                    try: target_socket.close()
                    except Exception: pass
            else:
                parsed_url = urlparse(url)
                
                if parsed_url.hostname:
                    host = parsed_url.hostname
                    target_port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
                    path_and_query = f"{parsed_url.path or '/'}{'?' + parsed_url.query if parsed_url.query else ''}"
                else:
                    host = ""
                    target_port = 80
                    for line in headers[1:]:
                        if line.lower().startswith("host:"):
                            host_val = line.split(":", 1)[1].strip()
                            if ":" in host_val:
                                h, p = host_val.split(":", 1)
                                host = h.strip()
                                target_port = int(p)
                            else:
                                host = host_val.strip()
                                target_port = 80
                            break
                    path_and_query = url

                if not host:
                    client_socket.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                    return
                
                if self.is_noise(host, path_and_query):
                    client_socket.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                    return

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
                
                sanitized_headers.append("Connection: close") 
                rebuilt_request = "\r\n".join(sanitized_headers).encode('utf-8', errors="replace") + b"\r\n\r\n" + body_bytes
                
                threading.Thread(target=self.fetch_target_info, args=(host,), daemon=True).start()
                target_info = self.target_cache.get(host, "Awaiting Resolution...")
                
                self.logger.log(method, host, path_and_query, target_info, self.inspect_mode, headers_str, self.dump_file)
                
                try: 
                    target_socket = self.tor_connect(host, target_port)
                    target_socket.sendall(rebuilt_request)
                    self.pipe_data(client_socket, target_socket)
                except Exception as error_msg:
                    self.logger.log(method, host, path_and_query, target_info, self.inspect_mode, headers_str, self.dump_file, f"err {error_msg}")
                    # Visual HTML Injection: Tells you if Tor couldn't resolve the domain vs code error
                    error_html = f"HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n<html><body style='background:#1a0525;color:#ff4664;font-family:sans-serif;padding:2rem;'><h2>ClearView Proxy System Alert</h2><p>Failed to connect to target: <b>{host}</b></p><p>Reason: <b>{error_msg}</b></p><p style='color:#ccc;font-size:0.9em;margin-top:10px;'>If the reason is 'Host Unreachable / DNS', Tor could not locate this domain (it may be dead, offline, or unregistered).</p></body></html>"
                    client_socket.sendall(error_html.encode(errors="replace"))
                finally:
                    try: target_socket.close()
                    except Exception: pass
        except Exception: pass
        finally:
            Track.conn_active -= 1
            try: client_socket.close()
            except Exception: pass

    def handle_keypress(self, char):
        self.trigger_ui = True
        if self.prompt_mode:
            if char in ('\r', '\n'):
                if self.prompt_mode == 'dump':
                    self.dump_file = self.prompt_text.strip()
                self.prompt_mode = None
                self.prompt_text = ""
            elif char in ('\x08', '\x7f'): 
                self.prompt_text = self.prompt_text[:-1]
            elif char == '\x03': 
                self.prompt_mode = None
                self.prompt_text = ""
            elif char.isprintable():
                self.prompt_text += char
            return

        if char == ' ':  
            if self.pause_event.is_set():
                self.pause_event.clear()
            else:
                self.pause_event.set()
        elif char == 'h':
            self.inspect_mode = not self.inspect_mode
        elif char == 'd':
            self.prompt_mode = 'dump'
            self.prompt_title = "ENTER FILENAME (Leave blank to stop)"
            self.prompt_text = ""
        elif char == 'l':
            self.show_menu = True
        elif char == 'c':
            UI.draw_hud(self.listen_host, self.listen_port, self.tor_host, self.tor_port)
        elif char == '\x03': 
            self.shutdown()

    def keyboard_listener(self):
        try:
            import msvcrt
            while self.running:
                if msvcrt.kbhit():
                    char = msvcrt.getch().decode('utf-8', 'ignore')
                    self.handle_keypress(char)
                time.sleep(0.01)
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
        sys.stdout.write(f"\n  {Colors.P_D}TERMINATING CLEAR VIEW PROTOCOLS.{Colors.RESET}\n\n")
        sys.stdout.flush()
        os._exit(0)

    def start(self):
        if self.listen_host not in ("127.0.0.1", "::1", "localhost"):
            sys.stdout.write(f"\n  {Colors.WARN}[!] CRITICAL: Binding to {self.listen_host} exposes your node.{Colors.RESET}\n")
            time.sleep(2)

        UI.boot_sequence(self.listen_host, self.listen_port, self.tor_host, self.tor_port)
        UI.draw_hud(self.listen_host, self.listen_port, self.tor_host, self.tor_port)
        
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try: 
            server_socket.bind((self.listen_host, self.listen_port))
        except OSError as bind_error:
            sys.stdout.write(f"\n  {Colors.WARN}BIND FAILURE: {self.listen_host}:{self.listen_port} — {bind_error}{Colors.RESET}\n")
            sys.stdout.write(f"  {Colors.DIM}Ensure the port is not in use by another application.{Colors.RESET}\n")
            sys.stdout.flush()
            time.sleep(5) 
            sys.exit(1)
            
        server_socket.listen(256) 
        server_socket.settimeout(0.2) 
        
        threading.Thread(target=self.keyboard_listener, daemon=True).start()

        frames = ["✯", "✰", "✱", "✲", "✳", "✴", "✵", "✶", "✷", "✸", "✹", "✺", "✹", "✸", "✷", "✶", "✵", "✴", "✳", "✲", "✱", "✰"]
        frame_index = 0
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
                    pass 
                except KeyboardInterrupt:
                    self.shutdown()
                    continue
                except Exception:
                    pass 

                current_time = time.time()
                if self.trigger_ui or current_time - last_time >= 0.15:
                    dt = current_time - last_time
                    tx_speed = (Track.tx - last_tx) / dt if dt > 0 else 0
                    rx_speed = (Track.rx - last_rx) / dt if dt > 0 else 0
                    
                    if current_time - last_time >= 0.15:
                        last_tx = Track.tx
                        last_rx = Track.rx
                        last_time = current_time

                    self.trigger_ui = False
                    current_cols = shutil.get_terminal_size().columns

                    if self.show_menu:
                        with self.logger.lock:
                            sys.stdout.write("\r\033[K")
                            menu_lines = [
                                f"┌─ {Colors.BOLD}{Colors.P_L}SYSTEM OVERLAY{Colors.RESET} {'─'*(max(0, current_cols - 23))}",
                                f"│ {Colors.P_M}Total Connections :{Colors.RESET} {Colors.P_VL}{Track.conn_total}{Colors.RESET}",
                                f"│ {Colors.P_M}Active Threads    :{Colors.RESET} {Colors.P_VL}{Track.conn_active}{Colors.RESET}",
                                f"│ {Colors.P_M}Data Transmitted  :{Colors.RESET} {Colors.P_VL}{fmt_bytes(Track.tx)}{Colors.RESET}",
                                f"│ {Colors.P_M}Data Received     :{Colors.RESET} {Colors.P_VL}{fmt_bytes(Track.rx)}{Colors.RESET}",
                                f"└{'─'*(max(0, current_cols - 3))}"
                            ]
                            for line in menu_lines:
                                sys.stdout.write(f"  {Colors.P_D}{line[:2]}{Colors.RESET}{line[2:]}\n")
                            sys.stdout.write("\n")
                            sys.stdout.flush()
                        self.show_menu = False

                    if self.prompt_mode:
                        prompt_str = f"{Colors.P_M}► {self.prompt_title}:{Colors.RESET} {Colors.P_VL}{self.prompt_text}{Colors.RESET}"
                        raw_len = len(ANSI_ESCAPE.sub('', prompt_str))
                        pad = max(0, (current_cols - raw_len - 1) // 2)
                        with self.logger.lock:
                            sys.stdout.write(f"\r\033[K{' ' * pad}{prompt_str}")
                            sys.stdout.flush()
                    else:
                        spin_char = frames[frame_index % len(frames)]
                        is_paused = not self.pause_event.is_set()
                        
                        status_text = f"{Colors.WARN}PAUSED{Colors.RESET}" if is_paused else f"{Colors.OK}ACTIVE{Colors.RESET}"
                        hdr_text = f"{Colors.P_VL}ON{Colors.RESET}" if self.inspect_mode else f"{Colors.DIM}OFF{Colors.RESET}"
                        dump_text = f"{Colors.P_VL}ON{Colors.RESET}" if self.dump_file else f"{Colors.DIM}OFF{Colors.RESET}"
                        
                        hud = (
                            f"  {Colors.P_VL}{spin_char}{Colors.RESET}   "
                            f"{Colors.P_M}TX:{Colors.RESET} {Colors.BOLD}{Colors.P_VL}{fmt_bytes(tx_speed):>8}/s{Colors.RESET}   "
                            f"{Colors.P_M}RX:{Colors.RESET} {Colors.BOLD}{Colors.P_VL}{fmt_bytes(rx_speed):>8}/s{Colors.RESET}   "
                            f"{Colors.DIM}•{Colors.RESET}   "
                            f"{Colors.P_M}[SPACE] STS:{Colors.RESET} {status_text}   "
                            f"{Colors.DIM}•{Colors.RESET}   "
                            f"{Colors.P_M}[H] HEADERS:{Colors.RESET} {hdr_text}   "
                            f"{Colors.DIM}•{Colors.RESET}   "
                            f"{Colors.P_M}[D] DUMP:{Colors.RESET} {dump_text}   "
                            f"{Colors.DIM}•{Colors.RESET}   "
                            f"{Colors.P_M}[C] CLEAR{Colors.RESET}  "
                        )
                        
                        raw_len = len(ANSI_ESCAPE.sub('', hud))
                        pad = max(0, (current_cols - raw_len - 1) // 2)
                        
                        with self.logger.lock:
                            sys.stdout.write(f"\r\033[K{' ' * pad}{hud}")
                            sys.stdout.flush()
                        frame_index += 1

if __name__ == "__main__":
    UI.hide_cursor()
    try:
        proxy = ClearViewProxy(LISTEN_HOST, LISTEN_PORT, TOR_HOST, TOR_PORT)
        proxy.start()
    except Exception as e:
        UI.show_cursor()
        sys.stdout.write(f"\r\033[K\n{Colors.WARN}FATAL ERROR: {e}{Colors.RESET}\n")
        import traceback
        traceback.print_exc()
        time.sleep(5)
