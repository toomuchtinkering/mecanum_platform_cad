"""Run part scripts under FreeCAD and report which ones built.

freecadcmd swallows tracebacks and exits 0 when a script raises, so every
build goes through here: each script runs inside a try block that prints the
traceback, and the last line says `BUILD OK` or `BUILD FAILED`.  `rebuild.py`
reads that line and checks the document exists, rather than the exit code.

The scripts to run come in the environment variable FCARGS, separated by `|`,
because freecadcmd treats file arguments on its command line as files to
open and rejects unknown options:

    flatpak run --env=FCARGS=model/<group>/<Part>.py --command=freecadcmd \\
        org.freecad.FreeCAD -c "exec(open('/abs/path/code/build.py').read())"

A script that needs the GUI (it says `# fcbuild: gui`, such as one that
imports a model with a colour per face, which only a GUI keeps) runs under the full
FreeCAD binary instead, which runs this file as its script; the lines below
then go straight down fd 1, since the GUI takes over `sys.stdout`, and the
process ends itself.  A script may raise `fcprim.SkipBuild` when what it
builds from is missing, and the last line then says `BUILD SKIPPED`.
"""

import os
import sys
import traceback

ROOT = "/".join(os.environ["FCROOT"].rstrip("/").split("/"))
# Before anything restores a fastener (the Fasteners add-on imports FreeCADGui,
# after which Draft segfaults freecadcmd): any document linking one does.
import DraftVecUtils  # noqa: E402,F401
sys.path.insert(0, os.path.join(ROOT, "code", "lib"))


def say(*args):
    os.write(1, (" ".join(str(a) for a in args) + "\n").encode())


def run(path):
    # A part script imports the family module next to it (`_<family>.py`).
    folder = os.path.dirname(path)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    namespace = {"__file__": path, "__name__": "__part__"}
    with open(path) as handle:
        code = compile(handle.read(), path, "exec")
    exec(code, namespace)


failed, skipped = [], []
scripts = [s for s in os.environ.get("FCARGS", "").split("|") if s]
for script in scripts:
    path = script if os.path.isabs(script) else os.path.join(ROOT, script)
    say(f"=== {os.path.relpath(path, ROOT)}")
    try:
        run(path)
    except BaseException as e:                 # SystemExit counts as failure
        if type(e).__name__ == "SkipBuild":
            skipped.append(script)
            say(f"  skipped: {e}")
        else:
            failed.append(script)
            say(traceback.format_exc())
if failed or not scripts:
    say("BUILD FAILED " + " ".join(failed))
else:
    say("BUILD SKIPPED" if skipped else "BUILD OK")
import FreeCAD as App  # noqa: E402
if App.GuiUp:                                  # nothing else closes the GUI
    os._exit(1 if failed else 0)
