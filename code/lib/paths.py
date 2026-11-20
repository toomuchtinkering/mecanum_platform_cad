"""Where everything is: the one place that knows the layout of the repository.

Plain Python without FreeCAD, so that the driver (`code/rebuild.py`) can use it
as well as the scripts that run inside FreeCAD.

    model/            the parameters, the parts and the assemblies: each
                      document next to the script that builds it
    model/project.py  the project's settings (licence, materials, colours)
    model/<group>/    one folder per group of parts: every folder that holds
                      scripts, but the assemblies' (`part_groups`); a module
                      whose name starts with "_" describes a family of parts
                      there and is not a part script itself
    data/build/       what each build found, one JSON file per document
    cache/            scratch, never committed
"""

import glob
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL = os.path.join(ROOT, "model")
PARAMETERS_SCRIPT = os.path.join(MODEL, "Parameters.py")
PARAMETERS = os.path.join(MODEL, "Parameters.FCStd")
PROJECT = os.path.join(MODEL, "project.py")
ASSEMBLY_GROUP = "assembly"
BUILD_DATA = os.path.join(ROOT, "data", "build")
CACHE = os.path.join(ROOT, "cache")


def model(*parts):
    """A path under model/, such as model("<group>", "<Part>.FCStd")."""
    return os.path.join(MODEL, *parts)


def rel(path):
    """A path relative to the repository's root, for messages and reports."""
    return os.path.relpath(path, ROOT)


def is_family(path):
    """True for a module that describes a family of parts (`_<family>.py`)."""
    return os.path.basename(path).startswith("_")


def part_groups():
    """The folders under model/ that hold part scripts: every folder with a
    script in it, but the assemblies'.  Parts need nothing from each other but
    the parameters, so their order does not matter; it is the alphabet's."""
    found = []
    for name in sorted(os.listdir(MODEL)):
        if name.startswith(("_", ".")) or name == ASSEMBLY_GROUP:
            continue
        if glob.glob(os.path.join(MODEL, name, "*.py")):
            found.append(name)
    return tuple(found)


_project = None


def project():
    """The project's settings, model/project.py, loaded from its path so that
    no other module of that name can stand in for it."""
    global _project
    if _project is None:
        spec = importlib.util.spec_from_file_location("project", PROJECT)
        _project = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_project)
    return _project
