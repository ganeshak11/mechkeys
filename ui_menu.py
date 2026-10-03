#!/usr/bin/env python3
import sys
import socket
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QStackedWidget, QPushButton, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QKeyEvent

SOCKET_PATH = "/tmp/mechkeys.sock"

SWITCH_PROFILES = [
    {
        "id": "cherry_mx_brown_abs",
        "name": "Cherry MX Brown",
        "tag": "TACTILE THOCK",
        "desc": "55g Actuation • Gentle Tactile Bump • Deep Acoustic Sound",
        "color": "#e67e22",
        "icon": "🟤",
        "key": "1"
    },
    {
        "id": "cherry_mx_red_abs",
        "name": "Cherry MX Red",
        "tag": "LINEAR SMOOTH",
        "desc": "45g Actuation • Smooth Rapid Travel • Soft Bottom-Out",
        "color": "#ff4757",
        "icon": "🔴",
        "key": "2"
    },
    {
        "id": "kailh_box_white",
        "name": "Kailh Box White",
        "tag": "CRISP CLICKY",
        "desc": "50g Actuation • Dual Click-Bar • High-Pitch Sharp Tactile Snap",
        "color": "#00d2d3",
        "icon": "⚪",
        "key": "3"
    },
    {
        "id": "glorious_panda",
        "name": "Glorious Panda",
        "tag": "HOLY PANDA",
        "desc": "67g Actuation • Heavy Snappy Bump • Creamy Thock Acoustic",
        "color": "#feca57",
        "icon": "🐼",
        "key": "4"
    },
    {
        "id": "unicomp_classic",
        "name": "IBM Model M 1985",
        "tag": "BUCKLING SPRING",
        "desc": "70g Actuation • Iconic Mechanical Spring Ping • Heavy Vintage",
        "color": "#a4b0be",
        "icon": "📜",
        "key": "5"
    },
    {
        "id": "nk_cream",
        "name": "NovelKeys Cream",
        "tag": "POM LINEAR",
        "desc": "55g Actuation • Self-Lubricating POM Stem • Deep Creamy Clack",
        "color": "#f8efba",
        "icon": "🍦",
        "key": "6"
    },
    {
        "id": "tealios_v2",
        "name": "Tealios V2",
        "tag": "BOUTIQUE LINEAR",
        "desc": "67g Actuation • Silky Ultra-Smooth • Marble Bottom-Out Acoustic",
        "color": "#1dd1a1",
        "icon": "💎",
        "key": "7"
    },
    {
        "id": "off",
        "name": "Mute / Silent Mode",
        "tag": "STEALTH",
        "desc": "Mute all keystroke sounds instantly (0dB Silence)",
        "color": "#747d8c",
        "icon": "🔇",
        "key": "0"
    }
]

PRANK_PROFILES = [
    {
        "id": "pop_cat",
        "name": "Pop Cat",
        "tag": "VIRAL MEME",
        "desc": "Iconic Pop Cat mouth pops on every single keystroke!",
        "color": "#ff9f43",
        "icon": "🐱",
        "key": "1"
    },
    {
        "id": "windows_xp",
        "name": "Windows XP Error",
        "tag": "CHAOS OS",
        "desc": "Ding on typing • USB chime on Space • CRITICAL STOP on Enter!",
        "color": "#0984e3",
        "icon": "🪟",
        "key": "2"
    },
    {
        "id": "vine_boom",
        "name": "Vine Boom Jumpscare",
        "tag": "JUMPSCARE",
        "desc": "Subtle click on typing • 💥 MASSIVE VINE BOOM on Space & Enter!",
        "color": "#d63031",
        "icon": "💥",
        "key": "3"
    },
    {
        "id": "voice_demo",
        "name": "Robot Voice Synthesizer",
        "tag": "SPEECH",
        "desc": "Speaks every single letter, space, and backspace out loud!",
        "color": "#a29bfe",
        "icon": "🤖",
        "key": "4"
    },
    {
        "id": "rosenclick",
        "name": "Michael Rosen Click",
        "tag": "NOICE",
        "desc": "Legendary Michael Rosen tongue click on every keypress",
        "color": "#fd79a8",
        "icon": "👄",
        "key": "5"
    },
    {
        "id": "off",
        "name": "Mute / Silent Mode",
        "tag": "STEALTH",
        "desc": "Mute all keystroke sounds instantly (0dB Silence)",
        "color": "#747d8c",
        "icon": "🔇",
        "key": "0"
    }
]

def send_ipc(cmd):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(SOCKET_PATH)
        s.sendall(f"{cmd}\n".encode())
        res = s.recv(1024).decode()
        s.close()
        return res
    except Exception as e:
        return f"Error: {e}"

