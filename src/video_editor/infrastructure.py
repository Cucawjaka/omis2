import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast

from video_editor.contracts import (
    IMediaRepository,
    IPreviewRenderer,
    IProjectRepository,
    IVideoExporter,
)
from video_editor.model import (
    AudioClip,
    AudioFile,
    ExportResult,
    ExportSettings,
    MediaFile,
    PreviewResult,
    TextOverlay,
    Timeline,
    VideoClip,
    VideoFile,
    VideoProject,
)

if TYPE_CHECKING:
    from video_editor.factories import ServiceFactory, UIFactory

T = TypeVar("T")
M = TypeVar("M", VideoFile, AudioFile)


class LocalProjectRepository(IProjectRepository):
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)

    def _path(self, projectId: int) -> Path:
        return self.directory / f"{int(projectId)}.json"

    def save(self, project: VideoProject) -> None:
        payload = asdict(project)
        payload["createdAt"] = project.createdAt.isoformat()
        payload["updatedAt"] = project.updatedAt.isoformat()
        payload["mediaFiles"] = [
            dict(asdict(m), kind=m.kind) for m in project.mediaFiles
        ]
        payload["timeline"]["elements"] = [
            dict(asdict(item), kind=item.kind) for item in project.timeline.elements
        ]
        path = self._path(project.projectId)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(path)

    def findById(self, projectId: int) -> VideoProject:
        data = json.loads(self._path(projectId).read_text(encoding="utf-8"))
        files: list[MediaFile] = []
        for entry in data.pop("mediaFiles"):
            cls = VideoFile if entry.pop("kind") == "video" else AudioFile
            files.append(cls(**entry))
        media = {item.mediaId: item for item in files}
        timelineData = data.pop("timeline")
        elements = []
        for entry in timelineData.pop("elements"):
            kind = entry.pop("kind")
            if kind in ("video", "audio"):
                sourceData = entry.pop("source")
                sourceId = sourceData["mediaId"]
                if sourceId not in media:
                    sourceClass = VideoFile if kind == "video" else AudioFile
                    media[sourceId] = sourceClass(**sourceData)
                    files.append(media[sourceId])
                entry["source"] = media[sourceId]
                cls = VideoClip if kind == "video" else AudioClip
            elif kind == "text":
                cls = TextOverlay
            else:
                raise ValueError(f"Неизвестный тип элемента: {kind}")
            elements.append(cls(**entry))
        data["createdAt"] = datetime.fromisoformat(data["createdAt"])
        data["updatedAt"] = datetime.fromisoformat(data["updatedAt"])
        return VideoProject(
            **data,
            mediaFiles=files,
            timeline=Timeline(**timelineData, elements=elements),
        )

    def findAll(self) -> list[VideoProject]:
        projects = []
        for path in self.directory.glob("*.json"):
            projects.append(self.findById(int(path.stem)))
        return sorted(projects, key=lambda project: project.updatedAt, reverse=True)

    def delete(self, projectId: int) -> None:
        self._path(projectId).unlink(missing_ok=True)


class FileMediaRepository(IMediaRepository):
    def __init__(self) -> None:
        self.files: dict[int, MediaFile] = {}

    def _register(self, path: str, cls: type[M]) -> M:
        file = Path(path).expanduser().resolve()
        if not file.is_file():
            raise ValueError("Выберите существующий медиафайл.")

        media = cls(fileName=file.name, filePath=str(file))
        self.files[media.mediaId] = media
        return media

    def registerVideo(self, path: str) -> VideoFile:
        return self._register(path, VideoFile)

    def registerAudio(self, path: str) -> AudioFile:
        return self._register(path, AudioFile)

    def remove(self, mediaId: int) -> None:
        self.files.pop(mediaId, None)


class PreviewRenderer(IPreviewRenderer):
    def render(self, timeline: Timeline) -> PreviewResult:
        return PreviewResult()


class VideoExporter(IVideoExporter):
    def export(self, project: VideoProject, settings: ExportSettings) -> ExportResult:
        return ExportResult(outputPath=settings.outputPath, success=False)


class DependencyContainer:
    def __init__(self) -> None:
        self._providers: dict[type, Callable[[], object]] = {}
        self._instances: dict[type, object] = {}
        self.serviceFactory: ServiceFactory | None = None
        self.uiFactory: UIFactory | None = None

    def register(
        self, interfaceType: type[T], implementationType: Callable[[], T]
    ) -> None:
        self._providers[interfaceType] = implementationType
        self._instances.pop(interfaceType, None)

    def resolve(self, type: type[T]) -> T:
        if type not in self._instances:
            self._instances[type] = self._providers[type]()

        return cast(T, self._instances[type])

    def configure(self) -> None:
        for cls in self._providers:
            self.resolve(cls)
