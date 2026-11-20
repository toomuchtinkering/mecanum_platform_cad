"""Helpers for building FreeCAD PartDesign bodies from sketches.

Every part is modelled the way it would be drawn in the GUI -- a PartDesign
Body holding fully constrained sketches driven by pads, pockets, revolves and
patterns -- so that every dimension can be changed by double clicking a sketch
and editing a constraint, without touching the script that wrote it.

Sketches produced here come out fully constrained: each straight segment of a
rectilinear profile carries its horizontal/vertical constraint plus one
dimension locating it, and every circle carries a diameter and its two centre
distances.  Constraints are named after what they control, so they read
sensibly in the Constraints panel, and a constraint can be driven from the
shared spreadsheet with `drive`.
"""

import json
import math
import os

import FreeCAD as App
import Part
import Sketcher
from FreeCAD import Placement, Rotation, Vector

import paths

# Sketcher's shorthand for the sketch origin and the two sketch axes.
ROOT_POINT = (-1, 1)
X_AXIS = -1
Y_AXIS = -2


def document(name):
    """Return a fresh (empty) document called `name`."""
    if name in App.listDocuments():
        App.closeDocument(name)
    return App.newDocument(name)


def body(doc, label="Body"):
    b = doc.addObject("PartDesign::Body", "Body")
    b.Label = label
    return b


def lcs(bdy, label, at=(0.0, 0.0, 0.0), axis=(0.0, 0.0, 1.0), roll=0.0,
        expressions=None):
    """A named mounting datum on a body, for the assembly to join against.

    The assembly joins parts by referring to these rather than to faces.  A
    joint that names `Face12` breaks the moment an earlier sketch changes and
    the face is renumbered -- the topological naming problem every part script
    here is written to avoid -- whereas a coordinate system placed by the part's
    own script is parametric and survives a rebuild.

    `axis` is the direction the datum's **Z** points, because that is the axis
    every joint turns or slides about: down a bore, along a rod, up a bolt.
    `roll` then spins the datum about it, which matters only where the other two
    axes have to line up too, as a `Fixed` joint's do.  `at` is in the body's
    own coordinates, so it comes straight off the dimensions the sketches use.

    The datum is deliberately left unattached (`MapMode` deactivated): mapping
    it to a face would reintroduce exactly the fragility it exists to avoid.
    `expressions` maps a property path such as `Placement.Base.y`, or
    `Placement` itself, to an expression, so the datum follows the dimensions
    it is made of; `at`, `axis` and `roll` are then only its first position.
    """
    o = bdy.Document.addObject("PartDesign::CoordinateSystem", "LCS")
    o.Label = label
    bdy.addObject(o)
    o.MapMode = "Deactivated"
    swing = Rotation(Vector(0.0, 0.0, 1.0), Vector(*axis))
    o.Placement = Placement(Vector(*at),
                            swing * Rotation(Vector(0.0, 0.0, 1.0), roll))
    for path, expression in (expressions or {}).items():
        o.setExpression(path, expression)
    return o


def frame(x, z):
    """(axis, roll) for `lcs` from where the datum's X and Z should point."""
    x, z = Vector(*x), Vector(*z)
    swing = Rotation(Vector(0.0, 0.0, 1.0), z)
    x0 = swing.multVec(Vector(1.0, 0.0, 0.0))
    roll = math.degrees(math.atan2(x0.cross(x).dot(z), x0.dot(x)))
    return tuple(z), roll


def _origin_feature(bdy, role):
    for feature in bdy.Origin.OriginFeatures:
        if feature.Role == role:
            return feature
    raise KeyError(f"no origin feature {role!r}")


def sketch(bdy, label, plane="XY_Plane", offset=0.0, angle=0.0, shift=(0.0, 0.0)):
    """An empty sketch attached to one of the body's origin planes.

    `offset` shifts the sketch along the plane's normal and `shift` within the
    plane, which is what the Attachment Offset field in the GUI does; `angle`
    turns the sketch about its own normal.

    The origin planes map to global coordinates like this -- worth keeping in
    mind, because XZ is the odd one out:

        XY_Plane   H -> +X   V -> +Y   pad -> +Z   offset -> +Z
        XZ_Plane   H -> +X   V -> +Z   pad -> -Y   offset -> -Y
        YZ_Plane   H -> +Y   V -> +Z   pad -> +X   offset -> +X

    A pocket cuts the other way from a pad on the same plane, so on XZ a pad
    runs towards -Y and a pocket towards +Y unless `reversed_` says otherwise.
    """
    sk = bdy.Document.addObject("Sketcher::SketchObject", "Sketch")
    sk.Label = label
    bdy.addObject(sk)
    support = [(_origin_feature(bdy, plane), "")]
    # FreeCAD 1.0 renamed Support to AttachmentSupport.
    if hasattr(sk, "AttachmentSupport"):
        sk.AttachmentSupport = support
    else:
        sk.Support = support
    sk.MapMode = "FlatFace"
    if offset or angle or shift != (0.0, 0.0):
        sk.AttachmentOffset = Placement(
            Vector(shift[0], shift[1], offset),
            Rotation(Vector(0, 0, 1), angle))
    return sk


