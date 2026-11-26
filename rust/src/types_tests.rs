use super::*;

#[test]
fn test_build_constraints_default_matches_expected() {
    let d = BuildConstraints::default();
    assert!(d.allow_mf);
    assert_eq!(d.min_fcr, 105);
    assert_eq!(d.min_fhr, 86);
    assert_eq!((d.min_fr, d.min_lr, d.min_cr, d.min_pr), (75, 75, 75, 0));
    assert_eq!(d.max_charm_slots, 23);
    assert_eq!(d.mode, "power");
    assert_eq!(d.character.base_hell_res, -100);
    assert_eq!(d.character.bo_base_bonus, 4);
    let caster = d.skills.caster().expect("default skills should be Caster");
    assert_eq!(
        (caster.blizz_base_lvl, caster.blizz_syn_pts, caster.cm_base_lvl),
        (20, 54, 20)
    );
    assert_eq!(d.limit, 5);
    assert_eq!(
        (
            d.character.base_life,
            d.character.base_mana,
            d.character.base_str,
            d.character.base_dex
        ),
        (0, 0, 0, 0)
    );
    assert_eq!(d.character.char_class, 1);
    assert_eq!(
        (
            d.character.base_max_fr,
            d.character.base_max_lr,
            d.character.base_max_cr,
            d.character.base_max_pr
        ),
        (0, 0, 0, 0)
    );
    assert!(d.character.use_bo);
    assert!(!d.fixed_gear);
    assert_eq!(d.offense, "caster");
    assert_eq!(d.target.target_type, "champion");
}

#[test]
fn test_target_type_parsing_and_mechanics() {
    assert_eq!(TargetType::default(), TargetType::Champion);
    assert_eq!(TargetType::parse("trash"), Ok(TargetType::Trash));
    assert_eq!(TargetType::parse("CHAMPION"), Ok(TargetType::Champion));
    assert_eq!(TargetType::parse("Boss"), Ok(TargetType::Boss));
    assert!(TargetType::parse("uber").is_err());

    assert!(TargetType::Trash.allows_itd());
    assert!(!TargetType::Champion.allows_itd());
    assert!(!TargetType::Boss.allows_itd());

    assert_eq!(TargetType::Trash.gear_target_def_reduction(50), 50);
    assert_eq!(TargetType::Champion.gear_target_def_reduction(50), 25);
    assert_eq!(TargetType::Boss.gear_target_def_reduction(50), 25);
    assert_eq!(TargetType::Champion.gear_target_def_reduction(25), 12);
    assert_eq!(TargetType::Boss.gear_target_def_reduction(120), 50);
}

#[test]
fn test_char_class_and_offense_profile_parsing_and_scoring() {
    assert_eq!(CharClass::from_id(1), Ok(CharClass::Sorceress));
    assert_eq!(CharClass::from_id(3), Ok(CharClass::Paladin));
    assert!(CharClass::from_id(0).is_err());

    assert_eq!(
        OffenseProfile::parse("caster", CharClass::Sorceress),
        Ok(OffenseProfile::Caster)
    );
    assert!(OffenseProfile::parse("melee", CharClass::Sorceress).is_err());
    assert!(OffenseProfile::parse("smite", CharClass::Sorceress).is_err());
    assert!(OffenseProfile::parse("unknown", CharClass::Paladin).is_err());

    assert_eq!(
        OffenseProfile::parse("MELEE", CharClass::Paladin),
        Ok(OffenseProfile::Melee)
    );
    let smite = OffenseProfile::parse("Smite", CharClass::Paladin).unwrap();
    assert!(smite.requires_shield());
    assert!(!OffenseProfile::Melee.requires_shield());
    assert_eq!(OffenseProfile::Caster.score(3, 50, 50), 3);
    assert_eq!(OffenseProfile::Melee.score(2, 100, 40), 2 * 20 + (80 * 3) / 2);
    assert_eq!(OffenseProfile::Zeal.score(2, 18, 40), 2 * 20 + (18 * 3) / 2);
    assert_eq!(smite.score(2, 100, 120), 100 * 4 + 80 * 2 + 20);
}

#[test]
fn test_empty_hand_weapon_matches_between_search_and_eval() {
    let empty_wep = ItemSpec::empty("weapon");
    assert_eq!(empty_wep.hand_weapon(), HandWeapon::empty());
    assert_eq!(equipped_hand_weapon(&[&empty_wep]), HandWeapon::empty());
    assert_eq!(equipped_hand_weapon(&[]), HandWeapon::empty());
    assert_eq!(empty_wep.hand_weapon().str_pct, 100);
}

