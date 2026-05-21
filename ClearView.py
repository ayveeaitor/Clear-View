#!/usr/bin/env python3

import socket, threading, sys, time, shutil
from datetime import datetime

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
TOR_HOST    = "127.0.0.1"
TOR_PORT    = 9050
BUFFER      = 4096

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

def rgb(r,g,b): return f"\033[38;2;{r};{g};{b}m"

PURPLE     = rgb(160, 90,220)
PURPLE_DIM = rgb( 70, 35,110)
LAVENDER   = rgb(190,150,255)
VIOLET     = rgb(110, 55,190)
VIOLET_LT  = rgb(140, 80,220)
GREY       = rgb( 90, 88,105)
GREY_LT    = rgb(150,148,168)
WHITE      = rgb(220,215,235)
DEEP       = rgb( 40, 20, 70)
PINK       = rgb(220,110,170)
BLUE       = rgb( 90,160,255)

C_GET     = rgb(110,210,130)
C_POST    = rgb(240,175, 55)
C_CONNECT = rgb( 90,175,240)
C_PUT     = rgb(200,120,255)
C_DELETE  = rgb(235, 80, 80)
C_HEAD    = rgb( 90,200,195)
C_OK      = rgb( 90,215,120)
C_ERROR   = rgb(235, 75, 75)

METHOD_COLOR = {
    "GET":C_GET,"POST":C_POST,"PUT":C_PUT,
    "DELETE":C_DELETE,"HEAD":C_HEAD,
    "OPTIONS":LAVENDER,"CONNECT":C_CONNECT,
}

METHOD_GLYPH = {
    "GET":     "◈",
    "POST":    "⬡",
    "PUT":     "◇",
    "DELETE":  "✦",
    "HEAD":    "○",
    "OPTIONS": "⊹",
    "CONNECT": "⬢",
}

NOTE_GLYPH = {
    "tls":  "⬢",
    "http": "◈",
    "err":  "✦",
}

_lock    = threading.Lock()
_counter = 0

_EYE_ROWS = None
def eye_rows():
    global _EYE_ROWS
    if _EYE_ROWS is None:
        raw = [
            [(PURPLE_DIM,"          ██████████████")],
            [(PURPLE_DIM,"       ███"),(PURPLE,"░░░░░░░░░░░░"),(PURPLE_DIM,"███")],
            [(PURPLE_DIM,"     ██"),(PURPLE,"░░░░░"),(LAVENDER,"▄████████▄"),(PURPLE,"░░░░░"),(PURPLE_DIM,"██")],
            [(PURPLE_DIM,"   ██"),(PURPLE,"░░░░"),(LAVENDER,"████"),(WHITE,"████████"),(LAVENDER,"████"),(PURPLE,"░░░░"),(PURPLE_DIM,"██")],
            [(PURPLE_DIM,"  ██"),(PURPLE,"░░░"),(LAVENDER,"███"),(WHITE,"███"),(VIOLET,"▄▄▄▄▄▄▄▄"),(WHITE,"███"),(LAVENDER,"███"),(PURPLE,"░░░"),(PURPLE_DIM,"██")],
            [(PURPLE_DIM,"  ██"),(PURPLE,"░░"),(LAVENDER,"████"),(WHITE,"██"),(VIOLET,"████"),(DEEP,"▄▄▄▄"),(VIOLET,"████"),(WHITE,"██"),(LAVENDER,"████"),(PURPLE,"░░"),(PURPLE_DIM,"██")],
            [(PURPLE_DIM,"  ██"),(PURPLE,"░░"),(LAVENDER,"████"),(WHITE,"██"),(VIOLET,"███"),(DEEP,"██████"),(VIOLET,"███"),(WHITE,"██"),(LAVENDER,"████"),(PURPLE,"░░"),(PURPLE_DIM,"██")],
            [(PURPLE_DIM,"  ██"),(PURPLE,"░░░"),(LAVENDER,"███"),(WHITE,"███"),(VIOLET,"▀▀▀▀▀▀▀▀"),(WHITE,"███"),(LAVENDER,"███"),(PURPLE,"░░░"),(PURPLE_DIM,"██")],
            [(PURPLE_DIM,"   ██"),(PURPLE,"░░░░"),(LAVENDER,"████"),(WHITE,"████████"),(LAVENDER,"████"),(PURPLE,"░░░░"),(PURPLE_DIM,"██")],
            [(PURPLE_DIM,"     ██"),(PURPLE,"░░░░░"),(LAVENDER,"▀████████▀"),(PURPLE,"░░░░░"),(PURPLE_DIM,"██")],
            [(PURPLE_DIM,"       ███"),(PURPLE,"░░░░░░░░░░░░"),(PURPLE_DIM,"███")],
            [(PURPLE_DIM,"          ██████████████")],
        ]
        _EYE_ROWS = [
            ("".join(c+t for c,t in segs)+RESET, "".join(t for _,t in segs))
            for segs in raw
        ]
    return _EYE_ROWS

