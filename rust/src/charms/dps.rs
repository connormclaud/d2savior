use super::dp::{
    CharmGroup, StatTotals, UbGroupEntry, eval_sorted_ub, min_slots_for_res_axis, min_slots_for_val,
};
use super::solver::{CharmSolver, DpsIndex};
use crate::dps::{CthEval, FastLeafDps, HandWeapon, OffenseProfile};
use crate::eval::{EvalSummary, base_res_caps, eval_build_summary, res_caps};
use crate::search::{BuildScore, score_eval_summary};
use crate::stats::Stats;
use crate::types::{CharClass, CharmSpec, ResolvedConstraints, SearchMode};

impl<'a> CharmSolver<'a> {
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn improve_for_dps(
        &mut self,
        gear: Stats,
        all_sk_non_wep: i32,
        hw: HandWeapon,
        has_shield: bool,
        leaf: Stats,
        reqs: (i32, i32),
        cutoff: Option<(i32, i32, i32)>,
        best_charms: &mut Vec<&'a CharmSpec>,
        best_sum: &mut EvalSummary,
        best_score: &mut BuildScore,
    ) {
        if self.dps.is_none() {
            return;
        }
        let offense = self.c.offense;
        let base_fast = offense.fast_leaf_dps(hw, leaf, &self.c);
        let gear_bucket = OffenseProfile::dps_bucket(base_fast.eval_eff_dps());
        let ub_leaf = leaf.add(self.charm_ub_stats());
        let global_ub_bucket =
            OffenseProfile::dps_bucket(offense.compute_eff_dps(hw, ub_leaf, &self.c));
        let caps_t = res_caps(leaf, &self.c);
        let bc_t = base_res_caps(&self.c);
        let base_caps = [
            caps_t.0.min(bc_t.0),
            caps_t.1.min(bc_t.1),
            caps_t.2.min(bc_t.2),
            caps_t.3.min(bc_t.3),
        ];
        let cbf_val = i32::from(leaf.cbf > 0);
        if let Some(cut) = cutoff {
            let max_res_base: i32 = [
                (ub_leaf.fr).min(base_caps[0]),
                (ub_leaf.lr).min(base_caps[1]),
                (ub_leaf.cr).min(base_caps[2]),
                (ub_leaf.pr).min(base_caps[3]),
            ]
            .iter()
            .sum();
            let global_top3 = match self.c.mode {
                SearchMode::Leveling => (global_ub_bucket, max_res_base, cbf_val),
                SearchMode::LevelingRes => (max_res_base, global_ub_bucket, cbf_val),
                _ => return,
            };
            if global_top3 < cut {
                return;
            }
        }
        let Some(dps_refiner) = self.dps.as_deref_mut() else {
            return;
        };
        let dps = &dps_refiner.index;
        let non_dps_solver = &mut dps_refiner.non_dps_solver;
        if dps.groups.is_empty()
            && (dps.pure_dps.is_empty() || gear_bucket >= global_ub_bucket)
        {
            return;
        }

        struct DpsStatic<'b, 'a> {
            pool: &'b [&'a CharmSpec],
            c: ResolvedConstraints<'a>,
            max_slots: i32,
            gear: Stats,
            all_sk_non_wep: i32,
            hw: HandWeapon,
            has_shield: bool,
            leaf: Stats,
            reqs: (i32, i32),
            cutoff: Option<(i32, i32, i32)>,
            cbf_val: i32,
            dps: &'b DpsIndex,
            base_caps: [i32; 4],
            base_fast: FastLeafDps,
        }

        struct DpsMut<'b, 'a> {
            non_dps_solver: &'b mut CharmSolver<'a>,
            cur_indices: Vec<usize>,
            pure_buf: Vec<(f64, u64)>,
            cth_cache: Vec<Option<CthEval>>,
            best_charms: &'b mut Vec<&'a CharmSpec>,
            best_sum: &'b mut EvalSummary,
            best_score: &'b mut BuildScore,
        }

