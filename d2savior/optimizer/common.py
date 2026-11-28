"""Shared optimizer baselines, class validators, level requirements, and pool traversal."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import cast

from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass, EquipSlot, ItemLocation, StoredIn
from d2savior.core.item import D2Item
from d2savior.core.item_name import LongName
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import STASH_TAB_TYPE_ADVANCED, SharedStash
from d2savior.core.stats import collect_item_properties
from d2savior.optimizer.native import (
    BuildConstraints,
    CharacterStats,
    OffenseProfileStr,
    SearchModeStr,
    SkillModel,
    TargetProfile,
    TargetTypeStr,
)

SUPPORTED_OPTIMIZER_CLASSES: tuple[CharClass, ...] = (CharClass.SORCERESS, CharClass.PALADIN)

KEEP_GEAR_GROUPS: frozendict[str, frozenset[str]] = frozendict(
    {
        "weapon": frozenset({"weapon", "weapon2h", "shield"}),
        "jewelry": frozenset({"amulet", "ring"}),
        "armor": frozenset({"helm", "armor", "belt", "gloves", "boots"}),
    }
)
KEEP_GEAR_SLOTS: frozendict[str, frozenset[str]] = frozendict(
    {
        "helm": frozenset({"helm"}),
        "chest": frozenset({"armor"}),
        "belt": frozenset({"belt"}),
        "gloves": frozenset({"gloves"}),
        "boots": frozenset({"boots"}),
        "amulet": frozenset({"amulet"}),
        "ring": frozenset({"ring"}),
        "shield": frozenset({"shield"}),
    }
)
_KEEP_GEAR_ALIASES: frozendict[str, str] = frozendict(
    {
        "body": "chest",
        "helmet": "helm",
        "rings": "ring",
    }
)
ALL_GEAR_SLOTS: frozenset[str] = frozenset().union(*KEEP_GEAR_GROUPS.values())


def parse_keep_gear(value: bool | str | None) -> frozenset[str]:
    """Parse a --keep-gear specification into the set of kept optimizer slot names.

    Accepts:
      - ``None`` / ``False``: no slots kept.
      - ``True`` / ``"all"``: all active gear slots kept.
      - Groups (``"weapon"``, ``"jewelry"``, ``"armor"``), individual slots
        (``"helm"``, ``"chest"``/``"body"``, ``"belt"``, ``"gloves"``, ``"boots"``,
        ``"amulet"``, ``"ring"``/``"rings"``, ``"shield"``), or ``'+'`` combinations
        (e.g. ``"weapon+helm+boots"``).
    """
    if value is None or value is False:
        return frozenset()
    if value is True:
        return ALL_GEAR_SLOTS
    raw = value.strip().lower()
    valid = ", ".join(("all", *KEEP_GEAR_GROUPS, *KEEP_GEAR_SLOTS))
    if not raw:
        raise ValueError(
            f"Empty --keep-gear value; expected one or more of: {valid} (join with '+')"
        )
    slots: set[str] = set()
    for part in raw.split("+"):
        token = part.strip()
        if token == "all":
            slots.update(ALL_GEAR_SLOTS)
        elif token in KEEP_GEAR_GROUPS:
            slots.update(KEEP_GEAR_GROUPS[token])
        else:
            canonical = _KEEP_GEAR_ALIASES.get(token, token)
            if canonical in KEEP_GEAR_SLOTS:
                slots.update(KEEP_GEAR_SLOTS[canonical])
            else:
                raise ValueError(
                    f"Invalid --keep-gear group or slot '{token}'; expected one or more of: {valid} (join with '+')"
                )
    return frozenset(slots)


def resolve_fixed_gear(value: bool | str | None) -> tuple[bool, tuple[str, ...]]:
    """Return ``(fixed_all, fixed_slots)`` for ``CharacterBaseline`` / ``BuildConstraints``."""
    kept = parse_keep_gear(value)
    if kept == ALL_GEAR_SLOTS:
        return True, ()
    return False, tuple(sorted(kept))


_SWAP_SLOTS: tuple[EquipSlot, EquipSlot] = (EquipSlot.WEAPON_II, EquipSlot.SHIELD_II)
_SKILL_BATTLE_ORDERS = 149


def active_skill_bindings(char_data: D2SStruct) -> tuple[int, int]:
    """Return `(left_skill, right_skill)` for the character's currently active weapon set."""
    if char_data.weapon_set == 0:
        return char_data.left_skill_1, char_data.right_skill_1
    return char_data.left_skill_2, char_data.right_skill_2


