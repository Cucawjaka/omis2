from abc import ABCMeta, abstractmethod
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal
from PySide6.QtGui import QCloseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from video_editor.contracts import IView
from video_editor.logic import (
    EditingService,
    ExportService,
    MediaService,
    PreviewService,
    ProjectService,
)
from video_editor.model import (
    AudioClip,
    AudioFile,
    ExportResult,
    ExportSettings,
    TextOverlay,
    VideoClip,
    VideoFile,
)

ARROW_PATH = (Path(__file__).parent / "assets" / "chevron-down.svg").as_posix()
STYLE = """
QWidget { background: transparent; color: #13151b; font: 14px 'Arial'; }
QWidget#view, QWidget#exportWindow, QDialog { background: #f6f7fa; }
QLabel#heading { font-size: 20px; font-weight: 600; }
QLabel#editorTitle { font-size: 19px; font-weight: 600; }
QLabel#sectionTitle { font-weight: 600; }
QLabel#muted { color: #6b717b; }
QPushButton { background: #282828; color: white; border: 0; border-radius: 6px;
              min-height: 34px; padding: 0 14px; }
QPushButton:hover { background: #414141; }
QPushButton:disabled { background: #b3b6bd; }
QLineEdit, QComboBox, QDoubleSpinBox {
    background: white; border: 1px solid #dadada; border-radius: 6px;
    min-height: 32px; padding: 0 12px;
}
QComboBox::drop-down { border: none; width: 30px; }
QFrame#panel { background: white; border: 1px solid #c3c8d2; border-radius: 7px; }
QFrame#projectCard, QFrame#detailPanel {
    background: #fbfcfd; border: 1px solid #c3c8d2; border-radius: 6px;
}
QFrame#projectCard[selected="true"] { border-color: #6f8dbb; }
QFrame#divider { background: #c3c8d2; border: none; }
QFrame#previewPanel { background: #242730; border: none; border-radius: 7px; }
QLabel#previewTitle { color: white; font-weight: 600; }
QLabel#preview { background: #030305; color: #cbd0d9;
                 border: 1px solid #51525c; border-radius: 4px; }
QPushButton#playPreview { background: white; color: #242730; border-radius: 18px;
                          padding: 0; min-height: 36px; }
QListWidget#mediaList { background: transparent; border: none; padding: 0; outline: none; }
QListWidget#mediaList::item { padding: 8px 1px; border-radius: 3px; }
QListWidget#mediaList::item:selected { background: #e1e9f5; color: #13151b; }
QScrollArea { border: none; background: transparent; }
""" + f'QComboBox::down-arrow {{ image: url("{ARROW_PATH}"); width: 10px; height: 10px; }}'


def button(text: str, action: Callable, name: str = "") -> QPushButton:
    control = QPushButton(text)
    control.setObjectName(name)
    control.clicked.connect(lambda checked=False: action())
    return control


def heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("heading")
    return label


class ViewMeta(ABCMeta, type(QWidget)):
    def __call__(cls, *args, **kwargs):
        if cls.__abstractmethods__:
            methods = ", ".join(sorted(cls.__abstractmethods__))
            raise TypeError(f"Абстрактное представление {cls.__name__}: {methods}")
        return super().__call__(*args, **kwargs)


class BaseView(QWidget, IView, metaclass=ViewMeta):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("view")
        self.setStyleSheet(STYLE)

    def show(self) -> None:
        super().show()

    @abstractmethod
    def refresh(self) -> None:
        self.update()

    def perform(self, action: Callable):
        try:
            return action()
        except (ValueError, OSError, KeyError) as error:
            QMessageBox.warning(self, "Не удалось выполнить действие", str(error))
            return None


