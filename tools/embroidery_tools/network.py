"""Find and fingerprint the machine on the local network.

Scope note, so nobody wastes an afternoon: Brother's wireless design-transfer
protocol is **closed**. There is no published API, no SDK, and no public
reverse-engineering effort for the SE-series. Pushing a design over the network
means Design Database Transfer (Windows GUI) or Artspira (phone) — this module
cannot do it and neither can anything else you can install.

What it *can* do is locate the machine, confirm it is online and reachable, and
fingerprint whatever services it exposes. That is genuinely useful: it turns
"the machine isn't showing up in Design Database Transfer" from a guessing game
into a two-minute answer.
"""

from __future__ import annotations

import concurrent.futures
import csv
import ipaddress
import re
import socket
import struct
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import profile as prof

OUI_PATH = prof.REPO_ROOT / "reference" / "oui.csv"
OUI_URL = "https://standards-oui.ieee.org/oui/oui.csv"

# Ports worth asking about on an unknown networked Brother device. The
# design-transfer port is undocumented; we probe broadly and report what answers
# rather than pretending to know.
CANDIDATE_PORTS = {
    80: "http",
    443: "https",
    139: "netbios-ssn",
    445: "smb",
    515: "lpd",
    631: "ipp",
    5222: "xmpp",
    5357: "wsd",
    8080: "http-alt",
    9100: "jetdirect/raw",
    9600: "brother-mgmt?",
    54921: "brother-ctl?",
    54925: "brother-discovery?",
}


@dataclass
class Host:
    ip: str
    mac: str = ""
    vendor: str = ""
    randomised_mac: bool = False
    icmp: bool = False
    open_ports: dict = field(default_factory=dict)
    hostname: str = ""
    snmp_sysdescr: str = ""
    banner: str = ""

    @property
    def is_brother(self) -> bool:
        return "brother industries" in self.vendor.lower()

    @property
    def evidence(self) -> list[str]:
        """Why we think this is a Brother machine. Empty means we don't."""
        found = []
        haystack = " ".join(
            (self.snmp_sysdescr, self.banner, self.hostname)
        ).lower()
        if self.is_brother:
            found.append(f"MAC registered to Brother ({self.vendor})")
        if "brother" in haystack:
            found.append("banner names Brother")
        for sig, why in BROTHER_SIGNATURES.items():
            if sig in haystack:
                found.append(why)
        if CERT_IDENTITY_RE.search(self.banner):
            m = CERT_IDENTITY_RE.search(self.banner)
            found.append(f"TLS cert identity string, software v{m.group(1)}")
        return found

    @property
    def looks_like_machine(self) -> bool:
        """Brother OUI, or any service fingerprint that identifies Brother.

        The OUI test alone is NOT sufficient, and assuming otherwise will make
        you miss the machine entirely: appliances frequently ship an OEM radio
        module (Foxconn, Espressif, Murata, AzureWave), so the registered MAC
        belongs to the module vendor rather than to Brother. The SE700 on the
        author's network reports a Foxconn/Cloud Network Technology OUI.
        """
        return bool(self.evidence)


# Service fingerprints that identify a Brother device regardless of MAC vendor.
BROTHER_SIGNATURES = {
    # Brother's embedded HTTP server. nmap fingerprints it as
    # "Debut embedded httpd (Brother/HP printer http admin)"; Tenable ships
    # plugin 104901 "Brother Printer Debut Embedded HTTP Server Detection".
    "debut/": "runs Brother's 'Debut' embedded httpd",
}

# Brother machines present a self-signed cert whose CN looks like
# "60;3;1;1.72.local" — the last numeric field is the machine software version.
CERT_IDENTITY_RE = re.compile(r"\d+;\d+;\d+;(\d+\.\d+)\.local")


# --------------------------------------------------------------------------- #
# OUI vendor lookup


