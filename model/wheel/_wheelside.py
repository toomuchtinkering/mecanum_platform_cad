"""One wheel side, drawn for either hand and either side of the wheel.

A wheel is two sides with the rollers between them: the motor side, which
the motor hub screws onto, and the outer side, whose tube spans the gap to
the motor side.  Each roller turns on a pin whose ends sit in a claw on each
side.  Both sides of a left-handed wheel carry the same claws, and a
right-handed side is a left-handed one mirrored in X; `hand` (+1 left, -1
right) is the only thing that flips.

Each side is drawn in its own frame: the wheel axis is Y, the disc's
back face at y = -back_y and its claw face at y = -(back_y + side_t).

A wheel side is:

- a disc of radius `wheel_r`, `side_t` thick;
- `claw_count` claws, one per roller.  Roller k's pin axis passes closest to
  the wheel axis at `claw_phase` + k x 360 / claw_count, at `pin_axis_r`, and
  runs at `roller_angle` to the wheel axis.  The washer face, square to the
  pin, crosses the pin axis on the claw face, `washer_offset` along the pin
  from the roller's middle.  Round the pin axis:
  - the knob: a Ø`claw_d` boss below the washer face, standing proud of the
    claw face on the half where that face falls away from the washer face,
    with a `claw_round` round on its end;
  - the cup: Ø`claw_d` cut above the washer face, where the roller's end
    turns, its exit through the claw face broken by a `cup_chamfer` chamfer
    and a `cup_round` round between the cup and that chamfer;
  - the pin hole: Ø`pin_hole_d`, `pin_hole_depth` deep, a flat bottom with
    an r1 round and a 0.2 mm lead-in;
- the envelope: everything beyond `wheel_r` trimmed, which cuts the knobs
  back to the rim, and a `rim_round` round on the back edge of the rim;
- the hub, motor side: a Ø`hub_boss_d` boss, the motor shaft's D-bore, four
  insert holes for the motor hub's screws and four counterbored screws
  through to the outer side.  Outer side: a tube that spans the gap between
  the two discs, bored to take the motor side's boss, with four insert holes
  in its end;
- a `notch_w` marker notch across the rim at the top, `notch_depth` deep.

Positions that follow from the spreadsheet (the claw's datum, the tube's
length) are expressions, so every cell above moves the part.
"""

import math

import FreeCAD as App
from FreeCAD import Placement, Rotation, Vector

import fcprim as fp
import fctest

P, V = fp.param, fp.sheet_value

# Every dimension the four wheel sides share is a cell of the spreadsheet, so
# that changing one in FreeCAD is one edit, not four.  These three are not
# dimensions: they only say how far a construction reaches past where it is
# trimmed, and the part is the same for any value that does the job.
KNOB_LEN = 8.0        # knob, back from the washer face: seats it in the disc,
                      # and short enough that its end stays inside it
CUP_LEN = 8.0         # cup, out from the washer face: clears the disc
ABOVE = 0.5           # how far the hole's groove reaches above the washer face
# Where the outer side is drawn in its own frame: its back face on y = -35.
# The frame, not a dimension of the part.
OUTER_BACK_Y = 35.0


class Side:
    """Which wheel side: hand +1 (left) or -1 (right), motor or outer."""

    def __init__(self, hand, motor, back_y):
        self.hand, self.motor, self.back_y = hand, motor, back_y

    def face_y(self, v):
        return self.back_y + v["side_t"]

    def face_y_expr(self):
        if self.back_y:
            return f"({self.back_y:g} mm + {P('side_t')})"
        return P("side_t")


def _values():
    names = ("roller_angle", "wheel_r", "side_t", "rim_round", "claw_count",
             "claw_phase", "pin_axis_r", "washer_offset", "claw_d", "claw_round",
             "cup_chamfer", "cup_round", "pin_hole_d", "pin_hole_depth",
             "hub_boss_d", "hub_screw_circle_d", "shaft_bore_d", "shaft_flat",
             "pin_hole_round", "pin_hole_lead", "hub_boss_len", "hub_boss_chamfer",
             "tube_d", "tube_chamfer", "tube_bore_clearance", "tube_insert_depth",
             "side_screw_d", "side_insert_d", "counterbore_d", "counterbore_depth",
             "marker_slot_w", "marker_slot_r", "notch_w", "notch_depth")
    return {n: V(n) for n in names}


