# Diablo II Data Files

This directory contains packaged game data tables and localized strings bundled with `d2savior`.

## Directory Structure

- `d2r/`: Canonical base data extracted from Diablo II: Resurrected (Patch 2.7 / build 2.7.3.77443).
  - Core game tables: `Armor.txt`, `Weapons.txt`, `Misc.txt`, `ItemStatCost.txt`, `Properties.txt`, `itemtypes.txt`, `magicprefix.txt`, `magicsuffix.txt`, `uniqueitems.txt`, `runes.txt`, `gems.txt`, `skills.txt`.
  - Generated parsing tables: `itemdata.txt`, `property.txt`.
  - `local/`: Localized JSON string tables (`item-modifiers.json`, `item-names.json`, `item-runes.json`, etc.).
- `0x63/`: Overlay data specific to D2R Beta / v1.0.0 (patch version 0x63 / 99).
  - Overrides only the 7 tables that differ from the D2R base: `Armor.txt`, `ItemStatCost.txt`, `Misc.txt`, `Weapons.txt`, `itemdata.txt`, `itemtypes.txt`, `property.txt`.

## Overlay Loading

The `GameData` loader uses an overlay priority chain (`OVERLAY_CHAIN`):
- Version `0x63`: checks `0x63/`, falling back to `d2r/`.
- Version `0x69`: loads directly from `d2r/`.

Every file stored here is strictly required and loaded by `d2savior`. Guard tests enforce that no unused or uncatalogued files are present.
