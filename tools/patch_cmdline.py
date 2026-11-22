#!/usr/bin/env python3
"""Append arguments to a version 4 boot image's kernel command line."""

import sys

CMDLINE_AT = 44
CMDLINE_LEN = 1536


def main(image, *args):
    with open(image, "rb") as f:
        data = bytearray(f.read())
    if data[:8] != b"ANDROID!":
        sys.exit("not a boot image")
    current = bytes(data[CMDLINE_AT:CMDLINE_AT + CMDLINE_LEN]).split(b"\0")[0].decode()
    words = current.split()
    for arg in args:
        if arg not in words:
            words.append(arg)
    line = " ".join(words)
    raw = line.encode()
    if len(raw) >= CMDLINE_LEN:
        sys.exit("the command line does not fit")
    data[CMDLINE_AT:CMDLINE_AT + CMDLINE_LEN] = raw.ljust(CMDLINE_LEN, b"\0")
    with open(image, "wb") as f:
        f.write(data)
    print(line)


if __name__ == "__main__":
    main(*sys.argv[1:])
