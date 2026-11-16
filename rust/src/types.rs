#[cfg(feature = "python")]
use pyo3::prelude::*;

pub(crate) const BASE_MAX_RES: i32 = 75;
pub(crate) const HARD_MAX_RES: i32 = 95;

#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum SearchMode {
    Power,
    Mf,
    MaxRes,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub(crate) struct Stats {
    pub(crate) all_skills: i32,
    pub(crate) sorc_skills: i32,
    pub(crate) blizz_skills: i32,
    pub(crate) cm_skills: i32,
    pub(crate) fcr: i32,
    pub(crate) fhr: i32,
    pub(crate) frw: i32,
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
        self.all_skills + self.sorc_skills
    }

    pub(crate) fn blizz_power_skills(self) -> i32 {
        self.total_skills() + self.blizz_skills
    }

    pub(crate) fn res_sum(self) -> i32 {
        self.fr + self.lr + self.cr + self.pr
    }

    pub(crate) fn max_res_sum(self) -> i32 {
        self.max_fr + self.max_lr + self.max_cr + self.max_pr
    }

    pub(crate) fn add(self, o: Stats) -> Stats {
        Stats {
            all_skills: self.all_skills + o.all_skills,
            sorc_skills: self.sorc_skills + o.sorc_skills,
            blizz_skills: self.blizz_skills + o.blizz_skills,
            cm_skills: self.cm_skills + o.cm_skills,
            fcr: self.fcr + o.fcr,
            fhr: self.fhr + o.fhr,
            frw: self.frw + o.frw,
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
            blizz_skills: self.blizz_skills.max(o.blizz_skills),
            cm_skills: self.cm_skills.max(o.cm_skills),
            fcr: self.fcr.max(o.fcr),
            fhr: self.fhr.max(o.fhr),
            frw: self.frw.max(o.frw),
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
            && self.blizz_skills >= o.blizz_skills
            && self.cm_skills >= o.cm_skills
            && self.fcr >= o.fcr
            && self.fhr >= o.fhr
            && self.frw >= o.frw
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
    pub blizz_skills: i32,
    pub cm_skills: i32,
    pub fcr: i32,
    pub fhr: i32,
    pub frw: i32,
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
}

impl ItemSpec {
    pub fn total_skills(&self) -> i32 {
        self.all_skills + self.sorc_skills
    }

    pub(crate) fn is_weapon_or_shield(&self) -> bool {
        matches!(self.slot.as_str(), "weapon" | "shield")
    }

    pub(crate) fn stats(&self) -> Stats {
        Stats {
            all_skills: self.all_skills,
            sorc_skills: self.sorc_skills,
            blizz_skills: self.blizz_skills,
            cm_skills: self.cm_skills,
            fcr: self.fcr,
            fhr: self.fhr,
            frw: self.frw,
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
            blizz_skills: s.blizz_skills,
            cm_skills: s.cm_skills,
            fcr: s.fcr,
            fhr: s.fhr,
            frw: s.frw,
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
    ) -> Self {
        Self {
            name,
            slot,
            loc,
            all_skills,
            sorc_skills,
            blizz_skills,
            cm_skills,
            fcr,
            fhr,
            frw,
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
    pub unique_id: Option<i32>,
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
            unique_id,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "CharmSpec(name={:?}, size={}, skills={}, fhr={}, mf={}, life={})",
            self.name, self.size, self.skills, self.fhr, self.mf, self.life
        )
    }
}

/// Search constraints and Sorceress baseline stats.
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
    pub skill_slack: i32,
    pub mf_slack: i32,
    pub limit: usize,
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
            skill_slack: 1,
            mf_slack: 15,
            limit: 5,
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
        skill_slack = 1,
        mf_slack = 15,
        limit = 5,
        blizz_base_lvl = 20,
        blizz_syn_pts = 54,
        cm_base_lvl = 20,
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
        skill_slack: i32,
        mf_slack: i32,
        limit: usize,
        blizz_base_lvl: i32,
        blizz_syn_pts: i32,
        cm_base_lvl: i32,
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
            skill_slack,
            mf_slack,
            limit,
        }
    }
}

/// Evaluated loadout result returned to Python.
#[cfg_attr(feature = "python", pyclass(get_all))]
#[derive(Clone, Debug, PartialEq)]
pub struct BuildResult {
    pub skills: i32,
    pub blizz_avg: f64,
    pub cm_pierce: i32,
    pub fcr: i32,
    pub fcr_bp: i32,
    pub fhr: i32,
    pub fhr_bp: i32,
    pub frw: i32,
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
