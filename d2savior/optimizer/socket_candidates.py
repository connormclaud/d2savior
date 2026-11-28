"""Larzuk Socket Quest eligibility, socketable scanning, and candidate discovery."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from d2savior.core.constants import DIFFICULTY_NAMES
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import ItemLocation, ItemQuality
from d2savior.core.item import D2Item
from d2savior.core.item_formatter import format_summary_properties, get_item_display_name
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import GEM_CODES, RUNE_CODES, SharedStash
from d2savior.core.stats import collect_item_properties, normalize_damage_props
from d2savior.optimizer.common import ALL_GEAR_SLOTS, item_levelreq, iter_pool_items
from d2savior.optimizer.extract import classify_slot, item_to_spec
from d2savior.optimizer.extract_props import ExtractionContext
from d2savior.optimizer.native import ItemSpec

_SOCKETABLE_SLOTS: frozenset[str] = frozenset({"helm", "armor", "shield", "weapon", "weapon2h"})
_JEWEL_CODES: frozenset[str] = frozenset({"jew", "cjw"})
_RUNE_CODES_STR: tuple[str, ...] = tuple(f"r{i:02d}" for i in range(1, 34))
_THEORETICAL_GEM_CODES: tuple[str, ...] = ("gpv", "gpb", "gpg", "gpr", "gpw", "gpy", "skz")
THEORETICAL_CHAR_LEVEL = 99


def get_socket_quest_status(char_data: D2SStruct) -> list[tuple[str, str]]:
    """Return `(difficulty_name, status)` for Larzuk's 'Siege on Harrogath' quest."""
    quests = char_data.quests
    has_quests = bool(quests and quests.magic == 0x216F6F57)
    out: list[tuple[str, str]] = []
    for diff_idx, diff_name in enumerate(DIFFICULTY_NAMES):
        status = "Locked"
        if has_quests and quests is not None and diff_idx < len(quests.qi_data):
            qd = quests.qi_data[diff_idx]
            w = qd.act_5[0] if qd.act_5 else 0
            if w & 1:
                status = "Used"
            elif w & 2:
                status = "Unclaimed"
        out.append((diff_name, status))
    return out


def find_unclaimed_socket_quests(chars: Sequence[D2SStruct]) -> list[tuple[str, str]]:
    """Return `(char_name, difficulty_name)` for characters with an unclaimed socket quest."""
    unclaimed: list[tuple[str, str]] = []
    for ch in chars:
        name = ch.get_char_name()
        for diff_name, status in get_socket_quest_status(ch):
            if status == "Unclaimed":
                unclaimed.append((name, diff_name))
    return unclaimed


def get_larzuk_socket_range(item: D2Item, resolver: GameDataResolver) -> tuple[int, int]:
    """Return `(min_sockets, max_sockets)` Larzuk can add to `item`, or `(0, 0)` if ineligible."""
    if (
        item.is_socketed
        or item.is_simple
        or item.is_ear
        or item.is_runeword
        or item.is_disabled
        or item.location == ItemLocation.SOCKET
    ):
        return (0, 0)

    ilvl = item.ext_info.drop_level if item.ext_info else 99
    max_sock = resolver.get_max_sockets(item.code_str, ilvl)
    if max_sock <= 0:
        return (0, 0)

    quality = item.quality()
    if quality in (ItemQuality.LOW, ItemQuality.NORMAL, ItemQuality.HIGH):
        return (max_sock, max_sock)
    if quality == ItemQuality.MAGIC:
        return (1, min(2, max_sock))
    if quality in (ItemQuality.SET, ItemQuality.RARE, ItemQuality.UNIQUE, ItemQuality.CRAFTED):
        return (1, 1)
    return (0, 0)


@dataclass(frozen=True, slots=True)
class SocketableOption:
    """A gem, rune, or jewel candidate that can be placed into a single socket."""

    label: str
    code: str
    loc: str
    levelreq: int
    owned: bool
    is_jewel: bool
    jewel_props: tuple[tuple[int, int, tuple[int, ...]], ...] = ()

    def props_for_item(
        self, parent_item: D2Item, resolver: GameDataResolver
    ) -> list[tuple[int, int, list[int]]]:
        """Return `(prop_id, val, params)` granted by this socketable inside `parent_item`."""
        if self.is_jewel:
            return [(pid, val, list(params)) for pid, val, params in self.jewel_props]
        return resolver.get_socket_properties_for_code(parent_item, self.code)


@dataclass(frozen=True, slots=True)
class CandidateItem:
    """An eligible unsocketed item discovered in the character/stash pool."""

    item: D2Item
    base_name: str
    loc: str
    slot: str
    version: int
    resolver: GameDataResolver
    sockets_range: tuple[int, int]
    locality_rank: int
    base_spec: ItemSpec | None