def _locate(sk, geo_id, pos_id, u, v, name, keep_zero=False):
    """Constrain a sketch point to (u, v), naming the dimensions after `name`.

    A coordinate of zero is held by a point-on-axis constraint rather than a
    zero length dimension, which is what the GUI would produce too -- unless
    `keep_zero`: a coordinate that an expression drives needs its dimension
    even where the expression is zero now, or the point stays on the axis
    when the cells behind it change.
    """
    for value, axis, kind, suffix in ((u, Y_AXIS, "DistanceX", "u"),
                                      (v, X_AXIS, "DistanceY", "v")):
        if abs(value) < 1e-9 and not keep_zero:
            sk.addConstraint(
                Sketcher.Constraint("PointOnObject", geo_id, pos_id, axis))
        else:
            idx = sk.addConstraint(
                Sketcher.Constraint(kind, *ROOT_POINT, geo_id, pos_id, value))
            sk.renameConstraint(idx, f"{name}_{suffix}")


class _Rails:
    """Union-find over vertex indices sharing a coordinate."""

    def __init__(self, count):
        self.parent = list(range(count))

    def find(self, i):
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i, j):
        a, b = self.find(i), self.find(j)
        if a != b:
            self.parent[a] = b

    def classes(self):
        """Representative vertex index per class, in vertex order."""
        seen = {}
        for i in range(len(self.parent)):
            seen.setdefault(self.find(i), i)
        return sorted(seen.values())


def arc_sweep(a, b, spec):
    """Normalise an arc specification to (radius, signed sweep in degrees).

    A bare radius means the arc that turns through less than half a circle:
    positive keeps the centre to the left of the way from `a` to `b`, negative
    to the right.  Since a chord and a radius admit a major arc as well, that
    one is asked for as a `(radius, sweep)` pair -- `(7.6, -255)` for a bore
    open at one side.
    """
    if isinstance(spec, (tuple, list)):
        radius, sweep = spec
        return abs(radius), float(sweep)
    span = math.hypot(b[0] - a[0], b[1] - a[1])
    if abs(spec) < span / 2 - 1e-9:
        raise ValueError(f"radius {spec} too small to span {span:.3f}")
    minor = 2 * math.degrees(math.asin(min(span / 2 / abs(spec), 1.0)))
    return abs(spec), minor if spec > 0 else -minor


def _arc_between(a, b, spec):
    """An arc from `a` to `b`, plus which of its ends is which.

    Arcs are always built anticlockwise from their start angle, so one that
    turns clockwise from `a` to `b` has to be stored back to front; the caller
    is told which end is which so it can still chain the profile in order.
    """
    (x0, y0), (x1, y1) = a, b
    radius, sweep = arc_sweep(a, b, spec)
    span = math.hypot(x1 - x0, y1 - y0)
    half = span / 2.0
    # The centre sits on the chord's perpendicular bisector, at a distance set
    # by the sweep -- which puts it on the far side for a major arc, and on the
    # chord itself for a half circle.
    turn = math.radians(sweep) / 2.0
    offset = half * math.cos(turn) / math.sin(turn)
    left = (-(y1 - y0) / span, (x1 - x0) / span)
    cx = (x0 + x1) / 2.0 + left[0] * offset
    cy = (y0 + y1) / 2.0 + left[1] * offset
    start = math.atan2(y0 - cy, x0 - cx)
    end = math.atan2(y1 - cy, x1 - cx)
    circle = Part.Circle(Vector(cx, cy, 0), Vector(0, 0, 1), radius)
    if sweep > 0:                              # anticlockwise: as drawn
        return Part.ArcOfCircle(circle, start, end), (1, 2)
    return Part.ArcOfCircle(circle, end, start), (2, 1)


