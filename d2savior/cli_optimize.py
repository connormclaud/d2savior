import argparse
import sys
lazy from pathlib import Path

lazy from d2savior.cli import (
    _common_parser,
    _resolve_and_save_targets,
    parse_d2i_file,
    parse_d2s_file,
)
lazy from d2savior.core.constants import DIFFICULTY_NAMES
lazy from d2savior.core.d2s_struct import D2SStruct
lazy from d2savior.core.enums import CharClass
lazy from d2savior.core.resolver import GameDataResolver
lazy from d2savior.core.stash import SharedStash
lazy from d2savior.core.stats import get_current_difficulty, get_difficulty_resist_penalty
lazy from d2savior.optimizer import (
    PALADIN_BUILD_CHOICES,
    SORC_ONLY_BUILD_CHOICES,
    SUPPORTED_OPTIMIZER_CLASSES,
    CharmSpec,
    ConstraintOverrides,
    ItemSpec,
    build_paladin_preset_constraints,
    extract_pool,
    format_build_report,
    format_paladin_leveling_report,
    format_socket_report,
    list_presets,
    optimize_builds,
    optimize_paladin_leveling,
    optimize_socket_quests,
    paladin_primary_skill_info,
    parse_keep_gear,
    resolve_build_expr,
    select_sorc_presets,
    validate_supported_class,
)
lazy from d2savior.optimizer.skill_tables import build_sorc_dps_tables, resolve_skill_override


def _resolve_primary_optimize_char(
    chars: list[D2SStruct], target_name: str | None, build: str
) -> tuple[D2SStruct | None, str | None]:
    build_lower = build.lower()
    if target_name is not None:
        for ch in chars:
            if ch.get_char_name().lower() == target_name.lower():
                return ch, None
        return None, f"Error: Character '{target_name}' not found in target saves"

    allowed_classes: tuple[CharClass, ...]
    if build_lower in SORC_ONLY_BUILD_CHOICES:
        allowed_classes, class_label = (CharClass.SORCERESS,), "Sorceress"
    elif build_lower in PALADIN_BUILD_CHOICES:
        allowed_classes, class_label = (CharClass.PALADIN,), "Paladin"
    else:
        allowed_classes, class_label = SUPPORTED_OPTIMIZER_CLASSES, "optimizable"
    candidates = [ch for ch in chars if ch.char_class in allowed_classes]
    if not candidates:
        no_cls_msg = (
            "Sorceress or Paladin"
            if allowed_classes == SUPPORTED_OPTIMIZER_CLASSES
            else class_label
        )
        return None, f"Error: No {no_cls_msg} character found in target saves"
    if len(candidates) > 1:
        names = ", ".join(ch.get_char_name() for ch in candidates)
        return (
            None,
            f"Error: Multiple {class_label} characters found ({names}); specify a character name",
        )
    return candidates[0], None


def _load_optimize_pool(
    files_to_process: list[str],
    target_name: str | None,
    resolver: GameDataResolver,
    *,
    build: str = "all",
) -> tuple[D2SStruct | None, list[D2SStruct], list[SharedStash], str | None]:
    chars: list[D2SStruct] = []
    stashes: list[SharedStash] = []
    for f in files_to_process:
        lower = f.lower()
        if lower.endswith(".d2s"):
            ok, char_data, _ = parse_d2s_file(f, resolver=resolver)
            if ok and char_data is not None:
                chars.append(char_data)
        elif lower.endswith(".d2i"):
            ok, stash_data, kind, _ = parse_d2i_file(f, resolver=resolver)
            if ok and kind == "stash" and isinstance(stash_data, SharedStash):
                stashes.append(stash_data)

    primary, err = _resolve_primary_optimize_char(chars, target_name, build)
    if primary is None:
        return None, [], stashes, err

    try:
        validate_supported_class(primary)
    except ValueError as exc:
        return None, [], stashes, f"Error: {exc}"

    build_lower = build.lower()
    if primary.char_class == CharClass.SORCERESS and build_lower in PALADIN_BUILD_CHOICES:
        return (
            None,
            [],
            stashes,
            f"Error: Build preset '{build}' is only supported for Paladin; '{primary.get_char_name()}' is Sorceress",
        )
    if primary.char_class == CharClass.PALADIN and build_lower in SORC_ONLY_BUILD_CHOICES:
        return (
            None,
            [],
            stashes,
            f"Error: Build preset '{build}' is only supported for Sorceress; '{primary.get_char_name()}' is Paladin",
        )

    extras = [ch for ch in chars if ch is not primary]
    return primary, extras, stashes, None


