"""One body quarter, drawn for any of the four quadrants.

The body is four quarters round the origin.  Each is the same part placed in
its own quadrant, the signs (sx, sy) saying which, with a short list of
extras of its own.  Everything is drawn in the quarter's own coordinates and
flipped by those signs as it goes into the sketch, so one description serves
all four, and every dimension the quarters share is a cell of the spreadsheet.

A quarter is:

- an L-shaped floor with an R8 corner, and a pocket in it for the alignment
  plate, the triangle x + y < plate_diag, plate_t deep;
- an S-shaped wall on the floor, R8 at its inside corners;
- a NEMA 17 face in the wall across the quarter (motor_x): the centring
  boss and four screws on nema_pitch;
- three Ø4 holes 15 deep with 118 degree drill points down into the wall
  corners, for the lid;
- the plate's screws through the floor, countersunk from below;
- a joint at each end of the wall with the neighbouring quarters.  The
  quarters join in a pinwheel: at every joint one quarter reaches over with a
  tongue (wall_t - skin_t thick, tongue_len long, two Ø4 insert holes) and the
  other leaves only its outer skin there (skin_t, two countersunk screws).
  Which end carries the tongue follows from the quadrant: the side wall when
  sx and sy have the same sign, the back wall otherwise.

Extras, given by each quarter's script: the two slots under the alignment
plate, a floor screw, the half of a board pin hole that falls in this quarter,
and the window in one quarter's side wall.  The floor screws and pin holes are
named by the controller board hole they sit under, and placed from the board
and baseplate cells, which the baseplate and the alignment plate use too.

Every dimension the quarters share is a cell of the spreadsheet, so changing
one in FreeCAD is one edit, not four.
"""

import math

import fcprim as fp
import fctest

P, V = fp.param, fp.sheet_value

LID_POINT = 118.0                                 # a twist drill's point
WINDOW = (23.6, 37.0, 36.0, 45.0)                 # y from, y to, z from, z to; one quarter's


class Quadrant:
    """Signs of one quadrant, and how they turn values and expressions."""

    def __init__(self, sx, sy):
        self.sx, self.sy = sx, sy
        self.side_tongue = sx * sy > 0

    def pt(self, x, y):
        return (self.sx * x, self.sy * y)

    def ex(self, e):
        return e if self.sx > 0 else f"-({e})"

    def ey(self, e):
        return e if self.sy > 0 else f"-({e})"


def _values():
    names = ("body_x", "body_y", "body_h", "floor_t", "wall_t", "skin_t",
             "tongue_len", "tongue_gap", "joint_chamfer", "step_y", "motor_x",
             "corner_r", "motor_y", "motor_z", "nema_pitch", "nema_boss_d",
             "nema_screw_d", "plate_diag", "plate_t", "plate_hole_in",
             "plate_hole_spread", "wheel_gap", "plate_slot_w", "plate_slot_h",
             "plate_slot_y1", "plate_slot_y2", "floor_hole_d", "countersink_d",
             "joint_insert_d", "joint_screw_d", "joint_z1", "joint_z2", "lid_hole_d",
             "lid_hole_depth", "baseplate_x", "baseplate_y")
    return {n: V(n) for n in names}


def outline(sk, q, pts, name, fillets=None):
    """A closed polyline whose dimensions are driven by expressions.

    `pts` holds ((x value, x expression), (y value, y expression)) per corner,
    in the quarter's own coordinates; a None expression leaves the plain value.
    """
    xy = [q.pt(px[0], py[0]) for px, py in pts]
    fp.polyline(sk, xy, name=name, fillets=fillets)
    names = [c.Name for c in sk.Constraints]
    for i, (px, py) in enumerate(pts):
        for axis, (_, expr), turn in (("x", px, q.ex), ("y", py, q.ey)):
            cname = f"{name}_{axis}{i}"
            if cname in names and expr:
                fp.drive(sk, cname, turn(expr))
    for i in (fillets or {}):
        fp.drive(sk, f"{name}_r{i}", P("corner_r"))


