"""Body_Alignment_Plate: the plate that locates the four body quarters.

The plate lies flat from z = 2 to z = 5, centred on the origin where the four
quarters meet.

Seen in a frame turned 45 degrees, the outline is a square whose sides sit
0.1 inside a 70 mm diamond (35 * sqrt(2) - 0.1 from the centre, a fit
clearance), with 5 mm chamfers on its corners.  The bottom edge is broken by a
0.5 mm chamfer all round, drawn as a tapered pad so it needs no edge picking.

- Eight Ø4 holes, two per side, 8 mm in from the unclearanced edge and 25 mm
  either side of the side's middle: one pair, patterned four times.
- Two 15 x 4 slots on +Y, and two Ø3.6 holes on the X axis for the pins that
  locate the controller's baseplate.  Slots and pins come from the spreadsheet,
  which the quarters' floors share: the pins sit at the baseplate's holes 2 and
  3, placed by `quarter.board_hole`.
"""

import math
import os

import fcprim as fp
import _quarter as quarter
import fctest

fp.open_parameters()
P, V = fp.param, fp.sheet_value

DIAMOND = 35.0 * math.sqrt(2.0)    # the 70 mm diamond's sides, from the centre
CLEARANCE = 0.1
CORNER = 5.0
Z_BOTTOM, THICKNESS, EDGE = 2.0, 3.0, 0.5
HOLE_D, HOLE_IN, HOLE_SPREAD = 4.0, 8.0, 25.0
ROOT_PT = (-1, 1)


def octagon(sk, half, corner):
    """A square of half-width `half` with `corner` chamfers, point-symmetric."""
    h, c = half, corner
    pts = [(h, -h + c), (h, h - c), (h - c, h), (-h + c, h),
           (-h, h - c), (-h, -h + c), (-h + c, -h), (h - c, -h)]
    L = [fp.line(sk, pts[i], pts[(i + 1) % 8]) for i in range(8)]
    k = lambda *args, name=None: fp.con(sk, *args, name=name)
    for i in range(8):
        k("Coincident", L[i], 2, L[(i + 1) % 8], 1)
    k("Vertical", L[0])
    k("Horizontal", L[2])
    for i in range(4):                     # point i mirrors point i + 4
        k("Symmetric", L[i], 1, L[i + 4], 1, *ROOT_PT)
    k("DistanceX", *ROOT_PT, L[0], 1, h, name="half_width")
    k("DistanceY", *ROOT_PT, L[2], 1, h, name="half_width_v")
    k("DistanceY", L[1], 1, L[1], 2, c, name="corner_chamfer")
    k("DistanceX", L[1], 2, L[1], 1, c, name="corner_chamfer_2")
    k("DistanceX", L[3], 2, L[3], 1, c, name="corner_chamfer_3")
    k("DistanceY", L[3], 2, L[3], 1, c, name="corner_chamfer_4")
    me = sk.Name
    fp.drive(sk, "half_width_v", f"{me}.Constraints.half_width")
    for n in ("corner_chamfer_2", "corner_chamfer_3", "corner_chamfer_4"):
        fp.drive(sk, n, f"{me}.Constraints.corner_chamfer")


