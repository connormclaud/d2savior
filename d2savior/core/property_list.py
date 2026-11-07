"""Magical property list data structures and bitstream serialization."""

from typing import TYPE_CHECKING, ClassVar

from d2savior.core.bit_io import BitIO, BitReader, BitWriter

if TYPE_CHECKING:
    from d2savior.core.d2data import VersionData
    from d2savior.core.ibitstream import IBitStream
    from d2savior.core.obitstream import OBitStream

type RawProperty = tuple[int, int, int]


def is_d2r(version: int) -> bool:
    return version >= 0x61


PAIRED_STATS = {
    17: [18],
    48: [49],
    50: [51],
    52: [53],
    54: [55, 56],
    57: [58, 59],
}

_TRACE_PROPERTY = False


class PropertyList:
    """List of magical item properties stored as (prop_id, layer, value) tuples."""

    IMPLICIT_STATS: ClassVar[set[int]] = {88}

    def __init__(self) -> None:
        self.properties: list[RawProperty] = []
        self.end_flag = 0
        self._version: int = 0
        self._use_stat_cost: bool = False
        self._data: VersionData | None = None

    def codec(self, io: BitIO, version: int, data: VersionData | None = None) -> None:
        """Serialize or deserialize magical properties using BitIO.

        Reading and writing have distinct control flows because reading unpacks
        variable-length bitfields from the stream into list elements until the 0x1FF
        terminator is reached, whereas writing iterates through the in-memory list
        while handling paired and implicit stats.
        """
        if io.is_reading:
            if data is None:
                raise ValueError(
                    f"VersionData is required to parse item properties for version {version:#x}"
                )
            assert isinstance(io, BitReader)
            self.deserialize(io.bs, version, data)
        else:
            assert isinstance(io, BitWriter)
            self.serialize(io.bs, version, data)

    def deserialize(self, bs: IBitStream, version: int, data: VersionData) -> None:
        self._version = version
        self._data = data
        self.properties = []
        self._use_stat_cost = is_d2r(version)

        while True:
            bit_pos = bs.get_offset() if _TRACE_PROPERTY else 0
            self.end_flag = bs.read_bits(9)
            if self.end_flag >= 0x1FF:
                break

            if self._use_stat_cost:
                stat_cost = data.get_stat(self.end_flag)
                if stat_cost is None or stat_cost.save_bits == 0:
                    continue

                layer = 0
                if stat_cost.save_param_bits > 0:
                    layer = bs.read_bits(stat_cost.save_param_bits)

                raw_value = bs.read_bits(stat_cost.save_bits)
                value = (raw_value - stat_cost.save_add) << stat_cost.val_shift
                self.properties.append((self.end_flag, layer, value))

                if _TRACE_PROPERTY:
                    print(
                        f"  stat {self.end_flag}: bit_pos={bit_pos}, layer={layer}, raw_value={raw_value}, value={value}, save_bits={stat_cost.save_bits}, save_param_bits={stat_cost.save_param_bits}"
                    )

                for paired_id in PAIRED_STATS.get(self.end_flag, []):
                    paired_cost = data.get_stat(paired_id)
                    if paired_cost and paired_cost.save_bits > 0:
                        paired_raw = bs.read_bits(paired_cost.save_bits)
                        paired_value = (paired_raw - paired_cost.save_add) << paired_cost.val_shift
                        self.properties.append((paired_id, 0, paired_value))
                        if _TRACE_PROPERTY:
                            print(
                                f"    paired stat {paired_id}: raw={paired_raw}, value={paired_value}"
                            )

                if self.end_flag == 57:
                    self.properties.append((88, 0, 1))
            else:
                prop_meta = data.get_property_meta(self.end_flag)
                if prop_meta and prop_meta.bits_sum > 0:
                    value = bs.read_bits(prop_meta.bits_sum)
                    self.properties.append((self.end_flag, 0, value))

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

        param_fields = active_fields[:-1]

        params = [0, 0, 0, 0]
        remaining_layer = layer
        for i, f in enumerate(param_fields):
            mask = (1 << f.bits) - 1
            params[i] = remaining_layer & mask
            remaining_layer >>= f.bits

        params[len(param_fields)] = display_value

        return params

    def _isc_layer_to_params(
        self, prop_id: int, layer: int, display_value: int, version: int, data: VersionData
    ) -> list[int]:
        # Layer packing follows the base (0x63) multi-field layout, not D2R's single-field rows.
        base_meta = data.get_property_meta(prop_id, 0x63)
        if base_meta:
            active_fields = [f for f in base_meta.fields if f.bits > 0]
            if len(active_fields) > 1:
                param_fields = active_fields[:-1]
                params = [0, 0, 0, 0]
                remaining_layer = layer
                for i, f in enumerate(param_fields):
                    mask = (1 << f.bits) - 1
                    params[i] = remaining_layer & mask
                    remaining_layer >>= f.bits
                params[len(param_fields)] = display_value
                return params
        return [layer, display_value, 0, 0]

    def serialize(self, bs: OBitStream, version: int, data: VersionData | None = None) -> None:
        d = data or self._data
        if d is None:
            raise ValueError("VersionData required for PropertyList serialization")
        self._use_stat_cost = is_d2r(version)

        all_paired_ids = set()
        for paired_list in PAIRED_STATS.values():
            all_paired_ids.update(paired_list)

        for prop_id, layer, value in self.properties:
            if prop_id in all_paired_ids:
                continue

            if prop_id in PropertyList.IMPLICIT_STATS:
                continue

            bs.write_bits(9, prop_id)

            if self._use_stat_cost:
                stat_cost = d.get_stat(prop_id)
                if stat_cost is None or stat_cost.save_bits == 0:
                    continue

                if stat_cost.save_param_bits > 0:
                    bs.write_bits(stat_cost.save_param_bits, layer)

                raw_value = (value >> stat_cost.val_shift) + stat_cost.save_add
                bs.write_bits(stat_cost.save_bits, raw_value)

                for paired_id in PAIRED_STATS.get(prop_id, []):
                    paired_cost = d.get_stat(paired_id)
                    if paired_cost and paired_cost.save_bits > 0:
                        paired_found = False
                        for pid, _pl, pv in self.properties:
                            if pid == paired_id:
                                paired_raw = (pv >> paired_cost.val_shift) + paired_cost.save_add
                                bs.write_bits(paired_cost.save_bits, paired_raw)
                                paired_found = True
                                break
                        if not paired_found:
                            bs.write_bits(paired_cost.save_bits, 0)
            else:
                prop_meta = d.get_property_meta(prop_id)
                if prop_meta and prop_meta.bits_sum > 0:
                    bs.write_bits(prop_meta.bits_sum, value)

        bs.write_bits(9, 0x1FF)