def _run_sorc_optimize(
    primary: D2SStruct,
    extras: list[D2SStruct],
    stashes: list[SharedStash],
    items: list[ItemSpec],
    charms: list[CharmSpec],
    resolver: GameDataResolver,
    args: argparse.Namespace,
    primary_inv_loc: str,
    *,
    left_skill: int | None = None,
    right_skill: int | None = None,
    overrides: ConstraintOverrides | None = None,
) -> None:
    filler_name = build_sorc_dps_tables(
        primary, left_skill=left_skill, right_skill=right_skill, targets=args.targets
    ).filler_skill_name
    diff_idx = get_current_difficulty(primary)
    diff_name = DIFFICULTY_NAMES[diff_idx]
    resist_penalty = get_difficulty_resist_penalty(primary, diff_idx)
    for title, constraints in select_sorc_presets(
        primary,
        build=args.build,
        max_charm_slots=args.charm_slots,
        limit=args.limit,
        extra_chars=extras,
        stashes=stashes,
        resolver=resolver,
        keep_equipped=args.keep_gear,
        targets=args.targets,
        target_type=args.target_type,
        left_skill=left_skill,
        right_skill=right_skill,
        overrides=overrides,
    ):
        results = optimize_builds(items, charms, constraints)
        print(
            format_build_report(
                title,
                results,
                charms,
                diff_name=diff_name,
                resist_penalty=resist_penalty,
                primary_inv_loc=primary_inv_loc,
                filler_skill_name=filler_name,
            )
        )
        print()


def _run_paladin_optimize(
    primary: D2SStruct,
    extras: list[D2SStruct],
    stashes: list[SharedStash],
    items: list[ItemSpec],
    charms: list[CharmSpec],
    resolver: GameDataResolver,
    args: argparse.Namespace,
    primary_inv_loc: str,
    *,
    left_skill: int | None = None,
    right_skill: int | None = None,
    overrides: ConstraintOverrides | None = None,
) -> None:
    resolved_presets = resolve_build_expr(
        args.build,
        CharClass.PALADIN,
        overrides=overrides,
        char_name=primary.get_char_name(),
    )
    has_mode_override = overrides is not None and overrides.mode is not None
    resist_penalty = get_difficulty_resist_penalty(primary)
    for preset in resolved_presets:
        use_probe = (
            preset.strategy == "leveling-probe"
            and not has_mode_override
            and preset.mode == "leveling-res"
        )
        if use_probe:
            title, options, resolved_spec, diff_name = optimize_paladin_leveling(
                primary,
                items,
                charms,
                max_charm_slots=args.charm_slots,
                limit=args.limit,
                extra_chars=extras,
                stashes=stashes,
                resolver=resolver,
                keep_equipped=args.keep_gear,
                targets=args.targets,
                target_type=args.target_type,
                left_skill=left_skill,
                right_skill=right_skill,
                overrides=preset.to_overrides(),
                title=preset.title,
            )
            skill_name, base_skill_lvl = paladin_primary_skill_info(primary, resolved_spec)
            report = format_paladin_leveling_report(
                title,
                options,
                charms,
                diff_name=diff_name,
                resist_penalty=resist_penalty,
                primary_skill_name=skill_name,
                primary_skill_base=base_skill_lvl,
                primary_inv_loc=primary_inv_loc,
            )
        else:
            title, constraints, resolved_spec, diff_name = build_paladin_preset_constraints(
                primary,
                preset,
                max_charm_slots=args.charm_slots,
                limit=args.limit,
                extra_chars=extras,
                stashes=stashes,
                resolver=resolver,
                keep_equipped=args.keep_gear,
                targets=args.targets,
                target_type=args.target_type,
                left_skill=left_skill,
                right_skill=right_skill,
            )
            skill_name, base_skill_lvl = paladin_primary_skill_info(primary, resolved_spec)
            report = format_build_report(
                title,
                optimize_builds(items, charms, constraints),
                charms,
                char_class=primary.char_class,
                diff_name=diff_name,
                resist_penalty=resist_penalty,
                primary_skill_name=skill_name,
                primary_skill_base=base_skill_lvl,
                primary_inv_loc=primary_inv_loc,
            )
        print(report)
        print()


