#!/usr/bin/env python3
"""Check a built Skyward image for the TB322FC's recovery partition."""

import struct
import sys

PARTITION_SIZE = 104_857_600


def main(image):
    data = open(image, "rb").read()
    magic = data[:8]
    kernel, ramdisk = struct.unpack_from("<II", data, 8)
    header_size = struct.unpack_from("<I", data, 20)[0]
    version = struct.unpack_from("<I", data, 40)[0]
    print(f"size={len(data)} magic={magic!r} header={version} kernel={kernel} ramdisk={ramdisk} header_size={header_size}")
    assert magic == b"ANDROID!" and version == 4, "not a version 4 boot image"
    assert kernel == 0, "the stock recovery carries no kernel of its own"
    assert len(data) == PARTITION_SIZE, f"the image fills {len(data)} bytes, not the partition"
    assert data[-64:-60] == b"AVBf", "the image does not end in an AVB footer"
    image_size, vbmeta_offset = struct.unpack_from(">QQ", data, len(data) - 64 + 12)
    rollback = struct.unpack_from(">Q", data, vbmeta_offset + 112)[0]
    print(f"vbmeta_offset={vbmeta_offset} image_size={image_size} rollback_index={rollback}")
    assert data[vbmeta_offset:vbmeta_offset + 4] == b"AVB0", "no vbmeta image where the footer points"
    assert rollback >= 1, "a rollback index below the one the bootloader has stored is refused"


if __name__ == "__main__":
    main(sys.argv[1])
