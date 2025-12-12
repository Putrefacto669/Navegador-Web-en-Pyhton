import sys
import json
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse
from PyQt5.QtCore import QUrl, Qt, QSize, QTimer, QSettings
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QLineEdit, QAction,
    QTabWidget, QStatusBar, QMessageBox, QPushButton, QMenu,
    QListWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QInputDialog, QListWidgetItem, QTextBrowser, QCheckBox,
    QComboBox, QSplitter, QFrame, QGroupBox
)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QTextCharFormat
from PyQt5.QtWebEngineWidgets import QWebEngineProfile, QWebEngineScript


class WebTab(QWebEngineView):
    def __init__(self, parent_browser, is_reader_mode=False):
        super().__init__()
        self.parent_browser = parent_browser
        self.is_reader_mode = is_reader_mode
        self.urlChanged.connect(self.on_url_changed)
        self.loadProgress.connect(self.on_load_progress)
        self.loadFinished.connect(self.on_load_finished)
        
        if is_reader_mode:
            self.setup_reader_mode()
    
    def setup_reader_mode(self):
        """Configura el modo lectura"""
        self.setZoomFactor(1.2)
        # Aplicar CSS para modo lectura
        css = """
        body {
            max-width: 800px;
            margin: 40px auto;
            font-family: 'Georgia', serif;
            font-size: 18px;
            line-height: 1.6;
            color: #333;
            padding: 20px;
        }
        h1, h2, h3 {
            font-family: 'Helvetica', sans-serif;
            color: #222;
        }
        img {
            max-width: 100%;
            height: auto;
        }
        """
        script = f"""
        document.addEventListener('DOMContentLoaded', function() {{
            var style = document.createElement('style');
            style.textContent = `{css}`;
            document.head.appendChild(style);
        }});
        """
        self.page().runJavaScript(script)
    
    def on_url_changed(self, url):
        current = self.parent_browser.tabs.currentWidget()
        if current == self:
            self.parent_browser.url_bar.setText(url.toString())
            self.parent_browser.add_to_history(url.toString())
    
    def on_load_progress(self, progress):
        if self == self.parent_browser.current_browser():
            self.parent_browser.statusBar().showMessage(f"Cargando... {progress}%")
    
    def on_load_finished(self, ok):
        if self == self.parent_browser.current_browser():
            if ok:
                self.parent_browser.statusBar().showMessage("Listo", 2000)
                # Si está en modo lectura y no es una página local, aplicar transformaciones
                if self.is_reader_mode and not self.url().toString().startswith("file://"):
                    self.apply_reader_mode_transform()
            else:
                self.parent_browser.statusBar().showMessage("Error al cargar la página", 3000)
    
    def apply_reader_mode_transform(self):
        """Extrae el contenido principal de la página para modo lectura"""
        script = """
        // Función para calcular la puntuación de un elemento
        function getReaderScore(element) {
            let score = 0;
            
            // Bonus por párrafos
            score += element.querySelectorAll('p').length * 3;
            
            // Bonus por texto largo
            const text = element.textContent;
            const words = text.split(/\\s+/).length;
            score += Math.min(words / 10, 100);
            
            // Penalizar elementos no deseados
            score -= element.querySelectorAll('script, style, nav, header, footer, aside').length * 10;
            score -= element.querySelectorAll('button, form, iframe, .ad, [class*="ad"], [id*="ad"]').length * 5;
            
            return score;
        }
        
        // Encontrar el elemento con mayor puntuación
        let bestElement = null;
        let bestScore = 0;
        
        const candidates = document.querySelectorAll('article, main, .post, .content, .article, [role="main"], div');
        candidates.forEach(element => {
            const score = getReaderScore(element);
            if (score > bestScore) {
                bestScore = score;
                bestElement = element;
            }
        });
        
        // Si encontramos un buen candidato, reemplazar el contenido del body
        if (bestElement && bestScore > 30) {
            document.body.innerHTML = bestElement.innerHTML;
            document.body.style.maxWidth = '800px';
            document.body.style.margin = '40px auto';
            document.body.style.padding = '20px';
            document.body.style.fontFamily = "'Georgia', serif";
            document.body.style.fontSize = '18px';
            document.body.style.lineHeight = '1.6';
            document.body.style.color = '#333';
        }
        
        // Remover elementos no deseados
        document.querySelectorAll('script, style, nav, header, footer, aside, button, form, iframe, .ad, [class*="ad"], [id*="ad"]').forEach(el => {
            el.remove();
        });
        """
        self.page().runJavaScript(script)


