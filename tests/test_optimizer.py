from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from d2savior import load_d2s
from d2savior.cli import main
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass, EquipSlot, ItemLocation
from d2savior.core.item import D2Item
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash
from d2savior.optimizer import (
    BUILD_CHOICES,
    HAS_NATIVE,
    PALADIN_BUILD_CHOICES,
    PALADIN_FCR_BPS,
    PALADIN_FHR_BPS,
    BuildConstraints,
    CasterSkillModel,
    CharacterStats,
    CharmSpec,
    ItemSpec,
    MeleeSkillModel,
    TargetProfile,
    blizzard_damage,
    blizzard_damage_with_base,
    class_breakpoints,
    detect_cta_bo_bonus,
    detect_paladin_spec,
    evaluate_build,
    extract_pool,
    format_build_report,
    format_paladin_leveling_report,
    optimize_builds,
    optimize_paladin_leveling,
    score_of_result,
    select_sorc_presets,
)
from d2savior.optimizer.common import item_levelreq
from d2savior.optimizer.extract import _extract_prop_acc, classify_slot, item_to_spec
from d2savior.optimizer.native import _missing_native
from d2savior.optimizer.paladin import _result_dedup_key

requires_native = pytest.mark.skipif(not HAS_NATIVE, reason="d2savior._native is not built")

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@requires_native
def test_blizzard_damage_pyo3() -> None:
    base0, syn0, cm0 = blizzard_damage(0)
    assert abs(base0 - 594.5) < 1e-9
    assert abs(syn0 - 2199.65) < 1e-6
    assert cm0 == -115

    base7, syn7, cm7 = blizzard_damage(7)
    assert abs(base7 - 963.0) < 1e-9
    assert abs(syn7 - 3563.1) < 1e-6
    assert cm7 == -150

    base9, syn9, cm9 = blizzard_damage(9)
    assert abs(base9 - 1084.0) < 1e-9
    assert abs(syn9 - 4010.8) < 1e-6
    assert cm9 == -160


@requires_native
def test_evaluate_build_and_constraints_validation() -> None:
    items = [
        ItemSpec("Spirit Sword", "weapon", "test", all_skills=2, fcr=34, fhr=55, vit=22, mana=93),
        ItemSpec(
            "Spirit Shield", "shield", "test", all_skills=2, fcr=34, fhr=55, lr=35, cr=35, pr=35
        ),
        ItemSpec("Tiara", "helm", "test", class_skills=2),
        ItemSpec("Smoke", "armor", "test", fhr=20, fr=50, lr=50, cr=50, pr=50),
        ItemSpec("Grim Noose", "amulet", "test", class_skills=1, fcr=5, lr=30),
        ItemSpec("Belt", "belt", "test", fcr=10, life=50, cr=27),
        ItemSpec("Trang-Oul's", "gloves", "test", fcr=20, cr=30),
        ItemSpec("Aldur's", "boots", "test", frw=40, life=50, fr=48),
        ItemSpec("Ring A", "ring", "test", fcr=10, fr=30, lr=30, pr=30),
        ItemSpec("Ring B", "ring", "test", fr=30, lr=30, cr=30, pr=30),
    ]
    charms = [
        CharmSpec("Vita GC", 3, "test", life=40),
        CharmSpec("Chilling GC", 3, "test", skills=1),
    ]

    res = evaluate_build(items, charms, base_hell_res=-70)
    assert res.skills == 8
    assert charms[1].skills == 1
    opt = optimize_builds(
        items,
        [
            CharmSpec("Chilling GC", 3, "test", skills=1),
            *(CharmSpec(f"Life {i}", 1, "test", life=20) for i in range(23)),
        ],
        BuildConstraints(
            allow_mf=False,
            min_fcr=105,
            min_fhr=86,
            min_fr=75,
            min_lr=75,
            min_cr=75,
            min_pr=75,
            mode="power",
            character=CharacterStats(base_hell_res=-70),
        ),
    )
    assert opt[0].skills == 8
    assert res.fcr == 113
    assert res.fcr_bp == 105
    assert res.fhr == 130
    assert res.fhr_bp == 86
    assert (res.fr, res.lr, res.cr, res.pr) == (75, 75, 75, 75)
    assert res.mf == 0

    bad = BuildConstraints(mode="invalid")  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError, match="invalid mode"):
        optimize_builds(items, charms, bad)


@requires_native
def test_str_dex_requirements_pyo3() -> None:
    items = [
        ItemSpec("Ali Baba", "weapon", "test", mf=89, dex_bonus=15, req_dex=42),
        ItemSpec("Spirit Sword", "weapon", "test", all_skills=2, fcr=34, fhr=55),
        ItemSpec(
            "Spirit Shield",
            "shield",
            "test",
            all_skills=2,
            fcr=34,
            fhr=55,
            lr=35,
            cr=35,
            pr=35,
            req_str=156,
        ),
        ItemSpec("Tiara", "helm", "test", class_skills=2, fr=40, lr=40, cr=50, pr=40),
        ItemSpec("Skullder's", "armor", "test", all_skills=1, mf=111, req_str=97),
        ItemSpec("Amulet", "amulet", "test", fcr=20, fr=30, lr=30, cr=30),
        ItemSpec("Tal's Belt", "belt", "test", mf=15, dex_bonus=20),
        ItemSpec("Trang-Oul's", "gloves", "test", fcr=20, cr=30),
        ItemSpec("Aldur's", "boots", "test", frw=40, fr=48),
        ItemSpec("Ring A", "ring", "test", fcr=10, lr=20, fr=20),
        ItemSpec("Ring B", "ring", "test", fcr=10, lr=20, fr=20),
    ]
    # 25 base Dex + 20 Tal's Belt = 45 >= 42 -> Ali Baba is equippable
    res_ok = optimize_builds(
        items,
        [],
        BuildConstraints(
            allow_mf=True,
            min_fcr=63,
            min_fhr=42,
            mode="mf",
            character=CharacterStats(base_str=156, base_dex=25, base_hell_res=-70),
        ),
    )
    assert res_ok[0].items[0].name == "Ali Baba"

    # 20 base Dex + 20 Tal's Belt = 40 < 42 -> Ali Baba excluded even with self +15 Dex
    res_low = optimize_builds(
        items,
        [],
        BuildConstraints(
            allow_mf=True,
            min_fcr=63,
            min_fhr=42,
            mode="mf",
            character=CharacterStats(base_str=156, base_dex=20, base_hell_res=-70),
        ),
    )
    assert res_low[0].items[0].name == "Spirit Sword"


@requires_native
def test_optimize_builds_from_fixtures(
    parsed_sork: D2SStruct,
    parsed_mule_unique: D2SStruct,
    parsed_shared_stash: SharedStash,
    game_data_resolver: GameDataResolver,
) -> None:
    resolver = game_data_resolver
    sork = parsed_sork
    mule = parsed_mule_unique
    stash = parsed_shared_stash

    items, charms = extract_pool(sork, extra_chars=[mule], stashes=[stash], resolver=resolver)
    assert len(items) > 10
    assert any(it.slot == "weapon" for it in items)
    assert any(it.slot == "shield" for it in items)
    assert len(charms) > 0

    presets = select_sorc_presets(sork, max_charm_slots=23)
    assert len(presets) == 5
    assert len(select_sorc_presets(sork, build="base")) == 1
    assert len(select_sorc_presets(sork, build="mf")) == 2
    assert len(select_sorc_presets(sork, build="tz")) == 1
    max_res_presets = select_sorc_presets(sork, build="max-res")
    assert len(max_res_presets) == 1
    assert max_res_presets[0][1].mode == "max-res"
    with pytest.raises(ValueError, match="Unknown build preset"):
        select_sorc_presets(sork, build="unknown")
    with pytest.raises(ValueError, match="expected Sorceress"):
        select_sorc_presets(mule)
    # Fixture sork may not have all items from later saves, so test relaxed constraints on fixtures
    relaxed = BuildConstraints(
        allow_mf=True,
        min_fcr=63,
        min_fhr=42,
        min_fr=50,
        min_lr=50,
        min_cr=50,
        min_pr=0,
        max_charm_slots=23,
        mode="power",
        limit=2,
        character=CharacterStats(
            base_life=sork.player_stats.max_life,
            base_mana=sork.player_stats.max_mana,
            base_hell_res=-70,
        ),
    )
    results = optimize_builds(items, charms, relaxed)
    assert len(results) >= 1
    assert results[0].fcr >= 63
    assert results[0].fhr >= 42
    report = format_build_report("Fixture Test", results, charms)
    assert "pruned sets):" in report
    assert "Rust/PyO3" not in report
    assert "      - remove:" in report
    assert "      - keep  :" in report
    assert "      - add   :" in report


@requires_native
def test_cli_optimize_fixtures(capsys: pytest.CaptureFixture[str]) -> None:
    main(
        [
            "optimize",
            "--no-config",
            "--char",
            "sork",
            str(FIXTURES_DIR),
        ]
    )
    captured = capsys.readouterr()
    assert "0% MF Base Hunting" in captured.out
    assert "Max Power & Terror Zones" in captured.out
    assert "Max Resist" in captured.out


@requires_native
def test_cli_optimize_positional_name_and_build_flag(capsys: pytest.CaptureFixture[str]) -> None:
    main(
        [
            "optimize",
            "--no-config",
            "sork",
            str(FIXTURES_DIR),
            "-b",
            "tz",
        ]
    )
    captured = capsys.readouterr()
    assert "Max Power & Terror Zones" in captured.out
    assert "0% MF Base Hunting" not in captured.out
    assert "Max MF & Boss Farm" not in captured.out

    main(["optimize", "--no-config", "sork", str(FIXTURES_DIR), "-b", "max-res"])
    captured_res = capsys.readouterr()
    assert "4. Max Resist" in captured_res.out
    assert "Max Power & Terror Zones" not in captured_res.out


def test_cli_optimize_class_validation_and_avoids_hardcoded_default(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit) as exc_ambiguous:
        main(["optimize", "--no-config", str(FIXTURES_DIR)])
    assert exc_ambiguous.value.code == 1
    assert "Multiple optimizable characters" in capsys.readouterr().err

    with pytest.raises(SystemExit) as exc_sorc_ambiguous:
        main(["optimize", "--no-config", str(FIXTURES_DIR), "-b", "tz"])
    assert exc_sorc_ambiguous.value.code == 1
    assert "Multiple Sorceress characters" in capsys.readouterr().err

    with pytest.raises(SystemExit) as exc_pal_pres_on_sorc:
        main(["optimize", "--no-config", "sork", str(FIXTURES_DIR), "-b", "leveling"])
    assert exc_pal_pres_on_sorc.value.code == 1
    assert "only supported for Paladin" in capsys.readouterr().err

    with pytest.raises(SystemExit) as exc_sorc_pres_on_pal:
        main(["optimize", "--no-config", "mule_unique", str(FIXTURES_DIR), "-b", "tz"])
    assert exc_sorc_pres_on_pal.value.code == 1
    assert "only supported for Sorceress" in capsys.readouterr().err

    # Unsupported class (e.g. Barbarian = 4) fails cleanly with expected Sorceress or Paladin
    raw = bytearray((FIXTURES_DIR / "mule_unique.d2s").read_bytes())
    raw[0x18] = 4
    barb_path = tmp_path / "mule_unique.d2s"
    barb_path.write_bytes(raw)
    with pytest.raises(SystemExit) as exc_non_supported:
        main(["optimize", "--no-config", str(barb_path)])
    assert exc_non_supported.value.code == 1
    assert "expected Sorceress or Paladin" in capsys.readouterr().err


