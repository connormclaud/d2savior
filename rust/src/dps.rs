use crate::stats::Stats;
use crate::types::{BuildConstraints, CharClass, ResolvedConstraints, SearchMode, TargetType};

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub(crate) enum WeaponClass {
    #[default]
    OneHandSwing,
    TwoHandSwing,
    OneHandThrust,
    TwoHandThrust,
    Staff,
    Bow,
    Crossbow,
}

impl WeaponClass {
    pub(crate) fn from_item(wclass: &str, slot: &str, name: &str) -> Self {
        match wclass.to_ascii_lowercase().as_str() {
            "1hs" | "hth" => Self::OneHandSwing,
            "2hs" => Self::TwoHandSwing,
            "1ht" => Self::OneHandThrust,
            "2ht" => Self::TwoHandThrust,
            "stf" => Self::Staff,
            "bow" => Self::Bow,
            "xbw" => Self::Crossbow,
            _ => match slot {
                "weapon2h" if name != "(empty)" => Self::TwoHandSwing,
                _ => Self::OneHandSwing,
            },
        }
    }

    pub(crate) fn is_ranged(self) -> bool {
        matches!(self, Self::Bow | Self::Crossbow)
    }

    pub(crate) fn frames_per_dir(self) -> i32 {
        match self {
            Self::OneHandSwing => 15,
            Self::TwoHandSwing | Self::Staff => 18,
            Self::OneHandThrust => 17,
            Self::TwoHandThrust | Self::Crossbow => 20,
            Self::Bow => 16,
        }
    }

