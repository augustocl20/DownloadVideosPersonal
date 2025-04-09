import sys
import re
import concurrent.futures
from datetime import datetime
from pathlib import Path

import yt_dlp
from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QFileDialog,
    QHBoxLayout,
    QSpinBox,
)


class DescargadorVideos(QWidget):
    """Descargador con lista previa y descargas progresivas; el usuario elige cuántas descargas paralelas (1‑10)."""

    # Señales Qt
    info_signal = pyqtSignal(str)           # mensajes informativos
    progress_signal = pyqtSignal(int, str)  # (idx, texto progreso)

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------
    def __init__(self):
        super().__init__()

        # Config ventana
        self.setWindowTitle("Descargador de Videos - YouTube & TikTok (Paralelo)")
        self.resize(720, 560)
        self.setStyleSheet(
            """
            background-color: #1e1e1e;
            color: white;
            font-size: 14px;
            """
        )

        # Estado
        self.carpeta_destino = str(Path.home() / "Downloads")
        self.detener_descarga = False
        self.progress_lines: dict[int, int] = {}
        self.total_videos: int = 0
        self.pending_urls: list[str] = []

        # -------------------- UI --------------------
        layout = QVBoxLayout(self)

        label = QLabel("🔗 Ingresa el enlace o carga un archivo TXT:")
        label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(label)

        # Input + botones
        input_layout = QHBoxLayout()

        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("Pega aquí el enlace de YouTube o TikTok…")
        self.input_url.setStyleSheet(
            """
            background-color: #2b2b2b;
            border: 1px solid #555;
            padding: 5px;
            border-radius: 5px;
            """
        )
        input_layout.addWidget(self.input_url)

        self.btn_cargar_txt = QPushButton("📂 Cargar TXT")
        self.btn_cargar_txt.setStyleSheet(self.button_style())
        self.btn_cargar_txt.clicked.connect(self.cargar_archivo_txt)
        input_layout.addWidget(self.btn_cargar_txt)

        # Selector de concurrencia — SIEMPRE editable
        self.spin_concurrency = QSpinBox()
        self.spin_concurrency.setRange(1, 10)
        self.spin_concurrency.setValue(3)
        self.spin_concurrency.setToolTip("Número máximo de descargas simultáneas (1‑10)")
        input_layout.addWidget(self.spin_concurrency)

        layout.addLayout(input_layout)

        # Botón carpeta
        self.btn_carpeta = QPushButton("📁 Seleccionar Carpeta")
        self.btn_carpeta.setStyleSheet(self.button_style())
        self.btn_carpeta.clicked.connect(self.seleccionar_carpeta)
        layout.addWidget(self.btn_carpeta)

        # Botones acción
        action_layout = QHBoxLayout()
        self.btn_descargar = QPushButton("⬇ Descargar Video")
        self.btn_descargar.setStyleSheet(self.button_style())
        self.btn_descargar.clicked.connect(self.descargar_video)
        action_layout.addWidget(self.btn_descargar)

        self.btn_detener = QPushButton("🛑 Detener Descarga")
        self.btn_detener.setStyleSheet(self.button_style())
        self.btn_detener.clicked.connect(self.detener_descarga_manual)
        self.btn_detener.setEnabled(False)
        action_layout.addWidget(self.btn_detener)

        layout.addLayout(action_layout)

        # Área de log
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet(
            """
            background-color: #2b2b2b;
            border: 1px solid #555;
            padding: 5px;
            border-radius: 5px;
            """
        )
        layout.addWidget(self.log_area)

        # Conectar señales
        self.info_signal.connect(self._append_info)
        self.progress_signal.connect(self._update_progress)

    # ------------------------------------------------------------------
    # Helpers UI
    # ------------------------------------------------------------------
    @staticmethod
    def button_style() -> str:
        return (
            """
            QPushButton {
                background-color: #0078D7;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
                padding: 8px;
            }
            QPushButton:hover { background-color: #005A9E; }
            QPushButton:pressed { background-color: #003F7F; }
            """
        )

    def _append_info(self, msg: str):
        self.log_area.append(msg)
        QApplication.processEvents()

    # ---------------- Progress handling ----------------
    def _init_progress_lines(self, total: int):
        self.progress_lines.clear()
        placeholders = [f"[{i}/{total}] ⏳ Pendiente…" for i in range(1, total + 1)]
        for i in range(1, total + 1):
            self.progress_lines[i] = i - 1
        self.log_area.setPlainText("\n".join(placeholders))
        QApplication.processEvents()

    def _update_progress(self, idx: int, text: str):
        lines = self.log_area.toPlainText().split("\n")
        line_idx = self.progress_lines.get(idx)
        if line_idx is None:
            return
        if line_idx >= len(lines):
            lines.append(text)
            self.progress_lines[idx] = len(lines) - 1
        else:
            lines[line_idx] = text
        self.log_area.setPlainText("\n".join(lines))
        cursor = self.log_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_area.setTextCursor(cursor)
        QApplication.processEvents()

    # ------------------------------------------------------------------
    # Seleccionar carpeta
    # ------------------------------------------------------------------
    def seleccionar_carpeta(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de destino", self.carpeta_destino)
        if carpeta:
            self.carpeta_destino = carpeta
            self.info_signal.emit(f"📁 Carpeta seleccionada: {self.carpeta_destino}")

    # ------------------------------------------------------------------
    # Descarga individual desde URL
    # ------------------------------------------------------------------
    def descargar_video(self):
        url = self.input_url.text().strip()
        if not url:
            self.info_signal.emit("⚠️ Por favor, ingresa un enlace válido.")
            return
        self._prepare_and_start([url])

    # ------------------------------------------------------------------
    # Cargar TXT
    # ------------------------------------------------------------------
    def cargar_archivo_txt(self):
        archivo, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo de enlaces", "", "Archivos de texto (*.txt)")
        if not archivo:
            return
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                urls = [u.strip() for u in f if u.strip()]
        except Exception as exc:
            self.info_signal.emit(f"❌ Error al leer el archivo: {exc}")
            return
        if not urls:
            self.info_signal.emit("⚠️ El archivo está vacío o no contiene enlaces válidos.")
            return
        self._prepare_and_start(urls)

    # ------------------------------------------------------------------
    # Preparar lista y lanzar descargas después de listar
    # ------------------------------------------------------------------
    def _prepare_and_start(self, urls: list[str]):
        self.pending_urls = urls
        self.total_videos = len(urls)
        self.detener_descarga = False
        self.btn_detener.setEnabled(True)

        # 1) Mostrar lista primero
        self._init_progress_lines(self.total_videos)
        self.info_signal.emit(f"🚀 Preparado para descargar {self.total_videos} videos…")

        # 2) Programar inicio tras un ciclo del event‑loop para asegurar que la lista ya se renderizó
        QTimer.singleShot(100, self._start_downloads)

    # ------------------------------------------------------------------
    # Iniciar descargas con concurrencia definida por usuario
    # ------------------------------------------------------------------
    def _start_downloads(self):
        if self.detener_descarga:
            return
        workers = self.spin_concurrency.value() or 1
        self.info_signal.emit(f"⬇ Iniciando descargas (máx {workers} simultáneas)…")

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._descargar, url, idx): url for idx, url in enumerate(self.pending_urls, 1)}
            for future in concurrent.futures.as_completed(futures):
                if self.detener_descarga:
                    break
        self.btn_detener.setEnabled(False)

    # ------------------------------------------------------------------
    # Descarga individual
    # ------------------------------------------------------------------
    def _descargar(self, url: str, idx: int):
        if self.detener_descarga:
            return
        fecha = datetime.now().strftime("[%d_%m_%Y]")
        opciones = {
            "outtmpl": f"{self.carpeta_destino}/{fecha} %(title)s.%(ext)s",
            "format": "bestvideo+bestaudio/best",
            "progress_hooks": [self._hook(idx)],
            "noprogress": False,
            "concurrent_fragment_downloads": 4,
        }
        try:
            with yt_dlp.YoutubeDL(opciones) as ydl:
                info = ydl.extract_info(url, download=True)
                archivo = ydl.prepare_filename(info)
            self.progress_signal.emit(idx, f"[{idx}/{self.total_videos}] ✔️ {Path(archivo).name}")
        except yt_dlp.utils.DownloadError as e:
            self.progress_signal.emit(idx, f"[{idx}/{self.total_videos}] ❌ Error: {e}")
        except Exception as e:
            self.progress_signal.emit(idx, f"[{idx}/{self.total_videos}] ⚠️ Error inesperado: {e}")

    # Hook progreso
    def _hook(self, idx: int):
        def inner(d):
            if d["status"] == "downloading":
                percent = d.get("_percent_str", "0%" ).strip()
                speed = d.get("_speed_str", "N/A").strip()
                eta = d.get("_eta_str", "N/A").strip()
                text = f"[{idx}/{self.total_videos}] ⬇ {percent} | {speed} | ETA {eta}"
                text = re.sub(r"\x1b\[[0-9;]*m", "", text)
                self.progress_signal.emit(idx, text)
        return inner

    # ------------------------------------------------------------------
    # Detener descargas
    # ------------------------------------------------------------------
    def detener_descarga_manual(self):
        self.detener_descarga = True
        self.info_signal.emit("🛑 Descarga detenida por el usuario.")


# ----------------------------------------------------------------------
# Ejecutar aplicación
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = DescargadorVideos()
    ventana.show()
    sys.exit(app.exec())
