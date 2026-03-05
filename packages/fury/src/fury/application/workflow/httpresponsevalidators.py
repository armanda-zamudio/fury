from crimsonking.application.workflow.model import HttpResponseValidationError, WorkflowData


def default(workflow_data: WorkflowData):
    response = workflow_data.http_response
    try:
        assert response.status_code == 200
        assert response.content is not None
        assert len(response.content) > 1024
    except AssertionError:
        raise HttpResponseValidationError()
