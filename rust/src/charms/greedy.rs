use std::collections::{BTreeMap, HashSet};

use crate::eval::res_caps;
use crate::types::{BASE_MAX_RES, BuildConstraints, CharClass, CharmSpec, SearchMode, Stats};
#[cfg(test)]
use crate::types::{ItemSpec, compute_effective_gear_stats};

pub(super) fn is_res_mode(mode: SearchMode) -> bool {
    matches!(mode, SearchMode::MaxRes | SearchMode::LevelingRes)
}

pub(super) fn res_opt_caps(caps: [i32; 4], mode: SearchMode) -> [i32; 4] {
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

pub(super) struct CharmState<'a, 'b> {
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
    pub(super) chosen_indices: Vec<usize>,
    pub(super) unique_ids: HashSet<i32>,
}

impl<'a, 'b> CharmState<'a, 'b> {
    #[allow(clippy::too_many_arguments)]
    pub(super) fn new(
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

    pub(super) fn pick(&mut self, idx: usize) {
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

pub(super) fn charm_eff_life(ch: &CharmSpec, class: CharClass) -> i32 {
    ch.life + class.life_per_vit(ch.vit)
}

pub(super) fn charm_eff_mana(ch: &CharmSpec, class: CharClass) -> i32 {
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

pub(super) fn greedy_fill_remaining(
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
        let eff = (cb.skills_total() * ca.size.max(1)).cmp(&(ca.skills_total() * cb.size.max(1)));
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
        greedy_res_loop(
            &mut state,
            res_targets,
            [1.5, 1.5, 1.2, 1.0],
            mf_w,
            sk_w,
            class,
        );
    } else {
        greedy_res_loop(
            &mut state,
            res_targets,
            [1.5, 1.5, 1.2, 1.0],
            mf_w,
            sk_w,
            class,
        );
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
pub(super) fn greedy_charms_pass<'a>(
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
pub(super) fn greedy_charms_indices(
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

pub(super) fn shrink_sunder_pool<'a>(
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
