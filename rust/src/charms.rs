use std::collections::{BTreeMap, HashMap, HashSet};

use crate::eval::res_caps;
use crate::types::{
    compute_effective_gear_stats, BuildConstraints, CharClass, CharmSpec, ItemSpec, SearchMode,
    Stats, BASE_MAX_RES,
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
    chosen_indices: Vec<usize>,
    unique_ids: HashSet<i32>,
}

impl<'a, 'b> CharmState<'a, 'b> {
    fn new(
        pool: &'b [&'a CharmSpec],
        max_slots: i32,
        cur_fhr: i32,
        cur_res: [i32; 4],
        cur_str: i32,
        cur_dex: i32,
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

fn greedy_res_loop(
    state: &mut CharmState<'_, '_>,
    targets: [i32; 4],
    weights: [f64; 4],
    mf_weight: f64,
    skill_weight: f64,
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
                let tie_bonus = c.mf as f64 * mf_weight + c.skills as f64 * skill_weight;
                let score = (gain + tie_bonus + c.life as f64 * 0.02) / c.size.max(1) as f64;
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
                    c.skills,
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

fn greedy_fill_remaining(
    state: &mut CharmState<'_, '_>,
    caps: [i32; 4],
    res_targets: [i32; 4],
    mode: SearchMode,
) {
    let pool = state.pool;
    let mut mf_indices: Vec<usize> = (0..pool.len())
        .filter(|&i| state.can_pick(i) && pool[i].mf > 0)
        .collect();
    mf_indices.sort_by(|&a, &b| {
        let ka = (
            pool[a].mf * 100 / pool[a].size.max(1),
            pool[a].skills,
            pool[a].lr,
        );
        let kb = (
            pool[b].mf * 100 / pool[b].size.max(1),
            pool[b].skills,
            pool[b].lr,
        );
        kb.cmp(&ka)
    });

    let mut sk_indices: Vec<usize> = (0..pool.len())
        .filter(|&i| state.can_pick(i) && pool[i].skills > 0)
        .collect();
    sk_indices.sort_by(|&a, &b| {
        let ca = pool[a];
        let cb = pool[b];
        let eff = (cb.skills * ca.size.max(1)).cmp(&(ca.skills * cb.size.max(1)));
        eff.then_with(|| {
            (cb.skills, cb.life, cb.fr + cb.lr + cb.cr, cb.mana).cmp(&(
                ca.skills,
                ca.life,
                ca.fr + ca.lr + ca.cr,
                ca.mana,
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

    if mode == SearchMode::Leveling {
        greedy_res_loop(
            state,
            res_opt_caps(caps, mode),
            [1.0, 1.0, 1.0, 1.0],
            0.0,
            0.2,
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
            let mut s = c.life as f64
                + c.mana as f64 * 0.4
                + (caps[3] - state.cur_res[3]).max(0).min(c.pr) as f64 * 1.2;
            if matches!(mode, SearchMode::Leveling | SearchMode::LevelingRes) {
                s += c.frw as f64 * 1.5;
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

fn greedy_charms_pass_indices(
    items: &[&ItemSpec],
    pool: &[&CharmSpec],
    c: &BuildConstraints,
    reqs: (i32, i32),
    mode: SearchMode,
    fhr_first: bool,
    prepicked: Option<&CharmSpec>,
) -> Option<Vec<usize>> {
    let (gear, _) = compute_effective_gear_stats(items);
    let (cap_fr, cap_lr, cap_cr, cap_pr) = res_caps(gear, c);
    if c.min_fr > cap_fr || c.min_lr > cap_lr || c.min_cr > cap_cr || c.min_pr > cap_pr {
        return None;
    }
    let caps = [cap_fr, cap_lr, cap_cr, cap_pr];
    let slot_budget = prepicked.map_or(c.max_charm_slots, |s| c.max_charm_slots - s.size);
    if slot_budget < 0 {
        return None;
    }
    let (s_fhr, s_fr, s_lr, s_cr, s_pr, s_str, s_dex) = match prepicked {
        Some(s) => (s.fhr, s.fr, s.lr, s.cr, s.pr, s.str_bonus, s.dex_bonus),
        None => (0, 0, 0, 0, 0, 0, 0),
    };
    let mut state = CharmState::new(
        pool,
        slot_budget,
        gear.fhr + s_fhr,
        [
            c.base_hell_res + gear.fr + s_fr,
            c.base_hell_res + gear.lr + s_lr,
            c.base_hell_res + gear.cr + s_cr,
            c.base_hell_res + gear.pr + s_pr,
        ],
        c.base_str + gear.str_bonus + s_str,
        c.base_dex + gear.dex_bonus + s_dex,
    );
    if let Some(uid) = prepicked.and_then(|s| s.unique_id) {
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
                let score = (gain as f64 + ch.skills as f64 * 0.1) / ch.size.max(1) as f64;
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
    let res_targets = [c.min_fr, c.min_lr, c.min_cr, c.min_pr];
    if fhr_first {
        greedy_fhr_loop(&mut state, c.min_fhr);
        greedy_res_loop(&mut state, res_targets, [1.5, 1.5, 1.2, 1.0], mf_w, sk_w);
    } else {
        greedy_res_loop(&mut state, res_targets, [1.5, 1.5, 1.2, 1.0], mf_w, sk_w);
        greedy_fhr_loop(&mut state, c.min_fhr);
    }

    if is_res_mode(mode) {
        greedy_res_loop(
            &mut state,
            res_opt_caps(caps, mode),
            [1.0, 1.0, 1.0, 1.0],
            0.0,
            0.2,
        );
    }

    greedy_fill_remaining(&mut state, caps, res_targets, mode);

    if state.cur_fhr < c.min_fhr
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
    greedy_charms_pass_indices(items, pool, c, reqs, mode, fhr_first, None)
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

fn greedy_charms_indices(
    items: &[&ItemSpec],
    pool: &[&CharmSpec],
    c: &BuildConstraints,
    reqs: (i32, i32),
    mode: SearchMode,
    prepicked: Option<&CharmSpec>,
) -> Option<Vec<usize>> {
    for fhr_first in [true, false] {
        if let Some(chosen) =
            greedy_charms_pass_indices(items, pool, c, reqs, mode, fhr_first, prepicked)
        {
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
        || a.frw < b.frw
        || a.str_bonus < b.str_bonus
        || a.dex_bonus < b.dex_bonus
        || a.skills < b.skills
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
        || a.frw > b.frw
        || a.str_bonus > b.str_bonus
        || a.dex_bonus > b.dex_bonus
        || a.skills > b.skills;
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
    res: [i32; 4],
    skills: i32,
    mf: i32,
}

impl StatTotals {
    fn from_charm(c: &CharmSpec) -> Self {
        Self {
            str_bonus: c.str_bonus,
            dex_bonus: c.dex_bonus,
            fhr: c.fhr,
            res: [c.fr, c.lr, c.cr, c.pr],
            skills: c.skills,
            mf: c.mf,
        }
    }

    fn max_each(self, o: Self) -> Self {
        Self {
            str_bonus: self.str_bonus.max(o.str_bonus),
            dex_bonus: self.dex_bonus.max(o.dex_bonus),
            fhr: self.fhr.max(o.fhr),
            res: [
                self.res[0].max(o.res[0]),
                self.res[1].max(o.res[1]),
                self.res[2].max(o.res[2]),
                self.res[3].max(o.res[3]),
            ],
            skills: self.skills.max(o.skills),
            mf: self.mf.max(o.mf),
        }
    }

    fn clamp_non_neg(self) -> Self {
        Self {
            str_bonus: self.str_bonus.max(0),
            dex_bonus: self.dex_bonus.max(0),
            fhr: self.fhr.max(0),
            res: [
                self.res[0].max(0),
                self.res[1].max(0),
                self.res[2].max(0),
                self.res[3].max(0),
            ],
            skills: self.skills.max(0),
            mf: self.mf.max(0),
        }
    }

    fn add_scaled(self, o: Self, k: i32) -> Self {
        Self {
            str_bonus: self.str_bonus + o.str_bonus * k,
            dex_bonus: self.dex_bonus + o.dex_bonus * k,
            fhr: self.fhr + o.fhr * k,
            res: [
                self.res[0] + o.res[0] * k,
                self.res[1] + o.res[1] * k,
                self.res[2] + o.res[2] * k,
                self.res[3] + o.res[3] * k,
            ],
            skills: self.skills + o.skills * k,
            mf: self.mf + o.mf * k,
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
    need_str: i32,
    need_dex: i32,
    need_fhr: i32,
    delta_res: [i32; 4],
    room: [i32; 4],
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
    raw_max_slots: i32,
    max_slots: i32,
    sum_neg: [i32; 4],
    ub_str: i32,
    ub_dex: i32,
    ub_fhr: i32,
    ub_res: [i32; 4],
    ub_skills: i32,
    ub_mf: i32,
    groups: Vec<CharmGroup>,
    suf_pos: Vec<StatTotals>,
    suf_neg_res: Vec<[i32; 4]>,
    order_str: Vec<UbGroupEntry>,
    order_dex: Vec<UbGroupEntry>,
    order_fhr: Vec<UbGroupEntry>,
    order_res: [Vec<UbGroupEntry>; 4],
    order_skills: Vec<UbGroupEntry>,
    order_mf: Vec<UbGroupEntry>,
    cache: HashMap<CharmCacheKey, Option<Vec<usize>>>,
}

impl<'a> CharmSolver<'a> {
    pub(crate) fn has_cold_sunder(&self) -> bool {
        !self.sunder_opts.is_empty()
    }

    pub(crate) fn charm_ub_stats(&self) -> Stats {
        let base = if let Some(&first) = self.sunder_opts.first() {
            let mut acc = Stats {
                all_skills: first.skills,
                fhr: first.fhr,
                fr: first.fr,
                lr: first.lr,
                cr: first.cr,
                pr: first.pr,
                mf: first.mf,
                str_bonus: first.str_bonus,
                dex_bonus: first.dex_bonus,
                ..Default::default()
            };
            for &s in &self.sunder_opts[1..] {
                acc = acc.max_each(Stats {
                    all_skills: s.skills,
                    fhr: s.fhr,
                    fr: s.fr,
                    lr: s.lr,
                    cr: s.cr,
                    pr: s.pr,
                    mf: s.mf,
                    str_bonus: s.str_bonus,
                    dex_bonus: s.dex_bonus,
                    ..Default::default()
                });
            }
            acc
        } else {
            Stats::default()
        };
        Stats {
            all_skills: base.all_skills + self.ub_skills,
            fhr: base.fhr + self.ub_fhr,
            fr: base.fr + self.ub_res[0],
            lr: base.lr + self.ub_res[1],
            cr: base.cr + self.ub_res[2],
            pr: base.pr + self.ub_res[3],
            mf: base.mf + self.ub_mf,
            str_bonus: base.str_bonus + self.ub_str,
            dex_bonus: base.dex_bonus + self.ub_dex,
            ..Default::default()
        }
    }

    pub(crate) fn new(
        raw_pool: &[&'a CharmSpec],
        c: &'a BuildConstraints,
        mode: SearchMode,
    ) -> Self {
        let raw_max_slots = c.max_charm_slots.max(0);
        let main_val_of = |ch: &CharmSpec| -> i32 {
            match mode {
                SearchMode::Power | SearchMode::Leveling => ch.skills.max(0),
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
                    s.life,
                    s.mana,
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
        let ub_res = [
            charm_stat_ub(&pool, max_slots, |ch| ch.fr),
            charm_stat_ub(&pool, max_slots, |ch| ch.lr),
            charm_stat_ub(&pool, max_slots, |ch| ch.cr),
            charm_stat_ub(&pool, max_slots, |ch| ch.pr),
        ];
        let ub_skills = charm_stat_ub(&pool, max_slots, |ch| ch.skills);
        let ub_mf = charm_stat_ub(&pool, max_slots, |ch| ch.mf);

        let is_relevant = |ch: &CharmSpec| {
            let helps_feas = ch.str_bonus > 0
                || ch.dex_bonus > 0
                || ch.fhr > 0
                || ch.fr > 0
                || ch.lr > 0
                || ch.cr > 0
                || ch.pr > 0;
            let helps_main = match mode {
                SearchMode::Power | SearchMode::Leveling => ch.skills > 0,
                SearchMode::Mf => ch.mf > 0,
                SearchMode::MaxRes | SearchMode::LevelingRes => {
                    ch.fr > 0 || ch.lr > 0 || ch.cr > 0 || ch.pr > 0
                }
            };
            helps_feas || helps_main
        };

        let mut unique_map: BTreeMap<i32, Vec<usize>> = BTreeMap::new();
        type MultiKey = (i32, i32, i32, i32, i32, i32, i32, i32, i32, i32);
        let mut multi_map: BTreeMap<MultiKey, Vec<usize>> = BTreeMap::new();

        for (idx, &ch) in pool.iter().enumerate() {
            if !is_relevant(ch) {
                continue;
            }
            if let Some(uid) = ch.unique_id {
                unique_map.entry(uid).or_default().push(idx);
            } else {
                let key = (
                    ch.size,
                    ch.fhr,
                    ch.fr,
                    ch.lr,
                    ch.cr,
                    ch.pr,
                    ch.mf,
                    ch.str_bonus,
                    ch.dex_bonus,
                    ch.skills,
                );
                multi_map.entry(key).or_default().push(idx);
            }
        }

        let mut groups: Vec<CharmGroup> = Vec::new();
        for (_, mut opts) in unique_map {
            opts.sort_by(|&a, &b| {
                let ca = pool[a];
                let cb = pool[b];
                let va = (main_val_of(ca), ca.skills, ca.life, ca.mana);
                let vb = (main_val_of(cb), cb.skills, cb.life, cb.mana);
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
            members.sort_by(|&a, &b| {
                let ca = pool[a];
                let cb = pool[b];
                (cb.life, cb.mana, cb.frw).cmp(&(ca.life, ca.mana, ca.frw))
            });
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
                        ch.life,
                        ch.mana,
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
                        ch.life,
                        ch.mana,
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
                res: [
                    suf_pos[i + 1].res[0] + gp.res[0],
                    suf_pos[i + 1].res[1] + gp.res[1],
                    suf_pos[i + 1].res[2] + gp.res[2],
                    suf_pos[i + 1].res[3] + gp.res[3],
                ],
                skills: suf_pos[i + 1].skills + gp.skills,
                mf: suf_pos[i + 1].mf + gp.mf,
            };
            let gn = groups[i].min_neg_res();
            for r in 0..4 {
                suf_neg_res[i][r] = suf_neg_res[i + 1][r] + gn[r];
            }
        }

        let order_str = sorted_ub_entries(&groups, &pool, |ch| ch.str_bonus);
        let order_dex = sorted_ub_entries(&groups, &pool, |ch| ch.dex_bonus);
        let order_fhr = sorted_ub_entries(&groups, &pool, |ch| ch.fhr);
        let order_res = [
            sorted_ub_entries(&groups, &pool, |ch| ch.fr),
            sorted_ub_entries(&groups, &pool, |ch| ch.lr),
            sorted_ub_entries(&groups, &pool, |ch| ch.cr),
            sorted_ub_entries(&groups, &pool, |ch| ch.pr),
        ];
        let order_skills = sorted_ub_entries(&groups, &pool, |ch| ch.skills);
        let order_mf = sorted_ub_entries(&groups, &pool, |ch| ch.mf);

        Self {
            pool,
            sunder_opts,
            c,
            mode,
            raw_max_slots,
            max_slots,
            sum_neg,
            ub_str,
            ub_dex,
            ub_fhr,
            ub_res,
            ub_skills,
            ub_mf,
            groups,
            suf_pos,
            suf_neg_res,
            order_str,
            order_dex,
            order_fhr,
            order_res,
            order_skills,
            order_mf,
            cache: HashMap::new(),
        }
    }

    fn main_score_of_indices(&self, idxs: &[usize], room: [i32; 4]) -> i32 {
        match self.mode {
            SearchMode::Power | SearchMode::Leveling => {
                idxs.iter().map(|&i| self.pool[i].skills).sum()
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

    fn max_res_gain_ub(&self, min_g_idx: usize, rem_slots: i32, rem_room: [i32; 4]) -> i32 {
        if rem_slots <= 0 {
            return 0;
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
        if per_res_ub == 0 {
            return 0;
        }
        let mut entries: Vec<(i32, i32, i32)> = Vec::new();
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
                        entries.push((val, *min_size, 1));
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
                        entries.push((val, *size, members.len() as i32));
                    }
                }
            }
        }
        entries.sort_by(|a, b| (b.0 as i64 * a.1 as i64).cmp(&(a.0 as i64 * b.1 as i64)));
        let mut rem = rem_slots;
        let mut joint_ub = 0;
        for (val, sz, cnt) in entries {
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
        init_delta: [i32; 7], // [str_delta, dex_delta, fhr_delta, fr_delta, lr_delta, cr_delta, pr_delta] (signed: >=0 means met, <0 means shortfall)
        room: [i32; 4],
        slot_budget: i32,
        forbidden_uid: Option<i32>,
        incumbent: Option<(i32, Vec<usize>)>,
    ) -> Option<Vec<usize>> {
        struct ExactCtx<'b, 'a> {
            solver: &'b CharmSolver<'a>,
            room: [i32; 4],
            forbidden_uid: Option<i32>,
            best_main: Option<i32>,
            best_indices: Option<Vec<usize>>,
            cur_indices: Vec<usize>,
        }

        fn dfs_charms(
            ctx: &mut ExactCtx<'_, '_>,
            g_idx: usize,
            rem_slots: i32,
            delta: [i32; 7],
            cur_res_added: [i32; 4],
            cur_skills: i32,
            cur_mf: i32,
        ) {
            let s = ctx.solver;
            let all_met = delta.iter().all(|&d| d >= 0);

            if all_met {
                let cur_main = match s.mode {
                    SearchMode::Power | SearchMode::Leveling => cur_skills,
                    SearchMode::Mf => cur_mf,
                    SearchMode::MaxRes | SearchMode::LevelingRes => (0..4)
                        .map(|r| cur_res_added[r].min(ctx.room[r]) - ctx.room[r].min(0))
                        .sum(),
                };
                if ctx.best_main.is_none_or(|b| cur_main > b) {
                    ctx.best_main = Some(cur_main);
                    ctx.best_indices = Some(ctx.cur_indices.clone());
                }
            }

            if g_idx == s.groups.len() || rem_slots == 0 {
                return;
            }

            // O(1) suffix feasibility check.
            let sp = s.suf_pos[g_idx];
            if delta[0] + sp.str_bonus < 0
                || delta[1] + sp.dex_bonus < 0
                || delta[2] + sp.fhr < 0
                || delta[3] + sp.res[0] < 0
                || delta[4] + sp.res[1] < 0
                || delta[5] + sp.res[2] < 0
                || delta[6] + sp.res[3] < 0
            {
                return;
            }

            // Objective upper-bound pruning once an incumbent exists.
            if let Some(best) = ctx.best_main {
                let ub_total = match s.mode {
                    SearchMode::Power | SearchMode::Leveling => {
                        cur_skills + eval_sorted_ub(&s.order_skills, g_idx, rem_slots)
                    }
                    SearchMode::Mf => cur_mf + eval_sorted_ub(&s.order_mf, g_idx, rem_slots),
                    SearchMode::MaxRes | SearchMode::LevelingRes => {
                        let cur_gain: i32 = (0..4)
                            .map(|r| cur_res_added[r].min(ctx.room[r]) - ctx.room[r].min(0))
                            .sum();
                        let rem_room = [
                            (ctx.room[0] - cur_res_added[0]).max(0),
                            (ctx.room[1] - cur_res_added[1]).max(0),
                            (ctx.room[2] - cur_res_added[2]).max(0),
                            (ctx.room[3] - cur_res_added[3]).max(0),
                        ];
                        cur_gain + s.max_res_gain_ub(g_idx, rem_slots, rem_room)
                    }
                };
                if ub_total <= best {
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
                            ],
                            [
                                cur_res_added[0] + ch.fr,
                                cur_res_added[1] + ch.lr,
                                cur_res_added[2] + ch.cr,
                                cur_res_added[3] + ch.pr,
                            ],
                            cur_skills + ch.skills,
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
                        ];
                        let gains = [
                            stats.str_bonus,
                            stats.dex_bonus,
                            stats.fhr,
                            stats.res[0],
                            stats.res[1],
                            stats.res[2],
                            stats.res[3],
                        ];
                        let mut cap = 0i32;
                        for i in 0..7 {
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

        let (best_main, best_indices) = match incumbent {
            Some((m, idxs)) => (Some(m), Some(idxs)),
            None => (None, None),
        };
        let mut ctx = ExactCtx {
            solver: self,
            room,
            forbidden_uid,
            best_main,
            best_indices,
            cur_indices: Vec::new(),
        };
        dfs_charms(&mut ctx, 0, slot_budget.max(0), init_delta, [0; 4], 0, 0);
        ctx.best_indices
    }

    pub(crate) fn solve(
        &mut self,
        items: &[&ItemSpec],
        leaf: Stats,
        reqs: (i32, i32),
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
                .solve_for_sunder(items, leaf, caps, reqs, 0, self.max_slots, None)
                .map(|idxs| idxs.into_iter().map(|i| self.pool[i]).collect());
        }

        if self.sunder_opts.len() == 1 {
            let sunder = self.sunder_opts[0];
            let slot_budget = (self.raw_max_slots - sunder.size).max(0);
            let leaf_s = add_charm_to_leaf(leaf, sunder);
            return self
                .solve_for_sunder(items, leaf_s, caps, reqs, 0, slot_budget, Some(sunder))
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
            let slot_budget = (self.raw_max_slots - sunder.size).max(0);
            let leaf_s = add_charm_to_leaf(leaf, sunder);
            let Some(idxs) =
                self.solve_for_sunder(items, leaf_s, caps, reqs, s_idx, slot_budget, Some(sunder))
            else {
                continue;
            };
            let rem_main = self.main_score_of_indices(&idxs, [0; 4]);
            let s_main = match self.mode {
                SearchMode::Power | SearchMode::Leveling => sunder.skills,
                SearchMode::Mf => sunder.mf,
                SearchMode::MaxRes | SearchMode::LevelingRes => 0,
            };
            let total_cr = leaf_s.cr + idxs.iter().map(|&i| self.pool[i].cr).sum::<i32>();
            let total_life = sunder.life + idxs.iter().map(|&i| self.pool[i].life).sum::<i32>();
            let total_mana = sunder.mana + idxs.iter().map(|&i| self.pool[i].mana).sum::<i32>();
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
        items: &[&ItemSpec],
        leaf: Stats,
        caps: [i32; 4],
        reqs: (i32, i32),
        sunder_idx: usize,
        slot_budget: i32,
        prepicked: Option<&'a CharmSpec>,
    ) -> Option<Vec<usize>> {
        // `leaf` already includes base_str, base_dex, base_hell_res, and any prepicked sunder.
        let need_str = (reqs.0 - leaf.str_bonus).max(0);
        let need_dex = (reqs.1 - leaf.dex_bonus).max(0);
        let need_fhr = (self.c.min_fhr - leaf.fhr).max(0);
        let leaf_res = [leaf.fr, leaf.lr, leaf.cr, leaf.pr];
        let mins = [self.c.min_fr, self.c.min_lr, self.c.min_cr, self.c.min_pr];
        let delta_res = [
            leaf_res[0].saturating_sub(mins[0]).min(-self.sum_neg[0]),
            leaf_res[1].saturating_sub(mins[1]).min(-self.sum_neg[1]),
            leaf_res[2].saturating_sub(mins[2]).min(-self.sum_neg[2]),
            leaf_res[3].saturating_sub(mins[3]).min(-self.sum_neg[3]),
        ];
        let room = if is_res_mode(self.mode) {
            let opt_caps = res_opt_caps(caps, self.mode);
            [
                (opt_caps[0] - leaf.fr).max(self.sum_neg[0]),
                (opt_caps[1] - leaf.lr).max(self.sum_neg[1]),
                (opt_caps[2] - leaf.cr).max(self.sum_neg[2]),
                (opt_caps[3] - leaf.pr).max(self.sum_neg[3]),
            ]
        } else {
            [
                (caps[0] - leaf.fr).max(0),
                (caps[1] - leaf.lr).max(0),
                (caps[2] - leaf.cr).max(0),
                (caps[3] - leaf.pr).max(0),
            ]
        };

        let key = CharmCacheKey {
            sunder_idx,
            need_str,
            need_dex,
            need_fhr,
            delta_res,
            room,
        };
        if let Some(cached) = self.cache.get(&key) {
            return cached.clone();
        }

        if need_str > self.ub_str
            || need_dex > self.ub_dex
            || need_fhr > self.ub_fhr
            || -delta_res[0] > self.ub_res[0]
            || -delta_res[1] > self.ub_res[1]
            || -delta_res[2] > self.ub_res[2]
            || -delta_res[3] > self.ub_res[3]
        {
            self.cache.insert(key, None);
            return None;
        }

        let greedy_res =
            greedy_charms_indices(items, &self.pool, self.c, reqs, self.mode, prepicked);
        let ub_main = match self.mode {
            SearchMode::Power | SearchMode::Leveling => self.ub_skills,
            SearchMode::Mf => self.ub_mf,
            SearchMode::MaxRes | SearchMode::LevelingRes => {
                (0..4).map(|r| room[r].max(0).min(self.ub_res[r])).sum()
            }
        };

        let incumbent = match &greedy_res {
            Some(idxs) => {
                let g_main = self.main_score_of_indices(idxs, room);
                if g_main >= ub_main {
                    self.cache.insert(key, greedy_res.clone());
                    return greedy_res;
                }
                Some((g_main, idxs.clone()))
            }
            None => None,
        };

        let init_delta = [
            -need_str,
            -need_dex,
            -need_fhr,
            delta_res[0],
            delta_res[1],
            delta_res[2],
            delta_res[3],
        ];
        let forbidden_uid = prepicked.and_then(|s| s.unique_id);
        let best_core = self.solve_exact(init_delta, room, slot_budget, forbidden_uid, incumbent);
        let final_indices = match (greedy_res, best_core) {
            (Some(g_idxs), Some(e_idxs)) => {
                if self.main_score_of_indices(&e_idxs, room)
                    > self.main_score_of_indices(&g_idxs, room)
                {
                    Some(self.top_off_filler(&e_idxs, leaf, caps, slot_budget, forbidden_uid))
                } else {
                    Some(g_idxs)
                }
            }
            (None, Some(e_idxs)) => {
                Some(self.top_off_filler(&e_idxs, leaf, caps, slot_budget, forbidden_uid))
            }
            (Some(g_idxs), None) => Some(g_idxs),
            (None, None) => None,
        };

        self.cache.insert(key, final_indices.clone());
        final_indices
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
        );
        if let Some(uid) = forbidden_uid {
            state.unique_ids.insert(uid);
        }
        for &idx in core {
            state.pick(idx);
        }
        let res_targets = [self.c.min_fr, self.c.min_lr, self.c.min_cr, self.c.min_pr];
        greedy_fill_remaining(&mut state, caps, res_targets, self.mode);
        state.chosen_indices
    }
}

fn add_charm_to_leaf(mut leaf: Stats, ch: &CharmSpec) -> Stats {
    leaf.str_bonus += ch.str_bonus;
    leaf.dex_bonus += ch.dex_bonus;
    leaf.fhr += ch.fhr;
    leaf.fr += ch.fr;
    leaf.lr += ch.lr;
    leaf.cr += ch.cr;
    leaf.pr += ch.pr;
    leaf
}

#[cfg(test)]
#[path = "charms_tests.rs"]
mod tests;
