from ast import Dict

from argowrapper.constants import WORKFLOW
from argowrapper.workflows.argo_workflows.gwas import GWAS


class WorkflowFactory:
    @staticmethod
    def _get_workflow(
        namespace: str,
        request_body: Dict,
        auth_header: str,
        workflow_type: WORKFLOW,
    ):
        workflows = {WORKFLOW.GWAS: GWAS}

        return workflows[workflow_type](namespace, request_body, auth_header)