class BookmarkManager:
    """Gestor de marcadores con persistencia en JSON"""
    
    def __init__(self, filename="bookmarks.json"):
        self.filename = filename
        self.bookmarks = []
        self.load_bookmarks()
    
    def load_bookmarks(self):
        """Cargar marcadores desde archivo JSON"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.bookmarks = data.get('bookmarks', [])
            else:
                self.bookmarks = []
        except Exception as e:
            print(f"Error cargando marcadores: {e}")
            self.bookmarks = []
    
    def save_bookmarks(self):
        """Guardar marcadores en archivo JSON"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump({'bookmarks': self.bookmarks}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando marcadores: {e}")
    
    def add_bookmark(self, title, url, folder="General"):
        """Agregar un nuevo marcador"""
        bookmark = {
            'id': len(self.bookmarks) + 1,
            'title': title,
            'url': url,
            'folder': folder,
            'date_added': datetime.now().isoformat(),
            'tags': []
        }
        self.bookmarks.append(bookmark)
        self.save_bookmarks()
        return bookmark
    
    def remove_bookmark(self, bookmark_id):
        """Eliminar un marcador por ID"""
        self.bookmarks = [b for b in self.bookmarks if b['id'] != bookmark_id]
        self.save_bookmarks()
    
    def get_bookmarks_by_folder(self, folder=None):
        """Obtener marcadores por carpeta"""
        if folder:
            return [b for b in self.bookmarks if b['folder'] == folder]
        return self.bookmarks
    
    def get_folders(self):
        """Obtener lista de carpetas únicas"""
        folders = set(b['folder'] for b in self.bookmarks)
        return sorted(list(folders))


