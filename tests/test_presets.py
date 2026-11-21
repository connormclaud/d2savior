"""Unit tests for built-in and user TOML build presets, inheritance, and CLI merging."""

from pathlib import Path

import pytest

from d2savior.core.enums import CharClass
from d2savior.optimizer.presets import (
    ConstraintOverrides,
    list_presets,
    resolve_build_expr,
)


def test_builtin_sorc_and_paladin_presets(tmp_path: Path) -> None:
    sorc_all = resolve_build_expr("all", CharClass.SORCERESS, user_dir=tmp_path)
    assert [p.name for p in sorc_all] == ["base", "mf-speed", "mf-pure", "tz", "max-res"]
    assert sorc_all[0].allow_mf is False
    assert (sorc_all[0].min_fcr, sorc_all[0].min_fhr, sorc_all[0].min_pr) == (105, 86, 75)
    assert (sorc_all[1].mode, sorc_all[1].min_pr) == ("mf", 0)
    assert (sorc_all[4].mode, sorc_all[4].min_fcr, sorc_all[4].min_fhr) == ("max-res", 63, 60)

    pal_all = resolve_build_expr("all", CharClass.PALADIN, user_dir=tmp_path)
    assert len(pal_all) == 1
    assert pal_all[0].name == "leveling"
    assert pal_all[0].strategy == "leveling-probe"

    pal_max_res = resolve_build_expr("max-res", CharClass.PALADIN, user_dir=tmp_path)
    assert len(pal_max_res) == 1
    assert (pal_max_res[0].mode, pal_max_res[0].min_fcr, pal_max_res[0].min_fhr) == (
        "max-res",
        0,
        0,
    )

    power = resolve_build_expr("power", CharClass.SORCERESS, user_dir=tmp_path)
    assert len(power) == 1
    assert (power[0].mode, power[0].min_fcr, power[0].min_fhr) == ("power", 105, 86)


def test_user_presets_extends_and_merge_syntax(tmp_path: Path) -> None:
    (tmp_path / "fast.toml").write_text(
        "require_cbf = true\nmin_frw = 55\nmin_ias = 30\n",
        encoding="utf-8",
    )
    (tmp_path / "tz-fast.toml").write_text(
        'extends = ["tz", "fast"]\nmin_pr = 0\n',
        encoding="utf-8",
    )
    (tmp_path / "bundle.toml").write_text(
        'presets = ["tz+fast", "mf-speed"]\n',
        encoding="utf-8",
    )

    # 1. extends inherits tz and overlays fast + local min_pr = 0.
    ext = resolve_build_expr("tz-fast", CharClass.SORCERESS, user_dir=tmp_path)
    assert len(ext) == 1
    p = ext[0]
    assert (p.mode, p.min_fcr, p.min_fhr, p.min_fr, p.min_pr) == ("power", 105, 86, 75, 0)
    assert (p.require_cbf, p.min_frw, p.min_ias) == (True, 55, 30)

    # 2. Ad-hoc CLI merge (+) and multi-select (,).
    multi = resolve_build_expr("leveling+fast,max-res", CharClass.PALADIN, user_dir=tmp_path)
    assert [x.name for x in multi] == ["leveling+fast", "max-res"]
    assert multi[0].strategy == "leveling-probe"
    assert (multi[0].require_cbf, multi[0].min_frw, multi[0].min_ias) == (True, 55, 30)

    # 3. Group preset referencing a merged expression.
    bundled = resolve_build_expr("bundle", CharClass.SORCERESS, user_dir=tmp_path)
    assert [x.name for x in bundled] == ["tz+fast", "mf-speed"]
    assert bundled[0].require_cbf is True
    assert bundled[0].title is not None
    assert "(+fast)" in bundled[0].title

    # 4. User preset can override a built-in preset of the same name.
    (tmp_path / "tz.toml").write_text(
        'class = "sorceress"\nmode = "power"\nmin_fcr = 63\nmin_fhr = 42\n',
        encoding="utf-8",
    )
    overridden = resolve_build_expr("tz", CharClass.SORCERESS, user_dir=tmp_path)
    assert (overridden[0].min_fcr, overridden[0].min_fhr) == (63, 42)
    entries = {e.name: e.source for e in list_presets(user_dir=tmp_path)}
    assert entries["tz"] == "user"
    assert entries["fast"] == "user"
    assert entries["base"] == "built-in"


def test_overrides_and_validation_errors(tmp_path: Path) -> None:
    ov = ConstraintOverrides(
        require_cbf=True, min_frw=55, min_pr=0, min_cb=35, min_ll=7, min_pdr=15, min_mf=100
    )
    res = resolve_build_expr("tz", CharClass.SORCERESS, overrides=ov, user_dir=tmp_path)[0]
    assert (res.require_cbf, res.min_frw, res.min_pr) == (True, 55, 0)
    assert (res.min_cb, res.min_ll, res.min_pdr, res.min_mf) == (35, 7, 15, 100)
    assert "CBF" in ov.summary_tags()
    assert "FRW>=55" in ov.summary_tags()

    # to_overrides preserves resolved preset fields.
    round_ov = res.to_overrides()
    assert (round_ov.mode, round_ov.allow_mf, round_ov.require_cbf, round_ov.min_frw) == (
        "power",
        True,
        True,
        55,
    )

    # Invalid override mode rejected.
    with pytest.raises(ValueError, match="Invalid mode"):
        resolve_build_expr(
            "leveling",
            CharClass.PALADIN,
            overrides=ConstraintOverrides(mode="bogus"),  # ty: ignore[invalid-argument-type]
            user_dir=tmp_path,
        )

    # Class mismatch rejected.
    with pytest.raises(ValueError, match="only supported for Paladin"):
        resolve_build_expr("leveling", CharClass.SORCERESS, user_dir=tmp_path)
    with pytest.raises(ValueError, match="only supported for Sorceress"):
        resolve_build_expr("tz", CharClass.PALADIN, user_dir=tmp_path)

    # Unknown preset rejected.
    with pytest.raises(ValueError, match="Unknown build preset"):
        resolve_build_expr("nonexistent", CharClass.SORCERESS, user_dir=tmp_path)

    # Unknown TOML key rejected.
    (tmp_path / "typo.toml").write_text("min_fwr = 55\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown key"):
        resolve_build_expr("typo", CharClass.SORCERESS, user_dir=tmp_path)

    # Circular extends rejected.
    (tmp_path / "a.toml").write_text('extends = ["b"]\n', encoding="utf-8")
    (tmp_path / "b.toml").write_text('extends = ["a"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Circular preset inheritance"):
        resolve_build_expr("a", CharClass.SORCERESS, user_dir=tmp_path)
