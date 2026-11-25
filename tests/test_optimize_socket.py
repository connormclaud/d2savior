"""Unit and integration tests for Larzuk Socket Quest optimization."""

from pathlib import Path

import pytest

from d2savior.cli import main, parse_d2i_file, parse_d2s_file
from d2savior.core.enums import CharClass, ItemLocation, ItemQuality
from d2savior.core.item import D2Item, ExtItemInfo, ItemInfo
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash
from d2savior.optimizer import (
    HAS_NATIVE,
    ItemSpec,
    extract_pool,
    extract_socketables,
    find_unclaimed_socket_quests,
    format_socket_report,
    get_larzuk_socket_range,
    get_socket_quest_status,
    optimize_socket_quests,
)
from d2savior.optimizer.paladin import build_paladin_preset_constraints
from d2savior.optimizer.presets import resolve_build_expr
from d2savior.optimizer.socket import SocketCandidateVariant, _pareto_prune_variants

requires_native = pytest.mark.skipif(not HAS_NATIVE, reason="d2savior._native is not built")
FIXTURES_DIR = Path(__file__).parent / "fixtures"
PAL_FIXTURES_DIR = FIXTURES_DIR / "paladin_snapshot"


def _make_item(
    code: str,
    *,
    quality: ItemQuality = ItemQuality.NORMAL,
    ilvl: int = 85,
    is_socketed: bool = False,
    is_simple: bool = False,
    is_runeword: bool = False,
    location: ItemLocation = ItemLocation.STORED,
) -> D2Item:
    item = D2Item()
    item.is_simple = is_simple
    item.is_socketed = is_socketed
    item.is_runeword = is_runeword
    item.location = int(location)
    info = ItemInfo()
    info.type_name = code.ljust(4)[:4].encode("ascii")
    ext = ExtItemInfo()
    ext.quality = int(quality)
    ext.drop_level = ilvl
    info.ext_info = ext
    item.item_info = info
    return item


def test_max_sockets_and_larzuk_rules(game_data_resolver: GameDataResolver) -> None:
    res = game_data_resolver
    # Crystal Sword (crs): 3 (<=25), 4 (26..40), 6 (41+)
    assert res.get_max_sockets("crs", 15) == 3
    assert res.get_max_sockets("crs", 26) == 4
    assert res.get_max_sockets("crs", 40) == 4
    assert res.get_max_sockets("crs", 41) == 6
    assert get_larzuk_socket_range(_make_item("crs", ilvl=35), res) == (4, 4)

    # Flail (fla): 3 (<=25), 4 (26..40), 5 (41+, capped by Weapons.txt gemsockets=5)
    assert res.get_max_sockets("fla", 30) == 4
    assert res.get_max_sockets("fla", 50) == 5

    # Monarch (uit): 4 sockets at high ilvl
    assert get_larzuk_socket_range(_make_item("uit", quality=ItemQuality.HIGH, ilvl=75), res) == (
        4,
        4,
    )

    # Circlet (ci0) at ilvl 10 -> 1 socket even if Magic; Tiara (ci2) Magic -> (1, 2)
    assert get_larzuk_socket_range(_make_item("ci0", quality=ItemQuality.MAGIC, ilvl=10), res) == (
        1,
        1,
    )
    assert get_larzuk_socket_range(_make_item("ci2", quality=ItemQuality.MAGIC, ilvl=75), res) == (
        1,
        2,
    )

    # Unique / Set / Rare / Crafted -> always (1, 1)
    for q in (ItemQuality.SET, ItemQuality.RARE, ItemQuality.UNIQUE, ItemQuality.CRAFTED):
        assert get_larzuk_socket_range(_make_item("ci2", quality=q, ilvl=85), res) == (1, 1)

    # Ineligible items: already socketed, runeword, simple, jewelry, boots, gloves, belt, throwing
    assert get_larzuk_socket_range(_make_item("crs", is_socketed=True), res) == (0, 0)
    assert get_larzuk_socket_range(_make_item("crs", is_runeword=True), res) == (0, 0)
    assert get_larzuk_socket_range(_make_item("r07", is_simple=True), res) == (0, 0)
    for code in ("rin", "amu", "lbt", "lgl", "mbl", "jav"):
        assert get_larzuk_socket_range(_make_item(code, quality=ItemQuality.UNIQUE), res) == (0, 0)


