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
    assert_eq!(d.base_hell_res, -100);
    assert_eq!(d.bo_base_bonus, 4);
    assert_eq!((d.blizz_base_lvl, d.blizz_syn_pts, d.cm_base_lvl), (20, 54, 20));
    assert_eq!(d.limit, 5);
    assert_eq!((d.base_life, d.base_mana, d.base_str, d.base_dex), (0, 0, 0, 0));
    assert_eq!(d.char_class, 1);
    assert_eq!((d.base_max_fr, d.base_max_lr, d.base_max_cr, d.base_max_pr), (0, 0, 0, 0));
    assert!(d.use_bo);
    assert!(!d.fixed_gear);
    assert_eq!(d.offense, "caster");
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
