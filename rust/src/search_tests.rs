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
    let c_ring_1 = BuildConstraints {
        min_fcr: 105,
        min_pr: 0,
        limit: 1,
        ..test_constraints()
    };
    let pruned1 = prune_slot_items(
        rings_only.clone(),
        true,
        SearchMode::Power,
        OffenseProfile::Caster,
        &c_ring_1,
    );
    let names1: HashSet<&str> = pruned1.iter().map(|i| i.name.as_str()).collect();
    assert!(names1.contains("Ring A") && names1.contains("Ring B"));
    assert!(names1.contains("Ring FR") && names1.contains("Ring LR"));
    assert!(!names1.contains("Ring C") && !names1.contains("Ring D"));

    // With limit=2 (threshold 3), Ring C (2 dominators: A, B) stays for #2 pair (A+C), while Ring D (3 dominators) drops.
    let c_ring_2 = BuildConstraints {
        limit: 2,
        ..c_ring_1
    };
    let pruned2 = prune_slot_items(
        rings_only,
        true,
        SearchMode::Power,
        OffenseProfile::Caster,
        &c_ring_2,
    );
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
    assert!(!c.require_cbf || sum.cbf);
    assert!(sum.frw >= c.min_frw);
    assert!(sum.ias >= c.min_ias);
    assert!(sum.cb >= c.min_cb);
    assert!(sum.life_leech + sum.ctc_lifetap_pct.clamp(0, 100) / 2 >= c.min_ll);
    assert!(sum.pdr_pct >= c.min_pdr);
    assert!(sum.mf >= c.min_mf);
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
    let require_melee = offense.requires_melee() && !c.is_hands_fixed();
    let norm = normalize_set_items(
        items,
        c.allow_mf,
        require_shield,
        require_melee,
        |slot| c.is_slot_fixed(slot),
    );
    let items = norm.as_slice();
    let valid_item = |i: &ItemSpec| c.allow_mf || i.mf == 0;
    let empty_shield = ItemSpec::empty("shield");
    let empty_weapon = ItemSpec::empty("weapon");
    let empty_ring = ItemSpec::empty("ring");

    let mut w1h: Vec<ItemSpec> = items
        .iter()
        .filter(|i| {
            i.slot == "weapon" && valid_item(i) && (!require_melee || i.hand_weapon().can_zeal)
        })
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
            .filter(|i| {
                i.slot == "weapon2h"
                    && valid_item(i)
                    && (!require_melee || i.hand_weapon().can_zeal)
            })
            .cloned()
            .collect()
    };
    if !shs.is_empty() && empty_dominators(&w1h, mode, offense, c) == 0 {
        w1h.push(empty_weapon.clone());
    }
    if !require_shield
        && !w1h.is_empty()
        && empty_dominators(&shs, mode, offense, c) == 0
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
            let comb = a.stats().add(b.stats()).for_mode(mode, offense, c);
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
            if empty_dominators(&v, mode, offense, c) == 0 {
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
    let ring_dom = empty_dominators(&rings, mode, offense, c);
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
                            || (c.require_cbf && !sum.cbf)
                            || sum.frw < c.min_frw
                            || sum.ias < c.min_ias
                            || sum.cb < c.min_cb
                            || (sum.life_leech + sum.ctc_lifetap_pct.clamp(0, 100) / 2) < c.min_ll
                            || sum.pdr_pct < c.min_pdr
                            || sum.mf < c.min_mf
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
    let norm = normalize_set_items(&[anon_a, anon_b, anon_shield], true, false, false, |_| false);
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
    let (bow_dps, _, _, _, bow_zeal) = OffenseProfile::Zeal.compute_dps(bow.hand_weapon(), s, &c);
    let (flail_dps, _, _, _, flail_zeal) =
        OffenseProfile::Zeal.compute_dps(fast_1h.hand_weapon(), s, &c);
    let (thrust_dps, _, _, _, thrust_zeal) =
        OffenseProfile::Zeal.compute_dps(thrust_1h.hand_weapon(), s, &c);
    assert!(!bow_zeal);
    assert!(flail_zeal && thrust_zeal);
    assert!(flail_dps > thrust_dps, "1hs F_last=15 must out-DPS 1ht F_last=17");
    assert!(flail_dps > bow_dps, "1h Zeal must out-DPS bow Attack fallback");

    // 3. Verify Zeal cycle IAS BP and rollback/last frames (1hs wsm=0 @ 40% IAS -> BP 32%, 6/11f).
    let sword = ItemSpec {
        name: "Broad Sword".into(),
        slot: "weapon".into(),
        wclass: "1hs".into(),
        wsm: 0,
        can_zeal: true,
        ..Default::default()
    };
    let (_, bp40, f_roll, f_last, used_zeal) =
        OffenseProfile::Zeal.attack_rate_and_frames(sword.hand_weapon(), 40, 5);
    assert!(used_zeal);
    assert_eq!((bp40, f_roll, f_last), (32, 6, 11));
}

#[test]
fn paladin_explosive_arrow_splash_targets_and_brute_force_parity() {
    let spirit = ItemSpec {
        name: "Spirit".into(),
        slot: "weapon".into(),
        all_skills: 2,
        wclass: "1hs".into(),
        wsm: 0,
        wep_phys_2x: 34,
        wep_str_pct: 100,
        can_zeal: true,
        ..Default::default()
    };
    let shield = ItemSpec {
        name: "Sigon's Guard".into(),
        slot: "shield".into(),
        all_skills: 1,
        ..Default::default()
    };
    let raven_claw = ItemSpec {
        name: "Raven Claw".into(),
        slot: "weapon2h".into(),
        wclass: "bow".into(),
        wsm: 0,
        wep_phys_2x: 20,
        wep_dex_pct: 100,
        can_zeal: false,
        splash_fire: true,
        splash_fire_2x: 44, // lvl 3 Exploding Arrow (17-27)
        ..Default::default()
    };
    let items = vec![spirit, shield, raven_claw];
    let mut c = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        offense: "melee".to_string(),
        mode: "leveling".to_string(),
        base_hell_res: 0,
        base_str: 50,
        base_dex: 50,
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 0,
        limit: 2,
        use_bo: false,
        aura_hit_dmg: (0..=10).map(|b| 400.0 + b as f64 * 45.0).collect(),
        aura_pulse_dps: (0..=10).map(|b| 35.0 + b as f64 * 4.0).collect(),
        action_ed: vec![0],
        action_hits: vec![1],
        has_aura: true,
        aura_is_fire: true,
        targets: 1,
        ..Default::default()
    };

    // Low AR (base_dex=50 => 57% melee CTH): auto-hit Exploding Arrow + Holy Fire beats Spirit even at 1 target.
    let res1_low_ar = optimize_builds_core(&items, &[], &c).unwrap();
    assert_eq!(res1_low_ar[0].items[0].name, "Raven Claw");

    // High AR (base_dex=500 => ~93% melee CTH): 1H + shield (+3 skills) beats Raven Claw on single target.
    c.base_dex = 500;
    let res1 = optimize_builds_core(&items, &[], &c).unwrap();
    assert_eq!(res1[0].items[0].name, "Spirit");

    // 3 targets with Holy Fire: Raven Claw fire splash wins and matches brute force.
    c.targets = 3;
    let res3 = optimize_builds_core(&items, &[], &c).unwrap();
    assert_eq!(res3[0].items[0].name, "Raven Claw");
    let bf3 = brute_force_top_scores(&items, &[], &c, SearchMode::Leveling);
    let mut sc3 = validate_and_score_result(&res3[0], &c, SearchMode::Leveling);
    sc3.locality = 0;
    assert_eq!(sc3, bf3[0]);

    // 3 targets with non-fire aura (Holy Freeze/Shock): aura on-hit does NOT splash, Spirit wins.
    c.aura_is_fire = false;
    let res_cold = optimize_builds_core(&items, &[], &c).unwrap();
    assert_eq!(res_cold[0].items[0].name, "Spirit");

    // 3 targets with Holy Fire in Zeal mode: ranged weapons (Raven Claw) are excluded; Spirit Zeals.
    c.aura_is_fire = true;
    c.offense = "zeal".to_string();
    c.action_hits = vec![5; 11];
    let res_zeal = optimize_builds_core(&items, &[], &c).unwrap();
    assert_eq!(res_zeal[0].items[0].name, "Spirit");
    assert!(res_zeal[0].used_zeal);
}

