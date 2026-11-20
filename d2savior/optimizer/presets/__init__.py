"""Built-in and user TOML build presets with inheritance (`extends`) and CLI merging (`+` / `,`)."""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import tomlkit
from tomlkit.exceptions import TOMLKitError

from d2savior.config import get_presets_dir
from d2savior.core.enums import CharClass
from d2savior.optimizer.native import SearchModeStr

BUILTIN_PRESETS_DIR: Path = Path(__file__).resolve().parent

VALID_MODES: tuple[SearchModeStr, ...] = ("power", "mf", "max-res", "leveling", "leveling-res")
VALID_CLASSES: frozenset[str] = frozenset({"sorceress", "paladin"})
VALID_STRATEGIES: frozenset[str] = frozenset({"leveling-probe"})

_INT_CONSTRAINT_KEYS: tuple[str, ...] = (
    "min_fcr",
    "min_fhr",
    "min_fr",
    "min_lr",
    "min_cr",
    "min_pr",
    "min_frw",
    "min_ias",
    "min_cb",
    "min_ll",
    "min_pdr",
    "min_mf",
)
_BOOL_CONSTRAINT_KEYS: tuple[str, ...] = ("allow_mf", "require_cbf")
_META_KEYS: frozenset[str] = frozenset({"title", "class", "strategy", "extends", "presets", "mode"})
_ALLOWED_KEYS: frozenset[str] = (
    _META_KEYS | frozenset(_INT_CONSTRAINT_KEYS) | frozenset(_BOOL_CONSTRAINT_KEYS) | VALID_CLASSES
)


@dataclass(frozen=True, slots=True)
class ConstraintOverrides:
    """Optional CLI or programmatic overrides layered on top of a resolved preset."""

    mode: SearchModeStr | None = None
    allow_mf: bool | None = None
    min_fcr: int | None = None
    min_fhr: int | None = None
    min_fr: int | None = None
    min_lr: int | None = None
    min_cr: int | None = None
    min_pr: int | None = None
    require_cbf: bool | None = None
    min_frw: int | None = None
    min_ias: int | None = None
    min_cb: int | None = None
    min_ll: int | None = None
    min_pdr: int | None = None
    min_mf: int | None = None

    def summary_tags(self) -> list[str]:
        """Return short human-readable tags for active overrides (for report titles)."""
        tags: list[str] = []
        if self.mode is not None:
            tags.append(f"mode={self.mode}")
        if self.allow_mf is False:
            tags.append("no-mf")
        if self.require_cbf is True:
            tags.append("CBF")
        elif self.require_cbf is False:
            tags.append("no-CBF")
        for key, label in (
            ("min_fcr", "FCR"),
            ("min_fhr", "FHR"),
            ("min_fr", "FR"),
            ("min_lr", "LR"),
            ("min_cr", "CR"),
            ("min_pr", "PR"),
            ("min_frw", "FRW"),
            ("min_ias", "IAS"),
            ("min_cb", "CB"),
            ("min_ll", "LL"),
            ("min_pdr", "PDR"),
            ("min_mf", "MF"),
        ):
            val = getattr(self, key)
            if val is not None:
                tags.append(f"{label}>={val}")
        return tags


