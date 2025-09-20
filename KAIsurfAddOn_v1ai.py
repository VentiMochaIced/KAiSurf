# AgenticAI Add-on for Koralai Browser
# entry_point for the addon specified in manifest.json

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel

class AgenticAI_Addon:
    def __init__(self, bridge):
        """
        The constructor is called by the browser, passing in the KoralaiBridge.
        """
        self.bridge = bridge
        self.main_window = None
        self.ui_initialized = False

    def setup_ui(self, main_window):
        """
        Called by the browser to allow the addon to create its UI elements.
        """
        self.main_window = main_window

        # Create a button in the browser's addon toolbar
        self.toggle_button = QPushButton("AI")
        self.toggle_button.setToolTip("Toggle Agentic AI Panel")
        self.toggle_button.setCheckable(True)
        self.toggle_button.toggled.connect(self.toggle_panel)
        main_window.addon_toolbar.addWidget(self.toggle_button)

    def initialize_panel_ui(self):
        """
        Lazily creates the panel UI the first time it's shown.
        """
        # --- Create Panel Widgets ---
        title = QLabel("Agentic AI Assistant")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #EEE; margin-bottom: 10px;")
        
        self.text_area = QTextEdit()
        self.text_area.setPlaceholderText("Page content will appear here...")
        self.text_area.setStyleSheet("background-color: #333; color: #DDD; font-family: monospace;")

        get_text_button = QPushButton("Get Page Text")
        get_text_button.clicked.connect(self.on_get_text_clicked)
        
        fill_form_button = QPushButton("Fill Search Form")
        fill_form_button.clicked.connect(self.on_fill_form_clicked)

        # Add widgets to the addon panel in the main window
        self.main_window.addon_panel_layout.addWidget(title)
        self.main_window.addon_panel_layout.addWidget(self.text_area)
        self.main_window.addon_panel_layout.addWidget(get_text_button)
        self.main_window.addon_panel_layout.addWidget(fill_form_button)
        
        self.ui_initialized = True

    def toggle_panel(self, checked):
        """
        Shows or hides the addon's side panel.
        """
        if checked:
            if not self.ui_initialized:
                self.initialize_panel_ui() # Create UI on first open
            self.main_window.addon_panel.show()
            # Adjust splitter to give addon panel 30% of the space
            total_width = self.main_window.splitter.width()
            self.main_window.splitter.setSizes([int(total_width * 0.7), int(total_width * 0.3)])

        else:
            self.main_window.addon_panel.hide()

    # --- Bridge Actions ---
    
    def on_get_text_clicked(self):
        """
        Action for the 'Get Page Text' button. Uses the bridge.
        """
        self.text_area.setText("Loading page content...")
        # The bridge's get_page_text is async, so we pass a callback
        self.bridge.get_page_text(self.update_text_area)

    def update_text_area(self, text):
        """
        Callback function that receives the text from the bridge.
        """
        self.text_area.setText(text)

    def on_fill_form_clicked(self):
        """
        Action for the 'Fill Search Form' button. This is a demo to fill a
        common search input field. It will work on pages like Google or DuckDuckGo.
        """
        # This uses common selectors for search bars as an example
        selectors_to_try = ['input[name="q"]', 'textarea[name="q"]', '#search_form_input']
        for selector in selectors_to_try:
            self.bridge.fill_form_field(selector, "Agentic AI was here!")

# This function is the entry point that the browser will call
def initialize(bridge):
    """
    The browser calls this function when loading the addon.
    It must return an instance of the addon's main class.
    """
    return AgenticAI_Addon(bridge)
