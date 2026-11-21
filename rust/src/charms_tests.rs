use super::*;
use crate::types::WeaponClass;

#[test]
fn test_charm_stat_ub_respects_max_slots_and_rounds_up_partial() {
    let charms = [
        CharmSpec {
            name: "Ruby SC".to_string(),
            size: 1,
            fr: 11,
            skills: 1,
            ..Default::default()
        },
        CharmSpec {
            name: "Ruby GC".to_string(),
            size: 3,
            fr: 28,
            skills: 1,
            ..Default::default()
        },
        CharmSpec {
            name: "Ruby LC".to_string(),
            size: 2,
            fr: 15,
            ..Default::default()
        },
        CharmSpec {
            name: "Sunder".to_string(),
            size: 3,
            fr: -70,
            ..Default::default()
        },
    ];
    let refs: Vec<&CharmSpec> = charms.iter().collect();

    assert_eq!(charm_stat_ub(&refs, 0, |c| c.fr), 0);
    // 1 slot: takes whole SC (density 11/1 = 11).
    assert_eq!(charm_stat_ub(&refs, 1, |c| c.fr), 11);
    // 2 slots: takes SC (11, 1 slot), remaining 1 slot on GC (28/3 = 9.33 -> ceil = 10) => 21.
    assert_eq!(charm_stat_ub(&refs, 2, |c| c.fr), 21);
    // 3 slots: takes SC (11, 1 slot), remaining 2 slots on GC (56/3 = 18.67 -> ceil = 19) => 30.
    assert_eq!(charm_stat_ub(&refs, 3, |c| c.fr), 30);
    // Skills: SC (1/1=1) + GC partial 1/3 with max_slots=2 => 1 + ceil(1*1/3) = 2.
    assert_eq!(charm_stat_ub(&refs, 2, |c| c.skills), 2);
    // Pool total fr (positive only) = 54, strictly larger than slot-bounded UB 30.
    assert_eq!(charm_stat_ub(&refs, 10, |c| c.fr), 54);
}

#[test]
fn test_greedy_charms_falls_back_to_res_first_on_tight_slots() {
    let charms = [
        CharmSpec {
            name: "FHR SC".to_string(),
            size: 1,
            fhr: 5,
            ..Default::default()
        },
        CharmSpec {
            name: "Hybrid LC".to_string(),
            size: 2,
            fhr: 5,
            fr: 15,
            ..Default::default()
        },
        CharmSpec {
            name: "Ruby SC".to_string(),
            size: 1,
            fr: 11,
            ..Default::default()
        },
    ];
    let pool: Vec<&CharmSpec> = charms.iter().collect();

    let c = BuildConstraints {
        base_hell_res: 0,
        min_fhr: 5,
        min_fr: 25,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 3,
        ..Default::default()
    };

    // FHR-first spends 1 slot on FHR SC and cannot reach 25 FR in the remaining 2 slots.
    assert!(greedy_charms_pass(&[], &pool, &c, (0, 0), SearchMode::Power, true).is_none());

    // Res-first picks Ruby SC + Hybrid LC, hitting both 26 FR and 5 FHR in 3 slots.
    let chosen = greedy_charms(&[], &pool, &c, (0, 0), SearchMode::Power)
        .expect("res-first fallback should satisfy tight FHR + FR constraints");
    let names: Vec<&str> = chosen.iter().map(|ch| ch.name.as_str()).collect();
    assert_eq!(names, vec!["Ruby SC", "Hybrid LC"]);
}

#[test]
fn test_charm_stat_ub_deduplicates_unique_id() {
    let torch = CharmSpec {
        name: "Hellfire Torch".to_string(),
        size: 2,
        skills: 3,
        unique_id: Some(400),
        ..Default::default()
    };
    let torches = [torch.clone(), torch.clone(), torch];
    let refs: Vec<&CharmSpec> = torches.iter().collect();

    assert_eq!(charm_stat_ub(&refs, 10, |c| c.skills), 3);
}

#[test]
fn test_greedy_charms_skips_negative_res_filler_breaking_target() {
    let charms = [
        CharmSpec {
            name: "Ruby SC".to_string(),
            size: 1,
            fr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Toxic Sunder".to_string(),
            size: 3,
            fr: -70,
            mf: 20,
            life: 40,
            skills: 1,
            ..Default::default()
        },
    ];
    let pool: Vec<&CharmSpec> = charms.iter().collect();

    // Base hell res = 70 + 11 from Ruby SC = 81 >= min_fr 75.
    // Picking Toxic Sunder (-70 FR) in MF/skill/life pass would drop FR to 11 < 75.
    let c = BuildConstraints {
        base_hell_res: 70,
        min_fhr: 0,
        min_fr: 75,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 10,
        ..Default::default()
    };
    let chosen = greedy_charms(&[], &pool, &c, (0, 0), SearchMode::Mf)
        .expect("negative-res filler should be skipped so FR target stays satisfied");
    assert!(!chosen.iter().any(|ch| ch.name == "Toxic Sunder"));
}

#[test]
fn test_shrink_charm_pool_respects_multiplicity_and_unique_ids() {
    let good_sc = CharmSpec {
        name: "Good SC".to_string(),
        size: 1,
        lr: 11,
        life: 20,
        ..Default::default()
    };
    let plain_sc = CharmSpec {
        name: "Plain SC".to_string(),
        size: 1,
        lr: 11,
        ..Default::default()
    };
    let torch_hi = CharmSpec {
        name: "Torch 20/20".to_string(),
        size: 2,
        skills: 3,
        fr: 20,
        lr: 20,
        cr: 20,
        pr: 20,
        unique_id: Some(400),
        ..Default::default()
    };
    let torch_lo = CharmSpec {
        name: "Torch 10/10".to_string(),
        size: 2,
        skills: 3,
        fr: 10,
        lr: 10,
        cr: 10,
        pr: 10,
        unique_id: Some(400),
        ..Default::default()
    };

    // With max_slots = 3, good_sc (1 copy) + 4 plain_sc copies -> 1 good_sc + 2 plain_sc kept (total 3).
    // torch_lo is strictly dominated by same-unique_id torch_hi and dropped.
    let raw = [
        &good_sc, &plain_sc, &plain_sc, &plain_sc, &plain_sc, &torch_hi, &torch_lo,
    ];
    let shrunk = shrink_charm_pool(&raw, 3);
    assert_eq!(shrunk.iter().filter(|c| c.name == "Good SC").count(), 1);
    assert_eq!(shrunk.iter().filter(|c| c.name == "Plain SC").count(), 2);
    assert_eq!(shrunk.iter().filter(|c| c.name == "Torch 20/20").count(), 1);
    assert_eq!(shrunk.iter().filter(|c| c.name == "Torch 10/10").count(), 0);
}