def polyline(sk, points, name="profile", fillets=None, arcs=None):
    """Add a closed profile through `points`, fully constrained.

    Horizontal and vertical segments get the matching constraint, which ties
    their endpoints' Y (resp. X) together.  Exactly one dimension is then
    added per group of coordinates that those constraints left equal, so the
    sketch comes out fully constrained with no redundancy whatever mix of
    axis-aligned and slanted segments the profile happens to use.

    `arcs` maps a segment's index -- the one leaving points[i] -- to a signed
    radius, turning that segment into an arc; see `arc_sweep` for the sign and
    for how to ask for a major arc.

    `fillets` maps a corner's index in `points` to its radius.  The corners are
    rounded with the sketcher's own fillet operation, the same one the GUI
    offers, so the sharp corner survives as a construction point and the
    dimensions above go on locating it.
    """
    arcs = arcs or {}
    first = len(sk.Geometry)
    count = len(points)
    ends = []                                  # (start PosId, end PosId) each
    for i in range(count):
        a, b = points[i], points[(i + 1) % count]
        if i in arcs:
            geometry, pos = _arc_between(a, b, arcs[i])
        else:
            geometry, pos = Part.LineSegment(Vector(*a, 0), Vector(*b, 0)), (1, 2)
        sk.addGeometry(geometry, False)
        ends.append(pos)

    # Chain the segments end to end.
    for i in range(count):
        nxt = (i + 1) % count
        sk.addConstraint(Sketcher.Constraint(
            "Coincident", first + i, ends[i][1], first + nxt, ends[nxt][0]))

    for i, spec in sorted(arcs.items(), key=lambda item: item[0]):
        a, b = points[i], points[(i + 1) % count]
        radius, sweep = arc_sweep(a, b, spec)
        # A half circle spans its own diameter, so dimensioning the radius as
        # well as both ends is degenerate and the solver rejects the sketch.
        # With the ends fixed the centre can only slide along their
        # perpendicular bisector, so pin it on the axis it moves across.
        if abs(abs(sweep) - 180.0) < 1e-6:
            across = 1 if abs(b[1] - a[1]) < 1e-9 else 0
            value = (a[across] + b[across]) / 2.0
            axis, kind = ((X_AXIS, "DistanceY") if across
                          else (Y_AXIS, "DistanceX"))
            if abs(value) < 1e-9:
                sk.addConstraint(Sketcher.Constraint(
                    "PointOnObject", first + i, 3, axis))
            else:
                idx = sk.addConstraint(Sketcher.Constraint(
                    kind, *ROOT_POINT, first + i, 3, value))
                sk.renameConstraint(idx, f"{name}_half{i}")
            continue
        idx = sk.addConstraint(
            Sketcher.Constraint("Radius", first + i, radius))
        sk.renameConstraint(idx, f"{name}_r{i}")

    # Shape constraints, and the coordinates they make equal.
    xs, ys = _Rails(count), _Rails(count)
    for i in range(count):
        if i in arcs:
            continue
        a, b = points[i], points[(i + 1) % count]
        nxt = (i + 1) % count
        if abs(a[1] - b[1]) < 1e-9:
            sk.addConstraint(Sketcher.Constraint("Horizontal", first + i))
            ys.union(i, nxt)
        elif abs(a[0] - b[0]) < 1e-9:
            sk.addConstraint(Sketcher.Constraint("Vertical", first + i))
            xs.union(i, nxt)

    # One dimension per remaining degree of freedom.
    for rails, coord, axis, kind in ((xs, 0, Y_AXIS, "DistanceX"),
                                     (ys, 1, X_AXIS, "DistanceY")):
        for i in rails.classes():
            value = points[i][coord]
            start = ends[i][0]
            if abs(value) < 1e-9:
                sk.addConstraint(Sketcher.Constraint(
                    "PointOnObject", first + i, start, axis))
            else:
                idx = sk.addConstraint(Sketcher.Constraint(
                    kind, *ROOT_POINT, first + i, start, value))
                sk.renameConstraint(idx, f"{name}_{'xy'[coord]}{i}")

    for corner, radius in sorted((fillets or {}).items()):
        _round_corner(sk, first + corner, radius, f"{name}_r{corner}")
    return sk


def _round_corner(sk, segment, radius, name):
    """Round the corner at the start of `segment` with a tangent arc.

    createCorner=True keeps the sharp corner behind as a construction point,
    so the dimensions that located it still drive the shape.
    """
    before = len(sk.Geometry)
    sk.fillet(segment, 1, radius, True, True)
    # The operation appends both the arc and the construction point that
    # remembers where the sharp corner was; only the arc takes the dimension.
    arcs = [i for i in range(before, len(sk.Geometry))
            if isinstance(sk.Geometry[i], Part.ArcOfCircle)]
    if not arcs:
        raise RuntimeError(f"fillet at geometry {segment} produced no arc")
    idx = sk.addConstraint(Sketcher.Constraint("Radius", arcs[0], radius))
    sk.renameConstraint(idx, name)
    return arcs[0]


def slot(sk, start, end, width, name="slot"):
    """An obround: two parallel lines capped by tangent semicircles.

    The shape every adjustment slot and every rod clearance in this machine is
    made of.  `start` and `end` are the centres of the two end radii.
    """
    first = len(sk.Geometry)
    (x0, y0), (x1, y1) = start, end
    length = math.hypot(x1 - x0, y1 - y0)
    if length < 1e-9:
        raise ValueError("slot ends coincide")
    radius = width / 2.0
    # Unit normal, so the two flanks sit half a width either side of the centre.
    # It points to the right of the centre line, which walks the loop
    # anticlockwise -- and an arc is always built anticlockwise from its start
    # angle, so this is what makes the end caps bulge outwards rather than
    # doubling back through the slot.
    nx, ny = (y1 - y0) / length, -(x1 - x0) / length
    ox, oy = nx * radius, ny * radius

    line_a = sk.addGeometry(Part.LineSegment(
        Vector(x0 + ox, y0 + oy, 0), Vector(x1 + ox, y1 + oy, 0)), False)
    arc_b = sk.addGeometry(Part.ArcOfCircle(
        Part.Circle(Vector(x1, y1, 0), Vector(0, 0, 1), radius),
        math.atan2(oy, ox), math.atan2(-oy, -ox)), False)
    line_c = sk.addGeometry(Part.LineSegment(
        Vector(x1 - ox, y1 - oy, 0), Vector(x0 - ox, y0 - oy, 0)), False)
    arc_d = sk.addGeometry(Part.ArcOfCircle(
        Part.Circle(Vector(x0, y0, 0), Vector(0, 0, 1), radius),
        math.atan2(-oy, -ox), math.atan2(oy, ox)), False)

    for one, two in ((line_a, arc_b), (arc_b, line_c),
                     (line_c, arc_d), (arc_d, line_a)):
        sk.addConstraint(Sketcher.Constraint("Tangent", one, 2, two, 1))
    sk.addConstraint(Sketcher.Constraint("Equal", arc_b, arc_d))
    idx = sk.addConstraint(Sketcher.Constraint("Radius", arc_b, radius))
    sk.renameConstraint(idx, f"{name}_r")
    # Locating both end radii is enough: it fixes the slot's length and angle
    # too, so no horizontal or vertical constraint is wanted on the flanks.
    _locate(sk, arc_d, 3, x0, y0, f"{name}_a")
    _locate(sk, arc_b, 3, x1, y1, f"{name}_b")
    return first


