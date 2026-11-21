use std::collections::{BTreeMap, HashMap, HashSet};

use crate::eval::{eval_build_summary, res_caps, EvalSummary};
use crate::search::{score_eval_summary, BuildScore};
#[cfg(test)]
use crate::types::{compute_effective_gear_stats, ItemSpec};
use crate::types::{
    BuildConstraints, CharClass, CharmSpec, HandWeapon, OffenseProfile, SearchMode, Stats,
    BASE_MAX_RES,
};

fn is_res_mode(mode: SearchMode) -> bool {
    matches!(mode, SearchMode::MaxRes | SearchMode::LevelingRes)
}

fn res_opt_caps(caps: [i32; 4], mode: SearchMode) -> [i32; 4] {
    match mode {
        SearchMode::MaxRes => caps,
        SearchMode::LevelingRes | SearchMode::Leveling => [
            caps[0].min(BASE_MAX_RES),
            caps[1].min(BASE_MAX_RES),
            caps[2].min(BASE_MAX_RES),
            caps[3].min(BASE_MAX_RES),
        ],
        _ => [0; 4],
    }
}

struct CharmState<'a, 'b> {
    pool: &'b [&'a CharmSpec],
    rem: Vec<bool>,
    used: i32,
    max_slots: i32,
    cur_fhr: i32,
    cur_res: [i32; 4],
    cur_str: i32,
    cur_dex: i32,
    cur_frw: i32,
    cur_mf: i32,
    chosen_indices: Vec<usize>,
    unique_ids: HashSet<i32>,
}

impl<'a, 'b> CharmState<'a, 'b> {
    #[allow(clippy::too_many_arguments)]
    fn new(
        pool: &'b [&'a CharmSpec],
        max_slots: i32,
        cur_fhr: i32,
        cur_res: [i32; 4],
        cur_str: i32,
        cur_dex: i32,
        cur_frw: i32,
        cur_mf: i32,
    ) -> Self {
        Self {
            pool,
            rem: vec![true; pool.len()],
            used: 0,
            max_slots,
            cur_fhr,
            cur_res,
            cur_str,
            cur_dex,
            cur_frw,
            cur_mf,
            chosen_indices: Vec::new(),
            unique_ids: HashSet::new(),
        }
    }

    fn can_pick(&self, idx: usize) -> bool {
        let c = self.pool[idx];
        self.rem[idx]
            && self.used + c.size <= self.max_slots
            && !matches!(c.unique_id, Some(uid) if self.unique_ids.contains(&uid))
    }

    fn preserves_res_targets(&self, idx: usize, targets: [i32; 4]) -> bool {
        let c = self.pool[idx];
        let deltas = [c.fr, c.lr, c.cr, c.pr];
        (0..4).all(|i| self.cur_res[i] < targets[i] || self.cur_res[i] + deltas[i] >= targets[i])
    }

    fn preserves_res_sum(&self, idx: usize, caps: [i32; 4]) -> bool {
        let c = self.pool[idx];
        let deltas = [c.fr, c.lr, c.cr, c.pr];
        let before: i32 = (0..4).map(|i| self.cur_res[i].min(caps[i])).sum();
        let after: i32 = (0..4)
            .map(|i| (self.cur_res[i] + deltas[i]).min(caps[i]))
            .sum();
        after >= before
    }

    fn pick(&mut self, idx: usize) {
        let c = self.pool[idx];
        self.rem[idx] = false;
        self.used += c.size;
        self.cur_str += c.str_bonus;
        self.cur_dex += c.dex_bonus;
        self.cur_fhr += c.fhr;
        self.cur_frw += c.frw;
        self.cur_mf += c.mf;
        self.cur_res[0] += c.fr;
        self.cur_res[1] += c.lr;
        self.cur_res[2] += c.cr;
        self.cur_res[3] += c.pr;
        if let Some(uid) = c.unique_id {
            self.unique_ids.insert(uid);
        }
        self.chosen_indices.push(idx);
    }
}

fn charm_eff_life(ch: &CharmSpec, class: CharClass) -> i32 {
    ch.life + class.life_per_vit(ch.vit)
}

fn charm_eff_mana(ch: &CharmSpec, class: CharClass) -> i32 {
    ch.mana + class.mana_per_ene(ch.ene)
}

fn greedy_res_loop(
    state: &mut CharmState<'_, '_>,
    targets: [i32; 4],
    weights: [f64; 4],
    mf_weight: f64,
    skill_weight: f64,
    class: CharClass,
) {
    loop {
        let deficits = [
            (targets[0] - state.cur_res[0]).max(0),
            (targets[1] - state.cur_res[1]).max(0),
            (targets[2] - state.cur_res[2]).max(0),
            (targets[3] - state.cur_res[3]).max(0),
        ];
        if deficits.iter().sum::<i32>() == 0 {
            break;
        }
        let mut best_idx = None;
        let mut best_score = 0.0_f64;
        for (idx, c) in state.pool.iter().enumerate() {
            if !state.can_pick(idx) {
                continue;
            }
            let gain = (deficits[0].min(c.fr) as f64) * weights[0]
                + (deficits[1].min(c.lr) as f64) * weights[1]
                + (deficits[2].min(c.cr) as f64) * weights[2]
                + (deficits[3].min(c.pr) as f64) * weights[3];
            if gain > 0.0 {
                let tie_bonus = c.mf as f64 * mf_weight + c.skills_total() as f64 * skill_weight;
                let score = (gain + tie_bonus + charm_eff_life(c, class) as f64 * 0.02)
                    / c.size.max(1) as f64;
                if score > best_score {
                    best_score = score;
                    best_idx = Some(idx);
                }
            }
        }
        match best_idx {
            Some(idx) => state.pick(idx),
            None => break,
        }
    }
}

pub(crate) fn charm_stat_ub(
    pool: &[&CharmSpec],
    max_slots: i32,
    extract: impl Fn(&CharmSpec) -> i32,
) -> i32 {
    let mut rem_slots = max_slots.max(0);
    if rem_slots == 0 {
        return 0;
    }
    let mut best_unique: BTreeMap<i32, (i32, i32)> = BTreeMap::new();
    let mut entries: Vec<(i32, i32)> = Vec::new();
    let mut ub = 0;
    let mut push_entry = |val: i32, size: i32| {
        if size <= 0 {
            ub += val;
        } else {
            entries.push((val, size));
        }
    };
    for &ch in pool {
        let val = extract(ch);
        if val <= 0 {
            continue;
        }
        if let Some(uid) = ch.unique_id {
            best_unique
                .entry(uid)
                .and_modify(|e| {
                    if val > e.0 {
                        *e = (val, ch.size);
                    }
                })
                .or_insert((val, ch.size));
        } else {
            push_entry(val, ch.size);
        }
    }
    for (val, size) in best_unique.into_values() {
        push_entry(val, size);
    }
    entries.sort_by(|a, b| (b.0 as i64 * a.1 as i64).cmp(&(a.0 as i64 * b.1 as i64)));
    for (val, sz) in entries {
        if sz <= rem_slots {
            ub += val;
            rem_slots -= sz;
        } else if rem_slots > 0 {
            ub += (val * rem_slots + sz - 1) / sz;
            break;
        }
    }
    ub
}

fn greedy_fhr_loop(state: &mut CharmState<'_, '_>, target_fhr: i32) {
    while state.cur_fhr < target_fhr {
        let need = target_fhr - state.cur_fhr;
        let mut best_idx = None;
        let mut best_key = (-1.0_f64, -1, -1);
        for (idx, c) in state.pool.iter().enumerate() {
            if state.can_pick(idx) && c.fhr > 0 {
                let key = (
                    c.fhr.min(need) as f64 / c.size.max(1) as f64,
                    c.skills_total(),
                    c.fhr,
                );
                if key > best_key {
                    best_key = key;
                    best_idx = Some(idx);
                }
            }
        }
        match best_idx {
            Some(idx) => state.pick(idx),
            None => break,
        }
    }
}

fn greedy_frw_loop(state: &mut CharmState<'_, '_>, target_frw: i32) {
    while state.cur_frw < target_frw {
        let need = target_frw - state.cur_frw;
        let mut best_idx = None;
        let mut best_key = (-1.0_f64, -1, -1);
        for (idx, c) in state.pool.iter().enumerate() {
            if state.can_pick(idx) && c.frw > 0 {
                let key = (
                    c.frw.min(need) as f64 / c.size.max(1) as f64,
                    c.skills_total(),
                    c.frw,
                );
                if key > best_key {
                    best_key = key;
                    best_idx = Some(idx);
                }
            }
        }
        match best_idx {
            Some(idx) => state.pick(idx),
            None => break,
        }
    }
}

fn greedy_mf_loop(state: &mut CharmState<'_, '_>, target_mf: i32) {
    while state.cur_mf < target_mf {
        let need = target_mf - state.cur_mf;
        let mut best_idx = None;
        let mut best_key = (-1.0_f64, -1, -1);
        for (idx, c) in state.pool.iter().enumerate() {
            if state.can_pick(idx) && c.mf > 0 {
                let key = (
                    c.mf.min(need) as f64 / c.size.max(1) as f64,
                    c.skills_total(),
                    c.mf,
                );
                if key > best_key {
                    best_key = key;
                    best_idx = Some(idx);
                }
            }
        }
        match best_idx {
            Some(idx) => state.pick(idx),
            None => break,
        }
    }
}