#[test]
fn sorc_blizzard_caster_dps_cold_pct_fcr_and_brute_force_parity() {
    use crate::types::mk_test_item;
    let mut fathom = mk_test_item("Death's Fathom", "weapon", 20, 0, 3, 20, 0);
    fathom.cold_dmg_pct = 25;
    let hoto = mk_test_item("Heart of the Oak", "weapon", 40, 0, 3, 35, 0);
    let mut nightwing = mk_test_item("Nightwing's Veil", "helm", 0, 0, 2, 0, 0);
    nightwing.cold_dmg_pct = 15;
    let shako = mk_test_item("Harlequin Crest", "helm", 0, 0, 2, 0, 50);
    let spirit = mk_test_item("Spirit", "shield", 35, 55, 2, 35, 0);
    let viper = mk_test_item("Skin of the Vipermagi", "armor", 30, 0, 1, 30, 0);
    let arach = mk_test_item("Arachnid Mesh", "belt", 20, 0, 1, 0, 0);
    let trang = mk_test_item("Trang-Oul's Claws", "gloves", 20, 0, 0, 0, 0);
    let items = vec![fathom, hoto, nightwing, shako, spirit, viper, arach, trang];

    let mut c = BuildConstraints {
        char_class: CharClass::SORCERESS_ID,
        offense: "caster".to_string(),
        mode: "power".to_string(),
        base_hell_res: 0,
        min_fcr: 105,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 0,
        limit: 2,
        use_bo: false,
        blizz_dmg: (0..=20).map(|b| 2200.0 + b as f64 * 260.0).collect(),
        filler_dmg: (0..=20).map(|b| 1400.0 + b as f64 * 160.0).collect(),
        filler_is_aoe: false,
        targets: 1,
        ..Default::default()
    };

    let opt = optimize_builds_core(&items, &[], &c).unwrap();
    let bf = brute_force_top_scores(&items, &[], &c, SearchMode::Power);
    let mut sc = validate_and_score_result(&opt[0], &c, SearchMode::Power);
    sc.locality = 0;
    assert_eq!(sc, bf[0]);
    // Death's Fathom (+25% cold) + Nightwing's (+15% cold) must beat HOTO + Shako at 105% FCR.
    let names: Vec<&str> = opt[0].items.iter().map(|i| i.name.as_str()).collect();
    assert!(names.contains(&"Death's Fathom"));
    assert!(names.contains(&"Nightwing's Veil"));
    assert!(opt[0].dps > 0.0);

    // AoE filler (Glacial Spike) scales with targets; single-target filler (Ice Blast) does not.
    let s = Stats {
        all_skills: 10,
        fcr: 105,
        cold_dmg_pct: 40,
        ..Default::default()
    };
    let dps_ib_1 = OffenseProfile::Caster.compute_caster_dps(s, &c);
    c.targets = 3;
    let dps_ib_3 = OffenseProfile::Caster.compute_caster_dps(s, &c);
    c.filler_is_aoe = true;
    let dps_gs_3 = OffenseProfile::Caster.compute_caster_dps(s, &c);
    assert!(dps_ib_3 > dps_ib_1);
    assert!(dps_gs_3 > dps_ib_3);

    // Verify discrete cycle monotonicity across all Sorceress FCR breakpoints (0..=200).
    let mut prev_dps = 0.0_f64;
    for &fcr in &[0, 9, 20, 37, 63, 105, 200] {
        let sf = Stats {
            all_skills: 10,
            fcr,
            cold_dmg_pct: 20,
            ..Default::default()
        };
        let d = OffenseProfile::Caster.compute_caster_dps(sf, &c);
        assert!(d >= prev_dps, "caster DPS must be monotone in FCR: {d} < {prev_dps} at {fcr}");
        prev_dps = d;
    }
}

