import typing
from playwright.async_api import Page
from crimsonking.application.workflow.model import WorkflowData
from crimsonking.application.workflow.model import (
    CSVBytes,
    HTMLBytes,
    PDFBytes,
    VideoBytes,
    ScreenshotBytes,
)

from ih.download.domain.model import HttpResponse


class Downloader(typing.Protocol):
    def __call__(
        self, workflow_data: WorkflowData
    ) -> typing.Tuple[HttpResponse, ScreenshotBytes, PDFBytes]: ...

class DownloaderWarmingFactory:
    warm_page:Page|None
    def __init__(self, url:str):
        self.url = url
        

    def __call__(self, page:Page) -> Page: ...