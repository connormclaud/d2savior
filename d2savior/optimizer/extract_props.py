"""Property accumulation and class-specific stat mapping for optimizer extraction."""

from collections.abc import Sequence
from dataclasses import dataclass

from d2savior.core.enums import CharClass
from d2savior.core.property import adjust_property_values
from d2savior.core.resolver import GameDataResolver
from d2savior.optimizer.native import CharmSpec, ItemSpec
from d2savior.optimizer.paladin import PALADIN_SPEC_INFO
from d2savior.optimizer.skill_tables import frozen_orb_avg_dmg_2x, venom_dps_2x

_SKILL_CRITICAL_STRIKE = 9
_SKILL_STATIC_FIELD = 42
_SKILL_BLIZZARD = 59
_SKILL_FROZEN_ORB = 64
_SKILL_COLD_MASTERY = 65
_SKILL_LIFE_TAP = 82
_SKILL_DECREPIFY = 87
_SKILL_ZEAL = 106
_SKILL_HOLY_SHIELD = 117
_SKILL_FANATICISM = 122
_SKILL_CONVICTION = 123
_SKILL_VENOM = 278
_FLAT_FIRE_PIDS: frozenset[int] = frozenset({48, 49})
_FLAT_ELEM_PIDS: frozenset[int] = frozenset({50, 51, 52, 53, 54, 55})
_ELEMENTAL_AURA_SPECS: frozenset[str] = frozenset({"holy-fire", "holy-freeze", "holy-shock"})
_MELEE_ACTION_SPECS: frozenset[str] = frozenset({"sacrifice", "charge", "vengeance"})
_SUPPORT_AURA_IDS: frozendict[str, int] = frozendict(
    {
        "zeal": _SKILL_FANATICISM,
        "sacrifice": _SKILL_FANATICISM,
        "charge": _SKILL_FANATICISM,
        "leveling": _SKILL_FANATICISM,
        "vengeance": _SKILL_CONVICTION,
    }
)

_SIMPLE_ITEM_STAT_MAP: frozendict[int, str] = frozendict(
    {
        0: "str_bonus",
        1: "ene",
        2: "dex_bonus",
        3: "vit",
        7: "life",
        9: "mana",
        20: "block_pct",
        34: "dr_flat",
        35: "mdr",
        36: "pdr_pct",
        39: "fr",
        40: "max_fr",
        41: "lr",
        42: "max_lr",
        43: "cr",
        44: "max_cr",
        45: "pr",
        46: "max_pr",
        76: "pct_life",
        77: "pct_mana",
        80: "mf",
        91: "req_pct",
        96: "frw",
        99: "fhr",
        102: "fbr",
        105: "fcr",
        127: "all_skills",
        142: "fire_abs_pct",
        187: "cold_sunder",
    }
)

_PER_LEVEL_STAT_MAP: frozendict[int, str] = frozendict(
    {
        216: "life_per_lvl",
        217: "mana_per_lvl",
        220: "str_bonus",
        221: "dex_bonus",
        222: "ene",
        223: "vit",
        230: "cr",
        231: "fr",
        232: "lr",
        233: "pr",
        240: "mf",
    }
)

_PAL_SIMPLE_STAT_MAP: frozendict[int, str] = frozendict({93: "ias", 136: "cb", 60: "life_leech"})

_USEFUL_ITEM_STATS: tuple[str, ...] = (
    "all_skills",
    "sorc_skills",
    "pal_skills",
    "blizz_skills",
    "cm_skills",
    "primary_skill",
    "action_skill_bonus",
    "aura_skill_bonus",
    "off_ed",
    "flat_phys_2x",
    "flat_fire_2x",
    "flat_elem_2x",
    "cold_dmg_pct",
    "ds",
    "cs_oskill",
    "ow",
    "ed_demon",
    "ed_undead",
    "psn_dps_2x",
    "pierce",
    "ctc_static_pct",
    "ctc_venom_dps_2x",
    "ctc_decrep_pct",
    "ctc_lifetap_pct",
    "ctc_orb_dmg_2x",
    "ar",
    "ar_pct",
    "itd",
    "target_def_pct",
    "fcr",
    "fhr",
    "frw",
    "ias",
    "cb",
    "cbf",
    "pdr_pct",
    "life_leech",
    "fr",
    "lr",
    "cr",
    "pr",
    "max_fr",
    "max_lr",
    "max_cr",
    "max_pr",
    "mf",
    "life",
    "life_per_lvl",
    "mana",
    "mana_per_lvl",
    "vit",
    "ene",
    "pct_life",
    "pct_mana",
    "mdr",
    "dr_flat",
    "fire_abs_pct",
    "str_bonus",
    "dex_bonus",
)