#[test]
fn test_fast_leaf_dps_matches_compute_dps_detailed() {
    let base_melee = MeleeSkillModel {
        action_hits: vec![1, 2, 3, 4, 5],
        action_ed: vec![0, 50, 100, 150, 200],
        action_ar_pct: vec![0, 20, 40, 60, 80],
        aura_hit_dmg: vec![0.0, 40.0, 80.0],
        aura_pulse_dps: vec![0.0, 15.0, 30.0],
        aura_ar_pct: vec![0, 10, 20],
        aura_target_def_pct: vec![0, 25, 50],
        ..Default::default()
    };
    let base_c = BuildConstraints {
        offense: "melee".to_string(),
        character: CharacterStats {
            char_class: 3,
            char_level: 85,
            ..Default::default()
        },
        target: TargetProfile {
            target_def: 1500,
            target_hp: 12000,
            targets: 3,
            ..Default::default()
        },
        skills: SkillModel::Melee(base_melee.clone()),
        ..Default::default()
    };
    let bow = HandWeapon {
        phys_2x: 60,
        wsm: 0,
        wclass: WeaponClass::Bow,
        str_pct: 0,
        dex_pct: 100,
        can_zeal: false,
        splash_fire: true,
        splash_fire_2x: 90,
    };
    let sword = HandWeapon {
        phys_2x: 80,
        wsm: -10,
        wclass: WeaponClass::OneHandSwing,
        str_pct: 100,
        dex_pct: 0,
        can_zeal: true,
        splash_fire: false,
        splash_fire_2x: 0,
    };
    let deltas = [
        (0, 0, 0, 0, 0),
        (120, 15, 22, 18, 40),
        (5000, 40, 0, 10, 0),
    ];

    let scenarios = [
        // 1. Bow + splash_fire + aura_is_fire + pierce + decrep + ow + poison/venom + cb + static + orb
        (
            OffenseProfile::Melee,
            bow,
            Stats {
                all_skills: 1,
                pal_skills: 1,
                dex_bonus: 120,
                ar: 200,
                ar_pct: 50,
                ias: 35,
                ds: 25,
                cs_oskill: 3,
                cb: 30,
                ow: 25,
                ctc_decrep_pct: 20,
                ctc_static_pct: 15,
                ctc_orb_dmg_2x: 100,
                ctc_venom_dps_2x: 60,
                psn_dps_2x: 30,
                pierce: 66,
                flat_phys_2x: 10,
                flat_fire_2x: 20,
                flat_elem_2x: 14,
                off_ed: 80,
                ed_demon: 150,
                ed_undead: 100,
                ..Default::default()
            },
            BuildConstraints {
                target: TargetProfile {
                    target_type: "trash".to_string(),
                    ..base_c.target.clone()
                },
                skills: SkillModel::Melee(MeleeSkillModel {
                    aura_is_fire: true,
                    ..base_melee
                }),
                ..base_c.clone()
            },
        ),
        // 2. ITD active on trash
        (
            OffenseProfile::Zeal,
            sword,
            Stats {
                itd: 1,
                str_bonus: 100,
                dex_bonus: 50,
                ar: 10,
                ias: 40,
                ..Default::default()
            },
            BuildConstraints {
                target: TargetProfile {
                    target_type: "trash".to_string(),
                    ..base_c.target.clone()
                },
                ..base_c.clone()
            },
        ),
        // 3. eff_dr == 0
        (
            OffenseProfile::Melee,
            sword,
            Stats {
                str_bonus: 80,
                dex_bonus: 40,
                ..Default::default()
            },
            BuildConstraints {
                target: TargetProfile {
                    target_def: 0,
                    target_type: "boss".to_string(),
                    ..base_c.target.clone()
                },
                ..base_c.clone()
            },
        ),
        // 4. CTH already capped at 0.95 (high AR)
        (
            OffenseProfile::Zeal,
            sword,
            Stats {
                str_bonus: 100,
                dex_bonus: 100,
                ar: 100_000,
                ..Default::default()
            },
            BuildConstraints {
                target: TargetProfile {
                    target_type: "champion".to_string(),
                    ..base_c.target.clone()
                },
                ..base_c.clone()
            },
        ),
        // 5. Negative base values (verify `.max(0)` clamp parity)
        (
            OffenseProfile::Melee,
            HandWeapon {
                phys_2x: 0,
                ..sword
            },
            Stats {
                ar: -50,
                flat_phys_2x: -10,
                flat_fire_2x: -8,
                flat_elem_2x: -6,
                psn_dps_2x: -20,
                ..Default::default()
            },
            base_c,
        ),
    ];

    for (idx, (offense, hand, leaf, c)) in scenarios.iter().enumerate() {
        let fast = offense.fast_leaf_dps(*hand, *leaf, c);
        for &(add_ar, add_phys, add_elem, add_fire, add_psn) in &deltas {
            let s = Stats {
                ar: leaf.ar + add_ar,
                flat_phys_2x: leaf.flat_phys_2x + add_phys,
                flat_elem_2x: leaf.flat_elem_2x + add_elem,
                flat_fire_2x: leaf.flat_fire_2x + add_fire,
                psn_dps_2x: leaf.psn_dps_2x + add_psn,
                ..*leaf
            };
            let exact = offense.compute_dps_detailed(*hand, s, c).0;
            let approx = fast.eval_dps(add_ar, add_phys, add_elem, add_fire, add_psn);
            assert!(
                (exact - approx).abs() <= 1e-9 * exact.abs().max(1.0),
                "scenario {idx} mismatch: exact={exact}, fast={approx}"
            );
        }
    }
}

