#!/usr/bin/env python3
"""
SpencerDev Live M3U8 Extractor - ALL SERVERS
Uses curl_cffi Chrome impersonation to bypass datacenter IP blocks
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

EXTRA_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://spencerdevs.xyz",
    "Referer": "https://spencerdevs.xyz/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


def snoopdog_to_url(snoopdog: str) -> str | None:
    try:
        BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
        SNOOPDOG_TABLE = {str(i): ch for i, ch in enumerate(BASE64_ALPHABET)}
        SNOOPDOG_TABLE.update({format(i, "08b"): ch for i, ch in enumerate(BASE64_ALPHABET)})

        encoded = "".join(SNOOPDOG_TABLE.get(token, "") for token in snoopdog.strip().split())
        payload = base64.b64decode(encoded + "=" * (-len(encoded) % 4))

        password = payload[:32]
        salt     = payload[32:48]
        iv       = payload[48:64]
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


def extract_all_m3u8(movie_id: str):
    session = cffi_requests.Session(impersonate="chrome120")

    # Warm-up: visit homepage to pick up cookies
    print("🌐 Warming up session...")
    try:
        session.get("https://spencerdevs.xyz/", headers=EXTRA_HEADERS, timeout=12)
        time.sleep(1)
    except Exception:
        pass

    print(f"\n🌐 Processing movie: {movie_id}")
    all_links = []

    for code in SERVER_CODES:
        server_url = f"https://servers.spencerdevs.xyz/{code}/m/{movie_id}"
        print(f"\n🔍 Server {code} → {server_url}")

        try:
            resp = session.get(server_url, headers=EXTRA_HEADERS, timeout=12)
            print(f"   └─ Status: {resp.status_code}")

            if resp.status_code == 403:
                print("   └─ 403 Forbidden (IP/TLS blocked)")
                continue
            if resp.status_code != 200:
                print(f"   └─ Failed ({resp.status_code})")
                continue

            try:
                data = resp.json()
            except Exception:
                print(f"   └─ Non-JSON: {resp.text[:120]}")
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

        except Exception as e:
            print(f"   └─ Error: {e}")

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