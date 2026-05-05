import os
from typing import List, Optional, Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QSpinBox, QComboBox, QPushButton, QGroupBox,
    QDialogButtonBox, QWidget, QFormLayout, QStyle, QProxyStyle
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor, QPainter, QPolygonF
from PySide6.QtCore import QPointF

from core.item import get_property_meta, get_stat_cost
from core.property import get_property_name, get_skill_name, get_class_name, get_skill_tab_name
from core.d2data import get_d2data_manager
from core.localized_data import get_localized_data
from gui.gui_translator import tr


class _DarkArrowStyle(QProxyStyle):
    def subControlRect(self, cc, opt, sc, widget):
        r = super().subControlRect(cc, opt, sc, widget)
        if cc == QStyle.ComplexControl.CC_ComboBox and sc == QStyle.SubControl.SC_ComboBoxArrow:
            r.setLeft(r.left() - 14)
        return r

    def drawPrimitive(self, element, option, painter, widget):
        if element == QStyle.PrimitiveElement.PE_IndicatorArrowDown:
            r = option.rect
            cx = r.center().x()
            cy = r.center().y()
            hw = r.width() * 0.4
            hh = r.height() * 0.3
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor(192, 192, 220))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(QPolygonF([
                QPointF(cx - hw, cy - hh),
                QPointF(cx + hw, cy - hh),
                QPointF(cx, cy + hh),
            ]))
            painter.restore()
            return
        super().drawPrimitive(element, option, painter, widget)


def _ensure_arrow_pngs():
    icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'resources', 'icons')
    os.makedirs(icons_dir, exist_ok=True)
    up_png = os.path.join(icons_dir, 'arrow-up.png')
    down_png = os.path.join(icons_dir, 'arrow-down.png')
    if os.path.isfile(up_png) and os.path.isfile(down_png):
        return up_png, down_png
    from PySide6.QtGui import QPixmap, QPainter, QColor, QPolygonF
    from PySide6.QtCore import QPointF
    for path, points in [
        (up_png, [QPointF(4, 1), QPointF(7, 7), QPointF(1, 7)]),
        (down_png, [QPointF(4, 7), QPointF(7, 1), QPointF(1, 1)]),
    ]:
        pm = QPixmap(8, 8)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(160, 160, 192))
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF(points))
        p.end()
        pm.save(path)
    return up_png, down_png


def _build_dialog_style():
    up_png, down_png = _ensure_arrow_pngs()
    up_png = up_png.replace('\\', '/')
    down_png = down_png.replace('\\', '/')
    return DIALOG_STYLE_BASE + f"""
QSpinBox::up-button {{
    background-color: #1a1a3e;
    border: 1px solid #3d3d54;
    width: 16px;
}}
QSpinBox::down-button {{
    background-color: #1a1a3e;
    border: 1px solid #3d3d54;
    width: 16px;
}}
QSpinBox::up-arrow {{
    image: url({up_png});
    width: 8px;
    height: 8px;
}}
QSpinBox::down-arrow {{
    image: url({down_png});
    width: 8px;
    height: 8px;
}}
"""


DIALOG_STYLE_BASE = """
QDialog {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QGroupBox {
    background-color: #16213e;
    border: 1px solid #4a4a6e;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 12px;
    color: #d0d0e8;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QLabel {
    color: #b8b8d8;
}
QSpinBox {
    background-color: #0a2a50;
    border: 1px solid #4a6a9e;
    border-radius: 3px;
    color: #e8e8f0;
    padding: 2px 6px;
    min-height: 22px;
    min-width: 80px;
}
QComboBox {
    background-color: #0a2a50;
    border: 1px solid #4a6a9e;
    border-radius: 3px;
    color: #e8e8f0;
    padding: 2px 6px;
    min-height: 22px;
    min-width: 160px;
}
QComboBox QAbstractItemView {
    background-color: #0a2a50;
    color: #e8e8f0;
    selection-background-color: #2a2a5e;
}
QPushButton {
    background-color: #0f3460;
    border: 1px solid #3d3d54;
    border-radius: 4px;
    color: #e0e0e0;
    padding: 5px 16px;
    min-height: 24px;
}
QPushButton:hover {
    background-color: #1a4a80;
    border-color: #5a5a8e;
}
QPushButton#maxMinBtn {
    background-color: #0a2a50;
    border: 1px solid #4a6a9e;
    border-radius: 2px;
    color: #e8e8f0;
    padding: 0px 0px;
    min-height: 20px;
    max-height: 20px;
    min-width: 20px;
    max-width: 20px;
    font-size: 10px;
    font-weight: bold;
}
QPushButton#maxMinBtn:hover {
    background-color: #1a4a80;
    border-color: #6a8abe;
}
"""

