"""Write the view data a GUI needs before it will show a built part.

`freecadcmd` has no view providers, so the `.FCStd` files it writes contain no
`GuiDocument.xml`.  Opening one in the real FreeCAD then hides every object and
starts the camera a few millimetres wide at the origin: the part opens blank.
Only a GUI can write that file, so this is the one script that runs under the
full FreeCAD binary.  `rebuild.py dress` runs it, one process per document:

    flatpak run --env=FCARGS=model/<group>/<Part>.FCStd --env=FCROOT=<root> \
        org.freecad.FreeCAD <root>/code/view.py

**It needs a real X11 display.**  Under `QT_QPA_PLATFORM=offscreen` there is
no GL context, and in another project built this way six of ten assemblies
deadlocked in `openDocument` with no error and no timeout.  So windows appear on screen while
it runs.  Camera, fit check and framing come from that project.
"""

import math
import os
import re
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from FreeCAD import Rotation, Vector

HERE = os.environ["FCROOT"]
sys.path.insert(0, os.path.join(HERE, "code", "lib"))

import fcprim  # noqa: E402  (needs the path above)

# How far the camera stands back, and how much air is left around the model,
# both as multiples of its diagonal.  An orthographic view is framed by its
# height rather than by its distance, so the standoff only has to clear the
# geometry and keep it between the near and far planes.
STANDOFF = 3.0
MARGIN = 1.15

# What FreeCAD stores in GuiDocument.xml as <Camera settings="...">, and reads
# back when the document is opened.
CAMERA = """#Inventor V2.1 ascii


OrthographicCamera {{
  viewportMapping ADJUST_CAMERA
  position {p.x:.6g} {p.y:.6g} {p.z:.6g}
  orientation {axis.x:.8g} {axis.y:.8g} {axis.z:.8g}  {angle:.8g}
  nearDistance {near:.6g}
  farDistance {far:.6g}
  aspectRatio 1
  focalDistance {focal:.6g}
  height {height:.6g}
}}
"""

SKIP = ("Assembly::AssemblyObject", "Assembly::JointGroup")

# A camera no real fit could produce: one millimetre tall, looking at the
# origin from a millimetre away.  `check_visible` points the camera here and
# asks FreeCAD to fit, so that a scene with anything at all in it must move it.
BOGUS = """#Inventor V2.1 ascii


OrthographicCamera {
  viewportMapping ADJUST_CAMERA
  position 0 0 1
  orientation 0 0 1  0
  aspectRatio 1
  focalDistance 5
  height 1
}
"""

# The octant FreeCAD's own isometric view looks from: front, right and above.
EYE = Vector(1, -1, 1)


def say(*args):
    """Print, straight down the file descriptor.

    Not `print`: the GUI puts its own object in `sys.stdout` and what goes
    into it is not seen until the process ends, so a run that takes ten
    minutes says nothing for ten minutes and a run that dies says nothing at
    all.  Writing to fd 1 is neither buffered nor redirected.
    """
    os.write(1, (" ".join(str(a) for a in args) + "\n").encode())


def placed_box(doc):
    """The bounding box of everything the document is going to show.

    An `App::Link` shares one shape with every other link to the same part and
    carries the placement itself, so its shape has to be moved before it
    counts -- otherwise a whole machine measures as one part at the origin.

    But a link's `Placement` is only global when the link sits at the top of
    the document.  Inside a nested assembly it is relative to the container,
    and reading it as global flings the part off into space: measured that way
    the whole machine came out 2137mm across the diagonal when it is really
    719mm, and every top-level assembly was framed three times too far out.
    An `Assembly::AssemblyObject` carries the union of everything it holds,
    already correctly placed and nesting and all -- so where there is one, it
    is the answer, and the links it contains must not be counted again.
    """
    containers = [obj for obj in doc.Objects
                  if obj.TypeId == "Assembly::AssemblyObject"]
    if containers:
        box = None
        for obj in containers:
            shape = getattr(obj, "Shape", None)
            if shape is None or shape.isNull() or not shape.Solids:
                continue
            box = _united(box, box_of(shape))
        if box is not None:
            return box

    box = None
    for obj in doc.Objects:                # a part document: no container
        if not getattr(obj, "Visibility", False) or obj.TypeId in SKIP:
            continue
        shape = getattr(obj, "Shape", None)
        if shape is None or shape.isNull() or not shape.Solids:
            continue
        if obj.TypeId == "App::Link":
            shape = obj.LinkedObject.Shape.copy()
            shape.Placement = obj.Placement.multiply(shape.Placement)
        box = _united(box, box_of(shape))
    return box


