from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


def newId() -> int:
    return uuid4().int >> 96


@dataclass(kw_only=True)
class MediaFile(ABC):
    mediaId: int = field(default_factory=newId)
    fileName: str
    filePath: str
    duration: float = 10.0

    @property
    @abstractmethod
    def kind(self) -> str: ...


@dataclass(kw_only=True)
class VideoFile(MediaFile):
    width: int = 1920
    height: int = 1080
    frameRate: float = 30.0

    @property
    def kind(self) -> str:
        return "video"


@dataclass(kw_only=True)
class AudioFile(MediaFile):
    bitRate: int = 192000

    @property
    def kind(self) -> str:
        return "audio"


@dataclass(kw_only=True)
class TimelineItem(ABC):
    position: float = 0.0
    startTime: float = 0.0
    endTime: float = 10.0

    @property
    @abstractmethod
    def kind(self) -> str: ...

    @property
    def duration(self) -> float:
        return self.endTime - self.startTime


@dataclass(kw_only=True)
class VideoClip(TimelineItem):
    clipId: int = field(default_factory=newId)
    sourceStartTime: float = 0.0
    sourceEndTime: float = 10.0
    source: VideoFile

    @property
    def kind(self) -> str:
        return "video"

    @classmethod
    def create(cls, videoFile: VideoFile) -> "VideoClip":
        return cls(source=videoFile, endTime=videoFile.duration, sourceEndTime=videoFile.duration)

    def setBounds(self, startTime: float, endTime: float) -> None:
        if not 0 <= startTime < endTime <= self.source.duration:
            raise ValueError("Границы фрагмента должны находиться в пределах исходного видео.")
        self.sourceStartTime, self.sourceEndTime = startTime, endTime
        self.startTime, self.endTime = startTime, endTime

    def split(self, splitTime: float) -> list["VideoClip"]:
        if not self.sourceStartTime < splitTime < self.sourceEndTime:
            raise ValueError("Точка разделения должна находиться внутри фрагмента.")
        first = VideoClip.create(self.source)
        first.setBounds(self.sourceStartTime, splitTime)
        first.position = self.position
        second = VideoClip.create(self.source)
        second.setBounds(splitTime, self.sourceEndTime)
        second.position = self.position + first.duration
        return [first, second]


@dataclass(kw_only=True)
class AudioClip(TimelineItem):
    clipId: int = field(default_factory=newId)
    sourceStartTime: float = 0.0
    sourceEndTime: float = 10.0
    source: AudioFile

    @property
    def kind(self) -> str:
        return "audio"

    @classmethod
    def create(cls, audioFile: AudioFile) -> "AudioClip":
        return cls(source=audioFile, endTime=audioFile.duration, sourceEndTime=audioFile.duration)


@dataclass(kw_only=True)
class TextOverlay(TimelineItem):
    textId: int = field(default_factory=newId)
    text: str

    @property
    def kind(self) -> str:
        return "text"

    @classmethod
    def create(cls, text: str, startTime: float, endTime: float) -> "TextOverlay":
        if not text.strip() or not 0 <= startTime < endTime:
            raise ValueError("Задайте текст и корректный интервал отображения.")
        return cls(text=text.strip(), position=startTime, startTime=startTime, endTime=endTime)


@dataclass
class Timeline:
    timelineId: int = field(default_factory=newId)
    duration: float = 0.0
    elements: list[TimelineItem] = field(default_factory=list)

    def getElements(self) -> list[TimelineItem]:
        return sorted(self.elements, key=lambda item: item.position)

    def getVideoClip(self, clipId: int) -> VideoClip:
        for element in self.elements:
            if isinstance(element, VideoClip) and element.clipId == clipId:
                return element
        raise ValueError("Видеоклип не найден.")

    def addClip(self, clip: TimelineItem) -> None:
        self.addElement(clip)

    def addElement(self, element: TimelineItem) -> None:
        self.elements.append(element)
        self.updateDuration()

    def replaceClip(self, clipId: int, firstClip: VideoClip, secondClip: VideoClip) -> None:
        original = self.getVideoClip(clipId)
        index = self.elements.index(original)
        self.elements[index : index + 1] = [firstClip, secondClip]
        self.updateDuration()

    def moveClip(self, clipId: int, newPosition: float) -> None:
        if newPosition < 0:
            raise ValueError("Позиция не может быть отрицательной.")
        self.getVideoClip(clipId).position = newPosition
        self.updateDuration()

    def updateDuration(self) -> None:
        self.duration = max((item.position + item.duration for item in self.elements), default=0.0)


@dataclass
class ExportSettings:
    format: str = "MP4"
    resolution: str = "1920×1080"
    frameRate: float = 30.0
    outputPath: str = ""


@dataclass
class VideoProject:
    projectId: int = field(default_factory=newId)
    name: str = "Новый проект"
    createdAt: datetime = field(default_factory=datetime.now)
    updatedAt: datetime = field(default_factory=datetime.now)
    timeline: Timeline = field(default_factory=Timeline)
    mediaFiles: list[MediaFile] = field(default_factory=list)


@dataclass
class PreviewResult:
    previewPath: str = ""


@dataclass
class ExportResult:
    outputPath: str = ""
    success: bool = False