@dataclass
class _PropAcc:
    all_skills: int = 0
    sorc_skills: int = 0
    pal_skills: int = 0
    blizz_skills: int = 0
    cm_skills: int = 0
    primary_skill: int = 0
    action_skill_bonus: int = 0
    aura_skill_bonus: int = 0
    off_ed: int = 0
    flat_phys_2x: int = 0
    flat_fire_2x: int = 0
    flat_elem_2x: int = 0
    cold_dmg_pct: int = 0
    ds: int = 0
    cs_oskill: int = 0
    ow: int = 0
    ed_demon: int = 0
    ed_undead: int = 0
    psn_dps_2x: int = 0
    pierce: int = 0
    ctc_static_pct: int = 0
    ctc_venom_dps_2x: int = 0
    ctc_decrep_pct: int = 0
    ctc_lifetap_pct: int = 0
    ctc_orb_dmg_2x: int = 0
    ar: int = 0
    ar_pct: int = 0
    itd: int = 0
    target_def_pct: int = 0
    fcr: int = 0
    fhr: int = 0
    frw: int = 0
    ias: int = 0
    cb: int = 0
    cbf: int = 0
    pdr_pct: int = 0
    life_leech: int = 0
    fr: int = 0
    lr: int = 0
    cr: int = 0
    pr: int = 0
    max_fr: int = 0
    max_lr: int = 0
    max_cr: int = 0
    max_pr: int = 0
    mf: int = 0
    life: int = 0
    life_per_lvl: int = 0
    mana: int = 0
    mana_per_lvl: int = 0
    vit: int = 0
    ene: int = 0
    pct_life: int = 0
    pct_mana: int = 0
    mdr: int = 0
    dr_flat: int = 0
    fire_abs_pct: int = 0
    light_skills: int = 0
    str_bonus: int = 0
    dex_bonus: int = 0
    req_pct: int = 0
    defense: int = 0
    block_pct: int = 0
    fbr: int = 0
    def_skill: int = 0
    cold_sunder: int = 0

    def to_item_spec(
        self,
        name: str,
        slot: str,
        loc: str,
        req_str: int,
        req_dex: int,
        belt_slots: int = 0,
        *,
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
    ) -> ItemSpec:
        return ItemSpec(
            name=name,
            slot=slot,
            loc=loc,
            all_skills=self.all_skills,
            sorc_skills=self.sorc_skills,
            fcr=self.fcr,
            fhr=self.fhr,
            frw=self.frw,
            fr=self.fr,
            lr=self.lr,
            cr=self.cr,
            pr=self.pr,
            mf=self.mf,
            life=self.life,
            mana=self.mana,
            vit=self.vit,
            ene=self.ene,
            pct_mana=self.pct_mana,
            mdr=self.mdr,
            dr_flat=self.dr_flat,
            fire_abs_pct=self.fire_abs_pct,
            str_bonus=self.str_bonus,
            dex_bonus=self.dex_bonus,
            req_str=req_str,
            req_dex=req_dex,
            max_fr=self.max_fr,
            max_lr=self.max_lr,
            max_cr=self.max_cr,
            max_pr=self.max_pr,
            life_per_lvl=self.life_per_lvl,
            mana_per_lvl=self.mana_per_lvl,
            blizz_skills=self.blizz_skills,
            cm_skills=self.cm_skills,
            defense=self.defense,
            belt_slots=belt_slots,
            pal_skills=self.pal_skills,
            primary_skill=self.primary_skill,
            ias=self.ias,
            cb=self.cb,
            cbf=self.cbf,
            pdr_pct=self.pdr_pct,
            life_leech=self.life_leech,
            set_group=set_group,
            set_item_id=set_item_id,
            set_bonuses=list(set_bonuses),
            wsm=wsm,
            wclass=wclass,
            action_skill_bonus=self.action_skill_bonus,
            aura_skill_bonus=self.aura_skill_bonus,
            off_ed=self.off_ed,
            flat_phys_2x=self.flat_phys_2x,
            flat_elem_2x=self.flat_elem_2x,
            wep_phys_2x=wep_phys_2x,
            wep_str_pct=wep_str_pct,
            wep_dex_pct=wep_dex_pct,
            can_zeal=can_zeal,
            splash_fire=splash_fire,
            splash_fire_2x=splash_fire_2x,
            cold_dmg_pct=self.cold_dmg_pct,
            global_set_bonuses=list(global_set_bonuses),
            pct_life=self.pct_life,
            ar=self.ar,
            ar_pct=self.ar_pct,
            itd=self.itd,
            target_def_pct=self.target_def_pct,
            flat_fire_2x=self.flat_fire_2x,
            ds=self.ds,
            cs_oskill=self.cs_oskill,
            ow=self.ow,
            ed_demon=self.ed_demon,
            ed_undead=self.ed_undead,
            psn_dps_2x=self.psn_dps_2x,
            pierce=self.pierce,
            ctc_static_pct=self.ctc_static_pct,
            ctc_venom_dps_2x=self.ctc_venom_dps_2x,
            ctc_decrep_pct=self.ctc_decrep_pct,
            ctc_lifetap_pct=self.ctc_lifetap_pct,
            ctc_orb_dmg_2x=self.ctc_orb_dmg_2x,
            block_pct=self.block_pct,
            fbr=self.fbr,
            def_skill=self.def_skill,
        )

    def to_charm_spec(
        self,
        name: str,
        size: int,
        loc: str,
        unique_id: int | None,
        char_class: int = int(CharClass.SORCERESS),
    ) -> CharmSpec:
        cls_skills = self.pal_skills if char_class == int(CharClass.PALADIN) else self.sorc_skills
        return CharmSpec(
            name=name,
            size=size,
            loc=loc,
            fhr=self.fhr,
            fr=self.fr,
            lr=self.lr,
            cr=self.cr,
            pr=self.pr,
            mf=self.mf,
            life=self.life,
            mana=self.mana,
            frw=self.frw,
            light_skills=self.light_skills,
            str_bonus=self.str_bonus,
            dex_bonus=self.dex_bonus,
            skills=cls_skills,
            unique_id=unique_id,
            cold_sunder=bool(self.cold_sunder) and char_class == int(CharClass.SORCERESS),
            action_skills=self.action_skill_bonus,
            aura_skills=self.aura_skill_bonus,
            all_skills=self.all_skills,
            vit=self.vit,
            ene=self.ene,
            ar=self.ar,
            flat_phys_2x=self.flat_phys_2x,
            flat_fire_2x=self.flat_fire_2x,
            flat_elem_2x=self.flat_elem_2x,
            psn_dps_2x=self.psn_dps_2x,
        )


