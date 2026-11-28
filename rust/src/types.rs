#[cfg(feature = "python")]
use pyo3::prelude::*;

use crate::dps::{HandWeapon, OffenseProfile, WeaponClass};
use crate::stats::{with_stat_fields, SetBonusSig, Stats};

pub(crate) const BASE_MAX_RES: i32 = 75;
pub(crate) const HARD_MAX_RES: i32 = 95;
pub(crate) const HARD_MAX_PDR_PCT: i32 = 50;

pub(crate) const SORCERESS_FCR_BPS: &[i32] = &[0, 9, 20, 37, 63, 105, 200];
pub(crate) const SORCERESS_FHR_BPS: &[i32] = &[0, 5, 9, 14, 20, 30, 42, 60, 86, 142, 280];
pub(crate) const SORCERESS_FBR_BPS: &[i32] = &[0, 7, 15, 27, 48, 86, 200];
pub(crate) const SORCERESS_FBR_FRAMES: &[i32] = &[9, 8, 7, 6, 5, 4, 3];
pub(crate) const PALADIN_FCR_BPS: &[i32] = &[0, 9, 18, 30, 48, 75, 125];
pub(crate) const PALADIN_FHR_BPS: &[i32] = &[0, 7, 15, 27, 48, 86, 200];
pub(crate) const PALADIN_FBR_BPS: &[i32] = &[0, 13, 32, 86, 600];
pub(crate) const PALADIN_FBR_FRAMES: &[i32] = &[5, 4, 3, 2, 1];
pub(crate) const PALADIN_HS_FBR_BPS: &[i32] = &[0, 86];
pub(crate) const PALADIN_HS_FBR_FRAMES: &[i32] = &[2, 1];

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

    pub(crate) fn base_ar_from_dex(self, dex: i32) -> i32 {
        match self {
            Self::Sorceress => (5 * dex - 50).max(0),
            Self::Paladin => (5 * dex - 15).max(0),
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

    pub(crate) fn class_block_bonus(self) -> i32 {
        match self {
            Self::Sorceress => 20,
            Self::Paladin => 30,
        }
    }

    pub(crate) fn fbr_bp_and_frames(self, fbr: i32, holy_shield_active: bool) -> (i32, i32) {
        let (bps, frames) = match self {
            Self::Sorceress => (SORCERESS_FBR_BPS, SORCERESS_FBR_FRAMES),
            Self::Paladin if holy_shield_active => (PALADIN_HS_FBR_BPS, PALADIN_HS_FBR_FRAMES),
            Self::Paladin => (PALADIN_FBR_BPS, PALADIN_FBR_FRAMES),
        };
        let mut best = (bps[0], frames[0]);
        for (&bp, &fr) in bps.iter().zip(frames.iter()) {
            if fbr >= bp {
                best = (bp, fr);
            }
        }
        best
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

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) enum TargetType {
    Trash,
    #[default]
    Champion,
    Boss,
}

impl TargetType {
    pub(crate) fn parse(s: &str) -> Result<Self, String> {
        if s.eq_ignore_ascii_case("trash") {
            Ok(Self::Trash)
        } else if s.eq_ignore_ascii_case("champion") {
            Ok(Self::Champion)
        } else if s.eq_ignore_ascii_case("boss") {
            Ok(Self::Boss)
        } else {
            Err(format!(
                "invalid target_type '{s}'; expected 'trash', 'champion', or 'boss'"
            ))
        }
    }

    pub(crate) fn allows_itd(self) -> bool {
        matches!(self, Self::Trash)
    }

    pub(crate) fn gear_target_def_reduction(self, target_def_pct: i32) -> i32 {
        let clamped = target_def_pct.clamp(0, 100);
        if matches!(self, Self::Trash) {
            clamped
        } else {
            clamped / 2
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum SearchMode {
    Power,
    Mf,
    MaxRes,
    Leveling,
    LevelingRes,
}

impl SearchMode {
    pub(crate) fn parse(s: &str) -> Result<Self, String> {
        match s.to_ascii_lowercase().as_str() {
            "power" => Ok(Self::Power),
            "mf" => Ok(Self::Mf),
            "max-res" => Ok(Self::MaxRes),
            "leveling" => Ok(Self::Leveling),
            "leveling-res" => Ok(Self::LevelingRes),
            other => Err(format!(
                "invalid mode '{other}'; expected 'power', 'mf', 'max-res', 'leveling', or 'leveling-res'"
            )),
        }
    }
}

/// Validated `BuildConstraints` with enum fields parsed once at API entry.
#[derive(Clone, Copy, Debug)]
pub(crate) struct ResolvedConstraints<'a> {
    pub(crate) raw: &'a BuildConstraints,
    pub(crate) class: CharClass,
    pub(crate) offense: OffenseProfile,
    pub(crate) target_type: TargetType,
    pub(crate) mode: SearchMode,
}

impl std::ops::Deref for ResolvedConstraints<'_> {
    type Target = BuildConstraints;

    #[inline]
    fn deref(&self) -> &BuildConstraints {
        self.raw
    }
}

impl<'a> ResolvedConstraints<'a> {
    pub(crate) fn resolve(raw: &'a BuildConstraints) -> Result<Self, String> {
        let class = CharClass::from_id(raw.character.char_class)?;
        let offense = OffenseProfile::parse(&raw.offense, class)?;
        let target_type = TargetType::parse(&raw.target.target_type)?;
        let mode = SearchMode::parse(&raw.mode)?;
        Ok(Self {
            raw,
            class,
            offense,
            target_type,
            mode,
        })
    }

    pub(crate) fn with_raw<'b>(self, raw: &'b BuildConstraints) -> ResolvedConstraints<'b> {
        debug_assert!(
            ResolvedConstraints::resolve(raw).is_ok_and(|r| r.class == self.class
                && r.offense == self.offense
                && r.target_type == self.target_type
                && r.mode == self.mode)
        );
        ResolvedConstraints {
            raw,
            class: self.class,
            offense: self.offense,
            target_type: self.target_type,
            mode: self.mode,
        }
    }

    pub(crate) fn with_mode(self, mode: SearchMode) -> Self {
        Self { mode, ..self }
    }
}

macro_rules! define_item_spec {
    ($( $field:ident => $combine:ident ),* $(,)?) => {
        /// Item specification passed between Python (`d2savior`) and Rust.
        #[cfg_attr(feature = "python", pyclass(get_all, set_all))]
        #[derive(Clone, Debug, Default, PartialEq, Eq)]
        pub struct ItemSpec {
            pub name: String,
            pub slot: String,
            pub loc: String,
            $( pub $field: i32, )*
            pub req_str: i32,
            pub req_dex: i32,
            pub set_group: i32,
            pub set_item_id: i32,
            pub set_bonuses: Vec<(i32, ItemSpec)>,
            pub global_set_bonuses: Vec<(i32, ItemSpec)>,
            pub wsm: i32,
            pub wclass: String,
            pub wep_phys_2x: i32,
            pub wep_str_pct: i32,
            pub wep_dex_pct: i32,
            pub can_zeal: bool,
            pub splash_fire: bool,
            pub splash_fire_2x: i32,
        }

        impl ItemSpec {
            pub(crate) fn stats(&self) -> Stats {
                Stats {
                    $( $field: self.$field, )*
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
                    $( $field: s.$field, )*
                    req_str,
                    req_dex,
                    ..Default::default()
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
                $( $field = 0, )*
                req_str = 0,
                req_dex = 0,
                set_group = 0,
                set_item_id = 0,
                set_bonuses = Vec::new(),
                global_set_bonuses = Vec::new(),
                wsm = 0,
                wclass = String::new(),
                wep_phys_2x = 0,
                wep_str_pct = 0,
                wep_dex_pct = 0,
                can_zeal = false,
                splash_fire = false,
                splash_fire_2x = 0,
            ))]
            #[allow(clippy::too_many_arguments)]
            pub fn new(
                name: String,
                slot: String,
                loc: String,
                $( $field: i32, )*
                req_str: i32,
                req_dex: i32,
                set_group: i32,
                set_item_id: i32,
                set_bonuses: Vec<(i32, ItemSpec)>,
                global_set_bonuses: Vec<(i32, ItemSpec)>,
                wsm: i32,
                wclass: String,
                wep_phys_2x: i32,
                wep_str_pct: i32,
                wep_dex_pct: i32,
                can_zeal: bool,
                splash_fire: bool,
                splash_fire_2x: i32,
            ) -> Self {
                Self {
                    name,
                    slot,
                    loc,
                    $( $field, )*
                    req_str,
                    req_dex,
                    set_group,
                    set_item_id,
                    set_bonuses,
                    global_set_bonuses,
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
    };
}

with_stat_fields!(define_item_spec);

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

    pub(crate) fn active_global_set_bonus_stats(&self, piece_count: i32) -> Stats {
        self.global_set_bonuses
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

    pub(crate) fn max_possible_global_set_bonus_stats(&self) -> Stats {
        self.global_set_bonuses
            .iter()
            .fold(Stats::default(), |acc, (_, b)| {
                acc.add(b.stats().max_each(Stats::default()))
            })
    }

    pub(crate) fn max_total_stats(&self) -> Stats {
        if self.set_group == 0 {
            self.stats()
        } else {
            self.stats().add(self.max_possible_set_bonus_stats())
        }
    }

    pub(crate) fn set_bonus_sig(&self) -> SetBonusSig {
        let mut sig: SetBonusSig = self
            .set_bonuses
            .iter()
            .map(|(req, b)| (*req, b.stats()))
            .collect();
        sig.extend(
            self.global_set_bonuses
                .iter()
                .map(|(req, b)| (-*req, b.stats())),
        );
        sig
    }
}

macro_rules! with_charm_direct_stats {
    ($mac:ident) => {
        $mac!(
            fhr,
            fr,
            lr,
            cr,
            pr,
            mf,
            life,
            mana,
            frw,
            str_bonus,
            dex_bonus,
            all_skills,
            vit,
            ene,
            ar,
            flat_phys_2x,
            flat_fire_2x,
            flat_elem_2x,
            psn_dps_2x,
        );
    };
}

pub(crate) use with_charm_direct_stats;

macro_rules! define_charm_spec {
    ($( $field:ident ),* $(,)?) => {
        /// Charm specification passed between Python (`d2savior`) and Rust.
        #[cfg_attr(feature = "python", pyclass(get_all, eq, hash, frozen))]
        #[derive(Clone, Debug, Default, PartialEq, Eq, Hash)]
        pub struct CharmSpec {
            pub name: String,
            pub size: i32,
            pub loc: String,
            $( pub $field: i32, )*
            pub light_skills: i32,
            pub skills: i32,
            pub action_skills: i32,
            pub aura_skills: i32,
            pub unique_id: Option<i32>,
            pub cold_sunder: bool,
        }

        impl CharmSpec {
            pub(crate) fn general_skills(&self) -> i32 {
                self.all_skills + self.skills
            }

            pub(crate) fn skills_total(&self) -> i32 {
                self.general_skills() + self.action_skills + self.aura_skills
            }

            pub(crate) fn to_stats(&self, class: CharClass) -> Stats {
                let (sorc_skills, pal_skills) = match class {
                    CharClass::Sorceress => (self.skills, 0),
                    CharClass::Paladin => (0, self.skills),
                };
                Stats {
                    $( $field: self.$field, )*
                    sorc_skills,
                    pal_skills,
                    action_skill_bonus: self.action_skills,
                    aura_skill_bonus: self.aura_skills,
                    def_skill: self.action_skills,
                    ..Default::default()
                }
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
                $( $field = 0, )*
                light_skills = 0,
                skills = 0,
                action_skills = 0,
                aura_skills = 0,
                unique_id = None,
                cold_sunder = false,
            ))]
            #[allow(clippy::too_many_arguments)]
            pub fn new(
                name: String,
                size: i32,
                loc: String,
                $( $field: i32, )*
                light_skills: i32,
                skills: i32,
                action_skills: i32,
                aura_skills: i32,
                unique_id: Option<i32>,
                cold_sunder: bool,
            ) -> Self {
                Self {
                    name,
                    size,
                    loc,
                    $( $field, )*
                    light_skills,
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
                    self.name,
                    self.size,
                    self.general_skills(),
                    self.fhr,
                    self.mf,
                    self.life
                )
            }
        }
    };
}

with_charm_direct_stats!(define_charm_spec);

/// Character baseline stats and passive modifiers.
#[cfg_attr(feature = "python", pyclass(get_all, eq, frozen))]
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CharacterStats {
    pub char_class: u8,
    pub char_level: i32,
    pub base_life: i32,
    pub base_mana: i32,
    pub base_str: i32,
    pub base_dex: i32,
    pub base_hell_res: i32,
    pub base_max_fr: i32,
    pub base_max_lr: i32,
    pub base_max_cr: i32,
    pub base_max_pr: i32,
    pub bo_base_bonus: i32,
    pub use_bo: bool,
}

impl Default for CharacterStats {
    fn default() -> Self {
        Self {
            char_class: CharClass::SORCERESS_ID,
            char_level: 1,
            base_life: 0,
            base_mana: 0,
            base_str: 0,
            base_dex: 0,
            base_hell_res: -100,
            base_max_fr: 0,
            base_max_lr: 0,
            base_max_cr: 0,
            base_max_pr: 0,
            bo_base_bonus: 4,
            use_bo: true,
        }
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl CharacterStats {
    #[new]
    #[pyo3(signature = (
        char_class = 1,
        char_level = 1,
        base_life = 0,
        base_mana = 0,
        base_str = 0,
        base_dex = 0,
        base_hell_res = -100,
        base_max_fr = 0,
        base_max_lr = 0,
        base_max_cr = 0,
        base_max_pr = 0,
        bo_base_bonus = 4,
        use_bo = true,
    ))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        char_class: u8,
        char_level: i32,
        base_life: i32,
        base_mana: i32,
        base_str: i32,
        base_dex: i32,
        base_hell_res: i32,
        base_max_fr: i32,
        base_max_lr: i32,
        base_max_cr: i32,
        base_max_pr: i32,
        bo_base_bonus: i32,
        use_bo: bool,
    ) -> Self {
        Self {
            char_class,
            char_level,
            base_life,
            base_mana,
            base_str,
            base_dex,
            base_hell_res,
            base_max_fr,
            base_max_lr,
            base_max_cr,
            base_max_pr,
            bo_base_bonus,
            use_bo,
        }
    }
}

