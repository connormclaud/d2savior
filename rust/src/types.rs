#[cfg(feature = "python")]
use pyo3::prelude::*;

pub(crate) const BASE_MAX_RES: i32 = 75;
pub(crate) const HARD_MAX_RES: i32 = 95;

pub(crate) const SORCERESS_FCR_BPS: &[i32] = &[0, 9, 20, 37, 63, 105, 200];
pub(crate) const SORCERESS_FHR_BPS: &[i32] = &[0, 5, 9, 14, 20, 30, 42, 60, 86, 142, 280];
pub(crate) const PALADIN_FCR_BPS: &[i32] = &[0, 9, 18, 30, 48, 75, 125];
pub(crate) const PALADIN_FHR_BPS: &[i32] = &[0, 7, 15, 27, 48, 86, 200];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum CharClass {
    Sorceress,
    Paladin,
}

impl CharClass {
    pub(crate) const SORCERESS_ID: u8 = 1;
    pub(crate) const PALADIN_ID: u8 = 3;

    pub(crate) fn from_id(id: u8) -> Result<Self, String> {
        match id {
            Self::SORCERESS_ID => Ok(Self::Sorceress),
            Self::PALADIN_ID => Ok(Self::Paladin),
            _ => Err(format!(
                "unsupported char_class {id}; expected {} (Sorceress) or {} (Paladin)",
                Self::SORCERESS_ID,
                Self::PALADIN_ID,
            )),
        }
    }

    pub(crate) fn from_id_or_default(id: u8) -> Self {
        Self::from_id(id).unwrap_or(Self::Sorceress)
    }

    pub(crate) fn life_per_vit(self, vit: i32) -> i32 {
        match self {
            Self::Sorceress => vit * 2,
            Self::Paladin => vit * 3,
        }
    }

    pub(crate) fn mana_per_ene(self, ene: i32) -> i32 {
        match self {
            Self::Sorceress => ene * 2,
            Self::Paladin => (ene * 3) / 2,
        }
    }

    pub(crate) fn fcr_bps(self) -> &'static [i32] {
        match self {
            Self::Sorceress => SORCERESS_FCR_BPS,
            Self::Paladin => PALADIN_FCR_BPS,
        }
    }

    pub(crate) fn fhr_bps(self) -> &'static [i32] {
        match self {
            Self::Sorceress => SORCERESS_FHR_BPS,
            Self::Paladin => PALADIN_FHR_BPS,
        }
    }

    pub(crate) fn has_blizzard_calc(self) -> bool {
        matches!(self, Self::Sorceress)
    }

    pub(crate) fn forces_cold_sunder(self) -> bool {
        matches!(self, Self::Sorceress)
    }

    pub(crate) fn excludes_light_skill_charms(self) -> bool {
        matches!(self, Self::Sorceress)
    }
}

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

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum OffenseProfile {
    Caster,
    Melee,
    Zeal,
    Smite,
}