@dataclass(frozen=True, slots=True)
class ResolvedPreset:
    """Concrete, validated build preset ready to construct `BuildConstraints`."""

    name: str
    title: str | None
    char_class: str | None
    strategy: str | None
    mode: SearchModeStr
    allow_mf: bool = True
    min_fcr: int = 0
    min_fhr: int = 0
    min_fr: int = 0
    min_lr: int = 0
    min_cr: int = 0
    min_pr: int = 0
    require_cbf: bool = False
    min_frw: int = 0
    min_ias: int = 0
    min_cb: int = 0
    min_ll: int = 0
    min_pdr: int = 0
    min_mf: int = 0

    def apply_overrides(self, overrides: ConstraintOverrides | None) -> ResolvedPreset:
        """Return a copy with any non-None override fields applied."""
        if overrides is None:
            return self
        updates: dict[str, Any] = {}
        for key in ("mode", *_BOOL_CONSTRAINT_KEYS, *_INT_CONSTRAINT_KEYS):
            val = getattr(overrides, key)
            if val is not None:
                updates[key] = val
        if not updates:
            return self
        return replace(self, **updates)

    def constraint_kwargs(self) -> dict[str, Any]:
        """Return keyword arguments matching `CharacterBaseline.build_constraints`."""
        return {
            "mode": self.mode,
            "allow_mf": self.allow_mf,
            "min_fcr": self.min_fcr,
            "min_fhr": self.min_fhr,
            "min_fr": self.min_fr,
            "min_lr": self.min_lr,
            "min_cr": self.min_cr,
            "min_pr": self.min_pr,
            "require_cbf": self.require_cbf,
            "min_frw": self.min_frw,
            "min_ias": self.min_ias,
            "min_cb": self.min_cb,
            "min_ll": self.min_ll,
            "min_pdr": self.min_pdr,
            "min_mf": self.min_mf,
        }


@dataclass(frozen=True, slots=True)
class PresetEntry:
    """Metadata for listing available built-in and user presets."""

    name: str
    source: str
    char_class: str | None
    path: Path


def _normalize_class(char_class: CharClass | str) -> str:
    if isinstance(char_class, CharClass):
        name = char_class.display_name.lower()
    else:
        name = char_class.strip().lower()
    if name not in VALID_CLASSES:
        raise ValueError(
            f"Unsupported optimizer class '{char_class}'; expected one of: {', '.join(sorted(VALID_CLASSES))}"
        )
    return name


def load_preset_catalog(user_dir: Path | None = None) -> dict[str, tuple[Path, str]]:
    """Discover built-in and user `<name>.toml` presets (user files override built-ins)."""
    catalog: dict[str, tuple[Path, str]] = {}
    if BUILTIN_PRESETS_DIR.is_dir():
        for path in sorted(BUILTIN_PRESETS_DIR.glob("*.toml")):
            catalog[path.stem.lower()] = (path, "built-in")
    eff_user_dir = user_dir if user_dir is not None else get_presets_dir()
    if eff_user_dir.is_dir():
        for path in sorted(eff_user_dir.glob("*.toml")):
            catalog[path.stem.lower()] = (path, "user")
    return catalog


def list_presets(user_dir: Path | None = None) -> list[PresetEntry]:
    """Return sorted metadata entries for all discoverable presets."""
    entries: list[PresetEntry] = []
    for name, (path, source) in sorted(load_preset_catalog(user_dir).items()):
        char_class: str | None = None
        try:
            raw = _read_toml_file(path)
            raw_cls = raw.get("class")
            if isinstance(raw_cls, str):
                char_class = raw_cls.lower()
        except ValueError:
            char_class = None
        entries.append(PresetEntry(name=name, source=source, char_class=char_class, path=path))
    return entries


def _read_toml_file(path: Path) -> dict[str, Any]:
    try:
        doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    except (OSError, TOMLKitError) as exc:
        raise ValueError(f"Failed to parse preset '{path}': {exc}") from exc
    return doc.unwrap()


def _validate_enum_str(
    data: dict[str, Any], key: str, allowed: tuple[str, ...] | frozenset[str], source_label: str
) -> None:
    if key not in data:
        return
    val = data[key]
    if not isinstance(val, str) or val.lower() not in allowed:
        raise ValueError(
            f"Invalid {key} '{val}' in preset '{source_label}'; "
            f"expected one of: {', '.join(sorted(allowed))}"
        )


