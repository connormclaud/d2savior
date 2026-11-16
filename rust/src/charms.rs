use std::collections::{HashMap, HashSet};

use crate::eval::res_caps;
use crate::types::{BuildConstraints, CharmSpec, ItemSpec, SearchMode, Stats};

struct CharmState<'a, 'b> {
    pool: &'b [&'a CharmSpec],
    rem: Vec<bool>,
    used: i32,
    max_slots: i32,
    cur_fhr: i32,
    cur_res: [i32; 4],
    cur_str: i32,
    cur_dex: i32,
    chosen: Vec<&'a CharmSpec>,
    unique_ids: HashSet<i32>,
}

impl<'a, 'b> CharmState<'a, 'b> {
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
        self.chosen.push(c);
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
    let mut best_unique: HashMap<i32, (i32, i32)> = HashMap::new();
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
                let key = (c.fhr.min(need) as f64 / c.size.max(1) as f64, c.skills, c.fhr);
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

fn greedy_charms_pass<'a>(
    items: &[&ItemSpec],
    pool: &[&'a CharmSpec],
    c: &BuildConstraints,
    reqs: (i32, i32),
    mode: SearchMode,
    fhr_first: bool,
) -> Option<Vec<&'a CharmSpec>> {
    let gear = items.iter().fold(Stats::default(), |acc, i| acc.add(i.stats()));
    let (cap_fr, cap_lr, cap_cr, cap_pr) = res_caps(gear);
    if c.min_fr > cap_fr || c.min_lr > cap_lr || c.min_cr > cap_cr || c.min_pr > cap_pr {
        return None;
    }
    let mut state = CharmState {
        pool,
        rem: vec![true; pool.len()],
        used: 0,
        max_slots: c.max_charm_slots,
        cur_fhr: gear.fhr,
        cur_res: [
            c.base_hell_res + gear.fr,
            c.base_hell_res + gear.lr,
            c.base_hell_res + gear.cr,
            c.base_hell_res + gear.pr,
        ],
        cur_str: c.base_str + gear.str_bonus,
        cur_dex: c.base_dex + gear.dex_bonus,
        chosen: Vec::new(),
        unique_ids: HashSet::new(),
    };

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
        SearchMode::Power | SearchMode::MaxRes => (0.0, 0.2),
    };
    let res_targets = [c.min_fr, c.min_lr, c.min_cr, c.min_pr];
    if fhr_first {
        greedy_fhr_loop(&mut state, c.min_fhr);
        greedy_res_loop(&mut state, res_targets, [1.5, 1.5, 1.2, 1.0], mf_w, sk_w);
    } else {
        greedy_res_loop(&mut state, res_targets, [1.5, 1.5, 1.2, 1.0], mf_w, sk_w);
        greedy_fhr_loop(&mut state, c.min_fhr);
    }

    if mode == SearchMode::MaxRes {
        greedy_res_loop(
            &mut state,
            [cap_fr, cap_lr, cap_cr, cap_pr],
            [1.0, 1.0, 1.0, 1.0],
            0.0,
            0.2,
        );
    }

    let mut mf_indices: Vec<usize> =
        (0..pool.len()).filter(|&i| state.can_pick(i) && pool[i].mf > 0).collect();
    mf_indices.sort_by(|&a, &b| {
        let ka = (pool[a].mf * 100 / pool[a].size.max(1), pool[a].skills, pool[a].lr);
        let kb = (pool[b].mf * 100 / pool[b].size.max(1), pool[b].skills, pool[b].lr);
        kb.cmp(&ka)
    });

    let mut sk_indices: Vec<usize> =
        (0..pool.len()).filter(|&i| state.can_pick(i) && pool[i].skills > 0).collect();
    sk_indices.sort_by(|&a, &b| {
        let ca = pool[a];
        let cb = pool[b];
        let eff = (cb.skills * ca.size.max(1)).cmp(&(ca.skills * cb.size.max(1)));
        eff.then_with(|| {
            (cb.skills, cb.life, cb.fr + cb.lr + cb.cr, cb.mana)
                .cmp(&(ca.skills, ca.life, ca.fr + ca.lr + ca.cr, ca.mana))
        })
    });

    let pick_ordered = |state: &mut CharmState<'_, '_>, indices: Vec<usize>| {
        for idx in indices {
            if state.can_pick(idx) && state.preserves_res_targets(idx, res_targets) {
                state.pick(idx);
            }
        }
    };

    if mode == SearchMode::Mf {
        pick_ordered(&mut state, mf_indices);
        pick_ordered(&mut state, sk_indices);
    } else {
        pick_ordered(&mut state, sk_indices);
    }

    loop {
        let mut best_idx = None;
        let mut best_score = 0.0_f64;
        for (idx, c) in pool.iter().enumerate() {
            if !state.can_pick(idx) || !state.preserves_res_targets(idx, res_targets) {
                continue;
            }
            let mut s = c.life as f64
                + c.mana as f64 * 0.4
                + (cap_pr - state.cur_res[3]).max(0).min(c.pr) as f64 * 1.2;
            if state.cur_res[0] < cap_fr {
                s += (cap_fr - state.cur_res[0]).min(c.fr) as f64 * 2.0;
            }
            if state.cur_res[1] < cap_lr {
                s += (cap_lr - state.cur_res[1]).min(c.lr) as f64 * 2.0;
            }
            if state.cur_res[2] < cap_cr {
                s += (cap_cr - state.cur_res[2]).min(c.cr) as f64 * 1.5;
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

    if state.cur_fhr < c.min_fhr
        || state.cur_res[0] < c.min_fr
        || state.cur_res[1] < c.min_lr
        || state.cur_res[2] < c.min_cr
        || state.cur_res[3] < c.min_pr
    {
        return None;
    }

    Some(state.chosen)
}

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

#[cfg(test)]
#[path = "charms_tests.rs"]
mod tests;