#[test]
fn test_charm_solver_recovers_when_greedy_misses_feasibility_or_main_score() {
    // Case 1 (feasibility): Greedy picks Str GC (9/3 = 3.0 str/slot > 2.0), using all 3 slots
    // and failing FHR + FR. Exact solver picks Str/FHR SC (1) + Str/Res LC (2) = 6 STR, 5 FHR, 15 FR.
    let charms_feas = [
        CharmSpec {
            name: "Str GC".to_string(),
            size: 3,
            str_bonus: 9,
            ..Default::default()
        },
        CharmSpec {
            name: "Str/FHR SC".to_string(),
            size: 1,
            str_bonus: 2,
            fhr: 5,
            ..Default::default()
        },
        CharmSpec {
            name: "Str/Res LC".to_string(),
            size: 2,
            str_bonus: 4,
            fr: 15,
            ..Default::default()
        },
    ];
    let pool_feas: Vec<&CharmSpec> = charms_feas.iter().collect();
    let c_feas = BuildConstraints {
        base_hell_res: 0,
        min_fhr: 5,
        min_fr: 15,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 3,
        ..Default::default()
    };
    let leaf = Stats::default();
    assert!(greedy_charms(&[], &pool_feas, &c_feas, (6, 0), SearchMode::Power).is_none());
    let mut solver_feas = CharmSolver::new(&pool_feas, &c_feas, SearchMode::Power);
    let exact = solver_feas
        .solve(&[], leaf, (6, 0))
        .expect("exact charm solver should find Str/FHR SC + Str/Res LC");
    let names: Vec<&str> = exact.iter().map(|ch| ch.name.as_str()).collect();
    assert!(names.contains(&"Str/FHR SC") && names.contains(&"Str/Res LC"));

    // Case 2 (main score): In 5 slots needing 5 FHR and 15 FR, greedy picks FHR SC (5/1=5.0)
    // + 2x FR SC (11/1=11.0) = 3 slots, leaving 2 slots (cannot fit size-3 Skill GC -> 0 skills).
    // Exact solver picks Hybrid LC (size 2, 5 FHR, 15 FR) + Skill GC (size 3, +1 skill) = 1 skill.
    let charms_sk = [
        CharmSpec {
            name: "FHR SC".to_string(),
            size: 1,
            fhr: 5,
            ..Default::default()
        },
        CharmSpec {
            name: "FR SC A".to_string(),
            size: 1,
            fr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "FR SC B".to_string(),
            size: 1,
            fr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Hybrid LC".to_string(),
            size: 2,
            fhr: 5,
            fr: 15,
            ..Default::default()
        },
        CharmSpec {
            name: "Skill GC".to_string(),
            size: 3,
            skills: 1,
            ..Default::default()
        },
    ];
    let pool_sk: Vec<&CharmSpec> = charms_sk.iter().collect();
    let c_skill = BuildConstraints {
        base_hell_res: 0,
        min_fhr: 5,
        min_fr: 15,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 5,
        ..Default::default()
    };
    let g_sk = greedy_charms(&[], &pool_sk, &c_skill, (0, 0), SearchMode::Power)
        .expect("greedy should still find a feasible 0-skill set");
    assert_eq!(g_sk.iter().map(|c| c.skills).sum::<i32>(), 0);

    let mut solver_skill = CharmSolver::new(&pool_sk, &c_skill, SearchMode::Power);
    let best_sk = solver_skill
        .solve(&[], leaf, (0, 0))
        .expect("exact should find Hybrid LC + Skill GC");
    assert_eq!(best_sk.iter().map(|c| c.skills).sum::<i32>(), 1);
}

#[test]
fn test_charm_solver_max_res_negative_res_overcap_and_cache_isolation() {
    let charms = [
        CharmSpec {
            name: "Cold Rupture STR".to_string(),
            size: 1,
            unique_id: Some(901),
            str_bonus: 10,
            cr: -40,
            ..Default::default()
        },
        CharmSpec {
            name: "FR SC".to_string(),
            size: 1,
            fr: 20,
            ..Default::default()
        },
        CharmSpec {
            name: "CR SC".to_string(),
            size: 1,
            cr: 25,
            ..Default::default()
        },
    ];
    let pool: Vec<&CharmSpec> = charms.iter().collect();
    let c = BuildConstraints {
        base_hell_res: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 2,
        ..Default::default()
    };

    let capped_sum = |leaf: Stats, chosen: &[&CharmSpec]| -> i32 {
        let mut r = [leaf.fr, leaf.lr, leaf.cr, leaf.pr];
        for ch in chosen {
            r[0] += ch.fr;
            r[1] += ch.lr;
            r[2] += ch.cr;
            r[3] += ch.pr;
        }
        r.into_iter().map(|v| v.min(75)).sum()
    };

    let mut solver = CharmSolver::new(&pool, &c, SearchMode::MaxRes);

    // At CR = 75 (0 overcap), Sunder + CR SC yields 55 + 75 + 60 + 75 = 265 > 260.
    let leaf_at_cap = Stats {
        fr: 55,
        lr: 75,
        cr: 75,
        pr: 75,
        ..Default::default()
    };
    let chosen_at_cap = solver
        .solve(&[], leaf_at_cap, (10, 0))
        .expect("should solve at cap");
    assert_eq!(capped_sum(leaf_at_cap, &chosen_at_cap), 265);

    // At CR = 100 (25 overcap), Sunder + FR SC yields 75 + 75 + 60 + 75 = 285 > 280.
    // Must neither mis-score the overcap nor collide in cache with CR = 75.
    let leaf_overcap = Stats {
        fr: 55,
        lr: 75,
        cr: 100,
        pr: 75,
        ..Default::default()
    };
    let chosen_overcap = solver
        .solve(&[], leaf_overcap, (10, 0))
        .expect("should solve with overcap");
    assert_eq!(capped_sum(leaf_overcap, &chosen_overcap), 285);
}

#[test]
fn test_charm_solver_max_res_multi_offsets_later_negative_res_charm() {
    let charms = [
        CharmSpec {
            name: "CR SC".to_string(),
            size: 1,
            cr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Cold Rupture STR".to_string(),
            size: 1,
            unique_id: Some(901),
            str_bonus: 10,
            cr: -70,
            ..Default::default()
        },
    ];
    let pool: Vec<&CharmSpec> = charms.iter().collect();
    let c = BuildConstraints {
        base_hell_res: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 2,
        ..Default::default()
    };
    let leaf = Stats {
        fr: 75,
        lr: 75,
        cr: 75,
        pr: 75,
        ..Default::default()
    };

    let mut solver = CharmSolver::new(&pool, &c, SearchMode::MaxRes);
    let chosen = solver
        .solve(&[], leaf, (10, 0))
        .expect("should solve with sunder + CR SC");
    let final_cr = leaf.cr + chosen.iter().map(|ch| ch.cr).sum::<i32>();
    assert_eq!(final_cr, 16);
}