def polygon(sk, center, across_flats, sides=6, angle=0.0, name="nut"):
    """A regular polygon, drawn the way the sketcher's own tool draws one.

    Sized across the flats, because that is how nuts are specified.  The
    vertices ride on a construction circle, consecutive edges are held equal,
    and one vertex is turned to `angle` -- which leaves the whole thing driven
    by the circle's diameter.
    """
    radius = (across_flats / 2.0) / math.cos(math.pi / sides)
    cx, cy = center
    guide = sk.addGeometry(Part.Circle(
        Vector(cx, cy, 0), Vector(0, 0, 1), radius), True)

    start = math.radians(angle)
    corners = [(cx + radius * math.cos(start + 2 * math.pi * i / sides),
                cy + radius * math.sin(start + 2 * math.pi * i / sides))
               for i in range(sides)]
    first = len(sk.Geometry)
    for i in range(sides):
        sk.addGeometry(Part.LineSegment(
            Vector(*corners[i], 0),
            Vector(*corners[(i + 1) % sides], 0)), False)
    for i in range(sides):
        sk.addConstraint(Sketcher.Constraint(
            "Coincident", first + i, 2, first + (i + 1) % sides, 1))
        sk.addConstraint(Sketcher.Constraint(
            "PointOnObject", first + i, 1, guide))
    for i in range(sides - 1):
        sk.addConstraint(Sketcher.Constraint("Equal", first + i, first + i + 1))
    idx = sk.addConstraint(Sketcher.Constraint(
        "Diameter", guide, radius * 2))
    sk.renameConstraint(idx, f"{name}_across_corners")
    _locate(sk, guide, 3, cx, cy, name)
    # One angle left: pin the first corner.
    idx = sk.addConstraint(Sketcher.Constraint(
        "Angle", first, math.radians(angle + 90 + 180.0 / sides)))
    sk.renameConstraint(idx, f"{name}_angle")
    return first


def circle(sk, center, diameter, name="hole", keep_zero=False):
    """Add a fully constrained circle at `center` (see `_locate`)."""
    geo_id = sk.addGeometry(
        Part.Circle(Vector(*center, 0), Vector(0, 0, 1), diameter / 2.0), False)
    idx = sk.addConstraint(Sketcher.Constraint("Diameter", geo_id, diameter))
    sk.renameConstraint(idx, f"{name}_dia")
    _locate(sk, geo_id, 3, center[0], center[1], name, keep_zero)
    return sk


def bolt_circle(sk, center, radius, diameter, count, angle=0.0, name="bolt"):
    """`count` holes evenly spaced round a bolt circle.

    Drawn the way a person draws one rather than the way a loop would: the
    holes sit on the corners of a construction polygon inscribed in a
    construction circle, so the sketch itself carries the layout.  Placing each
    hole at its own computed coordinate makes the same picture but says nothing
    -- move the circle and the holes stay where they were, and nothing on the
    screen tells you they were ever meant to be a circle of holes.

    Only the first hole is dimensioned.  The rest are held equal to it and
    coincident with a corner, so `{name}_dia` and that first hole's position
    drive the whole pattern; `angle` turns the first hole off the sketch's own
    horizontal.  A pattern this way round is also what a `PolarPattern` would
    give, without leaving the sketch.
    """
    if count < 3:
        raise ValueError("a bolt circle wants three holes or more; two corners "
                         "make no polygon and leave the circle free")
    cx, cy = center
    start = math.radians(angle)
    corners = [(cx + radius * math.cos(start + 2 * math.pi * i / count),
                cy + radius * math.sin(start + 2 * math.pi * i / count))
               for i in range(count)]

    first = len(sk.Geometry)
    for x, y in corners:
        sk.addGeometry(Part.Circle(
            Vector(x, y, 0), Vector(0, 0, 1), diameter / 2.0), False)
    idx = sk.addConstraint(Sketcher.Constraint("Diameter", first, diameter))
    sk.renameConstraint(idx, f"{name}_dia")
    _locate(sk, first, 3, corners[0][0], corners[0][1], name)
    for i in range(1, count):
        sk.addConstraint(Sketcher.Constraint("Equal", first, first + i))

    edge = len(sk.Geometry)
    for i in range(count):
        sk.addGeometry(Part.LineSegment(
            Vector(*corners[i], 0),
            Vector(*corners[(i + 1) % count], 0)), True)
    guide = sk.addGeometry(Part.Circle(
        Vector(cx, cy, 0), Vector(0, 0, 1), radius), True)

    # Corner to corner, every corner on the guide circle and every edge the
    # same length: that is a regular polygon, and it leaves the guide's radius
    # and the pattern's clocking as the only freedoms left to pin down.
    for i in range(count):
        sk.addConstraint(Sketcher.Constraint(
            "Coincident", edge + i, 2, edge + (i + 1) % count, 1))
    for i in range(1, count):
        sk.addConstraint(Sketcher.Constraint("Equal", edge, edge + i))
    for i in range(count):
        sk.addConstraint(Sketcher.Constraint(
            "PointOnObject", edge + i, 2, guide))
    if abs(cx) < 1e-9 and abs(cy) < 1e-9:
        sk.addConstraint(Sketcher.Constraint("Coincident", guide, 3, *ROOT_POINT))
    else:
        _locate(sk, guide, 3, cx, cy, f"{name}_centre")
    # Edge i ends on corner i + 1, so that is the hole it carries.
    for i in range(count):
        sk.addConstraint(Sketcher.Constraint(
            "Coincident", edge + i, 2, first + (i + 1) % count, 3))
    return first


