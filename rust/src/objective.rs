use crate::dps::{HandWeapon, OffenseProfile};
use crate::eval::{base_res_caps, res_caps, EvalSummary};
use crate::stats::Stats;
use crate::types::{BuildConstraints, ResolvedConstraints, SearchMode};

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

    #[inline]
    pub(crate) fn top3(self) -> (i32, i32, i32) {
        (self.primary, self.secondary, self.tertiary)
    }

    #[inline]
    fn ub_prefix1(primary: i32) -> Self {
        Self {
            primary,
            secondary: i32::MAX,
            tertiary: i32::MAX,
            tiebreakers: [i32::MAX; 7],
            locality: i32::MAX,
        }
    }

    #[inline]
    fn ub_prefix2(primary: i32, secondary: i32) -> Self {
        Self {
            primary,
            secondary,
            tertiary: i32::MAX,
            tiebreakers: [i32::MAX; 7],
            locality: i32::MAX,
        }
    }

    #[inline]
    fn ub_prefix3(primary: i32, secondary: i32, tertiary: i32) -> Self {
        Self {
            primary,
            secondary,
            tertiary,
            tiebreakers: [i32::MAX; 7],
            locality: i32::MAX,
        }
    }
}

fn capped_res_sum(fr: i32, lr: i32, cr: i32, pr: i32, caps: (i32, i32, i32, i32)) -> i32 {
    fr.min(caps.0) + lr.min(caps.1) + cr.min(caps.2) + pr.min(caps.3)
}

fn res_base_sum(fr: i32, lr: i32, cr: i32, pr: i32, c: &BuildConstraints) -> i32 {
    let bc = base_res_caps(c);
    let pr_term = if c.ignore_pr { 0 } else { pr.min(bc.3) };
    fr.min(bc.0) + lr.min(bc.1) + cr.min(bc.2) + pr_term
}

fn res_base_ub(s: Stats, caps: (i32, i32, i32, i32), c: &BuildConstraints) -> i32 {
    let bc = base_res_caps(c);
    let pr_term = if c.ignore_pr {
        0
    } else {
        s.pr.min(caps.3.min(bc.3))
    };
    s.fr.min(caps.0.min(bc.0))
        + s.lr.min(caps.1.min(bc.1))
        + s.cr.min(caps.2.min(bc.2))
        + pr_term
}

impl SearchMode {
    pub(crate) fn score(self, sum: &EvalSummary, c: &ResolvedConstraints<'_>) -> BuildScore {
        let offense = c.offense;
        let has_aura = c.skills.has_aura();
        let eff_primary = if offense.is_melee_dps()
            && (has_aura || sum.action_skill_bonus != 0 || sum.aura_skill_bonus != 0)
        {
            let bonus = if has_aura {
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
        match self {
            SearchMode::Mf => BuildScore {
                primary: sum.mf,
                secondary: eff_primary,
                tertiary: eff_fcr_bp,
                tiebreakers: [
                    sum.fhr_bp,
                    sum.pr,
                    sum.life_bo,
                    sum.belt_slots,
                    sum.gear_defense,
                    0,
                    0,
                ],
                locality: 0,
            },
            SearchMode::Power => BuildScore {
                primary: if offense.uses_caster_dps(c) {
                    sum.dps.floor() as i32
                } else {
                    eff_primary
                },
                secondary: sum.skills,
                tertiary: if c.ignore_pr {
                    0
                } else {
                    i32::from(sum.pr >= base_res_caps(c).3)
                },
                tiebreakers: [
                    sum.pr,
                    sum.life_bo,
                    sum.mana_bo,
                    sum.belt_slots,
                    sum.gear_defense,
                    0,
                    0,
                ],
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

    /// Sound upper bound on `self.score(..)` for any build reachable from `ub_ch`.
    /// Unbounded trailing slots are set to `i32::MAX` so `ub_score < cutoff` is exact.
    pub(crate) fn score_upper_bound(
        self,
        ub_ch: Stats,
        hand: Option<HandWeapon>,
        max_hand_ub_dps: i32,
        caps: (i32, i32, i32, i32),
        c: &ResolvedConstraints<'_>,
    ) -> BuildScore {
        let offense = c.offense;
        let has_aura = c.skills.has_aura();
        let level_ub = || {
            let eff_primary_ub = ub_ch.primary_power_skills_for(offense, has_aura);
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
            let res_base = res_base_ub(ub_ch, caps, c);
            let cbf_ub = i32::from(ub_ch.cbf > 0);
            (off_ub, res_base, cbf_ub)
        };
        match self {
            SearchMode::Power => {
                let power_ub = if offense.uses_caster_dps(c) {
                    offense.compute_caster_dps(ub_ch, c).floor() as i32
                } else {
                    ub_ch.primary_power_skills_for(offense, has_aura)
                };
                BuildScore::ub_prefix1(power_ub)
            }
            SearchMode::Mf => BuildScore::ub_prefix1(ub_ch.mf),
            SearchMode::MaxRes => BuildScore::ub_prefix2(
                capped_res_sum(ub_ch.fr, ub_ch.lr, ub_ch.cr, ub_ch.pr, caps),
                ub_ch.primary_power_skills_for(offense, has_aura),
            ),
            SearchMode::Leveling => {
                let (off_ub, res_base, cbf_ub) = level_ub();
                BuildScore::ub_prefix3(off_ub, res_base, cbf_ub)
            }
            SearchMode::LevelingRes => {
                let (off_ub, res_base, cbf_ub) = level_ub();
                BuildScore::ub_prefix3(res_base, off_ub, cbf_ub)
            }
        }
    }

    /// Lower bound on the charm solver's primary-axis contribution needed to reach `cut_primary`.
    pub(crate) fn min_charm_main_needed(
        self,
        leaf: Stats,
        ch: Stats,
        cut_primary: i32,
        c: &ResolvedConstraints<'_>,
    ) -> i32 {
        let offense = c.offense;
        match self {
            SearchMode::LevelingRes => {
                let caps_l = res_caps(leaf, c);
                let cur_sum = res_base_ub(leaf, caps_l, c);
                (cut_primary - cur_sum).max(0)
            }
            SearchMode::MaxRes => {
                let caps_l = res_caps(leaf, c);
                let cur_sum = capped_res_sum(leaf.fr, leaf.lr, leaf.cr, leaf.pr, caps_l);
                (cut_primary - cur_sum).max(0)
            }
            SearchMode::Mf => (cut_primary - leaf.mf).max(0),
            SearchMode::Power => {
                if offense.uses_caster_dps(c) {
                    let max_k = (ch.all_skills + ch.action_skill_bonus + ch.aura_skill_bonus).max(0);
                    (0..=max_k)
                        .find(|&k| {
                            let s = Stats {
                                all_skills: leaf.all_skills + k,
                                ..leaf
                            };
                            offense.compute_caster_dps(s, c).floor() as i32 >= cut_primary
                        })
                        .unwrap_or(max_k + 1)
                } else {
                    let cur_sk = leaf.primary_power_skills_for(offense, c.skills.has_aura());
                    (cut_primary - cur_sk).max(0)
                }
            }
            SearchMode::Leveling => 0,
        }
    }
}

pub(crate) fn score_eval_summary(sum: &EvalSummary, c: &ResolvedConstraints<'_>) -> BuildScore {
    c.mode.score(sum, c)
}

#[cfg(test)]
#[path = "objective_tests.rs"]
mod tests;