def pin_axes(side, v):
    """(O, A) per claw: where the pin axis meets the washer face, and the
    pin's direction towards the roller.  Used to pick edges, and to check the
    datum the sketches hang on."""
    out = []
    a = math.radians(v["roller_angle"])
    for k in range(int(round(v["claw_count"]))):
        phi = math.radians(v["claw_phase"] + 360.0 * k / v["claw_count"])
        rad = Vector(math.cos(phi), 0, math.sin(phi))
        tan = Vector(0, 1, 0).cross(rad)
        A = tan * (-side.hand * math.sin(a)) + Vector(0, -math.cos(a), 0)
        O = rad * v["pin_axis_r"] + tan * (side.hand * v["washer_offset"] * math.sin(a)) \
            + Vector(0, -side.face_y(v), 0)
        out.append((O, A))
    return out


def rename(sk, old, new):
    """Give a constraint `polyline` named by position a name that says what
    it drives."""
    names = [c.Name for c in sk.Constraints]
    sk.renameConstraint(names.index(old), new)


def claw_datum(bdy, side, v):
    """The first claw's frame, as two datums driven by the spreadsheet.

    `Claw ring` is the body's frame turned about the wheel axis by
    claw_phase, so its X runs out towards the first claw.  `Claw axis` hangs
    on it: its origin where the pin axis crosses the claw face, Z along the
    pin towards the roller, X radial, so its XY plane is the washer face and
    its XZ plane holds the pin axis.
    """
    doc = bdy.Document
    ring = doc.addObject("PartDesign::CoordinateSystem", "LCS")
    ring.Label = "Claw ring"
    bdy.addObject(ring)
    ring.AttachmentSupport = [(fp._origin_feature(bdy, "XY_Plane"), "")]
    ring.MapMode = "ObjectXY"
    ring.AttachmentOffset = Placement(
        Vector(0, 0, 0), Rotation(Vector(0, -1, 0), v["claw_phase"]))
    ring.setExpression(".AttachmentOffset.Rotation.Angle", P("claw_phase"))

    axis = doc.addObject("PartDesign::CoordinateSystem", "LCS")
    axis.Label = "Claw axis"
    bdy.addObject(axis)
    axis.AttachmentSupport = [(ring, "")]
    axis.MapMode = "ObjectXY"
    a = math.radians(v["roller_angle"])
    # Turning X by 90 - hand x roller_angle swings Z from the ring's Z onto
    # the pin, which leans back to -Y and round to -hand x tangential.
    tilt = 90.0 - side.hand * v["roller_angle"]
    axis.AttachmentOffset = Placement(
        Vector(v["pin_axis_r"], -side.face_y(v),
               -side.hand * v["washer_offset"] * math.sin(a)),
        Rotation(Vector(1, 0, 0), tilt))
    axis.setExpression(".AttachmentOffset.Base.x", P("pin_axis_r"))
    axis.setExpression(".AttachmentOffset.Base.y", f"-{side.face_y_expr()}")
    sign = "-" if side.hand > 0 else ""
    axis.setExpression(".AttachmentOffset.Base.z",
                       f"{sign}{P('washer_offset')} * sin({P('roller_angle')})")
    axis.setExpression(".AttachmentOffset.Rotation.Angle",
                       f"90 deg {'-' if side.hand > 0 else '+'} {P('roller_angle')}")
    for o in (ring, axis):
        o.Visibility = False
    return axis


def claw_sketch(bdy, label, datum, plane):
    sk = bdy.Document.addObject("Sketcher::SketchObject", "Sketch")
    sk.Label = label
    bdy.addObject(sk)
    sk.AttachmentSupport = [(datum, "")]
    sk.MapMode = {"XY": "ObjectXY", "XZ": "ObjectXZ"}[plane]
    return sk


