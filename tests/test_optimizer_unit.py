"""Pure-Python unit tests for optimizer modules that run without d2savior._native."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pytest

from d2savior.cli import parse_d2i_file, parse_d2s_file
from d2savior.core.d2s_struct import D2SStruct
from d2savior.core.enums import CharClass, EquipSlot, ItemLocation, StoredIn
from d2savior.core.item import D2Item, ExtItemInfo, ItemInfo, TypeSpecificInfo
from d2savior.core.item_name import LongName
from d2savior.core.property_list import PropertyList
from d2savior.core.resolver import GameDataResolver
from d2savior.core.stash import SharedStash, StashTab
from d2savior.core.stats import compute_anya_resist_bonus, compute_paladin_passive_max_res
from d2savior.optimizer.common import (
    _item_cta_bo,
    _item_levelreq,
    _long_name_levelreq,
    detect_cta_bo_bonus,
    validate_paladin,
    validate_sorceress,
    validate_supported_class,
)
from d2savior.optimizer.extract import (
    _char_item_locality_rank,
    _classify_slot,
    _effective_req,
    _extract_set_bonuses,
    _format_item_location,
    _item_to_spec,
    _resolve_item_set_info,
    extract_pool,
)
from d2savior.optimizer.extract_props import (
    _apply_paladin_prop,
    _apply_props_to_acc,
    _apply_sorc_prop,
    _PropAcc,
)
from d2savior.optimizer.native import BuildResult, CharmSpec
from d2savior.optimizer.paladin import (
    _build_paladin_baseline,
    _describe_lower_fhr_tradeoff,
    _describe_paladin_tradeoff,
    _format_opt1_label,
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
    pct_life: int = 0
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
    block_pct: int = 0
    fbr: int = 0
    def_skill: int = 0
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
    global_set_bonuses: list[tuple[int, object]] = field(default_factory=list)
    wsm: int = 0
    wclass: str = ""
    action_skill_bonus: int = 0
    aura_skill_bonus: int = 0
    off_ed: int = 0
    flat_phys_2x: int = 0
    flat_fire_2x: int = 0
    flat_elem_2x: int = 0
    wep_phys_2x: int = 0
    wep_str_pct: int = 0
    wep_dex_pct: int = 0
    can_zeal: bool = False
    splash_fire: bool = False
    splash_fire_2x: int = 0
    cold_dmg_pct: int = 0
    ds: int = 0
    cs_oskill: int = 0
    ow: int = 0
    ed_demon: int = 0
    ed_undead: int = 0
    psn_dps_2x: int = 0
    pierce: int = 0
    ctc_static_pct: int = 0
    ctc_venom_dps_2x: int = 0
    ctc_decrep_pct: int = 0
    ctc_lifetap_pct: int = 0
    ctc_orb_dmg_2x: int = 0
    ar: int = 0
    ar_pct: int = 0
    itd: int = 0
    target_def_pct: int = 0


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
    all_skills: int = 0
    vit: int = 0
    ene: int = 0
    ar: int = 0
    flat_phys_2x: int = 0
    flat_fire_2x: int = 0
    flat_elem_2x: int = 0
    psn_dps_2x: int = 0


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
    fixed_slots: list[str] = field(default_factory=list)
    offense: str = "caster"
    aura_hit_dmg: list[float] = field(default_factory=list)
    aura_pulse_dps: list[float] = field(default_factory=list)
    action_ed: list[int] = field(default_factory=list)
    action_hits: list[int] = field(default_factory=list)
    has_aura: bool = False
    aura_is_fire: bool = False
    targets: int = 1
    blizz_dmg: list[float] = field(default_factory=list)
    filler_dmg: list[float] = field(default_factory=list)
    filler_is_aoe: bool = False
    require_cbf: bool = False
    min_frw: int = 0
    min_ias: int = 0
    min_cb: int = 0
    min_ll: int = 0
    min_pdr: int = 0
    min_mf: int = 0
    action_ar_pct: list[int] = field(default_factory=list)
    aura_ar_pct: list[int] = field(default_factory=list)
    aura_target_def_pct: list[int] = field(default_factory=list)
    target_def: int = 180
    target_ar: int = 0
    target_lvl: int = 0
    target_type: str = "champion"
    char_level: int = 1
    target_hp: int = 0
    holy_shield_base_lvl: int = 0
    defiance_base_lvl: int = 0
    cold_armor_kind: int = 0
    cold_armor_base_lvl: int = 0


@dataclass
class _FakeBuildResult:
    items: list[_FakeItemSpec] = field(default_factory=list)
    charms: list[_FakeCharmSpec] = field(default_factory=list)
    skills: int = 0
    action_skill_bonus: int = 0
    aura_skill_bonus: int = 0
    dps: float = 0.0
    used_zeal: bool = False
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
    ias_last_frames: int = 0
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
    ar: int = 0
    cth: int = 0
    raw_dps: float = 0.0
    gear_defense: int = 0
    defense: int = 0
    enemy_cth: int = 0
    block_pct: int = 0
    fbr: int = 0
    fbr_bp: int = 0
    fbr_frames: int = 0
    has_shield: bool = False


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

    assert compute_anya_resist_bonus(empty_char) == 0
    assert compute_anya_resist_bonus(sork) >= 0

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
    assert _extract_blizz_base_skills(sork) == (0, 35, 20)
    sork.skills.skill_levels = [0] * 30
    assert _extract_blizz_base_skills(sork) == (0, 0, 0)
    sork.skills.skill_levels = []
    assert _extract_blizz_base_skills(sork) == (0, 0, 0)

    with pytest.raises(ValueError, match="expected Sorceress"):
        select_sorc_presets(mule)
    with pytest.raises(ValueError, match="Unknown build preset"):
        select_sorc_presets(sork, build="invalid")

    monkeypatch.setattr("d2savior.optimizer.common.BuildConstraints", _FakeConstraints)
    all_presets = select_sorc_presets(sork, build="all", max_charm_slots=20, limit=2)
    assert len(all_presets) == 5
    c_sork = cast(_FakeConstraints, all_presets[0][1])
    assert c_sork.base_hell_res == -20  # Nightmare (-40) + Normal/NM Anya (+20)
    assert c_sork.bo_base_bonus == 0
    assert c_sork.use_bo is False

    mf_presets = select_sorc_presets(sork, build="mf", resolver=resolver, bo_base_bonus=6)
    assert len(mf_presets) == 2
    assert cast(_FakeConstraints, mf_presets[0][1]).bo_base_bonus == 6
    assert cast(_FakeConstraints, mf_presets[0][1]).use_bo is True
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
    assert compute_paladin_passive_max_res(mule) == (5, 3, 2)
    empty_char = D2SStruct()
    assert compute_paladin_passive_max_res(empty_char) == (0, 0, 0)

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
        == "Lower FHR BP (27%, 6f)"
    )

    # All branches of _describe_paladin_tradeoff
    assert "Lower FHR BP (27%, 6f)" in _describe_paladin_tradeoff(
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
        == "Lower FCR BP (30%, 12f) — Better Resists"
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
        == "Lower FCR BP (30%, 12f) — Higher Skills"
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
        == "Lower FCR BP (30%, 12f)"
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
    opt_raw_low = _as_result(
        _FakeBuildResult(
            fhr_bp=48, fcr_bp=48, dps=800.0, raw_dps=1200.0, fr=50, lr=50, cr=50, pr=50
        )
    )
    opt_cth_win = _as_result(
        _FakeBuildResult(
            fhr_bp=48, fcr_bp=48, dps=950.0, raw_dps=1100.0, fr=50, lr=50, cr=50, pr=50
        )
    )
    assert (
        _describe_paladin_tradeoff(opt_raw_low, opt_cth_win, is_caster=False, is_smite=False)
        == "Higher Effective DPS"
    )
    assert (
        _describe_lower_fhr_tradeoff(
            opt_raw_low,
            _as_result(
                _FakeBuildResult(
                    fhr_bp=27, fcr_bp=48, dps=950.0, raw_dps=1100.0, fr=50, lr=50, cr=50, pr=50
                )
            ),
            sk_diff=0,
            res_diff=0,
        )
        == "Lower FHR BP (27%, 6f) — Higher Effective DPS"
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

    # Overrides with min_fhr / min_fcr / allow_mf / mode must not raise TypeError for duplicate kwargs.
    from d2savior.optimizer.presets import ConstraintOverrides

    seen_probe_constraints: list[_FakeConstraints] = []

    def _fake_opt_floor(_items: object, _charms: object, c: _FakeConstraints) -> list[BuildResult]:
        seen_probe_constraints.append(c)
        if c.min_fhr > 48 or c.min_fcr > 30:
            return []
        return [opt_high]

    monkeypatch.setattr("d2savior.optimizer.paladin.optimize_builds", _fake_opt_floor)
    _, opts_ov, _, _ = optimize_paladin_leveling(
        mule,
        [],
        [],
        limit=3,
        resolver=resolver,
        bo_base_bonus=0,
        overrides=ConstraintOverrides(min_fhr=48, min_fcr=30, allow_mf=False),
    )
    assert len(opts_ov) == 1
    assert all(
        c.min_fhr >= 48 and c.min_fcr >= 30 and not c.allow_mf for c in seen_probe_constraints
    )

    # Caster probe with min_fhr / min_fcr floors must enforce both during FCR & FHR probing.
    seen_probe_constraints.clear()
    _, opts_caster_ov, _, _ = optimize_paladin_leveling(
        mule,
        [],
        [],
        spec="hammer",
        limit=3,
        resolver=resolver,
        bo_base_bonus=0,
        overrides=ConstraintOverrides(min_fhr=27, min_fcr=30, allow_mf=False),
    )
    assert len(opts_caster_ov) == 1
    assert all(c.min_fhr >= 27 and not c.allow_mf for c in seen_probe_constraints)

    # select_paladin_max_res_preset honors mode override without duplicate 'mode' TypeError.
    _, c_mr_ov, _ = select_paladin_max_res_preset(
        mule,
        resolver=resolver,
        bo_base_bonus=0,
        overrides=ConstraintOverrides(mode="power", allow_mf=False),
    )
    assert cast(_FakeConstraints, c_mr_ov).mode == "power"
    assert not cast(_FakeConstraints, c_mr_ov).allow_mf


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

    sorc_noblizz_nobo = _as_result(
        _FakeBuildResult(
            skills=2,
            blizz_avg=0.0,
            cm_pierce=0,
            bo_lvl=0,
            life_no_bo=400,
            life_bo=400,
            mana_bo=150,
            charm_slots=0,
        )
    )
    noblizz_report = format_build_report("Normal Sorc", [sorc_noblizz_nobo], diff_name="Normal")
    assert "Blizz Avg" not in noblizz_report
    assert "CM:" not in noblizz_report
    assert "Normal Res:" in noblizz_report
    assert "BO lvl" not in noblizz_report
    assert "Life: 400 | Mana: 150" in noblizz_report

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

    pal_dps_res = _as_result(
        _FakeBuildResult(
            dps=800.0,
            raw_dps=1000.0,
            used_zeal=True,
            ar=1200,
            cth=86,
            skills=2,
            action_skill_bonus=1,
            ias=40,
            ias_bp=32,
            ias_frames=6,
            ias_last_frames=11,
        )
    )
    dps_report = format_build_report(
        "Paladin Zeal",
        [pal_dps_res],
        char_class=int(CharClass.PALADIN),
        diff_name="Normal",
        primary_skill_name="Zeal",
        primary_skill_base=4,
    )
    assert "DPS: 1000 (Zeal) | AR: 1200 (86%) |" in dps_report

    assert "No loadout found" in format_paladin_leveling_report("Empty Pal", [])
    pal_res_nm = _as_result(
        _FakeBuildResult(
            skills=1,
            bo_lvl=0,
            life_no_bo=500,
            mana_bo=80,
            fr=78,
            lr=75,
            cr=75,
            pr=75,
            fr_raw=78,
            lr_raw=76,
            cr_raw=75,
            pr_raw=80,
        )
    )
    lvl_report = format_paladin_leveling_report(
        "Paladin Leveling",
        [("High Breakpoint", pal_res_nm)],
        diff_name="Nightmare",
        primary_skill_name=None,
    )
    assert "Option #1: High Breakpoint" in lvl_report
    assert "Nightmare Res: F:78%(118) L:75%(116) C:75%(115) P:75%(120)" in lvl_report
    assert "Life: 500 | Mana: 80" in lvl_report

    hell_report = format_build_report(
        "Hell Sorc",
        [pal_res_nm],
        diff_name="Hell",
        resist_penalty=-50,
    )
    assert "Hell Res: F:78%(128) L:75%(126) C:75%(125) P:75%(130)" in hell_report

    shielded_res = _as_result(
        _FakeBuildResult(
            defense=4280,
            enemy_cth=38,
            block_pct=75,
            fbr=32,
            fbr_bp=32,
            fbr_frames=3,
            has_shield=True,
        )
    )
    shielded_report = format_build_report("Shielded", [shielded_res], diff_name="Hell")
    assert "  Def: 4280 (38% hit) | Block: 75% (FBR 32%, 3f)" in shielded_report

    bow_res = _as_result(
        _FakeBuildResult(
            defense=620,
            enemy_cth=74,
            has_shield=False,
        )
    )
    bow_report = format_build_report("Bow", [bow_res], char_class=int(CharClass.PALADIN))
    assert "  Def: 620 (74% hit)" in bow_report
    assert "Block:" not in bow_report


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

    # When Weapon Set II is active, Weapon I / Shield I are swap slots and Weapon II / Shield II are equipped.
    w2_swap = (EquipSlot.WEAPON_I, EquipSlot.SHIELD_I)
    assert _format_item_location("hero", it, swap_slots=w2_swap) == "hero Equipped"
    assert _char_item_locality_rank(it, swap_slots=w2_swap) == 0
    it.position = EquipSlot.WEAPON_I.value
    assert _format_item_location("hero", it, swap_slots=w2_swap) == "hero Swap"
    assert _char_item_locality_rank(it, swap_slots=w2_swap) == 1

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

    # %PDR (36) and CBF (153) must extract identically for Sorceress as well as Paladin.
    sorc_def_acc = _PropAcc()
    _apply_props_to_acc(
        sorc_def_acc,
        [(36, 15, [15]), (153, 1, [1])],
        d2r,
        char_level=80,
        char_class=int(CharClass.SORCERESS),
        pal_spec="leveling",
    )
    assert sorc_def_acc.pdr_pct == 15
    assert sorc_def_acc.cbf == 1

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
    monkeypatch.setattr("d2savior.optimizer.extract_props.ItemSpec", _FakeItemSpec)
    monkeypatch.setattr("d2savior.optimizer.extract_props.CharmSpec", _FakeCharmSpec)

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
    gid, sid, resolved_bonuses, resolved_global_bonuses = _resolve_item_set_info(
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
    # Sigon's Complete Steel global bonuses: 2pc (+10% LL), 3pc (+100 Def), 6pc (full set)
    global_by_req = dict(resolved_global_bonuses)
    assert 2 in global_by_req
    assert global_by_req[2].life_leech == 10
    assert 3 in global_by_req
    assert global_by_req[3].defense == 100
    assert 6 in global_by_req
    assert global_by_req[6].fr == 12
    assert global_by_req[6].mana == 20

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


def test_split_skill_reporting_eth_filter_and_flat_damage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typing import cast

    from d2savior.optimizer.extract import _compute_weapon_phys_2x
    from d2savior.optimizer.paladin import _eff_paladin_skills

    # 1. Split skill reporting: Holy Fire (has_aura=True) must not bleed action_skill_bonus,
    #    and pure Zeal (has_aura=False) must pick action_skill_bonus even when aura_skill_bonus > 0.
    r_combat_only = cast(
        BuildResult,
        _FakeBuildResult(skills=0, aura_skill_bonus=0, action_skill_bonus=2),
    )
    assert _eff_paladin_skills(r_combat_only, has_aura=True) == 0
    assert _eff_paladin_skills(r_combat_only, has_aura=False) == 2

    r_both = cast(
        BuildResult,
        _FakeBuildResult(skills=1, aura_skill_bonus=1, action_skill_bonus=2),
    )
    assert _eff_paladin_skills(r_both, has_aura=True) == 2
    assert _eff_paladin_skills(r_both, has_aura=False) == 3

    rep_hf = format_paladin_leveling_report(
        "Test",
        [("Opt", r_combat_only)],
        primary_skill_name="Holy Fire",
        primary_skill_base=20,
    )
    assert "(Holy Fire lvl 20)" in rep_hf

    rep_zeal = format_paladin_leveling_report(
        "Test",
        [("Opt", r_both)],
        primary_skill_name="Zeal",
        primary_skill_base=20,
    )
    assert "(Zeal lvl 23)" in rep_zeal

    # 2. Flat +Damage (pid 111, item_normaldamage) adds 2*val to wep_phys_2x.
    resolver = GameDataResolver.load()
    d2r = resolver.for_version(0x69)
    wep = D2Item()
    wep.type_name = b"bsd "
    phys_no_flat, _, _, _ = _compute_weapon_phys_2x(wep, [], d2r, 85, slot="weapon", code="bsd")
    phys_grief, _, _, _ = _compute_weapon_phys_2x(
        wep, [(111, 400, [400])], d2r, 85, slot="weapon", code="bsd"
    )
    assert phys_grief == phys_no_flat + 800

    # 3. Breakable eth melee weapon filtered by default; indestructible/allow_eth_melee kept + tagged (eth).
    monkeypatch.setattr("d2savior.optimizer.extract_props.ItemSpec", _FakeItemSpec)
    eth_wep = D2Item()
    eth_wep.type_name = b"mau "
    eth_wep.is_ethereal = True
    monkeypatch.setattr(
        "d2savior.optimizer.extract.collect_item_properties",
        lambda *a, **kw: [(17, 200, [200]), (18, 200, [200])],
    )
    assert (
        _item_to_spec(
            eth_wep,
            "loc",
            d2r,
            0x69,
            30,
            char_class=int(CharClass.PALADIN),
            pal_spec="holy-fire",
            pal_offense="zeal",
        )
        is None
    )
    kept_opt = _item_to_spec(
        eth_wep,
        "loc",
        d2r,
        0x69,
        30,
        char_class=int(CharClass.PALADIN),
        pal_spec="holy-fire",
        pal_offense="zeal",
        allow_eth_melee=True,
    )
    assert isinstance(kept_opt, _FakeItemSpec)
    assert kept_opt.name.endswith(" (eth)")

    # Breakable eth weapon is still kept when its slot is in skip_useful_slots (--keep-gear / weapon)
    kept_slot = _item_to_spec(
        eth_wep,
        "loc",
        d2r,
        0x69,
        30,
        char_class=int(CharClass.PALADIN),
        pal_spec="holy-fire",
        pal_offense="zeal",
        skip_useful_slots=frozenset({"weapon", "weapon2h", "shield"}),
    )
    assert isinstance(kept_slot, _FakeItemSpec)
    assert kept_slot.name.endswith(" (eth)")

    monkeypatch.setattr(
        "d2savior.optimizer.extract.collect_item_properties",
        lambda *a, **kw: [(17, 200, [200]), (152, 1, [1])],
    )
    indes_opt = _item_to_spec(
        eth_wep,
        "loc",
        d2r,
        0x69,
        30,
        char_class=int(CharClass.PALADIN),
        pal_spec="holy-fire",
        pal_offense="zeal",
    )
    assert isinstance(indes_opt, _FakeItemSpec)
    assert indes_opt.name.endswith(" (eth)")

    # Breakable eth Smite weapon is also excluded; eth Phase Blade (nodurability=True) is kept.
    monkeypatch.setattr(
        "d2savior.optimizer.extract.collect_item_properties",
        lambda *a, **kw: [(17, 200, [200]), (105, 20, [20])],
    )
    assert (
        _item_to_spec(
            eth_wep,
            "loc",
            d2r,
            0x69,
            90,
            char_class=int(CharClass.PALADIN),
            pal_spec="smite",
            pal_offense="smite",
        )
        is None
    )
    eth_pb = D2Item()
    eth_pb.type_name = b"7cr "
    eth_pb.is_ethereal = True
    pb_spec = _item_to_spec(
        eth_pb,
        "loc",
        d2r,
        0x69,
        90,
        char_class=int(CharClass.PALADIN),
        pal_spec="smite",
        pal_offense="smite",
    )
    assert isinstance(pb_spec, _FakeItemSpec)
    assert pb_spec.name.endswith(" (eth)")

    # Breakable eth caster weapon is still kept for Sorceress and Hammerdin.
    assert isinstance(
        _item_to_spec(
            eth_wep,
            "loc",
            d2r,
            0x69,
            90,
            char_class=int(CharClass.SORCERESS),
        ),
        _FakeItemSpec,
    )
    assert isinstance(
        _item_to_spec(
            eth_wep,
            "loc",
            d2r,
            0x69,
            90,
            char_class=int(CharClass.PALADIN),
            pal_spec="hammer",
            pal_offense="caster",
        ),
        _FakeItemSpec,
    )

    # Breakable eth armor/helm/shield/belt/gloves/boots excluded for Sorc and Paladin;
    # kept with (eth) tag when in skip_useful_slots (--keep-gear) or indestructible/self-repair.
    monkeypatch.setattr(
        "d2savior.optimizer.extract.collect_item_properties",
        lambda *a, **kw: [(39, 25, [25])],
    )
    for code_bytes, slot_name in (
        (b"qui ", "armor"),
        (b"cap ", "helm"),
        (b"lrg ", "shield"),
        (b"vbl ", "belt"),
        (b"lgl ", "gloves"),
        (b"lbt ", "boots"),
    ):
        eth_arm = D2Item()
        eth_arm.type_name = code_bytes
        eth_arm.is_ethereal = True
        for cls_id, p_spec, p_off in (
            (int(CharClass.SORCERESS), "leveling", None),
            (int(CharClass.PALADIN), "smite", "smite"),
        ):
            assert (
                _item_to_spec(
                    eth_arm,
                    "loc",
                    d2r,
                    0x69,
                    90,
                    char_class=cls_id,
                    pal_spec=p_spec,
                    pal_offense=p_off,
                )
                is None
            )
        kept_arm = _item_to_spec(
            eth_arm,
            "loc",
            d2r,
            0x69,
            90,
            char_class=int(CharClass.SORCERESS),
            skip_useful_slots=frozenset({slot_name}),
        )
        assert isinstance(kept_arm, _FakeItemSpec)
        assert kept_arm.name.endswith(" (eth)")

    monkeypatch.setattr(
        "d2savior.optimizer.extract.collect_item_properties",
        lambda *a, **kw: [(39, 25, [25]), (252, 5, [5])],  # Repairs durability
    )
    eth_rep = D2Item()
    eth_rep.type_name = b"lrg "
    eth_rep.is_ethereal = True
    rep_spec = _item_to_spec(eth_rep, "loc", d2r, 0x69, 90, char_class=int(CharClass.PALADIN))
    assert isinstance(rep_spec, _FakeItemSpec)
    assert rep_spec.name.endswith(" (eth)")

    monkeypatch.setattr(
        "d2savior.optimizer.extract.collect_item_properties",
        lambda *a, **kw: [(39, 25, [25]), (152, 1, [1])],  # Indestructible
    )
    ind_spec = _item_to_spec(eth_rep, "loc", d2r, 0x69, 90, char_class=int(CharClass.SORCERESS))
    assert isinstance(ind_spec, _FakeItemSpec)
    assert ind_spec.name.endswith(" (eth)")

    # 4. Active save skill bindings lock offense profile (Attack + Holy Fire -> melee, Zeal + Holy Fire -> zeal).
    from d2savior.core.d2s_struct import CharSkills

    pal = D2SStruct()
    pal.char_class = int(CharClass.PALADIN)
    pal.skills = CharSkills()
    pal.skills.skill_levels = [0] * 30
    pal.skills.skill_levels[6] = 20  # Holy Fire
    pal.skills.skill_levels[10] = 1  # Zeal
    # No bindings (0, 0) -> fallback to hard points ('zeal')
    assert paladin_offense_profile("holy-fire", pal) == "zeal"
    # Active binding Attack (0) + Holy Fire (102) -> locked to 'melee'
    pal.left_skill_1 = 0
    pal.right_skill_1 = 102
    assert paladin_offense_profile("holy-fire", pal) == "melee"
    # Active binding Zeal (106) + Holy Fire (102) -> locked to 'zeal'
    pal.left_skill_1 = 106
    pal.right_skill_1 = 102
    assert paladin_offense_profile("holy-fire", pal) == "zeal"

    # Weapon Set II reads left_skill_2 / right_skill_2 instead of *_1.
    pal.weapon_set = 1
    pal.left_skill_2 = 0
    pal.right_skill_2 = 102
    assert paladin_offense_profile("holy-fire", pal) == "melee"

    from d2savior.optimizer.paladin import detect_paladin_spec

    pal.skills.skill_levels[18] = 20  # Tie Holy Freeze (20) with Holy Fire (20)
    assert detect_paladin_spec(pal) == "holy-fire"
    pal.right_skill_2 = 114  # Active swap binding selects Holy Freeze
    assert detect_paladin_spec(pal) == "holy-freeze"


def test_parse_keep_gear_and_resolve_fixed_gear() -> None:
    from d2savior.optimizer.common import (
        ALL_GEAR_SLOTS,
        KEEP_GEAR_GROUPS,
        KEEP_GEAR_SLOTS,
        parse_keep_gear,
        resolve_fixed_gear,
    )

    assert parse_keep_gear(None) == frozenset()
    assert parse_keep_gear(False) == frozenset()
    assert parse_keep_gear(True) == ALL_GEAR_SLOTS
    assert parse_keep_gear("all") == ALL_GEAR_SLOTS
    assert parse_keep_gear("ALL") == ALL_GEAR_SLOTS
    assert parse_keep_gear("weapon") == frozenset({"weapon", "weapon2h", "shield"})
    assert parse_keep_gear("jewelry") == frozenset({"amulet", "ring"})
    assert parse_keep_gear("armor") == frozenset({"helm", "armor", "belt", "gloves", "boots"})
    assert parse_keep_gear("weapon+jewelry") == (
        KEEP_GEAR_GROUPS["weapon"] | KEEP_GEAR_GROUPS["jewelry"]
    )
    assert parse_keep_gear(" Weapon + Armor ") == (
        KEEP_GEAR_GROUPS["weapon"] | KEEP_GEAR_GROUPS["armor"]
    )
    assert parse_keep_gear("weapon+jewelry+armor") == ALL_GEAR_SLOTS
    assert parse_keep_gear("all+weapon") == ALL_GEAR_SLOTS

    # Individual slots and natural aliases
    for name, expected in KEEP_GEAR_SLOTS.items():
        assert parse_keep_gear(name) == expected
    assert parse_keep_gear("helmet") == frozenset({"helm"})
    assert parse_keep_gear("chest") == frozenset({"armor"})
    assert parse_keep_gear("body") == frozenset({"armor"})
    assert parse_keep_gear("rings") == frozenset({"ring"})
    assert parse_keep_gear("helm+boots") == frozenset({"helm", "boots"})
    assert parse_keep_gear("chest+gloves+belt") == frozenset({"armor", "gloves", "belt"})
    assert parse_keep_gear("weapon+helm+boots") == (
        KEEP_GEAR_GROUPS["weapon"] | frozenset({"helm", "boots"})
    )
    assert parse_keep_gear("jewelry+chest") == (KEEP_GEAR_GROUPS["jewelry"] | frozenset({"armor"}))

    assert resolve_fixed_gear(False) == (False, ())
    assert resolve_fixed_gear(True) == (True, ())
    assert resolve_fixed_gear("all") == (True, ())
    assert resolve_fixed_gear("weapon+jewelry+armor") == (True, ())
    assert resolve_fixed_gear("weapon+jewelry+helm+chest+belt+gloves+boots") == (True, ())
    assert resolve_fixed_gear("jewelry") == (False, ("amulet", "ring"))
    assert resolve_fixed_gear("helm+boots") == (False, ("boots", "helm"))
    assert resolve_fixed_gear("weapon+jewelry") == (
        False,
        ("amulet", "ring", "shield", "weapon", "weapon2h"),
    )

    for bad in ("", "   ", "weapon+", "+armor", "bogus", "weapon+bogus"):
        with pytest.raises(ValueError, match=r"(Empty|Invalid) --keep-gear"):
            parse_keep_gear(bad)


def test_normalize_keep_gear_argv_before_positionals() -> None:
    import argparse

    from d2savior.cli_optimize import _normalize_keep_gear_argv

    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--build", default="all")
    parser.add_argument("--char", default=None)
    parser.add_argument("--keep-gear", nargs="?", const="all", default=None)
    parser.add_argument("file_path", nargs="*")

    # Bare --keep-gear before sole character name preserves the character name as positional
    assert _normalize_keep_gear_argv(["--keep-gear", "smite"], parser) == [
        "--keep-gear=all",
        "smite",
    ]
    assert _normalize_keep_gear_argv(["-b", "leveling", "--keep-gear", "smite"], parser) == [
        "-b",
        "leveling",
        "--keep-gear=all",
        "smite",
    ]
    # Valid group/slot expression is bound to --keep-gear
    assert _normalize_keep_gear_argv(["--keep-gear", "weapon+jewelry", "smite"], parser) == [
        "--keep-gear=weapon+jewelry",
        "smite",
    ]
    assert _normalize_keep_gear_argv(["--keep-gear", "helm+boots", "smite"], parser) == [
        "--keep-gear=helm+boots",
        "smite",
    ]
    assert _normalize_keep_gear_argv(["--keep-gear", "boots", "smite"], parser) == [
        "--keep-gear=boots",
        "smite",
    ]
    # .d2s/.d2i path stays positional even when another positional is present
    assert _normalize_keep_gear_argv(["smite", "--keep-gear", "foo.d2s"], parser) == [
        "smite",
        "--keep-gear=all",
        "foo.d2s",
    ]
    # Invalid group with --char or another positional already present stays attached so argparse errors
    assert _normalize_keep_gear_argv(["--char", "smite", "--keep-gear", "invalid"], parser) == [
        "--char",
        "smite",
        "--keep-gear",
        "invalid",
    ]
    assert _normalize_keep_gear_argv(["--keep-gear", "weapon+bogus", "smite"], parser) == [
        "--keep-gear",
        "weapon+bogus",
        "smite",
    ]


def test_to_charm_spec_preserves_all_skills_vit_and_ene(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("d2savior.optimizer.extract_props.CharmSpec", _FakeCharmSpec)
    acc = _PropAcc(
        all_skills=1,
        sorc_skills=3,
        pal_skills=2,
        str_bonus=15,
        dex_bonus=15,
        vit=18,
        ene=14,
        fr=12,
        lr=12,
        cr=12,
        pr=12,
    )
    sorc_ch = acc.to_charm_spec("Torch+Anni", 3, "sork Inv", 400, int(CharClass.SORCERESS))
    assert sorc_ch.all_skills == 1
    assert sorc_ch.skills == 3
    assert sorc_ch.vit == 18
    assert sorc_ch.ene == 14

    pal_ch = acc.to_charm_spec("Torch+Anni", 3, "smite Inv", 400, int(CharClass.PALADIN))
    assert pal_ch.all_skills == 1
    assert pal_ch.skills == 2
    assert pal_ch.vit == 18
    assert pal_ch.ene == 14


def test_extract_per_level_attrs_res_def_and_pct_life() -> None:
    from d2savior.core.stats import calculate_effective_defence
    from d2savior.optimizer.extract_props import _apply_props_to_acc

    resolver = GameDataResolver.load()
    acc = _PropAcc()
    # At char_level=80, shift=3 (divide by 8): pval=6 -> 60, pval=4 -> 40, pval=8 -> 80.
    props: list[tuple[int, int, list[int]]] = [
        (76, 5, [5]),  # +5% max life
        (220, 6, [6]),  # +0.75 Str/lvl -> +60 Str
        (221, 4, [4]),  # +0.5 Dex/lvl -> +40 Dex
        (222, 4, [4]),  # +0.5 Ene/lvl -> +40 Ene
        (223, 4, [4]),  # +0.5 Vit/lvl -> +40 Vit
        (230, 8, [8]),  # +1.0 CR/lvl -> +80 CR
        (231, 6, [6]),  # +0.75 FR/lvl -> +60 FR
        (232, 4, [4]),  # +0.5 LR/lvl -> +40 LR
        (233, 2, [2]),  # +0.25 PR/lvl -> +20 PR
    ]
    _apply_props_to_acc(
        acc,
        props,
        resolver,
        80,
        char_class=int(CharClass.SORCERESS),
        pal_spec="leveling",
    )
    assert acc.pct_life == 5
    assert acc.str_bonus == 60
    assert acc.dex_bonus == 40
    assert acc.ene == 40
    assert acc.vit == 40
    assert acc.cr == 80
    assert acc.fr == 60
    assert acc.lr == 40
    assert acc.pr == 20

    # Defense with stat 16 (+100% ED), stat 215 (+0.5% ED/lvl -> +40% ED at lvl 80),
    # stat 31 (+50 Def), and stat 214 (+1.25 Def/lvl -> pval=10 -> +100 Def at lvl 80):
    # base 200 * (100 + 140) // 100 + 150 = 480 + 150 = 630.
    def_props: list[tuple[int, int, list[int]]] = [
        (16, 100, [100]),
        (215, 4, [4]),
        (31, 50, [50]),
        (214, 10, [10]),
    ]
    eff_def = calculate_effective_defence(200, def_props, char_level=80, resolver=resolver)
    assert eff_def == 630
    # Non-armor item with 0 base defense (e.g., Leaf staff with +2 Def/lvl -> pval=16 -> +160 Def).
    staff_def = calculate_effective_defence(0, [(214, 16, [16])], char_level=80, resolver=resolver)
    assert staff_def == 160


def test_ar_stats_extracted_only_for_melee_paladin() -> None:
    resolver = GameDataResolver.load()
    ar_props: list[tuple[int, int, list[int]]] = [
        (19, 100, [100]),  # +100 AR
        (119, 50, [50]),  # +50% AR
        (115, 1, [1]),  # ITD
        (116, 25, [25]),  # -25% Target Defense
        (123, 75, [75]),  # +75 AR vs Demons (-> +25)
        (124, 60, [60]),  # +60 AR vs Undead (-> +20)
        (224, 24, [24]),  # Angelic Halo 2pc +12/lvl * 30 = +360 AR
        (225, 8, [8]),  # +4%/lvl AR * 30 = +120% AR
    ]

    # Extracted for melee / zeal Paladin
    pal_acc = _PropAcc()
    _apply_props_to_acc(
        pal_acc,
        ar_props,
        resolver,
        30,
        char_class=int(CharClass.PALADIN),
        pal_spec="holy-fire",
        pal_offense="melee",
    )
    assert pal_acc.ar == 100 + 25 + 20 + 360
    assert pal_acc.ar_pct == 50 + 120
    assert pal_acc.itd == 1
    assert pal_acc.target_def_pct == 25

    # Skipped for Smite Paladin and Sorceress (keeps non-melee item/charm pools unchanged)
    for cls_id, p_spec, p_off in (
        (int(CharClass.PALADIN), "smite", "smite"),
        (int(CharClass.SORCERESS), "leveling", "caster"),
    ):
        non_melee = _PropAcc()
        _apply_props_to_acc(
            non_melee,
            ar_props,
            resolver,
            30,
            char_class=cls_id,
            pal_spec=p_spec,
            pal_offense=p_off,
        )
        assert (non_melee.ar, non_melee.ar_pct, non_melee.itd, non_melee.target_def_pct) == (
            0,
            0,
            0,
            0,
        )


def test_paladin_melee_and_support_aura_single_skill_extraction() -> None:
    resolver = GameDataResolver.load()
    # +2 Sacrifice (96), +2 Charge (107), +2 Vengeance (111), +3 Fanaticism (122),
    # +3 Blessed Aim (108), +3 Conviction (123).
    skill_props: list[tuple[int, int, list[int]]] = [
        (107, 2, [96, 2]),
        (107, 2, [107, 2]),
        (107, 2, [111, 2]),
        (107, 3, [122, 3]),
        (107, 3, [108, 3]),
        (107, 3, [123, 3]),
    ]

    for spec in ("sacrifice", "charge", "vengeance"):
        acc = _PropAcc()
        _apply_props_to_acc(
            acc,
            skill_props,
            resolver,
            30,
            char_class=int(CharClass.PALADIN),
            pal_spec=spec,
            pal_offense="melee",
        )
        assert acc.action_skill_bonus == 2
        assert acc.aura_skill_bonus == 3

    # Explicit pal_aura_id filters pid=107 aura bonuses to only the active support aura.
    zeal_ba = _PropAcc()
    _apply_props_to_acc(
        zeal_ba,
        skill_props,
        resolver,
        30,
        char_class=int(CharClass.PALADIN),
        pal_spec="zeal",
        pal_offense="zeal",
        pal_aura_id=108,
    )
    assert zeal_ba.action_skill_bonus == 0
    assert zeal_ba.aura_skill_bonus == 3

    # Single-target Fanaticism aura ID does not pick up Blessed Aim or Conviction bonuses.
    zeal_fanat = _PropAcc()
    _apply_props_to_acc(
        zeal_fanat,
        [(107, 3, [108, 3]), (107, 3, [123, 3])],
        resolver,
        30,
        char_class=int(CharClass.PALADIN),
        pal_spec="zeal",
        pal_offense="zeal",
        pal_aura_id=122,
    )
    assert zeal_fanat.aura_skill_bonus == 0


def test_format_paladin_option_lines_melee_action_labels() -> None:
    from d2savior.optimizer.report import _format_paladin_option_lines

    for skill_name in ("Sacrifice", "Charge", "Vengeance"):
        res = _as_result(
            _FakeBuildResult(
                dps=850.0,
                raw_dps=1000.0,
                ar=1200,
                cth=85,
                used_zeal=False,
                ias=20,
                ias_bp=20,
                ias_frames=11,
                action_skill_bonus=2,
            )
        )
        lines = _format_paladin_option_lines(
            "Option #1",
            res,
            (),
            diff_name="Nightmare",
            primary_skill_name=skill_name,
            primary_skill_base=20,
            primary_inv_loc=None,
            has_aura=False,
        )
        assert f"DPS: 1000 ({skill_name}) | AR: 1200 (85%)" in lines[1]


def test_paladin_target_type_baseline_and_cli_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    from d2savior.cli_optimize import cmd_optimize
    from d2savior.optimizer.paladin import _build_paladin_baseline

    resolver = GameDataResolver.load()
    ok_p, smite, _ = parse_d2s_file(
        str(FIXTURES_DIR / "paladin_snapshot" / "smite.d2s"), resolver=resolver
    )
    assert ok_p
    assert smite is not None
    lvl = smite.player_stats.level or smite.char_level

    monkeypatch.setattr("d2savior.optimizer.common.BuildConstraints", _FakeConstraints)
    b_champ, _, _, _ = _build_paladin_baseline(
        smite,
        spec="holy-fire",
        max_charm_slots=23,
        extra_chars=(),
        stashes=(),
        resolver=resolver,
        bo_base_bonus=0,
        keep_equipped=False,
    )
    b_trash, _, _, _ = _build_paladin_baseline(
        smite,
        spec="holy-fire",
        max_charm_slots=23,
        extra_chars=(),
        stashes=(),
        resolver=resolver,
        bo_base_bonus=0,
        keep_equipped=False,
        target_type="trash",
    )
    b_boss, _, _, _ = _build_paladin_baseline(
        smite,
        spec="holy-fire",
        max_charm_slots=23,
        extra_chars=(),
        stashes=(),
        resolver=resolver,
        bo_base_bonus=0,
        keep_equipped=False,
        target_type="boss",
    )
    assert b_champ.target_type == "champion"
    assert b_trash.target_type == "trash"
    assert b_boss.target_type == "boss"
    assert b_champ.target_def == 6 * lvl
    assert b_trash.target_def == 6 * lvl
    assert b_boss.target_def == 9 * lvl
    assert b_champ.build_constraints(mode="leveling", limit=1).target_type == "champion"
    assert b_boss.build_constraints(mode="leveling", limit=1).target_type == "boss"

    bad_target: Any = "uber"
    with pytest.raises(ValueError, match="Unknown target_type"):
        _build_paladin_baseline(
            smite,
            spec="holy-fire",
            max_charm_slots=23,
            extra_chars=(),
            stashes=(),
            resolver=resolver,
            bo_base_bonus=0,
            keep_equipped=False,
            target_type=bad_target,
        )

    captured: list[str] = []

    monkeypatch.setattr(
        "d2savior.cli_optimize._resolve_and_save_targets", lambda _args: ["smite.d2s"]
    )
    monkeypatch.setattr("d2savior.cli_optimize.GameDataResolver.load", lambda **_kw: resolver)
    monkeypatch.setattr(
        "d2savior.cli_optimize._load_optimize_pool",
        lambda *_a, **_kw: (smite, [], [], None),
    )
    monkeypatch.setattr("d2savior.cli_optimize.extract_pool", lambda *_a, **_kw: ([], []))
    monkeypatch.setattr(
        "d2savior.cli_optimize.optimize_paladin_leveling",
        lambda *_a, **kw: (
            captured.append(kw["target_type"]) or "Title",
            [],
            "holy-fire",
            "Normal",
        ),
    )
    assert cmd_optimize(["smite.d2s", "-b", "leveling"]) == 0
    assert cmd_optimize(["smite.d2s", "-b", "leveling", "--target-type", "boss"]) == 0
    assert cmd_optimize(["smite.d2s", "-b", "leveling", "--target-type", "trash"]) == 0
    assert captured == ["champion", "boss", "trash"]


def test_combat_props_blunt_2h_sockets_set_weapon_and_damage_charms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from d2savior.optimizer.extract import _compute_weapon_phys_2x

    resolver = GameDataResolver.load().for_version(0x63)

    # 1. All new melee/ranged combat properties + per-level scaling + CTC procs at char_level=80
    acc = _PropAcc()
    props: list[tuple[int, int, list[int]]] = [
        (141, 20, [20]),  # +20% DS
        (250, 3 << 2, [3 << 2]),  # +1.5% DS/lvl (op_param=3 -> >>3; 12*80//8 = 120)
        (97, 1, [9, 1]),  # +1 Critical Strike oskill (Insight)
        (135, 25, [25]),  # +25% OW
        (248, 4, [4]),  # per-lvl OW (4*80>>3 = 40)
        (121, 350, [350]),  # +350% vs Demons (LoH)
        (122, 100, [100]),  # +100% vs Undead
        (243, 4, [4]),  # +vs Demons per lvl
        (244, 4, [4]),  # +vs Undead per lvl
        (156, 50, [50]),  # +50% Pierce
        (48, 40, [40]),  # +40 min fire
        (49, 180, [180]),  # +180 max fire
        (50, 10, [10]),  # +10 min light
        (51, 90, [90]),  # +90 max light
        (57, 128, [128, 0, 0, 0]),  # poison min rate
        (58, 128, [128, 0, 0, 0]),  # poison max rate
        (59, 100, [100, 0, 0, 0]),  # duration 4s
        (198, 0, [15, 278, 5]),  # 5% CtC lvl 15 Venom on striking
        (198, 0, [1, 87, 33]),  # 33% CtC lvl 1 Decrepify on striking
        (195, 0, [13, 64, 16]),  # 16% CtC lvl 13 Frozen Orb on attack
        (198, 0, [5, 82, 5]),  # 5% CtC lvl 5 Life Tap on striking
        (195, 0, [10, 42, 15]),  # 15% CtC lvl 10 Static Field on attack
    ]
    _apply_props_to_acc(
        acc,
        props,
        resolver,
        80,
        char_class=int(CharClass.PALADIN),
        pal_spec="zeal",
        pal_offense="zeal",
        is_weapon=False,
    )
    assert acc.ds == 20 + ((12 * 80) >> 3)
    assert acc.cs_oskill == 1
    assert acc.ow == 25 + ((4 * 80) >> 3)
    assert acc.ed_demon == 350 + ((4 * 80) >> 3)
    assert acc.ed_undead == 100 + ((4 * 80) >> 3)
    assert acc.pierce == 50
    assert acc.flat_fire_2x == 220
    assert acc.flat_elem_2x == 100
    assert acc.psn_dps_2x == 24
    assert acc.ctc_venom_dps_2x == 1575
    assert acc.ctc_decrep_pct == 33
    assert acc.ctc_lifetap_pct == 5
    assert acc.ctc_static_pct == 15
    assert acc.ctc_orb_dmg_2x == round(0.16 * 2106)

    # Life Tap CTC also extracts for Smite Paladin
    smite_acc = _PropAcc()
    _apply_props_to_acc(
        smite_acc,
        [(198, 0, [5, 82, 5]), (141, 15, [15])],
        resolver,
        80,
        char_class=int(CharClass.PALADIN),
        pal_spec="smite",
        pal_offense="smite",
    )
    assert smite_acc.ctc_lifetap_pct == 5
    assert smite_acc.ds == 0

    # 2. 2H weapon with native 21/22 + 23/24 + pid 218 + socketed 21/22 jewel
    twoh_item = D2Item()
    twoh_item.type_name = b"2hs "
    twoh_item.item_info = ItemInfo()
    tp = TypeSpecificInfo()
    native_plist = PropertyList()
    monkeypatch.setattr(
        native_plist,
        "get_parsed_properties",
        lambda *_a, **_kw: [(21, 5, [5]), (22, 10, [10]), (23, 12, [12]), (24, 20, [20])],
    )
    tp.property_list = native_plist
    twoh_item.item_info.type_specific_info = tp
    gem = D2Item()
    twoh_item.gem_items = [gem]
    monkeypatch.setattr(
        resolver,
        "get_socket_properties",
        lambda *_a, **_kw: [(21, 8, [8]), (22, 15, [15])],
    )
    wep_2h_no_218, _, _, _ = _compute_weapon_phys_2x(
        twoh_item, [], resolver, 80, slot="weapon2h", code="2hs"
    )
    b_2h = resolver.data.get_item("2hs")
    assert b_2h is not None
    base_2h_min = b_2h.two_hand_mindam or b_2h.mindam
    base_2h_max = b_2h.two_hand_maxdam or b_2h.maxdam
    assert wep_2h_no_218 == (base_2h_min + 12 + 8) + (base_2h_max + 20 + 15)

    # Also verify pid 218 alongside pid 22 without pid 24 does NOT drop pid 22!
    monkeypatch.setattr(
        native_plist,
        "get_parsed_properties",
        lambda *_a, **_kw: [(22, 10, [10]), (218, 40, [40])],
    )
    wep_2h_with_218, _, _, _ = _compute_weapon_phys_2x(
        twoh_item, [], resolver, 80, slot="weapon2h", code="2hs"
    )
    scaled_218 = (40 * 80) >> 3
    assert wep_2h_with_218 == (base_2h_min + 8) + (base_2h_max + 10 + 15 + scaled_218)

    # 3. Blunt weapon implicit +50% Damage to Undead on Zeal/Melee Paladin
    _, stash, _, _ = parse_d2i_file(
        str(FIXTURES_DIR / "paladin_snapshot" / "ModernSharedStashSoftCoreV2.d2i"),
        resolver=resolver,
    )
    assert isinstance(stash, SharedStash)
    black_flail = next(
        it
        for tab in stash.tabs
        if tab.items is not None
        for it in tab.items.items
        if it.code_str.strip().lower() == "fla"
    )
    monkeypatch.setattr("d2savior.optimizer.extract_props.ItemSpec", _FakeItemSpec)
    flail_spec = _item_to_spec(
        black_flail,
        "Stash",
        resolver,
        0x63,
        char_level=80,
        char_class=int(CharClass.PALADIN),
        pal_spec="zeal",
        pal_offense="zeal",
    )
    assert isinstance(flail_spec, _FakeItemSpec)
    assert flail_spec.ed_undead >= 50

    # 4. Set-weapon local %ED adds to flat_phys_2x instead of off_ed
    set_wep = D2Item()
    set_wep.type_name = b"9bs "
    set_wep.item_info = ItemInfo()
    set_tp = TypeSpecificInfo()
    set_b2 = PropertyList()
    monkeypatch.setattr(
        set_b2,
        "get_parsed_properties",
        lambda *_a, **_kw: [(17, 100, [100]), (18, 100, [100])],
    )
    set_tp.set_properties = [set_b2]
    set_wep.item_info.type_specific_info = set_tp
    set_bonuses = _extract_set_bonuses(
        set_wep,
        resolver,
        0x63,
        char_level=80,
        char_class=int(CharClass.PALADIN),
        pal_spec="zeal",
        pal_offense="zeal",
        is_weapon=True,
        slot="weapon",
        code="9bs",
    )
    b_9bs = resolver.data.get_item("9bs")
    assert b_9bs is not None
    assert len(set_bonuses) == 1
    assert set_bonuses[0][1].off_ed == 0
    assert set_bonuses[0][1].flat_phys_2x == b_9bs.mindam + b_9bs.maxdam

    # 5. Damage charm extraction
    monkeypatch.setattr("d2savior.optimizer.extract_props.CharmSpec", _FakeCharmSpec)
    c_acc = _PropAcc(ar=20, flat_phys_2x=3, flat_fire_2x=7, flat_elem_2x=11, psn_dps_2x=24)
    c_spec = c_acc.to_charm_spec(
        "Fine SC of Venom", 1, "inv", None, char_class=int(CharClass.PALADIN)
    )
    assert (
        c_spec.ar,
        c_spec.flat_phys_2x,
        c_spec.flat_fire_2x,
        c_spec.flat_elem_2x,
        c_spec.psn_dps_2x,
    ) == (20, 3, 7, 11, 24)


def test_defense_block_and_cold_armor_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    from d2savior.optimizer.common import synthesize_monster_stats
    from d2savior.optimizer.skill_tables import resolve_sorc_cold_armor

    resolver = GameDataResolver.load()
    d2r = resolver.for_version(0x63)

    # Armor.txt shield block + CharStats-independent properties (pid 20, pid 102, Combat/Holy Shield/Armor staffmod)
    gilded = d2r.data.get_item("pa9")
    sacred = d2r.data.get_item("pab")
    monarch = d2r.data.get_item("uit")
    assert gilded is not None
    assert gilded.block == 22
    assert sacred is not None
    assert sacred.block == 30
    assert monarch is not None
    assert monarch.block == 22

    # Pick strongest Cold Armor allocated on Sorceress
    sork, _ = _load_char("sork.d2s")
    assert resolve_sorc_cold_armor(sork) == (1, 1, 40)
    assert sork.skills is not None
    sork.skills.skill_levels[50 - 36] = 1  # Shiver Armor lvl 1 (45% > 30%)
    assert resolve_sorc_cold_armor(sork) == (2, 1, 50)
    sork.skills.skill_levels[60 - 36] = 1  # Chilling Armor lvl 1 (60% > 45%)
    assert resolve_sorc_cold_armor(sork) == (3, 1, 60)

    # Monster stats scaling across difficulty / target_type
    n_def, n_ar, n_lvl, n_hp = synthesize_monster_stats(0, "champion", 30)
    assert (n_def, n_ar, n_lvl, n_hp) == (180, 720, 32, 1350)
    h_def, h_ar, h_lvl, h_hp = synthesize_monster_stats(2, "boss", 85)
    assert (h_def, h_ar, h_lvl, h_hp) == (2550, 7990, 88, 85000)

    # Shield + property extraction
    monkeypatch.setattr("d2savior.optimizer.extract.ItemSpec", _FakeItemSpec)
    monkeypatch.setattr("d2savior.optimizer.extract_props.ItemSpec", _FakeItemSpec)
    shield_item = D2Item()
    shield_item.type_name = b"pa9 "
    shield_item.item_info = ItemInfo()
    tp = TypeSpecificInfo()
    sp = PropertyList()
    monkeypatch.setattr(
        sp,
        "get_parsed_properties",
        lambda *_a, **_kw: [
            (20, 30, [30]),
            (102, 30, [30]),
            (188, 2, [0, 3, 2]),
            (107, 1, [117, 1]),
        ],
    )
    tp.property_list = sp
    shield_item.item_info.type_specific_info = tp
    spec = _item_to_spec(
        shield_item,
        "Stash",
        d2r,
        0x63,
        char_level=85,
        char_class=int(CharClass.PALADIN),
        pal_spec="zeal",
        pal_offense="zeal",
    )
    assert isinstance(spec, _FakeItemSpec)
    assert spec.block_pct == 52  # 22 Armor.txt + 30 toblock
    assert spec.fbr == 30
    assert spec.def_skill == 3  # +2 Combat + 1 Holy Shield

    # Zero hard points in all Cold Armors -> Snowclash Chilling Armor fallback, or active binding.
    sork.skills.skill_levels[40 - 36] = 0
    sork.skills.skill_levels[50 - 36] = 0
    sork.skills.skill_levels[60 - 36] = 0
    assert resolve_sorc_cold_armor(sork) == (3, 0, 60)

    # Flat +Defense (pid 31) is preserved on weapons/amulets without Armor.txt base defence.
    amul_item = D2Item()
    amul_item.type_name = b"amu "
    amul_item.item_info = ItemInfo()
    amul_tp = TypeSpecificInfo()
    amul_sp = PropertyList()
    monkeypatch.setattr(
        amul_sp,
        "get_parsed_properties",
        lambda *_a, **_kw: [(31, 325, [325]), (39, 30, [30])],
    )
    amul_tp.property_list = amul_sp
    amul_item.item_info.type_specific_info = amul_tp
    amul_spec = _item_to_spec(amul_item, "Stash", d2r, 0x63, char_level=85)
    assert isinstance(amul_spec, _FakeItemSpec)
    assert amul_spec.defense == 325

    # Non-split_skills Paladin: +Offensive Auras / +Fire Skills do not inflate def_skill,
    # while +Combat Skills still credits def_skill when 0 not in pal_tabs.
    acc_hf = _PropAcc()
    _apply_paladin_prop(
        acc_hf, 188, 2, [0, 3, 2], d2r, 85, "holy-fire", 102, frozenset({1}), pal_offense="caster"
    )
    _apply_paladin_prop(
        acc_hf, 126, 3, [1, 3], d2r, 85, "holy-fire", 102, frozenset({1}), pal_offense="caster"
    )
    assert (acc_hf.pal_skills, acc_hf.def_skill) == (3, -1)

    acc_lvl = _PropAcc()
    _apply_paladin_prop(
        acc_lvl,
        188,
        1,
        [1, 3, 1],
        d2r,
        85,
        "leveling",
        None,
        frozenset({0, 1}),
        pal_offense="caster",
    )
    assert (acc_lvl.pal_skills, acc_lvl.def_skill) == (1, -1)


def test_paladin_passive_max_res_cap_in_alternatives_and_socket_score_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from d2savior.optimizer.paladin import _collect_paladin_alternatives
    from d2savior.optimizer.socket import _build_score_key

    mule, _ = _load_char("mule_unique.d2s")
    assert mule.skills is not None
    mule.skills.skill_levels = [0] * 30
    mule.skills.skill_levels[4] = 10  # Resist Fire -> base_max_fr = 5 (cap 80%)
    mule.skills.skill_levels[6] = 20  # Holy Fire

    monkeypatch.setattr("d2savior.optimizer.common.BuildConstraints", _FakeConstraints)
    baseline, _, _, _ = _build_paladin_baseline(
        mule,
        spec="holy-fire",
        max_charm_slots=20,
        extra_chars=(),
        stashes=(),
        resolver=None,
        bo_base_bonus=0,
        keep_equipped=False,
    )
    assert baseline.base_max_fr == 5

    # Option #1 and #2 reach 75/75/75/75, which is still < 80 passive FR cap,
    # so `_collect_paladin_alternatives` must probe `leveling-res` at `floor_fhr` (0).
    opt1 = _as_result(_FakeBuildResult(fhr_bp=48, skills=2, fr=75, lr=75, cr=75, pr=75))
    opt_48 = _as_result(_FakeBuildResult(fhr_bp=27, skills=2, fr=75, lr=75, cr=75, pr=75))
    opt_cap = _as_result(_FakeBuildResult(fhr_bp=0, skills=2, fr=80, lr=75, cr=75, pr=75))
    seen_calls: list[tuple[str, int]] = []

    def _fake_opt(_items: object, _charms: object, c: _FakeConstraints) -> list[BuildResult]:
        seen_calls.append((c.mode, c.min_fhr))
        if c.mode == "leveling-res" and c.min_fhr == 27:
            return [opt_48]
        if c.mode == "leveling-res" and c.min_fhr == 0:
            return [opt_cap]
        return []

    monkeypatch.setattr("d2savior.optimizer.paladin.optimize_builds", _fake_opt)
    alts = _collect_paladin_alternatives(
        [],
        [],
        baseline,
        opt1,
        limit=4,
        offense="melee",
        is_caster=False,
        is_smite=False,
    )
    assert ("leveling-res", 0) in seen_calls
    assert any(r.fr == 80 for _, r in alts)

    # Socket `_build_score_key` uses `base_caps` rather than hardcoded 75.
    res_75 = _as_result(_FakeBuildResult(fr=75, lr=75, cr=75, pr=75))
    res_80 = _as_result(_FakeBuildResult(fr=80, lr=75, cr=75, pr=75))
    key_75 = _build_score_key(
        res_75,
        "leveling-res",
        "melee",
        has_aura=True,
        uses_caster_dps=False,
        base_caps=(80, 75, 75, 75),
    )
    key_80 = _build_score_key(
        res_80,
        "leveling-res",
        "melee",
        has_aura=True,
        uses_caster_dps=False,
        base_caps=(80, 75, 75, 75),
    )
    assert key_80 > key_75
