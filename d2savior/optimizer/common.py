"""Shared optimizer baselines, class validators, level requirements, and CTA BO detection."""

from collections.abc import Sequence
from dataclasses import dataclass

from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass, EquipSlot
from d2savior.core.item import D2Item
from d2savior.core.item_name import LongName
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash
from d2savior.core.stats import collect_item_properties
from d2savior.optimizer.native import BuildConstraints, OffenseProfileStr, SearchModeStr

SUPPORTED_OPTIMIZER_CLASSES: tuple[CharClass, ...] = (CharClass.SORCERESS, CharClass.PALADIN)

_SWAP_SLOTS: tuple[EquipSlot, EquipSlot] = (EquipSlot.WEAPON_II, EquipSlot.SHIELD_II)
_SKILL_BATTLE_ORDERS = 149


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


def validate_supported_class(char_data: D2SStruct) -> None:
    """Validate that a parsed character belongs to a supported optimizer class."""
    _validate_char_class(char_data, SUPPORTED_OPTIMIZER_CLASSES, "Sorceress or Paladin")


def _compute_anya_bonus(char_data: D2SStruct) -> int:
    if not (char_data.quests and char_data.quests.magic == 0x216F6F57):
        return 0
    bonus = 0
    for qd in char_data.quests.qi_data:
        if len(qd.act_5) > 2 and (qd.act_5[2] & 1):
            bonus += 10
    return bonus


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


def _item_levelreq(item: D2Item, resolver: GameDataResolver) -> int:
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
        req = max(req, _item_levelreq(gem, resolver))
    return req


def _item_cta_bo(item: D2Item, resolver: GameDataResolver, version: int) -> int | None:
    """Return `bo_oskill + all_skills` if `item` grants Battle Orders (pid 97), else None."""
    bo_oskill: int | None = None
    all_skills = 0
    for pid, val, params in collect_item_properties(item, resolver=resolver, version=version):
        if pid == 97 and len(params) >= 2 and params[0] == _SKILL_BATTLE_ORDERS:
            bo_oskill = (bo_oskill or 0) + params[1]
        elif pid == 127:
            all_skills += params[0] if params else val
    return bo_oskill + all_skills if bo_oskill is not None else None


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

    def scan(item: D2Item, version: int) -> None:
        nonlocal best
        ver_res = resolver.for_version(version)
        if max_level is not None and _item_levelreq(item, ver_res) > max_level:
            return
        bonus = _item_cta_bo(item, ver_res, version)
        if bonus is not None and (best is None or bonus > best):
            best = bonus

    for char in chars:
        ver = char.version or 0x63
        for it in char.item_list.items:
            scan(it, ver)
    for stash in stashes:
        for tab in stash.tabs:
            if tab.items is None:
                continue
            ver = tab.item_format or 0x63
            for it in tab.items.items:
                scan(it, ver)
    return best if best is not None else default


@dataclass(frozen=True, slots=True)
class CharacterBaseline:
    """Baseline character stats and limits shared across constraint builders."""

    char_class: int
    base_life: int
    base_mana: int
    base_hell_res: int
    base_str: int
    base_dex: int
    max_charm_slots: int
    bo_base_bonus: int
    use_bo: bool = True
    fixed_gear: bool = False
    blizz_base_lvl: int = 20
    blizz_syn_pts: int = 54
    cm_base_lvl: int = 20
    base_max_fr: int = 0
    base_max_lr: int = 0
    base_max_cr: int = 0
    base_max_pr: int = 0

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
            base_life=self.base_life,
            base_mana=self.base_mana,
            base_hell_res=self.base_hell_res,
            base_str=self.base_str,
            base_dex=self.base_dex,
            bo_base_bonus=self.bo_base_bonus,
            limit=limit,
            blizz_base_lvl=self.blizz_base_lvl,
            blizz_syn_pts=self.blizz_syn_pts,
            cm_base_lvl=self.cm_base_lvl,
            char_class=self.char_class,
            base_max_fr=self.base_max_fr,
            base_max_lr=self.base_max_lr,
            base_max_cr=self.base_max_cr,
            base_max_pr=self.base_max_pr,
            use_bo=self.use_bo,
            fixed_gear=self.fixed_gear,
            offense=offense,
        )
