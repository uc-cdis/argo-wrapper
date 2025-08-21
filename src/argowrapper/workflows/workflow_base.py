from argowrapper.constants import API_VERSION, WORKFLOW_ENTRYPOINT, WORKFLOW_KIND
from argowrapper.engine.helpers import argo_engine_helper
from argowrapper.workflows.workflow_metadata import WorkflowMetadata
from argowrapper.workflows.workflow_spec import WorkflowSpec


class WorkflowBase:
    """Class representation of argo workflow

    Attributes:
        wf_name (string): unique id of the submitted workflow

    """

    METADATA_ANNOTATIONS = {}
    METADATA_LABELS = {}

    def __init__(self, namespace: str, entrypoint: WORKFLOW_ENTRYPOINT, dry_run=False):
        self.wf_name = argo_engine_helper.generate_workflow_name(
            prefix_name=entrypoint.value
        )
        self.api_version = API_VERSION
        self.kind = WORKFLOW_KIND
        self.metadata = WorkflowMetadata(namespace)
        self.spec = WorkflowSpec()

        self._entrypoint = entrypoint.value
        self._dry_run = dry_run

        if not dry_run:
            self.setup_metadata()
            self.setup_spec()

    def _add_metadata_annotations(self):
        for annotation_key, annotation_val in self.METADATA_ANNOTATIONS.items():
            self.metadata.add_metadata_annotation(annotation_key, annotation_val)

    def _add_metadata_labels(self):
        for label_key, label_val in self.METADATA_LABELS.items():
            self.metadata.add_metadata_label(label_key, label_val)

    def setup_metadata(self):
        self.metadata.set_name(self.wf_name)
        self._add_metadata_annotations()
        self._add_metadata_labels()

    def setup_spec(self):
        self.spec.set_entry_point(self._entrypoint)

    def _to_dict(self):
        return {
            "apiVersion": self.api_version,
            "kind": self.kind,
            "metadata": self.metadata.to_argo_metadata_dict(),
            "spec": self.spec.to_argo_spec_dict(),
        }