        #[inline]
        fn required_dps_bucket(
            mode: SearchMode,
            res_ub: i32,
            cbf_val: i32,
            cutoff: Option<(i32, i32, i32)>,
            best_top2: (i32, i32),
        ) -> Option<i32> {
            match mode {
                SearchMode::Leveling => {
                    let mut req = if res_ub < best_top2.1 {
                        best_top2.0 + 1
                    } else {
                        best_top2.0
                    };
                    if let Some((cut_bkt, cut_res, cut_cbf)) = cutoff {
                        let c_req = if (res_ub, cbf_val) < (cut_res, cut_cbf) {
                            cut_bkt + 1
                        } else {
                            cut_bkt
                        };
                        req = req.max(c_req);
                    }
                    Some(req)
                }
                SearchMode::LevelingRes => {
                    if res_ub < best_top2.0 || cutoff.is_some_and(|cut| res_ub < cut.0) {
                        return None;
                    }
                    let mut req = if res_ub == best_top2.0 {
                        best_top2.1
                    } else {
                        0
                    };
                    if let Some((cut_res, cut_bkt, cut_cbf)) = cutoff
                        && res_ub == cut_res
                    {
                        req = req.max(if cbf_val < cut_cbf {
                            cut_bkt + 1
                        } else {
                            cut_bkt
                        });
                    }
                    Some(req)
                }
                _ => None,
            }
        }

        fn leaf_with_cur(leaf: Stats, cur: StatTotals, class: CharClass) -> Stats {
            cur.add_to_stats(leaf, class)
        }