#[test]
fn test_charm_solver_forces_best_cold_sunder_in_power_and_mf_only() {
    let charms = [
        CharmSpec {
            name: "Cold Rupture -85".to_string(),
            size: 3,
            cr: -85,
            unique_id: Some(401),
            cold_sunder: true,
            ..Default::default()
        },
        CharmSpec {
            name: "Cold Rupture -72".to_string(),
            size: 3,
            cr: -72,
            unique_id: Some(401),
            cold_sunder: true,
            ..Default::default()
        },
        CharmSpec {
            name: "Sapphire SC".to_string(),
            size: 1,
            cr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Skill GC".to_string(),
            size: 3,
            skills: 1,
            ..Default::default()
        },
        CharmSpec {
            name: "MF SC".to_string(),
            size: 1,
            mf: 7,
            ..Default::default()
        },
    ];
    let pool: Vec<&CharmSpec> = charms.iter().collect();
    let leaf = Stats {
        fr: 75,
        lr: 75,
        cr: 140,
        pr: 75,
        ..Default::default()
    };

    // Power mode: picks -72 Cold Rupture (3 slots) + Skill GC (3 slots) in 6 slots -> cr = 68 < 75 fails,
    // while with min_cr = 60 it picks -72 Cold Rupture + Sapphire SC (cr = 79) or Skill GC (cr = 68).
    let c_pow_strict = BuildConstraints {
        base_hell_res: 0,
        min_fhr: 0,
        min_fr: 75,
        min_lr: 75,
        min_cr: 75,
        min_pr: 75,
        max_charm_slots: 6,
        ..Default::default()
    };
    let mut solver_strict = CharmSolver::new(&pool, &c_pow_strict, SearchMode::Power);
    let chosen_strict = solver_strict
        .solve(&[], leaf, (0, 0))
        .expect("should pick Cold Rupture -72 + Sapphire SC to hit 75 CR");
    assert!(chosen_strict.iter().any(|ch| ch.name == "Cold Rupture -72"));
    assert!(!chosen_strict.iter().any(|ch| ch.name == "Cold Rupture -85"));
    assert!(chosen_strict.iter().any(|ch| ch.name == "Sapphire SC"));

    // Mf mode: still forces Cold Rupture -72 and uses remaining 3 slots for MF SCs (up to cap).
    let mut solver_mf = CharmSolver::new(&pool, &c_pow_strict, SearchMode::Mf);
    let chosen_mf = solver_mf
        .solve(&[], leaf, (0, 0))
        .expect("MF should also force Cold Rupture -72 and Sapphire SC");
    assert!(chosen_mf.iter().any(|ch| ch.name == "Cold Rupture -72"));
    assert!(chosen_mf.iter().any(|ch| ch.name == "Sapphire SC"));

    // MaxRes mode: Cold Rupture is optional, so it is skipped and CR stays at 75.
    let mut solver_max = CharmSolver::new(&pool, &c_pow_strict, SearchMode::MaxRes);
    let chosen_max = solver_max
        .solve(&[], leaf, (0, 0))
        .expect("MaxRes should solve without Cold Rupture");
    assert!(!chosen_max.iter().any(|ch| ch.cold_sunder));
}

#[test]
fn test_leveling_res_caps_at_75_and_paladin_never_forces_sunder() {
    let charms = [
        CharmSpec {
            name: "Cold Rupture".to_string(),
            size: 3,
            cr: -70,
            unique_id: Some(401),
            cold_sunder: true,
            skills: 1,
            ..Default::default()
        },
        CharmSpec {
            name: "Ruby SC".to_string(),
            size: 1,
            fr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Amber SC".to_string(),
            size: 1,
            lr: 11,
            ..Default::default()
        },
    ];
    let pool: Vec<&CharmSpec> = charms.iter().collect();

    // Even with max_fr=10 (cap 85), LevelingRes optimizes only up to 75, so at FR=75 and LR=65
    // it prefers Amber SC (+10 effective LR up to 75) over Ruby SC (+10 over 75).
    let c_lvl_res = BuildConstraints {
        char_class: 3,
        base_hell_res: 0,
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 1,
        ..Default::default()
    };
    let leaf = Stats {
        fr: 75,
        lr: 65,
        cr: 75,
        pr: 75,
        max_fr: 10,
        ..Default::default()
    };
    let mut solver_res = CharmSolver::new(&pool, &c_lvl_res, SearchMode::LevelingRes);
    assert!(!solver_res.has_cold_sunder());
    let chosen_res = solver_res
        .solve(&[], leaf, (0, 0))
        .expect("LevelingRes should pick Amber SC");
    assert_eq!(chosen_res.len(), 1);
    assert_eq!(chosen_res[0].name, "Amber SC");

    // In Leveling mode, Paladin does NOT force Cold Sunder either.
    let c_pal_lvl = BuildConstraints {
        max_charm_slots: 3,
        ..c_lvl_res
    };
    let solver_lvl = CharmSolver::new(&pool, &c_pal_lvl, SearchMode::Leveling);
    assert!(!solver_lvl.has_cold_sunder());
}

#[test]
fn test_leveling_charm_cache_does_not_collide_across_res_deficits_and_prioritizes_res_base() {
    // Regression test:
    // 1. Two gear loadouts in Leveling mode with `min_fr/lr/cr/pr == 0` and identical
    //    `(need_str, need_dex, need_fhr)` but different resistance deficits below 75 must not
    //    collide in `CharmSolver.cache`.
    // 2. After picking skill charms, Leveling mode must prioritize uncapped resistances up to 75
    //    (`res_base`, `BuildScore.secondary`) ahead of life filler charms (`tiebreakers[0]`).
    let charms = [
        CharmSpec {
            name: "Ruby SC".to_string(),
            size: 1,
            fr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Amber SC".to_string(),
            size: 1,
            lr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Vita SC".to_string(),
            size: 1,
            life: 20,
            ..Default::default()
        },
    ];
    let pool: Vec<&CharmSpec> = charms.iter().collect();
    let c = BuildConstraints {
        char_class: 3,
        base_hell_res: 0,
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 1,
        ..Default::default()
    };
    let mut solver = CharmSolver::new(&pool, &c, SearchMode::Leveling);

    // Loadout A: needs Fire Res (FR=64, LR=75, CR=75, PR=75) -> must pick Ruby SC (+11 FR -> 75),
    // not Vita SC (+20 Life).
    let item_need_fr = ItemSpec {
        fr: 64,
        lr: 75,
        cr: 75,
        pr: 75,
        ..ItemSpec::empty("armor")
    };
    let leaf_fr = item_need_fr.stats();
    let sel_fr = solver
        .solve(&[&item_need_fr], leaf_fr, (0, 0))
        .expect("should solve loadout A");
    assert_eq!(sel_fr.len(), 1);
    assert_eq!(sel_fr[0].name, "Ruby SC");

    // Loadout B: evaluated on the SAME CharmSolver instance, needs Lightning Res
    // (FR=75, LR=64, CR=75, PR=75) -> must NOT reuse cached Ruby SC from Loadout A!
    let item_need_lr = ItemSpec {
        fr: 75,
        lr: 64,
        cr: 75,
        pr: 75,
        ..ItemSpec::empty("armor")
    };
    let leaf_lr = item_need_lr.stats();
    let sel_lr = solver
        .solve(&[&item_need_lr], leaf_lr, (0, 0))
        .expect("should solve loadout B");
    assert_eq!(sel_lr.len(), 1);
    assert_eq!(sel_lr[0].name, "Amber SC");

    // Loadout C: already capped at 75/75/75/75 -> picks Vita SC (+20 Life).
    let item_capped = ItemSpec {
        fr: 75,
        lr: 75,
        cr: 75,
        pr: 75,
        ..ItemSpec::empty("armor")
    };
    let leaf_capped = item_capped.stats();
    let sel_capped = solver
        .solve(&[&item_capped], leaf_capped, (0, 0))
        .expect("should solve loadout C");
    assert_eq!(sel_capped.len(), 1);
    assert_eq!(sel_capped[0].name, "Vita SC");
}