#[test]
fn test_hard_constraint_floors_and_brute_force_parity() {
    let mut ring_cbf = mk_item("Raven Frost", "ring", 0, 0, 0, 0, 0);
    ring_cbf.cbf = 1;
    let mut ring_ll = mk_item("BK Ring", "ring", 1, 0, 0, 0, 0);
    ring_ll.life_leech = 5;
    let mut ring_plain = mk_item("SOJ", "ring", 1, 0, 0, 0, 0);
    ring_plain.mana = 50;

    let mut helm_cb = mk_item("G-Face", "helm", 0, 0, 30, 0, 0);
    helm_cb.cb = 35;
    let mut helm_pdr = mk_item("Shako", "helm", 2, 0, 0, 0, 50);
    helm_pdr.pdr_pct = 10;

    let mut gloves_ias = mk_item("Laying of Hands", "gloves", 0, 0, 0, 0, 0);
    gloves_ias.ias = 20;
    let mut gloves_plain = mk_item("Magefist", "gloves", 0, 20, 0, 0, 0);
    gloves_plain.life = 20;

    let mut belt_ias = mk_item("Goldwrap", "belt", 0, 0, 0, 0, 30);
    belt_ias.ias = 10;
    let mut belt_pdr = mk_item("String of Ears", "belt", 0, 0, 0, 0, 0);
    belt_pdr.pdr_pct = 15;
    belt_pdr.life_leech = 7;

    let mut boots_frw = mk_item("Natalya's Soul", "boots", 0, 0, 0, 0, 0);
    boots_frw.frw = 40;
    let mut boots_mf = mk_item("War Traveler", "boots", 0, 0, 0, 0, 50);
    boots_mf.frw = 25;

    let items = vec![
        ring_cbf,
        ring_ll,
        ring_plain,
        helm_cb,
        helm_pdr,
        gloves_ias,
        gloves_plain,
        belt_ias,
        belt_pdr,
        boots_frw,
        boots_mf,
    ];

    let ch_frw_1 = CharmSpec {
        name: "Inertia SC 1".to_string(),
        size: 1,
        frw: 5,
        ..Default::default()
    };
    let ch_frw_2 = CharmSpec {
        name: "Inertia SC 2".to_string(),
        size: 1,
        frw: 5,
        ..Default::default()
    };
    let ch_mf_1 = CharmSpec {
        name: "Good Luck SC 1".to_string(),
        size: 1,
        mf: 7,
        ..Default::default()
    };
    let ch_mf_2 = CharmSpec {
        name: "Good Luck SC 2".to_string(),
        size: 1,
        mf: 7,
        ..Default::default()
    };
    let ch_sk = CharmSpec {
        name: "Skiller GC".to_string(),
        size: 3,
        skills: 1,
        ..Default::default()
    };
    let charms = vec![ch_frw_1, ch_frw_2, ch_mf_1, ch_mf_2, ch_sk];

    let base_c = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        offense: "melee".to_string(),
        mode: "leveling".to_string(),
        use_bo: false,
        base_hell_res: 75,
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 5,
        limit: 3,
        ..Default::default()
    };

    // Case 1: CBF + IAS >= 30 + FRW >= 50 (needs 40 from boots + 10 from 2x Inertia SCs).
    let c1 = BuildConstraints {
        require_cbf: true,
        min_ias: 30,
        min_frw: 50,
        ..base_c.clone()
    };
    let opt1 = optimize_builds_core(&items, &charms, &c1).unwrap();
    let bf1 = brute_force_top_scores(&items, &charms, &c1, SearchMode::Leveling);
    assert!(!opt1.is_empty());
    assert_eq!(opt1.len(), bf1.len());
    for (r, exp) in opt1.iter().zip(bf1.iter()) {
        let mut sc = validate_and_score_result(r, &c1, SearchMode::Leveling);
        sc.locality = 0;
        assert_eq!(sc, *exp);
    }

    // Case 2: CB >= 35 + LL >= 7 + PDR >= 15 + MF >= 64 (50 boots + 14 from 2x MF SCs).
    let c2 = BuildConstraints {
        min_cb: 35,
        min_ll: 7,
        min_pdr: 15,
        min_mf: 64,
        ..base_c.clone()
    };
    let opt2 = optimize_builds_core(&items, &charms, &c2).unwrap();
    let bf2 = brute_force_top_scores(&items, &charms, &c2, SearchMode::Leveling);
    assert!(!opt2.is_empty());
    assert_eq!(opt2.len(), bf2.len());
    for (r, exp) in opt2.iter().zip(bf2.iter()) {
        let mut sc = validate_and_score_result(r, &c2, SearchMode::Leveling);
        sc.locality = 0;
        assert_eq!(sc, *exp);
    }

    // Case 3: Impossible FRW floor (needs 60, max is 40 + 10 = 50) returns empty cleanly.
    let c3 = BuildConstraints {
        min_frw: 60,
        ..base_c
    };
    assert!(optimize_builds_core(&items, &charms, &c3).unwrap().is_empty());
}

#[test]
fn test_global_set_bonuses_applied_once_and_respect_constraints() {
    // Sigon's Complete Steel global bonuses: 2pc = +10% LL, 3pc = +100 Def (applied ONCE per set, not per piece).
    let mut g2_ll = ItemSpec::empty("bonus");
    g2_ll.life_leech = 10;
    let mut g3_def = ItemSpec::empty("bonus");
    g3_def.defense = 100;
    let global_bonuses = vec![(2, g2_ll), (3, g3_def)];

    // Sigon's Guard (shield): no item-level set_bonuses, only global_set_bonuses.
    let mut sigon_guard = mk_item("Sigon's Guard", "shield", 1, 0, 0, 0, 0);
    sigon_guard.set_group = 1;
    sigon_guard.set_item_id = 41;
    sigon_guard.global_set_bonuses = global_bonuses.clone();

    // Sigon's Gage (gloves): 2pc item-level +30% IAS + global bonuses.
    let mut sigon_gage = mk_item("Sigon's Gage", "gloves", 0, 0, 0, 0, 0);
    sigon_gage.set_group = 1;
    sigon_gage.set_item_id = 36;
    let mut gage_2pc = ItemSpec::empty("2pc");
    gage_2pc.ias = 30;
    sigon_gage.set_bonuses = vec![(2, gage_2pc)];
    sigon_gage.global_set_bonuses = global_bonuses.clone();

    // Sigon's Wrap (belt): no item-level set_bonuses, only global bonuses.
    let mut sigon_wrap = mk_item("Sigon's Wrap", "belt", 0, 0, 0, 0, 0);
    sigon_wrap.set_group = 1;
    sigon_wrap.set_item_id = 40;
    sigon_wrap.global_set_bonuses = global_bonuses;

    let mut bloodletter = mk_item("Bloodletter", "weapon", 0, 0, 0, 0, 0);
    bloodletter.life_leech = 8;

    let alt_shield = mk_item("Rhyme", "shield", 0, 0, 0, 0, 0);
    let alt_gloves = mk_item("Magefist", "gloves", 0, 20, 0, 0, 0);
    let alt_belt = mk_item("Plain Belt", "belt", 0, 0, 0, 0, 0);

    // 1. 2pc Sigon's (Guard + Gage) + Bloodletter (8% LL) => 18% LL (NOT 28%!).
    let c_2pc = BuildConstraints {
        char_class: 3,
        mode: "leveling".to_string(),
        offense: "melee".to_string(),
        use_bo: false,
        base_hell_res: 0,
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        min_ll: 18,
        limit: 3,
        ..Default::default()
    };
    let items_2pc = vec![
        bloodletter.clone(),
        sigon_guard.clone(),
        alt_shield.clone(),
        sigon_gage.clone(),
        alt_gloves.clone(),
        alt_belt.clone(),
    ];
    let res_2pc = optimize_builds_core(&items_2pc, &[], &c_2pc).unwrap();
    assert!(!res_2pc.is_empty());
    assert_eq!(res_2pc[0].life_leech, 18);
    assert_eq!(res_2pc[0].ias, 30);

    // Brute-force parity check with min_ll satisfied via global set bonus.
    let bf_2pc = brute_force_top_scores(&items_2pc, &[], &c_2pc, SearchMode::Leveling);
    assert_eq!(res_2pc.len(), bf_2pc.len());
    for (r, exp) in res_2pc.iter().zip(bf_2pc.iter()) {
        let mut sc = validate_and_score_result(r, &c_2pc, SearchMode::Leveling);
        sc.locality = 0;
        assert_eq!(sc, *exp);
    }

    // 2. 3pc Sigon's (Guard + Gage + Wrap) still grants +10% LL ONCE (18% total), plus +100 Def ONCE.
    let items_3pc = vec![
        bloodletter,
        sigon_guard.clone(),
        sigon_gage.clone(),
        sigon_wrap.clone(),
    ];
    let c_fixed = BuildConstraints {
        fixed_gear: true,
        min_ll: 0,
        ..c_2pc.clone()
    };
    let res_3pc = optimize_builds_core(&items_3pc, &[], &c_fixed).unwrap();
    assert_eq!(res_3pc.len(), 1);
    assert_eq!(res_3pc[0].life_leech, 18);

    // 3. Set with ONLY global bonuses (Guard + Wrap, neither has item-level set_bonuses) stays active.
    let items_global_only = vec![sigon_guard, sigon_wrap];
    let res_global_only = optimize_builds_core(
        &items_global_only,
        &[],
        &BuildConstraints {
            min_ll: 10,
            ..c_2pc
        },
    )
    .unwrap();
    assert_eq!(res_global_only.len(), 1);
    assert_eq!(res_global_only[0].life_leech, 10);
}

