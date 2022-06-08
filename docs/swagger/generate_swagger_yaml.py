import os

import yaml

from argowrapper.app import get_app

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))

schema = get_app().openapi()
path = os.path.join(CURRENT_DIR, "swagger.yaml")
yaml.Dumper.ignore_aliases = lambda *args: True
with open(path, "w+") as f:
    yaml.dump(schema, f, default_flow_style=False)
print(f"Saved docs at {path}")
