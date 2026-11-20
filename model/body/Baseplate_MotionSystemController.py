"""Baseplate_MotionSystemController: the plate the controller board sits on.

The plate spans x 0..102, y -69..0, its top at z = 4.  It is 3 mm thick (z 1..4) with a 0.5 mm chamfer round the top
edge, standing on 1 mm bosses underneath.

- Four Ø4 holes that fix it to the body, at the spreadsheet's board_hole
  cells, which the body quarters and the alignment plate take their floor
  screws and pins from.
- Four Ø3.2 holes countersunk from below, Ø7 at the underside, for the screws
  that hold the controller board's spacers: its mounting holes as the board's
  KiCad layout has them, at (x - 25, 50.5 - y) in the layout's coordinates,
  which are the spreadsheet's board_screw cells.
- The bosses round the holes, drawn as chains of tangent arcs: each boss is a
  circle round its hole, neighbouring bosses are joined by R10 blends, and one
  group runs out to the plate's edge through R2 fillets.  Only the boss
  centres and radii are dimensioned; the blends' centres follow from
  tangency, so moving a hole moves its blends.  A boss's centre is its hole's,
  by expression: the board holes' from the spreadsheet, the screws' from the
  "Screw holes" sketch, which is the one place a screw is positioned (the
  countersinks follow it too).
"""

import math
import os

import fcprim as fp
import fctest

import Part
from FreeCAD import Vector

LENGTH, WIDTH = 102.0, 69.0
Z_UNDER, Z_TOP, EDGE = 1.0, 4.0, 0.5
BOSS_H = 1.0
BOARD_HOLE_D = 4.0
SCREW_D, HEAD_D = 3.2, 7.0
BLEND_R, FILLET_R = 10.0, 2.0
ROOT_PT, H_AXIS, V_AXIS = (-1, 1), -1, -2

fp.open_parameters()
P, V = fp.param, fp.sheet_value
ROW = {1: "board_row1_y", 2: "board_row2_y", 3: "board_row2_y", 4: "board_row1_y"}
BOARD_HOLES = [(V(f"board_hole{n}_x"), V(ROW[n])) for n in (1, 2, 3, 4)]
SCREWS = [(V(f"board_screw{n}_u"), V(f"board_screw{n}_v")) for n in (1, 2, 3, 4)]


# -- drawing helpers ---------------------------------------------------------

def _unit(a, b):
    d = (b[0] - a[0], b[1] - a[1])
    n = math.hypot(*d)
    return (d[0] / n, d[1] / n)


def touch(c1, r1, c2):
    """Where a circle round c1 touches an external neighbour centred at c2."""
    u = _unit(c1, c2)
    return (c1[0] + r1 * u[0], c1[1] + r1 * u[1])


def blend_centre(a, ra, b, rb, r, near):
    """Centre of a circle of radius r touching circles a and b from outside."""
    d = math.dist(a, b)
    p, q = ra + r, rb + r
    x = (p * p - q * q + d * d) / (2 * d)
    h = math.sqrt(max(p * p - x * x, 0.0))
    u = _unit(a, b)
    base = (a[0] + x * u[0], a[1] + x * u[1])
    cands = [(base[0] - h * u[1], base[1] + h * u[0]),
             (base[0] + h * u[1], base[1] - h * u[0])]
    return min(cands, key=lambda c: math.dist(c, near))


def arc(sk, centre, r, p_from, p_to, ccw=True):
    """An arc walked from p_from to p_to; returns (geo, from_pos, to_pos)."""
    a0 = math.atan2(p_from[1] - centre[1], p_from[0] - centre[0])
    a1 = math.atan2(p_to[1] - centre[1], p_to[0] - centre[0])
    if not ccw:
        a0, a1 = a1, a0
    while a1 <= a0:
        a1 += 2 * math.pi
    g = sk.addGeometry(Part.ArcOfCircle(Part.Circle(
        Vector(*centre, 0), Vector(0, 0, 1), r), a0, a1), False)
    return (g, 1, 2) if ccw else (g, 2, 1)


def seg(sk, p, q):
    return (fp.line(sk, p, q), 1, 2)


def close(sk, items, tangent):
    """Join each item's end to the next one's start: tangent or a corner."""
    for i, (g, _, end) in enumerate(items):
        g2, start2, _ = items[(i + 1) % len(items)]
        kind = "Tangent" if tangent[i] else "Coincident"
        fp.con(sk, kind, g, end, g2, start2)


