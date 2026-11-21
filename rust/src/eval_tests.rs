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

#[test]
fn test_charm_vit_ene_and_all_skills_bo_scaling() {
    let torch = CharmSpec {
        name: "Hellfire Torch".to_string(),
        size: 2,
        skills: 3,
        vit: 20,
        ene: 20,
        unique_id: Some(400),
        ..Default::default()
    };
    let anni = CharmSpec {
        name: "Annihilus".to_string(),
        size: 1,
        all_skills: 1,
        vit: 15,
        ene: 15,
        unique_id: Some(381),
        ..Default::default()
    };

    // Sorceress (2 life/vit, 2 mana/ene), BO base 4 + 1 (Anni all_skills; Torch skills excluded) => bo_lvl = 5 (47% BO).
    // vit_life = (20 + 15) * 2 = 70 (not BO-scaled).
    // ene_mana = (20 + 15) * 2 = 70 (not BO-scaled).
    let sorc_c = BuildConstraints {
        char_class: 1,
        base_life: 500,
        base_mana: 300,
        bo_base_bonus: 4,
        use_bo: true,
        ..Default::default()
    };
    let res_sorc = eval_build_core(&[], &[&torch, &anni], &sorc_c, 1);
    assert_eq!(res_sorc.skills, 4);
    assert_eq!(res_sorc.bo_lvl, 5);
    assert_eq!(res_sorc.life_no_bo, 500 + 70);
    assert_eq!(res_sorc.life_bo, (500.0 * 1.47) as i32 + 70);
    assert_eq!(res_sorc.mana_bo, (300.0 * 1.47) as i32 + 70);

    // Paladin (3 life/vit, 1.5 mana/ene), no BO.
    // vit_life = 35 * 3 = 105; ene_mana = 35 * 3 / 2 = 52.
    let pal_c = BuildConstraints {
        char_class: 3,
        base_life: 500,
        base_mana: 300,
        use_bo: false,
        ..Default::default()
    };
    let res_pal = eval_build_core(&[], &[&torch, &anni], &pal_c, 1);
    assert_eq!(res_pal.skills, 4);
    assert_eq!(res_pal.bo_lvl, 0);
    assert_eq!(res_pal.life_no_bo, 500 + 105);
    assert_eq!(res_pal.life_bo, 500 + 105);
    assert_eq!(res_pal.mana_bo, 300 + 52);
}

#[test]
fn test_pct_life_scales_bo_able_life_only() {
    let mut helm = mk_test_item("Jah Shako", "helm", 0, 0, 0, 0, 0);
    helm.life = 100;
    helm.pct_life = 5;
    helm.vit = 10; // +20 non-BO-able life on Sorc
    helm.life_per_lvl = 80; // non-BO-able

    let c_bo = BuildConstraints {
        char_class: 1,
        base_life: 500,
        bo_base_bonus: 6, // bo_pct = 32 + 18 = 50%
        use_bo: true,
        ..Default::default()
    };
    let res_bo = eval_build_core(&[&helm], &[], &c_bo, 1);
    // bo_able_life = 600. life_no_bo = 600 * 1.05 + 20 + 80 = 730.
    // life_bo = 600 * 1.55 + 20 + 80 = 1030.
    assert_eq!(res_bo.life_no_bo, 730);
    assert_eq!(res_bo.life_bo, 1030);

    let c_no_bo = BuildConstraints {
        use_bo: false,
        ..c_bo
    };
    let res_no_bo = eval_build_core(&[&helm], &[], &c_no_bo, 1);
    assert_eq!(res_no_bo.life_no_bo, 730);
    assert_eq!(res_no_bo.life_bo, 730);
}

