# Koralai Web Browser - Alpha v0.1.0
# Project: Learn Python
# Purpose: Educational tool to demonstrate browser shell construction in Python.
# For educational purposes only.

import sys
import json
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QTabWidget, QToolBar, QLabel)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QIcon, QAction

# --- Configuration ---
# This section defines the initial settings for the browser.
# In a more advanced version, this would be part of a larger settings module.
CONFIG = {
    "default_homepage": "https://www.google.com",
    "window_title": "Koralai Browser | Alpha",
    "initial_width": 1280,
    "initial_height": 720,
    "settings_file": "koralai_settings.json"
}

# --- Main Application Window ---
class KoralaiMainWindow(QMainWindow):
    """ The main browser window, containing the toolbar, tabs, and status bar. """

    def __init__(self, *args, **kwargs):
        super(KoralaiMainWindow, self).__init__(*args, **kwargs)

        self.setWindowTitle(CONFIG["window_title"])
        self.setGeometry(100, 100, CONFIG["initial_width"], CONFIG["initial_height"])

        # Load user profile/settings
        self.settings = self.load_settings()
        self.homepage = self.settings.get("homepage", CONFIG["default_homepage"])

        # --- UI Components ---
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_address_bar_on_tab_change)
        self.setCentralWidget(self.tabs)

        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet("background-color: #222; color: #AAA;")
        self.status_bar.showMessage("Status: Ready")

        self.setup_toolbar()

        # --- Initial State ---
        self.add_new_tab(QUrl(self.homepage), 'Homepage')

        # Set the main window style to a dark, mono-tone theme
        self.setStyleSheet("""
            QMainWindow { background-color: #222; }
            QToolBar { background-color: #333; border: none; }
            QLineEdit {
                background-color: #444;
                color: #EEE;
                border: 1px solid #555;
                padding: 4px;
                font-family: monospace;
            }
            QPushButton {
                background-color: #555;
                color: #EEE;
                border: 1px solid #666;
                padding: 4px 10px;
            }
            QPushButton:hover { background-color: #666; }
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                background: #333;
                color: #BBB;
                padding: 8px 15px;
                border-right: 1px solid #222;
            }
            QTabBar::tab:selected { background: #444; color: #FFF; }
            QTabBar::tab:!selected:hover { background: #555; }
        """)


    def setup_toolbar(self):
        """ Creates and configures the main navigation toolbar. """
        nav_toolbar = QToolBar("Navigation")
        nav_toolbar.setMovable(False)
        self.addToolBar(nav_toolbar)

        # --- Toolbar Actions ---
        # Instead of icons, we use text for a minimalist, expert-level feel.
        back_btn = QPushButton("<")
        back_btn.setToolTip("Back")
        back_btn.clicked.connect(lambda: self.tabs.currentWidget().back())
        nav_toolbar.addWidget(back_btn)

        fwd_btn = QPushButton(">")
        fwd_btn.setToolTip("Forward")
        fwd_btn.clicked.connect(lambda: self.tabs.currentWidget().forward())
        nav_toolbar.addWidget(fwd_btn)

        reload_btn = QPushButton("↻")
        reload_btn.setToolTip("Reload")
        reload_btn.clicked.connect(lambda: self.tabs.currentWidget().reload())
        nav_toolbar.addWidget(reload_btn)

        home_btn = QPushButton("⌂")
        home_btn.setToolTip("Home")
        home_btn.clicked.connect(self.navigate_home)
        nav_toolbar.addWidget(home_btn)

        # --- Address Bar ---
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        nav_toolbar.addWidget(self.url_bar)

        # --- New Tab Button ---
        add_tab_btn = QPushButton("+")
        add_tab_btn.setToolTip("New Tab")
        add_tab_btn.clicked.connect(lambda: self.add_new_tab(QUrl(self.homepage), 'New Tab'))
        nav_toolbar.addWidget(add_tab_btn)

    # --- Core Functionality ---

    def add_new_tab(self, qurl, label):
        """ Adds a new tab to the tab widget. """
        # Error handling: Ensure URL is valid, otherwise use homepage
        if not qurl or not qurl.isValid():
            # This is a silent error propagation, as requested. The user sees a functional
            # result (homepage) rather than a crash.
            qurl = QUrl(self.homepage)

        browser = QWebEngineView()
        browser.setUrl(qurl)
        i = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(i)

        # Connect signals for the new tab
        browser.urlChanged.connect(lambda qurl, browser=browser:
                                   self.update_url_bar(qurl, browser))
        browser.loadFinished.connect(lambda _, browser=browser, i=i:
                                     self.tabs.setTabText(i, browser.page().title()[:20]))
        browser.loadProgress.connect(lambda p: self.status_bar.showMessage(f"Loading... {p}%"))


    def close_tab(self, i):
        """ Closes a tab. If it's the last tab, it closes the application. """
        if self.tabs.count() < 2:
            self.close() # Close the entire application
        else:
            self.tabs.removeTab(i)

    def navigate_home(self):
        """ Navigates the current tab to the user's homepage. """
        self.tabs.currentWidget().setUrl(QUrl(self.homepage))

    def navigate_to_url(self):
        """ Navigates to the URL entered in the address bar. """
        raw_url = self.url_bar.text()
        if not raw_url.startswith(('http://', 'https://')):
            # Add scheme for convenience, a typical browser feature
            qurl = QUrl('http://' + raw_url)
        else:
            qurl = QUrl(raw_url)
        self.tabs.currentWidget().setUrl(qurl)

    # --- Signal Handlers / Updaters ---

    def update_url_bar(self, qurl, browser=None):
        """ Updates the address bar text when the URL changes. """
        # Only update the URL bar if the view sending the signal is the currently active one.
        if browser != self.tabs.currentWidget():
            return
        self.url_bar.setText(qurl.toString())
        self.url_bar.setCursorPosition(0)

    def update_address_bar_on_tab_change(self, i):
        """ Called when the user switches tabs, updates the address bar. """
        if i > -1 and self.tabs.widget(i):
             qurl = self.tabs.widget(i).url()
             self.update_url_bar(qurl, self.tabs.widget(i))

    # --- User Profile / Settings Management ---

    def load_settings(self):
        """
        Implements the 'root'/'user login' function by loading a settings file.
        This provides a dynamic initial compile state based on user preference.
        """
        # Diagnostic check: Does the settings file exist?
        if os.path.exists(CONFIG["settings_file"]):
            try:
                with open(CONFIG["settings_file"], 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                # Error propagation: If file is corrupt, log it and return default.
                # A more robust version would notify the user.
                print(f"DIAGNOSTIC: Could not parse {CONFIG['settings_file']}. Using defaults.")
                return {} # Return empty dict to use defaults
        else:
            # First time run: create default settings file
            self.save_settings({"homepage": CONFIG["default_homepage"]})
            return {"homepage": CONFIG["default_homepage"]}

    def save_settings(self, settings_dict):
        """ Saves the current settings to the JSON file. """
        try:
            with open(CONFIG["settings_file"], 'w') as f:
                json.dump(settings_dict, f, indent=4)
        except IOError as e:
            # Error propagation: Comment/print the error if saving fails.
            print(f"DIAG-ERROR: Could not save settings to {CONFIG['settings_file']}. Error: {e}")

# --- Application Bootstrap ---
if __name__ == '__main__':
    # Create the application instance
    app = QApplication(sys.argv)
    app.setApplicationName("Koralai")

    # Create and show the main window
    window = KoralaiMainWindow()
    window.show()

    # Start the event loop
    sys.exit(app.exec())

