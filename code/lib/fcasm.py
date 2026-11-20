"""Assemblies from scripts: links to part bodies, joined on named datums.

- Join parts on datums that the part scripts write, never on faces or edges.
  A joint names a datum by its label; nothing here searches for geometry, so
  a rebuilt part cannot leave a joint on the wrong face.
- The owning document is saved before any link is set.
- Each side of a joint names its datum twice: FreeCAD wants two subs there.
- An assembly is what the workbench's own command makes: its `Type` is
  "Assembly", the joints are in its joint group, and what it holds is sorted
  into the groups `GROUPS`, as an assembly drawn by hand would be.
- Screws, nuts and inserts are objects of the Fasteners workbench, made in the
  assembly that uses them and joined by their own origin to the datum of
  their hole (`fastener`).  The workbench's own way, a `BaseObject` on the
  hole's edge, would name an edge.
- Every build checks itself: the solver converges, nothing is left touched,
  the degrees of freedom are counted from the joints and must come out as
  intended, every joint's two frames coincide, grounded parts stay where they
  are, no two parts overlap and no part hangs in the air.  With FCASM_SHAKE=1
  every moving part starts off its place, so the joints, not the start pose,
  have to put it there.

A sub-assembly is linked whole (`Assembly::AssemblyLink`, rigid), and a joint
reaches a datum inside it through the child link FreeCAD makes for each of
its parts.  Parts inside one are named `<sub-assembly>/<part>`.

A document built here has no view providers; the GUI pass (`code/view.py`)
gives the joints and fasteners the ones the workbenches' commands would.
"""

import os
import sys
import time

import FreeCAD as App

import fcprim

for _d in ("/app/freecad/Mod/Assembly", "/app/share/freecad/Mod/Assembly"):
    if os.path.isdir(_d) and _d not in sys.path:
        sys.path.append(_d)
import JointObject  # noqa: E402
import UtilsAssembly  # noqa: E402

# Degrees of freedom each joint type takes away.
TAKES = {"Fixed": 6, "Revolute": 5, "Cylindrical": 4, "Slider": 5, "Ball": 3}

# The groups an assembly's tree is sorted into, in this order; an empty one is
# left out.  What goes where follows from what each thing is (`_group_for`).
GROUPS = ("Printed_parts", "Norm_parts", "COTS", "Assemblies")


def fasteners_module():
    """The Fasteners workbench's `FastenersCmd`.

    The add-on imports `FreeCADGui` and then Draft, whose parameter reading
    segfaults freecadcmd unless Draft was imported first; so every process
    that opens a document holding fasteners imports `DraftVecUtils` before
    anything else (code/build.py does).
    """
    import DraftVecUtils  # noqa: F401
    path = os.path.join(App.getUserAppDataDir(), "Mod", "fasteners")
    if path not in sys.path:
        sys.path.append(path)
    import FastenersCmd
    return FastenersCmd


def is_fastener(obj):
    """True for an object the Fasteners workbench made."""
    return obj.TypeId == "Part::FeaturePython" and \
        type(getattr(obj, "Proxy", None)).__name__ == "FSScrewObject"


def category(obj):
    """Which of `GROUPS` a thing in an assembly belongs to, from what it is: a
    fastener, a sub-assembly, or a part (or a link to one) whose material the
    project calls printed or not.  The groups and the bill of materials both
    ask this, so they cannot disagree."""
    if is_fastener(obj):
        return "Norm_parts"
    if obj.TypeId == "Assembly::AssemblyLink":
        return "Assemblies"
    target = obj.getLinkedObject(True) if obj.TypeId == "App::Link" else obj
    return "Printed_parts" if fcprim.is_printed(target) else "COTS"


def shape_of(obj):
    """The solid of a part in its own frame.

    A PartDesign body's shape; a fastener's shape with its placement taken
    off; for an imported part (an App::Part of imported solids) the compound
    of its solids that are valid and have a volume, since a few of a vendor
    model's solids are not and spoil every boolean they meet.
    """
    if obj.TypeId == "PartDesign::Body":
        return obj.Shape.copy()
    if is_fastener(obj):
        s = obj.Shape.copy()
        s.Placement = App.Placement()
        return s
    import Part
    s = Part.getShape(obj)
    return Part.makeCompound([x for x in s.Solids if x.isValid() and x.Volume > 0])