def _centre(shape):
    """Centre of mass of whatever solids a boolean returned."""
    solids = shape.Solids
    total = sum(x.Volume for x in solids)
    if total < 1e-6:
        raise SystemExit("a claw feature added or removed nothing")
    c = Vector(0, 0, 0)
    for x in solids:
        c += x.CenterOfMass * (x.Volume / total)
    return c


def claw(bdy, side, v, datum):
    """The first claw: knob, cup and pin hole.  Returns the three features."""
    r = v["claw_d"] / 2

    knob = claw_sketch(bdy, "Claw knob", datum, "XZ")
    fp.polyline(knob, [(0.0, 0.0), (r, 0.0), (r, -KNOB_LEN), (0.0, -KNOB_LEN)],
                name="knob", fillets={1: v["claw_round"]})
    rename(knob, "knob_x1", "claw_r")
    rename(knob, "knob_y2", "knob_len")
    rename(knob, "knob_r1", "claw_round")
    fp.drive(knob, "claw_r", f"{P('claw_d')} / 2")
    fp.drive(knob, "claw_round", P("claw_round"))
    # Half a turn: the half of the boss that stands proud of the claw face.
    knob_f = fp.revolution(bdy, "Claw knob", knob, axis="V_Axis", angle=180.0,
                           reversed_=side.hand > 0)

    cup = claw_sketch(bdy, "Roller cup", datum, "XY")
    fp.circle(cup, (0.0, 0.0), v["claw_d"], name="cup")
    fp.drive(cup, "cup_dia", P("claw_d"))
    cup_f = fp.pocket(bdy, "Roller cup", cup, CUP_LEN, reversed_=True)

    hole = claw_sketch(bdy, "Pin hole", datum, "XZ")
    hr, depth = v["pin_hole_d"] / 2, v["pin_hole_depth"]
    lead = v["pin_hole_lead"]
    fp.polyline(hole, [(0.0, ABOVE), (hr + lead + ABOVE, ABOVE),
                       (hr, -lead), (hr, -depth), (0.0, -depth)],
                name="hole", fillets={3: v["pin_hole_round"]})
    rename(hole, "hole_x2", "pin_hole_r")
    rename(hole, "hole_y3", "pin_hole_depth")
    rename(hole, "hole_r3", "bottom_round")
    rename(hole, "hole_y2", "lead_in")
    rename(hole, "hole_x1", "lead_in_top")
    rename(hole, "hole_y0", "above_washer")
    fp.drive(hole, "pin_hole_r", f"{P('pin_hole_d')} / 2")
    fp.drive(hole, "pin_hole_depth", f"-{P('pin_hole_depth')}")
    fp.drive(hole, "lead_in", f"-{P('pin_hole_lead')}")
    fp.drive(hole, "bottom_round", P("pin_hole_round"))
    # The lead-in stays at 45 degrees whatever the hole's diameter.
    me = hole.Name
    fp.drive(hole, "lead_in_top",
             f"{me}.Constraints.pin_hole_r - {me}.Constraints.lead_in + {me}.Constraints.above_washer")
    hole_f = fp.groove(bdy, "Pin hole", hole, axis="V_Axis")

    # Which way a revolve or pocket runs is easy to get backwards: the knob
    # must stand on the side where the claw face falls away below the washer
    # face, the cup must open towards the roller.
    bdy.Document.recompute()
    O, A = pin_axes(side, v)[0]
    across = A.cross(Vector(O.x, 0, O.z).normalize())     # the datum's Y
    added = knob_f.Shape.cut(knob_f.BaseFeature.Shape)
    removed = cup_f.BaseFeature.Shape.cut(cup_f.Shape)
    k, c = _centre(added) - O, _centre(removed) - O
    if side.hand * k.dot(across) >= 0 or k.dot(A) >= 0 or c.dot(A) <= 0:
        raise SystemExit(f"claw features run the wrong way: knob {k}, cup {c}")
    return [knob_f, cup_f, hole_f]


