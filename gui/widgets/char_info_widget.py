from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QSpinBox, QComboBox
)
from PySide6.QtCore import Qt, Signal

from core.d2data import get_d2data_manager
from core.localized_data import get_localized_data
from gui.gui_translator import tr


CLASS_NAMES = {
    0: "Amazon",
    1: "Sorceress",
    2: "Necromancer",
    3: "Paladin",
    4: "Barbarian",
    5: "Druid",
    6: "Assassin",
    7: "Warlock",
}

STAT_NAMES = [
    "Strength",
    "Energy",
    "Dexterity",
    "Vitality",
    "Stat Points",
    "Skills",
    "Life",
    "Max Life",
    "Mana",
    "Max Mana",
    "Stamina",
    "Max Stamina",
    "Level",
    "Experience",
    "Gold",
    "Stash Gold",
]


def _tr_class(class_id):
    return tr(CLASS_NAMES.get(class_id, f"Unknown ({class_id})"))


def _tr_stat(stat_idx):
    return tr(STAT_NAMES[stat_idx]) if stat_idx < len(STAT_NAMES) else f"Stat {stat_idx}"

STAT_RANGES = {
    0: (0, 65535),
    1: (0, 65535),
    2: (0, 65535),
    3: (0, 65535),
    4: (0, 65535),
    5: (0, 65535),
    6: (0, 65535),
    7: (0, 65535),
    8: (0, 65535),
    9: (0, 65535),
    10: (0, 65535),
    11: (0, 65535),
    12: (1, 99),
    13: (0, 0xFFFFFFFF),
    14: (0, 0xFFFFFFFF),
    15: (0, 0xFFFFFFFF),
}


