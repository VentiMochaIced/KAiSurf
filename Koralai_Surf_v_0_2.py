# Koralai Web Browser - Alpha v0.2.0
# Project: Learn Python
# Purpose: Educational tool to demonstrate browser shell construction and add-on architecture.
# For educational purposes only.

import sys
import json
import os
import importlib.util
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QLineEdit, QPushButton, QTabWidget, QToolBar, QSplitter, QTextEdit)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtCore import QUrl, Qt, QObject, pyqtSlot
from PyQt6.QtGui import QIcon, QAction

# --- Configuration ---
CONFIG = {
    "default_homepage": "https://www.google.com",
    "window_title": "Koralai Browser | Alpha v0.2.0",
    "initial_width": 1600,
    "initial_height": 900,
    "settings_file": "koralai_settings.json",
    "addons_folder": "addons"
}

# --- KoralaiBridge: The connection between Add-ons and the Browser ---
class KoralaiBridge:
    """
    Provides a controlled API for add-ons to interact with the browser.
    An instance of this class is passed to each loaded add-on.
    """
    def __init__(self, main_window):
        self._window = main_window

    def get_current_webview(self):
        """Returns the currently active QWebEngineView instance."""
        return self._window.tabs.currentWidget()

    def get_page_text(self, callback):
        """
        Asynchronously retrieves the full text content of the current page.
        The result is passed to the provided callback function.
        """
        view = self.get_current_webview()
        if view:
            view.page().toPlainText(callback)

    def fill_form_field(self, selector, value):
        """
        Finds a form field using a CSS selector and fills it with a value.
        Example: fill_form_field("#search_input", "Hello, World!")
        """
        view = self.get_current_webview()
        if view:
            # Note: Best practice is to escape the value to prevent JS injection
            escaped_value = value.replace('"', '\\"')
            js_code = f'document.querySelector("{selector}").value = "{escaped_value}";'
            view.page().runJavaScript(js_code)

