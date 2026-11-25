#[cfg(feature = "python")]
use pyo3::exceptions::PyValueError;
#[cfg(feature = "python")]
use pyo3::prelude::*;

use crate::types::{
    compute_effective_gear_stats, equipped_hand_weapon, BuildConstraints, BuildResult, CharClass,
    CharmSpec, HandWeapon, ItemSpec, OffenseProfile, Stats, BASE_MAX_RES, HARD_MAX_PDR_PCT,
    HARD_MAX_RES,
};
#[cfg(feature = "python")]
use crate::types::TargetType;

#[cfg(feature = "python")]
#[pyfunction]
pub fn class_breakpoints(char_class: u8) -> PyResult<(Vec<i32>, Vec<i32>)> {
    let class = CharClass::from_id(char_class).map_err(PyValueError::new_err)?;
    Ok((class.fcr_bps().to_vec(), class.fhr_bps().to_vec()))
}

fn bp_tier(val: i32, bps: &[i32]) -> i32 {
    let mut best = 0;
    for &b in bps {
        if val >= b {
            best = b;
        }
    }
    best
}

fn blizzard_damage_split(
    blizz_bonus: i32,
    blizz_base: i32,
    syn_pts: i32,
    cm_bonus: i32,
    cm_base: i32,
) -> (f64, f64, i32) {
    let slvl = blizz_base + blizz_bonus;
    let mut avg = if slvl >= 1 { 60.0 } else { 0.0 };
    for l in 2..=slvl {
        avg += if l <= 8 {
            15.5
        } else if l <= 16 {
            30.5
        } else if l <= 22 {
            45.5
        } else if l <= 28 {
            55.5
        } else {
            65.5
        };
    }
    let syn_avg = avg * (1.0 + 0.05 * syn_pts.max(0) as f64);
    let cm_lvl = cm_base + cm_bonus;
    let cm_pierce = if cm_lvl >= 1 {
        -(20 + 5 * (cm_lvl - 1))
    } else {
        0
    };
    (avg, syn_avg, cm_pierce)
}

/// Calculate (un-synergized avg, synergized Blizz avg, Cold Mastery pierce %) from base levels + `+skills`.
#[cfg_attr(feature = "python", pyfunction)]
#[cfg_attr(
    feature = "python",
    pyo3(signature = (skills, blizz_base = 20, syn_pts = 54, cm_base = 20))
)]
pub fn blizzard_damage_with_base(
    skills: i32,
    blizz_base: i32,
    syn_pts: i32,
    cm_base: i32,
) -> (f64, f64, i32) {
    blizzard_damage_split(skills, blizz_base, syn_pts, skills, cm_base)
}

/// Calculate (un-synergized avg, synergized lvl-20 Blizz + 54 hard syn pts avg, Cold Mastery pierce %).
#[cfg_attr(feature = "python", pyfunction)]
pub fn blizzard_damage(skills: i32) -> (f64, f64, i32) {
    blizzard_damage_with_base(skills, 20, 54, 20)
}

pub(crate) fn res_caps(max_res: Stats, c: &BuildConstraints) -> (i32, i32, i32, i32) {
    (
        (BASE_MAX_RES + c.base_max_fr + max_res.max_fr).min(HARD_MAX_RES),
        (BASE_MAX_RES + c.base_max_lr + max_res.max_lr).min(HARD_MAX_RES),
        (BASE_MAX_RES + c.base_max_cr + max_res.max_cr).min(HARD_MAX_RES),
        (BASE_MAX_RES + c.base_max_pr + max_res.max_pr).min(HARD_MAX_RES),
    )
}

#[derive(Clone, Copy)]
pub(crate) struct EvalSummary {
    pub skills: i32,
    pub primary_skill_bonus: i32,
    pub action_skill_bonus: i32,
    pub aura_skill_bonus: i32,
    pub dps: f64,
    pub used_zeal: bool,
    pub blizz_skills: i32,
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
    pub ctc_lifetap_pct: i32,
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
    pub gear_defense: i32,
    pub defense: i32,
    pub enemy_cth: i32,
    pub block_pct: i32,
    pub fbr: i32,
    pub fbr_bp: i32,
    pub fbr_frames: i32,
    pub has_shield: bool,
    pub belt_slots: i32,
    pub ar: i32,
    pub cth: i32,
    pub raw_dps: f64,
}