PROP_TYPE_SKILL = 'skill'
PROP_TYPE_AURA = 'aura'
PROP_TYPE_CLASS = 'class'
PROP_TYPE_SKILL_TAB = 'skill_tab'
PROP_TYPE_MONSTER = 'monster'
PROP_TYPE_CHARGES = 'charges'
PROP_TYPE_SIMPLE = 'simple'

LOWER_IS_BETTER_IDS = {92, 113, 134}

SPECIAL_PROPS = {
    83: PROP_TYPE_CLASS,
    97: PROP_TYPE_SKILL,
    107: PROP_TYPE_SKILL,
    126: PROP_TYPE_SKILL_TAB,
    151: PROP_TYPE_AURA,
    155: PROP_TYPE_MONSTER,
    188: PROP_TYPE_SKILL_TAB,
    195: PROP_TYPE_SKILL,
    196: PROP_TYPE_SKILL,
    197: PROP_TYPE_SKILL,
    198: PROP_TYPE_SKILL,
    199: PROP_TYPE_SKILL,
    201: PROP_TYPE_SKILL,
    204: PROP_TYPE_CHARGES,
}


def _get_all_skills() -> List[Tuple[int, str]]:
    result = []
    d2data = get_d2data_manager()
    loc = get_localized_data()

    aura_ids = d2data.get_aura_skill_ids() if d2data else set()

    for sid in range(0, 512):
        if sid in aura_ids:
            continue
        name, class_id = get_skill_name(sid)
        if name and name != 'Unknown Skill':
            if class_id >= 0:
                cn = get_class_name(class_id)
                result.append((sid, f"[{cn}] {name}"))
            else:
                result.append((sid, name))

    if not result:
        for sid in range(0, 512):
            if sid not in aura_ids:
                result.append((sid, f"Skill #{sid}"))

    return result


def _get_aura_skills() -> List[Tuple[int, str]]:
    result = []
    d2data = get_d2data_manager()
    if d2data:
        aura_ids = d2data.get_aura_skill_ids()
        for sid in sorted(aura_ids):
            name, class_id = get_skill_name(sid)
            if name and name != 'Unknown Skill':
                if class_id >= 0:
                    cn = get_class_name(class_id)
                    result.append((sid, f"[{cn}] {name}"))
                else:
                    result.append((sid, name))
            else:
                result.append((sid, f"Aura #{sid}"))

    if not result:
        result = _get_all_skills()

    return result


def _get_all_classes() -> List[Tuple[int, str]]:
    result = []
    for cid in range(7):
        name = get_class_name(cid)
        result.append((cid, name))
    return result


def _get_skill_tabs_for_class(class_id: int) -> List[Tuple[int, str]]:
    result = []
    for tab in range(3):
        name = get_skill_tab_name(tab, class_id)
        result.append((tab, name))
    return result