#[test]
fn test_ar_and_chance_to_hit_scaling() {
    assert_eq!(CharClass::Paladin.base_ar_from_dex(20), 85);
    assert_eq!(CharClass::Sorceress.base_ar_from_dex(25), 75);
    assert_eq!(CharClass::Sorceress.base_ar_from_dex(5), 0);

    // Base Paladin: dex=20 -> 85 base AR; sword weapon phys_2x=200 (100 avg), 1hs wsm=0 @ 0 IAS -> 15f = 25/15 hit/s.
    let sword = ItemSpec {
        name: "Test Sword".into(),
        slot: "weapon".into(),
        wclass: "1hs".into(),
        wep_phys_2x: 200,
        can_zeal: true,
        ..Default::default()
    };
    let mut ring_ar = mk_test_item("AR Ring", "ring", 0, 0, 0, 0, 0);
    ring_ar.ar = 200;
    ring_ar.ar_pct = 20;
    let charm_ar = CharmSpec {
        name: "Fine SC".into(),
        size: 1,
        ar: 20,
        ..Default::default()
    };
    let mut wep_itd = sword.clone();
    wep_itd.itd = 1;
    let mut wep_eth = sword.clone();
    wep_eth.target_def_pct = 50;

    let c_base = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        offense: "zeal".into(),
        mode: "leveling".into(),
        base_str: 0,
        base_dex: 20,
        target_def: 300,
        action_hits: vec![2, 3],
        action_ed: vec![0, 0],
        action_ar_pct: vec![10, 50],
        aura_ar_pct: vec![40, 60],
        aura_target_def_pct: vec![0, 50],
        aura_hit_dmg: vec![0.0, 0.0],
        aura_pulse_dps: vec![0.0, 0.0],
        use_bo: false,
        ..Default::default()
    };

    // Total base AR = 85 + 200 + 20 = 305.
    // Eff action=0 (hits=2 -> used_zeal=true, action_ar_pct=10%), eff aura=0 (aura_ar_pct=40%), ring ar_pct=20%
    // => +70% AR => AR = 305 * 170 / 100 = 518.
    let res_plain = eval_build_core(&[&sword, &ring_ar], &[&charm_ar], &c_base, 1);
    assert_eq!(res_plain.ar, 518);
    assert_eq!(res_plain.cth, 63);
    assert!(res_plain.used_zeal);
    let zeal_rate = 25.0 * 2.0 / (res_plain.ias_frames + res_plain.ias_last_frames) as f64;
    let expected_cth_plain = 518.0 / (518.0 + 300.0);
    let expected_dps_plain = 100.0 * expected_cth_plain * zeal_rate;
    let expected_raw_dps_plain = 100.0 * zeal_rate;
    assert!((res_plain.dps - expected_dps_plain).abs() < 1e-6);
    assert!((res_plain.raw_dps - expected_raw_dps_plain).abs() < 1e-6);

    // -50% Target Defense (weapon) + -50% (Conviction at +1 aura): total 100% reduction -> eff_dr = 0 -> CTH clamped to 0.95.
    let mut ring_sk = ring_ar.clone();
    ring_sk.aura_skill_bonus = 1;
    let res_eth_conv = eval_build_core(&[&wep_eth, &ring_sk], &[&charm_ar], &c_base, 1);
    // +1 aura gives aura_ar_pct=60% => total_ar_pct = 20 + 10 + 60 = 90 => 305 * 190 / 100 = 579.
    assert_eq!(res_eth_conv.ar, 579);
    assert_eq!(res_eth_conv.cth, 95);
    let expected_dps_eth_conv = 100.0 * 0.95 * zeal_rate;
    assert!((res_eth_conv.dps - expected_dps_eth_conv).abs() < 1e-6);
    assert!((res_eth_conv.raw_dps - expected_raw_dps_plain).abs() < 1e-6);

    // ITD gives 95% CTH directly regardless of low AR.
    let res_itd = eval_build_core(&[&wep_itd], &[], &c_base, 1);
    assert_eq!(res_itd.ar, 85 * 150 / 100); // 127
    assert_eq!(res_itd.cth, 95);
    assert!((res_itd.dps - expected_dps_eth_conv).abs() < 1e-6);
}
