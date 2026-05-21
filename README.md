# Clear-View
```
# C L E A R   V I E W   v 2

> A stealth local proxy that routes web traffic through Tor.
> Streams network requests, exit node locations, and live bandwidth directly to your terminal.

Built entirely with standard Python libraries. No external dependencies.

---

## ✦ features

* **Live Telemetry:** Real-time stream of HTTP/HTTPS requests with Tor exit node IPs and Geo-Location tracking.
* **Bandwidth Monitor:** Live Upload and Download speed tracking in the terminal HUD.
* **Fingerprint evasion:** Automatically strips identifying proxy headers and spoofs your User-Agent to prevent browser fingerprinting.
* **Hardened Security:** Blocks local network (RFC1918) leaks to prevent de-anonymization.

---

## ◈ 1. system setup

Requires Python 3 and a local Tor service listening on the default SOCKS5 port (`127.0.0.1:9050`).

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

Clone the repository and spin up the proxy:
```bash
git clone [https://github.com/ayveeaitor/Clear-View](https://github.com/ayveeaitor/Clear-View)
cd Clear-View
python3 ClearView.py```
