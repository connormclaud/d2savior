use crate::dps::{HandWeapon, OffenseProfile};
use crate::types::{ItemSpec, ResolvedConstraints, SearchMode, TargetType};

macro_rules! with_stat_fields {
    ($mac:ident) => {
        $mac!(
            all_skills => add,
            sorc_skills => add,
            pal_skills => add,
            blizz_skills => add,
            cm_skills => add,
            primary_skill => add,
            action_skill_bonus => add,
            aura_skill_bonus => add,
            off_ed => add,
            flat_phys_2x => add,
            flat_fire_2x => add,
            flat_elem_2x => add,
            cold_dmg_pct => add,
            ds => add,
            cs_oskill => add,
            ow => add,
            ed_demon => add,
            ed_undead => add,
            psn_dps_2x => add,
            pierce => add,
            ctc_static_pct => add,
            ctc_venom_dps_2x => max,
            ctc_decrep_pct => add,
            ctc_lifetap_pct => add,
            ctc_orb_dmg_2x => add,
            ar => add,
            ar_pct => add,
            itd => add,
            target_def_pct => add,
            fcr => add,
            fhr => add,
            frw => add,
            ias => add,
            cb => add,
            cbf => add,
            pdr_pct => add,
            life_leech => add,
            fr => add,
            lr => add,
            cr => add,
            pr => add,
            max_fr => add,
            max_lr => add,
            max_cr => add,
            max_pr => add,
            mf => add,
            life => add,
            mana => add,
            life_per_lvl => add,
            mana_per_lvl => add,
            vit => add,
            ene => add,
            pct_life => add,
            pct_mana => add,
            mdr => add,
            dr_flat => add,
            fire_abs_pct => add,
            str_bonus => add,
            dex_bonus => add,
            defense => add,
            belt_slots => add,
            block_pct => add,
            fbr => add,
            def_skill => add,
        );
    };
}

pub(crate) use with_stat_fields;

macro_rules! stat_combine {
    (add, $a:expr, $b:expr) => {
        $a + $b
    };
    (max, $a:expr, $b:expr) => {
        $a.max($b)
    };
}

macro_rules! and_all {
    ($first:expr $(, $rest:expr)* $(,)?) => {
        $first $(&& $rest)*
    };
}

macro_rules! define_stats {
    ($( $field:ident => $combine:ident ),* $(,)?) => {
        #[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
        pub(crate) struct Stats {
            $( pub(crate) $field: i32, )*
        }

        impl Stats {
            pub(crate) fn add(self, o: Stats) -> Stats {
                Stats {
                    $( $field: stat_combine!($combine, self.$field, o.$field), )*
                }
            }

            pub(crate) fn max_each(self, o: Stats) -> Stats {
                Stats {
                    $( $field: self.$field.max(o.$field), )*
                }
            }

            pub(crate) fn dominates(self, o: Stats) -> bool {
                and_all!( $( self.$field >= o.$field ),* )
            }
        }
    };
}

with_stat_fields!(define_stats);

impl Stats {
    pub(crate) fn total_skills(self) -> i32 {
        self.all_skills + self.sorc_skills + self.pal_skills
    }

    pub(crate) fn primary_power_skills(self) -> i32 {
        self.total_skills() + self.blizz_skills + self.primary_skill
    }

    pub(crate) fn primary_power_skills_for(self, offense: OffenseProfile, has_aura: bool) -> i32 {
        if offense.is_melee_dps()
            && (has_aura || self.action_skill_bonus != 0 || self.aura_skill_bonus != 0)
        {
            let bonus = if has_aura {
                self.aura_skill_bonus
            } else {
                self.action_skill_bonus.max(self.aura_skill_bonus)
            };
            self.total_skills() + self.blizz_skills + self.primary_skill + bonus
        } else {
            self.primary_power_skills()
        }
    }

    pub(crate) fn res_sum(self) -> i32 {
        self.fr + self.lr + self.cr + self.pr
    }

    pub(crate) fn max_res_sum(self) -> i32 {
        self.max_fr + self.max_lr + self.max_cr + self.max_pr
    }

