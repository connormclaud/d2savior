use std::cmp::Reverse;
use std::collections::{HashMap, HashSet};

#[cfg(feature = "python")]
use pyo3::exceptions::PyValueError;
#[cfg(feature = "python")]
use pyo3::prelude::*;

use crate::charms::CharmSolver;
use crate::eval::{base_res_caps, eval_build_summary, res_caps, EvalSummary};
use crate::types::{
    compute_effective_gear_stats, compute_effective_gear_stats_and_reqs, eff_req,
    equipped_hand_weapon, BuildConstraints, BuildResult, CharClass, CharmSpec, HandWeapon,
    ItemSpec, OffenseProfile, SearchMode, SetBonusSig, Stats, TargetType, WeaponClass,
    HARD_MAX_PDR_PCT,
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

pub type ScoreTuple = (i32, i32, i32, i32, i32, i32, i32, i32, i32, i32);

impl BuildScore {
    pub(crate) fn without_locality_tuple(self) -> ScoreTuple {
        (
            self.primary,
            self.secondary,
            self.tertiary,
            self.tiebreakers[0],
            self.tiebreakers[1],
            self.tiebreakers[2],
            self.tiebreakers[3],
            self.tiebreakers[4],
            self.tiebreakers[5],
            self.tiebreakers[6],
        )
    }
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

fn combine_cut<T: Ord>(a: Option<T>, b: Option<T>) -> Option<T> {
    match (a, b) {
        (Some(x), Some(y)) => Some(x.max(y)),
        (x, y) => x.or(y),
    }
}

/// Deduplicating result collector bounded to `limit` distinct signatures when `limit > 0`.
struct TopResults {
    limit: usize,
    seq: usize,
    score_floor: Option<BuildScore>,
    entries: Vec<(BuildScore, usize, BuildSig, BuildResult)>,
}

impl TopResults {
    fn with_floor(limit: usize, score_floor: Option<BuildScore>) -> Self {
        Self {
            limit,
            seq: 0,
            score_floor,
            entries: Vec::new(),
        }
    }

    fn would_accept(&self, score: BuildScore) -> bool {
        if self.score_floor.is_some_and(|floor| score < floor) {
            return false;
        }
        self.limit == 0
            || self.entries.len() < self.limit
            || self.entries.last().is_some_and(|worst| score > worst.0)
    }

    fn nth_primary(&self) -> Option<i32> {
        let entry_cut = if self.limit > 0 && self.entries.len() >= self.limit {
            self.entries.last().map(|e| e.0.primary)
        } else {
            None
        };
        combine_cut(entry_cut, self.score_floor.map(|f| f.primary))
    }

    fn nth_top2(&self) -> Option<(i32, i32)> {
        let entry_cut = if self.limit > 0 && self.entries.len() >= self.limit {
            self.entries.last().map(|e| (e.0.primary, e.0.secondary))
        } else {
            None
        };
        combine_cut(entry_cut, self.score_floor.map(|f| (f.primary, f.secondary)))
    }

    fn nth_top3(&self) -> Option<(i32, i32, i32)> {
        let entry_cut = if self.limit > 0 && self.entries.len() >= self.limit {
            self.entries
                .last()
                .map(|e| (e.0.primary, e.0.secondary, e.0.tertiary))
        } else {
            None
        };
        combine_cut(
            entry_cut,
            self.score_floor.map(|f| (f.primary, f.secondary, f.tertiary)),
        )
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
        combined.splash_fire = first.splash_fire;
        combined.splash_fire_2x = first.splash_fire_2x;
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

fn res_base_sum(fr: i32, lr: i32, cr: i32, pr: i32, c: &BuildConstraints) -> i32 {
    capped_res_sum(fr, lr, cr, pr, base_res_caps(c))
}

fn res_base_ub(s: Stats, caps: (i32, i32, i32, i32), c: &BuildConstraints) -> i32 {
    let bc = base_res_caps(c);
    capped_res_sum(
        s.fr,
        s.lr,
        s.cr,
        s.pr,
        (
            caps.0.min(bc.0),
            caps.1.min(bc.1),
            caps.2.min(bc.2),
            caps.3.min(bc.3),
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
    let res_base = res_base_sum(sum.fr, sum.lr, sum.cr, sum.pr, c);
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
            tiebreakers: [sum.fhr_bp, sum.pr, sum.life_bo, sum.belt_slots, sum.gear_defense, 0, 0],
            locality: 0,
        },
        SearchMode::Power => BuildScore {
            primary: if offense.uses_caster_dps(c) {
                sum.dps.floor() as i32
            } else {
                eff_primary
            },
            secondary: sum.skills,
            tertiary: i32::from(sum.pr >= base_res_caps(c).3),
            tiebreakers: [sum.pr, sum.life_bo, sum.mana_bo, sum.belt_slots, sum.gear_defense, 0, 0],
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
                sum.gear_defense,
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
                    sum.gear_defense,
                ]
            } else {
                [
                    sum.life_bo,
                    sum.frw,
                    res_sum,
                    sum.fhr_bp,
                    eff_fcr_bp,
                    sum.belt_slots,
                    sum.gear_defense,
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
                sum.gear_defense,
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
    raw_def: i32,
) -> (i32, i32, i32, i32, i32, i32, i32) {
    let eff_fcr = if offense.uses_fcr() { s.fcr } else { 0 };
    match mode {
        SearchMode::Mf => (
            s.mf,
            s.primary_power_skills(),
            eff_fcr,
            s.fr + s.lr,
            s.belt_slots,
            raw_def,
            locality,
        ),
        SearchMode::Power => (
            s.primary_power_skills() * 10 + s.cold_dmg_pct / 5,
            s.total_skills(),
            eff_fcr,
            s.fhr,
            s.belt_slots,
            raw_def,
            locality,
        ),
        SearchMode::MaxRes => (
            s.max_res_sum(),
            s.res_sum(),
            s.primary_power_skills(),
            eff_fcr,
            s.belt_slots,
            raw_def,
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
            raw_def,
            locality,
        ),
        SearchMode::LevelingRes => (
            s.res_sum(),
            offense.score_stats(*s),
            s.cbf,
            s.fhr,
            s.belt_slots,
            raw_def,
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
    is_ring: bool,
    mode: SearchMode,
    offense: OffenseProfile,
    c: &BuildConstraints,
) -> Vec<ItemSpec> {
    prune_candidates(items, c.limit, is_ring, c.base_str, c.base_dex, |it| {
        (
            &it.name,
            it.stats().for_mode(mode, offense, c),
            item_eff_reqs(it),
            single_set_sig(it),
        )
    })
}

fn empty_dominators(
    items: &[ItemSpec],
    mode: SearchMode,
    offense: OffenseProfile,
    c: &BuildConstraints,
) -> usize {
    items
        .iter()
        .filter(|it| {
            it.set_group == 0
                && it.weapon_class() == WeaponClass::OneHandSwing
                && it.wsm == 0
                && dominates_empty(
                    it.stats().for_mode(mode, offense, c),
                    item_prune_reqs(it, c.base_str, c.base_dex),
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
    let weapon_fixed = c.is_weapon_fixed();
    let shield_fixed = c.is_shield_fixed();
    let require_melee = offense.requires_melee() && !weapon_fixed;
    let mut weapons_1h: Vec<ItemSpec> = items
        .iter()
        .filter(|i| {
            i.slot == "weapon" && valid_item(i) && (!require_melee || i.hand_weapon().can_zeal)
        })
        .cloned()
        .collect();
    let mut shields: Vec<ItemSpec> = items
        .iter()
        .filter(|i| i.slot == "shield" && valid_item(i))
        .cloned()
        .collect();
    let must_keep_shield = shield_fixed && !shields.is_empty();
    let mut weapons_2h: Vec<ItemSpec> = if require_shield || must_keep_shield {
        Vec::new()
    } else {
        items
            .iter()
            .filter(|i| {
                i.slot == "weapon2h"
                    && valid_item(i)
                    && (!require_melee || i.hand_weapon().can_zeal)
            })
            .cloned()
            .collect()
    };
    let must_keep_2h = weapon_fixed && !weapons_2h.is_empty();

    if weapon_fixed {
        if !must_keep_2h && weapons_1h.is_empty() && !shields.is_empty() {
            weapons_1h.push(ItemSpec::empty("weapon"));
        }
    } else if !shields.is_empty() && empty_dominators(&weapons_1h, mode, offense, c) == 0 {
        weapons_1h.push(ItemSpec::empty("weapon"));
    }

    if shield_fixed {
        if !require_shield && shields.is_empty() && !weapons_1h.is_empty() {
            shields.push(ItemSpec::empty("shield"));
        }
    } else if !require_shield
        && !weapons_1h.is_empty()
        && empty_dominators(&shields, mode, offense, c) == 0
    {
        shields.push(ItemSpec::empty("shield"));
    }

    weapons_1h.sort_by_key(|it| {
        let max_s = it.max_total_stats();
        Reverse(item_sort_key(
            mode,
            offense,
            &max_s.for_mode(mode, offense, c),
            item_locality_score(&it.loc),
            max_s.defense,
        ))
    });
    shields.sort_by_key(|it| {
        let max_s = it.max_total_stats();
        Reverse(item_sort_key(
            mode,
            offense,
            &max_s.for_mode(mode, offense, c),
            item_locality_score(&it.loc),
            max_s.defense,
        ))
    });
    weapons_2h.sort_by_key(|it| {
        let max_s = it.max_total_stats();
        Reverse(item_sort_key(
            mode,
            offense,
            &max_s.for_mode(mode, offense, c),
            item_locality_score(&it.loc),
            max_s.defense,
        ))
    });

    let empty_hand = ItemSpec::empty("weapon").hand_weapon();
    let empty_anim = offense.weapon_anim_key(mode, empty_hand);
    let fold_wep_phys =
        offense.is_melee_dps() && matches!(mode, SearchMode::Leveling | SearchMode::LevelingRes);
    let wep_prune_stats = |it: &ItemSpec| {
        let mut s = it.stats().for_mode(mode, offense, c);
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
    let shields = prune_slot_items(shields, false, mode, offense, c);
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

    let has_kept_hand_item =
        must_keep_shield || must_keep_2h || (weapon_fixed && !weapons_1h.is_empty());
    if !require_shield && !has_kept_hand_item {
        if weapon_fixed && shield_fixed {
            if hands.is_empty() {
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
            if !has_empty_dom {
                hands.push(ItemPair::from_pair(
                    &ItemSpec::empty("weapon"),
                    &ItemSpec::empty("shield"),
                    "hands",
                ));
            }
        }
    }

    hands.sort_by_key(|h| {
        Reverse(item_sort_key(
            mode,
            offense,
            &h.max_stats.for_mode(mode, offense, c),
            h.locality,
            h.max_stats.defense,
        ))
    });
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
    require_melee: bool,
    is_slot_fixed: impl Fn(&str) -> bool,
) -> Vec<ItemSpec> {
    let excluded = |it: &ItemSpec| {
        (!allow_mf && it.mf != 0)
            || (require_shield && it.slot == "weapon2h")
            || (require_melee
                && matches!(it.slot.as_str(), "weapon" | "weapon2h")
                && !it.hand_weapon().can_zeal)
    };
    let mut group_seen: HashMap<i32, HashSet<i32>> = HashMap::new();
    for (idx, it) in items.iter().enumerate() {
        if excluded(it) || it.set_group == 0 {
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
        if excluded(it) || it.set_group == 0 {
            continue;
        }
        let max_pcs = group_seen.get(&it.set_group).map_or(0, |s| s.len() as i32);
        if max_pcs >= 2
            && it
                .set_bonuses
                .iter()
                .chain(it.global_set_bonuses.iter())
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
                cloned.global_set_bonuses.clear();
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
                cloned
                    .global_set_bonuses
                    .retain(|(req, b)| *req >= 2 && *req <= max_pcs && b.stats() != Stats::default());
            }
        }
        if !is_slot_fixed(&cloned.slot)
            && was_set
            && cloned.set_group == 0
            && cloned.stats() == Stats::default()
        {
            continue;
        }
        out.push(cloned);
    }
    out
}

const RELAXED_MIN_CR: i32 = -1_000_000;
type RingPairDedupKey = (Stats, i32, i32, ItemSetSig);
type RingPairNames = HashSet<(String, String)>;

struct GlobalSetBounds {
    bonuses: Vec<Stats>,
    overflow_ub: Stats,
    hand_masks: Vec<(u64, u64)>,
    group_masks: Vec<Vec<u64>>,
    ring_pair_masks: Vec<(u64, u64)>,
    suf_one: Vec<u64>,
    suf_two: Vec<u64>,
}

impl GlobalSetBounds {
    fn build(hands: &[ItemPair], groups: &[Vec<ItemSpec>], ring_pairs: &[ItemPair]) -> Self {
        let mut group_to_idx: HashMap<i32, usize> = HashMap::new();
        let mut bonuses: Vec<Stats> = Vec::new();
        let mut overflow_groups: HashMap<i32, Stats> = HashMap::new();

        let mut register = |it: &ItemSpec| {
            if it.set_group == 0 || it.global_set_bonuses.is_empty() {
                return;
            }
            let max_b = it.max_possible_global_set_bonus_stats();
            if max_b == Stats::default() {
                return;
            }
            if let Some(&idx) = group_to_idx.get(&it.set_group) {
                bonuses[idx] = bonuses[idx].max_each(max_b);
            } else if let Some(prev) = overflow_groups.get_mut(&it.set_group) {
                *prev = prev.max_each(max_b);
            } else if bonuses.len() < 64 {
                let idx = bonuses.len();
                group_to_idx.insert(it.set_group, idx);
                bonuses.push(max_b);
            } else {
                overflow_groups.insert(it.set_group, max_b);
            }
        };

        for h in hands {
            register(&h.first);
            register(&h.second);
        }
        for grp in groups {
            for it in grp {
                register(it);
            }
        }
        for rp in ring_pairs {
            register(&rp.first);
            register(&rp.second);
        }

        let overflow_ub = overflow_groups
            .into_values()
            .fold(Stats::default(), |acc, s| acc.add(s));

        let bit_of = |it: &ItemSpec| -> u64 {
            if it.set_group == 0 {
                0
            } else {
                group_to_idx
                    .get(&it.set_group)
                    .map_or(0, |&idx| 1u64 << idx)
            }
        };
        let pair_mask = |p: &ItemPair| -> (u64, u64) {
            let b1 = bit_of(&p.first);
            let b2 = bit_of(&p.second);
            (b1 | b2, b1 & b2)
        };

        let hand_masks: Vec<(u64, u64)> = hands.iter().map(&pair_mask).collect();
        let group_masks: Vec<Vec<u64>> = groups
            .iter()
            .map(|grp| grp.iter().map(&bit_of).collect())
            .collect();
        let ring_pair_masks: Vec<(u64, u64)> = ring_pairs.iter().map(&pair_mask).collect();

        let n = 1 + groups.len() + 1;
        let mut slot_one = vec![0u64; n];
        let mut slot_two = vec![0u64; n];
        for &(m1, m2) in &hand_masks {
            slot_one[0] |= m1;
            slot_two[0] |= m2;
        }
        for (k, gm) in group_masks.iter().enumerate() {
            for &m in gm {
                slot_one[k + 1] |= m;
            }
        }
        for &(m1, m2) in &ring_pair_masks {
            slot_one[n - 1] |= m1;
            slot_two[n - 1] |= m2;
        }

        let mut suf_one = vec![0u64; n + 1];
        let mut suf_two = vec![0u64; n + 1];
        for i in (0..n).rev() {
            suf_two[i] = suf_two[i + 1] | slot_two[i] | (suf_one[i + 1] & slot_one[i]);
            suf_one[i] = suf_one[i + 1] | slot_one[i];
        }

        Self {
            bonuses,
            overflow_ub,
            hand_masks,
            group_masks,
            ring_pair_masks,
            suf_one,
            suf_two,
        }
    }

    #[inline]
    fn ub_for_mask(&self, mut mask: u64) -> Stats {
        let mut acc = self.overflow_ub;
        while mask != 0 {
            let b = mask.trailing_zeros() as usize;
            acc = acc.add(self.bonuses[b]);
            mask &= mask - 1;
        }
        acc
    }
}

struct SearchPool<'a> {
    hands: &'a [ItemPair],
    groups: &'a [Vec<ItemSpec>],
    ring_pairs: &'a [ItemPair],
    suf: &'a [Stats],
    global_sets: &'a GlobalSetBounds,
    raw_pool: &'a [&'a CharmSpec],
}

#[derive(Clone, Copy)]
struct DfsNode {
    acc: Stats,
    reqs: (i32, i32),
    g_one: u64,
    g_two: u64,
    non_wep_all_sk: i32,
    has_set: bool,
}

fn leaf_items_ref<'a>(
    hand: &'a ItemPair,
    groups: &'a [Vec<ItemSpec>],
    chosen_slots: &[usize],
    rp: &'a ItemPair,
) -> [&'a ItemSpec; LEAF_ITEM_COUNT] {
    std::array::from_fn(|i| match i {
        0 => &hand.first,
        1 => &hand.second,
        k if k < 2 + SINGLE_SLOTS.len() => {
            let slot_idx = k - 2;
            &groups[slot_idx][chosen_slots[slot_idx]]
        }
        k if k == 2 + SINGLE_SLOTS.len() => &rp.first,
        _ => &rp.second,
    })
}

struct SearchState<'a> {
    hands: &'a [ItemPair],
    hand_order: Vec<usize>,
    max_hand_ub_dps: i32,
    groups: &'a [Vec<ItemSpec>],
    ring_pairs: &'a [ItemPair],
    suf: &'a [Stats],
    global_sets: &'a GlobalSetBounds,
    has_overflow_set_ub: bool,
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

impl<'a> SearchState<'a> {
    fn can_prune_by_score(
        &self,
        ub_ch: Stats,
        hand: Option<HandWeapon>,
        caps: (i32, i32, i32, i32),
    ) -> bool {
        let level_scores = || {
            let eff_primary_ub = ub_ch.primary_power_skills_for(self.offense, self.c.has_aura);
            let off_ub = if self.offense.uses_dps_tables(self.c) {
                match hand {
                    Some(hw) => {
                        OffenseProfile::dps_bucket(self.offense.compute_dps(hw, ub_ch, self.c).0)
                    }
                    None => self.max_hand_ub_dps,
                }
            } else {
                let ub_ias = match hand {
                    Some(hw) => self.offense.attack_speed(hw.wclass, hw.wsm, ub_ch.ias).0,
                    None => ub_ch.ias,
                };
                self.offense.score(eff_primary_ub, ub_ias, ub_ch.cb)
            };
            let res_base = res_base_ub(ub_ch, caps, self.c);
            let cbf_ub = i32::from(ub_ch.cbf > 0);
            (off_ub, res_base, cbf_ub)
        };
        match self.mode {
            SearchMode::Power => self.top_results.nth_primary().is_some_and(|cutoff| {
                let power_ub = if self.offense.uses_caster_dps(self.c) {
                    self.offense.compute_caster_dps(ub_ch, self.c).floor() as i32
                } else {
                    ub_ch.primary_power_skills_for(self.offense, self.c.has_aura)
                };
                power_ub < cutoff
            }),
            SearchMode::Mf => self
                .top_results
                .nth_primary()
                .is_some_and(|cutoff| ub_ch.mf < cutoff),
            SearchMode::MaxRes => self.top_results.nth_top2().is_some_and(|cutoff| {
                (
                    capped_res_sum(ub_ch.fr, ub_ch.lr, ub_ch.cr, ub_ch.pr, caps),
                    ub_ch.primary_power_skills_for(self.offense, self.c.has_aura),
                ) < cutoff
            }),
            SearchMode::Leveling => self
                .top_results
                .nth_top3()
                .is_some_and(|cutoff| level_scores() < cutoff),
            SearchMode::LevelingRes => self.top_results.nth_top3().is_some_and(|cutoff| {
                let (off_ub, res_base, cbf_ub) = level_scores();
                (res_base, off_ub, cbf_ub) < cutoff
            }),
        }
    }

    #[inline]
    fn can_prune_ub(&self, ub: Stats, reqs: (i32, i32), hand: Option<HandWeapon>) -> bool {
        if ub.fcr < self.c.min_fcr
            || (self.c.require_cbf && ub.cbf <= 0)
            || ub.ias < self.c.min_ias
            || ub.cb < self.c.min_cb
            || (ub.life_leech + ub.ctc_lifetap_pct.clamp(0, 100) / 2) < self.c.min_ll
            || ub.pdr_pct.min(HARD_MAX_PDR_PCT) < self.c.min_pdr
        {
            return true;
        }
        let ub_ch = ub.add(self.ch);
        if ub_ch.fhr < self.c.min_fhr
            || ub_ch.fr < self.c.min_fr
            || ub_ch.lr < self.c.min_lr
            || ub_ch.cr < self.c.min_cr
            || ub_ch.pr < self.c.min_pr
            || ub_ch.frw < self.c.min_frw
            || ub_ch.mf < self.c.min_mf
        {
            return true;
        }
        let caps_ub = res_caps(ub, self.c);
        if caps_ub.0 < self.c.min_fr
            || caps_ub.1 < self.c.min_lr
            || caps_ub.2 < self.c.min_cr
            || caps_ub.3 < self.c.min_pr
        {
            return true;
        }
        if ub_ch.str_bonus < reqs.0 || ub_ch.dex_bonus < reqs.1 {
            return true;
        }
        self.can_prune_by_score(ub_ch, hand, caps_ub)
    }

    fn eval_ring_pairs(&mut self, cur: DfsNode) {
        let hand = &self.hands[self.chosen_hand];
        let hw = hand.first.hand_weapon();
        for rp_idx in 0..self.ring_pairs.len() {
            let rp = &self.ring_pairs[rp_idx];
            let (rp_one, rp_two) = self.global_sets.ring_pair_masks[rp_idx];
            let leaf_possible_g = cur.g_two | rp_two | (cur.g_one & rp_one);
            let leaf_ub = cur
                .acc
                .add(rp.max_stats)
                .add(self.global_sets.ub_for_mask(leaf_possible_g));
            let ub_reqs = merge_reqs(cur.reqs, rp.reqs);
            if self.can_prune_ub(leaf_ub, ub_reqs, Some(hw)) {
                continue;
            }

            let leaf_has_set = cur.has_set || rp.set_sig.is_some();
            let rp_max_stats = rp.max_stats;
            let rp_all_skills = rp.combined.all_skills;
            let (items_ref_opt, gear, leaf, all_sk_non_wep, (final_req_str, final_req_dex)) =
                if leaf_has_set {
                    let items_ref = leaf_items_ref(hand, self.groups, &self.chosen_slots, rp);
                    let (gear, all_sk_non_wep, reqs_exact) =
                        compute_effective_gear_stats_and_reqs(&items_ref);
                    let leaf = Stats {
                        fr: gear.fr + self.c.base_hell_res,
                        lr: gear.lr + self.c.base_hell_res,
                        cr: gear.cr + self.c.base_hell_res,
                        pr: gear.pr + self.c.base_hell_res,
                        str_bonus: gear.str_bonus + self.c.base_str,
                        dex_bonus: gear.dex_bonus + self.c.base_dex,
                        ..gear
                    };
                    (Some(items_ref), gear, leaf, all_sk_non_wep, reqs_exact)
                } else {
                    // With no set pieces anywhere on the leaf, `cur.acc.add(rp.max_stats)` is exact.
                    let leaf = cur.acc.add(rp_max_stats);
                    let gear = Stats {
                        fr: leaf.fr - self.c.base_hell_res,
                        lr: leaf.lr - self.c.base_hell_res,
                        cr: leaf.cr - self.c.base_hell_res,
                        pr: leaf.pr - self.c.base_hell_res,
                        str_bonus: leaf.str_bonus - self.c.base_str,
                        dex_bonus: leaf.dex_bonus - self.c.base_dex,
                        ..leaf
                    };
                    (
                        None,
                        gear,
                        leaf,
                        cur.non_wep_all_sk + rp_all_skills,
                        ub_reqs,
                    )
                };
            if leaf_has_set || self.has_overflow_set_ub {
                if !self.c.allow_mf && leaf.mf > 0 {
                    continue;
                }
                if self.can_prune_ub(leaf, (final_req_str, final_req_dex), Some(hw)) {
                    continue;
                }
            }
            self.evals += 1;

            let min_main_needed = match self.mode {
                SearchMode::LevelingRes => self.top_results.nth_primary().map_or(0, |cut| {
                    let caps_l = res_caps(leaf, self.c);
                    let cur_sum = res_base_ub(leaf, caps_l, self.c);
                    (cut - cur_sum).max(0)
                }),
                SearchMode::MaxRes => self.top_results.nth_primary().map_or(0, |cut| {
                    let caps_l = res_caps(leaf, self.c);
                    let cur_sum = capped_res_sum(leaf.fr, leaf.lr, leaf.cr, leaf.pr, caps_l);
                    (cut - cur_sum).max(0)
                }),
                SearchMode::Mf => self
                    .top_results
                    .nth_primary()
                    .map_or(0, |cut| (cut - leaf.mf).max(0)),
                SearchMode::Power => self.top_results.nth_primary().map_or(0, |cut| {
                    if self.offense.uses_caster_dps(self.c) {
                        let max_k = (self.ch.all_skills
                            + self.ch.action_skill_bonus
                            + self.ch.aura_skill_bonus)
                            .max(0);
                        (0..=max_k)
                            .find(|&k| {
                                let s = Stats {
                                    all_skills: leaf.all_skills + k,
                                    ..leaf
                                };
                                self.offense.compute_caster_dps(s, self.c).floor() as i32 >= cut
                            })
                            .unwrap_or(max_k + 1)
                    } else {
                        let cur_sk = leaf.primary_power_skills_for(self.offense, self.c.has_aura);
                        (cut - cur_sk).max(0)
                    }
                }),
                SearchMode::Leveling => 0,
            };
            let Some(mut charms_sel) = self.charm_solver.solve_with_min_main(
                leaf,
                (final_req_str, final_req_dex),
                min_main_needed,
            ) else {
                continue;
            };
            let has_shield = hand.second.slot == "shield" && hand.second.name != "(empty)";
            let mut sum =
                eval_build_summary(gear, all_sk_non_wep, hw, has_shield, &charms_sel, self.c);
            if (!self.c.allow_mf && sum.mf > 0)
                || sum.fcr < self.c.min_fcr
                || sum.fhr < self.c.min_fhr
                || (self.c.require_cbf && !sum.cbf)
                || sum.ias < self.c.min_ias
                || sum.cb < self.c.min_cb
                || (sum.life_leech + sum.ctc_lifetap_pct.clamp(0, 100) / 2) < self.c.min_ll
                || sum.pdr_pct < self.c.min_pdr
                || sum.frw < self.c.min_frw
                || sum.mf < self.c.min_mf
            {
                continue;
            }
            if sum.fr < self.c.min_fr
                || sum.lr < self.c.min_lr
                || sum.cr < self.c.min_cr
                || sum.pr < self.c.min_pr
            {
                continue;
            }
            let mut score = score_eval_summary(self.mode, self.offense, &sum, self.c);
            let items_ref = items_ref_opt
                .unwrap_or_else(|| leaf_items_ref(hand, self.groups, &self.chosen_slots, rp));
            score.locality = items_ref.iter().map(|it| item_locality_score(&it.loc)).sum();
            if self.offense.uses_dps_tables(self.c)
                && matches!(self.mode, SearchMode::Leveling | SearchMode::LevelingRes)
            {
                self.charm_solver.improve_for_dps(
                    gear,
                    all_sk_non_wep,
                    hw,
                    has_shield,
                    leaf,
                    (final_req_str, final_req_dex),
                    self.offense,
                    self.top_results.nth_top3(),
                    &mut charms_sel,
                    &mut sum,
                    &mut score,
                );
            }
            if !self.top_results.would_accept(score) {
                continue;
            }
            let res = sum.into_result(&items_ref, &charms_sel, 0);
            self.top_results.push(score, res, self.offense);
        }
    }

    fn dfs(&mut self, idx: usize, cur: DfsNode) {
        let possible_g = cur.g_two
            | (cur.g_one & self.global_sets.suf_one[idx])
            | self.global_sets.suf_two[idx];
        let ub = cur
            .acc
            .add(self.suf[idx])
            .add(self.global_sets.ub_for_mask(possible_g));
        let hand_opt = (idx > 0).then(|| self.hands[self.chosen_hand].first.hand_weapon());
        if self.can_prune_ub(ub, cur.reqs, hand_opt) {
            return;
        }

        if idx == self.groups.len() + 1 {
            self.eval_ring_pairs(cur);
            return;
        }

        if idx == 0 {
            for pos in 0..self.hand_order.len() {
                let i = self.hand_order[pos];
                let h = &self.hands[i];
                let (h_one, h_two) = self.global_sets.hand_masks[i];
                self.chosen_hand = i;
                self.dfs(
                    1,
                    DfsNode {
                        acc: cur.acc.add(h.max_stats),
                        reqs: merge_reqs(cur.reqs, h.reqs),
                        g_one: h_one,
                        g_two: h_two,
                        non_wep_all_sk: 0,
                        has_set: h.set_sig.is_some(),
                    },
                );
            }
            return;
        }

        let g = idx - 1;
        for i in 0..self.groups[g].len() {
            let it = &self.groups[g][i];
            let bit = self.global_sets.group_masks[g][i];
            self.chosen_slots.push(i);
            self.dfs(
                idx + 1,
                DfsNode {
                    acc: cur.acc.add(it.max_total_stats()),
                    reqs: merge_reqs(cur.reqs, item_eff_reqs(it)),
                    g_one: cur.g_one | bit,
                    g_two: cur.g_two | (cur.g_one & bit),
                    non_wep_all_sk: cur.non_wep_all_sk + it.all_skills,
                    has_set: cur.has_set || it.set_group != 0,
                },
            );
            self.chosen_slots.pop();
        }
    }
}

fn build_score_of_result(
    res: &BuildResult,
    mode: SearchMode,
    offense: OffenseProfile,
    c: &BuildConstraints,
) -> BuildScore {
    let item_refs: Vec<&ItemSpec> = res.items.iter().collect();
    let charm_refs: Vec<&CharmSpec> = res.charms.iter().collect();
    let (gear, all_sk_non_wep) = compute_effective_gear_stats(&item_refs);
    let hw = equipped_hand_weapon(&item_refs);
    let has_shield = item_refs
        .iter()
        .any(|it| it.slot == "shield" && it.name != "(empty)");
    let sum = eval_build_summary(gear, all_sk_non_wep, hw, has_shield, &charm_refs, c);
    let mut score = score_eval_summary(mode, offense, &sum, c);
    score.locality = item_refs
        .iter()
        .map(|it| item_locality_score(&it.loc))
        .sum();
    score
}

/// Compute the comparable Rust score tuple (without locality) for an evaluated `BuildResult`.
pub fn score_of_result_core(res: &BuildResult, c: &BuildConstraints) -> Result<ScoreTuple, String> {
    let class = CharClass::from_id(c.char_class)?;
    let offense = OffenseProfile::parse(&c.offense, class)?;
    TargetType::parse(&c.target_type)?;
    let mode = SearchMode::parse(&c.mode)?;
    Ok(build_score_of_result(res, mode, offense, c).without_locality_tuple())
}

fn run_search_pass(
    pool: &SearchPool<'_>,
    c: &BuildConstraints,
    mode: SearchMode,
    offense: OffenseProfile,
    score_floor: Option<BuildScore>,
) -> (Vec<BuildResult>, bool) {
    let charm_solver = CharmSolver::new(pool.raw_pool, c, mode);
    let has_cold_sunder = charm_solver.has_cold_sunder();
    let ch = charm_solver.charm_ub_stats();

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
            .enumerate()
            .map(|(h_idx, h)| {
                let (h_one, h_two) = pool.global_sets.hand_masks[h_idx];
                let possible_h = h_two
                    | (h_one & pool.global_sets.suf_one[1])
                    | pool.global_sets.suf_two[1];
                let ub_h = tail_ub
                    .add(h.max_stats)
                    .add(pool.global_sets.ub_for_mask(possible_h));
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

    let has_overflow_set_ub = pool.global_sets.overflow_ub != Stats::default();
    let mut state = SearchState {
        hands: pool.hands,
        hand_order,
        max_hand_ub_dps,
        groups: pool.groups,
        ring_pairs: pool.ring_pairs,
        suf: pool.suf,
        global_sets: pool.global_sets,
        has_overflow_set_ub,
        ch,
        charm_solver,
        c,
        mode,
        offense,
        chosen_hand: 0,
        chosen_slots: Vec::with_capacity(pool.groups.len()),
        evals: 0,
        top_results: TopResults::with_floor(c.limit, score_floor),
    };

    state.dfs(
        0,
        DfsNode {
            acc: init_acc,
            reqs: (0, 0),
            g_one: 0,
            g_two: 0,
            non_wep_all_sk: 0,
            has_set: false,
        },
    );

    let total_evals = state.evals;
    (state.top_results.finish(total_evals), has_cold_sunder)
}

pub fn optimize_builds_core(
    items: &[ItemSpec],
    charms: &[CharmSpec],
    c: &BuildConstraints,
) -> Result<Vec<BuildResult>, String> {
    optimize_builds_with_baseline(items, charms, c, None)
}

pub fn optimize_builds_with_baseline(
    items: &[ItemSpec],
    charms: &[CharmSpec],
    c: &BuildConstraints,
    baseline: Option<&BuildResult>,
) -> Result<Vec<BuildResult>, String> {
    let class = CharClass::from_id(c.char_class)?;
    let offense = OffenseProfile::parse(&c.offense, class)?;
    TargetType::parse(&c.target_type)?;
    let mode = SearchMode::parse(&c.mode)?;

    let valid_item = |i: &ItemSpec| c.allow_mf || i.mf == 0;
    let norm_items = normalize_set_items(
        items,
        c.allow_mf,
        offense.requires_shield(),
        offense.requires_melee() && !c.is_weapon_fixed(),
        |slot| c.is_slot_fixed(slot),
    );

    let hands = build_hands(&norm_items, &valid_item, mode, offense, c);

    let mut groups: Vec<Vec<ItemSpec>> = Vec::with_capacity(SINGLE_SLOTS.len());
    for slot in SINGLE_SLOTS {
        let mut slot_items: Vec<ItemSpec> = norm_items
            .iter()
            .filter(|i| i.slot == slot && valid_item(i))
            .cloned()
            .collect();
        let need_empty = if c.is_slot_fixed(slot) {
            slot_items.is_empty()
        } else {
            empty_dominators(&slot_items, mode, offense, c) == 0
        };
        if need_empty {
            slot_items.push(ItemSpec::empty(slot));
        }
        slot_items.sort_by_key(|it| {
            let max_s = it.max_total_stats();
            Reverse(item_sort_key(
                mode,
                offense,
                &max_s.for_mode(mode, offense, c),
                item_locality_score(&it.loc),
                max_s.defense,
            ))
        });
        groups.push(prune_slot_items(slot_items, false, mode, offense, c));
    }

    let mut rngs: Vec<ItemSpec> = norm_items
        .iter()
        .filter(|i| i.slot == "ring" && valid_item(i))
        .cloned()
        .collect();
    let empty_rings_needed = if c.is_slot_fixed("ring") {
        2usize.saturating_sub(rngs.len())
    } else {
        2usize.saturating_sub(empty_dominators(&rngs, mode, offense, c))
    };
    for _ in 0..empty_rings_needed {
        rngs.push(ItemSpec::empty("ring"));
    }
    rngs.sort_by_key(|it| {
        let max_s = it.max_total_stats();
        Reverse(item_sort_key(
            mode,
            offense,
            &max_s.for_mode(mode, offense, c),
            item_locality_score(&it.loc),
            max_s.defense,
        ))
    });
    let rngs = prune_slot_items(rngs, true, mode, offense, c);

    let mut all_pairs: Vec<ItemPair> = Vec::with_capacity(rngs.len() * rngs.len() / 2);
    for i in 0..rngs.len() {
        for j in (i + 1)..rngs.len() {
            all_pairs.push(ItemPair::from_pair(&rngs[i], &rngs[j], "rings"));
        }
    }
    all_pairs.sort_by_key(|rp| {
        Reverse(item_sort_key(
            mode,
            offense,
            &rp.max_stats.for_mode(mode, offense, c),
            rp.locality,
            rp.max_stats.defense,
        ))
    });
    let mut ring_pairs: Vec<ItemPair> = Vec::with_capacity(all_pairs.len());
    let mut seen_rp: HashMap<RingPairDedupKey, RingPairNames> = HashMap::new();
    for rp in all_pairs {
        let comb_stats = rp.combined.stats().for_mode(mode, offense, c);
        let name_pair = if rp.first.name <= rp.second.name {
            (rp.first.name.clone(), rp.second.name.clone())
        } else {
            (rp.second.name.clone(), rp.first.name.clone())
        };
        let names = seen_rp
            .entry((comb_stats, rp.reqs.0, rp.reqs.1, rp.set_sig.clone()))
            .or_default();
        if names.contains(&name_pair) || (c.limit > 0 && names.len() >= c.limit) {
            continue;
        }
        names.insert(name_pair);
        ring_pairs.push(rp);
    }

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

    let global_sets = GlobalSetBounds::build(&hands, &groups, &ring_pairs);
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
        global_sets: &global_sets,
        raw_pool: &raw_pool,
    };
    let strict_floor = baseline
        .filter(|b| b.cr >= c.min_cr)
        .map(|b| build_score_of_result(b, mode, offense, c));
    let (results, has_cold_sunder) = run_search_pass(&pool, c, mode, offense, strict_floor);
    if results.is_empty()
        && strict_floor.is_none()
        && has_cold_sunder
        && c.min_cr > RELAXED_MIN_CR
    {
        let mut relaxed = c.clone();
        relaxed.min_cr = RELAXED_MIN_CR;
        let relaxed_floor = baseline.map(|b| build_score_of_result(b, mode, offense, &relaxed));
        return Ok(run_search_pass(&pool, &relaxed, mode, offense, relaxed_floor).0);
    }
    Ok(results)
}

/// Compute the Rust build score tuple (excluding locality) for a `BuildResult`.
#[cfg(feature = "python")]
#[pyfunction]
pub fn score_of_result(res: &BuildResult, constraints: &BuildConstraints) -> PyResult<ScoreTuple> {
    score_of_result_core(res, constraints).map_err(PyValueError::new_err)
}

/// Find top-ranked builds satisfying `constraints` using branch-and-bound DFS in Rust.
#[cfg(feature = "python")]
#[pyfunction]
#[pyo3(signature = (items, charms, constraints, baseline = None))]
pub fn optimize_builds(
    py: Python<'_>,
    items: Vec<ItemSpec>,
    charms: Vec<CharmSpec>,
    constraints: BuildConstraints,
    baseline: Option<BuildResult>,
) -> PyResult<Vec<BuildResult>> {
    py.allow_threads(|| {
        optimize_builds_with_baseline(&items, &charms, &constraints, baseline.as_ref())
    })
    .map_err(PyValueError::new_err)
}

#[cfg(test)]
#[path = "search_tests.rs"]
mod tests;
