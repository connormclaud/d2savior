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

    // Default target_type="champion": -50% Target Defense (weapon) is halved to -25%,
    // stacking multiplicatively with -50% (Conviction at +1 aura):
    // eff_dr = 300 * 0.5 * 0.75 = 112.5 -> CTH = 579 / (579 + 112.5) = 579 / 691.5 (~84%).
    let mut ring_sk = ring_ar.clone();
    ring_sk.aura_skill_bonus = 1;
    let res_eth_conv_champ = eval_build_core(&[&wep_eth, &ring_sk], &[&charm_ar], &c_base, 1);
    // +1 aura gives aura_ar_pct=60% => total_ar_pct = 20 + 10 + 60 = 90 => 305 * 190 / 100 = 579.
    assert_eq!(res_eth_conv_champ.ar, 579);
    assert_eq!(res_eth_conv_champ.cth, 84);
    let expected_dps_eth_conv_champ = 100.0 * (579.0 / (579.0 + 112.5)) * zeal_rate;
    assert!((res_eth_conv_champ.dps - expected_dps_eth_conv_champ).abs() < 1e-6);
    assert!((res_eth_conv_champ.raw_dps - expected_raw_dps_plain).abs() < 1e-6);

    // target_type="boss": same -50% gear Target Def halving as champion.
    let c_boss = BuildConstraints {
        target_type: "boss".into(),
        ..c_base.clone()
    };
    let res_eth_conv_boss = eval_build_core(&[&wep_eth, &ring_sk], &[&charm_ar], &c_boss, 1);
    assert_eq!(res_eth_conv_boss.cth, 84);
    assert!((res_eth_conv_boss.dps - expected_dps_eth_conv_champ).abs() < 1e-6);

    // target_type="trash": full -50% Target Defense (weapon) * -50% (Conviction) =>
    // eff_dr = 300 * 0.5 * 0.5 = 75 -> CTH = 579 / (579 + 75) = 579 / 654 (~89%).
    let c_trash = BuildConstraints {
        target_type: "trash".into(),
        ..c_base.clone()
    };
    let res_eth_conv = eval_build_core(&[&wep_eth, &ring_sk], &[&charm_ar], &c_trash, 1);
    assert_eq!(res_eth_conv.ar, 579);
    assert_eq!(res_eth_conv.cth, 89);
    let expected_dps_eth_conv = 100.0 * (579.0 / (579.0 + 75.0)) * zeal_rate;
    assert!((res_eth_conv.dps - expected_dps_eth_conv).abs() < 1e-6);
    assert!((res_eth_conv.raw_dps - expected_raw_dps_plain).abs() < 1e-6);

    // ITD is disabled against champion (default) and boss, using normal AR vs target_def instead.
    let res_itd_champ = eval_build_core(&[&wep_itd], &[], &c_base, 1);
    let expected_cth_champ: f64 = 127.0 / (127.0 + 300.0);
    assert_eq!(res_itd_champ.ar, 127);
    assert_eq!(res_itd_champ.cth, (expected_cth_champ * 100.0).round() as i32);
    assert!((res_itd_champ.dps - 100.0 * expected_cth_champ * zeal_rate).abs() < 1e-6);

    let res_itd_boss = eval_build_core(&[&wep_itd], &[], &c_boss, 1);
    assert_eq!(res_itd_boss.cth, res_itd_champ.cth);

    // ITD gives 95% CTH directly against trash regardless of low AR.
    let res_itd = eval_build_core(&[&wep_itd], &[], &c_trash, 1);
    assert_eq!(res_itd.ar, 85 * 150 / 100); // 127
    assert_eq!(res_itd.cth, 95);
    let expected_dps_itd = 100.0 * 0.95 * zeal_rate;
    assert!((res_itd.dps - expected_dps_itd).abs() < 1e-6);

    // Explicit target_def=0 honors 0 enemy defense (clamped to 95% CTH) instead of defaulting to 180.
    let c_zero_dr = BuildConstraints {
        target_def: 0,
        ..c_base.clone()
    };
    let res_zero_dr = eval_build_core(&[&sword], &[], &c_zero_dr, 1);
    assert_eq!(res_zero_dr.cth, 95);

    // Exploding Arrow + Holy Fire: AoE splash_fire and aura_hit_dmg * targets are auto-hit,
    // while direct arrow physical damage scales with CTH.
    let bow = ItemSpec {
        name: "Test Bow".into(),
        slot: "weapon2h".into(),
        wclass: "bow".into(),
        wep_phys_2x: 40, // 20 avg direct arrow
        splash_fire: true,
        splash_fire_2x: 80, // 40 avg skill splash
        ..Default::default()
    };
    let mut c_exp = BuildConstraints {
        offense: "melee".into(),
        aura_is_fire: true,
        targets: 3,
        action_hits: vec![1],
        action_ed: vec![0],
        action_ar_pct: vec![10], // melee action AR% must be ignored on ranged weapons
        aura_hit_dmg: vec![50.0], // 50 avg Holy Fire on-hit * 3 targets = 150 auto-hit
        aura_pulse_dps: vec![10.0],
        ..c_base.clone()
    };
    c_exp.aura_ar_pct = vec![0];
    c_exp.aura_target_def_pct = vec![0];
    let res_exp = eval_build_core(&[&bow], &[], &c_exp, 1);
    assert_eq!(res_exp.ar, 85); // base_ar=85 without melee action_ar_pct +10%
    // base_ar = 85 vs target_def = 300 => cth = 85 / 385
    let bow_rate = 25.0 / res_exp.ias_frames as f64;
    let exp_cth = 85.0 / 385.0;
    let expected_exp_eff = (20.0 * exp_cth + (40.0 + 50.0) * 3.0) * bow_rate + 10.0 * 3.0;
    let expected_exp_raw = (20.0 + (40.0 + 50.0) * 3.0) * bow_rate + 10.0 * 3.0;
    assert!((res_exp.dps - expected_exp_eff).abs() < 1e-6);
    assert!((res_exp.raw_dps - expected_exp_raw).abs() < 1e-6);
}

