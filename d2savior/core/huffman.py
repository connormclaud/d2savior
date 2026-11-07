from typing import Any

HUFFMAN_TREE = [
    1,
    1,
    1,
    1,
    1,
    ord("w"),
    0,
    0,
    ord("u"),
    0,
    0,
    1,
    1,
    ord("8"),
    0,
    0,
    1,
    ord("y"),
    0,
    0,
    1,
    ord("5"),
    0,
    0,
    1,
    ord("j"),
    0,
    0,
    1,
    0,
    0,
    ord("h"),
    0,
    0,
    1,
    ord("s"),
    0,
    0,
    1,
    1,
    ord("2"),
    0,
    0,
    ord("n"),
    0,
    0,
    ord("x"),
    0,
    0,
    1,
    1,
    1,
    ord("c"),
    0,
    0,
    1,
    ord("k"),
    0,
    0,
    ord("f"),
    0,
    0,
    ord("b"),
    0,
    0,
    1,
    1,
    ord("t"),
    0,
    0,
    ord("m"),
    0,
    0,
    1,
    ord("9"),
    0,
    0,
    ord("7"),
    0,
    0,
    1,
    ord(" "),
    0,
    0,
    1,
    1,
    1,
    1,
    ord("e"),
    0,
    0,
    ord("d"),
    0,
    0,
    ord("p"),
    0,
    0,
    1,
    ord("g"),
    0,
    0,
    1,
    1,
    1,
    ord("z"),
    0,
    0,
    ord("q"),
    0,
    0,
    ord("3"),
    0,
    0,
    1,
    ord("v"),
    0,
    0,
    ord("6"),
    0,
    0,
    1,
    1,
    ord("r"),
    0,
    0,
    ord("l"),
    0,
    0,
    1,
    ord("a"),
    0,
    0,
    1,
    1,
    ord("1"),
    0,
    0,
    1,
    ord("4"),
    0,
    0,
    ord("0"),
    0,
    0,
    1,
    ord("i"),
    0,
    0,
    ord("o"),
    0,
]


class HuffmanDecoder:
    def __init__(self) -> None:
        self._root = self._build_tree()
        self._codes: dict[int, tuple[int, int]] = {}
        self._build_codes(self._root, 0, 0)

    def _build_tree(self) -> dict[str, Any] | None:
        idx = [0]

        def build() -> dict[str, Any] | None:
            if idx[0] >= len(HUFFMAN_TREE):
                return None
            c = HUFFMAN_TREE[idx[0]]
            idx[0] += 1
            if c == 0:
                return None
            node = {"data": 0 if c == 1 else c, "left": None, "right": None}
            node["left"] = build()
            node["right"] = build()
            return node

        return build()

    def _build_codes(self, node: dict[str, Any] | None, bits: int, code: int) -> None:
        if node is None:
            return
        if node["data"] != 0:
            self._codes[node["data"]] = (code, bits)
            return
        self._build_codes(node["left"], bits + 1, code)
        self._build_codes(node["right"], bits + 1, code + (1 << bits))

    def read_char(self, bs: Any) -> int:
        node = self._root
        while node:
            if node["data"] != 0:
                return node["data"]
            bit = bs.read_bits(1)
            node = node["right"] if bit else node["left"]
        return 0

    def write_char(self, bs: Any, ch: int) -> None:
        if ch in self._codes:
            code, bits = self._codes[ch]
            bs.write_bits(bits, code)

    def get_code(self, ch: int) -> tuple[int, int] | None:
        return self._codes.get(ch)

    def get_all_codes(self) -> dict[int, tuple[int, int]]:
        return self._codes.copy()


DEFAULT_HUFFMAN = HuffmanDecoder()
