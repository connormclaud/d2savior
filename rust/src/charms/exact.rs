use std::collections::HashMap;

use super::dp::{CharmCacheKey, CharmGroup, eval_sorted_ub};
use super::greedy::{
    CharmState, charm_eff_life, charm_eff_mana, greedy_charms_indices, greedy_fill_remaining,
    is_res_mode, res_opt_caps,
};
use super::solver::CharmSolver;
use crate::eval::res_caps;
use crate::stats::Stats;
#[cfg(test)]
use crate::types::ItemSpec;
use crate::types::{CharmSpec, SearchMode};

impl<'a> CharmSolver<'a> {
    fn main_score_of_indices(&self, idxs: &[usize], room: [i32; 4]) -> i32 {
        match self.c.mode {
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
        let total_ub = eval_sorted_ub(&self.non_dps.order_res_total, min_g_idx, rem_slots);
        if total_ub < min_needed || total_ub == 0 {
            return total_ub;
        }
        let per_res_ub: i32 = (0..4)
            .map(|r| {
                if rem_room[r] <= 0 {
                    0
                } else {
                    rem_room[r].min(eval_sorted_ub(
                        &self.non_dps.order_res[r],
                        min_g_idx,
                        rem_slots,
                    ))
                }
            })
            .sum();
        if per_res_ub < min_needed || per_res_ub == 0 {
            return per_res_ub;
        }
        scratch.clear();
        for g in &self.non_dps.groups[min_g_idx..] {
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
        if is_res_mode(self.c.mode) && min_main_needed > 0 {
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
            let nd = &s.non_dps;
            let cur_main = match s.c.mode {
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
                        let Some(need_s) = nd.pure_axes[d].min_slots_for(-delta[d]) else {
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
                            next_indices.extend_from_slice(&nd.pure_axes[d].best_picks[need_s]);
                        }
                    }
                    ctx.best_indices = Some(next_indices);
                }
            }

            if g_idx == nd.groups.len() || rem_slots == 0 {
                return;
            }

            // O(1) suffix feasibility and joint multi-axis pure-slot checks.
            let sp = nd.suf_pos[g_idx];
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
                if delta[d] + suf_vals[d] + nd.pure_axes[d].max_gain < 0 {
                    return;
                }
            }
            let mut must_pure_slots = 0usize;
            for d in 0..9 {
                if delta[d] < 0 {
                    let must_pure = -delta[d] - suf_vals[d];
                    if must_pure > 0 {
                        let Some(need_s) = nd.pure_axes[d].min_slots_for(must_pure) else {
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
                let can_beat = match s.c.mode {
                    SearchMode::Power | SearchMode::Leveling => {
                        cur_skills + eval_sorted_ub(&nd.order_skills, g_idx, rem_dfs_slots) > best
                    }
                    SearchMode::Mf => {
                        cur_mf + eval_sorted_ub(&nd.order_mf, g_idx, rem_dfs_slots) > best
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
            if delta[0] < 0 && delta[0] + eval_sorted_ub(&nd.order_str, g_idx, rem_slots) < 0 {
                return;
            }
            if delta[1] < 0 && delta[1] + eval_sorted_ub(&nd.order_dex, g_idx, rem_slots) < 0 {
                return;
            }
            if delta[2] < 0 && delta[2] + eval_sorted_ub(&nd.order_fhr, g_idx, rem_slots) < 0 {
                return;
            }
            for r in 0..4 {
                if delta[3 + r] < 0
                    && delta[3 + r] + eval_sorted_ub(&nd.order_res[r], g_idx, rem_slots) < 0
                {
                    return;
                }
            }
            if delta[7] < 0 && delta[7] + eval_sorted_ub(&nd.order_frw, g_idx, rem_slots) < 0 {
                return;
            }
            if delta[8] < 0 && delta[8] + eval_sorted_ub(&nd.order_mf, g_idx, rem_slots) < 0 {
                return;
            }

            match &nd.groups[g_idx] {
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
                    let has_main = match s.c.mode {
                        SearchMode::Power | SearchMode::Leveling => stats.skills > 0,
                        SearchMode::Mf => stats.mf > 0,
                        SearchMode::MaxRes | SearchMode::LevelingRes => {
                            let neg_next = nd.suf_neg_res[g_idx + 1];
                            (0..4).any(|r| {
                                stats.res[r] > 0 && cur_res_added[r] + neg_next[r] < ctx.room[r]
                            })
                        }
                    };
                    let max_useful = if has_main {
                        max_k
                    } else {
                        let neg_next = nd.suf_neg_res[g_idx + 1];
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
            scratch: Vec::with_capacity(self.non_dps.groups.len()),
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
        let caps_t = res_caps(leaf, &self.c);
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

        let mode = self.c.mode;
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
            let leaf_s = leaf.add(sunder.to_stats(self.c.class));
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
            let leaf_s = leaf.add(sunder.to_stats(self.c.class));
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
            let total_life = charm_eff_life(sunder, self.c.class)
                + idxs
                    .iter()
                    .map(|&i| charm_eff_life(self.pool[i], self.c.class))
                    .sum::<i32>();
            let total_mana = charm_eff_mana(sunder, self.c.class)
                + idxs
                    .iter()
                    .map(|&i| charm_eff_mana(self.pool[i], self.c.class))
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
        let uses_room_in_cache =
            is_res_mode(self.c.mode) || self.c.mode == SearchMode::Leveling;
        let room = if is_res_mode(self.c.mode) {
            let opt_caps = res_opt_caps(caps, self.c.mode, &self.c);
            [
                (opt_caps[0] - leaf.fr).max(self.sum_neg[0]),
                (opt_caps[1] - leaf.lr).max(self.sum_neg[1]),
                (opt_caps[2] - leaf.cr).max(self.sum_neg[2]),
                (opt_caps[3] - leaf.pr).max(self.sum_neg[3]),
            ]
        } else if self.c.mode == SearchMode::Leveling {
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

        if need_str > self.ub.str_bonus
            || need_dex > self.ub.dex_bonus
            || need_fhr > self.ub.fhr
            || need_frw > self.ub.frw
            || need_mf > self.ub.mf
            || -delta_res[0] > self.ub.res[0]
            || -delta_res[1] > self.ub.res[1]
            || -delta_res[2] > self.ub.res[2]
            || -delta_res[3] > self.ub.res[3]
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

        let ub_main = match self.c.mode {
            SearchMode::Power | SearchMode::Leveling => {
                eval_sorted_ub(&self.non_dps.order_skills, 0, slot_budget)
            }
            SearchMode::Mf => eval_sorted_ub(&self.non_dps.order_mf, 0, slot_budget),
            SearchMode::MaxRes | SearchMode::LevelingRes => {
                (0..4).map(|r| room[r].max(0).min(self.ub.res[r])).sum()
            }
        };
        if ub_main < min_main_needed {
            record_failed_floor(&mut self.failed_floor);
            return None;
        }

        if is_res_mode(self.c.mode) && min_main_needed > 0 {
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
            &self.c,
            reqs,
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
                self.cache.insert(key, Some((g_main, g_idxs.clone())));
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
            &self.c,
            caps,
            res_targets,
            self.c.mode,
            self.c.class,
            true,
        );
        state.chosen_indices
    }
}
