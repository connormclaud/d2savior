use std::collections::{BTreeMap, HashMap, HashSet};

use super::dp::{
    CharmCacheKey, CharmGroup, PureAxisDp, PureDpsSolver, StatTotals, UbGroupEntry, eval_sorted_ub,
    sorted_ub_entries,
};
use super::greedy::{
    charm_eff_life, charm_eff_mana, charm_stat_ub, is_res_mode, shrink_charm_pool,
    shrink_sunder_pool,
};
use crate::types::{BuildConstraints, CharClass, CharmSpec, OffenseProfile, SearchMode, Stats};

pub(crate) struct CharmSolver<'a> {
    pub(crate) pool: Vec<&'a CharmSpec>,
    pub(super) sunder_opts: Vec<&'a CharmSpec>,
    pub(super) c: &'a BuildConstraints,
    pub(super) mode: SearchMode,
    pub(super) class: CharClass,
    pub(super) raw_max_slots: i32,
    pub(super) max_slots: i32,
    pub(super) sum_neg: [i32; 4],
    pub(super) ub_str: i32,
    pub(super) ub_dex: i32,
    pub(super) ub_fhr: i32,
    pub(super) ub_frw: i32,
    pub(super) ub_res: [i32; 4],
    pub(super) ub_all_skills: i32,
    pub(super) ub_class_skills: i32,
    pub(super) ub_action_skills: i32,
    pub(super) ub_aura_skills: i32,
    pub(super) ub_mf: i32,
    pub(super) ub_ar: i32,
    pub(super) ub_flat_phys_2x: i32,
    pub(super) ub_flat_fire_2x: i32,
    pub(super) ub_flat_elem_2x: i32,
    pub(super) ub_psn_dps_2x: i32,
    pub(super) groups: Vec<CharmGroup>,
    pub(super) pure_axes: [PureAxisDp; 9],
    pub(super) suf_pos: Vec<StatTotals>,
    pub(super) suf_neg_res: Vec<[i32; 4]>,
    pub(super) order_str: Vec<UbGroupEntry>,
    pub(super) order_dex: Vec<UbGroupEntry>,
    pub(super) order_fhr: Vec<UbGroupEntry>,
    pub(super) order_frw: Vec<UbGroupEntry>,
    pub(super) order_res: [Vec<UbGroupEntry>; 4],
    pub(super) order_res_total: Vec<UbGroupEntry>,
    pub(super) order_skills: Vec<UbGroupEntry>,
    pub(super) order_mf: Vec<UbGroupEntry>,
    pub(super) cache: HashMap<CharmCacheKey, Option<(i32, Vec<usize>)>>,
    pub(super) failed_floor: HashMap<CharmCacheKey, i32>,
    pub(super) dps_groups: Vec<CharmGroup>,
    pub(super) dps_suf_pos: Vec<StatTotals>,
    pub(super) dps_suf_neg_res: Vec<[i32; 4]>,
    pub(super) dps_min_size: Vec<i32>,
    pub(super) dps_order_all_skills: Vec<UbGroupEntry>,
    pub(super) dps_order_class_skills: Vec<UbGroupEntry>,
    pub(super) dps_order_action_skills: Vec<UbGroupEntry>,
    pub(super) dps_order_aura_skills: Vec<UbGroupEntry>,
    pub(super) dps_order_str: Vec<UbGroupEntry>,
    pub(super) dps_order_dex: Vec<UbGroupEntry>,
    pub(super) dps_order_ar: Vec<UbGroupEntry>,
    pub(super) dps_order_phys: Vec<UbGroupEntry>,
    pub(super) dps_order_fire: Vec<UbGroupEntry>,
    pub(super) dps_order_elem: Vec<UbGroupEntry>,
    pub(super) dps_order_psn: Vec<UbGroupEntry>,
    pub(super) dps_order_res: [Vec<UbGroupEntry>; 4],
    pub(super) dps_order_fhr: Vec<UbGroupEntry>,
    pub(super) dps_order_frw: Vec<UbGroupEntry>,
    pub(super) dps_order_mf: Vec<UbGroupEntry>,
    pub(super) dps_group_has_util: Vec<bool>,
    pub(super) pure_dps: PureDpsSolver,
    pub(super) non_dps_solver: Option<Box<CharmSolver<'a>>>,
    pub(super) nd_res_at: Vec<[i32; 4]>,
    pub(super) nd_fhr_at: Vec<i32>,
    pub(super) nd_frw_at: Vec<i32>,
    pub(super) nd_mf_at: Vec<i32>,
}

impl<'a> CharmSolver<'a> {
    pub(crate) fn has_cold_sunder(&self) -> bool {
        !self.sunder_opts.is_empty()
    }

