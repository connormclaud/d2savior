"""Pure-Python unit tests for optimizer modules that run without d2savior._native."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest

from d2savior.cli import parse_d2i_file, parse_d2s_file
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass, EquipSlot, ItemLocation, StoredIn
from d2savior.core.item import D2Item, ExtItemInfo, ItemInfo, TypeSpecificInfo
from d2savior.core.item_name import LongName
from d2savior.core.property_list import PropertyList
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash, StashTab
from d2savior.optimizer.common import (
    _compute_anya_bonus,
    _item_cta_bo,
    _item_levelreq,
    _long_name_levelreq,
    detect_cta_bo_bonus,
    validate_paladin,
    validate_sorceress,
    validate_supported_class,
)
from d2savior.optimizer.extract import (
    _apply_paladin_prop,
    _apply_props_to_acc,
    _apply_sorc_prop,
    _char_item_locality_rank,
    _classify_slot,
    _effective_req,
    _extract_set_bonuses,
    _format_item_location,
    _item_to_spec,
    _PropAcc,
    _resolve_item_set_info,
    extract_pool,
)
from d2savior.optimizer.native import BuildResult, CharmSpec
from d2savior.optimizer.paladin import (
    _build_paladin_baseline,
    _describe_lower_fhr_tradeoff,
    _describe_paladin_tradeoff,
    _format_opt1_label,
    _paladin_passive_max_res,
    _result_dedup_key,
    _step_below_bp,
    optimize_paladin_leveling,
    paladin_offense_profile,
    paladin_primary_skill_info,
    select_paladin_max_res_preset,
)
from d2savior.optimizer.report import (
    _charm_key,
    _format_charm_diff_lines,
    _is_inv_loc,
    format_build_report,
    format_paladin_leveling_report,
)
from d2savior.optimizer.sorc import _extract_blizz_base_skills, select_sorc_presets

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@dataclass
class _FakeItemSpec:
    name: str
    slot: str
    loc: str
    all_skills: int = 0
    sorc_skills: int = 0
    fcr: int = 0
    fhr: int = 0
    frw: int = 0
    fr: int = 0
    lr: int = 0
    cr: int = 0
    pr: int = 0
    mf: int = 0
    life: int = 0
    mana: int = 0
    vit: int = 0
    ene: int = 0
    pct_mana: int = 0
    mdr: int = 0
    dr_flat: int = 0
    fire_abs_pct: int = 0
    str_bonus: int = 0
    dex_bonus: int = 0
    req_str: int = 0
    req_dex: int = 0
    max_fr: int = 0
    max_lr: int = 0
    max_cr: int = 0
    max_pr: int = 0
    life_per_lvl: int = 0
    mana_per_lvl: int = 0
    blizz_skills: int = 0
    cm_skills: int = 0
    defense: int = 0
    belt_slots: int = 0
    pal_skills: int = 0
    primary_skill: int = 0
    ias: int = 0
    cb: int = 0
    cbf: int = 0
    pdr_pct: int = 0
    life_leech: int = 0
    set_group: int = 0
    set_item_id: int = 0
    set_bonuses: list[tuple[int, object]] = field(default_factory=list)
    wsm: int = 0
    wclass: str = ""
    action_skill_bonus: int = 0
    aura_skill_bonus: int = 0
    off_ed: int = 0
    flat_phys_2x: int = 0
    flat_elem_2x: int = 0
    wep_phys_2x: int = 0
    wep_str_pct: int = 0
    wep_dex_pct: int = 0
    can_zeal: bool = False


@dataclass
class _FakeCharmSpec:
    name: str
    size: int
    loc: str
    fhr: int = 0
    fr: int = 0
    lr: int = 0
    cr: int = 0
    pr: int = 0
    mf: int = 0
    life: int = 0
    mana: int = 0
    frw: int = 0
    light_skills: int = 0
    str_bonus: int = 0
    dex_bonus: int = 0
    skills: int = 0
    action_skills: int = 0
    aura_skills: int = 0
    unique_id: int | None = None
    cold_sunder: bool = False


@dataclass
class _FakeConstraints:
    allow_mf: bool = True
    min_fcr: int = 0
    min_fhr: int = 0
    min_fr: int = 0
    min_lr: int = 0
    min_cr: int = 0
    min_pr: int = 0
    max_charm_slots: int = 23
    mode: str = "power"
    base_life: int = 0
    base_mana: int = 0
    base_hell_res: int = -100
    base_str: int = 0
    base_dex: int = 0
    bo_base_bonus: int = 4
    limit: int = 3
    blizz_base_lvl: int = 20
    blizz_syn_pts: int = 54
    cm_base_lvl: int = 20
    char_class: int = int(CharClass.SORCERESS)
    base_max_fr: int = 0
    base_max_lr: int = 0
    base_max_cr: int = 0
    base_max_pr: int = 0
    use_bo: bool = True
    fixed_gear: bool = False
    offense: str = "caster"
    aura_hit_dmg: list[float] = field(default_factory=list)
    aura_pulse_dps: list[float] = field(default_factory=list)
    action_ed: list[int] = field(default_factory=list)
    action_hits: list[int] = field(default_factory=list)
    has_aura: bool = False


@dataclass
class _FakeBuildResult:
    items: list[_FakeItemSpec] = field(default_factory=list)
    charms: list[_FakeCharmSpec] = field(default_factory=list)
    skills: int = 0
    primary_skill_bonus: int = 0
    blizz_avg: float = 0.0
    cm_pierce: int = -115
    fcr: int = 0
    fcr_bp: int = 0
    fhr: int = 0
    fhr_bp: int = 0
    frw: int = 0
    ias: int = 0
    ias_bp: int = 0
    ias_frames: int = 12
    cb: int = 0
    cbf: bool = False
    pdr_pct: int = 0
    life_leech: int = 0
    fr: int = 0
    lr: int = 0
    cr: int = 0
    pr: int = 0
    fr_raw: int = 0
    lr_raw: int = 0
    cr_raw: int = 0
    pr_raw: int = 0
    mf: int = 0
    bo_lvl: int = 0
    life_no_bo: int = 500
    life_bo: int = 500
    mana_bo: int = 100
    charm_slots: int = 0
    evaluated_candidates: int = 12


def _as_result(res: _FakeBuildResult) -> BuildResult:
    return cast(BuildResult, res)


def _as_charm(charm: _FakeCharmSpec) -> CharmSpec:
    return cast(CharmSpec, charm)


def _load_char(filename: str) -> tuple[D2SStruct, GameDataResolver]:
    resolver = GameDataResolver.load()
    ok, char_data, _ = parse_d2s_file(str(FIXTURES_DIR / filename), resolver=resolver)
    assert ok
    assert char_data is not None
    return char_data, resolver


def test_common_validators_anya_levelreq_and_cta_bo(monkeypatch: pytest.MonkeyPatch) -> None:
    sork, resolver = _load_char("sork.d2s")
    mule, _ = _load_char("mule_unique.d2s")
    d2r = resolver.for_version(0x63)

    validate_sorceress(sork)
    validate_paladin(mule)
    validate_supported_class(sork)
    validate_supported_class(mule)
    with pytest.raises(ValueError, match="expected Sorceress"):
        validate_sorceress(mule)
    with pytest.raises(ValueError, match="expected Paladin"):
        validate_paladin(sork)

    empty_char = D2SStruct()
    empty_char.char_class = int(CharClass.BARBARIAN)
    with pytest.raises(ValueError, match="expected Sorceress or Paladin"):
        validate_supported_class(empty_char)

    assert _compute_anya_bonus(empty_char) == 0
    assert _compute_anya_bonus(sork) >= 0

    empty_ln = LongName()
    assert _long_name_levelreq(empty_ln, d2r, is_crafted=False) == 0

    pref_info = d2r.get_magic_prefix(1)
    suff_info = d2r.get_magic_suffix(1)
    assert pref_info is not None
    assert suff_info is not None
    ln = LongName()
    ln.pref_1 = 1
    ln.suff_1 = 1
    expected_rare = max(pref_info.levelreq, suff_info.levelreq)
    assert _long_name_levelreq(ln, d2r, is_crafted=False) == expected_rare
    assert _long_name_levelreq(ln, d2r, is_crafted=True) == expected_rare + 10 + 3 * 2

    rare_item = D2Item()
    rare_item.type_name = b"rin "
    rare_item.item_info = ItemInfo()
    rare_item.item_info.ext_info = ExtItemInfo()
    rare_item.item_info.ext_info.rare_name = ln
    assert _item_levelreq(rare_item, d2r) == expected_rare

    craft_item = D2Item()
    craft_item.type_name = b"rin "
    craft_item.item_info = ItemInfo()
    craft_item.item_info.ext_info = ExtItemInfo()
    craft_item.item_info.ext_info.craft_name = ln
    assert _item_levelreq(craft_item, d2r) == expected_rare + 10 + 3 * 2

    # Runeword without populated gem_items falls back to runeword rune_codes
    rw_id = next(iter(d2r.data.runewords))
    rw_item = D2Item()
    rw_item.type_name = b"crs "
    rw_item.is_runeword = True
    rw_item.item_info = ItemInfo()
    rw_item.item_info.ext_info = ExtItemInfo()
    rw_item.item_info.ext_info.rune_id = rw_id
    assert _item_levelreq(rw_item, d2r) >= 0

    # CTA Battle Orders detection across chars and stashes (including empty tab and max_level filter)
    cta_a = D2Item()
    cta_a.type_name = b"crs "
    cta_b = D2Item()
    cta_b.type_name = b"fla "
    plain = D2Item()
    plain.type_name = b"rin "
    sork.item_list.items = [plain, cta_a]

    stash = SharedStash()
    empty_tab = StashTab()
    empty_tab.items = None
    filled_tab = StashTab()
    filled_tab.item_format = 0x63
    filled_tab.items = sork.item_list.__class__()
    filled_tab.items.items = [cta_b]
    stash.tabs = [empty_tab, filled_tab]

    def _fake_props(item: D2Item, **_kw: object) -> list[tuple[int, int, list[int]]]:
        if item is cta_a:
            return [(127, 1, [1]), (97, 0, [149, 4])]
        if item is cta_b:
            return [(127, 1, [1]), (97, 0, [149, 6])]
        return []

    monkeypatch.setattr("d2savior.optimizer.common.collect_item_properties", _fake_props)
    assert _item_cta_bo(plain, d2r, 0x63) is None
    assert _item_cta_bo(cta_a, d2r, 0x63) == 5
    assert detect_cta_bo_bonus([sork], [stash], resolver, default=4) == 7

    # max_level filter skips items above threshold and falls back to default
    monkeypatch.setattr(
        "d2savior.optimizer.common._item_levelreq",
        lambda it, _res: 57 if it in (cta_a, cta_b) else 1,
    )
    assert detect_cta_bo_bonus([sork], [stash], resolver, max_level=30, default=0) == 0


def test_sorc_presets_and_blizz_base_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    sork, resolver = _load_char("sork.d2s")
    mule, _ = _load_char("mule_unique.d2s")

    assert _extract_blizz_base_skills(sork) == (20, 35, 20)
    assert sork.skills is not None
    sork.skills.skill_levels[23] = 0
    assert _extract_blizz_base_skills(sork) == (20, 54, 20)
    sork.skills.skill_levels = []
    assert _extract_blizz_base_skills(sork) == (20, 54, 20)

    with pytest.raises(ValueError, match="expected Sorceress"):
        select_sorc_presets(mule)
    with pytest.raises(ValueError, match="Unknown build preset"):
        select_sorc_presets(sork, build="invalid")

    monkeypatch.setattr("d2savior.optimizer.common.BuildConstraints", _FakeConstraints)
    all_presets = select_sorc_presets(sork, build="all", max_charm_slots=20, limit=2)
    assert len(all_presets) == 5
    mf_presets = select_sorc_presets(sork, build="mf", resolver=resolver, bo_base_bonus=6)
    assert len(mf_presets) == 2
    assert cast(_FakeConstraints, mf_presets[0][1]).bo_base_bonus == 6
    assert cast(_FakeConstraints, mf_presets[0][1]).mode == "mf"
    tz_presets = select_sorc_presets(sork, build="tz", resolver=resolver, bo_base_bonus=4)
    assert len(tz_presets) == 1
    assert cast(_FakeConstraints, tz_presets[0][1]).min_fcr == 105


def test_paladin_pure_helpers_and_tradeoff_descriptions() -> None:
    mule, _ = _load_char("mule_unique.d2s")

    assert paladin_offense_profile("smite") == "smite"
    assert paladin_offense_profile("hammer") == "caster"
    assert paladin_offense_profile("foh") == "caster"
    assert paladin_offense_profile("holy-bolt") == "caster"
    assert paladin_offense_profile("zeal") == "zeal"
    assert paladin_offense_profile("holy-fire", mule) == "melee"
    assert mule.skills is not None
    mule.skills.skill_levels[10] = 4  # Zeal
    assert paladin_offense_profile("holy-fire", mule) == "zeal"
    assert paladin_offense_profile("charge", mule) == "melee"

    assert paladin_primary_skill_info(mule, "unknown") == (None, 0)
    assert paladin_primary_skill_info(mule, "leveling") == (None, 0)
    mule.skills.skill_levels[6] = 18  # Holy Fire
    assert paladin_primary_skill_info(mule, "holy-fire") == ("Holy Fire", 18)

    mule.skills.skill_levels[4] = 11  # Resist Fire -> +5
    mule.skills.skill_levels[14] = 6  # Resist Lightning -> +3
    mule.skills.skill_levels[9] = 4  # Resist Cold -> +2
    assert _paladin_passive_max_res(mule) == (5, 3, 2)
    empty_char = D2SStruct()
    assert _paladin_passive_max_res(empty_char) == (0, 0, 0)

    assert _step_below_bp(0, (0, 7, 15, 27)) is None
    assert _step_below_bp(27, (0, 7, 15, 27)) == 15

    r1 = _FakeBuildResult(
        fhr_bp=48,
        fcr_bp=48,
        skills=2,
        fr=50,
        lr=50,
        cr=50,
        pr=50,
        ias_bp=20,
        cb=10,
        cbf=False,
        life_bo=500,
        frw=20,
        items=[_FakeItemSpec("A", "ring", "inv"), _FakeItemSpec("B", "helm", "inv")],
        charms=[_FakeCharmSpec("C1", 1, "inv"), _FakeCharmSpec("C2", 1, "inv")],
    )
    r1_reordered = _FakeBuildResult(
        fhr_bp=48,
        fcr_bp=48,
        skills=2,
        fr=50,
        lr=50,
        cr=50,
        pr=50,
        ias_bp=20,
        cb=10,
        cbf=False,
        life_bo=500,
        frw=20,
        items=[_FakeItemSpec("B", "helm", "inv"), _FakeItemSpec("A", "ring", "inv")],
        charms=[_FakeCharmSpec("C2", 1, "inv"), _FakeCharmSpec("C1", 1, "inv")],
    )
    assert _result_dedup_key(_as_result(r1)) == _result_dedup_key(_as_result(r1_reordered))
    assert _result_dedup_key(_as_result(r1), is_caster=True)[1] == 48

    assert "48% FCR / 48% FHR" in _format_opt1_label(_as_result(r1), is_caster=True)
    assert "48% FHR, 5f" in _format_opt1_label(_as_result(r1), is_caster=False)

    # All branches of _describe_lower_fhr_tradeoff
    base = _as_result(r1)
    assert "Higher Skills & Resists" in _describe_lower_fhr_tradeoff(
        base, _as_result(_FakeBuildResult(fhr_bp=27)), sk_diff=1, res_diff=10
    )
    assert "Higher IAS & Skills" in _describe_lower_fhr_tradeoff(
        base, _as_result(_FakeBuildResult(fhr_bp=27, ias_bp=30)), sk_diff=1, res_diff=0
    )
    assert "Higher IAS & Resists" in _describe_lower_fhr_tradeoff(
        base, _as_result(_FakeBuildResult(fhr_bp=27, ias_bp=30)), sk_diff=0, res_diff=10
    )
    assert "Better Resists & FRW" in _describe_lower_fhr_tradeoff(
        base, _as_result(_FakeBuildResult(fhr_bp=27, frw=35)), sk_diff=0, res_diff=10
    )
    assert "Better Resists" in _describe_lower_fhr_tradeoff(
        base, _as_result(_FakeBuildResult(fhr_bp=27, frw=10)), sk_diff=0, res_diff=10
    )
    assert "Higher IAS" in _describe_lower_fhr_tradeoff(
        base, _as_result(_FakeBuildResult(fhr_bp=27, ias_bp=30)), sk_diff=0, res_diff=0
    )
    assert "Higher Skills" in _describe_lower_fhr_tradeoff(
        base, _as_result(_FakeBuildResult(fhr_bp=27)), sk_diff=1, res_diff=0
    )
    assert "Higher Crushing Blow" in _describe_lower_fhr_tradeoff(
        base, _as_result(_FakeBuildResult(fhr_bp=27, cb=35)), sk_diff=0, res_diff=0
    )
    assert "Cannot Be Frozen" in _describe_lower_fhr_tradeoff(
        base, _as_result(_FakeBuildResult(fhr_bp=27, cbf=True)), sk_diff=0, res_diff=0
    )
    assert "More Life / FRW" in _describe_lower_fhr_tradeoff(
        base, _as_result(_FakeBuildResult(fhr_bp=27, life_bo=600)), sk_diff=0, res_diff=0
    )
    assert (
        _describe_lower_fhr_tradeoff(
            base, _as_result(_FakeBuildResult(fhr_bp=27, life_bo=400)), sk_diff=0, res_diff=0
        )
        == "Lower FHR BP (27%)"
    )

    # All branches of _describe_paladin_tradeoff
    assert "Lower FHR BP (27%)" in _describe_paladin_tradeoff(
        base,
        _as_result(_FakeBuildResult(fhr_bp=27, fr=60, lr=50, cr=50, pr=50)),
        is_caster=False,
        is_smite=False,
    )
    assert (
        _describe_paladin_tradeoff(
            base,
            _as_result(_FakeBuildResult(fhr_bp=48, fcr_bp=30, fr=70, lr=50, cr=50, pr=50)),
            is_caster=True,
            is_smite=False,
        )
        == "Lower FCR BP (30%) — Better Resists"
    )
    assert (
        _describe_paladin_tradeoff(
            base,
            _as_result(
                _FakeBuildResult(fhr_bp=48, fcr_bp=30, skills=4, fr=50, lr=50, cr=50, pr=50)
            ),
            is_caster=True,
            is_smite=False,
        )
        == "Lower FCR BP (30%) — Higher Skills"
    )
    assert (
        _describe_paladin_tradeoff(
            base,
            _as_result(
                _FakeBuildResult(fhr_bp=48, fcr_bp=30, skills=2, fr=50, lr=50, cr=50, pr=50)
            ),
            is_caster=True,
            is_smite=False,
        )
        == "Lower FCR BP (30%)"
    )
    assert (
        _describe_paladin_tradeoff(
            base,
            _as_result(_FakeBuildResult(fhr_bp=48, fcr_bp=48, fr=75, lr=50, cr=50, pr=50)),
            is_caster=False,
            is_smite=False,
        )
        == "Max Resist Cap"
    )
    assert (
        _describe_paladin_tradeoff(
            base,
            _as_result(_FakeBuildResult(fhr_bp=48, fcr_bp=48, cb=35, fr=50, lr=50, cr=50, pr=50)),
            is_caster=False,
            is_smite=True,
        )
        == "Max Smite Offense (CB/IAS)"
    )
    assert (
        _describe_paladin_tradeoff(
            base,
            _as_result(
                _FakeBuildResult(fhr_bp=48, fcr_bp=48, ias_bp=40, fr=50, lr=50, cr=50, pr=50)
            ),
            is_caster=False,
            is_smite=False,
        )
        == "Higher IAS"
    )
    assert (
        _describe_paladin_tradeoff(
            base,
            _as_result(
                _FakeBuildResult(fhr_bp=48, fcr_bp=48, skills=5, fr=50, lr=50, cr=50, pr=50)
            ),
            is_caster=False,
            is_smite=False,
        )
        == "Max Skill Damage"
    )
    assert (
        _describe_paladin_tradeoff(
            base,
            _as_result(
                _FakeBuildResult(
                    fhr_bp=48, fcr_bp=48, skills=2, cbf=True, fr=50, lr=50, cr=50, pr=50
                )
            ),
            is_caster=False,
            is_smite=False,
        )
        == "Cannot Be Frozen"
    )
    assert (
        _describe_paladin_tradeoff(
            base,
            _as_result(
                _FakeBuildResult(
                    fhr_bp=48, fcr_bp=48, skills=2, life_bo=650, fr=50, lr=50, cr=50, pr=50
                )
            ),
            is_caster=False,
            is_smite=False,
        )
        == "More Life / FRW"
    )
    assert (
        _describe_paladin_tradeoff(
            base,
            _as_result(
                _FakeBuildResult(
                    fhr_bp=48, fcr_bp=48, skills=2, life_bo=400, fr=50, lr=50, cr=50, pr=50
                )
            ),
            is_caster=False,
            is_smite=False,
        )
        == "Balanced Alternative"
    )


def test_paladin_baseline_presets_and_leveling_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    mule, resolver = _load_char("mule_unique.d2s")
    assert mule.skills is not None
    mule.skills.skill_levels = [0] * 30
    mule.skills.skill_levels[6] = 20  # Holy Fire

    monkeypatch.setattr("d2savior.optimizer.common.BuildConstraints", _FakeConstraints)

    baseline, lvl, diff, spec = _build_paladin_baseline(
        mule,
        spec=None,
        max_charm_slots=20,
        extra_chars=(),
        stashes=(),
        resolver=None,
        bo_base_bonus=None,
        keep_equipped=False,
    )
    assert lvl >= 1
    assert diff == "Normal"
    assert spec == "holy-fire"
    assert baseline.bo_base_bonus == 0

    with pytest.raises(ValueError, match="Unknown Paladin spec"):
        _build_paladin_baseline(
            mule,
            spec="bogus",
            max_charm_slots=20,
            extra_chars=(),
            stashes=(),
            resolver=resolver,
            bo_base_bonus=0,
            keep_equipped=False,
        )

    title_mr, c_mr, spec_mr = select_paladin_max_res_preset(
        mule, resolver=resolver, bo_base_bonus=0
    )
    assert "Paladin Max Resist" in title_mr
    assert spec_mr == "holy-fire"
    assert cast(_FakeConstraints, c_mr).mode == "max-res"

    # limit <= 0 returns early
    t0, opts0, _, _ = optimize_paladin_leveling(
        mule, [], [], limit=0, resolver=resolver, bo_base_bonus=0
    )
    assert "Holy Fire" in t0
    assert opts0 == []

    # Empty optimize_builds -> opt1 is None
    monkeypatch.setattr("d2savior.optimizer.paladin.optimize_builds", lambda _i, _c, _cn: [])
    _, opts_none, _, _ = optimize_paladin_leveling(
        mule, [], [], limit=3, resolver=resolver, bo_base_bonus=0
    )
    assert opts_none == []

    # Multi-option melee search + limit==1 + caster FCR probing
    opt_high = _as_result(
        _FakeBuildResult(fhr_bp=48, fcr_bp=30, skills=1, fr=50, lr=50, cr=50, pr=50)
    )
    opt_mid = _as_result(
        _FakeBuildResult(fhr_bp=27, fcr_bp=30, skills=2, fr=75, lr=75, cr=75, pr=75)
    )
    opt_low = _as_result(
        _FakeBuildResult(fhr_bp=15, fcr_bp=18, skills=3, fr=75, lr=75, cr=75, pr=75)
    )

    def _fake_opt(_items: object, _charms: object, c: _FakeConstraints) -> list[BuildResult]:
        if c.min_fcr > 30:
            return []
        if c.min_fhr > 48:
            return []
        if c.min_fhr == 48:
            return [opt_high]
        if c.min_fhr == 27:
            return [opt_mid]
        if c.mode == "leveling":
            return [opt_low]
        return [opt_mid, opt_low]

    monkeypatch.setattr("d2savior.optimizer.paladin.optimize_builds", _fake_opt)
    _, opts_one, _, _ = optimize_paladin_leveling(
        mule, [], [], limit=1, resolver=resolver, bo_base_bonus=0
    )
    assert len(opts_one) == 1
    assert "48% FHR" in opts_one[0][0]

    _, opts_three, _, _ = optimize_paladin_leveling(
        mule, [], [], limit=3, resolver=resolver, bo_base_bonus=0
    )
    assert len(opts_three) == 3

    _, opts_caster, spec_caster, _ = optimize_paladin_leveling(
        mule, [], [], spec="hammer", limit=4, resolver=resolver, bo_base_bonus=0
    )
    assert spec_caster == "hammer"
    assert len(opts_caster) >= 2
    assert "30% FCR" in opts_caster[0][0]


def test_report_formatting_sorc_paladin_and_charms() -> None:
    assert _is_inv_loc("inv")
    assert _is_inv_loc("sork Inv")
    assert not _is_inv_loc("Stash Tab 1")

    c_inv1 = _as_charm(_FakeCharmSpec("Vita SC", 1, "sork Inv", life=20))
    c_inv2 = _as_charm(_FakeCharmSpec("Vita SC", 1, "sork Inv", life=20))
    c_drop = _as_charm(_FakeCharmSpec("Drop GC", 3, "sork Inv", cr=10))
    c_add = _as_charm(_FakeCharmSpec("Luck SC", 1, "Stash Tab 2", mf=7))
    c_noloc = _as_charm(_FakeCharmSpec("Plain SC", 1, ""))
    assert _charm_key(c_inv1) == _charm_key(c_inv2)
    assert _format_charm_diff_lines([], []) == []

    diff_lines = _format_charm_diff_lines(
        [c_inv1, c_add, c_noloc],
        [c_inv1, c_inv2, c_drop, c_add],
        primary_inv_loc="sork Inv",
    )
    joined = "\n".join(diff_lines)
    assert "remove: Vita SC, Drop GC" in joined
    assert "keep  : Vita SC" in joined
    assert "add   : Luck SC [Stash Tab 2], Plain SC" in joined

    # Fallback when pool_charms is empty: inventory charm still shows up in keep
    diff_fallback = "\n".join(_format_charm_diff_lines([c_inv1], []))
    assert "remove: none" in diff_fallback
    assert "keep  : Vita SC" in diff_fallback
    assert "add   : none" in diff_fallback

    # Sorceress report
    sorc_res = _as_result(
        _FakeBuildResult(
            items=[
                _FakeItemSpec("Spirit", "weapon", "sork Equipped"),
                _FakeItemSpec("X", "ring", ""),
            ],
            charms=[_FakeCharmSpec("Vita SC", 1, "sork Inv", life=20)],
            skills=8,
            blizz_avg=3500.0,
            cm_pierce=-150,
            fcr=105,
            fcr_bp=105,
            fhr=86,
            fhr_bp=86,
            bo_lvl=6,
            life_no_bo=900,
            life_bo=1300,
            mana_bo=500,
            charm_slots=1,
        )
    )
    sorc_report = format_build_report("Sorc Test", [sorc_res], [c_inv1])
    assert "Blizz Avg: 3500" in sorc_report
    assert "- weapon  : Spirit (sork Equipped)" in sorc_report
    assert "- ring    : X" in sorc_report

    # Paladin reports: with primary skill + BO + DR/LL, and without primary skill + BO=0
    pal_res_bo = _as_result(
        _FakeBuildResult(
            items=[_FakeItemSpec("Steel", "weapon", "smite Equipped")],
            charms=[_FakeCharmSpec("Ruby SC", 1, "smite Inv", fr=11)],
            skills=2,
            primary_skill_bonus=4,
            ias=30,
            ias_bp=30,
            ias_frames=10,
            cb=25,
            cbf=True,
            pdr_pct=15,
            life_leech=7,
            fhr=48,
            fhr_bp=48,
            fcr=10,
            fcr_bp=9,
            bo_lvl=5,
            life_no_bo=600,
            life_bo=850,
            mana_bo=150,
        )
    )
    pal_res_nobo = _as_result(_FakeBuildResult(skills=1, bo_lvl=0, life_no_bo=500, mana_bo=80))
    pal_report = format_build_report(
        "Paladin Max Resist",
        [pal_res_bo],
        char_class=int(CharClass.PALADIN),
        diff_name="Normal",
        primary_skill_name="Holy Fire",
        primary_skill_base=20,
        primary_inv_loc="smite Inv",
    )
    assert "Holy Fire lvl 26" in pal_report
    assert "DR: 15% | LL: 7%" in pal_report
    assert "BO lvl 5: 850" in pal_report

    assert "No loadout found" in format_paladin_leveling_report("Empty Pal", [])
    lvl_report = format_paladin_leveling_report(
        "Paladin Leveling",
        [("High Breakpoint", pal_res_nobo)],
        diff_name="Nightmare",
        primary_skill_name=None,
    )
    assert "Option #1: High Breakpoint" in lvl_report
    assert "Life: 500 | Mana: 80" in lvl_report


def test_extract_pure_helpers_and_pool_with_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = GameDataResolver.load()
    d2r = resolver.for_version(0x63)

    # _format_item_location and _char_item_locality_rank
    it = D2Item()
    it.location = ItemLocation.EQUIPPED.value
    it.position = EquipSlot.WEAPON_I.value
    assert _format_item_location("hero", it) == "hero Equipped"
    assert _char_item_locality_rank(it) == 0

    it.position = EquipSlot.WEAPON_II.value
    assert _format_item_location("hero", it) == "hero Swap"
    assert _char_item_locality_rank(it) == 1

    it.location = ItemLocation.STORED.value
    it.stored_in = StoredIn.INVENTORY.value
    assert _format_item_location("hero", it) == "hero Inv"
    assert _char_item_locality_rank(it) == 2

    it.stored_in = StoredIn.STASH.value
    assert _format_item_location("hero", it) == "hero Stash"
    assert _char_item_locality_rank(it) == 3

    it.stored_in = StoredIn.CUBE.value
    assert _format_item_location("hero", it) == "hero"
    assert _char_item_locality_rank(it) == 4

    # _effective_req
    assert _effective_req(0, True, -20) == 0
    assert _effective_req(100, False, 0) == 100
    assert _effective_req(100, True, -15) == 76

    # _classify_slot edge cases
    unknown = D2Item()
    unknown.type_name = b"zzzz"
    assert _classify_slot(unknown, d2r) is None
    potion = D2Item()
    potion.type_name = b"hp1 "
    assert _classify_slot(potion, d2r) is None
    amu = D2Item()
    amu.type_name = b"amu "
    assert _classify_slot(amu, d2r) == ("amulet", 0, 0)
    ring = D2Item()
    ring.type_name = b"rin "
    assert _classify_slot(ring, d2r) == ("ring", 0, 0)

    # _apply_sorc_prop, _apply_paladin_prop, _apply_props_to_acc (defense props)
    sorc_acc = _PropAcc()
    _apply_sorc_prop(sorc_acc, 83, [int(CharClass.SORCERESS), 2])
    _apply_sorc_prop(sorc_acc, 107, [59, 3])
    _apply_sorc_prop(sorc_acc, 107, [65, 1])
    _apply_sorc_prop(sorc_acc, 188, [1, int(CharClass.SORCERESS), 1])
    _apply_sorc_prop(sorc_acc, 188, [2, int(CharClass.SORCERESS), 2])
    assert (
        sorc_acc.sorc_skills,
        sorc_acc.blizz_skills,
        sorc_acc.cm_skills,
        sorc_acc.light_skills,
    ) == (4, 3, 1, 1)

    pal_acc = _PropAcc()
    _apply_paladin_prop(pal_acc, 247, 8, [8], d2r, 80, "smite", 97, frozenset({0}))
    assert pal_acc.cb > 0

    def_acc = _PropAcc()
    _apply_props_to_acc(
        def_acc,
        [(31, 40, [40]), (214, 16, [16])],
        d2r,
        char_level=50,
        char_class=int(CharClass.PALADIN),
        pal_spec="leveling",
        include_defense_props=True,
    )
    assert def_acc.defense > 40

    # Mock native ItemSpec & CharmSpec to test _item_to_spec, set bonuses, and extract_pool
    monkeypatch.setattr("d2savior.optimizer.extract.ItemSpec", _FakeItemSpec)
    monkeypatch.setattr("d2savior.optimizer.extract.CharmSpec", _FakeCharmSpec)

    sock_it = D2Item()
    sock_it.location = ItemLocation.SOCKET.value
    assert _item_to_spec(sock_it, "loc", d2r, 0x63, 90) is None

    # Set bonuses extraction
    set_it = D2Item()
    set_it.type_name = b"hgl "
    set_it.item_info = ItemInfo()
    set_it.item_info.ext_info = ExtItemInfo()
    set_it.item_info.ext_info.set_id = 35
    tp = TypeSpecificInfo()
    sp = PropertyList()
    sp._use_stat_cost = True
    sp.properties = [(31, 0, 25)]  # +25 Defense 2pc bonus
    tp.set_properties = [sp, None, None, None, None]
    set_it.item_info.type_specific_info = tp
    bonuses = _extract_set_bonuses(
        set_it, d2r, 0x63, 30, char_class=int(CharClass.PALADIN), pal_spec="holy-fire"
    )
    assert len(bonuses) == 1
    assert bonuses[0][0] == 2
    gid, sid, resolved_bonuses = _resolve_item_set_info(
        set_it,
        d2r,
        0x63,
        30,
        char_class=int(CharClass.PALADIN),
        pal_spec="holy-fire",
        set_group_ids={},
    )
    assert gid == 1
    assert sid == 36
    assert len(resolved_bonuses) == 1

    # End-to-end extract_pool across real fixtures with mocked specs
    sork, _ = _load_char("sork.d2s")
    mule, _ = _load_char("mule_unique.d2s")
    ok_st, stash, _, _ = parse_d2i_file(
        str(FIXTURES_DIR / "ModernSharedStashSoftCoreV2.d2i"), resolver=resolver
    )
    assert ok_st
    assert isinstance(stash, SharedStash)
    items, charms = extract_pool(sork, extra_chars=[mule], stashes=[stash])
    assert len(items) > 10
    assert len(charms) > 0

    kept_items, kept_charms = extract_pool(
        sork, extra_chars=[mule], stashes=[stash], resolver=resolver, keep_equipped=True
    )
    assert all(it.loc == "sork Equipped" for it in kept_items)
    assert len(kept_charms) > 0