/// Target monster stats for hit, damage, and survivability calculations.
#[cfg_attr(feature = "python", pyclass(get_all, eq, frozen))]
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TargetProfile {
    pub targets: i32,
    pub target_type: String,
    pub target_def: i32,
    pub target_ar: i32,
    pub target_lvl: i32,
    pub target_hp: i32,
}

impl Default for TargetProfile {
    fn default() -> Self {
        Self {
            targets: 1,
            target_type: String::from("champion"),
            target_def: 180,
            target_ar: 0,
            target_lvl: 0,
            target_hp: 0,
        }
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl TargetProfile {
    #[new]
    #[pyo3(signature = (
        targets = 1,
        target_type = String::from("champion"),
        target_def = 180,
        target_ar = 0,
        target_lvl = 0,
        target_hp = 0,
    ))]
    pub fn new(
        targets: i32,
        target_type: String,
        target_def: i32,
        target_ar: i32,
        target_lvl: i32,
        target_hp: i32,
    ) -> Self {
        Self {
            targets,
            target_type,
            target_def,
            target_ar,
            target_lvl,
            target_hp,
        }
    }
}

/// Sorceress / caster skill progression tables and cold-armor baseline.
#[cfg_attr(feature = "python", pyclass(get_all, eq, frozen))]
#[derive(Clone, Debug, PartialEq)]
pub struct CasterSkillModel {
    pub blizz_base_lvl: i32,
    pub blizz_syn_pts: i32,
    pub cm_base_lvl: i32,
    pub blizz_dmg: Vec<f64>,
    pub filler_dmg: Vec<f64>,
    pub filler_is_aoe: bool,
    pub cold_armor_kind: u8,
    pub cold_armor_base_lvl: i32,
}

