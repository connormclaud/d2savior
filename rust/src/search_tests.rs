use super::*;
use crate::types::{mk_test_item as mk_item, test_constraints};

#[test]
fn test_optimize_builds_basic() {
    let items = vec![
        mk_item("Spirit Sword", "weapon", 34, 55, 2, 0, 0),
        mk_item("Oculus", "weapon", 30, 0, 3, 20, 50),
        mk_item("Spirit Shield", "shield", 34, 55, 2, 35, 0),
        mk_item("Tiara", "helm", 0, 0, 2, 15, 0),
        mk_item("Que-Hegan", "armor", 20, 20, 1, 0, 0),
        mk_item("Smoke", "armor", 0, 20, 0, 50, 0),
        mk_item("Grim Noose", "amulet", 5, 0, 1, 30, 0),
        mk_item("Credendum", "belt", 0, 0, 0, 45, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Aldurs", "boots", 0, 0, 0, 45, 0),
        mk_item("Ring A", "ring", 10, 0, 0, 20, 0),
        mk_item("Ring B", "ring", 10, 0, 0, 20, 0),
    ];
    let charms = vec![
        CharmSpec {
            name: "Balance GC".to_string(),
            size: 3,
            loc: "test".to_string(),
            fhr: 12,
            ..Default::default()
        },
        CharmSpec {
            name: "MF SC".to_string(),
            size: 1,
            loc: "test".to_string(),
            mf: 7,
            ..Default::default()
        },
    ];

    let c_power = BuildConstraints {
        min_pr: 75,
        ..test_constraints()
    };
    let res = optimize_builds_core(&items, &charms, &c_power).unwrap();
    assert!(!res.is_empty());
    assert_eq!(res[0].skills, 9);
    assert!(res[0].fcr >= 105);
    assert!(res[0].fhr >= 86);

    let c_zero_mf = BuildConstraints {
        allow_mf: false,
        ..c_power
    };
    let res0 = optimize_builds_core(&items, &charms, &c_zero_mf).unwrap();
    assert!(!res0.is_empty());
    assert_eq!(res0[0].mf, 0);
    assert_eq!(res0[0].skills, 8);
}

#[test]
fn test_str_dex_requirements() {
    let mut high_dex_wep = mk_item("High Dex Blade", "weapon", 50, 0, 3, 20, 0);
    high_dex_wep.req_dex = 42;
    high_dex_wep.dex_bonus = 15; // self dex cannot equip itself!

    let base_wep = mk_item("Low Dex Wand", "weapon", 30, 0, 1, 20, 0);

    let mut dex_belt = mk_item("Dex Belt", "belt", 0, 0, 0, 20, 0);
    dex_belt.dex_bonus = 20;

    let items = vec![
        high_dex_wep,
        base_wep,
        mk_item("Spirit Shield", "shield", 34, 55, 2, 35, 0),
        mk_item("Tiara", "helm", 0, 0, 2, 20, 0),
        mk_item("Armor", "armor", 20, 40, 1, 40, 0),
        mk_item("Amulet", "amulet", 10, 0, 0, 40, 0),
        dex_belt,
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Aldurs", "boots", 0, 0, 0, 45, 0),
        mk_item("Ring A", "ring", 10, 0, 0, 20, 0),
        mk_item("Ring B", "ring", 10, 0, 0, 20, 0),
    ];

    // With base_dex = 25 and only +20 Dex from belt (45 >= 42), High Dex Blade IS equippable.
    let c_ok = BuildConstraints {
        skill_slack: 3,
        ..test_constraints()
    };
    let res_ok = optimize_builds_core(&items, &[], &c_ok).unwrap();
    assert_eq!(res_ok[0].items[0].name, "High Dex Blade");

    // With base_dex = 20 (20 + 20 = 40 < 42), High Dex Blade CANNOT be equipped -> falls back to Low Dex Wand.
    let c_low = BuildConstraints {
        base_dex: 20,
        ..c_ok
    };
    let res_low = optimize_builds_core(&items, &[], &c_low).unwrap();
    assert_eq!(res_low[0].items[0].name, "Low Dex Wand");
}

#[test]
fn test_mf_charms_do_not_starve_resistances() {
    let mut items = vec![
        mk_item("Spirit Sword", "weapon", 35, 55, 2, 0, 0),
        mk_item("Spirit Shield", "shield", 35, 55, 2, 35, 0),
        mk_item("Tiara", "helm", 20, 0, 2, 20, 0),
        mk_item("Skullder", "armor", 0, 0, 1, 0, 110),
        mk_item("Amulet", "amulet", 10, 0, 1, 30, 0),
        mk_item("Belt", "belt", 0, 0, 0, 30, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Aldurs", "boots", 0, 0, 0, 40, 0),
        mk_item("Ring A", "ring", 10, 0, 0, 10, 0),
        mk_item("Ring B", "ring", 10, 0, 0, 10, 0),
    ];
    // Spirit/Trangs/Aldurs lack LR: 35 (shield) + 30 (gloves) + 40 (boots) removed from LR
    // -> gear LR = 20 + 30 + 30 + 10 + 10 = 100 -> -70 + 100 = 30, or keep Spirit LR=25 -> 55 LR (needs +20).
    items[1].lr = 25;
    items[6].lr = 0;
    items[7].lr = 0;

    let mut charms: Vec<CharmSpec> = (0..25)
        .map(|i| CharmSpec {
            name: format!("MF SC {i}"),
            size: 1,
            loc: "stash".to_string(),
            mf: 7,
            ..Default::default()
        })
        .collect();
    charms.push(CharmSpec {
        name: "Amber SC 1".to_string(),
        size: 1,
        loc: "stash".to_string(),
        lr: 11,
        ..Default::default()
    });
    charms.push(CharmSpec {
        name: "Amber SC 2".to_string(),
        size: 1,
        loc: "stash".to_string(),
        lr: 11,
        ..Default::default()
    });

    let c_mf = BuildConstraints {
        min_cr: 50,
        mode: "mf".to_string(),
        skill_slack: 3,
        ..test_constraints()
    };
    let res = optimize_builds_core(&items, &charms, &c_mf).unwrap();
    assert!(!res.is_empty(), "MF charms must not fill all slots before res targets");
    assert!(res[0].lr >= 75);
    // 2 slots for Amber SCs + 21 remaining slots filled with 7% MF SCs = 147 charm MF + 110 Skullder = 257
    assert_eq!(res[0].mf, 257);
}

#[test]
fn test_cold_skiller_charms_count_toward_skills() {
    let items = vec![
        mk_item("Spirit Sword", "weapon", 35, 55, 2, 0, 0),
        mk_item("Spirit Shield", "shield", 35, 55, 2, 35, 0),
        mk_item("Tiara", "helm", 20, 0, 2, 30, 0),
        mk_item("Smoke", "armor", 0, 20, 0, 50, 0),
        mk_item("Amulet", "amulet", 10, 0, 1, 30, 0),
        mk_item("Belt", "belt", 0, 0, 0, 30, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Aldurs", "boots", 0, 0, 0, 40, 0),
        mk_item("Ring A", "ring", 10, 0, 0, 20, 0),
        mk_item("Ring B", "ring", 10, 0, 0, 20, 0),
    ];
    // Pool has a plain Cold Skiller (no life/res), a Torch (+3), an Anni (+1), plus plain Life SCs that would otherwise fill all 23 slots.
    let mut charms = vec![
        CharmSpec {
            name: "Chilling GC".to_string(),
            size: 3,
            loc: "stash".to_string(),
            skills: 1,
            ..Default::default()
        },
        CharmSpec {
            name: "Sorc Torch".to_string(),
            size: 2,
            loc: "inv".to_string(),
            fr: 15,
            lr: 15,
            cr: 15,
            pr: 15,
            str_bonus: 15,
            skills: 3,
            ..Default::default()
        },
        CharmSpec {
            name: "Annihilus".to_string(),
            size: 1,
            loc: "inv".to_string(),
            fr: 15,
            lr: 15,
            cr: 15,
            pr: 15,
            str_bonus: 15,
            skills: 1,
            ..Default::default()
        },
        CharmSpec {
            name: "Sparking GC".to_string(),
            size: 3,
            loc: "stash".to_string(),
            life: 40,
            light_skills: 1,
            ..Default::default()
        },
    ];
    for i in 0..25 {
        charms.push(CharmSpec {
            name: format!("Vita SC {i}"),
            size: 1,
            loc: "stash".to_string(),
            life: 20,
            ..Default::default()
        });
    }

    let c_power = BuildConstraints {
        min_pr: 75,
        ..test_constraints()
    };
    let res = optimize_builds_core(&items, &charms, &c_power).unwrap();
    assert!(!res.is_empty());
    // Gear skills = 7, plus Chilling GC (+1), Sorc Torch (+3), Annihilus (+1) = 12
    assert_eq!(res[0].skills, 12);
    assert!(res[0].charms.iter().any(|c| c.name == "Chilling GC"));
    assert!(!res[0].charms.iter().any(|c| c.name == "Sparking GC"));
}

#[test]
fn test_result_and_ring_pair_deduplication_preserves_distinct_slots() {
    let mut ring_plain = mk_item("Ring Plain", "ring", 10, 0, 0, 20, 0);
    let mut ring_soj = mk_item("SoJ", "ring", 0, 0, 1, 0, 0);
    ring_soj.all_skills = 1;
    ring_soj.sorc_skills = 0;
    ring_soj.mana = 20;
    ring_soj.pct_mana = 25;

    let mut ring_caster = mk_item("Ring Caster", "ring", 0, 0, 1, 0, 0);
    ring_caster.all_skills = 0;
    ring_caster.sorc_skills = 1;
    ring_caster.mana = 0;
    ring_caster.pct_mana = 0;

    ring_plain.life = 0;
    let items = vec![
        mk_item("Spirit Sword", "weapon", 35, 55, 2, 0, 0),
        mk_item("Spirit Shield", "shield", 35, 55, 2, 35, 0),
        mk_item("Tiara", "helm", 20, 0, 2, 20, 0),
        mk_item("Smoke", "armor", 0, 20, 0, 50, 0),
        mk_item("Amulet A", "amulet", 15, 0, 1, 30, 0),
        mk_item("Amulet B", "amulet", 15, 0, 1, 35, 0),
        mk_item("Belt", "belt", 0, 0, 0, 30, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Aldurs", "boots", 0, 0, 0, 40, 0),
        ring_caster,
        ring_soj,
        ring_plain,
    ];

    let c_power = BuildConstraints {
        min_pr: 75,
        ..test_constraints()
    };
    let res = optimize_builds_core(&items, &[], &c_power).unwrap();
    // Distinct amulets and distinct ring pairs must both be preserved across results (limit = 5).
    assert!(res.len() >= 2);
    let amulet_names: HashSet<&str> = res.iter().map(|r| r.items[4].name.as_str()).collect();
    assert!(amulet_names.contains("Amulet A") && amulet_names.contains("Amulet B"));
    // Option #1 must keep SoJ (higher mana_bo & bo_lvl) rather than dropping SoJ during ring-pair dedup against Ring Caster.
    assert!(res[0].items.iter().any(|it| it.name == "SoJ"));
}

#[test]
fn test_bounded_top_results_caps_memory_and_keeps_distinct_top_k() {
    let mut amu_dup1 = mk_item("SameAmu", "amulet", 10, 0, 1, 30, 0);
    amu_dup1.life = 10;
    let mut amu_dup2 = mk_item("SameAmu", "amulet", 10, 0, 1, 30, 0);
    amu_dup2.life = 40;
    let mut amu_best = mk_item("BestAmu", "amulet", 10, 0, 2, 30, 0);
    amu_best.life = 50;
    let mut amu_mid = mk_item("MidAmu", "amulet", 10, 0, 1, 30, 0);
    amu_mid.life = 25;

    let items = vec![
        mk_item("Spirit Sword", "weapon", 35, 55, 2, 0, 0),
        mk_item("Spirit Shield", "shield", 35, 55, 2, 35, 0),
        mk_item("Tiara", "helm", 20, 0, 2, 20, 0),
        mk_item("Smoke", "armor", 0, 20, 0, 50, 0),
        amu_dup1,
        amu_dup2,
        amu_mid,
        amu_best,
        mk_item("Belt", "belt", 0, 0, 0, 30, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Aldurs", "boots", 0, 0, 0, 40, 0),
        mk_item("Ring A", "ring", 10, 0, 0, 20, 0),
        mk_item("Ring B", "ring", 10, 0, 0, 20, 0),
    ];

    let c_lim2 = BuildConstraints {
        min_pr: 75,
        limit: 2,
        ..test_constraints()
    };
    let top2 = optimize_builds_core(&items, &[], &c_lim2).unwrap();
    assert_eq!(top2.len(), 2);
    assert_eq!(top2[0].items[4].name, "BestAmu");
    assert_eq!(top2[1].items[4].name, "SameAmu");
    assert_eq!(top2[1].items[4].life, 40);

    let c_unlim = BuildConstraints {
        limit: 0,
        ..c_lim2
    };
    let all = optimize_builds_core(&items, &[], &c_unlim).unwrap();
    assert_eq!(all.len(), 3);
    assert_eq!(all[0].items, top2[0].items);
    assert_eq!(all[1].items, top2[1].items);
    assert_eq!(top2[0].evaluated_candidates, 2);
    assert_eq!(all[0].evaluated_candidates, 4);
    assert_eq!(all[2].items[4].name, "MidAmu");
}

#[test]
fn test_max_resistance_cap_allows_above_75_up_to_95() {
    let mut hotspur = mk_item("Hotspur", "boots", 0, 0, 0, 0, 0);
    hotspur.fr = 45;
    hotspur.max_fr = 15;

    let mut guardian = mk_item("Guardian Angel", "armor", 0, 0, 0, 0, 0);
    guardian.max_fr = 15;
    guardian.max_lr = 15;
    guardian.max_cr = 15;
    guardian.max_pr = 15;

    let mut shield = mk_item("Spirit Shield", "shield", 35, 55, 2, 35, 0);
    shield.fr = 0;
    let mut gloves = mk_item("Trangs", "gloves", 20, 0, 0, 30, 0);
    gloves.fr = 0;

    let items = vec![
        mk_item("Spirit Sword", "weapon", 35, 55, 2, 0, 0),
        shield,
        mk_item("Tiara", "helm", 20, 0, 2, 20, 0),
        mk_item("Smoke", "armor", 0, 20, 0, 50, 0),
        guardian,
        mk_item("Amulet", "amulet", 15, 0, 1, 20, 0),
        mk_item("Belt", "belt", 0, 0, 0, 10, 0),
        gloves,
        hotspur,
        mk_item("Ring A", "ring", 10, 0, 0, 20, 0),
        mk_item("Ring B", "ring", 10, 0, 0, 20, 0),
    ];
    // Gear FR with Guardian Angel + Hotspur = 20+20+10+45+20+20 = 135 -> raw 65 (-70 base).
    // 3x Ruby SC (+11 FR each) brings raw FR from 65 -> 76 -> 87 -> 98 (capped at 95).
    let charms = vec![
        CharmSpec {
            name: "Ruby SC 1".to_string(),
            size: 1,
            loc: "stash".to_string(),
            fr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Ruby SC 2".to_string(),
            size: 1,
            loc: "stash".to_string(),
            fr: 11,
            ..Default::default()
        },
        CharmSpec {
            name: "Ruby SC 3".to_string(),
            size: 1,
            loc: "stash".to_string(),
            fr: 11,
            ..Default::default()
        },
    ];

    // Requiring min_fr = 95 forces Hotspur (+15) + Guardian Angel (+15) -> capped at HARD_MAX_RES 95 (not 105).
    let c_max = BuildConstraints {
        min_fr: 95,
        ..test_constraints()
    };
    let res = optimize_builds_core(&items, &charms, &c_max).unwrap();
    assert_eq!(res.len(), 1);
    assert_eq!(res[0].max_fr, 95);
    assert_eq!(res[0].fr_raw, 98);
    assert_eq!(res[0].fr, 95);
    assert_eq!(res[0].max_lr, 90);
    assert_eq!(res[0].lr, 85);
}

#[test]
fn test_max_res_build_mode_prioritizes_max_effective_resistances() {
    let mut guardian = mk_item("Guardian Angel", "armor", 0, 0, 0, 0, 0);
    guardian.max_fr = 15;
    guardian.max_lr = 15;
    guardian.max_cr = 15;
    guardian.max_pr = 15;

    let coh = mk_item("Chains of Honor", "armor", 0, 0, 2, 65, 25);

    let items = vec![
        mk_item("Spirit Sword", "weapon", 35, 55, 2, 0, 0),
        mk_item("Spirit Shield", "shield", 35, 55, 2, 35, 0),
        mk_item("Tiara", "helm", 20, 0, 2, 30, 0),
        coh,
        guardian,
        mk_item("Amulet", "amulet", 15, 0, 1, 30, 0),
        mk_item("Belt", "belt", 0, 0, 0, 30, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Boots", "boots", 0, 0, 0, 35, 0),
        mk_item("Ring A", "ring", 10, 0, 0, 20, 0),
        mk_item("Ring B", "ring", 10, 0, 0, 20, 0),
    ];
    // Fill 23 slots: 8x Chilling GC (24 slots) + 4x All-Res SC (+5 all res each).
    // Under max-res mode, All-Res SCs should top resistances up toward 90/90/90/90 BEFORE skillers eat all slots.
    let mut charms: Vec<CharmSpec> = (0..8)
        .map(|i| CharmSpec {
            name: format!("Chilling GC {i}"),
            size: 3,
            loc: "stash".to_string(),
            skills: 1,
            ..Default::default()
        })
        .collect();
    for i in 0..4 {
        charms.push(CharmSpec {
            name: format!("Shimmering SC {i}"),
            size: 1,
            loc: "stash".to_string(),
            fr: 5,
            lr: 5,
            cr: 5,
            pr: 5,
            ..Default::default()
        });
    }

    let c_power = BuildConstraints {
        min_fcr: 63,
        min_fhr: 60,
        min_pr: 75,
        limit: 3,
        ..test_constraints()
    };
    let res_power = optimize_builds_core(&items, &charms, &c_power).unwrap();
    assert_eq!(res_power[0].items[3].name, "Chains of Honor");
    assert_eq!(res_power[0].fr + res_power[0].lr + res_power[0].cr + res_power[0].pr, 300);

    let c_maxres = BuildConstraints {
        mode: "max-res".to_string(),
        ..c_power
    };
    let res_maxres = optimize_builds_core(&items, &charms, &c_maxres).unwrap();
    assert_eq!(res_maxres[0].items[3].name, "Guardian Angel");
    assert!(res_maxres[0].fr + res_maxres[0].lr + res_maxres[0].cr + res_maxres[0].pr > 300);
    // Gear gives -70 + 30+30+30+35+20+20 = 95 base FR/CR, 130 LR/PR? Wait: Tiara 30 + Amu 30 + Belt 30 + Boots 35 + Rings 40 = 165 -> 95 raw;
    // shield + gloves only 35 LR/PR & 30 CR; 4x Shimmering SC (+20) pushes FR capped 90, LR 90, CR 90, PR 90!
    assert_eq!((res_maxres[0].fr, res_maxres[0].lr, res_maxres[0].cr, res_maxres[0].pr), (90, 90, 90, 90));
}

#[test]
fn test_unique_charm_limit_prevents_duplicates() {
    let items = vec![
        mk_item("Spirit Sword", "weapon", 35, 55, 2, 0, 0),
        mk_item("Spirit Shield", "shield", 35, 55, 2, 35, 0),
        mk_item("Tiara", "helm", 20, 0, 2, 40, 0),
        mk_item("Skin", "armor", 30, 0, 1, 35, 0),
        mk_item("Amulet", "amulet", 15, 0, 2, 30, 0),
        mk_item("Belt", "belt", 0, 0, 0, 20, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Boots", "boots", 0, 0, 0, 20, 0),
        mk_item("Ring A", "ring", 10, 0, 0, 20, 0),
        mk_item("Ring B", "ring", 10, 0, 0, 20, 0),
    ];
    let torch_a = CharmSpec {
        name: "Hellfire Torch A".to_string(),
        size: 2,
        loc: "inv".to_string(),
        fr: 20,
        lr: 20,
        cr: 20,
        pr: 20,
        str_bonus: 20,
        skills: 3,
        unique_id: Some(400),
        ..Default::default()
    };
    let torch_b = CharmSpec {
        name: "Hellfire Torch B".to_string(),
        size: 2,
        loc: "stash".to_string(),
        ..torch_a.clone()
    };
    let skiller = CharmSpec {
        name: "Chilling GC".to_string(),
        size: 3,
        loc: "stash".to_string(),
        skills: 1,
        ..Default::default()
    };

    let charms = vec![torch_a, torch_b, skiller];
    let c = BuildConstraints {
        min_pr: 75,
        limit: 3,
        ..test_constraints()
    };
    let res = optimize_builds_core(&items, &charms, &c).unwrap();
    assert_eq!(res.len(), 1);
    let unique_count = res[0]
        .charms
        .iter()
        .filter(|ch| ch.unique_id == Some(400))
        .count();
    assert_eq!(unique_count, 1);
    assert!(res[0].charms.iter().any(|ch| ch.name == "Chilling GC"));
}

#[test]
fn test_dominated_items_do_not_inflate_evaluated_candidates() {
    let best_helm = mk_item("Best Helm", "helm", 20, 20, 2, 30, 50);
    let soj_1 = mk_item("SoJ", "ring", 10, 0, 1, 20, 0);
    let soj_2 = soj_1.clone();

    let base_items = vec![
        mk_item("Spirit Sword", "weapon", 35, 55, 2, 0, 0),
        mk_item("Spirit Shield", "shield", 35, 55, 2, 35, 0),
        best_helm.clone(),
        mk_item("Smoke", "armor", 0, 20, 0, 50, 0),
        mk_item("Amulet", "amulet", 15, 0, 2, 30, 0),
        mk_item("Belt", "belt", 0, 0, 0, 30, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Boots", "boots", 0, 0, 0, 40, 0),
        soj_1.clone(),
        soj_2.clone(),
    ];

    let mut noisy_items = base_items.clone();
    // Add strictly dominated helms and extra redundant/dominated rings.
    for i in 0..8 {
        noisy_items.push(mk_item(&format!("Trash Helm {i}"), "helm", 10, 0, 1, 15, 10));
        noisy_items.push(mk_item(&format!("Bad Ring {i}"), "ring", 0, 0, 0, 10, 0));
    }
    // Add extra identical-stat SoJ copies beyond limit.max(2).
    for _ in 0..4 {
        noisy_items.push(soj_1.clone());
    }

    let c_lim1 = BuildConstraints {
        min_pr: 75,
        limit: 1,
        ..test_constraints()
    };
    let res_base = optimize_builds_core(&base_items, &[], &c_lim1).unwrap();
    let res_noisy = optimize_builds_core(&noisy_items, &[], &c_lim1).unwrap();

    assert_eq!(res_base.len(), 1);
    assert_eq!(res_noisy.len(), 1);
    assert_eq!(res_base[0].evaluated_candidates, 1);
    assert_eq!(
        res_noisy[0].evaluated_candidates,
        res_base[0].evaluated_candidates
    );
    assert_eq!(res_noisy[0].items[2].name, "Best Helm");
    assert_eq!(res_noisy[0].skills, res_base[0].skills);
}

#[test]
fn test_blizz_and_cm_single_skills_rank_and_damage() {
    let mut orb_blizz = mk_item("Sorc +2/+3 Blizz Orb", "weapon", 30, 0, 0, 20, 0);
    orb_blizz.sorc_skills = 2;
    orb_blizz.blizz_skills = 3;
    orb_blizz.cm_skills = 1;

    let mut orb_plain = mk_item("Sorc +3 Orb", "weapon", 30, 0, 0, 20, 0);
    orb_plain.sorc_skills = 3;

    let items = vec![
        orb_plain,
        orb_blizz,
        mk_item("Spirit Shield", "shield", 35, 55, 2, 35, 0),
        mk_item("Tiara", "helm", 20, 20, 2, 30, 0),
        mk_item("Armor", "armor", 20, 20, 1, 40, 0),
        mk_item("Amulet", "amulet", 10, 0, 2, 30, 0),
        mk_item("Belt", "belt", 0, 0, 0, 30, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Boots", "boots", 0, 0, 0, 40, 0),
        mk_item("Ring A", "ring", 10, 0, 0, 20, 0),
        mk_item("Ring B", "ring", 10, 0, 0, 20, 0),
    ];

    let c = BuildConstraints {
        min_pr: 75,
        skill_slack: 2,
        limit: 2,
        ..test_constraints()
    };
    let res = optimize_builds_core(&items, &[], &c).unwrap();
    assert_eq!(res.len(), 2);
    assert_eq!(res[0].items[0].name, "Sorc +2/+3 Blizz Orb");
    assert_eq!(res[1].items[0].name, "Sorc +3 Orb");
    assert!(res[0].blizz_avg > res[1].blizz_avg);
    // Both builds have effective CM = +2 (orb_blizz: 2+1-1? wait: 9+1=10 vs 10+0=10 -> equal CM pierce).
    let expected_blizz_0 = crate::eval::blizzard_damage(res[0].skills + 3).1;
    assert!((res[0].blizz_avg - expected_blizz_0).abs() < 1e-6);
}

#[test]
fn test_belt_potion_capacity_and_defense_break_ties_and_prevent_domination() {
    let mut heavy = mk_item("Goldwrap (Heavy Belt)", "belt", 0, 0, 0, 0, 30);
    heavy.defense = 35;
    heavy.belt_slots = 12;
    heavy.req_str = 45;

    let mut battle = mk_item("Goldwrap (Battle Belt)", "belt", 0, 0, 0, 0, 30);
    battle.defense = 89;
    battle.belt_slots = 16;
    battle.req_str = 88;

    let mut heavy_low_def = mk_item("Goldwrap (Heavy Belt) Low", "belt", 0, 0, 0, 0, 30);
    heavy_low_def.defense = 25;
    heavy_low_def.belt_slots = 12;
    heavy_low_def.req_str = 45;

    let mut tal_belt = mk_item("Tal Belt", "belt", 0, 0, 0, 0, 15);
    tal_belt.dex_bonus = 20;
    tal_belt.belt_slots = 16;
    tal_belt.defense = 37;
    tal_belt.req_str = 46;

    let mut monarch = mk_item("Spirit Shield", "shield", 35, 55, 2, 35, 0);
    monarch.req_str = 156;

    let items = vec![
        heavy_low_def,
        heavy,
        battle,
        tal_belt,
        mk_item("Spirit Sword", "weapon", 35, 55, 2, 0, 0),
        monarch,
        mk_item("Tiara", "helm", 20, 0, 2, 30, 0),
        mk_item("Armor", "armor", 20, 20, 1, 40, 0),
        mk_item("Amulet", "amulet", 10, 0, 2, 30, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Boots", "boots", 0, 0, 0, 40, 0),
        mk_item("Ring A", "ring", 10, 0, 0, 20, 0),
        mk_item("Ring B", "ring", 10, 0, 0, 20, 0),
    ];

    let c = BuildConstraints {
        mode: "mf".to_string(),
        min_fhr: 60,
        min_pr: 0,
        limit: 2,
        ..test_constraints()
    };
    let res = optimize_builds_core(&items, &[], &c).unwrap();
    assert_eq!(res.len(), 2);
    // At base_str=156, Battle Belt (req_str=88 -> 0) dominates both Heavy Belts; Layer 1 = [Battle Belt, Tal Belt].
    assert_eq!(res[0].evaluated_candidates, 2);
    assert_eq!(res[0].items[5].name, "Goldwrap (Battle Belt)");
    assert_eq!(res[1].items[5].name, "Tal Belt");

    // When base_str=45, Battle Belt (req_str=88) no longer dominates Heavy Belt (req_str=45 -> 0),
    // and only Heavy Belt is equippable without extra Str.
    let c_low_str = BuildConstraints {
        base_str: 45,
        limit: 3,
        ..c
    };
    // Swap Spirit Monarch (req_str=156) with a low-str shield so Heavy Belt is feasible while Battle Belt is not.
    let mut low_str_items = items;
    low_str_items[5].req_str = 45;
    let res_low = optimize_builds_core(&low_str_items, &[], &c_low_str).unwrap();
    assert_eq!(res_low[0].items[5].name, "Goldwrap (Heavy Belt)");
}

#[test]
fn test_ring_pruning_keeps_single_dominated_partner_and_drops_double_dominated() {
    let mut ring_a = mk_item("Ring A", "ring", 10, 0, 0, 0, 0);
    ring_a.life = 0;
    let mut ring_b = mk_item("Ring B", "ring", 9, 0, 0, 0, 0);
    ring_b.life = 0;
    let mut ring_c = mk_item("Ring C", "ring", 8, 0, 0, 0, 0);
    ring_c.life = 0;
    let mut ring_fr = mk_item("Ring FR", "ring", 0, 0, 0, 0, 0);
    ring_fr.fr = 30;
    ring_fr.life = 0;
    let mut ring_lr = mk_item("Ring LR", "ring", 0, 0, 0, 0, 0);
    ring_lr.lr = 30;
    ring_lr.life = 0;

    // Rest of gear provides 86 FCR (35 + 31 + 20 = 86), so only Ring A (10) + Ring B (9) reaches 105 FCR.
    let items = vec![
        mk_item("Spirit Sword", "weapon", 35, 55, 2, 0, 0),
        mk_item("Spirit Shield", "shield", 31, 55, 2, 35, 0),
        mk_item("Tiara", "helm", 0, 0, 2, 30, 0),
        mk_item("Smoke", "armor", 0, 20, 0, 50, 0),
        mk_item("Amulet", "amulet", 0, 0, 2, 30, 0),
        mk_item("Belt", "belt", 0, 0, 0, 30, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Boots", "boots", 0, 0, 0, 40, 0),
        ring_a,
        ring_fr,
        ring_lr,
        ring_b,
        ring_c,
    ];

    for limit in [2, 3] {
        let c = BuildConstraints {
            min_fcr: 105,
            min_pr: 0,
            limit,
            ..test_constraints()
        };
        let res = optimize_builds_core(&items, &[], &c).unwrap();
        assert_eq!(res.len(), 1, "limit={limit} must keep Ring B as partner for Ring A");
        let ring_names: HashSet<&str> = res[0].items[8..10].iter().map(|i| i.name.as_str()).collect();
        assert_eq!(ring_names, HashSet::from(["Ring A", "Ring B"]));
    }

    // Ring C is strictly dominated by both Ring A and Ring B, so pruning with limit=2 drops Ring C.
    let pruned = prune_slot_items(
        items
            .into_iter()
            .filter(|i| i.slot == "ring")
            .collect(),
        2,
        true,
        156,
        0,
    );
    let pruned_names: HashSet<&str> = pruned.iter().map(|i| i.name.as_str()).collect();
    assert!(pruned_names.contains("Ring A"));
    assert!(pruned_names.contains("Ring B"));
    assert!(pruned_names.contains("Ring FR"));
    assert!(pruned_names.contains("Ring LR"));
    assert!(!pruned_names.contains("Ring C"));
}

struct SplitMix64(u64);

impl SplitMix64 {
    fn next_u64(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9e37_79b9_7f4a_7c15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        z ^ (z >> 31)
    }

    fn gen_range(&mut self, lo: i32, hi_inclusive: i32) -> i32 {
        let span = (hi_inclusive - lo + 1) as u64;
        lo + (self.next_u64() % span) as i32
    }

    fn pick<T: Copy>(&mut self, slice: &[T]) -> T {
        let idx = (self.next_u64() as usize) % slice.len();
        slice[idx]
    }
}

fn score_summary(mode: SearchMode, sum: &crate::eval::EvalSummary) -> BuildScore {
    let eff_blizz_sk = sum.skills + sum.blizz_skills;
    let res_sum = sum.fr + sum.lr + sum.cr + sum.pr;
    match mode {
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
    }
}

fn validate_and_score_result(
    res: &BuildResult,
    c: &BuildConstraints,
    mode: SearchMode,
) -> BuildScore {
    let gear = res.items.iter().fold(Stats::default(), |acc, i| acc.add(i.stats()));
    let all_sk_non_wep: i32 = res
        .items
        .iter()
        .filter(|i| !i.is_weapon_or_shield())
        .map(|i| i.all_skills)
        .sum();
    let charm_refs: Vec<&CharmSpec> = res.charms.iter().collect();
    let charm_slots: i32 = charm_refs.iter().map(|ch| ch.size).sum();
    assert!(charm_slots <= c.max_charm_slots);

    let mut seen_uids = HashSet::new();
    let mut charm_str = 0;
    let mut charm_dex = 0;
    for ch in &charm_refs {
        if let Some(uid) = ch.unique_id {
            assert!(seen_uids.insert(uid), "duplicate unique charm id {uid}");
        }
        charm_str += ch.str_bonus;
        charm_dex += ch.dex_bonus;
    }

    let reqs = res
        .items
        .iter()
        .fold((0, 0), |acc, it| merge_reqs(acc, item_eff_reqs(it)));
    assert!(c.base_str + gear.str_bonus + charm_str >= reqs.0);
    assert!(c.base_dex + gear.dex_bonus + charm_dex >= reqs.1);

    let sum = eval_build_summary(gear, all_sk_non_wep, &charm_refs, c);
    assert!(sum.fcr >= c.min_fcr);
    assert!(sum.fhr >= c.min_fhr);
    assert!(sum.fr >= c.min_fr && sum.lr >= c.min_lr && sum.cr >= c.min_cr && sum.pr >= c.min_pr);
    score_summary(mode, &sum)
}

fn brute_force_top_scores(
    items: &[ItemSpec],
    charms: &[CharmSpec],
    c: &BuildConstraints,
    mode: SearchMode,
) -> Vec<BuildScore> {
    let valid_item = |i: &ItemSpec| c.allow_mf || i.mf == 0;
    let groups: Vec<Vec<&ItemSpec>> = EQUIP_SLOTS
        .iter()
        .map(|&slot| {
            items
                .iter()
                .filter(|i| i.slot == slot && valid_item(i))
                .collect()
        })
        .collect();
    if groups.iter().any(|g| g.is_empty()) {
        return Vec::new();
    }
    let rings: Vec<&ItemSpec> = items
        .iter()
        .filter(|i| i.slot == "ring" && valid_item(i))
        .collect();
    if rings.len() < 2 {
        return Vec::new();
    }
    let pool: Vec<&CharmSpec> = charms
        .iter()
        .filter(|ch| (c.allow_mf || ch.mf == 0) && ch.light_skills == 0)
        .collect();

    let mut best_by_sig: HashMap<BuildSig, BuildScore> = HashMap::new();
    let mut idxs = vec![0usize; groups.len()];
    loop {
        let slot_items: Vec<&ItemSpec> = groups.iter().enumerate().map(|(g, v)| v[idxs[g]]).collect();
        for ri in 0..rings.len() {
            for rj in (ri + 1)..rings.len() {
                let mut loadout = slot_items.clone();
                loadout.push(rings[ri]);
                loadout.push(rings[rj]);

                let gear = loadout
                    .iter()
                    .fold(Stats::default(), |acc, i| acc.add(i.stats()));
                if gear.fcr < c.min_fcr {
                    continue;
                }
                let (cap_fr, cap_lr, cap_cr, cap_pr) = res_caps(gear);
                if c.min_fr > cap_fr
                    || c.min_lr > cap_lr
                    || c.min_cr > cap_cr
                    || c.min_pr > cap_pr
                {
                    continue;
                }
                let reqs = loadout
                    .iter()
                    .fold((0, 0), |acc, it| merge_reqs(acc, item_eff_reqs(it)));
                let all_sk_non_wep: i32 = loadout
                    .iter()
                    .filter(|i| !i.is_weapon_or_shield())
                    .map(|i| i.all_skills)
                    .sum();
                let item_names: Vec<String> = loadout.iter().map(|i| i.name.clone()).collect();

                let mut best_for_gear: Option<(BuildSig, BuildScore)> = None;
                let mask_limit = 1usize << pool.len();
                for mask in 0..mask_limit {
                    let mut used_slots = 0;
                    let mut c_str = 0;
                    let mut c_dex = 0;
                    let mut uids = HashSet::new();
                    let mut valid_subset = true;
                    let mut chosen: Vec<&CharmSpec> = Vec::new();
                    for (ci, &ch) in pool.iter().enumerate() {
                        if (mask & (1 << ci)) != 0 {
                            used_slots += ch.size;
                            if used_slots > c.max_charm_slots {
                                valid_subset = false;
                                break;
                            }
                            if let Some(uid) = ch.unique_id
                                && !uids.insert(uid)
                            {
                                valid_subset = false;
                                break;
                            }
                            c_str += ch.str_bonus;
                            c_dex += ch.dex_bonus;
                            chosen.push(ch);
                        }
                    }
                    if !valid_subset {
                        continue;
                    }
                    if c.base_str + gear.str_bonus + c_str < reqs.0
                        || c.base_dex + gear.dex_bonus + c_dex < reqs.1
                    {
                        continue;
                    }
                    let sum = eval_build_summary(gear, all_sk_non_wep, &chosen, c);
                    if sum.fhr < c.min_fhr
                        || sum.fr < c.min_fr
                        || sum.lr < c.min_lr
                        || sum.cr < c.min_cr
                        || sum.pr < c.min_pr
                    {
                        continue;
                    }
                    let score = score_summary(mode, &sum);
                    let sig = (sum.skills, sum.fcr_bp, sum.fhr_bp, sum.mf, item_names.clone());
                    if best_for_gear
                        .as_ref()
                        .is_none_or(|(_, best)| score > *best)
                    {
                        best_for_gear = Some((sig, score));
                    }
                }
                if let Some((sig, score)) = best_for_gear {
                    best_by_sig
                        .entry(sig)
                        .and_modify(|cur| {
                            if score > *cur {
                                *cur = score;
                            }
                        })
                        .or_insert(score);
                }
            }
        }

        let mut pos = groups.len();
        while pos > 0 {
            pos -= 1;
            idxs[pos] += 1;
            if idxs[pos] < groups[pos].len() {
                break;
            }
            idxs[pos] = 0;
            if pos == 0 {
                let mut scores: Vec<BuildScore> = best_by_sig.into_values().collect();
                scores.sort_by_key(|&s| Reverse(s));
                if c.limit > 0 {
                    scores.truncate(c.limit);
                }
                return scores;
            }
        }
    }
}

fn gen_random_case(rng: &mut SplitMix64, seed_idx: usize) -> (Vec<ItemSpec>, Vec<CharmSpec>, BuildConstraints, SearchMode) {
    let mut items = Vec::new();
    for &slot in EQUIP_SLOTS {
        let count = rng.gen_range(1, 2) as usize;
        for j in 0..count {
            let mut it = mk_item(
                &format!("{slot}_{j}_{seed_idx}"),
                slot,
                rng.pick(&[0, 5, 10, 20, 35]),
                rng.pick(&[0, 10, 20, 55]),
                rng.gen_range(0, 2),
                rng.gen_range(0, 25),
                rng.pick(&[0, 0, 15, 35]),
            );
            it.blizz_skills = rng.pick(&[0, 0, 1]);
            it.life = rng.pick(&[0, 20, 40]);
            it.mana = rng.pick(&[0, 20, 50]);
            it.str_bonus = rng.pick(&[0, 0, 10, 20]);
            it.dex_bonus = rng.pick(&[0, 0, 10]);
            it.req_str = rng.pick(&[0, 45, 88, 120]);
            it.req_dex = rng.pick(&[0, 0, 25, 45]);
            it.fr += rng.gen_range(0, 15);
            it.lr += rng.gen_range(0, 15);
            it.pr += rng.gen_range(0, 15);
            if slot == "belt" {
                it.belt_slots = rng.pick(&[8, 12, 16]);
            }
            it.defense = rng.gen_range(10, 100);
            items.push(it);
        }
    }
    let ring_count = rng.gen_range(3, 4) as usize;
    for j in 0..ring_count {
        let mut r = mk_item(
            &format!("ring_{j}_{seed_idx}"),
            "ring",
            rng.pick(&[0, 9, 10]),
            0,
            rng.pick(&[0, 0, 1]),
            rng.gen_range(0, 15),
            rng.pick(&[0, 10, 25]),
        );
        r.str_bonus = rng.pick(&[0, 10, 20]);
        r.dex_bonus = rng.pick(&[0, 10]);
        r.fr += rng.gen_range(0, 20);
        r.lr += rng.gen_range(0, 20);
        r.pr += rng.gen_range(0, 20);
        r.life = rng.pick(&[0, 15, 30]);
        items.push(r);
    }

    let charm_count = rng.gen_range(5, 6) as usize;
    let mut charms = Vec::new();
    for j in 0..charm_count {
        let size = rng.pick(&[1, 2, 3]);
        let uid = match j {
            0 if rng.gen_range(0, 2) == 0 => Some(1),
            1 if rng.gen_range(0, 2) == 0 => Some(1),
            _ => None,
        };
        charms.push(CharmSpec {
            name: format!("ch_{j}_{seed_idx}"),
            size,
            loc: "inv".to_string(),
            skills: if size == 3 { rng.pick(&[0, 1]) } else { 0 },
            fhr: rng.pick(&[0, 5, 12]),
            fr: rng.gen_range(0, 20),
            lr: rng.gen_range(0, 20),
            cr: rng.gen_range(0, 20),
            pr: rng.gen_range(0, 20),
            mf: rng.pick(&[0, 5, 7]),
            life: rng.pick(&[0, 15, 20]),
            mana: rng.pick(&[0, 10, 17]),
            str_bonus: rng.pick(&[0, 0, 5, 15]),
            dex_bonus: rng.pick(&[0, 0, 5, 15]),
            unique_id: uid,
            ..Default::default()
        });
    }

    let (mode_str, mode) = match seed_idx % 3 {
        0 => ("power", SearchMode::Power),
        1 => ("mf", SearchMode::Mf),
        _ => ("max-res", SearchMode::MaxRes),
    };
    let c = BuildConstraints {
        mode: mode_str.to_string(),
        min_fcr: rng.pick(&[0, 37, 63]),
        min_fhr: rng.pick(&[0, 20, 42, 60]),
        min_fr: rng.pick(&[0, 40, 75]),
        min_lr: rng.pick(&[0, 40, 75]),
        min_cr: rng.pick(&[0, 20, 50]),
        min_pr: rng.pick(&[0, 20, 50]),
        max_charm_slots: rng.gen_range(5, 9),
        allow_mf: rng.gen_range(0, 3) != 0,
        base_str: rng.pick(&[60, 80, 110]),
        base_dex: rng.pick(&[0, 15, 30]),
        limit: rng.gen_range(1, 3) as usize,
        ..test_constraints()
    };
    (items, charms, c, mode)
}

#[test]
#[ignore = "Step 0 regression guard: fails until exact charm picker and exact top-N search are implemented"]
fn test_exhaustive_brute_force_matches_optimizer_on_random_pools() {
    let mut rng = SplitMix64(0x5eed_cafe_1234_5678);
    let mut mismatches = Vec::new();
    for seed_idx in 0..40 {
        let (items, charms, c, mode) = gen_random_case(&mut rng, seed_idx);
        let expected = brute_force_top_scores(&items, &charms, &c, mode);
        let actual_res = optimize_builds_core(&items, &charms, &c).unwrap();
        let actual: Vec<BuildScore> = actual_res
            .iter()
            .map(|r| validate_and_score_result(r, &c, mode))
            .collect();
        if actual != expected {
            mismatches.push(format!(
                "seed={seed_idx} mode={} limit={}: actual={:?} expected={:?}",
                c.mode, c.limit, actual, expected
            ));
        }
    }
    assert!(
        mismatches.is_empty(),
        "optimizer diverged from exhaustive brute force in {} / 40 cases:\n{}",
        mismatches.len(),
        mismatches.join("\n")
    );
}