def envelope(bdy, side, v):
    """Trim everything beyond the rim, and round the rim's back edge."""
    sk = fp.sketch(bdy, "Envelope", "XY_Plane")
    R, rr, b, f = v["wheel_r"], v["rim_round"], side.back_y, side.face_y(v)
    low, out = -f - 12.0, R + 20.0     # wide enough to take the knobs' far ends
    fp.polyline(sk, [(R, low), (R, -b - rr), (R - rr, -b), (R - rr, -b + 2.0),
                     (out, -b + 2.0), (out, low)],
                name="env", arcs={1: rr})
    rename(sk, "env_x0", "wheel_r")
    rename(sk, "env_r1", "rim_round")
    fp.drive(sk, "wheel_r", P("wheel_r"))
    fp.drive(sk, "rim_round", P("rim_round"))
    fp.drive(sk, "env_y1", f"-{b:g} mm - {P('rim_round')}")
    fp.drive(sk, "env_x2", f"{P('wheel_r')} - {P('rim_round')}")
    fp.drive(sk, "env_x4", f"{P('wheel_r')} + 20 mm")
    fp.drive(sk, "env_y0", f"-{side.face_y_expr()} - 12 mm")
    return fp.groove(bdy, "Envelope", sk, axis="V_Axis")


def _dist_to_axis(p, O, A):
    d = p - O
    return (d - A * d.dot(A)).Length


def cup_edges(bdy, side, v):
    """Chamfer the cup's exit through the claw face, then round the cup into
    the chamfer.  Edges are picked by where they lie: on the claw face (or
    off it), at claw_d / 2 from a pin axis, on the cup's side of the washer
    face."""
    axes = pin_axes(side, v)
    r, fy = v["claw_d"] / 2, side.face_y(v)

    def exit_edge(edge):
        pts = edge.discretize(11)[1:-1]
        return any(all(abs(p.y + fy) < 1e-6 and abs(_dist_to_axis(p, O, A) - r) < 1e-5
                       and (p - O).dot(A) > 1e-3 for p in pts) for O, A in axes)

    ch = fp.chamfer(bdy, "Cup chamfer", v["cup_chamfer"], exit_edge)
    ch.setExpression("Size", P("cup_chamfer"))
    n_ch = len(ch.Base[1])

    def cup_to_chamfer(edge):
        pts = edge.discretize(11)[1:-1]
        return any(all(abs(_dist_to_axis(p, O, A) - r) < 1e-3 and p.y > -fy + 1e-3
                       and (p - O).dot(A) > 1e-3
                       and math.hypot(p.x, p.z) < v["wheel_r"] - 1e-3
                       and p.y < -side.back_y - v["rim_round"] for p in pts)
                   for O, A in axes)

    fl = fp.fillet(bdy, "Cup round", v["cup_round"], cup_to_chamfer)
    fl.setExpression("Radius", P("cup_round"))
    n_fl = len(fl.Base[1])
    count = int(round(v["claw_count"]))
    if n_fl != count or n_ch < count:
        raise SystemExit(f"cup edges: {n_ch} chamfered, {n_fl} rounded, "
                         f"for {count} claws")
    return ch, fl


def d_bore(sk, d, flat):
    """A circle with a flat across its top: the D of the motor shaft."""
    r = d / 2
    x = math.sqrt(r * r - flat ** 2)
    a0 = math.atan2(flat, -x)
    a1 = math.atan2(flat, x) + 2 * math.pi
    arc = sk.addGeometry(fp.Part.ArcOfCircle(fp.Part.Circle(
        Vector(0, 0, 0), Vector(0, 0, 1), r), a0, a1), False)
    line = fp.line(sk, (x, flat), (-x, flat))
    c = lambda *args, name=None: fp.con(sk, *args, name=name)
    c("Coincident", arc, 2, line, 1)
    c("Coincident", line, 2, arc, 1)
    c("Coincident", arc, 3, *fp.ROOT_POINT)
    c("Diameter", arc, d, name="bore_d")
    c("Horizontal", line)
    c("DistanceY", *fp.ROOT_POINT, line, 1, flat, name="flat")


