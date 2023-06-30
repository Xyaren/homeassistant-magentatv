#!/usr/bin/env python

import os

from ruamel.yaml import YAML

from custom_components.magentatv.api.const import KeyCode

services_file = os.path.dirname(__file__) + "/custom_components/magentatv/services.yaml"
yaml = YAML()
with open(
    services_file,
    encoding="utf-8",
) as f:
    doc = yaml.load(f)

# set keys
key_options = [key.name for key in KeyCode]
doc["send_key"]["fields"]["key_code"]["selector"]["select"]["options"] = key_options

yaml.indent(mapping=2, sequence=4, offset=2)
with open(services_file, "w", encoding="utf-8") as f:
    yaml.dump(doc, f)