def circle(sk, q, x, y, d, name, d_expr=None, local=True):
    """A circle at (x, y): each a (value, expression) pair, local or global."""
    at = q.pt(x[0], y[0]) if local else (x[0], y[0])
    # A coordinate an expression drives keeps its dimension even at zero.
    fp.circle(sk, at, d, name=name, keep_zero=bool(x[1] or y[1]))
    tx, ty = (q.ex, q.ey) if local else ((lambda e: e), (lambda e: e))
    if x[1]:
        fp.drive(sk, f"{name}_u", tx(x[1]))
    if y[1]:
        fp.drive(sk, f"{name}_v", ty(y[1]))
    if d_expr:
        fp.drive(sk, f"{name}_dia", d_expr)


def wall_points(q, v):
    X, Y, W, S = P("body_x"), P("body_y"), P("wall_t"), P("skin_t")
    T, G, C = P("tongue_len"), P("tongue_gap"), P("joint_chamfer")
    SY, MX = P("step_y"), P("motor_x")
    x, y, w, s = v["body_x"], v["body_y"], v["wall_t"], v["skin_t"]
    t, g, c = v["tongue_len"], v["tongue_gap"], v["joint_chamfer"]
    sy_, mx = v["step_y"], v["motor_x"]
    pts = []
    if q.side_tongue:
        pts += [((x - w, f"{X} - {W}"), (-t, f"-{T}")),
                ((x - s - c, f"{X} - {S} - {C}"), (-t, f"-{T}")),
                ((x - s, f"{X} - {S}"), (-t + c, f"{C} - {T}")),
                ((x - s, f"{X} - {S}"), (0.0, None)),
                ((x, X), (0.0, None))]
    else:
        pts += [((x - w, f"{X} - {W}"), (t + g, f"{T} + {G}")),
                ((x - s, f"{X} - {S}"), (t + g, f"{T} + {G}")),
                ((x - s, f"{X} - {S}"), (c, C)),
                ((x - s + c, f"{X} - {S} + {C}"), (0.0, None)),
                ((x, X), (0.0, None))]
    pts += [((x, X), (sy_, SY)), ((mx, MX), (sy_, SY)), ((mx, MX), (y, Y))]
    if q.side_tongue:                      # the back end is a recess
        pts += [((0.0, None), (y, Y)),
                ((0.0, None), (y - s + c, f"{Y} - {S} + {C}")),
                ((c, C), (y - s, f"{Y} - {S}")),
                ((t + g, f"{T} + {G}"), (y - s, f"{Y} - {S}")),
                ((t + g, f"{T} + {G}"), (y - w, f"{Y} - {W}"))]
    else:                                  # the back end is a tongue
        pts += [((0.0, None), (y, Y)),
                ((0.0, None), (y - s, f"{Y} - {S}")),
                ((-t + c, f"{C} - {T}"), (y - s, f"{Y} - {S}")),
                ((-t, f"-{T}"), (y - s - c, f"{Y} - {S} - {C}")),
                ((-t, f"-{T}"), (y - w, f"{Y} - {W}"))]
    pts += [((mx - w, f"{MX} - {W}"), (y - w, f"{Y} - {W}")),
            ((mx - w, f"{MX} - {W}"), (sy_ - w, f"{SY} - {W}")),
            ((x - w, f"{X} - {W}"), (sy_ - w, f"{SY} - {W}"))]
    corners = {5 + 1: v["corner_r"], len(pts) - 3: v["corner_r"],
               len(pts) - 1: v["corner_r"]}
    return pts, corners