    pub(crate) fn charm_ub_stats(&self) -> Stats {
        let class_splits = |skills: i32| match self.class {
            CharClass::Sorceress => (skills, 0),
            CharClass::Paladin => (0, skills),
        };
        let base = if let Some(&first) = self.sunder_opts.first() {
            let (s_sk, p_sk) = class_splits(first.skills);
            let mut acc = Stats {
                all_skills: first.all_skills,
                sorc_skills: s_sk,
                pal_skills: p_sk,
                action_skill_bonus: first.action_skills,
                aura_skill_bonus: first.aura_skills,
                fhr: first.fhr,
                frw: first.frw,
                fr: first.fr,
                lr: first.lr,
                cr: first.cr,
                pr: first.pr,
                mf: first.mf,
                str_bonus: first.str_bonus,
                dex_bonus: first.dex_bonus,
                ar: first.ar,
                flat_phys_2x: first.flat_phys_2x,
                flat_fire_2x: first.flat_fire_2x,
                flat_elem_2x: first.flat_elem_2x,
                psn_dps_2x: first.psn_dps_2x,
                ..Default::default()
            };
            for &s in &self.sunder_opts[1..] {
                let (ss_sk, sp_sk) = class_splits(s.skills);
                acc = acc.max_each(Stats {
                    all_skills: s.all_skills,
                    sorc_skills: ss_sk,
                    pal_skills: sp_sk,
                    action_skill_bonus: s.action_skills,
                    aura_skill_bonus: s.aura_skills,
                    fhr: s.fhr,
                    frw: s.frw,
                    fr: s.fr,
                    lr: s.lr,
                    cr: s.cr,
                    pr: s.pr,
                    mf: s.mf,
                    str_bonus: s.str_bonus,
                    dex_bonus: s.dex_bonus,
                    ar: s.ar,
                    flat_phys_2x: s.flat_phys_2x,
                    flat_fire_2x: s.flat_fire_2x,
                    flat_elem_2x: s.flat_elem_2x,
                    psn_dps_2x: s.psn_dps_2x,
                    ..Default::default()
                });
            }
            acc
        } else {
            Stats::default()
        };
        let (ub_sorc, ub_pal) = class_splits(self.ub_class_skills);
        Stats {
            all_skills: base.all_skills + self.ub_all_skills,
            sorc_skills: base.sorc_skills + ub_sorc,
            pal_skills: base.pal_skills + ub_pal,
            action_skill_bonus: base.action_skill_bonus + self.ub_action_skills,
            aura_skill_bonus: base.aura_skill_bonus + self.ub_aura_skills,
            fhr: base.fhr + self.ub_fhr,
            frw: base.frw + self.ub_frw,
            fr: base.fr + self.ub_res[0],
            lr: base.lr + self.ub_res[1],
            cr: base.cr + self.ub_res[2],
            pr: base.pr + self.ub_res[3],
            mf: base.mf + self.ub_mf,
            str_bonus: base.str_bonus + self.ub_str,
            dex_bonus: base.dex_bonus + self.ub_dex,
            ar: base.ar + self.ub_ar,
            flat_phys_2x: base.flat_phys_2x + self.ub_flat_phys_2x,
            flat_fire_2x: base.flat_fire_2x + self.ub_flat_fire_2x,
            flat_elem_2x: base.flat_elem_2x + self.ub_flat_elem_2x,
            psn_dps_2x: base.psn_dps_2x + self.ub_psn_dps_2x,
            ..Default::default()
        }
    }