def _near(shape, other, gap):
    """`shape`, or for a compound of many solids only those of its solids
    that may come within `gap` of `other`: whose boxes meet the box of one of
    `other`'s faces, or that lie inside `other` altogether.  The rest cannot
    touch it, and a distance or a boolean against hundreds of solids took
    minutes each.  None if no solid can come near."""
    solids = shape.Solids
    if len(solids) < 8:
        return shape
    boxes = []
    for f in other.Faces:
        b = f.BoundBox
        b.enlarge(gap)
        boxes.append(b)
    whole = other.BoundBox
    near = []
    for x in solids:
        xb = x.BoundBox
        if not whole.intersect(xb):
            continue
        if any(b.intersect(xb) for b in boxes) or \
                other.isInside(xb.Center, 1e-6, True):
            near.append(x)
    if not near:
        return None
    import Part
    return Part.makeCompound(near)


def _datum_of(body, label):
    found = [o for o in body.Group
             if o.TypeId == "PartDesign::CoordinateSystem" and o.Label == label]
    if len(found) != 1:
        raise SystemExit(f"{body.Document.Name}: {len(found)} datums labelled {label}")
    return found[0]


def _source_label(link):
    """The name a child link finally stands for, as the assembly that holds
    the part called it.  Each level of nesting copies the links of the level
    below, and a document holding several copies numbers their labels
    (Part001 ...), so only the last link in the chain keeps the label its own
    assembly gave it.  A fastener is no link: the chain ends on the object,
    whose label the Fasteners workbench writes itself, so its internal name,
    which the build gave it, stands for it."""
    while link.LinkedObject.TypeId == "App::Link":
        link = link.LinkedObject
    if is_fastener(link.LinkedObject):
        return link.LinkedObject.Name
    return link.Label


def _set_length(obj, length):
    """A fastener's length: a table entry, `Custom` and a number, or a number."""
    if obj.getTypeIdOfProperty("Length") == "App::PropertyEnumeration":
        text = f"{length:g}"
        if text in obj.getEnumerationsOfProperty("Length"):
            obj.Length = text
        else:
            obj.Length = "Custom"
            obj.LengthCustom = length
    else:
        obj.Length = length


def _axes(pl):
    return (pl.Rotation.multVec(App.Vector(0, 0, 1)), pl.Rotation.multVec(App.Vector(1, 0, 0)))