        fn dfs_dps<'b, 'a>(
            st: &DpsStatic<'b, 'a>,
            mut_ctx: &mut DpsMut<'b, 'a>,
            mut g_idx: usize,
            rem_slots: i32,
            cur: StatTotals,
        ) {
            let dps = st.dps;
            if g_idx < dps.groups.len() && rem_slots < dps.min_size[g_idx] {
                g_idx = dps.groups.len();
            }
            let sp = dps.suf_pos[g_idx];
            let rs_idx = (rem_slots.max(0) as usize).min(dps.nd_fhr_at.len() - 1);
            let ub_rem_at = |cur_g: usize, sp_v: i32, order: &[UbGroupEntry], slots: i32| {
                if cur_g >= dps.groups.len() || slots <= 0 || sp_v <= 0 {
                    0
                } else {
                    sp_v.min(eval_sorted_ub(order, cur_g, slots))
                }
            };
            let leaf = st.leaf;
            let rem_str_all = if leaf.str_bonus + cur.str_bonus < st.reqs.0 {
                ub_rem_at(g_idx, sp.str_bonus, &dps.order_str, rem_slots)
            } else {
                0
            };
            let rem_dex_all = if leaf.dex_bonus + cur.dex_bonus < st.reqs.1 {
                ub_rem_at(g_idx, sp.dex_bonus, &dps.order_dex, rem_slots)
            } else {
                0
            };
            if leaf.str_bonus + cur.str_bonus + rem_str_all < st.reqs.0
                || leaf.dex_bonus + cur.dex_bonus + rem_dex_all < st.reqs.1
            {
                return;
            }
            let rem_fhr = if leaf.fhr + cur.fhr < st.c.min_fhr {
                ub_rem_at(g_idx, sp.fhr, &dps.order_fhr, rem_slots)
            } else {
                0
            };
            let rem_frw = if leaf.frw + cur.frw < st.c.min_frw {
                ub_rem_at(g_idx, sp.frw, &dps.order_frw, rem_slots)
            } else {
                0
            };
            let rem_mf = if leaf.mf + cur.mf < st.c.min_mf {
                ub_rem_at(g_idx, sp.mf, &dps.order_mf, rem_slots)
            } else {
                0
            };
            let mut s_req =
                min_slots_for_val(&dps.nd_fhr_at, st.c.min_fhr - (leaf.fhr + cur.fhr + rem_fhr))
                    .max(min_slots_for_val(
                        &dps.nd_frw_at,
                        st.c.min_frw - (leaf.frw + cur.frw + rem_frw),
                    ))
                    .max(min_slots_for_val(
                        &dps.nd_mf_at,
                        st.c.min_mf - (leaf.mf + cur.mf + rem_mf),
                    ));
            if s_req > rem_slots {
                return;
            }
            let leaf_res = [leaf.fr, leaf.lr, leaf.cr, leaf.pr];
            let min_res = [st.c.min_fr, st.c.min_lr, st.c.min_cr, st.c.min_pr];
            let mut rem_r_opt = [None; 4];
            let mut ub_res_base = 0i32;
            for r in 0..4 {
                let cap_r = st.base_caps[r];
                let base_r = leaf_res[r] + cur.res[r];
                let cur_plus_nd = base_r + dps.nd_res_at[rs_idx][r];
                if cur_plus_nd >= cap_r.max(min_res[r]) {
                    ub_res_base += cur_plus_nd.min(cap_r);
                } else {
                    let rem_r = ub_rem_at(g_idx, sp.res[r], &dps.order_res[r], rem_slots);
                    rem_r_opt[r] = Some(rem_r);
                    let total_r = cur_plus_nd + rem_r;
                    if total_r < min_res[r] {
                        return;
                    }
                    ub_res_base += total_r.min(cap_r);
                }
                if base_r < min_res[r] {
                    let rem_r = *rem_r_opt[r].get_or_insert_with(|| {
                        ub_rem_at(g_idx, sp.res[r], &dps.order_res[r], rem_slots)
                    });
                    s_req = s_req.max(min_slots_for_res_axis(
                        &dps.nd_res_at,
                        r,
                        min_res[r] - (base_r + rem_r),
                    ));
                    if s_req > rem_slots {
                        return;
                    }
                }
            }
            let mut s_req_res = s_req;
            if st.c.mode == SearchMode::LevelingRes {
                let target_res_base = mut_ctx
                    .best_score
                    .primary
                    .max(st.cutoff.map_or(i32::MIN, |cut| cut.0));
                if ub_res_base < target_res_base {
                    return;
                }
                let mut rem_r_full = [0i32; 4];
                for r in 0..4 {
                    let cap_r = st.base_caps[r];
                    if leaf_res[r] + cur.res[r] < cap_r {
                        rem_r_full[r] = *rem_r_opt[r].get_or_insert_with(|| {
                            ub_rem_at(g_idx, sp.res[r], &dps.order_res[r], rem_slots)
                        });
                    }
                }
                let mut found = false;
                let max_s = (rem_slots as usize).min(dps.nd_res_at.len() - 1);
                for (s, nd_res) in dps
                    .nd_res_at
                    .iter()
                    .enumerate()
                    .take(max_s + 1)
                    .skip(s_req as usize)
                {
                    let mut sum_r = 0i32;
                    for r in 0..4 {
                        let cap_r = st.base_caps[r];
                        sum_r +=
                            (leaf_res[r] + cur.res[r] + rem_r_full[r] + nd_res[r]).min(cap_r);
                    }
                    if sum_r >= target_res_base {
                        s_req_res = s as i32;
                        found = true;
                        break;
                    }
                }
                if !found {
                    return;
                }
            }
            let dps_rem_slots = rem_slots - s_req_res;
            if g_idx < dps.groups.len() && dps_rem_slots < dps.min_size[g_idx] {
                g_idx = dps.groups.len();
            }

            if g_idx == dps.groups.len() {
                let leaf_d = leaf_with_cur(leaf, cur, st.c.class);
                if leaf_d.fhr + dps.nd_fhr_at[rs_idx] < st.c.min_fhr
                    || leaf_d.frw + dps.nd_frw_at[rs_idx] < st.c.min_frw
                    || leaf_d.mf + dps.nd_mf_at[rs_idx] < st.c.min_mf
                    || leaf_d.fr + dps.nd_res_at[rs_idx][0] < st.c.min_fr
                    || leaf_d.lr + dps.nd_res_at[rs_idx][1] < st.c.min_lr
                    || leaf_d.cr + dps.nd_res_at[rs_idx][2] < st.c.min_cr
                    || leaf_d.pr + dps.nd_res_at[rs_idx][3] < st.c.min_pr
                {
                    return;
                }
                let fast = if cur.all_skills == 0
                    && cur.class_skills == 0
                    && cur.action_skills == 0
                    && cur.aura_skills == 0
                {
                    st.base_fast.with_non_skill_deltas(
                        cur.str_bonus,
                        cur.dex_bonus,
                        cur.ar,
                        cur.flat_phys_2x,
                        cur.flat_fire_2x,
                        cur.flat_elem_2x,
                        cur.psn_dps_2x,
                    )
                } else {
                    st.c.offense.fast_leaf_dps(st.hw, leaf_d, &st.c)
                };
                let max_pure_s = (dps_rem_slots.max(0) as usize).min(st.max_slots.max(0) as usize);
                let leaf_res_ub_0: i32 = [
                    (leaf_d.fr + dps.nd_res_at[rs_idx][0]).min(st.base_caps[0]),
                    (leaf_d.lr + dps.nd_res_at[rs_idx][1]).min(st.base_caps[1]),
                    (leaf_d.cr + dps.nd_res_at[rs_idx][2]).min(st.base_caps[2]),
                    (leaf_d.pr + dps.nd_res_at[rs_idx][3]).min(st.base_caps[3]),
                ]
                .iter()
                .sum();
                let best_top2 = (mut_ctx.best_score.primary, mut_ctx.best_score.secondary);
                let Some(req_bkt) = required_dps_bucket(
                    st.c.mode,
                    leaf_res_ub_0,
                    st.cbf_val,
                    st.cutoff,
                    best_top2,
                ) else {
                    return;
                };
                let leaf_ub_dps = dps.pure_dps.max_dps_ub(&fast, max_pure_s);
                if req_bkt > 0 && leaf_ub_dps < OffenseProfile::dps_bucket_safe_min_dps(req_bkt) {
                    return;
                }
                let leaf_ub_bucket = OffenseProfile::dps_bucket(leaf_ub_dps);
                let leaf_top3 = match st.c.mode {
                    SearchMode::Leveling => (leaf_ub_bucket, leaf_res_ub_0, st.cbf_val),
                    SearchMode::LevelingRes => (leaf_res_ub_0, leaf_ub_bucket, st.cbf_val),
                    _ => return,
                };
                if st.cutoff.is_some_and(|cut| leaf_top3 < cut)
                    || (leaf_top3.0, leaf_top3.1) < best_top2
                {
                    return;
                }
                dps.pure_dps.solve_for_leaf_into(
                    &fast,
                    max_pure_s,
                    &mut mut_ctx.cth_cache,
                    &mut mut_ctx.pure_buf,
                );
                let mut prev_tested_bucket: Option<i32> = None;
                for pure_s in 0..=max_pure_s {
                    if pure_s > 0 && mut_ctx.pure_buf[pure_s].0 <= mut_ctx.pure_buf[pure_s - 1].0 {
                        continue;
                    }
                    let rem_nd = rem_slots - pure_s as i32;
                    let nd_idx = (rem_nd.max(0) as usize).min(dps.nd_fhr_at.len() - 1);
                    if leaf_d.fhr + dps.nd_fhr_at[nd_idx] < st.c.min_fhr
                        || leaf_d.frw + dps.nd_frw_at[nd_idx] < st.c.min_frw
                        || leaf_d.mf + dps.nd_mf_at[nd_idx] < st.c.min_mf
                        || leaf_d.fr + dps.nd_res_at[nd_idx][0] < st.c.min_fr
                        || leaf_d.lr + dps.nd_res_at[nd_idx][1] < st.c.min_lr
                        || leaf_d.cr + dps.nd_res_at[nd_idx][2] < st.c.min_cr
                        || leaf_d.pr + dps.nd_res_at[nd_idx][3] < st.c.min_pr
                    {
                        continue;
                    }
                    let cand_res_ub: i32 = [
                        (leaf_d.fr + dps.nd_res_at[nd_idx][0]).min(st.base_caps[0]),
                        (leaf_d.lr + dps.nd_res_at[nd_idx][1]).min(st.base_caps[1]),
                        (leaf_d.cr + dps.nd_res_at[nd_idx][2]).min(st.base_caps[2]),
                        (leaf_d.pr + dps.nd_res_at[nd_idx][3]).min(st.base_caps[3]),
                    ]
                    .iter()
                    .sum();
                    let best_top2 = (mut_ctx.best_score.primary, mut_ctx.best_score.secondary);
                    let Some(req_bkt) = required_dps_bucket(
                        st.c.mode,
                        cand_res_ub,
                        st.cbf_val,
                        st.cutoff,
                        best_top2,
                    ) else {
                        continue;
                    };
                    let cand_dps = mut_ctx.pure_buf[pure_s].0;
                    if req_bkt > 0 && cand_dps < OffenseProfile::dps_bucket_safe_min_dps(req_bkt)
                    {
                        continue;
                    }
                    let cand_bucket = OffenseProfile::dps_bucket(cand_dps);
                    if prev_tested_bucket == Some(cand_bucket) {
                        continue;
                    }
                    let cand_top3 = match st.c.mode {
                        SearchMode::Leveling => (cand_bucket, cand_res_ub, st.cbf_val),
                        SearchMode::LevelingRes => (cand_res_ub, cand_bucket, st.cbf_val),
                        _ => continue,
                    };
                    if st.cutoff.is_some_and(|cut| cand_top3 < cut)
                        || (cand_top3.0, cand_top3.1) < best_top2
                    {
                        continue;
                    }
                    prev_tested_bucket = Some(cand_bucket);
                    let Some(mut cand_charms) =
                        mut_ctx
                            .non_dps_solver
                            .solve_with_budget(leaf_d, (0, 0), rem_nd, 0)
                    else {
                        continue;
                    };
                    for &idx in &mut_ctx.cur_indices {
                        cand_charms.push(st.pool[idx]);
                    }
                    let mut mask = mut_ctx.pure_buf[pure_s].1;
                    while mask != 0 {
                        let b = mask.trailing_zeros() as usize;
                        cand_charms.push(st.pool[dps.pure_dps.item_indices[b]]);
                        mask &= mask - 1;
                    }
                    let cand_sum = eval_build_summary(
                        st.gear,
                        st.all_sk_non_wep,
                        st.hw,
                        st.has_shield,
                        &cand_charms,
                        &st.c,
                    );
                    if (!st.c.allow_mf && cand_sum.mf > 0)
                        || cand_sum.fhr < st.c.min_fhr
                        || cand_sum.frw < st.c.min_frw
                        || cand_sum.mf < st.c.min_mf
                        || cand_sum.fr < st.c.min_fr
                        || cand_sum.lr < st.c.min_lr
                        || cand_sum.cr < st.c.min_cr
                        || cand_sum.pr < st.c.min_pr
                    {
                        continue;
                    }
                    let mut cand_score = score_eval_summary(&cand_sum, &st.c);
                    cand_score.locality = mut_ctx.best_score.locality;
                    if cand_score > *mut_ctx.best_score {
                        *mut_ctx.best_charms = cand_charms;
                        *mut_ctx.best_sum = cand_sum;
                        *mut_ctx.best_score = cand_score;
                    }
                }
                return;
            }

            let sp = dps.suf_pos[g_idx];
            // Note: negative res from remaining dps_groups stays <= 0.

            let rem_str = ub_rem_at(g_idx, sp.str_bonus, &dps.order_str, dps_rem_slots);
            let rem_dex = ub_rem_at(g_idx, sp.dex_bonus, &dps.order_dex, dps_rem_slots);
            let rem_ar = eval_sorted_ub(&dps.order_ar, g_idx, dps_rem_slots);
            let rem_all_sk = ub_rem_at(g_idx, sp.all_skills, &dps.order_all_skills, dps_rem_slots);
            let rem_cls_sk =
                ub_rem_at(g_idx, sp.class_skills, &dps.order_class_skills, dps_rem_slots);
            let rem_act_sk = ub_rem_at(
                g_idx,
                sp.action_skills,
                &dps.order_action_skills,
                dps_rem_slots,
            );
            let rem_aura_sk =
                ub_rem_at(g_idx, sp.aura_skills, &dps.order_aura_skills, dps_rem_slots);
            let rem_phys = eval_sorted_ub(&dps.order_phys, g_idx, dps_rem_slots);
            let rem_fire = eval_sorted_ub(&dps.order_fire, g_idx, dps_rem_slots);
            let rem_elem = eval_sorted_ub(&dps.order_elem, g_idx, dps_rem_slots);
            let rem_psn = eval_sorted_ub(&dps.order_psn, g_idx, dps_rem_slots);
            let ub_dps = if cur.all_skills + rem_all_sk == 0
                && cur.class_skills + rem_cls_sk == 0
                && cur.action_skills + rem_act_sk == 0
                && cur.aura_skills + rem_aura_sk == 0
            {
                st.base_fast
                    .with_non_skill_deltas(
                        cur.str_bonus + rem_str,
                        cur.dex_bonus + rem_dex,
                        cur.ar + rem_ar,
                        cur.flat_phys_2x + rem_phys,
                        cur.flat_fire_2x + rem_fire,
                        cur.flat_elem_2x + rem_elem,
                        cur.psn_dps_2x + rem_psn,
                    )
                    .eval_eff_dps()
            } else {
                let ub_dps_stats = StatTotals {
                    all_skills: cur.all_skills + rem_all_sk,
                    class_skills: cur.class_skills + rem_cls_sk,
                    action_skills: cur.action_skills + rem_act_sk,
                    aura_skills: cur.aura_skills + rem_aura_sk,
                    str_bonus: cur.str_bonus + rem_str,
                    dex_bonus: cur.dex_bonus + rem_dex,
                    ar: cur.ar + rem_ar,
                    flat_phys_2x: cur.flat_phys_2x + rem_phys,
                    flat_fire_2x: cur.flat_fire_2x + rem_fire,
                    flat_elem_2x: cur.flat_elem_2x + rem_elem,
                    psn_dps_2x: cur.psn_dps_2x + rem_psn,
                    ..Default::default()
                }
                .add_to_stats(leaf, st.c.class);
                st.c.offense.compute_eff_dps(st.hw, ub_dps_stats, &st.c)
            };
            let best_top2 = (mut_ctx.best_score.primary, mut_ctx.best_score.secondary);
            let Some(req_bkt) = required_dps_bucket(
                st.c.mode,
                ub_res_base,
                st.cbf_val,
                st.cutoff,
                best_top2,
            ) else {
                return;
            };
            if req_bkt > 0 && ub_dps < OffenseProfile::dps_bucket_safe_min_dps(req_bkt) {
                return;
            }
            let ub_bucket = OffenseProfile::dps_bucket(ub_dps);
            let ub_top3 = match st.c.mode {
                SearchMode::Leveling => (ub_bucket, ub_res_base, st.cbf_val),
                SearchMode::LevelingRes => (ub_res_base, ub_bucket, st.cbf_val),
                _ => return,
            };
            if st.cutoff.is_some_and(|cut| ub_top3 < cut) || (ub_top3.0, ub_top3.1) < best_top2 {
                return;
            }

            match &dps.groups[g_idx] {
                CharmGroup::Unique { options, .. } => {
                    for &opt_idx in options {
                        let ch = st.pool[opt_idx];
                        if ch.size > dps_rem_slots {
                            continue;
                        }
                        mut_ctx.cur_indices.push(opt_idx);
                        dfs_dps(
                            st,
                            mut_ctx,
                            g_idx + 1,
                            rem_slots - ch.size,
                            cur.add_scaled(StatTotals::from_charm(ch), 1),
                        );
                        mut_ctx.cur_indices.pop();
                    }
                    dfs_dps(st, mut_ctx, g_idx + 1, rem_slots, cur);
                }
                CharmGroup::Multi {
                    members,
                    size,
                    stats,
                } => {
                    let size = *size;
                    let stats = *stats;
                    let ch_skills_zero = stats.all_skills == 0
                        && stats.class_skills == 0
                        && stats.action_skills == 0
                        && stats.aura_skills == 0;
                    let skip_multi = ch_skills_zero
                        && stats.ar == 0
                        && stats.flat_phys_2x == 0
                        && stats.flat_fire_2x == 0
                        && stats.flat_elem_2x == 0
                        && stats.psn_dps_2x == 0
                        && !dps.group_has_util[g_idx]
                        && (stats.str_bonus <= 0
                            || (st.base_fast.str_pct == 0 && leaf.str_bonus + cur.str_bonus >= st.reqs.0))
                        && stats.dex_bonus <= 0;
                    if !skip_multi {
                        let max_k = ((dps_rem_slots / size).min(members.len() as i32)).max(0);
                        for k in (1..=max_k).rev() {
                            let ku = k as usize;
                            mut_ctx.cur_indices.extend_from_slice(&members[..ku]);
                            dfs_dps(
                                st,
                                mut_ctx,
                                g_idx + 1,
                                rem_slots - k * size,
                                cur.add_scaled(stats, k),
                            );
                            let new_len = mut_ctx.cur_indices.len() - ku;
                            mut_ctx.cur_indices.truncate(new_len);
                        }
                    }
                    dfs_dps(st, mut_ctx, g_idx + 1, rem_slots, cur);
                }
            }
        }

        let st = DpsStatic {
            pool: &self.pool,
            c: self.c,
            max_slots: self.max_slots,
            gear,
            all_sk_non_wep,
            hw,
            has_shield,
            leaf,
            reqs,
            cutoff,
            cbf_val,
            dps,
            base_caps,
            base_fast,
        };
        let mut mut_ctx = DpsMut {
            non_dps_solver,
            cur_indices: Vec::new(),
            pure_buf: Vec::with_capacity((self.max_slots.max(0) as usize) + 1),
            cth_cache: Vec::new(),
            best_charms,
            best_sum,
            best_score,
        };
        dfs_dps(
            &st,
            &mut mut_ctx,
            0,
            self.max_slots.max(0),
            StatTotals::default(),
        );
    }
}