def _is_valid_keep_gear_expr(token: str) -> bool:
    try:
        parse_keep_gear(token)
        return True
    except ValueError:
        return False


def _has_other_optimize_target(argv: list[str], value_opts: set[str]) -> bool:
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--":
            return i + 1 < len(argv)
        if tok == "--char" or tok.startswith("--char="):
            return True
        if tok == "--keep-gear":
            i += 2 if (i + 1 < len(argv) and not argv[i + 1].startswith("-")) else 1
            continue
        if tok in value_opts:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        return True
    return False


def _normalize_keep_gear_argv(argv: list[str], parser: argparse.ArgumentParser) -> list[str]:
    """Prevent bare ``--keep-gear`` from greedily consuming a following positional target."""
    if "--keep-gear" not in argv:
        return argv
    value_opts = {
        opt
        for action in parser._actions
        if action.option_strings and action.nargs not in (0, "?")
        for opt in action.option_strings
    }
    has_other_target = _has_other_optimize_target(argv, value_opts)

    out: list[str] = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--":
            out.extend(argv[i:])
            break
        if tok == "--keep-gear" and i + 1 < len(argv) and not argv[i + 1].startswith("-"):
            nxt = argv[i + 1]
            if _is_valid_keep_gear_expr(nxt):
                out.append(f"--keep-gear={nxt}")
                i += 2
                continue
            is_path = Path(nxt).exists() or nxt.lower().endswith((".d2s", ".d2i"))
            if is_path or ("+" not in nxt and not has_other_target):
                out.append("--keep-gear=all")
                i += 1
                continue
        out.append(tok)
        i += 1
    return out


def _split_optimize_targets(
    raw_targets: list[str], explicit_char: str | None
) -> tuple[str | None, list[str]]:
    """Separate an optional positional character name from explicit save paths."""
    char_name = explicit_char
    paths: list[str] = []
    for entry in raw_targets:
        p = Path(entry)
        if p.exists() or entry.lower().endswith((".d2s", ".d2i")):
            paths.append(entry)
            if char_name is None and entry.lower().endswith(".d2s"):
                char_name = p.stem
        elif char_name is None:
            char_name = entry
        else:
            paths.append(entry)
    return char_name, paths


