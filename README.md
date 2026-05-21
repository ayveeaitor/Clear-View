# Clear-View
```
# C L E A R   V I E W   v 2

> A minimalist local proxy that routes web traffic through Tor.
> Streams network requests directly to your terminal.

Built entirely with standard Python libraries.

---

## ◈ 1. system setup

Requires Python 3 and a local Tor service listening on the default SOCKS5 port (`127.0.0.1:9050`).

* install tor:
  * arch: `sudo pacman -S tor`
  * debian/ubuntu: `sudo apt install tor`

* start tor:
  * run `sudo tor` in a separate terminal.

## ⬢ 2. proxy execution

Clone the repository and spin up the proxy:

3. browser configuration
Route your traffic through the proxy using one of these methods:

[ optional ] foxy proxy addon
the quickest way to toggle the proxy on and off.

install the foxyproxy extension for your browser.

open options and add a new proxy profile.

set proxy type to HTTP.

set ip address to 127.0.0.1 and port to 8080 (or your custom port).

click the extension icon and select your new profile to activate.

[ standard ] manual browser settings
if you prefer not to use extensions.

open your browser's network or proxy settings.

select "manual proxy configuration".

set the HTTP proxy to 127.0.0.1 and port to 8080.

check the box that says "Also use this proxy for HTTPS" (or manually enter the same ip and port for HTTPS/SSL).```