def finite(box):
    """A bounding box of a real model: finite numbers, and smaller than a
    kilometre.  Coin stores a camera in single precision, which ends near
    3.4e38, so a box of 1e100 is saved as a camera of height 0 at the origin."""
    return box is not None and box.isValid() and all(
        math.isfinite(v) and abs(v) < 1e6
        for v in (box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax))


def box_of(shape):
    """The bounding box of what is solid in `shape`: the union of its solids'
    boxes.  A shape's own box also counts what is not solid, and something in
    an imported board (KiCad) without bounds made a whole assembly's box
    +-1e100 while every one of its 1554 solids was a sensible size."""
    box = None
    for solid in shape.Solids:
        b = solid.BoundBox
        if finite(b):
            box = _united(box, b)
    if box is None and finite(shape.BoundBox):
        box = shape.BoundBox
    return box


def _united(box, other):
    if other is None:
        return box
    return other if box is None else box.united(other)


def isometric():
    """The orientation FreeCAD's own isometric view uses.

    Built rather than borrowed: `View3DInventor.viewIsometric` animates the
    camera through the render loop, and an offscreen view never renders, so
    calling it leaves the camera exactly where it was.  A camera looks down its
    own -Z with +Y up the screen, so this turns +Z to face the eye and then
    spins about that axis until the screen's up is the world's up, flattened.
    It agrees with FreeCAD's own axonometric quaternion to six decimals.
    """
    axis = Vector(EYE)
    axis.normalize()
    swing = Rotation(Vector(0, 0, 1), axis)
    up = Vector(0, 0, 1) - axis * axis.z
    up.normalize()
    return Rotation(swing.multVec(Vector(0, 1, 0)), up).multiply(swing)


def height(view):
    """The height of `view`'s camera, which is what frames an orthographic one."""
    return float(re.search(r"height\s+(\S+)", view.getCamera()).group(1))


def check_visible(view, name):
    """Fail unless the document has something in its scene graph to show.

    The bug this guards against showed nothing and reported success: the check
    was that every `Body.ViewObject.Visibility` was `True`, which is necessary
    but not sufficient -- under `DisplayModeBody='Through'` a visible body with
    a hidden tip draws nothing, and all 49 part documents were saved blank.
    (The assemblies were not: `Assembly::AssemblyObject` carries the union
    shape itself, so they drew even while their links did not.)  So measure the
    scene, not the property.

    `fitAll` uses `SoGetBoundingBoxAction` and needs no GL context, so it works
    offscreen -- but an empty scene gives it no bounding box to fit and it
    leaves the camera exactly where it stands.  Park the camera somewhere no
    fit could ever return and the height failing to change *is* the failure.

    This runs before `frame`, which sets the camera that is actually saved.
    """
    view.setCamera(BOGUS)
    view.fitAll()
    if height(view) <= 1.0001:
        raise RuntimeError(f"{name}: nothing in the scene, opens blank")


def frame(view, box):
    """Aim the camera at `box` from the standard isometric direction.

    `fitAll` would frame it tighter, and does work offscreen (see
    `check_visible`), but it only ever moves the camera along the direction it
    already points: it fits, it does not aim.  The isometric orientation and
    the near and far planes have to be computed from the geometry regardless,
    so the height is too, and the framing stays in one place.
    """
    if not finite(box):
        raise RuntimeError(f"no finite bounding box to frame ({box})")
    rotation = isometric()
    span = box.DiagonalLength
    distance = span * STANDOFF
    view.setCamera(CAMERA.format(
        p=box.Center + rotation.multVec(Vector(0, 0, 1)) * distance,
        axis=rotation.Axis, angle=rotation.Angle,
        near=distance - span, far=distance + span,
        focal=distance, height=span * MARGIN))