#[test]
fn test_fast_leaf_dps_eval_detailed_fields() {
    let base_melee = MeleeSkillModel {
        action_hits: vec![1, 2, 3, 4, 5],
        action_ed: vec![0, 50, 100, 150, 200],
        action_ar_pct: vec![0, 20, 40, 60, 80],
        aura_hit_dmg: vec![0.0, 40.0, 80.0],
        aura_pulse_dps: vec![0.0, 15.0, 30.0],
        ..Default::default()
    };
    let base_c = BuildConstraints {
        character: CharacterStats {
            char_class: 3,
            char_level: 85,
            ..Default::default()
        },
        target: TargetProfile {
            target_def: 1500,
            target_hp: 12000,
            targets: 3,
            ..Default::default()
        },
        skills: SkillModel::Melee(base_melee.clone()),
        ..Default::default()
    };
    let bow = HandWeapon {
        phys_2x: 60,
        wsm: 0,
        wclass: WeaponClass::Bow,
        str_pct: 0,
        dex_pct: 100,
        can_zeal: false,
        splash_fire: true,
        splash_fire_2x: 90,
    };
    let sword = HandWeapon {
        phys_2x: 80,
        wsm: -10,
        wclass: WeaponClass::OneHandSwing,
        str_pct: 100,
        dex_pct: 0,
        can_zeal: true,
        splash_fire: false,
        splash_fire_2x: 0,
    };

    // 1. ITD active on trash: cth_pct is 95 while total_ar still reports actual AR.
    let itd_stats = Stats {
        all_skills: 2,
        itd: 1,
        str_bonus: 100,
        dex_bonus: 50,
        ar: 10,
        ias: 40,
        ..Default::default()
    };
    let trash_c = BuildConstraints {
        target: TargetProfile {
            target_type: "trash".to_string(),
            ..base_c.target.clone()
        },
        ..base_c.clone()
    };
    let (_, _, total_ar, cth_pct, ias_bp, display_frames, last_frames, used_zeal) =
        OffenseProfile::Zeal.compute_dps_detailed(sword, itd_stats, &trash_c);
    assert!(total_ar > 0);
    assert_eq!(cth_pct, 95);
    let (_, exp_ias, exp_disp, exp_last, exp_zeal) =
        OffenseProfile::Zeal.attack_rate_and_frames(sword, itd_stats.ias, 3);
    assert_eq!(
        (ias_bp, display_frames, last_frames, used_zeal),
        (exp_ias, exp_disp, exp_last, exp_zeal)
    );
    assert!(used_zeal);

    // 2. Combined pierce + ow + psn + splash_fire + aura_is_fire: raw_dps > eff_dps.
    let bow_stats = Stats {
        all_skills: 1,
        pal_skills: 1,
        dex_bonus: 120,
        ar: 200,
        ar_pct: 50,
        ias: 35,
        ow: 25,
        psn_dps_2x: 30,
        pierce: 66,
        flat_phys_2x: 10,
        flat_fire_2x: 20,
        ..Default::default()
    };
    let bow_c = BuildConstraints {
        target: TargetProfile {
            target_type: "trash".to_string(),
            ..base_c.target.clone()
        },
        skills: SkillModel::Melee(MeleeSkillModel {
            aura_is_fire: true,
            ..base_melee
        }),
        ..base_c.clone()
    };
    let fast_bow = OffenseProfile::Melee.fast_leaf_dps(bow, bow_stats, &bow_c);
    let (eff_dps, raw_dps, bow_ar, bow_cth_pct, _, _, _, bow_zeal) = fast_bow.eval_detailed();
    assert_eq!(eff_dps, fast_bow.eval_dps(0, 0, 0, 0, 0));
    assert!(raw_dps > eff_dps);
    assert!(bow_ar > 0);
    assert!((5..=95).contains(&bow_cth_pct));
    assert!(!bow_zeal);

    // 3. Negative base inputs clamp cleanly to non-negative outputs.
    let neg_weapon = HandWeapon {
        phys_2x: 0,
        ..sword
    };
    let neg_stats = Stats {
        ar: -50,
        flat_phys_2x: -10,
        flat_fire_2x: -8,
        flat_elem_2x: -6,
        psn_dps_2x: -20,
        ..Default::default()
    };
    let (neg_eff, neg_raw, neg_ar, neg_cth, ..) =
        OffenseProfile::Melee.compute_dps_detailed(neg_weapon, neg_stats, &base_c);
    assert!(neg_eff >= 0.0 && neg_raw >= 0.0);
    assert!(neg_ar >= 0);
    assert!((5..=95).contains(&neg_cth));
}

