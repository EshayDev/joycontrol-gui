#!/usr/bin/env python3

import sys
import asyncio
import threading
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QGroupBox,
    QMessageBox,
    QFileDialog,
    QDialog,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, QTimer, Signal, QSize

from joycontrol import logging_default as log
from joycontrol.controller import Controller
from joycontrol.controller_state import (
    ControllerState,
    button_press,
    button_release,
)
from joycontrol.memory import FlashMemory
from joycontrol.protocol import controller_protocol_factory
from joycontrol.server import create_hid_server
from joycontrol.nfc_tag import NFCTag
from joycontrol.device import HidDevice

logger = logging.getLogger(__name__)


class DarkTheme:
    BG_DARK = "#2a2d30"
    BG_MEDIUM = "#3a3d40"
    BG_LIGHT = "#54585a"
    BG_LIGHTER = "#707372"
    ACCENT = "#514689"
    ACCENT_HOVER = "#6b5a9d"
    SUCCESS = "#16a085"
    WARNING = "#f39c12"
    ERROR = "#e74c3c"
    TEXT_PRIMARY = "#f0f0f0"
    TEXT_SECONDARY = "#d0d0d0"
    TEXT_MUTED = "#a0a0a0"
    BORDER = "#707372"

    BTN_PRIMARY = "#514689"
    BTN_SECONDARY = "#707372"
    BTN_SUCCESS = "#28a745"
    BTN_WARNING = "#ffc107"
    BTN_DANGER = "#dc3545"
    BTN_ACTION = "#a7a4e0"
    BTN_SPECIAL = "#6f42c1"

    @staticmethod
    def get_stylesheet():
        return f"""
        QMainWindow {{
            background-color: {DarkTheme.BG_DARK};
            color: {DarkTheme.TEXT_PRIMARY};
        }}
        
        QWidget {{
            background-color: {DarkTheme.BG_DARK};
            color: {DarkTheme.TEXT_PRIMARY};
        }}
        
        QGroupBox {{
            background-color: {DarkTheme.BG_MEDIUM};
            border: 1px solid {DarkTheme.BORDER};
            border-radius: 4px;
            margin-top: 1ex;
            padding-top: 5px;
            font-weight: bold;
            font-size: 9pt;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 5px;
            padding: 0 4px 0 4px;
            color: {DarkTheme.TEXT_PRIMARY};
        }}
        
        QLabel {{
            color: {DarkTheme.TEXT_PRIMARY};
            font-size: 8pt;
            background-color: transparent;
        }}
        
        QPushButton {{
            background-color: {DarkTheme.BTN_PRIMARY};
            color: {DarkTheme.TEXT_PRIMARY};
            border: none;
            border-radius: 3px;
            padding: 4px 8px;
            font-weight: bold;
            font-size: 8pt;
            min-height: 10px;
            text-align: center;
        }}
        
        QPushButton:hover {{
            background-color: {DarkTheme.ACCENT_HOVER};
        }}
        
        QPushButton:pressed {{
            background-color: {DarkTheme.BG_DARK};
        }}
        
        QPushButton:disabled {{
            background-color: {DarkTheme.BG_LIGHT};
            color: {DarkTheme.TEXT_MUTED};
        }}
        
        QComboBox {{
            background-color: {DarkTheme.BG_LIGHT};
            color: {DarkTheme.TEXT_PRIMARY};
            border: 1px solid {DarkTheme.BORDER};
            border-radius: 3px;
            padding: 3px 6px;
            font-size: 8pt;
        }}
        
        QComboBox:hover {{
            border-color: {DarkTheme.ACCENT};
        }}
        
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {DarkTheme.TEXT_PRIMARY};
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {DarkTheme.BG_MEDIUM};
            color: {DarkTheme.TEXT_PRIMARY};
            border: 1px solid {DarkTheme.BORDER};
            selection-background-color: {DarkTheme.ACCENT};
        }}
        
        QLineEdit {{
            background-color: {DarkTheme.BG_LIGHT};
            color: {DarkTheme.TEXT_PRIMARY};
            border: 1px solid {DarkTheme.BORDER};
            border-radius: 3px;
            padding: 3px 6px;
            font-size: 8pt;
        }}
        
        QLineEdit:focus {{
            border-color: {DarkTheme.ACCENT};
        }}
        
        QDialog {{
            background-color: {DarkTheme.BG_DARK};
            color: {DarkTheme.TEXT_PRIMARY};
        }}
        
        QListWidget {{
            background-color: {DarkTheme.BG_MEDIUM};
            color: {DarkTheme.TEXT_PRIMARY};
            border: 1px solid {DarkTheme.BORDER};
            border-radius: 3px;
            padding: 4px;
            font-size: 8pt;
        }}
        
        QListWidget::item {{
            padding: 4px;
            border-radius: 2px;
        }}
        
        QListWidget::item:selected {{
            background-color: {DarkTheme.ACCENT};
        }}
        
        QListWidget::item:hover {{
            background-color: {DarkTheme.BG_LIGHT};
        }}
        
        QFrame {{
            background-color: transparent;
            border: none;
        }}
        """


class PairedSwitchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Connection Method")
        self.setModal(True)
        self.resize(250, 200)

        self.selected_address = None
        self.start_fresh = False

        self.setup_ui()
        self.detect_paired_switches()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Connect to your Nintendo Switch")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"font-size: 11pt; font-weight: bold; color: {DarkTheme.TEXT_PRIMARY}; margin: 5px;"
        )
        layout.addWidget(title)

        self.desc = QLabel(
            "Found paired Nintendo Switch devices. Choose how to connect:"
        )
        self.desc.setAlignment(Qt.AlignCenter)
        self.desc.setStyleSheet(
            f"color: {DarkTheme.TEXT_SECONDARY}; margin-bottom: 10px; font-size: 9pt;"
        )
        layout.addWidget(self.desc)

        self.devices_group = QGroupBox("Paired Consoles")
        devices_layout = QVBoxLayout(self.devices_group)

        self.devices_list = QListWidget()
        self.devices_list.setMinimumHeight(150)
        devices_layout.addWidget(self.devices_list)

        layout.addWidget(self.devices_group)

        button_layout = QHBoxLayout()

        self.use_paired_btn = QPushButton("Use Selected Console")
        self.use_paired_btn.setStyleSheet(
            f"font-weight: bold; min-height: 18px; font-size: 9pt;"
        )
        self.use_paired_btn.clicked.connect(self.use_paired_device)
        self.use_paired_btn.setEnabled(False)

        self.unpair_btn = QPushButton("Unpair Selected Console")
        self.unpair_btn.setStyleSheet(
            f"font-weight: bold; min-height: 18px; font-size: 9pt;"
        )
        self.unpair_btn.clicked.connect(self.unpair_device)
        self.unpair_btn.setEnabled(False)

        self.start_fresh_btn = QPushButton("Pair New Console")
        self.start_fresh_btn.setStyleSheet(
            f"font-weight: bold; min-height: 18px; font-size: 9pt;"
        )
        self.start_fresh_btn.clicked.connect(self.start_fresh_pairing)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            f"font-weight: bold; min-height: 18px; font-size: 9pt;"
        )
        cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(self.use_paired_btn)
        button_layout.addWidget(self.unpair_btn)
        button_layout.addWidget(self.start_fresh_btn)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        self.devices_list.itemSelectionChanged.connect(self.on_selection_changed)

    def detect_paired_switches(self):
        try:
            hid_device = HidDevice()
            paired_switches = hid_device.get_paired_switches()

            if not paired_switches:
                self.devices_group.setTitle("No Paired Consoles Found")
                self.desc.setText(
                    "No paired consoles found. You can pair a new console below:"
                )
                item = QListWidgetItem("No paired Nintendo Switch consoles detected")
                item.setFlags(Qt.NoItemFlags)
                item.setData(Qt.UserRole, None)
                self.devices_list.addItem(item)
                self.use_paired_btn.setEnabled(False)
            else:
                valid_devices_added = 0
                for switch_path in paired_switches:
                    try:
                        address = HidDevice.get_address_of_paired_path(switch_path)
                        item = QListWidgetItem(f"Nintendo Switch - {address}")
                        item.setData(Qt.UserRole, address)
                        self.devices_list.addItem(item)
                        valid_devices_added += 1
                    except Exception as e:
                        logger.warning(f"Could not get address for {switch_path}: {e}")

                if valid_devices_added > 0:
                    self.devices_list.setCurrentRow(0)
                elif valid_devices_added == 0:
                    self.devices_group.setTitle("No Valid Devices Found")
                    self.desc.setText(
                        "No paired consoles found. You can pair a new console below:"
                    )
                    self.devices_list.clear()
                    item = QListWidgetItem("No valid Nintendo Switch consoles detected")
                    item.setFlags(Qt.NoItemFlags)
                    item.setData(Qt.UserRole, None)
                    self.devices_list.addItem(item)
                    self.use_paired_btn.setEnabled(False)

        except Exception as e:
            logger.error(f"Error detecting paired switches: {e}")
            self.devices_group.setTitle("Error Detecting Devices")
            self.desc.setText(
                "No paired consoles found. You can pair a new console below:"
            )
            item = QListWidgetItem(f"Error: {str(e)}")
            item.setFlags(Qt.NoItemFlags)
            self.devices_list.addItem(item)

    def on_selection_changed(self):
        selected_items = self.devices_list.selectedItems()
        has_valid_selection = (
            len(selected_items) > 0 and selected_items[0].data(Qt.UserRole) is not None
        )
        self.use_paired_btn.setEnabled(has_valid_selection)
        self.unpair_btn.setEnabled(has_valid_selection)

    def use_paired_device(self):
        selected_items = self.devices_list.selectedItems()
        if selected_items:
            self.selected_address = selected_items[0].data(Qt.UserRole)
            if self.selected_address:
                self.accept()

    def start_fresh_pairing(self):
        self.start_fresh = True
        self.accept()

    def unpair_device(self):
        selected_items = self.devices_list.selectedItems()
        if not selected_items:
            return

        address = selected_items[0].data(Qt.UserRole)
        if not address:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Unpair",
            f"Are you sure you want to unpair Nintendo Switch ({address})?\n\n"
            "This will remove the device from your Bluetooth paired devices list.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        try:
            result = subprocess.run(
                ["bluetoothctl", "remove", address],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Successfully unpaired Nintendo Switch ({address})",
                )
                self.devices_list.clear()
                self.detect_paired_switches()
            else:
                error_msg = (
                    result.stderr.strip() or result.stdout.strip() or "Unknown error"
                )
                QMessageBox.critical(
                    self,
                    "Unpair Failed",
                    f"Failed to unpair device ({address}):\n{error_msg}",
                )

        except subprocess.TimeoutExpired:
            QMessageBox.critical(
                self,
                "Timeout Error",
                "bluetoothctl command timed out. Please try again.",
            )
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "Error",
                "bluetoothctl command not found. Please ensure BlueZ is installed.",
            )
        except Exception as e:
            logger.error(f"Error unpairing device: {e}")
            QMessageBox.critical(
                self, "Error", f"Unexpected error while unpairing: {str(e)}"
            )