def _apply_per_lvl_prop(
    acc: _PropAcc, pid: int, pval: int, resolver: GameDataResolver, char_level: int
) -> None:
    per_lvl_attr = _PER_LEVEL_STAT_MAP[pid]
    scaled = adjust_property_values(pid, [pval], resolver.data.get_stat(pid), char_level=char_level)
    if isinstance(scaled, int):
        setattr(acc, per_lvl_attr, getattr(acc, per_lvl_attr) + scaled)


def _apply_sorc_prop(
    acc: _PropAcc,
    pid: int,
    params: list[int],
    *,
    pval: int | None = None,
    sorc_filler_id: int | None = None,
    sorc_armor_id: int | None = None,
) -> None:
    sorc_id = int(CharClass.SORCERESS)
    if pid == 83 and len(params) >= 2 and params[0] == sorc_id:
        acc.sorc_skills += params[1]
    elif pid == 331:
        acc.cold_dmg_pct += pval if pval is not None else (params[0] if params else 0)
    elif pid == 107 and len(params) >= 2:
        if params[0] == _SKILL_BLIZZARD:
            acc.blizz_skills += params[1]
        elif params[0] == _SKILL_COLD_MASTERY:
            acc.cm_skills += params[1]
        elif sorc_filler_id is not None and params[0] == sorc_filler_id:
            acc.action_skill_bonus += params[1]
        if sorc_armor_id is not None and params[0] == sorc_armor_id:
            acc.def_skill += params[1]
    elif pid == 188 and len(params) >= 3 and params[1] == sorc_id:
        # Sorceress skill tab: 0=Fire, 1=Lightning, 2=Cold
        if params[0] == 1:
            acc.light_skills += params[2]
        elif params[0] == 2:
            acc.sorc_skills += params[2]