def inactive_weapon_slots(char_data: D2SStruct) -> tuple[EquipSlot, EquipSlot]:
    """Return the inactive (swap) weapon/shield EquipSlots for the character's active weapon set."""
    if char_data.weapon_set == 0:
        return (EquipSlot.WEAPON_II, EquipSlot.SHIELD_II)
    return (EquipSlot.WEAPON_I, EquipSlot.SHIELD_I)


def _validate_char_class(char_data: D2SStruct, allowed: tuple[CharClass, ...], label: str) -> None:
    if char_data.char_class not in allowed:
        actual = CharClass(char_data.char_class).display_name
        raise ValueError(f"Character '{char_data.get_char_name()}' is {actual}, expected {label}")


def validate_sorceress(char_data: D2SStruct) -> None:
    """Validate that a parsed character is a Sorceress."""
    _validate_char_class(char_data, (CharClass.SORCERESS,), "Sorceress")


def validate_paladin(char_data: D2SStruct) -> None:
    """Validate that a parsed character is a Paladin."""
    _validate_char_class(char_data, (CharClass.PALADIN,), "Paladin")


def supported_classes_label(classes: Sequence[CharClass] = SUPPORTED_OPTIMIZER_CLASSES) -> str:
    """Format a human-readable label for a sequence of character classes."""
    names = [c.display_name for c in classes]
    if len(names) <= 1:
        return names[0] if names else "supported"
    if len(names) == 2:
        return f"{names[0]} or {names[1]}"
    return f"{', '.join(names[:-1])}, or {names[-1]}"


def validate_supported_class(char_data: D2SStruct) -> None:
    """Validate that a parsed character belongs to a supported optimizer class."""
    _validate_char_class(char_data, SUPPORTED_OPTIMIZER_CLASSES, supported_classes_label())


def _long_name_levelreq(
    long_name: LongName, resolver: GameDataResolver, *, is_crafted: bool
) -> int:
    reqs: list[int] = []
    for pid in (long_name.pref_1, long_name.pref_2, long_name.pref_3):
        if pid and (pref_info := resolver.get_magic_prefix(pid)):
            reqs.append(pref_info.levelreq)
    for sid in (long_name.suff_1, long_name.suff_2, long_name.suff_3):
        if sid and (suff_info := resolver.get_magic_suffix(sid)):
            reqs.append(suff_info.levelreq)
    if not reqs:
        return 0
    max_req = max(reqs)
    return max_req + 10 + 3 * len(reqs) if is_crafted else max_req


def item_levelreq(item: D2Item, resolver: GameDataResolver) -> int:
    """Compute effective level requirement across base, unique/set, affixes, runewords, and sockets."""
    info = resolver.data.get_item(item.code_str.strip().lower())
    req = info.levelreq if info else 0

    ext = item.item_info.ext_info if item.item_info else None
    if ext is not None:
        if ext.unique_id is not None and (uniq_info := resolver.get_unique_item(ext.unique_id)):
            req = max(req, uniq_info.levelreq)
        if ext.set_id is not None and (set_info := resolver.get_set_item(ext.set_id)):
            req = max(req, set_info.levelreq)
        if ext.magic_prefix and (pref_info := resolver.get_magic_prefix(ext.magic_prefix)):
            req = max(req, pref_info.levelreq)
        if ext.magic_suffix and (suff_info := resolver.get_magic_suffix(ext.magic_suffix)):
            req = max(req, suff_info.levelreq)
        if ext.rare_name is not None:
            req = max(req, _long_name_levelreq(ext.rare_name, resolver, is_crafted=False))
        if ext.craft_name is not None:
            req = max(req, _long_name_levelreq(ext.craft_name, resolver, is_crafted=True))
        if (
            item.is_runeword
            and not item.gem_items
            and ext.rune_id
            and (rw_info := resolver.get_runeword(ext.rune_id))
        ):
            for code in rw_info.rune_codes:
                if rune_item := resolver.data.get_item(code.strip().lower()):
                    req = max(req, rune_item.levelreq)

    for gem in item.gem_items:
        req = max(req, item_levelreq(gem, resolver))
    return req


def item_cta_bo(item: D2Item, resolver: GameDataResolver, version: int) -> int | None:
    """Return `bo_oskill + all_skills` if `item` grants Battle Orders (pid 97), else None."""
    bo_oskill: int | None = None
    all_skills = 0
    for pid, val, params in collect_item_properties(item, resolver=resolver, version=version):
        if pid == 97 and len(params) >= 2 and params[0] == _SKILL_BATTLE_ORDERS:
            bo_oskill = (bo_oskill or 0) + params[1]
        elif pid == 127:
            all_skills += params[0] if params else val
    return bo_oskill + all_skills if bo_oskill is not None else None