impl EvalSummary {
    pub(crate) fn into_result(
        self,
        items: &[&ItemSpec],
        charms: &[&CharmSpec],
        evaluated_candidates: usize,
    ) -> BuildResult {
        BuildResult {
            skills: self.skills,
            primary_skill_bonus: self.primary_skill_bonus,
            action_skill_bonus: self.action_skill_bonus,
            aura_skill_bonus: self.aura_skill_bonus,
            dps: self.dps,
            used_zeal: self.used_zeal,
            blizz_avg: self.blizz_avg,
            cm_pierce: self.cm_pierce,
            fcr: self.fcr,
            fcr_bp: self.fcr_bp,
            fhr: self.fhr,
            fhr_bp: self.fhr_bp,
            frw: self.frw,
            ias: self.ias,
            ias_bp: self.ias_bp,
            ias_frames: self.ias_frames,
            ias_last_frames: self.ias_last_frames,
            cb: self.cb,
            cbf: self.cbf,
            pdr_pct: self.pdr_pct,
            life_leech: self.life_leech,
            mf: self.mf,
            fr: self.fr,
            fr_raw: self.fr_raw,
            max_fr: self.max_fr,
            lr: self.lr,
            lr_raw: self.lr_raw,
            max_lr: self.max_lr,
            cr: self.cr,
            cr_raw: self.cr_raw,
            max_cr: self.max_cr,
            pr: self.pr,
            pr_raw: self.pr_raw,
            max_pr: self.max_pr,
            life_no_bo: self.life_no_bo,
            life_bo: self.life_bo,
            mana_bo: self.mana_bo,
            bo_lvl: self.bo_lvl,
            charm_slots: self.charm_slots,
            ar: self.ar,
            cth: self.cth,
            raw_dps: self.raw_dps,
            gear_defense: self.gear_defense,
            defense: self.defense,
            enemy_cth: self.enemy_cth,
            block_pct: self.block_pct,
            fbr: self.fbr,
            fbr_bp: self.fbr_bp,
            fbr_frames: self.fbr_frames,
            has_shield: self.has_shield,
            items: items.iter().map(|i| (*i).clone()).collect(),
            charms: charms.iter().map(|c| (*c).clone()).collect(),
            evaluated_candidates,
        }
    }
}