def _decode_prop_params(prop_id: int, value: int, layer: int, version: int) -> List[int]:
    from core.item import is_d2r
    if is_d2r(version):
        sc = get_stat_cost(prop_id)
        if sc and sc.save_bits > 0:
            if sc.save_param_bits > 0:
                display_value = value >> sc.val_shift if sc.val_shift > 0 else value
                base_meta = get_property_meta(prop_id, 0x63)
                if base_meta:
                    active_fields = [f for f in base_meta.fields if f.bits > 0]
                    if len(active_fields) > 1:
                        param_fields = active_fields[:-1]
                        params = [0, 0, 0, 0]
                        remaining_layer = layer
                        for i, f in enumerate(param_fields):
                            mask = (1 << f.bits) - 1
                            params[i] = (remaining_layer & mask) + f.base
                            remaining_layer >>= f.bits
                        params[len(param_fields)] = display_value
                        return params
                if prop_id in (195, 196, 197, 198, 199, 201):
                    level = layer & 0x3F
                    skill_id = (layer >> 6) & 0x3FF
                    chance = display_value
                    return [level, skill_id, chance]
                return [layer, display_value, 0, 0]
            return [value]

    meta = get_property_meta(prop_id, version)
    if meta and meta.fields:
        params = meta.parse(value)
        if layer > 0 and meta.fields and meta.fields[0].bits == 0:
            params[0] = layer
        active_params = [p for p, f in zip(params, meta.fields) if f.bits > 0]
        return active_params

    sc = get_stat_cost(prop_id)
    if sc and sc.save_param_bits > 0:
        return [layer, value]
    return [value]


def _encode_prop_params(prop_id: int, params: List[int], version: int) -> Tuple[int, int]:
    from core.item import is_d2r
    if is_d2r(version):
        sc = get_stat_cost(prop_id)
        if sc and sc.save_bits > 0:
            if sc.save_param_bits > 0:
                base_meta = get_property_meta(prop_id, 0x63)
                if base_meta:
                    active_fields = [f for f in base_meta.fields if f.bits > 0]
                    if len(active_fields) > 1:
                        param_fields = active_fields[:-1]
                        a = list(params)
                        while len(a) < 4:
                            a.append(0)
                        value_param = a[len(param_fields)]
                        raw_value = (value_param + sc.save_add) << sc.val_shift
                        layer_val = 0
                        bit_pos = 0
                        for i, f in enumerate(param_fields):
                            v = a[i] - f.base
                            if v < 0:
                                v = 0
                            layer_val += v << bit_pos
                            bit_pos += f.bits
                        return raw_value, layer_val
                if prop_id in (195, 196, 197, 198, 199, 201):
                    level = params[0] if params else 0
                    skill_id = params[1] if len(params) > 1 else 0
                    chance = params[2] if len(params) > 2 else 0
                    layer_val = (skill_id << 6) | (level & 0x3F)
                    raw_value = (chance + sc.save_add) << sc.val_shift
                    return raw_value, layer_val
                layer_val = params[0] if params else 0
                value_param = params[1] if len(params) > 1 else 0
                raw_value = (value_param + sc.save_add) << sc.val_shift
                return raw_value, layer_val
            value = params[0] if params else 0
            return value, 0

    meta = get_property_meta(prop_id, version)
    if meta and meta.fields:
        active_fields = [f for f in meta.fields if f.bits > 0]
        if len(params) < len(active_fields):
            params = list(params) + [0] * (len(active_fields) - len(params))
        full_params = list(params)
        while len(full_params) < len(meta.fields):
            full_params.append(0)
        ok, value = meta.get_value(full_params)
        if ok:
            layer = 0
            if len(meta.fields) > 0 and meta.fields[0].bits == 0 and len(full_params) > 0:
                layer = full_params[0]
                ok2, value2 = meta.get_value([0] + full_params[1:])
                if ok2:
                    value = value2
            return value, layer
        return 0, 0

    sc = get_stat_cost(prop_id)
    if sc and sc.save_param_bits > 0 and len(params) >= 2:
        return params[1], params[0]
    if len(params) >= 1:
        return params[0], 0
    return 0, 0