def _append(bdy, feature):
    """Add a solid feature to the body's chain and make it the new tip.

    Done explicitly because Body.addObject does not reliably advance Tip past
    a Transformed feature such as Mirrored, which silently drops it from the
    result.
    """
    previous = bdy.Tip
    bdy.addObject(feature)
    if previous is not None:
        feature.BaseFeature = previous
    bdy.Tip = feature
    return feature


def _set_side(feature, midplane):
    """Symmetric-about-the-sketch extrusion, across FreeCAD versions.

    1.1 replaced the Midplane flag with the SideType enumeration and warns
    whenever the old property is touched.
    """
    if "SideType" in feature.PropertiesList:
        feature.SideType = "Symmetric" if midplane else "One side"
    else:
        feature.Midplane = midplane


def pad(bdy, label, profile, length, midplane=False, reversed_=False,
        taper=0.0):
    """Extrude a profile into solid.

    `taper` drafts the sides in degrees, the profile growing outwards as the
    pad runs on.  A 45 degree draft over 1 mm is how a chamfer that has to
    *add* material is drawn, since a Chamfer dressup can only take it away.
    """
    p = bdy.Document.addObject("PartDesign::Pad", "Pad")
    p.Label = label
    _append(bdy, p)
    p.Profile = profile
    p.Length = length
    p.TaperAngle = taper
    _set_side(p, midplane)
    p.Reversed = reversed_
    return p


def pocket(bdy, label, profile, length=None, midplane=False, reversed_=False):
    """A pocket, through all when `length` is None.

    One side unless `midplane`, and a pocket cuts the other way from a pad on
    the same plane, so through all from a sketch on a face cuts away from the
    material unless it is `midplane` or `reversed_`.
    """
    p = bdy.Document.addObject("PartDesign::Pocket", "Pocket")
    p.Label = label
    _append(bdy, p)
    p.Profile = profile
    if length is None:
        p.Type = "ThroughAll"
    else:
        p.Length = length
    _set_side(p, midplane)
    p.Reversed = reversed_
    return p


def _axis_link(bdy, profile, axis):
    """Resolve an axis name to the link a PartDesign feature expects.

    'H_Axis' and 'V_Axis' are the sketch's own axes, which is usually what a
    revolve wants; anything else is one of the body's origin axes.
    """
    if axis in ("H_Axis", "V_Axis") or axis.startswith("Axis"):
        # 'AxisN' is the sketch's N-th construction line.
        return (profile, [axis])
    return (_origin_feature(bdy, axis), [""])


def revolution(bdy, label, profile, axis="V_Axis", angle=360.0,
               midplane=False, reversed_=False):
    """Sweep a profile about an axis to make a turned part."""
    r = bdy.Document.addObject("PartDesign::Revolution", "Revolution")
    r.Label = label
    _append(bdy, r)
    r.Profile = profile
    r.ReferenceAxis = _axis_link(bdy, profile, axis)
    r.Angle = angle
    _set_side(r, midplane)
    r.Reversed = reversed_
    return r


def groove(bdy, label, profile, axis="V_Axis", angle=360.0,
           midplane=False, reversed_=False):
    """Sweep a profile about an axis to cut a turned recess.

    The way to cut a bore whose diameter changes along its length -- a lip, a
    counterbore, a lead in taper -- since a pocket can only cut one section.
    """
    g = bdy.Document.addObject("PartDesign::Groove", "Groove")
    g.Label = label
    _append(bdy, g)
    g.Profile = profile
    g.ReferenceAxis = _axis_link(bdy, profile, axis)
    g.Angle = angle
    g.Midplane = midplane
    g.Reversed = reversed_
    return g


def helix(bdy, label, profile, pitch, height, axis="V_Axis", cone=0.0,
          left_hand=False):
    """Sweep a profile along a helix -- a thread, a worm, a spiral rib.

    The one shape here that a revolve cannot make, since it advances along the
    axis as it turns.  `profile` is drawn in a plane through the axis, in the
    position the thread starts at, and `pitch` is how far one turn advances.
    """
    h = bdy.Document.addObject("PartDesign::AdditiveHelix", "Helix")
    h.Label = label
    _append(bdy, h)
    h.Profile = profile
    h.ReferenceAxis = _axis_link(bdy, profile, axis)
    h.Mode = "pitch-height-angle"
    h.Pitch = pitch
    h.Height = height
    h.Angle = cone
    h.LeftHanded = left_hand
    return h


def hole(bdy, label, profile, diameter, depth, point_angle=None):
    """A PartDesign Hole at every circle of `profile`, drilled into the part.

    The one feature that draws a drill point: `point_angle` (118 for a twist
    drill) gives the bottom its cone; None leaves it flat.
    """
    # The Hole checks its base shape as soon as a property is set, so the
    # body has to have one: recompute first.
    bdy.Document.recompute()
    h = bdy.Document.addObject("PartDesign::Hole", "Hole")
    h.Label = label
    _append(bdy, h)
    h.Profile = profile
    for prop, value in (("Threaded", False), ("ThreadType", "None"),
                        ("HoleCutType", "None")):
        if prop in h.PropertiesList:
            setattr(h, prop, value)
    h.Diameter = diameter
    h.DepthType = "Dimension"
    h.Depth = depth
    if point_angle:
        h.DrillPoint = "Angled"
        h.DrillPointAngle = point_angle
    else:
        h.DrillPoint = "Flat"
    return h