def motor_hub(bdy, side, v):
    f = side.face_y(v)
    rb = v["hub_boss_d"] / 2
    sk = fp.sketch(bdy, "Hub boss", "XY_Plane")
    bl, bc = v["hub_boss_len"], v["hub_boss_chamfer"]
    fp.polyline(sk, [(0.0, -f), (rb, -f), (rb, -f - bl + bc),
                     (rb - bc, -f - bl), (0.0, -f - bl)],
                name="boss")
    rename(sk, "boss_x1", "boss_r")
    rename(sk, "boss_y0", "claw_face")
    rename(sk, "boss_y3", "boss_end")
    fp.drive(sk, "boss_r", f"{P('hub_boss_d')} / 2")
    fp.drive(sk, "boss_x3", f"{P('hub_boss_d')} / 2 - {P('hub_boss_chamfer')}")
    fp.drive(sk, "claw_face", f"-{side.face_y_expr()}")
    fp.drive(sk, "boss_end", f"-{side.face_y_expr()} - {P('hub_boss_len')}")
    fp.drive(sk, "boss_y2", f"-{side.face_y_expr()} - {P('hub_boss_len')} + {P('hub_boss_chamfer')}")
    fp.revolution(bdy, "Hub boss", sk, axis="V_Axis")

    sk = fp.sketch(bdy, "Shaft bore", "XZ_Plane")
    d_bore(sk, v["shaft_bore_d"], v["shaft_flat"])
    fp.drive(sk, "bore_d", P("shaft_bore_d"))
    fp.drive(sk, "flat", P("shaft_flat"))
    fp.pocket(bdy, "Shaft bore", sk, None, midplane=True)

    rc = v["hub_screw_circle_d"] / 2
    sk = fp.sketch(bdy, "Motor hub inserts", "XZ_Plane")
    fp.bolt_circle(sk, (0.0, 0.0), rc, v["side_insert_d"], 4, angle=45.0, name="insert")
    fp.drive(sk, "insert_dia", P("side_insert_d"))
    fp.drive(sk, "insert_u", f"{P('hub_screw_circle_d')} / 2 * cos(45 deg)")
    fp.drive(sk, "insert_v", f"{P('hub_screw_circle_d')} / 2 * sin(45 deg)")
    fp.pocket(bdy, "Motor hub inserts", sk, None, midplane=True)

    sk = fp.sketch(bdy, "Side screws", "XZ_Plane")
    fp.bolt_circle(sk, (0.0, 0.0), rc, v["side_screw_d"], 4, angle=0.0, name="screw")
    fp.drive(sk, "screw_dia", P("side_screw_d"))
    fp.drive(sk, "screw_u", f"{P('hub_screw_circle_d')} / 2")
    fp.pocket(bdy, "Side screws", sk, None, midplane=True)

    sk = fp.sketch(bdy, "Counterbores", "XZ_Plane", offset=side.back_y)
    fp.bolt_circle(sk, (0.0, 0.0), rc, v["counterbore_d"], 4, angle=0.0, name="head")
    fp.drive(sk, "head_u", f"{P('hub_screw_circle_d')} / 2")
    fp.drive(sk, "head_dia", P("counterbore_d"))
    cut = fp.pocket(bdy, "Counterbores", sk, v["counterbore_depth"], reversed_=True)
    cut.setExpression("Length", P("counterbore_depth"))

    # A slot from the top counterbore outwards, as deep: a marker.
    sk = fp.sketch(bdy, "Marker slot", "XZ_Plane", offset=side.back_y)
    h, slot_r = v["marker_slot_w"] / 2, v["marker_slot_r"]
    top = math.sqrt(slot_r ** 2 - h ** 2)
    right = fp.line(sk, (h, rc), (h, top))
    arc = sk.addGeometry(fp.Part.ArcOfCircle(fp.Part.Circle(
        Vector(0, 0, 0), Vector(0, 0, 1), slot_r),
        math.atan2(top, h), math.atan2(top, -h)), False)
    left = fp.line(sk, (-h, top), (-h, rc))
    bottom = fp.line(sk, (-h, rc), (h, rc))
    c = lambda *args, name=None: fp.con(sk, *args, name=name)
    c("Coincident", right, 2, arc, 1)
    c("Coincident", arc, 2, left, 1)
    c("Coincident", left, 2, bottom, 1)
    c("Coincident", bottom, 2, right, 1)
    c("Coincident", arc, 3, *fp.ROOT_POINT)
    c("Radius", arc, slot_r, name="slot_r")
    c("Vertical", right)
    c("Vertical", left)
    # Symmetric about the axis also makes the bottom horizontal.
    c("Symmetric", bottom, 1, bottom, 2, fp.Y_AXIS)
    c("DistanceX", bottom, 1, bottom, 2, 2 * h, name="slot_w")
    c("DistanceY", *fp.ROOT_POINT, bottom, 1, rc, name="slot_from")
    fp.drive(sk, "slot_from", f"{P('hub_screw_circle_d')} / 2")
    fp.drive(sk, "slot_r", P("marker_slot_r"))
    fp.drive(sk, "slot_w", P("marker_slot_w"))
    cut = fp.pocket(bdy, "Marker slot", sk, v["counterbore_depth"], reversed_=True)
    cut.setExpression("Length", P("counterbore_depth"))


