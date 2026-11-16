use super::*;
use crate::types::mk_test_item;

#[test]
fn test_blizzard_damage_scaling() {
    let (_, syn7, cm7) = blizzard_damage(7);
    assert!((syn7 - 3245.4).abs() < 1.0);
    assert_eq!(cm7, -150);

    let (_, syn9, cm9) = blizzard_damage(9);
    assert!((syn9 - 3666.7).abs() < 1.0);
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
}