impl Default for CasterSkillModel {
    fn default() -> Self {
        Self {
            blizz_base_lvl: 20,
            blizz_syn_pts: 54,
            cm_base_lvl: 20,
            blizz_dmg: Vec::new(),
            filler_dmg: Vec::new(),
            filler_is_aoe: false,
            cold_armor_kind: 0,
            cold_armor_base_lvl: 0,
        }
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl CasterSkillModel {
    #[new]
    #[pyo3(signature = (
        blizz_base_lvl = 20,
        blizz_syn_pts = 54,
        cm_base_lvl = 20,
        blizz_dmg = Vec::new(),
        filler_dmg = Vec::new(),
        filler_is_aoe = false,
        cold_armor_kind = 0,
        cold_armor_base_lvl = 0,
    ))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        blizz_base_lvl: i32,
        blizz_syn_pts: i32,
        cm_base_lvl: i32,
        blizz_dmg: Vec<f64>,
        filler_dmg: Vec<f64>,
        filler_is_aoe: bool,
        cold_armor_kind: u8,
        cold_armor_base_lvl: i32,
    ) -> Self {
        Self {
            blizz_base_lvl,
            blizz_syn_pts,
            cm_base_lvl,
            blizz_dmg,
            filler_dmg,
            filler_is_aoe,
            cold_armor_kind,
            cold_armor_base_lvl,
        }
    }
}