#[test]
fn test_ds_cs_oskill_torch_vs_anni_and_ed_demon_undead() {
    let mut sword = ItemSpec {
        name: "Insight Broad Sword".into(),
        slot: "weapon".into(),
        wclass: "1hs".into(),
        wep_phys_2x: 200, // 100 avg
        can_zeal: true,
        itd: 1,
        ..Default::default()
    };
    sword.cs_oskill = 1; // +1 Critical Strike oskill -> 16%
    sword.ds = 25; // 25% Deadly Strike
    sword.ed_demon = 300;
    sword.ed_undead = 150;

    let anni = CharmSpec {
        name: "Anni".into(),
        size: 1,
        all_skills: 1,
        unique_id: Some(381),
        ..Default::default()
    };
    let torch = CharmSpec {
        name: "Paladin Torch".into(),
        size: 2,
        skills: 3, // +Paladin skills must NOT boost CS oskill
        unique_id: Some(400),
        ..Default::default()
    };

    let c_trash = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        offense: "melee".into(),
        mode: "leveling".into(),
        target_type: "trash".into(),
        base_str: 0,
        base_dex: 20,
        action_hits: vec![1],
        action_ed: vec![0],
        action_ar_pct: vec![0],
        aura_ar_pct: vec![0],
        aura_target_def_pct: vec![0],
        aura_hit_dmg: vec![0.0],
        aura_pulse_dps: vec![0.0],
        use_bo: false,
        ..Default::default()
    };

    // Torch alone: cs slvl remains 1 -> 16% CS; combined with 25% DS => 1 - 0.75 * 0.84 = 0.37 (crit_mult = 1.37).
    // Trash weights: ed_demon/3 + ed_undead/3 = 100 + 50 = 150% => eff_ed = 150% (phys mult = 2.5).
    let res_torch = eval_build_core(&[&sword], &[&torch], &c_trash, 1);
    let rate = 25.0 / res_torch.ias_frames as f64;
    let exp_torch_raw = 100.0 * 2.5 * 1.37 * rate;
    assert!((res_torch.raw_dps - exp_torch_raw).abs() < 1e-6);

    // Anni (+1 all_skills) DOES boost CS oskill to slvl 2 -> 5 + 75*(220/8)/100 = 25%, combined = 1 - 0.75*0.75 = 0.4375.
    let res_anni = eval_build_core(&[&sword], &[&anni], &c_trash, 1);
    let exp_anni_raw = 100.0 * 2.5 * 1.4375 * rate;
    assert!((res_anni.raw_dps - exp_anni_raw).abs() < 1e-6);

    // Boss target_type: ed_demon 100%, ed_undead 0% => eff_ed = 300% (phys mult = 4.0).
    let c_boss = BuildConstraints {
        target_type: "boss".into(),
        ..c_trash.clone()
    };
    let res_boss = eval_build_core(&[&sword], &[&anni], &c_boss, 1);
    let exp_boss_raw = 100.0 * 4.0 * 1.4375 * rate;
    assert!((res_boss.raw_dps - exp_boss_raw).abs() < 1e-6);
}

