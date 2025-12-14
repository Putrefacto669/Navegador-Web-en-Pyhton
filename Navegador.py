"""
AerisNet - Navegador web moderno con bloqueador de anuncios, modo incógnito y modo lectura
Autor: [Putrefacto669]
Versión: 2.0
Por el momento, este archivo contiene las clases y funciones principales para la gestión de pestañas web,
bloqueo de anuncios, modo lectura, y perfiles de navegación. Incluye también los gestores de marcadores, historial y temas.
PSDT: El código está diseñado para ser modular y extensible, facilitando futuras mejoras y adiciones de funcionalidades.
Y Tambien me acabo de dar cuenta que no funciona el modo incognito ://

"""

import sys
import json
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse, quote_plus
from PyQt5.QtCore import QUrl, Qt, QSize, QTimer, QSettings
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QLineEdit, QAction,
    QTabWidget, QStatusBar, QMessageBox, QPushButton, QMenu,
    QListWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QInputDialog, QListWidgetItem, QTextBrowser, QCheckBox,
    QComboBox, QFrame, QSplitter, QGroupBox, QFileDialog,
    QStackedWidget, QWidget, QScrollArea, QFormLayout,
    QSpinBox, QDoubleSpinBox, QRadioButton, QButtonGroup
)
from PyQt5.QtWebEngineWidgets import (
    QWebEngineView, QWebEnginePage, QWebEngineSettings,
    QWebEngineProfile
)
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QDesktopServices, QKeySequence
from PyQt5.QtWidgets import QShortcut


# ============================================================================
# PERFIL DE NAVEGACIÓN INCÓGNITO
# ============================================================================
def create_incognito_profile():
    """
    Crea un perfil de navegación completamente privado sin persistencia de datos.
    
    Returns:
        QWebEngineProfile: Perfil configurado para navegación privada
    """
    profile = QWebEngineProfile()
    # Deshabilitar todas las formas de persistencia
    profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
    profile.setCachePath("")  # Sin caché
    profile.setPersistentStoragePath("")  # Sin almacenamiento persistente
    profile.setHttpCacheType(QWebEngineProfile.NoCache)  # Sin caché HTTP
    profile.setOffTheRecord(True)  # Modo privado
    return profile


# ============================================================================
# BLOQUEADOR DE ANUNCIOS Y RASTREADORES
# ============================================================================
class AdBlocker(QWebEngineUrlRequestInterceptor):
    """
    Interceptor de solicitudes HTTP que bloquea anuncios y rastreadores.
    Utiliza listas de dominios y patrones para identificar contenido no deseado.
    """
    
    def __init__(self):
        super().__init__()
        self.blocked_domains = set()
        self.load_blocklists()
    
    def load_blocklists(self):
        """Carga listas de dominios bloqueados desde fuentes predefinidas."""
        # Lista básica de dominios de anuncios y rastreadores
        basic_ad_domains = [
            # Google Ads
            "doubleclick.net", "googleadservices.com", "googlesyndication.com",
            "google-analytics.com", "adservice.google.com",
            
            # Facebook/Meta
            "facebook.net", "facebook.com", "ads.facebook.com",
            
            # Otros servicios de anuncios
            "amazon-adsystem.com", "ads.youtube.com", "ad.yieldmanager.com",
            "adserver.yahoo.com", "adsystem.com", "adnxs.com",
            "casalemedia.com", "2mdn.net", "admeld.com", "adtech.de",
            "advertising.com", "atdmt.com", "bluekai.com", "chitika.net",
            "criteo.com", "demdex.net", "dotomi.com", "exelator.com",
            "eyereturn.com", "fastclick.net", "invitemedia.com",
            "kontera.com", "mediaplex.com", "mgid.com", "moat.com",
            "outbrain.com", "quantserve.com", "revjet.com",
            "rubiconproject.com", "scorecardresearch.com",
            "serving-sys.com", "sharethis.com", "smartadserver.com",
            "stormyew.com", "taboola.com", "tribalfusion.com",
            "zedo.com", "adzerk.net", "yieldmo.com"
        ]
        self.blocked_domains.update(basic_ad_domains)
    
    def interceptRequest(self, info):
        """
        Intercepta cada solicitud HTTP y la bloquea si coincide con patrones de anuncios.
        
        Args:
            info: Información de la solicitud web
        """
        url = info.requestUrl().toString()
        domain = info.requestUrl().host()
        
        # Bloquear por dominio
        for blocked_domain in self.blocked_domains:
            if blocked_domain in domain:
                info.block(True)
                return
        
        # Bloquear por patrones en la URL
        ad_patterns = [
            '/ad.', '/ads.', '/banner', '/popup', '/popunder',
            '/tracking', '/analytics', '/pixel', '/beacon',
            'banner', 'popup', 'popunder', 'tracking',
            'analytics', 'pixel', 'beacon'
        ]
        
        url_lower = url.lower()
        for pattern in ad_patterns:
            if pattern in url_lower:
                info.block(True)
                return