#[test]
fn test_partial_fixed_slots_keeps_only_selected_slots() {
    let bow = mk_item("Raven Claw", "weapon2h", 0, 0, 0, 0, 0);
    let helm_plain = mk_item("Plain Cap", "helm", 0, 0, 0, 0, 0);
    let helm_good = mk_item("Shako", "helm", 0, 0, 2, 0, 0);
    let ring_plain = mk_item("Plain Ring", "ring", 0, 0, 0, 0, 0);
    let ring_good = mk_item("SoJ", "ring", 0, 0, 1, 0, 0);

    // 1. Fixed weapon/hands: keeps non-melee Raven Claw even under zeal offense,
    //    while still optimizing helm and rings.
    let c_wep = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        mode: "leveling".to_string(),
        offense: "zeal".to_string(),
        fixed_slots: vec![
            "weapon".to_string(),
            "weapon2h".to_string(),
            "shield".to_string(),
        ],
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        base_hell_res: 0,
        use_bo: false,
        limit: 1,
        ..Default::default()
    };
    let res_wep = optimize_builds_core(
        &[
            bow.clone(),
            helm_plain.clone(),
            helm_good.clone(),
            ring_plain.clone(),
            ring_good.clone(),
        ],
        &[],
        &c_wep,
    )
    .unwrap();
    assert_eq!(res_wep.len(), 1);
    let names_wep: Vec<&str> = res_wep[0].items.iter().map(|i| i.name.as_str()).collect();
    assert!(names_wep.contains(&"Raven Claw"));
    assert!(names_wep.contains(&"Shako"));
    assert!(names_wep.contains(&"SoJ"));

    // 2. Fixed jewelry (amulet + ring): keeps the single plain ring + empty second ring
    //    (cannot drop plain ring for empty), while optimizing helm.
    let mut ring_plain_req = ring_plain;
    ring_plain_req.req_str = 10;
    let c_jew = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        mode: "leveling".to_string(),
        offense: "caster".to_string(),
        fixed_slots: vec!["amulet".to_string(), "ring".to_string()],
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        base_hell_res: 0,
        base_str: 20,
        use_bo: false,
        limit: 1,
        ..Default::default()
    };
    let res_jew = optimize_builds_core(&[helm_plain, helm_good, ring_plain_req], &[], &c_jew).unwrap();
    assert_eq!(res_jew.len(), 1);
    let names_jew: Vec<&str> = res_jew[0].items.iter().map(|i| i.name.as_str()).collect();
    assert!(names_jew.contains(&"Plain Ring"));
    assert!(names_jew.contains(&"Shako"));
}

#[test]
fn test_stats_for_mode_prunes_irrelevant_stats_and_preserves_tiebreakers() {
    let base_item = ItemSpec {
        name: "Base Helm".to_string(),
        slot: "helm".to_string(),
        all_skills: 2,
        fcr: 20,
        fr: 20,
        life: 40,
        defense: 100,
        belt_slots: 12,
        ..Default::default()
    };

    // 1. Power + Caster DPS (no filler): zeroes mf/fhr/ias/cb/cbf/pdr/ll/frw/off_ed/action/aura/mdr/dr_flat/fire_abs_pct
    //    when unconstrained, while keeping cold_dmg_pct, cm_skills, mana*, life*, defense, belt_slots.
    let mut noisy_power = base_item.clone();
    noisy_power.name = "Noisy Power Helm".to_string();
    noisy_power.life = 30;
    noisy_power.mf = 50;
    noisy_power.fhr = 20;
    noisy_power.frw = 30;
    noisy_power.ias = 20;
    noisy_power.cb = 15;
    noisy_power.cbf = 1;
    noisy_power.pdr_pct = 8;
    noisy_power.life_leech = 7;
    noisy_power.mdr = 12;
    noisy_power.dr_flat = 10;
    noisy_power.fire_abs_pct = 15;
    noisy_power.off_ed = 40;
    noisy_power.flat_phys_2x = 20;
    noisy_power.flat_elem_2x = 20;
    noisy_power.action_skill_bonus = 2;
    noisy_power.aura_skill_bonus = 2;

    let c_power = BuildConstraints {
        mode: "power".to_string(),
        min_fcr: 0,
        min_fhr: 0,
        min_mf: 0,
        allow_mf: true,
        blizz_dmg: vec![100.0; 5],
        limit: 1,
        ..test_constraints()
    };
    let pruned_pow = prune_slot_items(
        vec![base_item.clone(), noisy_power.clone()],
        false,
        SearchMode::Power,
        OffenseProfile::Caster,
        &c_power,
    );
    assert_eq!(pruned_pow.len(), 1);
    assert_eq!(pruned_pow[0].name, "Base Helm");

    // Enabling active constraint/filler_dmg/cold_dmg_pct/cm_skills/mana must keep distinct items.
    for mut c_keep in [
        BuildConstraints { min_mf: 10, ..c_power.clone() },
        BuildConstraints { min_fhr: 10, ..c_power.clone() },
        BuildConstraints { require_cbf: true, ..c_power.clone() },
        BuildConstraints { filler_dmg: vec![50.0; 5], ..c_power.clone() },
    ] {
        c_keep.limit = 1;
        let kept = prune_slot_items(
            vec![base_item.clone(), noisy_power.clone()],
            false,
            SearchMode::Power,
            OffenseProfile::Caster,
            &c_keep,
        );
        assert_eq!(kept.len(), 2);
    }
    let mut cold_helm = base_item.clone();
    cold_helm.name = "Cold Helm".to_string();
    cold_helm.life = 30;
    cold_helm.cold_dmg_pct = 15;
    assert_eq!(
        prune_slot_items(
            vec![base_item.clone(), cold_helm],
            false,
            SearchMode::Power,
            OffenseProfile::Caster,
            &c_power,
        )
        .len(),
        2
    );

    // 2. MaxRes + Caster: zeroes mana*, cold_dmg_pct, cm_skills, mf, mdr, etc.
    let mut noisy_res = base_item.clone();
    noisy_res.name = "Noisy Res Helm".to_string();
    noisy_res.life = 30;
    noisy_res.mana = 100;
    noisy_res.mana_per_lvl = 50;
    noisy_res.ene = 20;
    noisy_res.pct_mana = 25;
    noisy_res.cold_dmg_pct = 20;
    noisy_res.cm_skills = 2;
    noisy_res.mf = 40;
    noisy_res.mdr = 10;
    let c_max_res = BuildConstraints {
        mode: "max-res".to_string(),
        min_fcr: 0,
        min_fhr: 0,
        min_mf: 0,
        allow_mf: true,
        limit: 1,
        ..test_constraints()
    };
    let pruned_res = prune_slot_items(
        vec![base_item.clone(), noisy_res],
        false,
        SearchMode::MaxRes,
        OffenseProfile::Caster,
        &c_max_res,
    );
    assert_eq!(pruned_res.len(), 1);
    assert_eq!(pruned_res[0].name, "Base Helm");

    // 3. Mf + Caster: zeroes ias, cb, cbf, mdr, dr_flat, fire_abs_pct, mana, cold_dmg_pct, while keeping mf.
    let mut noisy_mf = base_item.clone();
    noisy_mf.name = "Noisy MF Helm".to_string();
    noisy_mf.life = 30;
    noisy_mf.ias = 30;
    noisy_mf.cb = 35;
    noisy_mf.cbf = 1;
    noisy_mf.mdr = 10;
    noisy_mf.dr_flat = 10;
    noisy_mf.fire_abs_pct = 10;
    noisy_mf.mana = 80;
    noisy_mf.cold_dmg_pct = 15;
    let c_mf = BuildConstraints {
        mode: "mf".to_string(),
        limit: 1,
        ..test_constraints()
    };
    let pruned_mf = prune_slot_items(
        vec![base_item.clone(), noisy_mf],
        false,
        SearchMode::Mf,
        OffenseProfile::Caster,
        &c_mf,
    );
    assert_eq!(pruned_mf.len(), 1);
    assert_eq!(pruned_mf[0].name, "Base Helm");

    // 4. Empty dominator check ignores permanently dead stats like `mdr`.
    let mdr_only = ItemSpec {
        name: "MDR Only".to_string(),
        slot: "helm".to_string(),
        mdr: 15,
        ..Default::default()
    };
    assert_eq!(
        empty_dominators(&[mdr_only], SearchMode::Power, OffenseProfile::Caster, &c_power),
        0
    );

    // 5. Leveling + Smite preserves pdr_pct, cb, ias, cbf, frw.
    let mut smite_extra = base_item.clone();
    smite_extra.name = "Smite Helm".to_string();
    smite_extra.life = 30;
    smite_extra.pdr_pct = 8;
    let c_smite = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        mode: "leveling".to_string(),
        offense: "smite".to_string(),
        limit: 1,
        ..test_constraints()
    };
    assert_eq!(
        prune_slot_items(
            vec![base_item, smite_extra],
            false,
            SearchMode::Leveling,
            OffenseProfile::Smite,
            &c_smite,
        )
        .len(),
        2
    );
}

