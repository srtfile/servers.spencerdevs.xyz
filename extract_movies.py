#!/usr/bin/env python3
"""
SpencerDev Live M3U8 Extractor - ALL SERVERS
Extracts every available streaming URL (master + variants)
"""

import argparse
import base64
import hashlib
import re
import sys

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7
except ImportError:
    print("❌ Run: pip install cryptography requests")
    sys.exit(1)

import requests

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
SERVER_CODES = [25, 24, 1, 23, 22]


def snoopdog_to_url(snoopdog: str) -> str | None:
    try:
        BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
        SNOOPDOG_TABLE = {str(i): ch for i, ch in enumerate(BASE64_ALPHABET)}
        SNOOPDOG_TABLE.update({format(i, "08b"): ch for i, ch in enumerate(BASE64_ALPHABET)})

        encoded = "".join(SNOOPDOG_TABLE.get(token, "") for token in snoopdog.strip().split())
        payload = base64.b64decode(encoded + "=" * (-len(encoded) % 4))

        password = payload[:32]
        salt = payload[32:48]
        iv = payload[48:64]
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
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Referer": "https://spencerdevs.xyz/",
        "Origin": "https://spencerdevs.xyz"
    })

    print(f"\n🌐 Processing movie: {movie_id}")
    all_links = []

    for code in SERVER_CODES:
        server_url = f"https://servers.spencerdevs.xyz/{code}/m/{movie_id}"
        print(f"\n🔍 Server {code} → {server_url}")

        try:
            resp = session.get(server_url, timeout=12)
            if resp.status_code != 200:
                print(f"   └─ Failed ({resp.status_code})")
                continue

            data = resp.json()
            if "snoopdog" in data:
                print("   └─ Snoopdog found → Decrypting...")
                m3u8_url = snoopdog_to_url(data["snoopdog"])

                if m3u8_url and m3u8_url.startswith("http"):
                    print(f"   ✅ WORKING LINK: {m3u8_url[:100]}...")
                    all_links.append(m3u8_url)
                else:
                    print("   └─ Decryption produced invalid URL")
        except Exception as e:
            print(f"   └─ Error: {e}")

    if all_links:
        print(f"\n🎉 Found {len(all_links)} streaming links!")
        for i, url in enumerate(all_links, 1):
            print(f"{i:2d}. {url}")
    else:
        print("❌ No links found. Try again later or site changed.")

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