class PropertyEditDialog(QDialog):
    def __init__(self, prop_id: int, value: int, layer: int, version: int = 0x63, parent=None):
        super().__init__(parent)
        self._prop_id = prop_id
        self._version = version
        self._params = _decode_prop_params(prop_id, value, layer, version)
        self._result_value = value
        self._result_layer = layer
        self._editors = []
        self._arrow_style = _DarkArrowStyle()
        self._init_ui()
        for cb in self.findChildren(QComboBox):
            cb.setStyle(self._arrow_style)

    def _init_ui(self):
        prop_name = get_property_name(self._prop_id)
        self.setWindowTitle(f"{tr('Edit Property')}: {prop_name}")
        self.setMinimumWidth(420)
        self.setStyleSheet(_build_dialog_style())
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(200, 200, 220))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(200, 200, 220))
        self.setPalette(pal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QLabel(f"ID: {self._prop_id}  |  {prop_name}")
        header.setStyleSheet("color: #aaaacc; font-size: 11px;")
        layout.addWidget(header)

        prop_type = SPECIAL_PROPS.get(self._prop_id, PROP_TYPE_SIMPLE)

        if prop_type == PROP_TYPE_SKILL:
            self._create_skill_editor(layout)
        elif prop_type == PROP_TYPE_AURA:
            self._create_aura_editor(layout)
        elif prop_type == PROP_TYPE_CLASS:
            self._create_class_editor(layout)
        elif prop_type == PROP_TYPE_SKILL_TAB:
            self._create_skill_tab_editor(layout)
        elif prop_type == PROP_TYPE_CHARGES:
            self._create_charges_editor(layout)
        elif prop_type == PROP_TYPE_MONSTER:
            self._create_monster_editor(layout)
        else:
            self._create_simple_editor(layout)

        preview_group = QGroupBox(tr("Preview"))
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(8, 14, 8, 8)
        self._preview_label = QLabel()
        self._preview_label.setWordWrap(True)
        self._preview_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        preview_layout.addWidget(self._preview_label)
        layout.addWidget(preview_group)
        self._update_preview()

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Ok).setText(tr("OK"))
        btn_box.button(QDialogButtonBox.Cancel).setText(tr("Cancel"))
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _create_simple_editor(self, layout):
        group = QGroupBox(tr("Value"))
        form = QFormLayout(group)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(8)
        form.setContentsMargins(8, 14, 8, 8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        meta = get_property_meta(self._prop_id, self._version)
        sc = get_stat_cost(self._prop_id)

        has_param = sc and sc.save_param_bits > 0
        if has_param:
            val = self._params[1] if len(self._params) > 1 else 0
        else:
            val = self._params[0] if self._params else 0
        min_val = 0
        max_val = 1023

        if meta and meta.fields:
            for i, field in enumerate(meta.fields):
                if field.bits > 0:
                    max_val = (1 << field.bits) - 1 + field.base
                    min_val = field.base
                    break
        elif sc:
            if sc.save_bits > 0:
                max_val = (1 << sc.save_bits) - 1 - sc.save_add
                min_val = -sc.save_add

        spin = QSpinBox()
        spin.setRange(min(min_val, 0), max(max_val, 1))
        spin.setValue(val)
        spin.valueChanged.connect(self._on_simple_changed)

        value_widget = QWidget()
        value_row = QHBoxLayout(value_widget)
        value_row.setContentsMargins(0, 0, 0, 0)
        value_row.setSpacing(4)
        value_row.addWidget(spin)

        if self._prop_id in LOWER_IS_BETTER_IDS:
            min_btn = QPushButton("▼")
            min_btn.setObjectName("maxMinBtn")
            min_btn.setFixedSize(20, 20)
            min_btn.setToolTip(tr("Minimize"))
            min_btn.clicked.connect(lambda: spin.setValue(spin.minimum()))
            value_row.addWidget(min_btn)
        else:
            max_btn = QPushButton("▲")
            max_btn.setObjectName("maxMinBtn")
            max_btn.setFixedSize(20, 20)
            max_btn.setToolTip(tr("Maximize"))
            max_btn.clicked.connect(lambda: spin.setValue(spin.maximum()))
            value_row.addWidget(max_btn)

        value_row.addStretch()
        form.addRow(tr("Value:"), value_widget)
        self._editors = [('value', spin)]

        if has_param:
            layer_val = self._params[0] if len(self._params) > 0 else 0
            layer_spin = QSpinBox()
            layer_max = (1 << sc.save_param_bits) - 1
            layer_spin.setRange(0, layer_max)
            layer_spin.setValue(layer_val)
            layer_spin.valueChanged.connect(self._on_simple_changed)
            form.addRow(tr("Layer:"), layer_spin)
            self._editors.append(('layer', layer_spin))

        layout.addWidget(group)

    def _create_skill_editor(self, layout):
        group = QGroupBox(tr("Skill Property"))
        form = QFormLayout(group)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(8)
        form.setContentsMargins(8, 14, 8, 8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        prop_id = self._prop_id

        if prop_id in (195, 196, 197, 198, 199, 201):
            level = self._params[0] if len(self._params) > 0 else 0
            skill_id = self._params[1] if len(self._params) > 1 else 0
            chance = self._params[2] if len(self._params) > 2 else 0

            chance_spin = QSpinBox()
            chance_spin.setRange(0, 127)
            chance_spin.setValue(chance)
            chance_spin.valueChanged.connect(self._update_preview)
            form.addRow(tr("Chance %:"), chance_spin)

            skill_combo = self._create_skill_combo(skill_id)
            form.addRow(tr("Skill:"), skill_combo)

            level_spin = QSpinBox()
            level_spin.setRange(1, 63)
            level_spin.setValue(max(1, level))
            level_spin.valueChanged.connect(self._update_preview)
            form.addRow(tr("Level:"), level_spin)

            self._editors = [('chance', chance_spin), ('skill', skill_combo), ('level', level_spin)]

        elif prop_id == 204:
            level = self._params[0] if len(self._params) > 0 else 1
            skill_id = self._params[1] if len(self._params) > 1 else 0
            cur_charges = self._params[2] if len(self._params) > 2 else 0
            max_charges = self._params[3] if len(self._params) > 3 else 0

            level_spin = QSpinBox()
            level_spin.setRange(1, 63)
            level_spin.setValue(max(1, level))
            level_spin.valueChanged.connect(self._update_preview)
            form.addRow(tr("Level:"), level_spin)

            skill_combo = self._create_skill_combo(skill_id)
            form.addRow(tr("Skill:"), skill_combo)

            cur_spin = QSpinBox()
            cur_spin.setRange(0, 511)
            cur_spin.setValue(cur_charges)
            cur_spin.valueChanged.connect(self._update_preview)
            form.addRow(tr("Current Charges:"), cur_spin)

            max_spin = QSpinBox()
            max_spin.setRange(0, 511)
            max_spin.setValue(max_charges)
            max_spin.valueChanged.connect(self._update_preview)
            form.addRow(tr("Max Charges:"), max_spin)

            self._editors = [('level', level_spin), ('skill', skill_combo), ('cur_charges', cur_spin), ('max_charges', max_spin)]

        elif prop_id in (97, 107):
            skill_id = self._params[0] if len(self._params) > 0 else 0
            level = self._params[1] if len(self._params) > 1 else 0

            skill_combo = self._create_skill_combo(skill_id)
            form.addRow(tr("Skill:"), skill_combo)

            level_spin = QSpinBox()
            level_spin.setRange(0, 63)
            level_spin.setValue(level)
            level_spin.valueChanged.connect(self._update_preview)
            form.addRow(tr("Level:"), level_spin)

            self._editors = [('skill', skill_combo), ('level', level_spin)]

        layout.addWidget(group)

    def _create_aura_editor(self, layout):
        group = QGroupBox(tr("Aura Property"))
        form = QFormLayout(group)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(8)
        form.setContentsMargins(8, 14, 8, 8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        skill_id = self._params[0] if len(self._params) > 0 else 0
        level = self._params[1] if len(self._params) > 1 else 0

        skill_combo = self._create_aura_skill_combo(skill_id)
        form.addRow(tr("Aura Skill:"), skill_combo)

        level_spin = QSpinBox()
        level_spin.setRange(1, 31)
        level_spin.setValue(max(1, level))
        level_spin.valueChanged.connect(self._update_preview)
        form.addRow(tr("Level:"), level_spin)

        self._editors = [('skill', skill_combo), ('level', level_spin)]

        layout.addWidget(group)

    def _create_class_editor(self, layout):
        group = QGroupBox(tr("Class Skill Property"))
        form = QFormLayout(group)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(8)
        form.setContentsMargins(8, 14, 8, 8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        class_id = self._params[0] if len(self._params) > 0 else 0
        level = self._params[1] if len(self._params) > 1 else 0

        class_combo = QComboBox()
        classes = _get_all_classes()
        for cid, cname in classes:
            class_combo.addItem(cname, cid)
        for i, (cid, _) in enumerate(classes):
            if cid == class_id:
                class_combo.setCurrentIndex(i)
                break
        class_combo.currentIndexChanged.connect(self._update_preview)
        form.addRow(tr("Class:"), class_combo)

        level_spin = QSpinBox()
        level_spin.setRange(0, 7)
        level_spin.setValue(level)
        level_spin.valueChanged.connect(self._update_preview)
        form.addRow(tr("Level:"), level_spin)

        self._editors = [('class', class_combo), ('level', level_spin)]
        layout.addWidget(group)

    def _create_skill_tab_editor(self, layout):
        group = QGroupBox(tr("Skill Tab Property"))
        form = QFormLayout(group)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(8)
        form.setContentsMargins(8, 14, 8, 8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        if self._prop_id == 188:
            tab = self._params[0] if len(self._params) > 0 else 0
            class_id = self._params[1] if len(self._params) > 1 else 0
            level = self._params[2] if len(self._params) > 2 else 0

            class_combo = QComboBox()
            classes = _get_all_classes()
            for cid, cname in classes:
                class_combo.addItem(cname, cid)
            for i, (cid, _) in enumerate(classes):
                if cid == class_id:
                    class_combo.setCurrentIndex(i)
                    break
            class_combo.currentIndexChanged.connect(self._on_tab_class_changed)
            form.addRow(tr("Class:"), class_combo)

            self._tab_combo = QComboBox()
            self._refresh_tab_combo(class_id, tab)
            self._tab_combo.currentIndexChanged.connect(self._update_preview)
            form.addRow(tr("Skill Tab:"), self._tab_combo)

            level_spin = QSpinBox()
            level_spin.setRange(0, 7)
            level_spin.setValue(level)
            level_spin.valueChanged.connect(self._update_preview)
            form.addRow(tr("Level:"), level_spin)

            self._editors = [('class', class_combo), ('tab', self._tab_combo), ('level', level_spin)]
        else:
            self._create_simple_editor(layout)
            return

        layout.addWidget(group)

    def _create_monster_editor(self, layout):
        group = QGroupBox(tr("Monster Property"))
        form = QFormLayout(group)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(8)
        form.setContentsMargins(8, 14, 8, 8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        from core.property import get_monster_name
        monster_id = self._params[0] if len(self._params) > 0 else 0
        chance = self._params[1] if len(self._params) > 1 else 0

        monster_spin = QSpinBox()
        monster_spin.setRange(0, 1023)
        monster_spin.setValue(monster_id)
        monster_spin.valueChanged.connect(self._update_preview)
        form.addRow(tr("Monster ID:"), monster_spin)

        monster_name_lbl = QLabel(get_monster_name(monster_id))
        monster_name_lbl.setStyleSheet("color: #aaaacc;")
        monster_spin.valueChanged.connect(
            lambda v: monster_name_lbl.setText(get_monster_name(v))
        )
        form.addRow("", monster_name_lbl)

        chance_spin = QSpinBox()
        chance_spin.setRange(0, 127)
        chance_spin.setValue(chance)
        chance_spin.valueChanged.connect(self._update_preview)
        form.addRow(tr("Chance %:"), chance_spin)

        self._editors = [('monster', monster_spin), ('chance', chance_spin)]
        layout.addWidget(group)

    def _create_charges_editor(self, layout):
        self._create_skill_editor(layout)

    def _create_skill_combo(self, current_skill_id: int) -> QComboBox:
        combo = QComboBox()
        skills = _get_all_skills()
        combo.setEditable(True)
        for sid, sname in skills:
            combo.addItem(sname, sid)
        for i, (sid, _) in enumerate(skills):
            if sid == current_skill_id:
                combo.setCurrentIndex(i)
                break
        combo.currentIndexChanged.connect(self._update_preview)
        return combo

    def _create_aura_skill_combo(self, current_skill_id: int) -> QComboBox:
        combo = QComboBox()
        skills = _get_aura_skills()
        combo.setEditable(True)
        for sid, sname in skills:
            combo.addItem(sname, sid)
        for i, (sid, _) in enumerate(skills):
            if sid == current_skill_id:
                combo.setCurrentIndex(i)
                break
        combo.currentIndexChanged.connect(self._update_preview)
        return combo

    def _refresh_tab_combo(self, class_id: int, current_tab: int = 0):
        self._tab_combo.clear()
        tabs = _get_skill_tabs_for_class(class_id)
        for tab, tname in tabs:
            self._tab_combo.addItem(tname, tab)
        for i, (tab, _) in enumerate(tabs):
            if tab == current_tab:
                self._tab_combo.setCurrentIndex(i)
                break

    def _on_tab_class_changed(self, index):
        class_combo = None
        for key, editor in self._editors:
            if key == 'class':
                class_combo = editor
                break
        if class_combo:
            class_id = class_combo.currentData()
            self._refresh_tab_combo(class_id, 0)
        self._update_preview()

    def _on_simple_changed(self):
        self._update_preview()

    def _collect_params(self) -> List[int]:
        prop_type = SPECIAL_PROPS.get(self._prop_id, PROP_TYPE_SIMPLE)

        if prop_type == PROP_TYPE_SKILL:
            if self._prop_id in (195, 196, 197, 198, 199, 201):
                level = self._get_editor_value('level', 1)
                skill_id = self._get_editor_data('skill', 0)
                chance = self._get_editor_value('chance', 0)
                return [level, skill_id, chance]
            elif self._prop_id == 204:
                level = self._get_editor_value('level', 1)
                skill_id = self._get_editor_data('skill', 0)
                cur = self._get_editor_value('cur_charges', 0)
                mx = self._get_editor_value('max_charges', 0)
                return [level, skill_id, cur, mx]
            elif self._prop_id in (97, 107):
                skill_id = self._get_editor_data('skill', 0)
                level = self._get_editor_value('level', 0)
                return [skill_id, level]

        elif prop_type == PROP_TYPE_AURA:
            skill_id = self._get_editor_data('skill', 0)
            level = self._get_editor_value('level', 1)
            return [skill_id, level]

        elif prop_type == PROP_TYPE_CLASS:
            class_id = self._get_editor_data('class', 0)
            level = self._get_editor_value('level', 0)
            return [class_id, level]

        elif prop_type == PROP_TYPE_SKILL_TAB:
            tab = self._get_editor_data('tab', 0)
            class_id = self._get_editor_data('class', 0)
            level = self._get_editor_value('level', 0)
            return [tab, class_id, level]

        elif prop_type == PROP_TYPE_MONSTER:
            monster_id = self._get_editor_value('monster', 0)
            chance = self._get_editor_value('chance', 0)
            return [monster_id, chance]

        value = self._get_editor_value('value', 0)
        layer = self._get_editor_value('layer', 0)
        if any(key == 'layer' for key, _ in self._editors):
            return [layer, value]
        return [value]

    def _get_editor_value(self, key: str, default: int) -> int:
        for k, editor in self._editors:
            if k == key:
                return editor.value()
        return default

    def _get_editor_data(self, key: str, default: int) -> int:
        for k, editor in self._editors:
            if k == key:
                data = editor.currentData()
                return data if data is not None else default
        return default

    def _update_preview(self):
        params = self._collect_params()
        from core.property import format_property
        text = format_property(self._prop_id, params, self._version)
        self._preview_label.setText(text if text else f"Property #{self._prop_id}")

    def _on_accept(self):
        params = self._collect_params()
        value, layer = _encode_prop_params(self._prop_id, params, self._version)
        self._result_value = value
        self._result_layer = layer
        self.accept()

    @property
    def result_value(self) -> int:
        return self._result_value

    @property
    def result_layer(self) -> int:
        return self._result_layer
