use super::*;

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