#[test]
fn test_sunder_forwards_min_main_needed_and_non_res_cache_tailors_filler() {
    // 1. Single & multi-sunder paths respect `min_main_needed` and preserve ties cleanly.
    let single_pool_charms = [
        CharmSpec {
            name: "Cold Rupture MF".to_string(),
            size: 3,
            cr: -70,
            mf: 5,
            unique_id: Some(401),
            cold_sunder: true,
            ..Default::default()
        },
        CharmSpec {
            name: "MF SC".to_string(),
            size: 1,
            mf: 7,
            ..Default::default()
        },
    ];
    let single_pool: Vec<&CharmSpec> = single_pool_charms.iter().collect();
    let c_single = BuildConstraints {
        base_hell_res: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 4,
        ..Default::default()
    };
    let leaf_ok = Stats {
        fr: 75,
        lr: 75,
        cr: 145,
        pr: 75,
        ..Default::default()
    };
    let mut single_solver = CharmSolver::new(&single_pool, &c_single, SearchMode::Mf);
    assert!(single_solver
        .solve_with_min_main(leaf_ok, (0, 0), 13)
        .is_none());
    let hit_exact = single_solver
        .solve_with_min_main(leaf_ok, (0, 0), 12)
        .expect("5 (sunder) + 7 (SC) = 12 meets min_main_needed=12");
    assert_eq!(hit_exact.iter().map(|ch| ch.mf).sum::<i32>(), 12);

    // Multi-sunder: tie on main MF (12) still selects the higher-CR sunder (-70 over -80),
    // while min_main_needed=13 rejects both.
    let multi_pool_charms = [
        CharmSpec {
            name: "Cold Rupture -80".to_string(),
            size: 3,
            cr: -80,
            mf: 5,
            unique_id: Some(401),
            cold_sunder: true,
            ..Default::default()
        },
        CharmSpec {
            name: "Cold Rupture -70".to_string(),
            size: 3,
            cr: -70,
            mf: 5,
            unique_id: Some(401),
            cold_sunder: true,
            ..Default::default()
        },
        CharmSpec {
            name: "MF SC".to_string(),
            size: 1,
            mf: 7,
            ..Default::default()
        },
    ];
    let multi_pool: Vec<&CharmSpec> = multi_pool_charms.iter().collect();
    let mut multi_solver = CharmSolver::new(&multi_pool, &c_single, SearchMode::Mf);
    assert!(multi_solver
        .solve_with_min_main(leaf_ok, (0, 0), 13)
        .is_none());
    let multi_hit = multi_solver
        .solve_with_min_main(leaf_ok, (0, 0), 12)
        .expect("should allow tied main score when CR tiebreaker wins");
    assert!(multi_hit.iter().any(|ch| ch.name == "Cold Rupture -70"));

    // 2. Non-res cache key omits `room` (`caps - leaf`) yet filler still adapts to each leaf's caps:
    //    Leaf A has capped PR (75) -> picks Vita SC (+5 life);
    //    Leaf B has low PR (65, min_pr=0) -> shares cache core hit yet picks Emerald SC (+11 PR)!
    let filler_charms = [
        CharmSpec {
            name: "Good Luck SC".to_string(),
            size: 1,
            mf: 7,
            ..Default::default()
        },
        CharmSpec {
            name: "Emerald SC".to_string(),
            size: 1,
            pr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Vita SC".to_string(),
            size: 1,
            life: 5,
            ..Default::default()
        },
    ];
    let filler_pool: Vec<&CharmSpec> = filler_charms.iter().collect();
    let c_filler = BuildConstraints {
        base_hell_res: 0,
        min_fhr: 0,
        min_fr: 75,
        min_lr: 75,
        min_cr: 75,
        min_pr: 0,
        max_charm_slots: 2,
        ..Default::default()
    };
    let mut mf_solver = CharmSolver::new(&filler_pool, &c_filler, SearchMode::Mf);

    let leaf_pr_capped = Stats {
        fr: 75,
        lr: 75,
        cr: 75,
        pr: 75,
        ..Default::default()
    };
    let chosen_a = mf_solver.solve_with_min_main(leaf_pr_capped, (0, 0), 0).unwrap();
    assert!(chosen_a.iter().any(|ch| ch.name == "Vita SC"));

    let leaf_pr_low = Stats {
        fr: 75,
        lr: 75,
        cr: 75,
        pr: 65,
        ..Default::default()
    };
    let chosen_b = mf_solver.solve_with_min_main(leaf_pr_low, (0, 0), 0).unwrap();
    assert!(chosen_b.iter().any(|ch| ch.name == "Emerald SC"));
}