def board_hole(n):
    """Controller board hole n in the body's frame: ((x, expr), (y, expr)).

    The baseplate lies turned half round, its origin at (baseplate_x,
    baseplate_y), so its point (u, v) is at (baseplate_x - u, baseplate_y - v).
    """
    row = "board_row1_y" if n in (1, 4) else "board_row2_y"
    x = V("baseplate_x") - V(f"board_hole{n}_x")
    y = V("baseplate_y") - V(row)
    return ((x, f"{P('baseplate_x')} - {P(f'board_hole{n}_x')}"),
            (y, f"{P('baseplate_y')} - {P(row)}"))


def countersunk(bdy, q, label, holes, cell, plane, offset, reversed_):
    """Holes of the diameter in `cell` through all, countersunk at 45 degrees
    to countersink_d."""
    d, sink_d = V(cell), V("countersink_d")
    through = fp.sketch(bdy, label, plane)
    for i, (x, y, local) in enumerate(holes, start=1):
        circle(through, q, x, y, d, f"hole{i}", d_expr=P(cell), local=local)
    fp.pocket(bdy, label, through, None, midplane=True)
    heads = fp.sketch(bdy, label + " countersinks", plane, offset=offset)
    for i, (x, y, local) in enumerate(holes, start=1):
        circle(heads, q, x, y, sink_d, f"sink{i}", d_expr=P("countersink_d"), local=local)
    sink = fp.pocket(bdy, label + " countersinks", heads, (sink_d - d) / 2,
                     reversed_=reversed_)
    sink.setExpression("Length", f"({P('countersink_d')} - {P(cell)}) / 2")
    sink.TaperAngle = -45.0
    return sink


