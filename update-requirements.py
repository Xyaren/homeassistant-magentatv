#!/usr/bin/env python

import json
import os

import requirements

EXCLUSIONS = ["homeassistant"]

dependencies = []

with open(os.path.dirname(__file__) + "/requirements.txt") as fd:
    dependencies = list(requirements.parse(fd))


print("Updating manifest.json")

with open(os.path.dirname(__file__) + "/custom_components/magentatv/manifest.json", "r+") as f:
    manifest_data = json.load(f)
    manifest_data["requirements"] = [req.line for req in dependencies if req.name not in EXCLUSIONS]
    f.seek(0)  # <--- should reset file position to the beginning.
    json.dump(manifest_data, f, indent=2)
    f.truncate()  # remove remaining part

print("Updating hacs.json")
with open(os.path.dirname(__file__) + "/hacs.json", "r+") as f:
    version = None
    for dep in dependencies:
        if dep.name == "homeassistant":
            version = dep.specs[0][1]
            break

    hacs = json.load(f)
    hacs["homeassistant"] = version
    f.seek(0)  # <--- should reset file position to the beginning.
    json.dump(hacs, f, indent=2)
    f.truncate()  # remove remaining part