@lru_cache(maxsize=1)
def load_oui(path: Path | None = None) -> dict[str, str]:
    p = Path(path) if path else OUI_PATH
    if not p.is_file():
        return {}
    table: dict[str, str] = {}
    with p.open(encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            assignment = (row.get("Assignment") or "").strip().upper()
            if assignment:
                table[assignment] = (row.get("Organization Name") or "").strip()
    return table


def download_oui(path: Path | None = None) -> Path:
    """Fetch the IEEE OUI registry (~4 MB) for offline vendor lookups."""
    import urllib.request

    dst = Path(path) if path else OUI_PATH
    dst.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(OUI_URL, timeout=120) as r, dst.open("wb") as f:
        f.write(r.read())
    load_oui.cache_clear()
    return dst


def brother_ouis() -> dict[str, str]:
    return {
        k: v for k, v in load_oui().items() if "brother industries" in v.lower()
    }


def vendor_for(mac: str) -> tuple[str, bool]:
    """Return (vendor, is_randomised) for a MAC in any common notation."""
    clean = re.sub(r"[^0-9A-Fa-f]", "", mac).upper()
    if len(clean) < 6:
        return ("", False)
    # Bit 1 of the first octet marks a locally administered (privacy) address.
    randomised = bool(int(clean[1], 16) & 0x2)
    vendor = load_oui().get(clean[:6], "")
    if not vendor:
        vendor = "locally administered (randomised)" if randomised else "unknown"
    return (vendor, randomised)


# --------------------------------------------------------------------------- #
# Discovery


def local_subnets() -> list[dict]:
    """Interfaces with an IPv4 address and a default gateway, via PowerShell."""
    ps = (
        "Get-NetIPConfiguration | Where-Object { $_.IPv4Address -and "
        "$_.NetAdapter.Status -eq 'Up' } | ForEach-Object { "
        "'{0}|{1}|{2}|{3}' -f $_.InterfaceAlias, $_.IPv4Address.IPAddress, "
        "$_.IPv4Address.PrefixLength, ($_.IPv4DefaultGateway.NextHop -join ',') }"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []

    nets = []
    for line in out.splitlines():
        parts = line.strip().split("|")
        if len(parts) != 4 or not parts[1]:
            continue
        alias, ip, prefix, gw = parts
        try:
            net = ipaddress.ip_network(f"{ip}/{prefix}", strict=False)
        except ValueError:
            continue
        nets.append(
            {"interface": alias, "ip": ip, "network": str(net),
             "gateway": gw, "hosts": net.num_addresses - 2}
        )
    return nets


def _ping(ip: str, timeout_ms: int = 800) -> bool:
    try:
        r = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout_ms), ip],
            capture_output=True, text=True,
            timeout=(timeout_ms / 1000) + 3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return r.returncode == 0 and "TTL=" in r.stdout.upper()
    except (OSError, subprocess.SubprocessError):
        return False


def sweep(network: str, workers: int = 128, timeout_ms: int = 800) -> set[str]:
    """Ping every host in the network. Also populates the ARP cache, which is
    what actually matters — devices that ignore ICMP still answer ARP."""
    net = ipaddress.ip_network(network, strict=False)
    targets = [str(h) for h in net.hosts()]
    alive: set[str] = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for ip, ok in zip(targets, pool.map(lambda i: _ping(i, timeout_ms), targets)):
            if ok:
                alive.add(ip)
    return alive


def arp_table() -> dict[str, str]:
    """Read the OS ARP cache: {ip: mac}."""
    try:
        out = subprocess.run(["arp", "-a"], capture_output=True, text=True,
                             timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    table = {}
    for m in re.finditer(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5})", out):
        mac = m.group(2).lower().replace(":", "-")
        if mac != "ff-ff-ff-ff-ff-ff":
            table[m.group(1)] = mac
    return table


def probe_ports(ip: str, ports: dict | None = None, timeout: float = 0.6) -> dict:
    ports = ports or CANDIDATE_PORTS
    found = {}

    def check(port: int) -> tuple[int, bool]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            return (port, s.connect_ex((ip, port)) == 0)
        except OSError:
            return (port, False)
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ports)) as pool:
        for port, ok in pool.map(check, ports):
            if ok:
                found[port] = ports[port]
    return found


