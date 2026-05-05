# 数据文件与版本加载机制

## 1. 数据文件组织结构

```
d2savior/data/
├── 0x63/                      # 0x63 版本专用数据
│   ├── Armor.txt              # 护甲定义
│   ├── Weapons.txt            # 武器定义
│   ├── Misc.txt               # 杂项物品定义
│   ├── ItemStatCost.txt       # 属性存储参数
│   ├── itemtypes.txt          # 物品类型层次
│   ├── itemdata.txt           # 物品元数据 (iPadBits等)
│   └── property.txt           # 属性编码元数据
│
├── 0x69/                      # 0x69 版本专用数据
│   ├── Armor.txt
│   ├── Weapons.txt
│   ├── Misc.txt
│   ├── ItemStatCost.txt
│   ├── itemtypes.txt
│   ├── itemdata.txt
│   ├── property.txt
│   ├── Properties.txt         # 属性定义
│   ├── magicprefix.txt        # 魔法前缀
│   ├── magicsuffix.txt        # 魔法后缀
│   ├── uniqueitems.txt        # 暗金物品
│   ├── skills.txt             # 技能定义
│   ├── runewords.txt          # 符文之语
│   └── local/                 # 本地化数据
│       └── item-runes.json
│
├── Armor.txt                  # 根目录文件（回退用）
├── Weapons.txt
├── ItemStatCost.txt
├── ... (其他通用文件)
└── local/
    └── item-modifiers.json    # 属性描述模板
```

## 2. 版本加载流程

### 2.1 入口函数

```python
def init_d2data(data_dir: str) -> bool:
    """初始化数据，加载所有版本"""
    _g_d2data_manager = D2DataManager()
    result = _g_d2data_manager.load_all_versions(data_dir)
    return result
```

### 2.2 加载所有版本

```python
def load_all_versions(self, base_data_dir: str) -> bool:
    # 1. 尝试加载 0x63 版本
    v63_dir = os.path.join(base_data_dir, '0x63')
    if os.path.exists(v63_dir):
        self.load_version(0x63, v63_dir, base_data_dir)  # 有版本目录
    else:
        self.load_version(0x63, base_data_dir)           # 无版本目录，从根目录加载
    
    # 2. 尝试加载 0x69 版本
    v69_dir = os.path.join(base_data_dir, '0x69')
    if os.path.exists(v69_dir):
        self.load_version(0x69, v69_dir, base_data_dir)
    
    return success
```

### 2.3 文件路径解析（回退机制）

```python
def _resolve_path(self, filename: str, data_dir: str, fallback_dir: str = None) -> str:
    """解析文件路径，优先从版本目录加载，缺失时回退到根目录"""
    path = os.path.join(data_dir, filename)
    if os.path.exists(path):
        return path                    # 版本目录中存在
    if fallback_dir:
        fallback_path = os.path.join(fallback_dir, filename)
        if os.path.exists(fallback_path):
            return fallback_path       # 回退到根目录
    return path                        # 返回路径（可能不存在）
```

### 2.4 加载流程图

```
init_d2data(data_dir)
    │
    └─► D2DataManager.load_all_versions()
            │
            ├─► load_version(0x63, data/0x63/, data/)
            │       │
            │       └─► D2DataLoader.load_version_data(data/0x63/, fallback=data/)
            │               │
            │               ├─► _resolve_path('Armor.txt')      → 0x63/Armor.txt 或 data/Armor.txt
            │               ├─► _resolve_path('Weapons.txt')    → 0x63/Weapons.txt 或 data/Weapons.txt
            │               ├─► _resolve_path('Properties.txt') → data/Properties.txt (0x63目录无此文件)
            │               ├─► _resolve_path('itemdata.txt')   → 0x63/itemdata.txt
            │               └─► ... (其他文件)
            │
            └─► load_version(0x69, data/0x69/, data/)
                    │
                    └─► D2DataLoader.load_version_data(data/0x69/, fallback=data/)
                            │
                            ├─► _resolve_path('Armor.txt')      → 0x69/Armor.txt
                            ├─► _resolve_path('Properties.txt') → 0x69/Properties.txt
                            └─► ... (其他文件)
```

## 3. 版本数据结构

### 3.1 VersionData 类

```python
@dataclass
class VersionData:
    """存储单个版本的所有数据"""
    stats: Dict[int, StatInfo]              # stat_id → StatInfo
    stats_by_name: Dict[str, StatInfo]      # stat_name → StatInfo
    properties: Dict[int, PropertyInfo]     # prop_id → PropertyInfo
    properties_by_code: Dict[str, PropertyInfo]  # prop_code → PropertyInfo
    items: Dict[str, ItemTypeInfo]          # item_code → ItemTypeInfo
    magic_prefixes: Dict[int, MagicAffixInfo]
    magic_suffixes: Dict[int, MagicAffixInfo]
    unique_items: Dict[int, UniqueItemInfo]
    runewords: Dict[int, RuneWordInfo]
    skills: Dict[int, str]
    type_ancestors: Dict[str, Set[str]]     # 类型 → 祖先类型集合
    type_descendants: Dict[str, Set[str]]   # 类型 → 后代类型集合
    item_manager: object                    # 物品元数据管理器
    prop_meta: Dict                         # 属性编码元数据
    stat_cost: Dict                         # 属性成本元数据
```

