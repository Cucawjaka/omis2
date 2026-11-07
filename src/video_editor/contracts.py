from abc import ABC, abstractmethod

from video_editor.model import (
    AudioFile,
    ExportResult,
    ExportSettings,
    PreviewResult,
    Timeline,
    VideoFile,
    VideoProject,
)


class IProjectRepository(ABC):
    @abstractmethod
    def findById(self, projectId: int) -> VideoProject: ...

    @abstractmethod
    def save(self, project: VideoProject) -> None: ...

    @abstractmethod
    def delete(self, projectId: int) -> None: ...

    @abstractmethod
    def findAll(self) -> list[VideoProject]: ...


class IMediaRepository(ABC):
    @abstractmethod
    def registerVideo(self, path: str) -> VideoFile: ...

    @abstractmethod
    def registerAudio(self, path: str) -> AudioFile: ...

    @abstractmethod
    def remove(self, mediaId: int) -> None: ...


class IPreviewRenderer(ABC):
    @abstractmethod
    def render(self, timeline: Timeline) -> PreviewResult: ...


class IVideoExporter(ABC):
    @abstractmethod
    def export(
        self, project: VideoProject, settings: ExportSettings
    ) -> ExportResult: ...


class IView(ABC):
    @abstractmethod
    def show(self) -> None: ...

    @abstractmethod
    def refresh(self) -> None: ...