def outer_hub(bdy, side, v):
    f = side.face_y(v)
    a = math.radians(v["roller_angle"])
    span = 2 * v["washer_offset"] * math.cos(a)     # the gap between the discs
    span_e = f"2 * {P('washer_offset')} * cos({P('roller_angle')})"
    rb = (v["hub_boss_d"] + v["tube_bore_clearance"]) / 2
    ro, c = v["tube_d"] / 2, v["tube_chamfer"]
    bore_e = f"({P('hub_boss_d')} + {P('tube_bore_clearance')}) / 2"
    c_e = P("tube_chamfer")
    sk = fp.sketch(bdy, "Tube", "XY_Plane")
    fp.polyline(sk, [(rb, -f), (ro, -f), (ro, -f - span + c), (ro - c, -f - span),
                     (rb + c, -f - span), (rb, -f - span + c)], name="tube")
    rename(sk, "tube_x0", "bore_r")
    rename(sk, "tube_y0", "claw_face")
    rename(sk, "tube_y3", "tube_end")
    fp.drive(sk, "bore_r", bore_e)
    fp.drive(sk, "tube_x1", f"{P('tube_d')} / 2")
    fp.drive(sk, "tube_x3", f"{P('tube_d')} / 2 - {c_e}")
    fp.drive(sk, "tube_x4", f"{bore_e} + {c_e}")
    fp.drive(sk, "claw_face", f"-{side.face_y_expr()}")
    fp.drive(sk, "tube_end", f"-{side.face_y_expr()} - {span_e}")
    fp.drive(sk, "tube_y2", f"-{side.face_y_expr()} - {span_e} + {c_e}")
    fp.drive(sk, "tube_y5", f"-{side.face_y_expr()} - {span_e} + {c_e}")
    fp.revolution(bdy, "Tube", sk, axis="V_Axis")

    sk = fp.sketch(bdy, "Tube inserts", "XZ_Plane", offset=f + span)
    sk.setExpression(".AttachmentOffset.Base.z", f"{side.face_y_expr()} + {span_e}")
    fp.bolt_circle(sk, (0.0, 0.0), v["hub_screw_circle_d"] / 2, v["side_insert_d"], 4,
                   angle=0.0, name="insert")
    fp.drive(sk, "insert_u", f"{P('hub_screw_circle_d')} / 2")
    fp.drive(sk, "insert_dia", P("side_insert_d"))
    cut = fp.pocket(bdy, "Tube inserts", sk, v["tube_insert_depth"])
    cut.setExpression("Length", P("tube_insert_depth"))


