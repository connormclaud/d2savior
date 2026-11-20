"""Unit tests for D2R skill DPS lookup table generation from skills.txt."""

import pytest

from d2savior.core.d2s_struct import CharSkills, D2SStruct
from d2savior.core.enums import CharClass
from d2savior.optimizer.skill_tables import build_paladin_dps_tables


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