    pub(crate) fn new(
        raw_pool: &[&'a CharmSpec],
        c: &'a BuildConstraints,
        mode: SearchMode,
    ) -> Self {
        Self::new_inner(raw_pool, c, mode, true)
    }

    fn new_inner(
        raw_pool: &[&'a CharmSpec],
        c: &'a BuildConstraints,
        mode: SearchMode,
        build_dps_refiner: bool,
    ) -> Self {
        let raw_max_slots = c.max_charm_slots.max(0);
        let class = CharClass::from_id_or_default(c.char_class);
        let (sunder_opts, max_slots, pool) =
            partition_sunder_pool(raw_pool, class, mode, raw_max_slots);

        let mut sum_neg = [0i32; 4];
        for &ch in &pool {
            sum_neg[0] += ch.fr.min(0);
            sum_neg[1] += ch.lr.min(0);
            sum_neg[2] += ch.cr.min(0);
            sum_neg[3] += ch.pr.min(0);
        }

        let ub_str = charm_stat_ub(&pool, max_slots, |ch| ch.str_bonus);
        let ub_dex = charm_stat_ub(&pool, max_slots, |ch| ch.dex_bonus);
        let ub_fhr = charm_stat_ub(&pool, max_slots, |ch| ch.fhr);
        let ub_frw = charm_stat_ub(&pool, max_slots, |ch| ch.frw);
        let ub_res = [
            charm_stat_ub(&pool, max_slots, |ch| ch.fr),
            charm_stat_ub(&pool, max_slots, |ch| ch.lr),
            charm_stat_ub(&pool, max_slots, |ch| ch.cr),
            charm_stat_ub(&pool, max_slots, |ch| ch.pr),
        ];
        let ub_all_skills = charm_stat_ub(&pool, max_slots, |ch| ch.all_skills);
        let ub_class_skills = charm_stat_ub(&pool, max_slots, |ch| ch.skills);
        let ub_action_skills = charm_stat_ub(&pool, max_slots, |ch| ch.action_skills);
        let ub_aura_skills = charm_stat_ub(&pool, max_slots, |ch| ch.aura_skills);
        let ub_mf = charm_stat_ub(&pool, max_slots, |ch| ch.mf);
        let ub_ar = charm_stat_ub(&pool, max_slots, |ch| ch.ar);
        let ub_flat_phys_2x = charm_stat_ub(&pool, max_slots, |ch| ch.flat_phys_2x);
        let ub_flat_fire_2x = charm_stat_ub(&pool, max_slots, |ch| ch.flat_fire_2x);
        let ub_flat_elem_2x = charm_stat_ub(&pool, max_slots, |ch| ch.flat_elem_2x);
        let ub_psn_dps_2x = charm_stat_ub(&pool, max_slots, |ch| ch.psn_dps_2x);

        let non_dps = build_non_dps_index(&pool, c, mode, class, max_slots);
        let dps = if build_dps_refiner
            && matches!(mode, SearchMode::Leveling | SearchMode::LevelingRes)
            && OffenseProfile::parse(&c.offense, class).is_ok_and(|o| o.uses_dps_tables(c))
        {
            build_dps_index(&pool, c, class, max_slots)
        } else {
            DpsIndex::default()
        };

        Self {
            pool,
            sunder_opts,
            c,
            mode,
            class,
            raw_max_slots,
            max_slots,
            sum_neg,
            ub_str,
            ub_dex,
            ub_fhr,
            ub_frw,
            ub_res,
            ub_all_skills,
            ub_class_skills,
            ub_action_skills,
            ub_aura_skills,
            ub_mf,
            ub_ar,
            ub_flat_phys_2x,
            ub_flat_fire_2x,
            ub_flat_elem_2x,
            ub_psn_dps_2x,
            groups: non_dps.groups,
            pure_axes: non_dps.pure_axes,
            suf_pos: non_dps.suf_pos,
            suf_neg_res: non_dps.suf_neg_res,
            order_str: non_dps.order_str,
            order_dex: non_dps.order_dex,
            order_fhr: non_dps.order_fhr,
            order_frw: non_dps.order_frw,
            order_res: non_dps.order_res,
            order_res_total: non_dps.order_res_total,
            order_skills: non_dps.order_skills,
            order_mf: non_dps.order_mf,
            cache: HashMap::new(),
            failed_floor: HashMap::new(),
            dps_groups: dps.dps_groups,
            dps_suf_pos: dps.dps_suf_pos,
            dps_suf_neg_res: dps.dps_suf_neg_res,
            dps_min_size: dps.dps_min_size,
            dps_order_all_skills: dps.dps_order_all_skills,
            dps_order_class_skills: dps.dps_order_class_skills,
            dps_order_action_skills: dps.dps_order_action_skills,
            dps_order_aura_skills: dps.dps_order_aura_skills,
            dps_order_str: dps.dps_order_str,
            dps_order_dex: dps.dps_order_dex,
            dps_order_ar: dps.dps_order_ar,
            dps_order_phys: dps.dps_order_phys,
            dps_order_fire: dps.dps_order_fire,
            dps_order_elem: dps.dps_order_elem,
            dps_order_psn: dps.dps_order_psn,
            dps_order_res: dps.dps_order_res,
            dps_order_fhr: dps.dps_order_fhr,
            dps_order_frw: dps.dps_order_frw,
            dps_order_mf: dps.dps_order_mf,
            dps_group_has_util: dps.dps_group_has_util,
            pure_dps: dps.pure_dps,
            non_dps_solver: dps.non_dps_solver,
            nd_res_at: dps.nd_res_at,
            nd_fhr_at: dps.nd_fhr_at,
            nd_frw_at: dps.nd_frw_at,
            nd_mf_at: dps.nd_mf_at,
        }
    }
}

fn main_val_for_mode(ch: &CharmSpec, mode: SearchMode) -> i32 {
    match mode {
        SearchMode::Power | SearchMode::Leveling => ch.skills_total().max(0),
        SearchMode::Mf => ch.mf.max(0),
        SearchMode::MaxRes | SearchMode::LevelingRes => {
            ch.fr.max(0) + ch.lr.max(0) + ch.cr.max(0) + ch.pr.max(0)
        }
    }
}

fn partition_sunder_pool<'a>(
    raw_pool: &[&'a CharmSpec],
    class: CharClass,
    mode: SearchMode,
    raw_max_slots: i32,
) -> (Vec<&'a CharmSpec>, i32, Vec<&'a CharmSpec>) {
    let main_val_of = |ch: &CharmSpec| main_val_for_mode(ch, mode);
    let raw_sunders: Vec<&'a CharmSpec> = if class.forces_cold_sunder() && !is_res_mode(mode) {
        raw_pool
            .iter()
            .copied()
            .filter(|ch| ch.cold_sunder && ch.size <= raw_max_slots)
            .collect()
    } else {
        Vec::new()
    };

    let (sunder_opts, max_slots, pool) = if !raw_sunders.is_empty() {
        let raw_non_sunders: Vec<&'a CharmSpec> = raw_pool
            .iter()
            .copied()
            .filter(|ch| !ch.cold_sunder)
            .collect();
        let non_sunder_uids: HashSet<i32> = raw_non_sunders
            .iter()
            .filter_map(|ch| ch.unique_id)
            .collect();
        let mut sunder_opts = shrink_sunder_pool(&raw_sunders, &non_sunder_uids);
        sunder_opts.sort_by_key(|s| {
            std::cmp::Reverse((
                main_val_of(s),
                s.cr,
                s.fhr,
                s.fr + s.lr + s.pr,
                s.str_bonus + s.dex_bonus,
                charm_eff_life(s, class),
                charm_eff_mana(s, class),
                -s.size,
            ))
        });
        let min_sunder_size = sunder_opts.iter().map(|s| s.size.max(0)).min().unwrap_or(0);
        let rem_slots = (raw_max_slots - min_sunder_size).max(0);
        let single_uid = if sunder_opts.len() == 1 {
            sunder_opts[0].unique_id
        } else {
            None
        };
        let filtered_non_sunders: Vec<&'a CharmSpec> = if let Some(uid) = single_uid {
            raw_non_sunders
                .into_iter()
                .filter(|ch| ch.unique_id != Some(uid))
                .collect()
        } else {
            raw_non_sunders
        };
        let pool = shrink_charm_pool(&filtered_non_sunders, rem_slots);
        (sunder_opts, rem_slots, pool)
    } else {
        (
            Vec::new(),
            raw_max_slots,
            shrink_charm_pool(raw_pool, raw_max_slots),
        )
    };