fn greedy_fill_remaining(
    state: &mut CharmState<'_, '_>,
    caps: [i32; 4],
    res_targets: [i32; 4],
    mode: SearchMode,
    class: CharClass,
    include_stats_tail: bool,
) {
    let pool = state.pool;
    let mut mf_indices: Vec<usize> = (0..pool.len())
        .filter(|&i| state.can_pick(i) && pool[i].mf > 0)
        .collect();
    mf_indices.sort_by(|&a, &b| {
        let ka = (
            pool[a].mf * 100 / pool[a].size.max(1),
            pool[a].skills_total(),
            pool[a].lr,
        );
        let kb = (
            pool[b].mf * 100 / pool[b].size.max(1),
            pool[b].skills_total(),
            pool[b].lr,
        );
        kb.cmp(&ka)
    });

    let mut sk_indices: Vec<usize> = (0..pool.len())
        .filter(|&i| state.can_pick(i) && pool[i].skills_total() > 0)
        .collect();
    sk_indices.sort_by(|&a, &b| {
        let ca = pool[a];
        let cb = pool[b];
        let eff =
            (cb.skills_total() * ca.size.max(1)).cmp(&(ca.skills_total() * cb.size.max(1)));
        eff.then_with(|| {
            (
                cb.skills_total(),
                cb.all_skills,
                charm_eff_life(cb, class),
                cb.fr + cb.lr + cb.cr,
                charm_eff_mana(cb, class),
            )
                .cmp(&(
                    ca.skills_total(),
                    ca.all_skills,
                    charm_eff_life(ca, class),
                    ca.fr + ca.lr + ca.cr,
                    charm_eff_mana(ca, class),
                ))
        })
    });

    let opt_caps = res_opt_caps(caps, mode);
    let pick_ordered = |state: &mut CharmState<'_, '_>, indices: Vec<usize>| {
        for idx in indices {
            if state.can_pick(idx)
                && state.preserves_res_targets(idx, res_targets)
                && (!is_res_mode(mode) || state.preserves_res_sum(idx, opt_caps))
            {
                state.pick(idx);
            }
        }
    };

    if mode == SearchMode::Mf {
        pick_ordered(state, mf_indices);
        pick_ordered(state, sk_indices);
    } else {
        pick_ordered(state, sk_indices);
    }

    if !include_stats_tail {
        return;
    }

    if mode == SearchMode::Leveling {
        greedy_res_loop(
            state,
            res_opt_caps(caps, mode),
            [1.0, 1.0, 1.0, 1.0],
            0.0,
            0.2,
            class,
        );
    }

    let preserve_res_caps = is_res_mode(mode) || mode == SearchMode::Leveling;
    loop {
        let mut best_idx = None;
        let mut best_score = 0.0_f64;
        for (idx, c) in pool.iter().enumerate() {
            if !state.can_pick(idx)
                || !state.preserves_res_targets(idx, res_targets)
                || (preserve_res_caps && !state.preserves_res_sum(idx, opt_caps))
            {
                continue;
            }
            let mut s = charm_eff_life(c, class) as f64
                + charm_eff_mana(c, class) as f64 * 0.4
                + (caps[3] - state.cur_res[3]).max(0).min(c.pr) as f64 * 1.2;
            if matches!(mode, SearchMode::Leveling | SearchMode::LevelingRes) {
                // Only use +AR/+Dex as tiny tie-break in free filler slots so it never displaces
                // life/FRW/res; actual DPS-bucket tradeoffs are solved in `improve_for_dps`.
                s += c.frw as f64 * 1.5 + (c.ar + c.dex_bonus * 5) as f64 * 1e-4;
            }
            if state.cur_res[0] < caps[0] {
                s += (caps[0] - state.cur_res[0]).min(c.fr) as f64 * 2.0;
            }
            if state.cur_res[1] < caps[1] {
                s += (caps[1] - state.cur_res[1]).min(c.lr) as f64 * 2.0;
            }
            if state.cur_res[2] < caps[2] {
                s += (caps[2] - state.cur_res[2]).min(c.cr) as f64 * 1.5;
            }
            s /= c.size.max(1) as f64;
            if s > best_score {
                best_score = s;
                best_idx = Some(idx);
            }
        }
        match best_idx {
            Some(idx) => state.pick(idx),
            None => break,
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn greedy_charms_pass_indices(
    leaf: Stats,
    pool: &[&CharmSpec],
    c: &BuildConstraints,
    reqs: (i32, i32),
    mode: SearchMode,
    fhr_first: bool,
    slot_budget: i32,
    forbidden_uid: Option<i32>,
    include_stats_tail: bool,
) -> Option<Vec<usize>> {
    let (cap_fr, cap_lr, cap_cr, cap_pr) = res_caps(leaf, c);
    if c.min_fr > cap_fr || c.min_lr > cap_lr || c.min_cr > cap_cr || c.min_pr > cap_pr {
        return None;
    }
    let caps = [cap_fr, cap_lr, cap_cr, cap_pr];
    if slot_budget < 0 {
        return None;
    }
    let mut state = CharmState::new(
        pool,
        slot_budget,
        leaf.fhr,
        [leaf.fr, leaf.lr, leaf.cr, leaf.pr],
        leaf.str_bonus,
        leaf.dex_bonus,
        leaf.frw,
        leaf.mf,
    );
    if let Some(uid) = forbidden_uid {
        state.unique_ids.insert(uid);
    }

    let (req_str_target, req_dex_target) = reqs;
    while state.cur_str < req_str_target || state.cur_dex < req_dex_target {
        let need_str = (req_str_target - state.cur_str).max(0);
        let need_dex = (req_dex_target - state.cur_dex).max(0);
        let mut best_idx = None;
        let mut best_key = 0.0_f64;
        for (idx, ch) in pool.iter().enumerate() {
            if !state.can_pick(idx) {
                continue;
            }
            let gain = need_str.min(ch.str_bonus) + need_dex.min(ch.dex_bonus);
            if gain > 0 {
                let score = (gain as f64 + ch.skills_total() as f64 * 0.1) / ch.size.max(1) as f64;
                if score > best_key {
                    best_key = score;
                    best_idx = Some(idx);
                }
            }
        }
        match best_idx {
            Some(idx) => state.pick(idx),
            None => break,
        }
    }
    if state.cur_str < req_str_target || state.cur_dex < req_dex_target {
        return None;
    }

    let (mf_w, sk_w) = match mode {
        SearchMode::Mf => (0.05, 0.02),
        _ => (0.0, 0.2),
    };
    let class = CharClass::from_id_or_default(c.char_class);
    let res_targets = [c.min_fr, c.min_lr, c.min_cr, c.min_pr];
    if fhr_first {
        greedy_fhr_loop(&mut state, c.min_fhr);
        greedy_res_loop(&mut state, res_targets, [1.5, 1.5, 1.2, 1.0], mf_w, sk_w, class);
    } else {
        greedy_res_loop(&mut state, res_targets, [1.5, 1.5, 1.2, 1.0], mf_w, sk_w, class);
        greedy_fhr_loop(&mut state, c.min_fhr);
    }
    if c.min_frw > 0 {
        greedy_frw_loop(&mut state, c.min_frw);
    }
    if c.min_mf > 0 {
        greedy_mf_loop(&mut state, c.min_mf);
    }

    if is_res_mode(mode) {
        greedy_res_loop(
            &mut state,
            res_opt_caps(caps, mode),
            [1.0, 1.0, 1.0, 1.0],
            0.0,
            0.2,
            class,
        );
    }

    greedy_fill_remaining(
        &mut state,
        caps,
        res_targets,
        mode,
        class,
        include_stats_tail,
    );

    if state.cur_fhr < c.min_fhr
        || state.cur_frw < c.min_frw
        || state.cur_mf < c.min_mf
        || state.cur_res[0] < c.min_fr
        || state.cur_res[1] < c.min_lr
        || state.cur_res[2] < c.min_cr
        || state.cur_res[3] < c.min_pr
    {
        return None;
    }

    Some(state.chosen_indices)
}

#[cfg(test)]
fn greedy_charms_pass<'a>(
    items: &[&ItemSpec],
    pool: &[&'a CharmSpec],
    c: &BuildConstraints,
    reqs: (i32, i32),
    mode: SearchMode,
    fhr_first: bool,
) -> Option<Vec<&'a CharmSpec>> {
    let (gear, _) = compute_effective_gear_stats(items);
    let leaf = Stats {
        fr: gear.fr + c.base_hell_res,
        lr: gear.lr + c.base_hell_res,
        cr: gear.cr + c.base_hell_res,
        pr: gear.pr + c.base_hell_res,
        str_bonus: gear.str_bonus + c.base_str,
        dex_bonus: gear.dex_bonus + c.base_dex,
        ..gear
    };
    greedy_charms_pass_indices(
        leaf,
        pool,
        c,
        reqs,
        mode,
        fhr_first,
        c.max_charm_slots,
        None,
        true,
    )
    .map(|idxs| idxs.into_iter().map(|i| pool[i]).collect())
}

#[cfg(test)]
pub(crate) fn greedy_charms<'a>(
    items: &[&ItemSpec],
    pool: &[&'a CharmSpec],
    c: &BuildConstraints,
    reqs: (i32, i32),
    mode: SearchMode,
) -> Option<Vec<&'a CharmSpec>> {
    for fhr_first in [true, false] {
        if let Some(chosen) = greedy_charms_pass(items, pool, c, reqs, mode, fhr_first) {
            return Some(chosen);
        }
    }
    None
}

#[allow(clippy::too_many_arguments)]
fn greedy_charms_indices(
    leaf: Stats,
    pool: &[&CharmSpec],
    c: &BuildConstraints,
    reqs: (i32, i32),
    mode: SearchMode,
    slot_budget: i32,
    forbidden_uid: Option<i32>,
    include_stats_tail: bool,
) -> Option<Vec<usize>> {
    for fhr_first in [true, false] {
        if let Some(chosen) = greedy_charms_pass_indices(
            leaf,
            pool,
            c,
            reqs,
            mode,
            fhr_first,
            slot_budget,
            forbidden_uid,
            include_stats_tail,
        ) {
            return Some(chosen);
        }
    }
    None
}

fn charm_dominates(a: &CharmSpec, b: &CharmSpec, a_idx: usize, b_idx: usize) -> bool {
    if (!a.cold_sunder && b.cold_sunder)
        || a.size > b.size
        || a.fhr < b.fhr
        || a.fr < b.fr
        || a.lr < b.lr
        || a.cr < b.cr
        || a.pr < b.pr
        || a.mf < b.mf
        || a.life < b.life
        || a.mana < b.mana
        || a.vit < b.vit
        || a.ene < b.ene
        || a.ar < b.ar
        || a.flat_phys_2x < b.flat_phys_2x
        || a.flat_fire_2x < b.flat_fire_2x
        || a.flat_elem_2x < b.flat_elem_2x
        || a.psn_dps_2x < b.psn_dps_2x
        || a.frw < b.frw
        || a.str_bonus < b.str_bonus
        || a.dex_bonus < b.dex_bonus
        || a.general_skills() < b.general_skills()
        || a.all_skills < b.all_skills
        || a.action_skills < b.action_skills
        || a.aura_skills < b.aura_skills
    {
        return false;
    }
    let strictly_better = (a.cold_sunder && !b.cold_sunder)
        || a.size < b.size
        || a.fhr > b.fhr
        || a.fr > b.fr
        || a.lr > b.lr
        || a.cr > b.cr
        || a.pr > b.pr
        || a.mf > b.mf
        || a.life > b.life
        || a.mana > b.mana
        || a.vit > b.vit
        || a.ene > b.ene
        || a.ar > b.ar
        || a.flat_phys_2x > b.flat_phys_2x
        || a.flat_fire_2x > b.flat_fire_2x
        || a.flat_elem_2x > b.flat_elem_2x
        || a.psn_dps_2x > b.psn_dps_2x
        || a.frw > b.frw
        || a.str_bonus > b.str_bonus
        || a.dex_bonus > b.dex_bonus
        || a.general_skills() > b.general_skills()
        || a.all_skills > b.all_skills
        || a.action_skills > b.action_skills
        || a.aura_skills > b.aura_skills;
    strictly_better || a_idx < b_idx
}

pub(crate) fn shrink_charm_pool<'a>(pool: &[&'a CharmSpec], max_slots: i32) -> Vec<&'a CharmSpec> {
    let max_slots = max_slots.max(0);
    let mut kept = Vec::with_capacity(pool.len());
    for (bi, &b) in pool.iter().enumerate() {
        if b.size > max_slots {
            continue;
        }
        let dom_cap = match b.unique_id {
            Some(_) => 1,
            None => (max_slots / b.size.max(1)).max(1) as usize,
        };
        let dom_count = pool
            .iter()
            .enumerate()
            .filter(|&(ai, &a)| {
                ai != bi
                    && a.unique_id == b.unique_id
                    && a.size <= max_slots
                    && charm_dominates(a, b, ai, bi)
            })
            .take(dom_cap)
            .count();
        if dom_count < dom_cap {
            kept.push(b);
        }
    }
    kept
}

