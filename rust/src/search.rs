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

const SINGLE_SLOTS: &[&str] = &["helm", "armor", "amulet", "belt", "gloves", "boots"];

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

fn normalize_reqs(reqs: (i32, i32), base_str: i32, base_dex: i32) -> (i32, i32) {
    (
        if reqs.0 <= base_str { 0 } else { reqs.0 },
        if reqs.1 <= base_dex { 0 } else { reqs.1 },
    )
}

fn item_prune_reqs(item: &ItemSpec, base_str: i32, base_dex: i32) -> (i32, i32) {
    normalize_reqs(item_eff_reqs(item), base_str, base_dex)
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

    fn nth_main_score(&self) -> Option<i32> {
        if self.limit > 0 && self.entries.len() >= self.limit {
            self.entries.last().map(|e| e.0 .0)
        } else {
            None
        }
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
struct ItemPair {
    combined: ItemSpec,
    first: ItemSpec,
    second: ItemSpec,
    reqs: (i32, i32),
}

impl ItemPair {
    fn from_pair(first: &ItemSpec, second: &ItemSpec, slot: &str) -> Self {
        let reqs = merge_reqs(item_eff_reqs(first), item_eff_reqs(second));
        let comb_stats = first.stats().add(second.stats());
        let loc = match (first.loc.is_empty(), second.loc.is_empty()) {
            (true, true) => String::new(),
            (false, true) => first.loc.clone(),
            (true, false) => second.loc.clone(),
            (false, false) => format!("{} / {}", first.loc, second.loc),
        };
        let combined = ItemSpec::from_stats(
            format!("{} + {}", first.name, second.name),
            slot.to_string(),
            loc,
            comb_stats,
            reqs.0,
            reqs.1,
        );
        Self {
            combined,
            first: first.clone(),
            second: second.clone(),
            reqs,
        }
    }

    fn single_2h(w2h: ItemSpec) -> Self {
        let reqs = item_eff_reqs(&w2h);
        let mut combined = w2h.clone();
        combined.slot = "hands".to_string();
        Self {
            combined,
            first: w2h,
            second: ItemSpec::empty("shield"),
            reqs,
        }
    }
}

fn dominates_empty(stats: Stats, norm_reqs: (i32, i32)) -> bool {
    stats.dominates(Stats::default())
        && norm_reqs == (0, 0)
        && stats != Stats::default()
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

fn prune_candidates<T>(
    items: Vec<T>,
    limit: usize,
    is_ring: bool,
    base_str: i32,
    base_dex: i32,
    meta: impl Fn(&T) -> (&str, Stats, (i32, i32)),
) -> Vec<T> {
    if limit == 0 {
        return items;
    }
    let dom_threshold = if is_ring { limit + 1 } else { limit };
    let same_name_cap = if is_ring { 2 } else { 1 };

    let mut stat_counts: HashMap<(Stats, i32, i32), usize> = HashMap::new();
    let mut name_stat_counts: HashMap<(String, Stats, i32, i32), usize> = HashMap::new();
    let mut deduped = Vec::with_capacity(items.len());
    for it in items {
        let (name, s, eff_reqs) = meta(&it);
        let (rs, rd) = normalize_reqs(eff_reqs, base_str, base_dex);
        let ns_entry = name_stat_counts
            .entry((name.to_string(), s, rs, rd))
            .or_insert(0);
        if *ns_entry >= same_name_cap {
            continue;
        }
        let s_entry = stat_counts.entry((s, rs, rd)).or_insert(0);
        if *s_entry >= dom_threshold {
            continue;
        }
        *ns_entry += 1;
        *s_entry += 1;
        deduped.push(it);
    }

    // Keep every candidate strictly dominated by fewer than `dom_threshold` others
    // (`limit` for single slots, `limit + 1` for rings because one dominator may
    // be the candidate's partner). Since `dominates` is a strict partial order, any
    // dropped item is dominated by at least `dom_threshold` kept items and can
    // never enter the top `limit`.
    let metas: Vec<(Stats, (i32, i32))> = deduped
        .iter()
        .map(|it| {
            let (_, s, eff_reqs) = meta(it);
            (s, normalize_reqs(eff_reqs, base_str, base_dex))
        })
        .collect();
    let dominates = |a: usize, b: usize| {
        let (sa, ra) = metas[a];
        let (sb, rb) = metas[b];
        sa.dominates(sb) && ra.0 <= rb.0 && ra.1 <= rb.1 && (sa != sb || ra != rb)
    };

    deduped
        .into_iter()
        .enumerate()
        .filter(|&(i, _)| {
            (0..metas.len())
                .filter(|&j| j != i && dominates(j, i))
                .take(dom_threshold)
                .count()
                < dom_threshold
        })
        .map(|(_, it)| it)
        .collect()
}

fn prune_slot_items(
    items: Vec<ItemSpec>,
    limit: usize,
    is_ring: bool,
    base_str: i32,
    base_dex: i32,
) -> Vec<ItemSpec> {
    prune_candidates(items, limit, is_ring, base_str, base_dex, |it| {
        (&it.name, it.stats(), item_eff_reqs(it))
    })
}

fn empty_dominators(items: &[ItemSpec], base_str: i32, base_dex: i32) -> usize {
    items
        .iter()
        .filter(|it| dominates_empty(it.stats(), item_prune_reqs(it, base_str, base_dex)))
        .count()
}

fn build_hands(
    items: &[ItemSpec],
    valid_item: &impl Fn(&ItemSpec) -> bool,
    mode: SearchMode,
    c: &BuildConstraints,
) -> Vec<ItemPair> {
    let mut weapons_1h: Vec<ItemSpec> = items
        .iter()
        .filter(|i| i.slot == "weapon" && valid_item(i))
        .cloned()
        .collect();
    let mut shields: Vec<ItemSpec> = items
        .iter()
        .filter(|i| i.slot == "shield" && valid_item(i))
        .cloned()
        .collect();
    let mut weapons_2h: Vec<ItemSpec> = items
        .iter()
        .filter(|i| i.slot == "weapon2h" && valid_item(i))
        .cloned()
        .collect();

    if !shields.is_empty() && empty_dominators(&weapons_1h, c.base_str, c.base_dex) == 0 {
        weapons_1h.push(ItemSpec::empty("weapon"));
    }
    if !weapons_1h.is_empty() && empty_dominators(&shields, c.base_str, c.base_dex) == 0 {
        shields.push(ItemSpec::empty("shield"));
    }

    weapons_1h.sort_by_key(|it| Reverse(item_sort_key(mode, &it.stats())));
    shields.sort_by_key(|it| Reverse(item_sort_key(mode, &it.stats())));
    weapons_2h.sort_by_key(|it| Reverse(item_sort_key(mode, &it.stats())));

    let weapons_1h = prune_slot_items(weapons_1h, c.limit, false, c.base_str, c.base_dex);
    let shields = prune_slot_items(shields, c.limit, false, c.base_str, c.base_dex);
    let weapons_2h = prune_slot_items(weapons_2h, c.limit, false, c.base_str, c.base_dex);

    let mut hands = Vec::with_capacity(weapons_1h.len() * shields.len() + weapons_2h.len() + 1);
    for w in &weapons_1h {
        for s in &shields {
            hands.push(ItemPair::from_pair(w, s, "hands"));
        }
    }
    for w2h in weapons_2h {
        hands.push(ItemPair::single_2h(w2h));
    }

    let has_empty_dom = hands.iter().any(|h| {
        dominates_empty(
            h.combined.stats(),
            normalize_reqs(h.reqs, c.base_str, c.base_dex),
        )
    });
    if !has_empty_dom {
        hands.push(ItemPair::from_pair(
            &ItemSpec::empty("weapon"),
            &ItemSpec::empty("shield"),
            "hands",
        ));
    }

    hands.sort_by_key(|h| Reverse(item_sort_key(mode, &h.combined.stats())));
    prune_candidates(hands, c.limit, false, c.base_str, c.base_dex, |h| {
        (&h.combined.name, h.combined.stats(), h.reqs)
    })
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

    let hands = build_hands(items, &valid_item, mode, c);

    let mut groups: Vec<Vec<ItemSpec>> = Vec::with_capacity(SINGLE_SLOTS.len());
    for &slot in SINGLE_SLOTS {
        let mut slot_items: Vec<ItemSpec> = items
            .iter()
            .filter(|i| i.slot == slot && valid_item(i))
            .cloned()
            .collect();
        if empty_dominators(&slot_items, c.base_str, c.base_dex) == 0 {
            slot_items.push(ItemSpec::empty(slot));
        }
        slot_items.sort_by_key(|it| Reverse(item_sort_key(mode, &it.stats())));
        groups.push(prune_slot_items(slot_items, c.limit, false, c.base_str, c.base_dex));
    }

    let mut rngs: Vec<ItemSpec> = items
        .iter()
        .filter(|i| i.slot == "ring" && valid_item(i))
        .cloned()
        .collect();
    let ring_empty_dom = empty_dominators(&rngs, c.base_str, c.base_dex);
    for _ in 0..2usize.saturating_sub(ring_empty_dom) {
        rngs.push(ItemSpec::empty("ring"));
    }
    rngs.sort_by_key(|it| Reverse(item_sort_key(mode, &it.stats())));
    let rngs = prune_slot_items(rngs, c.limit, true, c.base_str, c.base_dex);

    let mut ring_pairs: Vec<ItemPair> = Vec::new();
    let mut seen_rp: HashSet<(Stats, i32, i32)> = HashSet::new();
    for i in 0..rngs.len() {
        for j in (i + 1)..rngs.len() {
            let r1 = &rngs[i];
            let r2 = &rngs[j];
            let rp = ItemPair::from_pair(r1, r2, "rings");
            let comb_stats = rp.combined.stats();
            if !seen_rp.insert((comb_stats, rp.reqs.0, rp.reqs.1)) {
                continue;
            }
            ring_pairs.push(rp);
        }
    }
    ring_pairs.sort_by_key(|rp| Reverse(item_sort_key(mode, &rp.combined.stats())));

    let n = 1 + groups.len() + 1;
    let mut suf = vec![Stats::default(); n + 1];
    suf[n - 1] = ring_pairs
        .iter()
        .fold(Stats::default(), |acc, rp| acc.max_each(rp.combined.stats()));
    for k in (0..groups.len()).rev() {
        let slot_max = groups[k]
            .iter()
            .fold(Stats::default(), |acc, it| acc.max_each(it.stats()));
        suf[k + 1] = suf[k + 2].add(slot_max);
    }
    let hands_max = hands
        .iter()
        .fold(Stats::default(), |acc, h| acc.max_each(h.combined.stats()));
    suf[0] = suf[1].add(hands_max);

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

    fn main_score_ub(
        mode: SearchMode,
        ub_ch: Stats,
        caps: (i32, i32, i32, i32),
    ) -> i32 {
        match mode {
            SearchMode::Power => ub_ch.blizz_power_skills(),
            SearchMode::Mf => ub_ch.mf,
            SearchMode::MaxRes => {
                ub_ch.fr.min(caps.0)
                    + ub_ch.lr.min(caps.1)
                    + ub_ch.cr.min(caps.2)
                    + ub_ch.pr.min(caps.3)
            }
        }
    }

    struct State<'a> {
        hands: &'a [ItemPair],
        groups: &'a [Vec<ItemSpec>],
        ring_pairs: &'a [ItemPair],
        suf: &'a [Stats],
        ch: Stats,
        pool: &'a [&'a CharmSpec],
        c: &'a BuildConstraints,
        mode: SearchMode,
        chosen_hand: usize,
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
        let caps_ub = res_caps(ub);
        if caps_ub.0 < st.c.min_fr
            || caps_ub.1 < st.c.min_lr
            || caps_ub.2 < st.c.min_cr
            || caps_ub.3 < st.c.min_pr
        {
            return;
        }
        if ub_ch.str_bonus < reqs.0 || ub_ch.dex_bonus < reqs.1 {
            return;
        }
        if let Some(cutoff) = st.top_results.nth_main_score()
            && main_score_ub(st.mode, ub_ch, caps_ub) < cutoff
        {
            return;
        }

        if idx == st.groups.len() + 1 {
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
                let caps_leaf = res_caps(leaf);
                if caps_leaf.0 < st.c.min_fr
                    || caps_leaf.1 < st.c.min_lr
                    || caps_leaf.2 < st.c.min_cr
                    || caps_leaf.3 < st.c.min_pr
                {
                    continue;
                }
                let (final_req_str, final_req_dex) = merge_reqs(reqs, rp.reqs);
                if leaf_ch.str_bonus < final_req_str || leaf_ch.dex_bonus < final_req_dex {
                    continue;
                }
                if let Some(cutoff) = st.top_results.nth_main_score()
                    && main_score_ub(st.mode, leaf_ch, caps_leaf) < cutoff
                {
                    continue;
                }
                st.evals += 1;

                let hand = &st.hands[st.chosen_hand];
                let mut items_ref: Vec<&ItemSpec> = Vec::with_capacity(2 + st.groups.len() + 2);
                items_ref.push(&hand.first);
                items_ref.push(&hand.second);
                items_ref.extend(
                    st.chosen_slots
                        .iter()
                        .enumerate()
                        .map(|(g, &i)| &st.groups[g][i]),
                );
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

        if idx == 0 {
            for (i, h) in st.hands.iter().enumerate() {
                st.chosen_hand = i;
                dfs(
                    st,
                    1,
                    acc.add(h.combined.stats()),
                    merge_reqs(reqs, h.reqs),
                );
            }
            return;
        }

        let g = idx - 1;
        for i in 0..st.groups[g].len() {
            let it = &st.groups[g][i];
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
        hands: &hands,
        groups: &groups,
        ring_pairs: &ring_pairs,
        suf: &suf,
        ch,
        pool: &pool,
        c,
        mode,
        chosen_hand: 0,
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