    (sunder_opts, max_slots, pool)
}

struct NonDpsIndex {
    groups: Vec<CharmGroup>,
    pure_axes: [PureAxisDp; 9],
    suf_pos: Vec<StatTotals>,
    suf_neg_res: Vec<[i32; 4]>,
    order_str: Vec<UbGroupEntry>,
    order_dex: Vec<UbGroupEntry>,
    order_fhr: Vec<UbGroupEntry>,
    order_frw: Vec<UbGroupEntry>,
    order_res: [Vec<UbGroupEntry>; 4],
    order_res_total: Vec<UbGroupEntry>,
    order_skills: Vec<UbGroupEntry>,
    order_mf: Vec<UbGroupEntry>,
}

fn build_non_dps_index(
    pool: &[&CharmSpec],
    c: &BuildConstraints,
    mode: SearchMode,
    class: CharClass,
    max_slots: i32,
) -> NonDpsIndex {
    let main_val_of = |ch: &CharmSpec| main_val_for_mode(ch, mode);
    let is_relevant = |ch: &CharmSpec| {
        let helps_feas = ch.str_bonus > 0
            || ch.dex_bonus > 0
            || ch.fhr > 0
            || (c.min_frw > 0 && ch.frw > 0)
            || (c.min_mf > 0 && ch.mf > 0)
            || ch.fr > 0
            || ch.lr > 0
            || ch.cr > 0
            || ch.pr > 0;
        let helps_main = match mode {
            SearchMode::Power | SearchMode::Leveling => ch.skills_total() > 0,
            SearchMode::Mf => ch.mf > 0,
            SearchMode::MaxRes | SearchMode::LevelingRes => {
                ch.fr > 0 || ch.lr > 0 || ch.cr > 0 || ch.pr > 0
            }
        };
        helps_feas || helps_main
    };

    let active_frw = c.min_frw > 0;
    let active_mf = c.min_mf > 0 || mode == SearchMode::Mf;
    let pure_axis_of = |ch: &CharmSpec| -> Option<(usize, i32)> {
        if ch.unique_id.is_some()
            || ch.size <= 0
            || ch.fr < 0
            || ch.lr < 0
            || ch.cr < 0
            || ch.pr < 0
        {
            return None;
        }
        let zero_main = match mode {
            SearchMode::Power | SearchMode::Leveling => ch.skills_total() == 0,
            SearchMode::Mf => ch.mf == 0 && ch.skills_total() == 0,
            SearchMode::MaxRes | SearchMode::LevelingRes => {
                ch.fr == 0 && ch.lr == 0 && ch.cr == 0 && ch.pr == 0
            }
        };
        if !zero_main {
            return None;
        }
        let stats = [
            ch.str_bonus,
            ch.dex_bonus,
            ch.fhr,
            ch.fr,
            ch.lr,
            ch.cr,
            ch.pr,
            if active_frw { ch.frw } else { 0 },
            if active_mf { ch.mf } else { 0 },
        ];
        let mut found = None;
        for (d, &v) in stats.iter().enumerate() {
            if v < 0 {
                return None;
            }
            if v > 0 {
                if found.is_some() {
                    return None;
                }
                found = Some((d, v));
            }
        }
        found
    };

    let mut pure_items: [Vec<(usize, &CharmSpec, i32)>; 9] = std::array::from_fn(|_| Vec::new());
    let mut unique_map: BTreeMap<i32, Vec<usize>> = BTreeMap::new();
    type MultiKey = [i32; 14];
    let mut multi_map: BTreeMap<MultiKey, Vec<usize>> = BTreeMap::new();

    for (idx, &ch) in pool.iter().enumerate() {
        if !is_relevant(ch) {
            continue;
        }
        if let Some((axis, val)) = pure_axis_of(ch) {
            pure_items[axis].push((idx, ch, val));
        } else if let Some(uid) = ch.unique_id {
            unique_map.entry(uid).or_default().push(idx);
        } else {
            let key = [
                ch.size,
                ch.fhr,
                if active_frw { ch.frw } else { 0 },
                ch.fr,
                ch.lr,
                ch.cr,
                ch.pr,
                ch.mf,
                ch.str_bonus,
                ch.dex_bonus,
                ch.all_skills,
                ch.skills,
                ch.action_skills,
                ch.aura_skills,
            ];
            multi_map.entry(key).or_default().push(idx);
        }
    }
    let pure_axes: [PureAxisDp; 9] =
        std::array::from_fn(|d| PureAxisDp::build(&pure_items[d], max_slots, class));

    let mut groups: Vec<CharmGroup> = Vec::new();
    for (_, mut opts) in unique_map {
        opts.sort_by(|&a, &b| {
            let ca = pool[a];
            let cb = pool[b];
            let va = (
                main_val_of(ca),
                ca.skills_total(),
                ca.all_skills,
                charm_eff_life(ca, class),
                charm_eff_mana(ca, class),
            );
            let vb = (
                main_val_of(cb),
                cb.skills_total(),
                cb.all_skills,
                charm_eff_life(cb, class),
                charm_eff_mana(cb, class),
            );
            vb.cmp(&va)
        });
        let mut max_pos = StatTotals::default();
        let mut min_neg_res = [0i32; 4];
        let mut min_size = i32::MAX;
        for &i in &opts {
            let ch = pool[i];
            max_pos = max_pos.max_each(StatTotals::from_charm(ch).clamp_non_neg());
            min_neg_res[0] = min_neg_res[0].min(ch.fr.min(0));
            min_neg_res[1] = min_neg_res[1].min(ch.lr.min(0));
            min_neg_res[2] = min_neg_res[2].min(ch.cr.min(0));
            min_neg_res[3] = min_neg_res[3].min(ch.pr.min(0));
            min_size = min_size.min(ch.size.max(1));
        }
        groups.push(CharmGroup::Unique {
            options: opts,
            max_pos,
            min_size,
            min_neg_res,
        });
    }
    for (_, mut members) in multi_map {
        let member_tie = |ch: &CharmSpec| {
            (
                charm_eff_life(ch, class),
                ch.life,
                charm_eff_mana(ch, class),
                ch.mana,
                ch.frw,
                ch.ar,
            )
        };
        members.sort_by(|&a, &b| member_tie(pool[b]).cmp(&member_tie(pool[a])));
        let rep = pool[members[0]];
        let size = rep.size.max(1);
        let max_copies = (max_slots / size).max(0) as usize;
        members.truncate(max_copies);
        if !members.is_empty() {
            groups.push(CharmGroup::Multi {
                members,
                size,
                stats: StatTotals::from_charm(rep),
            });
        }
    }

    let group_sort_key = |g: &CharmGroup| -> (i64, i32, i32, i32, i32, i32, i32) {
        match g {
            CharmGroup::Unique { options, .. } => {
                let rep_idx = options[0];
                let ch = pool[rep_idx];
                let sz = ch.size.max(1) as i64;
                let mv = main_val_of(ch) as i64;
                let feas = ch.str_bonus.max(0)
                    + ch.dex_bonus.max(0)
                    + ch.fhr.max(0)
                    + ch.fr.max(0)
                    + ch.lr.max(0)
                    + ch.cr.max(0)
                    + ch.pr.max(0);
                (
                    mv * 1000 / sz,
                    feas,
                    -ch.size,
                    charm_eff_life(ch, class),
                    charm_eff_mana(ch, class),
                    ch.frw,
                    -(rep_idx as i32),
                )
            }
            CharmGroup::Multi {
                members,
                size,
                stats,
            } => {
                let rep_idx = members[0];
                let ch = pool[rep_idx];
                let mv = main_val_of(ch) as i64;
                let feas = stats.str_bonus.max(0)
                    + stats.dex_bonus.max(0)
                    + stats.fhr.max(0)
                    + stats.res.iter().map(|&r| r.max(0)).sum::<i32>();
                (
                    mv * 1000 / (*size as i64),
                    feas,
                    -*size,
                    charm_eff_life(ch, class),
                    charm_eff_mana(ch, class),
                    ch.frw,
                    -(rep_idx as i32),
                )
            }
        }
    };
    groups.sort_by_key(|g| std::cmp::Reverse(group_sort_key(g)));

    let mut suf_pos = vec![StatTotals::default(); groups.len() + 1];
    let mut suf_neg_res = vec![[0i32; 4]; groups.len() + 1];
    for i in (0..groups.len()).rev() {
        let gp = groups[i].max_pos_total();
        suf_pos[i] = StatTotals {
            str_bonus: suf_pos[i + 1].str_bonus + gp.str_bonus,
            dex_bonus: suf_pos[i + 1].dex_bonus + gp.dex_bonus,
            fhr: suf_pos[i + 1].fhr + gp.fhr,
            frw: suf_pos[i + 1].frw + gp.frw,
            res: [
                suf_pos[i + 1].res[0] + gp.res[0],
                suf_pos[i + 1].res[1] + gp.res[1],
                suf_pos[i + 1].res[2] + gp.res[2],
                suf_pos[i + 1].res[3] + gp.res[3],
            ],
            skills: suf_pos[i + 1].skills + gp.skills,
            all_skills: suf_pos[i + 1].all_skills + gp.all_skills,
            class_skills: suf_pos[i + 1].class_skills + gp.class_skills,
            general_skills: suf_pos[i + 1].general_skills + gp.general_skills,
            action_skills: suf_pos[i + 1].action_skills + gp.action_skills,
            aura_skills: suf_pos[i + 1].aura_skills + gp.aura_skills,
            mf: suf_pos[i + 1].mf + gp.mf,
            ar: suf_pos[i + 1].ar + gp.ar,
            flat_phys_2x: suf_pos[i + 1].flat_phys_2x + gp.flat_phys_2x,
            flat_fire_2x: suf_pos[i + 1].flat_fire_2x + gp.flat_fire_2x,
            flat_elem_2x: suf_pos[i + 1].flat_elem_2x + gp.flat_elem_2x,
            psn_dps_2x: suf_pos[i + 1].psn_dps_2x + gp.psn_dps_2x,
        };
        let gn = groups[i].min_neg_res();
        for r in 0..4 {
            suf_neg_res[i][r] = suf_neg_res[i + 1][r] + gn[r];
        }
    }

    let order_str = sorted_ub_entries(&groups, pool, &pure_items[0], |ch| ch.str_bonus);
    let order_dex = sorted_ub_entries(&groups, pool, &pure_items[1], |ch| ch.dex_bonus);
    let order_fhr = sorted_ub_entries(&groups, pool, &pure_items[2], |ch| ch.fhr);
    let order_frw = sorted_ub_entries(&groups, pool, &pure_items[7], |ch| ch.frw);
    let order_res = [
        sorted_ub_entries(&groups, pool, &pure_items[3], |ch| ch.fr),
        sorted_ub_entries(&groups, pool, &pure_items[4], |ch| ch.lr),
        sorted_ub_entries(&groups, pool, &pure_items[5], |ch| ch.cr),
        sorted_ub_entries(&groups, pool, &pure_items[6], |ch| ch.pr),
    ];
    let order_res_total = sorted_ub_entries(&groups, pool, &[], |ch| {
        ch.fr.max(0) + ch.lr.max(0) + ch.cr.max(0) + ch.pr.max(0)
    });
    let order_skills = sorted_ub_entries(&groups, pool, &[], |ch| ch.skills_total());
    let order_mf = sorted_ub_entries(&groups, pool, &pure_items[8], |ch| ch.mf);

    NonDpsIndex {
        groups,
        pure_axes,
        suf_pos,
        suf_neg_res,
        order_str,
        order_dex,
        order_fhr,
        order_frw,
        order_res,
        order_res_total,
        order_skills,
        order_mf,
    }
}

