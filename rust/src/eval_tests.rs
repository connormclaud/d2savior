use super::*;
use crate::types::{MeleeSkillModel, TargetProfile, mk_test_item};

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
        character: CharacterStats {
            base_life: 500,
            base_mana: 200,
            base_hell_res: -70,
            bo_base_bonus: 4,
            ..Default::default()
        },
        skills: SkillModel::Caster(CasterSkillModel {
            blizz_base_lvl: 20,
            blizz_syn_pts: 54,
            cm_base_lvl: 20,
            ..Default::default()
        }),
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
        character: CharacterStats {
            use_bo: false,
            bo_base_bonus: 0,
            ..Default::default()
        },
        skills: SkillModel::Caster(CasterSkillModel {
            blizz_base_lvl: 0,
            blizz_syn_pts: 0,
            cm_base_lvl: 0,
            ..Default::default()
        }),
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
    c_noblizz.character.base_hell_res = 0;
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
        character: CharacterStats {
            char_class: 1,
            base_life: 500,
            base_mana: 300,
            bo_base_bonus: 4,
            use_bo: true,
            ..Default::default()
        },
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
        character: CharacterStats {
            char_class: 3,
            base_life: 500,
            base_mana: 300,
            use_bo: false,
            ..Default::default()
        },
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
        character: CharacterStats {
            char_class: 1,
            base_life: 500,
            bo_base_bonus: 6, // bo_pct = 32 + 18 = 50%
            use_bo: true,
            ..Default::default()
        },
        ..Default::default()
    };
    let res_bo = eval_build_core(&[&helm], &[], &c_bo, 1);
    // bo_able_life = 600. life_no_bo = 600 * 1.05 + 20 + 80 = 730.
    // life_bo = 600 * 1.55 + 20 + 80 = 1030.
    assert_eq!(res_bo.life_no_bo, 730);
    assert_eq!(res_bo.life_bo, 1030);

    let c_no_bo = BuildConstraints {
        character: CharacterStats {
            use_bo: false,
            ..c_bo.character
        },
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
        offense: "zeal".into(),
        mode: "leveling".into(),
        character: CharacterStats {
            char_class: CharClass::PALADIN_ID,
            base_str: 0,
            base_dex: 20,
            use_bo: false,
            ..Default::default()
        },
        target: TargetProfile {
            target_def: 300,
            ..Default::default()
        },
        skills: SkillModel::Melee(MeleeSkillModel {
            action_hits: vec![2, 3],
            action_ed: vec![0, 0],
            action_ar_pct: vec![10, 50],
            aura_ar_pct: vec![40, 60],
            aura_target_def_pct: vec![0, 50],
            aura_hit_dmg: vec![0.0, 0.0],
            aura_pulse_dps: vec![0.0, 0.0],
            ..Default::default()
        }),
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
        target: TargetProfile {
            target_type: "boss".into(),
            ..c_base.target.clone()
        },
        ..c_base.clone()
    };
    let res_eth_conv_boss = eval_build_core(&[&wep_eth, &ring_sk], &[&charm_ar], &c_boss, 1);
    assert_eq!(res_eth_conv_boss.cth, 84);
    assert!((res_eth_conv_boss.dps - expected_dps_eth_conv_champ).abs() < 1e-6);

    // target_type="trash": full -50% Target Defense (weapon) * -50% (Conviction) =>
    // eff_dr = 300 * 0.5 * 0.5 = 75 -> CTH = 579 / (579 + 75) = 579 / 654 (~89%).
    let c_trash = BuildConstraints {
        target: TargetProfile {
            target_type: "trash".into(),
            ..c_base.target.clone()
        },
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
        target: TargetProfile {
            target_def: 0,
            ..c_base.target.clone()
        },
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
    let c_exp = BuildConstraints {
        offense: "melee".into(),
        target: TargetProfile {
            targets: 3,
            ..c_base.target.clone()
        },
        skills: SkillModel::Melee(MeleeSkillModel {
            aura_is_fire: true,
            action_hits: vec![1],
            action_ed: vec![0],
            action_ar_pct: vec![10], // melee action AR% must be ignored on ranged weapons
            aura_hit_dmg: vec![50.0], // 50 avg Holy Fire on-hit * 3 targets = 150 auto-hit
            aura_pulse_dps: vec![10.0],
            aura_ar_pct: vec![0],
            aura_target_def_pct: vec![0],
            ..Default::default()
        }),
        ..c_base.clone()
    };
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
        offense: "melee".into(),
        mode: "leveling".into(),
        character: CharacterStats {
            char_class: CharClass::PALADIN_ID,
            base_str: 0,
            base_dex: 20,
            use_bo: false,
            ..Default::default()
        },
        target: TargetProfile {
            target_type: "trash".into(),
            ..Default::default()
        },
        skills: SkillModel::Melee(MeleeSkillModel {
            action_hits: vec![1],
            action_ed: vec![0],
            action_ar_pct: vec![0],
            aura_ar_pct: vec![0],
            aura_target_def_pct: vec![0],
            aura_hit_dmg: vec![0.0],
            aura_pulse_dps: vec![0.0],
            ..Default::default()
        }),
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
        target: TargetProfile {
            target_type: "boss".into(),
            ..c_trash.target.clone()
        },
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
        offense: "melee".into(),
        mode: "leveling".into(),
        character: CharacterStats {
            char_class: CharClass::PALADIN_ID,
            char_level: 30,
            base_dex: 20,
            use_bo: false,
            ..Default::default()
        },
        target: TargetProfile {
            target_type: "trash".into(),
            target_hp: 1000,
            targets: 4,
            ..Default::default()
        },
        skills: SkillModel::Melee(MeleeSkillModel {
            action_hits: vec![1],
            action_ed: vec![0],
            action_ar_pct: vec![0],
            aura_ar_pct: vec![0],
            aura_target_def_pct: vec![0],
            aura_hit_dmg: vec![0.0],
            aura_pulse_dps: vec![0.0],
            ..Default::default()
        }),
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
        target: TargetProfile {
            target_type: "champion".into(),
            target_def: 0,
            ..c_trash.target.clone()
        },
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
        target: TargetProfile {
            targets: 10, // capped at 1 + 4 = 5 pierce hits
            ..c_trash.target.clone()
        },
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

#[test]
fn test_defense_block_fbr_paladin_holy_shield_and_sorc_cold_armors() {
    // 1. Paladin with shield + Holy Shield + Defiance + Combat charm/staffmod + FBR.
    let mut hoz = mk_test_item("Herald of Zakarum", "shield", 0, 0, 2, 0, 0);
    hoz.defense = 500;
    hoz.block_pct = 52; // 22 base (Gilded) + 30 HoZ
    hoz.fbr = 30;
    hoz.def_skill = 2; // +2 Combat or Holy Shield -> with 2 pal_skills = +4 total
    let mut armor = mk_test_item("Armor", "armor", 0, 0, 1, 0, 0);
    armor.defense = 300;
    armor.fbr = 60; // total fbr = 90 -> BP 86, 1f with Holy Shield

    let c_pal = BuildConstraints {
        offense: "melee".to_string(),
        mode: "leveling".to_string(),
        character: CharacterStats {
            char_class: CharClass::PALADIN_ID,
            base_dex: 115,
            char_level: 85,
            ..Default::default()
        },
        target: TargetProfile {
            target_ar: 6630,
            target_lvl: 87,
            ..Default::default()
        },
        skills: SkillModel::Melee(MeleeSkillModel {
            holy_shield_base_lvl: 1,
            defiance_base_lvl: 2,
            ..Default::default()
        }),
        ..Default::default()
    };
    let combat_gc = CharmSpec {
        name: "Captain's GC".to_string(),
        size: 3,
        action_skills: 1,
        ..Default::default()
    };
    let res_pal = eval_build_core(&[&hoz, &armor], &[&combat_gc], &c_pal, 1);
    assert!(res_pal.has_shield);
    // hs_slvl = 1 (base) + 3 (all/pal) + 2 (def_skill) + 1 (charm action) = 7
    // skill_def_pct = 25 + 15*6 + 15*2 = 145%
    // base_def = 500 + 300 + 115/4 = 828 -> 828 * 245 / 100 = 2028
    assert_eq!(res_pal.defense, 2028);
    // hs_block(7) = 10 + (30 * ((770 / 13) = 59)) / 100 = 27
    // shield_block = 52 + 30 (Pal) + 27 = 109 -> (109 * 100) / 170 = 64%
    assert_eq!(res_pal.block_pct, 64);
    assert_eq!(res_pal.fbr, 90);
    assert_eq!((res_pal.fbr_bp, res_pal.fbr_frames), (86, 1));
    // CTH: 2 * (6630 / (6630 + 2028)) * (87 / 172) = 0.7747 -> 77%
    assert_eq!(res_pal.enemy_cth, 77);

    // Without Holy Shield (0 base): 30% FBR uses standard Paladin table (BP 13, 4f); capped at 75% at high Dex.
    let c_no_hs = BuildConstraints {
        character: CharacterStats {
            base_dex: 200,
            ..c_pal.character.clone()
        },
        skills: SkillModel::Melee(MeleeSkillModel {
            holy_shield_base_lvl: 0,
            ..c_pal.skills.melee().cloned().unwrap_or_default()
        }),
        ..c_pal.clone()
    };
    let res_no_hs = eval_build_core(&[&hoz, &armor], &[], &c_no_hs, 1);
    // Total fbr = 90 -> standard Paladin BP 86, 2f; with Armor excluded (fbr=30): BP 13, 4f
    assert_eq!((res_no_hs.fbr_bp, res_no_hs.fbr_frames), (86, 2));
    assert_eq!(res_no_hs.defense, 500 + 300 + 200 / 4);
    assert_eq!(res_no_hs.block_pct, 75);

    // 2H Bow Paladin: has_shield = false -> Holy Shield inactive, block/FBR = 0.
    let bow = mk_test_item("Kuko", "weapon2h", 0, 0, 0, 0, 0);
    let res_bow = eval_build_core(&[&bow, &armor], &[], &c_pal, 1);
    assert!(!res_bow.has_shield);
    assert_eq!(res_bow.defense, 300 + 115 / 4);
    assert_eq!((res_bow.block_pct, res_bow.fbr, res_bow.fbr_bp, res_bow.fbr_frames), (0, 0, 0, 0));

    // 2. Sorceress Cold Armors (Frozen=1, Shiver=2, Chilling=3), FBR table, and enemy_cth clamp [5, 95].
    let mut storm = mk_test_item("Stormshield", "shield", 0, 0, 0, 0, 0);
    storm.defense = 400;
    storm.block_pct = 47; // 22 base + 25 mod -> +20 Sorc = 67%
    storm.fbr = 35; // Sorc BP 27, 6f
    let mut orb = mk_test_item("Orb", "weapon", 0, 0, 2, 0, 0);
    orb.def_skill = 1;
    let c_sorc = BuildConstraints {
        character: CharacterStats {
            char_class: CharClass::SORCERESS_ID,
            base_dex: 100,
            char_level: 80,
            ..Default::default()
        },
        target: TargetProfile {
            target_ar: 3000,
            target_lvl: 82,
            ..Default::default()
        },
        skills: SkillModel::Caster(CasterSkillModel {
            cold_armor_kind: 2, // Shiver: 45 + 6*(lvl-1)
            cold_armor_base_lvl: 1,
            ..Default::default()
        }),
        ..Default::default()
    };
    let res_sorc = eval_build_core(&[&storm, &orb], &[], &c_sorc, 1);
    // ca_slvl = 1 + 2 + 1 = 4 -> Shiver ED = 45 + 18 = 63%; base = 425 -> 425*163/100 = 692
    assert_eq!(res_sorc.defense, 692);
    assert_eq!(res_sorc.block_pct, (67 * 85) / 160);
    assert_eq!((res_sorc.fbr, res_sorc.fbr_bp, res_sorc.fbr_frames), (35, 27, 6));

    // Clamp checks: huge defense -> 5% hit, tiny defense & huge AR -> 95% hit.
    let mut huge_armor = armor.clone();
    huge_armor.defense = 1_000_000;
    let res_min_cth = eval_build_core(&[&huge_armor], &[], &c_sorc, 1);
    assert_eq!(res_min_cth.enemy_cth, 5);
    let res_max_cth = eval_build_core(
        &[],
        &[],
        &BuildConstraints {
            target: TargetProfile {
                target_ar: 100_000,
                ..c_sorc.target.clone()
            },
            ..c_sorc.clone()
        },
        1,
    );
    assert_eq!(res_max_cth.enemy_cth, 95);

    // Zero hard points in Cold Armor: Snowclash (+2 Chilling Armor via def_skill) unlocks Chilling Armor,
    // while +all_skills / +sorc_skills alone without def_skill gives 0% Cold Armor ED.
    let c_zero_ca = BuildConstraints {
        character: CharacterStats {
            base_dex: 0,
            ..c_sorc.character.clone()
        },
        skills: SkillModel::Caster(CasterSkillModel {
            cold_armor_kind: 3,
            cold_armor_base_lvl: 0,
            ..c_sorc.skills.caster().cloned().unwrap_or_default()
        }),
        ..c_sorc
    };
    let plain_orb = mk_test_item("Plain Orb", "weapon", 0, 0, 2, 0, 0);
    let mut snowclash = mk_test_item("Snowclash", "belt", 0, 0, 0, 0, 0);
    snowclash.defense = 100;
    snowclash.def_skill = 2; // +2 Chilling Armor
    let res_snow = eval_build_core(&[&snowclash, &plain_orb], &[], &c_zero_ca, 1);
    // ca_slvl = 0 + 2 (orb sorc_skills) + 2 (Snowclash) = 4 -> Chilling ED = 60 + 9*3 = 87%
    assert_eq!(res_snow.defense, 187);

    let res_no_snow = eval_build_core(&[&armor, &plain_orb], &[], &c_zero_ca, 1);
    // No Cold Armor hard pts and gear.def_skill == 0 (Armor's +1 all_skills, Orb's +2 sorc_skills): 0% ED
    assert_eq!(res_no_snow.defense, 300);

    // gear_defense includes partial set bonuses for score_eval_summary / socket.py parity.
    let mut set_bonus = ItemSpec::empty("armor");
    set_bonus.defense = 50;
    let mut set_helm = mk_test_item("Set Helm", "helm", 0, 0, 0, 0, 0);
    set_helm.defense = 100;
    set_helm.set_group = 1;
    set_helm.set_item_id = 1;
    set_helm.set_bonuses = vec![(2, set_bonus)];
    let mut set_gloves = mk_test_item("Set Gloves", "gloves", 0, 0, 0, 0, 0);
    set_gloves.defense = 20;
    set_gloves.set_group = 1;
    set_gloves.set_item_id = 2;
    let res_set = eval_build_core(&[&set_helm, &set_gloves], &[], &c_zero_ca, 1);
    assert_eq!(res_set.gear_defense, 170);
    assert_eq!(res_set.defense, 170);
}
