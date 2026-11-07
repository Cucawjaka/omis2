from datetime import datetime

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
    PreviewResult,
    TextOverlay,
    Timeline,
    VideoClip,
    VideoFile,
    VideoProject,
)


class ProjectService:
    def __init__(self, repository: IProjectRepository) -> None:
        self.repository = repository
        self.projects: dict[int, VideoProject] = {}

    def createProject(self, name: str) -> VideoProject:
        if not name.strip():
            raise ValueError("Введите название проекта.")
        project = VideoProject(name=name.strip())
        self.projects[project.projectId] = project
        self.repository.save(project)
        return project

    def openProject(self, projectId: int) -> VideoProject:
        project = self.repository.findById(projectId)
        self.projects[projectId] = project
        return project

    def saveProject(self, projectId: int) -> None:
        project = self.projects[projectId]
        project.updatedAt = datetime.now()
        self.repository.save(project)

    def deleteProject(self, projectId: int) -> None:
        self.repository.delete(projectId)
        self.projects.pop(projectId, None)

    def listProjects(self) -> list[VideoProject]:
        return self.repository.findAll()


class MediaService:
    def __init__(self, repository: IMediaRepository) -> None:
        self.repository = repository
        self.project: VideoProject | None = None

    def addVideoFile(self, path: str) -> VideoFile:
        media = self.repository.registerVideo(path)
        if self.project is not None:
            self.project.mediaFiles.append(media)
        return media

    def addAudioFile(self, path: str) -> AudioFile:
        media = self.repository.registerAudio(path)
        if self.project is not None:
            self.project.mediaFiles.append(media)
        return media

    def removeMediaFile(self, mediaId: int) -> None:
        self.repository.remove(mediaId)
        if self.project is not None:
            self.project.mediaFiles[:] = [
                m for m in self.project.mediaFiles if m.mediaId != mediaId
            ]
            self.project.timeline.elements[:] = [
                item
                for item in self.project.timeline.elements
                if not isinstance(item, (VideoClip, AudioClip))
                or item.source.mediaId != mediaId
            ]
            self.project.timeline.updateDuration()


class EditingService:
    def __init__(self) -> None:
        self.timeline = Timeline()

    def getTimeline(self) -> Timeline:
        return self.timeline

    def editClip(self) -> None:
        self.timeline.updateDuration()

    def _nextPosition(self, kind: str) -> float:
        return max(
            (
                item.position + item.duration
                for item in self.timeline.elements
                if item.kind == kind
            ),
            default=0.0,
        )

    def addVideoClip(self, videoFile: VideoFile) -> VideoClip:
        clip = VideoClip.create(videoFile)
        clip.position = self._nextPosition("video")
        self.timeline.addClip(clip)
        return clip

    def trimClip(self, clipId: int, startTime: float, endTime: float) -> None:
        self.timeline.getVideoClip(clipId).setBounds(startTime, endTime)
        self.editClip()

    def splitClip(self, clipId: int, splitTime: float) -> None:
        first, second = self.timeline.getVideoClip(clipId).split(splitTime)
        self.timeline.replaceClip(clipId, first, second)

    def moveClip(self, clipId: int, newPosition: float) -> None:
        self.timeline.moveClip(clipId, newPosition)

    def addAudioClip(self, audioFile: AudioFile) -> AudioClip:
        clip = AudioClip.create(audioFile)
        clip.position = self._nextPosition("audio")
        self.timeline.addClip(clip)
        return clip

    def addTextOverlay(
        self, text: str, startTime: float, endTime: float
    ) -> TextOverlay:
        element = TextOverlay.create(text, startTime, endTime)
        self.timeline.addElement(element)
        return element


class PreviewService:
    def __init__(self, renderer: IPreviewRenderer) -> None:
        self.renderer = renderer
        self.timeline = Timeline()

    def generatePreview(self) -> PreviewResult:
        return self.renderer.render(self.timeline)


class ExportService:
    def __init__(self, exporter: IVideoExporter) -> None:
        self.exporter = exporter
        self.project: VideoProject | None = None

    def exportVideo(self, settings: ExportSettings) -> ExportResult:
        if self.project is None:
            raise ValueError("Сначала откройте проект.")
        return self.exporter.export(self.project, settings)