#[test]
fn test_item_sort_key_uses_for_mode_so_higher_locality_duplicate_wins() {
    let mut belt_mule = mk_item("Arachnid Mesh", "belt", 20, 20, 1, 0, 0);
    belt_mule.loc = "mule Stash".to_string();
    belt_mule.cold_dmg_pct = 15;
    let mut belt_eq = mk_item("Arachnid Mesh", "belt", 0, 0, 1, 0, 0);
    belt_eq.loc = "Equipped".to_string();

    let mut ring_mule = mk_item("SoJ", "ring", 20, 20, 1, 0, 0);
    ring_mule.loc = "mule Stash".to_string();
    ring_mule.cold_dmg_pct = 15;
    let mut ring_eq = mk_item("SoJ", "ring", 0, 0, 1, 0, 0);
    ring_eq.loc = "Equipped".to_string();

    let c = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        mode: "power".to_string(),
        offense: "melee".to_string(),
        base_hell_res: 75,
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        limit: 1,
        ..test_constraints()
    };
    let res = optimize_builds_core(&[belt_mule, belt_eq, ring_mule, ring_eq], &[], &c).unwrap();
    assert_eq!(res.len(), 1);
    let belt = res[0].items.iter().find(|it| it.slot == "belt").unwrap();
    let ring = res[0].items.iter().find(|it| it.slot == "ring").unwrap();
    assert_eq!(belt.loc, "Equipped");
    assert_eq!(ring.loc, "Equipped");
}

#[test]
fn test_smite_pdr_cap_at_50_ties_and_breaks_on_frw() {
    let mut shield = mk_item("Stormshield", "shield", 0, 0, 0, 0, 0);
    shield.pdr_pct = 35;
    let mut belt_overcap = mk_item("Overcap Belt", "belt", 0, 0, 0, 0, 0);
    belt_overcap.pdr_pct = 30;
    belt_overcap.frw = 0;
    let mut belt_capped_frw = mk_item("Verdungo + FRW", "belt", 0, 0, 0, 0, 0);
    belt_capped_frw.pdr_pct = 15;
    belt_capped_frw.frw = 20;

    let mut c = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        mode: "leveling".to_string(),
        offense: "smite".to_string(),
        base_hell_res: 75,
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        use_bo: false,
        limit: 1,
        ..test_constraints()
    };
    let items = vec![shield, belt_overcap, belt_capped_frw];
    let res = optimize_builds_core(&items, &[], &c).unwrap();
    assert_eq!(res.len(), 1);
    assert_eq!(res[0].pdr_pct, 50);
    assert_eq!(res[0].frw, 20);
    assert_eq!(
        res[0].items.iter().find(|it| it.slot == "belt").unwrap().name,
        "Verdungo + FRW"
    );

    // min_pdr > 50 must be infeasible even when raw item sum reaches 65%.
    c.min_pdr = 55;
    let infeasible = optimize_builds_core(&items, &[], &c).unwrap();
    assert!(infeasible.is_empty());
}

#[test]
fn test_pct_life_breaks_life_bo_tie_and_is_not_pareto_pruned() {
    let helm_plain = mk_item("Plain Helm", "helm", 0, 0, 0, 0, 0);
    let mut helm_jah = mk_item("Jah Helm", "helm", 0, 0, 0, 0, 0);
    helm_jah.pct_life = 5;

    let c = BuildConstraints {
        mode: "power".to_string(),
        base_hell_res: 75,
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        base_life: 1000,
        use_bo: false,
        limit: 1,
        ..test_constraints()
    };
    let items = vec![helm_plain, helm_jah];
    let res = optimize_builds_core(&items, &[], &c).unwrap();
    assert_eq!(res.len(), 1);
    assert_eq!(res[0].life_no_bo, 1050);
    assert_eq!(res[0].life_bo, 1050);
    assert_eq!(
        res[0].items.iter().find(|it| it.slot == "helm").unwrap().name,
        "Jah Helm"
    );
}