#[test]
fn test_stats_combine_and_itemspec_roundtrip() {
    let a = Stats {
        all_skills: 2,
        fr: 30,
        ctc_static_pct: 5,
        ctc_venom_dps_2x: 30,
        belt_slots: 12,
        ..Default::default()
    };
    let b = Stats {
        all_skills: 1,
        fr: 15,
        ctc_static_pct: 10,
        ctc_venom_dps_2x: 50,
        belt_slots: 4,
        ..Default::default()
    };

    // add sums additive stats and takes .max() on ctc_venom_dps_2x in both orders.
    let added = a.add(b);
    assert_eq!(added.all_skills, 3);
    assert_eq!(added.fr, 45);
    assert_eq!(added.ctc_static_pct, 15);
    assert_eq!(added.ctc_venom_dps_2x, 50);
    assert_eq!(added.belt_slots, 16);
    assert_eq!(b.add(a), added);

    // max_each takes per-field max across additive and max fields.
    let maxed = a.max_each(b);
    assert_eq!(maxed.all_skills, 2);
    assert_eq!(maxed.fr, 30);
    assert_eq!(maxed.ctc_static_pct, 10);
    assert_eq!(maxed.ctc_venom_dps_2x, 50);
    assert_eq!(maxed.belt_slots, 12);

    // dominates requires >= across every stat field (first, middle ctc_venom_dps_2x, and last).
    assert!(added.dominates(a));
    assert!(added.dominates(b));
    assert!(a.dominates(a));
    assert!(!a.dominates(b));
    assert!(!Stats {
        all_skills: added.all_skills - 1,
        ..added
    }
    .dominates(added));
    assert!(!Stats {
        ctc_venom_dps_2x: added.ctc_venom_dps_2x - 1,
        ..added
    }
    .dominates(added));
    assert!(!Stats {
        belt_slots: added.belt_slots - 1,
        ..added
    }
    .dominates(added));

    // ItemSpec::from_stats -> ItemSpec::stats round-trips all stats and sets reqs/defaults.
    let item = ItemSpec::from_stats(
        "Test Item".to_string(),
        "armor".to_string(),
        "Stash".to_string(),
        added,
        97,
        42,
    );
    assert_eq!(item.name, "Test Item");
    assert_eq!(item.slot, "armor");
    assert_eq!(item.loc, "Stash");
    assert_eq!(item.req_str, 97);
    assert_eq!(item.req_dex, 42);
    assert_eq!(item.stats(), added);
    assert_eq!(item.set_group, 0);
    assert_eq!(item.wsm, 0);
    assert!(!item.can_zeal);
}