def notch(bdy, side, v):
    sk = fp.sketch(bdy, "Marker notch", "XZ_Plane")
    R, d, h = v["wheel_r"], v["notch_depth"], v["notch_w"] / 2
    fp.polyline(sk, [(-h, R - d), (h, R - d), (h, R + 1.0), (-h, R + 1.0)],
                name="notch")
    rename(sk, "notch_y0", "notch_bottom")
    fp.drive(sk, "notch_bottom", f"{P('wheel_r')} - {P('notch_depth')}")
    fp.drive(sk, "notch_x0", f"-{P('notch_w')} / 2")
    fp.drive(sk, "notch_x1", f"{P('notch_w')} / 2")
    fp.drive(sk, "notch_y2", f"{P('wheel_r')} + 1 mm")
    fp.pocket(bdy, "Marker notch", sk, None, midplane=True)


def check_datum(datum, side, v):
    """The datum must sit where the first pin axis crosses the claw face."""
    O, A = pin_axes(side, v)[0]
    pl = datum.Placement
    z = pl.Rotation.multVec(Vector(0, 0, 1))
    x = pl.Rotation.multVec(Vector(1, 0, 0))
    if (pl.Base - O).Length > 1e-9 or (z - A).Length > 1e-9 or abs(x.y) > 1e-9:
        raise SystemExit(f"claw datum at {pl.Base}, z {z}; wanted {O}, {A}")


def build(doc, label, hand, motor):
    back_y = 0.0 if motor else OUTER_BACK_Y
    side = Side(hand, motor, back_y)
    v = _values()
    bdy = fp.body(doc, label)

    disc = fp.sketch(bdy, "Disc", "XZ_Plane", offset=back_y)
    fp.circle(disc, (0.0, 0.0), 2 * v["wheel_r"], name="disc")
    fp.drive(disc, "disc_dia", f"2 * {P('wheel_r')}")
    pad = fp.pad(bdy, "Disc", disc, v["side_t"])
    pad.setExpression("Length", P("side_t"))

    datum = claw_datum(bdy, side, v)
    doc.recompute()
    check_datum(datum, side, v)
    features = claw(bdy, side, v, datum)
    pattern = fp.polar_pattern(bdy, "Claws", features, int(round(v["claw_count"])),
                               axis="Y_Axis")
    pattern.setExpression("Occurrences", P("claw_count"))
    envelope(bdy, side, v)
    cup_edges(bdy, side, v)
    (motor_hub if motor else outer_hub)(bdy, side, v)
    notch(bdy, side, v)
    made = assembly_datums(bdy, side, v, datum)
    doc.recompute()
    check_assembly_datums(made, side, v)
    return bdy


def assembly_datums(bdy, side, v, claw_axis):
    """Where the assemblies join a wheel side.

    PIN1 .. PINn: where roller k's pin passes the washer face, Z down the pin
    hole, X the way the pin's flat faces: away from the wheel axis on
    left-handed sides and towards it on right-handed ones.  Each is `Claw axis` turned about the wheel axis to its
    claw and flipped to point down the hole, by an expression, so it follows
    the spreadsheet; how many there are is fixed when the part is built.

    Motor side: HUB on the back face, where the motor hub's flange sits, and
    TUBE on the claw face, where the outer side's tube ends; Z along -Y, into
    the wheel, X along X.  Outer side: TUBE_END on its tube's end, Z back up
    the tube, X along -X, so that it meets TUBE turned half round, claws
    facing claws.

    For the bought parts, Z out of the material: on the motor side
    SIDE_SCREW1 to 4 at the bottom of the counterbores, where the heads of the
    screws that join the sides sit, and HUB_INSERT1 to 4 on the back face, the
    inserts the hub's screws go into; on the outer side TUBE_INSERT1 to 4 on
    the tube's end, the inserts the side screws go into.
    """
    made = {}
    flip = "vector(1, 0, 0)" if side.hand > 0 else "vector(0, 1, 0)"
    for k in range(int(round(v["claw_count"]))):
        o = fp.lcs(bdy, f"PIN{k + 1}")
        o.setExpression("Placement", (
            f"placement(vector(0, 0, 0), rotation(vector(0, -1, 0), "
            f"{k} * 360 deg / {P('claw_count')})) * {claw_axis.Name}.Placement"
            f" * placement(vector(0, 0, 0), rotation({flip}, 180 deg))"))
        made[f"PIN{k + 1}"] = o
    down = fp.frame((1, 0, 0), (0, -1, 0))
    if side.motor:
        made["HUB"] = fp.lcs(bdy, "HUB", at=(0, -side.back_y, 0), axis=down[0],
                             roll=down[1])
        made["TUBE"] = fp.lcs(bdy, "TUBE", at=(0, -side.face_y(v), 0), axis=down[0],
                              roll=down[1], expressions={
                                  "Placement.Base.y": f"-{side.face_y_expr()}"})
    else:
        a = math.radians(v["roller_angle"])
        span_e = f"2 * {P('washer_offset')} * cos({P('roller_angle')})"
        up = fp.frame((-1, 0, 0), (0, 1, 0))
        made["TUBE_END"] = fp.lcs(
            bdy, "TUBE_END",
            at=(0, -side.face_y(v) - 2 * v["washer_offset"] * math.cos(a), 0),
            axis=up[0], roll=up[1],
            expressions={"Placement.Base.y": f"-{side.face_y_expr()} - {span_e}"})
    bought_datums(bdy, side, v)
    return made


