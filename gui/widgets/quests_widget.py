from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QCheckBox, QTabWidget
)
from PySide6.QtCore import Qt

from gui.gui_translator import tr, tr_format


QUEST_NAMES = {
    0: [
        "Den of Evil",
        "Sisters' Burial Grounds",
        "Tools of the Trade",
        "The Search for Cain",
        "The Forgotten Tower",
        "Sisters to the Slaughter",
    ],
    1: [
        "Radament's Lair",
        "The Horadric Staff",
        "Tainted Sun",
        "Arcane Sanctuary",
        "The Summoner",
        "The Seven Tombs",
    ],
    2: [
        "The Golden Bird",
        "Blade of the Old Religion",
        "Khalim's Will",
        "Lam Esen's Tome",
        "The Blackened Temple",
        "The Guardian",
    ],
    3: [
        "The Fallen Angel",
        "The Hellforge",
        "Terror's End",
    ],
    4: [
        "Siege on Harrogath",
        "Rescue on Mount Arreat",
        "Prison of Ice",
        "Betrayal of Harrogath",
        "Rite of Passage",
        "Eve of Destruction",
    ],
}

DIFFICULTY_NAMES = ["Normal", "Nightmare", "Hell"]


def _tr_difficulty(idx):
    return tr(DIFFICULTY_NAMES[idx])


def _tr_quest(act_idx, quest_idx):
    quest_list = QUEST_NAMES.get(act_idx, [])
    if quest_idx < len(quest_list):
        return tr(quest_list[quest_idx])
    return f"Quest {quest_idx}"


def _tr_act(act_idx):
    act_names = ["Act I", "Act II", "Act III", "Act IV", "Act V"]
    return tr(act_names[act_idx])


class QuestsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.char_data = None
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.diff_tabs = QTabWidget()
        
        self.diff_widgets = []
        for diff_name in DIFFICULTY_NAMES:
            widget = QWidget()
            widget_layout = QVBoxLayout(widget)
            widget_layout.setContentsMargins(4, 4, 4, 4)
            self.diff_widgets.append(widget)
            self.diff_tabs.addTab(widget, _tr_difficulty(DIFFICULTY_NAMES.index(diff_name)))
        
        self.diff_tabs.setCurrentIndex(2)
        
        layout.addWidget(self.diff_tabs)
    
    def update_data(self, char_data):
        self.char_data = char_data
        for i in range(self.diff_tabs.count()):
            self.diff_tabs.setTabText(i, _tr_difficulty(i))
        self._populate_quests()
    
    def _populate_quests(self):
        for widget in self.diff_widgets:
            layout = widget.layout()
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        
        if not self.char_data:
            return
        
        if not hasattr(self.char_data, 'QuestInfo') or not self.char_data.QuestInfo:
            for widget in self.diff_widgets:
                no_quests = QLabel(tr("No quest data available"))
                widget.layout().addWidget(no_quests)
            return
        
        quest_info = self.char_data.QuestInfo
        
        for diff_idx, qi_data in enumerate(quest_info.QIData):
            if diff_idx >= len(self.diff_widgets):
                break
            
            widget = self.diff_widgets[diff_idx]
            diff_layout = widget.layout()
            
            diff_group = QGroupBox(tr_format("Quests - {}", _tr_difficulty(diff_idx)))
            group_layout = QGridLayout(diff_group)
            group_layout.setSpacing(4)
            group_layout.setContentsMargins(4, 10, 4, 4)
            
            act_quests = [
                (qi_data.wActI, 0),
                (qi_data.wActII, 1),
                (qi_data.wActIII, 2),
                (qi_data.wActIV, 3),
                (qi_data.wActV, 4),
            ]
            
            for act_col, (act_data, act_idx) in enumerate(act_quests):
                row_offset = 0 if act_col < 3 else 7
                col_offset = act_col if act_col < 3 else act_col - 3
                
                act_label = QLabel(_tr_act(act_idx))
                act_label.setStyleSheet("font-weight: bold;")
                act_label.setAlignment(Qt.AlignCenter)
                group_layout.addWidget(act_label, row_offset, col_offset)
                
                quest_names = QUEST_NAMES.get(act_idx, [])
                for quest_idx, quest_name in enumerate(quest_names):
                    if quest_idx < len(act_data):
                        quest_value = act_data[quest_idx]
                        is_completed = quest_value > 0
                        
                        cb = QCheckBox(_tr_quest(act_idx, quest_idx))
                        cb.setChecked(is_completed)
                        cb.setEnabled(False)
                        
                        if is_completed:
                            cb.setStyleSheet("color: #00aa00;")
                        else:
                            cb.setStyleSheet("color: #888888;")
                        
                        group_layout.addWidget(cb, row_offset + quest_idx + 1, col_offset)
            
            reset_label = QLabel(tr_format("Stat Reset Available: {}", tr("Yes") if qi_data.bResetStats else tr("No")))
            group_layout.addWidget(reset_label, 14, 0, 1, 3)
            
            diff_layout.addWidget(diff_group)
            diff_layout.addStretch()
