#!/usr/bin/env python3
"""
SpencerDev Live M3U8 Extractor - ALL SERVERS
Uses curl_cffi Chrome impersonation + rotating residential proxies
"""

import argparse
import base64
import hashlib
import re
import sys
import time

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7
except ImportError:
    print("❌ Run: pip install cryptography curl_cffi")
    sys.exit(1)

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("❌ Run: pip install curl_cffi")
    sys.exit(1)

SERVER_CODES = [25, 24, 1, 23, 22]

PROXIES = [
    {"ip": "31.59.20.176",    "port": "6754"},
    {"ip": "31.56.127.193",   "port": "7684"},
    {"ip": "45.38.107.97",    "port": "6014"},
    {"ip": "38.154.203.95",   "port": "5863"},
    {"ip": "198.105.121.200", "port": "6462"},
    {"ip": "64.137.96.74",    "port": "6641"},
    {"ip": "198.23.243.226",  "port": "6361"},
    {"ip": "38.154.185.97",   "port": "6370"},
    {"ip": "142.111.67.146",  "port": "5611"},
    {"ip": "191.96.254.138",  "port": "6185"},
]
PROXY_USER = "ygxmhkcc"
PROXY_PASS = "n3batopqanpg"

EXTRA_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://spencerdevs.xyz",
    "Referer": "https://spencerdevs.xyz/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


def make_proxy_url(p: dict) -> str:
    return f"http://{PROXY_USER}:{PROXY_PASS}@{p['ip']}:{p['port']}"


def make_session(proxy_url: str) -> cffi_requests.Session:
    session = cffi_requests.Session(impersonate="chrome120")
    session.proxies = {"http": proxy_url, "https": proxy_url}
    return session


def get_working_session() -> tuple[cffi_requests.Session, str] | tuple[None, None]:
    """Try each proxy until one successfully hits the homepage."""
    for p in PROXIES:
        proxy_url = make_proxy_url(p)
        label = f"{p['ip']}:{p['port']}"
        try:
            session = make_session(proxy_url)
            resp = session.get("https://spencerdevs.xyz/", headers=EXTRA_HEADERS, timeout=10)
            if resp.status_code < 500:
                print(f"   ✅ Proxy working: {label}")
                return session, label
            else:
                print(f"   ✗ {label} → {resp.status_code}")
        except Exception as e:
            print(f"   ✗ {label} → {e}")
    return None, None


def snoopdog_to_url(snoopdog: str) -> str | None:
    try:
        BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
        SNOOPDOG_TABLE = {str(i): ch for i, ch in enumerate(BASE64_ALPHABET)}
        SNOOPDOG_TABLE.update({format(i, "08b"): ch for i, ch in enumerate(BASE64_ALPHABET)})

        encoded = "".join(SNOOPDOG_TABLE.get(token, "") for token in snoopdog.strip().split())
        payload = base64.b64decode(encoded + "=" * (-len(encoded) % 4))

        password  = payload[:32]
        salt      = payload[32:48]
        iv        = payload[48:64]
        ciphertext = payload[64:]

        key = hashlib.pbkdf2_hmac("sha512", password, salt, 100000, dklen=32)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = PKCS7(128).unpadder()
        plain = unpadder.update(padded) + unpadder.finalize()
        return plain.decode("utf-8", errors="replace").strip()
    except Exception as e:
        print(f"   Decryption failed: {e}")
        return None


def fetch_with_fallback(url: str) -> dict | None:
    """Try each proxy until we get a 200 JSON response."""
    for p in PROXIES:
        proxy_url = make_proxy_url(p)
        label = f"{p['ip']}:{p['port']}"
        try:
            session = make_session(proxy_url)
            resp = session.get(url, headers=EXTRA_HEADERS, timeout=12)
            if resp.status_code == 200:
                return resp.json()
            print(f"      proxy {label} → {resp.status_code}, trying next...")
        except Exception as e:
            print(f"      proxy {label} → error: {e}, trying next...")
        time.sleep(0.3)
    return None


def extract_all_m3u8(movie_id: str):
    print("🌐 Finding working proxy...")
    session, active_proxy = get_working_session()
    if session is None:
        print("❌ All proxies failed on warm-up. Continuing anyway...")

    print(f"\n🌐 Processing movie: {movie_id}")
    all_links = []

    for code in SERVER_CODES:
        server_url = f"https://servers.spencerdevs.xyz/{code}/m/{movie_id}"
        print(f"\n🔍 Server {code} → {server_url}")

        # Try active session first, fall back to proxy rotation per request
        data = None
        if session:
            try:
                resp = session.get(server_url, headers=EXTRA_HEADERS, timeout=12)
                print(f"   └─ Status: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                elif resp.status_code in (403, 429):
                    print("   └─ Blocked, trying proxy rotation...")
                    data = fetch_with_fallback(server_url)
                else:
                    print(f"   └─ Failed ({resp.status_code})")
            except Exception as e:
                print(f"   └─ Session error: {e}, trying proxy rotation...")
                data = fetch_with_fallback(server_url)
        else:
            data = fetch_with_fallback(server_url)

        if data is None:
            print("   └─ All proxies exhausted for this server")
            continue

        if "snoopdog" in data:
            print("   └─ Snoopdog found → Decrypting...")
            m3u8_url = snoopdog_to_url(data["snoopdog"])
            if m3u8_url and m3u8_url.startswith("http"):
                print(f"   ✅ {m3u8_url}")
                all_links.append(m3u8_url)
            else:
                print("   └─ Decryption produced invalid URL")
        else:
            print(f"   └─ No snoopdog key. Keys: {list(data.keys())}")

        time.sleep(0.5)

    if all_links:
        print(f"\n🎉 Found {len(all_links)} streaming links!")
        for i, url in enumerate(all_links, 1):
            print(f"{i:2d}. {url}")
    else:
        print("\n❌ No links found.")

    return all_links


def main():
    parser = argparse.ArgumentParser(description="Extract ALL M3U8 from SpencerDev")
    parser.add_argument("input", nargs="?", help="Movie ID or URL")
    parser.add_argument("--url", help="Full URL")
    args = parser.parse_args()

    if args.url:
        input_val = args.url
    elif args.input:
        input_val = args.input
    else:
        input_val = input("Enter movie ID or full URL: ").strip()

    match = re.search(r"/movie/(\d+)", input_val)
    movie_id = match.group(1) if match else input_val.strip()

    if not movie_id.isdigit():
        print("❌ Invalid movie ID")
        sys.exit(1)

    extract_all_m3u8(movie_id)


if __name__ == "__main__":
    main()