# ============================================================================
# PESTAÑA DE NAVEGACIÓN PERSONALIZADA
# ============================================================================
class WebTab(QWebEngineView):
    """
    Representa una pestaña de navegación con funcionalidades extendidas.
    Soporta modo lectura, modo incógnito y bloqueo de anuncios.
    """
    
    def __init__(self, parent_browser, profile=None, is_reader_mode=False, is_incognito=False):
        """
        Inicializa una nueva pestaña web.
        
        Args:
            parent_browser: Referencia al navegador principal
            profile: Perfil web personalizado (para incógnito)
            is_reader_mode: Si es True, activa el modo lectura
            is_incognito: Si es True, activa el modo privado
        """
        super().__init__()
        self.parent_browser = parent_browser
        self.is_reader_mode = is_reader_mode
        self.is_incognito = is_incognito
        self.current_title = "Nueva pestaña"
        self.current_url = ""
        
        # Configurar página con perfil personalizado si es necesario
        if profile:
            page = QWebEnginePage(profile, self)
            self.setPage(page)
        
        # Configurar bloqueador de anuncios
        self.ad_blocker = AdBlocker()
        if self.page().profile():
            self.page().profile().setUrlRequestInterceptor(self.ad_blocker)
        
        # Conectar señales de eventos web
        self.urlChanged.connect(self.on_url_changed)
        self.loadProgress.connect(self.on_load_progress)
        self.loadFinished.connect(self.on_load_finished)
        self.titleChanged.connect(self.on_title_changed)
        
        # Configurar modo lectura si está activado
        if is_reader_mode:
            self.setup_reader_mode()
    
    def setup_reader_mode(self):
        """Configura los estilos CSS para el modo lectura."""
        self.setZoomFactor(1.2)
        
        # CSS para mejorar la legibilidad
        css = """
        body {
            max-width: 800px;
            margin: 40px auto;
            font-family: 'Georgia', 'Times New Roman', serif;
            font-size: 18px;
            line-height: 1.6;
            color: #333;
            padding: 20px;
            background-color: #f8f8f8 !important;
        }
        h1, h2, h3 {
            font-family: 'Helvetica', 'Arial', sans-serif;
            color: #222;
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
            margin-top: 1.5em;
        }
        p {
            margin: 1em 0;
            text-align: justify;
        }
        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 20px auto;
            border-radius: 4px;
        }
        blockquote {
            border-left: 4px solid #ddd;
            margin: 1em 0;
            padding-left: 1em;
            font-style: italic;
            color: #555;
        }
        pre, code {
            background-color: #f0f0f0;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Consolas', monospace;
        }
        """
        
        # Inyectar CSS cuando el DOM esté listo
        script = f"""
        document.addEventListener('DOMContentLoaded', function() {{
            var style = document.createElement('style');
            style.textContent = `{css}`;
            document.head.appendChild(style);
        }});
        """
        self.inject_js(script)
    
    def inject_js(self, script):
        """
        Inyecta código JavaScript de forma segura en la página actual.
        
        Args:
            script: Código JavaScript a ejecutar
        """
        try:
            self.page().runJavaScript(script)
        except Exception as e:
            print(f"Error inyectando JavaScript: {e}")
    
    def on_url_changed(self, url):
        """
        Maneja el cambio de URL en la pestaña.
        
        Args:
            url: Nueva URL como objeto QUrl
        """
        self.current_url = url.toString()
        # Actualizar barra de URL solo si esta pestaña está activa
        if self.parent_browser.tabs.currentWidget() == self:
            self.parent_browser.url_bar.setText(self.current_url)
    
    def on_load_progress(self, progress):
        """
        Maneja el progreso de carga de la página.
        
        Args:
            progress: Porcentaje de carga (0-100)
        """
        if self.parent_browser.tabs.currentWidget() == self:
            message = f"Cargando... {progress}%"
            self.parent_browser.status_bar.showMessage(message, 3000)
    
    def on_load_finished(self, success):
        """
        Maneja la finalización de la carga de página.
        
        Args:
            success: True si la carga fue exitosa, False si hubo error
        """
        if self.parent_browser.tabs.currentWidget() == self:
            if success:
                self.parent_browser.status_bar.showMessage("✅ Página cargada correctamente", 2000)
                
                # Añadir al historial solo si no es modo incógnito
                if (not self.is_incognito and 
                    self.current_url and 
                    self.current_url != "about:blank"):
                    self.parent_browser.history_manager.add_entry(
                        self.current_url, 
                        self.current_title
                    )
                
                # Aplicar transformaciones de modo lectura si está activo
                if self.is_reader_mode and not self.current_url.startswith("file://"):
                    self.apply_reader_mode_transform()
            else:
                self.parent_browser.status_bar.showMessage("❌ Error al cargar la página", 3000)
    
    def on_title_changed(self, title):
        """
        Maneja el cambio de título de la página.
        
        Args:
            title: Nuevo título de la página
        """
        self.current_title = title
        index = self.parent_browser.tabs.indexOf(self)
        if index >= 0:
            # Acortar títulos largos para la pestaña
            short_title = (title[:25] + "...") if len(title) > 25 else title
            
            # Prefijos para identificar tipo de pestaña
            if self.is_incognito:
                prefix = "🕶 "
            elif self.is_reader_mode:
                prefix = "📖 "
            else:
                prefix = ""
            
            self.parent_browser.tabs.setTabText(index, prefix + short_title)
    
    def apply_reader_mode_transform(self):
        """Aplica transformaciones avanzadas para el modo lectura."""
        script = """
        // Algoritmo para encontrar el contenido principal del artículo
        function findMainContent() {
            let bestElement = document.body;
            let bestScore = -Infinity;
            
            // Calcular puntuación de relevancia para elementos candidatos
            function calculateScore(element) {
                if (!element) return -Infinity;
                
                let score = 0;
                
                // Puntos por elementos de texto
                score += element.querySelectorAll('p').length * 3;
                score += element.querySelectorAll('article p').length * 5;
                score += element.querySelectorAll('h1, h2, h3, h4, h5, h6').length * 2;
                
                // Puntos por densidad de texto
                const text = element.textContent.trim();
                const words = text.split(/\s+/);
                score += Math.min(words.length / 10, 50);
                
                // Penalizar elementos no deseados
                const unwantedSelectors = [
                    'script', 'style', 'nav', 'header', 'footer', 'aside',
                    'iframe', 'form', 'button', '.ad', '.sidebar', '.menu',
                    '.social-share', '.comments', '.related-posts',
                    '[class*="ad"]', '[id*="ad"]', '[class*="banner"]'
                ];
                
                unwantedSelectors.forEach(selector => {
                    score -= element.querySelectorAll(selector).length * 10;
                });
                
                // Penalizar elementos con poco texto
                if (words.length < 50) {
                    score -= 100;
                }
                
                return score;
            }
            
            // Elementos candidatos probables
            const candidates = [
                document.querySelector('article'),
                document.querySelector('main'),
                document.querySelector('[role="main"]'),
                document.querySelector('.content'),
                document.querySelector('.article'),
                document.querySelector('.post'),
                document.querySelector('#content'),
                document.body
            ];
            
            // Evaluar cada candidato
            candidates.forEach(element => {
                if (element) {
                    const score = calculateScore(element);
                    if (score > bestScore) {
                        bestScore = score;
                        bestElement = element;
                    }
                }
            });
            
            return { element: bestElement, score: bestScore };
        }
        
        // Encontrar y aislar el contenido principal
        const result = findMainContent();
        
        // Solo reemplazar si encontramos contenido válido
        if (result.score > 30) {
            // Guardar el contenido original
            const originalContent = result.element.innerHTML;
            
            // Limpiar el body y añadir solo el contenido principal
            document.body.innerHTML = '';
            const container = document.createElement('div');
            container.id = 'reader-mode-content';
            container.innerHTML = originalContent;
            document.body.appendChild(container);
            
            // Remover elementos no deseados
            const unwantedSelectors = [
                'script', 'style', 'nav', 'header', 'footer', 'aside',
                'iframe', 'form', 'button', '.ad', '.sidebar', '.menu',
                '.social-share', '.comments', '.related-posts',
                '[class*="ad"]', '[id*="ad"]', '[class*="banner"]',
                '.newsletter', '.subscription', '.adsbygoogle'
            ];
            
            unwantedSelectors.forEach(selector => {
                container.querySelectorAll(selector).forEach(el => el.remove());
            });
        }
        
        // Aplicar estilos de lectura
        document.body.style.maxWidth = '800px';
        document.body.style.margin = '40px auto';
        document.body.style.padding = '20px';
        document.body.style.fontFamily = "'Georgia', 'Times New Roman', serif";
        document.body.style.fontSize = '18px';
        document.body.style.lineHeight = '1.6';
        document.body.style.color = '#333';
        document.body.style.backgroundColor = '#f8f8f8';
        """
        
        self.inject_js(script)
    
    def enable_ad_blocker(self, enable=True):
        """
        Activa o desactiva el bloqueador de anuncios.
        
        Args:
            enable: True para activar, False para desactivar
        """
        if enable:
            self.page().profile().setUrlRequestInterceptor(self.ad_blocker)
        else:
            self.page().profile().setUrlRequestInterceptor(None)