#[test]
fn test_pure_axis_dp_completes_multi_stat_deficits_and_prunes_joint_slot_exhaustion() {
    let charms = [
        CharmSpec {
            name: "Ruby SC plain".to_string(),
            size: 1,
            fr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Ruby SC of Vita".to_string(),
            size: 1,
            fr: 11,
            life: 20,
            ..Default::default()
        },
        CharmSpec {
            name: "Amber SC".to_string(),
            size: 1,
            lr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Sapphire SC".to_string(),
            size: 1,
            cr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Balance SC".to_string(),
            size: 1,
            fhr: 5,
            ..Default::default()
        },
        CharmSpec {
            name: "Strength SC".to_string(),
            size: 1,
            str_bonus: 2,
            ..Default::default()
        },
    ];
    let pool: Vec<&CharmSpec> = charms.iter().collect();
    let leaf = Stats {
        fr: 64,
        lr: 64,
        cr: 64,
        pr: 75,
        fhr: 0,
        str_bonus: 98,
        ..Default::default()
    };

    // Exact 5 slots: all pure charms move into 1D DP (`groups` is empty), solver completes
    // all 5 deficits and picks the +20 life Ruby SC via DP tie-breaking.
    let c_fit = BuildConstraints {
        base_hell_res: 0,
        min_fhr: 5,
        min_fr: 75,
        min_lr: 75,
        min_cr: 75,
        min_pr: 0,
        max_charm_slots: 5,
        ..Default::default()
    };
    let mut solver_fit = CharmSolver::new(&pool, &c_fit, SearchMode::Power);
    assert!(solver_fit.groups.is_empty());
    let chosen = solver_fit.solve_with_min_main(leaf, (100, 0), 0).unwrap();
    assert_eq!(chosen.len(), 5);
    assert!(chosen.iter().any(|ch| ch.name == "Ruby SC of Vita"));

    // 4 slots: each single-axis deficit fits in <=1 slot on its own, but jointly requires 5 > 4.
    let mut c_tight = c_fit.clone();
    c_tight.max_charm_slots = 4;
    let mut solver_tight = CharmSolver::new(&pool, &c_tight, SearchMode::Power);
    assert!(solver_tight.groups.is_empty());
    assert!(solver_tight.solve_with_min_main(leaf, (100, 0), 0).is_none());
}

#[test]
fn test_mixed_hybrid_and_pure_charms_requires_hybrid_to_fit_slots() {
    let charms = [
        CharmSpec {
            name: "Cold Skiller GC".to_string(),
            size: 3,
            skills: 1,
            ..Default::default()
        },
        CharmSpec {
            name: "Ruby SC".to_string(),
            size: 1,
            fr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Ruby SC 2".to_string(),
            size: 1,
            fr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Amber SC".to_string(),
            size: 1,
            lr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Balance SC".to_string(),
            size: 1,
            fhr: 5,
            ..Default::default()
        },
        CharmSpec {
            name: "Hybrid FR/LR SC".to_string(),
            size: 1,
            fr: 11,
            lr: 11,
            ..Default::default()
        },
    ];
    let pool: Vec<&CharmSpec> = charms.iter().collect();

    // Case 1: Feasibility requires the hybrid charm + pure DP charms within 3 slots
    // (pure alone would need 2 + 1 + 1 = 4 slots).
    let c_tight = BuildConstraints {
        base_hell_res: 0,
        min_fhr: 5,
        min_fr: 75,
        min_lr: 75,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 3,
        ..Default::default()
    };
    let leaf_tight = Stats {
        fr: 53,
        lr: 64,
        ..Default::default()
    };
    let mut solver_tight = CharmSolver::new(&pool, &c_tight, SearchMode::Power);
    let chosen_tight = solver_tight.solve_with_min_main(leaf_tight, (0, 0), 0).unwrap();
    assert!(chosen_tight.iter().any(|ch| ch.name == "Hybrid FR/LR SC"));
    assert!(chosen_tight.iter().any(|ch| ch.name == "Balance SC"));
    assert_eq!(chosen_tight.iter().map(|ch| ch.size).sum::<i32>(), 3);

    // Case 2: Objective maximization with 5 slots picks Cold Skiller GC (3 slots) +
    // Hybrid FR/LR SC (1 slot) + pure Balance SC (1 slot) -> 1 skill.
    let mut c_skill = c_tight.clone();
    c_skill.max_charm_slots = 5;
    let leaf_skill = Stats {
        fr: 64,
        lr: 64,
        ..Default::default()
    };
    let mut solver_skill = CharmSolver::new(&pool, &c_skill, SearchMode::Power);
    let chosen_skill = solver_skill.solve_with_min_main(leaf_skill, (0, 0), 0).unwrap();
    assert_eq!(chosen_skill.iter().map(|ch| ch.skills_total()).sum::<i32>(), 1);
    assert!(chosen_skill.iter().any(|ch| ch.name == "Cold Skiller GC"));
    assert!(chosen_skill.iter().any(|ch| ch.name == "Hybrid FR/LR SC"));
    assert!(chosen_skill.iter().any(|ch| ch.name == "Balance SC"));
}