def viewproviders(doc):
    """Give joints and fasteners the view providers the workbenches' own
    commands attach, which a document built headless lacks: without them a
    joint draws no markers and a double click opens no joint dialog, and a
    fastener has no icon in the tree.  Returns how many it attached.

    A missing view provider reads as the placeholder 1, not None.  The
    workbench makes its view provider before the joint names its parts; here
    it names them, the constructor's `Proxy` assignment triggers
    updates that need what `attach()` sets up, and `attach()` is not called
    for an object already on screen.  So each is attached first and then
    constructed, with the class's own code.
    """
    import JointObject
    n = 0
    for obj in doc.Objects:
        proxy = getattr(obj, "Proxy", None)
        vo = getattr(obj, "ViewObject", None)
        if vo is None or hasattr(getattr(vo, "Proxy", None), "attach"):
            continue
        if isinstance(proxy, JointObject.GroundedJoint):
            cls = JointObject.ViewProviderGroundedJoint
        elif isinstance(proxy, JointObject.Joint):
            cls = JointObject.ViewProviderJoint
        elif type(proxy).__name__ == "FSScrewObject":
            import FastenersCmd
            cls = FastenersCmd.FSViewProviderTree
        else:
            continue
        vp = cls.__new__(cls)
        vp.attach(vo)
        cls.__init__(vp, vo)
        n += 1
    missing = [o.Label for o in doc.Objects
               if type(getattr(o, "Proxy", None)).__name__ in
               ("Joint", "GroundedJoint", "FSScrewObject")
               and not hasattr(getattr(o.ViewObject, "Proxy", None), "attach")]
    if missing:
        raise RuntimeError(f"no view provider for {missing[:5]}")
    return n


def dress(path):
    """Give one document its visibilities and its camera, and save it back."""
    doc = App.openDocument(path)
    attached = viewproviders(doc)
    if attached:
        say(f"  {os.path.relpath(path, HERE)}: {attached} view provider(s) attached")
    fcprim.dress(doc)
    fcprim.colour(doc)
    view = Gui.getDocument(doc.Name).mdiViewsOfType("Gui::View3DInventor")[0]
    box = placed_box(doc)
    if box is not None:                    # nothing solid: leave the camera be
        check_visible(view, os.path.relpath(path, HERE))
        frame(view, box)
    doc.saveAs(path)                       # saveAs: save() skips a clean file
    return sum(1 for obj in doc.Objects if getattr(obj, "Visibility", False))


def main(argv):
    paths = [p if os.path.isabs(p) else os.path.join(HERE, p)
             for p in os.environ.get("FCARGS", "").split("|") if p]
    if not paths:
        say("no documents found")
        return 1
    failed = []
    for path in paths:
        name = os.path.relpath(path, HERE)
        try:
            shown = dress(path)
            say(f"  {name}: {shown} object(s) shown")
        except BaseException:
            failed.append(name)
            say(f"  {name}: FAILED")
            say(traceback.format_exc())
        # An assembly pulls its parts open as links; close everything between
        # documents so the next one is saved on its own.
        for open_name in list(App.listDocuments()):
            App.closeDocument(open_name)
    say(f"\n{len(paths) - len(failed)}/{len(paths)} dressed")
    say("DRESS OK" if not failed else "DRESS FAILED")
    for name in failed:
        say(f"  FAILED {name}")
    return 1 if failed else 0


STATUS = 1                                 # until main says otherwise
try:
    STATUS = main(None)
finally:
    # Nothing closes the application for us: the script runs inside a GUI that
    # would otherwise sit there with no window on an offscreen display.  So
    # leave the hard way.  Tearing down a run can wedge on a lock and sit there
    # at no CPU for ever, long after the last document is safely on disk --
    # `M8_55`, whose 44 turns of swept thread make much the biggest scene graph
    # here, hangs every time, minutes after it has printed that it is done.
    # Everything is saved and closed by now, so `os._exit` skips the teardown
    # entirely, and `say` has already written every line to fd 1.
    #
    # Not `Gui.getMainWindow().close()` first: that *is* the call that wedges,
    # and it buys nothing when the next line ends the process regardless.
    os._exit(STATUS)