def _ber_tlv(tag: int, payload: bytes) -> bytes:
    if len(payload) < 0x80:
        return bytes([tag, len(payload)]) + payload
    length = len(payload).to_bytes((len(payload).bit_length() + 7) // 8, "big")
    return bytes([tag, 0x80 | len(length)]) + length + payload


def _ber_read(data: bytes, pos: int) -> tuple[int, bytes, int]:
    """Read one BER element. Returns (tag, value, next_pos)."""
    if pos + 2 > len(data):
        raise ValueError("truncated BER")
    tag = data[pos]
    ln = data[pos + 1]
    pos += 2
    if ln & 0x80:
        n = ln & 0x7F
        if n == 0 or pos + n > len(data):
            raise ValueError("bad BER length")
        ln = int.from_bytes(data[pos:pos + n], "big")
        pos += n
    if pos + ln > len(data):
        raise ValueError("truncated BER value")
    return tag, data[pos:pos + ln], pos + ln


SNMP_ERRORS = {
    0: "", 1: "tooBig", 2: "noSuchName", 3: "badValue",
    4: "readOnly", 5: "genErr",
}


def snmp_get(ip: str, oid_arcs: bytes, community: str = "public",
             timeout: float = 1.5) -> str:
    """SNMPv1 GET, properly BER-decoded.

    Hand-rolled rather than pulling a dependency for one request. Returns the
    varbind value as text, or "" if the host does not answer or returns an
    error. Critically, this decodes the *structure* — an earlier version of this
    function scanned for the longest printable OCTET STRING and happily returned
    the echoed community string ("public") as if it were a device banner.
    """
    varbind = _ber_tlv(0x30, _ber_tlv(0x06, oid_arcs) + _ber_tlv(0x05, b""))
    pdu = _ber_tlv(
        0xA0,
        _ber_tlv(0x02, b"\x01")        # request-id
        + _ber_tlv(0x02, b"\x00")      # error-status
        + _ber_tlv(0x02, b"\x00")      # error-index
        + _ber_tlv(0x30, varbind),
    )
    msg = _ber_tlv(
        0x30,
        _ber_tlv(0x02, b"\x00") + _ber_tlv(0x04, community.encode()) + pdu,
    )

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(msg, (ip, 161))
        data, _ = s.recvfrom(8192)
    except OSError:
        return ""
    finally:
        s.close()

    try:
        _, body, _ = _ber_read(data, 0)              # outer SEQUENCE
        _, _, p = _ber_read(body, 0)                 # version
        _, _, p = _ber_read(body, p)                 # community (ignored)
        _, pdu_body, _ = _ber_read(body, p)          # response PDU
        _, _, q = _ber_read(pdu_body, 0)             # request-id
        _, err, q = _ber_read(pdu_body, q)           # error-status
        if err and err[0] != 0:
            return ""                                # noSuchName etc.
        _, _, q = _ber_read(pdu_body, q)             # error-index
        _, vblist, _ = _ber_read(pdu_body, q)        # varbind list
        _, vb, _ = _ber_read(vblist, 0)              # first varbind
        _, _, r = _ber_read(vb, 0)                   # the OID
        tag, value, _ = _ber_read(vb, r)             # the value
    except (ValueError, IndexError):
        return ""

    if tag in (0x05, 0x80, 0x81, 0x82):              # NULL / no-such-object
        return ""
    if tag == 0x02:
        return str(int.from_bytes(value, "big"))
    text = value.decode("utf-8", errors="replace").strip()
    return text if text.isprintable() else ""


# sysDescr.0 — 1.3.6.1.2.1.1.1.0 (first two arcs pack into 0x2B)
OID_SYSDESCR = bytes([0x2B, 0x06, 0x01, 0x02, 0x01, 0x01, 0x01, 0x00])
# sysName.0 — 1.3.6.1.2.1.1.5.0
OID_SYSNAME = bytes([0x2B, 0x06, 0x01, 0x02, 0x01, 0x01, 0x05, 0x00])


def snmp_sysdescr(ip: str, community: str = "public", timeout: float = 1.5) -> str:
    return snmp_get(ip, OID_SYSDESCR, community, timeout)


def _printable_runs(blob: bytes, minlen: int = 4) -> list[str]:
    return [m.decode("ascii") for m in re.findall(rb"[\x20-\x7e]{%d,}" % minlen, blob)]


def tls_identity(ip: str, port: int = 443, timeout: float = 3.0) -> str:
    """Pull identifying strings out of a TLS certificate.

    Self-signed certificates on appliances almost always carry the model or
    vendor in the subject CN, which makes this a strong fingerprint when the
    MAC belongs to an OEM radio module rather than the brand.
    """
    import ssl

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((ip, port), timeout=timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=ip) as tls:
                der = tls.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError, ValueError):
        return ""
    if not der:
        return ""
    # Parse-free extraction: certificate subject fields are printable ASCII runs.
    interesting = [
        s for s in _printable_runs(der, 4)
        if not s.startswith("http") and "." in s or s.isalpha()
    ]
    seen, out = set(), []
    for s in interesting:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return " | ".join(out[:8])