#[test]
fn test_cb_ow_poison_venom_ctc_and_exploding_arrow_pierce() {
    let mut wep = ItemSpec {
        name: "Test Maul".into(),
        slot: "weapon2h".into(),
        wclass: "2hs".into(),
        wep_phys_2x: 0,
        can_zeal: true,
        itd: 1,
        ..Default::default()
    };
    wep.cb = 100;
    wep.ow = 100;
    wep.psn_dps_2x = 100; // 50 dps
    wep.ctc_venom_dps_2x = 400; // 200 dps
    wep.ctc_static_pct = 50;
    wep.ctc_orb_dmg_2x = 200; // 100 avg orb

    let mut armor = mk_test_item("Treachery", "armor", 0, 0, 0, 0, 0);
    armor.ctc_venom_dps_2x = 300; // non-stacking max -> stays 400 from wep

    let c_trash = BuildConstraints {
        char_class: CharClass::PALADIN_ID,
        offense: "melee".into(),
        mode: "leveling".into(),
        target_type: "trash".into(),
        char_level: 30,
        target_hp: 1000,
        targets: 4,
        base_dex: 20,
        action_hits: vec![1],
        action_ed: vec![0],
        action_ar_pct: vec![0],
        aura_ar_pct: vec![0],
        aura_target_def_pct: vec![0],
        aura_hit_dmg: vec![0.0],
        aura_pulse_dps: vec![0.0],
        use_bo: false,
        ..Default::default()
    };
    let res = eval_build_core(&[&wep, &armor], &[], &c_trash, 1);
    let rate = 25.0 / res.ias_frames as f64;
    let cth: f64 = 0.95;
    // CB: 100% * 0.25 * (0.5 * 1000) = 125/hit; Static: 0.5 * 0.25 * (0.25 * 1000) * 4 = 125/hit; Orb: 100 * 3 = 300/hit.
    let direct_hit = 125.0 + 125.0 + 300.0;
    // OW at lvl 30: (18*30 - 95) = 445 -> 25 * 445 / 256 = 43.45703125 DPS (p_ow=1 -> uptime=1).
    let ow_dps = 25.0 * 445.0 / 256.0;
    // Poison: (50 + 200) * (1 - 0.05^(2*rate)).
    let psn_base = 250.0;
    let psn_dps = psn_base * (1.0 - (1.0 - cth).powf((2.0 * rate).max(1.0)));
    assert!((res.dps - (direct_hit * cth * rate + ow_dps + psn_dps)).abs() < 1e-6);

    // Champion halves CB (12.5%) and halves OW.
    let c_champ = BuildConstraints {
        target_type: "champion".into(),
        target_def: 0,
        ..c_trash.clone()
    };
    let res_champ = eval_build_core(&[&wep, &armor], &[], &c_champ, 1);
    let direct_champ = 62.5 + 125.0 + 300.0;
    assert!(
        (res_champ.dps - (direct_champ * 0.95 * rate + ow_dps * 0.5 + psn_dps)).abs() < 1e-6
    );

    // Decrepify multiplier tests:
    let mut lawbringer = ItemSpec {
        name: "Lawbringer".into(),
        slot: "weapon".into(),
        wclass: "1hs".into(),
        wep_phys_2x: 200,
        can_zeal: true,
        itd: 1,
        ..Default::default()
    };
    lawbringer.ctc_decrep_pct = 100; // 1.5x phys
    let res_dec = eval_build_core(&[&lawbringer], &[], &c_trash, 1);
    let dec_rate = 25.0 / res_dec.ias_frames as f64;
    assert!((res_dec.raw_dps - 100.0 * 1.5 * dec_rate).abs() < 1e-6);

    // Exploding Arrow + flat_fire_2x * targets + ranged Pierce capped at 4 extra targets.
    let mut kuko = ItemSpec {
        name: "Kuko".into(),
        slot: "weapon2h".into(),
        wclass: "bow".into(),
        wep_phys_2x: 0,
        splash_fire: true,
        splash_fire_2x: 20, // 10 avg skill splash
        itd: 1,
        ..Default::default()
    };
    kuko.flat_fire_2x = 40; // 20 avg gear fire -> * targets
    kuko.pierce = 100;
    let c_ea = BuildConstraints {
        targets: 10, // capped at 1 + 4 = 5 pierce hits
        ..c_trash
    };
    let res_kuko = eval_build_core(&[&kuko], &[], &c_ea, 1);
    let kuko_rate = 25.0 / res_kuko.ias_frames as f64;
    let mut pierce_eff = 1.0;
    let mut p_pow = 1.0;
    for _ in 0..4 {
        p_pow *= 0.95;
        pierce_eff += p_pow;
    }
    let auto_hit = (10.0 + 20.0) * 10.0;
    assert!((res_kuko.dps - auto_hit * pierce_eff * kuko_rate).abs() < 1e-6);
    assert!((res_kuko.raw_dps - auto_hit * 5.0 * kuko_rate).abs() < 1e-6);
}