/// Paladin / melee-aura skill progression tables and shield-defense baseline.
#[cfg_attr(feature = "python", pyclass(get_all, eq, frozen))]
#[derive(Clone, Debug, Default, PartialEq)]
pub struct MeleeSkillModel {
    pub aura_hit_dmg: Vec<f64>,
    pub aura_pulse_dps: Vec<f64>,
    pub action_ed: Vec<i32>,
    pub action_hits: Vec<i32>,
    pub has_aura: bool,
    pub aura_is_fire: bool,
    pub action_ar_pct: Vec<i32>,
    pub aura_ar_pct: Vec<i32>,
    pub aura_target_def_pct: Vec<i32>,
    pub holy_shield_base_lvl: i32,
    pub defiance_base_lvl: i32,
    pub aura_ed: Vec<i32>,
    pub aura_ias: Vec<i32>,
}

#[cfg(feature = "python")]
#[pymethods]
impl MeleeSkillModel {
    #[new]
    #[pyo3(signature = (
        aura_hit_dmg = Vec::new(),
        aura_pulse_dps = Vec::new(),
        action_ed = Vec::new(),
        action_hits = Vec::new(),
        has_aura = false,
        aura_is_fire = false,
        action_ar_pct = Vec::new(),
        aura_ar_pct = Vec::new(),
        aura_target_def_pct = Vec::new(),
        holy_shield_base_lvl = 0,
        defiance_base_lvl = 0,
        aura_ed = Vec::new(),
        aura_ias = Vec::new(),
    ))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        aura_hit_dmg: Vec<f64>,
        aura_pulse_dps: Vec<f64>,
        action_ed: Vec<i32>,
        action_hits: Vec<i32>,
        has_aura: bool,
        aura_is_fire: bool,
        action_ar_pct: Vec<i32>,
        aura_ar_pct: Vec<i32>,
        aura_target_def_pct: Vec<i32>,
        holy_shield_base_lvl: i32,
        defiance_base_lvl: i32,
        aura_ed: Vec<i32>,
        aura_ias: Vec<i32>,
    ) -> Self {
        Self {
            aura_hit_dmg,
            aura_pulse_dps,
            action_ed,
            action_hits,
            has_aura,
            aura_is_fire,
            action_ar_pct,
            aura_ar_pct,
            aura_target_def_pct,
            holy_shield_base_lvl,
            defiance_base_lvl,
            aura_ed,
            aura_ias,
        }
    }
}

