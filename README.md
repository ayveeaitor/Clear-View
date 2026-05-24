```C L E A R   V I E W   v 2

> A stealth local proxy that routes web traffic through Tor.  
> Streams network requests, exit node locations, and live bandwidth directly to your terminal.

Built entirely with standard Python libraries. No external dependencies.

---

## ✦ features

* Live telemetry — see requests flowing in real time with the Tor exit IP and quick geo info.  
* Bandwidth HUD — upload/download speeds right in your terminal.  
* Fingerprint evasion — strips common proxy headers and spoofs the User-Agent.  
* Blocks LAN leaks — stops RFC1918 addresses from leaking out.  
* Quiet the noise — simple filters for hosts/methods/status codes.  
* Rate limiting — optional per-client limits so your local machine doesn’t flood the proxy.  
* Handles HTTPS — tunnels CONNECT through Tor like it should.  
* Faster geo lookups — caches exit-node locations so the HUD stays snappy.  
* UA rotation — small pool of User-Agents to mix things up.  
* HUD shortcuts — keyboard keys to toggle sections, clear screen, or dump stats.

---

## ◈ 1. system setup

Requires Python 3 and Tor on SOCKS5 (`127.0.0.1:9050`).

* install tor:
  * arch: `sudo pacman -S tor`
  * debian/ubuntu: `sudo apt install tor`

* start tor:
  * run `sudo tor` in a separate terminal.

* install python:
  * arch: `sudo pacman -S python`
  * debian/ubuntu: `sudo apt install python3`

---

## ⬢ 2. proxy execution

Clone and run:
git clone https://github.com/ayveeaitor/Clear-View
cd Clear-View
python3 ClearView.py```