#[test]
fn test_multi_sunder_and_res_modes_keep_res_charms_in_dfs_and_respect_active_axes() {
    // Part A: Multi-sunder (`slot_budget < self.max_slots`) with pure res SCs.
    let sunder_charms = [
        CharmSpec {
            name: "Cold Rupture -75 (2x1)".to_string(),
            size: 2,
            cr: -75,
            mf: 5,
            unique_id: Some(401),
            cold_sunder: true,
            ..Default::default()
        },
        CharmSpec {
            name: "Cold Rupture -70 (3x1)".to_string(),
            size: 3,
            cr: -70,
            mf: 6,
            unique_id: Some(401),
            cold_sunder: true,
            ..Default::default()
        },
        CharmSpec {
            name: "Sapphire SC +20 life".to_string(),
            size: 1,
            cr: 11,
            life: 20,
            ..Default::default()
        },
        CharmSpec {
            name: "Sapphire SC +15 life".to_string(),
            size: 1,
            cr: 11,
            life: 15,
            ..Default::default()
        },
        CharmSpec {
            name: "Sapphire SC +10 life".to_string(),
            size: 1,
            cr: 11,
            life: 10,
            ..Default::default()
        },
        CharmSpec {
            name: "Sapphire SC +5 life".to_string(),
            size: 1,
            cr: 11,
            life: 5,
            ..Default::default()
        },
    ];
    let sunder_pool: Vec<&CharmSpec> = sunder_charms.iter().collect();
    let c_sunder = BuildConstraints {
        base_hell_res: 0,
        min_fhr: 0,
        min_fr: 75,
        min_lr: 75,
        min_cr: 75,
        min_pr: 0,
        max_charm_slots: 6,
        ..Default::default()
    };
    let mut sunder_solver = CharmSolver::new(&sunder_pool, &c_sunder, SearchMode::Mf);
    assert_eq!(sunder_solver.max_slots, 4);

    // Leaf CR=110: -70 (3x1, budget=3) needs 35 CR (impossible in 3 slots);
    // -75 (2x1, budget=4) needs 40 CR and completes with 4 SCs!
    let leaf_need_4 = Stats {
        fr: 75,
        lr: 75,
        cr: 110,
        ..Default::default()
    };
    let chosen_4 = sunder_solver.solve_with_min_main(leaf_need_4, (0, 0), 0).unwrap();
    assert!(chosen_4.iter().any(|ch| ch.name == "Cold Rupture -75 (2x1)"));
    assert_eq!(chosen_4.iter().map(|ch| ch.size).sum::<i32>(), 6);

    // Leaf CR=115: -70 (3x1, budget=3) needs 30 CR -> fits in 3 slots with top 3 life SCs.
    let leaf_need_3 = Stats {
        fr: 75,
        lr: 75,
        cr: 115,
        ..Default::default()
    };
    let chosen_3 = sunder_solver.solve_with_min_main(leaf_need_3, (0, 0), 0).unwrap();
    assert!(chosen_3.iter().any(|ch| ch.name == "Cold Rupture -70 (3x1)"));
    assert_eq!(
        chosen_3.iter().filter(|ch| !ch.cold_sunder).map(|ch| ch.life).sum::<i32>(),
        45
    );

    // Part B: MaxRes & LevelingRes must keep res charms in DFS (out of `pure_axes[3..7]`),
    // while moving pure non-res feasibility charms into DP.
    let res_charms = [
        CharmSpec {
            name: "Ruby SC".to_string(),
            size: 1,
            fr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Sapphire SC".to_string(),
            size: 1,
            cr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Strength SC".to_string(),
            size: 1,
            str_bonus: 2,
            ..Default::default()
        },
        CharmSpec {
            name: "Balance SC".to_string(),
            size: 1,
            fhr: 5,
            ..Default::default()
        },
        CharmSpec {
            name: "FRW SC".to_string(),
            size: 1,
            frw: 3,
            ..Default::default()
        },
        CharmSpec {
            name: "MF SC".to_string(),
            size: 1,
            mf: 7,
            ..Default::default()
        },
    ];
    let res_pool: Vec<&CharmSpec> = res_charms.iter().collect();
    let c_res = BuildConstraints {
        base_hell_res: 0,
        min_fhr: 5,
        min_frw: 3,
        min_mf: 7,
        min_fr: 50,
        min_lr: 50,
        min_cr: 50,
        min_pr: 0,
        max_charm_slots: 5,
        ..Default::default()
    };
    for mode in [SearchMode::MaxRes, SearchMode::LevelingRes] {
        let mut solver = CharmSolver::new(&res_pool, &c_res, mode);
        assert_eq!(solver.pure_axes[0].max_gain, 2);
        assert_eq!(solver.pure_axes[2].max_gain, 5);
        assert_eq!(solver.pure_axes[3].max_gain, 0);
        assert_eq!(solver.pure_axes[5].max_gain, 0);
        assert_eq!(solver.pure_axes[7].max_gain, 3);
        assert_eq!(solver.pure_axes[8].max_gain, 7);
        let leaf = Stats {
            fr: 50,
            lr: 50,
            cr: 50,
            ..Default::default()
        };
        let chosen = solver.solve_with_min_main(leaf, (2, 0), 0).unwrap();
        assert!(chosen.iter().any(|ch| ch.name == "Strength SC"));
        assert!(chosen.iter().any(|ch| ch.name == "Balance SC"));
        assert!(chosen.iter().any(|ch| ch.name == "FRW SC"));
        assert!(chosen.iter().any(|ch| ch.name == "MF SC"));
        assert!(chosen.iter().any(|ch| ch.name == "Ruby SC" || ch.name == "Sapphire SC"));
    }

    // Part B2: PureAxisDp breaks equal-gain ties on `skills_total()` before life in MaxRes / LevelingRes.
    let fhr_skill_charms = [
        CharmSpec {
            name: "Balance GC of Vita".to_string(),
            size: 3,
            fhr: 12,
            life: 20,
            ..Default::default()
        },
        CharmSpec {
            name: "Skiller GC of Balance".to_string(),
            size: 3,
            fhr: 12,
            skills: 1,
            ..Default::default()
        },
    ];
    let fhr_skill_pool: Vec<&CharmSpec> = fhr_skill_charms.iter().collect();
    let c_fhr_skill = BuildConstraints {
        base_hell_res: 0,
        min_fhr: 12,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 3,
        ..Default::default()
    };
    for mode in [SearchMode::MaxRes, SearchMode::LevelingRes] {
        let mut solver = CharmSolver::new(&fhr_skill_pool, &c_fhr_skill, mode);
        assert!(solver.groups.is_empty());
        let chosen = solver
            .solve_with_min_main(Stats::default(), (0, 0), 0)
            .unwrap();
        assert_eq!(chosen.len(), 1);
        assert_eq!(chosen[0].name, "Skiller GC of Balance");
    }

    // Part C: Active axis classification for FR/MF SC in Power (min_mf=0 vs min_mf>0) and Mf.
    let fr_mf_charm = [CharmSpec {
        name: "11 FR / 7 MF SC".to_string(),
        size: 1,
        fr: 11,
        mf: 7,
        ..Default::default()
    }];
    let fr_mf_pool: Vec<&CharmSpec> = fr_mf_charm.iter().collect();
    let c_pow_no_mf = BuildConstraints {
        base_hell_res: 0,
        min_fhr: 0,
        min_mf: 0,
        min_fr: 75,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        allow_mf: true,
        max_charm_slots: 2,
        ..Default::default()
    };
    let s_pure_fr = CharmSolver::new(&fr_mf_pool, &c_pow_no_mf, SearchMode::Power);
    assert!(s_pure_fr.groups.is_empty());
    assert_eq!(s_pure_fr.pure_axes[3].max_gain, 11);

    let mut c_pow_min_mf = c_pow_no_mf.clone();
    c_pow_min_mf.min_mf = 7;
    let s_multi_pow = CharmSolver::new(&fr_mf_pool, &c_pow_min_mf, SearchMode::Power);
    assert_eq!(s_multi_pow.groups.len(), 1);
    assert_eq!(s_multi_pow.pure_axes[3].max_gain, 0);

    let s_multi_mf = CharmSolver::new(&fr_mf_pool, &c_pow_no_mf, SearchMode::Mf);
    assert_eq!(s_multi_mf.groups.len(), 1);
    assert_eq!(s_multi_mf.pure_axes[3].max_gain, 0);
}

