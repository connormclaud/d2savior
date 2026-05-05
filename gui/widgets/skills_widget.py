from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QScrollArea, QFrame
)
from PySide6.QtCore import Qt

from core.localized_data import get_localized_data
from gui.gui_translator import tr, tr_format


CLASS_NAMES = {
    0: "Amazon",
    1: "Sorceress",
    2: "Necromancer",
    3: "Paladin",
    4: "Barbarian",
    5: "Druid",
    6: "Assassin",
}


def _tr_class(class_id):
    return tr(CLASS_NAMES.get(class_id, f"Unknown ({class_id})"))

SKILL_TABS = {
    0: [
        ["Magic Arrow", "Fire Arrow", "Inner Sight", "Critical Strike", "Jab", "Cold Arrow", "Multiple Shot", "Dodge", "Power Strike", "Poison Javelin"],
        ["Exploding Arrow", "Slow Missiles", "Avoid", "Impale", "Lightning Bolt", "Ice Arrow", "Guided Arrow", "Penetrate", "Charged Strike", "Plague Javelin"],
        ["Strafe", "Immolation Arrow", "Dopplezon", "Evade", "Fend", "Freezing Arrow", "Penetrate", "Valkyrie", "Pierce", "Lightning Fury"],
    ],
    1: [
        ["Fire Bolt", "Warmth", "Charged Bolt", "Ice Bolt", "Frozen Armor", "Fire Ball", "Telekinesis", "Static Field", "Teleport", "Glacial Spike"],
        ["Blaze", "Fire Ball", "Nova", "Lightning", "Shiver Armor", "Fire Wall", "Enchant", "Chain Lightning", "Teleport", "Blizzard"],
        ["Meteor", "Thunder Storm", "Energy Shield", "Chilling Armor", "Fire Mastery", "Hydra", "Lightning Mastery", "Frozen Orb", "Cold Mastery", "Warmth"],
    ],
    2: [
        ["Amplify Damage", "Teeth", "Bone Armor", "Skeleton Mastery", "Raise Skeleton", "Dim Vision", "Weaken", "Poison Dagger", "Corpse Explosion", "Clay Golem"],
        ["Raise Skeletal Mage", "Blood Golem", "Confuse", "Bone Spear", "Golem Mastery", "Raise Revived", "Iron Golem", "Terror", "Bone Wall", "Poison Nova"],
        ["Bone Spirit", "Fire Golem", "Attract", "Decrepify", "Bone Prison", "Summon Resist", "Iron Golem", "Lower Resist", "Poison Nova", "Revive"],
    ],
    3: [
        ["Sacrifice", "Smite", "Might", "Prayer", "Resist Fire", "Holy Bolt", "Holy Fire", "Thorns", "Defiance", "Resist Cold"],
        ["Zeal", "Charge", "Blessed Aim", "Cleansing", "Resist Lightning", "Vengeance", "Blessed Hammer", "Concentration", "Holy Freeze", "Holy Shield"],
        ["Fist of the Heavens", "Fanaticism", "Conviction", "Redemption", "Salvation", "Holy Shock", "Sanctuary", "Meditation", "Fanaticism", "Salvation"],
    ],
    4: [
        ["Bash", "Sword Mastery", "Axe Mastery", "Mace Mastery", "Howl", "Find Potion", "Leap", "Double Swing", "Stun", "Double Throw"],
        ["Leap Attack", "Concentration", "Iron Skin", "Shout", "Battle Cry", "Frenzy", "Increased Stamina", "Natural Resistance", "Battle Orders", "Grim Ward"],
        ["Whirlwind", "Berserk", "Combat Masteries", "Battle Command", "War Cry", "Battle Orders", "Grim Ward", "Find Item", "Taunt", "Battle Cry"],
    ],
    5: [
        ["Raven", "Poison Creeper", "Werewolf", "Lycanthropy", "Firestorm", "Oak Sage", "Summon Spirit Wolf", "Heart of Wolverine", "Arctic Blast", "Carrion Vine"],
        ["Feral Rage", "Maul", "Cyclone Armor", "Summon Dire Wolf", "Rabies", "Fire Claws", "Twister", "Solar Creeper", "Hunger", "Tornado"],
        ["Fury", "Armageddon", "Hurricane", "Spirit of Barbs", "Summon Grizzly", "Volcano", "Shock Wave", "Grizzly", "Armageddon", "Hurricane"],
    ],
    6: [
        ["Fire Blast", "Claw Mastery", "Psychic Hammer", "Tiger Strike", "Dragon Talon", "Shock Web", "Blade Sentinel", "Burst of Speed", "Fists of Fire", "Dragon Claw"],
        ["Blade Fury", "Cobra Strike", "Fade", "Shadow Warrior", "Claw Mastery", "Lightning Sentry", "Wake of Fire", "Chaos Sanctuary", "Dragon Tail", "Blade Shield"],
        ["Death Sentry", "Phoenix Strike", "Shadow Master", "Wake of Destruction", "Mind Blast", "Venom", "Dragon Flight", "Blade Storm", "Lightning Sentry", "Fade"],
    ],
}


class SkillsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.char_data = None
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)
    
    def update_data(self, char_data):
        self.char_data = char_data
        self._populate_skills()
    
    def _populate_skills(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self.char_data:
            return
        
        char_class = self.char_data.charClass
        class_name = _tr_class(char_class)
        
        class_label = QLabel(tr_format("Class: {}", class_name))
        class_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.scroll_layout.addWidget(class_label)
        
        if not hasattr(self.char_data, 'Skills') or not self.char_data.Skills:
            no_skills = QLabel(tr("No skill data available"))
            self.scroll_layout.addWidget(no_skills)
            return
        
        skills = self.char_data.Skills.bSkillLevel
        
        localized_data = get_localized_data()
        
        skill_tabs = SKILL_TABS.get(char_class, [])
        
        for tab_idx, tab_skills in enumerate(skill_tabs):
            tab_group = QGroupBox(tr_format("Skill Tree {}", tab_idx + 1))
            tab_layout = QGridLayout(tab_group)
            tab_layout.setSpacing(5)
            
            for row, skill_name in enumerate(tab_skills):
                if row < len(skills):
                    skill_level = skills[row]
                else:
                    skill_level = 0
                
                skill_label = QLabel(f"{skill_name}")
                level_label = QLabel(f"{skill_level}")
                level_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                if skill_level > 0:
                    level_label.setStyleSheet("color: #00aa00; font-weight: bold;")
                else:
                    level_label.setStyleSheet("color: #888888;")
                
                tab_layout.addWidget(skill_label, row, 0)
                tab_layout.addWidget(level_label, row, 1)
            
            self.scroll_layout.addWidget(tab_group)
        
        left_skill = self.char_data.dwLeftSkill1 if hasattr(self.char_data, 'dwLeftSkill1') else 0
        right_skill = self.char_data.dwRightSkill1 if hasattr(self.char_data, 'dwRightSkill1') else 0
        
        skills_group = QGroupBox(tr("Equipped Skills"))
        skills_layout = QGridLayout(skills_group)
        
        skills_layout.addWidget(QLabel(tr("Left Skill:")), 0, 0)
        skills_layout.addWidget(QLabel(f"ID: {left_skill}"), 0, 1)
        
        skills_layout.addWidget(QLabel(tr("Right Skill:")), 1, 0)
        skills_layout.addWidget(QLabel(f"ID: {right_skill}"), 1, 1)
        
        self.scroll_layout.addWidget(skills_group)
        
        self.scroll_layout.addStretch()