#[derive(Default)]
struct DpsIndex<'a> {
    dps_groups: Vec<CharmGroup>,
    dps_suf_pos: Vec<StatTotals>,
    dps_suf_neg_res: Vec<[i32; 4]>,
    dps_min_size: Vec<i32>,
    dps_order_all_skills: Vec<UbGroupEntry>,
    dps_order_class_skills: Vec<UbGroupEntry>,
    dps_order_action_skills: Vec<UbGroupEntry>,
    dps_order_aura_skills: Vec<UbGroupEntry>,
    dps_order_str: Vec<UbGroupEntry>,
    dps_order_dex: Vec<UbGroupEntry>,
    dps_order_ar: Vec<UbGroupEntry>,
    dps_order_phys: Vec<UbGroupEntry>,
    dps_order_fire: Vec<UbGroupEntry>,
    dps_order_elem: Vec<UbGroupEntry>,
    dps_order_psn: Vec<UbGroupEntry>,
    dps_order_res: [Vec<UbGroupEntry>; 4],
    dps_order_fhr: Vec<UbGroupEntry>,
    dps_order_frw: Vec<UbGroupEntry>,
    dps_order_mf: Vec<UbGroupEntry>,
    dps_group_has_util: Vec<bool>,
    pure_dps: PureDpsSolver,
    non_dps_solver: Option<Box<CharmSolver<'a>>>,
    nd_res_at: Vec<[i32; 4]>,
    nd_fhr_at: Vec<i32>,
    nd_frw_at: Vec<i32>,
    nd_mf_at: Vec<i32>,
}

