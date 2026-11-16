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