#[test]
fn test_ar_cth_angelic_itd_target_def_and_brute_force_parity() {
    // Compare weapons with identical base phys/speed: Plain Sword vs ITD Sword vs -50% Target Def Sword,
    // plus Angelic Wings + Halo (2pc +360 AR set bonus) vs plain jewelry, and +AR Small Charm.
    let plain_wep = ItemSpec {
        name: "Plain Sword".into(),
        slot: "weapon".into(),
        wclass: "1hs".into(),
        wep_phys_2x: 80,
        can_zeal: true,
        ..Default::default()
    };
    let mut eth_wep = plain_wep.clone();
    eth_wep.name = "Eth Sword".into();
    eth_wep.target_def_pct = 25;
    eth_wep.wep_phys_2x = 76; // slightly lower raw dmg, higher CTH

    let mut itd_wep = plain_wep.clone();
    itd_wep.name = "ITD Sword".into();
    itd_wep.itd = 1;
    itd_wep.wep_phys_2x = 70; // lowest raw dmg, but 95% CTH

    let plain_amu = mk_item("Plain Amulet", "amulet", 0, 0, 0, 0, 0);
    let plain_ring = mk_item("Plain Ring", "ring", 0, 0, 0, 0, 0);

    let mut angel_wings = mk_item("Angelic Wings", "amulet", 0, 0, 0, 0, 0);
    angel_wings.set_group = 10;
    angel_wings.set_item_id = 54;
    let mut angel_halo = mk_item("Angelic Halo", "ring", 0, 0, 0, 0, 0);
    angel_halo.set_group = 10;
    angel_halo.set_item_id = 53;
    let mut halo_2pc = ItemSpec::empty("2pc");
    halo_2pc.ar = 360;
    angel_halo.set_bonuses = vec![(2, halo_2pc)];

    let charms = vec![
        CharmSpec {
            name: "Sharp SC 1".into(),
            size: 1,
            ar: 36,
            ..Default::default()
        },
        CharmSpec {
            name: "Balance SC".into(),
            size: 1,
            fhr: 5,
            ..Default::default()
        },
    ];

    let c = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        offense: "zeal".into(),
        mode: "leveling".into(),
        base_hell_res: 75,
        base_str: 50,
        base_dex: 20, // base AR = 85
        target_def: 1200, // Hell-scale target defense -> low hit rate without AR/ITD
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 2,
        limit: 3,
        use_bo: false,
        aura_hit_dmg: vec![0.0, 0.0],
        aura_pulse_dps: vec![0.0, 0.0],
        action_ed: vec![0, 0],
        action_hits: vec![5, 5],
        action_ar_pct: vec![10, 20],
        aura_ar_pct: vec![0, 0],
        has_aura: false,
        ..Default::default()
    };

    // 1. Against trash, Plain Sword CTH is terrible (85 / (85+1200) ~ 6.6%) so ITD Sword wins easily!
    let c_trash = BuildConstraints {
        target_type: "trash".into(),
        ..c.clone()
    };
    let res_wep_trash = optimize_builds_core(
        &[plain_wep.clone(), eth_wep.clone(), itd_wep.clone(), plain_amu.clone(), plain_ring.clone()],
        &charms,
        &c_trash,
    )
    .unwrap();
    assert_eq!(res_wep_trash[0].items[0].name, "ITD Sword");

    // 1b. Against default target_type="champion", ITD is disabled so higher raw-dmg Eth/Plain beat ITD Sword
    //     and match brute-force parity.
    let champ_items = vec![
        plain_wep.clone(),
        eth_wep.clone(),
        itd_wep,
        plain_amu.clone(),
        plain_ring.clone(),
    ];
    let res_wep_champ = optimize_builds_core(&champ_items, &charms, &c).unwrap();
    assert_ne!(res_wep_champ[0].items[0].name, "ITD Sword");
    let bf_champ = brute_force_top_scores(&champ_items, &charms, &c, SearchMode::Leveling);
    let mut top_champ = validate_and_score_result(&res_wep_champ[0], &c, SearchMode::Leveling);
    top_champ.locality = 0;
    assert_eq!(top_champ, bf_champ[0]);

    // 2. Comparing Plain Sword with Angelic 2pc vs Plain Jewelry -> Angelic 2pc + Sharp SC wins via higher AR & DPS,
    //    and matches brute-force search parity!
    let angel_items = vec![
        plain_wep,
        eth_wep,
        plain_amu,
        angel_wings,
        plain_ring,
        angel_halo,
    ];
    let opt = optimize_builds_core(&angel_items, &charms, &c).unwrap();
    let bf = brute_force_top_scores(&angel_items, &charms, &c, SearchMode::Leveling);
    assert!(!opt.is_empty());
    let mut top_sc = validate_and_score_result(&opt[0], &c, SearchMode::Leveling);
    top_sc.locality = 0;
    assert_eq!(top_sc, bf[0]);
    let names: Vec<&str> = opt[0].items.iter().map(|i| i.name.as_str()).collect();
    assert!(names.contains(&"Angelic Wings"));
    assert!(names.contains(&"Angelic Halo"));
    assert!(opt[0].ar > 400);
    assert!(opt[0].charms.iter().any(|ch| ch.name == "Sharp SC 1"));
}

