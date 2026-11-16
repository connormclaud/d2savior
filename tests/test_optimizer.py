from pathlib import Path

import pytest

from d2savior.cli import main, parse_d2i_file, parse_d2s_file
from d2savior.core.enums import EquipSlot, ItemLocation
from d2savior.core.item import D2Item
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash
from d2savior.optimizer import (
    BuildConstraints,
    CharmSpec,
    ItemSpec,
    _classify_slot,
    _detect_cta_bo_bonus,
    _extract_prop_acc,
    _item_levelreq,
    _item_to_spec,
    blizzard_damage,
    blizzard_damage_with_base,
    evaluate_build,
    extract_pool,
    format_build_report,
    optimize_builds,
    select_sorc_presets,
)

pytest.importorskip("d2savior._native")

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_blizzard_damage_pyo3() -> None:
    base7, syn7, cm7 = blizzard_damage(7)
    assert base7 > 0
    assert abs(syn7 - 3245.4) < 1.0
    assert cm7 == -150

    _, syn9, cm9 = blizzard_damage(9)
    assert abs(syn9 - 3666.7) < 1.0
    assert cm9 == -160


def test_evaluate_build_and_constraints_validation() -> None:
    items = [
        ItemSpec("Spirit Sword", "weapon", "test", all_skills=2, fcr=34, fhr=55, vit=22, mana=93),
        ItemSpec(
            "Spirit Shield", "shield", "test", all_skills=2, fcr=34, fhr=55, lr=35, cr=35, pr=35
        ),
        ItemSpec("Tiara", "helm", "test", sorc_skills=2),
        ItemSpec("Smoke", "armor", "test", fhr=20, fr=50, lr=50, cr=50, pr=50),
        ItemSpec("Grim Noose", "amulet", "test", sorc_skills=1, fcr=5, lr=30),
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
            base_hell_res=-70,
            mode="power",
        ),
    )
    assert opt[0].skills == 8
    assert res.fcr == 113
    assert res.fcr_bp == 105
    assert res.fhr == 130
    assert res.fhr_bp == 86
    assert (res.fr, res.lr, res.cr, res.pr) == (75, 75, 75, 75)
    assert res.mf == 0

    bad = BuildConstraints(mode="invalid")
    with pytest.raises(ValueError, match="invalid mode"):
        optimize_builds(items, charms, bad)


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
        ItemSpec("Tiara", "helm", "test", sorc_skills=2, fr=40, lr=40, cr=50, pr=40),
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
            base_str=156,
            base_dex=25,
            base_hell_res=-70,
            mode="mf",
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
            base_str=156,
            base_dex=20,
            base_hell_res=-70,
            mode="mf",
        ),
    )
    assert res_low[0].items[0].name == "Spirit Sword"


def test_optimize_builds_from_fixtures() -> None:
    resolver = GameDataResolver.load()
    ok_s, sork, _ = parse_d2s_file(str(FIXTURES_DIR / "sork.d2s"), resolver=resolver)
    ok_m, mule, _ = parse_d2s_file(str(FIXTURES_DIR / "mule_unique.d2s"), resolver=resolver)
    ok_st, stash, kind, _ = parse_d2i_file(
        str(FIXTURES_DIR / "ModernSharedStashSoftCoreV2.d2i"), resolver=resolver
    )
    assert ok_s
    assert sork is not None
    assert ok_m
    assert mule is not None
    assert ok_st
    assert kind == "stash"
    assert isinstance(stash, SharedStash)

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
        base_life=sork.player_stats.max_life,
        base_mana=sork.player_stats.max_mana,
        base_hell_res=-70,
        limit=2,
    )
    results = optimize_builds(items, charms, relaxed)
    assert len(results) >= 1
    assert results[0].fcr >= 63
    assert results[0].fhr >= 42
    report = format_build_report("Fixture Test", results)
    assert "pruned sets):" in report
    assert "Rust/PyO3" not in report


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


def test_cli_optimize_requires_sorceress_and_avoids_hardcoded_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_non_sorc:
        main(["optimize", "--no-config", "mule_unique", str(FIXTURES_DIR)])
    assert exc_non_sorc.value.code == 1
    assert "expected Sorceress" in capsys.readouterr().err

    with pytest.raises(SystemExit) as exc_ambiguous:
        main(["optimize", "--no-config", str(FIXTURES_DIR)])
    assert exc_ambiguous.value.code == 1
    assert "Multiple Sorceress characters" in capsys.readouterr().err