def bought_datums(bdy, side, v):
    """The screw and insert datums (see `assembly_datums`)."""
    rc = v["hub_screw_circle_d"] / 2
    rce = f"{P('hub_screw_circle_d')} / 2"
    c45 = math.cos(math.radians(45.0))
    # (x, z, x expression, z expression) round the circle, from +X.
    square = [(rc, 0.0, rce, "0 mm"), (0.0, rc, "0 mm", rce),
              (-rc, 0.0, f"-{rce}", "0 mm"), (0.0, -rc, "0 mm", f"-{rce}")]
    diagonal = [(sx * rc * c45, sz * rc * c45, f"{'-' if sx < 0 else ''}{rce} * cos(45 deg)",
                 f"{'-' if sz < 0 else ''}{rce} * cos(45 deg)")
                for sx, sz in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    out_back, out_tube = (0, 1, 0), (0, -1, 0)
    if side.motor:
        groups = [("SIDE_SCREW", square, -v["counterbore_depth"], f"-{P('counterbore_depth')}",
                   out_back),
                  ("HUB_INSERT", diagonal, -side.back_y, "0 mm", out_back)]
    else:
        span = 2 * v["washer_offset"] * math.cos(math.radians(v["roller_angle"]))
        span_e = f"2 * {P('washer_offset')} * cos({P('roller_angle')})"
        groups = [("TUBE_INSERT", square, -side.face_y(v) - span,
                   f"-{side.face_y_expr()} - {span_e}", out_tube)]
    for name, points, y, ye, axis in groups:
        for k, (x, z, xe, ze) in enumerate(points, start=1):
            fp.lcs(bdy, f"{name}{k}", at=(x, y, z), axis=axis, expressions={
                "Placement.Base.x": xe, "Placement.Base.y": ye, "Placement.Base.z": ze})


def check_assembly_datums(made, side, v):
    """Every PINk where pin k's axis crosses the washer face, Z down the hole."""
    for k, (O, A) in enumerate(pin_axes(side, v)):
        pl = made[f"PIN{k + 1}"].Placement
        z = pl.Rotation.multVec(Vector(0, 0, 1))
        x = pl.Rotation.multVec(Vector(1, 0, 0))
        phi = math.radians(v["claw_phase"] + 360.0 * k / v["claw_count"])
        radial = Vector(math.cos(phi), 0, math.sin(phi))
        if ((pl.Base - O).Length > 1e-9 or (z + A).Length > 1e-9
                or (x - radial * side.hand).Length > 1e-9):
            raise SystemExit(f"PIN{k + 1} at {pl.Base}, z {z}, x {x}; wanted "
                             f"{O}, z {-A}, x {radial * side.hand}")


def test(doc, bdy):
    return fctest.flex(doc, bdy, [
        ("sheet", "cup_round", "=4.5 mm"),
        ("sheet", "cup_chamfer", "=1.4 mm"),
        ("sheet", "pin_axis_r", "=27.3 mm"),
        ("sheet", "pin_hole_depth", "=3 mm"),
        ("sheet", "pin_hole_round", "=0.8 mm"),
    ])