pub(crate) fn eval_build_summary(
    gear: Stats,
    all_sk_non_wep: i32,
    hand: HandWeapon,
    has_shield: bool,
    charms: &[&CharmSpec],
    c: &BuildConstraints,
) -> EvalSummary {
    let charm_all_skills: i32 = charms.iter().map(|ch| ch.all_skills).sum();
    let charm_skills: i32 = charms.iter().map(|ch| ch.general_skills()).sum();
    let charm_class_skills = charm_skills - charm_all_skills;
    let charm_action_skills: i32 = charms.iter().map(|ch| ch.action_skills).sum();
    let charm_aura_skills: i32 = charms.iter().map(|ch| ch.aura_skills).sum();
    let charm_str: i32 = charms.iter().map(|ch| ch.str_bonus).sum();
    let charm_dex: i32 = charms.iter().map(|ch| ch.dex_bonus).sum();
    let charm_fhr: i32 = charms.iter().map(|ch| ch.fhr).sum();
    let charm_frw: i32 = charms.iter().map(|ch| ch.frw).sum();
    let charm_mf: i32 = charms.iter().map(|ch| ch.mf).sum();
    let charm_fr: i32 = charms.iter().map(|ch| ch.fr).sum();
    let charm_lr: i32 = charms.iter().map(|ch| ch.lr).sum();
    let charm_cr: i32 = charms.iter().map(|ch| ch.cr).sum();
    let charm_pr: i32 = charms.iter().map(|ch| ch.pr).sum();
    let charm_life: i32 = charms.iter().map(|ch| ch.life).sum();
    let charm_mana: i32 = charms.iter().map(|ch| ch.mana).sum();
    let charm_vit: i32 = charms.iter().map(|ch| ch.vit).sum();
    let charm_ene: i32 = charms.iter().map(|ch| ch.ene).sum();
    let charm_ar: i32 = charms.iter().map(|ch| ch.ar).sum();
    let charm_flat_phys_2x: i32 = charms.iter().map(|ch| ch.flat_phys_2x).sum();
    let charm_flat_fire_2x: i32 = charms.iter().map(|ch| ch.flat_fire_2x).sum();
    let charm_flat_elem_2x: i32 = charms.iter().map(|ch| ch.flat_elem_2x).sum();
    let charm_psn_dps_2x: i32 = charms.iter().map(|ch| ch.psn_dps_2x).sum();

    let skills = gear.total_skills() + charm_skills;
    let fcr = gear.fcr;
    let fhr = gear.fhr + charm_fhr;
    let frw = gear.frw + charm_frw;
    let mf = gear.mf + charm_mf;

    let fr_raw = c.base_hell_res + gear.fr + charm_fr;
    let lr_raw = c.base_hell_res + gear.lr + charm_lr;
    let cr_raw = c.base_hell_res + gear.cr + charm_cr;
    let pr_raw = c.base_hell_res + gear.pr + charm_pr;

    let class = CharClass::from_id_or_default(c.char_class);
    let vit_life = class.life_per_vit(gear.vit + charm_vit);
    let ene_mana = class.mana_per_ene(gear.ene + charm_ene);

    let bo_able_life = c.base_life + gear.life + charm_life;
    let bo_able_mana = c.base_mana + gear.mana + charm_mana;
    let life_no_bo = (bo_able_life as f64 * (1.0 + gear.pct_life as f64 / 100.0)) as i32
        + vit_life
        + gear.life_per_lvl;
    let (bo_lvl, life_bo, mana_bo) = if c.use_bo {
        let bo_lvl = c.bo_base_bonus + all_sk_non_wep + charm_all_skills;
        let bo_pct = 32 + 3 * bo_lvl;
        let life_bo = (bo_able_life as f64 * (1.0 + (bo_pct + gear.pct_life) as f64 / 100.0))
            as i32
            + vit_life
            + gear.life_per_lvl;
        let mana_bo = (bo_able_mana as f64 * (1.0 + (bo_pct + gear.pct_mana) as f64 / 100.0))
            as i32
            + ene_mana
            + gear.mana_per_lvl;
        (bo_lvl, life_bo, mana_bo)
    } else {
        let mana_no_bo = (bo_able_mana as f64 * (1.0 + gear.pct_mana as f64 / 100.0)) as i32
            + ene_mana
            + gear.mana_per_lvl;
        (0, life_no_bo, mana_no_bo)
    };

    let (_, blizz_avg_base, cm_pierce) = if class.has_blizzard_calc() {
        let blizz_eff = if c.blizz_base_lvl > 0 || gear.blizz_skills > 0 {
            skills + gear.blizz_skills
        } else {
            0
        };
        let cm_eff = if c.cm_base_lvl > 0 || gear.cm_skills > 0 {
            skills + gear.cm_skills
        } else {
            0
        };
        blizzard_damage_split(
            blizz_eff,
            c.blizz_base_lvl,
            c.blizz_syn_pts,
            cm_eff,
            c.cm_base_lvl,
        )
    } else {
        (0.0, 0.0, 0)
    };
    let blizz_avg = blizz_avg_base * (1.0 + gear.cold_dmg_pct.max(0) as f64 / 100.0);
    let (cap_fr, cap_lr, cap_cr, cap_pr) = res_caps(gear, c);
    let offense = OffenseProfile::parse(&c.offense, class).unwrap_or(OffenseProfile::Caster);
    let action_skill_bonus = gear.action_skill_bonus + charm_action_skills;
    let aura_skill_bonus = gear.aura_skill_bonus + charm_aura_skills;
    let (charm_sorc_skills, charm_pal_skills) = match class {
        CharClass::Sorceress => (charm_class_skills, 0),
        CharClass::Paladin => (0, charm_class_skills),
    };
    let combined_ar_stats = Stats {
        all_skills: gear.all_skills + charm_all_skills,
        sorc_skills: gear.sorc_skills + charm_sorc_skills,
        pal_skills: gear.pal_skills + charm_pal_skills,
        action_skill_bonus,
        aura_skill_bonus,
        str_bonus: c.base_str + gear.str_bonus + charm_str,
        dex_bonus: c.base_dex + gear.dex_bonus + charm_dex,
        ar: gear.ar + charm_ar,
        flat_phys_2x: gear.flat_phys_2x + charm_flat_phys_2x,
        flat_fire_2x: gear.flat_fire_2x + charm_flat_fire_2x,
        flat_elem_2x: gear.flat_elem_2x + charm_flat_elem_2x,
        psn_dps_2x: gear.psn_dps_2x + charm_psn_dps_2x,
        ..gear
    };
    let (dps, raw_dps, ar, cth, ias_bp, ias_frames, ias_last_frames, used_zeal) =
        if offense.uses_dps_tables(c) {
            offense.compute_dps_detailed(hand, combined_ar_stats, c)
        } else if offense.uses_caster_dps(c) {
            let (bp, frames) = offense.attack_speed(hand.wclass, hand.wsm, gear.ias);
            (
                offense.compute_caster_dps(combined_ar_stats, c),
                0.0,
                0,
                0,
                bp,
                frames,
                0,
                false,
            )
        } else {
            let (bp, frames) = offense.attack_speed(hand.wclass, hand.wsm, gear.ias);
            (
                0.0,
                0.0,
                0,
                0,
                bp,
                frames,
                0,
                offense == OffenseProfile::Zeal && hand.can_zeal,
            )
        };

    let total_dex = c.base_dex + gear.dex_bonus + charm_dex;
    let base_def = (gear.defense + total_dex.max(0) / 4).max(0);
    let hs_bonus =
        skills + gear.def_skill + if offense.is_melee_dps() { charm_action_skills } else { 0 };
    let hs_slvl = if class == CharClass::Paladin && has_shield && c.holy_shield_base_lvl > 0 {
        (c.holy_shield_base_lvl + hs_bonus).max(1)
    } else {
        0
    };
    let (skill_def_pct, hs_block) = match class {
        CharClass::Paladin if hs_slvl > 0 => (
            25 + 15 * (hs_slvl - 1) + 15 * c.defiance_base_lvl.max(0),
            10 + (30 * ((110 * hs_slvl) / (hs_slvl + 6))) / 100,
        ),
        CharClass::Sorceress if c.cold_armor_base_lvl > 0 || gear.def_skill > 0 => {
            let ca_slvl = (c.cold_armor_base_lvl + skills + gear.def_skill).max(1);
            let ed = match c.cold_armor_kind {
                1 => 30 + 5 * (ca_slvl - 1),
                2 => 45 + 6 * (ca_slvl - 1),
                3 => 60 + 9 * (ca_slvl - 1),
                _ => 0,
            };
            (ed, 0)
        }
        _ => (0, 0),
    };
    let defense = ((base_def as i64 * (100 + skill_def_pct as i64)) / 100) as i32;
    let enemy_cth = if c.target_ar > 0 {
        let ar_f = c.target_ar as f64;
        let def_f = defense.max(0) as f64;
        let mlvl_f = c.target_lvl.max(1) as f64;
        let clvl_f = c.char_level.max(1) as f64;
        let raw = 2.0 * (ar_f / (ar_f + def_f)) * (mlvl_f / (mlvl_f + clvl_f));
        (raw.clamp(0.05, 0.95) * 100.0).round() as i32
    } else {
        0
    };
    let (block_pct, fbr, fbr_bp, fbr_frames) = if has_shield {
        let shield_block = (gear.block_pct + class.class_block_bonus() + hs_block).max(0);
        let eff_dex = (total_dex - 15).max(0);
        let clvl = c.char_level.max(1);
        let block = ((shield_block * eff_dex) / (2 * clvl)).clamp(0, 75);
        let total_fbr = gear.fbr.max(0);
        let (bp, frames) = class.fbr_bp_and_frames(total_fbr, hs_slvl > 0);
        (block, total_fbr, bp, frames)
    } else {
        (0, 0, 0, 0)
    };

    EvalSummary {
        skills,
        primary_skill_bonus: gear.primary_skill,
        action_skill_bonus,
        aura_skill_bonus,
        dps,
        used_zeal,
        blizz_skills: gear.blizz_skills,
        blizz_avg,
        cm_pierce,
        fcr,
        fcr_bp: bp_tier(fcr, class.fcr_bps()),
        fhr,
        fhr_bp: bp_tier(fhr, class.fhr_bps()),
        frw,
        ias: gear.ias,
        ias_bp,
        ias_frames,
        ias_last_frames,
        cb: gear.cb,
        cbf: gear.cbf > 0,
        pdr_pct: gear.pdr_pct.min(HARD_MAX_PDR_PCT),
        life_leech: gear.life_leech,
        ctc_lifetap_pct: gear.ctc_lifetap_pct,
        mf,
        fr: fr_raw.min(cap_fr),
        fr_raw,
        max_fr: cap_fr,
        lr: lr_raw.min(cap_lr),
        lr_raw,
        max_lr: cap_lr,
        cr: cr_raw.min(cap_cr),
        cr_raw,
        max_cr: cap_cr,
        pr: pr_raw.min(cap_pr),
        pr_raw,
        max_pr: cap_pr,
        life_no_bo,
        life_bo,
        mana_bo,
        bo_lvl,
        charm_slots: charms.iter().map(|ch| ch.size).sum(),
        gear_defense: gear.defense,
        defense,
        enemy_cth,
        block_pct,
        fbr,
        fbr_bp,
        fbr_frames,
        has_shield,
        belt_slots: gear.belt_slots,
        ar,
        cth,
        raw_dps,
    }
}