#[test]
fn test_ar_charms_brute_force_parity_all_cases() {
    let assert_bf_parity = |items: &[ItemSpec], charms: &[CharmSpec], c: &BuildConstraints, mode: SearchMode| {
        let opt = optimize_builds_core(items, charms, c).unwrap();
        let bf = brute_force_top_scores(items, charms, c, mode);
        assert!(!opt.is_empty(), "optimize returned no builds");
        assert!(!bf.is_empty(), "brute force returned no builds");
        let mut top_sc = validate_and_score_result(&opt[0], c, mode);
        top_sc.locality = 0;
        assert_eq!(top_sc, bf[0]);
        opt
    };

    let sword = ItemSpec {
        name: "Test Sword".into(),
        slot: "weapon".into(),
        wclass: "1hs".into(),
        wep_phys_2x: 80,
        can_zeal: true,
        ..Default::default()
    };
    let c_base = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        offense: "zeal".into(),
        mode: "leveling".into(),
        base_hell_res: 75,
        base_str: 50,
        base_dex: 20,
        target_def: 1200,
        min_fcr: 0,
        min_fhr: 0,
        min_fr: 0,
        min_lr: 0,
        min_cr: 0,
        min_pr: 0,
        max_charm_slots: 3,
        limit: 3,
        use_bo: false,
        aura_hit_dmg: vec![0.0, 0.0],
        aura_pulse_dps: vec![0.0, 0.0],
        action_ed: vec![0, 20],
        action_hits: vec![5, 5],
        action_ar_pct: vec![10, 20],
        aura_ar_pct: vec![0, 0],
        has_aura: false,
        ..Default::default()
    };

    // 1. Pure +AR Steel GC (+132 AR) beats Combat GC (+1 action skill) in both Leveling & LevelingRes
    //    (when res are capped) because doubling AR dominates +20% ED at low CTH.
    let charms_case1 = vec![
        CharmSpec {
            name: "Combat GC".into(),
            size: 3,
            action_skills: 1,
            ..Default::default()
        },
        CharmSpec {
            name: "Steel GC".into(),
            size: 3,
            ar: 132,
            ..Default::default()
        },
    ];
    let opt1 = assert_bf_parity(std::slice::from_ref(&sword), &charms_case1, &c_base, SearchMode::Leveling);
    assert_eq!(opt1[0].charms[0].name, "Steel GC");
    let c_lres = BuildConstraints {
        mode: "leveling-res".into(),
        ..c_base.clone()
    };
    let opt1_lres = assert_bf_parity(std::slice::from_ref(&sword), &charms_case1, &c_lres, SearchMode::LevelingRes);
    assert_eq!(opt1_lres[0].charms[0].name, "Steel GC");

    // 2. Uncapped res in SearchMode::Leveling: +AR charm beats +Res charm on primary `dps_bucket`.
    let c_uncapped = BuildConstraints {
        base_hell_res: 20,
        max_charm_slots: 1,
        ..c_base.clone()
    };
    let charms_case2 = vec![
        CharmSpec {
            name: "Fine SC".into(),
            size: 1,
            ar: 36,
            ..Default::default()
        },
        CharmSpec {
            name: "Ruby SC".into(),
            size: 1,
            fr: 11,
            ..Default::default()
        },
    ];
    let opt2 = assert_bf_parity(std::slice::from_ref(&sword), &charms_case2, &c_uncapped, SearchMode::Leveling);
    assert_eq!(opt2[0].charms[0].name, "Fine SC");

    // 3. Hybrid +FHR/+AR Steel LC of Balance beats Balance SC + Vita SC when max_charm_slots=2.
    let c_fhr = BuildConstraints {
        min_fhr: 5,
        max_charm_slots: 2,
        ..c_base.clone()
    };
    let charms_case3 = vec![
        CharmSpec {
            name: "Balance SC".into(),
            size: 1,
            fhr: 5,
            ..Default::default()
        },
        CharmSpec {
            name: "Vita SC".into(),
            size: 1,
            life: 20,
            ..Default::default()
        },
        CharmSpec {
            name: "Steel LC of Balance".into(),
            size: 2,
            fhr: 5,
            ar: 60,
            ..Default::default()
        },
    ];
    let opt3 = assert_bf_parity(std::slice::from_ref(&sword), &charms_case3, &c_fhr, SearchMode::Leveling);
    assert_eq!(opt3[0].charms.len(), 1);
    assert_eq!(opt3[0].charms[0].name, "Steel LC of Balance");

    // 4. ITD=1 and same-dps_bucket +AR: Vita SC (+20 life) beats Fine SC (+18 AR) on life_bo tiebreak.
    let mut sword_itd = sword.clone();
    sword_itd.itd = 1;
    let c_1slot = BuildConstraints {
        max_charm_slots: 1,
        ..c_base.clone()
    };
    let charms_case4 = vec![
        CharmSpec {
            name: "Fine SC 18".into(),
            size: 1,
            ar: 18,
            ..Default::default()
        },
        CharmSpec {
            name: "Vita SC 20".into(),
            size: 1,
            life: 20,
            ..Default::default()
        },
    ];
    let opt4_itd = assert_bf_parity(
        std::slice::from_ref(&sword_itd),
        &charms_case4,
        &BuildConstraints {
            target_type: "trash".into(),
            ..c_1slot.clone()
        },
        SearchMode::Leveling,
    );
    assert_eq!(opt4_itd[0].charms[0].name, "Vita SC 20");
    // Under default target_type="champion", ITD=1 is disabled so +18 AR advances dps_bucket and Fine SC 18 wins.
    let opt4_itd_champ = assert_bf_parity(&[sword_itd], &charms_case4, &c_1slot, SearchMode::Leveling);
    assert_eq!(opt4_itd_champ[0].charms[0].name, "Fine SC 18");
    // Same-bucket test without ITD: at high AR (ar=1000, target_def=100 -> cth ~ 91%), +18 AR (<0.2% DPS)
    // stays in the same 2% dps_bucket so Vita SC 20 wins.
    let mut sword_high_ar = sword.clone();
    sword_high_ar.ar = 1000;
    let c_high_ar = BuildConstraints {
        target_def: 100,
        ..c_1slot.clone()
    };
    let opt4_same = assert_bf_parity(&[sword_high_ar], &charms_case4, &c_high_ar, SearchMode::Leveling);
    assert_eq!(opt4_same[0].charms[0].name, "Vita SC 20");

    // 5. +Dex charm advances dps_bucket via Dex->AR over +Life filler charms.
    let c_2slot = BuildConstraints {
        max_charm_slots: 2,
        ..c_base.clone()
    };
    let charms_case5 = vec![
        CharmSpec {
            name: "LC of Dexterity".into(),
            size: 2,
            dex_bonus: 6,
            ..Default::default()
        },
        CharmSpec {
            name: "Vita SC A".into(),
            size: 1,
            life: 20,
            ..Default::default()
        },
        CharmSpec {
            name: "Vita SC B".into(),
            size: 1,
            life: 20,
            ..Default::default()
        },
    ];
    let opt5 = assert_bf_parity(&[sword], &charms_case5, &c_2slot, SearchMode::Leveling);
    assert_eq!(opt5[0].charms.len(), 1);
    assert_eq!(opt5[0].charms[0].name, "LC of Dexterity");
}

#[test]
fn test_damage_charms_and_combat_stats_brute_force_parity() {
    let mut sword = ItemSpec {
        name: "Plain Sword".into(),
        slot: "weapon".into(),
        wclass: "1hs".into(),
        wep_phys_2x: 40,
        can_zeal: true,
        ar: 200,
        ..Default::default()
    };
    sword.cs_oskill = 1;

    let mut lifetap_gloves = mk_item("Dracul's Grasp", "gloves", 0, 0, 0, 0, 0);
    lifetap_gloves.ow = 25;
    lifetap_gloves.ctc_lifetap_pct = 10; // provides 5 effective leech for min_ll
    let plain_gloves = mk_item("Plain Gloves", "gloves", 0, 0, 0, 0, 0);

    let charms = vec![
        CharmSpec {
            name: "Sharp GC".into(),
            size: 3,
            flat_phys_2x: 20,
            ar: 76,
            ..Default::default()
        },
        CharmSpec {
            name: "Flaming SC".into(),
            size: 1,
            flat_fire_2x: 40,
            ..Default::default()
        },
        CharmSpec {
            name: "Shocking SC".into(),
            size: 1,
            flat_elem_2x: 35,
            ..Default::default()
        },
        CharmSpec {
            name: "Pestilent SC".into(),
            size: 1,
            psn_dps_2x: 50,
            ..Default::default()
        },
        CharmSpec {
            name: "AllRes SC".into(),
            size: 1,
            fr: 5,
            lr: 5,
            cr: 5,
            pr: 5,
            ..Default::default()
        },
        CharmSpec {
            name: "Anni".into(),
            size: 1,
            all_skills: 1,
            fr: 10,
            lr: 10,
            cr: 10,
            pr: 10,
            unique_id: Some(381),
            ..Default::default()
        },
        CharmSpec {
            name: "Paladin Torch".into(),
            size: 2,
            skills: 3,
            fr: 10,
            lr: 10,
            cr: 10,
            pr: 10,
            unique_id: Some(400),
            ..Default::default()
        },
    ];

    for mode_str in ["leveling", "leveling-res"] {
        let mode = if mode_str == "leveling" {
            SearchMode::Leveling
        } else {
            SearchMode::LevelingRes
        };
        let c = BuildConstraints {
            char_class: CharClass::PALADIN_ID,
            offense: "zeal".into(),
            mode: mode_str.into(),
            char_level: 60,
            target_hp: 5000,
            base_hell_res: 40,
            base_str: 50,
            base_dex: 50,
            target_def: 400,
            min_fcr: 0,
            min_fhr: 0,
            min_fr: 50,
            min_lr: 50,
            min_cr: 50,
            min_pr: 50,
            min_ll: 5, // satisfied only by Dracul's 10% CTC Life Tap -> 5% effective
            max_charm_slots: 4,
            limit: 2,
            use_bo: false,
            aura_hit_dmg: vec![0.0, 0.0, 0.0, 0.0, 0.0],
            aura_pulse_dps: vec![0.0, 0.0, 0.0, 0.0, 0.0],
            action_ed: vec![0, 0, 0, 0, 0],
            action_hits: vec![5, 5, 5, 5, 5],
            action_ar_pct: vec![10, 20, 30, 40, 50],
            aura_ar_pct: vec![0, 0, 0, 0, 0],
            has_aura: false,
            ..Default::default()
        };
        let items = vec![sword.clone(), plain_gloves.clone(), lifetap_gloves.clone()];
        let opt = optimize_builds_core(&items, &charms, &c).unwrap();
        let bf = brute_force_top_scores(&items, &charms, &c, mode);
        assert!(!opt.is_empty());
        assert_eq!(opt[0].items[6].name, "Dracul's Grasp");
        let mut top_sc = validate_and_score_result(&opt[0], &c, mode);
        top_sc.locality = 0;
        assert_eq!(top_sc, bf[0], "mismatch for mode={mode_str}");
    }
}