def http_banner(ip: str, port: int = 80, timeout: float = 3.0) -> str:
    """Fetch the Server: header and <title> from an HTTP endpoint."""
    scheme_tls = port in (443, 8443)
    try:
        if scheme_tls:
            import ssl
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            raw = socket.create_connection((ip, port), timeout=timeout)
            sock = ctx.wrap_socket(raw, server_hostname=ip)
        else:
            sock = socket.create_connection((ip, port), timeout=timeout)
        with sock:
            sock.sendall(
                f"GET / HTTP/1.1\r\nHost: {ip}\r\n"
                f"User-Agent: stitch-discover\r\nConnection: close\r\n\r\n".encode()
            )
            chunks = []
            while len(b"".join(chunks)) < 16384:
                try:
                    b = sock.recv(4096)
                except (socket.timeout, OSError):
                    break
                if not b:
                    break
                chunks.append(b)
    except (OSError, ValueError, ImportError):
        return ""

    body = b"".join(chunks).decode("utf-8", errors="replace")
    bits = []
    m = re.search(r"^Server:\s*(.+)$", body, re.I | re.M)
    if m:
        bits.append(f"Server: {m.group(1).strip()}")
    m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
        if title:
            bits.append(f"title: {title}")
    return " | ".join(bits)


def reverse_name(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except (OSError, socket.herror):
        return ""


def discover(
    network: str | None = None,
    *,
    do_sweep: bool = True,
    deep: bool = False,
) -> list[Host]:
    """Enumerate LAN neighbours, annotate with vendor, and optionally probe.

    `deep` adds a TCP port scan, SNMP query, and reverse DNS per host — slower,
    but it is what identifies a device whose MAC vendor is uninformative.
    """
    if network is None:
        nets = [n for n in local_subnets() if n["gateway"]]
        if not nets:
            raise RuntimeError("No interface with a default gateway found.")
        network = nets[0]["network"]

    alive = sweep(network) if do_sweep else set()
    net = ipaddress.ip_network(network, strict=False)

    hosts: list[Host] = []
    for ip, mac in sorted(
        arp_table().items(), key=lambda kv: tuple(int(o) for o in kv[0].split("."))
    ):
        try:
            if ipaddress.ip_address(ip) not in net:
                continue
        except ValueError:
            continue
        vendor, randomised = vendor_for(mac)
        hosts.append(
            Host(ip=ip, mac=mac, vendor=vendor,
                 randomised_mac=randomised, icmp=ip in alive)
        )

    if deep and hosts:
        def enrich(h: Host) -> Host:
            h.open_ports = probe_ports(h.ip)
            h.hostname = reverse_name(h.ip)
            h.snmp_sysdescr = snmp_sysdescr(h.ip)
            h.banner = collect_banner(h.ip, h.open_ports)
            return h

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            hosts = list(pool.map(enrich, hosts))

    return hosts


def collect_banner(ip: str, open_ports: dict) -> str:
    """HTTP Server/title and TLS certificate identity for any web ports open."""
    bits = []
    for port in (80, 8080, 443, 8443):
        if port in open_ports:
            b = http_banner(ip, port)
            if b:
                bits.append(f"[:{port}] {b}")
    for port in (443, 8443):
        if port in open_ports:
            t = tls_identity(ip, port)
            if t:
                bits.append(f"[:{port} cert] {t}")
    return "  ".join(bits)


def fingerprint(ip: str) -> Host:
    """Everything we can learn about one address."""
    mac = arp_table().get(ip, "")
    vendor, randomised = vendor_for(mac) if mac else ("", False)
    h = Host(ip=ip, mac=mac, vendor=vendor, randomised_mac=randomised)
    h.icmp = _ping(ip)
    h.open_ports = probe_ports(ip, timeout=1.2)
    h.hostname = reverse_name(ip)
    h.snmp_sysdescr = snmp_sysdescr(ip)
    h.banner = collect_banner(ip, h.open_ports)
    return h


# --------------------------------------------------------------------------- #
# Snapshot / diff — the reliable way to spot a device with an OEM MAC


def snapshot(network: str | None = None) -> dict[str, str]:
    """{ip: mac} for the current subnet. Cheap; run before and after power-on."""
    return {h.ip: h.mac for h in discover(network, deep=False)}


def diff_snapshots(before: dict, after: dict) -> dict:
    """Hosts that appeared, disappeared, or changed MAC between two snapshots."""
    return {
        "appeared": {ip: mac for ip, mac in after.items() if ip not in before},
        "disappeared": {ip: mac for ip, mac in before.items() if ip not in after},
        "changed": {
            ip: (before[ip], after[ip])
            for ip in set(before) & set(after)
            if before[ip] != after[ip]
        },
    }
