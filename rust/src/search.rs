use std::cmp::Reverse;
use std::collections::{HashMap, HashSet};

#[cfg(feature = "python")]
use pyo3::exceptions::PyValueError;
#[cfg(feature = "python")]
use pyo3::prelude::*;

use crate::charms::{charm_stat_ub, greedy_charms};
use crate::eval::{eval_build_summary, res_caps};
use crate::types::{
    BuildConstraints, BuildResult, CharmSpec, ItemSpec, SearchMode, Stats, BASE_MAX_RES,
};

const EQUIP_SLOTS: &[&str] = &[
    "weapon", "shield", "helm", "armor", "amulet", "belt", "gloves", "boots",
];

fn eff_req(req: i32, self_bonus: i32) -> i32 {
    if req > 0 {
        req + self_bonus
    } else {
        0
    }
}

fn item_eff_reqs(item: &ItemSpec) -> (i32, i32) {
    (
        eff_req(item.req_str, item.str_bonus),
        eff_req(item.req_dex, item.dex_bonus),
    )
}

fn item_prune_reqs(item: &ItemSpec, base_str: i32, base_dex: i32) -> (i32, i32) {
    let (rs, rd) = item_eff_reqs(item);
    (
        if rs <= base_str { 0 } else { rs },
        if rd <= base_dex { 0 } else { rd },
    )
}

fn merge_reqs(cur: (i32, i32), next: (i32, i32)) -> (i32, i32) {
    (cur.0.max(next.0), cur.1.max(next.1))
}

type BuildScore = (i32, i32, i32, i32, i32, i32, i32, i32);
type BuildSig = (i32, i32, i32, i32, Vec<String>);

fn build_sig(res: &BuildResult) -> BuildSig {
    (
        res.skills,
        res.fcr_bp,
        res.fhr_bp,
        res.mf,
        res.items.iter().map(|i| i.name.clone()).collect(),
    )
}

/// Deduplicating result collector bounded to `limit` distinct signatures when `limit > 0`.
struct TopResults {
    limit: usize,
    seq: usize,
    entries: Vec<(BuildScore, usize, BuildSig, BuildResult)>,
}

impl TopResults {
    fn new(limit: usize) -> Self {
        Self {
            limit,
            seq: 0,
            entries: Vec::new(),
        }
    }

    fn would_accept(&self, score: BuildScore) -> bool {
        self.limit == 0
            || self.entries.len() < self.limit
            || self.entries.last().is_some_and(|worst| score > worst.0)
    }

    fn push(&mut self, score: BuildScore, res: BuildResult) {
        if !self.would_accept(score) {
            return;
        }

        let sig = build_sig(&res);
        let seq = self.seq;
        self.seq += 1;

        if let Some(pos) = self.entries.iter().position(|e| e.2 == sig) {
            if score > self.entries[pos].0 {
                self.entries[pos] = (score, seq, sig, res);
                self.entries.sort_by_key(|e| (Reverse(e.0), e.1));
            }
            return;
        }

        self.entries.push((score, seq, sig, res));
        self.entries.sort_by_key(|e| (Reverse(e.0), e.1));
        if self.limit > 0 {
            self.entries.truncate(self.limit);
        }
    }

    fn finish(self, total_evals: usize) -> Vec<BuildResult> {
        self.entries
            .into_iter()
            .map(|(_, _, _, mut res)| {
                res.evaluated_candidates = total_evals;
                res
            })
            .collect()
    }
}

#[derive(Clone)]
struct RingPair {
    combined: ItemSpec,
    first: ItemSpec,
    second: ItemSpec,
    reqs: (i32, i32),
}

