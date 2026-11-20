use std::cmp::Reverse;
use std::collections::{HashMap, HashSet};

#[cfg(feature = "python")]
use pyo3::exceptions::PyValueError;
#[cfg(feature = "python")]
use pyo3::prelude::*;

use crate::charms::CharmSolver;
use crate::eval::{eval_build_summary, res_caps, EvalSummary};
use crate::types::{
    compute_effective_gear_stats_and_reqs, eff_req, BuildConstraints, BuildResult, CharClass,
    CharmSpec, HandWeapon, ItemSpec, OffenseProfile, SearchMode, SetBonusSig, Stats, WeaponClass,
    BASE_MAX_RES,
};

const SINGLE_SLOTS: [&str; 6] = ["helm", "armor", "amulet", "belt", "gloves", "boots"];
const LEAF_ITEM_COUNT: usize = 2 + SINGLE_SLOTS.len() + 2;

type ItemSetSig = Option<Vec<(i32, i32, SetBonusSig)>>;

fn single_set_sig(it: &ItemSpec) -> ItemSetSig {
    if it.set_group == 0 {
        None
    } else {
        Some(vec![(it.set_group, it.set_item_id, it.set_bonus_sig())])
    }
}

fn pair_set_sig(a: &ItemSpec, b: &ItemSpec) -> ItemSetSig {
    let mut out = Vec::new();
    if a.set_group != 0 {
        out.push((a.set_group, a.set_item_id, a.set_bonus_sig()));
    }
    if b.set_group != 0 {
        out.push((b.set_group, b.set_item_id, b.set_bonus_sig()));
    }
    if out.is_empty() {
        None
    } else {
        out.sort_by_key(|(g, id, _)| (*g, *id));
        Some(out)
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

fn item_locality_score(loc: &str) -> i32 {
    if loc.is_empty() {
        0
    } else if loc.starts_with("Stash Tab ") || loc.eq_ignore_ascii_case("Shared Stash") {
        2
    } else if loc.len() >= 4 && loc[..4].eq_ignore_ascii_case("mule") {
        1
    } else if loc.ends_with(" Equipped") || loc.eq_ignore_ascii_case("Equipped") {
        6
    } else if loc.ends_with(" Swap") || loc.eq_ignore_ascii_case("Swap") {
        5
    } else if loc.ends_with(" Inv") || loc.eq_ignore_ascii_case("Inv") {
        4
    } else if loc.ends_with(" Stash") || loc.eq_ignore_ascii_case("Stash") {
        3
    } else {
        1
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub(crate) struct BuildScore {
    pub(crate) primary: i32,
    pub(crate) secondary: i32,
    pub(crate) tertiary: i32,
    pub(crate) tiebreakers: [i32; 7],
    pub(crate) locality: i32,
}

type BuildSig = (i32, i32, i32, i32, Vec<String>);

fn build_sig(res: &BuildResult, offense: OffenseProfile) -> BuildSig {
    (
        res.skills,
        if offense.uses_fcr() { res.fcr_bp } else { 0 },
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

    fn nth_primary(&self) -> Option<i32> {
        if self.limit > 0 && self.entries.len() >= self.limit {
            self.entries.last().map(|e| e.0.primary)
        } else {
            None
        }
    }

    fn nth_top2(&self) -> Option<(i32, i32)> {
        if self.limit > 0 && self.entries.len() >= self.limit {
            self.entries.last().map(|e| (e.0.primary, e.0.secondary))
        } else {
            None
        }
    }

    fn nth_top3(&self) -> Option<(i32, i32, i32)> {
        if self.limit > 0 && self.entries.len() >= self.limit {
            self.entries
                .last()
                .map(|e| (e.0.primary, e.0.secondary, e.0.tertiary))
        } else {
            None
        }
    }

    fn push(&mut self, score: BuildScore, res: BuildResult, offense: OffenseProfile) {
        if !self.would_accept(score) {
            return;
        }

        let sig = build_sig(&res, offense);
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
    max_stats: Stats,
    set_sig: ItemSetSig,
    locality: i32,
}

impl ItemPair {
    fn from_pair(first: &ItemSpec, second: &ItemSpec, slot: &str) -> Self {
        let reqs = merge_reqs(item_eff_reqs(first), item_eff_reqs(second));
        let comb_stats = first.stats().add(second.stats());
        let locality = item_locality_score(&first.loc) + item_locality_score(&second.loc);
        let loc = match (first.loc.is_empty(), second.loc.is_empty()) {
            (true, true) => String::new(),
            (false, true) => first.loc.clone(),
            (true, false) => second.loc.clone(),
            (false, false) => format!("{} / {}", first.loc, second.loc),
        };
        let mut combined = ItemSpec::from_stats(
            format!("{} + {}", first.name, second.name),
            slot.to_string(),
            loc,
            comb_stats,
            reqs.0,
            reqs.1,
        );
        combined.wsm = first.wsm;
        combined.wclass = first.wclass.clone();
        combined.wep_phys_2x = first.wep_phys_2x;
        combined.wep_str_pct = first.wep_str_pct;
        combined.wep_dex_pct = first.wep_dex_pct;
        combined.can_zeal = first.can_zeal;
        Self {
            combined,
            first: first.clone(),
            second: second.clone(),
            reqs,
            max_stats: first.max_total_stats().add(second.max_total_stats()),
            set_sig: pair_set_sig(first, second),
            locality,
        }
    }

    fn single_2h(w2h: ItemSpec) -> Self {
        let reqs = item_eff_reqs(&w2h);
        let max_stats = w2h.max_total_stats();
        let set_sig = single_set_sig(&w2h);
        let locality = item_locality_score(&w2h.loc);
        let mut combined = w2h.clone();
        combined.slot = "hands".to_string();
        Self {
            combined,
            first: w2h,
            second: ItemSpec::empty("shield"),
            reqs,
            max_stats,
            set_sig,
            locality,
        }
    }
}

fn dominates_empty(stats: Stats, norm_reqs: (i32, i32)) -> bool {
    stats.dominates(Stats::default())
        && norm_reqs == (0, 0)
        && stats != Stats::default()
}

fn capped_res_sum(fr: i32, lr: i32, cr: i32, pr: i32, caps: (i32, i32, i32, i32)) -> i32 {
    fr.min(caps.0) + lr.min(caps.1) + cr.min(caps.2) + pr.min(caps.3)
}

fn res_base_sum(fr: i32, lr: i32, cr: i32, pr: i32) -> i32 {
    capped_res_sum(fr, lr, cr, pr, (BASE_MAX_RES, BASE_MAX_RES, BASE_MAX_RES, BASE_MAX_RES))
}

fn res_base_ub(s: Stats, caps: (i32, i32, i32, i32)) -> i32 {
    capped_res_sum(
        s.fr,
        s.lr,
        s.cr,
        s.pr,
        (
            caps.0.min(BASE_MAX_RES),
            caps.1.min(BASE_MAX_RES),
            caps.2.min(BASE_MAX_RES),
            caps.3.min(BASE_MAX_RES),
        ),
    )
}

pub(crate) fn score_eval_summary(
    mode: SearchMode,
    offense: OffenseProfile,
    sum: &EvalSummary,
    c: &BuildConstraints,
) -> BuildScore {
    let eff_primary = if offense.is_melee_dps()
        && (c.has_aura || sum.action_skill_bonus != 0 || sum.aura_skill_bonus != 0)
    {
        let bonus = if c.has_aura {
            sum.aura_skill_bonus
        } else {
            sum.action_skill_bonus.max(sum.aura_skill_bonus)
        };
        sum.skills + sum.blizz_skills + sum.primary_skill_bonus + bonus
    } else {
        sum.skills + sum.blizz_skills + sum.primary_skill_bonus
    };
    let res_sum = sum.fr + sum.lr + sum.cr + sum.pr;
    let res_base = res_base_sum(sum.fr, sum.lr, sum.cr, sum.pr);
    let off = if offense.uses_dps_tables(c) {
        OffenseProfile::dps_bucket(sum.dps)
    } else {
        offense.score(eff_primary, sum.ias_bp, sum.cb)
    };
    let eff_fcr_bp = if offense.uses_fcr() { sum.fcr_bp } else { 0 };
    match mode {
        SearchMode::Mf => BuildScore {
            primary: sum.mf,
            secondary: eff_primary,
            tertiary: eff_fcr_bp,
            tiebreakers: [sum.fhr_bp, sum.pr, sum.life_bo, sum.belt_slots, sum.defense, 0, 0],
            locality: 0,
        },
        SearchMode::Power => BuildScore {
            primary: eff_primary,
            secondary: sum.skills,
            tertiary: i32::from(sum.pr >= BASE_MAX_RES),
            tiebreakers: [sum.pr, sum.life_bo, sum.mana_bo, sum.belt_slots, sum.defense, 0, 0],
            locality: 0,
        },
        SearchMode::MaxRes => BuildScore {
            primary: res_sum,
            secondary: eff_primary,
            tertiary: eff_fcr_bp,
            tiebreakers: [
                sum.fhr_bp,
                sum.life_bo,
                sum.fr_raw + sum.lr_raw + sum.cr_raw + sum.pr_raw,
                sum.belt_slots,
                sum.defense,
                0,
                0,
            ],
            locality: 0,
        },
        SearchMode::Leveling => BuildScore {
            primary: off,
            secondary: res_base,
            tertiary: i32::from(sum.cbf),
            tiebreakers: if offense == OffenseProfile::Smite {
                [
                    sum.life_bo,
                    sum.pdr_pct,
                    sum.frw,
                    sum.fhr_bp,
                    res_sum,
                    sum.belt_slots,
                    sum.defense,
                ]
            } else {
                [
                    sum.life_bo,
                    sum.frw,
                    res_sum,
                    sum.fhr_bp,
                    eff_fcr_bp,
                    sum.belt_slots,
                    sum.defense,
                ]
            },
            locality: 0,
        },
        SearchMode::LevelingRes => BuildScore {
            primary: res_base,
            secondary: off,
            tertiary: i32::from(sum.cbf),
            tiebreakers: [
                sum.life_bo,
                sum.frw,
                sum.fhr_bp,
                eff_fcr_bp,
                res_sum,
                sum.belt_slots,
                sum.defense,
            ],
            locality: 0,
        },
    }
}

fn item_sort_key(
    mode: SearchMode,
    offense: OffenseProfile,
    s: &Stats,
    locality: i32,
) -> (i32, i32, i32, i32, i32, i32, i32) {
    let eff_fcr = if offense.uses_fcr() { s.fcr } else { 0 };
    match mode {
        SearchMode::Mf => (
            s.mf,
            s.primary_power_skills(),
            eff_fcr,
            s.fr + s.lr,
            s.belt_slots,
            s.defense,
            locality,
        ),
        SearchMode::Power => (
            s.primary_power_skills(),
            s.total_skills(),
            eff_fcr,
            s.fhr,
            s.belt_slots,
            s.defense,
            locality,
        ),
        SearchMode::MaxRes => (
            s.max_res_sum(),
            s.res_sum(),
            s.primary_power_skills(),
            eff_fcr,
            s.belt_slots,
            s.defense,
            locality,
        ),
        SearchMode::Leveling => (
            offense.score_stats(*s),
            s.res_sum(),
            s.cbf,
            if offense == OffenseProfile::Smite {
                s.pdr_pct
            } else {
                s.frw
            },
            s.belt_slots,
            s.defense,
            locality,
        ),
        SearchMode::LevelingRes => (
            s.res_sum(),
            offense.score_stats(*s),
            s.cbf,
            s.fhr,
            s.belt_slots,
            s.defense,
            locality,
        ),
    }
}

fn prune_candidates<T, S: Eq + std::hash::Hash + Clone>(
    items: Vec<T>,
    limit: usize,
    is_ring: bool,
    base_str: i32,
    base_dex: i32,
    meta: impl Fn(&T) -> (&str, Stats, (i32, i32), S),
) -> Vec<T> {
    if limit == 0 {
        return items;
    }
    let dom_threshold = if is_ring { limit + 1 } else { limit };
    let same_name_cap = if is_ring { 2 } else { 1 };

    let mut stat_counts: HashMap<(Stats, i32, i32, S), HashSet<String>> = HashMap::new();
    let mut name_stat_counts: HashMap<(String, Stats, i32, i32, S), usize> = HashMap::new();
    let mut deduped = Vec::with_capacity(items.len());
    for it in items {
        let (name, s, eff_reqs, set_sig) = meta(&it);
        let (rs, rd) = normalize_reqs(eff_reqs, base_str, base_dex);
        let name_str = name.to_string();
        let ns_entry = name_stat_counts
            .entry((name_str.clone(), s, rs, rd, set_sig.clone()))
            .or_insert(0);
        if *ns_entry >= same_name_cap {
            continue;
        }
        let s_names = stat_counts.entry((s, rs, rd, set_sig)).or_default();
        if !s_names.contains(&name_str) && s_names.len() >= dom_threshold {
            continue;
        }
        *ns_entry += 1;
        s_names.insert(name_str);
        deduped.push(it);
    }

    // Keep every candidate strictly dominated by fewer than `same_name_cap` same-named
    // items AND fewer than `dom_threshold` distinct dominator names (`limit` for single
    // slots, `limit + 1` for rings because one dominator may be the candidate's partner).
    // Counting distinct dominator names prevents multiple rolls of the same item name
    // (which collapse to one `BuildSig` in `TopResults`) from crowding out distinct items.
    // Only compare within equal `set_sig` so items participating in set bonuses are preserved.
    let metas: Vec<(String, Stats, (i32, i32), S)> = deduped
        .iter()
        .map(|it| {
            let (name, s, eff_reqs, set_sig) = meta(it);
            (
                name.to_string(),
                s,
                normalize_reqs(eff_reqs, base_str, base_dex),
                set_sig,
            )
        })
        .collect();
    let dominates = |a: usize, b: usize| {
        let (_, sa, ra, ref sig_a) = metas[a];
        let (_, sb, rb, ref sig_b) = metas[b];
        sig_a == sig_b
            && sa.dominates(sb)
            && ra.0 <= rb.0
            && ra.1 <= rb.1
            && (sa != sb || ra != rb)
    };

    deduped
        .into_iter()
        .enumerate()
        .filter(|&(i, _)| {
            let mut same_name_doms = 0usize;
            let mut dom_names: HashSet<&str> = HashSet::new();
            for j in 0..metas.len() {
                if j != i && dominates(j, i) {
                    if metas[j].0 == metas[i].0 {
                        same_name_doms += 1;
                        if same_name_doms >= same_name_cap {
                            return false;
                        }
                    }
                    dom_names.insert(metas[j].0.as_str());
                    if dom_names.len() >= dom_threshold {
                        return false;
                    }
                }
            }
            true
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
    offense: OffenseProfile,
    min_fcr: i32,
) -> Vec<ItemSpec> {
    prune_candidates(items, limit, is_ring, base_str, base_dex, |it| {
        (
            &it.name,
            it.stats().for_offense(offense, min_fcr),
            item_eff_reqs(it),
            single_set_sig(it),
        )
    })
}

fn empty_dominators(
    items: &[ItemSpec],
    base_str: i32,
    base_dex: i32,
    offense: OffenseProfile,
    min_fcr: i32,
) -> usize {
    items
        .iter()
        .filter(|it| {
            it.set_group == 0
                && it.weapon_class() == WeaponClass::OneHandSwing
                && it.wsm == 0
                && dominates_empty(
                    it.stats().for_offense(offense, min_fcr),
                    item_prune_reqs(it, base_str, base_dex),
                )
        })
        .count()
}

fn build_hands(
    items: &[ItemSpec],
    valid_item: &impl Fn(&ItemSpec) -> bool,
    mode: SearchMode,
    offense: OffenseProfile,
    c: &BuildConstraints,
) -> Vec<ItemPair> {
    let require_shield = offense.requires_shield();
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
    let mut weapons_2h: Vec<ItemSpec> = if require_shield {
        Vec::new()
    } else {
        items
            .iter()
            .filter(|i| i.slot == "weapon2h" && valid_item(i))
            .cloned()
            .collect()
    };

    if c.fixed_gear {
        if weapons_1h.is_empty() && !shields.is_empty() {
            weapons_1h.push(ItemSpec::empty("weapon"));
        }
        if !require_shield && shields.is_empty() && !weapons_1h.is_empty() {
            shields.push(ItemSpec::empty("shield"));
        }
    } else {
        if !shields.is_empty()
            && empty_dominators(&weapons_1h, c.base_str, c.base_dex, offense, c.min_fcr) == 0
        {
            weapons_1h.push(ItemSpec::empty("weapon"));
        }
        if !require_shield
            && !weapons_1h.is_empty()
            && empty_dominators(&shields, c.base_str, c.base_dex, offense, c.min_fcr) == 0
        {
            shields.push(ItemSpec::empty("shield"));
        }
    }

    weapons_1h.sort_by_key(|it| {
        Reverse(item_sort_key(
            mode,
            offense,
            &it.max_total_stats(),
            item_locality_score(&it.loc),
        ))
    });
    shields.sort_by_key(|it| {
        Reverse(item_sort_key(
            mode,
            offense,
            &it.max_total_stats(),
            item_locality_score(&it.loc),
        ))
    });
    weapons_2h.sort_by_key(|it| {
        Reverse(item_sort_key(
            mode,
            offense,
            &it.max_total_stats(),
            item_locality_score(&it.loc),
        ))
    });

    let empty_hand = ItemSpec::empty("weapon").hand_weapon();
    let empty_anim = offense.weapon_anim_key(mode, empty_hand);
    let fold_wep_phys =
        offense.is_melee_dps() && matches!(mode, SearchMode::Leveling | SearchMode::LevelingRes);
    let wep_prune_stats = |it: &ItemSpec| {
        let mut s = it.stats().for_offense(offense, c.min_fcr);
        if fold_wep_phys {
            s.flat_phys_2x += it.wep_phys_2x;
        }
        s
    };
    let weapons_1h = prune_candidates(
        weapons_1h,
        c.limit,
        false,
        c.base_str,
        c.base_dex,
        |it| {
            (
                &it.name,
                wep_prune_stats(it),
                item_eff_reqs(it),
                (
                    offense.weapon_anim_key(mode, it.hand_weapon()),
                    single_set_sig(it),
                ),
            )
        },
    );
    let shields =
        prune_slot_items(shields, c.limit, false, c.base_str, c.base_dex, offense, c.min_fcr);
    let weapons_2h = prune_candidates(
        weapons_2h,
        c.limit,
        false,
        c.base_str,
        c.base_dex,
        |it| {
            (
                &it.name,
                wep_prune_stats(it),
                item_eff_reqs(it),
                (
                    offense.weapon_anim_key(mode, it.hand_weapon()),
                    single_set_sig(it),
                ),
            )
        },
    );

    let mut hands = Vec::with_capacity(weapons_1h.len() * shields.len() + weapons_2h.len() + 1);
    for w in &weapons_1h {
        for s in &shields {
            hands.push(ItemPair::from_pair(w, s, "hands"));
        }
    }
    for w2h in weapons_2h {
        hands.push(ItemPair::single_2h(w2h));
    }

    if c.fixed_gear {
        if !require_shield && hands.is_empty() {
            hands.push(ItemPair::from_pair(
                &ItemSpec::empty("weapon"),
                &ItemSpec::empty("shield"),
                "hands",
            ));
        }
    } else {
        let has_empty_dom = hands.iter().any(|h| {
            h.set_sig.is_none()
                && offense.weapon_anim_key(mode, h.first.hand_weapon()) == empty_anim
                && dominates_empty(
                    wep_prune_stats(&h.combined),
                    normalize_reqs(h.reqs, c.base_str, c.base_dex),
                )
        });
        if !require_shield && !has_empty_dom {
            hands.push(ItemPair::from_pair(
                &ItemSpec::empty("weapon"),
                &ItemSpec::empty("shield"),
                "hands",
            ));
        }
    }

    hands.sort_by_key(|h| Reverse(item_sort_key(mode, offense, &h.max_stats, h.locality)));
    prune_candidates(hands, c.limit, false, c.base_str, c.base_dex, |h| {
        (
            &h.combined.name,
            wep_prune_stats(&h.combined),
            h.reqs,
            (
                offense.weapon_anim_key(mode, h.first.hand_weapon()),
                h.set_sig.clone(),
            ),
        )
    })
}

pub(crate) fn normalize_set_items(
    items: &[ItemSpec],
    allow_mf: bool,
    require_shield: bool,
    fixed_gear: bool,
) -> Vec<ItemSpec> {
    let mut group_seen: HashMap<i32, HashSet<i32>> = HashMap::new();
    for (idx, it) in items.iter().enumerate() {
        if (!allow_mf && it.mf != 0)
            || (require_shield && it.slot == "weapon2h")
            || it.set_group == 0
        {
            continue;
        }
        let eid = if it.set_item_id != 0 {
            it.set_item_id
        } else {
            -(idx as i32 + 1)
        };
        group_seen.entry(it.set_group).or_default().insert(eid);
    }

    let mut active_groups: HashSet<i32> = HashSet::new();
    for it in items {
        if (!allow_mf && it.mf != 0)
            || (require_shield && it.slot == "weapon2h")
            || it.set_group == 0
        {
            continue;
        }
        let max_pcs = group_seen.get(&it.set_group).map_or(0, |s| s.len() as i32);
        if max_pcs >= 2
            && it
                .set_bonuses
                .iter()
                .any(|(req, b)| *req >= 2 && *req <= max_pcs && b.stats() != Stats::default())
        {
            active_groups.insert(it.set_group);
        }
    }

    let mut out = Vec::with_capacity(items.len());
    for (idx, it) in items.iter().enumerate() {
        let mut cloned = it.clone();
        let was_set = cloned.set_group != 0;
        if was_set {
            if !active_groups.contains(&cloned.set_group) {
                cloned.set_group = 0;
                cloned.set_item_id = 0;
                cloned.set_bonuses.clear();
            } else {
                if cloned.set_item_id == 0 {
                    cloned.set_item_id = -(idx as i32 + 1);
                }
                let max_pcs = group_seen
                    .get(&cloned.set_group)
                    .map_or(0, |s| s.len() as i32);
                cloned
                    .set_bonuses
                    .retain(|(req, b)| *req >= 2 && *req <= max_pcs && b.stats() != Stats::default());
            }
        }
        if !fixed_gear && was_set && cloned.set_group == 0 && cloned.stats() == Stats::default() {
            continue;
        }
        out.push(cloned);
    }
    out
}

pub fn optimize_builds_core(
    items: &[ItemSpec],
    charms: &[CharmSpec],
    c: &BuildConstraints,
) -> Result<Vec<BuildResult>, String> {
    let class = CharClass::from_id(c.char_class)?;
    let offense = OffenseProfile::parse(&c.offense, class)?;
    let mode = match c.mode.to_ascii_lowercase().as_str() {
        "power" => SearchMode::Power,
        "mf" => SearchMode::Mf,
        "max-res" => SearchMode::MaxRes,
        "leveling" => SearchMode::Leveling,
        "leveling-res" => SearchMode::LevelingRes,
        other => {
            return Err(format!(
                "invalid mode '{other}'; expected 'power', 'mf', 'max-res', 'leveling', or 'leveling-res'"
            ))
        }
    };

    let valid_item = |i: &ItemSpec| c.allow_mf || i.mf == 0;
    let norm_items = normalize_set_items(items, c.allow_mf, offense.requires_shield(), c.fixed_gear);

    let hands = build_hands(&norm_items, &valid_item, mode, offense, c);

    let mut groups: Vec<Vec<ItemSpec>> = Vec::with_capacity(SINGLE_SLOTS.len());
    for slot in SINGLE_SLOTS {
        let mut slot_items: Vec<ItemSpec> = norm_items
            .iter()
            .filter(|i| i.slot == slot && valid_item(i))
            .cloned()
            .collect();
        let need_empty = if c.fixed_gear {
            slot_items.is_empty()
        } else {
            empty_dominators(&slot_items, c.base_str, c.base_dex, offense, c.min_fcr) == 0
        };
        if need_empty {
            slot_items.push(ItemSpec::empty(slot));
        }
        slot_items.sort_by_key(|it| {
            Reverse(item_sort_key(
                mode,
                offense,
                &it.max_total_stats(),
                item_locality_score(&it.loc),
            ))
        });
        groups.push(prune_slot_items(
            slot_items, c.limit, false, c.base_str, c.base_dex, offense, c.min_fcr,
        ));
    }

    let mut rngs: Vec<ItemSpec> = norm_items
        .iter()
        .filter(|i| i.slot == "ring" && valid_item(i))
        .cloned()
        .collect();
    let empty_rings_needed = if c.fixed_gear {
        2usize.saturating_sub(rngs.len())
    } else {
        2usize.saturating_sub(empty_dominators(
            &rngs, c.base_str, c.base_dex, offense, c.min_fcr,
        ))
    };
    for _ in 0..empty_rings_needed {
        rngs.push(ItemSpec::empty("ring"));
    }
    rngs.sort_by_key(|it| {
        Reverse(item_sort_key(
            mode,
            offense,
            &it.max_total_stats(),
            item_locality_score(&it.loc),
        ))
    });
    let rngs = prune_slot_items(rngs, c.limit, true, c.base_str, c.base_dex, offense, c.min_fcr);

    let mut ring_pairs: Vec<ItemPair> = Vec::new();
    let mut seen_rp: HashSet<(Stats, i32, i32, ItemSetSig)> = HashSet::new();
    for i in 0..rngs.len() {
        for j in (i + 1)..rngs.len() {
            let r1 = &rngs[i];
            let r2 = &rngs[j];
            let rp = ItemPair::from_pair(r1, r2, "rings");
            let comb_stats = rp.combined.stats().for_offense(offense, c.min_fcr);
            if !seen_rp.insert((comb_stats, rp.reqs.0, rp.reqs.1, rp.set_sig.clone())) {
                continue;
            }
            ring_pairs.push(rp);
        }
    }
    ring_pairs.sort_by_key(|rp| Reverse(item_sort_key(mode, offense, &rp.max_stats, rp.locality)));

    let n = 1 + groups.len() + 1;
    let mut suf = vec![Stats::default(); n + 1];
    suf[n - 1] = ring_pairs
        .iter()
        .fold(Stats::default(), |acc, rp| acc.max_each(rp.max_stats));
    for k in (0..groups.len()).rev() {
        let slot_max = groups[k]
            .iter()
            .fold(Stats::default(), |acc, it| acc.max_each(it.max_total_stats()));
        suf[k + 1] = suf[k + 2].add(slot_max);
    }
    let hands_max = hands
        .iter()
        .fold(Stats::default(), |acc, h| acc.max_each(h.max_stats));
    suf[0] = suf[1].add(hands_max);

    const RELAXED_MIN_CR: i32 = -1_000_000;

    struct SearchPool<'a> {
        hands: &'a [ItemPair],
        groups: &'a [Vec<ItemSpec>],
        ring_pairs: &'a [ItemPair],
        suf: &'a [Stats],
        raw_pool: &'a [&'a CharmSpec],
    }

    fn run_search_pass(
        pool: &SearchPool<'_>,
        c: &BuildConstraints,
        mode: SearchMode,
        offense: OffenseProfile,
    ) -> (Vec<BuildResult>, bool) {
        let charm_solver = CharmSolver::new(pool.raw_pool, c, mode);
        let has_cold_sunder = charm_solver.has_cold_sunder();
        let ch = charm_solver.charm_ub_stats();

        fn can_prune_by_score(
            mode: SearchMode,
            offense: OffenseProfile,
            ub_ch: Stats,
            hand: Option<HandWeapon>,
            max_hand_ub_dps: i32,
            caps: (i32, i32, i32, i32),
            c: &BuildConstraints,
            top: &TopResults,
        ) -> bool {
            let eff_primary_ub = ub_ch.primary_power_skills_for(offense, c.has_aura);
            let off_ub = if offense.uses_dps_tables(c) {
                match hand {
                    Some(hw) => OffenseProfile::dps_bucket(offense.compute_dps(hw, ub_ch, c).0),
                    None => max_hand_ub_dps,
                }
            } else {
                let ub_ias = match hand {
                    Some(hw) => offense.attack_speed(hw.wclass, hw.wsm, ub_ch.ias).0,
                    None => ub_ch.ias,
                };
                offense.score(eff_primary_ub, ub_ias, ub_ch.cb)
            };
            let res_base = res_base_ub(ub_ch, caps);
            let cbf_ub = i32::from(ub_ch.cbf > 0);
            match mode {
                SearchMode::Power => top
                    .nth_primary()
                    .is_some_and(|cutoff| eff_primary_ub < cutoff),
                SearchMode::Mf => top.nth_primary().is_some_and(|cutoff| ub_ch.mf < cutoff),
                SearchMode::MaxRes => top.nth_top2().is_some_and(|cutoff| {
                    (
                        capped_res_sum(ub_ch.fr, ub_ch.lr, ub_ch.cr, ub_ch.pr, caps),
                        eff_primary_ub,
                    ) < cutoff
                }),
                SearchMode::Leveling => top
                    .nth_top3()
                    .is_some_and(|cutoff| (off_ub, res_base, cbf_ub) < cutoff),
                SearchMode::LevelingRes => top
                    .nth_top3()
                    .is_some_and(|cutoff| (res_base, off_ub, cbf_ub) < cutoff),
            }
        }

        struct State<'a> {
            hands: &'a [ItemPair],
            hand_order: Vec<usize>,
            max_hand_ub_dps: i32,
            groups: &'a [Vec<ItemSpec>],
            ring_pairs: &'a [ItemPair],
            suf: &'a [Stats],
            ch: Stats,
            charm_solver: CharmSolver<'a>,
            c: &'a BuildConstraints,
            mode: SearchMode,
            offense: OffenseProfile,
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
            let caps_ub = res_caps(ub, st.c);
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
            let hand_opt = (idx > 0).then(|| st.hands[st.chosen_hand].first.hand_weapon());
            if can_prune_by_score(
                st.mode,
                st.offense,
                ub_ch,
                hand_opt,
                st.max_hand_ub_dps,
                caps_ub,
                st.c,
                &st.top_results,
            ) {
                return;
            }

            if idx == st.groups.len() + 1 {
                let hand = &st.hands[st.chosen_hand];
                let hw = hand.first.hand_weapon();
                for rp in st.ring_pairs {
                    let leaf_ub = acc.add(rp.max_stats);
                    if leaf_ub.fcr < st.c.min_fcr {
                        continue;
                    }
                    let leaf_ub_ch = leaf_ub.add(st.ch);
                    if leaf_ub_ch.fhr < st.c.min_fhr
                        || leaf_ub_ch.fr < st.c.min_fr
                        || leaf_ub_ch.lr < st.c.min_lr
                        || leaf_ub_ch.cr < st.c.min_cr
                        || leaf_ub_ch.pr < st.c.min_pr
                    {
                        continue;
                    }
                    let caps_ub_leaf = res_caps(leaf_ub, st.c);
                    if caps_ub_leaf.0 < st.c.min_fr
                        || caps_ub_leaf.1 < st.c.min_lr
                        || caps_ub_leaf.2 < st.c.min_cr
                        || caps_ub_leaf.3 < st.c.min_pr
                    {
                        continue;
                    }
                    let ub_reqs = merge_reqs(reqs, rp.reqs);
                    if leaf_ub_ch.str_bonus < ub_reqs.0 || leaf_ub_ch.dex_bonus < ub_reqs.1 {
                        continue;
                    }
                    if can_prune_by_score(
                        st.mode,
                        st.offense,
                        leaf_ub_ch,
                        Some(hw),
                        st.max_hand_ub_dps,
                        caps_ub_leaf,
                        st.c,
                        &st.top_results,
                    ) {
                        continue;
                    }

                    let items_ref: [&ItemSpec; LEAF_ITEM_COUNT] =
                        std::array::from_fn(|i| match i {
                            0 => &hand.first,
                            1 => &hand.second,
                            k if k < 2 + SINGLE_SLOTS.len() => {
                                let slot_idx = k - 2;
                                &st.groups[slot_idx][st.chosen_slots[slot_idx]]
                            }
                            k if k == 2 + SINGLE_SLOTS.len() => &rp.first,
                            _ => &rp.second,
                        });
                    let (gear, all_sk_non_wep, (final_req_str, final_req_dex)) =
                        compute_effective_gear_stats_and_reqs(&items_ref);
                    let leaf = Stats {
                        fr: gear.fr + st.c.base_hell_res,
                        lr: gear.lr + st.c.base_hell_res,
                        cr: gear.cr + st.c.base_hell_res,
                        pr: gear.pr + st.c.base_hell_res,
                        str_bonus: gear.str_bonus + st.c.base_str,
                        dex_bonus: gear.dex_bonus + st.c.base_dex,
                        ..gear
                    };
                    if items_ref.iter().any(|it| it.set_group != 0) {
                        if !st.c.allow_mf && leaf.mf > 0 {
                            continue;
                        }
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
                        let caps_leaf = res_caps(leaf, st.c);
                        if caps_leaf.0 < st.c.min_fr
                            || caps_leaf.1 < st.c.min_lr
                            || caps_leaf.2 < st.c.min_cr
                            || caps_leaf.3 < st.c.min_pr
                        {
                            continue;
                        }
                        if leaf_ch.str_bonus < final_req_str || leaf_ch.dex_bonus < final_req_dex {
                            continue;
                        }
                        if can_prune_by_score(
                            st.mode,
                            st.offense,
                            leaf_ch,
                            Some(hw),
                            st.max_hand_ub_dps,
                            caps_leaf,
                            st.c,
                            &st.top_results,
                        ) {
                            continue;
                        }
                    }
                    st.evals += 1;

                    let min_main_needed = match st.mode {
                        SearchMode::LevelingRes => st.top_results.nth_primary().map_or(0, |cut| {
                            let cur = res_base_sum(leaf.fr, leaf.lr, leaf.cr, leaf.pr);
                            (cut - cur).max(0)
                        }),
                        SearchMode::MaxRes => st.top_results.nth_primary().map_or(0, |cut| {
                            let caps_l = res_caps(leaf, st.c);
                            let cur = capped_res_sum(leaf.fr, leaf.lr, leaf.cr, leaf.pr, caps_l);
                            (cut - cur).max(0)
                        }),
                        _ => 0,
                    };
                    let Some(charms_sel) = st.charm_solver.solve_with_min_main(
                        &items_ref,
                        leaf,
                        (final_req_str, final_req_dex),
                        min_main_needed,
                    ) else {
                        continue;
                    };
                    let sum = eval_build_summary(gear, all_sk_non_wep, hw, &charms_sel, st.c);
                    if (!st.c.allow_mf && sum.mf > 0)
                        || sum.fcr < st.c.min_fcr
                        || sum.fhr < st.c.min_fhr
                    {
                        continue;
                    }
                    if sum.fr < st.c.min_fr
                        || sum.lr < st.c.min_lr
                        || sum.cr < st.c.min_cr
                        || sum.pr < st.c.min_pr
                    {
                        continue;
                    }
                    let mut score = score_eval_summary(st.mode, st.offense, &sum, st.c);
                    score.locality = items_ref.iter().map(|it| item_locality_score(&it.loc)).sum();
                    if !st.top_results.would_accept(score) {
                        continue;
                    }
                    let res = sum.into_result(&items_ref, &charms_sel, 0);
                    st.top_results.push(score, res, st.offense);
                }
                return;
            }

            if idx == 0 {
                for pos in 0..st.hand_order.len() {
                    let i = st.hand_order[pos];
                    let h = &st.hands[i];
                    st.chosen_hand = i;
                    dfs(
                        st,
                        1,
                        acc.add(h.max_stats),
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
                    acc.add(it.max_total_stats()),
                    merge_reqs(reqs, item_eff_reqs(it)),
                );
                st.chosen_slots.pop();
            }
        }

        let init_acc = Stats {
            fr: c.base_hell_res,
            lr: c.base_hell_res,
            cr: c.base_hell_res,
            pr: c.base_hell_res,
            str_bonus: c.base_str,
            dex_bonus: c.base_dex,
            ..Default::default()
        };

        let mut hand_order: Vec<usize> = (0..pool.hands.len()).collect();
        let max_hand_ub_dps = if offense.uses_dps_tables(c) {
            let tail_ub = init_acc.add(pool.suf[1]).add(ch);
            let hand_ubs: Vec<i32> = pool
                .hands
                .iter()
                .map(|h| {
                    let ub_h = tail_ub.add(h.max_stats);
                    OffenseProfile::dps_bucket(
                        offense.compute_dps(h.first.hand_weapon(), ub_h, c).0,
                    )
                })
                .collect();
            if mode == SearchMode::Leveling {
                hand_order.sort_by_key(|&i| Reverse(hand_ubs[i]));
            }
            hand_ubs.into_iter().max().unwrap_or(0)
        } else {
            0
        };

        let mut state = State {
            hands: pool.hands,
            hand_order,
            max_hand_ub_dps,
            groups: pool.groups,
            ring_pairs: pool.ring_pairs,
            suf: pool.suf,
            ch,
            charm_solver,
            c,
            mode,
            offense,
            chosen_hand: 0,
            chosen_slots: Vec::with_capacity(pool.groups.len()),
            evals: 0,
            top_results: TopResults::new(c.limit),
        };

        dfs(&mut state, 0, init_acc, (0, 0));

        let total_evals = state.evals;
        (state.top_results.finish(total_evals), has_cold_sunder)
    }

    let raw_pool: Vec<&CharmSpec> = charms
        .iter()
        .filter(|ch| {
            (c.allow_mf || ch.mf == 0)
                && (!class.excludes_light_skill_charms() || ch.light_skills == 0)
        })
        .collect();
    let pool = SearchPool {
        hands: &hands,
        groups: &groups,
        ring_pairs: &ring_pairs,
        suf: &suf,
        raw_pool: &raw_pool,
    };
    let (results, has_cold_sunder) = run_search_pass(&pool, c, mode, offense);
    if results.is_empty() && has_cold_sunder && c.min_cr > RELAXED_MIN_CR {
        let mut relaxed = c.clone();
        relaxed.min_cr = RELAXED_MIN_CR;
        return Ok(run_search_pass(&pool, &relaxed, mode, offense).0);
    }
    Ok(results)
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