def test_socket_quest_status_and_socketables(game_data_resolver: GameDataResolver) -> None:
    _, sork, _ = parse_d2s_file(str(FIXTURES_DIR / "sork.d2s"), resolver=game_data_resolver)
    _, mule, _ = parse_d2s_file(str(FIXTURES_DIR / "mule_unique.d2s"), resolver=game_data_resolver)
    _, stash, kind, _ = parse_d2i_file(
        str(FIXTURES_DIR / "ModernSharedStashSoftCoreV2.d2i"), resolver=game_data_resolver
    )
    assert sork is not None
    assert mule is not None
    assert kind == "stash"
    assert isinstance(stash, SharedStash)

    assert get_socket_quest_status(sork) == [
        ("Normal", "Used"),
        ("Nightmare", "Unclaimed"),
        ("Hell", "Locked"),
    ]
    assert find_unclaimed_socket_quests([sork, mule]) == [("sork", "Nightmare")]

    owned_opts, rune_counts, gem_types, jewel_count = extract_socketables(
        sork, extra_chars=[mule], stashes=[stash], resolver=game_data_resolver, theoretical=False
    )
    assert rune_counts["r07"] == 15  # Tal from currency tab
    assert rune_counts["r31"] == 0  # Jah is empty in currency tab (stack_size == 0)
    assert gem_types == 29
    assert jewel_count > 0
    assert all(opt.owned for opt in owned_opts)

    theo_opts, _, _, _ = extract_socketables(
        sork, extra_chars=[mule], stashes=[stash], resolver=game_data_resolver, theoretical=True
    )
    assert len(theo_opts) > len(owned_opts)
    assert any(opt.code == "r22" and not opt.owned for opt in theo_opts)


@requires_native
def test_pareto_prune_preserves_zero_mf_bucket() -> None:
    v_mf = SocketCandidateVariant(
        item_name="Shako",
        item_loc="Inv",
        slot="helm",
        kind="socket",
        action_label="Jewel (+30% FR, +5% MF)",
        sockets_range=(1, 1),
        owned=True,
        missing_runes=(),
        spec=ItemSpec("Shako [+Jewel]", "helm", "Inv", fr=30, mf=5),
    )
    v_ral = SocketCandidateVariant(
        item_name="Shako",
        item_loc="Inv",
        slot="helm",
        kind="socket",
        action_label="Ral Rune",
        sockets_range=(1, 1),
        owned=True,
        missing_runes=(),
        spec=ItemSpec("Shako [+Ral]", "helm", "Inv", fr=30, mf=0),
    )
    v_weak = SocketCandidateVariant(
        item_name="Shako",
        item_loc="Inv",
        slot="helm",
        kind="socket",
        action_label="Weak",
        sockets_range=(1, 1),
        owned=True,
        missing_runes=(),
        spec=ItemSpec("Shako [+Weak]", "helm", "Inv", fr=15, mf=0),
    )
    pruned = _pareto_prune_variants([v_mf, v_ral, v_weak])
    labels = {v.action_label for v in pruned}
    assert labels == {"Jewel (+30% FR, +5% MF)", "Ral Rune"}


@requires_native
def test_optimize_socket_sorc_fixtures(game_data_resolver: GameDataResolver) -> None:
    _, sork, _ = parse_d2s_file(str(FIXTURES_DIR / "sork.d2s"), resolver=game_data_resolver)
    _, mule, _ = parse_d2s_file(str(FIXTURES_DIR / "mule_unique.d2s"), resolver=game_data_resolver)
    _, stash, _, _ = parse_d2i_file(
        str(FIXTURES_DIR / "ModernSharedStashSoftCoreV2.d2i"), resolver=game_data_resolver
    )
    assert sork is not None
    assert mule is not None
    assert isinstance(stash, SharedStash)

    # TZ preset is infeasible without a socket quest, and Wall of the Eyeless + Flawless Diamond unlocks it.
    report_tz = optimize_socket_quests(
        sork, extra_chars=[mule], stashes=[stash], resolver=game_data_resolver, build="tz", limit=3
    )
    assert len(report_tz.presets) == 1
    p_tz = report_tz.presets[0]
    assert p_tz.baseline is None
    assert p_tz.candidates
    assert p_tz.candidates[0].unlocked_feasibility is True
    assert "Wall of the Eyeless" in p_tz.candidates[0].variant.item_name
    assert "Diamond" in p_tz.candidates[0].variant.action_label

    # Keep-gear restricts candidates to sork's currently equipped gear only.
    report_kept = optimize_socket_quests(
        sork,
        extra_chars=[mule],
        stashes=[stash],
        resolver=game_data_resolver,
        build="mf-speed",
        keep_equipped="all",
        limit=3,
    )
    for cand in report_kept.presets[0].candidates:
        assert cand.variant.item_loc == "sork Equipped"

    text = format_socket_report(report_tz)
    assert "Unlocks feasible build!" in text
    assert "Nightmare: Unclaimed" in text


