"""Magical property list data structures and bitstream serialization."""

import logging
from typing import TYPE_CHECKING

from d2savior.core.bit_io import BitIO, BitReader, BitWriter

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from d2savior.core.ibitstream import IBitStream
    from d2savior.core.models import PropertyField, VersionData
    from d2savior.core.obitstream import OBitStream

type RawProperty = tuple[int, int, int]


def is_d2r(version: int) -> bool:
    return version >= 0x61


PAIRED_STATS: frozendict[int, tuple[int, ...]] = frozendict(
    {
        17: (18,),
        48: (49,),
        50: (51,),
        52: (53,),
        54: (55, 56),
        57: (58, 59),
    }
)
_PAIRED_STAT_IDS: frozenset[int] = frozenset({*p for p in PAIRED_STATS.values()})


class PropertyList:
    """List of magical item properties stored as (prop_id, layer, value) tuples."""

    def __init__(self) -> None:
        self.properties: list[RawProperty] = []
        self.end_flag = 0
        self._version: int = 0
        self._use_stat_cost: bool = False
        self._data: VersionData | None = None

    def codec(self, io: BitIO, version: int, data: VersionData | None = None) -> None:
        """Serialize or deserialize magical properties using BitIO."""
        d = data or self._data
        if d is None:
            action = "parse" if io.is_reading else "serialize"
            raise ValueError(
                f"VersionData is required to {action} item properties for version {version:#x}"
            )
        self._use_stat_cost = is_d2r(version)

        if io.is_reading:
            self._version = version
            self._data = d
            self.properties = []
            trace = logger.isEnabledFor(logging.DEBUG)
            while True:
                bit_pos = io.get_offset() if trace else 0
                self.end_flag = io.bits(9)
                if self.end_flag >= 0x1FF:
                    break
                self._codec_property(io, self.end_flag, 0, 0, d, trace=trace, bit_pos=bit_pos)
        else:
            for prop_id, layer, value in self.properties:
                if prop_id in _PAIRED_STAT_IDS:
                    continue
                io.bits(9, prop_id)
                self._codec_property(io, prop_id, layer, value, d)
            io.bits(9, 0x1FF)

    def _codec_property(
        self,
        io: BitIO,
        prop_id: int,
        layer: int,
        value: int,
        data: VersionData,
        *,
        trace: bool = False,
        bit_pos: int = 0,
    ) -> None:
        if self._use_stat_cost:
            stat_cost = data.get_stat(prop_id)
            if stat_cost is None or stat_cost.save_bits == 0:
                return

            if stat_cost.save_param_bits > 0:
                layer = io.bits(stat_cost.save_param_bits, layer)

            raw_value = 0 if io.is_reading else (value >> stat_cost.val_shift) + stat_cost.save_add
            raw_value = io.bits(stat_cost.save_bits, raw_value)
            if io.is_reading:
                value = (raw_value - stat_cost.save_add) << stat_cost.val_shift
                self.properties.append((prop_id, layer, value))
                if trace:
                    logger.debug(
                        "  stat %s: bit_pos=%s, layer=%s, raw_value=%s, value=%s, "
                        "save_bits=%s, save_param_bits=%s",
                        prop_id,
                        bit_pos,
                        layer,
                        raw_value,
                        value,
                        stat_cost.save_bits,
                        stat_cost.save_param_bits,
                    )

            for paired_id in PAIRED_STATS.get(prop_id, []):
                paired_cost = data.get_stat(paired_id)
                if paired_cost and paired_cost.save_bits > 0:
                    if io.is_writing:
                        paired_val = next(
                            (pv for pid, _pl, pv in self.properties if pid == paired_id),
                            None,
                        )
                        paired_raw = (
                            (paired_val >> paired_cost.val_shift) + paired_cost.save_add
                            if paired_val is not None
                            else 0
                        )
                    else:
                        paired_raw = 0
                    paired_raw = io.bits(paired_cost.save_bits, paired_raw)
                    if io.is_reading:
                        paired_value = (paired_raw - paired_cost.save_add) << paired_cost.val_shift
                        self.properties.append((paired_id, 0, paired_value))
                        if trace:
                            logger.debug(
                                "    paired stat %s: raw=%s, value=%s",
                                paired_id,
                                paired_raw,
                                paired_value,
                            )
        else:
            prop_meta = data.get_property_meta(prop_id)
            if prop_meta and prop_meta.bits_sum > 0:
                value = io.bits(prop_meta.bits_sum, value)
                if io.is_reading:
                    self.properties.append((prop_id, 0, value))

    def deserialize(self, bs: IBitStream, version: int, data: VersionData | None = None) -> None:
        self.codec(BitReader(bs), version, data)

    def ext_sockets(self) -> int:
        r = 0
        for prop_id, _layer, value in self.properties:
            if prop_id == 194:
                r += value
        return r

    def is_indestructible(self) -> bool:
        return any(prop_id == 152 and value != 0 for prop_id, _layer, value in self.properties)

    def get_parsed_properties(
        self, version: int | None = None, data: VersionData | None = None
    ) -> list[tuple[int, int, list[int]]]:
        ver = version if version is not None else self._version
        d = data or self._data
        result = []
        for prop_id, layer, value in self.properties:
            if self._use_stat_cost and d:
                params = self._isc_to_params(prop_id, layer, value, ver, d)
                result.append((prop_id, value, params))
            else:
                prop_meta = d.get_property_meta(prop_id) if d else None
                if prop_meta:
                    params = prop_meta.parse(value)
                    result.append((prop_id, value, params))
                else:
                    result.append((prop_id, value, []))
        return result

    def _isc_to_params(
        self, prop_id: int, layer: int, value: int, version: int, data: VersionData
    ) -> list[int]:
        prop_meta = data.get_property_meta(prop_id)
        stat_cost = data.get_stat(prop_id)
        display_value = (
            value >> stat_cost.val_shift if stat_cost and stat_cost.val_shift > 0 else value
        )

        if not prop_meta or prop_meta.bits_sum == 0:
            if stat_cost and stat_cost.save_param_bits > 0:
                return self._isc_layer_to_params(prop_id, layer, display_value, version, data)
            return [display_value, 0, 0, 0]

        fields = prop_meta.fields
        active_fields = [f for f in fields if f.bits > 0]

        isc_bits = stat_cost.save_bits + stat_cost.save_param_bits if stat_cost else 0
        if (
            len(active_fields) <= 1
            and stat_cost
            and stat_cost.save_param_bits > 0
            and isc_bits > prop_meta.bits_sum
        ):
            return self._isc_layer_to_params(prop_id, layer, display_value, version, data)

        if len(active_fields) <= 1:
            return [display_value, 0, 0, 0]

        if prop_meta.bits_sum > isc_bits and isc_bits > 0:
            return [display_value, 0, 0, 0]

        param_bits = stat_cost.save_param_bits if stat_cost else 0
        return self._unpack_fields(active_fields, layer, display_value, param_bits)

    def _unpack_fields(
        self,
        active_fields: list[PropertyField],
        layer: int,
        display_value: int,
        param_bits: int,
    ) -> list[int]:
        params = [0, 0, 0, 0]
        remaining_layer = layer
        remaining_value = display_value
        bits_acc = 0
        for i, f in enumerate(active_fields):
            mask = (1 << f.bits) - 1
            if bits_acc < param_bits:
                params[i] = (remaining_layer & mask) + f.base
                remaining_layer >>= f.bits
                bits_acc += f.bits
            else:
                params[i] = (remaining_value & mask) + f.base
                remaining_value >>= f.bits
        return params

    def _isc_layer_to_params(
        self, prop_id: int, layer: int, display_value: int, version: int, data: VersionData
    ) -> list[int]:
        # Layer packing follows the base (0x63) multi-field layout, not D2R's single-field rows.
        base_meta = data.get_property_meta(prop_id, 0x63)
        if base_meta:
            active_fields = [f for f in base_meta.fields if f.bits > 0]
            if len(active_fields) > 1:
                stat_cost = data.get_stat(prop_id)
                param_bits = stat_cost.save_param_bits if stat_cost else 0
                return self._unpack_fields(active_fields, layer, display_value, param_bits)
        return [layer, display_value, 0, 0]

    def serialize(self, bs: OBitStream, version: int, data: VersionData | None = None) -> None:
        self.codec(BitWriter(bs), version, data)
