import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from video_editor.contracts import (
    IMediaRepository,
    IPreviewRenderer,
    IProjectRepository,
    IVideoExporter,
)
from video_editor.factories import ServiceFactory, UIFactory
from video_editor.infrastructure import (
    DependencyContainer,
    FileMediaRepository,
    LocalProjectRepository,
    PreviewRenderer,
    VideoExporter,
)
from video_editor.logic import (
    EditingService,
    ExportService,
    MediaService,
    PreviewService,
    ProjectService,
)
from video_editor.model import VideoProject
from video_editor.presentation import ExportUI, ProjectEditorUI, ProjectListUI


class ApplicationConfigurator:
    def __init__(self, application: "Application") -> None:
        self.application = application
        self.container = application.container

    def configure(self) -> None:
        self.registerInfrastructure()
        self.createServices()
        self.createViews()
        self.container.configure()
        self.connectComponents()

    def registerInfrastructure(self) -> None:
        self.container.register(
            IProjectRepository,
            lambda: LocalProjectRepository(self.application.dataDirectory),
        )
        self.container.register(IMediaRepository, FileMediaRepository)
        self.container.register(IPreviewRenderer, PreviewRenderer)
        self.container.register(IVideoExporter, VideoExporter)

    def createServices(self) -> None:
        factory = ServiceFactory(self.container)
        self.container.serviceFactory = factory
        self.container.register(ProjectService, factory.createProjectService)
        self.container.register(MediaService, factory.createMediaService)
        self.container.register(EditingService, factory.createEditingService)
        self.container.register(PreviewService, factory.createPreviewService)
        self.container.register(ExportService, factory.createExportService)

    def createViews(self) -> None:
        factory = UIFactory(self.container)
        self.container.uiFactory = factory
        self.container.register(ProjectListUI, factory.createProjectListUI)
        self.container.register(ProjectEditorUI, factory.createProjectEditorUI)
        self.container.register(ExportUI, factory.createExportUI)
        self.application.projectListUI = self.container.resolve(ProjectListUI)
        self.application.projectEditorUI = self.container.resolve(ProjectEditorUI)
        self.application.exportUI = self.container.resolve(ExportUI)

    def connectComponents(self) -> None:
        app = self.application
        app.projectListUI.projectOpened.connect(app.openProject)
        app.projectListUI.quitRequested.connect(app.shutdown)
        app.projectEditorUI.projectClosed.connect(app.showProjectList)
        app.projectEditorUI.exportRequested.connect(app.showExport)
        app.exportUI.finished.connect(app.projectEditorUI.show)


class Application:
    projectListUI: ProjectListUI
    projectEditorUI: ProjectEditorUI
    exportUI: ExportUI

    def __init__(self, dataDirectory: Path | None = None) -> None:
        self.dataDirectory = (
            dataDirectory if dataDirectory is not None else Path("data/projects")
        )
        self.container = DependencyContainer()
        self.configurator = ApplicationConfigurator(self)

    def initialize(self) -> None:
        instance = QApplication.instance()
        if instance is None:
            qtArgs = sys.argv[:1]
            if sys.platform == "linux":
                qtArgs.extend(["-platformtheme", "generic"])
            instance = QApplication(qtArgs)
        if not isinstance(instance, QApplication):
            raise TypeError("Для графического интерфейса требуется QApplication.")
        self.qt = instance
        self.qt.setApplicationName("Video Editor")
        self.configurator.configure()

    def openProject(self, project: VideoProject) -> None:
        self.container.resolve(EditingService).timeline = project.timeline
        self.container.resolve(MediaService).project = project
        self.container.resolve(PreviewService).timeline = project.timeline
        self.container.resolve(ExportService).project = project
        self.projectEditorUI.openEditor()
        self.projectListUI.hide()

    def showProjectList(self) -> None:
        self.projectListUI.showProjects()

    def showExport(self) -> None:
        self.exportUI.showExportSettings()

    def run(self) -> None:
        self.projectListUI.showProjects()
        self.qt.exec()

    def shutdown(self) -> None:
        self.qt.quit()

    @staticmethod
    def main(args: list[str] | None = None) -> None:
        parser = argparse.ArgumentParser(
            description="Прототип редактора коротких видеороликов"
        )
        parser.add_argument(
            "--data-dir",
            type=Path,
            default=Path("data/projects"),
            help="Каталог JSON-проектов (по умолчанию data/projects)",
        )
        options = parser.parse_args(args)
        application = Application(options.data_dir)
        application.initialize()
        application.run()


def main() -> None:
    Application.main()