def _validate_section(data: dict[str, Any], source_label: str) -> None:
    unknown = sorted(set(data) - _ALLOWED_KEYS)
    if unknown:
        raise ValueError(f"Unknown key(s) in preset '{source_label}': {', '.join(unknown)}")
    _validate_enum_str(data, "class", VALID_CLASSES, source_label)
    _validate_enum_str(data, "mode", VALID_MODES, source_label)
    _validate_enum_str(data, "strategy", VALID_STRATEGIES, source_label)
    if "title" in data and not isinstance(data["title"], str):
        raise ValueError(f"Invalid title in preset '{source_label}': expected string")
    for list_key in ("extends", "presets"):
        if list_key in data:
            val = data[list_key]
            if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                raise ValueError(
                    f"Invalid '{list_key}' in preset '{source_label}': expected list of strings"
                )
    for key in _BOOL_CONSTRAINT_KEYS:
        if key in data and not isinstance(data[key], bool):
            raise ValueError(f"Invalid '{key}' in preset '{source_label}': expected boolean")
    for key in _INT_CONSTRAINT_KEYS:
        if key in data and (isinstance(data[key], bool) or not isinstance(data[key], int)):
            raise ValueError(f"Invalid '{key}' in preset '{source_label}': expected integer")


def _extract_class_doc(raw: dict[str, Any], class_name: str, source_label: str) -> dict[str, Any]:
    _validate_section(raw, source_label)
    merged: dict[str, Any] = {k: v for k, v in raw.items() if k not in VALID_CLASSES}
    class_overlay = raw.get(class_name)
    if class_overlay is not None:
        if not isinstance(class_overlay, dict):
            raise ValueError(f"Invalid [{class_name}] section in preset '{source_label}'")
        _validate_section(class_overlay, f"{source_label}[{class_name}]")
        merged.update(class_overlay)
    return merged


def _check_class_compatibility(
    doc: dict[str, Any], preset_name: str, class_name: str, char_name: str | None = None
) -> None:
    req_cls = doc.get("class")
    if isinstance(req_cls, str) and req_cls.lower() != class_name:
        target = f"'{char_name}' is {class_name.title()}" if char_name else f"class is {class_name}"
        raise ValueError(
            f"Build preset '{preset_name}' is only supported for {req_cls.title()}; {target}"
        )


def _resolve_single_dict(
    name: str,
    class_name: str,
    catalog: dict[str, tuple[Path, str]],
    *,
    stack: tuple[str, ...] = (),
    char_name: str | None = None,
) -> dict[str, Any]:
    key = name.strip().lower()
    if key in stack:
        cycle = " -> ".join((*stack, key))
        raise ValueError(f"Circular preset inheritance detected: {cycle}")
    entry = catalog.get(key)
    if entry is None:
        valid = ", ".join(sorted(catalog))
        raise ValueError(f"Unknown build preset '{name}'; available presets: {valid}")
    path, _ = entry
    raw = _read_toml_file(path)
    doc = _extract_class_doc(raw, class_name, key)
    _check_class_compatibility(doc, key, class_name, char_name=char_name)

    extends = doc.get("extends") or []
    if not extends:
        return doc

    merged: dict[str, Any] = {}
    for parent in extends:
        parent_doc = _resolve_single_dict(
            parent, class_name, catalog, stack=(*stack, key), char_name=char_name
        )
        if parent_doc.get("presets"):
            raise ValueError(f"Preset '{key}' cannot extend group preset '{parent}'")
        merged.update(parent_doc)
    for k, v in doc.items():
        if k != "extends":
            merged[k] = v
    return merged