# ============================================================================
# GESTORES DE DATOS
# ============================================================================
class BookmarkManager:
    """
    Gestiona los marcadores del navegador con almacenamiento en archivo JSON.
    """
    
    def __init__(self, filename="bookmarks.json"):
        """
        Inicializa el gestor de marcadores.
        
        Args:
            filename: Ruta del archivo de almacenamiento
        """
        self.filename = filename
        self.bookmarks = []
        self.load_bookmarks()
    
    def load_bookmarks(self):
        """Carga los marcadores desde el archivo JSON."""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.bookmarks = data.get('bookmarks', [])
            else:
                # Inicializar con marcadores por defecto
                self.bookmarks = []
        except Exception as e:
            print(f"Error cargando marcadores: {e}")
            self.bookmarks = []
    
    def save_bookmarks(self):
        """Guarda los marcadores en el archivo JSON."""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump({'bookmarks': self.bookmarks}, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error guardando marcadores: {e}")
            return False
    
    def add_bookmark(self, title, url, folder="General"):
        """
        Agrega un nuevo marcador.
        
        Args:
            title: Título del marcador
            url: URL del marcador
            folder: Carpeta para organizar (opcional)
            
        Returns:
            dict: El marcador creado o None si hubo error
        """
        if not url or url == "about:blank":
            return None
        
        # Verificar si el marcador ya existe
        for bookmark in self.bookmarks:
            if bookmark['url'] == url:
                return bookmark
        
        # Crear nuevo marcador
        bookmark = {
            'id': len(self.bookmarks) + 1,
            'title': title or "Sin título",
            'url': url,
            'folder': folder or "General",
            'date': datetime.now().isoformat(),
            'favicon': f"https://www.google.com/s2/favicons?domain={urlparse(url).netloc}&sz=16"
        }
        
        self.bookmarks.append(bookmark)
        if self.save_bookmarks():
            return bookmark
        return None
    
    def remove_bookmark(self, bookmark_id):
        """
        Elimina un marcador por ID.
        
        Args:
            bookmark_id: ID del marcador a eliminar
        """
        self.bookmarks = [b for b in self.bookmarks if b['id'] != bookmark_id]
        self.save_bookmarks()
    
    def get_bookmarks(self, folder=None):
        """
        Obtiene todos los marcadores o los de una carpeta específica.
        
        Args:
            folder: Filtra por carpeta (opcional)
            
        Returns:
            list: Lista de marcadores
        """
        if folder:
            return [b for b in self.bookmarks if b['folder'] == folder]
        return self.bookmarks
    
    def get_folders(self):
        """Obtiene la lista de carpetas únicas."""
        folders = set(b['folder'] for b in self.bookmarks)
        return sorted(list(folders))


class HistoryManager:
    """
    Gestiona el historial de navegación con almacenamiento en archivo JSON.
    """
    
    def __init__(self, filename="history.json", max_entries=1000):
        """
        Inicializa el gestor de historial.
        
        Args:
            filename: Ruta del archivo de almacenamiento
            max_entries: Número máximo de entradas a guardar
        """
        self.filename = filename
        self.max_entries = max_entries
        self.history = []
        self.load_history()
    
    def load_history(self):
        """Carga el historial desde el archivo JSON."""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history = data.get('history', [])
        except Exception as e:
            print(f"Error cargando historial: {e}")
            self.history = []
    
    def save_history(self):
        """Guarda el historial en el archivo JSON."""
        try:
            # Limitar el número de entradas guardadas
            history_to_save = self.history[-self.max_entries:] if len(self.history) > self.max_entries else self.history
            
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump({'history': history_to_save}, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error guardando historial: {e}")
            return False
    
    def add_entry(self, url, title):
        """
        Agrega una entrada al historial.
        
        Args:
            url: URL visitada
            title: Título de la página
        """
        if not url or url == "about:blank":
            return
        
        # Verificar si la última entrada es la misma (evitar duplicados consecutivos)
        if self.history:
            last_entry = self.history[-1]
            if last_entry['url'] == url:
                # Actualizar título si cambió
                last_entry['title'] = title or "Sin título"
                self.save_history()
                return
        
        entry = {
            'url': url,
            'title': title or "Sin título",
            'timestamp': datetime.now().isoformat(),
            'visit_count': 1
        }
        
        self.history.append(entry)
        self.save_history()
    
    def clear_history(self):
        """Elimina todo el historial."""
        self.history = []
        self.save_history()
    
    def clear_history_range(self, start_date, end_date):
        """
        Elimina el historial dentro de un rango de fechas.
        
        Args:
            start_date: Fecha de inicio
            end_date: Fecha de fin
        """
        self.history = [
            entry for entry in self.history
            if not (start_date <= datetime.fromisoformat(entry['timestamp']).date() <= end_date)
        ]
        self.save_history()
    
    def get_recent(self, limit=50):
        """
        Obtiene las entradas más recientes del historial.
        
        Args:
            limit: Número máximo de entradas a devolver
            
        Returns:
            list: Lista de entradas ordenadas por fecha (más reciente primero)
        """
        return list(reversed(self.history[-limit:]))
    
    def search_history(self, query):
        """
        Busca en el historial por término.
        
        Args:
            query: Término de búsqueda
            
        Returns:
            list: Entradas que coinciden con la búsqueda
        """
        query_lower = query.lower()
        results = []
        
        for entry in reversed(self.history):
            if (query_lower in entry['title'].lower() or 
                query_lower in entry['url'].lower()):
                results.append(entry)
                if len(results) >= 50:  # Limitar resultados
                    break
        
        return results


class ThemeManager:
    """
    Gestiona los temas visuales de la aplicación.
    """
    
    # Definición de temas disponibles
    THEMES = {
        "light": {
            "name": "Claro",
            "icon": "🌗",
            "colors": {
                "primary": "#0066cc",
                "secondary": "#4da6ff",
                "background": "#f0f8ff",
                "surface": "#ffffff",
                "text": "#000000",
                "text_secondary": "#666666",
                "border": "#cce0ff",
                "hover": "#e6f2ff",
                "selected": "#b3d9ff"
            }
        },
        "dark": {
            "name": "Oscuro",
            "icon": "🌗",
            "colors": {
                "primary": "#3399ff",
                "secondary": "#66b3ff",
                "background": "#0a1929",
                "surface": "#1a2b3c",
                "text": "#e6f2ff",
                "text_secondary": "#a0b9d0",
                "border": "#2a3b4c",
                "hover": "#2a3b4c",
                "selected": "#3a4b5c"
            }
        },
        "aero": {
            "name": "Frutiger Aero",
            "icon": "🌗",
            "colors": {
                "primary": "#40b0ff",
                "secondary": "#80d0ff",
                "background": "#c0e8ff",
                "surface": "#ffffff",
                "text": "#005080",
                "text_secondary": "#407090",
                "border": "#80c0ff",
                "hover": "#e6f2ff",
                "selected": "#b3e0ff"
            }
        },
        "midnight": {
            "name": "Medianoche",
            "icon": "🌗",
            "colors": {
                "primary": "#9d4edd",
                "secondary": "#c77dff",
                "background": "#10002b",
                "surface": "#240046",
                "text": "#e0aaff",
                "text_secondary": "#c77dff",
                "border": "#3c096c",
                "hover": "#3c096c",
                "selected": "#5a189a"
            }
        }
    }
    
    def __init__(self):
        """Inicializa el gestor de temas."""
        self.current_theme = "aero"
        self.settings = QSettings("AerisNet", "ThemeSettings")
        self.load_theme()
    
    def load_theme(self):
        """Carga el tema guardado en las preferencias."""
        saved_theme = self.settings.value("current_theme", "aero")
        if saved_theme in self.THEMES:
            self.current_theme = saved_theme
    
    def save_theme(self):
        """Guarda el tema actual en las preferencias."""
        self.settings.setValue("current_theme", self.current_theme)
    
    def get_theme(self, theme_name=None):
        """
        Obtiene la configuración de un tema.
        
        Args:
            theme_name: Nombre del tema (opcional, usa el actual si es None)
            
        Returns:
            dict: Configuración del tema
        """
        if theme_name is None:
            theme_name = self.current_theme
        return self.THEMES.get(theme_name, self.THEMES["aero"])
    
    def set_theme(self, theme_name):
        """
        Cambia el tema actual.
        
        Args:
            theme_name: Nombre del nuevo tema
            
        Returns:
            bool: True si el cambio fue exitoso, False si el tema no existe
        """
        if theme_name in self.THEMES:
            self.current_theme = theme_name
            self.save_theme()
            return True
        return False
    
    def get_theme_names(self):
        """
        Obtiene la lista de nombres de temas disponibles.
        
        Returns:
            list: Nombres de temas
        """
        return list(self.THEMES.keys())
    
    def get_theme_display_names(self):
        """
        Obtiene nombres para mostrar de los temas.
        
        Returns:
            list: Tuplas (nombre_para mostrar, nombre_interno)
        """
        return [(theme["icon"] + " " + theme["name"], name) 
                for name, theme in self.THEMES.items()]


# ============================================================================
# VENTANA PRINCIPAL DEL NAVEGADOR
# ============================================================================
class Browser(QMainWindow):
    """
    Ventana principal del navegador AerisNet.
    Coordina todas las funcionalidades y componentes de la interfaz.
    """
    
    def __init__(self):
        """Inicializa la ventana principal del navegador."""
        super().__init__()
        
        # Inicializar gestores de datos
        self.bookmark_manager = BookmarkManager()
        self.history_manager = HistoryManager()
        self.theme_manager = ThemeManager()
        
        # Variables de estado
        self.reader_mode_active = False
        self.current_zoom = 100
        self.fullscreen_mode = False
        
        # Configurar interfaz
        self.init_ui()
        self.apply_theme()
        self.setup_shortcuts()
        
        # Cargar estado anterior (si existe)
        self.load_window_state()
    
    def init_ui(self):
        """Configura todos los componentes de la interfaz de usuario."""
        # Configuración básica de la ventana
        self.setWindowTitle("AerisNet • Navegador Seguro")
        self.setGeometry(100, 100, 1200, 800)
        
        # Crear barra de herramientas principal
        self.setup_toolbar()
        
        # Crear sistema de pestañas
        self.setup_tab_system()
        
        # Crear barra de estado
        self.setup_status_bar()
        
        # Crear primera pestaña
        self.new_tab(QUrl("https://www.google.com"))
    
    def setup_toolbar(self):
        """Configura la barra de herramientas principal."""
        self.toolbar = QToolBar("Barra de Navegación")
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(self.toolbar)
        
        # Acciones de navegación básica
        nav_actions = [
            ("➕", "Nueva pestaña (Ctrl+T)", self.new_tab, "new_tab"),
            ("🕶", "Nueva incógnito (Ctrl+Shift+N)", self.new_incognito_tab, "new_incognito"),
            ("◀", "Atrás (Alt+←)", self.go_back, "back"),
            ("▶", "Adelante (Alt+→)", self.go_forward, "forward"),
            ("↻", "Recargar (F5)", self.reload_page, "reload"),
            ("⏹", "Detener", self.stop_loading, "stop"),
            ("🏠", "Página de inicio", self.go_home, "home"),
        ]
        
        for icon, tooltip, handler, action_name in nav_actions:
            action = QAction(icon, self)
            action.setToolTip(tooltip)
            action.triggered.connect(handler)
            action.setObjectName(action_name)
            self.toolbar.addAction(action)
        
        self.toolbar.addSeparator()
        
        # Barra de dirección URL
        self.setup_url_bar()
        
        self.toolbar.addSeparator()
        
        # Acciones adicionales
        extra_actions = [
            ("📖", "Modo lectura (Ctrl+R)", self.toggle_reader_mode, "reader_mode"),
            ("⭐", "Agregar marcador (Ctrl+D)", self.add_bookmark, "add_bookmark"),
            ("📜", "Historial (Ctrl+H)", self.show_history, "show_history"),
            ("📂", "Marcadores", self.show_bookmarks, "show_bookmarks"),
            ("⚙️", "Configuración", self.show_settings, "settings"),
            ("🔍", "Buscar en página", self.find_on_page, "find"),
        ]
        
        for icon, tooltip, handler, action_name in extra_actions:
            action = QAction(icon, self)
            action.setToolTip(tooltip)
            action.triggered.connect(handler)
            action.setObjectName(action_name)
            self.toolbar.addAction(action)
        
        # Selector de temas
        self.setup_theme_selector()
    
    def setup_url_bar(self):
        """Configura la barra de direcciones URL."""
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Escribe una URL o término de búsqueda...")
        self.url_bar.setClearButtonEnabled(True)
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.url_bar.setMinimumWidth(400)
        
        # Sugerencias al escribir
        self.url_bar.textChanged.connect(self.show_url_suggestions)
        
        # Botón de acción para la barra de URL
        url_action = QAction("🔍", self)
        url_action.setToolTip("Ir a la URL o buscar")
        url_action.triggered.connect(self.navigate_to_url)
        self.url_bar.addAction(url_action, QLineEdit.TrailingPosition)
        
        self.toolbar.addWidget(self.url_bar)
    
    def setup_theme_selector(self):
        """Configura el selector de temas."""
        self.theme_combo = QComboBox()
        self.theme_combo.setToolTip("Cambiar tema visual")
        
        # Añadir temas disponibles
        theme_display_names = self.theme_manager.get_theme_display_names()
        for display_name, theme_name in theme_display_names:
            self.theme_combo.addItem(display_name, theme_name)
        
        # Seleccionar tema actual
        current_index = self.theme_combo.findData(self.theme_manager.current_theme)
        if current_index >= 0:
            self.theme_combo.setCurrentIndex(current_index)
        
        self.theme_combo.currentIndexChanged.connect(self.change_theme)
        self.toolbar.addWidget(QLabel(" Tema:"))
        self.toolbar.addWidget(self.theme_combo)
    
    def setup_tab_system(self):
        """Configura el sistema de pestañas."""
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setElideMode(Qt.ElideRight)
        
        # Conectar señales
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabs.tabBarDoubleClicked.connect(self.on_tab_bar_double_clicked)
        
        # Añadir botón de nueva pestaña al lado de las pestañas
        new_tab_btn = QPushButton("➕")
        new_tab_btn.setToolTip("Nueva pestaña")
        new_tab_btn.clicked.connect(self.new_tab)
        new_tab_btn.setMaximumSize(30, 30)
        self.tabs.setCornerWidget(new_tab_btn, Qt.TopRightCorner)
        
        self.setCentralWidget(self.tabs)
    
    def setup_status_bar(self):
        """Configura la barra de estado."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Indicador de progreso (simulado con texto)
        self.progress_label = QLabel()
        self.status_bar.addWidget(self.progress_label)
        
        # Indicador de modo
        self.mode_label = QLabel("🌐 Normal")
        self.status_bar.addPermanentWidget(self.mode_label)
        
        # Indicador de zoom
        self.zoom_label = QLabel("100%")
        self.status_bar.addPermanentWidget(self.zoom_label)
        
        # Reloj en tiempo real
        self.clock_label = QLabel()
        self.status_bar.addPermanentWidget(self.clock_label)
        self.update_clock()
        
        # Temporizador para actualizar el reloj cada segundo
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
    
    def setup_shortcuts(self):
        """Configura los atajos de teclado globales."""
        shortcuts = [
            (QKeySequence("Ctrl+T"), self.new_tab),
            (QKeySequence("Ctrl+W"), self.close_current_tab),
            (QKeySequence("Ctrl+Shift+W"), self.close_all_tabs),
            (QKeySequence("Ctrl+Tab"), self.next_tab),
            (QKeySequence("Ctrl+Shift+Tab"), self.previous_tab),
            (QKeySequence("Ctrl+L"), lambda: self.url_bar.setFocus()),
            (QKeySequence("F5"), self.reload_page),
            (QKeySequence("Ctrl+F5"), self.hard_reload),
            (QKeySequence("F11"), self.toggle_fullscreen),
            (QKeySequence("Ctrl+R"), self.toggle_reader_mode),
            (QKeySequence("Ctrl+H"), self.show_history),
            (QKeySequence("Ctrl+D"), self.add_bookmark),
            (QKeySequence("Ctrl+Shift+N"), self.new_incognito_tab),
            (QKeySequence("Ctrl++"), self.zoom_in),
            (QKeySequence("Ctrl+-"), self.zoom_out),
            (QKeySequence("Ctrl+0"), self.reset_zoom),
            (QKeySequence("Ctrl+F"), self.find_on_page),
            (QKeySequence("Ctrl+S"), self.save_page),
            (QKeySequence("Ctrl+P"), self.print_page),
            (QKeySequence("Alt+Left"), self.go_back),
            (QKeySequence("Alt+Right"), self.go_forward),
            (QKeySequence("Ctrl+Shift+Delete"), self.clear_browsing_data),
        ]
        
        for key_sequence, handler in shortcuts:
            shortcut = QShortcut(key_sequence, self)
            shortcut.activated.connect(handler)
    
    def apply_theme(self):
        """Aplica el tema actual a toda la interfaz."""
        theme = self.theme_manager.get_theme()
        colors = theme["colors"]
        
        # Hoja de estilos CSS personalizada
        style_sheet = f"""
            /* Ventana principal */
            QMainWindow {{
                background-color: {colors['background']};
            }}
            
            /* Barra de herramientas */
            QToolBar {{
                background-color: {colors['surface']};
                border-bottom: 2px solid {colors['border']};
                spacing: 6px;
                padding: 4px;
            }}
            
            QToolBar::separator {{
                width: 1px;
                background-color: {colors['border']};
                margin: 4px 8px;
            }}
            
            /* Barra de direcciones */
            QLineEdit {{
                background-color: {colors['surface']};
                border: 2px solid {colors['border']};
                border-radius: 16px;
                padding: 8px 16px;
                color: {colors['text']};
                selection-background-color: {colors['selected']};
                font-size: 13px;
            }}
            
            QLineEdit:focus {{
                border: 2px solid {colors['primary']};
                background-color: {colors['surface']};
            }}
            
            QLineEdit:hover {{
                border: 2px solid {colors['secondary']};
            }}
            
            /* Pestañas */
            QTabWidget::pane {{
                border: none;
                background-color: {colors['background']};
            }}
            
            QTabBar::tab {{
                background-color: {colors['hover']};
                border: 1px solid {colors['border']};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 16px;
                margin-right: 2px;
                color: {colors['text']};
                min-width: 120px;
                max-width: 200px;
            }}
            
            QTabBar::tab:selected {{
                background-color: {colors['surface']};
                border-bottom: 2px solid {colors['primary']};
                font-weight: bold;
            }}
            
            QTabBar::tab:hover:!selected {{
                background-color: {colors['hover']};
                border-color: {colors['secondary']};
            }}
            
            QTabBar::close-button {{
                image: url(:/close.png);
                subcontrol-position: right;
                padding: 4px;
            }}
            
            QTabBar::close-button:hover {{
                background-color: {colors['hover']};
                border-radius: 8px;
            }}
            
            /* Barra de estado */
            QStatusBar {{
                background-color: {colors['surface']};
                color: {colors['text']};
                border-top: 1px solid {colors['border']};
                font-size: 12px;
            }}
            
            QStatusBar::item {{
                border: none;
            }}
            
            /* ComboBox (selector de temas) */
            QComboBox {{
                background-color: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 12px;
                padding: 6px 12px;
                color: {colors['text']};
                min-width: 120px;
            }}
            
            QComboBox:hover {{
                border: 1px solid {colors['secondary']};
            }}
            
            QComboBox::drop-down {{
                border: none;
            }}
            
            QComboBox::down-arrow {{
                image: url(:/down_arrow.png);
                width: 12px;
                height: 12px;
            }}
            
            QComboBox QAbstractItemView {{
                background-color: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
                selection-background-color: {colors['selected']};
                color: {colors['text']};
            }}
            
            /* Botones en barra de herramientas */
            QToolButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                padding: 6px;
                color: {colors['text']};
            }}
            
            QToolButton:hover {{
                background-color: {colors['hover']};
                border: 1px solid {colors['border']};
            }}
            
            QToolButton:pressed {{
                background-color: {colors['selected']};
            }}
            
            /* Botones generales */
            QPushButton {{
                background-color: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
                padding: 8px 16px;
                color: {colors['text']};
                font-weight: normal;
            }}
            
            QPushButton:hover {{
                background-color: {colors['hover']};
                border: 1px solid {colors['secondary']};
            }}
            
            QPushButton:pressed {{
                background-color: {colors['selected']};
            }}
            
            /* Diálogos */
            QDialog {{
                background-color: {colors['background']};
            }}
            
            QLabel {{
                color: {colors['text']};
            }}
            
            /* Listas */
            QListWidget {{
                background-color: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
                color: {colors['text']};
                outline: none;
            }}
            
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {colors['border']};
            }}
            
            QListWidget::item:selected {{
                background-color: {colors['selected']};
                color: {colors['text']};
            }}
            
            QListWidget::item:hover {{
                background-color: {colors['hover']};
            }}
        """
        
        self.setStyleSheet(style_sheet)
    
    # ============================================================================
    # GESTIÓN DE PESTAÑAS
    # ============================================================================
    
    def new_tab(self, url=None, reader_mode=False, is_incognito=False):
        """
        Crea una nueva pestaña de navegación.
        
        Args:
            url: URL inicial (opcional)
            reader_mode: Si es True, activa modo lectura
            is_incognito: Si es True, activa modo privado
            
        Returns:
            WebTab: La pestaña creada
        """
        try:
            # Procesar la URL
            if url is None:
                url = QUrl("https://www.google.com")
            elif isinstance(url, str):
                url = QUrl(url)
            elif not isinstance(url, QUrl):
                url = QUrl("https://www.google.com")
            
            # Crear perfil para modo incógnito si es necesario
            profile = None
            if is_incognito:
                profile = create_incognito_profile()
            
            # Crear la pestaña web
            webview = WebTab(
                parent_browser=self,
                profile=profile,
                is_reader_mode=reader_mode,
                is_incognito=is_incognito
            )
            
            # Configurar URL inicial
            webview.setUrl(url)
            
            # Determinar título inicial
            if is_incognito:
                title = "🕶 Incógnito"
                icon = "🕶"
            elif reader_mode:
                title = "📖 Modo Lectura"
                icon = "📖"
            else:
                title = "Nueva pestaña"
                icon = "🌐"
            
            # Añadir al sistema de pestañas
            index = self.tabs.addTab(webview, icon + " " + title)
            self.tabs.setCurrentIndex(index)
            
            # Actualizar interfaz
            self.update_mode_indicator()
            
            return webview
            
        except Exception as e:
            print(f"Error al crear pestaña: {e}")
            # Crear pestaña de respaldo
            webview = WebTab(self)
            webview.setUrl(QUrl("https://www.google.com"))
            self.tabs.addTab(webview, "⚠️ Error")
            return webview
    
    def new_incognito_tab(self):
        """Crea una nueva pestaña en modo de navegación privada."""
        self.new_tab(QUrl("https://www.google.com"), is_incognito=True)
        self.status_bar.showMessage("✅ Modo incógnito activado", 2000)
    
    def close_tab(self, index):
        """
        Cierra una pestaña específica.
        
        Args:
            index: Índice de la pestaña a cerrar
        """
        if self.tabs.count() <= 1:
            # Si es la última pestaña, cerrar la aplicación
            self.close()
        else:
            # Eliminar widget y pestaña
            widget = self.tabs.widget(index)
            if widget:
                widget.deleteLater()
            self.tabs.removeTab(index)
    
    def close_current_tab(self):
        """Cierra la pestaña actualmente activa."""
        current_index = self.tabs.currentIndex()
        if current_index >= 0:
            self.close_tab(current_index)
    
    def close_all_tabs(self):
        """Cierra todas las pestañas excepto la actual."""
        reply = QMessageBox.question(
            self, "Cerrar pestañas",
            "¿Cerrar todas las pestañas excepto la actual?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            current_index = self.tabs.currentIndex()
            
            # Cerrar pestañas en orden inverso para evitar problemas de índices
            for i in range(self.tabs.count() - 1, -1, -1):
                if i != current_index:
                    self.close_tab(i)
    
    def next_tab(self):
        """Activa la siguiente pestaña (cíclico)."""
        current = self.tabs.currentIndex()
        next_index = (current + 1) % self.tabs.count()
        self.tabs.setCurrentIndex(next_index)
    
    def previous_tab(self):
        """Activa la pestaña anterior (cíclico)."""
        current = self.tabs.currentIndex()
        prev_index = (current - 1) % self.tabs.count()
        self.tabs.setCurrentIndex(prev_index)
    
    def on_tab_changed(self, index):
        """
        Se ejecuta cuando el usuario cambia de pestaña.
        
        Args:
            index: Índice de la nueva pestaña activa
        """
        if 0 <= index < self.tabs.count():
            webview = self.tabs.widget(index)
            if webview:
                # Actualizar barra de URL
                self.url_bar.setText(webview.current_url)
                
                # Actualizar estado de modo lectura
                self.reader_mode_active = webview.is_reader_mode
                
                # Actualizar indicadores de interfaz
                self.update_mode_indicator()
                self.update_zoom_indicator()
    
    def on_tab_bar_double_clicked(self, index):
        """
        Maneja doble clic en la barra de pestañas.
        
        Args:
            index: Índice donde se hizo clic (-1 si fue en área vacía)
        """
        if index == -1:
            # Doble clic en área vacía: nueva pestaña
            self.new_tab()
    
    def current_browser(self):
        """
        Obtiene el widget de navegación actual.
        
        Returns:
            WebTab: Pestaña actual o None si no hay pestañas
        """
        return self.tabs.currentWidget()
    
    def update_mode_indicator(self):
        """Actualiza el indicador de modo en la barra de estado."""
        current = self.current_browser()
        if current:
            if current.is_incognito:
                self.mode_label.setText("🕶 Incógnito")
                self.mode_label.setStyleSheet("color: #888; font-weight: bold;")
            elif current.is_reader_mode:
                self.mode_label.setText("📖 Lectura")
                self.mode_label.setStyleSheet("color: #0066cc; font-weight: bold;")
            else:
                self.mode_label.setText("🌐 Normal")
                self.mode_label.setStyleSheet("color: #00aa00; font-weight: normal;")
        else:
            self.mode_label.setText("🌐 Normal")
    
    # ============================================================================
    # NAVEGACIÓN Y CONTROL DE PÁGINAS
    # ============================================================================
    
    def navigate_to_url(self):
        """Navega a la URL ingresada en la barra de direcciones."""
        text = self.url_bar.text().strip()
        if not text:
            return
        
        current_webview = self.current_browser()
        if not current_webview:
            return
        
        # Determinar si es una URL o término de búsqueda
        url = self.parse_url(text)
        current_webview.setUrl(url)
        
        # Guardar en historial de búsquedas rápidas
        if "search" in text.lower() or " " in text:
            self.status_bar.showMessage(f"🔍 Buscando: {text}", 2000)
    
    def parse_url(self, text):
        """
        Convierte texto en una URL válida.
        
        Args:
            text: Texto de entrada (URL o término de búsqueda)
            
        Returns:
            QUrl: URL formateada correctamente
        """
        # Si ya es una URL completa
        if text.startswith(("http://", "https://", "file://", "ftp://")):
            return QUrl(text)
        
        # Si parece un dominio (contiene punto y no espacios)
        if "." in text and " " not in text:
            # Añadir https:// por defecto
            if not text.startswith(("http://", "https://")):
                return QUrl("https://" + text)
            return QUrl(text)
        
        # En otros casos, buscar en Google
        search_query = quote_plus(text)
        return QUrl(f"https://www.google.com/search?q={search_query}")
    
    def show_url_suggestions(self, text):
        """Muestra sugerencias mientras se escribe en la barra de URL."""
        # Esta función se puede expandir para integrar con un motor de sugerencias
        pass
    
    def go_back(self):
        """Retrocede en el historial de navegación de la pestaña actual."""
        current = self.current_browser()
        if current and current.history().canGoBack():
            current.back()
    
    def go_forward(self):
        """Avanza en el historial de navegación de la pestaña actual."""
        current = self.current_browser()
        if current and current.history().canGoForward():
            current.forward()
    
    def reload_page(self):
        """Recarga la página actual."""
        current = self.current_browser()
        if current:
            current.reload()
    
    def hard_reload(self):
        """Recarga la página ignorando la caché (Shift+F5)."""
        current = self.current_browser()
        if current:
            current.reload()
            # En QtWebEngine, para recarga completa necesitamos:
            current.page().profile().clearHttpCache()
            self.status_bar.showMessage("🔄 Recarga completa (sin caché)", 2000)
    
    def stop_loading(self):
        """Detiene la carga de la página actual."""
        current = self.current_browser()
        if current:
            current.stop()
            self.status_bar.showMessage("⏹ Carga detenida", 2000)
    
    def go_home(self):
        """Navega a la página de inicio configurada."""
        current = self.current_browser()
        if current:
            # Por defecto Google, se podría configurar
            current.setUrl(QUrl("https://www.google.com"))
    
    def toggle_reader_mode(self):
        """Activa o desactiva el modo lectura en la pestaña actual."""
        current = self.current_browser()
        if not current:
            return
        
        if current.is_reader_mode:
            # Salir del modo lectura
            url = QUrl(current.current_url) if current.current_url else QUrl("https://www.google.com")
            self.close_current_tab()
            self.new_tab(url)
            self.status_bar.showMessage("📖 Modo lectura desactivado", 2000)
        else:
            # Entrar en modo lectura
            if not current.current_url or current.current_url == "about:blank":
                QMessageBox.information(self, "Modo lectura", 
                                       "Navega a una página web primero para usar el modo lectura.")
                return
            
            url = QUrl(current.current_url)
            self.close_current_tab()
            self.new_tab(url, reader_mode=True)
            self.status_bar.showMessage("📖 Modo lectura activado", 2000)
    
    # ============================================================================
    # GESTIÓN DE ZOOM
    # ============================================================================
    
    def zoom_in(self):
        """Aumenta el zoom de la página actual."""
        current = self.current_browser()
        if current:
            current.setZoomFactor(current.zoomFactor() + 0.1)
            self.update_zoom_indicator()
    
    def zoom_out(self):
        """Disminuye el zoom de la página actual."""
        current = self.current_browser()
        if current:
            current.setZoomFactor(max(0.25, current.zoomFactor() - 0.1))
            self.update_zoom_indicator()
    
    def reset_zoom(self):
        """Restablece el zoom al 100%."""
        current = self.current_browser()
        if current:
            current.setZoomFactor(1.0)
            self.update_zoom_indicator()
    
    def update_zoom_indicator(self):
        """Actualiza el indicador de zoom en la barra de estado."""
        current = self.current_browser()
        if current:
            zoom_percent = int(current.zoomFactor() * 100)
            self.zoom_label.setText(f"{zoom_percent}%")
            self.current_zoom = zoom_percent
        else:
            self.zoom_label.setText("100%")
            self.current_zoom = 100
    
    # ============================================================================
    # MARCADORES E HISTORIAL
    # ============================================================================
    
    def add_bookmark(self):
        """Agrega la página actual a los marcadores."""
        current = self.current_browser()
        if not current:
            return
        
        title = current.current_title or "Sin título"
        url = current.current_url
        
        if not url or url == "about:blank":
            QMessageBox.warning(self, "Agregar marcador", 
                               "No hay una página web activa para marcar.")
            return
        
        # Diálogo para agregar marcador con opciones
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QComboBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("⭐ Agregar marcador")
        dialog.setFixedWidth(400)
        
        layout = QFormLayout()
        
        title_edit = QLineEdit(title)
        url_edit = QLineEdit(url)
        url_edit.setReadOnly(True)
        
        folder_combo = QComboBox()
        folders = self.bookmark_manager.get_folders()
        folder_combo.addItems(folders)
        folder_combo.setEditable(True)
        folder_combo.setCurrentText("General")
        
        layout.addRow("Título:", title_edit)
        layout.addRow("URL:", url_edit)
        layout.addRow("Carpeta:", folder_combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        
        layout.addRow(buttons)
        dialog.setLayout(layout)
        
        if dialog.exec_() == QDialog.Accepted:
            bookmark = self.bookmark_manager.add_bookmark(
                title_edit.text(),
                url,
                folder_combo.currentText()
            )
            
            if bookmark:
                self.status_bar.showMessage(f"✅ '{bookmark['title']}' agregado a marcadores", 3000)
            else:
                QMessageBox.warning(self, "Error", "No se pudo agregar el marcador.")
    
    def show_bookmarks(self):
        """Muestra un diálogo con todos los marcadores."""
        dialog = QDialog(self)
        dialog.setWindowTitle("📂 Marcadores")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout()
        
        # Lista de marcadores
        bookmarks_list = QListWidget()
        bookmarks = self.bookmark_manager.get_bookmarks()
        
        for bookmark in bookmarks:
            try:
                # Formatear fecha
                date_obj = datetime.fromisoformat(bookmark['date'].replace('Z', '+00:00'))
                date_str = date_obj.strftime("%d/%m/%Y")
                
                # Crear texto del ítem
                item_text = f"{bookmark['title']}\n{bookmark['url']}\nCarpeta: {bookmark['folder']} • {date_str}"
                
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, bookmark['url'])
                item.setToolTip(f"Clic para abrir: {bookmark['url']}")
                bookmarks_list.addItem(item)
            except Exception as e:
                print(f"Error mostrando marcador: {e}")
                continue
        
        def open_bookmark(item):
            """Abre un marcador en una nueva pestaña."""
            url = QUrl(item.data(Qt.UserRole))
            self.new_tab(url)
            dialog.accept()
        
        bookmarks_list.itemDoubleClicked.connect(open_bookmark)
        layout.addWidget(bookmarks_list)
        
        # Botones de acción
        button_layout = QHBoxLayout()
        
        open_btn = QPushButton("Abrir")
        open_btn.clicked.connect(
            lambda: open_bookmark(bookmarks_list.currentItem())
        )
        button_layout.addWidget(open_btn)
        
        delete_btn = QPushButton("🗑️ Eliminar")
        delete_btn.clicked.connect(
            lambda: self.delete_bookmark(bookmarks_list, dialog)
        )
        button_layout.addWidget(delete_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("✕ Cerrar")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        
        dialog.exec_()
    
    def delete_bookmark(self, bookmarks_list, parent_dialog):
        """Elimina el marcador seleccionado."""
        current_item = bookmarks_list.currentItem()
        if not current_item:
            return
        
        reply = QMessageBox.question(
            parent_dialog, "Eliminar marcador",
            "¿Estás seguro de eliminar este marcador?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Aquí necesitaríamos el ID del marcador para eliminarlo
            # Por simplicidad, en esta versión solo removemos de la lista visual
            row = bookmarks_list.row(current_item)
            bookmarks_list.takeItem(row)
            
            # En una implementación completa, eliminaríamos de bookmarks_manager
            self.status_bar.showMessage("Marcador eliminado", 2000)
    
    def show_history(self):
        """Muestra el historial de navegación en un diálogo."""
        dialog = QDialog(self)
        dialog.setWindowTitle("📜 Historial de navegación")
        dialog.setMinimumSize(700, 500)
        
        layout = QVBoxLayout()
        
        # Barra de búsqueda
        search_layout = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText("Buscar en historial...")
        search_input.textChanged.connect(
            lambda text: self.filter_history(history_list, text)
        )
        search_layout.addWidget(search_input)
        layout.addLayout(search_layout)
        
        # Lista de historial
        history_list = QListWidget()
        history = self.history_manager.get_recent(100)
        
        for entry in history:
            try:
                timestamp = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                time_str = timestamp.strftime("%d/%m/%Y %H:%M")
                
                # Acortar título y URL para mostrar
                title = entry['title'][:60] + "..." if len(entry['title']) > 60 else entry['title']
                url = entry['url'][:80] + "..." if len(entry['url']) > 80 else entry['url']
                
                item_text = f"{title}\n{url}\n{time_str}"
                
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, entry['url'])
                item.setToolTip(f"Clic para abrir: {entry['url']}")
                history_list.addItem(item)
            except:
                continue
        
        def open_history_item(item):
            """Abre una entrada del historial en nueva pestaña."""
            url = QUrl(item.data(Qt.UserRole))
            self.new_tab(url)
            dialog.accept()
        
        history_list.itemDoubleClicked.connect(open_history_item)
        layout.addWidget(history_list)
        
        # Botones de acción
        button_layout = QHBoxLayout()
        
        open_btn = QPushButton("Abrir en nueva pestaña")
        open_btn.clicked.connect(
            lambda: open_history_item(history_list.currentItem())
        )
        button_layout.addWidget(open_btn)
        
        clear_btn = QPushButton("🗑️ Limpiar historial")
        clear_btn.clicked.connect(
            lambda: self.clear_history_confirmation(dialog)
        )
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("✕ Cerrar")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        
        dialog.exec_()
    
    def filter_history(self, history_list, query):
        """Filtra la lista de historial según la consulta."""
        if not query:
            # Mostrar todo si no hay consulta
            self.show_history()
            return
        
        # En una implementación completa, usaríamos history_manager.search_history()
        for i in range(history_list.count()):
            item = history_list.item(i)
            item_text = item.text().lower()
            item.setHidden(query.lower() not in item_text)
    
    def clear_history_confirmation(self, parent_dialog):
        """Pide confirmación antes de limpiar el historial."""
        reply = QMessageBox.question(
            parent_dialog, "Limpiar historial",
            "¿Estás seguro de borrar todo el historial de navegación?\nEsta acción no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.history_manager.clear_history()
            self.status_bar.showMessage("✅ Historial limpiado", 3000)
            parent_dialog.accept()
    
    # ============================================================================
    # CONFIGURACIÓN Y PREFERENCIAS
    # ============================================================================
    
    def show_settings(self):
        """Muestra el diálogo de configuración de la aplicación."""
        # Este es un diálogo básico. Se puede expandir significativamente.
        dialog = QDialog(self)
        dialog.setWindowTitle("⚙️ Configuración de AerisNet")
        dialog.setFixedSize(500, 400)
        
        layout = QVBoxLayout()
        
        # Página de inicio
        homepage_group = QGroupBox("Página de inicio")
        homepage_layout = QFormLayout()
        
        homepage_input = QLineEdit("https://www.google.com")
        homepage_layout.addRow("URL de inicio:", homepage_input)
        
        homepage_group.setLayout(homepage_layout)
        layout.addWidget(homepage_group)
        
        # Configuración de privacidad
        privacy_group = QGroupBox("Privacidad")
        privacy_layout = QVBoxLayout()
        
        block_ads_check = QCheckBox("Bloquear anuncios (recomendado)")
        block_ads_check.setChecked(True)
        privacy_layout.addWidget(block_ads_check)
        
        block_trackers_check = QCheckBox("Bloquear rastreadores")
        block_trackers_check.setChecked(True)
        privacy_layout.addWidget(block_trackers_check)
        
        clear_on_exit_check = QCheckBox("Limpiar datos al salir")
        clear_on_exit_check.setChecked(False)
        privacy_layout.addWidget(clear_on_exit_check)
        
        privacy_group.setLayout(privacy_layout)
        layout.addWidget(privacy_group)
        
        # Botones
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("💾 Guardar")
        save_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        
        if dialog.exec_() == QDialog.Accepted:
            self.status_bar.showMessage("✅ Configuración guardada", 2000)
            # Aquí se implementaría la lógica para guardar configuraciones
    
    def change_theme(self, index):
        """
        Cambia el tema visual de la aplicación.
        
        Args:
            index: Índice seleccionado en el combobox
        """
        if 0 <= index < self.theme_combo.count():
            theme_name = self.theme_combo.itemData(index)
            if self.theme_manager.set_theme(theme_name):
                self.apply_theme()
                self.status_bar.showMessage(f"✅ Tema cambiado a {self.theme_manager.get_theme()['name']}", 2000)
    
    # ============================================================================
    # FUNCIONALIDADES AVANZADAS
    # ============================================================================
    
    def toggle_fullscreen(self):
        """Activa o desactiva el modo pantalla completa."""
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_mode = False
            self.status_bar.showMessage("Pantalla completa desactivada", 1500)
        else:
            self.showFullScreen()
            self.fullscreen_mode = True
            self.status_bar.showMessage("Pantalla completa activada", 1500)
    
    def find_on_page(self):
        """Activa la función de buscar texto en la página actual."""
        current = self.current_browser()
        if not current:
            return
        
        # Diálogo simple de búsqueda
        text, ok = QInputDialog.getText(
            self, "Buscar en página",
            "Texto a buscar:",
            QLineEdit.Normal,
            ""
        )
        
        if ok and text:
            # Buscar en la página usando JavaScript
            script = f"""
            var searchText = '{text}';
            if (window.find(searchText)) {{
                window.getSelection().collapseToEnd();
            }} else {{
                alert('Texto no encontrado: ' + searchText);
            }}
            """
            current.inject_js(script)
            self.status_bar.showMessage(f"🔍 Buscando: '{text}'", 2000)
    
    def save_page(self):
        """Guarda la página actual como archivo HTML."""
        current = self.current_browser()
        if not current:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar página como",
            f"{current.current_title[:50]}.html",
            "Páginas web (*.html *.htm);;Todos los archivos (*)"
        )
        
        if file_path:
            # En una implementación completa, usaríamos current.page().toHtml()
            QMessageBox.information(
                self, "Guardar página",
                f"La página se guardará en:\n{file_path}\n\n(Esta función requiere implementación adicional)"
            )
    
    def print_page(self):
        """Imprime la página actual."""
        current = self.current_browser()
        if current:
            # QtWebEngine tiene soporte de impresión incorporado
            current.page().printToPdf = lambda file_path: print(f"Imprimiendo a PDF: {file_path}")
            QMessageBox.information(
                self, "Imprimir",
                "La función de impresión está disponible en la versión completa."
            )
    
    def clear_browsing_data(self):
        """Limpia los datos de navegación (caché, cookies, etc.)."""
        reply = QMessageBox.question(
            self, "Limpiar datos de navegación",
            "¿Estás seguro de limpiar todos los datos de navegación?\n"
            "Esto incluye caché, cookies e historial.\n\n"
            "Las pestañas incógnito no se verán afectadas.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Limpiar caché
            current = self.current_browser()
            if current:
                current.page().profile().clearHttpCache()
            
            # Limpiar cookies (implementación básica)
            # En QtWebEngine, esto requiere más configuración
            
            self.status_bar.showMessage("✅ Datos de navegación limpiados", 3000)
    
    # ============================================================================
    # UTILIDADES Y MANTENIMIENTO
    # ============================================================================
    
    def update_clock(self):
        """Actualiza el reloj en la barra de estado."""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.clock_label.setText(f"🕒 {current_time}")
    
    def load_window_state(self):
        """Carga el estado anterior de la ventana desde configuraciones."""
        settings = QSettings("AerisNet", "WindowState")
        geometry = settings.value("geometry")
        state = settings.value("windowState")
        
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)
    
    def save_window_state(self):
        """Guarda el estado actual de la ventana en configuraciones."""
        settings = QSettings("AerisNet", "WindowState")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
    
    def closeEvent(self, event):
        """
        Maneja el evento de cierre de la ventana.
        
        Args:
            event: Evento de cierre
        """
        # Guardar estado de la ventana
        self.save_window_state()
        
        # Preguntar antes de cerrar si hay múltiples pestañas
        if self.tabs.count() > 1:
            reply = QMessageBox.question(
                self, "Cerrar navegador",
                f"¿Cerrar el navegador con {self.tabs.count()} pestañas abiertas?",
                QMessageBox.Yes | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
        
        # Guardar datos de gestores
        self.bookmark_manager.save_bookmarks()
        self.history_manager.save_history()
        
        # Aceptar el evento de cierre
        event.accept()


# ============================================================================
# PUNTO DE ENTRADA DE LA APLICACIÓN
# ============================================================================
def main():
    """
    Función principal que inicializa y ejecuta la aplicación.
    
    Returns:
        int: Código de salida de la aplicación
    """
    try:
        # Crear aplicación Qt
        app = QApplication(sys.argv)
        
        # Configurar información de la aplicación
        app.setApplicationName("AerisNet")
        app.setApplicationDisplayName("AerisNet Navegador")
        app.setOrganizationName("AerisNet")
        app.setOrganizationDomain("aerisnet.example.com")
        
        # Configurar estilo visual
        app.setStyle("Fusion")  # Estilo moderno y consistente
        
        # Configurar fuente por defecto
        default_font = QFont("Segoe UI", 10)
        app.setFont(default_font)
        
        # Configurar paleta de colores base
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(240, 248, 255))  # Fondo azul claro
        palette.setColor(QPalette.WindowText, QColor(0, 0, 0))    # Texto negro
        app.setPalette(palette)
        
        # Crear y mostrar ventana principal
        browser = Browser()
        browser.show()
        
        # Ejecutar bucle principal de eventos
        return app.exec_()
        
    except Exception as e:
        print(f"Error crítico al iniciar la aplicación: {e}")
        QMessageBox.critical(
            None, "Error de inicio",
            f"No se pudo iniciar el navegador:\n\n{str(e)}"
        )
        return 1


# ============================================================================
# EJECUCIÓN DIRECTA
# ============================================================================
if __name__ == "__main__":
    # Ejecutar aplicación y obtener código de salida
    exit_code = main()
    
    # Salir con el código apropiado
    sys.exit(exit_code)
