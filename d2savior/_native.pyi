from collections.abc import Sequence
from typing import Literal

SearchModeStr = Literal["power", "mf", "max-res", "leveling", "leveling-res"]
OffenseProfileStr = Literal["caster", "melee", "zeal", "smite"]
TargetTypeStr = Literal["trash", "champion", "boss"]

class ItemSpec:
    name: str
    slot: str
    loc: str
    all_skills: int
    sorc_skills: int
    pal_skills: int
    blizz_skills: int
    cm_skills: int
    primary_skill: int
    action_skill_bonus: int
    aura_skill_bonus: int
    off_ed: int
    flat_phys_2x: int
    flat_fire_2x: int
    flat_elem_2x: int
    cold_dmg_pct: int
    ds: int
    cs_oskill: int
    ow: int
    ed_demon: int
    ed_undead: int
    psn_dps_2x: int
    pierce: int
    ctc_static_pct: int
    ctc_venom_dps_2x: int
    ctc_decrep_pct: int
    ctc_lifetap_pct: int
    ctc_orb_dmg_2x: int
    ar: int
    ar_pct: int
    itd: int
    target_def_pct: int
    fcr: int
    fhr: int
    frw: int
    ias: int
    cb: int
    cbf: int
    pdr_pct: int
    life_leech: int
    fr: int
    lr: int
    cr: int
    pr: int
    mf: int
    life: int
    life_per_lvl: int
    mana: int
    mana_per_lvl: int
    vit: int
    ene: int
    pct_life: int
    pct_mana: int
    mdr: int
    dr_flat: int
    fire_abs_pct: int
    str_bonus: int
    dex_bonus: int
    req_str: int
    req_dex: int
    max_fr: int
    max_lr: int
    max_cr: int
    max_pr: int
    defense: int
    belt_slots: int
    block_pct: int
    fbr: int
    def_skill: int
    set_group: int
    set_item_id: int
    set_bonuses: list[tuple[int, ItemSpec]]
    global_set_bonuses: list[tuple[int, ItemSpec]]
    wsm: int
    wclass: str
    wep_phys_2x: int
    wep_str_pct: int
    wep_dex_pct: int
    can_zeal: bool
    splash_fire: bool
    splash_fire_2x: int

    def __init__(
        self,
        name: str,
        slot: str,
        loc: str = "",
        all_skills: int = 0,
        sorc_skills: int = 0,
        pal_skills: int = 0,
        blizz_skills: int = 0,
        cm_skills: int = 0,
        primary_skill: int = 0,
        action_skill_bonus: int = 0,
        aura_skill_bonus: int = 0,
        off_ed: int = 0,
        flat_phys_2x: int = 0,
        flat_fire_2x: int = 0,
        flat_elem_2x: int = 0,
        cold_dmg_pct: int = 0,
        ds: int = 0,
        cs_oskill: int = 0,
        ow: int = 0,
        ed_demon: int = 0,
        ed_undead: int = 0,
        psn_dps_2x: int = 0,
        pierce: int = 0,
        ctc_static_pct: int = 0,
        ctc_venom_dps_2x: int = 0,
        ctc_decrep_pct: int = 0,
        ctc_lifetap_pct: int = 0,
        ctc_orb_dmg_2x: int = 0,
        ar: int = 0,
        ar_pct: int = 0,
        itd: int = 0,
        target_def_pct: int = 0,
        fcr: int = 0,
        fhr: int = 0,
        frw: int = 0,
        ias: int = 0,
        cb: int = 0,
        cbf: int = 0,
        pdr_pct: int = 0,
        life_leech: int = 0,
        fr: int = 0,
        lr: int = 0,
        cr: int = 0,
        pr: int = 0,
        max_fr: int = 0,
        max_lr: int = 0,
        max_cr: int = 0,
        max_pr: int = 0,
        mf: int = 0,
        life: int = 0,
        mana: int = 0,
        life_per_lvl: int = 0,
        mana_per_lvl: int = 0,
        vit: int = 0,
        ene: int = 0,
        pct_life: int = 0,
        pct_mana: int = 0,
        mdr: int = 0,
        dr_flat: int = 0,
        fire_abs_pct: int = 0,
        str_bonus: int = 0,
        dex_bonus: int = 0,
        defense: int = 0,
        belt_slots: int = 0,
        block_pct: int = 0,
        fbr: int = 0,
        def_skill: int = 0,
        req_str: int = 0,
        req_dex: int = 0,
        set_group: int = 0,
        set_item_id: int = 0,
        set_bonuses: Sequence[tuple[int, ItemSpec]] = (),
        global_set_bonuses: Sequence[tuple[int, ItemSpec]] = (),
        wsm: int = 0,
        wclass: str = "",
        wep_phys_2x: int = 0,
        wep_str_pct: int = 0,
        wep_dex_pct: int = 0,
        can_zeal: bool = False,
        splash_fire: bool = False,
        splash_fire_2x: int = 0,
    ) -> None: ...
    @property
    def skills(self) -> int: ...