### 3.2 D2DataManager 类

```python
class D2DataManager:
    version_data: Dict[int, VersionData]    # 版本号 → 版本数据
    default_version: int = 0x63             # 默认版本
```

## 4. 数据访问接口

### 4.1 基本访问

```python
manager = get_d2data_manager()

# 获取指定版本的 stat 信息
stat_info = manager.get_stat(stat_id=0, version=0x63)

# 获取指定版本的物品信息
item_info = manager.get_item(code='cap ', version=0x69)

# 获取指定版本的属性信息
prop_info = manager.get_property(prop_id=151, version=0x69)
```

### 4.2 版本回退规则

```python
def get_version_data(self, version: int) -> Optional[VersionData]:
    if version in self.version_data:
        return self.version_data[version]
    # 请求的版本不存在，返回默认版本
    return self.version_data.get(self.default_version)
```

## 5. 物品元数据访问

### 5.1 get_item_meta

```python
def get_item_meta(type_id: bytes, version: int = 0) -> Optional[ItemMetaData]:
    # 1. 优先从 D2DataManager 获取版本化数据
    d2data_manager = get_d2data_manager()
    if d2data_manager is not None:
        meta = d2data_manager.get_item_meta(type_id, version)
        if meta is not None:
            return meta
    
    # 2. 回退到全局 _g_item_manager（向后兼容）
    if _g_item_manager is not None:
        return _g_item_manager.get_item(type_id, version)
    
    return None
```

### 5.2 get_property_meta

```python
def get_property_meta(prop_id: int, version: int) -> Optional[PropertyMetaDataItem]:
    d2data_manager = get_d2data_manager()
    if d2data_manager is not None:
        result = d2data_manager.get_property_meta(prop_id, version)
        if result is not None:
            return result
    
    # 回退到全局 _g_properties
    if _g_properties is not None and prop_id in _g_properties:
        return _g_properties[prop_id].find_data(version)
    
    return None
```

## 6. 版本间差异处理

### 6.1 属性差异

| 属性ID | 属性名称 | 0x63 bits_sum | 0x69 bits_sum |
|--------|----------|---------------|---------------|
| 151 | item_aura | 14 | 5 |

解析时根据存档版本选择对应定义：

```python
prop_meta = get_property_meta(prop_id=151, version=dwVersion)
bits_sum = prop_meta.bits_sum  # 0x63→14, 0x69→5
```

### 6.2 物品差异

| 物品类型 | 0x63 iPadBits | 0x69 iPadBits |
|----------|---------------|---------------|
| vip | 1 | 0 |
| bks | 1 | 0 |

```python
meta = get_item_meta(b'vip ', version=dwVersion)
ipad_bits = meta.ipad_bits  # 0x63→1, 0x69→0
```

## 7. 文件覆盖关系

### 7.1 0x63 版本

| 文件 | 来源 | 说明 |
|------|------|------|
| Armor.txt | 0x63/ | 版本专用 |
| Weapons.txt | 0x63/ | 版本专用 |
| ItemStatCost.txt | 0x63/ | 版本专用 |
| itemdata.txt | 0x63/ | 版本专用 |
| property.txt | 0x63/ | 版本专用 |
| Properties.txt | data/ | 回退到根目录 |
| magicprefix.txt | data/ | 回退到根目录 |
| magicsuffix.txt | data/ | 回退到根目录 |
| uniqueitems.txt | data/ | 回退到根目录 |
| skills.txt | data/ | 回退到根目录 |

### 7.2 0x69 版本

| 文件 | 来源 | 说明 |
|------|------|------|
| Armor.txt | 0x69/ | 版本专用 |
| Weapons.txt | 0x69/ | 版本专用 |
| ItemStatCost.txt | 0x69/ | 版本专用 |
| itemdata.txt | 0x69/ | 版本专用 |
| property.txt | 0x69/ | 版本专用 |
| Properties.txt | 0x69/ | 版本专用 |
| magicprefix.txt | 0x69/ | 版本专用 |
| magicsuffix.txt | 0x69/ | 版本专用 |
| uniqueitems.txt | 0x69/ | 版本专用 |
| skills.txt | 0x69/ | 版本专用 |

## 8. 向后兼容

### 8.1 D2DataWrapper

提供旧接口的包装器，保持向后兼容：

```python
class D2DataWrapper:
    def __init__(self, manager: D2DataManager):
        self.manager = manager
    
    def get_stat(self, stat_id: int) -> Optional[StatInfo]:
        return self.manager.get_stat(stat_id)
    
    # ... 其他方法代理到 manager
```

### 8.2 全局访问函数

```python
def get_d2data() -> Optional[D2DataWrapper]:
    """获取数据加载器（旧接口）"""
    return _g_d2data_wrapper

def get_d2data_manager() -> Optional[D2DataManager]:
    """获取数据管理器（新接口）"""
    return _g_d2data_manager
```