class CharInfoWidget(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.char_data = None
        self._updating = False
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        basic_group = QGroupBox(tr("Basic Information"))
        basic_layout = QGridLayout(basic_group)
        basic_layout.setContentsMargins(12, 10, 12, 4)
        basic_layout.setHorizontalSpacing(6)
        basic_layout.setVerticalSpacing(2)
        basic_layout.setColumnStretch(1, 1)
        basic_layout.setColumnStretch(3, 1)
        basic_layout.setColumnStretch(5, 1)
        basic_layout.setColumnStretch(7, 1)
        
        self._basic_labels = {}
        
        lbl = QLabel(tr("Name:"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        basic_layout.addWidget(lbl, 0, 0)
        self._basic_labels['name'] = lbl
        self.name_label = QLabel()
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        basic_layout.addWidget(self.name_label, 0, 1)
        
        lbl = QLabel(tr("Class:"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        basic_layout.addWidget(lbl, 0, 2)
        self._basic_labels['class'] = lbl
        self.class_label = QLabel()
        basic_layout.addWidget(self.class_label, 0, 3)
        
        lbl = QLabel(tr("Level:"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        basic_layout.addWidget(lbl, 0, 4)
        self._basic_labels['level'] = lbl
        self.level_label = QLabel("1")
        self.level_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        basic_layout.addWidget(self.level_label, 0, 5)
        
        lbl = QLabel(tr("Version:"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        basic_layout.addWidget(lbl, 0, 6)
        self._basic_labels['version'] = lbl
        self.version_label = QLabel()
        basic_layout.addWidget(self.version_label, 0, 7)
        
        lbl = QLabel(tr("Title:"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        basic_layout.addWidget(lbl, 1, 0)
        self._basic_labels['title'] = lbl
        self.title_label = QLabel()
        basic_layout.addWidget(self.title_label, 1, 1)
        
        lbl = QLabel(tr("Status:"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        basic_layout.addWidget(lbl, 1, 2)
        self._basic_labels['status'] = lbl
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        basic_layout.addWidget(self.status_label, 1, 3)
        
        lbl = QLabel(tr("Play Time:"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        basic_layout.addWidget(lbl, 1, 4)
        self._basic_labels['playtime'] = lbl
        self.playtime_label = QLabel()
        self.playtime_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        basic_layout.addWidget(self.playtime_label, 1, 5)
        
        lbl = QLabel(tr("Last Save:"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        basic_layout.addWidget(lbl, 1, 6)
        self._basic_labels['lastsave'] = lbl
        self.lastsave_label = QLabel()
        self.lastsave_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        basic_layout.addWidget(self.lastsave_label, 1, 7)
        
        self._basic_group = basic_group
        layout.addWidget(basic_group)
        
        self._stats_group = QGroupBox(tr("Character Stats"))
        stats_layout = QGridLayout(self._stats_group)
        stats_layout.setContentsMargins(4, 10, 4, 4)
        stats_layout.setHorizontalSpacing(6)
        stats_layout.setVerticalSpacing(4)
        
        self.stat_edits = {}
        self._stat_labels = {}
        self._stat_readonly = {}
        
        col_pairs = 4
        for i, stat_name in enumerate(STAT_NAMES):
            row = i // col_pairs
            col = (i % col_pairs) * 3
            lbl = QLabel(f"{_tr_stat(i)}:")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            stats_layout.addWidget(lbl, row, col)
            self._stat_labels[i] = lbl
            
            min_val, max_val = STAT_RANGES.get(i, (0, 65535))
            
            if i in (12, 13):
                value_label = QLabel("0")
                value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                value_label.setFixedWidth(80)
                value_label.setMinimumHeight(22)
                value_label.setStyleSheet("color: #c0c0d0; padding: 2px 4px; background-color: #2a2a3e; border: 1px solid #3a3a5e; border-radius: 2px;")
                stats_layout.addWidget(value_label, row, col + 1)
                self.stat_edits[i] = value_label
                self._stat_readonly[i] = True
            else:
                edit = QSpinBox()
                edit.setRange(min_val, min(max_val, 0x7FFFFFFF))
                edit.setFixedWidth(80)
                edit.setAlignment(Qt.AlignRight)
                edit.valueChanged.connect(
                    lambda val, idx=i: self._on_stat_spin_changed(idx, val)
                )
                stats_layout.addWidget(edit, row, col + 1)
                self.stat_edits[i] = edit
                self._stat_readonly[i] = False
            
            spacer = QWidget()
            spacer.setFixedWidth(12)
            stats_layout.addWidget(spacer, row, col + 2)
        
        layout.addWidget(self._stats_group)
        
        self.skills_group = QGroupBox(tr("Skills"))
        skills_layout = QHBoxLayout(self.skills_group)
        skills_layout.setContentsMargins(6, 10, 6, 6)
        skills_layout.setSpacing(10)
        
        self.skill_tree_widgets = []
        for i in range(3):
            tree_widget = QWidget()
            tree_widget.setFixedWidth(145)
            tree_layout = QVBoxLayout(tree_widget)
            tree_layout.setContentsMargins(0, 0, 0, 0)
            tree_layout.setSpacing(2)
            self.skill_tree_widgets.append(tree_widget)
            skills_layout.addWidget(tree_widget)
        
        layout.addWidget(self.skills_group)
    
    def refresh_ui_texts(self):
        self._basic_group.setTitle(tr("Basic Information"))
        self._basic_labels['name'].setText(tr("Name:"))
        self._basic_labels['class'].setText(tr("Class:"))
        self._basic_labels['level'].setText(tr("Level:"))
        self._basic_labels['version'].setText(tr("Version:"))
        self._basic_labels['title'].setText(tr("Title:"))
        self._basic_labels['status'].setText(tr("Status:"))
        self._basic_labels['playtime'].setText(tr("Game Mode:"))
        self._basic_labels['lastsave'].setText(tr("Last Save:"))
        self._stats_group.setTitle(tr("Character Stats"))
        for i, lbl in self._stat_labels.items():
            lbl.setText(f"{_tr_stat(i)}:")
        self.skills_group.setTitle(tr("Skills"))
        if self.char_data:
            self.class_label.setText(_tr_class(self.char_data.charClass))
            self.title_label.setText(self._get_char_title_name(self.char_data.charTitle, self.char_data.charClass))
            status_flags = []
            if self.char_data.is_expansion():
                status_flags.append(tr("Expansion"))
            if self.char_data.is_hardcore():
                status_flags.append(tr("Hardcore"))
            if self.char_data.is_ladder():
                status_flags.append(tr("Ladder"))
            if self.char_data.is_died_before():
                status_flags.append(tr("Died"))
            self.status_label.setText(" | ".join(status_flags) if status_flags else tr("Normal"))
            game_version = getattr(self.char_data, 'gameVersion', 0)
            if game_version >= 3:
                self.playtime_label.setText(tr("Reign of Warlock"))
            elif game_version >= 2:
                self.playtime_label.setText(tr("Expansion"))
            elif self.char_data.is_expansion():
                self.playtime_label.setText(tr("Expansion"))
            else:
                self.playtime_label.setText(tr("Classic"))
    
    def update_data(self, char_data):
        self.char_data = char_data
        
        self._updating = True
        
        name = char_data.get_char_name() if hasattr(char_data, 'get_char_name') else "Unknown"
        self.name_label.setText(name)
        
        class_name = _tr_class(char_data.charClass)
        self.class_label.setText(class_name)
        
        self.level_label.setText(str(char_data.charLevel))
        
        version_str = f"0x{char_data.dwVersion:02X}" if char_data.dwVersion else "Unknown"
        self.version_label.setText(version_str)
        
        title_str = self._get_char_title_name(char_data.charTitle, char_data.charClass)
        self.title_label.setText(title_str)
        
        status_flags = []
        if char_data.is_expansion():
            status_flags.append(tr("Expansion"))
        if char_data.is_hardcore():
            status_flags.append(tr("Hardcore"))
        if char_data.is_ladder():
            status_flags.append(tr("Ladder"))
        if char_data.is_died_before():
            status_flags.append(tr("Died"))
        self.status_label.setText(" | ".join(status_flags) if status_flags else tr("Normal"))
        
        game_version = getattr(char_data, 'gameVersion', 0)
        if game_version >= 3:
            self.playtime_label.setText(tr("Reign of Warlock"))
        elif game_version >= 2:
            self.playtime_label.setText(tr("Expansion"))
        elif char_data.is_expansion():
            self.playtime_label.setText(tr("Expansion"))
        else:
            self.playtime_label.setText(tr("Classic"))
        
        last_save = 0
        if hasattr(char_data, 'lastSaveTime') and char_data.lastSaveTime and char_data.lastSaveTime != 0xFFFFFFFF:
            last_save = char_data.lastSaveTime
        elif hasattr(char_data, 'dwTime') and char_data.dwTime and char_data.dwTime != 0xFFFFFFFF:
            last_save = char_data.dwTime
        if last_save:
            try:
                import datetime
                dt = datetime.datetime.fromtimestamp(last_save)
                self.lastsave_label.setText(dt.strftime("%Y-%m-%d %H:%M"))
            except (OSError, ValueError):
                self.lastsave_label.setText(str(last_save))
        else:
            self.lastsave_label.setText(tr("N/A"))
        
        if char_data.PlayerStats and char_data.PlayerStats.m_adwValue:
            count = min(16, len(char_data.PlayerStats.m_adwValue), len(self.stat_edits))
            for i in range(count):
                value = char_data.PlayerStats.m_adwValue[i]
                edit = self.stat_edits[i]
                if self._stat_readonly.get(i):
                    edit.setText(str(value))
                else:
                    edit.setValue(value)
        
        self._updating = False
        self._update_skills()
    
    def _on_stat_spin_changed(self, stat_idx, value):
        if self._updating or not self.char_data:
            return
        if self.char_data.PlayerStats and stat_idx < len(self.char_data.PlayerStats.m_adwValue):
            self.char_data.PlayerStats.m_adwValue[stat_idx] = value
            if stat_idx == 12:
                self.level_label.setText(str(value))
                self.char_data.charLevel = value
            self.data_changed.emit()
    
    SKILL_OFFSETS = {
        0: 6,
        1: 36,
        2: 66,
        3: 96,
        4: 126,
        5: 221,
        6: 251,
        7: 373,
    }

    def _update_skills(self):
        for tree_widget in self.skill_tree_widgets:
            layout = tree_widget.layout()
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        
        if not self.char_data:
            return
        
        char_class = self.char_data.charClass
        skills = []
        if hasattr(self.char_data, 'Skills') and self.char_data.Skills:
            skills = self.char_data.Skills.bSkillLevel
        
        d2data_manager = get_d2data_manager()
        version = self.char_data.dwVersion if self.char_data.dwVersion else 0x63
        
        skill_offset = self.SKILL_OFFSETS.get(char_class, 0)
        
        for tree_idx in range(3):
            if tree_idx >= len(self.skill_tree_widgets):
                break
            
            tree_widget = self.skill_tree_widgets[tree_idx]
            tree_layout = tree_widget.layout()
            
            start_idx = tree_idx * 10
            end_idx = min(start_idx + 10, len(skills))
            
            for idx in range(start_idx, end_idx):
                skill_id = skill_offset + idx
                skill_level = skills[idx] if idx < len(skills) else 0
                
                skill_name = f"Skill {skill_id}"
                skill_key = None
                if d2data_manager:
                    name = d2data_manager.get_skill_name(skill_id, version)
                    if name:
                        skill_key = name
                        skill_name = name
                
                localized = get_localized_data()
                if skill_key and localized:
                    translated = localized.get_skill_name(skill_key)
                    if translated and translated != skill_key:
                        skill_name = translated
                
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(4)
                
                name_label = QLabel(skill_name)
                name_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                name_label.setFixedWidth(90)
                
                level_spin = QSpinBox()
                level_spin.setRange(0, 20)
                level_spin.setValue(skill_level)
                level_spin.setFixedWidth(40)
                level_spin.setAlignment(Qt.AlignRight)
                level_spin.valueChanged.connect(
                    lambda val, i=idx: self._on_skill_changed(i, val)
                )
                
                if skill_level > 0:
                    level_spin.setStyleSheet("color: #00aa00; font-weight: bold;")
                else:
                    level_spin.setStyleSheet("color: #888888;")
                
                row_layout.addWidget(name_label)
                row_layout.addWidget(level_spin)
                row_layout.addStretch()
                
                tree_layout.addWidget(row_widget)
            
            tree_layout.addStretch()
    
    def _on_skill_changed(self, skill_index, value):
        if self._updating or not self.char_data:
            return
        if hasattr(self.char_data, 'Skills') and self.char_data.Skills:
            if skill_index < len(self.char_data.Skills.bSkillLevel):
                self.char_data.Skills.bSkillLevel[skill_index] = value
                
                sender = self.sender()
                if isinstance(sender, QSpinBox):
                    if value > 0:
                        sender.setStyleSheet("color: #00aa00; font-weight: bold;")
                    else:
                        sender.setStyleSheet("color: #888888;")
                
                self.data_changed.emit()
    
    def _get_char_type_name(self, char_type):
        flags = []
        if char_type & 0x40:
            flags.append(tr("Ladder"))
        if char_type & 0x20:
            flags.append(tr("Expansion"))
        if char_type & 0x8:
            flags.append(tr("Died"))
        if char_type & 0x4:
            flags.append(tr("Hardcore"))
        return " | ".join(flags) if flags else tr("Normal")
    
    def _get_char_title_name(self, char_title, char_class):
        if char_title == 0:
            return tr("None")
        elif char_title >= 0xF:
            if char_class in [0, 1]:
                return tr("Matriarch")
            else:
                return tr("Patriarch")
        elif char_title >= 0xA:
            return tr("Champion")
        elif char_title >= 5:
            return tr("Slayer")
        else:
            return f"Unknown ({char_title})"
