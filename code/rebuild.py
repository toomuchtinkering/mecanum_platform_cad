"""Build everything, in stages that can also run alone.

    python3 code/rebuild.py                          # every stage, in order
    python3 code/rebuild.py parts dress              # just these
    python3 code/rebuild.py parts model/<group>/<Part>.py      # one part
    python3 code/rebuild.py dress model/<group>/<Part>.FCStd   # one document's GUI pass
    python3 code/rebuild.py --list
    python3 code/rebuild.py --show ...               # GUI passes on the desktop

Plain Python with the system interpreter: it drives FreeCAD (the flatpak
`org.freecad.FreeCAD`) as subprocesses, one per document, because FreeCAD
fails to restore links between documents that were opened and closed earlier
in the same session.  freecadcmd exits 0 when a script raises and swallows the
traceback, so each run is judged by the `BUILD OK` line `build.py` prints and
by the document existing afterwards.

## The stages

    parameters  the shared spreadsheet, model/Parameters.FCStd
    parts       every part script in the folders under model/ but the
                assemblies' (`paths.part_groups`);
                each recomputes clean, its sketches are fully constrained and
                it passes its own test (named dimensions changed and put back)
    assemblies  every script in model/assembly, after the ones it NEEDS; each
                solves with the degrees of freedom it should have, from a
                shaken start too (FCASM_SHAKE=1), with no overlap and no part
                touching nothing
    dress       the view data a GUI needs (full FreeCAD, real display)
    meta        the licence and no absolute path in every document
    bom         the bill of materials, BOM.md and data/bom.json, counted from
                every assembly that no other one needs (code/bom.py)

What each build found is written to data/build/<document>.json.

## The GUI passes

Dressing a document and importing a model with a colour per face need the
full FreeCAD binary and an X display with GL: Qt's offscreen platform has
none, and assemblies deadlocked in it.  Where Xvfb is installed (package `xvfb`), the build starts a
private Xvfb for them, so no window appears and work on the desktop goes on;
without it, or with `--show`, they use the desktop's display.
"""

import glob
import atexit
import os
import re
import select
import shutil
import subprocess
import sys
import time
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import paths  # noqa: E402

ROOT = paths.ROOT
FLATPAK = ["flatpak", "run", f"--env=FCROOT={ROOT}"]
APP = "org.freecad.FreeCAD"
# The result lines a build prints that the log shows: a script's header, and
# every line of two spaces, a lowercase word and a colon or space, which is
# how the helpers and the scripts print what they found ("  solved: ...",
# "  flex width -> 12: ...").  Print each with its own leading newline, so
# that no progress output can stand in front of it.
SHOWN = re.compile(r"^(===|  [a-z_]+[: ])")


def say(*a):
    print(*a, flush=True)


def freecadcmd(script, args=()):
    """Run `script` (relative to the root) under freecadcmd; its output.

    flatpak passes no environment through, so the assembly test switches
    (FCASM_*, see code/lib/fcasm.py) are forwarded explicitly.
    """
    extra = [f"--env={k}={v}" for k, v in os.environ.items() if k.startswith("FCASM_")]
    cmd = FLATPAK + extra + [f"--env=FCARGS={'|'.join(args)}", "--command=freecadcmd",
                             APP, "-c", f"exec(open('{os.path.join(ROOT, script)}').read())"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout + p.stderr).replace("\r", "\n")
    # Progress output is not always ended by a newline: the next line printed
    # can follow it on the same line, behind tabs or a "Recompute......".
    # Filtering whole lines dropped results that way, so the progress
    # fragments are cut out wherever they are.  A counter can be cut in two,
    # "(6" before the next line and " %)" after it; it always comes behind
    # tabs.  The result lines the log shows also start with their own newline,
    # so nothing can stand in front of them.
    out = re.sub(r"(?:Recompute|Postprocessing|Importing project files|saving)\.*"
                 r"|\t+\([ ]*\d*(?:[ ]*%\))?|\([ ]*\d+ %\)", "\n", out)
    return "\n".join(l.lstrip("\t") for l in out.splitlines()
                     if l.strip() and not re.match(r"^\s*%?\)\s*$", l))