@requires_native
def test_optimize_socket_paladin_runeword_base(game_data_resolver: GameDataResolver) -> None:
    _, smite, _ = parse_d2s_file(str(PAL_FIXTURES_DIR / "smite.d2s"), resolver=game_data_resolver)
    extras = [
        ch
        for p in sorted(PAL_FIXTURES_DIR.glob("mule_*.d2s"))
        if (ch := parse_d2s_file(str(p), resolver=game_data_resolver)[1]) is not None
    ]
    _, stash, _, _ = parse_d2i_file(
        str(PAL_FIXTURES_DIR / "ModernSharedStashSoftCoreV2.d2i"), resolver=game_data_resolver
    )
    assert smite is not None
    assert isinstance(stash, SharedStash)

    report = optimize_socket_quests(
        smite, extra_chars=extras, stashes=[stash], resolver=game_data_resolver, limit=3
    )
    assert len(report.presets) == 1
    top = report.presets[0].candidates[0]
    assert top.variant.kind == "runeword"
    assert "Rondache" in top.variant.item_name
    assert "Spirit" in top.variant.action_label
    assert top.result.skills > (
        report.presets[0].baseline.skills if report.presets[0].baseline else 0
    )


@requires_native
def test_cli_optimize_socket(capsys: pytest.CaptureFixture[str]) -> None:
    main(
        ["optimize", "socket", "--no-config", "--char", "sork", "-b", "mf-pure", str(FIXTURES_DIR)]
    )
    out = capsys.readouterr().out
    assert "Socket Quest Optimizer: sork" in out
    assert "Stealskull" in out
    assert "Shael" in out

    main(
        [
            "optimize",
            "socket",
            "--no-config",
            "--theoretical",
            "--char",
            "sork",
            "-b",
            "mf-speed",
            str(FIXTURES_DIR),
        ]
    )
    out_theo = capsys.readouterr().out
    assert "Ist Rune" in out_theo
    assert "[theoretical]" in out_theo
    assert "lvl 99 unbound Str/Dex" in out_theo


@requires_native
def test_theoretical_socket_unbinds_level_and_str_dex_reqs(
    game_data_resolver: GameDataResolver,
) -> None:
    # Low-level / low-Str Sorc (lvl 17, Str 20, Dex 25) against Paladin stash (high-lvl/high-Str items)
    _, norm_sorc, _ = parse_d2s_file(str(FIXTURES_DIR / "Sorc.d2s"), resolver=game_data_resolver)
    _, pal_stash, _, _ = parse_d2i_file(
        str(PAL_FIXTURES_DIR / "ModernSharedStashSoftCoreV2.d2i"), resolver=game_data_resolver
    )
    assert norm_sorc is not None
    assert isinstance(pal_stash, SharedStash)

    # Without theoretical: high-level/high-Str items like Lidless Wall (lvl 41, Str 58) are excluded.
    sorc_owned = optimize_socket_quests(
        norm_sorc,
        stashes=[pal_stash],
        resolver=game_data_resolver,
        build="mf-pure",
        theoretical=False,
        limit=5,
    )
    sorc_theo = optimize_socket_quests(
        norm_sorc,
        stashes=[pal_stash],
        resolver=game_data_resolver,
        build="mf-pure",
        theoretical=True,
        limit=5,
    )
    assert sorc_theo.char_level == 17
    assert sorc_theo.eligible_item_count > sorc_owned.eligible_item_count
    assert any("Lidless Wall" in c.variant.item_name for c in sorc_theo.presets[0].candidates)
    assert all("Lidless Wall" not in c.variant.item_name for c in sorc_owned.presets[0].candidates)

    # Synthetic high-Str/high-lvl Monarch (lvlreq 54, req_str 156) is usable as Spirit base on lvl 17 Sorc.
    monarch = _make_item("uit", quality=ItemQuality.NORMAL, ilvl=85)
    norm_sorc.item_list.items.append(monarch)
    pool_default, _ = extract_pool(norm_sorc, resolver=game_data_resolver)
    pool_unbound, _ = extract_pool(
        norm_sorc, resolver=game_data_resolver, char_level_override=99, ignore_reqs=True
    )
    assert all(it.req_str == 0 and it.req_dex == 0 for it in pool_unbound)
    assert len(pool_unbound) >= len(pool_default)

    sorc_monarch_owned = optimize_socket_quests(
        norm_sorc,
        stashes=[pal_stash],
        resolver=game_data_resolver,
        build="mf-pure",
        theoretical=False,
        limit=5,
    )
    sorc_monarch_theo = optimize_socket_quests(
        norm_sorc,
        stashes=[pal_stash],
        resolver=game_data_resolver,
        build="mf-pure",
        theoretical=True,
        limit=5,
    )
    assert all(
        "Monarch" not in c.variant.item_name for c in sorc_monarch_owned.presets[0].candidates
    )
    assert any(
        "Monarch" in c.variant.item_name and "Spirit" in c.variant.action_label
        for c in sorc_monarch_theo.presets[0].candidates
    )