class ControllerButton(QPushButton):
    button_pressed = Signal(str)
    button_released = Signal(str)

    def __init__(
        self,
        button_name: str,
        text: str = None,
        color: str = None,
        circular: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.button_name = button_name
        self.base_color = color or DarkTheme.BTN_PRIMARY
        self.is_controller_pressed = False
        self.is_circular = circular

        self.setText(text or button_name.upper())

        if circular:
            self.setMinimumSize(QSize(30, 30))
            self.setMaximumSize(QSize(80, 80))
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        else:
            self.setMinimumSize(QSize(50, 25))
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.update_style()

        self.pressed.connect(self.on_press)
        self.released.connect(self.on_release)

    def sizeHint(self):
        if self.is_circular:
            return QSize(40, 40)
        else:
            return super().sizeHint()

    def minimumSizeHint(self):
        if self.is_circular:
            return QSize(30, 30)
        else:
            return super().minimumSizeHint()

    def hasHeightForWidth(self):
        return self.is_circular

    def heightForWidth(self, width):
        if self.is_circular:
            return width
        return (
            super().heightForWidth(width)
            if hasattr(super(), "heightForWidth")
            else width
        )

    def update_style(self):
        if self.is_controller_pressed:
            bg_color = DarkTheme.BG_DARK
        else:
            bg_color = self.base_color

        hover_color = self.get_hover_color(self.base_color)

        if self.is_circular:
            current_size = min(self.width(), self.height())
            radius = max(12, current_size // 2)

            self.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {bg_color};
                    color: {DarkTheme.TEXT_PRIMARY};
                    border: none;
                    border-radius: {radius}px;
                    font-weight: bold;
                    font-size: 10pt;
                    text-align: center;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
                QPushButton:pressed {{
                    background-color: {DarkTheme.BG_DARK};
                    border: 2px solid {self.base_color};
                }}
            """
            )
        else:
            self.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {bg_color};
                    color: {DarkTheme.TEXT_PRIMARY};
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 10pt;
                    min-height: 22px;
                    text-align: center;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
                QPushButton:pressed {{
                    background-color: {DarkTheme.BG_DARK};
                    border: 1px solid {self.base_color};
                }}
            """
            )

    def get_hover_color(self, base_color: str) -> str:
        hover_map = {
            DarkTheme.BTN_PRIMARY: DarkTheme.ACCENT_HOVER,
            DarkTheme.BTN_SUCCESS: "#20c997",
            DarkTheme.BTN_DANGER: "#e85a5a",
            DarkTheme.BTN_WARNING: "#ffcd39",
            DarkTheme.BTN_SECONDARY: "#8a8d8f",
            DarkTheme.BTN_ACTION: "#bbb8e8",
            DarkTheme.BTN_SPECIAL: "#7d4dd3",
        }
        return hover_map.get(base_color, DarkTheme.ACCENT_HOVER)

    def on_press(self):
        self.button_pressed.emit(self.button_name)

    def on_release(self):
        self.button_released.emit(self.button_name)

    def set_controller_pressed(self, pressed: bool):
        self.is_controller_pressed = pressed
        self.update_style()

    def resizeEvent(self, event):
        if self.is_circular:
            size = event.size()
            min_dimension = min(size.width(), size.height())

            if size.width() != min_dimension or size.height() != min_dimension:
                self.resize(min_dimension, min_dimension)

            self.update_style()
        super().resizeEvent(event)


class AsyncWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, async_loop, coro):
        super().__init__()
        self.async_loop = async_loop
        self.coro = coro
        self.future = None

    def run(self):
        try:
            if self.async_loop and not self.async_loop.is_closed():
                self.future = asyncio.run_coroutine_threadsafe(
                    self.coro, self.async_loop
                )
                self.future.result()
                self.finished.emit(True, "Success")
            else:
                self.finished.emit(False, "Async loop not available")
        except Exception as e:
            logger.error(f"AsyncWorker error: {e}")
            self.finished.emit(False, str(e))


class JoyControlGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.controller_state: Optional[ControllerState] = None
        self.transport = None
        self.protocol = None
        self.connected = False
        self.reconnect_address = None
        self._last_connected_address = None

        self.button_widgets: Dict[str, ControllerButton] = {}
        self.button_states: Dict[str, bool] = {}

        self.current_amiibo = None

        self.async_loop = None
        self.async_thread = None
        self.connection_worker = None

        self.connection_monitor_timer = QTimer()
        self.connection_monitor_timer.timeout.connect(self.check_connection_status)
        self.connection_monitor_timer.setInterval(1000)

        self.setup_window()
        self.setup_async_loop()

        QTimer.singleShot(100, self.show_startup_dialog)

    def setup_window(self):
        self.setWindowTitle("joycontrol-gui")
        self.setMinimumSize(600, 600)

        self.setAttribute(Qt.WA_AcceptTouchEvents, False)
        self.setStyleSheet(DarkTheme.get_stylesheet())

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        self.setup_ui()

    def setup_ui(self):
        self.setup_connection_section()
        self.setup_controller_section()
        self.setup_amiibo_section()
        self.setup_status_section()

    def setup_connection_section(self):
        connection_group = QGroupBox("Connection Settings")
        connection_layout = QHBoxLayout(connection_group)
        connection_layout.setSpacing(8)

        self.reconnect_entry = QLineEdit()
        self.reconnect_entry.hide()

        self.connection_info = QLabel("Click Connect to choose your Nintendo Switch")
        self.connection_info.setStyleSheet(
            f"color: {DarkTheme.TEXT_SECONDARY}; font-size: 9pt;"
        )
        connection_layout.addWidget(self.connection_info)

        connection_layout.addStretch()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setStyleSheet(
            f"min-width: 60px; min-height: 18px; font-size: 9pt;"
        )
        self.connect_btn.clicked.connect(self.toggle_connection)
        connection_layout.addWidget(self.connect_btn)

        self.main_layout.addWidget(connection_group)

    def setup_controller_section(self):
        self.controller_group = QGroupBox("Controller")
        self.controller_layout = QVBoxLayout(self.controller_group)

        self.create_controller_layout()

        self.main_layout.addWidget(self.controller_group, 1)

    def setup_amiibo_section(self):
        amiibo_group = QGroupBox("Amiibo Emulation")
        amiibo_layout = QHBoxLayout(amiibo_group)
        amiibo_layout.setSpacing(8)

        self.amiibo_status = QLabel("No amiibo loaded")
        self.amiibo_status.setStyleSheet(
            f"color: {DarkTheme.TEXT_MUTED}; font-size: 9pt;"
        )
        amiibo_layout.addWidget(self.amiibo_status)

        amiibo_layout.addStretch()

        self.amiibo_btn = QPushButton("Load Amiibo")
        self.amiibo_btn.setStyleSheet(
            f"min-height: 18px; font-size: 9pt; text-align: center;"
        )
        self.amiibo_btn.clicked.connect(self.toggle_amiibo)
        amiibo_layout.addWidget(self.amiibo_btn)

        self.main_layout.addWidget(amiibo_group)

    def update_amiibo_button(self):
        if self.current_amiibo:
            self.amiibo_btn.setText("Eject Amiibo")
            self.amiibo_btn.setStyleSheet(f"min-height: 35px; font-weight: bold;")
        else:
            self.amiibo_btn.setText("Load Amiibo")
            self.amiibo_btn.setStyleSheet(f"min-height: 35px; font-weight: bold;")

    def setup_status_section(self):
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)

        connection_label = QLabel("🔗 Connection:")
        status_layout.addWidget(connection_label)

        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet(f"color: {DarkTheme.ERROR}; font-weight: bold;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        version_label = QLabel("Made with ❤️ by EshayDev")
        version_label.setStyleSheet(f"color: {DarkTheme.TEXT_MUTED}; font-size: 8pt;")
        status_layout.addWidget(version_label)

        self.main_layout.addWidget(status_frame)

    def setup_async_loop(self):
        def run_loop():
            try:
                self.async_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.async_loop)
                logger.info("Async loop started")
                self.async_loop.run_forever()
            except Exception as e:
                logger.error(f"Error in async loop: {e}")
            finally:
                logger.info("Async loop stopped")

        self.async_thread = threading.Thread(target=run_loop, daemon=True)
        self.async_thread.start()

        import time

        time.sleep(0.1)

    def run_async(self, coro):
        if self.async_loop:
            future = asyncio.run_coroutine_threadsafe(coro, self.async_loop)
            return future
        return None

    def show_startup_dialog(self):
        try:
            dialog = PairedSwitchDialog(self)
            if dialog.exec() == QDialog.Accepted:
                if dialog.start_fresh:
                    self.reconnect_address = None
                    self.connect(start_fresh=True)
                elif dialog.selected_address:
                    self.reconnect_address = dialog.selected_address
                    self.reconnect_entry.setText(dialog.selected_address)
                    self.connect()

        except Exception as e:
            logger.error(f"Error in startup dialog: {e}")

    def show_connection_dialog(self):
        try:
            dialog = PairedSwitchDialog(self)
            if dialog.exec() == QDialog.Accepted:
                if dialog.start_fresh:
                    self.reconnect_address = None
                    self.reconnect_entry.setText("")
                    self.connect(start_fresh=True)
                elif dialog.selected_address:
                    self.reconnect_address = dialog.selected_address
                    self.reconnect_entry.setText(dialog.selected_address)
                    self.connect()

        except Exception as e:
            logger.error(f"Error in connection dialog: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to show connection dialog: {e}"
            )

    def create_controller_layout(self):
        for i in reversed(range(self.controller_layout.count())):
            child = self.controller_layout.takeAt(i)
            if child.widget():
                child.widget().deleteLater()

        self.button_widgets.clear()
        self.button_states.clear()

        self.create_pro_controller_layout()

    def create_pro_controller_layout(self):
        main_widget = QWidget()
        main_layout = QGridLayout(main_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(5, 5, 5, 5)

        dpad_frame = QFrame()
        dpad_frame_layout = QVBoxLayout(dpad_frame)
        dpad_frame_layout.setSpacing(5)

        dpad_label = QLabel("D-Pad")
        dpad_label.setAlignment(Qt.AlignCenter)
        dpad_label.setStyleSheet(
            "font-weight: bold; font-size: 10pt; margin-bottom: 8px;"
        )
        dpad_frame_layout.addWidget(dpad_label)

        dpad_widget = QWidget()
        dpad_layout = QGridLayout(dpad_widget)
        dpad_layout.setSpacing(1)
        dpad_layout.setAlignment(Qt.AlignCenter)
        dpad_layout.setContentsMargins(0, 0, 0, 0)

        self.add_button(dpad_layout, "up", 0, 1, "↑", "#54585a", circular=True)
        self.add_button(dpad_layout, "left", 1, 0, "←", "#54585a", circular=True)
        self.add_button(dpad_layout, "right", 1, 2, "→", "#54585a", circular=True)
        self.add_button(dpad_layout, "down", 2, 1, "↓", "#54585a", circular=True)

        dpad_frame_layout.addWidget(dpad_widget, 1)

        system_frame = QFrame()
        system_frame_layout = QVBoxLayout(system_frame)
        system_frame_layout.setSpacing(5)

        system_label = QLabel("System")
        system_label.setAlignment(Qt.AlignCenter)
        system_label.setStyleSheet(
            "font-weight: bold; font-size: 10pt; margin-bottom: 8px;"
        )
        system_frame_layout.addWidget(system_label)

        system_widget = QWidget()
        system_layout = QGridLayout(system_widget)
        system_layout.setSpacing(8)
        system_layout.setAlignment(Qt.AlignCenter)
        system_layout.setContentsMargins(10, 10, 10, 10)

        self.add_button(system_layout, "minus", 0, 0, "−", "#707372")
        self.add_button(system_layout, "home", 0, 1, "HOME", "#707372")
        self.add_button(system_layout, "plus", 0, 2, "+", "#707372")
        self.add_button(system_layout, "capture", 1, 1, "⧇", "#707372")

        for i in range(3):
            system_layout.setColumnStretch(i, 1)
        system_layout.setRowStretch(0, 1)
        system_layout.setRowStretch(1, 1)

        system_frame_layout.addWidget(system_widget, 1)

        action_frame = QFrame()
        action_frame_layout = QVBoxLayout(action_frame)
        action_frame_layout.setSpacing(5)

        action_label = QLabel("Action Buttons")
        action_label.setAlignment(Qt.AlignCenter)
        action_label.setStyleSheet(
            "font-weight: bold; font-size: 10pt; margin-bottom: 8px;"
        )
        action_frame_layout.addWidget(action_label)

        action_widget = QWidget()
        action_layout = QGridLayout(action_widget)
        action_layout.setSpacing(1)
        action_layout.setAlignment(Qt.AlignCenter)
        action_layout.setContentsMargins(0, 0, 0, 0)

        self.add_button(action_layout, "x", 0, 1, "X", "#a7a4e0", circular=True)
        self.add_button(action_layout, "y", 1, 0, "Y", "#a7a4e0", circular=True)
        self.add_button(action_layout, "b", 2, 1, "B", "#514689", circular=True)
        self.add_button(action_layout, "a", 1, 2, "A", "#514689", circular=True)

        action_frame_layout.addWidget(action_widget, 1)

        left_shoulder_frame = QFrame()
        left_shoulder_layout = QVBoxLayout(left_shoulder_frame)
        left_shoulder_layout.setSpacing(5)

        left_shoulder_label = QLabel("Shoulder")
        left_shoulder_label.setAlignment(Qt.AlignCenter)
        left_shoulder_label.setStyleSheet(
            "font-weight: bold; font-size: 10pt; margin-bottom: 8px;"
        )
        left_shoulder_layout.addWidget(left_shoulder_label)

        left_shoulder_widget = QWidget()
        left_shoulder_buttons = QVBoxLayout(left_shoulder_widget)
        left_shoulder_buttons.setSpacing(8)
        left_shoulder_buttons.setContentsMargins(15, 10, 15, 10)

        l_btn = self.create_button("l", "L", "#707372")
        zl_btn = self.create_button("zl", "ZL", "#707372")
        left_shoulder_buttons.addWidget(l_btn)
        left_shoulder_buttons.addWidget(zl_btn)

        left_shoulder_layout.addWidget(left_shoulder_widget, 1)

        analog_frame = QFrame()
        analog_frame_layout = QVBoxLayout(analog_frame)
        analog_frame_layout.setSpacing(5)

        stick_label = QLabel("Analog Sticks")
        stick_label.setAlignment(Qt.AlignCenter)
        stick_label.setStyleSheet(
            "font-weight: bold; font-size: 10pt; margin-bottom: 8px;"
        )
        analog_frame_layout.addWidget(stick_label)

        stick_widget = QWidget()
        stick_layout = QGridLayout(stick_widget)
        stick_layout.setSpacing(15)
        stick_layout.setAlignment(Qt.AlignCenter)
        stick_layout.setContentsMargins(20, 15, 20, 15)

        l_stick_btn = self.create_button("l_stick", "L3", "#707372", circular=True)
        r_stick_btn = self.create_button("r_stick", "R3", "#707372", circular=True)

        l_stick_btn.setMinimumSize(QSize(45, 45))
        r_stick_btn.setMinimumSize(QSize(45, 45))

        stick_layout.addWidget(l_stick_btn, 0, 0, Qt.AlignCenter)
        stick_layout.addWidget(r_stick_btn, 0, 1, Qt.AlignCenter)

        stick_layout.setColumnStretch(0, 1)
        stick_layout.setColumnStretch(1, 1)
        stick_layout.setRowStretch(0, 1)

        analog_frame_layout.addWidget(stick_widget, 1)

        right_shoulder_frame = QFrame()
        right_shoulder_layout = QVBoxLayout(right_shoulder_frame)
        right_shoulder_layout.setSpacing(5)

        right_shoulder_label = QLabel("Shoulder")
        right_shoulder_label.setAlignment(Qt.AlignCenter)
        right_shoulder_label.setStyleSheet(
            "font-weight: bold; font-size: 10pt; margin-bottom: 8px;"
        )
        right_shoulder_layout.addWidget(right_shoulder_label)

        right_shoulder_widget = QWidget()
        right_shoulder_buttons = QVBoxLayout(right_shoulder_widget)
        right_shoulder_buttons.setSpacing(8)
        right_shoulder_buttons.setContentsMargins(15, 10, 15, 10)

        r_btn = self.create_button("r", "R", "#707372")
        zr_btn = self.create_button("zr", "ZR", "#707372")
        right_shoulder_buttons.addWidget(r_btn)
        right_shoulder_buttons.addWidget(zr_btn)

        right_shoulder_layout.addWidget(right_shoulder_widget, 1)

        main_layout.addWidget(dpad_frame, 0, 0)
        main_layout.addWidget(system_frame, 0, 1)
        main_layout.addWidget(action_frame, 0, 2)
        main_layout.addWidget(left_shoulder_frame, 1, 0)
        main_layout.addWidget(analog_frame, 1, 1)
        main_layout.addWidget(right_shoulder_frame, 1, 2)

        main_layout.setColumnStretch(0, 2)
        main_layout.setColumnStretch(1, 3)
        main_layout.setColumnStretch(2, 2)

        main_layout.setRowStretch(0, 1)
        main_layout.setRowStretch(1, 1)

        self.controller_layout.addWidget(main_widget)

    def create_button(
        self, button_name: str, text: str, color: str, circular: bool = False
    ) -> ControllerButton:
        button = ControllerButton(button_name, text, color, circular)
        button.button_pressed.connect(self.on_button_press)
        button.button_released.connect(self.on_button_release)

        self.button_widgets[button_name] = button
        self.button_states[button_name] = False

        return button

    def add_button(
        self,
        layout: QGridLayout,
        button_name: str,
        row: int,
        col: int,
        text: str,
        color: str,
        circular: bool = False,
    ):
        button = self.create_button(button_name, text, color, circular)

        if circular:
            layout.addWidget(button, row, col, Qt.AlignCenter)
        else:
            layout.addWidget(button, row, col)

    def toggle_connection(self):
        if self.connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self, start_fresh=False):
        try:
            if os.geteuid() != 0:
                QMessageBox.critical(
                    self, "Error", "This application must be run as root!"
                )
                return

            reconnect_addr = (
                self.reconnect_entry.text().strip() or self.reconnect_address
            )

            if not reconnect_addr and not start_fresh:
                self.show_connection_dialog()
                return

            self.connect_btn.setText("Connecting...")
            self.connect_btn.setEnabled(False)
            self.status_label.setText("Connecting...")
            self.status_label.setStyleSheet(
                f"color: {DarkTheme.WARNING}; font-weight: bold;"
            )

            controller_type = "PRO_CONTROLLER"

            final_reconnect_addr = None if start_fresh else reconnect_addr

            logger.info(
                f"Starting connection. Start fresh: {start_fresh}, Reconnect addr: {final_reconnect_addr}"
            )

            connection_coro = self._connect_async(controller_type, final_reconnect_addr)
            self.connection_worker = AsyncWorker(self.async_loop, connection_coro)
            self.connection_worker.finished.connect(self.on_connection_finished)
            self.connection_worker.start()

        except Exception as e:
            logger.error(f"Connection error: {e}")
            QMessageBox.critical(self, "Connection Error", str(e))
            self.reset_connection_ui()

    async def _connect_async(self, controller_type: str, reconnect_addr: Optional[str]):
        try:
            controller = Controller.from_arg(controller_type)
            spi_flash = FlashMemory()
            factory = controller_protocol_factory(
                controller, spi_flash=spi_flash, reconnect=reconnect_addr
            )

            self.transport, self.protocol = await create_hid_server(
                factory,
                reconnect_bt_addr=reconnect_addr,
                ctl_psm=17,
                itr_psm=19,
                capture_file=None,
                device_id=None,
                interactive=False,
            )

            self.controller_state = self.protocol.get_controller_state()

            await self.controller_state.connect()

            self.connected = True

        except Exception as e:
            logger.error(f"Async connection error: {e}")
            raise

    def on_connection_finished(self, success: bool, message: str):
        try:
            if success:
                self.status_label.setText("Connected")
                self.status_label.setStyleSheet(
                    f"color: {DarkTheme.BTN_ACTION}; font-weight: bold;"
                )
                self.connect_btn.setText("Disconnect")
                self.connect_btn.setEnabled(True)

                addr = "Unknown"
                try:
                    if self.transport and hasattr(self.transport, "_itr_sock"):
                        peer_info = self.transport._itr_sock.getpeername()
                        addr = (
                            peer_info[0]
                            if peer_info
                            else (self.reconnect_address or "Unknown")
                        )
                    else:
                        addr = self.reconnect_address or "Unknown"
                except Exception as e:
                    logger.debug(f"Could not get peer address: {e}")
                    addr = self.reconnect_address or "Unknown"

                if addr != "Unknown":
                    self._last_connected_address = addr
                    logger.info(f"Stored address for auto-reconnect: {addr}")

                self.connection_info.setText(f"Connected to: {addr}")
                self.connection_info.setStyleSheet(
                    f"color: {DarkTheme.BTN_ACTION}; font-size: 9pt;"
                )

                self.connection_monitor_timer.start()

                self.update_amiibo_button()
            else:
                logger.error(f"Connection failed: {message}")
                QMessageBox.critical(self, "Connection Failed", message)
                self.reset_connection_ui()

        finally:
            self.connection_worker = None

    def disconnect(self):
        try:
            self.connection_monitor_timer.stop()

            if self.connection_worker and self.connection_worker.isRunning():
                if self.connection_worker.future:
                    self.connection_worker.future.cancel()
                self.connection_worker.quit()
                self.connection_worker.wait()

            if self.transport:
                self.run_async(self.transport.close())

            self.connected = False
            self.controller_state = None
            self.transport = None
            self.protocol = None
            self.connection_worker = None

            self.reconnect_address = None
            self.reconnect_entry.setText("")
            self._last_connected_address = None

            self.reset_connection_ui()
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet(
                f"color: {DarkTheme.ERROR}; font-weight: bold;"
            )

            self.connection_info.setText("Click Connect to choose your Nintendo Switch")
            self.connection_info.setStyleSheet(
                f"color: {DarkTheme.TEXT_SECONDARY}; font-size: 9pt;"
            )

        except Exception as e:
            logger.error(f"Disconnect error: {e}")

    def reset_connection_ui(self):
        self.connect_btn.setText("Connect")
        self.connect_btn.setEnabled(True)

        self.connection_info.setText("Click Connect to choose your Nintendo Switch")
        self.connection_info.setStyleSheet(
            f"color: {DarkTheme.TEXT_SECONDARY}; font-size: 9pt;"
        )

    def check_connection_status(self):
        if not self.connected:
            return

        try:
            if self.protocol and self.protocol.transport is None:
                logger.warning("Connection lost detected - protocol transport is None")
                self.handle_connection_lost()
                return

            if self.transport and (
                self.transport.is_closing() or not hasattr(self.transport, "_itr_sock")
            ):
                logger.warning(
                    "Connection lost detected - transport is closing or invalid"
                )
                self.handle_connection_lost()
                return

        except Exception as e:
            logger.error(f"Error checking connection status: {e}")
            self.handle_connection_lost()

    def handle_connection_lost(self):
        if not self.connected:
            return

        logger.info("Handling unexpected connection loss")

        self.connected = False
        self.controller_state = None
        self.transport = None
        self.protocol = None

        self.connection_monitor_timer.stop()

        self.reconnect_address = None
        self.reconnect_entry.setText("")
        logger.info(
            f"Connection lost. Preserved last address: {getattr(self, '_last_connected_address', 'None')} for auto-reconnect"
        )

        self.reset_connection_ui()
        self.status_label.setText("Connection Lost")
        self.status_label.setStyleSheet(f"color: {DarkTheme.ERROR}; font-weight: bold;")

        self.connection_info.setText("Connection Lost - Click Connect to Reconnect")
        self.connection_info.setStyleSheet(f"color: {DarkTheme.ERROR}; font-size: 9pt;")

        self.current_amiibo = None
        self.amiibo_status.setText("No amiibo loaded")
        self.amiibo_status.setStyleSheet(f"color: {DarkTheme.TEXT_MUTED};")
        self.update_amiibo_button()

        for button_name, button_widget in self.button_widgets.items():
            button_widget.set_controller_pressed(False)
            self.button_states[button_name] = False

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Connection Lost")
        msg_box.setText("The connection to Nintendo Switch was lost.")
        msg_box.setInformativeText("Would you like to reconnect?")
        msg_box.setIcon(QMessageBox.Warning)

        reconnect_btn = msg_box.addButton("Reconnect", QMessageBox.AcceptRole)
        msg_box.addButton("Cancel", QMessageBox.RejectRole)

        msg_box.setDefaultButton(reconnect_btn)

        msg_box.exec()

        if msg_box.clickedButton() == reconnect_btn:
            QTimer.singleShot(100, self.auto_reconnect)

    def auto_reconnect(self):
        try:
            logger.info(
                f"Reconnect called. Last address: {getattr(self, '_last_connected_address', 'None')}"
            )
            logger.info(
                f"Current reconnect address: {getattr(self, 'reconnect_address', 'None')}"
            )

            if (
                hasattr(self, "_last_connected_address")
                and self._last_connected_address
            ):
                logger.info(f"Reconnecting to {self._last_connected_address}")
                self.reconnect_address = self._last_connected_address
                self.reconnect_entry.setText(self._last_connected_address)
                self.connect()
            else:
                logger.info("No previous address available, showing connection dialog")
                self.show_connection_dialog()

        except Exception as e:
            logger.error(f"Error during auto-reconnect: {e}")
            QMessageBox.critical(self, "Reconnect Failed", f"Failed to reconnect: {e}")

    def on_button_press(self, button_name: str):
        if not self.connected or not self.controller_state:
            return

        try:
            self.button_states[button_name] = True

            if button_name in self.button_widgets:
                self.button_widgets[button_name].set_controller_pressed(True)

            self.run_async(button_press(self.controller_state, button_name))

        except Exception as e:
            logger.error(f"Error handling button press {button_name}: {e}")

    def on_button_release(self, button_name: str):
        if not self.connected or not self.controller_state:
            if button_name in self.button_widgets:
                self.button_widgets[button_name].set_controller_pressed(False)
            return

        try:
            self.button_states[button_name] = False

            if button_name in self.button_widgets:
                self.button_widgets[button_name].set_controller_pressed(False)

            self.run_async(button_release(self.controller_state, button_name))

        except Exception as e:
            logger.error(f"Error handling button release {button_name}: {e}")

    def toggle_amiibo(self):
        if not self.connected or not self.controller_state:
            QMessageBox.warning(
                self, "Warning", "Please connect to a Nintendo Switch first!"
            )
            return

        if self.current_amiibo:
            try:
                self.controller_state.set_nfc(None)
                self.current_amiibo = None

                self.amiibo_status.setText("No amiibo loaded")
                self.amiibo_status.setStyleSheet(f"color: {DarkTheme.TEXT_MUTED};")
                self.update_amiibo_button()

            except Exception as e:
                logger.error(f"Error ejecting amiibo: {e}")
                QMessageBox.critical(self, "Error", f"Failed to eject amiibo: {e}")
        else:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Amiibo Dump", "", "Amiibo dumps (*.bin);;All files (*.*)"
            )

            if file_path:
                try:
                    nfc_tag = NFCTag.load_amiibo(file_path)
                    self.controller_state.set_nfc(nfc_tag)
                    self.current_amiibo = Path(file_path).name

                    self.amiibo_status.setText(f"{self.current_amiibo}")
                    self.amiibo_status.setStyleSheet(
                        f"color: {DarkTheme.BTN_ACTION}; font-weight: bold; font-size: 9pt;"
                    )
                    self.update_amiibo_button()

                except Exception as e:
                    logger.error(f"Error loading amiibo: {e}")
                    QMessageBox.critical(self, "Error", f"Failed to load amiibo: {e}")

    def closeEvent(self, event):
        try:
            self.connection_monitor_timer.stop()

            if self.connection_worker and self.connection_worker.isRunning():
                if self.connection_worker.future:
                    self.connection_worker.future.cancel()
                self.connection_worker.quit()
                self.connection_worker.wait()

            if self.connected:
                self.disconnect()

            if self.async_loop:
                self.async_loop.call_soon_threadsafe(self.async_loop.stop)

            if self.async_thread and self.async_thread.is_alive():
                self.async_thread.join(timeout=2.0)

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        event.accept()


def main():
    if os.geteuid() != 0:
        print("This application must be run as root!")
        print("Try: sudo python3 main.py")
        return 1

    os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.qpa.xcb.debug=false"
    os.environ["DCONF_PROFILE"] = "/dev/null"
    os.environ["GSETTINGS_BACKEND"] = "memory"

    log.configure(console_level=logging.WARNING)

    if hasattr(Qt, "AA_ShareOpenGLContexts"):
        QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

    app = QApplication(sys.argv)
    app.setApplicationName("joycontrol-gui")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("EshayDev")
    app.setQuitOnLastWindowClosed(True)

    font = app.font()
    font.setPointSize(max(8, font.pointSize()))
    app.setFont(font)

    try:
        window = JoyControlGUI()
        window.show()
        return app.exec()

    except Exception as e:
        print(f"Failed to start application: {e}")
        logger.error(f"Application startup error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