def run_build(scripts):
    """Each script in its own FreeCAD; fail unless it says so and saved.

    Each document is dressed and its metadata checked as soon as it is built,
    not after the stage: a document written by freecadcmd opens with
    everything hidden, and a stage that stopped half way once left the parts
    it had built that way, so that an assembly of them opened empty.
    """
    for script in scripts:
        t = time.time()
        if GUI_MARK in open(os.path.join(ROOT, script)).read():
            out = gui_build(script)
        else:
            out = freecadcmd("code/build.py", [script])
        doc = os.path.splitext(os.path.join(ROOT, script))[0] + ".FCStd"
        if "BUILD SKIPPED" in out.splitlines():
            say("\n".join(l for l in out.splitlines() if "skipped" in l))
            continue
        ok = "BUILD OK" in out.splitlines() and os.path.exists(doc)
        lines = [l for l in out.splitlines() if SHOWN.match(l) or not ok]
        say("\n".join(lines))
        say(f"  {'ok' if ok else 'FAILED'} in {time.time() - t:.0f} s")
        if not ok:
            raise SystemExit(f"{script} failed")
        dress([paths.rel(doc)])
        meta_check([paths.rel(doc)])


GUI_MARK = "# fcbuild: gui"


SHOW = False                 # --show: the GUI passes on the desktop's display
_XVFB = {}


def _stop_xvfb():
    proc = _XVFB.get("proc")
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()


def gui_env():
    """The environment for a GUI process: a private Xvfb display, started on
    first use and stopped when the build ends, or the desktop's."""
    env = dict(os.environ)
    if SHOW or not shutil.which("Xvfb"):
        if not env.get("DISPLAY"):
            raise SystemExit("no X display for the GUI passes: install Xvfb (package "
                             "xvfb) or build in a desktop session")
        return env
    if "display" not in _XVFB:
        r, w = os.pipe()
        proc = subprocess.Popen(["Xvfb", "-displayfd", str(w), "-screen", "0",
                                 "1920x1080x24", "-nolisten", "tcp"], pass_fds=(w,),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(w)
        _XVFB["proc"] = proc
        atexit.register(_stop_xvfb)
        number = b""
        while not number.endswith(b"\n"):
            ready, _, _ = select.select([r], [], [], 10)
            if not ready:
                raise SystemExit("Xvfb did not start within 10 s")
            chunk = os.read(r, 16)
            if not chunk:
                raise SystemExit("Xvfb exited before it was ready")
            number += chunk
        os.close(r)
        _XVFB["display"] = f":{number.decode().strip()}"
        say(f"  GUI passes on a private display {_XVFB['display']} (Xvfb); "
            f"--show puts them on the desktop")
    env["DISPLAY"] = _XVFB["display"]
    return env


def gui_build(script):
    """Run one script under the full FreeCAD binary (see code/build.py)."""
    cmd = FLATPAK + [f"--env=FCARGS={script}", APP, os.path.join(ROOT, "code", "build.py")]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=gui_env())
    except subprocess.TimeoutExpired:
        raise SystemExit(f"{script}: GUI build timed out (deadlock?)")
    return p.stdout.replace("\r", "\n")


def _scripts(group):
    return sorted(paths.rel(p) for p in glob.glob(paths.model(group, "*.py"))
                  if not paths.is_family(p))


def part_scripts(only=()):
    if only:
        return list(only)
    found = []
    for group in paths.part_groups():
        found += _scripts(group)
    return found


def documents():
    found = [paths.rel(paths.PARAMETERS)]
    for group in paths.part_groups() + (paths.ASSEMBLY_GROUP,):
        found += sorted(paths.rel(p) for p in glob.glob(paths.model(group, "*.FCStd")))
    return found


def stage_parameters(_):
    run_build([paths.rel(paths.PARAMETERS_SCRIPT)])


def stage_parts(only):
    asm = paths.rel(paths.model(paths.ASSEMBLY_GROUP)) + os.sep
    scripts = [s for s in only if s.endswith(".py")]
    run_build([s for s in part_scripts(scripts) if not s.startswith(asm)])