fn item_sort_key(mode: SearchMode, s: &Stats) -> (i32, i32, i32, i32, i32, i32) {
    match mode {
        SearchMode::Mf => (
            s.mf,
            s.blizz_power_skills(),
            s.fcr,
            s.fr + s.lr,
            s.belt_slots,
            s.defense,
        ),
        SearchMode::Power => (
            s.blizz_power_skills(),
            s.total_skills(),
            s.fcr,
            s.fhr,
            s.belt_slots,
            s.defense,
        ),
        SearchMode::MaxRes => (
            s.max_res_sum(),
            s.res_sum(),
            s.blizz_power_skills(),
            s.fcr,
            s.belt_slots,
            s.defense,
        ),
    }
}

fn prune_slot_items(
    items: Vec<ItemSpec>,
    limit: usize,
    is_ring: bool,
    base_str: i32,
    base_dex: i32,
) -> Vec<ItemSpec> {
    if limit == 0 {
        return items;
    }
    let min_keep = if is_ring { limit.max(2) } else { limit };
    let same_name_cap = if is_ring { 2 } else { 1 };

    let mut stat_counts: HashMap<(Stats, i32, i32), usize> = HashMap::new();
    let mut name_stat_counts: HashMap<(String, Stats, i32, i32), usize> = HashMap::new();
    let mut deduped = Vec::with_capacity(items.len());
    for it in items {
        let s = it.stats();
        let (rs, rd) = item_prune_reqs(&it, base_str, base_dex);
        let ns_entry = name_stat_counts
            .entry((it.name.clone(), s, rs, rd))
            .or_insert(0);
        if *ns_entry >= same_name_cap {
            continue;
        }
        let s_entry = stat_counts.entry((s, rs, rd)).or_insert(0);
        if *s_entry >= min_keep {
            continue;
        }
        *ns_entry += 1;
        *s_entry += 1;
        deduped.push(it);
    }

    // Always keep the full first Pareto frontier so no trade-off item is lost,
    // peeling extra dominated layers only until at least `min_keep` items remain.
    // Rings occupy two slots, so a ring is only safely dominated once at least
    // 2 other active rings strictly dominate it (otherwise it can still be the
    // best partner for the single ring that dominates it).
    let metas: Vec<(Stats, (i32, i32))> = deduped
        .iter()
        .map(|it| (it.stats(), item_prune_reqs(it, base_str, base_dex)))
        .collect();
    let dominates = |a: usize, b: usize| {
        let (sa, ra) = metas[a];
        let (sb, rb) = metas[b];
        sa.dominates(sb) && ra.0 <= rb.0 && ra.1 <= rb.1 && (sa != sb || ra != rb)
    };

    let dom_threshold = if is_ring { 2 } else { 1 };
    let mut active = vec![true; deduped.len()];
    let mut active_count = deduped.len();
    let mut kept_indices = Vec::with_capacity(deduped.len());
    while active_count > 0 && kept_indices.len() < min_keep {
        let layer: Vec<usize> = (0..deduped.len())
            .filter(|&i| {
                active[i]
                    && (0..deduped.len())
                        .filter(|&j| active[j] && j != i && dominates(j, i))
                        .take(dom_threshold)
                        .count()
                        < dom_threshold
            })
            .collect();
        if layer.is_empty() {
            kept_indices.extend((0..deduped.len()).filter(|&i| active[i]));
            break;
        }
        for idx in layer {
            active[idx] = false;
            active_count -= 1;
            kept_indices.push(idx);
        }
    }

    let mut slots: Vec<Option<ItemSpec>> = deduped.into_iter().map(Some).collect();
    kept_indices
        .into_iter()
        .filter_map(|idx| slots[idx].take())
        .collect()
}

