use super::*;
use crate::types::mk_test_item;

#[test]
fn test_blizzard_damage_scaling() {
    let (base0, syn0, cm0) = blizzard_damage(0);
    assert!((base0 - 594.5).abs() < 1e-9);
    assert!((syn0 - 2199.65).abs() < 1e-6);
    assert_eq!(cm0, -115);

    let (base7, syn7, cm7) = blizzard_damage(7);
    assert!((base7 - 963.0).abs() < 1e-9);
    assert!((syn7 - 3563.1).abs() < 1e-6);
    assert_eq!(cm7, -150);

    let (base9, syn9, cm9) = blizzard_damage(9);
    assert!((base9 - 1084.0).abs() < 1e-9);
    assert!((syn9 - 4010.8).abs() < 1e-6);
    assert_eq!(cm9, -160);
}

#[test]
fn test_bo_skips_per_level_life_mana_and_vit_ene() {
    let mut shako = mk_test_item("Harlequin Crest", "helm", 0, 0, 2, 0, 50);
    shako.life = 50;
    shako.life_per_lvl = 133;
    shako.mana = 40;
    shako.mana_per_lvl = 133;
    shako.vit = 10;
    shako.ene = 15;
    shako.pct_mana = 25;

    let items = [shako];
    let charms = [CharmSpec {
        name: "Life/Mana SC".to_string(),
        size: 1,
        loc: "inv".to_string(),
        life: 20,
        mana: 17,
        ..Default::default()
    }];
    // all_skills non-weapon = 2, bo_base_bonus = 4 -> bo_lvl = 6 -> bo_pct = 32 + 18 = 50%
    // bo_able_life = 500 (base) + 50 (flat item) + 20 (charm) = 570 -> * 1.5 = 855
    // + item_vit * 2 (20) + item_life_per_lvl (133) = 1008
    // bo_able_mana = 200 (base) + 40 (flat item) + 17 (charm) = 257 -> * (1 + (50 + 25)/100) = 449.75 -> 449
    // + item_ene * 2 (30) + item_mana_per_lvl (133) = 612
    let c = BuildConstraints {
        base_life: 500,
        base_mana: 200,
        base_hell_res: -70,
        bo_base_bonus: 4,
        blizz_base_lvl: 20,
        blizz_syn_pts: 54,
        cm_base_lvl: 20,
        ..Default::default()
    };
    let res = eval_build_core(
        &items.iter().collect::<Vec<_>>(),
        &charms.iter().collect::<Vec<_>>(),
        &c,
        1,
    );
    assert_eq!(res.bo_lvl, 6);
    assert_eq!(res.life_no_bo, 500 + 50 + 133 + 20 + 20);
    assert_eq!(res.life_bo, 1008);
    assert_eq!(res.mana_bo, 612);
}

#[test]
fn test_blizzard_damage_with_custom_base_skills() {
    let (base_d, syn_d, cm_d) = blizzard_damage(5);
    assert_eq!((base_d, syn_d, cm_d), blizzard_damage_with_base(5, 20, 54, 20));

    // 20 Blizzard, 35 synergy hard pts, 10 Cold Mastery, +5 skills -> blizz=25, cm=15
    let (base_c, syn_c, cm_c) = blizzard_damage_with_base(5, 20, 35, 10);
    assert!((base_c - base_d).abs() < 1e-9);
    assert!((syn_c - base_c * (1.0 + 0.05 * 35.0)).abs() < 1e-9);
    assert_eq!(cm_c, -(20 + 5 * (15 - 1)));

    // Unallocated (0, 0, 0) with 0 +skills gives 0 damage and 0% pierce
    assert_eq!(blizzard_damage_with_base(0, 0, 0, 0), (0.0, 0.0, 0));

    // Non-Blizzard Sorc (0, 0, 0) with +3 All Skills gear still evaluates to 0 Blizzard / CM
    let mut c_noblizz = BuildConstraints {
        blizz_base_lvl: 0,
        blizz_syn_pts: 0,
        cm_base_lvl: 0,
        use_bo: false,
        bo_base_bonus: 0,
        ..Default::default()
    };
    let circlet = mk_test_item("Circlet", "helm", 20, 0, 3, 0, 0);
    let res_noblizz = eval_build_core(&[&circlet], &[], &c_noblizz, 1);
    assert_eq!(res_noblizz.skills, 3);
    assert_eq!(res_noblizz.blizz_avg, 0.0);
    assert_eq!(res_noblizz.cm_pierce, 0);

    // Staffmod +2 Blizzard on orb still produces Blizzard damage even with 0 hard points
    let mut orb = mk_test_item("Staffmod Orb", "weapon", 20, 0, 0, 0, 0);
    orb.blizz_skills = 2;
    c_noblizz.base_hell_res = 0;
    let res_staff = eval_build_core(&[&circlet, &orb], &[], &c_noblizz, 1);
    assert!(res_staff.blizz_avg > 0.0);
    assert_eq!(res_staff.cm_pierce, 0);
}