class CharmSpec:
    name: str
    size: int
    loc: str
    fhr: int
    fr: int
    lr: int
    cr: int
    pr: int
    mf: int
    life: int
    mana: int
    frw: int
    light_skills: int
    str_bonus: int
    dex_bonus: int
    skills: int
    action_skills: int
    aura_skills: int
    unique_id: int | None
    cold_sunder: bool
    all_skills: int
    vit: int
    ene: int
    ar: int
    flat_phys_2x: int
    flat_fire_2x: int
    flat_elem_2x: int
    psn_dps_2x: int

    def __init__(
        self,
        name: str,
        size: int,
        loc: str = "",
        fhr: int = 0,
        fr: int = 0,
        lr: int = 0,
        cr: int = 0,
        pr: int = 0,
        mf: int = 0,
        life: int = 0,
        mana: int = 0,
        frw: int = 0,
        str_bonus: int = 0,
        dex_bonus: int = 0,
        all_skills: int = 0,
        vit: int = 0,
        ene: int = 0,
        ar: int = 0,
        flat_phys_2x: int = 0,
        flat_fire_2x: int = 0,
        flat_elem_2x: int = 0,
        psn_dps_2x: int = 0,
        light_skills: int = 0,
        skills: int = 0,
        action_skills: int = 0,
        aura_skills: int = 0,
        unique_id: int | None = None,
        cold_sunder: bool = False,
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...

class CharacterStats:
    char_class: int
    char_level: int
    base_life: int
    base_mana: int
    base_str: int
    base_dex: int
    base_hell_res: int
    base_max_fr: int
    base_max_lr: int
    base_max_cr: int
    base_max_pr: int
    bo_base_bonus: int
    use_bo: bool

    def __init__(
        self,
        char_class: int = 1,
        char_level: int = 1,
        base_life: int = 0,
        base_mana: int = 0,
        base_str: int = 0,
        base_dex: int = 0,
        base_hell_res: int = -100,
        base_max_fr: int = 0,
        base_max_lr: int = 0,
        base_max_cr: int = 0,
        base_max_pr: int = 0,
        bo_base_bonus: int = 4,
        use_bo: bool = True,
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...

class TargetProfile:
    targets: int
    target_type: str
    target_def: int
    target_ar: int
    target_lvl: int
    target_hp: int

    def __init__(
        self,
        targets: int = 1,
        target_type: TargetTypeStr = "champion",
        target_def: int = 180,
        target_ar: int = 0,
        target_lvl: int = 0,
        target_hp: int = 0,
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...

class CasterSkillModel:
    blizz_base_lvl: int
    blizz_syn_pts: int
    cm_base_lvl: int
    blizz_dmg: list[float]
    filler_dmg: list[float]
    filler_is_aoe: bool
    cold_armor_kind: int
    cold_armor_base_lvl: int

    def __init__(
        self,
        blizz_base_lvl: int = 20,
        blizz_syn_pts: int = 54,
        cm_base_lvl: int = 20,
        blizz_dmg: Sequence[float] = (),
        filler_dmg: Sequence[float] = (),
        filler_is_aoe: bool = False,
        cold_armor_kind: int = 0,
        cold_armor_base_lvl: int = 0,
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...

class MeleeSkillModel:
    aura_hit_dmg: list[float]
    aura_pulse_dps: list[float]
    action_ed: list[int]
    action_hits: list[int]
    has_aura: bool
    aura_is_fire: bool
    action_ar_pct: list[int]
    aura_ar_pct: list[int]
    aura_target_def_pct: list[int]
    holy_shield_base_lvl: int
    defiance_base_lvl: int
    aura_ed: list[int]
    aura_ias: list[int]

    def __init__(
        self,
        aura_hit_dmg: Sequence[float] = (),
        aura_pulse_dps: Sequence[float] = (),
        action_ed: Sequence[int] = (),
        action_hits: Sequence[int] = (),
        has_aura: bool = False,
        aura_is_fire: bool = False,
        action_ar_pct: Sequence[int] = (),
        aura_ar_pct: Sequence[int] = (),
        aura_target_def_pct: Sequence[int] = (),
        holy_shield_base_lvl: int = 0,
        defiance_base_lvl: int = 0,
        aura_ed: Sequence[int] = (),
        aura_ias: Sequence[int] = (),
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...

type SkillModel = CasterSkillModel | MeleeSkillModel

class BuildConstraints:
    allow_mf: bool
    min_fcr: int
    min_fhr: int
    min_fr: int
    min_lr: int
    min_cr: int
    min_pr: int
    max_charm_slots: int
    mode: SearchModeStr
    limit: int
    fixed_gear: bool
    fixed_slots: list[str]
    offense: OffenseProfileStr
    require_cbf: bool
    min_frw: int
    min_ias: int
    min_cb: int
    min_ll: int
    min_pdr: int
    min_mf: int
    character: CharacterStats
    target: TargetProfile
    skills: SkillModel

    def __init__(
        self,
        allow_mf: bool = True,
        min_fcr: int = 105,
        min_fhr: int = 86,
        min_fr: int = 75,
        min_lr: int = 75,
        min_cr: int = 75,
        min_pr: int = 0,
        max_charm_slots: int = 23,
        mode: SearchModeStr = "power",
        limit: int = 5,
        fixed_gear: bool = False,
        fixed_slots: Sequence[str] = (),
        offense: OffenseProfileStr = "caster",
        require_cbf: bool = False,
        min_frw: int = 0,
        min_ias: int = 0,
        min_cb: int = 0,
        min_ll: int = 0,
        min_pdr: int = 0,
        min_mf: int = 0,
        character: CharacterStats | None = None,
        target: TargetProfile | None = None,
        skills: SkillModel | None = None,
    ) -> None: ...
    def with_limit(self, limit: int) -> BuildConstraints: ...

class BuildResult:
    @property
    def skills(self) -> int: ...
    @property
    def primary_skill_bonus(self) -> int: ...
    @property
    def action_skill_bonus(self) -> int: ...
    @property
    def aura_skill_bonus(self) -> int: ...
    @property
    def dps(self) -> float: ...
    @property
    def used_zeal(self) -> bool: ...
    @property
    def blizz_avg(self) -> float: ...
    @property
    def cm_pierce(self) -> int: ...
    @property
    def fcr(self) -> int: ...
    @property
    def fcr_bp(self) -> int: ...
    @property
    def fhr(self) -> int: ...
    @property
    def fhr_bp(self) -> int: ...
    @property
    def frw(self) -> int: ...
    @property
    def ias(self) -> int: ...
    @property
    def ias_bp(self) -> int: ...
    @property
    def ias_frames(self) -> int: ...
    @property
    def ias_last_frames(self) -> int: ...
    @property
    def cb(self) -> int: ...
    @property
    def cbf(self) -> bool: ...
    @property
    def pdr_pct(self) -> int: ...
    @property
    def life_leech(self) -> int: ...
    @property
    def mf(self) -> int: ...
    @property
    def fr(self) -> int: ...
    @property
    def fr_raw(self) -> int: ...
    @property
    def max_fr(self) -> int: ...
    @property
    def lr(self) -> int: ...
    @property
    def lr_raw(self) -> int: ...
    @property
    def max_lr(self) -> int: ...
    @property
    def cr(self) -> int: ...
    @property
    def cr_raw(self) -> int: ...
    @property
    def max_cr(self) -> int: ...
    @property
    def pr(self) -> int: ...
    @property
    def pr_raw(self) -> int: ...
    @property
    def max_pr(self) -> int: ...
    @property
    def life_no_bo(self) -> int: ...
    @property
    def life_bo(self) -> int: ...
    @property
    def mana_bo(self) -> int: ...
    @property
    def bo_lvl(self) -> int: ...
    @property
    def charm_slots(self) -> int: ...
    @property
    def ar(self) -> int: ...
    @property
    def cth(self) -> int: ...
    @property
    def raw_dps(self) -> float: ...
    @property
    def gear_defense(self) -> int: ...
    @property
    def defense(self) -> int: ...
    @property
    def enemy_cth(self) -> int: ...
    @property
    def block_pct(self) -> int: ...
    @property
    def fbr(self) -> int: ...
    @property
    def fbr_bp(self) -> int: ...
    @property
    def fbr_frames(self) -> int: ...
    @property
    def has_shield(self) -> bool: ...
    @property
    def items(self) -> list[ItemSpec]: ...
    @property
    def charms(self) -> list[CharmSpec]: ...
    @property
    def evaluated_candidates(self) -> int: ...

def blizzard_damage(skills: int) -> tuple[float, float, int]: ...
def blizzard_damage_with_base(
    skills: int,
    blizz_base: int = 20,
    syn_pts: int = 54,
    cm_base: int = 20,
) -> tuple[float, float, int]: ...
def evaluate_build(
    items: list[ItemSpec],
    charms: list[CharmSpec],
    base_life: int = 0,
    base_mana: int = 0,
    base_hell_res: int = -100,
    bo_base_bonus: int = 4,
    blizz_base_lvl: int = 20,
    blizz_syn_pts: int = 54,
    cm_base_lvl: int = 20,
    char_class: int = 1,
    use_bo: bool = True,
    base_max_fr: int = 0,
    base_max_lr: int = 0,
    base_max_cr: int = 0,
    base_max_pr: int = 0,
    constraints: BuildConstraints | None = None,
) -> BuildResult: ...
def optimize_builds(
    items: list[ItemSpec],
    charms: list[CharmSpec],
    constraints: BuildConstraints,
    baseline: BuildResult | None = None,
) -> list[BuildResult]: ...
def score_of_result(
    result: BuildResult,
    constraints: BuildConstraints,
) -> tuple[int, int, int, int, int, int, int, int, int, int]: ...
def class_breakpoints(char_class: int) -> tuple[list[int], list[int]]: ...