def _dict_to_resolved(name: str, doc: dict[str, Any], class_name: str) -> ResolvedPreset:
    default_mode: SearchModeStr = "power" if class_name == "sorceress" else "leveling-res"
    mode_raw = doc.get("mode")
    mode = cast(SearchModeStr, mode_raw.lower() if isinstance(mode_raw, str) else default_mode)
    cls_raw = doc.get("class")
    strat_raw = doc.get("strategy")
    return ResolvedPreset(
        name=name,
        title=doc.get("title"),
        char_class=cls_raw.lower() if isinstance(cls_raw, str) else None,
        strategy=strat_raw.lower() if isinstance(strat_raw, str) else None,
        mode=mode,
        allow_mf=bool(doc.get("allow_mf", True)),
        min_fcr=int(doc.get("min_fcr", 0)),
        min_fhr=int(doc.get("min_fhr", 0)),
        min_fr=int(doc.get("min_fr", 0)),
        min_lr=int(doc.get("min_lr", 0)),
        min_cr=int(doc.get("min_cr", 0)),
        min_pr=int(doc.get("min_pr", 0)),
        require_cbf=bool(doc.get("require_cbf", False)),
        min_frw=int(doc.get("min_frw", 0)),
        min_ias=int(doc.get("min_ias", 0)),
        min_cb=int(doc.get("min_cb", 0)),
        min_ll=int(doc.get("min_ll", 0)),
        min_pdr=int(doc.get("min_pdr", 0)),
        min_mf=int(doc.get("min_mf", 0)),
    )


def _expand_term(
    term: str,
    class_name: str,
    catalog: dict[str, tuple[Path, str]],
    *,
    stack: tuple[str, ...] = (),
    char_name: str | None = None,
) -> list[ResolvedPreset]:
    parts = [p.strip() for p in term.split("+")]
    if any(not p for p in parts):
        raise ValueError(f"Invalid build preset expression '{term}'")
    if len(parts) > 1:
        merged: dict[str, Any] = {}
        extra_labels: list[str] = []
        for idx, part in enumerate(parts):
            p_doc = _resolve_single_dict(part, class_name, catalog, char_name=char_name)
            if p_doc.get("presets"):
                raise ValueError(f"Cannot merge group preset '{part}' in '{term}'")
            if idx > 0 and "title" not in p_doc:
                extra_labels.append(part.lower())
            merged.update(p_doc)
        if extra_labels and isinstance(merged.get("title"), str):
            merged["title"] = f"{merged['title']} (+{' +'.join(extra_labels)})"
        merged_name = "+".join(p.lower() for p in parts)
        return [_dict_to_resolved(merged_name, merged, class_name)]

    single_name = parts[0].lower()
    if single_name in stack:
        cycle = " -> ".join((*stack, single_name))
        raise ValueError(f"Circular preset group detected: {cycle}")
    doc = _resolve_single_dict(single_name, class_name, catalog, char_name=char_name)
    group = doc.get("presets")
    if group:
        expanded: list[ResolvedPreset] = []
        for member in group:
            expanded.extend(
                _expand_term(
                    member,
                    class_name,
                    catalog,
                    stack=(*stack, single_name),
                    char_name=char_name,
                )
            )
        return expanded
    return [_dict_to_resolved(single_name, doc, class_name)]


def resolve_build_expr(
    expr: str,
    char_class: CharClass | str,
    *,
    overrides: ConstraintOverrides | None = None,
    user_dir: Path | None = None,
    char_name: str | None = None,
) -> list[ResolvedPreset]:
    """Resolve a `-b` expression (`name`, `a+b`, `a,b`) into concrete presets with overrides."""
    class_name = _normalize_class(char_class)
    catalog = load_preset_catalog(user_dir=user_dir)
    terms = [t.strip() for t in expr.split(",")]
    if not terms or any(not t for t in terms):
        raise ValueError(f"Invalid build preset expression '{expr}'")
    resolved: list[ResolvedPreset] = []
    for term in terms:
        for preset in _expand_term(term, class_name, catalog, char_name=char_name):
            resolved.append(preset.apply_overrides(overrides))
    return resolved


__all__ = [
    "BUILTIN_PRESETS_DIR",
    "VALID_CLASSES",
    "VALID_MODES",
    "VALID_STRATEGIES",
    "ConstraintOverrides",
    "PresetEntry",
    "ResolvedPreset",
    "list_presets",
    "load_preset_catalog",
    "resolve_build_expr",
]