def get_current_status():
    res = send_ipc("STATUS")
    active_profile = "cherry_mx_brown_abs"
    muted = False
    if "Active:" in res:
        parts = res.split("Active:")[1].split("(")
        active_profile = parts[0].strip()
        if "Muted: true" in res:
            muted = True
    return active_profile, muted

class ProfileCard(QFrame):
    def __init__(self, item, is_active, on_select, parent=None):
        super().__init__(parent)
        self.item = item
        self.is_active = is_active
        self.is_highlighted = is_active
        self.on_select = on_select
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 14, 7)
        layout.setSpacing(12)

        # Left color bar pill
        self.accent_bar = QFrame()
        self.accent_bar.setFixedWidth(4)
        self.accent_bar.setFixedHeight(34)
        self.accent_bar.setStyleSheet(f"""
            background: {self.item['color'] if self.is_active else 'rgba(255, 255, 255, 0.15)'};
            border-radius: 2px;
        """)
        layout.addWidget(self.accent_bar)

        # Icon box
        icon_box = QFrame()
        icon_box.setFixedSize(36, 36)
        icon_box.setStyleSheet(f"""
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 9px;
        """)
        ib_layout = QVBoxLayout(icon_box)
        ib_layout.setContentsMargins(0, 0, 0, 0)
        ib_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel(self.item["icon"])
        icon_label.setFont(QFont("Segoe UI Emoji", 16))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ib_layout.addWidget(icon_label)
        layout.addWidget(icon_box)

        # Info Box
        info_vbox = QVBoxLayout()
        info_vbox.setSpacing(2)

        # Title Row
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        name_label = QLabel(self.item["name"])
        name_label.setStyleSheet("color: #ffffff; font-weight: 700; font-size: 13px;")
        title_row.addWidget(name_label)

        tag_label = QLabel(self.item["tag"])
        tag_bg = self.item["color"]
        tag_label.setStyleSheet(f"""
            background: {tag_bg}22;
            color: {tag_bg};
            border: 1px solid {tag_bg}55;
            border-radius: 4px;
            padding: 1px 6px;
            font-size: 9px;
            font-weight: 800;
            letter-spacing: 0.5px;
        """)
        title_row.addWidget(tag_label)
        title_row.addStretch()

        if self.is_active:
            active_badge = QLabel("● ACTIVE")
            active_badge.setStyleSheet("""
                color: #2ecc71;
                font-weight: 800;
                font-size: 10px;
                letter-spacing: 0.8px;
                background: rgba(46, 204, 113, 0.15);
                border: 1px solid rgba(46, 204, 113, 0.4);
                border-radius: 4px;
                padding: 2px 7px;
            """)
            title_row.addWidget(active_badge)

        info_vbox.addLayout(title_row)

        # Specs / Description
        desc_label = QLabel(self.item["desc"])
        desc_label.setStyleSheet("color: #8b92a5; font-size: 11px;")
        info_vbox.addWidget(desc_label)

        layout.addLayout(info_vbox)

        # Mechanical Keycap Badge
        keycap = QLabel(self.item["key"])
        keycap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        keycap.setFixedSize(28, 28)
        keycap.setStyleSheet("""
            color: #d1d5db;
            font-family: monospace;
            font-size: 12px;
            font-weight: 800;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #252836, stop:1 #1a1c26);
            border: 1px solid #373d52;
            border-bottom: 2px solid #0f1118;
            border-radius: 6px;
        """)
        layout.addWidget(keycap)

        self.apply_style(hover=self.is_active)

    def apply_style(self, hover=False):
        self.is_highlighted = hover
        card_color = self.item["color"]
        if self.is_active:
            border = f"1px solid {card_color}88"
            bg = f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {card_color}18, stop:1 rgba(255, 255, 255, 0.04))"
            bar_color = card_color
        elif hover:
            border = f"1px solid {card_color}aa"
            bg = "rgba(255, 255, 255, 0.07)"
            bar_color = card_color
        else:
            border = "1px solid rgba(255, 255, 255, 0.07)"
            bg = "rgba(255, 255, 255, 0.03)"
            bar_color = "rgba(255, 255, 255, 0.15)"

        self.accent_bar.setStyleSheet(f"background: {bar_color}; border-radius: 2px;")
        self.setStyleSheet(f"""
            ProfileCard {{
                background: {bg};
                border: {border};
                border-radius: 12px;
            }}
        """)

    def enterEvent(self, event):
        self.apply_style(hover=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_active:
            self.apply_style(hover=False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_select(self.item["id"])
        super().mousePressEvent(event)

class MechkeysDropdownUI(QWidget):
    def __init__(self):
        super().__init__()
        self.active_profile, self.is_muted = get_current_status()
        self.switch_cards = []
        self.prank_cards = []
        self.selected_idx = 0
        self.current_tab = 0  # 0: Switches, 1: Pranks
        self._can_autoclose = False

        # If current profile is in pranks, open directly on Pranks tab!
        prank_ids = [p["id"] for p in PRANK_PROFILES if p["id"] != "off"]
        if self.active_profile in prank_ids:
            self.current_tab = 1

        self.setup_ui()

    def setup_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(560)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)

        # Glass Container
        container = QFrame(self)
        container.setObjectName("container")
        container.setStyleSheet("""
            #container {
                background: rgba(13, 16, 25, 0.97);
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 18px;
            }
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(36)
        shadow.setColor(QColor(0, 0, 0, 220))
        shadow.setOffset(0, 14)
        container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(18, 16, 18, 16)
        container_layout.setSpacing(10)

        # Header Row
        header = QHBoxLayout()
        header.setContentsMargins(2, 2, 2, 0)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)

        title = QLabel("⌨️  MECHKEYS ENGINE")
        title.setStyleSheet("""
            color: #ffffff;
            font-size: 13px;
            font-weight: 900;
            letter-spacing: 1.5px;
        """)
        title_vbox.addWidget(title)

        subtitle = QLabel("HARDWARE ACCELERATED AUDIO")
        subtitle.setStyleSheet("""
            color: #636e88;
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 1.2px;
        """)
        title_vbox.addWidget(subtitle)
        header.addLayout(title_vbox)

        header.addStretch()

        latency_badge = QLabel("⚡ 0.05ms BUFFER")
        latency_badge.setStyleSheet("""
            color: #1dd1a1;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 0.8px;
            background: rgba(29, 209, 161, 0.12);
            padding: 4px 9px;
            border-radius: 10px;
            border: 1px solid rgba(29, 209, 161, 0.3);
        """)
        header.addWidget(latency_badge)
        container_layout.addLayout(header)

        # Tab Selector Bar
        tab_bar = QHBoxLayout()
        tab_bar.setSpacing(8)

        self.btn_switches = QPushButton("⌨️  Mechanical Switches")
        self.btn_pranks = QPushButton("🎭  Pranks & Memes")
        for btn in (self.btn_switches, self.btn_pranks):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(32)

        self.btn_switches.clicked.connect(lambda: self.switch_to_tab(0))
        self.btn_pranks.clicked.connect(lambda: self.switch_to_tab(1))

        tab_bar.addWidget(self.btn_switches)
        tab_bar.addWidget(self.btn_pranks)
        container_layout.addLayout(tab_bar)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background: rgba(255, 255, 255, 0.08); max-height: 1px;")
        container_layout.addWidget(divider)

        # Stacked Widget for Pages
        self.stack = QStackedWidget()

        # Page 0: Switches
        page0 = QWidget()
        page0_layout = QVBoxLayout(page0)
        page0_layout.setContentsMargins(0, 0, 0, 0)
        page0_layout.setSpacing(7)

        for i, item in enumerate(SWITCH_PROFILES):
            is_active = (self.is_muted and item["id"] == "off") or (not self.is_muted and item["id"] == self.active_profile)
            if is_active and self.current_tab == 0:
                self.selected_idx = i
            card = ProfileCard(item, is_active, self.select_profile)
            self.switch_cards.append(card)
            page0_layout.addWidget(card)
        self.stack.addWidget(page0)

        # Page 1: Pranks
        page1 = QWidget()
        page1_layout = QVBoxLayout(page1)
        page1_layout.setContentsMargins(0, 0, 0, 0)
        page1_layout.setSpacing(7)

        for i, item in enumerate(PRANK_PROFILES):
            is_active = (self.is_muted and item["id"] == "off") or (not self.is_muted and item["id"] == self.active_profile)
            if is_active and self.current_tab == 1:
                self.selected_idx = i
            card = ProfileCard(item, is_active, self.select_profile)
            self.prank_cards.append(card)
            page1_layout.addWidget(card)
        self.stack.addWidget(page1)

        container_layout.addWidget(self.stack)

        # Footer hints
        footer = QHBoxLayout()
        footer.setContentsMargins(4, 4, 4, 0)
        hint = QLabel("⚡ Press [0-7] instant  •  Tab / ← / → switch mode  •  ↑/↓ select  •  Esc close")
        hint.setStyleSheet("color: #636e88; font-size: 11px; font-weight: 500;")
        footer.addWidget(hint)
        container_layout.addLayout(footer)

        main_layout.addWidget(container)

        self.update_tab_styles()
        self.position_window()

        # Arm auto-close after 350ms to allow smooth focus transition on Wayland
        QTimer.singleShot(350, self._arm_autoclose)

    def _arm_autoclose(self):
        self._can_autoclose = True

    def changeEvent(self, event):
        if event.type() == event.Type.ActivationChange:
            if self._can_autoclose and not self.isActiveWindow():
                self.close()
        super().changeEvent(event)

    def update_tab_styles(self):
        active_tab_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.12);
                color: #ffffff;
                font-weight: 800;
                font-size: 12px;
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 8px;
            }
        """
        inactive_tab_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.03);
                color: #718096;
                font-weight: 600;
                font-size: 12px;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 8px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.06);
                color: #cbd5e0;
            }
        """
        if self.current_tab == 0:
            self.btn_switches.setStyleSheet(active_tab_style)
            self.btn_pranks.setStyleSheet(inactive_tab_style)
        else:
            self.btn_switches.setStyleSheet(inactive_tab_style)
            self.btn_pranks.setStyleSheet(active_tab_style)

        self.stack.setCurrentIndex(self.current_tab)

        cards = self.active_cards()
        if 0 <= self.selected_idx < len(cards):
            cards[self.selected_idx].apply_style(hover=True)

    def switch_to_tab(self, tab_idx):
        if self.current_tab != tab_idx:
            # Unhover previous
            old_cards = self.active_cards()
            if 0 <= self.selected_idx < len(old_cards) and not old_cards[self.selected_idx].is_active:
                old_cards[self.selected_idx].apply_style(hover=False)

            self.current_tab = tab_idx
            self.selected_idx = 0
            # If active profile is in this tab, select it
            for i, card in enumerate(self.active_cards()):
                if card.is_active:
                    self.selected_idx = i
                    break
            self.update_tab_styles()

    def active_cards(self):
        return self.switch_cards if self.current_tab == 0 else self.prank_cards

    def active_profiles(self):
        return SWITCH_PROFILES if self.current_tab == 0 else PRANK_PROFILES

    def position_window(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = 50
        self.move(x, y)

    def select_profile(self, profile_id):
        if profile_id == "off":
            send_ipc("SET off")
            self.notify("MechKeys Muted", "Keystroke audio silenced 🔇")
        else:
            send_ipc(f"SET {profile_id}")
            all_profiles = SWITCH_PROFILES + PRANK_PROFILES
            name = next((p["name"] for p in all_profiles if p["id"] == profile_id), profile_id)
            self.notify("MechKeys Activated", f"Switched to {name} ⚡")
        self.close()

    def notify(self, title, msg):
        import subprocess
        try:
            subprocess.Popen(["notify-send", title, msg, "-t", "1200", "-a", "MechKeys", "-i", "input-keyboard"])
        except Exception:
            pass

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        text = event.text()

        KEY_MAP = {
            "1": Qt.Key.Key_1,
            "2": Qt.Key.Key_2,
            "3": Qt.Key.Key_3,
            "4": Qt.Key.Key_4,
            "5": Qt.Key.Key_5,
            "6": Qt.Key.Key_6,
            "7": Qt.Key.Key_7,
            "0": Qt.Key.Key_0,
        }

        # Tab or Left/Right arrows to flip categories
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Right, Qt.Key.Key_Left):
            new_tab = 1 - self.current_tab
            self.switch_to_tab(new_tab)
            return

        # Instant number key selection [0-7] on active tab
        profiles = self.active_profiles()
        for item in profiles:
            k = item["key"]
            if text == k or key == KEY_MAP.get(k):
                self.select_profile(item["id"])
                return

        cards = self.active_cards()
        if key == Qt.Key.Key_Escape:
            self.close()
        elif key == Qt.Key.Key_Down:
            if not cards[self.selected_idx].is_active:
                cards[self.selected_idx].apply_style(hover=False)
            self.selected_idx = (self.selected_idx + 1) % len(cards)
            cards[self.selected_idx].apply_style(hover=True)
        elif key == Qt.Key.Key_Up:
            if not cards[self.selected_idx].is_active:
                cards[self.selected_idx].apply_style(hover=False)
            self.selected_idx = (self.selected_idx - 1 + len(cards)) % len(cards)
            cards[self.selected_idx].apply_style(hover=True)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            chosen = profiles[self.selected_idx]["id"]
            self.select_profile(chosen)
        else:
            super().keyPressEvent(event)

def main():
    app = QApplication(sys.argv)
    window = MechkeysDropdownUI()
    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
