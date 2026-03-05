import logging
import typing

from crimsonking.application.workflow import(
    pdfvalidators,
    screenshotvalidators,
    urlvalidators
)

from crimsonking.application.workflow.model import(
    SkipWorkflow,
    WorkflowData,
    WorkflowStage,
    WorkflowState,
    SkipExport,
    Exception403,
    Exception502,
    WebWarmingError
)

from crimsonking.application.workflow.ports import(
    Exporter,
    Notifier,
    Validator
)

from crimsonking_downloader.application.workflow import httpresponsevalidators

from crimsonking_downloader.application.workflow.ports import Downloader

from ih.download.domain.model import HttpResponse

from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

class WorkflowExecutor:
    def __init__(
        self,
        *,
        downloader: Downloader,        
        exporters: typing.Iterable[Exporter] = [],   
        notifiers: typing.Iterable[Notifier] = [],                
        response_validators: typing.Iterable[Validator] = [
            httpresponsevalidators.default,
            # screenshotvalidators.default,
            # pdfvalidators.default,
        ],
        url_validators: typing.Iterable[Validator] = [urlvalidators.default],
    ):
        self._log = logging.getLogger().getChild(self.__class__.__qualname__)

        self._downloader = downloader
        self._exporters = exporters  
        self._notifiers = notifiers
        self._response_validators = response_validators        
        self._url_validators = url_validators

    def execute(self, url: str, url_type:str, uuid:str, years:list) -> WorkflowData:        
        workflow_data = WorkflowData(url=url, url_type=url_type, uuid=uuid, years=years)        
        workflow_data.workflow_response = {"url":url}
        stages = (
            (WorkflowStage.VALIDATE_URL, self._validate_url),
            (WorkflowStage.DOWNLOAD, self._download),
            (WorkflowStage.VALIDATE_RESPONSE, self._validate_response),            
            (WorkflowStage.EXPORT, self._export),
            (WorkflowStage.NOTIFY, self._notify)
        )
        export = True
        for stage, action in stages:
            
            workflow_data.stage = stage         
            try:
                if stage == WorkflowStage.EXPORT:
                    if export:
                        action(workflow_data)
                    else:
                        self._log.info(f"SKIP called at stage {stage.name}.")                                    
                else:
                    action(workflow_data)    
            except SkipWorkflow:
                self._log.info(f"SKIP called at stage {stage.name}.")
                workflow_data.state = WorkflowState.SKIPPED
                raise
            except SkipExport:
                self._log.info(f"SKIP called at stage Export.")
                export = False       
            except PlaywrightTimeoutError:
                raise   
            except Exception403:
                raise      
            except Exception502:
                raise        
            except WebWarmingError:
                raise       
            except Exception as exc:
                workflow_data.state = WorkflowState.FAILED
                self._log.info(f"FAIL at {stage.name}.", exc_info=exc)
                raise
        workflow_data.state = WorkflowState.COMPLETE
        workflow_data.stage = WorkflowStage.COMPLETE
        self._log.info("COMPLETE")
        
        return workflow_data

    def _validate_url(self, workflow_data: WorkflowData) -> typing.Self:
        self._log.info("Validating URL")
        for validator in self._url_validators:
            validator(workflow_data)
        return self

    def _download(self, workflow_data: WorkflowData):
        self._log.info("Downloading")
        self._downloader(workflow_data)

    def _validate_response(self, workflow_data: WorkflowData):
        self._log.info("Validating response")
        for validator in self._response_validators:
            validator(workflow_data)

    def _export(self, workflow_data: WorkflowData):
        self._log.info("Executing exporters.")
        for exporter in self._exporters:
            exporter(workflow_data)

    def _notify(self, workflow_data: WorkflowData):
        self._log.info("Executing notifiers.")
        for notifier in self._notifiers:
            notifier(workflow_data)


