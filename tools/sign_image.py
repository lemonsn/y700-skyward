#!/usr/bin/env python3
"""Re-sign the AVB footer of an image skyward-pack built.

skyward-pack ends its image in an unsigned vbmeta image (algorithm NONE),
which only an unlocked bootloader boots. The TB322FC's bootloader is locked
and verifies the recovery chain against the AOSP test key, which is what the
TWRP image booting on it proves, so the footer is replaced with one signed
by the same key.
"""

import argparse
import os
import shutil
import struct
import subprocess
import sys
import tempfile

FOOTER_LEN = 64


def original_size(image):
    footer = image[-FOOTER_LEN:]
    if footer[:4] != b"AVBf":
        sys.exit("the image does not end in an AVB footer")
    return struct.unpack(">Q", footer[12:20])[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--avbtool", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--partition-size", type=int, required=True)
    parser.add_argument("--partition-name", default="recovery")
    parser.add_argument("--salt", required=True)
    parser.add_argument("--rollback-index", type=int, default=1)
    args = parser.parse_args()

    with open(args.image, "rb") as f:
        data = f.read()
    size = original_size(data)
    if size > len(data) or size % 4096:
        sys.exit(f"implausible original image size {size}")
    # avbtool's verify_image looks the image up by partition name beside it.
    workdir = tempfile.mkdtemp()
    plain = os.path.join(workdir, f"{args.partition_name}.img")
    with open(plain, "wb") as f:
        f.write(data[:size])
    try:
        subprocess.run([
            sys.executable, args.avbtool, "add_hash_footer",
            "--image", plain,
            "--partition_size", str(args.partition_size),
            "--partition_name", args.partition_name,
            "--algorithm", "SHA256_RSA4096",
            "--key", args.key,
            "--salt", args.salt,
            "--rollback_index", str(args.rollback_index),
        ], check=True)
        subprocess.run([
            sys.executable, args.avbtool, "verify_image", "--image", plain,
        ], check=True)
        os.replace(plain, args.image)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