CREDIT_LINES = [
    "  █████╗ ██╗   ██╗██╗   ██╗███████╗███████╗ █████╗ ██╗████████╗ ██████╗ ██████╗ ",
    " ██╔══██╗╚██╗ ██╔╝██║   ██║██╔════╝██╔════╝██╔══██╗██║╚══██╔══╝██╔═══██╗██╔══██╗",
    " ███████║ ╚████╔╝ ██║   ██║█████╗  █████╗  ███████║██║   ██║   ██║   ██║██████╔╝",
    " ██╔══██║  ╚██╔╝  ╚██╗ ██╔╝██╔══╝  ██╔══╝  ██╔══██║██║   ██║   ██║   ██║██╔══██╗",
    " ██║  ██║   ██║    ╚████╔╝ ███████╗███████╗██║  ██║██║   ██║   ╚██████╔╝██║  ██║",
    " ╚═╝  ╚═╝   ╚═╝     ╚═══╝  ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝",
]

def show_eye(fade=False):
    cols = shutil.get_terminal_size().columns
    for ansi,plain in eye_rows():
        pad = max(0,(cols-len(plain))//2)
        print(" "*pad + (DIM+ansi+RESET if fade else ansi))
    print()

def show_credit():
    cols = shutil.get_terminal_size().columns
    for line in CREDIT_LINES:
        pad = max(0,(cols-len(line))//2)
        print(" "*pad + PURPLE_DIM + line + RESET)
    print()

def move_up(n):   sys.stdout.write(f"\033[{n}A"); sys.stdout.flush()
def erase_down(): sys.stdout.write("\033[J"); sys.stdout.flush()
def hide_cursor(): sys.stdout.write("\033[?25l"); sys.stdout.flush()
def show_cursor(): sys.stdout.write("\033[?25h"); sys.stdout.flush()

def boot():
    hide_cursor()
    cols = shutil.get_terminal_size().columns

    print()
    show_eye()
    show_credit()

    press = "·  press enter to start  ·"
    pad   = max(0,(cols-len(press))//2)
    print(" "*pad + PURPLE_DIM + press + RESET)
    print()

    show_cursor()
    input()
    hide_cursor()

    move_up(len(eye_rows()) + len(CREDIT_LINES) + 4)
    erase_down()

    title  = "C L E A R   V I E W   v 2"
    w      = 70
    tpad   = (w-len(title))//2


    print(f"\n{VIOLET}  ╔{'═'*w}╗{RESET}")
    print(f"{VIOLET}  ║{RESET}{' '*tpad}{BOLD}{LAVENDER}{title}{RESET}{' '*(w-tpad-len(title))}{VIOLET}║{RESET}")
    print(f"{VIOLET}  ╚{'═'*w}╝{RESET}")
    print()

    print(f"  {PINK}proxy{RESET}  {BLUE}{LISTEN_HOST}:{LISTEN_PORT}{RESET}"
          f"  {PINK}→  tor socks5{RESET}  {BLUE}{TOR_HOST}:{TOR_PORT}{RESET}"
          f"  {PINK}·  http proxy mode{RESET}")
    print()

    for label,val in [
        ("socks5 target",    f"{TOR_HOST}:{TOR_PORT}"),
        ("listener binding", f"{LISTEN_HOST}:{LISTEN_PORT}"),
    ]:
        print(f"  {PINK}  {label:<20}{RESET}  {BLUE}{val}{RESET}")
        time.sleep(0.14)
    print()

def divider():
    print(f"{PURPLE_DIM}  {'─'*72}{RESET}")

def row_sep():
    print(f"{PURPLE_DIM}  {'╌'*72}{RESET}")

def col_header():
    print(f"\n  {PINK}  {'TIME':<16}  {'METHOD':<12}  {'EXIT NODE':<22}  DESTINATION{RESET}\n")
    divider()
    print()

def log(method, host, path, exit_ip="", note=""):
    global _counter
    with _lock:
        _counter += 1
        ts  = datetime.now().strftime("%I:%M:%S %p").lstrip("0")
        mc  = METHOD_COLOR.get(method, LAVENDER)
        g   = METHOD_GLYPH.get(method, "◈")
        nk  = note.split()[0] if note else ""
        ng  = NOTE_GLYPH.get(nk, "◈")
 
        seq  = f"  {PURPLE_DIM}{g}{RESET}"
        t    = f"    {PINK}{ts:<14}{RESET}"
        meth = f"  {BOLD}{mc}{method:<10}{RESET}"
        ip   = (f"  {BLUE}{exit_ip:<22}{RESET}"
                if exit_ip else f"  {PINK}{'···':<22}{RESET}")
        dest = f"  {LAVENDER}{host}{RESET}"
        pth  = f"{GREY_LT}{path}{RESET}" if path and path not in ("/","") else ""
        nt   = f"    {PURPLE_DIM}{ng} {note}{RESET}" if note else ""

        print(f"{seq}{t}{meth}{ip}{dest}{pth}{nt}")
        print()
        row_sep()
        print()

_cached_exit_ip = ""
_exit_ip_lock   = threading.Lock()

def fetch_exit_ip_bg():
    global _cached_exit_ip
    try:
        s = socket.create_connection((TOR_HOST,TOR_PORT),timeout=10)
        s.sendall(b"\x05\x01\x00")
        if s.recv(2) != b"\x05\x00": s.close(); return
        h = b"api.ipify.org"
        s.sendall(b"\x05\x01\x00\x03"+bytes([len(h)])+h+(80).to_bytes(2,"big"))
        if s.recv(10)[1] != 0x00: s.close(); return
        s.sendall(b"GET / HTTP/1.1\r\nHost: api.ipify.org\r\nConnection: close\r\n\r\n")
        r = b""
        while True:
            c = s.recv(512)
            if not c: break
            r += c
        s.close()
        body = r.split(b"\r\n\r\n",1)[-1].decode().strip()
        if body and len(body)<40:
            with _exit_ip_lock: _cached_exit_ip = body
    except Exception: pass

def get_exit_ip():
    with _exit_ip_lock: return _cached_exit_ip or ""

def tor_connect(host,port):
    s = socket.create_connection((TOR_HOST,TOR_PORT),timeout=15)
    s.sendall(b"\x05\x01\x00")
    if s.recv(2) != b"\x05\x00":
        s.close(); raise ConnectionError("SOCKS5 handshake failed")
    hb = host.encode()
    s.sendall(b"\x05\x01\x00\x03"+bytes([len(hb)])+hb+port.to_bytes(2,"big"))
    d = s.recv(10)
    if len(d)<2 or d[1]!=0x00:
        s.close(); raise ConnectionError(f"SOCKS5 connect code={d[1] if len(d)>1 else '?'}")
    return s

def pipe(a,b):
    def fwd(src,dst):
        try:
            while True:
                data=src.recv(BUFFER)
                if not data: break
                dst.sendall(data)
        except: pass
        finally:
            for s in(src,dst):
                try: s.shutdown(socket.SHUT_WR)
                except: pass
    t1=threading.Thread(target=fwd,args=(a,b),daemon=True)
    t2=threading.Thread(target=fwd,args=(b,a),daemon=True)
    t1.start();t2.start();t1.join();t2.join()

def handle(client):
    try:
        raw=client.recv(BUFFER)
        if not raw: return
        fl=raw.split(b"\r\n")[0].decode(errors="replace")
        parts=fl.split(" ",2)
        if len(parts)<2: return
        method=parts[0].upper()
        exit_ip=get_exit_ip()

        if method=="CONNECT":
            host,_,ps=parts[1].rpartition(":")
            port=int(ps) if ps.isdigit() else 443
            log("CONNECT",host,f":{port}",exit_ip,"tls")
            try: ts=tor_connect(host,port)
            except Exception as e:
                log("CONNECT",host,"",exit_ip,f"err · {e}"); client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n"); return
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            pipe(client,ts); ts.close()
        else:
            url=parts[1]
            ur=url[7:] if url.startswith("http://") else url
            sl=ur.find("/")
            hp,path=(ur,"/") if sl==-1 else (ur[:sl],ur[sl:])
            if ":" in hp:
                host,ps=hp.rsplit(":",1); port=int(ps) if ps.isdigit() else 80
            else:
                host,port=hp,80
            hl=raw.decode(errors="replace").split("\r\n")
            hl[0]=f"{method} {path} HTTP/1.1"
            rebuilt="\r\n".join(hl).encode(errors="replace")
            log(method,host,path,exit_ip,"http")
            try: ts=tor_connect(host,port)
            except Exception as e:
                log(method,host,path,exit_ip,f"err · {e}"); client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n"); return
            ts.sendall(rebuilt); pipe(client,ts); ts.close()
    except: pass
    finally:
        try: client.close()
        except: pass

def main():
    boot()

    srv=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    try: srv.bind((LISTEN_HOST,LISTEN_PORT))
    except OSError as e:
        print(f"\n  {C_ERROR}bind failed: {LISTEN_HOST}:{LISTEN_PORT} — {e}{RESET}\n")
        show_cursor(); sys.exit(1)
    srv.listen(64)

    threading.Thread(target=fetch_exit_ip_bg,daemon=True).start()

    print(f"  {C_OK}{BOLD}●{RESET}  {BLUE}listening{RESET}  {PINK}{LISTEN_HOST}:{LISTEN_PORT}{RESET}  "
          f"{PINK}·  ctrl-c to quit{RESET}\n")
    col_header()
    print()
    show_cursor()

    try:
        while True:
            c,_=srv.accept()
            threading.Thread(target=handle,args=(c,),daemon=True).start()
    except KeyboardInterrupt:
        print(f"\n\n  {PURPLE}◆{RESET}  {PINK}clear view closed.{RESET}\n")
    finally:
        srv.close()

if __name__=="__main__":
    main()
