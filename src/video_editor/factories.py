from video_editor.contracts import (
    IMediaRepository,
    IPreviewRenderer,
    IProjectRepository,
    IVideoExporter,
)
from video_editor.infrastructure import DependencyContainer
from video_editor.logic import (
    EditingService,
    ExportService,
    MediaService,
    PreviewService,
    ProjectService,
)
from video_editor.presentation import ExportUI, ProjectEditorUI, ProjectListUI


class ServiceFactory:
    def __init__(self, container: DependencyContainer) -> None:
        self.container = container

    def createProjectService(self) -> ProjectService:
        return ProjectService(self.container.resolve(IProjectRepository))

    def createMediaService(self) -> MediaService:
        return MediaService(self.container.resolve(IMediaRepository))

    def createEditingService(self) -> EditingService:
        return EditingService()

    def createPreviewService(self) -> PreviewService:
        return PreviewService(self.container.resolve(IPreviewRenderer))

    def createExportService(self) -> ExportService:
        return ExportService(self.container.resolve(IVideoExporter))


class UIFactory:
    def __init__(self, container: DependencyContainer) -> None:
        self.container = container

    def createProjectListUI(self) -> ProjectListUI:
        return ProjectListUI(self.container.resolve(ProjectService))

    def createProjectEditorUI(self) -> ProjectEditorUI:
        return ProjectEditorUI(
            self.container.resolve(EditingService),
            self.container.resolve(MediaService),
            self.container.resolve(PreviewService),
            self.container.resolve(ProjectService),
        )

    def createExportUI(self) -> ExportUI:
        return ExportUI(self.container.resolve(ExportService))