def build(doc, label, sx, sy, slots=False, floor_screws=(), pin_hole=None,
          window=False):
    q = Quadrant(sx, sy)
    v = _values()
    bdy = fp.body(doc, label)

    floor = fp.sketch(bdy, "Floor", "XY_Plane")
    X, Y, SY, MX = P("body_x"), P("body_y"), P("step_y"), P("motor_x")
    outline(floor, q, [((0.0, None), (0.0, None)), ((v["body_x"], X), (0.0, None)),
                       ((v["body_x"], X), (v["step_y"], SY)),
                       ((v["motor_x"], MX), (v["step_y"], SY)),
                       ((v["motor_x"], MX), (v["body_y"], Y)),
                       ((0.0, None), (v["body_y"], Y))],
            "floor", fillets={3: v["corner_r"]})
    pad = fp.pad(bdy, "Floor", floor, v["floor_t"])
    pad.setExpression("Length", P("floor_t"))

    wall = fp.sketch(bdy, "Wall", "XY_Plane", offset=v["floor_t"])
    wall.setExpression(".AttachmentOffset.Base.z", P("floor_t"))
    pts, corners = wall_points(q, v)
    outline(wall, q, pts, "wall", fillets=corners)
    pad = fp.pad(bdy, "Wall", wall, v["body_h"] - v["floor_t"])
    pad.setExpression("Length", f"{P('body_h')} - {P('floor_t')}")

    # The alignment plate's pocket.
    pocket = fp.sketch(bdy, "Plate pocket", "XY_Plane", offset=v["floor_t"])
    pocket.setExpression(".AttachmentOffset.Base.z", P("floor_t"))
    D = P("plate_diag")
    outline(pocket, q, [((0.0, None), (0.0, None)), ((v["plate_diag"], D), (0.0, None)),
                        ((0.0, None), (v["plate_diag"], D))], "pocket")
    cut = fp.pocket(bdy, "Plate pocket", pocket, v["plate_t"])
    cut.setExpression("Length", P("plate_t"))

    # Floor screws: the plate's two in this quadrant, then the extras, all
    # countersunk from below.
    u = f"({P('plate_diag')} / sqrt(2) - {P('plate_hole_in')})"
    s = P("plate_hole_spread")
    uv = v["plate_diag"] / math.sqrt(2) - v["plate_hole_in"]
    a, b = (uv - v["plate_hole_spread"]) / math.sqrt(2), (uv + v["plate_hole_spread"]) / math.sqrt(2)
    ea, eb = f"({u} - {s}) / sqrt(2)", f"({u} + {s}) / sqrt(2)"
    holes = [((a, ea), (b, eb), True), ((b, eb), (a, ea), True)]
    holes += [board_hole(n) + (False,) for n in floor_screws]
    if pin_hole:
        holes.append(board_hole(pin_hole) + (False,))
    countersunk(bdy, q, "Floor screws", holes, "floor_hole_d", "XY_Plane", 0.0, True)

    if slots:
        sk = fp.sketch(bdy, "Plate slots", "XY_Plane")
        xt, xe = v["plate_slot_w"] / 2, f"{P('plate_slot_w')} / 2"
        for i, cell in enumerate(("plate_slot_y1", "plate_slot_y2"), start=1):
            y0, y1 = v[cell] - v["plate_slot_h"] / 2, v[cell] + v["plate_slot_h"] / 2
            e0 = f"{P(cell)} - {P('plate_slot_h')} / 2"
            e1 = f"{P(cell)} + {P('plate_slot_h')} / 2"
            outline(sk, q, [((0.0, None), (y0, e0)), ((xt, xe), (y0, e0)),
                            ((xt, xe), (y1, e1)), ((0.0, None), (y1, e1))],
                    f"slot{i}")
        fp.pocket(bdy, "Plate slots", sk, v["floor_t"] - v["plate_t"],
                  reversed_=True)

    # The motor face, in the wall across the quarter.
    motor = fp.sketch(bdy, "Motor face", "YZ_Plane")
    my, mz, p = P("motor_y"), P("motor_z"), P("nema_pitch")
    at = (q.sy * v["motor_y"], v["motor_z"])
    fp.circle(motor, at, v["nema_boss_d"], name="boss")
    fp.drive(motor, "boss_u", q.ey(my))
    fp.drive(motor, "boss_v", mz)
    fp.drive(motor, "boss_dia", P("nema_boss_d"))
    half = v["nema_pitch"] / 2
    for i, (dy, dz) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)), start=1):
        fp.circle(motor, (q.sy * (v["motor_y"] + dy * half), v["motor_z"] + dz * half),
                  v["nema_screw_d"], name=f"screw{i}")
        fp.drive(motor, f"screw{i}_u", q.ey(f"{my} {'+' if dy > 0 else '-'} {p} / 2"))
        fp.drive(motor, f"screw{i}_v", f"{mz} {'+' if dz > 0 else '-'} {p} / 2")
        fp.drive(motor, f"screw{i}_dia", P("nema_screw_d"))
    fp.pocket(bdy, "Motor face", motor, None, midplane=True)

    # The joints.  Side joint: holes along X at y = -/+ T/2; back joint:
    # along Y at x = -/+ T/2.  A tongue takes inserts, a skin countersunk screws.
    T = v["tongue_len"]
    side_y = -T / 2 if q.side_tongue else T / 2
    back_x = T / 2 if q.side_tongue else -T / 2
    heights = [(v["joint_z1"], P("joint_z1")), (v["joint_z2"], P("joint_z2"))]
    side = [((side_y, f"{'-' if q.side_tongue else ''}{P('tongue_len')} / 2"), z)
            for z in heights]
    back = [((back_x, f"{'' if q.side_tongue else '-'}{P('tongue_len')} / 2"), z)
            for z in heights]

    def along_y_sketch(lbl, pts, cell, plane, offset=0.0):
        sk = fp.sketch(bdy, lbl, plane, offset=offset)
        for i, ((h, he), (z, ze)) in enumerate(pts, start=1):
            hh = q.sy * h if plane == "YZ_Plane" else q.sx * h
            fp.circle(sk, (hh, z), V(cell), name=f"hole{i}")
            fp.drive(sk, f"hole{i}_u", q.ey(he) if plane == "YZ_Plane" else q.ex(he))
            fp.drive(sk, f"hole{i}_v", ze)
            fp.drive(sk, f"hole{i}_dia", P(cell))
        return sk

    def countersink_depth(sink):
        sink.setExpression("Length", f"({P('countersink_d')} - {P('joint_screw_d')}) / 2")
        sink.TaperAngle = -45.0
    depth = (v["countersink_d"] - v["joint_screw_d"]) / 2

    if q.side_tongue:
        sk = along_y_sketch("Side joint inserts", side, "joint_insert_d", "YZ_Plane")
        fp.pocket(bdy, "Side joint inserts", sk, None, midplane=True)
        sk = along_y_sketch("Back joint screws", back, "joint_screw_d", "XZ_Plane")
        fp.pocket(bdy, "Back joint screws", sk, None, midplane=True)
        sk = along_y_sketch("Back joint countersinks", back, "countersink_d", "XZ_Plane",
                            offset=-q.sy * v["body_y"])
        countersink_depth(fp.pocket(bdy, "Back joint countersinks", sk, depth,
                                    reversed_=q.sy > 0))
    else:
        sk = along_y_sketch("Back joint inserts", back, "joint_insert_d", "XZ_Plane")
        fp.pocket(bdy, "Back joint inserts", sk, None, midplane=True)
        sk = along_y_sketch("Side joint screws", side, "joint_screw_d", "YZ_Plane")
        fp.pocket(bdy, "Side joint screws", sk, None, midplane=True)
        sk = along_y_sketch("Side joint countersinks", side, "countersink_d", "YZ_Plane",
                            offset=q.sx * v["body_x"])
        countersink_depth(fp.pocket(bdy, "Side joint countersinks", sk, depth,
                                    reversed_=q.sx < 0))

    # Lid screws, down into the three wall corners.
    lid = fp.sketch(bdy, "Lid screws", "XY_Plane", offset=v["body_h"])
    lid.setExpression(".AttachmentOffset.Base.z", P("body_h"))
    W = P("wall_t")
    for i, ((x, ex_), (y, ey_)) in enumerate((
            ((v["motor_x"], MX), (v["step_y"], SY)),
            ((v["body_x"] - v["wall_t"], f"{X} - {W}"), (v["step_y"] - v["wall_t"], f"{SY} - {W}")),
            ((v["motor_x"] - v["wall_t"], f"{MX} - {W}"), (v["body_y"] - v["wall_t"], f"{Y} - {W}"))),
            start=1):
        circle(lid, q, (x, ex_), (y, ey_), v["lid_hole_d"], f"lid{i}", d_expr=P("lid_hole_d"))
    drill = fp.hole(bdy, "Lid screws", lid, v["lid_hole_d"], v["lid_hole_depth"], LID_POINT)
    drill.setExpression("Diameter", P("lid_hole_d"))
    drill.setExpression("Depth", P("lid_hole_depth"))

    if window:
        y0, y1, z0, z1 = WINDOW
        sk = fp.sketch(bdy, "Window", "YZ_Plane")
        fp.polyline(sk, [(q.sy * y0, z0), (q.sy * y1, z0), (q.sy * y1, z1), (q.sy * y0, z1)],
                    name="window")
        fp.pocket(bdy, "Window", sk, None, midplane=True)
        c = v["joint_chamfer"]
        sk = fp.sketch(bdy, "Window chamfer", "YZ_Plane", offset=q.sx * v["body_x"])
        fp.polyline(sk, [(q.sy * (y0 - c), z0 - c), (q.sy * (y1 + c), z0 - c),
                         (q.sy * (y1 + c), z1 + c), (q.sy * (y0 - c), z1 + c)],
                    name="window_chamfer")
        sink = fp.pocket(bdy, "Window chamfer", sk, c, reversed_=q.sx < 0)
        sink.TaperAngle = -45.0
    datums(bdy, q, v, floor_screws)
    bought_datums(bdy, q, v, holes[:2], floor_screws, pin_hole)
    return bdy