pub fn optimize_builds_core(
    items: &[ItemSpec],
    charms: &[CharmSpec],
    c: &BuildConstraints,
) -> Result<Vec<BuildResult>, String> {
    let mode = match c.mode.to_ascii_lowercase().as_str() {
        "power" => SearchMode::Power,
        "mf" => SearchMode::Mf,
        "max-res" => SearchMode::MaxRes,
        other => {
            return Err(format!(
                "invalid mode '{other}'; expected 'power', 'mf', or 'max-res'"
            ))
        }
    };

    let valid_item = |i: &ItemSpec| c.allow_mf || i.mf == 0;

    let mut groups: Vec<Vec<ItemSpec>> = Vec::with_capacity(EQUIP_SLOTS.len());
    for &slot in EQUIP_SLOTS {
        let mut slot_items: Vec<ItemSpec> = items
            .iter()
            .filter(|i| i.slot == slot && valid_item(i))
            .cloned()
            .collect();
        if slot_items.is_empty() {
            return Ok(Vec::new());
        }
        slot_items.sort_by_key(|it| Reverse(item_sort_key(mode, &it.stats())));
        groups.push(prune_slot_items(slot_items, c.limit, false, c.base_str, c.base_dex));
    }

    let mut rngs: Vec<ItemSpec> = items
        .iter()
        .filter(|i| i.slot == "ring" && valid_item(i))
        .cloned()
        .collect();
    if rngs.len() < 2 {
        return Ok(Vec::new());
    }
    rngs.sort_by_key(|it| Reverse(item_sort_key(mode, &it.stats())));
    let rngs = prune_slot_items(rngs, c.limit, true, c.base_str, c.base_dex);
    if rngs.len() < 2 {
        return Ok(Vec::new());
    }

    let mut ring_pairs: Vec<RingPair> = Vec::new();
    let mut seen_rp: HashSet<(Stats, i32, i32)> = HashSet::new();
    for i in 0..rngs.len() {
        for j in (i + 1)..rngs.len() {
            let r1 = &rngs[i];
            let r2 = &rngs[j];
            let rp_reqs = merge_reqs(item_eff_reqs(r1), item_eff_reqs(r2));
            let comb_stats = r1.stats().add(r2.stats());
            if !seen_rp.insert((comb_stats, rp_reqs.0, rp_reqs.1)) {
                continue;
            }
            let combined = ItemSpec::from_stats(
                format!("{} + {}", r1.name, r2.name),
                "rings".to_string(),
                format!("{} / {}", r1.loc, r2.loc),
                comb_stats,
                rp_reqs.0,
                rp_reqs.1,
            );
            ring_pairs.push(RingPair {
                combined,
                first: r1.clone(),
                second: r2.clone(),
                reqs: rp_reqs,
            });
        }
    }
    ring_pairs.sort_by_key(|rp| Reverse(item_sort_key(mode, &rp.combined.stats())));

    let n = groups.len() + 1;
    let mut suf = vec![Stats::default(); n + 1];
    suf[n - 1] = ring_pairs
        .iter()
        .fold(Stats::default(), |acc, rp| acc.max_each(rp.combined.stats()));
    for k in (0..groups.len()).rev() {
        let slot_max = groups[k]
            .iter()
            .fold(Stats::default(), |acc, it| acc.max_each(it.stats()));
        suf[k] = suf[k + 1].add(slot_max);
    }

    let pool: Vec<&CharmSpec> = charms
        .iter()
        .filter(|ch| (c.allow_mf || ch.mf == 0) && ch.light_skills == 0)
        .collect();
    let ch = Stats {
        all_skills: charm_stat_ub(&pool, c.max_charm_slots, |ch| ch.skills),
        fhr: charm_stat_ub(&pool, c.max_charm_slots, |ch| ch.fhr),
        fr: charm_stat_ub(&pool, c.max_charm_slots, |ch| ch.fr),
        lr: charm_stat_ub(&pool, c.max_charm_slots, |ch| ch.lr),
        cr: charm_stat_ub(&pool, c.max_charm_slots, |ch| ch.cr),
        pr: charm_stat_ub(&pool, c.max_charm_slots, |ch| ch.pr),
        mf: charm_stat_ub(&pool, c.max_charm_slots, |ch| ch.mf),
        str_bonus: charm_stat_ub(&pool, c.max_charm_slots, |ch| ch.str_bonus),
        dex_bonus: charm_stat_ub(&pool, c.max_charm_slots, |ch| ch.dex_bonus),
        ..Default::default()
    };

    struct State<'a> {
        groups: &'a [Vec<ItemSpec>],
        ring_pairs: &'a [RingPair],
        suf: &'a [Stats],
        ch: Stats,
        pool: &'a [&'a CharmSpec],
        c: &'a BuildConstraints,
        mode: SearchMode,
        best_sk: i32,
        best_mf: i32,
        best_res_sum: i32,
        chosen_slots: Vec<usize>,
        evals: usize,
        top_results: TopResults,
    }

    fn dfs(st: &mut State<'_>, idx: usize, acc: Stats, reqs: (i32, i32)) {
        let ub = acc.add(st.suf[idx]);
        if ub.fcr < st.c.min_fcr {
            return;
        }
        let ub_ch = ub.add(st.ch);
        if ub_ch.fhr < st.c.min_fhr
            || ub_ch.fr < st.c.min_fr
            || ub_ch.lr < st.c.min_lr
            || ub_ch.cr < st.c.min_cr
            || ub_ch.pr < st.c.min_pr
        {
            return;
        }
        let (cap_ub_fr, cap_ub_lr, cap_ub_cr, cap_ub_pr) = res_caps(ub);
        if cap_ub_fr < st.c.min_fr
            || cap_ub_lr < st.c.min_lr
            || cap_ub_cr < st.c.min_cr
            || cap_ub_pr < st.c.min_pr
        {
            return;
        }
        if ub_ch.str_bonus < reqs.0 || ub_ch.dex_bonus < reqs.1 {
            return;
        }
        if st.mode == SearchMode::Power
            && st.best_sk >= 0
            && ub_ch.blizz_power_skills() < st.best_sk - st.c.skill_slack
        {
            return;
        }
        if st.mode == SearchMode::Mf
            && st.best_mf >= 0
            && ub_ch.mf < st.best_mf - st.c.mf_slack
        {
            return;
        }
        if st.mode == SearchMode::MaxRes && st.best_res_sum >= 0 {
            let ub_res_sum = ub_ch.fr.min(cap_ub_fr)
                + ub_ch.lr.min(cap_ub_lr)
                + ub_ch.cr.min(cap_ub_cr)
                + ub_ch.pr.min(cap_ub_pr);
            if ub_res_sum < st.best_res_sum - 15 {
                return;
            }
        }

        if idx == st.groups.len() {
            for rp in st.ring_pairs {
                let leaf = acc.add(rp.combined.stats());
                if leaf.fcr < st.c.min_fcr {
                    continue;
                }
                let leaf_ch = leaf.add(st.ch);
                if leaf_ch.fhr < st.c.min_fhr
                    || leaf_ch.fr < st.c.min_fr
                    || leaf_ch.lr < st.c.min_lr
                    || leaf_ch.cr < st.c.min_cr
                    || leaf_ch.pr < st.c.min_pr
                {
                    continue;
                }
                let (final_req_str, final_req_dex) = merge_reqs(reqs, rp.reqs);
                if leaf_ch.str_bonus < final_req_str || leaf_ch.dex_bonus < final_req_dex {
                    continue;
                }
                st.evals += 1;

                let mut items_ref: Vec<&ItemSpec> = st
                    .chosen_slots
                    .iter()
                    .enumerate()
                    .map(|(g, &i)| &st.groups[g][i])
                    .collect();
                items_ref.push(&rp.first);
                items_ref.push(&rp.second);

                let Some(charms_sel) = greedy_charms(
                    &items_ref,
                    st.pool,
                    st.c,
                    (final_req_str, final_req_dex),
                    st.mode,
                ) else {
                    continue;
                };
                let gear = Stats {
                    fr: leaf.fr - st.c.base_hell_res,
                    lr: leaf.lr - st.c.base_hell_res,
                    cr: leaf.cr - st.c.base_hell_res,
                    pr: leaf.pr - st.c.base_hell_res,
                    ..leaf
                };
                let all_sk_non_wep: i32 = items_ref
                    .iter()
                    .filter(|i| !i.is_weapon_or_shield())
                    .map(|i| i.all_skills)
                    .sum();
                let sum = eval_build_summary(gear, all_sk_non_wep, &charms_sel, st.c);
                if sum.fcr < st.c.min_fcr || sum.fhr < st.c.min_fhr {
                    continue;
                }
                if sum.fr < st.c.min_fr
                    || sum.lr < st.c.min_lr
                    || sum.cr < st.c.min_cr
                    || sum.pr < st.c.min_pr
                {
                    continue;
                }
                let res_sum = sum.fr + sum.lr + sum.cr + sum.pr;
                let eff_blizz_sk = sum.skills + sum.blizz_skills;
                if eff_blizz_sk > st.best_sk {
                    st.best_sk = eff_blizz_sk;
                }
                if sum.mf > st.best_mf {
                    st.best_mf = sum.mf;
                }
                if res_sum > st.best_res_sum {
                    st.best_res_sum = res_sum;
                }
                let score = match st.mode {
                    SearchMode::Mf => (
                        sum.mf,
                        eff_blizz_sk,
                        sum.fcr_bp,
                        sum.fhr_bp,
                        sum.pr,
                        sum.life_bo,
                        sum.belt_slots,
                        sum.defense,
                    ),
                    SearchMode::Power => (
                        eff_blizz_sk,
                        sum.skills,
                        i32::from(sum.pr >= BASE_MAX_RES),
                        sum.pr,
                        sum.life_bo,
                        sum.mana_bo,
                        sum.belt_slots,
                        sum.defense,
                    ),
                    SearchMode::MaxRes => (
                        res_sum,
                        eff_blizz_sk,
                        sum.fcr_bp,
                        sum.fhr_bp,
                        sum.life_bo,
                        sum.fr_raw + sum.lr_raw + sum.cr_raw + sum.pr_raw,
                        sum.belt_slots,
                        sum.defense,
                    ),
                };
                if !st.top_results.would_accept(score) {
                    continue;
                }
                let res = sum.into_result(&items_ref, &charms_sel, 0);
                st.top_results.push(score, res);
            }
            return;
        }

        for i in 0..st.groups[idx].len() {
            let it = &st.groups[idx][i];
            st.chosen_slots.push(i);
            dfs(
                st,
                idx + 1,
                acc.add(it.stats()),
                merge_reqs(reqs, item_eff_reqs(it)),
            );
            st.chosen_slots.pop();
        }
    }

    let mut state = State {
        groups: &groups,
        ring_pairs: &ring_pairs,
        suf: &suf,
        ch,
        pool: &pool,
        c,
        mode,
        best_sk: -1,
        best_mf: -1,
        best_res_sum: -1,
        chosen_slots: Vec::with_capacity(groups.len()),
        evals: 0,
        top_results: TopResults::new(c.limit),
    };

    let init_acc = Stats {
        fr: c.base_hell_res,
        lr: c.base_hell_res,
        cr: c.base_hell_res,
        pr: c.base_hell_res,
        str_bonus: c.base_str,
        dex_bonus: c.base_dex,
        ..Default::default()
    };
    dfs(&mut state, 0, init_acc, (0, 0));

    let total_evals = state.evals;
    Ok(state.top_results.finish(total_evals))
}

/// Find top-ranked builds satisfying `constraints` using branch-and-bound DFS in Rust.
#[cfg(feature = "python")]
#[pyfunction]
pub fn optimize_builds(
    py: Python<'_>,
    items: Vec<ItemSpec>,
    charms: Vec<CharmSpec>,
    constraints: BuildConstraints,
) -> PyResult<Vec<BuildResult>> {
    py.allow_threads(|| optimize_builds_core(&items, &charms, &constraints))
        .map_err(PyValueError::new_err)
}

#[cfg(test)]
#[path = "search_tests.rs"]
mod tests;