#[test]
fn test_ub_main_counts_action_and_aura_skills_total() {
    for (name, action_skills, aura_skills) in [
        ("Paladin Combat GC", 1, 0),
        ("Offensive Aura GC", 0, 1),
    ] {
        let charms = [
            CharmSpec {
                name: "Ruby SC".to_string(),
                size: 1,
                fr: 11,
                ..Default::default()
            },
            CharmSpec {
                name: "Amber SC".to_string(),
                size: 1,
                lr: 11,
                ..Default::default()
            },
            CharmSpec {
                name: name.to_string(),
                size: 3,
                fr: 11,
                lr: 11,
                action_skills,
                aura_skills,
                ..Default::default()
            },
        ];
        let pool: Vec<&CharmSpec> = charms.iter().collect();
        let c = BuildConstraints {
            base_hell_res: 0,
            min_fhr: 0,
            min_fr: 75,
            min_lr: 75,
            min_cr: 0,
            min_pr: 0,
            max_charm_slots: 3,
            ..Default::default()
        };
        let leaf = Stats {
            fr: 64,
            lr: 64,
            ..Default::default()
        };
        let mut solver = CharmSolver::new(&pool, &c, SearchMode::Power);

        // 1. Greedy takes Ruby + Amber (2 slots, g_main=0); ub_main must still see skills_total=1
        //    so solve_exact runs instead of short-circuiting on 0 >= 0.
        let picked_unconstrained = solver.solve_with_min_main(leaf, (0, 0), 0).unwrap();
        assert_eq!(
            picked_unconstrained
                .iter()
                .map(|ch| ch.skills_total())
                .sum::<i32>(),
            1
        );
        assert!(picked_unconstrained.iter().any(|ch| ch.name == name));

        // 2. With min_main_needed=1, ub_main must not falsely prune or poison failed_floor.
        let mut fresh_solver = CharmSolver::new(&pool, &c, SearchMode::Power);
        assert!(fresh_solver.solve_with_min_main(leaf, (0, 0), 2).is_none());
        let picked_min1 = fresh_solver.solve_with_min_main(leaf, (0, 0), 1).unwrap();
        assert_eq!(
            picked_min1
                .iter()
                .map(|ch| ch.skills_total())
                .sum::<i32>(),
            1
        );
        assert!(picked_min1.iter().any(|ch| ch.name == name));
    }
}

#[test]
fn test_charm_solver_handles_all_skills_and_vit_ene_tiebreak() {
    let torch_low = CharmSpec {
        name: "Torch 10/10".to_string(),
        size: 2,
        skills: 3,
        str_bonus: 10,
        dex_bonus: 10,
        vit: 10,
        ene: 10,
        fr: 15,
        lr: 15,
        cr: 15,
        pr: 15,
        unique_id: Some(400),
        ..Default::default()
    };
    let torch_high = CharmSpec {
        name: "Torch 20/15".to_string(),
        size: 2,
        skills: 3,
        str_bonus: 10,
        dex_bonus: 10,
        vit: 20,
        ene: 20,
        fr: 15,
        lr: 15,
        cr: 15,
        pr: 15,
        unique_id: Some(400),
        ..Default::default()
    };
    let anni = CharmSpec {
        name: "Annihilus".to_string(),
        size: 1,
        all_skills: 1,
        str_bonus: 15,
        dex_bonus: 15,
        vit: 15,
        ene: 15,
        fr: 15,
        lr: 15,
        cr: 15,
        pr: 15,
        unique_id: Some(381),
        ..Default::default()
    };

    let pool = vec![&torch_low, &torch_high, &anni];
    let c = BuildConstraints {
        char_class: 3,
        base_hell_res: 45,
        min_fhr: 0,
        min_fr: 75,
        min_lr: 75,
        min_cr: 75,
        min_pr: 75,
        max_charm_slots: 3,
        ..Default::default()
    };
    let mut solver = CharmSolver::new(&pool, &c, SearchMode::Power);
    assert_eq!(solver.charm_ub_stats().total_skills(), 4);
    assert_eq!(solver.charm_ub_stats().all_skills, 1);

    let leaf = Stats {
        fr: 45,
        lr: 45,
        cr: 45,
        pr: 45,
        ..Default::default()
    };
    let picked = solver
        .solve_with_min_main(leaf, (0, 0), 4)
        .expect("Torch + Anni should satisfy min_main=4");
    assert_eq!(picked.len(), 2);
    assert!(picked.iter().any(|ch| ch.name == "Torch 20/15"));
    assert!(picked.iter().any(|ch| ch.name == "Annihilus"));
}

