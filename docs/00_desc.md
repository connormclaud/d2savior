# 游戏版本

## Classic Diablo II (1.x)

- 1.09: 存档版本 < 0x61
- 1.10: 存档版本 < 0x61

## D2R (Diablo II: Resurrected) >= 0x61

- 2.x: 存档版本 0x61 ~ 0x63 (D2R 基础版)
  - 2.4: 存档版本 0x62
  - 2.5: 存档版本 0x63
- 3.x: 存档版本 0x69 (D2R 资料片 - 术士君临，新增术士职业)

## 版本判断

```python
def is_d2r(version: int) -> bool:
    return version >= 0x61
```

- `version < 0x61`: Classic Diablo II
- `0x61 <= version < 0x69`: D2R 基础版 (2.x)
- `version >= 0x69`: D2R 资料片 - 术士君临 (3.x)
