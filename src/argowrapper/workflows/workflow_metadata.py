from typing import Dict

from argowrapper import logger


class WorkflowMetadata:
    def __init__(self, namespace: str):
        self.namespace = namespace
        self.name = ""
        self.annotations = {}
        self.labels = {}

    def add_metadata_label(
        self, metadata_label_key: str, metadata_label_val: str
    ) -> None:
        if metadata_label_key in self.labels:
            logger.warning(
                f"workflow metadata label {metadata_label_key} \
                    will be overwritten with value {metadata_label_val}"
            )

        self.labels[metadata_label_key] = metadata_label_val

    def add_metadata_annotation(
        self, metadata_annotation_key: str, metadata_annotation_val: str
    ) -> None:
        if metadata_annotation_key in self.annotations:
            logger.warning(
                f"workflow metadata annotation {metadata_annotation_key} \
                    will be overwritten with value {metadata_annotation_val}"
            )

        self.annotations[metadata_annotation_key] = metadata_annotation_val

    def set_name(self, name: str) -> None:
        self.name = name

    # used to debug workflow metadata state
    def _to_dict(self) -> Dict:
        dict_representation = {}
        for attribute, attribute_val in self.__dict__.items():
            if attribute_val:
                dict_representation[attribute] = attribute_val
        return dict_representation

    def to_argo_metadata_dict(self) -> Dict:
        return self._to_dict()