def _item_props_key(
    props: Sequence[tuple[int, int, list[int]]],
) -> tuple[tuple[int, int, tuple[int, ...]], ...]:
    return tuple((pid, val, tuple(params)) for pid, val, params in props)


def _format_jewel_label(item: D2Item, resolver: GameDataResolver, version: int) -> str:
    base_title = get_item_display_name(item, resolver=resolver, version=version)
    props = collect_item_properties(
        item, resolver=resolver, version=version, normalize_source=normalize_damage_props
    )
    prop_strs = format_summary_properties(props, resolver=resolver, version=version)
    if prop_strs:
        return f"{base_title} ({', '.join(prop_strs)})"
    return base_title


def _record_socketable_item(
    item: D2Item,
    loc: str,
    rank: int,
    ver: int,
    ver_res: GameDataResolver,
    *,
    count: int,
    rune_counts: Counter[str],
    gem_counts: Counter[str],
    code_locs: dict[str, tuple[int, str]],
    jewel_map: dict[tuple[object, ...], tuple[int, SocketableOption]],
) -> None:
    if item.location == ItemLocation.SOCKET:
        return
    tn = item.type_name
    code = item.code_str.strip().lower()
    if tn in RUNE_CODES or code in _RUNE_CODES_STR:
        rune_counts[code] += count
        prev = code_locs.get(code)
        if prev is None or rank < prev[0]:
            code_locs[code] = (rank, loc)
    elif tn in GEM_CODES:
        gem_counts[code] += count
        prev = code_locs.get(code)
        if prev is None or rank < prev[0]:
            code_locs[code] = (rank, loc)
    elif code in _JEWEL_CODES:
        tp = item.type_specific_info
        raw_props = (
            tp.property_list.get_parsed_properties(ver, data=ver_res.data)
            if tp and tp.property_list
            else []
        )
        if not raw_props:
            return
        props_key = _item_props_key(raw_props)
        lvlreq = item_levelreq(item, ver_res)
        dedup_key = (props_key, lvlreq)
        prev_j = jewel_map.get(dedup_key)
        if prev_j is None or rank < prev_j[0]:
            label = _format_jewel_label(item, ver_res, ver)
            opt = SocketableOption(
                label=label,
                code=code,
                loc=loc,
                levelreq=lvlreq,
                owned=True,
                is_jewel=True,
                jewel_props=props_key,
            )
            jewel_map[dedup_key] = (rank, opt)


def extract_socketables(
    primary_char: D2SStruct,
    extra_chars: Sequence[D2SStruct] = (),
    stashes: Sequence[SharedStash] = (),
    resolver: GameDataResolver | None = None,
    *,
    theoretical: bool = False,
) -> tuple[list[SocketableOption], Counter[str], int, int]:
    """Collect owned (and optionally theoretical) gems, runes, and jewels."""
    if resolver is None:
        resolver = GameDataResolver.load()

    rune_counts: Counter[str] = Counter()
    gem_counts: Counter[str] = Counter()
    code_locs: dict[str, tuple[int, str]] = {}
    jewel_map: dict[tuple[object, ...], tuple[int, SocketableOption]] = {}
    jewel_count = 0

    for entry in iter_pool_items(
        primary_char,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        skip_swap_cta=False,
    ):
        if entry.item.location in (ItemLocation.EQUIPPED, ItemLocation.SOCKET):
            continue
        if entry.item.code_str.strip().lower() in _JEWEL_CODES:
            jewel_count += 1
        _record_socketable_item(
            entry.item,
            entry.loc,
            entry.locality_rank,
            entry.version,
            entry.resolver,
            count=entry.stack_count,
            rune_counts=rune_counts,
            gem_counts=gem_counts,
            code_locs=code_locs,
            jewel_map=jewel_map,
        )

    options: list[SocketableOption] = []
    for code, count in sorted({**rune_counts, **gem_counts}.items()):
        if count <= 0:
            continue
        info = resolver.get_item(code)
        label = resolver.get_localized_item_name(code, fallback=info.name if info else code)
        options.append(
            SocketableOption(
                label=label,
                code=code,
                loc=code_locs[code][1],
                levelreq=info.levelreq if info else 0,
                owned=True,
                is_jewel=False,
            )
        )

    options.extend(opt for _, opt in sorted(jewel_map.values(), key=lambda p: (p[0], p[1].label)))

    if theoretical:
        owned_codes = set(rune_counts) | set(gem_counts)
        for code in (*_THEORETICAL_GEM_CODES, *_RUNE_CODES_STR):
            if code in owned_codes or (info := resolver.get_item(code)) is None:
                continue
            label = resolver.get_localized_item_name(code, fallback=info.name)
            options.append(
                SocketableOption(
                    label=label,
                    code=code,
                    loc="Theoretical",
                    levelreq=info.levelreq,
                    owned=False,
                    is_jewel=False,
                )
            )

    return options, rune_counts, len(gem_counts), jewel_count