class HistoryManager:
    """Gestor de historial con persistencia opcional"""
    
    def __init__(self, persist_to_file=False, filename="history.json"):
        self.persist_to_file = persist_to_file
        self.filename = filename
        self.history = []
        self.max_entries = 1000  # Máximo de entradas en historial
        
        if persist_to_file:
            self.load_history()
    
    def load_history(self):
        """Cargar historial desde archivo"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history = data.get('history', [])
        except Exception as e:
            print(f"Error cargando historial: {e}")
            self.history = []
    
    def save_history(self):
        """Guardar historial en archivo"""
        if not self.persist_to_file:
            return
        
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump({'history': self.history[-self.max_entries:]}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando historial: {e}")
    
    def add_entry(self, url, title):
        """Agregar entrada al historial"""
        entry = {
            'id': len(self.history) + 1,
            'url': url,
            'title': title,
            'timestamp': datetime.now().isoformat(),
            'visit_count': 1
        }
        
        # Buscar si ya existe esta URL en el historial
        existing = None
        for i, item in enumerate(self.history):
            if item['url'] == url:
                existing = i
                break
        
        if existing is not None:
            # Actualizar entrada existente
            self.history[existing]['visit_count'] += 1
            self.history[existing]['timestamp'] = entry['timestamp']
            self.history[existing]['title'] = title
            # Mover al final (más reciente)
            item = self.history.pop(existing)
            self.history.append(item)
        else:
            # Agregar nueva entrada
            self.history.append(entry)
        
        # Limitar tamaño del historial
        if len(self.history) > self.max_entries:
            self.history = self.history[-self.max_entries:]
        
        self.save_history()
    
    def get_recent(self, limit=50):
        """Obtener entradas recientes"""
        return list(reversed(self.history[-limit:]))
    
    def search(self, query):
        """Buscar en el historial"""
        query = query.lower()
        results = []
        for entry in reversed(self.history):
            if (query in entry['title'].lower() or 
                query in entry['url'].lower()):
                results.append(entry)
        return results
    
    def clear_history(self, older_than_days=None):
        """Limpiar historial"""
        if older_than_days:
            cutoff = datetime.now() - timedelta(days=older_than_days)
            self.history = [
                h for h in self.history 
                if datetime.fromisoformat(h['timestamp']) > cutoff
            ]
        else:
            self.history.clear()
        self.save_history()


class ThemeManager:
    """Gestor de temas claro/oscuro"""
    
    THEMES = {
        "light": {
            "name": "Claro",
            "colors": {
                "primary": "#0066cc",
                "secondary": "#4da6ff",
                "background": "#f0f8ff",
                "surface": "#ffffff",
                "text": "#000000",
                "text_secondary": "#666666",
                "border": "#cce0ff",
                "hover": "#e6f2ff",
                "accent": "#ff6b6b"
            },
            "styles": {
                "main_window": """
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #c0e8ff, stop:0.5 #a0d4ff, stop:1 #80c0ff);
                """,
                "toolbar": """
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(245, 252, 255, 230), stop:1 rgba(225, 242, 255, 210));
                    border-bottom: 2px solid #80d0ff;
                """,
                "url_bar": """
                    background: rgba(255, 255, 255, 240);
                    border: 2px solid #80d0ff;
                    color: #000000;
                """,
                "button": """
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(220, 245, 255, 200), stop:1 rgba(200, 235, 255, 180));
                    border: 2px solid #a0d8ff;
                    color: #005080;
                """
            }
        },
        "dark": {
            "name": "Oscuro",
            "colors": {
                "primary": "#3399ff",
                "secondary": "#66b3ff",
                "background": "#0a1929",
                "surface": "#1a2b3c",
                "text": "#e6f2ff",
                "text_secondary": "#a3c6e0",
                "border": "#2a3b4c",
                "hover": "#2a3b4c",
                "accent": "#ff6b6b"
            },
            "styles": {
                "main_window": """
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #0a1929, stop:0.5 #1a2b3c, stop:1 #2a3b4c);
                """,
                "toolbar": """
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(26, 43, 60, 230), stop:1 rgba(20, 35, 50, 210));
                    border-bottom: 2px solid #3399ff;
                """,
                "url_bar": """
                    background: rgba(42, 59, 76, 240);
                    border: 2px solid #3399ff;
                    color: #e6f2ff;
                """,
                "button": """
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(51, 153, 255, 100), stop:1 rgba(42, 59, 76, 180));
                    border: 2px solid #3399ff;
                    color: #e6f2ff;
                """
            }
        },
        "aero": {
            "name": "Frutiger Aero",
            "colors": {
                "primary": "#40b0ff",
                "secondary": "#80d0ff",
                "background": "#c0e8ff",
                "surface": "#ffffff",
                "text": "#005080",
                "text_secondary": "#4070a0",
                "border": "#80c0ff",
                "hover": "#e6f2ff",
                "accent": "#ff8c42"
            },
            "styles": {
                "main_window": """
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #c0e8ff, stop:0.5 #a0d4ff, stop:1 #80c0ff);
                """,
                "toolbar": """
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(245, 252, 255, 230), stop:1 rgba(225, 242, 255, 210));
                    border-bottom: 2px solid #80d0ff;
                """,
                "url_bar": """
                    background: rgba(255, 255, 255, 240);
                    border: 2px solid #80d0ff;
                    color: #005080;
                """,
                "button": """
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(220, 245, 255, 200), stop:1 rgba(200, 235, 255, 180));
                    border: 2px solid #a0d8ff;
                    color: #005080;
                """
            }
        }
    }
    
    def __init__(self):
        self.current_theme = "aero"
        self.settings = QSettings("PyBrowser", "Themes")
        self.load_theme()
    
    def load_theme(self):
        """Cargar tema guardado"""
        saved_theme = self.settings.value("current_theme", "aero")
        if saved_theme in self.THEMES:
            self.current_theme = saved_theme
    
    def save_theme(self):
        """Guardar tema actual"""
        self.settings.setValue("current_theme", self.current_theme)
    
    def get_theme(self, theme_name=None):
        """Obtener configuración de tema"""
        if theme_name is None:
            theme_name = self.current_theme
        return self.THEMES.get(theme_name, self.THEMES["aero"])
    
    def set_theme(self, theme_name):
        """Cambiar tema"""
        if theme_name in self.THEMES:
            self.current_theme = theme_name
            self.save_theme()
            return True
        return False
    
    def get_available_themes(self):
        """Obtener lista de temas disponibles"""
        return list(self.THEMES.keys())
    
    def apply_theme_to_app(self, app):
        """Aplicar tema a la aplicación completa"""
        theme = self.get_theme()
        colors = theme["colors"]
        
        # Configurar paleta de colores
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(colors["background"]))
        palette.setColor(QPalette.WindowText, QColor(colors["text"]))
        palette.setColor(QPalette.Base, QColor(colors["surface"]))
        palette.setColor(QPalette.AlternateBase, QColor(colors["hover"]))
        palette.setColor(QPalette.ToolTipBase, QColor(colors["surface"]))
        palette.setColor(QPalette.ToolTipText, QColor(colors["text"]))
        palette.setColor(QPalette.Text, QColor(colors["text"]))
        palette.setColor(QPalette.Button, QColor(colors["surface"]))
        palette.setColor(QPalette.ButtonText, QColor(colors["text"]))
        palette.setColor(QPalette.BrightText, QColor(colors["accent"]))
        palette.setColor(QPalette.Link, QColor(colors["primary"]))
        palette.setColor(QPalette.Highlight, QColor(colors["primary"]))
        palette.setColor(QPalette.HighlightedText, QColor(colors["text"]))
        
        app.setPalette(palette)


class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Inicializar gestores
        self.bookmark_manager = BookmarkManager("bookmarks.json")
        self.history_manager = HistoryManager(persist_to_file=True, filename="history.json")
        self.theme_manager = ThemeManager()
        
        # Variables de estado
        self.reader_mode_active = False
        
        self.initUI()
        self.apply_theme()
        self.setup_shortcuts()
    
    def initUI(self):
        self.setWindowTitle("PyBrowser • Navegador Inteligente")
        self.setGeometry(100, 100, 1400, 900)

        # Barra de URL
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.url_bar.setFixedHeight(36)
        self.url_bar.setPlaceholderText("Escribe una URL o término de búsqueda...")

        # Barra de herramientas principal
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(30, 30))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Botones de navegación
        actions = [
            ("＋", "Nueva pestaña (Ctrl+T)", lambda: self.new_tab()),
            ("◀", "Atrás (Alt+Left)", lambda: self.current_browser().back()),
            ("▶", "Adelante (Alt+Right)", lambda: self.current_browser().forward()),
            ("↻", "Recargar (F5)", lambda: self.current_browser().reload()),
            ("🏠", "Página de inicio", lambda: self.current_browser().setUrl(QUrl("https://www.google.com"))),
        ]
        
        for text, tip, handler in actions:
            action = QAction(text, self)
            action.setToolTip(tip)
            action.triggered.connect(handler)
            toolbar.addAction(action)

        toolbar.addWidget(self.url_bar)

        # Botón de búsqueda
        search_action = QAction("🔍", self)
        search_action.triggered.connect(self.navigate_to_url)
        toolbar.addAction(search_action)

        # Selector de temas
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["🌗 Tema: Frutiger Aero", "🌗 Tema: Claro", "🌗 Tema: Oscuro"])
        self.theme_combo.currentIndexChanged.connect(self.change_theme)
        self.theme_combo.setFixedWidth(180)
        toolbar.addWidget(self.theme_combo)

        # Botón modo lectura
        self.reader_mode_action = QAction("📖", self)
        self.reader_mode_action.setToolTip("Modo lectura (Ctrl+R)")
        self.reader_mode_action.triggered.connect(self.toggle_reader_mode)
        toolbar.addAction(self.reader_mode_action)

        # Botón para agregar marcador
        add_bookmark_action = QAction("☆", self)
        add_bookmark_action.setToolTip("Agregar a marcadores (Ctrl+D)")
        add_bookmark_action.triggered.connect(self.add_current_to_bookmarks)
        toolbar.addAction(add_bookmark_action)

        # Botón para ver marcadores
        bookmark_action = QAction("⭐", self)
        bookmark_action.setToolTip("Ver marcadores (Ctrl+B)")
        bookmark_action.triggered.connect(self.show_bookmarks)
        toolbar.addAction(bookmark_action)

        # Botón de historial
        history_action = QAction("📜", self)
        history_action.setToolTip("Historial (Ctrl+H)")
        history_action.triggered.connect(self.show_history)
        toolbar.addAction(history_action)

        # Botón de configuración
        settings_action = QAction("⚙️", self)
        settings_action.setToolTip("Configuración")
        settings_action.triggered.connect(self.show_settings)
        toolbar.addAction(settings_action)

        # Barra de pestañas
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabBar().setExpanding(True)
        self.setCentralWidget(self.tabs)

        # Conectar señales
        self.tabs.tabBarDoubleClicked.connect(self.tab_doubleclick)
        self.tabs.currentChanged.connect(self.current_tab_changed)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        # Barra de estado
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Etiqueta de información
        self.info_label = QLabel()
        self.status_bar.addWidget(self.info_label)
        
        # Temporizador para actualizar hora
        self.time_label = QLabel()
        self.status_bar.addPermanentWidget(self.time_label)
        self.update_time()
        QTimer.singleShot(1000, self.update_time_continuously)

        # Primera pestaña
        self.new_tab(QUrl("https://www.google.com"))

    def apply_theme(self):
        """Aplicar el tema actual a la interfaz"""
        theme = self.theme_manager.get_theme()
        colors = theme["colors"]
        styles = theme["styles"]
        
        style_sheet = f"""
            QMainWindow {{
                {styles['main_window']}
            }}
            QToolBar {{
                {styles['toolbar']}
                padding: 8px;
                spacing: 10px;
            }}
            QLineEdit {{
                {styles['url_bar']}
                border-radius: 18px;
                padding: 6px 20px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                selection-background-color: {colors['primary']};
            }}
            QLineEdit:focus {{
                border: 2px solid {colors['primary']};
                background: {colors['surface']};
            }}
            QToolButton, QPushButton {{
                {styles['button']}
                border-radius: 15px;
                padding: 8px 14px;
                font-family: 'Segoe UI';
                font-size: 18px;
                min-width: 40px;
            }}
            QToolButton:hover, QPushButton:hover {{
                background: {colors['hover']};
                border: 2px solid {colors['primary']};
            }}
            QTabBar::tab {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {colors['hover']}dd, stop:1 {colors['surface']}cc);
                border: 1px solid {colors['border']};
                padding: 10px 25px;
                margin: 3px 1px;
                border-radius: 10px 10px 0 0;
                color: {colors['text']};
                font-family: 'Segoe UI';
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {colors['surface']}, stop:1 {colors['hover']});
                border: 2px solid {colors['primary']};
                border-bottom: 2px solid {colors['surface']};
                font-weight: bold;
                margin-bottom: -1px;
            }}
            QTabBar::tab:hover:!selected {{
                background: {colors['hover']};
            }}
            QTabWidget::pane {{
                border: 2px solid {colors['primary']};
                border-top: none;
                background: {colors['surface']};
                top: -1px;
            }}
            QStatusBar {{
                background: {colors['hover']};
                color: {colors['text']};
                font-family: 'Segoe UI';
                border-top: 1px solid {colors['border']};
            }}
            QComboBox {{
                background: {colors['surface']};
                border: 2px solid {colors['border']};
                border-radius: 15px;
                padding: 6px;
                color: {colors['text']};
                font-family: 'Segoe UI';
                selection-background-color: {colors['primary']};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background: {colors['surface']};
                border: 2px solid {colors['border']};
                color: {colors['text']};
                selection-background-color: {colors['primary']};
            }}
        """
        
        self.setStyleSheet(style_sheet)
        
        # Actualizar combo de temas
        theme_names = {
            "aero": "🌗 Tema: Frutiger Aero",
            "light": "🌗 Tema: Claro", 
            "dark": "🌗 Tema: Oscuro"
        }
        self.theme_combo.setCurrentText(theme_names.get(self.theme_manager.current_theme, "🌗 Tema: Frutiger Aero"))

    def change_theme(self, index):
        """Cambiar el tema según la selección"""
        theme_map = {
            0: "aero",
            1: "light",
            2: "dark"
        }
        
        theme_name = theme_map.get(index, "aero")
        if self.theme_manager.set_theme(theme_name):
            self.apply_theme()
            self.theme_manager.apply_theme_to_app(QApplication.instance())
            
            # Notificar al usuario
            theme_info = self.theme_manager.get_theme(theme_name)
            self.show_notification(f"Tema cambiado a: {theme_info['name']}", 2000)

    def setup_shortcuts(self):
        from PyQt5.QtGui import QKeySequence
        from PyQt5.QtWidgets import QShortcut
        
        shortcuts = [
            ("Ctrl+T", lambda: self.new_tab()),
            ("Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex())),
            ("Ctrl+D", self.add_current_to_bookmarks),
            ("Ctrl+B", self.show_bookmarks),
            ("Ctrl+H", self.show_history),
            ("F5", lambda: self.current_browser().reload()),
            ("Ctrl+F", self.find_on_page),
            ("Ctrl+L", lambda: self.url_bar.setFocus()),
            ("Ctrl+R", self.toggle_reader_mode),
            ("Ctrl+Shift+R", self.reload_ignoring_cache),
            ("Ctrl+Plus", lambda: self.current_browser().setZoomFactor(
                min(self.current_browser().zoomFactor() + 0.1, 3.0)
            )),
            ("Ctrl+Minus", lambda: self.current_browser().setZoomFactor(
                max(self.current_browser().zoomFactor() - 0.1, 0.5)
            )),
            ("Ctrl+0", lambda: self.current_browser().setZoomFactor(1.0)),
        ]
        
        for key, handler in shortcuts:
            QShortcut(QKeySequence(key), self).activated.connect(handler)

    def new_tab(self, url=None, reader_mode=False):
        if url is None:
            url = QUrl("https://www.google.com")
        elif not isinstance(url, QUrl):
            url = QUrl(url)
        
        browser = WebTab(self, is_reader_mode=reader_mode)
        browser.setUrl(url)
        
        title = "📖 Modo lectura" if reader_mode else "Nueva pestaña"
        i = self.tabs.addTab(browser, title)
        self.tabs.setCurrentIndex(i)
        
        # Actualizar título cuando se cargue la página
        browser.loadFinished.connect(
            lambda ok, b=browser, i=i: self.update_tab_title(b, i)
        )
        
        return browser

    def update_tab_title(self, browser, index):
        title = browser.title() or "Sin título"
        if len(title) > 25:
            title = title[:25] + "..."
        
        prefix = "📖 " if browser.is_reader_mode else ""
        self.tabs.setTabText(index, prefix + title)

    def tab_doubleclick(self, i):
        if i == -1:
            self.new_tab()

    def current_tab_changed(self, i):
        if self.tabs.count() == 0:
            return
        
        if i >= 0:
            browser = self.tabs.widget(i)
            qurl = browser.url()
            self.url_bar.setText(qurl.toString())
            
            # Actualizar estado del botón de modo lectura
            self.reader_mode_active = browser.is_reader_mode
            self.reader_mode_action.setText("📖" if browser.is_reader_mode else "📄")
            self.reader_mode_action.setToolTip(
                "Salir del modo lectura (Ctrl+R)" if browser.is_reader_mode 
                else "Activar modo lectura (Ctrl+R)"
            )
            
            title = browser.title() or "PyBrowser"
            self.setWindowTitle(f"{title} • PyBrowser")

    def current_browser(self):
        return self.tabs.currentWidget()

    def close_tab(self, i):
        if self.tabs.count() > 1:
            widget = self.tabs.widget(i)
            if widget:
                widget.deleteLater()
            self.tabs.removeTab(i)
        else:
            self.close()

    def navigate_to_url(self):
        text = self.url_bar.text().strip()
        if not text:
            return
        
        # Verificar si es una URL válida
        if text.startswith(("http://", "https://", "file://")):
            url = text
        elif "." in text and " " not in text and not text.startswith("?"):
            url = "https://" + text
        else:
            from urllib.parse import quote_plus
            query = quote_plus(text)
            url = f"https://www.google.com/search?q={query}"
        
        self.current_browser().setUrl(QUrl(url))

    def add_current_to_bookmarks(self):
        current = self.current_browser()
        title = current.title() or "Página sin título"
        url = current.url().toString()
        
        if url and url != "about:blank":
            # Diálogo para agregar marcador
            dialog = QDialog(self)
            dialog.setWindowTitle("⭐ Agregar a marcadores")
            dialog.setFixedSize(400, 300)
            dialog.setStyleSheet(f"""
                QDialog {{
                    background: {self.theme_manager.get_theme()['colors']['surface']};
                    border: 2px solid {self.theme_manager.get_theme()['colors']['primary']};
                    border-radius: 15px;
                }}
                QLabel, QLineEdit, QComboBox {{
                    color: {self.theme_manager.get_theme()['colors']['text']};
                    font-family: 'Segoe UI';
                }}
            """)
            
            layout = QVBoxLayout()
            
            # Título
            title_label = QLabel("Título:")
            layout.addWidget(title_label)
            
            title_input = QLineEdit(title)
            layout.addWidget(title_input)
            
            # URL (solo lectura)
            url_label = QLabel("URL:")
            layout.addWidget(url_label)
            
            url_input = QLineEdit(url)
            url_input.setReadOnly(True)
            layout.addWidget(url_input)
            
            # Carpeta
            folder_label = QLabel("Carpeta:")
            layout.addWidget(folder_label)
            
            folder_combo = QComboBox()
            folders = self.bookmark_manager.get_folders()
            folder_combo.addItems(folders)
            folder_combo.addItem("Nueva carpeta...")
            folder_combo.setEditable(True)
            layout.addWidget(folder_combo)
            
            # Botones
            button_layout = QHBoxLayout()
            
            save_btn = QPushButton("💾 Guardar")
            def save_bookmark():
                folder = folder_combo.currentText()
                if folder == "Nueva carpeta...":
                    folder = "General"
                
                self.bookmark_manager.add_bookmark(
                    title_input.text() or title,
                    url,
                    folder
                )
                dialog.accept()
                self.show_notification("✓ Marcador guardado", 2000)
            
            save_btn.clicked.connect(save_bookmark)
            button_layout.addWidget(save_btn)
            
            cancel_btn = QPushButton("❌ Cancelar")
            cancel_btn.clicked.connect(dialog.reject)
            button_layout.addWidget(cancel_btn)
            
            layout.addLayout(button_layout)
            dialog.setLayout(layout)
            dialog.exec_()

    def show_bookmarks(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("⭐ Mis Marcadores")
        dialog.setFixedSize(600, 500)
        
        theme = self.theme_manager.get_theme()
        dialog.setStyleSheet(f"""
            QDialog {{
                background: {theme['colors']['surface']};
                border: 2px solid {theme['colors']['primary']};
                border-radius: 15px;
            }}
            QListWidget {{
                background: {theme['colors']['background']};
                border: 2px solid {theme['colors']['border']};
                border-radius: 10px;
                color: {theme['colors']['text']};
                font-family: 'Segoe UI';
                font-size: 13px;
            }}
            QLabel {{
                color: {theme['colors']['text']};
                font-family: 'Segoe UI';
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        
        layout = QVBoxLayout()
        
        # Título
        title_label = QLabel("🌟 Mis Marcadores")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Lista de marcadores
        list_widget = QListWidget()
        bookmarks = self.bookmark_manager.get_bookmarks_by_folder()
        
        for bookmark in bookmarks:
            item = QListWidgetItem(f"⭐ {bookmark['title']}")
            item.setData(Qt.UserRole, bookmark['url'])
            item.setToolTip(f"{bookmark['url']}\nCarpeta: {bookmark['folder']}")
            list_widget.addItem(item)
        
        list_widget.itemDoubleClicked.connect(
            lambda item: self.new_tab(QUrl(item.data(Qt.UserRole)))
        )
        layout.addWidget(list_widget)
        
        # Botones
        button_layout = QHBoxLayout()
        
        open_btn = QPushButton("🌐 Abrir")
        open_btn.clicked.connect(
            lambda: list_widget.currentItem() and self.new_tab(
                QUrl(list_widget.currentItem().data(Qt.UserRole))
            )
        )
        button_layout.addWidget(open_btn)
        
        delete_btn = QPushButton("🗑️ Eliminar")
        delete_btn.clicked.connect(lambda: self.delete_bookmark_dialog(list_widget))
        button_layout.addWidget(delete_btn)
        
        organize_btn = QPushButton("📁 Organizar")
        organize_btn.clicked.connect(self.organize_bookmarks)
        button_layout.addWidget(organize_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("✕ Cerrar")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec_()

    def delete_bookmark_dialog(self, list_widget):
        item = list_widget.currentItem()
        if item:
            reply = QMessageBox.question(
                self, "Confirmar",
                "¿Eliminar este marcador?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                # Aquí necesitaríamos el ID del marcador para eliminarlo
                # Por simplicidad, solo lo removemos de la lista
                row = list_widget.row(item)
                list_widget.takeItem(row)

    def organize_bookmarks(self):
        QMessageBox.information(
            self, 
            "Organizar marcadores",
            "Esta funcionalidad está en desarrollo.\n\n"
            "Próximamente podrás:\n"
            "• Crear y gestionar carpetas\n"
            "• Arrastrar y soltar marcadores\n"
            "• Importar/exportar marcadores"
        )

    def add_to_history(self, url):
        """Agregar página al historial"""
        current = self.current_browser()
        title = current.title() or "Sin título"
        self.history_manager.add_entry(url, title)
        self.info_label.setText(f"📚 Historial actualizado: {title[:30]}...")

    def show_history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("📜 Historial de Navegación")
        dialog.setFixedSize(700, 500)
        
        theme = self.theme_manager.get_theme()
        dialog.setStyleSheet(f"""
            QDialog {{
                background: {theme['colors']['surface']};
                border: 2px solid {theme['colors']['primary']};
                border-radius: 15px;
            }}
            QListWidget, QLineEdit {{
                background: {theme['colors']['background']};
                border: 2px solid {theme['colors']['border']};
                border-radius: 10px;
                color: {theme['colors']['text']};
                font-family: 'Segoe UI';
            }}
            QLabel {{
                color: {theme['colors']['text']};
                font-family: 'Segoe UI';
            }}
        """)
        
        layout = QVBoxLayout()
        
        # Barra de búsqueda
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Buscar en historial:")
        search_layout.addWidget(search_label)
        
        search_input = QLineEdit()
        search_input.setPlaceholderText("Escribe para buscar...")
        search_layout.addWidget(search_input)
        layout.addLayout(search_layout)
        
        # Lista de historial
        list_widget = QListWidget()
        history_entries = self.history_manager.get_recent(100)
        
        for entry in history_entries:
            try:
                timestamp = datetime.fromisoformat(entry['timestamp']).strftime("%d/%m %H:%M")
                item_text = f"{timestamp} - {entry['title']}"
                if len(item_text) > 80:
                    item_text = item_text[:80] + "..."
                
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, entry['url'])
                item.setToolTip(f"{entry['url']}\nVisitas: {entry['visit_count']}")
                list_widget.addItem(item)
            except:
                continue
        
        def search_history(text):
            list_widget.clear()
            if text.strip():
                results = self.history_manager.search(text)
                for entry in results[:50]:  # Limitar resultados
                    try:
                        timestamp = datetime.fromisoformat(entry['timestamp']).strftime("%d/%m %H:%M")
                        item_text = f"{timestamp} - {entry['title']}"
                        item = QListWidgetItem(item_text)
                        item.setData(Qt.UserRole, entry['url'])
                        list_widget.addItem(item)
                    except:
                        continue
            else:
                # Mostrar historial reciente
                history_entries = self.history_manager.get_recent(100)
                for entry in history_entries:
                    try:
                        timestamp = datetime.fromisoformat(entry['timestamp']).strftime("%d/%m %H:%M")
                        item_text = f"{timestamp} - {entry['title']}"
                        item = QListWidgetItem(item_text)
                        item.setData(Qt.UserRole, entry['url'])
                        list_widget.addItem(item)
                    except:
                        continue
        
        search_input.textChanged.connect(search_history)
        list_widget.itemDoubleClicked.connect(
            lambda item: self.new_tab(QUrl(item.data(Qt.UserRole)))
        )
        layout.addWidget(list_widget)
        
        # Estadísticas
        stats_label = QLabel(f"📊 Total en historial: {len(self.history_manager.history)} páginas")
        layout.addWidget(stats_label)
        
        # Botones
        button_layout = QHBoxLayout()
        
        clear_btn = QPushButton("🗑️ Limpiar historial")
        def clear_history():
            reply = QMessageBox.question(
                dialog, "Confirmar",
                "¿Borrar todo el historial?\nEsta acción no se puede deshacer.",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.history_manager.clear_history()
                list_widget.clear()
                stats_label.setText("📊 Historial limpiado")
                self.show_notification("✓ Historial borrado", 2000)
        
        clear_btn.clicked.connect(clear_history)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("✕ Cerrar")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec_()

    def toggle_reader_mode(self):
        """Activar/desactivar modo lectura en la pestaña actual"""
        current = self.current_browser()
        if current:
            if current.is_reader_mode:
                # Salir del modo lectura - crear nueva pestaña normal con la misma URL
                url = current.url()
                self.close_tab(self.tabs.currentIndex())
                self.new_tab(url)
                self.show_notification("Modo lectura desactivado", 1500)
            else:
                # Entrar en modo lectura - crear nueva pestaña en modo lectura
                url = current.url()
                self.close_tab(self.tabs.currentIndex())
                self.new_tab(url, reader_mode=True)
                self.show_notification("Modo lectura activado", 1500)

    def reload_ignoring_cache(self):
        """Recargar página ignorando caché"""
        current = self.current_browser()
        if current:
            current.page().triggerAction(QWebEnginePage.ReloadAndBypassCache)

    def find_on_page(self):
        """Buscar texto en la página actual"""
        text, ok = QInputDialog.getText(self, "Buscar en página", "Texto a buscar:")
        if ok and text:
            current = self.current_browser()
            if current:
                # Resaltar texto encontrado
                script = f"""
                if (window.findText) {{
                    window.findText('{text}');
                }} else {{
                    // Fallback para navegadores más antiguos
                    const regex = new RegExp('({text})', 'gi');
                    document.body.innerHTML = document.body.innerHTML.replace(regex, 
                        '<mark style="background-color: yellow;">$1</mark>');
                }}
                """
                current.page().runJavaScript(script)

    def show_settings(self):
        """Mostrar diálogo de configuración"""
        dialog = QDialog(self)
        dialog.setWindowTitle("⚙️ Configuración")
        dialog.setFixedSize(500, 600)
        
        theme = self.theme_manager.get_theme()
        dialog.setStyleSheet(f"""
            QDialog {{
                background: {theme['colors']['surface']};
                border: 2px solid {theme['colors']['primary']};
                border-radius: 15px;
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {theme['colors']['border']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
            QLabel, QCheckBox, QComboBox {{
                color: {theme['colors']['text']};
                font-family: 'Segoe UI';
            }}
        """)
        
        layout = QVBoxLayout()
        
        # Grupo: Historial
        history_group = QGroupBox("📜 Historial")
        history_layout = QVBoxLayout()
        
        self.history_enabled_check = QCheckBox("Guardar historial de navegación")
        self.history_enabled_check.setChecked(True)
        history_layout.addWidget(self.history_enabled_check)
        
        self.clear_on_exit_check = QCheckBox("Limpiar historial al salir")
        history_layout.addWidget(self.clear_on_exit_check)
        
        clear_now_btn = QPushButton("Limpiar historial ahora")
        clear_now_btn.clicked.connect(
            lambda: self.history_manager.clear_history() and 
            self.show_notification("Historial limpiado", 2000)
        )
        history_layout.addWidget(clear_now_btn)
        
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
        # Grupo: Privacidad
        privacy_group = QGroupBox("🔒 Privacidad")
        privacy_layout = QVBoxLayout()
        
        self.do_not_track_check = QCheckBox("Enviar señal 'No Rastrear'")
        privacy_layout.addWidget(self.do_not_track_check)
        
        self.block_ads_check = QCheckBox("Bloquear anuncios (experimental)")
        privacy_layout.addWidget(self.block_ads_check)
        
        self.clear_cookies_btn = QPushButton("Limpiar cookies y caché")
        privacy_layout.addWidget(self.clear_cookies_btn)
        
        privacy_group.setLayout(privacy_layout)
        layout.addWidget(privacy_group)
        
        # Grupo: Apariencia
        appearance_group = QGroupBox("🎨 Apariencia")
        appearance_layout = QVBoxLayout()
        
        font_label = QLabel("Tamaño de fuente:")
        appearance_layout.addWidget(font_label)
        
        font_combo = QComboBox()
        font_combo.addItems(["Pequeño", "Mediano", "Grande"])
        font_combo.setCurrentIndex(1)
        appearance_layout.addWidget(font_combo)
        
        zoom_label = QLabel("Zoom por defecto:")
        appearance_layout.addWidget(zoom_label)
        
        zoom_combo = QComboBox()
        zoom_combo.addItems(["100%", "110%", "125%", "150%"])
        zoom_combo.setCurrentIndex(0)
        appearance_layout.addWidget(zoom_combo)
        
        appearance_group.setLayout(appearance_layout)
        layout.addWidget(appearance_group)
        
        # Grupo: Modo lectura
        reader_group = QGroupBox("📖 Modo lectura")
        reader_layout = QVBoxLayout()
        
        self.auto_reader_check = QCheckBox("Sugerir modo lectura automáticamente")
        reader_layout.addWidget(self.auto_reader_check)
        
        font_family_label = QLabel("Fuente en modo lectura:")
        reader_layout.addWidget(font_family_label)
        
        reader_font_combo = QComboBox()
        reader_font_combo.addItems(["Georgia", "Times New Roman", "Arial", "Verdana"])
        reader_font_combo.setCurrentIndex(0)
        reader_layout.addWidget(reader_font_combo)
        
        reader_group.setLayout(reader_layout)
        layout.addWidget(reader_group)
        
        # Botones
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Guardar")
        save_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ Cancelar")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        layout.addStretch()
        
        dialog.setLayout(layout)
        dialog.exec_()

    def show_notification(self, message, duration=3000):
        """Mostrar notificación en la barra de estado"""
        self.status_bar.showMessage(message, duration)

    def update_time(self):
        """Actualizar hora en la barra de estado"""
        time_str = datetime.now().strftime("%H:%M:%S")
        self.time_label.setText(f"🕒 {time_str}")

    def update_time_continuously(self):
        """Actualizar hora continuamente"""
        self.update_time()
        QTimer.singleShot(1000, self.update_time_continuously)

    def closeEvent(self, event):
        """Evento al cerrar la ventana"""
        if hasattr(self, 'clear_on_exit_check') and self.clear_on_exit_check.isChecked():
            self.history_manager.clear_history()
        
        # Guardar configuración
        settings = QSettings("PyBrowser", "Settings")
        settings.setValue("window_geometry", self.saveGeometry())
        settings.setValue("window_state", self.saveState())
        
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("PyBrowser • Navegador Inteligente")
    app.setStyle("Fusion")
    
    # Establecer fuente global
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = Browser()
    
    # Cargar configuración guardada
    settings = QSettings("PyBrowser", "Settings")
    window.restoreGeometry(settings.value("window_geometry", window.saveGeometry()))
    window.restoreState(settings.value("window_state", window.saveState()))
    
    window.show()
    sys.exit(app.exec_())
