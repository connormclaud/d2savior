use super::*;
use crate::types::{equipped_hand_weapon, mk_test_item as mk_item, test_constraints};

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
    let c_ok = test_constraints();
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
    // At base_str=156 with limit=2, Battle Belt and Heavy Belt both have MF=30 and fill the top 2,
    // allowing Tal Belt (MF=15 < 30) to be pruned by nth_main_score while Heavy Belt Low (2 dominators) was pruned upfront.
    assert_eq!(res[0].evaluated_candidates, 2);
    assert_eq!(res[0].items[5].name, "Goldwrap (Battle Belt)");
    assert_eq!(res[1].items[5].name, "Goldwrap (Heavy Belt)");

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
    let mut ring_d = mk_item("Ring D", "ring", 7, 0, 0, 0, 0);
    ring_d.life = 0;
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
        ring_d,
    ];

    for limit in [1, 2, 3] {
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

    // With limit=1 (threshold 2), Ring C and Ring D (>=2 dominators) are dropped while Ring B (1 dominator) stays.
    let rings_only: Vec<ItemSpec> = items.into_iter().filter(|i| i.slot == "ring").collect();
    let pruned1 = prune_slot_items(
        rings_only.clone(),
        1,
        true,
        156,
        0,
        OffenseProfile::Caster,
        105,
    );
    let names1: HashSet<&str> = pruned1.iter().map(|i| i.name.as_str()).collect();
    assert!(names1.contains("Ring A") && names1.contains("Ring B"));
    assert!(names1.contains("Ring FR") && names1.contains("Ring LR"));
    assert!(!names1.contains("Ring C") && !names1.contains("Ring D"));

    // With limit=2 (threshold 3), Ring C (2 dominators: A, B) stays for #2 pair (A+C), while Ring D (3 dominators) drops.
    let pruned2 = prune_slot_items(rings_only, 2, true, 156, 0, OffenseProfile::Caster, 105);
    let names2: HashSet<&str> = pruned2.iter().map(|i| i.name.as_str()).collect();
    assert!(names2.contains("Ring C"));
    assert!(!names2.contains("Ring D"));
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

fn validate_and_score_result(
    res: &BuildResult,
    c: &BuildConstraints,
    mode: SearchMode,
) -> BuildScore {
    let class = CharClass::from_id(c.char_class).unwrap();
    let offense = OffenseProfile::parse(&c.offense, class).unwrap();
    let item_refs: Vec<&ItemSpec> = res.items.iter().collect();
    let (gear, all_sk_non_wep, reqs) = compute_effective_gear_stats_and_reqs(&item_refs);
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

    assert!(c.base_str + gear.str_bonus + charm_str >= reqs.0);
    assert!(c.base_dex + gear.dex_bonus + charm_dex >= reqs.1);

    let hand = equipped_hand_weapon(&item_refs);
    let sum = eval_build_summary(gear, all_sk_non_wep, hand, &charm_refs, c);
    assert!(c.allow_mf || sum.mf == 0);
    assert!(sum.fcr >= c.min_fcr);
    assert!(sum.fhr >= c.min_fhr);
    assert!(sum.fr >= c.min_fr && sum.lr >= c.min_lr && sum.cr >= c.min_cr && sum.pr >= c.min_pr);
    score_eval_summary(mode, offense, &sum, c)
}

const TEST_EQUIP_SLOTS: &[&str] = &[
    "weapon", "shield", "helm", "armor", "amulet", "belt", "gloves", "boots",
];

fn brute_force_top_scores(
    items: &[ItemSpec],
    charms: &[CharmSpec],
    c: &BuildConstraints,
    mode: SearchMode,
) -> Vec<BuildScore> {
    let class = CharClass::from_id(c.char_class).unwrap();
    let offense = OffenseProfile::parse(&c.offense, class).unwrap();
    let require_shield = offense.requires_shield();
    let norm = normalize_set_items(items, c.allow_mf, require_shield, c.fixed_gear);
    let items = norm.as_slice();
    let valid_item = |i: &ItemSpec| c.allow_mf || i.mf == 0;
    let empty_shield = ItemSpec::empty("shield");
    let empty_weapon = ItemSpec::empty("weapon");
    let empty_ring = ItemSpec::empty("ring");

    let mut w1h: Vec<ItemSpec> = items
        .iter()
        .filter(|i| i.slot == "weapon" && valid_item(i))
        .cloned()
        .collect();
    let mut shs: Vec<ItemSpec> = items
        .iter()
        .filter(|i| i.slot == "shield" && valid_item(i))
        .cloned()
        .collect();
    let w2h: Vec<ItemSpec> = if require_shield {
        Vec::new()
    } else {
        items
            .iter()
            .filter(|i| i.slot == "weapon2h" && valid_item(i))
            .cloned()
            .collect()
    };
    if !shs.is_empty() && empty_dominators(&w1h, c.base_str, c.base_dex, offense, c.min_fcr) == 0 {
        w1h.push(empty_weapon.clone());
    }
    if !require_shield
        && !w1h.is_empty()
        && empty_dominators(&shs, c.base_str, c.base_dex, offense, c.min_fcr) == 0
    {
        shs.push(empty_shield.clone());
    }
    let mut hand_pairs: Vec<(ItemSpec, ItemSpec)> = Vec::new();
    for w in &w1h {
        for s in &shs {
            hand_pairs.push((w.clone(), s.clone()));
        }
    }
    for w in w2h {
        hand_pairs.push((w, empty_shield.clone()));
    }
    if !require_shield
        && !hand_pairs.iter().any(|(a, b)| {
            let comb = a.stats().add(b.stats()).for_offense(offense, c.min_fcr);
            let reqs = normalize_reqs(
                merge_reqs(item_eff_reqs(a), item_eff_reqs(b)),
                c.base_str,
                c.base_dex,
            );
            a.set_group == 0
                && b.set_group == 0
                && a.weapon_class() == WeaponClass::OneHandSwing
                && a.wsm == 0
                && dominates_empty(comb, reqs)
        })
    {
        hand_pairs.push((empty_weapon, empty_shield));
    }

    let empty_singles: Vec<ItemSpec> = SINGLE_SLOTS.iter().map(|s| ItemSpec::empty(s)).collect();
    let groups: Vec<Vec<ItemSpec>> = SINGLE_SLOTS
        .iter()
        .enumerate()
        .map(|(idx, &slot)| {
            let mut v: Vec<ItemSpec> = items
                .iter()
                .filter(|i| i.slot == slot && valid_item(i))
                .cloned()
                .collect();
            if empty_dominators(&v, c.base_str, c.base_dex, offense, c.min_fcr) == 0 {
                v.push(empty_singles[idx].clone());
            }
            v
        })
        .collect();
    let mut rings: Vec<ItemSpec> = items
        .iter()
        .filter(|i| i.slot == "ring" && valid_item(i))
        .cloned()
        .collect();
    let ring_dom = empty_dominators(&rings, c.base_str, c.base_dex, offense, c.min_fcr);
    for _ in 0..2usize.saturating_sub(ring_dom) {
        rings.push(empty_ring.clone());
    }
    let pool: Vec<&CharmSpec> = charms
        .iter()
        .filter(|ch| {
            (c.allow_mf || ch.mf == 0)
                && (!class.excludes_light_skill_charms() || ch.light_skills == 0)
        })
        .collect();

    let mut best_by_sig: HashMap<BuildSig, BuildScore> = HashMap::new();
    let mut idxs = vec![0usize; groups.len()];
    loop {
        let slot_items: Vec<&ItemSpec> = groups.iter().enumerate().map(|(g, v)| &v[idxs[g]]).collect();
        for (h1, h2) in &hand_pairs {
            for ri in 0..rings.len() {
                for rj in (ri + 1)..rings.len() {
                    let loadout = [
                        h1,
                        h2,
                        slot_items[0],
                        slot_items[1],
                        slot_items[2],
                        slot_items[3],
                        slot_items[4],
                        slot_items[5],
                        &rings[ri],
                        &rings[rj],
                    ];

                    let (gear, all_sk_non_wep, reqs) =
                        compute_effective_gear_stats_and_reqs(&loadout);
                    if (!c.allow_mf && gear.mf > 0) || gear.fcr < c.min_fcr {
                        continue;
                    }
                    let (cap_fr, cap_lr, cap_cr, cap_pr) = res_caps(gear, c);
                    if c.min_fr > cap_fr
                        || c.min_lr > cap_lr
                        || c.min_cr > cap_cr
                        || c.min_pr > cap_pr
                    {
                        continue;
                    }
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
                        let hand = h1.hand_weapon();
                        let sum = eval_build_summary(gear, all_sk_non_wep, hand, &chosen, c);
                        if (!c.allow_mf && sum.mf > 0)
                            || sum.fhr < c.min_fhr
                            || sum.fr < c.min_fr
                            || sum.lr < c.min_lr
                            || sum.cr < c.min_cr
                            || sum.pr < c.min_pr
                        {
                            continue;
                        }
                        let score = score_eval_summary(mode, offense, &sum, c);
                        let eff_fcr_bp = if offense.uses_fcr() { sum.fcr_bp } else { 0 };
                        let sig = (sum.skills, eff_fcr_bp, sum.fhr_bp, sum.mf, item_names.clone());
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
    for &slot in TEST_EQUIP_SLOTS {
        let count = rng.gen_range(1, 3) as usize;
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
    let ring_count = rng.gen_range(3, 6) as usize;
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

    let charm_count = rng.gen_range(5, 9) as usize;
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
        max_charm_slots: rng.pick(&[3, 4, 5, 6, 8]),
        allow_mf: rng.gen_range(0, 3) != 0,
        base_str: rng.pick(&[60, 80, 110]),
        base_dex: rng.pick(&[0, 15, 30]),
        limit: rng.gen_range(1, 3) as usize,
        ..test_constraints()
    };
    (items, charms, c, mode)
}

fn run_exhaustive_brute_force_seeds(seed_count: usize) {
    let mut rng = SplitMix64(0x5eed_cafe_1234_5678);
    let mut mismatches = Vec::new();
    for seed_idx in 0..seed_count {
        let (items, charms, c, mode) = gen_random_case(&mut rng, seed_idx);
        let expected: Vec<i32> = brute_force_top_scores(&items, &charms, &c, mode)
            .into_iter()
            .map(|s| s.primary)
            .collect();
        let actual_res = optimize_builds_core(&items, &charms, &c).unwrap();
        let actual: Vec<i32> = actual_res
            .iter()
            .map(|r| validate_and_score_result(r, &c, mode).primary)
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
        "optimizer diverged from exhaustive brute force in {} / {seed_count} cases:\n{}",
        mismatches.len(),
        mismatches.join("\n")
    );
}

#[test]
fn test_exhaustive_brute_force_matches_optimizer_on_random_pools() {
    run_exhaustive_brute_force_seeds(60);
}

#[test]
#[ignore = "slow 400-seed oracle (~200s debug); run with cargo test -- --ignored"]
fn test_exhaustive_brute_force_matches_optimizer_on_400_random_pools() {
    run_exhaustive_brute_force_seeds(400);
}

#[test]
fn test_empty_slot_fallback_allows_missing_shield_belt_and_rings() {
    let items = vec![
        mk_item("Spirit Sword", "weapon", 35, 55, 2, 0, 0),
        mk_item("Tiara", "helm", 20, 0, 2, 20, 0),
        mk_item("Vipermagi", "armor", 30, 0, 1, 35, 0),
        mk_item("Amulet", "amulet", 10, 0, 2, 20, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Boots", "boots", 0, 0, 0, 40, 0),
        mk_item("SoJ", "ring", 0, 0, 1, 0, 0),
    ];
    let c = BuildConstraints {
        min_fcr: 105,
        min_fhr: 42,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        ..test_constraints()
    };
    let res = optimize_builds_core(&items, &[], &c).unwrap();
    assert_eq!(res.len(), 1);
    assert_eq!(res[0].items.len(), 10);
    assert_eq!(res[0].items[1].name, "(empty)");
    assert_eq!(res[0].items[1].slot, "shield");
    assert_eq!(res[0].items[5].name, "(empty)");
    assert_eq!(res[0].items[5].slot, "belt");
    assert_eq!(res[0].items[8].name, "SoJ");
    assert_eq!(res[0].items[9].name, "(empty)");
    assert_eq!(res[0].items[9].slot, "ring");

    // Also works when an existing shield is too heavy (req_str > base_str) and no charms cover it.
    let mut monarch = mk_item("Monarch", "shield", 35, 55, 2, 35, 0);
    monarch.req_str = 156;
    let mut with_heavy_shield = items;
    with_heavy_shield.push(monarch);
    let c_low_str = BuildConstraints {
        base_str: 60,
        ..c
    };
    let res_low = optimize_builds_core(&with_heavy_shield, &[], &c_low_str).unwrap();
    assert_eq!(res_low.len(), 1);
    assert_eq!(res_low[0].items[1].name, "(empty)");
}

#[test]
fn test_two_handed_weapon_competes_and_excludes_bo_all_skills() {
    let mut mang_song = mk_item("Mang Song's Lesson", "weapon2h", 30, 0, 5, 0, 0);
    mang_song.req_str = 44;

    let mut weak_orb = mk_item("Weak Orb", "weapon", 20, 0, 2, 0, 0);
    weak_orb.sorc_skills = 0;
    let weak_shield = mk_item("Weak Shield", "shield", 20, 0, 2, 10, 0);

    let items = vec![
        mang_song,
        weak_orb,
        weak_shield,
        mk_item("Tiara", "helm", 20, 0, 2, 30, 0),
        mk_item("Vipermagi", "armor", 30, 0, 1, 35, 0),
        mk_item("Amulet", "amulet", 15, 0, 2, 30, 0),
        mk_item("Belt", "belt", 0, 0, 0, 30, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Boots", "boots", 0, 0, 0, 40, 0),
        mk_item("Ring A", "ring", 10, 0, 0, 20, 0),
        mk_item("Ring B", "ring", 10, 0, 0, 20, 0),
    ];
    let c = BuildConstraints {
        min_fcr: 105,
        min_fhr: 0,
        min_pr: 75,
        limit: 2,
        ..test_constraints()
    };
    let res = optimize_builds_core(&items, &[], &c).unwrap();
    assert_eq!(res.len(), 2);
    assert_eq!(res[0].items[0].name, "Mang Song's Lesson");
    assert_eq!(res[0].items[0].slot, "weapon2h");
    assert_eq!(res[0].items[1].name, "(empty)");
    assert_eq!(res[0].items[1].slot, "shield");
    assert_eq!(res[0].skills, 10);
    // Mang Song's +5 all_skills must NOT count toward Battle Orders (only helm 2 + armor 1 + amulet 2 = 5 -> BO lvl 4 + 5 = 9).
    assert_eq!(res[0].bo_lvl, 9);
    assert_eq!(res[1].items[0].name, "Weak Orb");
    assert_eq!(res[1].items[1].name, "Weak Shield");
}

#[test]
fn test_top_n_finds_builds_beyond_old_slack_and_prunes_by_nth_score() {
    let base = vec![
        mk_item("Spirit Shield", "shield", 35, 55, 2, 35, 0),
        mk_item("Tiara", "helm", 20, 0, 2, 20, 0),
        mk_item("Smoke", "armor", 0, 20, 0, 50, 0),
        mk_item("Belt", "belt", 0, 0, 0, 30, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 30, 0),
        mk_item("Boots", "boots", 0, 0, 0, 40, 0),
        mk_item("Ring A", "ring", 10, 0, 0, 20, 0),
        mk_item("Ring B", "ring", 10, 0, 0, 20, 0),
    ];

    // Power mode with limit=3 returns all 3 distinct skill tiers (10, 7, 5), even though gap > 1.
    let mut pow_items = base.clone();
    pow_items.push(mk_item("Wep +5", "weapon", 35, 55, 5, 0, 0));
    pow_items.push(mk_item("Wep +2", "weapon", 35, 55, 2, 0, 0));
    pow_items.push(mk_item("Wep +0", "weapon", 35, 55, 0, 0, 0));
    pow_items.push(mk_item("Amu", "amulet", 10, 0, 1, 30, 0));

    let c_pow = BuildConstraints {
        mode: "power".to_string(),
        min_pr: 75,
        limit: 3,
        ..test_constraints()
    };
    let res_pow = optimize_builds_core(&pow_items, &[], &c_pow).unwrap();
    let pow_skills: Vec<i32> = res_pow.iter().map(|r| r.skills).collect();
    assert_eq!(pow_skills, vec![10, 7, 5]);

    // MF mode with limit=3 returns all 3 MF tiers (50, 10, 0), even though gap > 15.
    let mut mf_items = base;
    mf_items.push(mk_item("Wep", "weapon", 35, 55, 2, 0, 0));
    mf_items.push(mk_item("Amu 50MF", "amulet", 10, 0, 1, 30, 50));
    mf_items.push(mk_item("Amu 10MF", "amulet", 10, 0, 1, 30, 10));
    mf_items.push(mk_item("Amu 0MF", "amulet", 10, 0, 1, 30, 0));

    let c_mf = BuildConstraints {
        mode: "mf".to_string(),
        min_pr: 75,
        limit: 3,
        ..test_constraints()
    };
    let res_mf = optimize_builds_core(&mf_items, &[], &c_mf).unwrap();
    let mf_vals: Vec<i32> = res_mf.iter().map(|r| r.mf).collect();
    assert_eq!(mf_vals, vec![50, 10, 0]);
}

#[test]
fn test_exhaustive_brute_force_max_res_negative_res_overcap() {
    let mut base = Vec::new();
    let mut a1 = mk_item("Armor CapCR", "armor", 0, 0, 1, 0, 0);
    a1.req_str = 10;
    a1.fr = 55;
    a1.lr = 75;
    a1.cr = 75;
    a1.pr = 75;
    base.push(a1);

    let mut a2 = mk_item("Armor OverCR", "armor", 0, 0, 0, 0, 0);
    a2.req_str = 10;
    a2.fr = 55;
    a2.lr = 75;
    a2.cr = 100;
    a2.pr = 75;
    base.push(a2);

    let charms = vec![
        CharmSpec {
            name: "Cold Rupture STR".to_string(),
            size: 1,
            loc: "inv".to_string(),
            unique_id: Some(901),
            str_bonus: 10,
            cr: -40,
            ..Default::default()
        },
        CharmSpec {
            name: "FR SC".to_string(),
            size: 1,
            loc: "inv".to_string(),
            fr: 20,
            ..Default::default()
        },
        CharmSpec {
            name: "CR SC".to_string(),
            size: 1,
            loc: "inv".to_string(),
            cr: 25,
            ..Default::default()
        },
    ];
    let c = BuildConstraints {
        mode: "max-res".to_string(),
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        base_hell_res: 0,
        base_str: 0,
        base_dex: 0,
        max_charm_slots: 2,
        limit: 2,
        ..test_constraints()
    };

    let expected: Vec<i32> = brute_force_top_scores(&base, &charms, &c, SearchMode::MaxRes)
        .into_iter()
        .map(|s| s.primary)
        .collect();
    let actual_res = optimize_builds_core(&base, &charms, &c).unwrap();
    let actual: Vec<i32> = actual_res
        .iter()
        .map(|r| validate_and_score_result(r, &c, SearchMode::MaxRes).primary)
        .collect();
    assert_eq!(actual, vec![285, 265]);
    assert_eq!(actual, expected);

    // Also fuzz 60 small random MaxRes pools that include negative-resist charms.
    let mut rng = SplitMix64(0xdead_beef_9876_5432);
    for seed_idx in 0..60 {
        let mut items = Vec::new();
        for &slot in TEST_EQUIP_SLOTS {
            let count = if slot == "armor" || slot == "helm" { 2 } else { 1 };
            for j in 0..count {
                let mut it = mk_item(&format!("{slot}_{j}"), slot, 0, 0, rng.gen_range(0, 2), 0, 0);
                it.fr = rng.gen_range(20, 60);
                it.lr = rng.gen_range(20, 60);
                it.cr = rng.gen_range(30, 95);
                it.pr = rng.gen_range(20, 60);
                it.str_bonus = rng.pick(&[0, 10]);
                if slot == "helm" {
                    it.req_str = rng.pick(&[0, 10]);
                }
                items.push(it);
            }
        }
        items.push(mk_item("ring_0", "ring", 0, 0, 0, 0, 0));
        items.push(mk_item("ring_1", "ring", 0, 0, 0, 0, 0));

        let mut fuzz_charms = Vec::new();
        for j in 0..5 {
            let size = rng.pick(&[1, 2]);
            let is_sunder = j == 0;
            fuzz_charms.push(CharmSpec {
                name: format!("ch_{j}"),
                size,
                loc: "inv".to_string(),
                unique_id: if is_sunder { Some(901) } else { None },
                str_bonus: if is_sunder { 10 } else { rng.pick(&[0, 5]) },
                fr: if is_sunder { 0 } else { rng.gen_range(0, 18) },
                lr: if is_sunder { 0 } else { rng.gen_range(0, 18) },
                cr: if is_sunder { -rng.pick(&[30, 40, 70]) } else { rng.gen_range(0, 22) },
                pr: if is_sunder { 0 } else { rng.gen_range(0, 18) },
                fhr: rng.pick(&[0, 5]),
                ..Default::default()
            });
        }
        let fc = BuildConstraints {
            mode: "max-res".to_string(),
            min_fcr: 0,
            min_fhr: rng.pick(&[0, 5]),
            min_fr: 0,
            min_lr: 0,
            min_cr: rng.pick(&[0, 20]),
            min_pr: 0,
            base_hell_res: 0,
            base_str: 0,
            max_charm_slots: rng.pick(&[2, 3, 4]),
            limit: rng.gen_range(1, 3) as usize,
            ..test_constraints()
        };
        let exp: Vec<i32> = brute_force_top_scores(&items, &fuzz_charms, &fc, SearchMode::MaxRes)
            .into_iter()
            .map(|s| s.primary)
            .collect();
        let act: Vec<i32> = optimize_builds_core(&items, &fuzz_charms, &fc)
            .unwrap()
            .iter()
            .map(|r| validate_and_score_result(r, &fc, SearchMode::MaxRes).primary)
            .collect();
        assert_eq!(act, exp, "seed={seed_idx}");
    }
}

#[test]
fn test_cold_sunder_forced_with_min_cr_fallback_and_max_res_optional() {
    let mut armor_hi_skill = mk_item("HighSkill Armor", "armor", 30, 0, 2, 0, 0);
    armor_hi_skill.fr = 150;
    armor_hi_skill.lr = 150;
    armor_hi_skill.cr = 150;
    armor_hi_skill.pr = 150;

    let mut armor_cr = mk_item("ColdRes Armor", "armor", 30, 0, 1, 0, 0);
    armor_cr.fr = 150;
    armor_cr.lr = 150;
    armor_cr.cr = 220; // With base_hell_res=-70 and sunder -75 => cr_raw = 75!
    armor_cr.pr = 150;

    let mut shield = mk_item("Spirit Shield", "shield", 35, 60, 2, 0, 0);
    shield.mf = 0;
    let wep = mk_item("Hoto", "weapon", 40, 0, 3, 0, 0);
    let items = vec![wep, shield, armor_hi_skill.clone(), armor_cr];

    let sunder = CharmSpec {
        name: "Cold Rupture".to_string(),
        size: 3,
        loc: "inv".to_string(),
        cr: -75,
        unique_id: Some(401),
        cold_sunder: true,
        ..Default::default()
    };
    let sunder_worse = CharmSpec {
        name: "Cold Rupture -88".to_string(),
        size: 3,
        loc: "stash".to_string(),
        cr: -88,
        unique_id: Some(401),
        cold_sunder: true,
        ..Default::default()
    };
    let charms = vec![sunder.clone(), sunder_worse];

    // 1. When 75 CR is achievable WITH Cold Rupture, min_cr=75 is strictly honored (picks ColdRes Armor).
    let c_pow = BuildConstraints {
        mode: "power".to_string(),
        min_fcr: 105,
        min_fhr: 60,
        min_fr: 75,
        min_lr: 75,
        min_cr: 75,
        min_pr: 75,
        max_charm_slots: 6,
        limit: 1,
        ..test_constraints()
    };
    let res_met = optimize_builds_core(&items, &charms, &c_pow).unwrap();
    assert_eq!(res_met.len(), 1);
    assert!(res_met[0].charms.iter().any(|ch| ch.name == "Cold Rupture"));
    assert_eq!(res_met[0].cr, 75);
    assert_eq!(res_met[0].items[3].name, "ColdRes Armor");

    // 2. When 75 CR is UNACHIEVABLE with Cold Rupture (only HighSkill Armor exists -> cr_raw = 5),
    //    both Power and Mf fall back to relaxing min_cr while still forcing Cold Rupture.
    let items_unachievable = vec![
        mk_item("Hoto", "weapon", 40, 0, 3, 0, 0),
        mk_item("Spirit Shield", "shield", 35, 60, 2, 0, 0),
        armor_hi_skill,
    ];
    let res_fallback_pow = optimize_builds_core(&items_unachievable, &charms, &c_pow).unwrap();
    assert_eq!(res_fallback_pow.len(), 1);
    assert!(
        res_fallback_pow[0]
            .charms
            .iter()
            .any(|ch| ch.name == "Cold Rupture")
    );
    assert_eq!(res_fallback_pow[0].cr, 5);
    assert!(res_fallback_pow[0].fr >= 75 && res_fallback_pow[0].lr >= 75 && res_fallback_pow[0].pr >= 75);

    let c_mf = BuildConstraints {
        mode: "mf".to_string(),
        ..c_pow.clone()
    };
    let res_fallback_mf = optimize_builds_core(&items_unachievable, &charms, &c_mf).unwrap();
    assert_eq!(res_fallback_mf.len(), 1);
    assert!(
        res_fallback_mf[0]
            .charms
            .iter()
            .any(|ch| ch.name == "Cold Rupture")
    );
    assert_eq!(res_fallback_mf[0].cr, 5);

    // 3. MaxRes mode keeps Cold Rupture optional so CR stays capped at 75.
    let c_max = BuildConstraints {
        mode: "max-res".to_string(),
        ..c_pow
    };
    let res_max = optimize_builds_core(&items_unachievable, &charms, &c_max).unwrap();
    assert_eq!(res_max.len(), 1);
    assert!(!res_max[0].charms.iter().any(|ch| ch.cold_sunder));
    assert_eq!(res_max[0].cr, 75);
}

#[test]
fn test_leveling_res_and_smite_modes_and_require_shield() {
    let mut darkglow = mk_item("Darkglow", "armor", 0, 0, 0, 0, 0);
    darkglow.max_fr = 5;
    darkglow.max_lr = 5;
    darkglow.max_cr = 5;
    darkglow.max_pr = 5;

    let mut spirit_shroud = mk_item("The Spirit Shroud", "armor", 0, 0, 1, 0, 0);
    spirit_shroud.cbf = 1;

    let mut smoke = mk_item("Smoke", "armor", 0, 20, 0, 50, 0);
    smoke.defense = 400;

    let mut goblin_toe = mk_item("Goblin Toe", "boots", 0, 0, 0, 0, 0);
    goblin_toe.cb = 25;

    let mut black_flail = mk_item("Black", "weapon", 0, 0, 0, 0, 0);
    black_flail.ias = 15;
    black_flail.cb = 40;

    let mut kinemil = mk_item("Kinemil's Awl", "weapon2h", 0, 0, 0, 0, 0);
    kinemil.primary_skill = 6;

    let mut pal_shield = mk_item("Rondache", "shield", 0, 0, 0, 44, 0);
    pal_shield.fr = 44;
    pal_shield.lr = 44;
    pal_shield.cr = 44;
    pal_shield.pr = 44;

    let items = vec![
        darkglow,
        spirit_shroud,
        smoke,
        goblin_toe,
        black_flail,
        kinemil,
        pal_shield,
        mk_item("Amulet", "amulet", 0, 0, 0, 40, 0),
        mk_item("Belt", "belt", 0, 0, 0, 40, 0),
    ];

    // LevelingRes caps res score at 75, so once 75/75/75/75 is achieved via Rondache + Amulet + Belt (124 res -> capped 75 in Normal),
    // Spirit Shroud (+1 all_skills, CBF) beats Darkglow (+5 max_res).
    let c_lvl_res = BuildConstraints {
        char_class: 3,
        use_bo: false,
        base_hell_res: 0,
        mode: "leveling-res".to_string(),
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        limit: 3,
        ..Default::default()
    };
    let res_lvl = optimize_builds_core(&items, &[], &c_lvl_res).unwrap();
    assert!(!res_lvl.is_empty());
    assert_eq!(res_lvl[0].items[3].name, "The Spirit Shroud");
    assert!(res_lvl[0].cbf);

    // Smite offense profile requires a shield (excludes Kinemil's Awl weapon2h) and equips Black + Rondache + Goblin Toe.
    let c_smite = BuildConstraints {
        mode: "leveling".to_string(),
        offense: "smite".to_string(),
        ..c_lvl_res
    };
    let res_smite = optimize_builds_core(&items, &[], &c_smite).unwrap();
    assert!(!res_smite.is_empty());
    assert_eq!(res_smite[0].items[0].name, "Black");
    assert_eq!(res_smite[0].items[1].name, "Rondache");
    assert_eq!(res_smite[0].cb, 65);
    assert_eq!(res_smite[0].ias, 15);
    assert!(
        res_smite
            .iter()
            .all(|r| r.items[0].slot != "weapon2h" && r.items[1].name != "(empty)")
    );
}

#[test]
fn test_exhaustive_brute_force_paladin_leveling_modes() {
    let mut rng = SplitMix64(0x9a1a_d100_cafe_babe);
    let mut mismatches = Vec::new();
    for seed_idx in 0..60 {
        let mut items = Vec::new();
        for &slot in TEST_EQUIP_SLOTS {
            let count = rng.gen_range(1, 3) as usize;
            for j in 0..count {
                let mut it = mk_item(
                    &format!("pal_{slot}_{j}_{seed_idx}"),
                    slot,
                    rng.pick(&[0, 10, 20]),
                    rng.pick(&[0, 10, 20]),
                    rng.pick(&[0, 1]),
                    rng.gen_range(0, 25),
                    0,
                );
                it.pal_skills = rng.pick(&[0, 0, 1]);
                it.primary_skill = rng.pick(&[0, 0, 2, 4]);
                it.ias = rng.pick(&[0, 10, 20]);
                it.cb = rng.pick(&[0, 15, 25]);
                it.cbf = rng.pick(&[0, 0, 1]);
                it.pdr_pct = rng.pick(&[0, 10]);
                it.life_leech = rng.pick(&[0, 5]);
                it.max_fr = rng.pick(&[0, 0, 5]);
                it.frw = rng.pick(&[0, 10, 20]);
                it.life = rng.pick(&[0, 20]);
                it.str_bonus = rng.pick(&[0, 10]);
                it.dex_bonus = rng.pick(&[0, 10]);
                it.req_str = rng.pick(&[0, 45, 75]);
                it.req_dex = rng.pick(&[0, 20]);
                it.defense = rng.gen_range(5, 80);
                if matches!(slot, "gloves" | "belt" | "helm") && j == 0 && rng.gen_range(0, 2) == 0 {
                    it.set_group = 1;
                    it.set_item_id = match slot {
                        "gloves" => 101,
                        "belt" => 102,
                        _ => 103,
                    };
                    let mut b2 = ItemSpec::empty("2pc");
                    b2.ias = rng.pick(&[0, 20, 30]);
                    b2.fr = rng.pick(&[0, 15]);
                    b2.life = rng.pick(&[0, 25]);
                    let mut b3 = ItemSpec::empty("3pc");
                    b3.all_skills = rng.pick(&[0, 1]);
                    it.set_bonuses = vec![(2, b2), (3, b3)];
                }
                items.push(it);
            }
        }
        items.push(mk_item(&format!("w2h_{seed_idx}"), "weapon2h", 0, 0, 1, 10, 0));
        items.push(mk_item(&format!("r0_{seed_idx}"), "ring", 10, 0, 0, 15, 0));
        let mut r1 = mk_item(&format!("r1_{seed_idx}"), "ring", 0, 0, 1, 10, 0);
        if rng.gen_range(0, 2) == 0 {
            r1.set_group = 1;
            r1.set_item_id = 104;
            let mut b2 = ItemSpec::empty("2pc");
            b2.life = 20;
            r1.set_bonuses = vec![(2, b2)];
        }
        items.push(r1);

        let charms: Vec<CharmSpec> = (0..5)
            .map(|j| CharmSpec {
                name: format!("pch_{j}_{seed_idx}"),
                size: rng.pick(&[1, 2, 3]),
                loc: "inv".to_string(),
                skills: if j == 0 { 1 } else { 0 },
                fhr: rng.pick(&[0, 5, 12]),
                frw: rng.pick(&[0, 3, 5]),
                fr: rng.gen_range(0, 18),
                lr: rng.gen_range(0, 18),
                cr: rng.gen_range(0, 18),
                pr: rng.gen_range(0, 18),
                life: rng.pick(&[0, 10, 15]),
                str_bonus: rng.pick(&[0, 5]),
                ..Default::default()
            })
            .collect();

        let (mode_str, mode, offense_str) = match seed_idx % 5 {
            0 => ("leveling", SearchMode::Leveling, "caster"),
            1 => ("leveling", SearchMode::Leveling, "melee"),
            2 => ("leveling-res", SearchMode::LevelingRes, "smite"),
            3 => ("leveling", SearchMode::Leveling, "smite"),
            _ => ("max-res", SearchMode::MaxRes, "caster"),
        };
        let c = BuildConstraints {
            char_class: CharClass::PALADIN_ID,
            use_bo: false,
            offense: offense_str.to_string(),
            base_hell_res: 0,
            mode: mode_str.to_string(),
            min_fcr: rng.pick(&[0, 9]),
            min_fhr: rng.pick(&[0, 7, 15, 27]),
            min_fr: rng.pick(&[0, 30]),
            min_lr: rng.pick(&[0, 30]),
            min_cr: rng.pick(&[0, 30]),
            min_pr: 0,
            max_charm_slots: rng.pick(&[3, 4, 6]),
            base_str: rng.pick(&[50, 70]),
            base_dex: rng.pick(&[20, 35]),
            limit: rng.gen_range(1, 3) as usize,
            ..Default::default()
        };
        let expected: Vec<BuildScore> = brute_force_top_scores(&items, &charms, &c, mode);
        let actual: Vec<BuildScore> = optimize_builds_core(&items, &charms, &c)
            .unwrap()
            .iter()
            .map(|r| validate_and_score_result(r, &c, mode))
            .collect();
        let top_prefix = |scores: &[BuildScore]| -> Vec<(i32, i32, i32)> {
            scores
                .iter()
                .map(|s| match mode {
                    SearchMode::MaxRes => (s.primary, s.secondary, 0),
                    _ => (s.primary, s.secondary, s.tertiary),
                })
                .collect()
        };
        if top_prefix(&actual) != top_prefix(&expected) {
            mismatches.push(format!(
                "seed={seed_idx} mode={mode_str} offense={offense_str}: actual={actual:?} expected={expected:?}"
            ));
        }
    }
    assert!(
        mismatches.is_empty(),
        "Paladin optimizer diverged from brute force:\n{}",
        mismatches.join("\n")
    );
}

#[test]
fn test_fixed_gear_keeps_zero_stat_equipped_items() {
    let bow = mk_item("Raven Claw", "weapon2h", 0, 0, 0, 0, 0);
    let amulet = mk_item("Angelic Wings", "amulet", 0, 0, 0, 0, 0);
    let helm = mk_item("Tarnhelm", "helm", 0, 0, 1, 0, 25);
    let armor = mk_item("Stealth", "armor", 25, 25, 0, 0, 0);
    let belt = mk_item("Sigon's Wrap", "belt", 0, 0, 0, 0, 0);
    let gloves = mk_item("Sigon's Gage", "gloves", 0, 0, 0, 0, 0);
    let boots = mk_item("Tearhaunch", "boots", 0, 0, 0, 10, 0);
    let ring1 = mk_item("Angelic Halo", "ring", 0, 0, 0, 0, 0);
    let ring2 = mk_item("Manald Heal", "ring", 0, 0, 0, 0, 0);

    let items = vec![bow, helm, armor, amulet, belt, gloves, boots, ring1, ring2];
    let c_fixed = BuildConstraints {
        char_class: 3,
        use_bo: false,
        base_hell_res: 0,
        mode: "leveling-res".to_string(),
        min_fcr: 0,
        min_fhr: 15,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        limit: 3,
        fixed_gear: true,
        ..Default::default()
    };
    let res = optimize_builds_core(&items, &[], &c_fixed).unwrap();
    assert_eq!(res.len(), 1);
    assert_eq!(res[0].items[0].name, "Raven Claw");
    assert_eq!(res[0].items[1].name, "(empty)");
    assert_eq!(res[0].items[4].name, "Angelic Wings");
    assert_eq!(res[0].items[5].name, "Sigon's Wrap");
    assert_eq!(res[0].items[6].name, "Sigon's Gage");
    assert_eq!(res[0].items[8].name, "Angelic Halo");
    assert_eq!(res[0].items[9].name, "Manald Heal");
}

#[test]
fn test_set_bonus_2pc_unlocks_ias_and_ignores_duplicate_rings() {
    let mut b2_ias = ItemSpec::empty("2pc");
    b2_ias.ias = 30;
    let mut b3_mf = ItemSpec::empty("3pc");
    b3_mf.mf = 50;

    let mut sigon_gloves = mk_item("Sigon's Gage", "gloves", 0, 0, 0, 0, 0);
    sigon_gloves.str_bonus = 10;
    sigon_gloves.set_group = 10;
    sigon_gloves.set_item_id = 35;
    sigon_gloves.set_bonuses = vec![(2, b2_ias)];

    let mut sigon_belt = mk_item("Sigon's Wrap", "belt", 0, 0, 0, 0, 0);
    sigon_belt.fr = 20;
    sigon_belt.life = 20;
    sigon_belt.set_group = 10;
    sigon_belt.set_item_id = 39;

    let mut sigon_boots = mk_item("Sigon's Sabot", "boots", 0, 0, 0, 0, 0);
    sigon_boots.frw = 20;
    sigon_boots.cr = 40;
    sigon_boots.set_group = 10;
    sigon_boots.set_item_id = 38;
    sigon_boots.set_bonuses = vec![(3, b3_mf)];

    let mut magefist = mk_item("Magefist", "gloves", 20, 0, 0, 0, 0);
    magefist.pal_skills = 1;

    let mut halo_1 = mk_item("Angelic Halo A", "ring", 0, 0, 0, 0, 0);
    halo_1.life = 20;
    halo_1.set_group = 20;
    halo_1.set_item_id = 52;
    let mut angel_b2 = ItemSpec::empty("2pc");
    angel_b2.life = 75;
    let mut halo_b2 = ItemSpec::empty("2pc");
    halo_b2.mana = 50;
    let mut halo_2 = mk_item("Angelic Halo B", "ring", 0, 0, 0, 0, 0);
    halo_2.life = 20;
    halo_2.set_group = 20;
    halo_2.set_item_id = 52;
    halo_2.set_bonuses = vec![(2, halo_b2)];

    let mut angel_amu = mk_item("Angelic Wings", "amulet", 0, 0, 0, 0, 0);
    angel_amu.set_group = 20;
    angel_amu.set_item_id = 53;
    angel_amu.set_bonuses = vec![(2, angel_b2)];

    let plain_boots = mk_item("Plain Boots", "boots", 0, 0, 0, 0, 0);
    let armor_res = mk_item("Smoke", "armor", 0, 20, 0, 75, 0);

    let items = vec![
        sigon_gloves,
        magefist,
        sigon_belt,
        sigon_boots,
        plain_boots,
        armor_res,
        halo_1.clone(),
        halo_2.clone(),
    ];
    let c_ias = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        use_bo: false,
        offense: "melee".to_string(),
        allow_mf: false,
        base_hell_res: 0,
        mode: "leveling-res".to_string(),
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 75,
        min_lr: 75,
        min_cr: 75,
        min_pr: 75,
        limit: 3,
        ..Default::default()
    };
    let res = optimize_builds_core(&items, &[], &c_ias).unwrap();
    assert!(!res.is_empty());
    // 1. Sigon's 2pc (+30 IAS = 30 leveling_offense) beats Magefist (+1 skill = 20)
    assert_eq!(res[0].items[6].name, "Sigon's Gage");
    assert_eq!(res[0].items[5].name, "Sigon's Wrap");
    assert_eq!(res[0].ias, 30);
    // 2. allow_mf=false prevents picking Sigon's Sabot when Sigon's Gage + Wrap would trigger 3pc +50% MF
    assert_ne!(res[0].items[7].name, "Sigon's Sabot");
    assert_eq!(res[0].mf, 0);
    // 3. Two identical Angelic Halo rings (set_item_id=52) must NOT unlock 2pc bonuses
    assert_eq!(res[0].life_no_bo, 20 + 20 + 20);
    assert_eq!(res[0].mana_bo, 0);

    // Adding Angelic Wings (distinct set_item_id=53) DOES unlock 2pc +75 Life & +50 Mana!
    let mut items_with_amu = items;
    items_with_amu.push(angel_amu);
    let res_amu = optimize_builds_core(&items_with_amu, &[], &c_ias).unwrap();
    assert_eq!(res_amu[0].items[4].name, "Angelic Wings");
    assert_eq!(res_amu[0].life_no_bo, 20 + 20 + 20 + 75);
    assert_eq!(res_amu[0].mana_bo, 50);

    // 4. Synthetic set items with default `set_item_id == 0` receive distinct negative IDs in
    //    `normalize_set_items` so `single_set_sig` / `pair_set_sig` do not prune one against another.
    let mut anon_a = mk_item("Anon Set Weapon A", "weapon", 0, 0, 0, 0, 0);
    anon_a.life = 10;
    anon_a.set_group = 99;
    let mut anon_b = mk_item("Anon Set Weapon B", "weapon", 0, 0, 0, 0, 0);
    anon_b.life = 5;
    anon_b.set_group = 99;
    let mut anon_shield = mk_item("Anon Set Shield", "shield", 0, 0, 0, 0, 0);
    anon_shield.set_group = 99;
    let mut anon_bonus = ItemSpec::empty("2pc");
    anon_bonus.ias = 20;
    anon_a.set_bonuses = vec![(2, anon_bonus.clone())];
    anon_b.set_bonuses = vec![(2, anon_bonus)];
    let norm = normalize_set_items(&[anon_a, anon_b, anon_shield], true, false, false);
    assert_eq!(norm.len(), 3);
    assert_eq!(norm[0].set_item_id, -1);
    assert_eq!(norm[1].set_item_id, -2);
    assert_eq!(norm[2].set_item_id, -3);
}

#[test]
fn test_power_mode_pruning_respects_primary_skill_bonus() {
    // Regression test: Power mode must include `primary_skill` in `can_prune_by_score`
    // and `item_sort_key` so branches achieving higher `eff_primary` via `primary_skill`
    // are not unsoundly pruned once an incumbent has `primary_skill > 0`.
    let mut helm_incumbent = mk_item("Incumbent Helm", "helm", 0, 0, 2, 0, 0);
    helm_incumbent.primary_skill = 2; // eff_primary = 4, req_str = 0
    let mut helm_high = mk_item("High Primary Helm", "helm", 0, 0, 0, 0, 0);
    helm_high.primary_skill = 6; // eff_primary = 6, req_str = 50
    helm_high.req_str = 50;

    // Two weapons tried at depth 0:
    // `w_fast` (+1 all_skills, 0 str) is sorted first; with `helm_incumbent` it yields eff_primary = 5.
    // `w_str` (+0 skills, +50 str) is tried second; at depth 0 its `all_skills` is 0, so without
    // `primary_skill` in `suf[1]` (`ub_ch`), its upper bound would be `0 + 2 = 2 < cutoff (5)` and
    // prune before reaching `helm_high` (total eff_primary = 6)!
    let w_fast = mk_item("Fast Weapon", "weapon", 0, 0, 1, 0, 0);
    let mut w_str = mk_item("Strength Weapon", "weapon", 0, 0, 0, 0, 0);
    w_str.str_bonus = 50;

    let c = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        use_bo: false,
        base_hell_res: 0,
        mode: "power".to_string(),
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        limit: 1,
        ..Default::default()
    };
    let res = optimize_builds_core(
        &[w_fast, w_str, helm_incumbent, helm_high],
        &[],
        &c,
    )
    .unwrap();
    assert_eq!(res.len(), 1);
    assert_eq!(res[0].items[2].name, "High Primary Helm");
    assert_eq!(res[0].skills + res[0].primary_skill_bonus, 6);
}

#[test]
fn test_prune_candidates_does_not_crowd_out_distinct_names_with_duplicate_rolls() {
    // Regression test: three rolls of "Harlequin Crest" differing in a non-dominating stat
    // (e.g., trade-off between defense and life) must not count as 2 distinct dominator names
    // and prune "Tarnhelm" when `limit == 2`, because all "Harlequin Crest" builds with equal
    // `(skills, fcr_bp, fhr_bp, mf)` collapse to 1 `BuildSig` in `TopResults`.
    let mut shako_a = mk_item("Harlequin Crest", "helm", 0, 0, 2, 0, 50);
    shako_a.defense = 141;
    shako_a.life = 10;
    let mut shako_b = mk_item("Harlequin Crest", "helm", 0, 0, 2, 0, 50);
    shako_b.defense = 130;
    shako_b.life = 20;
    let mut tarnhelm = mk_item("Tarnhelm", "helm", 0, 0, 1, 0, 40);
    tarnhelm.defense = 10;

    let c = BuildConstraints {
        base_hell_res: 0,
        mode: "mf".to_string(),
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        limit: 2,
        ..Default::default()
    };
    let res = optimize_builds_core(&[shako_a, shako_b, tarnhelm], &[], &c).unwrap();
    assert_eq!(res.len(), 2);
    assert_eq!(res[0].items[2].name, "Harlequin Crest");
    assert_eq!(res[1].items[2].name, "Tarnhelm");
}

#[test]
fn test_non_caster_offense_zeroes_fcr_weight_against_manald_heal() {
    // Regression test: for non-caster offense profiles (Melee / Smite), FCR must carry
    // 0 weight in item pruning, ring-pair dedup, and build scoring so Manald Heal (+20 Life,
    // +10% FCR, 20% Mana Regen, 5% Mana Leech) does not beat resist/stat rings like Beast Gyre
    // (+29% LR, +16% CR, +10% FCR) or Angelic Halo (+20 Life, 0% FCR).
    let mut manald_a = mk_item("Manald Heal", "ring", 10, 0, 0, 0, 0);
    manald_a.life = 20;
    let mut manald_b = mk_item("Manald Heal", "ring", 10, 0, 0, 0, 0);
    manald_b.life = 20;

    let mut beast_gyre = mk_item("Beast Gyre", "ring", 10, 0, 0, 0, 0);
    beast_gyre.lr = 29;
    beast_gyre.cr = 16;

    let mut angelic_halo = mk_item("Angelic Halo", "ring", 0, 0, 0, 0, 0);
    angelic_halo.life = 20;

    let c = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        use_bo: false,
        offense: "melee".to_string(),
        base_hell_res: 0,
        mode: "leveling".to_string(),
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        limit: 1,
        ..Default::default()
    };
    // 1. Beast Gyre (+29 LR, +16 CR) + Angelic Halo (+20 Life) beats double Manald Heal
    let res = optimize_builds_core(
        &[angelic_halo.clone(), manald_a.clone(), manald_b, beast_gyre],
        &[],
        &c,
    )
    .unwrap();
    assert_eq!(res.len(), 1);
    let ring_names: Vec<&str> = res[0].items[8..10].iter().map(|i| i.name.as_str()).collect();
    assert!(ring_names.contains(&"Beast Gyre"));
    assert!(ring_names.contains(&"Angelic Halo"));
    assert!(!ring_names.contains(&"Manald Heal"));

    // 2. When resists are already capped (75/75/75/75), Angelic Halo (+20 Life, 0 FCR)
    //    is treated as stat-equivalent to Manald Heal (+20 Life, +10 FCR) for melee.
    let armor_capped = mk_item("Smoke", "armor", 0, 0, 0, 75, 0);
    let res_capped = optimize_builds_core(&[armor_capped, angelic_halo, manald_a], &[], &c).unwrap();
    assert_eq!(res_capped.len(), 1);
}

#[test]
fn test_locality_tiebreaker_order_equipped_inv_stash_shared_mule() {
    // Regression test: when items have identical modeled stats, candidate sorting, pruning,
    // and leaf BuildScore tiebreaking must prefer:
    // Equipped > Swap > Char Inv > Char Stash > Shared Stash > Mule
    // regardless of input order or inactive optimistic set bonuses in `max_total_stats()`.
    let mk_ring = |name: &str, loc: &str| {
        let mut r = mk_item(name, "ring", 0, 0, 0, 0, 0);
        r.loc = loc.to_string();
        r.life = 20;
        r
    };

    let r_mule = mk_ring("Ring Mule", "mule_charms Inv");
    let r_shared = mk_ring("Ring Shared", "Stash Tab 1");
    let r_stash = mk_ring("Ring Char Stash", "smite Stash");
    let r_inv = mk_ring("Ring Char Inv", "smite Inv");
    let r_eq = mk_ring("Ring Equipped", "smite Equipped");

    let c = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        use_bo: false,
        offense: "melee".to_string(),
        base_hell_res: 75,
        mode: "leveling".to_string(),
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 75,
        min_lr: 75,
        min_cr: 75,
        min_pr: 75,
        limit: 1,
        ..Default::default()
    };

    // Pass rings in reverse locality order (Mule first, Equipped last):
    // top 2 rings chosen must be Equipped and Char Inv.
    let res = optimize_builds_core(
        &[
            r_mule.clone(),
            r_shared.clone(),
            r_stash.clone(),
            r_inv.clone(),
            r_eq,
        ],
        &[],
        &c,
    )
    .unwrap();
    assert_eq!(res.len(), 1);
    assert_eq!(res[0].items[8].name, "Ring Equipped");
    assert_eq!(res[0].items[9].name, "Ring Char Inv");

    // Without Equipped, top 2 must be Char Inv and Char Stash.
    let res2 = optimize_builds_core(
        &[r_mule.clone(), r_shared.clone(), r_stash.clone(), r_inv],
        &[],
        &c,
    )
    .unwrap();
    assert_eq!(res2[0].items[8].name, "Ring Char Inv");
    assert_eq!(res2[0].items[9].name, "Ring Char Stash");

    // Without Char Inv, top 2 must be Char Stash and Shared Stash (beating Mule).
    let res3 = optimize_builds_core(&[r_mule, r_shared, r_stash], &[], &c).unwrap();
    assert_eq!(res3[0].items[8].name, "Ring Char Stash");
    assert_eq!(res3[0].items[9].name, "Ring Shared");
}

#[test]
fn test_paladin_dps_zeal_vs_bow_fallback_and_brute_force_parity() {
    let kinemil = ItemSpec {
        name: "Kinemil's Awl".to_string(),
        slot: "weapon2h".to_string(),
        aura_skill_bonus: 6,
        flat_elem_2x: 44, // 6-38 fire
        wep_phys_2x: 68,  // ~34 avg
        wep_str_pct: 100,
        wep_dex_pct: 0,
        wsm: 0,
        wclass: "2hs".to_string(),
        can_zeal: true,
        ..Default::default()
    };
    let fast_1h = ItemSpec {
        name: "Fast Flail".to_string(),
        slot: "weapon".to_string(),
        ias: 20,
        wep_phys_2x: 25,
        wep_str_pct: 100,
        wep_dex_pct: 0,
        wsm: -10,
        wclass: "1hs".to_string(),
        can_zeal: true,
        ..Default::default()
    };
    let thrust_1h = ItemSpec {
        name: "Thrust Spear".to_string(),
        slot: "weapon".to_string(),
        ias: 20,
        wep_phys_2x: 25,
        wep_str_pct: 100,
        wep_dex_pct: 0,
        wsm: -10,
        wclass: "1ht".to_string(),
        can_zeal: true,
        ..Default::default()
    };
    let bow = ItemSpec {
        name: "Raven Claw".to_string(),
        slot: "weapon2h".to_string(),
        wep_phys_2x: 22,
        wep_str_pct: 0,
        wep_dex_pct: 100,
        wsm: 0,
        wclass: "bow".to_string(),
        can_zeal: false,
        ..Default::default()
    };
    let shield = ItemSpec {
        name: "Res Shield".to_string(),
        slot: "shield".to_string(),
        fr: 40,
        lr: 40,
        cr: 40,
        pr: 40,
        ..Default::default()
    };
    let gloves_ias = ItemSpec {
        name: "IAS Gloves".to_string(),
        slot: "gloves".to_string(),
        ias: 20,
        ..Default::default()
    };
    let helm_sk = ItemSpec {
        name: "Skill Helm".to_string(),
        slot: "helm".to_string(),
        all_skills: 1,
        ..Default::default()
    };
    let charms = vec![
        CharmSpec {
            name: "Offensive Aura GC".to_string(),
            size: 3,
            aura_skills: 1,
            ..Default::default()
        },
        CharmSpec {
            name: "Combat GC".to_string(),
            size: 3,
            action_skills: 1,
            ..Default::default()
        },
        CharmSpec {
            name: "Res SC".to_string(),
            size: 1,
            fr: 10,
            lr: 10,
            cr: 10,
            pr: 10,
            ..Default::default()
        },
    ];
    let items = vec![
        kinemil.clone(),
        fast_1h.clone(),
        thrust_1h.clone(),
        bow.clone(),
        shield,
        gloves_ias,
        helm_sk,
    ];
    let mut c = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        offense: "zeal".to_string(),
        mode: "leveling".to_string(),
        base_hell_res: 0,
        base_str: 60,
        base_dex: 20,
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 6,
        limit: 3,
        use_bo: false,
        aura_hit_dmg: (0..=15).map(|b| 350.0 + b as f64 * 40.0).collect(),
        aura_pulse_dps: (0..=15).map(|b| 30.0 + b as f64 * 3.5).collect(),
        action_ed: vec![12; 16],
        action_hits: (0..=15).map(|b| (2 + b).min(5)).collect(),
        has_aura: true,
        ..Default::default()
    };

    // 1. Verify brute-force parity in both Leveling and LevelingRes modes.
    for (mode_str, mode_enum) in [
        ("leveling", SearchMode::Leveling),
        ("leveling-res", SearchMode::LevelingRes),
    ] {
        c.mode = mode_str.to_string();
        let opt = optimize_builds_core(&items, &charms, &c).unwrap();
        let bf = brute_force_top_scores(&items, &charms, &c, mode_enum);
        let opt_scores: Vec<BuildScore> = opt
            .iter()
            .map(|r| {
                let mut sc = validate_and_score_result(r, &c, mode_enum);
                sc.locality = 0;
                sc
            })
            .collect();
        assert_eq!(opt_scores[0], bf[0], "top score mismatch in {mode_str}");
    }

    // 2. Verify bow falls back to Attack (used_zeal == false) and 1hs beats 1ht (F_last 15 vs 17).
    let s = Stats {
        str_bonus: 60,
        dex_bonus: 20,
        ias: 20,
        ..Default::default()
    };
    let (bow_dps, _, _, bow_zeal) = OffenseProfile::Zeal.compute_dps(bow.hand_weapon(), s, &c);
    let (flail_dps, _, _, flail_zeal) =
        OffenseProfile::Zeal.compute_dps(fast_1h.hand_weapon(), s, &c);
    let (thrust_dps, _, _, thrust_zeal) =
        OffenseProfile::Zeal.compute_dps(thrust_1h.hand_weapon(), s, &c);
    assert!(!bow_zeal);
    assert!(flail_zeal && thrust_zeal);
    assert!(flail_dps > thrust_dps, "1hs F_last=15 must out-DPS 1ht F_last=17");
    assert!(flail_dps > bow_dps, "1h Zeal must out-DPS bow Attack fallback");
}
