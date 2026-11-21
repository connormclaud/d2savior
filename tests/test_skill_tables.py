"""Unit tests for D2R skill DPS lookup table generation from skills.txt."""

import pytest

from d2savior.core.d2s_struct import CharSkills, D2SStruct
from d2savior.core.enums import CharClass
from d2savior.optimizer.skill_tables import (
    build_paladin_dps_tables,
    build_sorc_dps_tables,
    exploding_arrow_fire_2x,
    resolve_skill_override,
    resolve_sorc_filler_skill,
)


def _make_paladin(skill_pts: dict[int, int]) -> D2SStruct:
    """Create a minimal Paladin D2SStruct with given hard skill points (0-based offsets)."""
    char = D2SStruct()
    char.char_class = int(CharClass.PALADIN)
    sd = CharSkills()
    sd.skill_levels = [0] * 30
    for offset, pts in skill_pts.items():
        sd.skill_levels[offset] = pts
    char.skills = sd
    return char


class TestPaladinDpsTables:
    def test_holy_fire_lvl1_and_lvl20_with_synergy(self):
        # Holy Fire offset = 6, Resist Fire offset = 4, Zeal offset = 10, Sacrifice offset = 0
        c1 = _make_paladin({6: 1})
        t1 = build_paladin_dps_tables(c1, "holy-fire", "melee", max_bonus=2)
        assert t1.has_aura is True
        # HitShift=7 (0.5x), EMin=2, EMax=6 => pulse 1..3 (avg 2.0, dps 1.0), on-hit 6x = 6..18 (avg 12.0)
        assert t1.aura_pulse_dps[0] == pytest.approx(1.0)
        assert t1.aura_hit_dmg[0] == pytest.approx(12.0)
        assert t1.action_hits == (1,)
        assert t1.action_ed == (0,)

        # smite.d2s baseline: Holy Fire 20, Resist Fire 3 (+63% synergy), Zeal 1, Sacrifice 1 (+12% ED)
        c20 = _make_paladin({6: 20, 4: 3, 10: 1, 0: 1})
        t20 = build_paladin_dps_tables(c20, "holy-fire", "zeal", max_bonus=10)
        assert t20.has_aura is True
        # lvl 20 raw: min=2+7+32+24=65, max=6+14+40+28=88 => pulse_avg=76.5*0.5*1.63=62.3475
        assert t20.aura_pulse_dps[0] == pytest.approx(62.3475 / 2.0)
        assert t20.aura_hit_dmg[0] == pytest.approx(62.3475 * 6.0)
        # lvl 28 (bonus +8): min=65+12+42=119, max=88+14+48=150 => pulse_avg=134.5*0.5*1.63=109.6175
        assert t20.aura_hit_dmg[8] == pytest.approx(109.6175 * 6.0)
        # Zeal lvl 1 -> 2 hits, lvl 2 -> 3 hits, lvl 4 -> 5 hits, lvl 5 -> 5 hits + 6% ED + 12% Sac
        assert t20.action_hits[:5] == (2, 3, 4, 5, 5)
        assert t20.action_ed[:6] == (12, 12, 12, 12, 18, 24)

    def test_holy_freeze_multiplier_and_synergy(self):
        # Holy Freeze offset = 18, Resist Cold offset = 9 (15%/pt), Salvation offset = 29 (ID 125, 7%/pt)
        c = _make_paladin({18: 1, 9: 2, 29: 1})
        t = build_paladin_dps_tables(c, "holy-freeze", "melee", max_bonus=1)
        assert t.has_aura is True
        # EMin=2, EMax=3, HitShift=8 (1.0x), syn=1+0.37=1.37, on-hit=5x
        pulse_avg = 2.5 * 1.37
        assert t.aura_pulse_dps[0] == pytest.approx(pulse_avg / 2.0)
        assert t.aura_hit_dmg[0] == pytest.approx(pulse_avg * 5.0)

    def test_holy_shock_flat_min_one_and_6x_max(self):
        # Holy Shock offset = 22, Resist Lightning offset = 14 (12%/pt)
        c = _make_paladin({22: 1, 14: 1})
        t = build_paladin_dps_tables(c, "holy-shock", "melee", max_bonus=1)
        assert t.has_aura is True
        # EMin=1, EMax=10, HitShift=8 (1.0x), syn=1.12 => pulse 1.12..11.2, on-hit min=1.0, max=6*11.2=67.2
        assert t.aura_pulse_dps[0] == pytest.approx((1.12 + 11.2) / 4.0)
        assert t.aura_hit_dmg[0] == pytest.approx((1.0 + 67.2) / 2.0)

    def test_zero_hard_points_edge_cases(self):
        # 0 hard points in Holy Fire and 0 hard points in Zeal -> all-zero aura, normal Attack
        c = _make_paladin({})
        t = build_paladin_dps_tables(c, "holy-fire", "zeal", max_bonus=5)
        assert t.has_aura is False
        assert t.aura_hit_dmg == (0.0,)
        assert t.aura_pulse_dps == (0.0,)
        assert t.action_hits == (1,)
        assert t.action_ed == (0,)
        assert t.aura_is_fire is False

    def test_aura_is_fire_and_exploding_arrow_fire_2x(self):
        assert build_paladin_dps_tables(_make_paladin({6: 20}), "holy-fire", "melee").aura_is_fire
        assert not build_paladin_dps_tables(
            _make_paladin({18: 20}), "holy-freeze", "melee"
        ).aura_is_fire
        assert not build_paladin_dps_tables(
            _make_paladin({22: 20}), "holy-shock", "melee"
        ).aura_is_fire
        # Exploding Arrow lvl 3 (Raven Claw): 17-27 fire -> 2x = 44; lvl 0 -> 0
        assert exploding_arrow_fire_2x(0) == 0
        assert exploding_arrow_fire_2x(3) == 44

    def test_paladin_ar_and_conviction_tables(self):
        # Zeal lvl 1..20 (ToHit=10, LevToHit=10 => 10 * slvl) + Fanaticism lvl 20 (40 + 19*5 = 135%)
        # + Blessed Aim 4 hard pts passive (+20%) => aura_ar_pct[0] = 155%.
        # Fanaticism keeps has_aura=False so primary skill remains Zeal!
        c_zeal = _make_paladin({10: 1, 26: 20, 12: 4})
        t_zeal = build_paladin_dps_tables(c_zeal, "zeal", "zeal", max_bonus=5)
        assert t_zeal.has_aura is False
        assert t_zeal.action_ar_pct[:3] == (10, 20, 30)
        assert t_zeal.aura_ar_pct[:3] == (155, 160, 165)
        assert t_zeal.aura_target_def_pct == (0,)

        # Blessed Aim active (offset=12, lvl 10 => 75 + 9*15 = 210%) overrides passive when selected.
        c_ba = _make_paladin({10: 5, 12: 10})
        t_ba = build_paladin_dps_tables(c_ba, "zeal", "zeal", right_skill=108, max_bonus=2)
        assert t_ba.has_aura is False
        assert t_ba.aura_ar_pct == (210, 225, 240)

        # Vengeance (offset=15, ToHit=20, LevToHit=10) + Conviction (ID=123, offset=27)
        c_conv = _make_paladin({15: 20, 27: 20})
        t_conv = build_paladin_dps_tables(c_conv, "vengeance", "melee", max_bonus=5)
        assert t_conv.has_aura is False
        assert t_conv.action_ar_pct[:2] == (210, 220)
        # Conviction slvl 20: 90%, slvl 21: 91%, slvl 25: 92%.
        assert t_conv.aura_target_def_pct[:2] == (90, 91)
        assert t_conv.aura_target_def_pct[5] == 92

        # Sacrifice (offset=0, ToHit=20, LevToHit=7) & Charge (offset=11, ToHit=50, LevToHit=15).
        assert build_paladin_dps_tables(
            _make_paladin({0: 2}), "sacrifice", "melee", max_bonus=1
        ).action_ar_pct == (27, 34)
        assert build_paladin_dps_tables(
            _make_paladin({11: 2}), "charge", "melee", max_bonus=1
        ).action_ar_pct == (65, 80)


