class ItemSpec:
    name: str
    slot: str
    loc: str
    all_skills: int
    sorc_skills: int
    blizz_skills: int
    cm_skills: int
    fcr: int
    fhr: int
    frw: int
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

    def __init__(
        self,
        name: str,
        slot: str,
        loc: str = "",
        all_skills: int = 0,
        sorc_skills: int = 0,
        fcr: int = 0,
        fhr: int = 0,
        frw: int = 0,
        fr: int = 0,
        lr: int = 0,
        cr: int = 0,
        pr: int = 0,
        mf: int = 0,
        life: int = 0,
        mana: int = 0,
        vit: int = 0,
        ene: int = 0,
        pct_mana: int = 0,
        mdr: int = 0,
        dr_flat: int = 0,
        fire_abs_pct: int = 0,
        str_bonus: int = 0,
        dex_bonus: int = 0,
        req_str: int = 0,
        req_dex: int = 0,
        max_fr: int = 0,
        max_lr: int = 0,
        max_cr: int = 0,
        max_pr: int = 0,
        life_per_lvl: int = 0,
        mana_per_lvl: int = 0,
        blizz_skills: int = 0,
        cm_skills: int = 0,
        defense: int = 0,
        belt_slots: int = 0,
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
    unique_id: int | None

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
        light_skills: int = 0,
        str_bonus: int = 0,
        dex_bonus: int = 0,
        skills: int = 0,
        unique_id: int | None = None,
    ) -> None: ...

class BuildConstraints:
    allow_mf: bool
    min_fcr: int
    min_fhr: int
    min_fr: int
    min_lr: int
    min_cr: int
    min_pr: int
    max_charm_slots: int
    mode: str
    base_life: int
    base_mana: int
    base_hell_res: int
    base_str: int
    base_dex: int
    bo_base_bonus: int
    blizz_base_lvl: int
    blizz_syn_pts: int
    cm_base_lvl: int
    limit: int

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
        mode: str = "power",
        base_life: int = 0,
        base_mana: int = 0,
        base_hell_res: int = -100,
        base_str: int = 0,
        base_dex: int = 0,
        bo_base_bonus: int = 4,
        limit: int = 5,
        blizz_base_lvl: int = 20,
        blizz_syn_pts: int = 54,
        cm_base_lvl: int = 20,
    ) -> None: ...

class BuildResult:
    @property
    def skills(self) -> int: ...
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
) -> BuildResult: ...
def optimize_builds(
    items: list[ItemSpec],
    charms: list[CharmSpec],
    constraints: BuildConstraints,
) -> list[BuildResult]: ...