def format_item_location(
    char_name: str,
    item: D2Item,
    swap_slots: tuple[EquipSlot, EquipSlot] = _SWAP_SLOTS,
) -> str:
    """Format a character item's human-readable location label."""
    if item.location == ItemLocation.EQUIPPED:
        if item.position in swap_slots:
            return f"{char_name} Swap"
        return f"{char_name} Equipped"
    if item.stored_in == StoredIn.STASH:
        return f"{char_name} Stash"
    if item.stored_in == StoredIn.INVENTORY:
        return f"{char_name} Inv"
    return char_name


def char_item_locality_rank(
    item: D2Item,
    swap_slots: tuple[EquipSlot, EquipSlot] = _SWAP_SLOTS,
) -> int:
    """Return per-character locality rank (0 equipped, 1 swap, 2 inv, 3 stash, 4 other)."""
    if item.location == ItemLocation.EQUIPPED:
        return 1 if item.position in swap_slots else 0
    if item.stored_in == StoredIn.INVENTORY:
        return 2
    if item.stored_in == StoredIn.STASH:
        return 3
    return 4


@dataclass(frozen=True, slots=True)
class PoolItem:
    """An item yielded from a character or shared stash during pool traversal."""

    item: D2Item
    loc: str
    version: int
    resolver: GameDataResolver
    locality_rank: int
    stack_count: int
    is_primary: bool
    is_active_primary: bool
    is_stash: bool
    source_idx: int


def _iter_char_pool_items(
    ch: D2SStruct,
    *,
    is_primary: bool,
    source_idx: int,
    resolver: GameDataResolver,
    skip_swap_cta: bool,
) -> Iterator[PoolItem]:
    ver = ch.version or 0x63
    ver_res = resolver.for_version(ver)
    char_name = ch.get_char_name()
    swap_slots = inactive_weapon_slots(ch)
    has_swap_cta = skip_swap_cta and any(
        it.location == ItemLocation.EQUIPPED
        and it.position in swap_slots
        and item_cta_bo(it, ver_res, ver) is not None
        for it in ch.item_list.items
    )
    rank_offset = 0 if is_primary else 100
    for it in ch.item_list.items:
        if has_swap_cta and it.location == ItemLocation.EQUIPPED and it.position in swap_slots:
            continue
        is_active_primary = (
            is_primary and it.location == ItemLocation.EQUIPPED and it.position not in swap_slots
        )
        yield PoolItem(
            item=it,
            loc=format_item_location(char_name, it, swap_slots=swap_slots),
            version=ver,
            resolver=ver_res,
            locality_rank=rank_offset + char_item_locality_rank(it, swap_slots=swap_slots),
            stack_count=1,
            is_primary=is_primary,
            is_active_primary=is_active_primary,
            is_stash=False,
            source_idx=source_idx,
        )


def iter_pool_items(
    primary_char: D2SStruct | None,
    extra_chars: Sequence[D2SStruct] = (),
    stashes: Sequence[SharedStash] = (),
    resolver: GameDataResolver | None = None,
    *,
    skip_swap_cta: bool = False,
) -> Iterator[PoolItem]:
    """Yield items across `primary_char`, `stashes`, and `extra_chars` with locality metadata."""
    if resolver is None:
        resolver = GameDataResolver.load()
    if primary_char is not None:
        yield from _iter_char_pool_items(
            primary_char,
            is_primary=True,
            source_idx=0,
            resolver=resolver,
            skip_swap_cta=skip_swap_cta,
        )
    for stash_idx, stash in enumerate(stashes):
        stash_source_idx = 1 + stash_idx
        for idx, tab in enumerate(stash.tabs, start=1):
            if tab.items is None:
                continue
            ver = tab.item_format or 0x63
            ver_res = resolver.for_version(ver)
            loc = f"Stash Tab {idx}"
            is_adv = tab.tab_type == STASH_TAB_TYPE_ADVANCED
            for it in tab.items.items:
                cnt = it.stash_stack_size if is_adv else 1
                if is_adv and cnt <= 0:
                    continue
                yield PoolItem(
                    item=it,
                    loc=loc,
                    version=ver,
                    resolver=ver_res,
                    locality_rank=10 + idx,
                    stack_count=cnt,
                    is_primary=False,
                    is_active_primary=False,
                    is_stash=True,
                    source_idx=stash_source_idx,
                )
    extra_base_idx = 1 + len(stashes)
    for i, ch in enumerate(extra_chars):
        yield from _iter_char_pool_items(
            ch,
            is_primary=False,
            source_idx=extra_base_idx + i,
            resolver=resolver,
            skip_swap_cta=skip_swap_cta,
        )