fn shrink_sunder_pool<'a>(
    raw_sunders: &[&'a CharmSpec],
    non_sunder_uids: &HashSet<i32>,
) -> Vec<&'a CharmSpec> {
    let mut kept = Vec::with_capacity(raw_sunders.len());
    for (bi, &b) in raw_sunders.iter().enumerate() {
        let uid_isolated = !matches!(b.unique_id, Some(u) if non_sunder_uids.contains(&u));
        let dominated = raw_sunders.iter().enumerate().any(|(ai, &a)| {
            ai != bi
                && (a.unique_id == b.unique_id || uid_isolated)
                && charm_dominates(a, b, ai, bi)
        });
        if !dominated {
            kept.push(b);
        }
    }
    kept
}

#[derive(Clone, Copy, Default)]
struct StatTotals {
    str_bonus: i32,
    dex_bonus: i32,
    fhr: i32,
    frw: i32,
    res: [i32; 4],
    skills: i32,
    all_skills: i32,
    class_skills: i32,
    general_skills: i32,
    action_skills: i32,
    aura_skills: i32,
    mf: i32,
    ar: i32,
    flat_phys_2x: i32,
    flat_fire_2x: i32,
    flat_elem_2x: i32,
    psn_dps_2x: i32,
}

impl StatTotals {
    fn from_charm(c: &CharmSpec) -> Self {
        Self {
            str_bonus: c.str_bonus,
            dex_bonus: c.dex_bonus,
            fhr: c.fhr,
            frw: c.frw,
            res: [c.fr, c.lr, c.cr, c.pr],
            skills: c.skills_total(),
            all_skills: c.all_skills,
            class_skills: c.skills,
            general_skills: c.general_skills(),
            action_skills: c.action_skills,
            aura_skills: c.aura_skills,
            mf: c.mf,
            ar: c.ar,
            flat_phys_2x: c.flat_phys_2x,
            flat_fire_2x: c.flat_fire_2x,
            flat_elem_2x: c.flat_elem_2x,
            psn_dps_2x: c.psn_dps_2x,
        }
    }

    fn max_each(self, o: Self) -> Self {
        Self {
            str_bonus: self.str_bonus.max(o.str_bonus),
            dex_bonus: self.dex_bonus.max(o.dex_bonus),
            fhr: self.fhr.max(o.fhr),
            frw: self.frw.max(o.frw),
            res: [
                self.res[0].max(o.res[0]),
                self.res[1].max(o.res[1]),
                self.res[2].max(o.res[2]),
                self.res[3].max(o.res[3]),
            ],
            skills: self.skills.max(o.skills),
            all_skills: self.all_skills.max(o.all_skills),
            class_skills: self.class_skills.max(o.class_skills),
            general_skills: self.general_skills.max(o.general_skills),
            action_skills: self.action_skills.max(o.action_skills),
            aura_skills: self.aura_skills.max(o.aura_skills),
            mf: self.mf.max(o.mf),
            ar: self.ar.max(o.ar),
            flat_phys_2x: self.flat_phys_2x.max(o.flat_phys_2x),
            flat_fire_2x: self.flat_fire_2x.max(o.flat_fire_2x),
            flat_elem_2x: self.flat_elem_2x.max(o.flat_elem_2x),
            psn_dps_2x: self.psn_dps_2x.max(o.psn_dps_2x),
        }
    }

    fn clamp_non_neg(self) -> Self {
        Self {
            str_bonus: self.str_bonus.max(0),
            dex_bonus: self.dex_bonus.max(0),
            fhr: self.fhr.max(0),
            frw: self.frw.max(0),
            res: [
                self.res[0].max(0),
                self.res[1].max(0),
                self.res[2].max(0),
                self.res[3].max(0),
            ],
            skills: self.skills.max(0),
            all_skills: self.all_skills.max(0),
            class_skills: self.class_skills.max(0),
            general_skills: self.general_skills.max(0),
            action_skills: self.action_skills.max(0),
            aura_skills: self.aura_skills.max(0),
            mf: self.mf.max(0),
            ar: self.ar.max(0),
            flat_phys_2x: self.flat_phys_2x.max(0),
            flat_fire_2x: self.flat_fire_2x.max(0),
            flat_elem_2x: self.flat_elem_2x.max(0),
            psn_dps_2x: self.psn_dps_2x.max(0),
        }
    }

    fn add_scaled(self, o: Self, k: i32) -> Self {
        Self {
            str_bonus: self.str_bonus + o.str_bonus * k,
            dex_bonus: self.dex_bonus + o.dex_bonus * k,
            fhr: self.fhr + o.fhr * k,
            frw: self.frw + o.frw * k,
            res: [
                self.res[0] + o.res[0] * k,
                self.res[1] + o.res[1] * k,
                self.res[2] + o.res[2] * k,
                self.res[3] + o.res[3] * k,
            ],
            skills: self.skills + o.skills * k,
            all_skills: self.all_skills + o.all_skills * k,
            class_skills: self.class_skills + o.class_skills * k,
            general_skills: self.general_skills + o.general_skills * k,
            action_skills: self.action_skills + o.action_skills * k,
            aura_skills: self.aura_skills + o.aura_skills * k,
            mf: self.mf + o.mf * k,
            ar: self.ar + o.ar * k,
            flat_phys_2x: self.flat_phys_2x + o.flat_phys_2x * k,
            flat_fire_2x: self.flat_fire_2x + o.flat_fire_2x * k,
            flat_elem_2x: self.flat_elem_2x + o.flat_elem_2x * k,
            psn_dps_2x: self.psn_dps_2x + o.psn_dps_2x * k,
        }
    }
}

#[derive(Clone)]
enum CharmGroup {
    Unique {
        options: Vec<usize>,
        max_pos: StatTotals,
        min_size: i32,
        min_neg_res: [i32; 4],
    },
    Multi {
        members: Vec<usize>,
        size: i32,
        stats: StatTotals,
    },
}

impl CharmGroup {
    fn max_pos_total(&self) -> StatTotals {
        match self {
            CharmGroup::Unique { max_pos, .. } => *max_pos,
            CharmGroup::Multi { members, stats, .. } => {
                StatTotals::default().add_scaled(stats.clamp_non_neg(), members.len() as i32)
            }
        }
    }

    fn min_neg_res(&self) -> [i32; 4] {
        match self {
            CharmGroup::Unique { min_neg_res, .. } => *min_neg_res,
            CharmGroup::Multi { members, stats, .. } => {
                let k = members.len() as i32;
                [
                    stats.res[0].min(0) * k,
                    stats.res[1].min(0) * k,
                    stats.res[2].min(0) * k,
                    stats.res[3].min(0) * k,
                ]
            }
        }
    }

    fn ub_entry_with_pool(
        &self,
        pool: &[&CharmSpec],
        extract: impl Fn(&CharmSpec) -> i32,
    ) -> Option<(i32, i32, i32)> {
        match self {
            CharmGroup::Unique {
                options, min_size, ..
            } => {
                let max_val = options.iter().map(|&i| extract(pool[i])).max().unwrap_or(0);
                if max_val > 0 {
                    Some((max_val, *min_size, 1))
                } else {
                    None
                }
            }
            CharmGroup::Multi { members, size, .. } => {
                let val = extract(pool[members[0]]);
                if val > 0 {
                    Some((val, *size, members.len() as i32))
                } else {
                    None
                }
            }
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Hash)]
struct CharmCacheKey {
    sunder_idx: usize,
    slot_budget: i32,
    need_str: i32,
    need_dex: i32,
    need_fhr: i32,
    need_frw: i32,
    need_mf: i32,
    delta_res: [i32; 4],
    room: [i32; 4],
}

#[derive(Clone, Default)]
struct PureAxisDp {
    best_gain: Vec<i32>,
    best_picks: Vec<Vec<usize>>,
    max_gain: i32,
}

impl PureAxisDp {
    fn build(items: &[(usize, &CharmSpec, i32)], max_slots: i32, class: CharClass) -> Self {
        if items.is_empty() {
            return Self {
                best_gain: vec![0],
                best_picks: vec![Vec::new()],
                max_gain: 0,
            };
        }
        let cap = max_slots.max(0) as usize;
        let mut best_gain = vec![0i32; cap + 1];
        let mut best_tie = vec![(0i32, 0i32, 0i32, 0i32, 0i32, 0i32); cap + 1];
        let mut best_picks = vec![Vec::new(); cap + 1];

        for &(idx, ch, val) in items {
            let sz = ch.size as usize;
            if val <= 0 || sz == 0 || sz > cap {
                continue;
            }
            for s in (sz..=cap).rev() {
                let cand_gain = best_gain[s - sz] + val;
                let prev_tie = best_tie[s - sz];
                let cand_tie = (
                    prev_tie.0 + ch.skills_total(),
                    prev_tie.1 + ch.all_skills,
                    prev_tie.2 + charm_eff_life(ch, class),
                    prev_tie.3 + charm_eff_mana(ch, class),
                    prev_tie.4 + ch.frw,
                    prev_tie.5 + ch.ar,
                );
                if (cand_gain, cand_tie) > (best_gain[s], best_tie[s]) {
                    best_gain[s] = cand_gain;
                    best_tie[s] = cand_tie;
                    let mut picks = best_picks[s - sz].clone();
                    picks.push(idx);
                    best_picks[s] = picks;
                }
            }
        }

        for s in 1..=cap {
            if (best_gain[s - 1], best_tie[s - 1]) > (best_gain[s], best_tie[s]) {
                best_gain[s] = best_gain[s - 1];
                best_tie[s] = best_tie[s - 1];
                best_picks[s] = best_picks[s - 1].clone();
            }
        }

        let max_gain = best_gain[cap];
        Self {
            best_gain,
            best_picks,
            max_gain,
        }
    }

    #[inline]
    fn min_slots_for(&self, need: i32) -> Option<usize> {
        if need <= 0 {
            return Some(0);
        }
        if need > self.max_gain {
            return None;
        }
        Some(self.best_gain.partition_point(|&g| g < need))
    }