/// Class-specific skill model attached to `BuildConstraints`.
#[derive(Clone, Debug, PartialEq)]
#[cfg_attr(feature = "python", derive(FromPyObject, IntoPyObject))]
pub enum SkillModel {
    Caster(CasterSkillModel),
    Melee(MeleeSkillModel),
}

impl Default for SkillModel {
    fn default() -> Self {
        Self::Caster(CasterSkillModel::default())
    }
}

impl SkillModel {
    pub fn caster(&self) -> Option<&CasterSkillModel> {
        match self {
            Self::Caster(m) => Some(m),
            Self::Melee(_) => None,
        }
    }

    pub fn melee(&self) -> Option<&MeleeSkillModel> {
        match self {
            Self::Melee(m) => Some(m),
            Self::Caster(_) => None,
        }
    }

    pub fn has_aura(&self) -> bool {
        self.melee().is_some_and(|m| m.has_aura)
    }
}

/// Search constraints, character baseline, target profile, and skill model.
#[cfg_attr(feature = "python", pyclass(get_all, frozen))]
#[derive(Clone, Debug, PartialEq)]
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
    pub limit: usize,
    pub fixed_gear: bool,
    pub fixed_slots: Vec<String>,
    pub offense: String,
    pub require_cbf: bool,
    pub min_frw: i32,
    pub min_ias: i32,
    pub min_cb: i32,
    pub min_ll: i32,
    pub min_pdr: i32,
    pub min_mf: i32,
    pub character: CharacterStats,
    pub target: TargetProfile,
    pub skills: SkillModel,
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
            limit: 5,
            fixed_gear: false,
            fixed_slots: Vec::new(),
            offense: String::from("caster"),
            require_cbf: false,
            min_frw: 0,
            min_ias: 0,
            min_cb: 0,
            min_ll: 0,
            min_pdr: 0,
            min_mf: 0,
            character: CharacterStats::default(),
            target: TargetProfile::default(),
            skills: SkillModel::default(),
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
        limit = 5,
        fixed_gear = false,
        fixed_slots = Vec::new(),
        offense = String::from("caster"),
        require_cbf = false,
        min_frw = 0,
        min_ias = 0,
        min_cb = 0,
        min_ll = 0,
        min_pdr = 0,
        min_mf = 0,
        character = None,
        target = None,
        skills = None,
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
        limit: usize,
        fixed_gear: bool,
        fixed_slots: Vec<String>,
        offense: String,
        require_cbf: bool,
        min_frw: i32,
        min_ias: i32,
        min_cb: i32,
        min_ll: i32,
        min_pdr: i32,
        min_mf: i32,
        character: Option<CharacterStats>,
        target: Option<TargetProfile>,
        skills: Option<SkillModel>,
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
            limit,
            fixed_gear,
            fixed_slots,
            offense,
            require_cbf,
            min_frw,
            min_ias,
            min_cb,
            min_ll,
            min_pdr,
            min_mf,
            character: character.unwrap_or_default(),
            target: target.unwrap_or_default(),
            skills: skills.unwrap_or_default(),
        }
    }

    pub fn with_limit(&self, limit: usize) -> Self {
        let mut cloned = self.clone();
        cloned.limit = limit;
        cloned
    }
}

