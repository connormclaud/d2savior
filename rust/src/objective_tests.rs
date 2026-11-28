use super::*;
use crate::eval::eval_build_summary;
use crate::stats::{compute_effective_gear_stats, equipped_hand_weapon};
use crate::types::{BuildConstraints, CharacterStats, ItemSpec, TargetProfile};

#[test]
fn ub_prefix_ordering_matches_exact_prefix_comparison() {
    let cutoff = BuildScore {
        primary: 10,
        secondary: 20,
        tertiary: 1,
        tiebreakers: [999, 888, 777, 666, 555, 444, 333],
        locality: 123,
    };

    // Prefix-1: only primary < cutoff.primary prunes.
    assert!(BuildScore::ub_prefix1(9) < cutoff);
    assert!(!(BuildScore::ub_prefix1(10) < cutoff));
    assert!(!(BuildScore::ub_prefix1(11) < cutoff));

    // Prefix-2: (primary, secondary) < (10, 20) prunes; tie does not.
    assert!(BuildScore::ub_prefix2(9, 999) < cutoff);
    assert!(BuildScore::ub_prefix2(10, 19) < cutoff);
    assert!(!(BuildScore::ub_prefix2(10, 20) < cutoff));
    assert!(!(BuildScore::ub_prefix2(10, 21) < cutoff));

    // Prefix-3: (primary, secondary, tertiary) < (10, 20, 1) prunes; tie does not.
    assert!(BuildScore::ub_prefix3(10, 20, 0) < cutoff);
    assert!(!(BuildScore::ub_prefix3(10, 20, 1) < cutoff));
    assert!(!(BuildScore::ub_prefix3(10, 20, 2) < cutoff));
}

#[test]
fn score_upper_bound_dominates_score_for_all_modes() {
    let weapon = ItemSpec {
        slot: "weapon".to_string(),
        name: "Test Sword".to_string(),
        loc: "Equipped".to_string(),
        all_skills: 2,
        class_skills: 1,
        fcr: 35,
        fhr: 20,
        ias: 20,
        cb: 25,
        fr: 140,
        lr: 150,
        cr: 120,
        pr: 115,
        max_fr: 5,
        max_lr: 10,
        mf: 50,
        cbf: 1,
        wclass: "1hs".to_string(),
        ..ItemSpec::empty("weapon")
    };
    let items = [weapon];
    let gear: Vec<&ItemSpec> = items.iter().collect();
    let hw = equipped_hand_weapon(&gear);
    let base_c = BuildConstraints {
        mode: "power".to_string(),
        offense: "caster".to_string(),
        min_fcr: 0,
        min_fhr: 0,
        min_fr: -100,
        min_lr: -100,
        min_cr: -100,
        min_pr: -100,
        max_charm_slots: 0,
        character: CharacterStats {
            char_class: 3, // Paladin
            base_hell_res: -100,
            ..CharacterStats::default()
        },
        target: TargetProfile::default(),
        ..BuildConstraints::default()
    };

    let profiles = ["caster", "zeal", "smite"];
    let modes = [
        SearchMode::Power,
        SearchMode::Mf,
        SearchMode::MaxRes,
        SearchMode::Leveling,
        SearchMode::LevelingRes,
    ];
    for prof in profiles {
        let mut c = base_c.clone();
        c.offense = prof.to_string();
        let rc_base = ResolvedConstraints::resolve(&c).unwrap();
        let (gear_stats, all_sk_non_wep) = compute_effective_gear_stats(&gear);
        // Mirror SearchState's base_stats (base_hell_res + base_str/base_dex).
        let base_res = rc_base.character.base_hell_res;
        let ub_ch = Stats {
            str_bonus: gear_stats.str_bonus + rc_base.character.base_str,
            dex_bonus: gear_stats.dex_bonus + rc_base.character.base_dex,
            fr: gear_stats.fr + base_res,
            lr: gear_stats.lr + base_res,
            cr: gear_stats.cr + base_res,
            pr: gear_stats.pr + base_res,
            ..gear_stats
        };
        let caps = res_caps(ub_ch, &rc_base);

        for mode in modes {
            let rc = rc_base.with_mode(mode);
            let sum = eval_build_summary(gear_stats, all_sk_non_wep, hw, false, &[], &rc);
            let score = mode.score(&sum, &rc);
            let max_hand_dps = if rc.offense.uses_dps_tables(&rc) {
                OffenseProfile::dps_bucket(rc.offense.compute_dps(hw, ub_ch, &rc).0)
            } else {
                0
            };
            for hand_opt in [Some(hw), None] {
                let ub = mode.score_upper_bound(ub_ch, hand_opt, max_hand_dps, caps, &rc);
                assert!(
                    score <= ub,
                    "unsound UB for profile={prof} mode={mode:?} hand={hand_opt:?}: score={score:?} > ub={ub:?}"
                );
            }
        }
    }
}

#[test]
fn min_charm_main_needed_matches_each_mode() {
    let c = BuildConstraints {
        mode: "power".to_string(),
        offense: "caster".to_string(),
        character: CharacterStats {
            char_class: 3, // Paladin
            base_hell_res: 0,
            ..CharacterStats::default()
        },
        ..BuildConstraints::default()
    };
    let rc_base = ResolvedConstraints::resolve(&c).unwrap();
    let leaf = Stats {
        all_skills: 3,
        class_skills: 2,
        mf: 120,
        fr: 80,
        lr: 70,
        cr: 60,
        pr: 50,
        max_fr: 5,
        ..Stats::default()
    };
    let ch = Stats {
        all_skills: 4,
        ..Stats::default()
    };

    // Power (non-caster-dps): cur_sk = 3 + 2 = 5
    assert_eq!(
        SearchMode::Power.min_charm_main_needed(leaf, ch, 8, &rc_base.with_mode(SearchMode::Power)),
        3
    );
    assert_eq!(
        SearchMode::Power.min_charm_main_needed(leaf, ch, 4, &rc_base.with_mode(SearchMode::Power)),
        0
    );
    // Mf: leaf.mf = 120
    assert_eq!(
        SearchMode::Mf.min_charm_main_needed(leaf, ch, 155, &rc_base.with_mode(SearchMode::Mf)),
        35
    );
    // MaxRes: caps = (80, 75, 75, 75), cur_sum = 80 + 70 + 60 + 50 = 260
    assert_eq!(
        SearchMode::MaxRes.min_charm_main_needed(
            leaf,
            ch,
            285,
            &rc_base.with_mode(SearchMode::MaxRes)
        ),
        25
    );
    // LevelingRes: base caps = (75, 75, 75, 75), cur_sum = 75 + 70 + 60 + 50 = 255
    assert_eq!(
        SearchMode::LevelingRes.min_charm_main_needed(
            leaf,
            ch,
            285,
            &rc_base.with_mode(SearchMode::LevelingRes)
        ),
        30
    );
    // Leveling: always 0
    assert_eq!(
        SearchMode::Leveling.min_charm_main_needed(
            leaf,
            ch,
            999,
            &rc_base.with_mode(SearchMode::Leveling)
        ),
        0
    );
}