def datums(bdy, q, v, floor_screws):
    """Where the assemblies join a quarter.

    CENTRE: the body's centre, which the quarter is drawn about, in its own
    frame; the four quarters and the alignment plate meet on it.  WHEEL: on
    the motor axis, `wheel_gap` beyond the motor wall's outer face, where the
    wheel's back face sits; Z out along the shaft, X up where sx and sy have
    the same sign and down where they differ, as the motor's datum MOTOR has
    it, so that the hub's flat starts on the shaft's.  FLOOR_SCREW: on the
    floor's top at the floor screw, where the baseplate's board hole sits; Z
    down the screw, X along -x, the row the board's floor screws share.
    """
    fp.lcs(bdy, "CENTRE")
    axis, roll = fp.frame((0, 0, q.sx * q.sy), (q.sx, 0, 0))
    fp.lcs(bdy, "WHEEL",
           at=(q.sx * (v["motor_x"] + v["wheel_gap"]), q.sy * v["motor_y"], v["motor_z"]),
           axis=axis, roll=roll, expressions={
               "Placement.Base.x": q.ex(f"{P('motor_x')} + {P('wheel_gap')}"),
               "Placement.Base.y": q.ey(P("motor_y")),
               "Placement.Base.z": P("motor_z")})
    axis, roll = fp.frame((-1, 0, 0), (0, 0, -1))
    for i, n in enumerate(floor_screws):
        (x, ex), (y, ey) = board_hole(n)
        fp.lcs(bdy, "FLOOR_SCREW" + ("" if len(floor_screws) == 1 else str(i + 1)),
               at=(x, y, v["floor_t"]), axis=axis, roll=roll,
               expressions={"Placement.Base.x": ex, "Placement.Base.y": ey,
                            "Placement.Base.z": P("floor_t")})