def polar_pattern(bdy, label, features, count, axis="Z_Axis", angle=360.0):
    """Repeat features around an axis -- knurls, spokes, bolt circles."""
    p = bdy.Document.addObject("PartDesign::PolarPattern", "PolarPattern")
    p.Label = label
    _append(bdy, p)
    p.Originals = features
    p.Axis = _axis_link(bdy, None, axis)
    p.Angle = angle
    p.Occurrences = count
    return p


def linear_pattern(bdy, label, features, count, spacing, axis="Z_Axis",
                   reversed_=False):
    """Repeat features along an axis -- a row of holes, a hinge's knuckles.

    `spacing` is centre to centre and `count` **includes the original**, which
    is what PartDesign means by an occurrence: two occurrences 20 apart are the
    seed and one copy, and the feature's own `Length` is the span between the
    outermost two rather than the step between them.
    """
    p = bdy.Document.addObject("PartDesign::LinearPattern", "LinearPattern")
    p.Label = label
    _append(bdy, p)
    p.Originals = features
    p.Direction = _axis_link(bdy, None, axis)
    p.Length = spacing * (count - 1)
    p.Occurrences = count
    p.Reversed = reversed_
    return p


def mirrored(bdy, label, features, plane="XY_Plane"):
    m = bdy.Document.addObject("PartDesign::Mirrored", "Mirrored")
    m.Label = label
    _append(bdy, m)
    # The property holding the mirrored features was renamed across versions.
    for attr in ("Originals", "Transformations"):
        if hasattr(m, attr):
            setattr(m, attr, features)
            break
    else:
        raise AttributeError("PartDesign::Mirrored has no Originals property")
    m.MirrorPlane = (_origin_feature(bdy, plane), [""])
    return m


def midpoint(edge):
    """The middle of an edge -- what a `pick` usually wants to look at."""
    return edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))


def _dressup(bdy, kind, label, pick):
    """Add a Chamfer or Fillet over whichever edges of the tip `pick` accepts.

    Edges are chosen by where they are rather than by name: 'Edge31' says
    nothing to read and moves the moment an earlier sketch changes.

    Prefer drawing an edge treatment into the sketch that makes it -- a
    sketched radius carries a name and a dimension, and this does not.  Use
    this only where the treatment runs along an edge no single sketch contains.
    """
    base = bdy.Tip
    bdy.Document.recompute()
    names = [f"Edge{i + 1}" for i, edge in enumerate(base.Shape.Edges)
             if pick(edge)]
    if not names:
        raise RuntimeError(f"{label} matched no edge of {base.Name}")
    feature = bdy.Document.addObject(f"PartDesign::{kind}", kind)
    feature.Label = label
    feature.Base = (base, names)
    bdy.addObject(feature)
    bdy.Tip = feature
    return feature


def chamfer(bdy, label, size, pick):
    """Break the picked edges at 45 degrees."""
    feature = _dressup(bdy, "Chamfer", label, pick)
    feature.Size = size
    return feature


def fillet(bdy, label, radius, pick):
    """Round the picked edges."""
    feature = _dressup(bdy, "Fillet", label, pick)
    feature.Radius = radius
    return feature


def check_sketches(bdy):
    """Report any sketch that did not come out fully constrained."""
    for obj in bdy.Group:
        if obj.TypeId != "Sketcher::SketchObject":
            continue
        if obj.solve() != 0:
            raise SystemExit(f"sketch {obj.Label!r} failed to solve")
        for kind in ("Conflicting", "Redundant", "Malformed"):
            bad = list(getattr(obj, kind + "Constraints", []) or [])
            if bad:
                raise SystemExit(f"sketch {obj.Label!r}: {kind.lower()} "
                                 f"constraints {bad}")
        if obj.FullyConstrained:
            print(f"  sketch {obj.Label!r}: fully constrained")
        else:
            raise SystemExit(f"sketch {obj.Label!r} is not fully constrained")


# ---------------------------------------------------------------------------
# Lines, points and ellipses for profiles that `polyline` cannot draw.
#
# A turned part whose outline mixes straight segments with an ellipse needs
# its constraints written out by hand: which points mirror
# which, and which dimension drives what, is the design itself.  These helpers
# only save the bookkeeping.

def line(sk, a, b, construction=False):
    """A line segment from `a` to `b`; returns its geometry index."""
    return sk.addGeometry(Part.LineSegment(Vector(*a, 0), Vector(*b, 0)),
                          construction)


def point(sk, at):
    """A construction point, e.g. the sharp corner a chamfer is measured from."""
    return sk.addGeometry(Part.Point(Vector(*at, 0)), True)


def ellipse_arc(sk, center, a, b, start, end):
    """An arc of an axis-aligned ellipse from parameter `start` to `end`.

    The parameter is the eccentric angle in radians, anticlockwise from +H, so
    a point is (cx + a cos t, cy + b sin t).  The major axis lies along H.

    Returns (arc, major, minor): the arc and the two construction lines that
    the sketcher exposes for its axes.  Those are what carry the semi-axis
    dimensions, since the sketcher has no radius constraint for an ellipse --
    a `Distance` on the major line is the full major axis, 2a.
    """
    cx, cy = center
    ellipse = Part.Ellipse(Vector(cx + a, cy, 0), Vector(cx, cy + b, 0),
                           Vector(cx, cy, 0))
    arc = sk.addGeometry(Part.ArcOfEllipse(ellipse, start, end), False)
    before = len(sk.Geometry)
    sk.exposeInternalGeometry(arc)
    lines = [i for i in range(before, len(sk.Geometry))
             if isinstance(sk.Geometry[i], Part.LineSegment)]
    if len(lines) != 2:
        raise RuntimeError(f"ellipse {arc} exposed {len(lines)} axis lines")
    lines.sort(key=lambda i: -sk.Geometry[i].length())
    return arc, lines[0], lines[1]