def assembly_scripts(only=()):
    """Every assembly script, each after the ones its NEEDS line names."""
    scripts = {os.path.splitext(os.path.basename(p))[0]: p
               for p in _scripts(paths.ASSEMBLY_GROUP)}
    needs = {}
    for name, rel in scripts.items():
        m = re.search(r"^NEEDS = \[(.*)\]", open(os.path.join(ROOT, rel)).read(), re.M)
        needs[name] = re.findall(r"[\"'](\w+)[\"']", m.group(1)) if m else []
    order, seen = [], set()

    def visit(name, path=()):
        if name in path:
            raise SystemExit(f"assemblies need each other: {path + (name,)}")
        if name not in seen:
            for n in needs.get(name, []):
                if n not in scripts:
                    raise SystemExit(f"{name} needs {n}, which has no script")
                visit(n, path + (name,))
            seen.add(name)
            order.append(scripts[name])
    for name in sorted(scripts):
        visit(name)
    wanted = [s for s in only if s in scripts.values()]
    return [s for s in order if not wanted or s in wanted]


def stage_assemblies(only):
    run_build(assembly_scripts(only))


def top_assemblies():
    """The assemblies no other assembly needs: what the bill of materials counts."""
    scripts = assembly_scripts()
    needed = set()
    for rel in scripts:
        m = re.search(r"^NEEDS = \[(.*)\]", open(os.path.join(ROOT, rel)).read(), re.M)
        needed.update(re.findall(r"[\"'](\w+)[\"']", m.group(1)) if m else [])
    return [os.path.splitext(rel)[0] + ".FCStd" for rel in scripts
            if os.path.splitext(os.path.basename(rel))[0] not in needed]


def stage_bom(_):
    tops = top_assemblies()
    if not tops:
        say("  no assembly, no bill of materials")
        return
    out = freecadcmd("code/bom.py", tops)
    say("\n".join(l for l in out.splitlines() if l.startswith("  bom")))
    if "BOM OK" not in out.splitlines() or not os.path.exists(os.path.join(ROOT, "BOM.md")):
        say(out[-2000:])
        raise SystemExit("bill of materials failed")


def stage_dress(only):
    dress([d for d in only if d.endswith(".FCStd")] or documents())


def dress(docs):
    """The GUI pass for each document (code/view.py), so it opens showing."""
    for doc in docs:
        cmd = FLATPAK + [f"--env=FCARGS={doc}", APP,
                         os.path.join(ROOT, "code", "view.py")]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                               env=gui_env())
        except subprocess.TimeoutExpired:
            raise SystemExit(f"{doc}: GUI pass timed out (deadlock?)")
        if "DRESS OK" not in p.stdout:
            say(p.stdout[-2000:], p.stderr[-2000:])
            raise SystemExit(f"{doc}: GUI pass failed")
        say(f"  {doc}: dressed")


def stage_meta(_):
    meta_check(documents())


def meta_check(docs):
    """Each document carries the project's licence and no absolute path.

    The author fields are not checked: they are whoever built or edited the
    document, as their FreeCAD preferences say.
    """
    import xml.etree.ElementTree as ET
    licence = paths.project().LICENSE
    bad = []
    for doc in docs:
        with zipfile.ZipFile(os.path.join(ROOT, doc)) as z:
            text = z.read("Document.xml").decode()
            every = " ".join(z.read(n).decode(errors="replace")
                             for n in z.namelist() if n.endswith((".xml", ".txt")))
        props = {}
        root = ET.fromstring(text)
        for prop in root.find("Properties"):
            s = prop.find("String")
            if s is not None:
                props[prop.get("name")] = s.get("value")
        if props.get("License") != licence:
            bad.append(f"{doc}: License is {props.get('License')!r}, not {licence!r}")
        if "/home/" in every or "/var/" in every or "/tmp/" in every:
            bad.append(f"{doc}: contains an absolute path")
    for b in bad:
        say("  " + b)
    if bad:
        raise SystemExit("metadata check failed")
    say(f"  {len(docs)} documents clean")


STAGES = [("parameters", stage_parameters), ("parts", stage_parts),
          ("assemblies", stage_assemblies), ("dress", stage_dress), ("meta", stage_meta),
          ("bom", stage_bom)]


def main(argv, stages=STAGES):
    global SHOW
    SHOW = "--show" in argv
    if "--list" in argv:
        for name, _ in stages:
            say(name)
        return 0
    names = [a for a in argv if a in dict(stages)]
    only = [a for a in argv if a.endswith((".py", ".FCStd"))]
    chosen = names or [n for n, _ in stages]
    t = time.time()
    for name, fn in stages:
        if name in chosen:
            say(f"== {name}")
            fn(only)
    say(f"done in {time.time() - t:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
