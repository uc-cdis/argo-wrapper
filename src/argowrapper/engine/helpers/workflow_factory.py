from typing import Any, Dict, Optional

from argowrapper.constants import WORKFLOW
from argowrapper.workflows.argo_workflows.gwas import GWAS
from argowrapper.workflows.argo_workflows.plp import PLP


class WorkflowFactory:
    @staticmethod
    def _get_workflow(
        namespace: str,
        request_body: Dict[str, Any],
        auth_header: Optional[str],
    ):
        if request_body["template_version"].startswith("plp-template"):
            workflow = PLP
        elif request_body["template_version"].startswith("gwas-template"):
            workflow = GWAS

        return workflow(namespace, request_body, auth_header)