def _build_optimize_parser(
    *,
    prog: str = "d2savior optimize",
    description: str = (
        "Optimize Sorceress or Paladin leveling builds across characters and shared stash "
        "(use 'optimize socket' to find the best item for Larzuk's Socket Quest)"
    ),
    default_limit: int = 3,
    include_socket_flags: bool = False,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=description,
        parents=[_common_parser],
    )
    parser.add_argument(
        "--char",
        default=None,
        help="Target character name (Sorceress or Paladin; can also be passed positionally)",
    )
    parser.add_argument(
        "-b",
        "--build",
        default="all",
        help=(
            "Build preset expression: a preset name, 'a+b' (merge), 'a,b' (multi-run), "
            "or any name from --list-builds (default: all)"
        ),
    )
    parser.add_argument(
        "--list-builds",
        action="store_true",
        help="List all available built-in and user build presets and exit",
    )
    parser.add_argument(
        "--charm-slots",
        type=int,
        default=23,
        help="Maximum inventory charm slots to allocate (default: 23)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=default_limit,
        help=f"Maximum top options to show per build preset (default: {default_limit})",
    )
    parser.add_argument(
        "--keep-gear",
        nargs="?",
        const="all",
        default=None,
        metavar="SLOTS",
        help=(
            "Keep currently equipped active gear slots: all (default), groups "
            "(weapon=weapon+shield, jewelry=amulet+rings, armor=helm/chest/belt/gloves/boots), "
            "individual slots (helm, chest/body, belt, gloves, boots, amulet, ring/rings, shield), "
            "or '+' combinations (e.g. weapon+helm+boots)"
        ),
    )
    parser.add_argument(
        "--targets",
        type=int,
        default=1,
        help="Number of simultaneous targets for AoE DPS (e.g. 1=boss, 3=pack; default: 1)",
    )
    parser.add_argument(
        "--target-type",
        choices=("boss", "champion", "trash"),
        default="champion",
        help=(
            "Target monster class for AR/CTH: champion (default; ITD disabled, gear -%% Def halved), "
            "boss (1.5x defense, ITD disabled, gear -%% Def halved), or trash (normal; full ITD/-%% Def)"
        ),
    )
    parser.add_argument(
        "--left-skill",
        default=None,
        help="Override left-click active skill (e.g. ice-blast, glacial-spike, zeal, attack, none)",
    )
    parser.add_argument(
        "--right-skill",
        default=None,
        help="Override right-click active skill (e.g. blizzard, holy-fire, holy-freeze, holy-shock)",
    )
    # Constraint override flags
    parser.add_argument(
        "--mode",
        default=None,
        metavar="MODE",
        help="Override search mode (power, mf, max-res, leveling, leveling-res)",
    )
    parser.add_argument(
        "--cbf",
        dest="require_cbf",
        action="store_true",
        default=None,
        help="Require Cannot Be Frozen",
    )
    parser.add_argument(
        "--no-cbf",
        dest="require_cbf",
        action="store_false",
        help="Do not require Cannot Be Frozen",
    )
    parser.add_argument(
        "--mf",
        dest="allow_mf",
        action="store_true",
        default=None,
        help="Allow Magic Find gear",
    )
    parser.add_argument(
        "--no-mf",
        dest="allow_mf",
        action="store_false",
        help="Disallow Magic Find gear",
    )
    parser.add_argument("--min-fcr", type=int, default=None, metavar="N", help="Minimum FCR floor")
    parser.add_argument("--min-fhr", type=int, default=None, metavar="N", help="Minimum FHR floor")
    parser.add_argument(
        "--min-fr", type=int, default=None, metavar="N", help="Minimum fire resist floor"
    )
    parser.add_argument(
        "--min-lr", type=int, default=None, metavar="N", help="Minimum lightning resist floor"
    )
    parser.add_argument(
        "--min-cr", type=int, default=None, metavar="N", help="Minimum cold resist floor"
    )
    parser.add_argument(
        "--min-pr", type=int, default=None, metavar="N", help="Minimum poison resist floor"
    )
    parser.add_argument(
        "--ignore-pr",
        action="store_true",
        help="Ignore poison resist floor (shorthand for --min-pr 0)",
    )
    parser.add_argument(
        "--min-frw", type=int, default=None, metavar="N", help="Minimum Faster Run/Walk floor"
    )
    parser.add_argument("--min-ias", type=int, default=None, metavar="N", help="Minimum IAS floor")
    parser.add_argument(
        "--min-cb", type=int, default=None, metavar="N", help="Minimum Crushing Blow floor"
    )
    parser.add_argument(
        "--min-ll", type=int, default=None, metavar="N", help="Minimum Life Leech floor"
    )
    parser.add_argument(
        "--min-pdr",
        type=int,
        default=None,
        metavar="N",
        help="Minimum Physical Damage Reduction floor",
    )
    parser.add_argument(
        "--min-mf", type=int, default=None, metavar="N", help="Minimum Magic Find floor"
    )
    if include_socket_flags:
        parser.add_argument(
            "--theoretical",
            "--ideal",
            dest="theoretical",
            action="store_true",
            help="Evaluate theoretical runes, perfect gems, and runewords for a lvl 99 respec unbound by current level and Str/Dex requirements",
        )
    return parser