def locate(sk, geo, pos, at, name):
    fp.con(sk, "DistanceX", *ROOT_PT, geo, pos, at[0], name=f"{name}_x")
    fp.con(sk, "DistanceY", *ROOT_PT, geo, pos, at[1], name=f"{name}_y")


def boss_circle(sk, item, centre, r, name):
    """Dimension an arc as a boss round a hole: its centre and radius."""
    g = item[0]
    locate(sk, g, 3, centre, name)
    fp.con(sk, "Radius", g, r, name=f"{name}_r")


# -- the bosses --------------------------------------------------------------

def edge_boss(sk, centre, r, name):
    """A boss circle cut off by the plate's edge at x = 0."""
    dy = math.sqrt(r * r - centre[0] ** 2)
    lo, hi = (0.0, centre[1] - dy), (0.0, centre[1] + dy)
    a = arc(sk, centre, r, lo, hi, ccw=True)
    edge = seg(sk, hi, lo)
    close(sk, [a, edge], [False, False])
    boss_circle(sk, a, centre, r, name)
    fp.con(sk, "PointOnObject", a[0], 1, V_AXIS)
    fp.con(sk, "PointOnObject", a[0], 2, V_AXIS)


def u_boss(sk, centre, r, name):
    """A boss round a hole near the edge y = -WIDTH, run out to that edge."""
    cx, cy = centre
    p_bl, p_br = (cx - r, -WIDTH), (cx + r, -WIDTH)
    p_r, p_l = (cx + r, cy), (cx - r, cy)
    items = [seg(sk, p_bl, p_br), seg(sk, p_br, p_r),
             arc(sk, centre, r, p_r, p_l, ccw=True), seg(sk, p_l, p_bl)]
    close(sk, items, [False, True, True, False])
    boss_circle(sk, items[2], centre, r, name)
    fp.con(sk, "Vertical", items[1][0])
    fp.con(sk, "Vertical", items[3][0])
    fp.con(sk, "Horizontal", items[0][0])
    fp.con(sk, "DistanceY", *ROOT_PT, items[0][0], 1, -WIDTH, name=f"{name}_edge")


def twin_boss(sk, a, ra, b, rb, near_1, near_2, name):
    """Two boss circles joined by R10 blends on both sides."""
    c1 = blend_centre(a, ra, b, rb, BLEND_R, near_1)
    c2 = blend_centre(a, ra, b, rb, BLEND_R, near_2)
    items = [arc(sk, a, ra, touch(a, ra, c1), touch(a, ra, c2), ccw=True),
             arc(sk, c2, BLEND_R, touch(c2, BLEND_R, a), touch(c2, BLEND_R, b), ccw=False),
             arc(sk, b, rb, touch(b, rb, c2), touch(b, rb, c1), ccw=True),
             arc(sk, c1, BLEND_R, touch(c1, BLEND_R, b), touch(c1, BLEND_R, a), ccw=False)]
    close(sk, items, [True] * 4)
    boss_circle(sk, items[0], a, ra, f"{name}_a")
    boss_circle(sk, items[2], b, rb, f"{name}_b")
    fp.con(sk, "Radius", items[1][0], BLEND_R, name=f"{name}_blend")
    fp.con(sk, "Radius", items[3][0], BLEND_R, name=f"{name}_blend_2")
    fp.drive(sk, f"{name}_blend_2", f"{sk.Name}.Constraints.{name}_blend")