impl OffenseProfile {
    pub(crate) fn parse(s: &str, class: CharClass) -> Result<Self, String> {
        let profile = match s.to_ascii_lowercase().as_str() {
            "caster" => Self::Caster,
            "melee" => Self::Melee,
            "zeal" => Self::Zeal,
            "smite" => Self::Smite,
            other => {
                return Err(format!(
                    "invalid offense profile '{other}'; expected 'caster', 'melee', 'zeal', or 'smite'"
                ))
            }
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
        matches!(self, Self::Melee | Self::Zeal)
    }

    pub(crate) fn uses_dps_tables(self, c: &BuildConstraints) -> bool {
        self.is_melee_dps() && !c.action_hits.is_empty()
    }

    pub(crate) fn uses_caster_dps(self, c: &BuildConstraints) -> bool {
        self == Self::Caster && !c.blizz_dmg.is_empty()
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
        if c.blizz_dmg.is_empty() {
            return 0.0;
        }
        let targets = c.targets.max(1) as f64;
        let cold_mult = 1.0 + s.cold_dmg_pct.max(0) as f64 / 100.0;
        let eff_blizz = (s.all_skills + s.sorc_skills + s.blizz_skills).max(0) as usize;
        let blizz_per_cast =
            c.blizz_dmg[eff_blizz.min(c.blizz_dmg.len() - 1)] * cold_mult * 3.0 * targets;

        let (cast_f, action_f) = Self::sorc_cast_and_action_frames(s.fcr);
        let cd_ready = action_f + 45;

        if c.filler_dmg.is_empty() {
            return blizz_per_cast * (25.0 / cd_ready as f64);
        }

        let eff_filler = (s.all_skills + s.sorc_skills + s.action_skill_bonus).max(0) as usize;
        let filler_mult = if c.filler_is_aoe { targets } else { 1.0 };
        let filler_per_cast =
            c.filler_dmg[eff_filler.min(c.filler_dmg.len() - 1)] * cold_mult * filler_mult;

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

    fn ias_bp_for_min_speed(min_speed: i32, wsm: i32) -> i32 {
        let min_net_eias = ((100 * min_speed + 255) / 256 - 100).max(-85);
        let min_eias = (min_net_eias + wsm).max(0);
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
        (Self::ias_bp_for_min_speed(min_speed, wsm), frames)
    }

    /// Return `(hits_per_sec, ias_bp, display_frames, last_frames, used_zeal)` using exact D2R rollback frames.
    pub(crate) fn attack_rate_and_frames(
        self,
        hand: HandWeapon,
        ias: i32,
        zeal_hits: i32,
    ) -> (f64, i32, i32, i32, bool) {
        let clamped_ias = ias.max(0);
        let eias = (120 * clamped_ias) / (120 + clamped_ias);
        let net_eias = (eias - hand.wsm).clamp(-85, 75);
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
                Self::ias_bp_for_min_speed(ms_rollback.max(ms_last), hand.wsm),
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
                Self::ias_bp_for_min_speed(ms, hand.wsm),
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

    /// Compute exact single-target DPS for `Zeal`/`Melee` with precomputed skill tables.
    ///
    /// Expects `s.str_bonus` and `s.dex_bonus` to be total character strength/dexterity
    /// (`c.base_str + gear + charms`), matching `ub_ch` in `search.rs`.
    pub(crate) fn compute_dps(
        self,
        hand: HandWeapon,
        s: Stats,
        c: &BuildConstraints,
    ) -> (f64, i32, i32, i32, bool) {
        let eff_action = (s.all_skills + s.pal_skills + s.action_skill_bonus).max(0) as usize;
        let eff_aura = (s.all_skills + s.pal_skills + s.aura_skill_bonus).max(0) as usize;

        let hits = if c.action_hits.is_empty() {
            1
        } else {
            c.action_hits[eff_action.min(c.action_hits.len() - 1)].max(1)
        };
        let (rate, ias_bp, display_frames, last_frames, used_zeal) =
            self.attack_rate_and_frames(hand, s.ias, hits);

        let action_ed = if used_zeal && !c.action_ed.is_empty() {
            c.action_ed[eff_action.min(c.action_ed.len() - 1)]
        } else {
            0
        };

        let total_str = s.str_bonus.max(0);
        let total_dex = s.dex_bonus.max(0);
        let stat_ed = (total_str * hand.str_pct + total_dex * hand.dex_pct) / 100;

        let phys_avg = (hand.phys_2x + s.flat_phys_2x).max(0) as f64 / 2.0;
        let d_phys = phys_avg * (1.0 + (stat_ed + action_ed + s.off_ed).max(0) as f64 / 100.0);

        let d_aura_hit = if c.aura_hit_dmg.is_empty() {
            0.0
        } else {
            c.aura_hit_dmg[eff_aura.min(c.aura_hit_dmg.len() - 1)]
        };
        let d_aura_pulse = if c.aura_pulse_dps.is_empty() {
            0.0
        } else {
            c.aura_pulse_dps[eff_aura.min(c.aura_pulse_dps.len() - 1)]
        };
        let d_elem_gear = s.flat_elem_2x.max(0) as f64 / 2.0;
        let targets = c.targets.max(1) as f64;
        let aura_hit_mult = if hand.splash_fire && c.aura_is_fire {
            targets
        } else {
            1.0
        };
        let d_splash_fire = if hand.splash_fire {
            (hand.splash_fire_2x.max(0) as f64 / 2.0) * targets
        } else {
            0.0
        };

        let dps = (d_phys + d_aura_hit * aura_hit_mult + d_splash_fire + d_elem_gear) * rate
            + d_aura_pulse * targets;
        (dps, ias_bp, display_frames, last_frames, used_zeal)
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

#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum SearchMode {
    Power,
    Mf,
    MaxRes,
    Leveling,
    LevelingRes,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub(crate) struct Stats {
    pub(crate) all_skills: i32,
    pub(crate) sorc_skills: i32,
    pub(crate) pal_skills: i32,
    pub(crate) blizz_skills: i32,
    pub(crate) cm_skills: i32,
    pub(crate) primary_skill: i32,
    pub(crate) action_skill_bonus: i32,
    pub(crate) aura_skill_bonus: i32,
    pub(crate) off_ed: i32,
    pub(crate) flat_phys_2x: i32,
    pub(crate) flat_elem_2x: i32,
    pub(crate) cold_dmg_pct: i32,
    pub(crate) fcr: i32,
    pub(crate) fhr: i32,
    pub(crate) frw: i32,
    pub(crate) ias: i32,
    pub(crate) cb: i32,
    pub(crate) cbf: i32,
    pub(crate) pdr_pct: i32,
    pub(crate) life_leech: i32,
    pub(crate) fr: i32,
    pub(crate) lr: i32,
    pub(crate) cr: i32,
    pub(crate) pr: i32,
    pub(crate) max_fr: i32,
    pub(crate) max_lr: i32,
    pub(crate) max_cr: i32,
    pub(crate) max_pr: i32,
    pub(crate) mf: i32,
    pub(crate) life: i32,
    pub(crate) mana: i32,
    pub(crate) life_per_lvl: i32,
    pub(crate) mana_per_lvl: i32,
    pub(crate) vit: i32,
    pub(crate) ene: i32,
    pub(crate) pct_mana: i32,
    pub(crate) mdr: i32,
    pub(crate) dr_flat: i32,
    pub(crate) fire_abs_pct: i32,
    pub(crate) str_bonus: i32,
    pub(crate) dex_bonus: i32,
    pub(crate) defense: i32,
    pub(crate) belt_slots: i32,
}

impl Stats {
    pub(crate) fn total_skills(self) -> i32 {
        self.all_skills + self.sorc_skills + self.pal_skills
    }

    pub(crate) fn primary_power_skills(self) -> i32 {
        self.total_skills() + self.blizz_skills + self.primary_skill
    }

    pub(crate) fn primary_power_skills_for(self, offense: OffenseProfile, has_aura: bool) -> i32 {
        if offense.is_melee_dps()
            && (has_aura || self.action_skill_bonus != 0 || self.aura_skill_bonus != 0)
        {
            let bonus = if has_aura {
                self.aura_skill_bonus
            } else {
                self.action_skill_bonus.max(self.aura_skill_bonus)
            };
            self.total_skills() + self.blizz_skills + self.primary_skill + bonus
        } else {
            self.primary_power_skills()
        }
    }

    pub(crate) fn res_sum(self) -> i32 {
        self.fr + self.lr + self.cr + self.pr
    }

    pub(crate) fn max_res_sum(self) -> i32 {
        self.max_fr + self.max_lr + self.max_cr + self.max_pr
    }

    pub(crate) fn for_offense(mut self, offense: OffenseProfile, min_fcr: i32) -> Self {
        if !offense.uses_fcr() && min_fcr <= 0 {
            self.fcr = 0;
        }
        if !offense.is_melee_dps() {
            self.aura_skill_bonus = 0;
            self.off_ed = 0;
            self.flat_phys_2x = 0;
            self.flat_elem_2x = 0;
        }
        if !offense.uses_fcr() {
            self.cold_dmg_pct = 0;
        }
        self
    }

    pub(crate) fn add(self, o: Stats) -> Stats {
        Stats {
            all_skills: self.all_skills + o.all_skills,
            sorc_skills: self.sorc_skills + o.sorc_skills,
            pal_skills: self.pal_skills + o.pal_skills,
            blizz_skills: self.blizz_skills + o.blizz_skills,
            cm_skills: self.cm_skills + o.cm_skills,
            primary_skill: self.primary_skill + o.primary_skill,
            action_skill_bonus: self.action_skill_bonus + o.action_skill_bonus,
            aura_skill_bonus: self.aura_skill_bonus + o.aura_skill_bonus,
            off_ed: self.off_ed + o.off_ed,
            flat_phys_2x: self.flat_phys_2x + o.flat_phys_2x,
            flat_elem_2x: self.flat_elem_2x + o.flat_elem_2x,
            cold_dmg_pct: self.cold_dmg_pct + o.cold_dmg_pct,
            fcr: self.fcr + o.fcr,
            fhr: self.fhr + o.fhr,
            frw: self.frw + o.frw,
            ias: self.ias + o.ias,
            cb: self.cb + o.cb,
            cbf: self.cbf + o.cbf,
            pdr_pct: self.pdr_pct + o.pdr_pct,
            life_leech: self.life_leech + o.life_leech,
            fr: self.fr + o.fr,
            lr: self.lr + o.lr,
            cr: self.cr + o.cr,
            pr: self.pr + o.pr,
            max_fr: self.max_fr + o.max_fr,
            max_lr: self.max_lr + o.max_lr,
            max_cr: self.max_cr + o.max_cr,
            max_pr: self.max_pr + o.max_pr,
            mf: self.mf + o.mf,
            life: self.life + o.life,
            mana: self.mana + o.mana,
            life_per_lvl: self.life_per_lvl + o.life_per_lvl,
            mana_per_lvl: self.mana_per_lvl + o.mana_per_lvl,
            vit: self.vit + o.vit,
            ene: self.ene + o.ene,
            pct_mana: self.pct_mana + o.pct_mana,
            mdr: self.mdr + o.mdr,
            dr_flat: self.dr_flat + o.dr_flat,
            fire_abs_pct: self.fire_abs_pct + o.fire_abs_pct,
            str_bonus: self.str_bonus + o.str_bonus,
            dex_bonus: self.dex_bonus + o.dex_bonus,
            defense: self.defense + o.defense,
            belt_slots: self.belt_slots + o.belt_slots,
        }
    }

    pub(crate) fn max_each(self, o: Stats) -> Stats {
        Stats {
            all_skills: self.all_skills.max(o.all_skills),
            sorc_skills: self.sorc_skills.max(o.sorc_skills),
            pal_skills: self.pal_skills.max(o.pal_skills),
            blizz_skills: self.blizz_skills.max(o.blizz_skills),
            cm_skills: self.cm_skills.max(o.cm_skills),
            primary_skill: self.primary_skill.max(o.primary_skill),
            action_skill_bonus: self.action_skill_bonus.max(o.action_skill_bonus),
            aura_skill_bonus: self.aura_skill_bonus.max(o.aura_skill_bonus),
            off_ed: self.off_ed.max(o.off_ed),
            flat_phys_2x: self.flat_phys_2x.max(o.flat_phys_2x),
            flat_elem_2x: self.flat_elem_2x.max(o.flat_elem_2x),
            cold_dmg_pct: self.cold_dmg_pct.max(o.cold_dmg_pct),
            fcr: self.fcr.max(o.fcr),
            fhr: self.fhr.max(o.fhr),
            frw: self.frw.max(o.frw),
            ias: self.ias.max(o.ias),
            cb: self.cb.max(o.cb),
            cbf: self.cbf.max(o.cbf),
            pdr_pct: self.pdr_pct.max(o.pdr_pct),
            life_leech: self.life_leech.max(o.life_leech),
            fr: self.fr.max(o.fr),
            lr: self.lr.max(o.lr),
            cr: self.cr.max(o.cr),
            pr: self.pr.max(o.pr),
            max_fr: self.max_fr.max(o.max_fr),
            max_lr: self.max_lr.max(o.max_lr),
            max_cr: self.max_cr.max(o.max_cr),
            max_pr: self.max_pr.max(o.max_pr),
            mf: self.mf.max(o.mf),
            life: self.life.max(o.life),
            mana: self.mana.max(o.mana),
            life_per_lvl: self.life_per_lvl.max(o.life_per_lvl),
            mana_per_lvl: self.mana_per_lvl.max(o.mana_per_lvl),
            vit: self.vit.max(o.vit),
            ene: self.ene.max(o.ene),
            pct_mana: self.pct_mana.max(o.pct_mana),
            mdr: self.mdr.max(o.mdr),
            dr_flat: self.dr_flat.max(o.dr_flat),
            fire_abs_pct: self.fire_abs_pct.max(o.fire_abs_pct),
            str_bonus: self.str_bonus.max(o.str_bonus),
            dex_bonus: self.dex_bonus.max(o.dex_bonus),
            defense: self.defense.max(o.defense),
            belt_slots: self.belt_slots.max(o.belt_slots),
        }
    }

    pub(crate) fn dominates(self, o: Stats) -> bool {
        self.all_skills >= o.all_skills
            && self.sorc_skills >= o.sorc_skills
            && self.pal_skills >= o.pal_skills
            && self.blizz_skills >= o.blizz_skills
            && self.cm_skills >= o.cm_skills
            && self.primary_skill >= o.primary_skill
            && self.action_skill_bonus >= o.action_skill_bonus
            && self.aura_skill_bonus >= o.aura_skill_bonus
            && self.off_ed >= o.off_ed
            && self.flat_phys_2x >= o.flat_phys_2x
            && self.flat_elem_2x >= o.flat_elem_2x
            && self.cold_dmg_pct >= o.cold_dmg_pct
            && self.fcr >= o.fcr
            && self.fhr >= o.fhr
            && self.frw >= o.frw
            && self.ias >= o.ias
            && self.cb >= o.cb
            && self.cbf >= o.cbf
            && self.pdr_pct >= o.pdr_pct
            && self.life_leech >= o.life_leech
            && self.fr >= o.fr
            && self.lr >= o.lr
            && self.cr >= o.cr
            && self.pr >= o.pr
            && self.max_fr >= o.max_fr
            && self.max_lr >= o.max_lr
            && self.max_cr >= o.max_cr
            && self.max_pr >= o.max_pr
            && self.mf >= o.mf
            && self.life >= o.life
            && self.mana >= o.mana
            && self.life_per_lvl >= o.life_per_lvl
            && self.mana_per_lvl >= o.mana_per_lvl
            && self.vit >= o.vit
            && self.ene >= o.ene
            && self.pct_mana >= o.pct_mana
            && self.mdr >= o.mdr
            && self.dr_flat >= o.dr_flat
            && self.fire_abs_pct >= o.fire_abs_pct
            && self.str_bonus >= o.str_bonus
            && self.dex_bonus >= o.dex_bonus
            && self.defense >= o.defense
            && self.belt_slots >= o.belt_slots
    }
}

/// Item specification passed between Python (`d2savior`) and Rust.
#[cfg_attr(feature = "python", pyclass(get_all, set_all))]
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ItemSpec {
    pub name: String,
    pub slot: String,
    pub loc: String,
    pub all_skills: i32,
    pub sorc_skills: i32,
    pub pal_skills: i32,
    pub blizz_skills: i32,
    pub cm_skills: i32,
    pub primary_skill: i32,
    pub action_skill_bonus: i32,
    pub aura_skill_bonus: i32,
    pub off_ed: i32,
    pub flat_phys_2x: i32,
    pub flat_elem_2x: i32,
    pub cold_dmg_pct: i32,
    pub fcr: i32,
    pub fhr: i32,
    pub frw: i32,
    pub ias: i32,
    pub cb: i32,
    pub cbf: i32,
    pub pdr_pct: i32,
    pub life_leech: i32,
    pub fr: i32,
    pub lr: i32,
    pub cr: i32,
    pub pr: i32,
    pub mf: i32,
    pub life: i32,
    pub life_per_lvl: i32,
    pub mana: i32,
    pub mana_per_lvl: i32,
    pub vit: i32,
    pub ene: i32,
    pub pct_mana: i32,
    pub mdr: i32,
    pub dr_flat: i32,
    pub fire_abs_pct: i32,
    pub str_bonus: i32,
    pub dex_bonus: i32,
    pub req_str: i32,
    pub req_dex: i32,
    pub max_fr: i32,
    pub max_lr: i32,
    pub max_cr: i32,
    pub max_pr: i32,
    pub defense: i32,
    pub belt_slots: i32,
    pub set_group: i32,
    pub set_item_id: i32,
    pub set_bonuses: Vec<(i32, ItemSpec)>,
    pub wsm: i32,
    pub wclass: String,
    pub wep_phys_2x: i32,
    pub wep_str_pct: i32,
    pub wep_dex_pct: i32,
    pub can_zeal: bool,
    pub splash_fire: bool,
    pub splash_fire_2x: i32,
}

pub(crate) type SetBonusSig = Vec<(i32, Stats)>;

pub(crate) fn equipped_hand_weapon(items: &[&ItemSpec]) -> HandWeapon {
    for &it in items {
        if matches!(it.slot.as_str(), "weapon" | "weapon2h") && it.name != "(empty)" {
            return it.hand_weapon();
        }
    }
    HandWeapon::empty()
}

pub(crate) fn eff_req(req: i32, self_bonus: i32) -> i32 {
    if req > 0 {
        req + self_bonus
    } else {
        0
    }
}

pub(crate) fn compute_effective_gear_stats_and_reqs(items: &[&ItemSpec]) -> (Stats, i32, (i32, i32)) {
    if items.iter().all(|it| it.set_group == 0) {
        let mut gear = Stats::default();
        let mut all_sk_non_wep = 0;
        let mut req_str = 0;
        let mut req_dex = 0;
        for &it in items {
            gear = gear.add(it.stats());
            if !it.is_weapon_or_shield() {
                all_sk_non_wep += it.all_skills;
            }
            req_str = req_str.max(eff_req(it.req_str, it.str_bonus));
            req_dex = req_dex.max(eff_req(it.req_dex, it.dex_bonus));
        }
        return (gear, all_sk_non_wep, (req_str, req_dex));
    }

    let mut counts: Vec<(i32, i32)> = Vec::new();
    let mut seen: Vec<(i32, i32)> = Vec::with_capacity(items.len());
    for (idx, &it) in items.iter().enumerate() {
        if it.set_group == 0 {
            continue;
        }
        let eid = if it.set_item_id != 0 {
            it.set_item_id
        } else {
            -(idx as i32 + 1)
        };
        if !seen.contains(&(it.set_group, eid)) {
            seen.push((it.set_group, eid));
            if let Some(entry) = counts.iter_mut().find(|(g, _)| *g == it.set_group) {
                entry.1 += 1;
            } else {
                counts.push((it.set_group, 1));
            }
        }
    }

    let mut gear = Stats::default();
    let mut all_sk_non_wep = 0;
    let mut req_str = 0;
    let mut req_dex = 0;
    for &it in items {
        let bonus = if it.set_group != 0 && !it.set_bonuses.is_empty() {
            let cnt = counts
                .iter()
                .find(|(g, _)| *g == it.set_group)
                .map_or(0, |(_, c)| *c);
            it.active_set_bonus_stats(cnt)
        } else {
            Stats::default()
        };
        let eff = it.stats().add(bonus);
        gear = gear.add(eff);
        if !it.is_weapon_or_shield() {
            all_sk_non_wep += eff.all_skills;
        }
        req_str = req_str.max(eff_req(it.req_str, it.str_bonus + bonus.str_bonus));
        req_dex = req_dex.max(eff_req(it.req_dex, it.dex_bonus + bonus.dex_bonus));
    }
    (gear, all_sk_non_wep, (req_str, req_dex))
}

pub(crate) fn compute_effective_gear_stats(items: &[&ItemSpec]) -> (Stats, i32) {
    let (gear, all_sk_non_wep, _) = compute_effective_gear_stats_and_reqs(items);
    (gear, all_sk_non_wep)
}

impl ItemSpec {
    pub fn total_skills(&self) -> i32 {
        self.all_skills + self.sorc_skills + self.pal_skills
    }

    pub(crate) fn weapon_class(&self) -> WeaponClass {
        WeaponClass::from_item(&self.wclass, &self.slot, &self.name)
    }

    pub(crate) fn hand_weapon(&self) -> HandWeapon {
        if self.name == "(empty)" {
            return HandWeapon::empty();
        }
        let wclass = self.weapon_class();
        let can_zeal = self.can_zeal
            || (!wclass.is_ranged()
                && self.wep_phys_2x == 0
                && self.wep_str_pct == 0
                && self.wep_dex_pct == 0);
        HandWeapon {
            wclass,
            wsm: self.wsm,
            phys_2x: self.wep_phys_2x,
            str_pct: self.wep_str_pct,
            dex_pct: self.wep_dex_pct,
            can_zeal,
            splash_fire: self.splash_fire,
            splash_fire_2x: self.splash_fire_2x,
        }
    }

    pub(crate) fn is_weapon_or_shield(&self) -> bool {
        matches!(self.slot.as_str(), "weapon" | "weapon2h" | "shield")
    }

    pub(crate) fn empty(slot: &str) -> Self {
        Self {
            name: "(empty)".to_string(),
            slot: slot.to_string(),
            ..Default::default()
        }
    }

    pub(crate) fn active_set_bonus_stats(&self, piece_count: i32) -> Stats {
        self.set_bonuses
            .iter()
            .filter(|(req, _)| piece_count >= *req)
            .fold(Stats::default(), |acc, (_, b)| acc.add(b.stats()))
    }

    pub(crate) fn max_possible_set_bonus_stats(&self) -> Stats {
        self.set_bonuses
            .iter()
            .fold(Stats::default(), |acc, (_, b)| {
                acc.add(b.stats().max_each(Stats::default()))
            })
    }

    pub(crate) fn max_total_stats(&self) -> Stats {
        self.stats().add(self.max_possible_set_bonus_stats())
    }

    pub(crate) fn set_bonus_sig(&self) -> SetBonusSig {
        self.set_bonuses
            .iter()
            .map(|(req, b)| (*req, b.stats()))
            .collect()
    }

    pub(crate) fn stats(&self) -> Stats {
        Stats {
            all_skills: self.all_skills,
            sorc_skills: self.sorc_skills,
            pal_skills: self.pal_skills,
            blizz_skills: self.blizz_skills,
            cm_skills: self.cm_skills,
            primary_skill: self.primary_skill,
            action_skill_bonus: self.action_skill_bonus,
            aura_skill_bonus: self.aura_skill_bonus,
            off_ed: self.off_ed,
            flat_phys_2x: self.flat_phys_2x,
            flat_elem_2x: self.flat_elem_2x,
            cold_dmg_pct: self.cold_dmg_pct,
            fcr: self.fcr,
            fhr: self.fhr,
            frw: self.frw,
            ias: self.ias,
            cb: self.cb,
            cbf: self.cbf,
            pdr_pct: self.pdr_pct,
            life_leech: self.life_leech,
            fr: self.fr,
            lr: self.lr,
            cr: self.cr,
            pr: self.pr,
            max_fr: self.max_fr,
            max_lr: self.max_lr,
            max_cr: self.max_cr,
            max_pr: self.max_pr,
            mf: self.mf,
            life: self.life,
            mana: self.mana,
            life_per_lvl: self.life_per_lvl,
            mana_per_lvl: self.mana_per_lvl,
            vit: self.vit,
            ene: self.ene,
            pct_mana: self.pct_mana,
            mdr: self.mdr,
            dr_flat: self.dr_flat,
            fire_abs_pct: self.fire_abs_pct,
            str_bonus: self.str_bonus,
            dex_bonus: self.dex_bonus,
            defense: self.defense,
            belt_slots: self.belt_slots,
        }
    }

    pub(crate) fn from_stats(
        name: String,
        slot: String,
        loc: String,
        s: Stats,
        req_str: i32,
        req_dex: i32,
    ) -> Self {
        Self {
            name,
            slot,
            loc,
            all_skills: s.all_skills,
            sorc_skills: s.sorc_skills,
            pal_skills: s.pal_skills,
            blizz_skills: s.blizz_skills,
            cm_skills: s.cm_skills,
            primary_skill: s.primary_skill,
            action_skill_bonus: s.action_skill_bonus,
            aura_skill_bonus: s.aura_skill_bonus,
            off_ed: s.off_ed,
            flat_phys_2x: s.flat_phys_2x,
            flat_elem_2x: s.flat_elem_2x,
            cold_dmg_pct: s.cold_dmg_pct,
            fcr: s.fcr,
            fhr: s.fhr,
            frw: s.frw,
            ias: s.ias,
            cb: s.cb,
            cbf: s.cbf,
            pdr_pct: s.pdr_pct,
            life_leech: s.life_leech,
            fr: s.fr,
            lr: s.lr,
            cr: s.cr,
            pr: s.pr,
            mf: s.mf,
            life: s.life,
            life_per_lvl: s.life_per_lvl,
            mana: s.mana,
            mana_per_lvl: s.mana_per_lvl,
            vit: s.vit,
            ene: s.ene,
            pct_mana: s.pct_mana,
            mdr: s.mdr,
            dr_flat: s.dr_flat,
            fire_abs_pct: s.fire_abs_pct,
            str_bonus: s.str_bonus,
            dex_bonus: s.dex_bonus,
            req_str,
            req_dex,
            max_fr: s.max_fr,
            max_lr: s.max_lr,
            max_cr: s.max_cr,
            max_pr: s.max_pr,
            defense: s.defense,
            belt_slots: s.belt_slots,
            set_group: 0,
            set_item_id: 0,
            set_bonuses: Vec::new(),
            wsm: 0,
            wclass: String::new(),
            wep_phys_2x: 0,
            wep_str_pct: 0,
            wep_dex_pct: 0,
            can_zeal: false,
            splash_fire: false,
            splash_fire_2x: 0,
        }
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl ItemSpec {
    #[new]
    #[pyo3(signature = (
        name,
        slot,
        loc = String::new(),
        all_skills = 0,
        sorc_skills = 0,
        fcr = 0,
        fhr = 0,
        frw = 0,
        fr = 0,
        lr = 0,
        cr = 0,
        pr = 0,
        mf = 0,
        life = 0,
        mana = 0,
        vit = 0,
        ene = 0,
        pct_mana = 0,
        mdr = 0,
        dr_flat = 0,
        fire_abs_pct = 0,
        str_bonus = 0,
        dex_bonus = 0,
        req_str = 0,
        req_dex = 0,
        max_fr = 0,
        max_lr = 0,
        max_cr = 0,
        max_pr = 0,
        life_per_lvl = 0,
        mana_per_lvl = 0,
        blizz_skills = 0,
        cm_skills = 0,
        defense = 0,
        belt_slots = 0,
        pal_skills = 0,
        primary_skill = 0,
        ias = 0,
        cb = 0,
        cbf = 0,
        pdr_pct = 0,
        life_leech = 0,
        set_group = 0,
        set_item_id = 0,
        set_bonuses = Vec::new(),
        wsm = 0,
        wclass = String::new(),
        action_skill_bonus = 0,
        aura_skill_bonus = 0,
        off_ed = 0,
        flat_phys_2x = 0,
        flat_elem_2x = 0,
        wep_phys_2x = 0,
        wep_str_pct = 0,
        wep_dex_pct = 0,
        can_zeal = false,
        splash_fire = false,
        splash_fire_2x = 0,
        cold_dmg_pct = 0,
    ))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        name: String,
        slot: String,
        loc: String,
        all_skills: i32,
        sorc_skills: i32,
        fcr: i32,
        fhr: i32,
        frw: i32,
        fr: i32,
        lr: i32,
        cr: i32,
        pr: i32,
        mf: i32,
        life: i32,
        mana: i32,
        vit: i32,
        ene: i32,
        pct_mana: i32,
        mdr: i32,
        dr_flat: i32,
        fire_abs_pct: i32,
        str_bonus: i32,
        dex_bonus: i32,
        req_str: i32,
        req_dex: i32,
        max_fr: i32,
        max_lr: i32,
        max_cr: i32,
        max_pr: i32,
        life_per_lvl: i32,
        mana_per_lvl: i32,
        blizz_skills: i32,
        cm_skills: i32,
        defense: i32,
        belt_slots: i32,
        pal_skills: i32,
        primary_skill: i32,
        ias: i32,
        cb: i32,
        cbf: i32,
        pdr_pct: i32,
        life_leech: i32,
        set_group: i32,
        set_item_id: i32,
        set_bonuses: Vec<(i32, ItemSpec)>,
        wsm: i32,
        wclass: String,
        action_skill_bonus: i32,
        aura_skill_bonus: i32,
        off_ed: i32,
        flat_phys_2x: i32,
        flat_elem_2x: i32,
        wep_phys_2x: i32,
        wep_str_pct: i32,
        wep_dex_pct: i32,
        can_zeal: bool,
        splash_fire: bool,
        splash_fire_2x: i32,
        cold_dmg_pct: i32,
    ) -> Self {
        Self {
            name,
            slot,
            loc,
            all_skills,
            sorc_skills,
            pal_skills,
            blizz_skills,
            cm_skills,
            primary_skill,
            action_skill_bonus,
            aura_skill_bonus,
            off_ed,
            flat_phys_2x,
            flat_elem_2x,
            cold_dmg_pct,
            fcr,
            fhr,
            frw,
            ias,
            cb,
            cbf,
            pdr_pct,
            life_leech,
            fr,
            lr,
            cr,
            pr,
            mf,
            life,
            life_per_lvl,
            mana,
            mana_per_lvl,
            vit,
            ene,
            pct_mana,
            mdr,
            dr_flat,
            fire_abs_pct,
            str_bonus,
            dex_bonus,
            req_str,
            req_dex,
            max_fr,
            max_lr,
            max_cr,
            max_pr,
            defense,
            belt_slots,
            set_group,
            set_item_id,
            set_bonuses,
            wsm,
            wclass,
            wep_phys_2x,
            wep_str_pct,
            wep_dex_pct,
            can_zeal,
            splash_fire,
            splash_fire_2x,
        }
    }

    #[getter]
    pub fn skills(&self) -> i32 {
        self.total_skills()
    }

    fn __repr__(&self) -> String {
        format!(
            "ItemSpec(name={:?}, slot={:?}, skills={}, fcr={}, fhr={}, mf={})",
            self.name,
            self.slot,
            self.total_skills(),
            self.fcr,
            self.fhr,
            self.mf
        )
    }
}

/// Charm specification passed between Python (`d2savior`) and Rust.
#[cfg_attr(feature = "python", pyclass(get_all, set_all))]
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct CharmSpec {
    pub name: String,
    pub size: i32,
    pub loc: String,
    pub fhr: i32,
    pub fr: i32,
    pub lr: i32,
    pub cr: i32,
    pub pr: i32,
    pub mf: i32,
    pub life: i32,
    pub mana: i32,
    pub frw: i32,
    pub light_skills: i32,
    pub str_bonus: i32,
    pub dex_bonus: i32,
    pub skills: i32,
    pub action_skills: i32,
    pub aura_skills: i32,
    pub unique_id: Option<i32>,
    pub cold_sunder: bool,
}

impl CharmSpec {
    pub(crate) fn skills_total(&self) -> i32 {
        self.skills + self.action_skills + self.aura_skills
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl CharmSpec {
    #[new]
    #[pyo3(signature = (
        name,
        size,
        loc = String::new(),
        fhr = 0,
        fr = 0,
        lr = 0,
        cr = 0,
        pr = 0,
        mf = 0,
        life = 0,
        mana = 0,
        frw = 0,
        light_skills = 0,
        str_bonus = 0,
        dex_bonus = 0,
        skills = 0,
        unique_id = None,
        cold_sunder = false,
        action_skills = 0,
        aura_skills = 0,
    ))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        name: String,
        size: i32,
        loc: String,
        fhr: i32,
        fr: i32,
        lr: i32,
        cr: i32,
        pr: i32,
        mf: i32,
        life: i32,
        mana: i32,
        frw: i32,
        light_skills: i32,
        str_bonus: i32,
        dex_bonus: i32,
        skills: i32,
        unique_id: Option<i32>,
        cold_sunder: bool,
        action_skills: i32,
        aura_skills: i32,
    ) -> Self {
        Self {
            name,
            size,
            loc,
            fhr,
            fr,
            lr,
            cr,
            pr,
            mf,
            life,
            mana,
            frw,
            light_skills,
            str_bonus,
            dex_bonus,
            skills,
            action_skills,
            aura_skills,
            unique_id,
            cold_sunder,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "CharmSpec(name={:?}, size={}, skills={}, fhr={}, mf={}, life={})",
            self.name, self.size, self.skills, self.fhr, self.mf, self.life
        )
    }
}

/// Search constraints and character baseline stats.
#[cfg_attr(feature = "python", pyclass(get_all, set_all))]
#[derive(Clone, Debug)]
pub struct BuildConstraints {
    pub allow_mf: bool,
    pub min_fcr: i32,
    pub min_fhr: i32,
    pub min_fr: i32,
    pub min_lr: i32,
    pub min_cr: i32,
    pub min_pr: i32,
    pub max_charm_slots: i32,
    pub mode: String,
    pub base_life: i32,
    pub base_mana: i32,
    pub base_hell_res: i32,
    pub base_str: i32,
    pub base_dex: i32,
    pub bo_base_bonus: i32,
    pub blizz_base_lvl: i32,
    pub blizz_syn_pts: i32,
    pub cm_base_lvl: i32,
    pub limit: usize,
    pub char_class: u8,
    pub base_max_fr: i32,
    pub base_max_lr: i32,
    pub base_max_cr: i32,
    pub base_max_pr: i32,
    pub use_bo: bool,
    pub fixed_gear: bool,
    pub offense: String,
    pub aura_hit_dmg: Vec<f64>,
    pub aura_pulse_dps: Vec<f64>,
    pub action_ed: Vec<i32>,
    pub action_hits: Vec<i32>,
    pub has_aura: bool,
    pub aura_is_fire: bool,
    pub targets: i32,
    pub blizz_dmg: Vec<f64>,
    pub filler_dmg: Vec<f64>,
    pub filler_is_aoe: bool,
    pub require_cbf: bool,
    pub min_frw: i32,
    pub min_ias: i32,
    pub min_cb: i32,
    pub min_ll: i32,
    pub min_pdr: i32,
    pub min_mf: i32,
}

impl Default for BuildConstraints {
    fn default() -> Self {
        Self {
            allow_mf: true,
            min_fcr: 105,
            min_fhr: 86,
            min_fr: 75,
            min_lr: 75,
            min_cr: 75,
            min_pr: 0,
            max_charm_slots: 23,
            mode: String::from("power"),
            base_life: 0,
            base_mana: 0,
            base_hell_res: -100,
            base_str: 0,
            base_dex: 0,
            bo_base_bonus: 4,
            blizz_base_lvl: 20,
            blizz_syn_pts: 54,
            cm_base_lvl: 20,
            limit: 5,
            char_class: CharClass::SORCERESS_ID,
            base_max_fr: 0,
            base_max_lr: 0,
            base_max_cr: 0,
            base_max_pr: 0,
            use_bo: true,
            fixed_gear: false,
            offense: String::from("caster"),
            aura_hit_dmg: Vec::new(),
            aura_pulse_dps: Vec::new(),
            action_ed: Vec::new(),
            action_hits: Vec::new(),
            has_aura: false,
            aura_is_fire: false,
            targets: 1,
            blizz_dmg: Vec::new(),
            filler_dmg: Vec::new(),
            filler_is_aoe: false,
            require_cbf: false,
            min_frw: 0,
            min_ias: 0,
            min_cb: 0,
            min_ll: 0,
            min_pdr: 0,
            min_mf: 0,
        }
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl BuildConstraints {
    #[new]
    #[pyo3(signature = (
        allow_mf = true,
        min_fcr = 105,
        min_fhr = 86,
        min_fr = 75,
        min_lr = 75,
        min_cr = 75,
        min_pr = 0,
        max_charm_slots = 23,
        mode = String::from("power"),
        base_life = 0,
        base_mana = 0,
        base_hell_res = -100,
        base_str = 0,
        base_dex = 0,
        bo_base_bonus = 4,
        limit = 5,
        blizz_base_lvl = 20,
        blizz_syn_pts = 54,
        cm_base_lvl = 20,
        char_class = 1,
        base_max_fr = 0,
        base_max_lr = 0,
        base_max_cr = 0,
        base_max_pr = 0,
        use_bo = true,
        fixed_gear = false,
        offense = String::from("caster"),
        aura_hit_dmg = Vec::new(),
        aura_pulse_dps = Vec::new(),
        action_ed = Vec::new(),
        action_hits = Vec::new(),
        has_aura = false,
        aura_is_fire = false,
        targets = 1,
        blizz_dmg = Vec::new(),
        filler_dmg = Vec::new(),
        filler_is_aoe = false,
        require_cbf = false,
        min_frw = 0,
        min_ias = 0,
        min_cb = 0,
        min_ll = 0,
        min_pdr = 0,
        min_mf = 0,
    ))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        allow_mf: bool,
        min_fcr: i32,
        min_fhr: i32,
        min_fr: i32,
        min_lr: i32,
        min_cr: i32,
        min_pr: i32,
        max_charm_slots: i32,
        mode: String,
        base_life: i32,
        base_mana: i32,
        base_hell_res: i32,
        base_str: i32,
        base_dex: i32,
        bo_base_bonus: i32,
        limit: usize,
        blizz_base_lvl: i32,
        blizz_syn_pts: i32,
        cm_base_lvl: i32,
        char_class: u8,
        base_max_fr: i32,
        base_max_lr: i32,
        base_max_cr: i32,
        base_max_pr: i32,
        use_bo: bool,
        fixed_gear: bool,
        offense: String,
        aura_hit_dmg: Vec<f64>,
        aura_pulse_dps: Vec<f64>,
        action_ed: Vec<i32>,
        action_hits: Vec<i32>,
        has_aura: bool,
        aura_is_fire: bool,
        targets: i32,
        blizz_dmg: Vec<f64>,
        filler_dmg: Vec<f64>,
        filler_is_aoe: bool,
        require_cbf: bool,
        min_frw: i32,
        min_ias: i32,
        min_cb: i32,
        min_ll: i32,
        min_pdr: i32,
        min_mf: i32,
    ) -> Self {
        Self {
            allow_mf,
            min_fcr,
            min_fhr,
            min_fr,
            min_lr,
            min_cr,
            min_pr,
            max_charm_slots,
            mode,
            base_life,
            base_mana,
            base_hell_res,
            base_str,
            base_dex,
            bo_base_bonus,
            blizz_base_lvl,
            blizz_syn_pts,
            cm_base_lvl,
            limit,
            char_class,
            base_max_fr,
            base_max_lr,
            base_max_cr,
            base_max_pr,
            use_bo,
            fixed_gear,
            offense,
            aura_hit_dmg,
            aura_pulse_dps,
            action_ed,
            action_hits,
            has_aura,
            aura_is_fire,
            targets,
            blizz_dmg,
            filler_dmg,
            filler_is_aoe,
            require_cbf,
            min_frw,
            min_ias,
            min_cb,
            min_ll,
            min_pdr,
            min_mf,
        }
    }
}

/// Evaluated loadout result returned to Python.
#[cfg_attr(feature = "python", pyclass(get_all))]
#[derive(Clone, Debug, PartialEq)]
pub struct BuildResult {
    pub skills: i32,
    pub primary_skill_bonus: i32,
    pub action_skill_bonus: i32,
    pub aura_skill_bonus: i32,
    pub dps: f64,
    pub used_zeal: bool,
    pub blizz_avg: f64,
    pub cm_pierce: i32,
    pub fcr: i32,
    pub fcr_bp: i32,
    pub fhr: i32,
    pub fhr_bp: i32,
    pub frw: i32,
    pub ias: i32,
    pub ias_bp: i32,
    pub ias_frames: i32,
    pub ias_last_frames: i32,
    pub cb: i32,
    pub cbf: bool,
    pub pdr_pct: i32,
    pub life_leech: i32,
    pub mf: i32,
    pub fr: i32,
    pub fr_raw: i32,
    pub max_fr: i32,
    pub lr: i32,
    pub lr_raw: i32,
    pub max_lr: i32,
    pub cr: i32,
    pub cr_raw: i32,
    pub max_cr: i32,
    pub pr: i32,
    pub pr_raw: i32,
    pub max_pr: i32,
    pub life_no_bo: i32,
    pub life_bo: i32,
    pub mana_bo: i32,
    pub bo_lvl: i32,
    pub charm_slots: i32,
    pub items: Vec<ItemSpec>,
    pub charms: Vec<CharmSpec>,
    pub evaluated_candidates: usize,
}

#[cfg(feature = "python")]
#[pymethods]
impl BuildResult {
    fn __repr__(&self) -> String {
        format!(
            "BuildResult(skills=+{}, fcr={}%(BP {}), fhr={}%(BP {}), mf={}%, res={}/{}/{}/{}, life_bo={})",
            self.skills,
            self.fcr,
            self.fcr_bp,
            self.fhr,
            self.fhr_bp,
            self.mf,
            self.fr,
            self.lr,
            self.cr,
            self.pr,
            self.life_bo
        )
    }
}

#[cfg(test)]
pub(crate) fn mk_test_item(
    name: &str,
    slot: &str,
    fcr: i32,
    fhr: i32,
    sk: i32,
    res: i32,
    mf: i32,
) -> ItemSpec {
    ItemSpec {
        name: name.to_string(),
        slot: slot.to_string(),
        loc: "test".to_string(),
        all_skills: sk,
        fcr,
        fhr,
        fr: res,
        lr: res,
        cr: res,
        pr: res,
        mf,
        ..Default::default()
    }
}

#[cfg(test)]
pub(crate) fn test_constraints() -> BuildConstraints {
    BuildConstraints {
        base_life: 806,
        base_mana: 211,
        base_hell_res: -70,
        base_str: 156,
        base_dex: 25,
        ..Default::default()
    }
}

#[cfg(test)]
#[path = "types_tests.rs"]
mod tests;