def _candidate_dedup_key(
    it: D2Item,
    display_name: str,
    sock_range: tuple[int, int],
    ver_res: GameDataResolver,
    ver: int,
) -> tuple[object, ...]:
    base_props = collect_item_properties(it, resolver=ver_res, version=ver)
    tp = it.type_specific_info
    defence = tp.get_defence() if tp and tp.defence is not None else 0
    quality = it.quality()
    code = it.code_str.strip().lower()
    if quality in (ItemQuality.LOW, ItemQuality.NORMAL, ItemQuality.HIGH):
        return ("base", code, it.is_ethereal, sock_range, defence, _item_props_key(base_props))
    return (
        "magic+",
        display_name,
        code,
        it.is_ethereal,
        quality,
        sock_range,
        defence,
        _item_props_key(base_props),
    )


def _consider_candidate_item(
    it: D2Item,
    loc: str,
    rank: int,
    ver: int,
    ver_res: GameDataResolver,
    *,
    is_active_primary: bool,
    keep_all: bool,
    kept_slots: frozenset[str],
    ctx: ExtractionContext,
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
    dedup: dict[tuple[object, ...], CandidateItem],
    ignore_reqs: bool = False,
) -> None:
    if it.location == ItemLocation.SOCKET or (keep_all and not is_active_primary):
        return
    if item_levelreq(it, ver_res) > ctx.char_level:
        return
    sock_range = get_larzuk_socket_range(it, ver_res)
    if sock_range[1] <= 0:
        return
    classified = classify_slot(it, ver_res, char_class=ctx.char_class)
    if classified is None:
        return
    slot, _, _ = classified
    if slot not in _SOCKETABLE_SLOTS or (not is_active_primary and slot in kept_slots):
        return

    display_name = get_item_display_name(it, resolver=ver_res, version=ver)
    d_key = _candidate_dedup_key(it, display_name, sock_range, ver_res, ver)
    prev = dedup.get(d_key)
    if prev is not None and rank >= prev.locality_rank:
        return

    base_spec_raw = item_to_spec(
        it,
        loc,
        ver_res,
        ver,
        ctx=ctx,
        set_group_ids=set_group_ids,
        global_set_cache=global_set_cache,
        skip_useful_check=True,
        ignore_reqs=ignore_reqs,
    )
    dedup[d_key] = CandidateItem(
        item=it,
        base_name=display_name,
        loc=loc,
        slot=slot,
        version=ver,
        resolver=ver_res,
        sockets_range=sock_range,
        locality_rank=rank,
        base_spec=base_spec_raw if isinstance(base_spec_raw, ItemSpec) else None,
    )


def collect_eligible_items(
    primary_char: D2SStruct,
    extra_chars: Sequence[D2SStruct],
    stashes: Sequence[SharedStash],
    resolver: GameDataResolver,
    *,
    kept_slots: frozenset[str],
    set_group_ids: dict[str, int],
    global_set_cache: dict[tuple[str, int], list[tuple[int, ItemSpec]]],
    ctx: ExtractionContext | None = None,
    pal_spec: str = "leveling",
    pal_offense: str = "caster",
    sorc_filler_id: int | None = None,
    pal_aura_id: int | None = -1,
    sorc_armor_id: int | None = None,
    char_level_override: int | None = None,
    ignore_reqs: bool = False,
) -> list[CandidateItem]:
    """Find deduplicated, class-equippable, unsocketed items eligible for Larzuk."""
    if ctx is None:
        char_level = (
            char_level_override
            if char_level_override is not None
            else max(1, primary_char.player_stats.level or primary_char.char_level)
        )
        eff_ctx = ExtractionContext(
            char_class=primary_char.char_class,
            char_level=char_level,
            pal_spec=pal_spec,
            pal_offense=pal_offense,
            sorc_filler_id=sorc_filler_id,
            sorc_armor_id=sorc_armor_id,
            pal_aura_id=pal_aura_id,
        )
    else:
        eff_ctx = ctx
    keep_all = kept_slots == ALL_GEAR_SLOTS
    dedup: dict[tuple[object, ...], CandidateItem] = {}

    for entry in iter_pool_items(
        primary_char,
        extra_chars=extra_chars,
        stashes=stashes,
        resolver=resolver,
        skip_swap_cta=True,
    ):
        _consider_candidate_item(
            entry.item,
            entry.loc,
            entry.locality_rank,
            entry.version,
            entry.resolver,
            is_active_primary=entry.is_active_primary,
            keep_all=keep_all,
            kept_slots=kept_slots,
            ctx=eff_ctx,
            set_group_ids=set_group_ids,
            global_set_cache=global_set_cache,
            dedup=dedup,
            ignore_reqs=ignore_reqs,
        )

    return sorted(dedup.values(), key=lambda c: (c.locality_rank, c.base_name))