def edge_twin_boss(sk, p, rp, q, rq, near_top, near_bottom, f_top, f_bottom, name):
    """Boss p at the edge x = LENGTH (R2 fillets) and boss q joined by blends."""
    ctop = blend_centre(p, rp, q, rq, BLEND_R, near_top)
    cbot = blend_centre(p, rp, q, rq, BLEND_R, near_bottom)
    ftop = (LENGTH - FILLET_R, p[1] + math.sqrt((rp + FILLET_R) ** 2 - (LENGTH - FILLET_R - p[0]) ** 2))
    fbot = (LENGTH - FILLET_R, p[1] - (ftop[1] - p[1]))
    e_bot, e_top = (LENGTH, fbot[1]), (LENGTH, ftop[1])
    items = [seg(sk, e_bot, e_top),
             arc(sk, ftop, FILLET_R, e_top, touch(ftop, FILLET_R, p), ccw=False),
             arc(sk, p, rp, touch(p, rp, ftop), touch(p, rp, ctop), ccw=True),
             arc(sk, ctop, BLEND_R, touch(ctop, BLEND_R, p), touch(ctop, BLEND_R, q), ccw=False),
             arc(sk, q, rq, touch(q, rq, ctop), touch(q, rq, cbot), ccw=True),
             arc(sk, cbot, BLEND_R, touch(cbot, BLEND_R, q), touch(cbot, BLEND_R, p), ccw=False),
             arc(sk, p, rp, touch(p, rp, cbot), touch(p, rp, fbot), ccw=True),
             arc(sk, fbot, FILLET_R, touch(fbot, FILLET_R, p), e_bot, ccw=False)]
    close(sk, items, [True] * 8)
    fp.con(sk, "Vertical", items[0][0])
    fp.con(sk, "DistanceX", *ROOT_PT, items[0][0], 1, LENGTH, name=f"{name}_edge")
    boss_circle(sk, items[2], p, rp, f"{name}_a")
    fp.con(sk, "Coincident", items[6][0], 3, items[2][0], 3)
    fp.con(sk, "Equal", items[6][0], items[2][0])
    boss_circle(sk, items[4], q, rq, f"{name}_b")
    me = sk.Name
    fp.con(sk, "Radius", items[3][0], BLEND_R, name=f"{name}_blend")
    fp.con(sk, "Radius", items[5][0], BLEND_R, name=f"{name}_blend_2")
    fp.con(sk, "Radius", items[1][0], FILLET_R, name=f"{name}_fillet")
    fp.con(sk, "Radius", items[7][0], FILLET_R, name=f"{name}_fillet_2")
    fp.drive(sk, f"{name}_blend_2", f"{me}.Constraints.{name}_blend")
    fp.drive(sk, f"{name}_fillet_2", f"{me}.Constraints.{name}_fillet")


def bosses(sk):
    # The points after a pair of bosses only pick which of the two possible
    # blend circles is drawn, by a point near it; they are not dimensions.
    edge_boss(sk, SCREWS[0], 5.0, "boss_screw1")
    edge_boss(sk, SCREWS[1], 5.0, "boss_screw2")
    fp.circle(sk, BOARD_HOLES[0], 10.0, name="boss_board1")
    u_boss(sk, BOARD_HOLES[1], 5.5, "boss_board2")
    twin_boss(sk, SCREWS[3], 5.0, BOARD_HOLES[2], 4.5,
              (107.0, -54.0), (84.0, -70.0), "boss_pair_low")
    edge_twin_boss(sk, SCREWS[2], 5.0, BOARD_HOLES[3], 5.0,
                   (101.0, -5.0), (86.0, -30.0), None, None, "boss_pair_high")


# -- the part ----------------------------------------------------------------

def holes(sk, points, d, name):
    for i, p in enumerate(points, start=1):
        fp.circle(sk, p, d, name=f"{name}{i}")
        if i > 1:
            fp.drive(sk, f"{name}{i}_dia", f"{sk.Name}.Constraints.{name}1_dia")