class Assembly:
    def __init__(self, script, name):
        folder = os.path.dirname(os.path.abspath(script))
        self.path = os.path.join(folder, name + ".FCStd")
        self.doc = App.newDocument(name)
        self.doc.saveAs(self.path)                 # links need a saved owner
        self.asm = self.doc.addObject("Assembly::AssemblyObject", "Assembly")
        self.asm.Label = name
        # What the workbench's command sets.  Left empty, a joint never solves
        # on a change of its own, and a solve after a joint's offset changed
        # moved the grounded part instead of the joined one.
        self.asm.Type = "Assembly"
        UtilsAssembly.getJointGroup(self.asm)      # first in the tree
        self.groups = {}
        for g in GROUPS:
            grp = self.asm.newObject("App::DocumentObjectGroup", g)
            grp.Label = g
            self.groups[g] = grp
        self.links, self.joints, self.grounded = {}, [], []
        self.ends = []                             # (kind, end a, end b) per joint
        self._docs = {}
        self.overlaps = set()
        self.report = {"assembly": name}

    @classmethod
    def open(cls, path):
        """An assembly document that has been built, opened to be looked at.

        Gives `items` and `datum` as during the build; nothing is changed.
        A fastener goes by its internal name, which the build gave it.
        """
        self = cls.__new__(cls)
        self.path = path
        self.doc = App.openDocument(path)
        found = [o for o in self.doc.Objects if o.TypeId == "Assembly::AssemblyObject"]
        if len(found) != 1:
            raise SystemExit(f"{path}: {len(found)} assemblies, wanted one")
        self.asm = found[0]
        self.links = {o.Label: o for o in self.asm.Group
                      if o.TypeId in ("App::Link", "Assembly::AssemblyLink")}
        self.links.update({o.Name: o for o in self.asm.Group if is_fastener(o)})
        self.joints, self.grounded, self.ends, self._docs, self.report = [], [], [], {}, {}
        return self

    # -- instances ---------------------------------------------------------
    def _open(self, path):
        if path not in self._docs:
            for d in App.listDocuments().values():
                if d.FileName and os.path.abspath(d.FileName) == os.path.abspath(path):
                    self._docs[path] = d
                    break
            else:
                self._docs[path] = App.openDocument(path)
        return self._docs[path]

    def part(self, label, path):
        """A link to the one body in the part document at `path`, or to its
        one top-level App::Part where the document is an import.  It goes in
        `Printed_parts` when the project calls its material printed, in
        `COTS` otherwise."""
        doc = self._open(path)
        bodies = [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]
        if not bodies:
            bodies = [o for o in doc.Objects if o.TypeId == "App::Part" and not o.InList]
        if len(bodies) != 1:
            raise SystemExit(f"{path}: {len(bodies)} bodies, wanted one")
        link = self.groups[category(bodies[0])].newObject("App::Link", label)
        link.LinkedObject = bodies[0]
        link.Label = label
        self.links[label] = link
        return link

    def subassembly(self, label, path):
        """A rigid link to the assembly in the document at `path`."""
        doc = self._open(path)
        found = [o for o in doc.Objects if o.TypeId == "Assembly::AssemblyObject"]
        if len(found) != 1:
            raise SystemExit(f"{path}: {len(found)} assemblies, wanted one")
        link = self.groups["Assemblies"].newObject("Assembly::AssemblyLink", label)
        link.LinkedObject = found[0]
        link.Rigid = True
        link.Label = label
        self.doc.recompute()                       # makes the child links
        self.links[label] = link
        return link

    def _child(self, label, child):
        """The child link of sub-assembly `label` that stands for `child`."""
        found = [c for c in self.links[label].Group
                 if c.TypeId == "App::Link" and _source_label(c) == child]
        if len(found) != 1:
            raise SystemExit(f"{label}: {len(found)} parts called {child}")
        return found[0]

    def items(self):
        """{name: (part, placement in the assembly)} for every part, down
        through sub-assemblies inside sub-assemblies.  The part is a body, an
        imported App::Part or a fastener."""
        def walk(prefix, link, base):
            out = {}
            for c in link.Group:
                if c.TypeId == "App::Link":
                    out[f"{prefix}/{_source_label(c)}"] = (
                        c.getLinkedObject(True), base.multiply(c.Placement))
                elif c.TypeId == "Assembly::AssemblyLink":
                    out.update(walk(f"{prefix}/{c.LinkedObject.Label}", c,
                                    base.multiply(c.Placement)))
            return out
        out = {}
        for label, link in self.links.items():
            if link.TypeId == "Assembly::AssemblyLink":
                out.update(walk(label, link, link.Placement))
            elif is_fastener(link):
                out[label] = (link, link.Placement)
            else:
                out[label] = (link.LinkedObject, link.Placement)
        return out

    # -- joints ------------------------------------------------------------
    def datum(self, label, datum, child=None):
        """(link, sub, frame in the link) for the datum labelled `datum`.

        `child` names the part inside a sub-assembly that carries it.
        """
        link = self.links[label]
        if child is None:
            lcs = _datum_of(link.LinkedObject, datum)
            return link, lcs.Name + ".", lcs.Placement
        c = self._child(label, child)
        lcs = _datum_of(c.getLinkedObject(True), datum)
        return link, f"{c.Name}.{lcs.Name}.", c.Placement.multiply(lcs.Placement)

    def ground(self, label):
        # In the joint group: FreeCAD 1.1's solver looks for grounded joints
        # there, and one placed beside it left the assembly unsolved.
        jg = UtilsAssembly.getJointGroup(self.asm)
        gj = jg.newObject("App::FeaturePython", "GroundedJoint")
        JointObject.GroundedJoint(gj, self.links[label])
        gj.Label = f"Grounded {label}"
        self.grounded.append(label)

    def _new_joint(self, kind, label, ref1, ref2):
        jg = UtilsAssembly.getJointGroup(self.asm)
        j = jg.newObject("App::FeaturePython", "Joint")
        JointObject.Joint(j, JointObject.JointTypes.index(kind))
        j.Label = label
        j.Reference1 = ref1
        j.Reference2 = ref2
        return j

    def joint(self, kind, a, b, label=None):
        """A joint of `kind` between datums a and b, each (part, datum[, child]).

        Part a is seated first: put where its datum lies on b's, Z the same
        way round.  A joint is satisfied with its two frames either matched
        or flipped, and the solver keeps whichever the start pose is nearer;
        a part started with its frame flipped came out on the wrong side of
        the face it was joined to.  So b must already be in place, which
        joining outwards from the grounded part gives.
        """
        la, sa, fa = self.datum(*a)
        lb, sb, fb = self.datum(*b)
        if a[0] in self.grounded:
            raise SystemExit(f"joint {a} - {b}: the first part must be the one that moves")
        la.Placement = lb.Placement.multiply(fb).multiply(fa.inverse())
        j = self._new_joint(kind, label or f"{kind} {'.'.join(a)} - {'.'.join(b)}",
                            (la, [sa, sa]), (lb, [sb, sb]))
        self.joints.append((kind, a[0], b[0]))
        self.ends.append((kind, lambda a=a: self.frame(a), lambda b=b: self.frame(b),
                          j.Label))
        return j

    def bought(self, label, path, datum, onto, into=()):
        """A bought part drawn as its own document (an envelope), fixed on a
        datum of a part already in place: its datum `datum` on `onto` =
        (part, datum[, child]).

        `into` names the parts it may overlap by design, as the contact check
        names them.
        """
        self.part(label, path)
        self.joint("Fixed", (label, datum), onto)
        for other in into:
            self.overlaps.add(frozenset((label, other)))
        return self.links[label]

    def fastener(self, label, kind, diameter, length, onto, made_of, at="seat", into=()):
        """A Fasteners object fixed in the hole whose datum is `onto` =
        (part, datum[, child]).

        `kind` is the workbench's type ("ISO4762", "IUTHeatInsert" ...),
        `diameter` its size ("M3") and `length` in mm.  The workbench draws a
        fastener with its axis on Z, the shank or body running down -Z from
        the origin: a screw's head bearing face (the top of a countersunk
        head), an insert's mouth.  The joint holds that origin on the datum,
        which has Z out of the material, or with `at="tip"` the end of the
        shank, by an offset that follows the length.  The workbench names the
        object's label itself ("M3x8-Screw"); `label` is what this build
        calls it and becomes its internal name, which nothing renames, so a
        parent assembly can name it too.  `into` names the parts it may
        overlap by design, such as the insert a screw threads into, since
        neither is drawn with threads.
        """
        fc = fasteners_module()
        obj = self.groups["Norm_parts"].newObject("Part::FeaturePython", label)
        if obj.Name != label:
            raise SystemExit(f"{label}: FreeCAD named the fastener {obj.Name}; a "
                             f"fastener's label must be a new, plain identifier")
        fc.FSScrewObject(obj, kind, None)
        # The first recompute after a new diameter resets the length to the
        # table's, so the length goes in after it.
        obj.Diameter = diameter
        self.doc.recompute()
        _set_length(obj, length)
        self.doc.recompute()
        local = shape_of(obj)
        drawn = -local.BoundBox.ZMin
        if obj.Diameter != diameter or abs(drawn - length) > 1e-6:
            raise SystemExit(f"{label}: the workbench made {kind} {obj.Diameter} x "
                             f"{drawn:.3f}, wanted {diameter} x {length}")
        fcprim.material(obj, made_of)
        self.links[label] = obj
        lb, sb, fb = self.datum(*onto)
        offset = App.Placement()
        if at == "tip":
            offset = App.Placement(App.Vector(0, 0, -length), App.Rotation())
        elif at != "seat":
            raise SystemExit(f"{label}: at={at!r}, wanted 'seat' or 'tip'")
        obj.Placement = lb.Placement.multiply(fb).multiply(offset.inverse())
        # The whole object on this side of the joint: its own origin is the frame.
        j = self._new_joint("Fixed", f"Fixed {obj.Label}{' tip' if at == 'tip' else ''}"
                            f" - {'.'.join(onto)}", (obj, ["", ""]), (lb, [sb, sb]))
        if at == "tip":
            j.Offset1 = offset
            prop = "LengthCustom" if hasattr(obj, "LengthCustom") else "Length"
            j.setExpression(".Offset1.Base.z", f"-{obj.Name}.{prop}")
        self.joints.append(("Fixed", label, onto[0]))
        self.ends.append(("Fixed", lambda: obj.Placement.multiply(j.Offset1),
                          lambda: self.frame(onto), j.Label))
        for other in into:
            self.overlaps.add(frozenset((label, other)))
        return obj

    def note(self, text):
        """A sentence the bill of materials prints for this assembly, such as
        what it leaves out.  Kept in the document, as `BomNotes`."""
        if not hasattr(self.asm, "BomNotes"):
            self.asm.addProperty("App::PropertyStringList", "BomNotes", "Assembly",
                                 "Sentences the bill of materials prints for this assembly")
        self.asm.BomNotes = list(self.asm.BomNotes) + [text]

    # -- checks ------------------------------------------------------------
    def solve(self, free):
        """Solve and check; `free` is how many degrees of freedom are meant.

        The count is structural: six per part or rigid sub-assembly that is
        not grounded, less what each joint takes.  A joint too many or too
        few changes it.  The solver must also converge and leave nothing
        touched, which is how an over-constraint showed itself in another
        project built this way.  Then every joint's two frames must coincide
        and every grounded part must be where it was: a check of where parts
        lie relative to each other passes even when the solver moved the
        grounded part.  FCASM_SHAKE=1 starts every moving part 2 mm and
        10 degrees off, to show that the joints, not the start pose, put it
        in place.
        """
        self.doc.recompute()
        moving = [k for k in self.links if k not in self.grounded]
        dof = 6 * len(moving) - sum(TAKES[k] for k, _, _ in self.joints)
        if dof != free:
            raise SystemExit(f"{self.doc.Name}: {dof} degrees of freedom by the "
                             f"joints, wanted {free}")
        held = {k: App.Placement(self.links[k].Placement) for k in self.grounded}
        if os.environ.get("FCASM_SHAKE"):
            for k in moving:
                self.links[k].Placement = self.links[k].Placement.multiply(
                    App.Placement(App.Vector(1.2, -1.1, 1.2),
                                  App.Rotation(App.Vector(1, 2, 3), 10)))
        rc = self.asm.solve()
        if rc != 0:
            raise SystemExit(f"{self.doc.Name}: solver did not converge (rc={rc})")
        self.doc.recompute()
        touched = [o.Label for o in self.doc.Objects if "Touched" in o.State]
        if touched:
            raise SystemExit(f"{self.doc.Name}: still touched after recompute: "
                             f"{touched[:6]}")
        bad = [o.Label for o in self.doc.Objects
               if "Invalid" in o.State or "Error" in o.State]
        if bad:
            raise SystemExit(f"{self.doc.Name}: failed objects: {bad[:6]}")
        for k, pl in held.items():
            now = self.links[k].Placement
            if not now.isSame(pl, 1e-9):
                raise SystemExit(f"{self.doc.Name}: the grounded {k} moved, from "
                                 f"{pl} to {now}")
        worst = self.joint_check()
        self.report.update({"instances": len(self.links), "joints": len(self.joints),
                            "degrees_of_freedom": dof})
        print(f"\n  solved: {len(self.links)} parts and sub-assemblies, "
              f"{len(self.joints)} joints, {dof} degrees of freedom as meant, every "
              f"joint's frames within {worst:.1e} mm", flush=True)

    def joint_check(self, tolerance=1e-6):
        """Each joint's two frames where its kind says: a Fixed joint's origin,
        Z and X the same, a Revolute joint's origin and Z.  Returns the worst
        difference."""
        worst = 0.0
        for kind, end_a, end_b, label in self.ends:
            fa, fb = end_a(), end_b()
            (za, xa), (zb, xb) = _axes(fa), _axes(fb)
            off = max((fa.Base - fb.Base).Length, (za - zb).Length)
            if kind == "Fixed":
                off = max(off, (xa - xb).Length)
            elif kind != "Revolute":
                continue
            worst = max(worst, off)
            if off > tolerance:
                raise SystemExit(f"{self.doc.Name}: joint {label!r} is {off:.6f} off")
        return worst

    def frame(self, end):
        """Where the datum `end` = (part, datum[, child]) is, in the assembly."""
        link, _, local = self.datum(*end)
        return link.Placement.multiply(local)

    def datum_check(self, a, b, tolerance=1e-6):
        """Two datums that no joint ties must coincide: origin, Z and X.

        a and b are (part, datum[, child]) as for a joint.  This is how an
        assembly checks a fit that a joint would otherwise force, such as the
        far end of a part held at its other end.
        """
        frames = [self.frame(a), self.frame(b)]
        fa, fb = frames
        z = [f.Rotation.multVec(App.Vector(0, 0, 1)) for f in frames]
        x = [f.Rotation.multVec(App.Vector(1, 0, 0)) for f in frames]
        off = max((fa.Base - fb.Base).Length, (z[0] - z[1]).Length, (x[0] - x[1]).Length)
        if off > tolerance:
            raise SystemExit(f"{self.doc.Name}: {'.'.join(a)} is {off:.6f} mm off "
                             f"{'.'.join(b)}")
        self.report.setdefault("datums_matched", []).append(f"{'.'.join(a)} = {'.'.join(b)}")

    def contact_check(self, gap, alone=()):
        """No two parts overlap, and every part is within `gap` of another.

        Overlap is the common volume of each pair whose boxes meet; contact
        is the distance between solids.  `alone` lists (part, reason) for
        parts allowed to touch nothing.  The pairs `bought` and `fastener`
        registered (an insert in its part, a screw in its thread) may overlap;
        nothing else.
        """
        shapes = {}
        for name, (body, pl) in self.items().items():
            s = shape_of(body)
            s.Placement = pl.multiply(s.Placement)
            shapes[name] = s
        keys = sorted(shapes)
        near = {k: False for k in keys}
        worst = (0.0, None)
        subs = {k for k, l in self.links.items() if l.TypeId == "Assembly::AssemblyLink"}
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                # Two parts of one rigid sub-assembly: its own build checked
                # them, and they stay as it put them.
                sa, sb = a.split("/")[0], b.split("/")[0]
                if "/" in a and "/" in b and sa == sb and sa in subs:
                    near[a] = near[b] = True
                    continue
                box = shapes[a].BoundBox
                box.enlarge(gap)
                if not box.intersect(shapes[b].BoundBox):
                    continue
                t = time.time()
                na, nb = _near(shapes[a], shapes[b], gap), _near(shapes[b], shapes[a], gap)
                if na is None or nb is None:
                    continue
                d = na.distToShape(nb)[0]
                t1 = time.time()
                if d <= gap:
                    near[a] = near[b] = True
                if d <= 1e-6 and frozenset((a, b)) not in self.overlaps:
                    v = na.common(nb).Volume
                    if v > worst[0]:
                        worst = (v, (a, b))
                if os.environ.get("FCASM_TIMES") and time.time() - t > 2:
                    print(f"    {a} / {b}: distance {d:.4f} in {t1 - t:.1f} s, "
                          f"overlap in {time.time() - t1:.1f} s", flush=True)
        if worst[0] > 1e-6:
            raise SystemExit(f"{self.doc.Name}: {worst[1][0]} and {worst[1][1]} "
                             f"overlap by {worst[0]:.6f} mm^3")
        allowed = dict(alone)
        lonely = [k for k in keys if not near[k] and k not in allowed]
        if lonely:
            raise SystemExit(f"{self.doc.Name}: touching nothing within {gap} mm: "
                             f"{lonely}")
        self.report.update({"overlap": "none", "contact_gap": gap,
                            "overlaps_by_design": len(self.overlaps),
                            "excused": [f"{k}: {why}" for k, why in allowed.items()]})
        print(f"\n  contacts: {len(keys)} parts, no overlap, each within {gap} mm "
              f"of another" + (f", {len(allowed)} excused" if allowed else ""),
              flush=True)

    def save(self):
        """Save the document, and what its checks found to data/build/."""
        self.report["groups"] = {name: len(g.Group) for name, g in self.groups.items()
                                 if g.Group}
        for name, g in list(self.groups.items()):
            if not g.Group:
                self.doc.removeObject(g.Name)
                del self.groups[name]
        fcprim.meta(self.doc)
        self.doc.recompute()
        self.doc.save()
        self.report["parts"] = len(self.items())
        if self.report.get("datums_matched"):
            print(f"\n  datums: {len(self.report['datums_matched'])} pairs that no joint "
                  f"ties coincide", flush=True)
        fcprim.report(self.doc.Name, self.report)
        print(f"  saved {self.path}", flush=True)