    /// Zero fields unused by active constraints or `BuildScore` for exact dominance pruning.
    pub(crate) fn for_mode(mut self, c: &ResolvedConstraints<'_>) -> Self {
        let mode = c.mode;
        let offense = c.offense;
        let is_leveling = matches!(mode, SearchMode::Leveling | SearchMode::LevelingRes);
        let caster_dps = offense.uses_caster_dps(c);
        if !(c.min_fcr > 0
            || (offense.uses_fcr() && (mode != SearchMode::Power || caster_dps)))
        {
            self.fcr = 0;
        }
        if mode == SearchMode::Power && c.min_fhr <= 0 {
            self.fhr = 0;
        }
        if !(mode == SearchMode::Power && caster_dps) {
            self.cold_dmg_pct = 0;
        }
        if !(mode == SearchMode::Power && offense == OffenseProfile::Caster) {
            self.cm_skills = 0;
        }
        if !(offense.is_melee_dps()
            || (mode == SearchMode::Power
                && caster_dps
                && c.skills.caster().is_some_and(|m| !m.filler_dmg.is_empty())))
        {
            self.action_skill_bonus = 0;
        }
        if !offense.is_melee_dps() {
            self.aura_skill_bonus = 0;
        }
        if !(is_leveling && offense.uses_dps_tables(c)) {
            self.off_ed = 0;
            self.flat_phys_2x = 0;
            self.flat_fire_2x = 0;
            self.flat_elem_2x = 0;
            self.ds = 0;
            self.cs_oskill = 0;
            self.ow = 0;
            self.ed_demon = 0;
            self.ed_undead = 0;
            self.psn_dps_2x = 0;
            self.pierce = 0;
            self.ctc_static_pct = 0;
            self.ctc_venom_dps_2x = 0;
            self.ctc_decrep_pct = 0;
            self.ctc_orb_dmg_2x = 0;
            self.ar = 0;
            self.ar_pct = 0;
            self.itd = 0;
            self.target_def_pct = 0;
        } else {
            if !c.target_type.allows_itd() {
                self.itd = 0;
            }
            if c.target.target_hp <= 0 {
                self.ctc_static_pct = 0;
            }
            if matches!(c.target_type, TargetType::Boss) {
                self.ed_undead = 0;
            }
            if c.target.targets <= 1 {
                self.pierce = 0;
            }
            if offense == OffenseProfile::Smite {
                self.flat_fire_2x = 0;
                self.flat_elem_2x = 0;
                self.ds = 0;
                self.cs_oskill = 0;
                self.ed_demon = 0;
                self.ed_undead = 0;
                self.psn_dps_2x = 0;
                self.pierce = 0;
                self.ctc_venom_dps_2x = 0;
                self.ar = 0;
                self.ar_pct = 0;
                self.itd = 0;
                self.target_def_pct = 0;
            }
        }
        if !(mode == SearchMode::Mf || c.min_mf > 0 || !c.allow_mf) {
            self.mf = 0;
        }
        if mode != SearchMode::Power {
            self.mana = 0;
            self.mana_per_lvl = 0;
            self.ene = 0;
            self.pct_mana = 0;
        }
        if !(is_leveling || c.min_frw > 0) {
            self.frw = 0;
        }
        if !((is_leveling && offense != OffenseProfile::Caster) || c.min_ias > 0) {
            self.ias = 0;
        }
        if !((is_leveling
            && (offense == OffenseProfile::Smite
                || (offense.uses_dps_tables(c) && c.target.target_hp > 0)))
            || c.min_cb > 0)
        {
            self.cb = 0;
        }
        if !(is_leveling || c.require_cbf) {
            self.cbf = 0;
        }
        if !((mode == SearchMode::Leveling && offense == OffenseProfile::Smite) || c.min_pdr > 0) {
            self.pdr_pct = 0;
        }
        if c.min_ll <= 0 {
            self.life_leech = 0;
            self.ctc_lifetap_pct = 0;
        }
        self.mdr = 0;
        self.dr_flat = 0;
        self.fire_abs_pct = 0;
        self.defense = 0;
        self.block_pct = 0;
        self.fbr = 0;
        if !(is_leveling
            && offense == OffenseProfile::Smite
            && c.skills.melee().is_some_and(|m| m.holy_shield_base_lvl > 0))
        {
            self.def_skill = 0;
        }
        self
    }
}

pub(crate) type SetBonusSig = Vec<(i32, Stats)>;