# --- Main Application Window ---
class KoralaiMainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super(KoralaiMainWindow, self).__init__(*args, **kwargs)

        self.setWindowTitle(CONFIG["window_title"])
        self.setGeometry(100, 100, CONFIG["initial_width"], CONFIG["initial_height"])
        self.settings = self.load_settings()
        self.homepage = self.settings.get("homepage", CONFIG["default_homepage"])
        self.addons = {}

        # --- Main Layout with Splitter ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)

        # Tab widget for web pages
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_address_bar_on_tab_change)
        
        # Add-on Panel (initially hidden)
        self.addon_panel = QWidget()
        self.addon_panel_layout = QVBoxLayout()
        self.addon_panel.setLayout(self.addon_panel_layout)
        
        self.splitter.addWidget(self.tabs)
        self.splitter.addWidget(self.addon_panel)
        self.addon_panel.hide() # Hide by default

        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet("background-color: #222; color: #AAA;")
        self.status_bar.showMessage("Status: Ready")

        self.setup_toolbar()
        self.add_new_tab(QUrl(self.homepage), 'Homepage')

        # --- Load Add-ons ---
        self.bridge = KoralaiBridge(self)
        self.load_addons()

        # --- Styling ---
        self.setStyleSheet("""
            QMainWindow { background-color: #222; }
            QToolBar { background-color: #333; border: none; padding: 5px; }
            QLineEdit {
                background-color: #444; color: #EEE; border: 1px solid #555;
                padding: 4px; font-family: monospace;
            }
            QPushButton {
                background-color: #555; color: #EEE; border: 1px solid #666;
                padding: 4px 10px; margin: 0 2px;
            }
            QPushButton:hover { background-color: #666; }
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                background: #333; color: #BBB; padding: 8px 15px; border-right: 1px solid #222;
            }
            QTabBar::tab:selected { background: #444; color: #FFF; }
            QTabBar::tab:!selected:hover { background: #555; }
            QSplitter::handle { background-color: #555; }
        """)

    def setup_toolbar(self):
        nav_toolbar = QToolBar("Navigation")
        nav_toolbar.setMovable(False)
        self.addToolBar(nav_toolbar)
        # ... (same button setup as before)
        back_btn = QPushButton("<"); back_btn.setToolTip("Back"); back_btn.clicked.connect(lambda: self.tabs.currentWidget().back()); nav_toolbar.addWidget(back_btn)
        fwd_btn = QPushButton(">"); fwd_btn.setToolTip("Forward"); fwd_btn.clicked.connect(lambda: self.tabs.currentWidget().forward()); nav_toolbar.addWidget(fwd_btn)
        reload_btn = QPushButton("↻"); reload_btn.setToolTip("Reload"); reload_btn.clicked.connect(lambda: self.tabs.currentWidget().reload()); nav_toolbar.addWidget(reload_btn)
        home_btn = QPushButton("⌂"); home_btn.setToolTip("Home"); home_btn.clicked.connect(self.navigate_home); nav_toolbar.addWidget(home_btn)
        self.url_bar = QLineEdit(); self.url_bar.returnPressed.connect(self.navigate_to_url); nav_toolbar.addWidget(self.url_bar)
        add_tab_btn = QPushButton("+"); add_tab_btn.setToolTip("New Tab"); add_tab_btn.clicked.connect(lambda: self.add_new_tab(QUrl(self.homepage), 'New Tab')); nav_toolbar.addWidget(add_tab_btn)
        self.addon_toolbar = QToolBar("Add-ons")
        self.addToolBar(Qt.ToolBarArea.RightToolBarArea, self.addon_toolbar)


    def add_new_tab(self, qurl, label):
        if not qurl or not qurl.isValid():
            qurl = QUrl(self.homepage)
        browser = QWebEngineView()
        browser.setUrl(qurl)
        i = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(i)
        browser.urlChanged.connect(lambda qurl, browser=browser: self.update_url_bar(qurl, browser))
        browser.loadFinished.connect(lambda _, browser=browser, i=i: self.tabs.setTabText(i, browser.page().title()[:20]))
        browser.loadProgress.connect(lambda p: self.status_bar.showMessage(f"Loading... {p}%"))

    def close_tab(self, i):
        if self.tabs.count() < 2: self.close()
        else: self.tabs.removeTab(i)

    def navigate_home(self):
        self.tabs.currentWidget().setUrl(QUrl(self.homepage))

    def navigate_to_url(self):
        raw_url = self.url_bar.text()
        if not raw_url.startswith(('http://', 'https://')):
            qurl = QUrl('http://' + raw_url)
        else:
            qurl = QUrl(raw_url)
        self.tabs.currentWidget().setUrl(qurl)

    def update_url_bar(self, qurl, browser=None):
        if browser != self.tabs.currentWidget(): return
        self.url_bar.setText(qurl.toString())
        self.url_bar.setCursorPosition(0)

    def update_address_bar_on_tab_change(self, i):
        if i > -1 and self.tabs.widget(i):
             qurl = self.tabs.widget(i).url()
             self.update_url_bar(qurl, self.tabs.widget(i))

    def load_settings(self):
        if os.path.exists(CONFIG["settings_file"]):
            try:
                with open(CONFIG["settings_file"], 'r') as f: return json.load(f)
            except json.JSONDecodeError:
                print(f"DIAGNOSTIC: Could not parse {CONFIG['settings_file']}. Using defaults.")
                return {}
        else:
            self.save_settings({"homepage": CONFIG["default_homepage"]})
            return {"homepage": CONFIG["default_homepage"]}

    def save_settings(self, settings_dict):
        try:
            with open(CONFIG["settings_file"], 'w') as f: json.dump(settings_dict, f, indent=4)
        except IOError as e:
            print(f"DIAG-ERROR: Could not save settings. Error: {e}")

    # --- Add-on Management ---
    def load_addons(self):
        """Finds and initializes all valid add-ons in the addons folder."""
        addon_dir = CONFIG["addons_folder"]
        if not os.path.isdir(addon_dir):
            os.makedirs(addon_dir)
            print(f"DIAGNOSTIC: Created addons directory at '{addon_dir}'")
            return

        for name in os.listdir(addon_dir):
            path = os.path.join(addon_dir, name)
            if os.path.isdir(path):
                manifest_path = os.path.join(path, 'manifest.json')
                if os.path.exists(manifest_path):
                    try:
                        with open(manifest_path) as f:
                            manifest = json.load(f)
                            self.load_single_addon(manifest, path)
                    except Exception as e:
                        print(f"DIAG-ERROR: Could not load addon '{name}'. Error: {e}")

    def load_single_addon(self, manifest, path):
        """Loads a single addon module and calls its initializer."""
        entry_point = manifest.get('entry_point')
        module_path = os.path.join(path, entry_point)

        spec = importlib.util.spec_from_file_location(manifest['name'], module_path)
        addon_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(addon_module)

        # Initialize the addon
        addon_instance = addon_module.initialize(self.bridge)
        self.addons[manifest['name']] = addon_instance

        # Add UI components from the addon
        addon_instance.setup_ui(self)
        print(f"DIAGNOSTIC: Successfully loaded addon '{manifest['name']}'")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("Koralai")
    window = KoralaiMainWindow()
    window.show()
    sys.exit(app.exec())

