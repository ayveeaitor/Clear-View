#!/usr/bin/env python3

import os
import socket
import sys
import time
import shutil
import threading
import json
import ipaddress
from urllib.parse import urlparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
TOR_HOST = "127.0.0.1"
TOR_PORT = 9050
BUFFER_SIZE = 8192
MAX_WORKERS = 100
SPOOFED_UA = "Mozilla/5.0 (Windows NT 10.0; rv:115.0) Gecko/20100101 Firefox/115.0"

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
    P_D = rgb(70, 20, 120)
    P_M = rgb(140, 50, 210)
    P_L = rgb(190, 110, 255)
    P_VL = rgb(235, 200, 255)
    CYAN = rgb(0, 255, 255)
    RED = rgb(255, 50, 50)
    GREEN = rgb(50, 255, 50)

METHOD_THEME = {
    "GET": (Colors.P_VL, "◈"),
    "POST": (Colors.P_L, "⬡"),
    "PUT": (Colors.P_M, "◇"),
    "DELETE": (Colors.P_D, "✦"),
    "HEAD": (Colors.P_L, "○"),
    "OPTIONS": (Colors.P_M, "⊹"),
    "CONNECT": (Colors.P_VL, "⬢"),
    "SYSTEM": (Colors.CYAN, "⚙"),
}

BANNED_HEADERS = frozenset({
    "x-forwarded-for", "via", "proxy-connection", "x-real-ip",
    "forwarded", "x-forwarded-host", "x-forwarded-proto"
})

class Track:
    tx = 0
    rx = 0