pub(crate) fn equipped_hand_weapon(items: &[&ItemSpec]) -> HandWeapon {
    for &it in items {
        if matches!(it.slot.as_str(), "weapon" | "weapon2h") && it.name != "(empty)" {
            return it.hand_weapon();
        }
    }
    HandWeapon::empty()
}

pub(crate) fn eff_req(req: i32, self_bonus: i32) -> i32 {
    if req > 0 {
        req + self_bonus
    } else {
        0
    }
}

pub(crate) fn compute_effective_gear_stats_and_reqs(items: &[&ItemSpec]) -> (Stats, i32, (i32, i32)) {
    if items.iter().all(|it| it.set_group == 0) {
        let mut gear = Stats::default();
        let mut all_sk_non_wep = 0;
        let mut req_str = 0;
        let mut req_dex = 0;
        for &it in items {
            gear = gear.add(it.stats());
            if !it.is_weapon_or_shield() {
                all_sk_non_wep += it.all_skills;
            }
            req_str = req_str.max(eff_req(it.req_str, it.str_bonus));
            req_dex = req_dex.max(eff_req(it.req_dex, it.dex_bonus));
        }
        return (gear, all_sk_non_wep, (req_str, req_dex));
    }

    let mut counts: Vec<(i32, i32)> = Vec::new();
    let mut non_wep_counts: Vec<(i32, i32)> = Vec::new();
    let mut seen: Vec<(i32, i32)> = Vec::with_capacity(items.len());
    let mut non_wep_seen: Vec<(i32, i32)> = Vec::with_capacity(items.len());
    for (idx, &it) in items.iter().enumerate() {
        if it.set_group == 0 {
            continue;
        }
        let eid = if it.set_item_id != 0 {
            it.set_item_id
        } else {
            -(idx as i32 + 1)
        };
        if !seen.contains(&(it.set_group, eid)) {
            seen.push((it.set_group, eid));
            if let Some(entry) = counts.iter_mut().find(|(g, _)| *g == it.set_group) {
                entry.1 += 1;
            } else {
                counts.push((it.set_group, 1));
            }
        }
        if !it.is_weapon_or_shield() && !non_wep_seen.contains(&(it.set_group, eid)) {
            non_wep_seen.push((it.set_group, eid));
            if let Some(entry) = non_wep_counts.iter_mut().find(|(g, _)| *g == it.set_group) {
                entry.1 += 1;
            } else {
                non_wep_counts.push((it.set_group, 1));
            }
        }
    }

    let mut gear = Stats::default();
    let mut all_sk_non_wep = 0;
    let mut req_str = 0;
    let mut req_dex = 0;
    for &it in items {
        let bonus = if it.set_group != 0 && !it.set_bonuses.is_empty() {
            let cnt = counts
                .iter()
                .find(|(g, _)| *g == it.set_group)
                .map_or(0, |(_, c)| *c);
            it.active_set_bonus_stats(cnt)
        } else {
            Stats::default()
        };
        let eff = it.stats().add(bonus);
        gear = gear.add(eff);
        if !it.is_weapon_or_shield() {
            all_sk_non_wep += eff.all_skills;
        }
        req_str = req_str.max(eff_req(it.req_str, it.str_bonus + bonus.str_bonus));
        req_dex = req_dex.max(eff_req(it.req_dex, it.dex_bonus + bonus.dex_bonus));
    }
    for (group, cnt) in &counts {
        if *cnt < 2 {
            continue;
        }
        if let Some(&rep) = items
            .iter()
            .find(|it| it.set_group == *group && !it.global_set_bonuses.is_empty())
        {
            gear = gear.add(rep.active_global_set_bonus_stats(*cnt));
            let nw_cnt = non_wep_counts
                .iter()
                .find(|(g, _)| g == group)
                .map_or(0, |(_, c)| *c);
            if nw_cnt >= 2 {
                all_sk_non_wep += rep.active_global_set_bonus_stats(nw_cnt).all_skills;
            }
        }
    }
    (gear, all_sk_non_wep, (req_str, req_dex))
}

pub(crate) fn compute_effective_gear_stats(items: &[&ItemSpec]) -> (Stats, i32) {
    let (gear, all_sk_non_wep, _) = compute_effective_gear_stats_and_reqs(items);
    (gear, all_sk_non_wep)
}