def _apply_paladin_staffmod(
    acc: _PropAcc,
    params: list[int],
    pal_spec: str,
    pal_primary_id: int | None,
    pal_offense: str,
    pal_aura_id: int | None,
    split_skills: bool,
) -> None:
    if params[0] == _SKILL_HOLY_SHIELD:
        acc.def_skill += params[1]
    if not split_skills:
        if pal_primary_id is not None and params[0] == pal_primary_id:
            acc.primary_skill += params[1]
        return
    eff_aura_id = (
        (pal_primary_id if pal_spec in _ELEMENTAL_AURA_SPECS else _SUPPORT_AURA_IDS.get(pal_spec))
        if pal_aura_id == -1
        else pal_aura_id
    )
    is_action = (params[0] == _SKILL_ZEAL and pal_offense == "zeal") or (
        pal_offense == "melee" and pal_spec in _MELEE_ACTION_SPECS and params[0] == pal_primary_id
    )
    if is_action:
        acc.action_skill_bonus += params[1]
    if eff_aura_id is not None and params[0] == eff_aura_id:
        acc.aura_skill_bonus += params[1]


def _apply_paladin_skill_prop(
    acc: _PropAcc,
    pid: int,
    params: list[int],
    pal_spec: str,
    pal_primary_id: int | None,
    pal_tabs: frozenset[int],
    pal_offense: str,
    pal_aura_id: int | None = -1,
) -> bool:
    pal_id = int(CharClass.PALADIN)
    split_skills = pal_offense in ("zeal", "melee")
    if pid == 83 and len(params) >= 2 and params[0] == pal_id:
        acc.pal_skills += params[1]
        return True
    if pid == 188 and len(params) >= 3 and params[1] == pal_id:
        if split_skills:
            if params[0] == 0:
                acc.action_skill_bonus += params[2]
                acc.def_skill += params[2]
            elif params[0] == 1:
                acc.aura_skill_bonus += params[2]
        elif params[0] in pal_tabs:
            acc.pal_skills += params[2]
            if params[0] != 0:
                acc.def_skill -= params[2]
        elif params[0] == 0:
            acc.def_skill += params[2]
        return True
    if pid == 126 and len(params) >= 2 and params[0] == 1 and pal_spec == "holy-fire":
        if split_skills:
            acc.aura_skill_bonus += params[1]
        else:
            acc.pal_skills += params[1]
            acc.def_skill -= params[1]
        return True
    if pid == 107 and len(params) >= 2:
        _apply_paladin_staffmod(
            acc, params, pal_spec, pal_primary_id, pal_offense, pal_aura_id, split_skills
        )
        return True
    return False


_PAL_MELEE_STAT_MAP: frozendict[int, str] = frozendict(
    {
        19: "ar",
        119: "ar_pct",
        116: "target_def_pct",
        121: "ed_demon",
        122: "ed_undead",
        135: "ow",
        141: "ds",
        156: "pierce",
    }
)
_PAL_MELEE_PER_LVL_MAP: frozendict[int, str] = frozendict(
    {224: "ar", 225: "ar_pct", 243: "ed_demon", 244: "ed_undead", 248: "ow", 250: "ds"}
)
_PAL_CTC_CHANCE_MAP: frozendict[int, str] = frozendict(
    {_SKILL_STATIC_FIELD: "ctc_static_pct", _SKILL_DECREPIFY: "ctc_decrep_pct"}
)


def _apply_scaled_stat(
    acc: _PropAcc,
    pid: int,
    pval: int,
    attr: str,
    resolver: GameDataResolver,
    char_level: int,
) -> None:
    scaled = adjust_property_values(pid, [pval], resolver.data.get_stat(pid), char_level=char_level)
    if isinstance(scaled, int):
        setattr(acc, attr, getattr(acc, attr) + scaled)


def _apply_paladin_ctc_prop(acc: _PropAcc, params: list[int], pal_offense: str) -> None:
    if len(params) < 3:
        return
    slvl, sid, chance = params[0], params[1], params[2]
    if sid == _SKILL_LIFE_TAP:
        acc.ctc_lifetap_pct += chance
        return
    if pal_offense not in ("zeal", "melee"):
        return
    if attr := _PAL_CTC_CHANCE_MAP.get(sid):
        setattr(acc, attr, getattr(acc, attr) + chance)
    elif sid == _SKILL_VENOM:
        acc.ctc_venom_dps_2x = max(acc.ctc_venom_dps_2x, venom_dps_2x(slvl))
    elif sid == _SKILL_FROZEN_ORB:
        acc.ctc_orb_dmg_2x += round((chance / 100.0) * frozen_orb_avg_dmg_2x(slvl))