impl BuildConstraints {
    pub fn is_slot_fixed(&self, slot: &str) -> bool {
        self.fixed_gear || self.fixed_slots.iter().any(|s| s == slot)
    }

    pub fn is_weapon_fixed(&self) -> bool {
        self.fixed_gear
            || self
                .fixed_slots
                .iter()
                .any(|s| matches!(s.as_str(), "weapon" | "weapon2h"))
    }

    pub fn is_shield_fixed(&self) -> bool {
        self.fixed_gear || self.fixed_slots.iter().any(|s| s == "shield")
    }

    pub fn is_hands_fixed(&self) -> bool {
        self.is_weapon_fixed() || self.is_shield_fixed()
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
    pub ar: i32,
    pub cth: i32,
    pub raw_dps: f64,
    pub gear_defense: i32,
    pub defense: i32,
    pub enemy_cth: i32,
    pub block_pct: i32,
    pub fbr: i32,
    pub fbr_bp: i32,
    pub fbr_frames: i32,
    pub has_shield: bool,
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
        character: CharacterStats {
            base_life: 806,
            base_mana: 211,
            base_hell_res: -70,
            base_str: 156,
            base_dex: 25,
            ..Default::default()
        },
        ..Default::default()
    }
}

#[cfg(test)]
#[path = "types_tests.rs"]
mod tests;