    pub(crate) fn action_frame(self) -> i32 {
        match self {
            Self::OneHandSwing | Self::OneHandThrust | Self::Bow => 7,
            Self::TwoHandSwing | Self::Staff => 8,
            Self::TwoHandThrust | Self::Crossbow => 9,
        }
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub(crate) struct HandWeapon {
    pub(crate) wclass: WeaponClass,
    pub(crate) wsm: i32,
    pub(crate) phys_2x: i32,
    pub(crate) str_pct: i32,
    pub(crate) dex_pct: i32,
    pub(crate) can_zeal: bool,
    pub(crate) splash_fire: bool,
    pub(crate) splash_fire_2x: i32,
}

impl HandWeapon {
    pub(crate) fn empty() -> Self {
        Self {
            wclass: WeaponClass::OneHandSwing,
            wsm: 0,
            phys_2x: 0,
            str_pct: 100,
            dex_pct: 0,
            can_zeal: true,
            splash_fire: false,
            splash_fire_2x: 0,
        }
    }
}

pub(crate) fn holy_shield_smite_dmg_2x(slvl: i32) -> i32 {
    if slvl <= 0 {
        return 0;
    }
    let mut bonus = 0;
    let mut rem = slvl - 1;
    for (tier_len, inc) in [(7, 2), (8, 3), (6, 4), (6, 4)] {
        let step = rem.min(tier_len);
        bonus += step * inc;
        rem -= step;
        if rem <= 0 {
            return 9 + 2 * bonus;
        }
    }
    9 + 2 * (bonus + rem * 4)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum OffenseProfile {
    Caster,
    Melee,
    Zeal,
    Smite,
}

impl OffenseProfile {
    pub(crate) fn parse(s: &str, class: CharClass) -> Result<Self, String> {
        let profile = if s.eq_ignore_ascii_case("caster") {
            Self::Caster
        } else if s.eq_ignore_ascii_case("melee") {
            Self::Melee
        } else if s.eq_ignore_ascii_case("zeal") {
            Self::Zeal
        } else if s.eq_ignore_ascii_case("smite") {
            Self::Smite
        } else {
            return Err(format!(
                "invalid offense profile '{s}'; expected 'caster', 'melee', 'zeal', or 'smite'"
            ));
        };
        if class == CharClass::Sorceress && profile != Self::Caster {
            return Err(format!(
                "offense profile '{s}' is not supported for Sorceress; expected 'caster'"
            ));
        }
        Ok(profile)
    }

    pub(crate) fn requires_shield(self) -> bool {
        matches!(self, Self::Smite)
    }

    pub(crate) fn requires_melee(self) -> bool {
        matches!(self, Self::Zeal)
    }

    pub(crate) fn uses_fcr(self) -> bool {
        matches!(self, Self::Caster)
    }

    pub(crate) fn is_melee_dps(self) -> bool {
        matches!(self, Self::Melee | Self::Zeal | Self::Smite)
    }

    pub(crate) fn uses_dps_tables(self, c: &BuildConstraints) -> bool {
        self.is_melee_dps() && c.skills.melee().is_some_and(|m| !m.action_hits.is_empty())
    }

    pub(crate) fn uses_caster_dps(self, c: &BuildConstraints) -> bool {
        self == Self::Caster && c.skills.caster().is_some_and(|m| !m.blizz_dmg.is_empty())
    }

    /// Return `(cast_frames, action_frame)` for Sorceress standard cast (`SC`, FPD=14, AF=7).
    pub(crate) fn sorc_cast_and_action_frames(fcr: i32) -> (i32, i32) {
        if fcr >= 200 {
            (7, 4)
        } else if fcr >= 105 {
            (8, 5)
        } else if fcr >= 63 {
            (9, 5)
        } else if fcr >= 37 {
            (10, 6)
        } else if fcr >= 20 {
            (11, 6)
        } else if fcr >= 9 {
            (12, 7)
        } else {
            (13, 7)
        }
    }

    pub(crate) fn compute_caster_dps(self, s: Stats, c: &BuildConstraints) -> f64 {
        let Some(caster) = c.skills.caster() else {
            return 0.0;
        };
        if caster.blizz_dmg.is_empty() {
            return 0.0;
        }
        let targets = c.target.targets.max(1) as f64;
        let cold_mult = 1.0 + s.cold_dmg_pct.max(0) as f64 / 100.0;
        let eff_blizz = (s.all_skills + s.class_skills + s.blizz_skills).max(0) as usize;
        let blizz_per_cast = caster.blizz_dmg[eff_blizz.min(caster.blizz_dmg.len() - 1)]
            * cold_mult
            * 3.0
            * targets;

        let (cast_f, action_f) = Self::sorc_cast_and_action_frames(s.fcr);
        let cd_ready = action_f + 45;

        if caster.filler_dmg.is_empty() {
            return blizz_per_cast * (25.0 / cd_ready as f64);
        }

        let eff_filler = (s.all_skills + s.class_skills + s.action_skill_bonus).max(0) as usize;
        let filler_mult = if caster.filler_is_aoe { targets } else { 1.0 };
        let filler_per_cast = caster.filler_dmg[eff_filler.min(caster.filler_dmg.len() - 1)]
            * cold_mult
            * filler_mult;

        // Discrete Blizzard + filler cycle: compare idle (k_idle fillers, cycle = cd_ready)
        // vs over-cast (k_over fillers, cycle = (1 + k_over) * cast_f). Strictly monotone in FCR.
        let rem = (cd_ready - cast_f).max(0);
        let k_idle = rem / cast_f;
        let dps_idle = (blizz_per_cast + k_idle as f64 * filler_per_cast) * (25.0 / cd_ready as f64);

        let k_over = (rem + cast_f - 1) / cast_f;
        let cycle_over = (1 + k_over) * cast_f;
        let dps_over =
            (blizz_per_cast + k_over as f64 * filler_per_cast) * (25.0 / cycle_over as f64);

        dps_idle.max(dps_over)
    }

    pub(crate) fn weapon_anim_key(
        self,
        mode: SearchMode,
        hand: HandWeapon,
    ) -> (bool, WeaponClass, i32, i32, i32, bool, i32) {
        if !matches!(mode, SearchMode::Leveling | SearchMode::LevelingRes) || self == Self::Caster {
            return (false, WeaponClass::OneHandSwing, 0, 0, 0, false, 0);
        }
        if self == Self::Smite {
            (false, WeaponClass::OneHandSwing, hand.wsm, 0, 0, false, 0)
        } else {
            (
                hand.can_zeal,
                hand.wclass,
                hand.wsm,
                hand.str_pct,
                hand.dex_pct,
                hand.splash_fire,
                hand.splash_fire_2x,
            )
        }
    }

    fn ias_bp_for_min_speed(min_speed: i32, wsm: i32, skill_eias: i32) -> i32 {
        let min_net_eias = ((100 * min_speed + 255) / 256 - 100).max(-85);
        let min_eias = (min_net_eias + wsm - skill_eias).max(0);
        if min_eias <= 0 {
            0
        } else {
            let denom = (120 - min_eias).max(1);
            (120 * min_eias + denom - 1) / denom
        }
    }

    pub(crate) fn attack_speed(self, wclass: WeaponClass, wsm: i32, ias: i32) -> (i32, i32) {
        let clamped_ias = ias.max(0);
        let eias = (120 * clamped_ias) / (120 + clamped_ias);
        let net_eias = (eias - wsm).clamp(-85, 75);
        let speed = (256 * (100 + net_eias)) / 100;
        let (frames, min_speed) = if self == Self::Smite {
            let fpd = 12;
            let f = (256 * fpd + speed - 1) / speed - 1;
            let ms = (256 * fpd + f) / (f + 1);
            (f, ms)
        } else if self == Self::Zeal && !wclass.is_ranged() {
            let af = wclass.action_frame();
            let f = (256 * af + speed - 1) / speed;
            let ms = (256 * af + f - 1) / f;
            (f, ms)
        } else {
            let fpd = wclass.frames_per_dir();
            let f = (256 * fpd + speed - 1) / speed - 1;
            let ms = (256 * fpd + f) / (f + 1);
            (f, ms)
        };
        (Self::ias_bp_for_min_speed(min_speed, wsm, 0), frames)
    }

    /// Return `(hits_per_sec, ias_bp, display_frames, last_frames, used_zeal)` using exact D2R rollback frames.
    pub(crate) fn attack_rate_and_frames(
        self,
        hand: HandWeapon,
        ias: i32,
        zeal_hits: i32,
        skill_eias: i32,
    ) -> (f64, i32, i32, i32, bool) {
        let clamped_ias = ias.max(0);
        let eias = (120 * clamped_ias) / (120 + clamped_ias);
        let net_eias = (eias + skill_eias - hand.wsm).clamp(-85, 75);
        let speed = (256 * (100 + net_eias)) / 100;

        if self == Self::Zeal && hand.can_zeal && zeal_hits >= 2 {
            let af = hand.wclass.action_frame();
            let f_rollback = (256 * af + speed - 1) / speed;
            let ms_rollback = (256 * af + f_rollback - 1) / f_rollback;
            let fpd = hand.wclass.frames_per_dir();
            let f_last = (256 * fpd + speed - 1) / speed - 1;
            let ms_last = (256 * fpd + f_last) / (f_last + 1);
            let cycle = (zeal_hits - 1) * f_rollback + f_last;
            let rate = (25.0 * zeal_hits as f64) / (cycle.max(1) as f64);
            (
                rate,
                Self::ias_bp_for_min_speed(ms_rollback.max(ms_last), hand.wsm, skill_eias),
                f_rollback,
                f_last,
                true,
            )
        } else {
            let fpd = if self == Self::Smite {
                12
            } else {
                hand.wclass.frames_per_dir()
            };
            let f_normal = (256 * fpd + speed - 1) / speed - 1;
            let ms = (256 * fpd + f_normal) / (f_normal + 1);
            let rate = 25.0 / (f_normal.max(1) as f64);
            (
                rate,
                Self::ias_bp_for_min_speed(ms, hand.wsm, skill_eias),
                f_normal,
                0,
                false,
            )
        }
    }

    /// Quantize continuous DPS into ~2% logarithmic buckets (monotone in `dps`).
    pub(crate) fn dps_bucket(dps: f64) -> i32 {
        if dps <= 0.0 || !dps.is_finite() {
            0
        } else {
            (dps.ln() / 1.02_f64.ln()).floor().max(0.0) as i32
        }
    }

    #[inline]
    pub(crate) fn dps_bucket_safe_min_dps(bucket: i32) -> f64 {
        if bucket <= 0 {
            0.0
        } else {
            1.02_f64.powi(bucket) * (1.0 - 1e-12)
        }
    }

    /// Compute detailed melee DPS breakdown (`eff_dps`, `raw_dps`, AR, CTH, IAS/frames, Zeal flag).
    ///
    /// Expects `s.str_bonus` and `s.dex_bonus` to be total character strength/dexterity
    /// (`c.character.base_str + gear + charms`), matching `ub_ch` in `search.rs`.
    pub(crate) fn compute_dps_detailed(
        self,
        hand: HandWeapon,
        s: Stats,
        c: &ResolvedConstraints<'_>,
    ) -> DpsBreakdown {
        self.fast_leaf_dps(hand, s, c).eval_detailed()
    }

    pub(crate) fn compute_dps(
        self,
        hand: HandWeapon,
        s: Stats,
        c: &ResolvedConstraints<'_>,
    ) -> (f64, i32, i32, i32, bool) {
        let d = self.compute_dps_detailed(hand, s, c);
        (d.eff_dps, d.ias_bp, d.display_frames, d.last_frames, d.used_zeal)
    }

    pub(crate) fn compute_eff_dps(
        self,
        hand: HandWeapon,
        s: Stats,
        c: &ResolvedConstraints<'_>,
    ) -> f64 {
        self.fast_leaf_dps(hand, s, c).eval_eff_dps()
    }

    /// Build a fast precomputed DPS evaluator at fixed `leaf` (only pure AR/flat/psn vary).
    pub(crate) fn fast_leaf_dps(
        self,
        hand: HandWeapon,
        leaf: Stats,
        c: &ResolvedConstraints<'_>,
    ) -> FastLeafDps {
        let is_smite = self == Self::Smite;
        let melee = c.skills.melee();
        let action_hits = melee.map_or(&[][..], |m| m.action_hits.as_slice());
        let action_ed_tbl = melee.map_or(&[][..], |m| m.action_ed.as_slice());
        let action_ar_tbl = melee.map_or(&[][..], |m| m.action_ar_pct.as_slice());
        let aura_ar_tbl = melee.map_or(&[][..], |m| m.aura_ar_pct.as_slice());
        let aura_target_def_tbl = melee.map_or(&[][..], |m| m.aura_target_def_pct.as_slice());
        let aura_hit_tbl = melee.map_or(&[][..], |m| m.aura_hit_dmg.as_slice());
        let aura_pulse_tbl = melee.map_or(&[][..], |m| m.aura_pulse_dps.as_slice());
        let aura_ed_tbl = melee.map_or(&[][..], |m| m.aura_ed.as_slice());
        let aura_ias_tbl = melee.map_or(&[][..], |m| m.aura_ias.as_slice());
        let aura_is_fire = !is_smite && melee.is_some_and(|m| m.aura_is_fire);
        let holy_shield_base_lvl = melee.map_or(0, |m| m.holy_shield_base_lvl);

        let eff_action = (leaf.all_skills + leaf.class_skills + leaf.action_skill_bonus).max(0) as usize;
        let eff_aura = (leaf.all_skills + leaf.class_skills + leaf.aura_skill_bonus).max(0) as usize;

        let hits = if action_hits.is_empty() {
            1
        } else {
            action_hits[eff_action.min(action_hits.len() - 1)].max(1)
        };
        let skill_eias = if is_smite && !aura_ias_tbl.is_empty() {
            aura_ias_tbl[eff_aura.min(aura_ias_tbl.len() - 1)]
        } else {
            0
        };
        let (rate, ias_bp, display_frames, last_frames, used_zeal) =
            self.attack_rate_and_frames(hand, leaf.ias, hits, skill_eias);
        let action_ed = if (used_zeal || is_smite) && !action_ed_tbl.is_empty() {
            action_ed_tbl[eff_action.min(action_ed_tbl.len() - 1)]
        } else {
            0
        };
        let aura_ed = if is_smite && !aura_ed_tbl.is_empty() {
            aura_ed_tbl[eff_aura.min(aura_ed_tbl.len() - 1)]
        } else {
            0
        };

        let (str_pct, dex_pct) = if is_smite {
            (100, 0)
        } else {
            (hand.str_pct, hand.dex_pct)
        };
        let total_str = leaf.str_bonus.max(0);
        let total_dex = leaf.dex_bonus.max(0);
        let stat_ed = (total_str * str_pct + total_dex * dex_pct) / 100;

        let target_type = c.target_type;
        let (demon_w, undead_w) = if is_smite {
            (0.0, 0.0)
        } else if matches!(target_type, TargetType::Boss) {
            (1.0, 0.0)
        } else {
            (1.0 / 3.0, 1.0 / 3.0)
        };
        let base_ed_int = action_ed + aura_ed + leaf.off_ed;
        let ed_du =
            leaf.ed_demon.max(0) as f64 * demon_w + leaf.ed_undead.max(0) as f64 * undead_w;
        let eff_ed = (stat_ed + base_ed_int).max(0) as f64 + ed_du;

        let crit_mult = if is_smite {
            1.0
        } else {
            let ds_prob = leaf.ds.clamp(0, 100) as f64 / 100.0;
            let cs_prob = if leaf.cs_oskill > 0 {
                let slvl = (leaf.cs_oskill + leaf.all_skills).max(1);
                let pct = 5 + (75 * ((110 * slvl) / (slvl + 6))) / 100;
                pct.clamp(0, 100) as f64 / 100.0
            } else {
                0.0
            };
            1.0 + (1.0 - (1.0 - ds_prob) * (1.0 - cs_prob))
        };
        let phys_scale = (1.0 + eff_ed / 100.0) * crit_mult;

        let class = c.class;
        let dex_base_ar = class.base_ar_from_dex(total_dex);
        let act_ar_pct = if !is_smite
            && (used_zeal || (self == Self::Melee && !hand.wclass.is_ranged()))
            && !action_ar_tbl.is_empty()
        {
            action_ar_tbl[eff_action.min(action_ar_tbl.len() - 1)]
        } else {
            0
        };
        let aura_ar_pct = if !is_smite && !aura_ar_tbl.is_empty() {
            aura_ar_tbl[eff_aura.min(aura_ar_tbl.len() - 1)]
        } else {
            0
        };
        let total_ar_pct = (leaf.ar_pct + act_ar_pct + aura_ar_pct).max(0);
        let itd_active = !is_smite && leaf.itd > 0 && target_type.allows_itd();
        let conv_red = if is_smite || aura_target_def_tbl.is_empty() {
            0
        } else {
            aura_target_def_tbl[eff_aura.min(aura_target_def_tbl.len() - 1)]
        };
        // In D2R, Conviction's defense reduction and gear -% Target Defense stack multiplicatively,
        // and gear -% Target Defense is halved against Champions, Uniques, and Bosses.
        let conv_mult = (100 - conv_red.clamp(0, 100)) as f64 / 100.0;
        let gear_red = target_type.gear_target_def_reduction(leaf.target_def_pct);
        let gear_mult = (100 - gear_red) as f64 / 100.0;
        let eff_dr = if is_smite {
            0.0
        } else {
            (c.target.target_def.max(0) as f64) * conv_mult * gear_mult
        };

        let p_dec = leaf.ctc_decrep_pct.clamp(0, 100) as f64 / 100.0;
        let d_aura_hit = if is_smite || aura_hit_tbl.is_empty() {
            0.0
        } else {
            aura_hit_tbl[eff_aura.min(aura_hit_tbl.len() - 1)]
        };
        let d_aura_pulse = if is_smite || aura_pulse_tbl.is_empty() {
            0.0
        } else {
            aura_pulse_tbl[eff_aura.min(aura_pulse_tbl.len() - 1)]
        };
        let targets = c.target.targets.max(1) as f64;
        let d_splash_fire = if !is_smite && hand.splash_fire {
            (hand.splash_fire_2x.max(0) as f64 / 2.0) * targets
        } else {
            0.0
        };

        let cb_frac = match (target_type, !is_smite && hand.wclass.is_ranged()) {
            (TargetType::Trash, false) => 0.25,
            (TargetType::Trash, true) | (_, false) => 0.125,
            (_, true) => 0.0625,
        };
        let d_cb_hit =
            (leaf.cb.clamp(0, 100) as f64 / 100.0) * cb_frac * (0.5 * c.target.target_hp.max(0) as f64);

        let p_ow = leaf.ow.clamp(0, 100) as f64 / 100.0;
        let ow_target_mult = if matches!(target_type, TargetType::Trash) {
            1.0
        } else {
            0.5
        };
        let clvl_i = c.character.char_level.max(1);
        let clvl = clvl_i as f64;
        let ow_raw_tick = if clvl_i <= 15 {
            9.0 * clvl + 40.0
        } else if clvl_i <= 30 {
            18.0 * clvl - 95.0
        } else if clvl_i <= 45 {
            27.0 * clvl - 365.0
        } else if clvl_i <= 60 {
            36.0 * clvl - 770.0
        } else {
            45.0 * clvl - 1310.0
        };
        let ow_base_dps = 25.0 * ow_raw_tick / 256.0 * ow_target_mult;

        let d_static_hit = (leaf.ctc_static_pct.clamp(0, 100) as f64 / 100.0)
            * 0.25
            * (0.25 * c.target.target_hp.max(0) as f64)
            * targets;
        let d_orb_hit = (leaf.ctc_orb_dmg_2x.max(0) as f64 / 2.0) * targets.min(3.0);

        let (pierce_p, max_extra_pierce) =
            if !is_smite && hand.wclass.is_ranged() && c.target.targets > 1 && leaf.pierce > 0 {
                (
                    leaf.pierce.clamp(0, 100) as f64 / 100.0,
                    (c.target.targets - 1).min(4),
                )
            } else {
                (0.0, 0)
            };

        // Exploding Arrow's AoE blast is auto-hit and carries flat fire and Holy Fire on-hit damage
        // across all targets even when the physical arrow misses the AR roll. Note `pid 158`
        // (`item_explosivearrow`) uses weapon `ar_pct` rather than Amazon skill ToHit%, and
        // `d_aura_hit * targets` is counted once per target in `auto_hit_attack` (keeping prior
        // raw_dps parity rather than double-counting direct arrow + splash on the primary target).
        let (base_direct_non_phys, base_auto_hit) = if !is_smite && hand.splash_fire {
            let (direct_aura, auto_aura) = if aura_is_fire {
                (0.0, d_aura_hit * targets)
            } else {
                (d_aura_hit, 0.0)
            };
            (
                direct_aura + d_cb_hit + d_static_hit + d_orb_hit,
                d_splash_fire + auto_aura,
            )
        } else {
            (
                d_aura_hit + d_cb_hit + d_static_hit + d_orb_hit,
                d_splash_fire,
            )
        };

        let hs_dmg_2x = if is_smite && holy_shield_base_lvl > 0 {
            let hs_slvl = (holy_shield_base_lvl
                + leaf.all_skills
                + leaf.class_skills
                + leaf.def_skill)
                .max(1);
            holy_shield_smite_dmg_2x(hs_slvl)
        } else {
            0
        };
        let phys_2x_0 = if is_smite {
            hs_dmg_2x + leaf.flat_phys_2x
        } else {
            hand.phys_2x + leaf.flat_phys_2x
        };

        let psn_exp = (2.0 * rate).max(1.0);
        let eff_rate = if leaf.cbf > 0 {
            rate
        } else {
            rate * NO_CBF_CHILL_RATE_MULT
        };
        let mut fast = FastLeafDps {
            is_smite,
            rate,
            eff_rate,
            ias_bp,
            display_frames,
            last_frames,
            used_zeal,
            phys_scale,
            dex_base_ar,
            leaf_ar: if is_smite { 0 } else { leaf.ar },
            total_ar_pct,
            eff_dr,
            itd_active,
            cth_is_const: false,
            p_dec,
            p_ow,
            ow_base_dps,
            pierce_p,
            max_extra_pierce,
            psn_exp,
            const_decrep_mult: 1.0,
            const_pierce_mult: 1.0,
            const_ow_dps: 0.0,
            const_psn_prob: 0.0,
            targets,
            splash_fire: !is_smite && hand.splash_fire,
            phys_2x_0,
            flat_fire_2x_0: if is_smite { 0 } else { leaf.flat_fire_2x },
            flat_elem_2x_0: if is_smite { 0 } else { leaf.flat_elem_2x },
            psn_2x_0: if is_smite { 0 } else { leaf.psn_dps_2x },
            ctc_venom_2x: if is_smite { 0 } else { leaf.ctc_venom_dps_2x.max(0) },
            base_direct_non_phys,
            base_auto_hit,
            base_aura_pulse_dps: d_aura_pulse * targets,
            base_str: leaf.str_bonus,
            base_dex: leaf.dex_bonus,
            str_pct,
            dex_pct,
            base_ed_int,
            ed_du,
            crit_mult,
            class,
        };
        fast.init_cth_const();
        fast
    }

    pub(crate) fn score(self, eff_primary: i32, ias_bp: i32, cb: i32) -> i32 {
        match self {
            Self::Caster => eff_primary,
            Self::Melee | Self::Zeal => eff_primary * 20 + (ias_bp.min(80) * 3) / 2,
            Self::Smite => cb.min(100) * 4 + ias_bp.min(80) * 2 + eff_primary * 10,
        }
    }

    pub(crate) fn score_stats(self, s: Stats) -> i32 {
        self.score(s.primary_power_skills(), s.ias, s.cb)
    }
}

/// Effective attack-rate multiplier when lacking Cannot Be Frozen (CBF).
/// Models ~30% chill uptime in combat with ~50% attack-speed loss while chilled (~15% net loss).
pub(crate) const NO_CBF_CHILL_RATE_MULT: f64 = 0.85;

#[derive(Clone, Copy)]
pub(crate) struct FastLeafDps {
    pub(crate) is_smite: bool,
    pub(crate) rate: f64,
    pub(crate) eff_rate: f64,
    pub(crate) ias_bp: i32,
    pub(crate) display_frames: i32,
    pub(crate) last_frames: i32,
    pub(crate) used_zeal: bool,
    pub(crate) phys_scale: f64,
    pub(crate) dex_base_ar: i32,
    pub(crate) leaf_ar: i32,
    pub(crate) total_ar_pct: i32,
    pub(crate) eff_dr: f64,
    pub(crate) itd_active: bool,
    pub(crate) cth_is_const: bool,
    pub(crate) p_dec: f64,
    pub(crate) p_ow: f64,
    pub(crate) ow_base_dps: f64,
    pub(crate) pierce_p: f64,
    pub(crate) max_extra_pierce: i32,
    pub(crate) psn_exp: f64,
    pub(crate) const_decrep_mult: f64,
    pub(crate) const_pierce_mult: f64,
    pub(crate) const_ow_dps: f64,
    pub(crate) const_psn_prob: f64,
    pub(crate) targets: f64,
    pub(crate) splash_fire: bool,
    pub(crate) phys_2x_0: i32,
    pub(crate) flat_fire_2x_0: i32,
    pub(crate) flat_elem_2x_0: i32,
    pub(crate) psn_2x_0: i32,
    pub(crate) ctc_venom_2x: i32,
    pub(crate) base_direct_non_phys: f64,
    pub(crate) base_auto_hit: f64,
    pub(crate) base_aura_pulse_dps: f64,
    pub(crate) base_str: i32,
    pub(crate) base_dex: i32,
    pub(crate) str_pct: i32,
    pub(crate) dex_pct: i32,
    pub(crate) base_ed_int: i32,
    pub(crate) ed_du: f64,
    pub(crate) crit_mult: f64,
    pub(crate) class: CharClass,
}

struct EvalCore {
    cth: f64,
    direct_hit: f64,
    auto_hit_attack: f64,
    psn_base: f64,
    eff_dps: f64,
}

#[derive(Clone, Copy)]
pub(crate) struct CthEval {
    pub(crate) cth: f64,
    pub(crate) decrep_mult: f64,
    pub(crate) pierce_mult: f64,
    pub(crate) d_ow_dps: f64,
    pub(crate) psn_prob: f64,
}

impl FastLeafDps {
    #[inline(always)]
    fn compute_cth_multipliers(&self, cth: f64) -> (f64, f64, f64) {
        let decrep_mult = if self.p_dec > 0.0 {
            1.0 + 0.5 * (1.0 - (1.0 - self.p_dec).powf((8.0 * self.rate * cth).max(1.0)))
        } else {
            1.0
        };
        let pierce_mult = if !self.is_smite && self.max_extra_pierce > 0 && self.pierce_p > 0.0 {
            let mut eff_m = 1.0;
            let mut eff_pow = 1.0;
            for _ in 0..self.max_extra_pierce {
                eff_pow *= cth * self.pierce_p;
                eff_m += eff_pow;
            }
            eff_m
        } else {
            1.0
        };
        let d_ow_dps = if self.p_ow > 0.0 {
            self.ow_base_dps * (1.0 - (1.0 - self.p_ow).powf((8.0 * self.rate * cth).max(1.0)))
        } else {
            0.0
        };
        (decrep_mult, pierce_mult, d_ow_dps)
    }

    fn init_cth_const(&mut self) {
        self.cth_is_const = self.is_smite
            || self.itd_active
            || self.eff_dr <= 0.0
            || self.cth_for_add_ar(0) >= 0.95;
        if self.cth_is_const {
            let cth = if self.is_smite { 1.0 } else { 0.95_f64 };
            let (decrep_mult, pierce_mult, d_ow_dps) = self.compute_cth_multipliers(cth);
            self.const_decrep_mult = decrep_mult;
            self.const_pierce_mult = pierce_mult;
            self.const_ow_dps = d_ow_dps;
            self.const_psn_prob = if self.is_smite {
                0.0
            } else {
                1.0 - (1.0 - cth).powf(self.psn_exp)
            };
        }
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn with_non_skill_deltas(
        &self,
        d_str: i32,
        d_dex: i32,
        d_ar: i32,
        d_phys_2x: i32,
        d_fire_2x: i32,
        d_elem_2x: i32,
        d_psn_2x: i32,
    ) -> FastLeafDps {
        let mut out = *self;
        if d_str != 0 || d_dex != 0 {
            out.base_str += d_str;
            out.base_dex += d_dex;
            let total_str = out.base_str.max(0);
            let total_dex = out.base_dex.max(0);
            let stat_ed = (total_str * out.str_pct + total_dex * out.dex_pct) / 100;
            let eff_ed = (stat_ed + out.base_ed_int).max(0) as f64 + out.ed_du;
            out.phys_scale = (1.0 + eff_ed / 100.0) * out.crit_mult;
            if d_dex != 0 {
                out.dex_base_ar = out.class.base_ar_from_dex(total_dex);
            }
        }
        if !self.is_smite {
            out.leaf_ar += d_ar;
            out.phys_2x_0 += d_phys_2x;
            out.flat_fire_2x_0 += d_fire_2x;
            out.flat_elem_2x_0 += d_elem_2x;
            out.psn_2x_0 += d_psn_2x;
            if (d_dex != 0 || d_ar != 0) && (!self.cth_is_const || d_dex < 0 || d_ar < 0) {
                out.init_cth_const();
            }
        }
        out
    }

    #[inline]
    pub(crate) fn total_ar_for_add_ar(&self, add_ar: i32) -> i32 {
        let base_ar = (self.dex_base_ar + (self.leaf_ar + add_ar).max(0)).max(0);
        ((base_ar as i64) * (100 + self.total_ar_pct as i64) / 100) as i32
    }

    #[inline]
    pub(crate) fn cth_for_add_ar(&self, add_ar: i32) -> f64 {
        if self.itd_active {
            return 0.95;
        }
        let total_ar = self.total_ar_for_add_ar(add_ar);
        let denom = total_ar as f64 + self.eff_dr;
        if denom <= 0.0 {
            0.95
        } else {
            (total_ar as f64 / denom).clamp(0.05, 0.95)
        }
    }

    #[inline(always)]
    fn eval_core_with_cth(
        &self,
        c: &mut CthEval,
        add_phys_2x: i32,
        add_elem_2x: i32,
        add_fire_2x: i32,
        add_psn_2x: i32,
    ) -> EvalCore {
        if self.is_smite {
            let phys_avg = self.phys_2x_0.max(0) as f64 / 2.0;
            let direct_hit =
                phys_avg * self.phys_scale * c.decrep_mult + self.base_direct_non_phys;
            let eff_dps = direct_hit * self.eff_rate + c.d_ow_dps;
            return EvalCore {
                cth: 1.0,
                direct_hit,
                auto_hit_attack: 0.0,
                psn_base: 0.0,
                eff_dps,
            };
        }
        let phys_avg = (self.phys_2x_0 + add_phys_2x).max(0) as f64 / 2.0;
        let d_phys = phys_avg * self.phys_scale * c.decrep_mult;
        let d_flat_fire = (self.flat_fire_2x_0 + add_fire_2x).max(0) as f64 / 2.0;
        let d_elem_other = (self.flat_elem_2x_0 + add_elem_2x).max(0) as f64 / 2.0;
        let (direct_hit, auto_hit_attack) = if self.splash_fire {
            (
                d_phys + d_elem_other + self.base_direct_non_phys,
                self.base_auto_hit + d_flat_fire * self.targets,
            )
        } else {
            (
                d_phys + d_flat_fire + d_elem_other + self.base_direct_non_phys,
                self.base_auto_hit,
            )
        };
        let psn_base = ((self.psn_2x_0 + add_psn_2x).max(0) + self.ctc_venom_2x) as f64 / 2.0;
        let d_psn_dps = if psn_base > 0.0 {
            if c.psn_prob < 0.0 {
                c.psn_prob = 1.0 - (1.0 - c.cth).powf(self.psn_exp);
            }
            psn_base * c.psn_prob
        } else {
            0.0
        };
        let eff_dps = (direct_hit * c.cth + auto_hit_attack) * c.pierce_mult * self.eff_rate
            + self.base_aura_pulse_dps
            + c.d_ow_dps
            + d_psn_dps;
        EvalCore {
            cth: c.cth,
            direct_hit,
            auto_hit_attack,
            psn_base,
            eff_dps,
        }
    }

    #[inline(always)]
    fn eval_core(
        &self,
        add_ar: i32,
        add_phys_2x: i32,
        add_elem_2x: i32,
        add_fire_2x: i32,
        add_psn_2x: i32,
    ) -> EvalCore {
        let mut cth = self.eval_cth_no_psn(add_ar);
        self.eval_core_with_cth(&mut cth, add_phys_2x, add_elem_2x, add_fire_2x, add_psn_2x)
    }

    #[inline]
    pub(crate) fn eval_dps(
        &self,
        add_ar: i32,
        add_phys_2x: i32,
        add_elem_2x: i32,
        add_fire_2x: i32,
        add_psn_2x: i32,
    ) -> f64 {
        self.eval_core(add_ar, add_phys_2x, add_elem_2x, add_fire_2x, add_psn_2x)
            .eff_dps
    }

    #[inline]
    pub(crate) fn eval_eff_dps(&self) -> f64 {
        self.eval_core(0, 0, 0, 0, 0).eff_dps
    }

    #[inline]
    pub(crate) fn const_cth_eval(&self) -> CthEval {
        CthEval {
            cth: if self.is_smite { 1.0 } else { 0.95 },
            decrep_mult: self.const_decrep_mult,
            pierce_mult: self.const_pierce_mult,
            d_ow_dps: self.const_ow_dps,
            psn_prob: self.const_psn_prob,
        }
    }

    #[inline]
    pub(crate) fn eval_cth_no_psn(&self, add_ar: i32) -> CthEval {
        if self.cth_is_const {
            return self.const_cth_eval();
        }
        let cth = self.cth_for_add_ar(add_ar);
        let (decrep_mult, pierce_mult, d_ow_dps) = self.compute_cth_multipliers(cth);
        CthEval {
            cth,
            decrep_mult,
            pierce_mult,
            d_ow_dps,
            psn_prob: -1.0,
        }
    }

    #[inline(always)]
    pub(crate) fn eval_dps_with_cth(
        &self,
        c: &mut CthEval,
        add_phys_2x: i32,
        add_elem_2x: i32,
        add_fire_2x: i32,
        add_psn_2x: i32,
    ) -> f64 {
        self.eval_core_with_cth(c, add_phys_2x, add_elem_2x, add_fire_2x, add_psn_2x)
            .eff_dps
    }

    pub(crate) fn eval_detailed(&self) -> DpsBreakdown {
        let core = self.eval_core(0, 0, 0, 0, 0);
        let (_, raw_pierce_mult, d_ow_dps_raw) = self.compute_cth_multipliers(1.0);
        let (total_ar, cth_pct, psn_raw) = if self.is_smite {
            (0, 0, 0.0)
        } else {
            (
                self.total_ar_for_add_ar(0),
                (core.cth * 100.0).round() as i32,
                core.psn_base,
            )
        };
        let raw_dps = (core.direct_hit + core.auto_hit_attack) * raw_pierce_mult * self.rate
            + self.base_aura_pulse_dps
            + d_ow_dps_raw
            + psn_raw;
        DpsBreakdown {
            eff_dps: core.eff_dps,
            raw_dps,
            total_ar,
            cth_pct,
            ias_bp: self.ias_bp,
            display_frames: self.display_frames,
            last_frames: self.last_frames,
            used_zeal: self.used_zeal,
        }
    }
}

#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct DpsBreakdown {
    pub(crate) eff_dps: f64,
    pub(crate) raw_dps: f64,
    pub(crate) total_ar: i32,
    pub(crate) cth_pct: i32,
    pub(crate) ias_bp: i32,
    pub(crate) display_frames: i32,
    pub(crate) last_frames: i32,
    pub(crate) used_zeal: bool,
}