def detect_cta_bo_bonus(
    chars: Sequence[D2SStruct],
    stashes: Sequence[SharedStash],
    resolver: GameDataResolver,
    *,
    max_level: int | None = None,
    default: int = 4,
) -> int:
    """Return max Battle Orders bonus (`oskill + all_skills`) from any CTA in pool, else `default`."""
    best: int | None = None
    for entry in iter_pool_items(
        None, extra_chars=chars, stashes=stashes, resolver=resolver, skip_swap_cta=False
    ):
        if max_level is not None and item_levelreq(entry.item, entry.resolver) > max_level:
            continue
        bonus = item_cta_bo(entry.item, entry.resolver, entry.version)
        if bonus is not None and (best is None or bonus > best):
            best = bonus
    return best if best is not None else default


_VALID_TARGET_TYPES: frozenset[str] = frozenset({"trash", "champion", "boss"})


def normalize_target_type(target_type: str) -> TargetTypeStr:
    """Validate and normalize a target type string ('trash', 'champion', or 'boss')."""
    resolved = target_type.strip().lower()
    if resolved not in _VALID_TARGET_TYPES:
        valid = ", ".join(sorted(_VALID_TARGET_TYPES))
        raise ValueError(f"Unknown target_type '{target_type}'; expected one of: {valid}")
    return cast(TargetTypeStr, resolved)


def synthesize_monster_stats(
    diff_idx: int, target_type: TargetTypeStr, char_level: int
) -> tuple[int, int, int, int]:
    """Synthesize `(target_def, target_ar, target_lvl, target_hp)` for `diff_idx` and `target_type`."""
    d = min(max(diff_idx, 0), 2)
    clvl = max(1, char_level)
    base_def = (6, 12, 20)[d]
    target_def = (base_def * 3 // 2 if target_type == "boss" else base_def) * clvl
    eff_lvl = max((1, 36, 67)[d], clvl)
    mlvl_offset = {"trash": 0, "champion": 2, "boss": 3}[target_type]
    target_lvl = min(99, eff_lvl + mlvl_offset)
    base_ar = (16, 30, 52)[d]
    ar_mult = {"trash": 1.0, "champion": 1.5, "boss": 1.8}[target_type]
    target_ar = round(base_ar * ar_mult) * eff_lvl
    hp_mult = {"trash": 1, "champion": 3, "boss": 10}[target_type]
    target_hp = (15, 45, 100)[d] * clvl * hp_mult
    return target_def, target_ar, target_lvl, target_hp


@dataclass(frozen=True, slots=True)
class CharacterBaseline:
    """Baseline character stats and limits shared across constraint builders."""

    character: CharacterStats
    target: TargetProfile
    skills: SkillModel
    max_charm_slots: int
    fixed_gear: bool = False
    fixed_slots: tuple[str, ...] = ()

    def build_constraints(
        self,
        *,
        mode: SearchModeStr,
        limit: int,
        allow_mf: bool = True,
        min_fcr: int = 0,
        min_fhr: int = 0,
        min_fr: int = 0,
        min_lr: int = 0,
        min_cr: int = 0,
        min_pr: int = 0,
        offense: OffenseProfileStr = "caster",
        require_cbf: bool = False,
        min_frw: int = 0,
        min_ias: int = 0,
        min_cb: int = 0,
        min_ll: int = 0,
        min_pdr: int = 0,
        min_mf: int = 0,
    ) -> BuildConstraints:
        return BuildConstraints(
            allow_mf=allow_mf,
            min_fcr=min_fcr,
            min_fhr=min_fhr,
            min_fr=min_fr,
            min_lr=min_lr,
            min_cr=min_cr,
            min_pr=min_pr,
            max_charm_slots=self.max_charm_slots,
            mode=mode,
            limit=limit,
            fixed_gear=self.fixed_gear,
            fixed_slots=list(self.fixed_slots),
            offense=offense,
            require_cbf=require_cbf,
            min_frw=min_frw,
            min_ias=min_ias,
            min_cb=min_cb,
            min_ll=min_ll,
            min_pdr=min_pdr,
            min_mf=min_mf,
            character=self.character,
            target=self.target,
            skills=self.skills,
        )