pub(crate) fn eval_build_core(
    items: &[&ItemSpec],
    charms: &[&CharmSpec],
    c: &BuildConstraints,
    evaluated_candidates: usize,
) -> BuildResult {
    let (gear, all_sk_non_wep) = compute_effective_gear_stats(items);
    let hand = equipped_hand_weapon(items);
    let has_shield = items
        .iter()
        .any(|it| it.slot == "shield" && it.name != "(empty)");
    eval_build_summary(gear, all_sk_non_wep, hand, has_shield, charms, c).into_result(
        items,
        charms,
        evaluated_candidates,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn evaluate_build_core(
    items: &[ItemSpec],
    charms: &[CharmSpec],
    base_life: i32,
    base_mana: i32,
    base_hell_res: i32,
    bo_base_bonus: i32,
    blizz_base_lvl: i32,
    blizz_syn_pts: i32,
    cm_base_lvl: i32,
    char_class: u8,
    use_bo: bool,
    base_max_fr: i32,
    base_max_lr: i32,
    base_max_cr: i32,
    base_max_pr: i32,
) -> Result<BuildResult, String> {
    CharClass::from_id(char_class)?;
    let item_refs: Vec<&ItemSpec> = items.iter().collect();
    let charm_refs: Vec<&CharmSpec> = charms.iter().collect();
    let c = BuildConstraints {
        base_life,
        base_mana,
        base_hell_res,
        bo_base_bonus,
        blizz_base_lvl,
        blizz_syn_pts,
        cm_base_lvl,
        char_class,
        use_bo,
        base_max_fr,
        base_max_lr,
        base_max_cr,
        base_max_pr,
        ..Default::default()
    };
    Ok(eval_build_core(&item_refs, &charm_refs, &c, 1))
}

/// Evaluate a concrete list of equipped items and inventory charms.
#[cfg(feature = "python")]
#[pyfunction]
#[pyo3(signature = (
    items,
    charms,
    base_life = 0,
    base_mana = 0,
    base_hell_res = -100,
    bo_base_bonus = 4,
    blizz_base_lvl = 20,
    blizz_syn_pts = 54,
    cm_base_lvl = 20,
    char_class = 1,
    use_bo = true,
    base_max_fr = 0,
    base_max_lr = 0,
    base_max_cr = 0,
    base_max_pr = 0,
    constraints = None,
))]
#[allow(clippy::too_many_arguments)]
pub fn evaluate_build(
    items: Vec<ItemSpec>,
    charms: Vec<CharmSpec>,
    base_life: i32,
    base_mana: i32,
    base_hell_res: i32,
    bo_base_bonus: i32,
    blizz_base_lvl: i32,
    blizz_syn_pts: i32,
    cm_base_lvl: i32,
    char_class: u8,
    use_bo: bool,
    base_max_fr: i32,
    base_max_lr: i32,
    base_max_cr: i32,
    base_max_pr: i32,
    constraints: Option<BuildConstraints>,
) -> PyResult<BuildResult> {
    if let Some(c) = constraints.as_ref() {
        CharClass::from_id(c.char_class).map_err(PyValueError::new_err)?;
        TargetType::parse(&c.target_type).map_err(PyValueError::new_err)?;
        let item_refs: Vec<&ItemSpec> = items.iter().collect();
        let charm_refs: Vec<&CharmSpec> = charms.iter().collect();
        return Ok(eval_build_core(&item_refs, &charm_refs, c, 1));
    }
    evaluate_build_core(
        &items,
        &charms,
        base_life,
        base_mana,
        base_hell_res,
        bo_base_bonus,
        blizz_base_lvl,
        blizz_syn_pts,
        cm_base_lvl,
        char_class,
        use_bo,
        base_max_fr,
        base_max_lr,
        base_max_cr,
        base_max_pr,
    )
    .map_err(PyValueError::new_err)
}

#[cfg(test)]
#[path = "eval_tests.rs"]
mod tests;