    #[inline]
    fn gain_at(&self, slots: i32) -> i32 {
        let s = slots.max(0) as usize;
        if s < self.best_gain.len() {
            self.best_gain[s]
        } else {
            self.max_gain
        }
    }
}

#[derive(Clone, Copy)]
struct UbGroupEntry {
    g_idx: usize,
    val: i32,
    size: i32,
    count: i32,
}

fn sorted_ub_entries(
    groups: &[CharmGroup],
    pool: &[&CharmSpec],
    pure_axis_items: &[(usize, &CharmSpec, i32)],
    extract: impl Fn(&CharmSpec) -> i32,
) -> Vec<UbGroupEntry> {
    let mut out = Vec::new();
    for (g_idx, g) in groups.iter().enumerate() {
        if let Some((val, size, count)) = g.ub_entry_with_pool(pool, &extract) {
            out.push(UbGroupEntry {
                g_idx,
                val,
                size,
                count,
            });
        }
    }
    if !pure_axis_items.is_empty() {
        let mut by_val_size: BTreeMap<(i32, i32), i32> = BTreeMap::new();
        for &(idx, _, _) in pure_axis_items {
            let ch = pool[idx];
            let val = extract(ch);
            if val > 0 {
                *by_val_size.entry((val, ch.size.max(1))).or_insert(0) += 1;
            }
        }
        for ((val, size), count) in by_val_size {
            out.push(UbGroupEntry {
                g_idx: usize::MAX,
                val,
                size,
                count,
            });
        }
    }
    out.sort_by(|a, b| (b.val as i64 * a.size as i64).cmp(&(a.val as i64 * b.size as i64)));
    out
}

fn eval_sorted_ub(entries: &[UbGroupEntry], min_g_idx: usize, mut rem_slots: i32) -> i32 {
    if rem_slots <= 0 {
        return 0;
    }
    let mut ub = 0;
    for e in entries {
        if e.g_idx < min_g_idx {
            continue;
        }
        if e.size <= 0 {
            ub += e.val * e.count;
            continue;
        }
        let max_take = (rem_slots / e.size).min(e.count);
        if max_take > 0 {
            ub += e.val * max_take;
            rem_slots -= max_take * e.size;
        }
        if rem_slots > 0 && max_take < e.count {
            ub += (e.val * rem_slots + e.size - 1) / e.size;
            break;
        }
        if rem_slots == 0 {
            break;
        }
    }
    ub
}

pub(crate) struct CharmSolver<'a> {
    pub(crate) pool: Vec<&'a CharmSpec>,
    sunder_opts: Vec<&'a CharmSpec>,
    c: &'a BuildConstraints,
    mode: SearchMode,
    class: CharClass,
    raw_max_slots: i32,
    max_slots: i32,
    sum_neg: [i32; 4],
    ub_str: i32,
    ub_dex: i32,
    ub_fhr: i32,
    ub_frw: i32,
    ub_res: [i32; 4],
    ub_all_skills: i32,
    ub_class_skills: i32,
    ub_action_skills: i32,
    ub_aura_skills: i32,
    ub_mf: i32,
    ub_ar: i32,
    ub_flat_phys_2x: i32,
    ub_flat_fire_2x: i32,
    ub_flat_elem_2x: i32,
    ub_psn_dps_2x: i32,
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
    cache: HashMap<CharmCacheKey, Option<(i32, Vec<usize>)>>,
    failed_floor: HashMap<CharmCacheKey, i32>,
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
    pure_ar_dp: PureAxisDp,
    non_dps_solver: Option<Box<CharmSolver<'a>>>,
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
        let main_val_of = |ch: &CharmSpec| -> i32 {
            match mode {
                SearchMode::Power | SearchMode::Leveling => ch.skills_total().max(0),
                SearchMode::Mf => ch.mf.max(0),
                SearchMode::MaxRes | SearchMode::LevelingRes => {
                    ch.fr.max(0) + ch.lr.max(0) + ch.cr.max(0) + ch.pr.max(0)
                }
            }
        };

        let class = CharClass::from_id_or_default(c.char_class);
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

        let order_str = sorted_ub_entries(&groups, &pool, &pure_items[0], |ch| ch.str_bonus);
        let order_dex = sorted_ub_entries(&groups, &pool, &pure_items[1], |ch| ch.dex_bonus);
        let order_fhr = sorted_ub_entries(&groups, &pool, &pure_items[2], |ch| ch.fhr);
        let order_frw = sorted_ub_entries(&groups, &pool, &pure_items[7], |ch| ch.frw);
        let order_res = [
            sorted_ub_entries(&groups, &pool, &pure_items[3], |ch| ch.fr),
            sorted_ub_entries(&groups, &pool, &pure_items[4], |ch| ch.lr),
            sorted_ub_entries(&groups, &pool, &pure_items[5], |ch| ch.cr),
            sorted_ub_entries(&groups, &pool, &pure_items[6], |ch| ch.pr),
        ];
        let order_res_total = sorted_ub_entries(&groups, &pool, &[], |ch| {
            ch.fr.max(0) + ch.lr.max(0) + ch.cr.max(0) + ch.pr.max(0)
        });
        let order_skills = sorted_ub_entries(&groups, &pool, &[], |ch| ch.skills_total());
        let order_mf = sorted_ub_entries(&groups, &pool, &pure_items[8], |ch| ch.mf);