def con(sk, kind, *args, name=None):
    """Add one constraint, named if `name` is given; returns its index."""
    idx = sk.addConstraint(Sketcher.Constraint(kind, *args))
    if name:
        sk.renameConstraint(idx, name)
    return idx


# ---------------------------------------------------------------------------
# The shared spreadsheet.
#
# Values more than one part depends on live in one spreadsheet in its own
# document,
# `model/Parameters.FCStd`.  A part binds a sketch dimension to a cell
# with an expression, so editing the cell in the GUI moves every part that
# uses it.  FreeCAD stores the link with a path relative to the part.

PARAMS_DOC = "Parameters"
PARAMS_SHEET = "Spreadsheet"


def param(alias):
    """The expression text that reads one cell of the shared spreadsheet."""
    return f"{PARAMS_DOC}#{PARAMS_SHEET}.{alias}"


def open_parameters():
    """Open the shared spreadsheet's document, which must have been built."""
    path = paths.PARAMETERS
    if PARAMS_DOC in App.listDocuments():
        return App.getDocument(PARAMS_DOC)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing: build parameters first")
    return App.openDocument(path)


def sheet_value(alias):
    """A cell's value as a plain float, in mm or degrees."""
    doc = App.getDocument(PARAMS_DOC)
    value = getattr(doc.getObject(PARAMS_SHEET), alias)
    return float(getattr(value, "Value", value))


def drive(sk, name, expression):
    """Drive the named constraint of `sk` by an expression."""
    sk.setExpression(f".Constraints.{name}", expression)


# ---------------------------------------------------------------------------
# What the parts are made of, and what the documents say about themselves.

# What a part is made of, and the licence a document carries, are the
# project's: model/project.py (`paths.project()`).  A material there has a
# FreeCAD material card, a colour and whether it is printed.
PROJECT = paths.project()


def _material(kind):
    if kind not in PROJECT.MATERIALS:
        raise KeyError(f"unknown material {kind!r}; model/project.py names "
                       f"{sorted(PROJECT.MATERIALS)}")
    return PROJECT.MATERIALS[kind]


def material(obj, kind=None):
    """Say what a part is made of, and give it the matching material card.

    `obj` is a PartDesign body or any other object with a shape, such as a
    Fasteners object; `kind` names a material of the project's, by default
    its `DEFAULT_MATERIAL`.
    """
    kind = kind or PROJECT.DEFAULT_MATERIAL
    card = _material(kind)["card"]
    if not hasattr(obj, "PartMaterial"):
        obj.addProperty("App::PropertyString", "PartMaterial", "Stock",
                        "What the part is made of; see fcprim.material",
                        locked=True)
    obj.PartMaterial = kind
    if hasattr(obj, "ShapeMaterial"):
        import Materials                    # only in FreeCAD 1.1 and later
        obj.ShapeMaterial = Materials.MaterialManager().getMaterial(card)
    return obj


def designation(obj, text):
    """What a bought part is ordered as (`Threaded rod M5, 100 mm`), for the
    bill of materials.  Build the text from the part's own dimensions, so it
    cannot go on naming a size the part no longer has."""
    if not hasattr(obj, "Designation"):
        obj.addProperty("App::PropertyString", "Designation", "Stock",
                        "What the part is ordered as; see fcprim.designation",
                        locked=True)
    obj.Designation = text
    return obj


def material_name(kind):
    """The name the project gives a material, for people to read."""
    return _material(kind).get("name", kind)


def is_printed(obj):
    """True for a part whose material the project calls printed."""
    kind = getattr(obj, "PartMaterial", None)
    return kind in PROJECT.MATERIALS and PROJECT.MATERIALS[kind]["printed"]


def meta(doc):
    """The licence a document carries: the project's, not FreeCAD's default
    `All rights reserved`.  The author fields are left as FreeCAD fills them
    from the preferences of whoever builds or edits the document."""
    doc.License = PROJECT.LICENSE
    doc.LicenseURL = PROJECT.LICENSE_URL
    return doc


# What a document holds that is not the thing itself: the sketches a feature
# was drawn from, the datums it was drawn on, and the intermediate features a
# body's tip already contains.
SCAFFOLDING = ("Sketcher::", "PartDesign::CoordinateSystem", "PartDesign::Plane",
               "PartDesign::Line", "PartDesign::Point", "App::Origin",
               "App::OriginFeature", "App::Plane", "App::Line", "App::Point",
               "App::Placement", "Spreadsheet::",
               "Assembly::JointGroup", "App::FeaturePython")