def build(doc):
    bdy = fp.body(doc, "Body_Alignment_Plate")
    turned = dict(plane="XY_Plane", angle=45.0)

    # The outline at the top of the edge chamfer: up to the top, and down,
    # shrinking at 45 degrees, to the bottom.
    # Size, thickness and screw positions are the spreadsheet's, shared with
    # the pockets in the four body quarters; the plate sits in its pocket, so
    # its underside is at floor_t - plate_t.
    outline = fp.sketch(bdy, "Outline", offset=Z_BOTTOM + EDGE, **turned)
    outline.setExpression(".AttachmentOffset.Base.z",
                          f"{P('floor_t')} - {P('plate_t')} + {EDGE} mm")
    octagon(outline, DIAMOND - CLEARANCE, CORNER)
    fp.drive(outline, "half_width", f"{P('plate_diag')} / sqrt(2) - {CLEARANCE} mm")
    plate = fp.pad(bdy, "Plate", outline, THICKNESS - EDGE)
    plate.setExpression("Length", f"{P('plate_t')} - {EDGE} mm")
    edge = fp.pad(bdy, "Bottom edge chamfer", outline, EDGE, reversed_=True,
                  taper=-45.0)
    outline.Visibility = False

    holes = fp.sketch(bdy, "Holes", offset=Z_BOTTOM, **turned)
    u = DIAMOND - HOLE_IN
    fp.circle(holes, (u, HOLE_SPREAD), HOLE_D, name="hole")
    fp.drive(holes, "hole_u", f"{P('plate_diag')} / sqrt(2) - {P('plate_hole_in')}")
    fp.drive(holes, "hole_v", P("plate_hole_spread"))
    fp.circle(holes, (u, -HOLE_SPREAD), HOLE_D, name="hole_2")
    me = holes.Name
    fp.drive(holes, "hole_2_dia", f"{me}.Constraints.hole_dia")
    fp.drive(holes, "hole_2_u", f"{me}.Constraints.hole_u")
    fp.drive(holes, "hole_2_v", f"-{me}.Constraints.hole_v")
    pair = fp.pocket(bdy, "Holes", holes, None, midplane=True)
    fp.polar_pattern(bdy, "Holes round", [pair], 4)

    slots = fp.sketch(bdy, "Slots", offset=Z_BOTTOM)
    w, h = V("plate_slot_w"), V("plate_slot_h")
    for i, cell in enumerate(("plate_slot_y2", "plate_slot_y1")):
        name, y = f"slot{i + 1}", V(cell)
        fp.polyline(slots, [(-w / 2, y - h / 2), (w / 2, y - h / 2),
                            (w / 2, y + h / 2), (-w / 2, y + h / 2)],
                    name=name)
        fp.drive(slots, f"{name}_x0", f"-{P('plate_slot_w')} / 2")
        fp.drive(slots, f"{name}_x1", f"{P('plate_slot_w')} / 2")
        fp.drive(slots, f"{name}_y0", f"{P(cell)} - {P('plate_slot_h')} / 2")
        fp.drive(slots, f"{name}_y2", f"{P(cell)} + {P('plate_slot_h')} / 2")
    for n, label in ((2, "pin_a"), (3, "pin_b")):
        (x, ex), (y, ey) = quarter.board_hole(n)
        fp.circle(slots, (x, y), V("floor_hole_d"), name=label, keep_zero=True)
        fp.drive(slots, f"{label}_u", ex)
        fp.drive(slots, f"{label}_v", ey)
        fp.drive(slots, f"{label}_dia", P("floor_hole_d"))
    fp.pocket(bdy, "Slots and pin holes", slots, None, midplane=True)
    # Where the assemblies join it: the body's centre, which it is drawn about.
    fp.lcs(bdy, "CENTRE")
    # Where the bought parts go.  INSERT1 to 8: an insert in each screw hole,
    # flush with the underside, where the quarters' plate screws come up
    # through the floor, Z down.  BATTERY: on the top face, where the battery
    # stands with its back to the centre, Z up, X along -x.
    u = f"({P('plate_diag')} / sqrt(2) - {P('plate_hole_in')})"
    s = P("plate_hole_spread")
    uv = V("plate_diag") / math.sqrt(2) - V("plate_hole_in")
    a, b = (uv - V("plate_hole_spread")) / math.sqrt(2), (uv + V("plate_hole_spread")) / math.sqrt(2)
    ea, eb = f"({u} - {s}) / sqrt(2)", f"({u} + {s}) / sqrt(2)"
    bottom = f"{P('floor_t')} - {P('plate_t')}"
    n = 0
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        for (x, ex), (y, ey) in (((a, ea), (b, eb)), ((b, eb), (a, ea))):
            n += 1
            fp.lcs(bdy, f"INSERT{n}", at=(sx * x, sy * y, Z_BOTTOM), axis=(0, 0, -1),
                   expressions={"Placement.Base.x": ex if sx > 0 else f"-({ex})",
                                "Placement.Base.y": ey if sy > 0 else f"-({ey})",
                                "Placement.Base.z": bottom})
    axis, roll = fp.frame((-1, 0, 0), (0, 0, 1))
    fp.lcs(bdy, "BATTERY", at=(V("battery_x"), V("battery_y"), Z_BOTTOM + THICKNESS),
           axis=axis, roll=roll,
           expressions={"Placement.Base.x": P("battery_x"), "Placement.Base.y": P("battery_y"),
                        "Placement.Base.z": P("floor_t")})
    return bdy


def test(doc, bdy):
    get = lambda label: doc.getObjectsByLabel(label)[0]
    return fctest.flex(doc, bdy, [
        (get("Outline"), "corner_chamfer", 8.0),
        ("sheet", "plate_hole_spread", "=20 mm"),
        ("sheet", "plate_diag", "=66 mm"),
        (get("Holes"), "hole_dia", 3.5),
        ("sheet", "baseplate_x", "=52 mm"),
        ("sheet", "baseplate_y", "=-63 mm"),
        ("sheet", "plate_slot_y1", "=20 mm"),
    ])


fp.make(__file__, "Body_Alignment_Plate", build, test=test)
