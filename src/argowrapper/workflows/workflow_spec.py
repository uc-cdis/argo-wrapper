from typing import List

from argowrapper import logger


class WorkflowSpec:
    def __init__(self):
        self.entrypoint = ""
        self.podGC = {}
        self.nodeSelector = {}
        self.tolerations = {}
        self.podMetadata = {}
        self.arguments = {}
        self.volumes = []
        self.workflowTemplateRef = {}

    def set_entry_point(self, entrypoint: str) -> None:
        self.entrypoint = entrypoint

    def add_scaling_group(self, scaling_group: str) -> None:
        self.nodeSelector = {"role": scaling_group}

        self.tolerations = [
            {
                "key": "role",
                "operator": "Equal",
                "value": scaling_group,
                "effect": "NoSchedule",
            }
        ]

    def _add_parameter(
        self, parameter_name: str, parameter_value: str, **kwargs
    ) -> None:
        if not self.arguments.get("parameters"):
            self.arguments["parameters"] = []

        parameter = {"name": parameter_name, "value": parameter_value}

        if kwargs.get("default"):
            parameter["default"] = kwargs.get("default")

        if kwargs.get("enum"):
            parameter["enum"] = kwargs.get("enum")

        # if a value is None, then remove it, setting a value to None will cause issues
        if parameter_value is None:
            del parameter["value"]

        self.arguments["parameters"].append(parameter)

    def add_enum_parameter(
        self,
        parameter_name: str,
        parameter_value: str,
        enum: List[str],
        default: str = "",
    ) -> None:
        self._add_parameter(parameter_name, parameter_value, enum=enum, default=default)

    def add_string_parameter(
        self, parameter_name: str, parameter_value: str, default: str = ""
    ) -> None:
        self._add_parameter(parameter_name, parameter_value, default=default)

    def set_workflow_template_ref(self, workflow_template_name: str) -> None:
        self.workflowTemplateRef = {"name": workflow_template_name}

    def add_persistent_volume_claim(self, name: str, claim_name: str):
        pvc = {"name": name, "persistentVolumeClaim": {"claimName": claim_name}}

        self.volumes.append(pvc)

    def add_pod_metadata_label(
        self, pod_metadata_label_key: str, pod_metadata_label_val: str
    ) -> None:
        if not self.podMetadata.get("labels"):
            self.podMetadata["labels"] = {}

        if pod_metadata_label_key in self.podMetadata.get("labels"):
            logger.warning(
                f"pod metadata label {pod_metadata_label_key} \
                    will be overwritten with value {pod_metadata_label_val}"
            )

        self.podMetadata["labels"][pod_metadata_label_key] = pod_metadata_label_val

    def add_pod_metadata_annotation(
        self, pod_metadata_annotation_key: str, pod_metadata_annotation_val: str
    ) -> None:
        if not self.podMetadata.get("annotations"):
            self.podMetadata["annotations"] = {}

        if pod_metadata_annotation_key in self.podMetadata.get("annotations"):
            logger.warning(
                f"pod metadata annotation {pod_metadata_annotation_key} \
                    will be overwritten with value {pod_metadata_annotation_val}"
            )

        self.podMetadata["annotations"][
            pod_metadata_annotation_key
        ] = pod_metadata_annotation_val

    def set_podGC_strategy(self, completed_pods_deletion_strategy: str):
        self.podGC = {"strategy": completed_pods_deletion_strategy}

    def add_empty_dir(self, name: str, dir_size: str):
        empty_dir = {"name": name, "emptyDir": {"sizeLimit": dir_size}}
        self.volumes.append(empty_dir)

    # used to debug workflow spec state
    def _to_dict(self):
        dict_representation = {}
        for attribute, attribute_val in self.__dict__.items():
            if attribute_val:
                dict_representation[attribute] = attribute_val

        return dict_representation

    def to_argo_spec_dict(self):
        if not self.entrypoint:
            logger.error("workflow must have an entrypoint")
            return {}

        if not self.workflowTemplateRef:
            logger.error("workflow must refer to an existing workflow template")
            return {}

        return self._to_dict()