class UI:
    TITLE_LINES = [
        "  ██████╗██╗     ███████╗█████╗ ██████╗    ██╗   ██╗██╗███████╗██╗    ██╗",
        " ██╔════╝██║     ██╔════╝██╔══██╗██╔══██╗  ██║   ██║██║██╔════╝██║    ██║",
        " ██║     ██║     █████╗  ███████║██████╔╝  ██║   ██║██║█████╗  ██║ █╗ ██║",
        " ██║     ██║     ██╔══╝  ██╔══██║██╔══██╗  ╚██╗ ██╔╝██║██╔══╝  ██║███╗██║",
        " ╚██████╗███████╗███████╗██║  ██║██║  ██║   ╚████╔╝ ██║███████╗╚███╔███╔╝",
        "  ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝    ╚═══╝  ╚═╝╚══════╝ ╚══╝╚══╝ ",
        "                         made by ayveeaitor                          "
    ]

    @staticmethod
    def clear_screen():
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    @staticmethod
    def _get_lens_rows():
        raw = [
            [(Colors.P_D,  "       ▄▄▄██████▄▄▄       ")],
            [(Colors.P_M,  "    ▄████▀▀▀▀▀▀▀▀████▄    ")],
            [(Colors.P_L,  "  ▄███▀            ▀███▄  ")],
            [(Colors.P_VL, " ▄██▀     "), (Colors.P_M, "▄▄▄▄▄▄"), (Colors.P_VL, "     ▀██▄ ")],
            [(Colors.P_VL, " ██▌    "), (Colors.P_D, "▄████████▄"), (Colors.P_VL, "    ▐██ ")],
            [(Colors.P_VL, " ██▌    "), (Colors.P_D, "▀████████▀"), (Colors.P_VL, "    ▐██ ")],
            [(Colors.P_VL, " ▀██▄     "), (Colors.P_M, "▀▀▀▀▀▀"), (Colors.P_VL, "     ▄██▀ ")],
            [(Colors.P_L,  "  ▀███▄            ▄███▀  ")],
            [(Colors.P_M,  "    ▀████▄▄▄▄▄▄▄▄████▀    ")],
            [(Colors.P_D,  "       ▀▀▀██████▀▀▀       ")]
        ]
        return [("".join(c + t for c, t in segs) + Colors.RESET, "".join(t for _, t in segs)) for segs in raw]

    @classmethod
    def show_lens(cls, fade=False):
        cols = shutil.get_terminal_size().columns
        for ansi, plain in cls._get_lens_rows():
            pad = max(0, (cols - len(plain)) // 2)
            print(" " * pad + (Colors.DIM + ansi + Colors.RESET if fade else ansi))
        print()

    @classmethod
    def show_title(cls, fade=False):
        cols = shutil.get_terminal_size().columns
        for i, line in enumerate(cls.TITLE_LINES):
            pad = max(0, (cols - len(line)) // 2)
            fmt = (Colors.DIM + Colors.P_D) if fade and i == 6 else ((Colors.DIM + Colors.P_M) if fade else (Colors.P_M if i == 6 else Colors.P_L))
            print(" " * pad + Colors.BOLD + fmt + line + Colors.RESET)
        print()

    @staticmethod
    def hide_cursor():
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    @staticmethod
    def show_cursor():
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    @classmethod
    def boot_sequence(cls, listen_host, listen_port, tor_host, tor_port):
        cls.clear_screen()
        print("\n\n")
        cls.show_lens()
        print("\n")
        cls.show_title()
        
        cols = shutil.get_terminal_size().columns
        press_msg = "·  PRESS ENTER TO INITIALIZE  ·"
        pad = max(0, (cols - len(press_msg)) // 2)
        print("\n\n" + " " * pad + Colors.BOLD + Colors.P_VL + press_msg + Colors.RESET)
        
        cls.show_cursor()
        input()
        cls.hide_cursor()
        
        cls.clear_screen()
        print("\n\n")
        cls.show_lens(fade=True)
        print("\n")
        cls.show_title(fade=True)
        print("\n")
        
        steps = [
            ("Verifying host environment...", 0.4),
            ("Applying RFC1918 local network blocks...", 0.3),
            (f"Binding listener to {listen_host}:{listen_port}...", 0.6),
            (f"Testing SOCKS5 route to {tor_host}:{tor_port}...", 0.8),
            ("Mounting Clear View interface...", 0.7)
        ]
        
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
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
            
        time.sleep(0.3)
        cls.clear_screen()

    @classmethod
    def draw_hud(cls, listen_host, listen_port, tor_host, tor_port):
        cls.clear_screen()
        cols = shutil.get_terminal_size().columns
        print("\n")
        cls.show_title()
        print("\n")
        
        l1 = f"{Colors.P_M}SYSTEM STATUS:{Colors.RESET} {Colors.BOLD}{Colors.P_VL}ONLINE & ROUTING{Colors.RESET}"
        l2 = f"{Colors.P_M}LOCAL PROXY  :{Colors.RESET} {Colors.P_L}{listen_host}:{listen_port}{Colors.RESET}"
        l3 = f"{Colors.P_M}TOR PROXY    :{Colors.RESET} {Colors.P_L}{tor_host}:{tor_port}{Colors.RESET}"
        
        for text, raw_len in [(l1, 31), (l2, 29), (l3, 29)]:
            pad = max(0, (cols - raw_len) // 2)
            print(" " * pad + text)
        print("\n")

class ProxyLogger:
    def __init__(self):
        self.lock = threading.Lock()

    def log(self, method, host, path, exit_ip="", note=""):
        with self.lock:
            sys.stdout.write("\r\033[K")
            timestamp = datetime.now().strftime("%H:%M:%S")
            method_color, icon = METHOD_THEME.get(method, (Colors.P_M, "◈"))
            ip_display = exit_ip if exit_ip else "AWAITING UPLINK"
            
            time_str = f"{Colors.P_D}[{Colors.P_M}{timestamp}{Colors.P_D}]{Colors.RESET}"
            method_str = f"{icon} {Colors.BOLD}{method_color}{method:<7}{Colors.RESET}"
            host_str = f"{Colors.P_VL}{host}{Colors.RESET}"
            
            print(f"  {time_str} {method_str} ⮞ {host_str}")
            
            telemetry = f"NODE: {ip_display}"
            
            if method == "CONNECT":
                telemetry += f"  {Colors.P_D}|{Colors.RESET}  {Colors.P_L}TLS SECURE{Colors.RESET}"
            elif path and path not in ("/", ""):
                display_path = path[:60] + "..." if len(path) > 60 else path
                telemetry += f"  {Colors.P_D}|{Colors.RESET}  {Colors.P_M}PATH: {display_path}{Colors.RESET}"
                
            if note and "err" not in note:
                telemetry += f"  {Colors.P_D}|{Colors.RESET}  {Colors.CYAN}{note}{Colors.RESET}"
            elif note and "err" in note:
                telemetry += f"  {Colors.P_D}|{Colors.RESET}  {Colors.RED}ERROR: {note}{Colors.RESET}"

            print(f"             {Colors.P_D}└─{Colors.RESET} {Colors.P_M}{telemetry}{Colors.RESET}\n")

class ClearViewProxy:
    def __init__(self, listen_host, listen_port, tor_host, tor_port):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.tor_host = tor_host
        self.tor_port = tor_port
        self.logger = ProxyLogger()
        self.exit_ip = ""
        self.ip_lock = threading.Lock()

    def is_safe_target(self, host):
        try:
            ip_obj = ipaddress.ip_address(host)
            if ip_obj.is_private or ip_obj.is_loopback:
                return False
        except ValueError:
            pass
        return True

    def fetch_exit_ip(self):
        while True:
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
                            country_name = data.get("country", "Unknown")
                            if current_ip:
                                with self.ip_lock:
                                    self.exit_ip = f"{current_ip} [{country_name}]"
                        except Exception:
                            pass
            except Exception:
                pass
            finally:
                try: conn.close()
                except Exception: pass
            time.sleep(60)

    def tor_connect(self, target_host, target_port):
        if not self.is_safe_target(target_host):
            raise ConnectionError("RFC1918 Blocked: Local network access denied.")
            
        conn = socket.create_connection((self.tor_host, self.tor_port), timeout=15)
        conn.sendall(b"\x05\x01\x00")
        if conn.recv(2) != b"\x05\x00":
            conn.close()
            raise ConnectionError("SOCKS5 handshake failed")
            
        encoded_host = target_host.encode()
        conn.sendall(b"\x05\x01\x00\x03" + bytes([len(encoded_host)]) + encoded_host + target_port.to_bytes(2, "big"))
        response_data = conn.recv(10)
        
        if len(response_data) < 2 or response_data[1] != 0x00:
            error_code = response_data[1] if len(response_data) > 1 else "?"
            conn.close()
            raise ConnectionError(f"SOCKS5 connect code={error_code}")
        return conn

    def pipe_data(self, client_socket, target_socket):
        client_socket.settimeout(60)
        target_socket.settimeout(60)
        
        def forward(source, destination, is_tx):
            try:
                while data := source.recv(BUFFER_SIZE):
                    data_length = len(data)
                    if is_tx: Track.tx += data_length
                    else: Track.rx += data_length
                    destination.sendall(data)
            except Exception:
                pass
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
        try:
            raw_request = client_socket.recv(BUFFER_SIZE)
            if not raw_request or len(raw_request) > BUFFER_SIZE:
                return
            
            headers = raw_request.decode(errors="replace").split("\r\n")
            if not headers or not headers[0]:
                return
            
            request_parts = headers[0].split(" ")
            if len(request_parts) < 2:
                return
            
            method, url = request_parts[0].upper(), request_parts[1]
            if method not in METHOD_THEME:
                client_socket.sendall(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                return

            with self.ip_lock:
                current_exit_ip = self.exit_ip

            if method == "CONNECT":
                host, _, port_string = url.rpartition(":")
                target_port = int(port_string) if port_string.isdigit() else 443
                
                self.logger.log("CONNECT", f"{host}:{target_port}", "", current_exit_ip)
                
                try: 
                    target_socket = self.tor_connect(host, target_port)
                    client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    self.pipe_data(client_socket, target_socket)
                except Exception as error_msg:
                    self.logger.log("CONNECT", host, "", current_exit_ip, f"err {error_msg}")
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
                    if not header_line:
                        continue
                    header_key = header_line.split(":", 1)[0].lower().strip()
                    
                    if header_key in BANNED_HEADERS or header_key == "connection":
                        continue 
                    if header_key == "user-agent":
                        sanitized_headers.append(f"User-Agent: {SPOOFED_UA}")
                        has_ua = True
                        continue
                    sanitized_headers.append(header_line)
                
                if not has_ua:
                    sanitized_headers.append(f"User-Agent: {SPOOFED_UA}")
                    
                sanitized_headers.append("Connection: close\r\n") 
                rebuilt_request = "\r\n".join(sanitized_headers).encode(errors="replace")
                
                self.logger.log(method, host, path_and_query, current_exit_ip)
                
                try: 
                    target_socket = self.tor_connect(host, target_port)
                    target_socket.sendall(rebuilt_request)
                    self.pipe_data(client_socket, target_socket)
                except Exception as error_msg:
                    self.logger.log(method, host, path_and_query, current_exit_ip, f"err {error_msg}")
                    client_socket.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                finally:
                    try: target_socket.close()
                    except Exception: pass
        except Exception:
            pass
        finally:
            try: client_socket.close()
            except Exception: pass

    def start(self):
        if self.listen_host not in ("127.0.0.1", "::1", "localhost"):
            print(f"\n  {Colors.P_D}[!] CRITICAL: Binding to {self.listen_host} exposes your node.{Colors.RESET}")
            time.sleep(2)

        UI.boot_sequence(self.listen_host, self.listen_port, self.tor_host, self.tor_port)
        UI.draw_hud(self.listen_host, self.listen_port, self.tor_host, self.tor_port)
        
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try: 
            server_socket.bind((self.listen_host, self.listen_port))
        except OSError as bind_error:
            print(f"\n  {Colors.P_D}BIND FAILURE: {self.listen_host}:{self.listen_port} — {bind_error}{Colors.RESET}\n")
            sys.exit(1)
            
        server_socket.listen(128)
        server_socket.settimeout(0.25) 
        
        threading.Thread(target=self.fetch_exit_ip, daemon=True).start()

        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        frame_index = 0
        cols = shutil.get_terminal_size().columns
        last_tx = 0
        last_rx = 0
        last_time = time.time()

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            while True:
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

                    spin_char = frames[frame_index % len(frames)]
                    wait_message = f"UPLOAD: {fmt_bytes(tx_speed)}/s | DOWNLOAD: {fmt_bytes(rx_speed)}/s | Press Ctrl+C to Exit"
                    pad = max(0, (cols - len(wait_message) - 2) // 2)
                    
                    with self.logger.lock:
                        sys.stdout.write(f"\r{' ' * pad}{Colors.P_L}{spin_char}{Colors.RESET} {Colors.P_M}{wait_message}{Colors.RESET}\033[K")
                        sys.stdout.flush()
                    frame_index += 1
                except KeyboardInterrupt:
                    sys.stdout.write("\r\033[K")
                    UI.show_cursor()
                    try:
                        ans = input(f"\n  {Colors.P_M}Exit Clear View? (y/n): {Colors.RESET}").strip().lower()
                    except KeyboardInterrupt:
                        ans = 'y'
                        
                    UI.hide_cursor()
                    if ans == 'y':
                        print(f"\n  {Colors.P_D}TERMINATING CLEAR VIEW.{Colors.RESET}\n")
                        server_socket.close()
                        os._exit(0)
                    else:
                        print(f"\n  {Colors.P_L}Resuming operations...{Colors.RESET}\n")
                        continue

if __name__ == "__main__":
    UI.hide_cursor()
    proxy = ClearViewProxy(LISTEN_HOST, LISTEN_PORT, TOR_HOST, TOR_PORT)
    proxy.start()