def _prepare_optimize_run(
    argv: list[str], parser: argparse.ArgumentParser
) -> (
    tuple[
        argparse.Namespace,
        ConstraintOverrides | None,
        int | None,
        int | None,
        D2SStruct,
        list[D2SStruct],
        list[SharedStash],
        GameDataResolver,
    ]
    | int
):
    """Parse optimize args, handle --list-builds, validate flags, and load target character/pool."""
    args = parser.parse_intermixed_args(_normalize_keep_gear_argv(argv, parser))

    if args.list_builds:
        entries = list_presets()
        if not entries:
            print("No build presets found.")
            return 0
        col_w = max(len(e.name) for e in entries) + 2
        for e in entries:
            cls_tag = f"  [{e.char_class}]" if e.char_class else ""
            src_tag = f"  ({e.source})" if e.source != "built-in" else ""
            print(f"  {e.name:<{col_w}}{cls_tag}{src_tag}")
        return 0

    if args.targets < 1:
        parser.error("--targets must be >= 1")

    try:
        parse_keep_gear(args.keep_gear)
    except ValueError as exc:
        parser.error(str(exc))

    min_pr = 0 if args.ignore_pr else args.min_pr
    overrides = ConstraintOverrides(
        mode=args.mode,
        allow_mf=args.allow_mf,
        require_cbf=args.require_cbf,
        min_fcr=args.min_fcr,
        min_fhr=args.min_fhr,
        min_fr=args.min_fr,
        min_lr=args.min_lr,
        min_cr=args.min_cr,
        min_pr=min_pr,
        min_frw=args.min_frw,
        min_ias=args.min_ias,
        min_cb=args.min_cb,
        min_ll=args.min_ll,
        min_pdr=args.min_pdr,
        min_mf=args.min_mf,
    )
    active_overrides = overrides if overrides.as_kwargs() else None

    try:
        left_skill = resolve_skill_override(args.left_skill) if args.left_skill else None
        right_skill = resolve_skill_override(args.right_skill) if args.right_skill else None
    except ValueError as exc:
        parser.error(str(exc))

    target_char, args.file_path = _split_optimize_targets(args.file_path, args.char)
    files_to_process = _resolve_and_save_targets(args)
    if not files_to_process:
        return 1

    resolver = GameDataResolver.load(lang_key=args.lang or "enUS")
    primary, extras, stashes, err = _load_optimize_pool(
        files_to_process, target_char, resolver, build=args.build
    )
    if primary is None:
        print(err or "Error: Character not found in target saves", file=sys.stderr)
        return 1

    return args, active_overrides, left_skill, right_skill, primary, extras, stashes, resolver


def cmd_optimize_socket(argv: list[str]) -> int:
    """Run the Larzuk Socket Quest optimizer (`d2savior optimize socket`)."""
    parser = _build_optimize_parser(
        prog="d2savior optimize socket",
        description=(
            "Find the best unsocketed gear or runeword base for Larzuk's Socket Quest "
            "across characters and shared stash"
        ),
        default_limit=5,
        include_socket_flags=True,
    )
    prepared = _prepare_optimize_run(argv, parser)
    if isinstance(prepared, int):
        return prepared
    args, active_overrides, left_skill, right_skill, primary, extras, stashes, resolver = prepared

    try:
        report = optimize_socket_quests(
            primary,
            extra_chars=extras,
            stashes=stashes,
            resolver=resolver,
            build=args.build,
            max_charm_slots=args.charm_slots,
            limit=args.limit,
            keep_equipped=args.keep_gear,
            targets=args.targets,
            target_type=args.target_type,
            left_skill=left_skill,
            right_skill=right_skill,
            overrides=active_overrides,
            theoretical=args.theoretical,
        )
        print(format_socket_report(report))
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_optimize(argv: list[str]) -> int:
    if argv and argv[0] == "socket":
        return cmd_optimize_socket(argv[1:])

    parser = _build_optimize_parser()
    prepared = _prepare_optimize_run(argv, parser)
    if isinstance(prepared, int):
        return prepared
    args, active_overrides, left_skill, right_skill, primary, extras, stashes, resolver = prepared

    primary_inv_loc = f"{primary.get_char_name()} Inv"
    try:
        items, charms = extract_pool(
            primary,
            extra_chars=extras,
            stashes=stashes,
            resolver=resolver,
            keep_equipped=args.keep_gear,
            left_skill=left_skill,
            right_skill=right_skill,
            targets=args.targets,
        )
        if primary.char_class == CharClass.SORCERESS:
            _run_sorc_optimize(
                primary,
                extras,
                stashes,
                items,
                charms,
                resolver,
                args,
                primary_inv_loc,
                left_skill=left_skill,
                right_skill=right_skill,
                overrides=active_overrides,
            )
        else:
            _run_paladin_optimize(
                primary,
                extras,
                stashes,
                items,
                charms,
                resolver,
                args,
                primary_inv_loc,
                left_skill=left_skill,
                right_skill=right_skill,
                overrides=active_overrides,
            )
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0