fn build_dps_index<'a>(
    pool: &[&'a CharmSpec],
    c: &'a BuildConstraints,
    class: CharClass,
    max_slots: i32,
) -> DpsIndex<'a> {
    let is_pure_dps = |ch: &CharmSpec| {
        (ch.ar > 0
            || ch.flat_phys_2x > 0
            || ch.flat_fire_2x > 0
            || ch.flat_elem_2x > 0
            || ch.psn_dps_2x > 0)
            && ch.ar >= 0
            && ch.flat_phys_2x >= 0
            && ch.flat_fire_2x >= 0
            && ch.flat_elem_2x >= 0
            && ch.psn_dps_2x >= 0
            && ch.unique_id.is_none()
            && ch.size > 0
            && ch.fhr == 0
            && ch.fr == 0
            && ch.lr == 0
            && ch.cr == 0
            && ch.pr == 0
            && ch.mf == 0
            && ch.life == 0
            && ch.mana == 0
            && ch.vit == 0
            && ch.ene == 0
            && ch.frw == 0
            && ch.str_bonus == 0
            && ch.dex_bonus == 0
            && ch.skills_total() == 0
    };
    let is_dps_stat = |ch: &CharmSpec| {
        ch.ar > 0
            || ch.dex_bonus > 0
            || ch.str_bonus > 0
            || ch.skills_total() > 0
            || ch.flat_phys_2x > 0
            || ch.flat_fire_2x > 0
            || ch.flat_elem_2x > 0
            || ch.psn_dps_2x > 0
    };
    let dps_uids: HashSet<i32> = pool
        .iter()
        .filter(|&&ch| is_dps_stat(ch))
        .filter_map(|ch| ch.unique_id)
        .collect();

    let mut pure_dps_indices: Vec<usize> = Vec::new();
    let mut dps_unique_map: BTreeMap<i32, Vec<usize>> = BTreeMap::new();
    let mut dps_multi_map: BTreeMap<[i32; 19], Vec<usize>> = BTreeMap::new();
    let mut non_dps_pool: Vec<&'a CharmSpec> = Vec::new();

    let multi_key = |ch: &CharmSpec| {
        [
            ch.size,
            ch.fhr,
            ch.frw,
            ch.fr,
            ch.lr,
            ch.cr,
            ch.pr,
            ch.mf,
            ch.str_bonus,
            ch.dex_bonus,
            ch.all_skills,
            ch.skills,
            ch.action_skills,
            ch.aura_skills,
            ch.ar,
            ch.flat_phys_2x,
            ch.flat_fire_2x,
            ch.flat_elem_2x,
            ch.psn_dps_2x,
        ]
    };

    for (idx, &ch) in pool.iter().enumerate() {
        if is_pure_dps(ch) {
            pure_dps_indices.push(idx);
        } else if is_dps_stat(ch) || matches!(ch.unique_id, Some(u) if dps_uids.contains(&u)) {
            if let Some(uid) = ch.unique_id {
                dps_unique_map.entry(uid).or_default().push(idx);
            } else {
                dps_multi_map.entry(multi_key(ch)).or_default().push(idx);
            }
        } else {
            non_dps_pool.push(ch);
        }
    }

    let (pure_dps, pure_dps_ub_items, overflow) =
        PureDpsSolver::build(pool, &pure_dps_indices, max_slots);
    for idx in overflow {
        dps_multi_map
            .entry(multi_key(pool[idx]))
            .or_default()
            .push(idx);
    }
    let mut dps_groups: Vec<CharmGroup> = Vec::new();
    for (_, mut opts) in dps_unique_map {
        opts.sort_by(|&a, &b| {
            let key_of = |ch: &CharmSpec| {
                (
                    ch.skills_total(),
                    ch.ar,
                    ch.dex_bonus,
                    ch.str_bonus,
                    ch.fr + ch.lr + ch.cr + ch.pr,
                    charm_eff_life(ch, class),
                    charm_eff_mana(ch, class),
                )
            };
            key_of(pool[b]).cmp(&key_of(pool[a]))
        });
        let mut max_pos = StatTotals::default();
        let mut min_neg_res = [0i32; 4];
        let mut min_size = i32::MAX;
        for &i in &opts {
            let ch = pool[i];
            max_pos = max_pos.max_each(StatTotals::from_charm(ch).clamp_non_neg());
            min_neg_res[0] = min_neg_res[0].min(ch.fr.min(0));
            min_neg_res[1] = min_neg_res[1].min(ch.lr.min(0));
            min_neg_res[2] = min_neg_res[2].min(ch.cr.min(0));
            min_neg_res[3] = min_neg_res[3].min(ch.pr.min(0));
            min_size = min_size.min(ch.size.max(1));
        }
        dps_groups.push(CharmGroup::Unique {
            options: opts,
            max_pos,
            min_size,
            min_neg_res,
        });
    }
    for (_, mut members) in dps_multi_map {
        let member_tie = |ch: &CharmSpec| {
            (
                charm_eff_life(ch, class),
                ch.life,
                charm_eff_mana(ch, class),
                ch.mana,
            )
        };
        members.sort_by(|&a, &b| member_tie(pool[b]).cmp(&member_tie(pool[a])));
        let rep = pool[members[0]];
        let size = rep.size.max(1);
        let max_copies = (max_slots / size).max(0) as usize;
        members.truncate(max_copies);
        if !members.is_empty() {
            dps_groups.push(CharmGroup::Multi {
                members,
                size,
                stats: StatTotals::from_charm(rep),
            });
        }
    }
    dps_groups.sort_by_key(|g| {
        let (mv, sz, idx, st) = match g {
            CharmGroup::Unique {
                options,
                max_pos,
                min_size,
                ..
            } => {
                let ch = pool[options[0]];
                (
                    ch.skills_total() * 1000
                        + ch.ar
                        + ch.dex_bonus * 10
                        + ch.str_bonus * 5
                        + ch.flat_phys_2x * 10
                        + ch.flat_fire_2x * 5
                        + ch.flat_elem_2x * 5
                        + ch.psn_dps_2x * 3,
                    (*min_size).max(1),
                    options[0],
                    *max_pos,
                )
            }
            CharmGroup::Multi {
                members,
                size,
                stats,
            } => {
                let ch = pool[members[0]];
                (
                    ch.skills_total() * 1000
                        + ch.ar
                        + ch.dex_bonus * 10
                        + ch.str_bonus * 5
                        + ch.flat_phys_2x * 10
                        + ch.flat_fire_2x * 5
                        + ch.flat_elem_2x * 5
                        + ch.psn_dps_2x * 3,
                    (*size).max(1),
                    members[0],
                    *stats,
                )
            }
        };
        std::cmp::Reverse((
            mv * 1000 / sz,
            st.res.iter().map(|&r| r.max(0)).sum::<i32>() + st.fhr.max(0),
            -sz,
            -(idx as i32),
        ))
    });
    let has_util = |ch: &CharmSpec| {
        ch.life > 0
            || ch.mana > 0
            || ch.vit > 0
            || ch.ene > 0
            || ch.fhr > 0
            || ch.frw > 0
            || ch.mf > 0
            || ch.fr != 0
            || ch.lr != 0
            || ch.cr != 0
            || ch.pr != 0
    };
    let mut dps_group_has_util = Vec::with_capacity(dps_groups.len());
    for g in &dps_groups {
        let indices: &[usize] = match g {
            CharmGroup::Unique { options, .. } => options,
            CharmGroup::Multi { members, .. } => members,
        };
        dps_group_has_util.push(indices.iter().any(|&i| has_util(pool[i])));
    }
    let mut dps_suf_pos = vec![StatTotals::default(); dps_groups.len() + 1];
    let mut dps_suf_neg_res = vec![[0i32; 4]; dps_groups.len() + 1];
    let mut dps_min_size = vec![i32::MAX; dps_groups.len() + 1];
    for i in (0..dps_groups.len()).rev() {
        let gp = dps_groups[i].max_pos_total();
        dps_suf_pos[i] = dps_suf_pos[i + 1].add_scaled(gp, 1);
        let gn = dps_groups[i].min_neg_res();
        for r in 0..4 {
            dps_suf_neg_res[i][r] = dps_suf_neg_res[i + 1][r] + gn[r];
        }
        let g_sz = match &dps_groups[i] {
            CharmGroup::Unique { min_size, .. } => *min_size,
            CharmGroup::Multi { size, .. } => *size,
        };
        dps_min_size[i] = dps_min_size[i + 1].min(g_sz);
    }
    let dps_order_all_skills = sorted_ub_entries(&dps_groups, pool, &[], |ch| ch.all_skills);
    let dps_order_class_skills = sorted_ub_entries(&dps_groups, pool, &[], |ch| ch.skills);
    let dps_order_action_skills = sorted_ub_entries(&dps_groups, pool, &[], |ch| ch.action_skills);
    let dps_order_aura_skills = sorted_ub_entries(&dps_groups, pool, &[], |ch| ch.aura_skills);
    let dps_order_str = sorted_ub_entries(&dps_groups, pool, &[], |ch| ch.str_bonus);
    let dps_order_dex = sorted_ub_entries(&dps_groups, pool, &[], |ch| ch.dex_bonus);
    let dps_order_ar = sorted_ub_entries(&dps_groups, pool, &pure_dps_ub_items, |ch| ch.ar);
    let dps_order_phys =
        sorted_ub_entries(&dps_groups, pool, &pure_dps_ub_items, |ch| ch.flat_phys_2x);
    let dps_order_fire =
        sorted_ub_entries(&dps_groups, pool, &pure_dps_ub_items, |ch| ch.flat_fire_2x);
    let dps_order_elem =
        sorted_ub_entries(&dps_groups, pool, &pure_dps_ub_items, |ch| ch.flat_elem_2x);
    let dps_order_psn =
        sorted_ub_entries(&dps_groups, pool, &pure_dps_ub_items, |ch| ch.psn_dps_2x);
    let dps_order_res = [
        sorted_ub_entries(&dps_groups, pool, &[], |ch| ch.fr),
        sorted_ub_entries(&dps_groups, pool, &[], |ch| ch.lr),
        sorted_ub_entries(&dps_groups, pool, &[], |ch| ch.cr),
        sorted_ub_entries(&dps_groups, pool, &[], |ch| ch.pr),
    ];
    let dps_order_fhr = sorted_ub_entries(&dps_groups, pool, &[], |ch| ch.fhr);
    let dps_order_frw = sorted_ub_entries(&dps_groups, pool, &[], |ch| ch.frw);
    let dps_order_mf = sorted_ub_entries(&dps_groups, pool, &[], |ch| ch.mf);
    let non_dps_solver = Box::new(CharmSolver::new_inner(
        &non_dps_pool,
        c,
        SearchMode::LevelingRes,
        false,
    ));
    let slots_len = (max_slots.max(0) as usize) + 1;
    let nd_res_at: Vec<[i32; 4]> = (0..slots_len)
        .map(|s| {
            let si = s as i32;
            [
                eval_sorted_ub(&non_dps_solver.order_res[0], 0, si),
                eval_sorted_ub(&non_dps_solver.order_res[1], 0, si),
                eval_sorted_ub(&non_dps_solver.order_res[2], 0, si),
                eval_sorted_ub(&non_dps_solver.order_res[3], 0, si),
            ]
        })
        .collect();
    let nd_fhr_at: Vec<i32> = (0..slots_len)
        .map(|s| eval_sorted_ub(&non_dps_solver.order_fhr, 0, s as i32))
        .collect();
    let nd_frw_at: Vec<i32> = (0..slots_len)
        .map(|s| eval_sorted_ub(&non_dps_solver.order_frw, 0, s as i32))
        .collect();
    let nd_mf_at: Vec<i32> = (0..slots_len)
        .map(|s| eval_sorted_ub(&non_dps_solver.order_mf, 0, s as i32))
        .collect();

    DpsIndex {
        dps_groups,
        dps_suf_pos,
        dps_suf_neg_res,
        dps_min_size,
        dps_order_all_skills,
        dps_order_class_skills,
        dps_order_action_skills,
        dps_order_aura_skills,
        dps_order_str,
        dps_order_dex,
        dps_order_ar,
        dps_order_phys,
        dps_order_fire,
        dps_order_elem,
        dps_order_psn,
        dps_order_res,
        dps_order_fhr,
        dps_order_frw,
        dps_order_mf,
        dps_group_has_util,
        pure_dps,
        non_dps_solver: Some(non_dps_solver),
        nd_res_at,
        nd_fhr_at,
        nd_frw_at,
        nd_mf_at,
    }
}