#[test]
fn test_optimize_builds_with_baseline_prunes_and_preserves_ties() {
    let base_items = vec![
        mk_item("Spirit Sword", "weapon", 35, 55, 2, 0, 0),
        mk_item("Spirit Shield", "shield", 35, 55, 2, 35, 0),
        mk_item("Lore", "helm", 0, 0, 1, 30, 0),
        mk_item("Vipermagi", "armor", 30, 0, 1, 35, 0),
        mk_item("Amulet", "amulet", 10, 0, 1, 30, 0),
        mk_item("Belt", "belt", 0, 0, 0, 35, 0),
        mk_item("Trangs", "gloves", 20, 0, 0, 35, 0),
        mk_item("Aldurs", "boots", 0, 0, 0, 45, 0),
        mk_item("Ring A", "ring", 10, 0, 0, 20, 0),
        mk_item("Ring B", "ring", 10, 0, 0, 20, 0),
    ];
    let c = BuildConstraints {
        min_pr: 75,
        limit: 1,
        ..test_constraints()
    };
    let baseline = optimize_builds_with_baseline(&base_items, &[], &c, None).unwrap()[0].clone();
    assert_eq!(baseline.skills, 7);

    // 1. Strictly worse candidate than baseline returns empty when floor is enforced.
    let weaker_helm = mk_item("Peasant Crown", "helm", 0, 0, 0, 30, 0);
    let mut weaker_pool: Vec<ItemSpec> = base_items
        .iter()
        .filter(|it| it.slot != "helm")
        .cloned()
        .collect();
    weaker_pool.push(weaker_helm);
    let worse_res = optimize_builds_with_baseline(&weaker_pool, &[], &c, Some(&baseline)).unwrap();
    assert!(worse_res.is_empty());

    // 2. Strictly better candidate than baseline is returned.
    let better_helm = mk_item("Shako", "helm", 0, 0, 2, 30, 0);
    let mut better_pool: Vec<ItemSpec> = base_items
        .iter()
        .filter(|it| it.slot != "helm")
        .cloned()
        .collect();
    better_pool.push(better_helm);
    let better_res = optimize_builds_with_baseline(&better_pool, &[], &c, Some(&baseline)).unwrap();
    assert_eq!(better_res.len(), 1);
    assert_eq!(better_res[0].skills, 8);

    // 3. Candidate tying BuildScore (overcap resist beyond 75) is still accepted so Python's extra key can rank it.
    let mut tie_helm = mk_item("Lore [+Ral]", "helm", 0, 0, 1, 30, 0);
    tie_helm.fr = 60;
    let mut tie_pool: Vec<ItemSpec> = base_items
        .iter()
        .filter(|it| it.slot != "helm")
        .cloned()
        .collect();
    tie_pool.push(tie_helm);
    let tie_res = optimize_builds_with_baseline(&tie_pool, &[], &c, Some(&baseline)).unwrap();
    assert_eq!(tie_res.len(), 1);
    assert!(tie_res[0].fr_raw > baseline.fr_raw);

    // 4. Cold-sunder baseline relaxed below strict min_cr allows strict unlock on pass 1 and falls back with floor on pass 2.
    let sunder = CharmSpec {
        name: "Cold Rupture".into(),
        size: 3,
        cold_sunder: true,
        cr: -120,
        ..Default::default()
    };
    let c_cold = BuildConstraints {
        base_hell_res: -100,
        min_cr: 75,
        min_pr: 75,
        limit: 1,
        ..test_constraints()
    };
    // Baseline CR = 285 - 100 - 120 = 65 < 75, so it falls back to relaxed CR.
    let relaxed_base =
        optimize_builds_with_baseline(&base_items, std::slice::from_ref(&sunder), &c_cold, None)
            .unwrap()[0]
            .clone();
    assert!(relaxed_base.cr < c_cold.min_cr);

    // A +35 CR helm (+5 CR over Lore) gives CR = 70 (< 75) and ties relaxed score -> pass 2 returns it.
    let mut um_helm = mk_item("Lore [+Ral-Cold]", "helm", 0, 0, 1, 30, 0);
    um_helm.cr = 35;
    let mut um_pool: Vec<ItemSpec> = base_items
        .iter()
        .filter(|it| it.slot != "helm")
        .cloned()
        .collect();
    um_pool.push(um_helm);
    let um_res = optimize_builds_with_baseline(
        &um_pool,
        std::slice::from_ref(&sunder),
        &c_cold,
        Some(&relaxed_base),
    )
    .unwrap();
    assert_eq!(um_res.len(), 1);
    assert!(um_res[0].cr > relaxed_base.cr);

    // Huge CR unlock on helm meets strict min_cr = 75 -> pass 1 succeeds even though strict_floor was None.
    let mut strict_unlock_helm = mk_item("Kira's", "helm", 0, 0, 0, 30, 0);
    strict_unlock_helm.cr = 100;
    let mut unlock_pool: Vec<ItemSpec> = base_items
        .iter()
        .filter(|it| it.slot != "helm")
        .cloned()
        .collect();
    unlock_pool.push(strict_unlock_helm);
    let unlock_res = optimize_builds_with_baseline(
        &unlock_pool,
        std::slice::from_ref(&sunder),
        &c_cold,
        Some(&relaxed_base),
    )
    .unwrap();
    assert_eq!(unlock_res.len(), 1);
    assert!(unlock_res[0].cr >= 75);
}