        let (
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
            pure_ar_dp,
            non_dps_solver,
        ) =
            if build_dps_refiner
                && matches!(mode, SearchMode::Leveling | SearchMode::LevelingRes)
                && OffenseProfile::parse(&c.offense, class).is_ok_and(|o| o.uses_dps_tables(c))
            {
                let is_pure_ar = |ch: &CharmSpec| {
                    ch.ar > 0
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
                        && ch.flat_phys_2x == 0
                        && ch.flat_fire_2x == 0
                        && ch.flat_elem_2x == 0
                        && ch.psn_dps_2x == 0
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

                let mut pure_ar_items: Vec<(usize, &CharmSpec, i32)> = Vec::new();
                let mut dps_unique_map: BTreeMap<i32, Vec<usize>> = BTreeMap::new();
                let mut dps_multi_map: BTreeMap<[i32; 19], Vec<usize>> = BTreeMap::new();
                let mut non_dps_pool: Vec<&'a CharmSpec> = Vec::new();

                for (idx, &ch) in pool.iter().enumerate() {
                    if is_pure_ar(ch) {
                        pure_ar_items.push((idx, ch, ch.ar));
                    } else if is_dps_stat(ch)
                        || matches!(ch.unique_id, Some(u) if dps_uids.contains(&u))
                    {
                        if let Some(uid) = ch.unique_id {
                            dps_unique_map.entry(uid).or_default().push(idx);
                        } else {
                            let key = [
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
                            ];
                            dps_multi_map.entry(key).or_default().push(idx);
                        }
                    } else {
                        non_dps_pool.push(ch);
                    }
                }

                let pure_ar_dp = PureAxisDp::build(&pure_ar_items, max_slots, class);
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
                        CharmGroup::Unique { options, max_pos, min_size, .. } => {
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
                        CharmGroup::Multi { members, size, stats } => {
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
                let dps_order_all_skills =
                    sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.all_skills);
                let dps_order_class_skills =
                    sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.skills);
                let dps_order_action_skills =
                    sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.action_skills);
                let dps_order_aura_skills =
                    sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.aura_skills);
                let dps_order_str =
                    sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.str_bonus);
                let dps_order_dex =
                    sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.dex_bonus);
                let dps_order_ar = sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.ar);
                let dps_order_phys =
                    sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.flat_phys_2x);
                let dps_order_fire =
                    sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.flat_fire_2x);
                let dps_order_elem =
                    sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.flat_elem_2x);
                let dps_order_psn =
                    sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.psn_dps_2x);
                let dps_order_res = [
                    sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.fr),
                    sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.lr),
                    sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.cr),
                    sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.pr),
                ];
                let dps_order_fhr = sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.fhr);
                let dps_order_frw = sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.frw);
                let dps_order_mf = sorted_ub_entries(&dps_groups, &pool, &[], |ch| ch.mf);
                let non_dps_solver = Box::new(CharmSolver::new_inner(
                    &non_dps_pool,
                    c,
                    SearchMode::LevelingRes,
                    false,
                ));
                (
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
                    pure_ar_dp,
                    Some(non_dps_solver),
                )
            } else {
                (
                    Vec::new(),
                    Vec::new(),
                    Vec::new(),
                    Vec::new(),
                    Vec::new(),
                    Vec::new(),
                    Vec::new(),
                    Vec::new(),
                    Vec::new(),
                    Vec::new(),
                    Vec::new(),
                    Vec::new(),
                    Vec::new(),
                    Vec::new(),
                    Vec::new(),
                    [Vec::new(), Vec::new(), Vec::new(), Vec::new()],
                    Vec::new(),
                    Vec::new(),
                    Vec::new(),
                    PureAxisDp::default(),
                    None,
                )
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
            cache: HashMap::new(),
            failed_floor: HashMap::new(),
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
            pure_ar_dp,
            non_dps_solver,
        }
    }

    fn main_score_of_indices(&self, idxs: &[usize], room: [i32; 4]) -> i32 {
        match self.mode {
            SearchMode::Power | SearchMode::Leveling => {
                idxs.iter().map(|&i| self.pool[i].skills_total()).sum()
            }
            SearchMode::Mf => idxs.iter().map(|&i| self.pool[i].mf).sum(),
            SearchMode::MaxRes | SearchMode::LevelingRes => {
                let mut sum_r = [0i32; 4];
                for &i in idxs {
                    let ch = self.pool[i];
                    sum_r[0] += ch.fr;
                    sum_r[1] += ch.lr;
                    sum_r[2] += ch.cr;
                    sum_r[3] += ch.pr;
                }
                (0..4).map(|r| sum_r[r].min(room[r]) - room[r].min(0)).sum()
            }
        }
    }

    fn max_res_gain_ub(
        &self,
        min_g_idx: usize,
        rem_slots: i32,
        rem_room: [i32; 4],
        min_needed: i32,
        scratch: &mut Vec<(i32, i32, i32)>,
    ) -> i32 {
        if rem_slots <= 0 {
            return 0;
        }
        let room_sum: i32 = rem_room.iter().sum();
        if room_sum < min_needed || room_sum == 0 {
            return room_sum;
        }
        let total_ub = eval_sorted_ub(&self.order_res_total, min_g_idx, rem_slots);
        if total_ub < min_needed || total_ub == 0 {
            return total_ub;
        }
        let per_res_ub: i32 = (0..4)
            .map(|r| {
                if rem_room[r] <= 0 {
                    0
                } else {
                    rem_room[r].min(eval_sorted_ub(&self.order_res[r], min_g_idx, rem_slots))
                }
            })
            .sum();
        if per_res_ub < min_needed || per_res_ub == 0 {
            return per_res_ub;
        }
        scratch.clear();
        for g in &self.groups[min_g_idx..] {
            match g {
                CharmGroup::Unique {
                    options, min_size, ..
                } => {
                    let val = options
                        .iter()
                        .map(|&i| {
                            let ch = self.pool[i];
                            ch.fr.max(0).min(rem_room[0])
                                + ch.lr.max(0).min(rem_room[1])
                                + ch.cr.max(0).min(rem_room[2])
                                + ch.pr.max(0).min(rem_room[3])
                        })
                        .max()
                        .unwrap_or(0);
                    if val > 0 {
                        scratch.push((val, *min_size, 1));
                    }
                }
                CharmGroup::Multi {
                    members,
                    size,
                    stats,
                } => {
                    let val = (0..4)
                        .map(|r| stats.res[r].max(0).min(rem_room[r]))
                        .sum::<i32>();
                    if val > 0 {
                        scratch.push((val, *size, members.len() as i32));
                    }
                }
            }
        }
        scratch.sort_unstable_by(|a, b| (b.0 as i64 * a.1 as i64).cmp(&(a.0 as i64 * b.1 as i64)));
        let mut rem = rem_slots;
        let mut joint_ub = 0;
        for &(val, sz, cnt) in scratch.iter() {
            let take = (rem / sz).min(cnt);
            if take > 0 {
                joint_ub += val * take;
                rem -= take * sz;
            }
            if rem > 0 && take < cnt {
                joint_ub += (val * rem + sz - 1) / sz;
                break;
            }
            if rem == 0 {
                break;
            }
        }
        per_res_ub.min(joint_ub)
    }

    fn solve_exact(
        &self,
        mut init_delta: [i32; 9], // [str, dex, fhr, fr, lr, cr, pr, frw, mf] (signed: >=0 means met, <0 means shortfall)
        room: [i32; 4],
        slot_budget: i32,
        forbidden_uid: Option<i32>,
        incumbent: Option<(i32, Vec<usize>)>,
        min_main_needed: i32,
    ) -> Option<Vec<usize>> {
        if is_res_mode(self.mode) && min_main_needed > 0 {
            let room_sum: i32 = (0..4).map(|r| room[r].max(0)).sum();
            let slack = room_sum - min_main_needed;
            if slack < 0 {
                return None;
            }
            for r in 0..4 {
                if room[r] > slack {
                    init_delta[3 + r] = init_delta[3 + r].min(-(room[r] - slack));
                }
            }
        }

        struct ExactCtx<'b, 'a> {
            solver: &'b CharmSolver<'a>,
            room: [i32; 4],
            forbidden_uid: Option<i32>,
            best_main: Option<i32>,
            best_indices: Option<Vec<usize>>,
            cur_indices: Vec<usize>,
            scratch: Vec<(i32, i32, i32)>,
        }

        fn dfs_charms(
            ctx: &mut ExactCtx<'_, '_>,
            g_idx: usize,
            rem_slots: i32,
            delta: [i32; 9],
            cur_res_added: [i32; 4],
            cur_skills: i32,
            cur_mf: i32,
        ) {
            let s = ctx.solver;
            let cur_main = match s.mode {
                SearchMode::Power | SearchMode::Leveling => cur_skills,
                SearchMode::Mf => cur_mf,
                SearchMode::MaxRes | SearchMode::LevelingRes => (0..4)
                    .map(|r| cur_res_added[r].min(ctx.room[r]) - ctx.room[r].min(0))
                    .sum(),
            };

            if ctx.best_main.is_none_or(|b| cur_main > b) {
                let mut axis_slots = [0usize; 9];
                let mut total_pure_slots = 0usize;
                let mut feasible = true;
                for d in 0..9 {
                    if delta[d] < 0 {
                        let Some(need_s) = s.pure_axes[d].min_slots_for(-delta[d]) else {
                            feasible = false;
                            break;
                        };
                        axis_slots[d] = need_s;
                        total_pure_slots += need_s;
                        if total_pure_slots as i32 > rem_slots {
                            feasible = false;
                            break;
                        }
                    }
                }
                if feasible {
                    ctx.best_main = Some(cur_main);
                    let mut next_indices = ctx.cur_indices.clone();
                    for (d, &need_s) in axis_slots.iter().enumerate() {
                        if need_s > 0 {
                            next_indices.extend_from_slice(&s.pure_axes[d].best_picks[need_s]);
                        }
                    }
                    ctx.best_indices = Some(next_indices);
                }
            }

            if g_idx == s.groups.len() || rem_slots == 0 {
                return;
            }

            // O(1) suffix feasibility and joint multi-axis pure-slot checks.
            let sp = s.suf_pos[g_idx];
            let suf_vals = [
                sp.str_bonus,
                sp.dex_bonus,
                sp.fhr,
                sp.res[0],
                sp.res[1],
                sp.res[2],
                sp.res[3],
                sp.frw,
                sp.mf,
            ];
            for d in 0..9 {
                if delta[d] + suf_vals[d] + s.pure_axes[d].max_gain < 0 {
                    return;
                }
            }
            let mut must_pure_slots = 0usize;
            for d in 0..9 {
                if delta[d] < 0 {
                    let must_pure = -delta[d] - suf_vals[d];
                    if must_pure > 0 {
                        let Some(need_s) = s.pure_axes[d].min_slots_for(must_pure) else {
                            return;
                        };
                        must_pure_slots += need_s;
                        if must_pure_slots as i32 > rem_slots {
                            return;
                        }
                    }
                }
            }

            // Objective upper-bound pruning once an incumbent or floor exists.
            let rem_dfs_slots = rem_slots - must_pure_slots as i32;
            if let Some(best) = ctx.best_main {
                let can_beat = match s.mode {
                    SearchMode::Power | SearchMode::Leveling => {
                        cur_skills + eval_sorted_ub(&s.order_skills, g_idx, rem_dfs_slots) > best
                    }
                    SearchMode::Mf => {
                        cur_mf + eval_sorted_ub(&s.order_mf, g_idx, rem_dfs_slots) > best
                    }
                    SearchMode::MaxRes | SearchMode::LevelingRes => {
                        let cur_gain = cur_main;
                        let min_needed = best - cur_gain + 1;
                        if min_needed <= 0 {
                            true
                        } else {
                            let rem_room = [
                                (ctx.room[0] - cur_res_added[0]).max(0),
                                (ctx.room[1] - cur_res_added[1]).max(0),
                                (ctx.room[2] - cur_res_added[2]).max(0),
                                (ctx.room[3] - cur_res_added[3]).max(0),
                            ];
                            cur_gain
                                + s.max_res_gain_ub(
                                    g_idx,
                                    rem_dfs_slots,
                                    rem_room,
                                    min_needed,
                                    &mut ctx.scratch,
                                )
                                > best
                        }
                    }
                };
                if !can_beat {
                    return;
                }
            }

            // Slot-constrained feasibility upper bounds for any currently unmet shortfalls.
            if delta[0] < 0 && delta[0] + eval_sorted_ub(&s.order_str, g_idx, rem_slots) < 0 {
                return;
            }
            if delta[1] < 0 && delta[1] + eval_sorted_ub(&s.order_dex, g_idx, rem_slots) < 0 {
                return;
            }
            if delta[2] < 0 && delta[2] + eval_sorted_ub(&s.order_fhr, g_idx, rem_slots) < 0 {
                return;
            }
            for r in 0..4 {
                if delta[3 + r] < 0
                    && delta[3 + r] + eval_sorted_ub(&s.order_res[r], g_idx, rem_slots) < 0
                {
                    return;
                }
            }
            if delta[7] < 0 && delta[7] + eval_sorted_ub(&s.order_frw, g_idx, rem_slots) < 0 {
                return;
            }
            if delta[8] < 0 && delta[8] + eval_sorted_ub(&s.order_mf, g_idx, rem_slots) < 0 {
                return;
            }

            match &s.groups[g_idx] {
                CharmGroup::Unique { options, .. } => {
                    for &opt_idx in options {
                        let ch = s.pool[opt_idx];
                        if ch.size > rem_slots
                            || (ctx.forbidden_uid.is_some() && ch.unique_id == ctx.forbidden_uid)
                        {
                            continue;
                        }
                        ctx.cur_indices.push(opt_idx);
                        dfs_charms(
                            ctx,
                            g_idx + 1,
                            rem_slots - ch.size,
                            [
                                delta[0] + ch.str_bonus,
                                delta[1] + ch.dex_bonus,
                                delta[2] + ch.fhr,
                                delta[3] + ch.fr,
                                delta[4] + ch.lr,
                                delta[5] + ch.cr,
                                delta[6] + ch.pr,
                                delta[7] + ch.frw,
                                delta[8] + ch.mf,
                            ],
                            [
                                cur_res_added[0] + ch.fr,
                                cur_res_added[1] + ch.lr,
                                cur_res_added[2] + ch.cr,
                                cur_res_added[3] + ch.pr,
                            ],
                            cur_skills + ch.skills_total(),
                            cur_mf + ch.mf,
                        );
                        ctx.cur_indices.pop();
                    }
                    dfs_charms(
                        ctx,
                        g_idx + 1,
                        rem_slots,
                        delta,
                        cur_res_added,
                        cur_skills,
                        cur_mf,
                    );
                }
                CharmGroup::Multi {
                    members,
                    size,
                    stats,
                } => {
                    let max_k = ((rem_slots / *size).min(members.len() as i32)).max(0);
                    let has_main = match s.mode {
                        SearchMode::Power | SearchMode::Leveling => stats.skills > 0,
                        SearchMode::Mf => stats.mf > 0,
                        SearchMode::MaxRes | SearchMode::LevelingRes => {
                            let neg_next = s.suf_neg_res[g_idx + 1];
                            (0..4).any(|r| {
                                stats.res[r] > 0 && cur_res_added[r] + neg_next[r] < ctx.room[r]
                            })
                        }
                    };
                    let max_useful = if has_main {
                        max_k
                    } else {
                        let neg_next = s.suf_neg_res[g_idx + 1];
                        let deficits = [
                            (-delta[0]).max(0),
                            (-delta[1]).max(0),
                            (-delta[2]).max(0),
                            (-(delta[3] + neg_next[0])).max(0),
                            (-(delta[4] + neg_next[1])).max(0),
                            (-(delta[5] + neg_next[2])).max(0),
                            (-(delta[6] + neg_next[3])).max(0),
                            (-delta[7]).max(0),
                            (-delta[8]).max(0),
                        ];
                        let gains = [
                            stats.str_bonus,
                            stats.dex_bonus,
                            stats.fhr,
                            stats.res[0],
                            stats.res[1],
                            stats.res[2],
                            stats.res[3],
                            stats.frw,
                            stats.mf,
                        ];
                        let mut cap = 0i32;
                        for i in 0..9 {
                            if deficits[i] > 0 && gains[i] > 0 {
                                cap = cap.max((deficits[i] + gains[i] - 1) / gains[i]);
                            }
                        }
                        cap.min(max_k)
                    };

                    for k in (1..=max_useful).rev() {
                        let ku = k as usize;
                        ctx.cur_indices.extend_from_slice(&members[..ku]);
                        dfs_charms(
                            ctx,
                            g_idx + 1,
                            rem_slots - k * *size,
                            [
                                delta[0] + stats.str_bonus * k,
                                delta[1] + stats.dex_bonus * k,
                                delta[2] + stats.fhr * k,
                                delta[3] + stats.res[0] * k,
                                delta[4] + stats.res[1] * k,
                                delta[5] + stats.res[2] * k,
                                delta[6] + stats.res[3] * k,
                                delta[7] + stats.frw * k,
                                delta[8] + stats.mf * k,
                            ],
                            [
                                cur_res_added[0] + stats.res[0] * k,
                                cur_res_added[1] + stats.res[1] * k,
                                cur_res_added[2] + stats.res[2] * k,
                                cur_res_added[3] + stats.res[3] * k,
                            ],
                            cur_skills + stats.skills * k,
                            cur_mf + stats.mf * k,
                        );
                        let new_len = ctx.cur_indices.len() - ku;
                        ctx.cur_indices.truncate(new_len);
                    }
                    dfs_charms(
                        ctx,
                        g_idx + 1,
                        rem_slots,
                        delta,
                        cur_res_added,
                        cur_skills,
                        cur_mf,
                    );
                }
            }
        }

        let floor_main = (min_main_needed > 0).then_some(min_main_needed - 1);
        let (best_main, best_indices) = match incumbent {
            Some((m, idxs)) if m >= min_main_needed => (Some(m), Some(idxs)),
            Some((m, _)) => (Some(m.max(min_main_needed - 1)), None),
            None => (floor_main, None),
        };
        let mut ctx = ExactCtx {
            solver: self,
            room,
            forbidden_uid,
            best_main,
            best_indices,
            cur_indices: Vec::new(),
            scratch: Vec::with_capacity(self.groups.len()),
        };
        dfs_charms(&mut ctx, 0, slot_budget.max(0), init_delta, [0; 4], 0, 0);
        ctx.best_indices
    }

    #[cfg(test)]
    pub(crate) fn solve(
        &mut self,
        _items: &[&ItemSpec],
        leaf: Stats,
        reqs: (i32, i32),
    ) -> Option<Vec<&'a CharmSpec>> {
        self.solve_with_min_main(leaf, reqs, 0)
    }

    pub(crate) fn solve_with_min_main(
        &mut self,
        leaf: Stats,
        reqs: (i32, i32),
        min_main_needed: i32,
    ) -> Option<Vec<&'a CharmSpec>> {
        self.solve_with_budget(leaf, reqs, self.max_slots, min_main_needed)
    }

    pub(crate) fn solve_with_budget(
        &mut self,
        leaf: Stats,
        reqs: (i32, i32),
        slot_budget: i32,
        min_main_needed: i32,
    ) -> Option<Vec<&'a CharmSpec>> {
        let caps_t = res_caps(leaf, self.c);
        let caps = [caps_t.0, caps_t.1, caps_t.2, caps_t.3];
        if self.c.min_fr > caps[0]
            || self.c.min_lr > caps[1]
            || self.c.min_cr > caps[2]
            || self.c.min_pr > caps[3]
        {
            return None;
        }

        if self.sunder_opts.is_empty() {
            return self
                .solve_for_sunder(
                    leaf,
                    caps,
                    reqs,
                    0,
                    slot_budget.max(0),
                    None,
                    min_main_needed,
                )
                .map(|idxs| idxs.into_iter().map(|i| self.pool[i]).collect());
        }

        let mode = self.mode;
        let sunder_main = |ch: &CharmSpec| -> i32 {
            match mode {
                SearchMode::Power | SearchMode::Leveling => ch.skills_total(),
                SearchMode::Mf => ch.mf,
                SearchMode::MaxRes | SearchMode::LevelingRes => 0,
            }
        };

        if self.sunder_opts.len() == 1 {
            let sunder = self.sunder_opts[0];
            let slot_budget = (self.raw_max_slots - sunder.size).max(0);
            let leaf_s = add_charm_to_leaf(leaf, sunder);
            let rem_min = (min_main_needed - sunder_main(sunder)).max(0);
            return self
                .solve_for_sunder(leaf_s, caps, reqs, 0, slot_budget, Some(sunder), rem_min)
                .map(|idxs| {
                    std::iter::once(sunder)
                        .chain(idxs.into_iter().map(|i| self.pool[i]))
                        .collect()
                });
        }

        struct SunderCandidate<'a> {
            score: (i32, i32, i32, i32, i32, i32),
            sunder: &'a CharmSpec,
            idxs: Vec<usize>,
        }
        let mut best: Option<SunderCandidate<'a>> = None;
        for s_idx in 0..self.sunder_opts.len() {
            let sunder = self.sunder_opts[s_idx];
            let s_main = sunder_main(sunder);
            let target_main = best
                .as_ref()
                .map_or(min_main_needed, |b| b.score.0.max(min_main_needed));
            let rem_min = (target_main - s_main).max(0);
            let slot_budget = (self.raw_max_slots - sunder.size).max(0);
            let leaf_s = add_charm_to_leaf(leaf, sunder);
            let Some(idxs) = self.solve_for_sunder(
                leaf_s,
                caps,
                reqs,
                s_idx,
                slot_budget,
                Some(sunder),
                rem_min,
            ) else {
                continue;
            };
            let rem_main = self.main_score_of_indices(&idxs, [0; 4]);
            let total_cr = leaf_s.cr + idxs.iter().map(|&i| self.pool[i].cr).sum::<i32>();
            let total_life = charm_eff_life(sunder, self.class)
                + idxs
                    .iter()
                    .map(|&i| charm_eff_life(self.pool[i], self.class))
                    .sum::<i32>();
            let total_mana = charm_eff_mana(sunder, self.class)
                + idxs
                    .iter()
                    .map(|&i| charm_eff_mana(self.pool[i], self.class))
                    .sum::<i32>();
            let total_fhr = leaf_s.fhr + idxs.iter().map(|&i| self.pool[i].fhr).sum::<i32>();
            let total_slots = sunder.size + idxs.iter().map(|&i| self.pool[i].size).sum::<i32>();
            let score = (
                s_main + rem_main,
                total_cr,
                total_life,
                total_mana,
                total_fhr,
                -total_slots,
            );
            if best.as_ref().is_none_or(|b| score > b.score) {
                best = Some(SunderCandidate {
                    score,
                    sunder,
                    idxs,
                });
            }
        }
        best.map(|b| {
            std::iter::once(b.sunder)
                .chain(b.idxs.into_iter().map(|i| self.pool[i]))
                .collect()
        })
    }

    #[allow(clippy::too_many_arguments)]
    fn solve_for_sunder(
        &mut self,
        leaf: Stats,
        caps: [i32; 4],
        reqs: (i32, i32),
        sunder_idx: usize,
        slot_budget: i32,
        prepicked: Option<&'a CharmSpec>,
        min_main_needed: i32,
    ) -> Option<Vec<usize>> {
        // `leaf` already includes base_str, base_dex, base_hell_res, and any prepicked sunder.
        let need_str = (reqs.0 - leaf.str_bonus).max(0);
        let need_dex = (reqs.1 - leaf.dex_bonus).max(0);
        let need_fhr = (self.c.min_fhr - leaf.fhr).max(0);
        let need_frw = (self.c.min_frw - leaf.frw).max(0);
        let need_mf = (self.c.min_mf - leaf.mf).max(0);
        let leaf_res = [leaf.fr, leaf.lr, leaf.cr, leaf.pr];
        let mins = [self.c.min_fr, self.c.min_lr, self.c.min_cr, self.c.min_pr];
        let delta_res = [
            leaf_res[0].saturating_sub(mins[0]).min(-self.sum_neg[0]),
            leaf_res[1].saturating_sub(mins[1]).min(-self.sum_neg[1]),
            leaf_res[2].saturating_sub(mins[2]).min(-self.sum_neg[2]),
            leaf_res[3].saturating_sub(mins[3]).min(-self.sum_neg[3]),
        ];
        let uses_room_in_cache = is_res_mode(self.mode) || self.mode == SearchMode::Leveling;
        let room = if is_res_mode(self.mode) {
            let opt_caps = res_opt_caps(caps, self.mode);
            [
                (opt_caps[0] - leaf.fr).max(self.sum_neg[0]),
                (opt_caps[1] - leaf.lr).max(self.sum_neg[1]),
                (opt_caps[2] - leaf.cr).max(self.sum_neg[2]),
                (opt_caps[3] - leaf.pr).max(self.sum_neg[3]),
            ]
        } else if self.mode == SearchMode::Leveling {
            [
                (caps[0] - leaf.fr).max(0),
                (caps[1] - leaf.lr).max(0),
                (caps[2] - leaf.cr).max(0),
                (caps[3] - leaf.pr).max(0),
            ]
        } else {
            [0; 4]
        };

        let key = CharmCacheKey {
            sunder_idx,
            slot_budget,
            need_str,
            need_dex,
            need_fhr,
            need_frw,
            need_mf,
            delta_res,
            room,
        };
        let forbidden_uid = prepicked.and_then(|s| s.unique_id);
        if let Some(cached) = self.cache.get(&key) {
            return match cached {
                None => None,
                Some((cached_main, idxs)) => {
                    if *cached_main < min_main_needed {
                        None
                    } else if uses_room_in_cache {
                        Some(idxs.clone())
                    } else {
                        Some(self.top_off_filler(idxs, leaf, caps, slot_budget, forbidden_uid))
                    }
                }
            };
        }
        if min_main_needed > 0
            && self
                .failed_floor
                .get(&key)
                .is_some_and(|&f| min_main_needed >= f)
        {
            return None;
        }

        if need_str > self.ub_str
            || need_dex > self.ub_dex
            || need_fhr > self.ub_fhr
            || need_frw > self.ub_frw
            || need_mf > self.ub_mf
            || -delta_res[0] > self.ub_res[0]
            || -delta_res[1] > self.ub_res[1]
            || -delta_res[2] > self.ub_res[2]
            || -delta_res[3] > self.ub_res[3]
        {
            self.cache.insert(key, None);
            return None;
        }

        let record_failed_floor = |failed_floor: &mut HashMap<CharmCacheKey, i32>| {
            failed_floor
                .entry(key)
                .and_modify(|f| *f = (*f).min(min_main_needed))
                .or_insert(min_main_needed);
        };

        let ub_main = match self.mode {
            SearchMode::Power | SearchMode::Leveling => {
                eval_sorted_ub(&self.order_skills, 0, slot_budget)
            }
            SearchMode::Mf => eval_sorted_ub(&self.order_mf, 0, slot_budget),
            SearchMode::MaxRes | SearchMode::LevelingRes => {
                (0..4).map(|r| room[r].max(0).min(self.ub_res[r])).sum()
            }
        };
        if ub_main < min_main_needed {
            record_failed_floor(&mut self.failed_floor);
            return None;
        }

        if is_res_mode(self.mode) && min_main_needed > 0 {
            let rem_room_init = [
                room[0].max(0),
                room[1].max(0),
                room[2].max(0),
                room[3].max(0),
            ];
            let mut scratch = Vec::new();
            if self.max_res_gain_ub(0, slot_budget, rem_room_init, min_main_needed, &mut scratch)
                < min_main_needed
            {
                record_failed_floor(&mut self.failed_floor);
                return None;
            }
        }

        let greedy_scored = greedy_charms_indices(
            leaf,
            &self.pool,
            self.c,
            reqs,
            self.mode,
            slot_budget,
            forbidden_uid,
            uses_room_in_cache,
        )
        .map(|idxs| (self.main_score_of_indices(&idxs, room), idxs));

        let incumbent = if let Some((g_main, ref g_idxs)) = greedy_scored {
            if g_main >= ub_main {
                let filled = if uses_room_in_cache {
                    g_idxs.clone()
                } else {
                    self.top_off_filler(g_idxs, leaf, caps, slot_budget, forbidden_uid)
                };
                self.cache
                    .insert(key, Some((g_main, greedy_scored.unwrap().1)));
                return Some(filled);
            }
            Some((g_main, g_idxs.clone()))
        } else {
            None
        };

        let init_delta = [
            -need_str,
            -need_dex,
            -need_fhr,
            delta_res[0],
            delta_res[1],
            delta_res[2],
            delta_res[3],
            -need_frw,
            -need_mf,
        ];
        let best_exact = self
            .solve_exact(
                init_delta,
                room,
                slot_budget,
                forbidden_uid,
                incumbent,
                min_main_needed,
            )
            .map(|idxs| (self.main_score_of_indices(&idxs, room), idxs));

        let winner = match (greedy_scored, best_exact) {
            (Some((g_main, _)), Some((e_main, e_idxs))) if e_main > g_main => {
                Some((e_main, e_idxs, false))
            }
            (Some((g_main, g_idxs)), _) if min_main_needed == 0 || g_main >= min_main_needed => {
                Some((g_main, g_idxs, uses_room_in_cache))
            }
            (_, Some((e_main, e_idxs))) if e_main >= min_main_needed => {
                Some((e_main, e_idxs, false))
            }
            _ => None,
        };

        match winner {
            Some((win_main, win_idxs, already_filled)) => {
                let filled = if already_filled {
                    win_idxs.clone()
                } else {
                    self.top_off_filler(&win_idxs, leaf, caps, slot_budget, forbidden_uid)
                };
                let to_cache = if uses_room_in_cache {
                    filled.clone()
                } else {
                    win_idxs
                };
                self.cache.insert(key, Some((win_main, to_cache)));
                Some(filled)
            }
            None => {
                if min_main_needed <= 0 {
                    self.cache.insert(key, None);
                } else {
                    record_failed_floor(&mut self.failed_floor);
                }
                None
            }
        }
    }

    fn top_off_filler(
        &self,
        core: &[usize],
        leaf: Stats,
        caps: [i32; 4],
        slot_budget: i32,
        forbidden_uid: Option<i32>,
    ) -> Vec<usize> {
        let mut state = CharmState::new(
            &self.pool,
            slot_budget.max(0),
            leaf.fhr,
            [leaf.fr, leaf.lr, leaf.cr, leaf.pr],
            leaf.str_bonus,
            leaf.dex_bonus,
            leaf.frw,
            leaf.mf,
        );
        if let Some(uid) = forbidden_uid {
            state.unique_ids.insert(uid);
        }
        for &idx in core {
            state.pick(idx);
        }
        let res_targets = [self.c.min_fr, self.c.min_lr, self.c.min_cr, self.c.min_pr];
        greedy_fill_remaining(
            &mut state,
            caps,
            res_targets,
            self.mode,
            self.class,
            true,
        );
        state.chosen_indices
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn improve_for_dps(
        &mut self,
        gear: Stats,
        all_sk_non_wep: i32,
        hw: HandWeapon,
        leaf: Stats,
        reqs: (i32, i32),
        offense: OffenseProfile,
        cutoff: Option<(i32, i32, i32)>,
        best_charms: &mut Vec<&'a CharmSpec>,
        best_sum: &mut EvalSummary,
        best_score: &mut BuildScore,
    ) {
        if self.non_dps_solver.is_none() {
            return;
        }
        let gear_bucket = OffenseProfile::dps_bucket(offense.compute_dps(hw, leaf, self.c).0);
        let ub_leaf = leaf.add(self.charm_ub_stats());
        let global_ub_bucket =
            OffenseProfile::dps_bucket(offense.compute_dps(hw, ub_leaf, self.c).0);
        let caps_t = res_caps(leaf, self.c);
        let caps = [caps_t.0, caps_t.1, caps_t.2, caps_t.3];
        let cbf_val = i32::from(leaf.cbf > 0);
        if let Some(cut) = cutoff {
            let max_res_base: i32 = [
                (ub_leaf.fr).min(caps[0]).min(BASE_MAX_RES),
                (ub_leaf.lr).min(caps[1]).min(BASE_MAX_RES),
                (ub_leaf.cr).min(caps[2]).min(BASE_MAX_RES),
                (ub_leaf.pr).min(caps[3]).min(BASE_MAX_RES),
            ]
            .iter()
            .sum();
            let global_top3 = match self.mode {
                SearchMode::Leveling => (global_ub_bucket, max_res_base, cbf_val),
                SearchMode::LevelingRes => (max_res_base, global_ub_bucket, cbf_val),
                _ => return,
            };
            if global_top3 < cut {
                return;
            }
        }
        if self.dps_groups.is_empty()
            && (self.pure_ar_dp.max_gain == 0 || gear_bucket >= global_ub_bucket)
        {
            return;
        }
        let non_dps_solver = self.non_dps_solver.as_deref_mut().expect("checked non_dps_solver");
        let slots_len = (self.max_slots.max(0) as usize) + 1;
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

        struct DpsCtx<'b, 'a> {
            pool: &'b [&'a CharmSpec],
            c: &'a BuildConstraints,
            mode: SearchMode,
            class: CharClass,
            gear: Stats,
            all_sk_non_wep: i32,
            hw: HandWeapon,
            leaf: Stats,
            reqs: (i32, i32),
            offense: OffenseProfile,
            cutoff: Option<(i32, i32, i32)>,
            cbf_val: i32,
            groups: &'b [CharmGroup],
            suf_pos: &'b [StatTotals],
            suf_neg_res: &'b [[i32; 4]],
            min_size: &'b [i32],
            order_all_skills: &'b [UbGroupEntry],
            order_class_skills: &'b [UbGroupEntry],
            order_action_skills: &'b [UbGroupEntry],
            order_aura_skills: &'b [UbGroupEntry],
            order_str: &'b [UbGroupEntry],
            order_dex: &'b [UbGroupEntry],
            order_ar: &'b [UbGroupEntry],
            order_phys: &'b [UbGroupEntry],
            order_fire: &'b [UbGroupEntry],
            order_elem: &'b [UbGroupEntry],
            order_psn: &'b [UbGroupEntry],
            order_res: &'b [Vec<UbGroupEntry>; 4],
            order_fhr: &'b [UbGroupEntry],
            order_frw: &'b [UbGroupEntry],
            order_mf: &'b [UbGroupEntry],
            pure_ar_dp: &'b PureAxisDp,
            non_dps_solver: &'b mut CharmSolver<'a>,
            nd_res_at: &'b [[i32; 4]],
            nd_fhr_at: &'b [i32],
            nd_frw_at: &'b [i32],
            nd_mf_at: &'b [i32],
            caps: [i32; 4],
            cur_indices: Vec<usize>,
            best_charms: &'b mut Vec<&'a CharmSpec>,
            best_sum: &'b mut EvalSummary,
            best_score: &'b mut BuildScore,
        }

        fn dfs_dps<'b, 'a>(
            ctx: &mut DpsCtx<'b, 'a>,
            mut g_idx: usize,
            rem_slots: i32,
            cur: StatTotals,
        ) {
            if g_idx < ctx.groups.len() && rem_slots < ctx.min_size[g_idx] {
                g_idx = ctx.groups.len();
            }
            let sp = ctx.suf_pos[g_idx];
            let sn = ctx.suf_neg_res[g_idx];
            let rs_idx = (rem_slots.max(0) as usize).min(ctx.nd_fhr_at.len() - 1);
            let ub_rem = |sp_v: i32, order: &[UbGroupEntry]| {
                if g_idx >= ctx.groups.len() || rem_slots <= 0 {
                    0
                } else {
                    sp_v.min(eval_sorted_ub(order, g_idx, rem_slots))
                }
            };
            let leaf = ctx.leaf;
            let rem_str = ub_rem(sp.str_bonus, ctx.order_str);
            let rem_dex = ub_rem(sp.dex_bonus, ctx.order_dex);
            if leaf.str_bonus + cur.str_bonus + rem_str < ctx.reqs.0
                || leaf.dex_bonus + cur.dex_bonus + rem_dex < ctx.reqs.1
            {
                return;
            }
            if leaf.fhr + cur.fhr + ctx.nd_fhr_at[rs_idx] < ctx.c.min_fhr
                && leaf.fhr + cur.fhr + ub_rem(sp.fhr, ctx.order_fhr) + ctx.nd_fhr_at[rs_idx]
                    < ctx.c.min_fhr
            {
                return;
            }
            if leaf.frw + cur.frw + ctx.nd_frw_at[rs_idx] < ctx.c.min_frw
                && leaf.frw + cur.frw + ub_rem(sp.frw, ctx.order_frw) + ctx.nd_frw_at[rs_idx]
                    < ctx.c.min_frw
            {
                return;
            }
            if leaf.mf + cur.mf + ctx.nd_mf_at[rs_idx] < ctx.c.min_mf
                && leaf.mf + cur.mf + ub_rem(sp.mf, ctx.order_mf) + ctx.nd_mf_at[rs_idx]
                    < ctx.c.min_mf
            {
                return;
            }
            let leaf_res = [leaf.fr, leaf.lr, leaf.cr, leaf.pr];
            let min_res = [ctx.c.min_fr, ctx.c.min_lr, ctx.c.min_cr, ctx.c.min_pr];
            let mut ub_res_base = 0i32;
            for r in 0..4 {
                let cap_r = ctx.caps[r].min(BASE_MAX_RES);
                let cur_plus_nd = leaf_res[r] + cur.res[r] + ctx.nd_res_at[rs_idx][r];
                if cur_plus_nd >= cap_r.max(min_res[r]) {
                    ub_res_base += cur_plus_nd.min(cap_r);
                } else {
                    let rem_r = ub_rem(sp.res[r], &ctx.order_res[r]);
                    let total_r = cur_plus_nd + rem_r;
                    if total_r < min_res[r] {
                        return;
                    }
                    ub_res_base += total_r.min(cap_r);
                }
            }
            let rem_ar = ub_rem(sp.ar, ctx.order_ar);
            let max_ar = leaf.ar + cur.ar + rem_ar + ctx.pure_ar_dp.gain_at(rem_slots);
            let rem_all_sk = ub_rem(sp.all_skills, ctx.order_all_skills);
            let rem_cls_sk = ub_rem(sp.class_skills, ctx.order_class_skills);
            let (cur_sorc_ub, cur_pal_ub) = match ctx.class {
                CharClass::Sorceress => (cur.class_skills + rem_cls_sk, 0),
                CharClass::Paladin => (0, cur.class_skills + rem_cls_sk),
            };
            let ub_dps_stats = Stats {
                all_skills: leaf.all_skills + cur.all_skills + rem_all_sk,
                sorc_skills: leaf.sorc_skills + cur_sorc_ub,
                pal_skills: leaf.pal_skills + cur_pal_ub,
                action_skill_bonus: leaf.action_skill_bonus
                    + cur.action_skills
                    + ub_rem(sp.action_skills, ctx.order_action_skills),
                aura_skill_bonus: leaf.aura_skill_bonus
                    + cur.aura_skills
                    + ub_rem(sp.aura_skills, ctx.order_aura_skills),
                str_bonus: leaf.str_bonus + cur.str_bonus + rem_str,
                dex_bonus: leaf.dex_bonus + cur.dex_bonus + rem_dex,
                ar: max_ar,
                flat_phys_2x: leaf.flat_phys_2x
                    + cur.flat_phys_2x
                    + ub_rem(sp.flat_phys_2x, ctx.order_phys),
                flat_fire_2x: leaf.flat_fire_2x
                    + cur.flat_fire_2x
                    + ub_rem(sp.flat_fire_2x, ctx.order_fire),
                flat_elem_2x: leaf.flat_elem_2x
                    + cur.flat_elem_2x
                    + ub_rem(sp.flat_elem_2x, ctx.order_elem),
                psn_dps_2x: leaf.psn_dps_2x + cur.psn_dps_2x + ub_rem(sp.psn_dps_2x, ctx.order_psn),
                ..leaf
            };
            let ub_bucket =
                OffenseProfile::dps_bucket(ctx.offense.compute_dps(ctx.hw, ub_dps_stats, ctx.c).0);
            let ub_top3 = match ctx.mode {
                SearchMode::Leveling => (ub_bucket, ub_res_base, ctx.cbf_val),
                SearchMode::LevelingRes => (ub_res_base, ub_bucket, ctx.cbf_val),
                _ => return,
            };
            if ctx.cutoff.is_some_and(|cut| ub_top3 < cut)
                || (ub_top3.0, ub_top3.1) < (ctx.best_score.primary, ctx.best_score.secondary)
            {
                return;
            }
            // Note: negative res from remaining dps_groups can never exceed `sn[r]`, which stays <= 0.
            let _ = sn;

            if g_idx == ctx.groups.len() {
                let (cur_sorc, cur_pal) = match ctx.class {
                    CharClass::Sorceress => (cur.class_skills, 0),
                    CharClass::Paladin => (0, cur.class_skills),
                };
                let leaf_d = Stats {
                    all_skills: leaf.all_skills + cur.all_skills,
                    sorc_skills: leaf.sorc_skills + cur_sorc,
                    pal_skills: leaf.pal_skills + cur_pal,
                    action_skill_bonus: leaf.action_skill_bonus + cur.action_skills,
                    aura_skill_bonus: leaf.aura_skill_bonus + cur.aura_skills,
                    str_bonus: leaf.str_bonus + cur.str_bonus,
                    dex_bonus: leaf.dex_bonus + cur.dex_bonus,
                    fhr: leaf.fhr + cur.fhr,
                    frw: leaf.frw + cur.frw,
                    mf: leaf.mf + cur.mf,
                    fr: leaf.fr + cur.res[0],
                    lr: leaf.lr + cur.res[1],
                    cr: leaf.cr + cur.res[2],
                    pr: leaf.pr + cur.res[3],
                    ar: leaf.ar + cur.ar,
                    flat_phys_2x: leaf.flat_phys_2x + cur.flat_phys_2x,
                    flat_fire_2x: leaf.flat_fire_2x + cur.flat_fire_2x,
                    flat_elem_2x: leaf.flat_elem_2x + cur.flat_elem_2x,
                    psn_dps_2x: leaf.psn_dps_2x + cur.psn_dps_2x,
                    ..leaf
                };
                let mut prev_tested_bucket: Option<i32> = None;
                let max_ar_s = (rem_slots.max(0) as usize)
                    .min(ctx.pure_ar_dp.best_gain.len().saturating_sub(1));
                for ar_s in 0..=max_ar_s {
                    let extra_ar = ctx.pure_ar_dp.gain_at(ar_s as i32);
                    if ar_s > 0 && extra_ar <= ctx.pure_ar_dp.gain_at(ar_s as i32 - 1) {
                        continue;
                    }
                    let rem_nd = rem_slots - ar_s as i32;
                    let nd_idx = (rem_nd.max(0) as usize).min(ctx.nd_fhr_at.len() - 1);
                    if leaf_d.fhr + ctx.nd_fhr_at[nd_idx] < ctx.c.min_fhr
                        || leaf_d.frw + ctx.nd_frw_at[nd_idx] < ctx.c.min_frw
                        || leaf_d.mf + ctx.nd_mf_at[nd_idx] < ctx.c.min_mf
                        || leaf_d.fr + ctx.nd_res_at[nd_idx][0] < ctx.c.min_fr
                        || leaf_d.lr + ctx.nd_res_at[nd_idx][1] < ctx.c.min_lr
                        || leaf_d.cr + ctx.nd_res_at[nd_idx][2] < ctx.c.min_cr
                        || leaf_d.pr + ctx.nd_res_at[nd_idx][3] < ctx.c.min_pr
                    {
                        continue;
                    }
                    let cand_res_ub: i32 = [
                        (leaf_d.fr + ctx.nd_res_at[nd_idx][0])
                            .min(ctx.caps[0])
                            .min(BASE_MAX_RES),
                        (leaf_d.lr + ctx.nd_res_at[nd_idx][1])
                            .min(ctx.caps[1])
                            .min(BASE_MAX_RES),
                        (leaf_d.cr + ctx.nd_res_at[nd_idx][2])
                            .min(ctx.caps[2])
                            .min(BASE_MAX_RES),
                        (leaf_d.pr + ctx.nd_res_at[nd_idx][3])
                            .min(ctx.caps[3])
                            .min(BASE_MAX_RES),
                    ]
                    .iter()
                    .sum();
                    let cand_ar_stats = Stats {
                        ar: leaf_d.ar + extra_ar,
                        ..leaf_d
                    };
                    let cand_bucket = OffenseProfile::dps_bucket(
                        ctx.offense.compute_dps(ctx.hw, cand_ar_stats, ctx.c).0,
                    );
                    if prev_tested_bucket == Some(cand_bucket) {
                        continue;
                    }
                    let cand_top3 = match ctx.mode {
                        SearchMode::Leveling => (cand_bucket, cand_res_ub, ctx.cbf_val),
                        SearchMode::LevelingRes => (cand_res_ub, cand_bucket, ctx.cbf_val),
                        _ => continue,
                    };
                    if ctx.cutoff.is_some_and(|cut| cand_top3 < cut)
                        || (cand_top3.0, cand_top3.1)
                            < (ctx.best_score.primary, ctx.best_score.secondary)
                    {
                        continue;
                    }
                    prev_tested_bucket = Some(cand_bucket);
                    let Some(mut cand_charms) =
                        ctx.non_dps_solver.solve_with_budget(leaf_d, (0, 0), rem_nd, 0)
                    else {
                        continue;
                    };
                    for &idx in &ctx.cur_indices {
                        cand_charms.push(ctx.pool[idx]);
                    }
                    for &idx in &ctx.pure_ar_dp.best_picks[ar_s] {
                        cand_charms.push(ctx.pool[idx]);
                    }
                    let cand_sum = eval_build_summary(
                        ctx.gear,
                        ctx.all_sk_non_wep,
                        ctx.hw,
                        &cand_charms,
                        ctx.c,
                    );
                    if (!ctx.c.allow_mf && cand_sum.mf > 0)
                        || cand_sum.fhr < ctx.c.min_fhr
                        || cand_sum.frw < ctx.c.min_frw
                        || cand_sum.mf < ctx.c.min_mf
                        || cand_sum.fr < ctx.c.min_fr
                        || cand_sum.lr < ctx.c.min_lr
                        || cand_sum.cr < ctx.c.min_cr
                        || cand_sum.pr < ctx.c.min_pr
                    {
                        continue;
                    }
                    let mut cand_score =
                        score_eval_summary(ctx.mode, ctx.offense, &cand_sum, ctx.c);
                    cand_score.locality = ctx.best_score.locality;
                    if cand_score > *ctx.best_score {
                        *ctx.best_charms = cand_charms;
                        *ctx.best_sum = cand_sum;
                        *ctx.best_score = cand_score;
                    }
                }
                return;
            }

            match &ctx.groups[g_idx] {
                CharmGroup::Unique { options, .. } => {
                    let opts = options.clone();
                    for opt_idx in opts {
                        let ch = ctx.pool[opt_idx];
                        if ch.size > rem_slots {
                            continue;
                        }
                        ctx.cur_indices.push(opt_idx);
                        dfs_dps(
                            ctx,
                            g_idx + 1,
                            rem_slots - ch.size,
                            cur.add_scaled(StatTotals::from_charm(ch), 1),
                        );
                        ctx.cur_indices.pop();
                    }
                    dfs_dps(ctx, g_idx + 1, rem_slots, cur);
                }
                CharmGroup::Multi {
                    members,
                    size,
                    stats,
                } => {
                    let members = members.clone();
                    let size = *size;
                    let stats = *stats;
                    let max_k = ((rem_slots / size).min(members.len() as i32)).max(0);
                    for k in (1..=max_k).rev() {
                        let ku = k as usize;
                        ctx.cur_indices.extend_from_slice(&members[..ku]);
                        dfs_dps(
                            ctx,
                            g_idx + 1,
                            rem_slots - k * size,
                            cur.add_scaled(stats, k),
                        );
                        let new_len = ctx.cur_indices.len() - ku;
                        ctx.cur_indices.truncate(new_len);
                    }
                    dfs_dps(ctx, g_idx + 1, rem_slots, cur);
                }
            }
        }

        let mut ctx = DpsCtx {
            pool: &self.pool,
            c: self.c,
            mode: self.mode,
            class: self.class,
            gear,
            all_sk_non_wep,
            hw,
            leaf,
            reqs,
            offense,
            cutoff,
            cbf_val,
            groups: &self.dps_groups,
            suf_pos: &self.dps_suf_pos,
            suf_neg_res: &self.dps_suf_neg_res,
            min_size: &self.dps_min_size,
            order_all_skills: &self.dps_order_all_skills,
            order_class_skills: &self.dps_order_class_skills,
            order_action_skills: &self.dps_order_action_skills,
            order_aura_skills: &self.dps_order_aura_skills,
            order_str: &self.dps_order_str,
            order_dex: &self.dps_order_dex,
            order_ar: &self.dps_order_ar,
            order_phys: &self.dps_order_phys,
            order_fire: &self.dps_order_fire,
            order_elem: &self.dps_order_elem,
            order_psn: &self.dps_order_psn,
            order_res: &self.dps_order_res,
            order_fhr: &self.dps_order_fhr,
            order_frw: &self.dps_order_frw,
            order_mf: &self.dps_order_mf,
            pure_ar_dp: &self.pure_ar_dp,
            non_dps_solver,
            nd_res_at: &nd_res_at,
            nd_fhr_at: &nd_fhr_at,
            nd_frw_at: &nd_frw_at,
            nd_mf_at: &nd_mf_at,
            caps,
            cur_indices: Vec::new(),
            best_charms,
            best_sum,
            best_score,
        };
        dfs_dps(&mut ctx, 0, self.max_slots.max(0), StatTotals::default());
    }
}

fn add_charm_to_leaf(mut leaf: Stats, ch: &CharmSpec) -> Stats {
    leaf.str_bonus += ch.str_bonus;
    leaf.dex_bonus += ch.dex_bonus;
    leaf.fhr += ch.fhr;
    leaf.frw += ch.frw;
    leaf.mf += ch.mf;
    leaf.fr += ch.fr;
    leaf.lr += ch.lr;
    leaf.cr += ch.cr;
    leaf.pr += ch.pr;
    leaf
}

#[cfg(test)]
#[path = "charms_tests.rs"]
mod tests;