def build(doc):
    bdy = fp.body(doc, "Baseplate_MotionSystemController")
    plate = fp.sketch(bdy, "Plate", "XY_Plane", offset=Z_TOP - EDGE)
    fp.polyline(plate, [(0, -WIDTH), (LENGTH, -WIDTH), (LENGTH, 0), (0, 0)], name="plate")
    names = [c.Name for c in plate.Constraints]
    plate.renameConstraint(names.index("plate_x1"), "plate_length")
    plate.renameConstraint(names.index("plate_y0"), "plate_width")
    fp.pad(bdy, "Plate", plate, Z_TOP - EDGE - Z_UNDER, reversed_=True)
    fp.pad(bdy, "Top edge chamfer", plate, EDGE, taper=-45.0)

    under = fp.sketch(bdy, "Bosses", "XY_Plane", offset=Z_UNDER)
    bosses(under)
    fp.pad(bdy, "Bosses", under, BOSS_H, reversed_=True)

    board = fp.sketch(bdy, "Board holes", "XY_Plane")
    holes(board, BOARD_HOLES, BOARD_HOLE_D, "board")
    fp.pocket(bdy, "Board holes", board, None, midplane=True)

    screws = fp.sketch(bdy, "Screw holes", "XY_Plane")
    holes(screws, SCREWS, SCREW_D, "screw")
    fp.pocket(bdy, "Screw holes", screws, None, midplane=True)

    heads = fp.sketch(bdy, "Countersinks", "XY_Plane")
    holes(heads, SCREWS, HEAD_D, "head")
    sink = fp.pocket(bdy, "Countersinks", heads, (HEAD_D - SCREW_D) / 2,
                     reversed_=True)
    sink.setExpression("Length", f"({heads.Name}.Constraints.head1_dia - "
                                 f"{screws.Name}.Constraints.screw1_dia) / 2")
    sink.TaperAngle = -45.0
    one_place(under, board, screws, heads)
    # Where the assemblies join it: board hole 1 at the underside of its boss,
    # which stands on the floor over a floor screw; Z down the screw, X along
    # +x, to board hole 4 in the same row.
    axis, roll = fp.frame((1, 0, 0), (0, 0, -1))
    fp.lcs(bdy, "BOARD1", at=(BOARD_HOLES[0][0], BOARD_HOLES[0][1], 0.0), axis=axis, roll=roll,
           expressions={"Placement.Base.x": P("board_hole1_x"),
                        "Placement.Base.y": P(ROW[1])})
    # Where the bought parts go, Z out of the material: an insert in each
    # board hole from below, a spacer on each screw hole, and the countersunk
    # screw under it, its head flush with the underside.
    for n in (1, 2, 3, 4):
        at = {"Placement.Base.x": P(f"board_hole{n}_x"), "Placement.Base.y": P(ROW[n])}
        fp.lcs(bdy, f"INSERT{n}", at=(*BOARD_HOLES[n - 1], 0.0), axis=axis, roll=roll,
               expressions=at)
        at = {"Placement.Base.x": P(f"board_screw{n}_u"),
              "Placement.Base.y": P(f"board_screw{n}_v")}
        fp.lcs(bdy, f"SCREW{n}", at=(*SCREWS[n - 1], 0.0), axis=axis, roll=roll,
               expressions=at)
        fp.lcs(bdy, f"SPACER{n}", at=(*SCREWS[n - 1], Z_TOP), expressions=at)
    return bdy


def one_place(under, board, screws, heads):
    """Each position set once: the holes from the spreadsheet, and the
    bosses and countersinks from the hole they surround."""
    for n in (1, 2, 3, 4):
        fp.drive(board, f"board{n}_u", P(f"board_hole{n}_x"))
        fp.drive(board, f"board{n}_v", P(ROW[n]))
        fp.drive(screws, f"screw{n}_u", P(f"board_screw{n}_u"))
        fp.drive(screws, f"screw{n}_v", P(f"board_screw{n}_v"))
    hole = lambda n, uv: f"{screws.Name}.Constraints.screw{n}_{uv}"
    for n in (1, 2, 3, 4):
        fp.drive(heads, f"head{n}_u", hole(n, "u"))
        fp.drive(heads, f"head{n}_v", hole(n, "v"))
    # Boss centres: (sketch constraint, x expression, y expression).
    bosses = [("boss_screw1_x", "boss_screw1_y", hole(1, "u"), hole(1, "v")),
              ("boss_screw2_x", "boss_screw2_y", hole(2, "u"), hole(2, "v")),
              ("boss_pair_high_a_x", "boss_pair_high_a_y", hole(3, "u"), hole(3, "v")),
              ("boss_pair_low_a_x", "boss_pair_low_a_y", hole(4, "u"), hole(4, "v")),
              ("boss_board1_u", "boss_board1_v", P("board_hole1_x"), P(ROW[1])),
              ("boss_board2_x", "boss_board2_y", P("board_hole2_x"), P(ROW[2])),
              ("boss_pair_low_b_x", "boss_pair_low_b_y", P("board_hole3_x"), P(ROW[3])),
              ("boss_pair_high_b_x", "boss_pair_high_b_y", P("board_hole4_x"), P(ROW[4]))]
    for cx, cy, ex, ey in bosses:
        fp.drive(under, cx, ex)
        fp.drive(under, cy, ey)


def test(doc, bdy):
    get = lambda label: doc.getObjectsByLabel(label)[0]
    return fctest.flex(doc, bdy, [
        (get("Plate"), "plate_length", 110.0),
        (get("Bosses"), "boss_pair_high_blend", 8.0),
        ("sheet", "board_screw4_u", "=92 mm"),
        ("sheet", "board_hole3_x", "=96 mm"),
        (get("Board holes"), "board1_dia", 3.5),
    ])


fp.make(__file__, "Baseplate_MotionSystemController", build, test=test)
