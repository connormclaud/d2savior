use std::collections::{BTreeMap, HashMap};

use super::greedy::{charm_eff_life, charm_eff_mana};
use crate::dps::{CthEval, FastLeafDps};
use crate::types::{CharClass, CharmSpec};

#[derive(Clone, Copy, Default)]
pub(super) struct StatTotals {
    pub(super) str_bonus: i32,
    pub(super) dex_bonus: i32,
    pub(super) fhr: i32,
    pub(super) frw: i32,
    pub(super) res: [i32; 4],
    pub(super) skills: i32,
    pub(super) all_skills: i32,
    pub(super) class_skills: i32,
    pub(super) general_skills: i32,
    pub(super) action_skills: i32,
    pub(super) aura_skills: i32,
    pub(super) mf: i32,
    pub(super) ar: i32,
    pub(super) flat_phys_2x: i32,
    pub(super) flat_fire_2x: i32,
    pub(super) flat_elem_2x: i32,
    pub(super) psn_dps_2x: i32,
}

impl StatTotals {
    pub(super) fn from_charm(c: &CharmSpec) -> Self {
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

    pub(super) fn max_each(self, o: Self) -> Self {
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

    pub(super) fn clamp_non_neg(self) -> Self {
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

    pub(super) fn add_scaled(self, o: Self, k: i32) -> Self {
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
pub(super) enum CharmGroup {
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
    pub(super) fn max_pos_total(&self) -> StatTotals {
        match self {
            CharmGroup::Unique { max_pos, .. } => *max_pos,
            CharmGroup::Multi { members, stats, .. } => {
                StatTotals::default().add_scaled(stats.clamp_non_neg(), members.len() as i32)
            }
        }
    }

    pub(super) fn min_neg_res(&self) -> [i32; 4] {
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

    pub(super) fn ub_entry_with_pool(
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
pub(super) struct CharmCacheKey {
    pub(super) sunder_idx: usize,
    pub(super) slot_budget: i32,
    pub(super) need_str: i32,
    pub(super) need_dex: i32,
    pub(super) need_fhr: i32,
    pub(super) need_frw: i32,
    pub(super) need_mf: i32,
    pub(super) delta_res: [i32; 4],
    pub(super) room: [i32; 4],
}

#[derive(Clone, Default)]
pub(super) struct PureAxisDp {
    pub(super) best_gain: Vec<i32>,
    pub(super) best_picks: Vec<Vec<usize>>,
    pub(super) max_gain: i32,
}

impl PureAxisDp {
    pub(super) fn build(
        items: &[(usize, &CharmSpec, i32)],
        max_slots: i32,
        class: CharClass,
    ) -> Self {
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
    pub(super) fn min_slots_for(&self, need: i32) -> Option<usize> {
        if need <= 0 {
            return Some(0);
        }
        if need > self.max_gain {
            return None;
        }
        Some(self.best_gain.partition_point(|&g| g < need))
    }
}

#[derive(Clone, Copy)]
pub(super) struct UbGroupEntry {
    pub(super) g_idx: usize,
    pub(super) val: i32,
    pub(super) size: i32,
    pub(super) count: i32,
}

pub(super) fn sorted_ub_entries(
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

#[derive(Clone, Copy, Default)]
pub(super) struct PureDpsState {
    pub(super) ar: i32,
    pub(super) phys_2x: i32,
    pub(super) elem_2x: i32,
    pub(super) fire_2x: i32,
    pub(super) psn_2x: i32,
    pub(super) picks: u64,
    pub(super) ar_idx: u16,
}

#[derive(Default, Clone)]
struct PureDpsGroup {
    size: i32,
    flat_phys_2x: i32,
    flat_fire_2x: i32,
    flat_elem_2x: i32,
    psn_dps_2x: i32,
    prefix_ar: Vec<i32>,
    prefix_mask: Vec<u64>,
}

#[derive(Default, Clone)]
pub(super) struct PureDpsSolver {
    pub(super) item_indices: Vec<usize>,
    pareto_by_slot: Vec<Vec<PureDpsState>>,
    unique_ars: Vec<i32>,
    max_stats_by_slot: Vec<(i32, i32, i32, i32, i32)>,
}

impl PureDpsSolver {
    pub(super) fn is_empty(&self) -> bool {
        self.item_indices.is_empty()
    }

    pub(super) fn build<'a>(
        pool: &[&'a CharmSpec],
        pure_indices: &[usize],
        max_slots: i32,
    ) -> (Self, Vec<(usize, &'a CharmSpec, i32)>, Vec<usize>) {
        let mut by_key: BTreeMap<[i32; 5], Vec<usize>> = BTreeMap::new();
        for &idx in pure_indices {
            let ch = pool[idx];
            let key = [
                ch.size.max(1),
                ch.flat_phys_2x,
                ch.flat_fire_2x,
                ch.flat_elem_2x,
                ch.psn_dps_2x,
            ];
            by_key.entry(key).or_default().push(idx);
        }
        let mut by_key_sorted: Vec<([i32; 5], Vec<usize>)> = by_key.into_iter().collect();
        by_key_sorted.sort_by_key(|(k, _)| std::cmp::Reverse([k[1], k[2], k[3], k[4], k[0]]));

        let mut item_indices = Vec::new();
        let mut groups = Vec::new();
        let mut ub_items = Vec::new();
        let mut overflow = Vec::new();

        for (key, mut members) in by_key_sorted {
            let size = key[0];
            members.sort_by(|&a, &b| pool[b].ar.cmp(&pool[a].ar));
            let max_copies = (max_slots / size).max(0) as usize;
            members.truncate(max_copies);
            if members.is_empty() {
                continue;
            }
            let room = 64usize.saturating_sub(item_indices.len());
            if members.len() > room {
                overflow.extend_from_slice(&members[room..]);
                members.truncate(room);
            }
            if members.is_empty() {
                continue;
            }
            let mut prefix_ar = Vec::with_capacity(members.len() + 1);
            let mut prefix_mask = Vec::with_capacity(members.len() + 1);
            prefix_ar.push(0);
            prefix_mask.push(0);
            let mut acc_ar = 0i32;
            let mut acc_mask = 0u64;
            for &idx in &members {
                let bit = 1u64 << item_indices.len();
                item_indices.push(idx);
                ub_items.push((idx, pool[idx], 0));
                acc_ar += pool[idx].ar;
                acc_mask |= bit;
                prefix_ar.push(acc_ar);
                prefix_mask.push(acc_mask);
            }
            groups.push(PureDpsGroup {
                size,
                flat_phys_2x: key[1],
                flat_fire_2x: key[2],
                flat_elem_2x: key[3],
                psn_dps_2x: key[4],
                prefix_ar,
                prefix_mask,
            });
        }

        let pareto_by_slot = if groups.is_empty() || max_slots <= 0 {
            Vec::new()
        } else {
            let cap = max_slots as usize;
            let mut dp: Vec<Vec<PureDpsState>> = vec![Vec::new(); cap + 1];
            dp[0].push(PureDpsState::default());

            for g in &groups {
                let g_sz = g.size as usize;
                let max_k = g.prefix_ar.len() - 1;
                let mut touched = vec![false; cap + 1];
                for s in (0..=cap).rev() {
                    if dp[s].is_empty() {
                        continue;
                    }
                    let src_len = dp[s].len();
                    for k in 1..=max_k {
                        let ns = s + k * g_sz;
                        if ns > cap {
                            break;
                        }
                        touched[ns] = true;
                        let d_ar = g.prefix_ar[k];
                        let d_phys = (k as i32) * g.flat_phys_2x;
                        let d_fire = (k as i32) * g.flat_fire_2x;
                        let d_elem = (k as i32) * g.flat_elem_2x;
                        let d_psn = (k as i32) * g.psn_dps_2x;
                        let mask = g.prefix_mask[k];
                        for i in 0..src_len {
                            let st = dp[s][i];
                            dp[ns].push(PureDpsState {
                                ar: st.ar + d_ar,
                                phys_2x: st.phys_2x + d_phys,
                                elem_2x: st.elem_2x + d_elem,
                                fire_2x: st.fire_2x + d_fire,
                                psn_2x: st.psn_2x + d_psn,
                                picks: st.picks | mask,
                                ar_idx: 0,
                            });
                        }
                    }
                }

                for (ns, list) in dp.iter_mut().enumerate() {
                    if !touched[ns] || list.len() <= 1 {
                        continue;
                    }
                    list.sort_by(|a, b| {
                        b.ar.cmp(&a.ar)
                            .then_with(|| b.phys_2x.cmp(&a.phys_2x))
                            .then_with(|| b.elem_2x.cmp(&a.elem_2x))
                            .then_with(|| b.fire_2x.cmp(&a.fire_2x))
                            .then_with(|| b.psn_2x.cmp(&a.psn_2x))
                            .then_with(|| a.picks.cmp(&b.picks))
                    });
                    let mut kept: Vec<PureDpsState> = Vec::with_capacity(list.len());
                    'outer: for &cand in list.iter() {
                        for &prev in &kept {
                            if prev.ar >= cand.ar
                                && prev.phys_2x >= cand.phys_2x
                                && prev.elem_2x >= cand.elem_2x
                                && prev.fire_2x >= cand.fire_2x
                                && prev.psn_2x >= cand.psn_2x
                            {
                                continue 'outer;
                            }
                        }
                        kept.push(cand);
                    }
                    *list = kept;
                }
            }

            let mut frontier: Vec<PureDpsState> = vec![PureDpsState::default()];
            for list in dp.iter_mut().skip(1) {
                list.retain(|cand| {
                    !frontier.iter().any(|prev| {
                        prev.ar >= cand.ar
                            && prev.phys_2x >= cand.phys_2x
                            && prev.elem_2x >= cand.elem_2x
                            && prev.fire_2x >= cand.fire_2x
                            && prev.psn_2x >= cand.psn_2x
                    })
                });
                for &st in list.iter() {
                    frontier.retain(|f| {
                        !(st.ar >= f.ar
                            && st.phys_2x >= f.phys_2x
                            && st.elem_2x >= f.elem_2x
                            && st.fire_2x >= f.fire_2x
                            && st.psn_2x >= f.psn_2x)
                    });
                    frontier.push(st);
                }
            }
            dp
        };

        let mut unique_ars = Vec::new();
        let mut max_stats_by_slot = Vec::new();
        let mut pareto_by_slot = pareto_by_slot;
        if !pareto_by_slot.is_empty() {
            let mut ar_map: HashMap<i32, u16> = HashMap::new();
            max_stats_by_slot.reserve(pareto_by_slot.len());
            let mut run = (0i32, 0i32, 0i32, 0i32, 0i32);
            for (s, list) in pareto_by_slot.iter_mut().enumerate() {
                if s > 0 {
                    for st in list.iter_mut() {
                        run.0 = run.0.max(st.ar);
                        run.1 = run.1.max(st.phys_2x);
                        run.2 = run.2.max(st.elem_2x);
                        run.3 = run.3.max(st.fire_2x);
                        run.4 = run.4.max(st.psn_2x);
                        st.ar_idx = if let Some(&idx) = ar_map.get(&st.ar) {
                            idx
                        } else if unique_ars.len() < u16::MAX as usize {
                            let idx = unique_ars.len() as u16;
                            unique_ars.push(st.ar);
                            ar_map.insert(st.ar, idx);
                            idx
                        } else {
                            u16::MAX
                        };
                    }
                }
                max_stats_by_slot.push(run);
            }
        }

        (
            Self {
                item_indices,
                pareto_by_slot,
                unique_ars,
                max_stats_by_slot,
            },
            ub_items,
            overflow,
        )
    }

    #[inline]
    pub(super) fn max_dps_ub(&self, fast: &FastLeafDps, max_s: usize) -> f64 {
        if self.max_stats_by_slot.is_empty() || max_s == 0 {
            return fast.eval_eff_dps();
        }
        let lim = max_s.min(self.max_stats_by_slot.len() - 1);
        let (ar, phys, elem, fire, psn) = self.max_stats_by_slot[lim];
        fast.eval_dps(ar, phys, elem, fire, psn)
    }

    pub(super) fn solve_for_leaf_into(
        &self,
        fast: &FastLeafDps,
        max_s: usize,
        cth_cache: &mut Vec<Option<CthEval>>,
        out: &mut Vec<(f64, u64)>,
    ) {
        out.clear();
        let base_dps = fast.eval_eff_dps();
        if self.pareto_by_slot.is_empty() || max_s == 0 {
            out.resize(max_s + 1, (base_dps, 0));
            return;
        }
        out.push((base_dps, 0));
        let lim = max_s.min(self.pareto_by_slot.len() - 1);
        if fast.cth_is_const {
            let mut cth = fast.const_cth_eval();
            for s in 1..=lim {
                let mut best = out[s - 1];
                for st in &self.pareto_by_slot[s] {
                    let v = fast.eval_dps_with_cth(
                        &mut cth,
                        st.phys_2x,
                        st.elem_2x,
                        st.fire_2x,
                        st.psn_2x,
                    );
                    if v > best.0 {
                        best = (v, st.picks);
                    }
                }
                out.push(best);
            }
        } else {
            cth_cache.clear();
            cth_cache.resize(self.unique_ars.len(), None);
            for s in 1..=lim {
                let mut best = out[s - 1];
                for st in &self.pareto_by_slot[s] {
                    let idx = st.ar_idx as usize;
                    let mut fallback;
                    let cth_ref = if idx < cth_cache.len() {
                        cth_cache[idx].get_or_insert_with(|| fast.eval_cth_no_psn(st.ar))
                    } else {
                        fallback = fast.eval_cth_no_psn(st.ar);
                        &mut fallback
                    };
                    let v = fast.eval_dps_with_cth(
                        cth_ref,
                        st.phys_2x,
                        st.elem_2x,
                        st.fire_2x,
                        st.psn_2x,
                    );
                    if v > best.0 {
                        best = (v, st.picks);
                    }
                }
                out.push(best);
            }
        }
        if max_s > lim {
            let last = *out.last().unwrap_or(&(base_dps, 0));
            out.resize(max_s + 1, last);
        }
    }

    #[cfg(test)]
    pub(super) fn solve_for_leaf(&self, fast: &FastLeafDps, max_s: usize) -> Vec<(f64, u64)> {
        let mut cth_cache = Vec::new();
        let mut out = Vec::with_capacity(max_s + 1);
        self.solve_for_leaf_into(fast, max_s, &mut cth_cache, &mut out);
        out
    }
}

#[inline]
pub(super) fn min_slots_for_val(table: &[i32], deficit: i32) -> i32 {
    if deficit <= 0 {
        return 0;
    }
    table
        .iter()
        .position(|&v| v >= deficit)
        .map_or(i32::MAX, |s| s as i32)
}

#[inline]
pub(super) fn min_slots_for_res_axis(table: &[[i32; 4]], axis: usize, deficit: i32) -> i32 {
    if deficit <= 0 {
        return 0;
    }
    table
        .iter()
        .position(|row| row[axis] >= deficit)
        .map_or(i32::MAX, |s| s as i32)
}

pub(super) fn eval_sorted_ub(
    entries: &[UbGroupEntry],
    min_g_idx: usize,
    mut rem_slots: i32,
) -> i32 {
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