def _make_sorc(skill_pts: dict[int, int], left: int = 0, right: int = 0) -> D2SStruct:
    char = D2SStruct()
    char.char_class = int(CharClass.SORCERESS)
    char.left_skill_1 = left
    char.right_skill_1 = right
    sd = CharSkills()
    sd.skill_levels = [0] * 30
    for offset, pts in skill_pts.items():
        sd.skill_levels[offset] = pts
    char.skills = sd
    return char


class TestSorcDpsTablesAndOverrides:
    def test_sorc_blizzard_and_filler_tables(self):
        # Sorc offsets relative to 36: Ice Bolt=3, Ice Blast=9, Glacial Spike=19, Blizzard=23
        c = _make_sorc({3: 14, 9: 20, 19: 20, 23: 20})
        t_ib = build_sorc_dps_tables(c, targets=1, max_bonus=5)
        # Blizzard lvl 20, 54 syn pts (+270%): raw avg 594.5 * 3.7 = 2199.65
        assert t_ib.blizz_dmg[0] == pytest.approx(594.5 * 3.7)
        assert t_ib.filler_skill_name == "Ice Blast"
        assert t_ib.filler_is_aoe is False
        # Ice Blast lvl 20 (HitShift=7 => 0.5x), 34 syn pts (Ice Bolt 14 + Blizz 20 => +272%):
        # EMin(20)=16+7*14+8*28+4*42=506, EMax(20)=24+7*15+8*29+4*43=533 => avg 519.5*0.5*3.72
        assert t_ib.filler_dmg[0] == pytest.approx(519.5 * 0.5 * 3.72)

        # Tie between 20 IB and 20 GS picks Glacial Spike for targets > 1, or explicit override.
        t_gs = build_sorc_dps_tables(c, targets=3, max_bonus=5)
        assert t_gs.filler_skill_name == "Glacial Spike"
        assert t_gs.filler_is_aoe is True

        # Most allocated skill points wins when save has neither bound.
        c_more_gs = _make_sorc({3: 1, 9: 10, 19: 20, 23: 20})
        assert resolve_sorc_filler_skill(c_more_gs, targets=1) == 55

        # Explicit --left-skill none disables filler.
        t_none = build_sorc_dps_tables(c, left_skill=-1)
        assert t_none.filler_dmg == ()
        assert t_none.filler_skill_name is None

        # Weapon Set II reads left_skill_2 / right_skill_2.
        c_w2 = _make_sorc({3: 14, 9: 20, 19: 20, 23: 20}, left=45, right=59)
        c_w2.left_skill_2 = 55  # Glacial Spike
        c_w2.right_skill_2 = 59
        c_w2.weapon_set = 1
        assert resolve_sorc_filler_skill(c_w2, targets=1) == 55

    def test_resolve_skill_override(self):
        assert resolve_skill_override("none") == -1
        assert resolve_skill_override("attack") == 0
        assert resolve_skill_override("ice-blast") == 45
        assert resolve_skill_override("Glacial Spike") == 55
        assert resolve_skill_override("blizzard") == 59
        assert resolve_skill_override("zeal") == 106
        assert resolve_skill_override("holy-fire") == 102
        with pytest.raises(ValueError, match="Unknown skill"):
            resolve_skill_override("not-a-skill")