def _apply_paladin_melee_combat_prop(
    acc: _PropAcc,
    pid: int,
    pval: int,
    params: list[int],
    resolver: GameDataResolver,
    char_level: int,
    *,
    is_weapon: bool,
) -> None:
    if attr := _PAL_MELEE_STAT_MAP.get(pid):
        setattr(acc, attr, getattr(acc, attr) + pval)
    elif lvl_attr := _PAL_MELEE_PER_LVL_MAP.get(pid):
        _apply_scaled_stat(acc, pid, pval, lvl_attr, resolver, char_level)
    elif pid in _FLAT_FIRE_PIDS:
        acc.flat_fire_2x += pval
    elif pid in _FLAT_ELEM_PIDS:
        acc.flat_elem_2x += pval
    elif not is_weapon and pid in (17, 25):
        acc.off_ed += pval
    elif not is_weapon and pid in (21, 22):
        acc.flat_phys_2x += pval
    elif not is_weapon and pid in (218, 219):
        _apply_scaled_stat(
            acc, pid, pval, "flat_phys_2x" if pid == 218 else "off_ed", resolver, char_level
        )
    elif pid == 97 and len(params) >= 2 and params[0] == _SKILL_CRITICAL_STRIKE:
        acc.cs_oskill += params[1]
    elif pid == 57:
        rate_sum = (params[0] + params[1]) if len(params) >= 2 else (params[0] if params else 0)
        acc.psn_dps_2x += round(rate_sum * 25.0 / 256.0)
    elif pid == 58:
        acc.psn_dps_2x += round(pval * 25.0 / 256.0)
    elif pid == 115 and pval > 0:
        acc.itd = 1
    elif pid in (123, 124) and pval > 0:
        acc.ar += max(1, pval // 3)


def _apply_paladin_prop(
    acc: _PropAcc,
    pid: int,
    pval: int,
    params: list[int],
    resolver: GameDataResolver,
    char_level: int,
    pal_spec: str,
    pal_primary_id: int | None,
    pal_tabs: frozenset[int],
    *,
    pal_offense: str = "caster",
    is_weapon: bool = False,
    pal_aura_id: int | None = -1,
) -> None:
    if pal_attr := _PAL_SIMPLE_STAT_MAP.get(pid):
        setattr(acc, pal_attr, getattr(acc, pal_attr) + pval)
    elif _apply_paladin_skill_prop(
        acc, pid, params, pal_spec, pal_primary_id, pal_tabs, pal_offense, pal_aura_id
    ):
        return
    elif pid == 247:
        _apply_scaled_stat(acc, pid, pval, "cb", resolver, char_level)
    elif pid in (195, 198):
        _apply_paladin_ctc_prop(acc, params, pal_offense)
    elif pal_offense in ("zeal", "melee"):
        _apply_paladin_melee_combat_prop(
            acc, pid, pval, params, resolver, char_level, is_weapon=is_weapon
        )


def _apply_props_to_acc(
    acc: _PropAcc,
    props: Sequence[tuple[int, int, list[int]]],
    resolver: GameDataResolver,
    char_level: int,
    *,
    char_class: int,
    pal_spec: str,
    pal_offense: str = "caster",
    is_weapon: bool = False,
    include_defense_props: bool = False,
    sorc_filler_id: int | None = None,
    sorc_armor_id: int | None = None,
    pal_aura_id: int | None = -1,
) -> None:
    pal_primary_id, _, pal_tabs = PALADIN_SPEC_INFO.get(pal_spec, (None, None, frozenset({0, 1})))
    for pid, val, params in props:
        pval = params[0] if params else val
        if attr := _SIMPLE_ITEM_STAT_MAP.get(pid):
            setattr(acc, attr, getattr(acc, attr) + pval)
        elif pid in _PER_LEVEL_STAT_MAP:
            _apply_per_lvl_prop(acc, pid, pval, resolver, char_level)
        elif pid == 153 and pval > 0:
            acc.cbf = 1
        elif include_defense_props and pid == 31:
            acc.defense += pval
        elif include_defense_props and pid == 214:
            scaled = adjust_property_values(
                pid, [pval], resolver.data.get_stat(pid), char_level=char_level
            )
            if isinstance(scaled, int):
                acc.defense += scaled
        elif char_class == int(CharClass.SORCERESS):
            _apply_sorc_prop(
                acc,
                pid,
                params,
                pval=pval,
                sorc_filler_id=sorc_filler_id,
                sorc_armor_id=sorc_armor_id,
            )
        elif char_class == int(CharClass.PALADIN):
            _apply_paladin_prop(
                acc,
                pid,
                pval,
                params,
                resolver,
                char_level,
                pal_spec,
                pal_primary_id,
                pal_tabs,
                pal_offense=pal_offense,
                is_weapon=is_weapon,
                pal_aura_id=pal_aura_id,
            )