#[test]
fn test_paladin_eval_breakpoints_vit_ene_no_bo_and_passive_max_res() {
    let mut armor = mk_test_item("Paladin Armor", "armor", 30, 27, 1, 20, 0);
    armor.pal_skills = 1;
    armor.primary_skill = 3;
    armor.vit = 10;
    armor.ene = 7;
    armor.ias = 20;
    armor.cb = 15;
    armor.cbf = 1;
    armor.pdr_pct = 10;
    armor.life_leech = 5;

    let res = evaluate_build_core(
        &[armor],
        &[CharmSpec {
            name: "Balance SC".to_string(),
            size: 1,
            fhr: 21,
            life: 15,
            mana: 10,
            ..Default::default()
        }],
        400,
        50,
        0,
        0,
        0,
        0,
        0,
        3,
        false,
        2,
        1,
        0,
        0,
    )
    .unwrap();
    assert_eq!(res.skills, 2);
    assert_eq!(res.primary_skill_bonus, 3);
    assert_eq!(res.fcr_bp, 30);
    assert_eq!(res.fhr_bp, 48);
    assert_eq!(res.ias, 20);
    assert_eq!(res.cb, 15);
    assert!(res.cbf);
    assert_eq!(res.pdr_pct, 10);
    assert_eq!(res.life_leech, 5);
    assert_eq!(res.bo_lvl, 0);
    // Vit*3 = 30, Ene*3/2 = 10; no BO
    assert_eq!(res.life_no_bo, 400 + 30 + 15);
    assert_eq!(res.life_bo, res.life_no_bo);
    assert_eq!(res.mana_bo, 50 + 10 + 10);
    assert_eq!(res.blizz_avg, 0.0);
    assert_eq!(res.cm_pierce, 0);
    assert_eq!((res.max_fr, res.max_lr, res.max_cr, res.max_pr), (77, 76, 75, 75));

    let err = evaluate_build_core(&[], &[], 0, 0, -100, 4, 20, 54, 20, 99, true, 0, 0, 0, 0)
        .unwrap_err();
    assert!(err.contains("unsupported char_class 99"));
}

#[test]
fn test_pdr_pct_capped_at_50() {
    let mut helm = mk_test_item("Shako", "helm", 0, 0, 0, 0, 0);
    helm.pdr_pct = 10;
    let mut armor = mk_test_item("Shaftstop", "armor", 0, 0, 0, 0, 0);
    armor.pdr_pct = 30;
    let mut shield = mk_test_item("Stormshield", "shield", 0, 0, 0, 0, 0);
    shield.pdr_pct = 35;

    let res_over = eval_build_core(
        &[&helm, &armor, &shield],
        &[],
        &BuildConstraints::default(),
        1,
    );
    assert_eq!(res_over.pdr_pct, 50);

    let res_under = eval_build_core(&[&armor], &[], &BuildConstraints::default(), 1);
    assert_eq!(res_under.pdr_pct, 30);
}