def test_cli_optimize_missing_native_extension_prints_clean_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def _missing(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Rust extension 'd2savior._native' is not built; run 'make build-rust'.")

    monkeypatch.setattr("d2savior.optimizer.ItemSpec", _missing)
    with pytest.raises(SystemExit) as exc:
        main(["optimize", "--no-config", "sork", str(FIXTURES_DIR)])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "make build-rust" in err


def test_item_level_requirements_uniques_sets_runewords() -> None:
    resolver = GameDataResolver.load()
    d2r = resolver.for_version(0x63)

    griff = d2r.get_unique_item(336)
    assert griff is not None
    assert griff.levelreq == 76

    tal_amu = d2r.get_set_item(77)
    assert tal_amu is not None
    assert tal_amu.levelreq == 67

    ok_s, sork, _ = parse_d2s_file(str(FIXTURES_DIR / "sork.d2s"), resolver=resolver)
    ok_m, mule, _ = parse_d2s_file(str(FIXTURES_DIR / "mule_unique.d2s"), resolver=resolver)
    assert ok_s
    assert sork is not None
    assert ok_m
    assert mule is not None

    # Stealth (Tal 17 + Eth 15) in Studded Leather (base req 0) -> levelreq 17
    stealth = next(it for it in sork.item_list.items if it.code_str.strip() == "stu")
    assert _item_levelreq(stealth, d2r) == 17
    assert _item_to_spec(stealth, "test", d2r, 0x63, char_level=16) is None

    # The Oculus (base Swirling Crystal 37, unique 284 -> levelreq 42)
    oculus = next(it for it in mule.item_list.items if it.code_str.strip() == "oba")
    assert _item_levelreq(oculus, d2r) == 42
    assert _item_to_spec(oculus, "test", d2r, 0x63, char_level=41) is None
    assert _item_to_spec(oculus, "test", d2r, 0x63, char_level=42) is not None

    # Set amulet (base req 0, simulated Tal Rasha's Adjudication set_id=77 -> levelreq 67)
    amu = next(it for it in sork.item_list.items if it.code_str.strip() == "amu")
    assert amu.item_info is not None
    assert amu.item_info.ext_info is not None
    amu.item_info.ext_info.magic_prefix = None
    amu.item_info.ext_info.magic_suffix = None
    amu.item_info.ext_info.set_id = 77
    assert _item_levelreq(amu, d2r) == 67
    assert _item_to_spec(amu, "test", d2r, 0x63, char_level=66) is None


def test_extract_prop_acc_per_level_and_cold_tab(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = GameDataResolver.load().for_version(0x63)
    ok_s, sork, _ = parse_d2s_file(str(FIXTURES_DIR / "sork.d2s"), resolver=resolver)
    assert ok_s
    assert sork is not None
    dummy_item = sork.item_list.items[0]

    fake_props = [
        (216, 12 << 8, [12, 0, 0, 0]),  # Shako +1.5 Life/lvl (val_shift=8, op_param=3)
        (217, 12 << 8, [12, 0, 0, 0]),  # Shako +1.5 Mana/lvl
        (240, 10, [10, 0, 0, 0]),  # Skullder +1.25 MF/lvl
        (188, 0, [2, 1, 1]),  # +1 Cold Skills (Sorc tab 2)
    ]
    monkeypatch.setattr("d2savior.optimizer.collect_item_properties", lambda *a, **kw: fake_props)

    acc = _extract_prop_acc(dummy_item, resolver, version=0x63, char_level=89)
    assert acc.life_per_lvl == (12 * 89) >> 3
    assert acc.mana_per_lvl == (12 * 89) >> 3
    assert acc.life == 0
    assert acc.mana == 0
    assert acc.mf == (10 * 89) >> 3
    assert acc.sorc_skills == 1


def test_item_to_spec_keeps_frw_mdr_fire_absorb_and_max_res(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = GameDataResolver.load().for_version(0x63)
    ok_m, mule, _ = parse_d2s_file(str(FIXTURES_DIR / "mule_unique.d2s"), resolver=resolver)
    assert ok_m
    assert mule is not None
    # Pick a high-level-usable item that classifies to a slot (e.g. a ring, boot, belt, or sword)
    boot_or_ring = next(
        it
        for it in mule.item_list.items
        if _item_to_spec(it, "test", resolver, 0x63, 99) is not None
    )

    for pid, attr, expected in (
        (96, "frw", 30),
        (35, "mdr", 15),
        (142, "fire_abs_pct", 15),
        (40, "max_fr", 15),
    ):
        monkeypatch.setattr(
            "d2savior.optimizer.collect_item_properties",
            lambda *_a, _pid=pid, _val=expected, **_kw: [(_pid, _val, [_val])],
        )
        spec = _item_to_spec(boot_or_ring, "test", resolver, 0x63, char_level=99)
        assert isinstance(spec, ItemSpec)
        assert getattr(spec, attr) == expected

    # An item with no useful stats at all is still dropped
    monkeypatch.setattr(
        "d2savior.optimizer.collect_item_properties",
        lambda *_a, **_kw: [(16, 100, [100])],  # +100% enhanced defense only
    )
    assert _item_to_spec(boot_or_ring, "test", resolver, 0x63, char_level=99) is None


def test_max_resistance_cap_in_evaluate_and_optimize() -> None:
    items = [
        ItemSpec("Spirit Sword", "weapon", "test", all_skills=2, fcr=34, fhr=55),
        ItemSpec(
            "Spirit Shield", "shield", "test", all_skills=2, fcr=34, fhr=55, lr=35, cr=35, pr=35
        ),
        ItemSpec("Tiara", "helm", "test", sorc_skills=2, fr=40, lr=40, cr=40, pr=40),
        ItemSpec("Guardian Angel", "armor", "test", max_fr=15, max_lr=15, max_cr=15, max_pr=15),
        ItemSpec("Amulet", "amulet", "test", sorc_skills=1, fcr=10, fr=30, lr=30, cr=30, pr=30),
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
            base_hell_res=-70,
            mode="power",
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
            base_hell_res=-70,
            mode="max-res",
        ),
    )
    assert res_max[0].items[3].name == "Guardian Angel"
    assert res_max[0].fr == 95
    assert res_max[0].lr == 86


def test_classify_slot_rejects_two_handed_and_1or2handed_weapons() -> None:
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
        assert _classify_slot(_make_item(two_handed_code), resolver) is None

    for one_handed_code in ("crs", "ob1"):
        classified = _classify_slot(_make_item(one_handed_code), resolver)
        assert classified is not None
        assert classified[0] == "weapon"


def test_unique_charm_limit_prevents_duplicates() -> None:
    items = [
        ItemSpec("Spirit Sword", "weapon", "test", all_skills=2, fcr=35, fhr=55),
        ItemSpec(
            "Spirit Shield", "shield", "test", all_skills=2, fcr=35, fhr=55, lr=35, cr=35, pr=35
        ),
        ItemSpec("Tiara", "helm", "test", sorc_skills=2, fcr=20, fr=40, lr=40, cr=40, pr=40),
        ItemSpec("Skin", "armor", "test", all_skills=1, fcr=30, fr=35, lr=35, cr=35, pr=35),
        ItemSpec("Amulet", "amulet", "test", sorc_skills=2, fcr=15, fr=30, lr=30, cr=30, pr=30),
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
            base_hell_res=-70,
            mode="power",
        ),
    )
    assert len(res) == 1
    assert sum(1 for c in res[0].charms if c.unique_id == 400) == 1
    assert any(c.name == "Chilling GC" for c in res[0].charms)


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


def test_blizzard_base_skills_from_save_and_fallback() -> None:
    resolver = GameDataResolver.load()
    ok_s, sork, _ = parse_d2s_file(str(FIXTURES_DIR / "sork.d2s"), resolver=resolver)
    assert ok_s
    assert sork is not None

    presets = select_sorc_presets(sork, build="tz")
    _, c = presets[0]
    # sork.d2s has Blizzard=20 (idx 23), Ice Bolt=1 (idx 3), Ice Blast=14 (idx 9), Glacial Spike=20 (idx 19), Cold Mastery=20 (idx 29)
    assert (c.blizz_base_lvl, c.blizz_syn_pts, c.cm_base_lvl) == (20, 35, 20)

    _, syn_default, _ = blizzard_damage(5)
    _, syn_custom, cm_custom = blizzard_damage_with_base(5, 20, 35, 20)
    assert syn_custom < syn_default
    assert cm_custom == -(20 + 5 * (25 - 1))

    # Fallback to (20, 54, 20) when Blizzard has 0 allocated hard points
    assert sork.skills is not None
    sork.skills.skill_levels[23] = 0
    fallback_c = select_sorc_presets(sork, build="tz")[0][1]
    assert (fallback_c.blizz_base_lvl, fallback_c.blizz_syn_pts, fallback_c.cm_base_lvl) == (
        20,
        54,
        20,
    )


def test_single_skill_blizzard_orb_extraction_and_ranking(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = GameDataResolver.load().for_version(0x63)
    ok_m, mule, _ = parse_d2s_file(str(FIXTURES_DIR / "mule_unique.d2s"), resolver=resolver)
    assert ok_m
    assert mule is not None
    orb = next(it for it in mule.item_list.items if it.code_str.strip() == "oba")

    monkeypatch.setattr(
        "d2savior.optimizer.collect_item_properties",
        lambda *_a, **_kw: [(83, 0, [1, 2]), (107, 0, [59, 3]), (107, 0, [65, 1])],
    )
    orb_spec = _item_to_spec(orb, "test", resolver, 0x63, char_level=99)
    assert isinstance(orb_spec, ItemSpec)
    assert orb_spec.sorc_skills == 2
    assert orb_spec.blizz_skills == 3
    assert orb_spec.cm_skills == 1

    items = [
        ItemSpec(
            "Sorc +3 Orb", "weapon", "test", sorc_skills=3, fcr=30, fr=20, lr=20, cr=20, pr=20
        ),
        ItemSpec(
            "Sorc +2/+3 Blizz Orb",
            "weapon",
            "test",
            sorc_skills=2,
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
            "Tiara", "helm", "test", sorc_skills=2, fcr=20, fhr=20, fr=30, lr=30, cr=30, pr=30
        ),
        ItemSpec(
            "Armor", "armor", "test", all_skills=1, fcr=20, fhr=20, fr=40, lr=40, cr=40, pr=40
        ),
        ItemSpec("Amulet", "amulet", "test", sorc_skills=2, fcr=10, fr=30, lr=30, cr=30, pr=30),
        ItemSpec("Belt", "belt", "test", fr=30, lr=30, cr=30, pr=30),
        ItemSpec("Trangs", "gloves", "test", fcr=20, fr=30, lr=30, cr=30, pr=30),
        ItemSpec("Boots", "boots", "test", fr=40, lr=40, cr=40, pr=40),
        ItemSpec("Ring A", "ring", "test", fcr=10, fr=20, lr=20, cr=20, pr=20),
        ItemSpec("Ring B", "ring", "test", fcr=10, fr=20, lr=20, cr=20, pr=20),
    ]
    res = optimize_builds(
        items,
        [],
        BuildConstraints(min_pr=75, base_hell_res=-70, skill_slack=2, limit=2),
    )
    assert len(res) == 2
    assert res[0].items[0].name == "Sorc +2/+3 Blizz Orb"
    assert res[1].items[0].name == "Sorc +3 Orb"
    assert res[0].blizz_avg > res[1].blizz_avg


def test_detect_cta_bo_bonus_and_excludes_swap_cta(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = GameDataResolver.load()
    ok_s, sork, _ = parse_d2s_file(str(FIXTURES_DIR / "sork.d2s"), resolver=resolver)
    assert ok_s
    assert sork is not None
    # Default fallback when no CTA is present
    assert _detect_cta_bo_bonus([sork], [], resolver) == 4

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

    monkeypatch.setattr("d2savior.optimizer.collect_item_properties", _fake_props)
    assert _detect_cta_bo_bonus([sork], [], resolver) == 7
    presets = select_sorc_presets(sork, build="tz", resolver=resolver)
    assert presets[0][1].bo_base_bonus == 7

    items, _ = extract_pool(sork, resolver=resolver)
    assert not any("Swap" in it.loc for it in items)


def test_belt_slots_and_defense_prefer_upped_goldwrap() -> None:
    resolver = GameDataResolver.load()
    ok_s, sork, _ = parse_d2s_file(str(FIXTURES_DIR / "sork.d2s"), resolver=resolver)
    ok_m, mule, _ = parse_d2s_file(str(FIXTURES_DIR / "mule_unique.d2s"), resolver=resolver)
    assert ok_s
    assert sork is not None
    assert ok_m
    assert mule is not None

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
        ItemSpec("Helm", "helm", "test", sorc_skills=2, fcr=20, fr=40, lr=40, cr=40),
        ItemSpec("Skullder", "armor", "test", all_skills=1, mf=110),
        ItemSpec("Amulet", "amulet", "test", sorc_skills=2, fcr=15, fr=30, lr=30, cr=30),
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
            base_str=156,
            base_hell_res=-70,
            limit=2,
        ),
    )
    assert len(res) == 2
    assert res[0].items[5].name == "Goldwrap (Battle Belt)"
    assert res[0].items[5].loc == "sork Stash"
