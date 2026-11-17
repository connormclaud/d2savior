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
}