def bought_datums(bdy, q, v, plate_holes, floor_screws, pin_hole):
    """Where the bought parts go, each datum with Z out of the material.

    MOTOR: the motor's face, on the inside of the motor wall at the motor
    axis, Z along the shaft (out through the wall), X turned so that the
    motor's connector points to the back wall.  NEMA_SCREW1 to 4: on the
    wall's outer face at the screws.  JOINT_SCREW1 and 2: the countersunk
    screws through this quarter's skin, flush with its outer face.
    JOINT_INSERT1 and 2: the inserts in this quarter's tongue, flush with the
    face the neighbour's skin covers.  LID_INSERT1 to 3: the lid holes' mouths
    on top of the wall.  PLATE_SCREW1 and 2: the alignment plate's screws,
    countersunk flush under the floor; FLOOR_SCREW_HEAD and PIN_SCREW_HEAD the
    same for the baseplate's floor screw and pin, the pin's in the quarter
    below the centre line only, since two quarters share its countersink.
    """
    X, Y, MX, SY, W = P("body_x"), P("body_y"), P("motor_x"), P("step_y"), P("wall_t")
    my, mz, pitch = P("motor_y"), P("motor_z"), P("nema_pitch")
    out_x, out_y = (q.sx, 0, 0), (0, q.sy, 0)
    axis, roll = fp.frame((0, 0, q.sx * q.sy), out_x)
    fp.lcs(bdy, "MOTOR", at=(q.sx * (v["motor_x"] - v["wall_t"]), q.sy * v["motor_y"],
                             v["motor_z"]), axis=axis, roll=roll,
           expressions={"Placement.Base.x": q.ex(f"{MX} - {W}"),
                        "Placement.Base.y": q.ey(my), "Placement.Base.z": mz})
    half = v["nema_pitch"] / 2
    for i, (dy, dz) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)), start=1):
        fp.lcs(bdy, f"NEMA_SCREW{i}",
               at=(q.sx * v["motor_x"], q.sy * (v["motor_y"] + dy * half),
                   v["motor_z"] + dz * half), axis=out_x, expressions={
                   "Placement.Base.x": q.ex(MX),
                   "Placement.Base.y": q.ey(f"{my} {'+' if dy > 0 else '-'} {pitch} / 2"),
                   "Placement.Base.z": f"{mz} {'+' if dz > 0 else '-'} {pitch} / 2"})
    T, skin = v["tongue_len"], v["skin_t"]
    zs = [(v["joint_z1"], P("joint_z1")), (v["joint_z2"], P("joint_z2"))]
    half_t = f"{P('tongue_len')} / 2"
    side = (-T / 2, f"-{half_t}") if q.side_tongue else (T / 2, half_t)
    back = (T / 2, half_t) if q.side_tongue else (-T / 2, f"-{half_t}")
    for i, (z, ze) in enumerate(zs, start=1):
        # A side joint lies on the side wall at y = side, a back joint on the
        # back wall at x = back; this quarter's skin is at the one end, its
        # tongue at the other.
        side_at = lambda depth, de: (
            (q.sx * (v["body_x"] - depth), q.sy * side[0], z),
            {"Placement.Base.x": q.ex(f"{X} - {de}"), "Placement.Base.y": q.ey(side[1]),
             "Placement.Base.z": ze}, out_x)
        back_at = lambda depth, de: (
            (q.sx * back[0], q.sy * (v["body_y"] - depth), z),
            {"Placement.Base.x": q.ex(back[1]), "Placement.Base.y": q.ey(f"{Y} - {de}"),
             "Placement.Base.z": ze}, out_y)
        screw = back_at(0.0, "0 mm") if q.side_tongue else side_at(0.0, "0 mm")
        insert = side_at(skin, P("skin_t")) if q.side_tongue else back_at(skin, P("skin_t"))
        for name, (at, ex, ax) in ((f"JOINT_SCREW{i}", screw), (f"JOINT_INSERT{i}", insert)):
            fp.lcs(bdy, name, at=at, axis=ax, expressions=ex)
    for i, ((x, ex_), (y, ey_)) in enumerate((
            ((v["motor_x"], MX), (v["step_y"], SY)),
            ((v["body_x"] - v["wall_t"], f"{X} - {W}"), (v["step_y"] - v["wall_t"], f"{SY} - {W}")),
            ((v["motor_x"] - v["wall_t"], f"{MX} - {W}"), (v["body_y"] - v["wall_t"], f"{Y} - {W}"))),
            start=1):
        fp.lcs(bdy, f"LID_INSERT{i}", at=(q.sx * x, q.sy * y, v["body_h"]), expressions={
            "Placement.Base.x": q.ex(ex_), "Placement.Base.y": q.ey(ey_),
            "Placement.Base.z": P("body_h")})
    down = (0, 0, -1)
    for i, ((x, ex_), (y, ey_), _) in enumerate(plate_holes, start=1):
        fp.lcs(bdy, f"PLATE_SCREW{i}", at=(q.sx * x, q.sy * y, 0.0), axis=down,
               expressions={"Placement.Base.x": q.ex(ex_), "Placement.Base.y": q.ey(ey_)})
    heads = [("FLOOR_SCREW_HEAD", n) for n in floor_screws]
    if pin_hole and q.sy < 0:
        heads.append(("PIN_SCREW_HEAD", pin_hole))
    for name, n in heads:
        (x, ex_), (y, ey_) = board_hole(n)
        fp.lcs(bdy, name, at=(x, y, 0.0), axis=down,
               expressions={"Placement.Base.x": ex_, "Placement.Base.y": ey_})


def test(doc, bdy):
    return fctest.flex(doc, bdy, [
        ("sheet", "wall_t", "=4 mm"),
        ("sheet", "tongue_len", "=12 mm"),
        ("sheet", "corner_r", "=6 mm"),
        ("sheet", "plate_diag", "=66 mm"),
        ("sheet", "motor_z", "=28 mm"),
        ("sheet", "baseplate_x", "=52 mm"),
        ("sheet", "baseplate_y", "=-63 mm"),
        ("sheet", "joint_z1", "=16 mm"),
    ])