def test_cli_optimize_missing_native_extension_prints_clean_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty_report = format_build_report("Empty", [])
    assert "No loadout found matching all constraints." in empty_report

    monkeypatch.setattr("d2savior.optimizer.extract_props.ItemSpec", _missing_native)
    monkeypatch.setattr("d2savior.optimizer.common.BuildConstraints", _missing_native)
    with pytest.raises(SystemExit) as exc:
        main(["optimize", "--no-config", "sork", str(FIXTURES_DIR)])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "d2savior[optimize]" in err
    assert "make build-rust" in err


def test_item_level_requirements_uniques_sets_runewords(
    parsed_sork: D2SStruct,
    parsed_mule_unique: D2SStruct,
    game_data_resolver: GameDataResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    d2r = game_data_resolver.for_version(0x63)

    griff = d2r.get_unique_item(336)
    assert griff is not None
    assert griff.levelreq == 76

    tal_amu = d2r.get_set_item(77)
    assert tal_amu is not None
    assert tal_amu.levelreq == 67

    sork = parsed_sork
    mule = parsed_mule_unique

    # Stealth (Tal 17 + Eth 15) in Studded Leather (base req 0) -> levelreq 17
    stealth = next(it for it in sork.item_list.items if it.code_str.strip() == "stu")
    assert item_levelreq(stealth, d2r) == 17
    assert item_to_spec(stealth, "test", d2r, 0x63, char_level=16) is None

    # The Oculus (base Swirling Crystal 37, unique 284 -> levelreq 42)
    oculus = next(it for it in mule.item_list.items if it.code_str.strip() == "oba")
    assert item_levelreq(oculus, d2r) == 42
    assert item_to_spec(oculus, "test", d2r, 0x63, char_level=41) is None
    if HAS_NATIVE:
        assert item_to_spec(oculus, "test", d2r, 0x63, char_level=42) is not None

    # Set amulet (base req 0, simulated Tal Rasha's Adjudication set_id=77 -> levelreq 67)
    amu = next(it for it in sork.item_list.items if it.code_str.strip() == "amu")
    assert amu.item_info is not None
    assert amu.item_info.ext_info is not None
    monkeypatch.setattr(amu.item_info.ext_info, "magic_prefix", None)
    monkeypatch.setattr(amu.item_info.ext_info, "magic_suffix", None)
    monkeypatch.setattr(amu.item_info.ext_info, "set_id", 77)
    assert item_levelreq(amu, d2r) == 67
    assert item_to_spec(amu, "test", d2r, 0x63, char_level=66) is None


def test_extract_prop_acc_per_level_and_cold_tab(
    parsed_sork: D2SStruct,
    game_data_resolver: GameDataResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = game_data_resolver.for_version(0x63)
    dummy_item = parsed_sork.item_list.items[0]

    fake_props = [
        (216, 12 << 8, [12, 0, 0, 0]),  # Shako +1.5 Life/lvl (val_shift=8, op_param=3)
        (217, 12 << 8, [12, 0, 0, 0]),  # Shako +1.5 Mana/lvl
        (240, 10, [10, 0, 0, 0]),  # Skullder +1.25 MF/lvl
        (188, 0, [2, 1, 1]),  # +1 Cold Skills (Sorc tab 2)
    ]
    monkeypatch.setattr(
        "d2savior.optimizer.extract.collect_item_properties", lambda *a, **kw: fake_props
    )

    acc = _extract_prop_acc(dummy_item, resolver, version=0x63, char_level=89)
    assert acc.life_per_lvl == (12 * 89) >> 3
    assert acc.mana_per_lvl == (12 * 89) >> 3
    assert acc.life == 0
    assert acc.mana == 0
    assert acc.mf == (10 * 89) >> 3
    assert acc.class_skills == 1


@requires_native
def test_item_to_spec_keeps_frw_mdr_fire_absorb_and_max_res(
    parsed_mule_unique: D2SStruct,
    game_data_resolver: GameDataResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = game_data_resolver.for_version(0x63)
    mule = parsed_mule_unique
    # Pick a high-level-usable item that classifies to a slot (e.g. a ring, boot, belt, or sword)
    boot_or_ring = next(
        it
        for it in mule.item_list.items
        if item_to_spec(it, "test", resolver, 0x63, 99) is not None
    )

    for pid, attr, expected in (
        (96, "frw", 30),
        (35, "mdr", 15),
        (142, "fire_abs_pct", 15),
        (40, "max_fr", 15),
    ):
        monkeypatch.setattr(
            "d2savior.optimizer.extract.collect_item_properties",
            lambda *_a, _pid=pid, _val=expected, **_kw: [(_pid, _val, [_val])],
        )
        spec = item_to_spec(boot_or_ring, "test", resolver, 0x63, char_level=99)
        assert isinstance(spec, ItemSpec)
        assert getattr(spec, attr) == expected

    # An item with no useful stats at all is still dropped
    monkeypatch.setattr(
        "d2savior.optimizer.extract.collect_item_properties",
        lambda *_a, **_kw: [(16, 100, [100])],  # +100% enhanced defense only
    )
    assert item_to_spec(boot_or_ring, "test", resolver, 0x63, char_level=99) is None

    # Sorceress items with %PDR (pid 36) and CBF (pid 153) satisfy --cbf and --min-pdr floors.
    helm_it = next(
        it
        for it in mule.item_list.items
        if (_cls := classify_slot(it, resolver, char_class=1)) is not None and _cls[0] == "helm"
    )
    ring_it = next(
        it
        for it in mule.item_list.items
        if (_cls := classify_slot(it, resolver, char_class=1)) is not None and _cls[0] == "ring"
    )
    monkeypatch.setattr(
        "d2savior.optimizer.extract.collect_item_properties",
        lambda it, **_kw: [(36, 10, [10])] if it is helm_it else [(153, 1, [1])],
    )
    helm_spec = item_to_spec(
        helm_it, "test", resolver, 0x63, char_level=99, char_class=int(CharClass.SORCERESS)
    )
    ring_spec = item_to_spec(
        ring_it, "test", resolver, 0x63, char_level=99, char_class=int(CharClass.SORCERESS)
    )
    assert isinstance(helm_spec, ItemSpec)
    assert helm_spec.pdr_pct == 10
    assert isinstance(ring_spec, ItemSpec)
    assert ring_spec.cbf == 1
    sorc_res = optimize_builds(
        [helm_spec, ring_spec],
        [],
        BuildConstraints(
            min_fcr=0,
            min_fhr=0,
            min_fr=0,
            min_lr=0,
            min_cr=0,
            min_pr=0,
            require_cbf=True,
            min_pdr=10,
            character=CharacterStats(
                char_class=int(CharClass.SORCERESS),
                base_hell_res=0,
                base_str=200,
                base_dex=200,
            ),
        ),
    )
    assert len(sorc_res) == 1
    assert sorc_res[0].cbf is True
    assert sorc_res[0].pdr_pct >= 10


@requires_native
def test_max_resistance_cap_in_evaluate_and_optimize() -> None:
    items = [
        ItemSpec("Spirit Sword", "weapon", "test", all_skills=2, fcr=34, fhr=55),
        ItemSpec(
            "Spirit Shield", "shield", "test", all_skills=2, fcr=34, fhr=55, lr=35, cr=35, pr=35
        ),
        ItemSpec("Tiara", "helm", "test", class_skills=2, fr=40, lr=40, cr=40, pr=40),
        ItemSpec("Guardian Angel", "armor", "test", max_fr=15, max_lr=15, max_cr=15, max_pr=15),
        ItemSpec("Amulet", "amulet", "test", class_skills=1, fcr=10, fr=30, lr=30, cr=30, pr=30),
        ItemSpec("Belt", "belt", "test", fcr=10, fr=20),
        ItemSpec("Magefist", "gloves", "test", fcr=20, fr=30),
        ItemSpec("Hotspur", "boots", "test", fr=45, max_fr=15),
        ItemSpec("Ring A", "ring", "test", fcr=10, fr=20, lr=20, cr=20, pr=20),
        ItemSpec("Ring B", "ring", "test", fr=20, lr=20, cr=20, pr=20),
    ]
    res = evaluate_build(items, [], base_hell_res=-70)
    assert (res.max_fr, res.max_lr, res.max_cr, res.max_pr) == (95, 90, 90, 90)
    assert res.fr == 95
    assert res.lr == 75
    opt = optimize_builds(
        items,
        [CharmSpec("Amber SC", 1, "test", lr=11)],
        BuildConstraints(
            allow_mf=True,
            min_fcr=105,
            min_fhr=86,
            min_fr=90,
            min_lr=85,
            min_cr=75,
            min_pr=0,
            mode="power",
            character=CharacterStats(base_hell_res=-70),
        ),
    )
    assert len(opt) == 1
    assert opt[0].fr == 95
    assert opt[0].lr == 86

    # max-res mode picks +max-res armor over +skills armor and tops up res with charms
    max_res_items = [
        *items,
        ItemSpec("Chains of Honor", "armor", "test", all_skills=2, fr=65, lr=65, cr=65, pr=65),
    ]
    res_max = optimize_builds(
        max_res_items,
        [CharmSpec("Amber SC", 1, "test", lr=11), CharmSpec("Chilling GC", 3, "test", skills=1)],
        BuildConstraints(
            allow_mf=True,
            min_fcr=105,
            min_fhr=86,
            min_fr=75,
            min_lr=75,
            min_cr=75,
            min_pr=0,
            mode="max-res",
            character=CharacterStats(base_hell_res=-70),
        ),
    )
    assert res_max[0].items[3].name == "Guardian Angel"
    assert res_max[0].fr == 95
    assert res_max[0].lr == 86


def test_classify_slot_tags_two_handed_and_1or2handed_weapons_as_weapon2h() -> None:
    resolver = GameDataResolver.load().for_version(0x63)

    def _make_item(code: str) -> D2Item:
        it = D2Item()
        it.type_name = code.ljust(4).encode("ascii")
        return it

    bax_info = resolver.data.get_item("bax")
    assert bax_info is not None
    assert bax_info.two_handed
    assert not bax_info.one_or_two_handed
    hs2_info = resolver.data.get_item("2hs")
    assert hs2_info is not None
    assert hs2_info.one_or_two_handed
    mau_info = resolver.data.get_item("mau")
    assert mau_info is not None
    assert mau_info.two_handed

    for two_handed_code in ("bax", "2hs", "mau", "sst"):
        classified = classify_slot(_make_item(two_handed_code), resolver)
        assert classified is not None
        assert classified[0] == "weapon2h"

    for one_handed_code in ("crs", "ob1"):
        classified = classify_slot(_make_item(one_handed_code), resolver)
        assert classified is not None
        assert classified[0] == "weapon"

    # Paladin allows auric shields (pa1) and rejects Sorceress orbs (ob1); Sorceress does the opposite
    assert classify_slot(_make_item("pa1"), resolver, char_class=1) is None
    assert classify_slot(_make_item("pa1"), resolver, char_class=3) == ("shield", 16, 0)
    assert classify_slot(_make_item("ob1"), resolver, char_class=3) is None


@requires_native
def test_unique_charm_limit_prevents_duplicates() -> None:
    items = [
        ItemSpec("Spirit Sword", "weapon", "test", all_skills=2, fcr=35, fhr=55),
        ItemSpec(
            "Spirit Shield", "shield", "test", all_skills=2, fcr=35, fhr=55, lr=35, cr=35, pr=35
        ),
        ItemSpec("Tiara", "helm", "test", class_skills=2, fcr=20, fr=40, lr=40, cr=40, pr=40),
        ItemSpec("Skin", "armor", "test", all_skills=1, fcr=30, fr=35, lr=35, cr=35, pr=35),
        ItemSpec("Amulet", "amulet", "test", class_skills=2, fcr=15, fr=30, lr=30, cr=30, pr=30),
        ItemSpec("Belt", "belt", "test", fr=20, lr=20, cr=20, pr=20),
        ItemSpec("Trangs", "gloves", "test", fcr=20, cr=30),
        ItemSpec("Boots", "boots", "test", fr=20, lr=20, cr=20, pr=20),
        ItemSpec("Ring A", "ring", "test", fcr=10, fr=20, lr=20, cr=20, pr=20),
        ItemSpec("Ring B", "ring", "test", fcr=10, fr=20, lr=20, cr=20, pr=20),
    ]
    charms = [
        CharmSpec(
            "Hellfire Torch A",
            2,
            "inv",
            fr=20,
            lr=20,
            cr=20,
            pr=20,
            str_bonus=20,
            skills=3,
            unique_id=400,
        ),
        CharmSpec(
            "Hellfire Torch B",
            2,
            "stash",
            fr=20,
            lr=20,
            cr=20,
            pr=20,
            str_bonus=20,
            skills=3,
            unique_id=400,
        ),
        CharmSpec("Chilling GC", 3, "stash", skills=1),
    ]
    res = optimize_builds(
        items,
        charms,
        BuildConstraints(
            allow_mf=True,
            min_fcr=105,
            min_fhr=86,
            min_fr=75,
            min_lr=75,
            min_cr=75,
            min_pr=75,
            mode="power",
            character=CharacterStats(base_hell_res=-70),
        ),
    )
    assert len(res) == 1
    assert sum(1 for c in res[0].charms if c.unique_id == 400) == 1
    assert any(c.name == "Chilling GC" for c in res[0].charms)


@requires_native
def test_bo_scales_flat_life_mana_not_per_lvl_or_vit_ene() -> None:
    shako = ItemSpec(
        "Harlequin Crest",
        "helm",
        "test",
        all_skills=2,
        life=50,
        mana=40,
        vit=10,
        ene=15,
        pct_mana=25,
        life_per_lvl=133,
        mana_per_lvl=133,
    )
    charm = CharmSpec("Life/Mana SC", 1, "inv", life=20, mana=17)
    res = evaluate_build([shako], [charm], base_life=500, base_mana=200, bo_base_bonus=4)
    # bo_lvl=6 -> 50% BO: (500 + 50 + 20) * 1.5 + 10*2 + 133 = 855 + 20 + 133 = 1008
    # mana: (200 + 40 + 17) * (1 + 0.75) + 15*2 + 133 = 449 + 30 + 133 = 612
    assert res.bo_lvl == 6
    assert res.life_no_bo == 500 + 50 + 133 + 20 + 20
    assert res.life_bo == 1008
    assert res.mana_bo == 612


@requires_native
def test_blizzard_base_skills_from_save_and_fallback(
    parsed_sork: D2SStruct,
    game_data_resolver: GameDataResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = game_data_resolver
    sork = parsed_sork

    presets = select_sorc_presets(sork, build="tz")
    _, c = presets[0]
    caster_skills = c.skills
    assert isinstance(caster_skills, CasterSkillModel)
    # sork.d2s has Blizzard=20 (idx 23), Ice Bolt=1 (idx 3), Ice Blast=14 (idx 9), Glacial Spike=20 (idx 19), Cold Mastery=20 (idx 29)
    assert (
        caster_skills.blizz_base_lvl,
        caster_skills.blizz_syn_pts,
        caster_skills.cm_base_lvl,
    ) == (
        20,
        35,
        20,
    )

    _, syn_default, _ = blizzard_damage(5)
    _, syn_custom, cm_custom = blizzard_damage_with_base(5, 20, 35, 20)
    assert syn_custom < syn_default
    assert cm_custom == -(20 + 5 * (25 - 1))

    # sork.d2s is Nightmare (diff=1 -> -40) with Normal+NM Anya (+20) => -20, and no CTA
    assert c.character.base_hell_res == -20
    assert c.character.bo_base_bonus == 0
    assert c.character.use_bo is False

    # When Blizzard has 0 hard points, hard synergy & Cold Mastery points are preserved for staffmod +Blizzard orbs
    assert sork.skills is not None
    skills = list(sork.skills.skill_levels)
    skills[23] = 0
    monkeypatch.setattr(sork.skills, "skill_levels", skills)
    fallback_c = select_sorc_presets(sork, build="tz")[0][1]
    assert isinstance(fallback_c.skills, CasterSkillModel)
    assert (
        fallback_c.skills.blizz_base_lvl,
        fallback_c.skills.blizz_syn_pts,
        fallback_c.skills.cm_base_lvl,
    ) == (
        0,
        35,
        20,
    )

    # Low-level Normal Sorc (Sorc.d2s, lvl 17, 0 Blizzard): Normal res penalty (0) & max_level filters high CTA
    norm_sorc, _ = load_d2s(FIXTURES_DIR / "Sorc.d2s", resolver=resolver)
    norm_c = select_sorc_presets(norm_sorc, build="tz", resolver=resolver)[0][1]
    assert norm_c.character.base_hell_res == 0
    assert isinstance(norm_c.skills, CasterSkillModel)
    assert (
        norm_c.skills.blizz_base_lvl,
        norm_c.skills.blizz_syn_pts,
        norm_c.skills.cm_base_lvl,
    ) == (
        0,
        0,
        0,
    )
    assert norm_c.character.bo_base_bonus == 0
    assert norm_c.character.use_bo is False

    # High-level CTA (lvlreq 57) is ignored for lvl 17 Sorc because max_level=char_level
    high_cta = norm_sorc.item_list.items[0]
    cta_ptr = id(high_cta)
    monkeypatch.setattr(
        "d2savior.optimizer.common.item_levelreq", lambda it, _res: 57 if id(it) == cta_ptr else 1
    )
    monkeypatch.setattr(
        "d2savior.optimizer.common.collect_item_properties",
        lambda it, **_kw: [(127, 1, [1]), (97, 0, [149, 6])] if id(it) == cta_ptr else [],
    )
    norm_cta_c = select_sorc_presets(norm_sorc, build="tz", resolver=resolver)[0][1]
    assert norm_cta_c.character.bo_base_bonus == 0
    assert norm_cta_c.character.use_bo is False


@requires_native
def test_single_skill_blizzard_orb_extraction_and_ranking(
    parsed_mule_unique: D2SStruct,
    game_data_resolver: GameDataResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = game_data_resolver.for_version(0x63)
    mule = parsed_mule_unique
    orb = next(it for it in mule.item_list.items if it.code_str.strip() == "oba")

    monkeypatch.setattr(
        "d2savior.optimizer.extract.collect_item_properties",
        lambda *_a, **_kw: [(83, 0, [1, 2]), (107, 0, [59, 3]), (107, 0, [65, 1])],
    )
    orb_spec = item_to_spec(orb, "test", resolver, 0x63, char_level=99)
    assert isinstance(orb_spec, ItemSpec)
    assert orb_spec.class_skills == 2
    assert orb_spec.blizz_skills == 3
    assert orb_spec.cm_skills == 1

    items = [
        ItemSpec(
            "Sorc +3 Orb", "weapon", "test", class_skills=3, fcr=30, fr=20, lr=20, cr=20, pr=20
        ),
        ItemSpec(
            "Sorc +2/+3 Blizz Orb",
            "weapon",
            "test",
            class_skills=2,
            blizz_skills=3,
            cm_skills=1,
            fcr=30,
            fr=20,
            lr=20,
            cr=20,
            pr=20,
        ),
        ItemSpec(
            "Spirit Shield", "shield", "test", all_skills=2, fcr=35, fhr=55, lr=35, cr=35, pr=35
        ),
        ItemSpec(
            "Tiara", "helm", "test", class_skills=2, fcr=20, fhr=20, fr=30, lr=30, cr=30, pr=30
        ),
        ItemSpec(
            "Armor", "armor", "test", all_skills=1, fcr=20, fhr=20, fr=40, lr=40, cr=40, pr=40
        ),
        ItemSpec("Amulet", "amulet", "test", class_skills=2, fcr=10, fr=30, lr=30, cr=30, pr=30),
        ItemSpec("Belt", "belt", "test", fr=30, lr=30, cr=30, pr=30),
        ItemSpec("Trangs", "gloves", "test", fcr=20, fr=30, lr=30, cr=30, pr=30),
        ItemSpec("Boots", "boots", "test", fr=40, lr=40, cr=40, pr=40),
        ItemSpec("Ring A", "ring", "test", fcr=10, fr=20, lr=20, cr=20, pr=20),
        ItemSpec("Ring B", "ring", "test", fcr=10, fr=20, lr=20, cr=20, pr=20),
    ]
    res = optimize_builds(
        items,
        [],
        BuildConstraints(min_pr=75, limit=2, character=CharacterStats(base_hell_res=-70)),
    )
    assert len(res) == 2
    assert res[0].items[0].name == "Sorc +2/+3 Blizz Orb"
    assert res[1].items[0].name == "Sorc +3 Orb"
    assert res[0].blizz_avg > res[1].blizz_avg


@requires_native
def test_detect_cta_bo_bonus_and_excludes_swap_cta(
    game_data_resolver: GameDataResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = game_data_resolver
    sork, _ = load_d2s(FIXTURES_DIR / "sork.d2s", resolver=resolver)
    # Default fallback when no CTA is present
    assert detect_cta_bo_bonus([sork], [], resolver) == 4

    cta_item = sork.item_list.items[0]
    cta_item.location = ItemLocation.EQUIPPED
    cta_item.position = EquipSlot.WEAPON_II
    cta_id = id(cta_item)
    swap_shield = sork.item_list.items[1]
    swap_shield.location = ItemLocation.EQUIPPED
    swap_shield.position = EquipSlot.SHIELD_II

    def _fake_props(item: D2Item, **_kw: object) -> list[tuple[int, int, list[int]]]:
        if id(item) == cta_id:
            return [(127, 1, [1]), (97, 0, [149, 6])]  # +1 All Skills, +6 Battle Orders
        return [(127, 2, [2])]

    monkeypatch.setattr("d2savior.optimizer.common.collect_item_properties", _fake_props)
    monkeypatch.setattr("d2savior.optimizer.extract.collect_item_properties", _fake_props)
    assert detect_cta_bo_bonus([sork], [], resolver) == 7
    presets = select_sorc_presets(sork, build="tz", resolver=resolver)
    assert presets[0][1].character.bo_base_bonus == 7

    items, _ = extract_pool(sork, resolver=resolver)
    assert not any("Swap" in it.loc for it in items)

    # When weapon_set == 1, WEAPON_I/SHIELD_I are the swap set and WEAPON_II is active Equipped.
    sork.weapon_set = 1
    cta_item.position = EquipSlot.WEAPON_I
    swap_shield.position = EquipSlot.SHIELD_I
    active_w2 = sork.item_list.items[2]
    active_w2.location = ItemLocation.EQUIPPED
    active_w2.position = EquipSlot.WEAPON_II
    items_w2, _ = extract_pool(sork, resolver=resolver)
    assert not any("Swap" in it.loc for it in items_w2)
    assert any(it.loc == "sork Equipped" and it.slot in ("weapon", "weapon2h") for it in items_w2)


@requires_native
def test_belt_slots_and_defense_prefer_upped_goldwrap(
    parsed_sork: D2SStruct,
    parsed_mule_unique: D2SStruct,
    game_data_resolver: GameDataResolver,
) -> None:
    resolver = game_data_resolver
    sork = parsed_sork
    mule = parsed_mule_unique

    items, _ = extract_pool(sork, extra_chars=[mule], resolver=resolver)
    belts = [it for it in items if it.slot == "belt"]
    assert any(b.belt_slots == 12 and b.defense > 0 for b in belts)
    assert any(b.belt_slots == 16 and b.defense > 0 for b in belts)
    assert any(it.slot != "belt" and it.defense > 0 and it.belt_slots == 0 for it in items)

    upped = ItemSpec(
        "Goldwrap (Battle Belt)", "belt", "sork Stash", mf=30, req_str=88, defense=89, belt_slots=16
    )
    non_upped = ItemSpec(
        "Goldwrap (Heavy Belt)",
        "belt",
        "mule_unique Inv",
        mf=30,
        req_str=45,
        defense=35,
        belt_slots=12,
    )
    pool = [
        ItemSpec("Spirit Sword", "weapon", "test", all_skills=2, fcr=35, fhr=55),
        ItemSpec(
            "Spirit Shield",
            "shield",
            "test",
            all_skills=2,
            fcr=35,
            fhr=55,
            lr=35,
            cr=35,
            pr=35,
            req_str=156,
        ),
        ItemSpec("Helm", "helm", "test", class_skills=2, fcr=20, fr=40, lr=40, cr=40),
        ItemSpec("Skullder", "armor", "test", all_skills=1, mf=110),
        ItemSpec("Amulet", "amulet", "test", class_skills=2, fcr=15, fr=30, lr=30, cr=30),
        non_upped,
        upped,
        ItemSpec("Trangs", "gloves", "test", fcr=20, cr=30),
        ItemSpec("Boots", "boots", "test", fr=45, lr=20, cr=20, pr=40),
        ItemSpec("Ring A", "ring", "test", fcr=10, fr=20, lr=20, cr=20),
        ItemSpec("Ring B", "ring", "test", fcr=10, fr=20, lr=20, cr=20),
    ]
    res = optimize_builds(
        pool,
        [],
        BuildConstraints(
            mode="mf",
            min_fcr=105,
            min_fhr=60,
            min_pr=0,
            limit=2,
            character=CharacterStats(base_str=156, base_hell_res=-70),
        ),
    )
    assert len(res) == 2
    assert res[0].items[5].name == "Goldwrap (Battle Belt)"
    assert res[0].items[5].loc == "sork Stash"


@requires_native
def test_cold_sunder_charm_extraction_and_optimizer_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace
    from typing import cast

    import d2savior.optimizer.extract as extract_mod

    resolver = GameDataResolver.load()
    ext_ns = SimpleNamespace(
        unique_id=401,
        set_id=None,
        magic_prefix=0,
        magic_suffix=0,
        rare_name=None,
        craft_name=None,
        rune_id=0,
    )
    dummy_item = cast(
        D2Item,
        SimpleNamespace(
            location=ItemLocation.STORED,
            code_str="cm3",
            is_runeword=False,
            gem_items=(),
            type_specific_info=None,
            ext_info=ext_ns,
            item_info=SimpleNamespace(ext_info=ext_ns),
        ),
    )
    monkeypatch.setattr(extract_mod, "get_item_display_name", lambda *_a, **_kw: "Cold Rupture")
    monkeypatch.setattr(
        extract_mod,
        "collect_item_properties",
        lambda *_a, **_kw: [(187, 1, ()), (43, -75, ())],
    )
    spec = item_to_spec(dummy_item, "sork Inv", resolver, 105, 85)
    assert isinstance(spec, CharmSpec)
    assert spec.cold_sunder is True
    assert spec.cr == -75
    assert spec.size == 3
    assert spec.unique_id == 401

    pool = [
        ItemSpec("Hoto", "weapon", "test", all_skills=3, fcr=40),
        ItemSpec("Spirit Shield", "shield", "test", all_skills=2, fcr=35, fhr=60),
        ItemSpec("CoH", "armor", "test", all_skills=2, fcr=30, fr=150, lr=150, cr=150, pr=150),
    ]
    charms = [spec]

    res_pow = optimize_builds(
        pool,
        charms,
        BuildConstraints(
            mode="power",
            min_fcr=105,
            min_fhr=60,
            min_fr=75,
            min_lr=75,
            min_cr=75,
            min_pr=75,
            limit=1,
            character=CharacterStats(base_hell_res=-70),
        ),
    )
    assert len(res_pow) == 1
    assert any(c.cold_sunder and c.name == "Cold Rupture" for c in res_pow[0].charms)
    assert res_pow[0].cr == 5

    res_max = optimize_builds(
        pool,
        charms,
        BuildConstraints(
            mode="max-res",
            min_fcr=105,
            min_fhr=60,
            min_fr=75,
            min_lr=75,
            min_cr=75,
            min_pr=75,
            limit=1,
            character=CharacterStats(base_hell_res=-70),
        ),
    )
    assert len(res_max) == 1
    assert not any(c.cold_sunder for c in res_max[0].charms)
    assert res_max[0].cr == 75


@requires_native
def test_format_build_report_charm_diff_and_inventory_order(
    parsed_sork: D2SStruct,
    game_data_resolver: GameDataResolver,
) -> None:
    inv_vita_1 = CharmSpec("Small Charm of Vita", 1, "sork Inv", life=20)
    inv_vita_2 = CharmSpec("Small Charm of Vita", 1, "sork Inv", life=20)
    inv_drop = CharmSpec("Azure Grand Charm", 3, "sork Inv", cr=8)
    inv_keep_tail = CharmSpec("Crimson Grand Charm", 3, "sork Inv", fr=12)
    stash_charm = CharmSpec("Small Charm of Good Luck", 1, "Stash Tab 5", mf=7)

    pool_charms = [inv_vita_1, inv_drop, inv_vita_2, inv_keep_tail, stash_charm]
    # Selected order differs from inventory order and includes only 1 of 2 identical inv_vita copies
    selected = [inv_keep_tail, stash_charm, inv_vita_2]
    res = evaluate_build([], selected)

    report = format_build_report("Charm Diff", [res], pool_charms)
    assert "    - Charms  :" in report
    assert "      - remove: Azure Grand Charm, Small Charm of Vita" in report
    assert "      - keep  : Small Charm of Vita, Crimson Grand Charm" in report
    assert "      - add   : Small Charm of Good Luck [Stash Tab 5]" in report

    # Fallback when charms pool is omitted: inventory charms stay in keep, others in add, remove is none
    report_no_pool = format_build_report("No Pool", [res])
    assert "      - remove: none" in report_no_pool
    assert "      - keep  : Crimson Grand Charm, Small Charm of Vita" in report_no_pool
    assert "      - add   : Small Charm of Good Luck [Stash Tab 5]" in report_no_pool

    # extract_pool orders character inventory charms by (column, row)
    resolver = game_data_resolver
    sork = parsed_sork
    _, extracted_charms = extract_pool(sork, resolver=resolver)
    inv_names = [c.name for c in extracted_charms if c.loc == "sork Inv"]
    assert inv_names == [
        "Russet Grand Charm",
        "Jade Small Charm",
        "Tangerine Grand Charm",
        "Ocher Small Charm of Sustenance",
        "Azure Grand Charm",
        "Ocher Small Charm",
        "Serpent's Large Charm of Inertia",
        "Ocher Large Charm of Life",
        "Crimson Grand Charm",
    ]


def test_paladin_prop_extraction_and_detect_spec(
    parsed_mule_unique: D2SStruct,
    game_data_resolver: GameDataResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert PALADIN_BUILD_CHOICES == ("leveling",)
    for legacy_spec in ("holy-fire", "hammer", "foh", "smite"):
        assert legacy_spec not in BUILD_CHOICES

    d2r = game_data_resolver.for_version(0x63)
    mule = parsed_mule_unique
    assert detect_paladin_spec(mule) == "leveling"

    assert mule.skills is not None
    skills = [0] * 30
    monkeypatch.setattr(mule.skills, "skill_levels", skills)
    skills[6] = 20  # Holy Fire
    assert detect_paladin_spec(mule) == "holy-fire"
    skills[:] = [0] * 30
    skills[16] = 20  # Blessed Hammer
    assert detect_paladin_spec(mule) == "hammer"
    skills[:] = [0] * 30
    skills[25] = 20  # Fist of the Heavens
    assert detect_paladin_spec(mule) == "foh"
    skills[:] = [0] * 30
    skills[5] = 20  # Holy Bolt
    assert detect_paladin_spec(mule) == "holy-bolt"
    skills[:] = [0] * 30
    skills[1] = 20  # Smite
    assert detect_paladin_spec(mule) == "smite"
    skills[:] = [0] * 30
    skills[10] = 20  # Zeal (+ 20 Fanaticism + 1 Smite -> still "zeal")
    skills[26] = 20
    skills[1] = 1
    assert detect_paladin_spec(mule) == "zeal"
    skills[:] = [0] * 30
    skills[15] = 20  # Vengeance
    assert detect_paladin_spec(mule) == "vengeance"
    skills[:] = [0] * 30
    skills[11] = 20  # Charge
    assert detect_paladin_spec(mule) == "charge"

    dummy_item = next(
        it for it in mule.item_list.items if classify_slot(it, d2r, char_class=3) is not None
    )
    fake_props = [
        (83, 0, [3, 2]),  # +2 Paladin Skills
        (188, 0, [1, 3, 1]),  # +1 Offensive Auras (tab 1)
        (188, 0, [0, 3, 1]),  # +1 Combat Skills (tab 0)
        (126, 0, [1, 1]),  # +1 Fire Skills (Magefist -> Holy Fire only)
        (107, 0, [102, 6]),  # +6 Holy Fire
        (93, 20, [20]),  # +20% IAS
        (136, 25, [25]),  # 25% Crushing Blow
        (153, 1, [1]),  # Cannot Be Frozen
        (36, 15, [15]),  # 15% PDR
        (60, 7, [7]),  # 7% Life Leech
    ]
    monkeypatch.setattr(
        "d2savior.optimizer.extract.collect_item_properties", lambda *a, **kw: fake_props
    )

    hf_acc = _extract_prop_acc(dummy_item, d2r, 0x63, 29, char_class=3, pal_spec="holy-fire")
    assert hf_acc.class_skills == 2  # +2 pal only (tabs/fire/single split for melee/zeal)
    assert hf_acc.primary_skill == 0
    assert hf_acc.action_skill_bonus == 1  # +1 combat tab
    assert hf_acc.aura_skill_bonus == 8  # +1 off aura +1 fire +6 Holy Fire
    assert hf_acc.ias == 20
    assert hf_acc.cb == 25
    assert hf_acc.cbf == 1
    assert hf_acc.pdr_pct == 15
    assert hf_acc.life_leech == 7

    smite_acc = _extract_prop_acc(dummy_item, d2r, 0x63, 29, char_class=3, pal_spec="smite")
    assert smite_acc.class_skills == 2  # +2 pal only (tabs split for Smite vs Fanaticism)
    assert smite_acc.primary_skill == 0
    assert smite_acc.action_skill_bonus == 1  # +1 combat tab
    assert smite_acc.def_skill == 1  # +1 combat tab also boosts Holy Shield
    assert smite_acc.aura_skill_bonus == 1  # +1 off aura boosts Fanaticism (no fire)


@requires_native
def test_optimize_paladin_leveling_tradeoffs_and_keep_gear(
    parsed_mule_unique: D2SStruct,
    parsed_sork: D2SStruct,
    game_data_resolver: GameDataResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = game_data_resolver
    mule = parsed_mule_unique
    sork = parsed_sork
    assert mule.skills is not None
    skills = list(mule.skills.skill_levels)
    skills[6] = 20  # Holy Fire
    monkeypatch.setattr(mule.skills, "skill_levels", skills)

    # Synthetic gear creating an explicit 48% FHR vs 27% FHR / higher resists + offense trade-off:
    # Weapon gives 25% FHR + 2 skills (or 2h +6 Holy Fire, 0 FHR)
    items = [
        ItemSpec("Spirit Sword", "weapon", "Stash", all_skills=2, fhr=55),
        ItemSpec("Kinemil's Awl", "weapon2h", "mule Equipped", primary_skill=6),
        ItemSpec("Ancients' Pledge", "shield", "Stash", fr=43, lr=48, cr=43, pr=48),
        ItemSpec("FHR Helm", "helm", "Stash", fhr=30, fr=10, lr=10),
        ItemSpec("Res Helm", "helm", "Stash", all_skills=1, fr=35, lr=35, cr=35, pr=35),
        ItemSpec("Stealth", "armor", "Stash", fhr=25, frw=25, pr=30),
        ItemSpec("Skin", "armor", "Stash", all_skills=1, fr=35, lr=35, cr=35, pr=35, cbf=1),
    ]
    charms = [
        CharmSpec("Balance SC", 1, "sork Inv", fhr=5),
        CharmSpec("Ruby SC", 1, "Stash", fr=11),
        CharmSpec("Amber SC", 1, "Stash", lr=11),
    ]

    title, options, spec, diff_name = optimize_paladin_leveling(
        mule,
        items,
        charms,
        spec="holy-fire",
        max_charm_slots=10,
        limit=3,
        resolver=resolver,
        bo_base_bonus=0,
    )
    assert spec == "holy-fire"
    assert diff_name == "Normal"
    assert "Holy Fire" in title
    assert len(options) >= 2
    assert options[0][1].fhr_bp == 86
    assert any(res.fhr_bp < options[0][1].fhr_bp for _, res in options[1:])

    # Empty primary inventory must NOT treat sork's "sork Inv" charm as primary's remove list
    report = format_paladin_leveling_report(
        title,
        options,
        charms,
        diff_name=diff_name,
        primary_skill_name="Holy Fire",
        primary_skill_base=20,
        primary_inv_loc="mule_unique Inv",
    )
    assert "remove: none" in report
    assert "Balance SC [sork Inv]" in report

    # Test keep_equipped=True on a Paladin with active set items and swap weapon
    # Patch mule's items: keep only 1 active equipped sword + 1 stash helm + 1 stash charm
    eq_wep = next(it for it in mule.item_list.items if it.location == ItemLocation.EQUIPPED)
    monkeypatch.setattr(eq_wep, "position", EquipSlot.WEAPON_I)
    monkeypatch.setattr(mule, "weapon_set", 0)
    st_charm = next(
        it for it in sork.item_list.items if it.code_str.strip() in ("cm1", "cm2", "cm3")
    )
    monkeypatch.setattr(mule.item_list, "items", [eq_wep])
    monkeypatch.setattr(sork.item_list, "items", [st_charm])
    monkeypatch.setattr(
        "d2savior.optimizer.extract.collect_item_properties",
        lambda it, **_kw: [(107, 0, [102, 4])] if it is eq_wep else [(39, 10, [10])],
    )
    kept_items, kept_charms = extract_pool(
        mule, extra_chars=[sork], resolver=resolver, pal_spec="holy-fire", keep_equipped=True
    )
    assert len(kept_items) == 1
    assert kept_items[0].aura_skill_bonus == 4
    assert len(kept_charms) >= 1


@requires_native
def test_cli_optimize_paladin_fixtures(capsys: pytest.CaptureFixture[str]) -> None:
    main(["optimize", "--no-config", "mule_unique", str(FIXTURES_DIR)])
    out = capsys.readouterr().out
    assert "Paladin Leveling" in out
    assert "Option #1:" in out

    main(
        [
            "optimize",
            "--no-config",
            "mule_unique",
            str(FIXTURES_DIR),
            "-b",
            "leveling",
            "--keep-gear",
        ]
    )
    out_kept = capsys.readouterr().out
    assert "Paladin Leveling" in out_kept

    main(["optimize", "--no-config", "mule_unique", str(FIXTURES_DIR), "-b", "max-res"])
    out_res = capsys.readouterr().out
    assert "Paladin Max Resist" in out_res

    pal_dir = FIXTURES_DIR / "paladin_snapshot"
    main(
        [
            "optimize",
            "--no-config",
            "smite",
            str(pal_dir),
            "--min-fhr",
            "48",
            "--min-fcr",
            "30",
        ]
    )
    out_floors = capsys.readouterr().out
    assert "Paladin Leveling" in out_floors
    assert "Option #1:" in out_floors
    assert "FHR: " in out_floors
    assert "FCR: " in out_floors

    # Paladin CLI routes through resolve_build_expr (user TOML presets, +, ',', --mode, --no-mf).
    with pytest.raises(SystemExit) as exc_bogus:
        main(["optimize", "--no-config", "smite", str(pal_dir), "-b", "bogus"])
    assert exc_bogus.value.code == 1
    assert "Unknown build preset 'bogus'" in capsys.readouterr().err

    with pytest.raises(SystemExit) as exc_bad_mode:
        main(["optimize", "--no-config", "smite", str(pal_dir), "--mode", "bogus"])
    assert exc_bad_mode.value.code == 1
    assert "Invalid mode 'bogus'" in capsys.readouterr().err


@requires_native
def test_cli_paladin_toml_presets_and_overrides(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    pal_dir = FIXTURES_DIR / "paladin_snapshot"
    (tmp_path / "fast.toml").write_text(
        'title = "Paladin Fast"\nrequire_cbf = true\nmin_frw = 30\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("d2savior.optimizer.presets.get_presets_dir", lambda: tmp_path)

    # User TOML preset + multi-run (,)
    main(["optimize", "--no-config", "smite", str(pal_dir), "-b", "leveling+fast,max-res"])
    out_multi = capsys.readouterr().out
    assert "=== Paladin Fast ===" in out_multi
    assert "=== Paladin Max Resist" in out_multi
    assert "CBF: Yes" in out_multi

    # --mode power and --no-mf must be honored rather than falling through to leveling-probe.
    main(["optimize", "--no-config", "smite", str(pal_dir), "--mode", "power", "--no-mf"])
    out_power = capsys.readouterr().out
    assert "=== Paladin Power" in out_power
    assert "MF: 0%" in out_power


@requires_native
def test_paladin_dedup_key_and_keep_equipped_preserves_zero_stat_items(
    parsed_mule_unique: D2SStruct,
    game_data_resolver: GameDataResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = game_data_resolver
    mule = parsed_mule_unique
    assert mule.skills is not None
    skills = list(mule.skills.skill_levels)
    skills[6] = 20
    monkeypatch.setattr(mule.skills, "skill_levels", skills)

    r_a = ItemSpec("Angelic Halo", "ring", "mule Equipped")
    r_b = ItemSpec("Manald Heal", "ring", "mule Equipped")
    amu = ItemSpec("Angelic Wings", "amulet", "mule Equipped")
    bow = ItemSpec("Raven Claw", "weapon2h", "mule Equipped")
    armor = ItemSpec("Stealth", "armor", "mule Equipped", fhr=25, frw=25, pr=30)
    boots = ItemSpec("Tearhaunch", "boots", "mule Equipped", fr=10, lr=10, cr=10, pr=10)

    c_1 = CharmSpec("Balance SC", 1, "mule Inv", fhr=5)
    c_2 = CharmSpec("Ruby SC", 1, "Stash Tab 1", fr=11)

    res_ab = evaluate_build([bow, armor, amu, boots, r_a, r_b], [c_1, c_2])
    res_ba = evaluate_build([bow, armor, amu, boots, r_b, r_a], [c_2, c_1])
    assert _result_dedup_key(res_ab) == _result_dedup_key(res_ba)

    charms = [
        CharmSpec("Balance SC A", 1, "mule Inv", fhr=5),
        CharmSpec("Balance SC B", 1, "mule Inv", fhr=5),
        CharmSpec("Balance SC C", 1, "Stash Tab 1", fhr=5),
        CharmSpec("Balance SC D", 1, "Stash Tab 1", fhr=5),
        CharmSpec("Ruby SC", 1, "Stash Tab 1", fr=11),
        CharmSpec("Amber SC", 1, "Stash Tab 1", lr=11),
    ]
    _title, options, _spec, _diff = optimize_paladin_leveling(
        mule,
        [bow, armor, amu, boots, r_a, r_b],
        charms,
        spec="holy-fire",
        max_charm_slots=4,
        limit=3,
        resolver=resolver,
        bo_base_bonus=0,
        keep_equipped=True,
    )
    assert len(options) >= 1
    keys = [_result_dedup_key(res) for _, res in options]
    assert len(keys) == len(set(keys))
    for _label, res in options:
        item_names = {it.slot: it.name for it in res.items}
        assert item_names["weapon2h"] == "Raven Claw"
        assert item_names["amulet"] == "Angelic Wings"
        assert {it.name for it in res.items if it.slot == "ring"} == {"Angelic Halo", "Manald Heal"}


@requires_native
def test_extract_pool_and_optimize_paladin_set_bonuses(
    parsed_mule_unique: D2SStruct,
    parsed_shared_stash: SharedStash,
    game_data_resolver: GameDataResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from d2savior.core.item import ExtItemInfo, ItemInfo, TypeSpecificInfo
    from d2savior.core.property_list import PropertyList

    resolver = game_data_resolver
    mule = parsed_mule_unique
    stash = parsed_shared_stash
    assert mule.skills is not None
    skills = [0] * 30
    skills[6] = 20  # Holy Fire -> attack spec (use_ias=True)
    monkeypatch.setattr(mule.skills, "skill_levels", skills)
    stat_values = list(mule.player_stats.stat_values)
    stat_values[0xC] = 29
    stat_values[0] = 60  # Strength for Sigon's Gage/Wrap (req 60)
    monkeypatch.setattr(mule.player_stats, "stat_values", stat_values)
    monkeypatch.setattr(mule, "char_level", 29)

    # Pull real Sigon's Gage (35) & Sigon's Wrap (39) from Tab 2, Angelic Halo (52) from Tab 1,
    # and add synthetic Angelic Wings (53, 2pc=+75 Life) + an alternate 0-IAS +1 glove to compare.
    tab1_items = stash.tabs[0].items
    tab2_items = stash.tabs[1].items
    assert tab1_items is not None
    assert tab2_items is not None
    sig_gage = next(
        it for it in tab2_items.items if it.ext_info is not None and it.ext_info.set_id == 35
    )
    sig_wrap = next(
        it for it in tab2_items.items if it.ext_info is not None and it.ext_info.set_id == 39
    )
    ang_halo = next(
        it for it in tab1_items.items if it.ext_info is not None and it.ext_info.set_id == 52
    )
    ang_wings = D2Item()
    ang_wings.location = ItemLocation.STORED.value
    ang_wings.type_name = b"amu "
    ang_wings.item_info = ItemInfo()
    ang_wings.item_info.ext_info = ExtItemInfo()
    ang_wings.item_info.ext_info.set_id = 53
    tp_w = TypeSpecificInfo()
    sp_w = PropertyList()
    sp_w._use_stat_cost = True
    sp_w.properties = [(7, 0, 75 << 8)]  # 2pc +75 Life (stat 7 val_shift=8)
    tp_w.set_properties = [sp_w, None, None, None, None]
    ang_wings.item_info.type_specific_info = tp_w

    alt_gloves = D2Item()
    alt_gloves.location = ItemLocation.STORED.value
    alt_gloves.type_name = b"tgl "
    alt_gloves.item_info = ItemInfo()
    tp_g = TypeSpecificInfo()
    pl_g = PropertyList()
    pl_g._use_stat_cost = True
    pl_g.properties = [(126, 1, 1)]  # +1 Fire Skills (20 offense vs Sigon's 2pc +30 IAS = 30)
    tp_g.property_list = pl_g
    alt_gloves.item_info.type_specific_info = tp_g

    monkeypatch.setattr(
        "d2savior.optimizer.extract.get_item_display_name",
        lambda it, **_kw: (
            "Angelic Wings"
            if it is ang_wings
            else ("Magefist-like" if it is alt_gloves else it.code_str.strip())
        ),
    )

    # 1. Full-gear extract_pool + optimize: selects Sigon's 2pc (+30 IAS) + Angelic 2pc (+75 Life)
    monkeypatch.setattr(
        mule.item_list, "items", [sig_gage, sig_wrap, ang_halo, ang_wings, alt_gloves]
    )
    items_full, charms_full = extract_pool(mule, resolver=resolver)
    sig_specs = [it for it in items_full if it.name in ("hgl", "hbl")]
    assert len(sig_specs) == 2
    assert sig_specs[0].set_group == sig_specs[1].set_group
    assert sig_specs[0].set_group != 0
    assert sig_specs[0].set_item_id == 35 + 1

    # Duplicate copies of set_id == 0 (Civerb's Ward) must share a non-zero 1-indexed set_item_id (1)
    # rather than colliding with Rust's 0 sentinel and being treated as 2 distinct set pieces.
    civ_a = D2Item()
    civ_a.location = ItemLocation.STORED.value
    civ_a.type_name = b"lrg "
    civ_a.item_info = ItemInfo()
    civ_a.item_info.ext_info = ExtItemInfo()
    civ_a.item_info.ext_info.set_id = 0
    tp_civ = TypeSpecificInfo()
    tp_civ.set_properties = [sp_w, None, None, None, None]
    civ_a.item_info.type_specific_info = tp_civ
    civ_b = D2Item()
    civ_b.location = ItemLocation.STORED.value
    civ_b.type_name = b"lrg "
    civ_b.item_info = ItemInfo()
    civ_b.item_info.ext_info = ExtItemInfo()
    civ_b.item_info.ext_info.set_id = 0
    civ_b.item_info.type_specific_info = tp_civ
    monkeypatch.setattr(mule.item_list, "items", [civ_a, civ_b])
    civ_items, _ = extract_pool(mule, resolver=resolver)
    assert len(civ_items) == 2
    assert all(it.set_item_id == 1 for it in civ_items)
    _tc, opts_civ, _sc, _dc = optimize_paladin_leveling(
        mule, civ_items, [], resolver=resolver, bo_base_bonus=0
    )
    assert opts_civ[0][1].life_no_bo == mule.player_stats.max_life
    monkeypatch.setattr(
        mule.item_list, "items", [sig_gage, sig_wrap, ang_halo, ang_wings, alt_gloves]
    )
    alt_specs = [it for it in items_full if it.name == "Magefist-like"]
    assert len(alt_specs) == 1
    assert alt_specs[0].aura_skill_bonus == 1
    _t, opts_full, _s, _d = optimize_paladin_leveling(
        mule, items_full, charms_full, resolver=resolver, bo_base_bonus=0
    )
    assert len(opts_full) >= 1
    assert opts_full[0][1].ias == 30
    assert opts_full[0][1].life_no_bo == mule.player_stats.max_life + 20 + 20 + 75

    # 2. keep_equipped=True with all four set items actively equipped gives the same 2pc bonuses
    for set_item, slot_pos in (
        (sig_gage, EquipSlot.GLOVES.value),
        (sig_wrap, EquipSlot.BELT.value),
        (ang_halo, EquipSlot.RING_LEFT.value),
        (ang_wings, EquipSlot.AMULET.value),
    ):
        monkeypatch.setattr(set_item, "location", ItemLocation.EQUIPPED.value)
        monkeypatch.setattr(set_item, "position", slot_pos)
    monkeypatch.setattr(mule.item_list, "items", [sig_gage, sig_wrap, ang_halo, ang_wings])
    items_kept, charms_kept = extract_pool(mule, resolver=resolver, keep_equipped=True)
    _t2, opts_kept, _s2, _d2 = optimize_paladin_leveling(
        mule, items_kept, charms_kept, resolver=resolver, bo_base_bonus=0, keep_equipped=True
    )
    assert len(opts_kept) >= 1
    assert opts_kept[0][1].ias == 30
    assert opts_kept[0][1].life_no_bo == mule.player_stats.max_life + 20 + 20 + 75


@requires_native
def test_paladin_unknown_spec_error_and_native_validation(
    parsed_mule_unique: D2SStruct,
    game_data_resolver: GameDataResolver,
) -> None:
    resolver = game_data_resolver
    mule = parsed_mule_unique

    with pytest.raises(ValueError, match="Unknown Paladin spec") as exc_spec:
        optimize_paladin_leveling(mule, [], [], spec="bogus-spec", resolver=resolver)
    msg = str(exc_spec.value)
    for expected_spec in ("holy-fire", "smite", "hammer", "leveling"):
        assert expected_spec in msg

    fcr_bps, fhr_bps = class_breakpoints(int(CharClass.PALADIN))
    assert (fcr_bps, fhr_bps) == (list(PALADIN_FCR_BPS), list(PALADIN_FHR_BPS))
    with pytest.raises(ValueError, match="unsupported char_class"):
        class_breakpoints(99)
    with pytest.raises(ValueError, match="unsupported char_class"):
        evaluate_build([], [], char_class=99)

    for bad_offense in ("smite", "melee"):
        with pytest.raises(ValueError, match="not supported for Sorceress"):
            optimize_builds(
                [],
                [],
                BuildConstraints(
                    offense=bad_offense,
                    character=CharacterStats(char_class=int(CharClass.SORCERESS)),
                ),
            )


@requires_native
def test_extract_pool_locality_order(
    parsed_paladin_smite: D2SStruct,
    parsed_paladin_mule_sets: D2SStruct,
    parsed_paladin_stash: SharedStash,
    game_data_resolver: GameDataResolver,
) -> None:
    resolver = game_data_resolver
    smite = parsed_paladin_smite
    mule = parsed_paladin_mule_sets
    stash = parsed_paladin_stash

    items, charms = extract_pool(smite, extra_chars=[mule], stashes=[stash], resolver=resolver)

    def tier(loc: str) -> int:
        if loc == "smite Equipped":
            return 0
        if loc == "smite Swap":
            return 1
        if loc == "smite Inv":
            return 2
        if loc == "smite Stash":
            return 3
        if loc.startswith("Stash Tab "):
            return 4
        return 5

    item_tiers = [tier(it.loc) for it in items]
    charm_tiers = [tier(ch.loc) for ch in charms]
    assert item_tiers == sorted(item_tiers)
    assert charm_tiers == sorted(charm_tiers)


@requires_native
def test_keep_gear_groups_and_combinations(
    parsed_paladin_smite: D2SStruct,
    parsed_paladin_mule_sets: D2SStruct,
    parsed_paladin_stash: SharedStash,
    game_data_resolver: GameDataResolver,
    capsys: pytest.CaptureFixture[str],
) -> None:
    resolver = game_data_resolver
    pal_dir = FIXTURES_DIR / "paladin_snapshot"
    smite = parsed_paladin_smite
    mule = parsed_paladin_mule_sets
    stash = parsed_paladin_stash

    all_items, all_charms = extract_pool(
        smite, extra_chars=[mule], stashes=[stash], resolver=resolver
    )
    kept_all_items, kept_all_charms = extract_pool(
        smite, extra_chars=[mule], stashes=[stash], resolver=resolver, keep_equipped="all"
    )
    kept_bool_items, kept_bool_charms = extract_pool(
        smite, extra_chars=[mule], stashes=[stash], resolver=resolver, keep_equipped=True
    )
    assert [(i.name, i.slot, i.loc) for i in kept_all_items] == [
        (i.name, i.slot, i.loc) for i in kept_bool_items
    ]
    assert len(kept_all_charms) == len(kept_bool_charms) == len(all_charms)

    # weapon+jewelry keeps only primary active weapon/shield/amulet/ring, while still allowing
    # stash/mule armor slots (helm/armor/belt/gloves/boots).
    wj_items, _ = extract_pool(
        smite,
        extra_chars=[mule],
        stashes=[stash],
        resolver=resolver,
        keep_equipped="weapon+jewelry",
    )
    wj_kept_slots = {"weapon", "weapon2h", "shield", "amulet", "ring"}
    wj_free_slots = {"helm", "armor", "belt", "gloves", "boots"}
    kept_all_by_slot = {(i.name, i.slot, i.loc) for i in kept_all_items}
    assert {(i.name, i.slot, i.loc) for i in wj_items if i.slot in wj_kept_slots} == {
        x for x in kept_all_by_slot if x[1] in wj_kept_slots
    }
    assert any(it.slot in wj_free_slots and it.loc != "smite Equipped" for it in wj_items)
    assert len(kept_all_items) < len(wj_items) < len(all_items)

    # armor keeps only primary active helm/armor/belt/gloves/boots, while still allowing
    # stash/mule weapons, shields, and jewelry.
    arm_items, _ = extract_pool(
        smite, extra_chars=[mule], stashes=[stash], resolver=resolver, keep_equipped="armor"
    )
    assert {(i.name, i.slot, i.loc) for i in arm_items if i.slot in wj_free_slots} == {
        x for x in kept_all_by_slot if x[1] in wj_free_slots
    }
    assert any(it.slot in wj_kept_slots and it.loc != "smite Equipped" for it in arm_items)

    # Individual slots (e.g. helm+boots) keep only those equipped slots while still allowing
    # stash/mule items for armor, belt, gloves, weapons, shields, and jewelry.
    hb_items, _ = extract_pool(
        smite, extra_chars=[mule], stashes=[stash], resolver=resolver, keep_equipped="helm+boots"
    )
    hb_kept_slots = {"helm", "boots"}
    assert {(i.name, i.slot, i.loc) for i in hb_items if i.slot in hb_kept_slots} == {
        x for x in kept_all_by_slot if x[1] in hb_kept_slots
    }
    assert {(i.name, i.slot, i.loc) for i in hb_items if i.slot not in hb_kept_slots} == {
        (i.name, i.slot, i.loc) for i in all_items if i.slot not in hb_kept_slots
    }
    assert any(
        it.slot in {"armor", "belt", "gloves"} and it.loc != "smite Equipped" for it in hb_items
    )

    # End-to-end CLI tests for --keep-gear groups, individual slots & combinations + invalid value error.
    for expr in (
        "weapon",
        "jewelry",
        "armor",
        "weapon+jewelry",
        "all",
        "helm",
        "chest",
        "helm+boots",
        "weapon+helm+boots",
    ):
        main(
            [
                "optimize",
                "--no-config",
                "smite",
                str(pal_dir),
                "-b",
                "leveling",
                "--keep-gear",
                expr,
            ]
        )
        out = capsys.readouterr().out
        assert "Paladin Leveling" in out
        assert "Option #1:" in out

    # Bare --keep-gear before positional character name or save path should not consume the target.
    main(["optimize", "--no-config", "smite", "--keep-gear", str(pal_dir), "-b", "leveling"])
    out_before_path = capsys.readouterr().out
    assert "Paladin Leveling" in out_before_path
    assert "Option #1:" in out_before_path

    main(["optimize", "--no-config", "--keep-gear", str(pal_dir / "smite.d2s"), "-b", "leveling"])
    out_before_d2s = capsys.readouterr().out
    assert "Paladin Leveling" in out_before_d2s
    assert "Option #1:" in out_before_d2s

    with pytest.raises(SystemExit) as exc_info:
        main(["optimize", "--no-config", "smite", str(pal_dir), "--keep-gear", "invalid"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "Invalid --keep-gear group" in err

    with pytest.raises(SystemExit) as exc_info2:
        main(["optimize", "--no-config", "--keep-gear=invalid", "smite", str(pal_dir)])
    assert exc_info2.value.code == 2
    err2 = capsys.readouterr().err
    assert "Invalid --keep-gear group" in err2


@requires_native
def test_torch_and_annihilus_vit_ene_and_bo_all_skills() -> None:
    items = [
        ItemSpec("Spirit Sword", "weapon", "test", all_skills=2, fcr=35, fhr=55),
        ItemSpec("Spirit Shield", "shield", "test", all_skills=2, fcr=35, fhr=55),
        ItemSpec("Tiara", "helm", "test", class_skills=2),
        ItemSpec("Smoke", "armor", "test", fhr=20, fr=180, lr=180, cr=180, pr=180),
        ItemSpec("Grim Noose", "amulet", "test", class_skills=1, fcr=20),
        ItemSpec("Belt", "belt", "test", fcr=20),
        ItemSpec("Trang-Oul's", "gloves", "test", fcr=20),
        ItemSpec("Aldur's", "boots", "test", frw=40),
        ItemSpec("Ring A", "ring", "test", fcr=10),
        ItemSpec("Ring B", "ring", "test", fcr=10),
    ]
    torch = CharmSpec(
        "Hellfire Torch",
        2,
        "test",
        skills=3,
        str_bonus=15,
        dex_bonus=15,
        vit=20,
        ene=20,
        fr=15,
        lr=15,
        cr=15,
        pr=15,
        unique_id=400,
    )
    anni = CharmSpec(
        "Annihilus",
        1,
        "test",
        all_skills=1,
        str_bonus=15,
        dex_bonus=15,
        vit=15,
        ene=15,
        fr=15,
        lr=15,
        cr=15,
        pr=15,
        unique_id=381,
    )
    c_bo = BuildConstraints(
        mode="power",
        min_fcr=105,
        min_fhr=60,
        min_fr=75,
        min_lr=75,
        min_cr=75,
        min_pr=75,
        max_charm_slots=3,
        character=CharacterStats(
            base_life=500,
            base_mana=300,
            bo_base_bonus=4,
            use_bo=True,
        ),
    )
    res_with = optimize_builds(items, [torch, anni], c_bo)[0]
    res_without = optimize_builds(items, [], c_bo)[0]

    assert res_with.skills == res_without.skills + 4
    # Only Annihilus (+1 all_skills) boosts Battle Orders; Torch (+3 class skills) does not.
    assert res_with.bo_lvl == res_without.bo_lvl + 1
    # Sorceress gets +2 life/vit and +2 mana/ene from Torch (20) + Anni (15) = +70 non-BO life & mana.
    assert res_with.life_no_bo == res_without.life_no_bo + 70
    assert res_with.life_bo > res_without.life_bo + 70
    assert res_with.mana_bo > res_without.mana_bo + 70


@requires_native
def test_item_pct_life_scales_evaluate_and_optimize() -> None:
    helm_plain = ItemSpec("Shako", "helm", "test", all_skills=2, life=100, vit=10)
    helm_jah = ItemSpec("Shako (Jah)", "helm", "test", all_skills=2, life=100, vit=10, pct_life=5)

    res_plain = evaluate_build([helm_plain], [], base_life=500, bo_base_bonus=4, use_bo=True)
    res_jah = evaluate_build([helm_jah], [], base_life=500, bo_base_bonus=4, use_bo=True)
    # bo_able_life = 600, vit_life = 20. +5% max life adds 30 to both life_no_bo and life_bo.
    assert res_jah.life_no_bo == res_plain.life_no_bo + 30
    assert res_jah.life_bo == res_plain.life_bo + 30


@requires_native
def test_angelic_set_and_itd_win_with_ar_cth_model(
    parsed_paladin_smite: D2SStruct,
    game_data_resolver: GameDataResolver,
) -> None:
    # Verify extracted Angelic Halo + Wings from real fixtures give 2pc +AR/lvl and beat plain jewelry
    resolver = game_data_resolver
    smite = parsed_paladin_smite
    items, _ = extract_pool(smite, resolver=resolver)
    halos = [it for it in items if it.name.startswith("Angelic Halo") and it.set_bonuses]
    assert halos
    assert any(req == 2 and bonus.ar == 360 for req, bonus in halos[0].set_bonuses)

    plain_sword = ItemSpec(
        "Plain Sword", "weapon", "test", wclass="1hs", wep_phys_2x=60, can_zeal=True
    )
    eth_sword = ItemSpec(
        "Eth Sword",
        "weapon",
        "test",
        wclass="1hs",
        wep_phys_2x=60,
        can_zeal=True,
        target_def_pct=25,
    )
    res = optimize_builds(
        [plain_sword, eth_sword],
        [],
        BuildConstraints(
            offense="zeal",
            mode="leveling",
            min_fcr=0,
            min_fhr=0,
            min_fr=0,
            min_lr=0,
            min_cr=0,
            min_pr=0,
            character=CharacterStats(
                char_class=int(CharClass.PALADIN),
                base_str=50,
                base_dex=20,
                base_hell_res=75,
                use_bo=False,
            ),
            target=TargetProfile(target_def=1000),
            skills=MeleeSkillModel(
                action_hits=[5],
                action_ed=[0],
                action_ar_pct=[10],
                aura_hit_dmg=[0.0],
                aura_pulse_dps=[0.0],
            ),
        ),
    )
    assert len(res) >= 1
    assert res[0].items[0].name == "Eth Sword"
    assert res[0].ar == (85 * 110) // 100
    assert 0 < res[0].cth < 95
    assert res[0].raw_dps > res[0].dps


@requires_native
def test_evaluate_build_with_constraints_and_melee_action_end_to_end(
    parsed_paladin_smite: D2SStruct,
    game_data_resolver: GameDataResolver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = game_data_resolver
    char_data = parsed_paladin_smite
    assert char_data.skills is not None

    # 1. evaluate_build(items, charms, constraints=c) evaluates melee/zeal AR/CTH/DPS directly.
    sword = ItemSpec(
        "Broad Sword", "weapon", "test", wclass="1hs", wep_phys_2x=60, can_zeal=True, ar=100
    )
    charm = CharmSpec("Sharp SC", 1, "Inv", ar=40)
    c_zeal = BuildConstraints(
        offense="zeal",
        mode="leveling",
        character=CharacterStats(
            char_class=int(CharClass.PALADIN),
            base_str=50,
            base_dex=20,
            base_hell_res=75,
            use_bo=False,
        ),
        target=TargetProfile(target_def=300),
        skills=MeleeSkillModel(
            action_hits=[5],
            action_ed=[100],
            action_ar_pct=[50],
            aura_ar_pct=[50],
            aura_hit_dmg=[0.0],
            aura_pulse_dps=[0.0],
        ),
    )
    ev = evaluate_build([sword], [charm], constraints=c_zeal)
    # base_ar = 85 + 100 + 40 = 225; total_ar_pct = +100% => AR = 450; cth = 450/750 = 60%
    assert ev.ar == 450
    assert ev.cth == 60
    assert ev.raw_dps > ev.dps > 0.0

    # 2. End-to-end optimize_paladin_leveling + report for Vengeance+Conviction and Charge/Sacrifice+Blessed Aim
    items = [ItemSpec("War Sword", "weapon", "Inv", wclass="1hs", wep_phys_2x=80, can_zeal=True)]

    skills = [0] * 30
    skills[15] = 20  # Vengeance (ID 111)
    skills[27] = 20  # Conviction (ID 123)
    monkeypatch.setattr(char_data.skills, "skill_levels", skills)
    title_v, opts_v, _spec_v, diff_v = optimize_paladin_leveling(
        char_data, items, [], spec="vengeance", right_skill=123, resolver=resolver, bo_base_bonus=0
    )
    assert len(opts_v) >= 1
    assert opts_v[0][1].ar > 0
    assert opts_v[0][1].cth > 0
    report_v = format_paladin_leveling_report(
        title_v, opts_v, diff_name=diff_v, primary_skill_name="Vengeance", primary_skill_base=20
    )
    assert "(Vengeance) | AR:" in report_v

    for spec_name, offset in (("charge", 11), ("sacrifice", 0)):
        skills = [0] * 30
        skills[offset] = 20
        skills[12] = 10  # Blessed Aim (ID 108)
        monkeypatch.setattr(char_data.skills, "skill_levels", skills)
        title_m, opts_m, _spec_m, diff_m = optimize_paladin_leveling(
            char_data,
            items,
            [],
            spec=spec_name,
            right_skill=108,
            resolver=resolver,
            bo_base_bonus=0,
        )
        assert len(opts_m) >= 1
        assert opts_m[0][1].ar > 0
        assert opts_m[0][1].cth > 0
        skill_label = spec_name.title()
        report_m = format_paladin_leveling_report(
            title_m,
            opts_m,
            diff_name=diff_m,
            primary_skill_name=skill_label,
            primary_skill_base=20,
        )
        assert f"({skill_label}) | AR:" in report_m


@requires_native
def test_target_type_prevents_overvaluing_itd_on_champion_and_boss(
    parsed_paladin_smite: D2SStruct,
    game_data_resolver: GameDataResolver,
) -> None:
    resolver = game_data_resolver
    smite = parsed_paladin_smite

    plain_sword = ItemSpec(
        "Plain Sword", "weapon", "Inv", wclass="1hs", wep_phys_2x=100, can_zeal=True
    )
    itd_sword = ItemSpec(
        "ITD Sword", "weapon", "Inv", wclass="1hs", wep_phys_2x=70, can_zeal=True, itd=1
    )
    items = [plain_sword, itd_sword]

    _, opts_default, _, _ = optimize_paladin_leveling(
        smite, items, [], spec="zeal", resolver=resolver, bo_base_bonus=0, limit=1
    )
    _, opts_boss, _, _ = optimize_paladin_leveling(
        smite,
        items,
        [],
        spec="zeal",
        resolver=resolver,
        bo_base_bonus=0,
        limit=1,
        target_type="boss",
    )
    title_trash, opts_trash, _, _ = optimize_paladin_leveling(
        smite,
        items,
        [],
        spec="zeal",
        resolver=resolver,
        bo_base_bonus=0,
        limit=1,
        target_type="trash",
    )
    assert opts_default[0][1].items[0].name == "Plain Sword"
    assert opts_boss[0][1].items[0].name == "Plain Sword"
    assert opts_boss[0][1].cth < opts_default[0][1].cth
    assert opts_trash[0][1].items[0].name == "ITD Sword"
    assert opts_trash[0][1].cth == 95
    assert "trash" in title_trash

    bad_target: Any = "uber"
    with pytest.raises(ValueError, match="Unknown target_type"):
        optimize_paladin_leveling(
            smite,
            items,
            [],
            spec="zeal",
            resolver=resolver,
            bo_base_bonus=0,
            target_type=bad_target,
        )


@requires_native
def test_optimizer_performance_budgets(
    parsed_paladin_smite: D2SStruct,
    parsed_paladin_extra_chars: list[D2SStruct],
    parsed_paladin_stash: SharedStash,
    parsed_sork: D2SStruct,
    parsed_mule_unique: D2SStruct,
    parsed_shared_stash: SharedStash,
    game_data_resolver: GameDataResolver,
) -> None:
    import time

    resolver = game_data_resolver

    # 1. Paladin snapshot leveling optimize (full mules + shared stash with damage/AR charms)
    smite = parsed_paladin_smite
    pal_extras = parsed_paladin_extra_chars
    pal_stash = parsed_paladin_stash
    pal_items, pal_charms = extract_pool(
        smite, extra_chars=pal_extras, stashes=[pal_stash], resolver=resolver
    )
    t0 = time.perf_counter()
    _, pal_opts, _, _ = optimize_paladin_leveling(
        smite,
        pal_items,
        pal_charms,
        extra_chars=pal_extras,
        stashes=[pal_stash],
        resolver=resolver,
    )
    pal_elapsed = time.perf_counter() - t0
    assert len(pal_opts) >= 1
    assert pal_elapsed < 2.0, f"Paladin optimize regression: {pal_elapsed:.3f}s"

    # 1b. Paladin snapshot leveling optimize with --targets 2
    pal_t2_items, pal_t2_charms = extract_pool(
        smite, extra_chars=pal_extras, stashes=[pal_stash], targets=2, resolver=resolver
    )
    t0_t2 = time.perf_counter()
    _, pal_t2_opts, _, _ = optimize_paladin_leveling(
        smite,
        pal_t2_items,
        pal_t2_charms,
        extra_chars=pal_extras,
        stashes=[pal_stash],
        targets=2,
        resolver=resolver,
    )
    pal_t2_elapsed = time.perf_counter() - t0_t2
    assert len(pal_t2_opts) >= 1
    assert pal_t2_elapsed < 2.0, f"Paladin targets=2 optimize regression: {pal_t2_elapsed:.3f}s"

    # 2. Sorceress optimize (sork + mule_unique + shared stash)
    sork = parsed_sork
    mule = parsed_mule_unique
    sorc_stash = parsed_shared_stash
    sorc_items, sorc_charms = extract_pool(
        sork, extra_chars=[mule], stashes=[sorc_stash], resolver=resolver
    )
    sorc_presets = select_sorc_presets(
        sork,
        extra_chars=[mule],
        stashes=[sorc_stash],
        resolver=resolver,
    )
    t1 = time.perf_counter()
    sorc_results = [optimize_builds(sorc_items, sorc_charms, c) for _, c in sorc_presets]
    sorc_elapsed = time.perf_counter() - t1
    assert any(sorc_results)
    assert sorc_elapsed < 2.0, f"Sorc optimize regression: {sorc_elapsed:.3f}s"


@requires_native
def test_score_of_result_matches_rust_rules() -> None:
    import math

    # 1. base_max_fr cap is respected in leveling-res.
    c_res = BuildConstraints(
        offense="melee",
        mode="leveling-res",
        min_fcr=0,
        min_fhr=0,
        min_fr=0,
        min_lr=0,
        min_cr=0,
        min_pr=0,
        character=CharacterStats(char_class=3, base_max_fr=5, base_hell_res=0),
    )
    r_75 = evaluate_build(
        [ItemSpec("Helm75", "helm", fr=75, lr=75, cr=75, pr=75)], [], constraints=c_res
    )
    r_80 = evaluate_build(
        [ItemSpec("Helm80", "helm", fr=80, lr=75, cr=75, pr=75)], [], constraints=c_res
    )
    s_75 = score_of_result(r_75, c_res)
    s_80 = score_of_result(r_80, c_res)
    assert s_80[0] - s_75[0] == 5
    assert s_80 > s_75

    # 2. blizz_skills contributes to eff_primary, and locality is excluded.
    c_mf = BuildConstraints(
        mode="mf",
        min_fcr=0,
        min_fhr=0,
        min_fr=0,
        min_lr=0,
        min_cr=0,
        min_pr=0,
        character=CharacterStats(base_hell_res=0),
    )
    r_eq = evaluate_build(
        [ItemSpec("Orb", "weapon", loc="Equipped", all_skills=1, blizz_skills=2)],
        [],
        constraints=c_mf,
    )
    r_st = evaluate_build(
        [ItemSpec("Orb", "weapon", loc="Stash", all_skills=1, blizz_skills=2)],
        [],
        constraints=c_mf,
    )
    assert score_of_result(r_eq, c_mf) == score_of_result(r_st, c_mf)
    assert score_of_result(r_eq, c_mf)[1] == 3

    # 3. Smite offense scoring matches Rust OffenseProfile::score.
    c_smite = BuildConstraints(
        offense="smite",
        mode="leveling",
        min_fcr=0,
        min_fhr=0,
        min_fr=0,
        min_lr=0,
        min_cr=0,
        min_pr=0,
        character=CharacterStats(char_class=3, base_hell_res=0),
    )
    r_smite = evaluate_build(
        [
            ItemSpec("Scepter", "weapon", all_skills=1, ias=20, cb=25),
            ItemSpec("Shield", "shield"),
        ],
        [],
        constraints=c_smite,
    )
    expected_smite = min(r_smite.cb, 100) * 4 + min(r_smite.ias_bp, 80) * 2 + r_smite.skills * 10
    assert score_of_result(r_smite, c_smite)[0] == expected_smite

    # 4. Zeal with DPS tables uses 2% log DPS buckets.
    c_zeal = BuildConstraints(
        offense="zeal",
        mode="leveling",
        min_fcr=0,
        min_fhr=0,
        min_fr=0,
        min_lr=0,
        min_cr=0,
        min_pr=0,
        character=CharacterStats(
            char_class=3,
            char_level=80,
            base_str=100,
            base_dex=100,
            base_hell_res=0,
        ),
        target=TargetProfile(target_def=0),
        skills=MeleeSkillModel(action_hits=[5], action_ed=[100]),
    )
    r_zeal = evaluate_build(
        [ItemSpec("Phase Blade", "weapon", wsm=-30, wep_phys_2x=66, can_zeal=True)],
        [],
        constraints=c_zeal,
    )
    assert r_zeal.dps > 0.0
    assert score_of_result(r_zeal, c_zeal)[0] == math.floor(math.log(r_zeal.dps) / math.log(1.02))

    # 5. Power mode: caster DPS vs non-DPS eff_primary and pr >= base_max_pr tertiary.
    orb = ItemSpec(
        "Orb", "weapon", fcr=37, all_skills=1, blizz_skills=2, fr=75, lr=75, cr=75, pr=75
    )
    c_power_nodps = BuildConstraints(
        mode="power",
        min_fcr=0,
        min_fhr=0,
        min_fr=0,
        min_lr=0,
        min_cr=0,
        min_pr=0,
        character=CharacterStats(base_hell_res=0),
    )
    r_power_nodps = evaluate_build([orb], [], constraints=c_power_nodps)
    sc_power_nodps = score_of_result(r_power_nodps, c_power_nodps)
    assert sc_power_nodps[:3] == (3, 1, 1)

    c_power_dps = BuildConstraints(
        mode="power",
        min_fcr=0,
        min_fhr=0,
        min_fr=0,
        min_lr=0,
        min_cr=0,
        min_pr=0,
        character=CharacterStats(base_hell_res=0),
        skills=CasterSkillModel(blizz_dmg=[100.0, 150.0, 200.0, 250.0]),
    )
    r_power_dps = evaluate_build([orb], [], constraints=c_power_dps)
    assert r_power_dps.dps > 0.0
    assert score_of_result(r_power_dps, c_power_dps)[0] == math.floor(r_power_dps.dps)

    # 6. Max-res mode includes raw resistance sum as tiebreaker index 5.
    c_max_res = BuildConstraints(
        mode="max-res",
        min_fcr=0,
        min_fhr=0,
        min_fr=0,
        min_lr=0,
        min_cr=0,
        min_pr=0,
        character=CharacterStats(base_hell_res=0),
    )
    r_mr_75 = evaluate_build(
        [ItemSpec("Helm75", "helm", fr=75, lr=75, cr=75, pr=75)], [], constraints=c_max_res
    )
    r_mr_85 = evaluate_build(
        [ItemSpec("Helm85", "helm", fr=85, lr=75, cr=75, pr=75)], [], constraints=c_max_res
    )
    sc_mr_75 = score_of_result(r_mr_75, c_max_res)
    sc_mr_85 = score_of_result(r_mr_85, c_max_res)
    assert sc_mr_75[0] == 300
    assert sc_mr_85[0] == 300
    assert sc_mr_85[5] - sc_mr_75[5] == 10

    # 7. Leveling melee without DPS tables uses Rust Melee offense formula and aura_skill_bonus.
    c_melee = BuildConstraints(
        offense="melee",
        mode="leveling",
        min_fcr=0,
        min_fhr=0,
        min_fr=0,
        min_lr=0,
        min_cr=0,
        min_pr=0,
        character=CharacterStats(char_class=3, base_hell_res=0),
        skills=MeleeSkillModel(has_aura=True),
    )
    r_melee = evaluate_build(
        [
            ItemSpec(
                "MeleeWep",
                "weapon",
                all_skills=1,
                aura_skill_bonus=2,
                action_skill_bonus=5,
                ias=20,
            )
        ],
        [],
        constraints=c_melee,
    )
    expected_melee = (1 + 2) * 20 + (min(r_melee.ias_bp, 80) * 3) // 2
    assert score_of_result(r_melee, c_melee)[0] == expected_melee

    # 8. Invalid mode, offense, char_class, or target_type raises ValueError.
    bad_mode: Any = "bogus"
    bad_target: Any = "uber"
    for bad_c, err_match in (
        (BuildConstraints(mode=bad_mode), "invalid mode"),
        (BuildConstraints(offense="smite"), "offense profile 'smite'"),
        (BuildConstraints(character=CharacterStats(char_class=99)), "unsupported char_class 99"),
        (BuildConstraints(target=TargetProfile(target_type=bad_target)), "invalid target_type"),
    ):
        with pytest.raises(ValueError, match=err_match):
            score_of_result(r_eq, bad_c)


@requires_native
def test_charmspec_eq_hash_frozen_and_constraints_with_limit() -> None:
    c1 = CharmSpec("Vita SC", 1, "inv", life=20, mana=17, skills=1)
    c2 = CharmSpec("Vita SC", 1, "inv", life=20, mana=17, skills=1)
    c3 = CharmSpec("Vita SC", 1, "stash", life=20, mana=17, skills=1)
    assert c1 == c2
    assert hash(c1) == hash(c2)
    assert c1 != c3
    counts = Counter([c1, c2, c3])
    assert counts[c1] == 2
    assert counts[c3] == 1
    with pytest.raises(AttributeError):
        c1.life = 25  # type: ignore[misc]

    char = CharacterStats(
        char_class=3,
        char_level=85,
        base_life=500,
        base_mana=200,
        base_str=100,
        base_dex=50,
        base_hell_res=-40,
        base_max_fr=5,
        bo_base_bonus=6,
        use_bo=True,
    )
    target = TargetProfile(targets=3, target_type="trash", target_def=1000, target_hp=5000)
    skills = MeleeSkillModel(action_hits=[5], action_ed=[100], has_aura=True, aura_is_fire=True)
    orig = BuildConstraints(
        allow_mf=False,
        min_fcr=30,
        min_fhr=48,
        min_fr=75,
        min_lr=75,
        min_cr=75,
        min_pr=50,
        max_charm_slots=20,
        mode="leveling-res",
        limit=5,
        fixed_gear=True,
        fixed_slots=["weapon"],
        offense="zeal",
        require_cbf=True,
        min_frw=20,
        min_ias=30,
        min_cb=35,
        min_ll=7,
        min_pdr=15,
        min_mf=25,
        character=char,
        target=target,
        skills=skills,
    )
    cloned = orig.with_limit(1)
    assert orig.limit == 5
    assert cloned.limit == 1
    assert cloned.character == char
    assert cloned.target == target
    assert cloned.skills == skills
    assert cloned.allow_mf is False
    assert cloned.mode == "leveling-res"
    assert cloned.offense == "zeal"
    assert cloned.fixed_gear is True
    assert cloned.fixed_slots == ["weapon"]
    assert cloned.require_cbf is True
    assert (
        cloned.min_frw,
        cloned.min_ias,
        cloned.min_cb,
        cloned.min_ll,
        cloned.min_pdr,
        cloned.min_mf,
    ) == (
        20,
        30,
        35,
        7,
        15,
        25,
    )
    with pytest.raises(AttributeError):
        orig.limit = 10  # type: ignore[misc]
