"""Bitstream inspection and pattern search utilities."""


def debug_bitstream(bs, context_bits=64, label=""):
    offset = bs.getOffset()
    bits_str = bs.to_bit_string() if hasattr(bs, "to_bit_string") else str(bs)

    start = max(0, offset - context_bits)
    end = min(len(bits_str), offset + context_bits)

    before = bits_str[start:offset]
    current = bits_str[offset:end]

    byte_pos = offset // 8
    bit_pos = offset % 8

    print(f"\n=== BitStream Debug {label} ===")
    print(f"Offset: {offset} (byte {byte_pos}, bit {bit_pos})")
    print(f"Position marker: ...{before}[HERE]{current}...")
    print(f"Byte context: {bs.data[max(0, byte_pos - 4) : byte_pos + 8].hex()}")
    print("=" * 40)


def search_bits(bs, pattern, context=16):
    bits_str = bs.to_bit_string() if hasattr(bs, "to_bit_string") else str(bs)
    results = []
    start = 0
    while (pos := bits_str.find(pattern, start)) != -1:
        byte_pos = pos // 8
        bit_pos = pos % 8
        before = bits_str[max(0, pos - context) : pos]
        after = bits_str[pos + len(pattern) : pos + len(pattern) + context]
        results.append(
            {
                "offset": pos,
                "byte": byte_pos,
                "bit": bit_pos,
                "context": f"...{before}[{pattern}]{after}...",
            }
        )
        start = pos + 1
    return results


def search_bytes(bs, byte_pattern, context=4):
    data = bs.data
    results = []
    start = 0
    while (pos := data.find(byte_pattern, start)) != -1:
        before = data[max(0, pos - context) : pos].hex()
        after = data[pos + len(byte_pattern) : pos + len(byte_pattern) + context].hex()
        results.append({"offset": pos, "context": f"...{before}[{byte_pattern.hex()}]{after}..."})
        start = pos + 1
    return results


def run_bitstream_searches(bs, args):
    """Execute bit and byte pattern searches on the bitstream if requested via CLI args."""
    if not bs:
        return

    if getattr(args, "search", None):
        results = search_bits(bs, args.search)
        print(f"\n=== Search Results for '{args.search}' ===")
        for r in results:
            print(f"Offset {r['offset']} (byte {r['byte']}, bit {r['bit']}): {r['context']}")
        if not results:
            print("Pattern not found")

    if getattr(args, "search_bytes", None):
        search_byte_pattern = bytes.fromhex(args.search_bytes)
        results = search_bytes(bs, search_byte_pattern)
        print(f"\n=== Search Results for bytes '{search_byte_pattern.hex()}' ===")
        for r in results:
            print(f"Offset {r['offset']}: {r['context']}")
        if not results:
            print("Pattern not found")


_run_bitstream_searches = run_bitstream_searches
