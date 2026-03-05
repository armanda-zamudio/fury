
import logging
from ih.download.domain.model import ProxyUrl
from ih.download.domain.ports import ProxyUrlFactory
NOISY_LOGGERS = ["botocore", "boto3"]
format_string = "%Y%m%d"

def configure_logging_for_cli():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(levelname)-10s - %(asctime)s - %(name)s - %(message)s",
    )
    for logger in NOISY_LOGGERS:
        logging.getLogger(logger).setLevel(logging.WARNING)

def configure_logging_for_lambda():
    logging.getLogger().setLevel(logging.DEBUG)
    for logger in NOISY_LOGGERS:
        try:
            logging.getLogger(logger).setLevel(logging.WARNING)
        except Exception as exc:
            logging.error(exec)


PLAYWRIGHT_CHROMIUM_ARGS = [
    "--disable-component-extensions-with-background-pages",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-features=InterestFeedContentSuggestions",
    "--disable-features=Translate",
    "--hide-scrollbars",
    "--mute-audio",
    "--no-default-browser-check",
    "--no-first-run",
    "--ash-no-nudges",
    "--disable-search-engine-choice-screen",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-features=CalculateNativeWinOcclusion",
    "--aggressive-cache-discard",
    "--disable-back-forward-cache",
    "--disable-features=BackForwardCache",
    "--disable-features=LazyFrameLoading",
    "--disable-features=ScriptStreaming",
    "--enable-precise-memory-info",
    "--disable-dev-shm-usage",
    "--in-process-gpu",
    "--no-zygote",
]




class StaticProxy(ProxyUrlFactory):
    def __init__(
        self,
        *,
        url:str   
    ):
        self._url  = url  
    def __call__(
        self,
    ) -> ProxyUrl:
        fields = {}
        
        return self._url
