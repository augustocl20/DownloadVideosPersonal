import sys
import re
import yt_dlp
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QHBoxLayout
from PyQt6.QtGui import QFont, QTextCursor

class DescargadorVideos(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Descargador de Videos - YouTube & TikTok")
        self.setGeometry(100, 100, 600, 500)
        self.setStyleSheet("""
            background-color: #1e1e1e;
            color: white;
            font-size: 14px;
        """)

        self.ultima_linea_progreso = None
        self.carpeta_destino = "videos"
        self.detener_descarga = False

        layout = QVBoxLayout()

        self.label = QLabel("🔗 Ingresa el enlace o carga un archivo TXT:")
        self.label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(self.label)

        input_layout = QHBoxLayout()
        self.input_url = QLineEdit(self)
        self.input_url.setPlaceholderText("Pega aquí el enlace de YouTube o TikTok...")
        self.input_url.setStyleSheet("""
            background-color: #2b2b2b;
            border: 1px solid #555;
            padding: 5px;
            color: white;
            border-radius: 5px;
        """)
        input_layout.addWidget(self.input_url)

        self.btn_cargar_txt = QPushButton("📂 Cargar TXT", self)
        self.btn_cargar_txt.setStyleSheet(self.button_style())
        self.btn_cargar_txt.clicked.connect(self.cargar_archivo_txt)
        input_layout.addWidget(self.btn_cargar_txt)

        layout.addLayout(input_layout)

        self.btn_seleccionar_carpeta = QPushButton("📁 Seleccionar Carpeta", self)
        self.btn_seleccionar_carpeta.setStyleSheet(self.button_style())
        self.btn_seleccionar_carpeta.clicked.connect(self.seleccionar_carpeta)
        layout.addWidget(self.btn_seleccionar_carpeta)

        buttons_layout = QHBoxLayout()
        self.btn_descargar = QPushButton("⬇ Descargar Video", self)
        self.btn_descargar.setStyleSheet(self.button_style())
        self.btn_descargar.clicked.connect(self.descargar_video)
        buttons_layout.addWidget(self.btn_descargar)

        self.btn_detener = QPushButton("🛑 Detener Descarga", self)
        self.btn_detener.setStyleSheet(self.button_style())
        self.btn_detener.clicked.connect(self.detener_descarga_manual)
        self.btn_detener.setEnabled(False)
        buttons_layout.addWidget(self.btn_detener)

        layout.addLayout(buttons_layout)

        self.log_area = QTextEdit(self)
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("""
            background-color: #2b2b2b;
            border: 1px solid #555;
            padding: 5px;
            color: white;
            border-radius: 5px;
        """)
        layout.addWidget(self.log_area)

        self.setLayout(layout)

    def button_style(self):
        return """
            QPushButton {
                background-color: #0078D7;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #005A9E;
            }
            QPushButton:pressed {
                background-color: #003F7F;
            }
        """

    def log(self, mensaje):
        self.log_area.append(mensaje)
        QApplication.processEvents()

    def seleccionar_carpeta(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de destino")
        if carpeta:
            self.carpeta_destino = carpeta
            self.log(f"📁 Carpeta seleccionada: {self.carpeta_destino}")

    def descargar_video(self):
        url = self.input_url.text().strip()
        if not url:
            self.log("⚠️ Por favor, ingresa un enlace válido.")
            return
        self.procesar_descarga([url])

    def cargar_archivo_txt(self):
        archivo_txt, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo de enlaces", "", "Archivos de texto (*.txt)")
        if archivo_txt:
            try:
                with open(archivo_txt, 'r', encoding='utf-8') as file:
                    urls = [url.strip() for url in file if url.strip()]

                if not urls:
                    self.log("⚠️ El archivo está vacío o no tiene enlaces válidos.")
                    return

                self.log("📋 Enlaces encontrados:")
                for url in urls:
                    self.log(f" - {url}")

                self.procesar_descarga(urls)

            except Exception as e:
                self.log(f"❌ Error al leer el archivo: {e}")

    def procesar_descarga(self, urls):
        self.detener_descarga = False
        self.btn_detener.setEnabled(True)
        for i, url in enumerate(urls, 1):
            if self.detener_descarga:
                self.log("🛑 Descarga detenida por el usuario.")
                break

            self.ultima_linea_progreso = None
            self.log(f"\n🚀 Iniciando descarga del video {i} de {len(urls)}")

            fecha = datetime.now().strftime("[%d_%m_%Y]")
            opciones = {
                'outtmpl': f'{self.carpeta_destino}/{fecha} %(title)s.%(ext)s',
                'format': 'bestvideo+bestaudio/best',
                'progress_hooks': [self.barra_progreso],
                'noprogress': False,
            }

            try:
                with yt_dlp.YoutubeDL(opciones) as ydl:
                    info = ydl.extract_info(url, download=False)
                    titulo = info.get("title", "Video sin título")

                    contenido_actual = self.log_area.toPlainText().split('\n')
                    contenido_actual.append(f"🔹 Descargando:")
                    contenido_actual.append(f" - {url}")
                    contenido_actual.append(f" - {titulo}")
                    contenido_actual.append("")
                    self.log_area.setPlainText('\n'.join(contenido_actual))
                    self.ultima_linea_progreso = len(contenido_actual)

                    info = ydl.extract_info(url, download=True)
                    archivo = ydl.prepare_filename(info)

                if info.get("requested_downloads") is None:
                    self.log(f"✅ Video ya estaba descargado: {archivo}")
                else:
                    self.log(f"✅ Descarga completada: {archivo}")

            except yt_dlp.utils.DownloadError as e:
                self.log(f"❌ Error al descargar el video: {e}")
            except Exception as e:
                self.log(f"⚠️ Ocurrió un error inesperado: {e}")

        self.btn_detener.setEnabled(False)

    def detener_descarga_manual(self):
        self.detener_descarga = True

    def barra_progreso(self, d):
        if d['status'] == 'downloading':
            porcentaje = d.get('_percent_str', '0%').strip()
            velocidad = d.get('_speed_str', 'N/A').strip()
            tiempo_restante = d.get('_eta_str', 'N/A').strip()

            mensaje = f"Velocidad: {velocidad} / Tiempo restante: {tiempo_restante} / Progreso: {porcentaje}"
            mensaje = re.sub(r'\x1b\[[0-9;]*m', '', mensaje)

            texto_actual = self.log_area.toPlainText().split('\n')
            if self.ultima_linea_progreso is not None:
                texto_actual[self.ultima_linea_progreso - 1] = mensaje
                self.log_area.setPlainText('\n'.join(texto_actual))
                cursor = self.log_area.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.log_area.setTextCursor(cursor)

            QApplication.processEvents()

        elif d['status'] == 'finished':
            self.ultima_linea_progreso = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = DescargadorVideos()
    ventana.show()
    sys.exit(app.exec())