#[test]
fn test_improve_for_dps_negative_res_leveling_res_and_pure_dps_solver_parity() {
    // 1. Regression for LevelingRes when `best_score.primary < 0` and `cutoff == None`.
    let ruby_sc = CharmSpec {
        name: "Ruby SC".to_string(),
        size: 1,
        fr: 5,
        ..Default::default()
    };
    let fiery_sc = CharmSpec {
        name: "Fiery SC".to_string(),
        size: 1,
        flat_fire_2x: 40,
        ..Default::default()
    };
    let c_neg = BuildConstraints {
        char_class: 3,
        char_level: 80,
        base_hell_res: -100,
        min_fhr: 0,
        min_fr: -100,
        min_lr: -100,
        min_cr: -100,
        min_pr: -100,
        max_charm_slots: 1,
        offense: "melee".to_string(),
        action_hits: vec![1],
        target_def: 1000,
        mode: "leveling-res".to_string(),
        ..Default::default()
    };
    let gear = Stats {
        dex_bonus: 50,
        ..Default::default()
    };
    let leaf = Stats {
        fr: -100,
        lr: -100,
        cr: -100,
        pr: -100,
        ..gear
    };
    let hw = HandWeapon {
        phys_2x: 40,
        str_pct: 100,
        ..Default::default()
    };
    let pool_neg = vec![&ruby_sc, &fiery_sc];
    let mut solver_neg = CharmSolver::new(&pool_neg, &c_neg, SearchMode::LevelingRes);
    let best_charms = solver_neg.solve_with_min_main(leaf, (0, 0), 0).unwrap();
    let best_sum = eval_build_summary(gear, 0, hw, &best_charms, &c_neg);
    let best_score =
        score_eval_summary(SearchMode::LevelingRes, OffenseProfile::Melee, &best_sum, &c_neg);
    assert!(best_score.primary < 0);

    // Without ruby_sc (only fiery_sc in pool), res_base stays -400 (< 0), so improve_for_dps
    // must NOT falsely prune on `cutoff.map_or(0, ...)`!
    let pool_fire_only = vec![&fiery_sc];
    let mut solver_fire = CharmSolver::new(&pool_fire_only, &c_neg, SearchMode::LevelingRes);
    let mut best_c2: Vec<&CharmSpec> = Vec::new();
    let mut best_s2 = eval_build_summary(gear, 0, hw, &best_c2, &c_neg);
    let mut best_sc2 = score_eval_summary(SearchMode::LevelingRes, OffenseProfile::Melee, &best_s2, &c_neg);
    solver_fire.improve_for_dps(
        gear,
        0,
        hw,
        leaf,
        (0, 0),
        OffenseProfile::Melee,
        None,
        &mut best_c2,
        &mut best_s2,
        &mut best_sc2,
    );
    assert_eq!(best_c2.len(), 1);
    assert_eq!(best_c2[0].name, "Fiery SC");

    // 2. PureDpsSolver parity vs brute force across cth_is_const, p_dec==0 + splash_fire,
    //    p_dec>0, negative base damage, and >64 pure DPS charm overflow.
    let pure_items = [
        CharmSpec {
            name: "Fine SC A".to_string(),
            size: 1,
            ar: 20,
            flat_phys_2x: 6,
            ..Default::default()
        },
        CharmSpec {
            name: "Fine SC B".to_string(),
            size: 1,
            ar: 10,
            flat_phys_2x: 6,
            ..Default::default()
        },
        CharmSpec {
            name: "Fiery LC".to_string(),
            size: 2,
            flat_fire_2x: 24,
            ..Default::default()
        },
        CharmSpec {
            name: "Shock GC".to_string(),
            size: 3,
            flat_elem_2x: 36,
            ..Default::default()
        },
        CharmSpec {
            name: "Venom SC".to_string(),
            size: 1,
            psn_dps_2x: 18,
            ..Default::default()
        },
        CharmSpec {
            name: "Iron GC".to_string(),
            size: 3,
            ar: 120,
            ..Default::default()
        },
    ];
    let pure_pool: Vec<&CharmSpec> = pure_items.iter().collect();
    let base_c = BuildConstraints {
        char_class: 3,
        char_level: 80,
        base_hell_res: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 5,
        targets: 2,
        target_def: 1500,
        offense: "melee".to_string(),
        action_hits: vec![1],
        mode: "leveling".to_string(),
        ..Default::default()
    };
    let cases = [
        // (cth_is_const via target_def=0, splash_fire=false, p_dec=0, non_neg_base=true)
        (
            BuildConstraints {
                target_def: 0,
                ..base_c.clone()
            },
            HandWeapon {
                phys_2x: 30,
                str_pct: 100,
                ..Default::default()
            },
            Stats {
                str_bonus: 50,
                dex_bonus: 50,
                ..Default::default()
            },
        ),
        // (p_dec == 0.0, splash_fire = true)
        (
            base_c.clone(),
            HandWeapon {
                phys_2x: 20,
                wclass: WeaponClass::Bow,
                dex_pct: 100,
                splash_fire: true,
                splash_fire_2x: 50,
                ..Default::default()
            },
            Stats {
                dex_bonus: 40,
                ..Default::default()
            },
        ),
        // (p_dec > 0.0)
        (
            base_c.clone(),
            HandWeapon {
                phys_2x: 40,
                str_pct: 100,
                ..Default::default()
            },
            Stats {
                str_bonus: 60,
                dex_bonus: 30,
                ctc_decrep_pct: 25,
                ..Default::default()
            },
        ),
        // (cth_is_const + negative base damage -> !non_neg_base fallback)
        (
            BuildConstraints {
                target_def: 0,
                ..base_c.clone()
            },
            HandWeapon {
                phys_2x: 0,
                str_pct: 100,
                ..Default::default()
            },
            Stats {
                flat_phys_2x: -4,
                flat_fire_2x: -10,
                ..Default::default()
            },
        ),
    ];

    for (idx, (c_case, hw_case, leaf_case)) in cases.iter().enumerate() {
        let solver = CharmSolver::new(&pure_pool, c_case, SearchMode::Leveling);
        let fast = OffenseProfile::Melee.fast_leaf_dps(*hw_case, *leaf_case, c_case);
        let dp_res = solver
            .pure_dps
            .solve_for_leaf(&fast, c_case.max_charm_slots as usize);
        let dp_best_dps = dp_res[c_case.max_charm_slots as usize].0;

        let mut bf_best_dps = 0.0_f64;
        for mask in 0u32..(1u32 << pure_items.len()) {
            let picks: Vec<&CharmSpec> = (0..pure_items.len())
                .filter(|&i| (mask & (1 << i)) != 0)
                .map(|i| &pure_items[i])
                .collect();
            let slots: i32 = picks.iter().map(|ch| ch.size).sum();
            if slots > c_case.max_charm_slots {
                continue;
            }
            let s = Stats {
                ar: leaf_case.ar + picks.iter().map(|ch| ch.ar).sum::<i32>(),
                flat_phys_2x: leaf_case.flat_phys_2x
                    + picks.iter().map(|ch| ch.flat_phys_2x).sum::<i32>(),
                flat_fire_2x: leaf_case.flat_fire_2x
                    + picks.iter().map(|ch| ch.flat_fire_2x).sum::<i32>(),
                flat_elem_2x: leaf_case.flat_elem_2x
                    + picks.iter().map(|ch| ch.flat_elem_2x).sum::<i32>(),
                psn_dps_2x: leaf_case.psn_dps_2x
                    + picks.iter().map(|ch| ch.psn_dps_2x).sum::<i32>(),
                ..*leaf_case
            };
            let dps = OffenseProfile::Melee.compute_dps(*hw_case, s, c_case).0;
            bf_best_dps = bf_best_dps.max(dps);
        }
        assert!(
            (dp_best_dps - bf_best_dps).abs() <= 1e-9 * bf_best_dps.max(1.0),
            "PureDpsSolver case {idx} mismatch: dp={dp_best_dps}, bf={bf_best_dps}"
        );
    }

    // 3. >64 pure DPS charms overflow into `dps_groups` cleanly without panic or loss.
    let mut many_pure: Vec<CharmSpec> = (0..65)
        .map(|i| CharmSpec {
            name: format!("Weak Pure SC {i}"),
            size: 1,
            ar: 5,
            ..Default::default()
        })
        .collect();
    // 65 different flat_fire values so max_copies=1 doesn't truncate below 65 items.
    for (i, ch) in many_pure.iter_mut().enumerate() {
        ch.flat_fire_2x = (i as i32) + 1;
        ch.psn_dps_2x = 65 - (i as i32);
    }
    // Give the lowest-flat_fire item (which overflows into `dps_groups`) huge poison DPS so it must win.
    many_pure[0].psn_dps_2x = 5000;
    let many_pool: Vec<&CharmSpec> = many_pure.iter().collect();
    let mut c_many = base_c;
    c_many.max_charm_slots = 1;
    let mut solver_many = CharmSolver::new(&many_pool, &c_many, SearchMode::Leveling);
    assert_eq!(solver_many.pure_dps.item_indices.len(), 64);
    assert_eq!(solver_many.dps_groups.len(), 1);
    let mut best_c3: Vec<&CharmSpec> = Vec::new();
    let mut best_s3 = eval_build_summary(gear, 0, hw, &best_c3, &c_many);
    let mut best_sc3 = score_eval_summary(SearchMode::Leveling, OffenseProfile::Melee, &best_s3, &c_many);
    solver_many.improve_for_dps(
        gear,
        0,
        hw,
        Stats {
            dex_bonus: 50,
            ..Default::default()
        },
        (0, 0),
        OffenseProfile::Melee,
        None,
        &mut best_c3,
        &mut best_s3,
        &mut best_sc3,
    );
    assert_eq!(best_c3.len(), 1);
    assert_eq!(best_c3[0].psn_dps_2x, 5000);
}