def dress(doc):
    """Leave every solid visible and everything that drew it hidden.

    Within a PartDesign body every intermediate feature is hidden -- every one
    *except the tip*.  A body's view provider defaults to
    `DisplayModeBody = 'Through'`, and in that mode the body draws only its
    visible children, so hiding the tip too leaves a document that opens blank.
    This is necessary but not sufficient: a document saved headless has no
    `GuiDocument.xml`, which the GUI pass (`code/view.py`) writes.
    """
    bodies = [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]
    tips = {body.Tip.Name for body in bodies if body.Tip is not None}
    # A body built on another object (a fastener) shows that object's shape
    # itself, so the object is hidden as the body's sketches are.
    bases = {body.BaseFeature.Name for body in bodies if body.BaseFeature is not None}
    for obj in doc.Objects:
        if not hasattr(obj, "Visibility"):
            continue
        kind = obj.TypeId
        scaffold = any(kind.startswith(prefix) for prefix in SCAFFOLDING)
        inside_body = (kind.startswith("PartDesign::")
                       and kind != "PartDesign::Body"
                       and obj.Name not in tips)
        obj.Visibility = not (scaffold or inside_body or obj.Name in bases)
    return doc


def appearance(rgb):
    """A FreeCAD material for a view provider, from sRGB 0 to 255."""
    m = App.Material()
    m.DiffuseColor = tuple(c / 255.0 for c in rgb) + (0.0,)
    return m


def colour(doc):
    """Show every part in the colour of what it is made of (GUI only).

    A part is any object `material` marked: a body, coloured on itself and on
    each feature in it, since the body draws its tip with the tip's own view
    provider, or a Fasteners object.  Assigned as a new tuple: changing
    `ShapeAppearance[0]` in place changes a copy and the view stays grey.
    """
    for obj in doc.Objects:
        kind = getattr(obj, "PartMaterial", None)
        if kind not in PROJECT.MATERIALS:
            continue
        look = (appearance(PROJECT.MATERIALS[kind]["colour"]),)
        members = list(obj.Group) if obj.TypeId == "PartDesign::Body" else []
        for o in [obj] + members:
            vo = getattr(o, "ViewObject", None)
            if vo is not None and hasattr(vo, "ShapeAppearance"):
                vo.ShapeAppearance = look
    return doc


def fail_on_invalid(doc):
    """Raise if any feature failed to build.

    A feature that throws is only reported to the console: the body keeps the
    last shape that worked, every later feature is skipped, and the result is
    still a valid solid with part of the part missing.
    """
    failed = [f"{obj.Label} ({obj.Name})" for obj in doc.Objects
              if "Invalid" in obj.State or "Error" in obj.State]
    if failed:
        raise SystemExit("feature(s) failed to build: " + ", ".join(failed))
    touched = [obj.Label for obj in doc.Objects if "Touched" in obj.State]
    if touched:
        raise SystemExit("still touched after recompute: " + ", ".join(touched))


def finish(doc, bdy, path, test=None, made_of=None):
    """Recompute, test and save the document to `path`.

    `test(doc, bdy)` is the part's own test, normally `fctest.flex` on a few of
    its dimensions, and runs on the saved document, so whatever it changes it
    has to put back.  Nothing is kept if a feature failed or the test raised.
    What the build found goes to data/build/<document>.json.
    """
    doc.recompute()
    fail_on_invalid(doc)
    material(bdy, made_of)
    shape = bdy.Shape
    if not shape.isValid() or len(shape.Solids) != 1:
        raise SystemExit(f"{doc.Name}: result is not one valid solid "
                         f"({len(shape.Solids)} solids, valid={shape.isValid()})")
    bb = shape.optimalBoundingBox()
    print(f"{doc.Name}: volume {shape.Volume:.3f} mm^3, "
          f"{len(shape.Faces)} faces", flush=True)
    print(f"  bbox X[{bb.XMin:.3f},{bb.XMax:.3f}] "
          f"Y[{bb.YMin:.3f},{bb.YMax:.3f}] Z[{bb.ZMin:.3f},{bb.ZMax:.3f}]",
          flush=True)
    meta(doc)
    dress(doc)
    # Saved before the test so that cross-document links resolve against the
    # file's real location; a failed test deletes it again.
    doc.saveAs(path)
    flexed = []
    try:
        if test is not None:
            flexed = test(doc, bdy) or []
            doc.recompute()
            fail_on_invalid(doc)
            meta(doc)
            doc.save()
    except BaseException:
        os.remove(path)
        raise
    report(doc.Name, {
        "document": paths.rel(path),
        "volume": round(shape.Volume, 4),
        "faces": len(shape.Faces),
        "bbox": [round(v, 4) for v in (bb.XMin, bb.YMin, bb.ZMin,
                                       bb.XMax, bb.YMax, bb.ZMax)],
        "flexed": flexed,
    })
    print(f"  saved {path}", flush=True)
    return bdy


class SkipBuild(Exception):
    """Raised by a script whose source is missing, such as a part imported
    from a file that is not there: nothing is built, and the build says so
    instead of failing."""


def report(name, data):
    """Write what a build found to data/build/<name>.json."""
    os.makedirs(paths.BUILD_DATA, exist_ok=True)
    with open(os.path.join(paths.BUILD_DATA, name + ".json"), "w") as fh:
        json.dump(data, fh, indent=1)
        fh.write("\n")


def make(script, name, builder, test=None, made_of=None):
    """Build one part and save it next to its script.

    `builder(doc)` draws the part and returns its body.  The document is saved
    first, empty, because a cross-document expression -- every link to the
    shared spreadsheet -- can only be set from a document that has a file.
    """
    folder = os.path.dirname(os.path.abspath(script))
    path = os.path.join(folder, name + ".FCStd")
    doc = document(name)
    meta(doc)
    doc.saveAs(path)
    bdy = builder(doc)
    doc.recompute()
    check_sketches(bdy)
    return finish(doc, bdy, path, test=test, made_of=made_of)