class ProjectListUI(BaseView):
    projectOpened = Signal(object)
    quitRequested = Signal()

    def __init__(self, service: ProjectService) -> None:
        super().__init__()
        self.service = service
        self.selectedProjectId: int | None = None
        self.projectRows: dict[int, QFrame] = {}
        self.setWindowTitle("Video Editor — Видеопроекты")
        self.resize(978, 626)
        self.setMinimumSize(760, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(31, 26, 31, 21)
        layout.setSpacing(0)
        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(10)
        titles.addWidget(heading("Video Editor"))
        subtitle = QLabel("Видеопроекты")
        subtitle.setObjectName("muted")
        subtitle.setStyleSheet("font-weight: 600;")
        titles.addWidget(subtitle)
        top.addLayout(titles)
        top.addStretch()
        top.setSpacing(16)
        create = button("Новый проект", self.createProject, "createProject")
        create.setFixedWidth(142)
        top.addWidget(create, 0, Qt.AlignmentFlag.AlignTop)
        openButton = button("Открыть", self.openProject, "openProject")
        openButton.setFixedWidth(108)
        top.addWidget(openButton, 0, Qt.AlignmentFlag.AlignTop)
        top.addSpacing(48)
        layout.addLayout(top)
        layout.addSpacing(25)
        box = QFrame()
        box.setObjectName("panel")
        boxLayout = QVBoxLayout(box)
        boxLayout.setContentsMargins(15, 15, 15, 20)
        boxLayout.setSpacing(0)
        header = QHBoxLayout()
        header.setContentsMargins(8, 0, 10, 0)
        header.setSpacing(0)
        for title, width in (("Название проекта", 0), ("Дата изменения", 170), ("Действия", 168)):
            label = QLabel(title)
            label.setObjectName("sectionTitle")
            label.setFixedHeight(34)
            if width:
                label.setFixedWidth(width)
            if title == "Действия":
                label.setContentsMargins(20, 0, 0, 0)
            header.addWidget(label, 0 if width else 1)
        boxLayout.addLayout(header)
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        boxLayout.addWidget(divider)
        boxLayout.addSpacing(12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.rowsLayout = QVBoxLayout(content)
        self.rowsLayout.setContentsMargins(0, 0, 0, 0)
        self.rowsLayout.setSpacing(15)
        self.rowsLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(content)
        boxLayout.addWidget(scroll, 1)
        self.emptyLabel = QLabel("Выберите проект или создайте новый.")
        self.emptyLabel.setObjectName("muted")
        boxLayout.addWidget(self.emptyLabel)
        layout.addWidget(box, 1)
        layout.addSpacing(25)
        bottom = QHBoxLayout()
        bottom.addStretch()
        quitButton = button("Выйти", self.quitRequested.emit, "quitApplication")
        quitButton.setFixedWidth(108)
        bottom.addWidget(quitButton)
        bottom.addSpacing(20)
        layout.addLayout(bottom)

    def showProjects(self) -> None:
        self.refresh()
        self.show()

    def refresh(self) -> None:
        self.perform(self._loadProjects)

    def _loadProjects(self) -> None:
        projects = self.service.listProjects()
        while self.rowsLayout.count():
            item = self.rowsLayout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.projectRows.clear()
        for project in projects:
            card = QFrame()
            card.setObjectName("projectCard")
            card.setProperty("projectId", project.projectId)
            card.setFixedHeight(76)
            row = QHBoxLayout(card)
            row.setContentsMargins(20, 8, 10, 8)
            row.setSpacing(0)
            row.setAlignment(Qt.AlignmentFlag.AlignTop)
            name = QLabel(project.name)
            name.setObjectName("sectionTitle")
            name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            name.setToolTip(project.name)
            name.setFixedHeight(34)
            date = QLabel(project.updatedAt.strftime("%d.%m.%Y"))
            date.setObjectName("muted")
            date.setFixedWidth(170)
            date.setFixedHeight(34)
            row.addWidget(name, 1)
            row.addWidget(date)
            actions = QHBoxLayout()
            actions.setSpacing(9)
            for text, action, width in (("Открыть", self.openProject, 84), ("Удалить", self.deleteProject, 75)):
                control = button(text, lambda pid=project.projectId, handler=action: handler(pid))
                control.setFixedWidth(width)
                actions.addWidget(control)
            row.addLayout(actions)
            for target in (card, name, date):
                target.setProperty("projectId", project.projectId)
                target.installEventFilter(self)
            self.projectRows[project.projectId] = card
            self.rowsLayout.addWidget(card)
        if self.selectedProjectId not in self.projectRows:
            self.selectedProjectId = None
        self._markSelection()
        self.emptyLabel.setText(
            "Выберите проект или создайте новый."
            if projects
            else "Проектов пока нет. Нажмите «Новый проект», чтобы начать."
        )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        projectId = watched.property("projectId")
        if projectId is not None and event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
            self.selectedProjectId = int(projectId)
            self._markSelection()
            if event.type() == QEvent.Type.MouseButtonDblClick:
                self.openProject(self.selectedProjectId)
            return True
        return super().eventFilter(watched, event)

    def _markSelection(self) -> None:
        for projectId, card in self.projectRows.items():
            card.setProperty("selected", projectId == self.selectedProjectId)
            card.style().unpolish(card)
            card.style().polish(card)

    def createProject(self, name: str | None = None) -> None:
        accepted = True
        if name is None:
            name, accepted = QInputDialog.getText(self, "Новый проект", "Название проекта:")
        if accepted:
            project = self.perform(lambda: self.service.createProject(name))
            if project is not None:
                self.projectOpened.emit(project)

    def _selectedId(self) -> int:
        if self.selectedProjectId is None:
            raise ValueError("Сначала выберите проект в списке.")
        return self.selectedProjectId

    def openProject(self, projectId: int | None = None) -> None:
        if isinstance(projectId, bool):
            projectId = None

        def openSelected():
            pid = projectId if projectId is not None else self._selectedId()
            return self.service.openProject(pid)

        project = self.perform(openSelected)
        if project is not None:
            self.projectOpened.emit(project)

    def deleteProject(self, projectId: int | None = None) -> None:
        pid = projectId if projectId is not None else self.perform(self._selectedId)
        if pid is None:
            return
        answer = QMessageBox.question(
            self, "Удаление проекта", "Удалить выбранный проект?"
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.perform(lambda: self.service.deleteProject(pid))
            self.refresh()


class MediaImportDialog(QDialog):
    def __init__(self, kind: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setObjectName(f"import_{kind}")
        self.setStyleSheet(STYLE)
        title = "Добавление видео" if kind == "video" else "Добавление аудио"
        material = "видеофайл" if kind == "video" else "аудиофайл"
        self.setWindowTitle(title)
        self.resize(586, 432 if kind == "video" else 439)
        self.setMinimumSize(560, 432)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(23, 16 if kind == "video" else 19, 23, 17)
        layout.setSpacing(0)
        titleLabel = heading(title)
        titleLabel.setFixedHeight(26)
        layout.addWidget(titleLabel)
        layout.addSpacing(9)
        subtitle = QLabel(f"Выберите {material}, который будет добавлен в текущий проект.")
        subtitle.setObjectName("muted")
        subtitle.setFixedHeight(20)
        layout.addWidget(subtitle)
        layout.addSpacing(32)
        pathLabel = QLabel("Путь к видеофайлу" if kind == "video" else "Путь к аудиофайлу")
        pathLabel.setFixedHeight(20)
        layout.addWidget(pathLabel)
        layout.addSpacing(5)
        self.pathEdit = QLineEdit()
        self.pathEdit.setObjectName("mediaPath")
        self.pathEdit.setFixedHeight(34)
        layout.addWidget(self.pathEdit)
        layout.addSpacing(33)
        choose = button("Выбрать файл", self.chooseFile, "chooseMedia")
        choose.setFixedWidth(125)
        layout.addWidget(choose, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(25)
        box = QFrame()
        box.setObjectName("detailPanel")
        box.setFixedHeight(100)
        boxLayout = QGridLayout(box)
        boxLayout.setContentsMargins(16, 15, 16, 20)
        boxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        boxLayout.setVerticalSpacing(8)
        boxLayout.setHorizontalSpacing(0)
        infoTitle = QLabel("Информация о файле")
        infoTitle.setObjectName("sectionTitle")
        infoTitle.setFixedHeight(20)
        boxLayout.addWidget(infoTitle, 0, 0, 1, 2)
        self.info = QLabel("Файл не выбран.")
        self.info.setFixedWidth(204)
        self.info.setFixedHeight(20)
        self.metadata = QLabel("")
        self.metadata.setObjectName("muted")
        self.metadata.setFixedHeight(20)
        boxLayout.addWidget(self.info, 1, 0)
        boxLayout.addWidget(self.metadata, 1, 1)
        boxLayout.setColumnStretch(1, 1)
        boxLayout.setColumnMinimumWidth(0, 204)
        layout.addWidget(box)
        self.pathEdit.textChanged.connect(self.showFileInfo)
        layout.addSpacing(27)
        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addStretch()
        cancel = button("Отмена", self.reject, "cancelImport")
        cancel.setFixedWidth(117)
        actions.addWidget(cancel)
        confirm = button(
            "Добавить видео" if kind == "video" else "Добавить аудио",
            self.accept, "confirmImport",
        )
        confirm.setFixedWidth(136)
        actions.addWidget(confirm)
        layout.addLayout(actions)

    def chooseFile(self) -> None:
        fileFilter = (
            "Видео (*.mp4 *.mov *.mkv *.avi *.webm)"
            if self.kind == "video"
            else "Аудио (*.mp3 *.wav *.ogg *.aac *.flac *.m4a)"
        )
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать файл", "", fileFilter)
        if path:
            self.pathEdit.setText(path)

    def showFileInfo(self, path: str) -> None:
        file = Path(path).expanduser()
        metadata = (
            "00:00:10 · 1920×1080 · 30 FPS"
            if self.kind == "video"
            else "00:00:10 · 192 кбит/с"
        )
        self.info.setText(file.name if file.is_file() else "Файл не найден.")
        self.info.setToolTip(file.name)
        self.metadata.setText(metadata if file.is_file() else "")

    def accept(self) -> None:
        if not Path(self.pathEdit.text()).expanduser().is_file():
            QMessageBox.warning(self, "Выбор файла", "Укажите существующий файл.")
            return
        super().accept()


class ProjectEditorUI(BaseView):
    projectClosed = Signal()
    exportRequested = Signal()

    def __init__(
        self,
        editingService: EditingService,
        mediaService: MediaService,
        previewService: PreviewService,
        projectService: ProjectService,
    ) -> None:
        super().__init__()
        self.editingService = editingService
        self.mediaService = mediaService
        self.previewService = previewService
        self.projectService = projectService
        self.selectedClipId: int | None = None
        self.importDialog: MediaImportDialog | None = None
        self.editDialog: QDialog | None = None
        self.resize(1180, 672)
        self.setMinimumSize(820, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 10, 11, 0)
        layout.setSpacing(0)
        top = QHBoxLayout()
        top.setSpacing(12)
        self.title = heading("Video Editor")
        self.title.setObjectName("editorTitle")
        self.title.setContentsMargins(0, 0, 0, 6)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        top.addWidget(self.title, 1)
        for text, action, name, width in (
            ("Сохранить", self.saveProject, "saveProject", 108),
            ("Предпросмотр", self.startPreview, "startPreview", 125),
            ("Экспорт", self.exportRequested.emit, "openExport", 108),
        ):
            control = button(text, action, name)
            control.setFixedWidth(width)
            top.addWidget(control)
        top.addSpacing(30)
        layout.addLayout(top)
        layout.addSpacing(26)
        main = QHBoxLayout()
        main.setSpacing(23)
        mediaBox = QFrame()
        mediaBox.setObjectName("panel")
        mediaLayout = QVBoxLayout(mediaBox)
        mediaLayout.setContentsMargins(14, 19, 14, 12)
        mediaLayout.setSpacing(14)
        mediaTitle = QLabel("Медиаматериалы")
        mediaTitle.setObjectName("sectionTitle")
        mediaLayout.addWidget(mediaTitle)
        imports = QHBoxLayout()
        imports.setSpacing(9)
        for text, action, name in (("+ Видео", self.importVideo, "importVideo"), ("+ Аудио", self.importAudio, "importAudio")):
            control = button(text, action, name)
            control.setFixedWidth(83)
            imports.addWidget(control)
        imports.addStretch()
        mediaLayout.addLayout(imports)
        mediaLayout.addSpacing(3)
        self.mediaList = QListWidget()
        self.mediaList.setObjectName("mediaList")
        self.mediaList.setToolTip("Дважды нажмите на файл, чтобы добавить его на временную шкалу.")
        self.mediaList.itemDoubleClicked.connect(lambda item: self.placeSelectedMedia())
        mediaLayout.addWidget(self.mediaList)
        mediaBox.setFixedWidth(225)
        main.addWidget(mediaBox)
        self.previewBox = QFrame()
        self.previewBox.setObjectName("previewPanel")
        self.previewTitle = QLabel("Предварительный просмотр", self.previewBox)
        self.previewTitle.setObjectName("previewTitle")
        self.previewLabel = QLabel("", self.previewBox)
        self.previewLabel.setObjectName("preview")
        self.previewLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previewLabel.setWordWrap(True)
        self.playButton = button("▶", self.startPreview, "playPreview")
        self.playButton.setParent(self.previewBox)
        self.playButton.setFixedSize(67, 36)
        main.addWidget(self.previewBox, 1)
        layout.addLayout(main, 1)
        layout.addSpacing(24)
        timelineBox = QFrame()
        timelineBox.setObjectName("panel")
        timelineBox.setFixedHeight(160)
        timelineLayout = QVBoxLayout(timelineBox)
        timelineLayout.setContentsMargins(14, 16, 14, 4)
        timelineLayout.setSpacing(21)
        timelineTitle = QLabel("Временная шкала")
        timelineTitle.setObjectName("sectionTitle")
        timelineLayout.addWidget(timelineTitle)
        timelineBody = QHBoxLayout()
        timelineBody.setSpacing(60)
        tracks = QVBoxLayout()
        tracks.setSpacing(10)
        tracks.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.trackWidgets: dict[str, QWidget] = {}
        for kind, label in [("video", "Video"), ("audio", "Audio"), ("text", "Text")]:
            row = QHBoxLayout()
            row.setSpacing(8)
            name = QLabel(label)
            name.setObjectName("muted")
            name.setFixedWidth(54)
            row.addWidget(name)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFixedHeight(27)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            track = QWidget()
            self.trackWidgets[kind] = track
            scroll.setWidget(track)
            row.addWidget(scroll, 1)
            tracks.addLayout(row)
        timelineBody.addLayout(tracks, 7)
        actions = QVBoxLayout()
        actions.setSpacing(18)
        clipActions = QHBoxLayout()
        clipActions.setSpacing(9)
        for text, action, name, width in (
            ("Обрезать", self.trimClip, "trimClip", 87),
            ("Разделить", self.splitClip, "splitClip", 92),
            ("Переместить", self.moveClip, "moveClip", 100),
        ):
            control = button(text, action, name)
            control.setFixedWidth(width)
            control.setStyleSheet("padding: 0 8px;")
            clipActions.addWidget(control)
        clipActions.addStretch()
        actions.addLayout(clipActions)
        addText = button("Добавить текст", self.addTextOverlay, "addText")
        addText.setFixedWidth(138)
        actions.addWidget(addText, 0, Qt.AlignmentFlag.AlignLeft)
        actions.addStretch()
        timelineBody.addLayout(actions, 4)
        timelineLayout.addLayout(timelineBody)
        layout.addWidget(timelineBox)
        self.statusLabel = QLabel(self)
        self.statusLabel.hide()

    def openEditor(self) -> None:
        self.selectedClipId = None
        self.previewLabel.clear()
        self.statusLabel.setText("Выберите видеоклип на шкале для редактирования.")
        self.displayEditor()
        self.show()

    def displayEditor(self) -> None:
        project = self.mediaService.project
        if project is not None:
            self.title.setText(f"Video Editor — {project.name}")
            self.title.setToolTip(self.title.text())
            self.setWindowTitle(f"Video Editor — {project.name}")
        self.refresh()

    def refresh(self) -> None:
        self.mediaList.clear()
        project = self.mediaService.project
        if project is not None:
            for media in project.mediaFiles:
                item = QListWidgetItem(media.fileName)
                item.setData(Qt.ItemDataRole.UserRole, media.mediaId)
                item.setToolTip(
                    f"{media.filePath}\n\nДважды нажмите, чтобы добавить на временную шкалу."
                )
                item.setSizeHint(QSize(0, 34))
                self.mediaList.addItem(item)
        self.displayTimeline()

    def displayTimeline(self) -> None:
        colors = {"video": "#e1e9f5", "audio": "#e1f2e7", "text": "#faeed2"}
        timeline = self.editingService.getTimeline()
        pixelsPerSecond = max(1, self.trackWidgets["video"].width()) / max(10, timeline.duration)
        for track in self.trackWidgets.values():
            for widget in track.findChildren(QPushButton):
                widget.hide()
                widget.deleteLater()
        videoIndex = 0
        for item in timeline.getElements():
            if isinstance(item, TextOverlay):
                label = item.text
            elif isinstance(item, VideoClip):
                videoIndex += 1
                label = f"clip {videoIndex}"
            elif isinstance(item, AudioClip):
                label = item.source.fileName
            else:
                continue
            clip = QPushButton(
                label,
                self.trackWidgets[item.kind],
            )
            start = round(item.position * pixelsPerSecond)
            end = round((item.position + item.duration) * pixelsPerSecond)
            clip.setGeometry(
                start, 0, max(1, end - start - 4), 27,
            )
            clip.setToolTip(f"{label}: начало {item.position:g} с, длительность {item.duration:g} с")
            if isinstance(item, VideoClip):
                clip.setCheckable(True)
                clip.setChecked(item.clipId == self.selectedClipId)
                clip.clicked.connect(
                    lambda checked=False, cid=item.clipId: self.selectClip(cid)
                )
            border = "1px solid #6f8dbb" if clip.isChecked() else "1px solid #c3c8d2"
            color = "#ece4f5" if item.kind == "video" and videoIndex % 2 == 0 else colors[item.kind]
            clip.setStyleSheet(
                f"QPushButton {{ background: {color}; color: #282828; min-height: 0; "
                f"border: {border}; padding: 0 3px; border-radius: 3px; }}"
            )
            availableWidth = max(0, clip.width() - 10)
            metrics = clip.fontMetrics()
            clip.setText(
                metrics.elidedText(label, Qt.TextElideMode.ElideRight, availableWidth)
            )
            clip.show()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "playButton"):
            self.previewTitle.setGeometry(25, 18, self.previewBox.width() - 50, 20)
            width = min(round(self.previewBox.width() * 0.5), round(max(40, self.previewBox.height() - 130) * 674 / 386))
            height = round(width * 386 / 674)
            self.previewLabel.setGeometry((self.previewBox.width() - width) // 2, 55, width, height)
            self.playButton.move((self.previewBox.width() - 67) // 2, 55 + height + 21)
            self.displayTimeline()

    def selectClip(self, clipId: int) -> None:
        self.selectedClipId = clipId
        self.statusLabel.setText(
            "Видеоклип выбран. Доступны обрезка, разделение и перемещение."
        )
        self.displayTimeline()

    def _selectedClip(self) -> VideoClip:
        if self.selectedClipId is None:
            raise ValueError("Сначала нажмите на видеоклип на временной шкале.")
        return self.editingService.getTimeline().getVideoClip(self.selectedClipId)

    def importVideo(self) -> None:
        self._openImport("video")

    def importAudio(self) -> None:
        self._openImport("audio")

    def _openImport(self, kind: str) -> None:
        dialog = MediaImportDialog(kind, self)
        self.importDialog = dialog
        dialog.accepted.connect(lambda: self._finishImport(dialog))
        dialog.open()

    def _finishImport(self, dialog: MediaImportDialog) -> None:
        def register():
            path = dialog.pathEdit.text()
            if dialog.kind == "video":
                self.mediaService.addVideoFile(path)
            else:
                self.mediaService.addAudioFile(path)
            self.refresh()
            self.statusLabel.setText(
                "Файл добавлен. Дважды нажмите на него для размещения на шкале."
            )

        self.perform(register)

    def placeSelectedMedia(self) -> None:
        def place():
            selected = self.mediaList.currentItem()
            if selected is None:
                raise ValueError("Выберите файл в списке медиаматериалов.")
            project = self.mediaService.project
            if project is None:
                raise ValueError("Сначала откройте проект.")
            mediaId = selected.data(Qt.ItemDataRole.UserRole)
            media = next(
                m for m in project.mediaFiles if m.mediaId == mediaId
            )
            if isinstance(media, VideoFile):
                self.addVideoClip(media)
            elif isinstance(media, AudioFile):
                self.addAudioClip(media)

        self.perform(place)

    def addVideoClip(self, videoFile: VideoFile) -> None:
        clip = self.editingService.addVideoClip(videoFile)
        self.selectedClipId = clip.clipId
        self.displayTimeline()

    def addAudioClip(self, audioFile: AudioFile) -> None:
        self.editingService.addAudioClip(audioFile)
        self.displayTimeline()

    def _fields(
        self, title: str, fields: list[tuple[str, str | float]], action: Callable
    ) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(430)
        form = QFormLayout(dialog)
        editors = []
        for label, value in fields:
            if isinstance(value, str):
                editor = QLineEdit(value)
            else:
                editor = QDoubleSpinBox()
                editor.setRange(0, 86400)
                editor.setDecimals(2)
                editor.setValue(float(value))
                editor.setSuffix(" с")
            form.addRow(label, editor)
            editors.append(editor)
        controls = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        controls.button(QDialogButtonBox.StandardButton.Ok).setText("Применить")
        controls.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        form.addRow(controls)

        def apply():
            try:
                values = [
                    e.text() if isinstance(e, QLineEdit) else e.value() for e in editors
                ]
                action(*values)
                self.displayTimeline()
            except ValueError as error:
                QMessageBox.warning(dialog, title, str(error))
                return
            dialog.accept()

        controls.accepted.connect(apply)
        controls.rejected.connect(dialog.reject)
        self.editDialog = dialog
        dialog.open()

    def trimClip(
        self, clipId: int | None = None,
        startTime: float | None = None, endTime: float | None = None,
    ) -> None:
        if clipId is not None:
            def trim():
                if startTime is None or endTime is None:
                    raise ValueError("Укажите начало и окончание фрагмента.")
                self.editingService.trimClip(clipId, startTime, endTime)
                self.displayTimeline()
            self.perform(trim)
            return
        clip = self.perform(self._selectedClip)
        if clip is not None:
            self._fields(
                "Обрезать видеоклип",
                [
                    ("Начало в исходном файле", clip.sourceStartTime),
                    ("Окончание в исходном файле", clip.sourceEndTime),
                ],
                lambda start, end: self.editingService.trimClip(
                    clip.clipId, start, end
                ),
            )

    def splitClip(self, clipId: int | None = None, splitTime: float | None = None) -> None:
        if clipId is not None:
            def splitSelected():
                if splitTime is None:
                    raise ValueError("Укажите момент разделения.")
                self.editingService.splitClip(clipId, splitTime)
                self.selectedClipId = None
                self.displayTimeline()
            self.perform(splitSelected)
            return
        clip = self.perform(self._selectedClip)
        if clip is not None:
            def split(time):
                self.editingService.splitClip(clip.clipId, time)
                self.selectedClipId = None

            self._fields(
                "Разделить видеоклип",
                [
                    (
                        "Момент в исходном файле",
                        (clip.sourceStartTime + clip.sourceEndTime) / 2,
                    ),
                ],
                split,
            )

    def moveClip(self, clipId: int | None = None, newPosition: float | None = None) -> None:
        if clipId is not None:
            def move():
                if newPosition is None:
                    raise ValueError("Укажите позицию клипа.")
                self.editingService.moveClip(clipId, newPosition)
                self.displayTimeline()
            self.perform(move)
            return
        clip = self.perform(self._selectedClip)
        if clip is not None:
            self._fields(
                "Переместить видеоклип",
                [("Позиция на шкале", clip.position)],
                lambda position: self.editingService.moveClip(clip.clipId, position),
            )

    def addTextOverlay(
        self, text: str | None = None,
        startTime: float | None = None, endTime: float | None = None,
    ) -> None:
        if text is not None:
            def add():
                if startTime is None or endTime is None:
                    raise ValueError("Укажите интервал отображения текста.")
                self.editingService.addTextOverlay(text, startTime, endTime)
                self.displayTimeline()
            self.perform(add)
            return
        self._fields(
            "Добавить текст",
            [
                ("Текст", ""),
                ("Начало отображения", 0.0),
                ("Окончание отображения", 5.0),
            ],
            self.editingService.addTextOverlay,
        )

    def startPreview(self) -> None:
        self.previewService.generatePreview()
        self.displayPreview()

    def displayPreview(self) -> None:
        timeline = self.editingService.getTimeline()
        self.previewLabel.setToolTip(
            f"Предпросмотр проекта\n\nЭлементов на шкале: {len(timeline.elements)}\n"
            f"Продолжительность: {timeline.duration:g} с\n\n"
            "Воспроизведение видео в прототипе не реализовано."
        )

    def saveProject(self) -> None:
        def save():
            project = self.mediaService.project
            if project is None:
                raise ValueError("Сначала откройте проект.")
            self.projectService.saveProject(project.projectId)
            self.statusLabel.setText("Проект сохранён.")

        self.perform(save)

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            if self.mediaService.project is not None:
                self.projectService.saveProject(self.mediaService.project.projectId)
        except (ValueError, OSError, KeyError) as error:
            QMessageBox.warning(self, "Сохранение проекта", str(error))
            event.ignore()
            return
        self.projectClosed.emit()
        event.accept()


class ExportUI(BaseView):
    finished = Signal()

    def __init__(self, exportService: ExportService) -> None:
        super().__init__()
        self.exportService = exportService
        self.result: ExportResult | None = None
        self.setWindowTitle("Экспорт видеоролика")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setObjectName("exportWindow")
        self.resize(582, 557)
        self.setMinimumSize(520, 550)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 27, 45)
        layout.setSpacing(0)
        title = heading("Экспорт видеоролика")
        title.setFixedHeight(26)
        layout.addWidget(title)
        layout.addSpacing(9)
        subtitle = QLabel("Настройте параметры итогового файла.")
        subtitle.setObjectName("muted")
        subtitle.setFixedHeight(20)
        layout.addWidget(subtitle)
        layout.addSpacing(32)
        form = QGridLayout()
        form.setHorizontalSpacing(33)
        form.setVerticalSpacing(7)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        self.formatEdit = QComboBox()
        self.formatEdit.addItems(["MP4", "MOV", "WEBM"])
        self.resolutionEdit = QComboBox()
        self.resolutionEdit.addItems(["1920×1080", "1080×1920", "1280×720", "720×1280"])
        self.frameRateEdit = QComboBox()
        for rate in (24, 25, 30, 60):
            self.frameRateEdit.addItem(f"{rate} FPS", rate)
        self.frameRateEdit.setCurrentIndex(2)
        self.pathEdit = QLineEdit()
        self.pathEdit.setPlaceholderText("Путь к итоговому видеофайлу")
        form.addWidget(QLabel("Формат"), 0, 0)
        form.addWidget(QLabel("Разрешение"), 0, 1)
        form.addWidget(self.formatEdit, 1, 0)
        form.addWidget(self.resolutionEdit, 1, 1)
        form.setRowMinimumHeight(2, 29)
        form.addWidget(QLabel("Частота кадров"), 3, 0)
        form.addWidget(self.frameRateEdit, 4, 0)
        form.setRowMinimumHeight(5, 26)
        form.addWidget(QLabel("Путь сохранения"), 6, 0, 1, 2)
        form.addWidget(self.pathEdit, 7, 0, 1, 2)
        for editor in (self.formatEdit, self.resolutionEdit, self.frameRateEdit, self.pathEdit):
            editor.setFixedHeight(34)
        layout.addLayout(form)
        layout.addSpacing(42)
        statusBox = QFrame()
        statusBox.setObjectName("detailPanel")
        statusBox.setMinimumHeight(59)
        statusLayout = QHBoxLayout(statusBox)
        statusLayout.setContentsMargins(16, 12, 16, 12)
        statusLayout.setSpacing(36)
        statusTitle = QLabel("Статус")
        statusTitle.setObjectName("sectionTitle")
        statusLayout.addWidget(statusTitle, 0, Qt.AlignmentFlag.AlignTop)
        self.statusLabel = QLabel("Готов к экспорту")
        self.statusLabel.setObjectName("muted")
        self.statusLabel.setWordWrap(True)
        statusLayout.addWidget(self.statusLabel, 1, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(statusBox)
        layout.addSpacing(32)
        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addStretch()
        cancelButton = button("Отмена", self.close, "cancelExport")
        cancelButton.setFixedWidth(109)
        actions.addWidget(cancelButton)
        exportButton = button("Экспортировать", self.startExport, "startExport")
        exportButton.setFixedWidth(138)
        actions.addWidget(exportButton)
        self.doneButton = button("Завершить", self.close, "finishExport")
        self.doneButton.hide()
        actions.addWidget(self.doneButton)
        layout.addLayout(actions)

    def showExportSettings(self) -> None:
        self.refresh()
        self.show()

    def refresh(self) -> None:
        self.result = None
        self.doneButton.hide()
        self.statusLabel.setText("Готов к экспорту")
        extension = self.formatEdit.currentText().lower()
        self.pathEdit.setText(str(Path.cwd() / f"output.{extension}"))

    def startExport(self, format: str | None = None, resolution: str | None = None) -> None:
        if format is not None:
            self.formatEdit.setCurrentText(format)
        if resolution is not None:
            self.resolutionEdit.setCurrentText(resolution)
        def export():
            if not self.pathEdit.text().strip():
                raise ValueError("Укажите путь сохранения.")
            settings = ExportSettings(
                format=self.formatEdit.currentText(),
                resolution=self.resolutionEdit.currentText(),
                frameRate=float(self.frameRateEdit.currentData()),
                outputPath=self.pathEdit.text().strip(),
            )
            self.result = self.exportService.exportVideo(settings)
            self.displayExportResult()

        self.perform(export)

    def displayExportResult(self) -> None:
        if self.result is not None and self.result.success:
            self.statusLabel.setText(f"Видео сохранено: {self.result.outputPath}")
        else:
            self.statusLabel.setText(
                "Демонстрация экспорта завершена. Генерация видео не реализована; файл не создан."
            )
        self.doneButton.show()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.finished.emit()
        event.accept()