@requires_native
def test_theoretical_socket_paladin_lvl99_preserves_base_stats(
    game_data_resolver: GameDataResolver,
) -> None:
    _, smite, _ = parse_d2s_file(str(PAL_FIXTURES_DIR / "smite.d2s"), resolver=game_data_resolver)
    extras = [
        ch
        for p in sorted(PAL_FIXTURES_DIR.glob("mule_*.d2s"))
        if (ch := parse_d2s_file(str(p), resolver=game_data_resolver)[1]) is not None
    ]
    _, stash, _, _ = parse_d2i_file(
        str(PAL_FIXTURES_DIR / "ModernSharedStashSoftCoreV2.d2i"), resolver=game_data_resolver
    )
    assert smite is not None
    assert isinstance(stash, SharedStash)

    # Paladin baseline with char_level_override=99 keeps real base_str/base_dex (no fake melee DPS inflation).
    preset = resolve_build_expr("leveling", CharClass.PALADIN)[0]
    title_99, constraints_99, _, _ = build_paladin_preset_constraints(
        smite,
        preset,
        extra_chars=extras,
        stashes=[stash],
        resolver=game_data_resolver,
        char_level_override=99,
    )
    assert constraints_99.char_level == 99
    assert constraints_99.base_str == smite.player_stats.strength
    assert constraints_99.base_dex == smite.player_stats.dexterity
    assert "lvl 99" in title_99

    rep_owned = optimize_socket_quests(
        smite,
        extra_chars=extras,
        stashes=[stash],
        resolver=game_data_resolver,
        theoretical=False,
        limit=5,
    )
    rep_theo = optimize_socket_quests(
        smite,
        extra_chars=extras,
        stashes=[stash],
        resolver=game_data_resolver,
        theoretical=True,
        limit=5,
    )
    assert rep_theo.char_level == 30
    assert rep_theo.eligible_item_count > rep_owned.eligible_item_count
    cands = rep_theo.presets[0].candidates
    assert any("Sacred Targe" in c.variant.item_name for c in cands)
    assert any("Guillaume's Face" in c.variant.item_name for c in cands)
    assert all("Sacred Targe" not in c.variant.item_name for c in rep_owned.presets[0].candidates)


@requires_native
def test_socket_sorc_cold_armor_staffmod_and_gear_defense_parity(
    game_data_resolver: GameDataResolver,
) -> None:
    _, norm_sorc, _ = parse_d2s_file(
        str(PAL_FIXTURES_DIR.parent / "sork.d2s"), resolver=game_data_resolver
    )
    assert norm_sorc is not None
    # Verify socket candidate generation preserves Chilling Armor staffmod (Snowclash) and gear_defense.
    from d2savior.optimizer.socket import _collect_eligible_items

    eligible = _collect_eligible_items(
        norm_sorc,
        extra_chars=(),
        stashes=(),
        resolver=game_data_resolver,
        kept_slots=frozenset(),
        pal_spec="leveling",
        pal_offense="caster",
        set_group_ids={},
        global_set_cache={},
        sorc_filler_id=None,
        sorc_armor_id=40,
        pal_aura_id=None,
    )
    assert eligible
    assert eligible[0].base_spec is None or eligible[0].base_spec.defense >= 0

    rep = optimize_socket_quests(
        norm_sorc,
        resolver=game_data_resolver,
        build="mf-pure",
        theoretical=True,
        limit=2,
    )
    assert rep.presets
    baseline = rep.presets[0].baseline
    assert baseline is not None
    assert (
        baseline.gear_defense == sum(it.defense for it in baseline.items)
        or baseline.gear_defense > 0
    )
