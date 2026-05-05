from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QCheckBox, QTabWidget
)
from PySide6.QtCore import Qt, Signal

from gui.gui_translator import tr, tr_format


WAYPOINT_NAMES = {
    0: [
        "Rogue Encampment",
        "Cold Plains",
        "Stony Field",
        "Dark Wood",
        "Black Marsh",
        "Outer Cloister",
        "Jail Level 1",
        "Inner Cloister",
        "Catacombs Level 2",
    ],
    1: [
        "Lut Gholein",
        "Sewers Level 2",
        "Dry Hills",
        "Halls of the Dead Level 2",
        "Far Oasis",
        "Lost City",
        "Palace Cellar Level 1",
        "Arcane Sanctuary",
        "Canyon of the Magi",
    ],
    2: [
        "Kurast Docks",
        "Spider Forest",
        "Great Marsh",
        "Flayer Jungle",
        "Lower Kurast",
        "Kurast Bazaar",
        "Upper Kurast",
        "Travincal",
        "Durance of Hate Level 2",
    ],
    3: [
        "The Pandemonium Fortress",
        "City of the Damned",
        "River of Flame",
    ],
    4: [
        "Harrogath",
        "Frigid Highlands",
        "Arreat Plateau",
        "Crystalline Passage",
        "Halls of Pain",
        "Glacial Trail",
        "Frozen Tundra",
        "The Ancients' Way",
        "Worldstone Keep Level 2",
    ],
}

ACT_NAMES = ["Act I", "Act II", "Act III", "Act IV", "Act V"]
DIFFICULTY_NAMES = ["Normal", "Nightmare", "Hell"]


def _tr_difficulty(idx):
    return tr(DIFFICULTY_NAMES[idx])


def _tr_wp(act_idx, wp_idx):
    wp_list = WAYPOINT_NAMES.get(act_idx, [])
    if wp_idx < len(wp_list):
        return tr(wp_list[wp_idx])
    return f"WP {wp_idx}"


def _tr_act(act_idx):
    return tr(ACT_NAMES[act_idx])


class WaypointsWidget(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.char_data = None
        self._updating = False
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        toolbar = QHBoxLayout()
        self.unlock_all_btn = None
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        self.diff_tabs = QTabWidget()
        
        self.diff_widgets = []
        for i, diff_name in enumerate(DIFFICULTY_NAMES):
            widget = QWidget()
            widget_layout = QVBoxLayout(widget)
            widget_layout.setContentsMargins(4, 4, 4, 4)
            self.diff_widgets.append(widget)
            self.diff_tabs.addTab(widget, _tr_difficulty(i))
        
        self.diff_tabs.setCurrentIndex(2)
        
        layout.addWidget(self.diff_tabs)
    
    def update_data(self, char_data):
        self.char_data = char_data
        for i in range(self.diff_tabs.count()):
            self.diff_tabs.setTabText(i, _tr_difficulty(i))
        self._populate_waypoints()
    
    def _populate_waypoints(self):
        for widget in self.diff_widgets:
            layout = widget.layout()
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        
        if not self.char_data:
            return
        
        if not hasattr(self.char_data, 'Waypoints') or not self.char_data.Waypoints:
            for widget in self.diff_widgets:
                no_wp = QLabel(tr("No waypoint data available"))
                widget.layout().addWidget(no_wp)
            return
        
        waypoints = self.char_data.Waypoints
        
        self._updating = True
        
        for diff_idx, wp_data in enumerate(waypoints.wp):
            if diff_idx >= len(self.diff_widgets):
                break
            
            widget = self.diff_widgets[diff_idx]
            diff_layout = widget.layout()
            
            diff_group = QGroupBox(tr_format("Waypoints - {}", _tr_difficulty(diff_idx)))
            group_layout = QGridLayout(diff_group)
            group_layout.setSpacing(4)
            group_layout.setContentsMargins(4, 10, 4, 4)
            
            wp_bytes = wp_data.Waypoints
            
            for act_idx, act_wps in WAYPOINT_NAMES.items():
                row_offset = 0 if act_idx < 3 else 10
                col_offset = act_idx if act_idx < 3 else act_idx - 3
                
                act_label = QLabel(_tr_act(act_idx))
                act_label.setStyleSheet("font-weight: bold;")
                act_label.setAlignment(Qt.AlignCenter)
                group_layout.addWidget(act_label, row_offset, col_offset)
                
                for wp_idx, wp_name in enumerate(act_wps):
                    global_wp_idx = sum(len(WAYPOINT_NAMES[i]) for i in range(act_idx)) + wp_idx
                    byte_idx = global_wp_idx // 8
                    bit_idx = global_wp_idx % 8
                    
                    if byte_idx < len(wp_bytes):
                        is_active = (wp_bytes[byte_idx] >> bit_idx) & 1
                    else:
                        is_active = 0
                    
                    cb = QCheckBox(_tr_wp(act_idx, wp_idx))
                    cb.setChecked(bool(is_active))
                    cb.setEnabled(True)
                    
                    self._style_checkbox(cb, bool(is_active))
                    
                    cb.stateChanged.connect(
                        lambda state, d=diff_idx, b=byte_idx, bi=bit_idx: self._on_waypoint_changed(d, b, bi, state)
                    )
                    
                    group_layout.addWidget(cb, row_offset + wp_idx + 1, col_offset)
            
            diff_layout.addWidget(diff_group)
            diff_layout.addStretch()
        
        self._updating = False
    
    def _style_checkbox(self, cb, is_active):
        if is_active:
            cb.setStyleSheet("color: #00aa00;")
        else:
            cb.setStyleSheet("color: #cccccc;")
    
    def _on_waypoint_changed(self, diff_idx, byte_idx, bit_idx, state):
        if self._updating or not self.char_data:
            return
        
        waypoints = self.char_data.Waypoints
        if not waypoints or diff_idx >= len(waypoints.wp):
            return
        
        wp_bytes = waypoints.wp[diff_idx].Waypoints
        if byte_idx >= len(wp_bytes):
            return
        
        if state:
            wp_bytes[byte_idx] |= (1 << bit_idx)
        else:
            wp_bytes[byte_idx] &= ~(1 << bit_idx)
        
        sender = self.sender()
        if isinstance(sender, QCheckBox):
            self._style_checkbox(sender, bool(state))
        
        self.data_changed.emit()
