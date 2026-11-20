"""Pin_For_Ball_Bearing: the axle each roller turns on, 36 of them.

A turned pin along -Y from the origin: a Ø`pin_d` middle between two
shoulders, a Ø`pin_end_d` journal of `pin_end_len` at each end that carries a
bearing and goes on into the wheel side, a small 45 degree break at each tip.
A flat along the whole length at `pin_end_d`/2 below the axis, tangent to the
journals, lets it print lying down.
Datums CLAW_A, CLAW_B, MIDDLE and the two shoulders are where the assemblies
join it.
"""

import os

import fcprim as fp
import fctest

fp.open_parameters()
P, V = fp.param, fp.sheet_value

TIP_CHAMFER = 0.1
V_AXIS, ROOT_PT = -2, (-1, 1)


def profile(sk):
    """Half section in the XY plane: X is the radius, the pin runs to -Y."""
    length, end_len = V("pin_len"), V("pin_end_len")
    r_end, r_mid, ch = V("pin_end_d") / 2, V("pin_d") / 2, TIP_CHAMFER
    pts = [(0, 0), (r_end - ch, 0), (r_end, -ch), (r_end, -end_len),
           (r_mid, -end_len), (r_mid, end_len - length), (r_end, end_len - length),
           (r_end, ch - length), (r_end - ch, -length), (0, -length)]
    L = [fp.line(sk, pts[i], pts[(i + 1) % 10]) for i in range(10)]
    c = lambda *args, name=None: fp.con(sk, *args, name=name)
    for i in range(10):
        c("Coincident", L[i], 2, L[(i + 1) % 10], 1)
    c("Coincident", L[0], 1, *ROOT_PT)
    c("PointOnObject", L[9], 1, V_AXIS)
    for i in (0, 3, 5, 8):
        c("Horizontal", L[i])
    for i in (2, 4, 6):
        c("Vertical", L[i])
    c("DistanceX", L[1], 1, L[1], 2, ch, name="tip_chamfer")
    c("DistanceY", L[1], 2, L[1], 1, ch, name="tip_chamfer_v")
    c("DistanceX", L[7], 2, L[7], 1, ch, name="tip_chamfer_2")
    c("DistanceY", L[7], 2, L[7], 1, ch, name="tip_chamfer_2v")
    c("DistanceX", *ROOT_PT, L[2], 1, r_end, name="end_r")
    c("DistanceX", *ROOT_PT, L[6], 1, r_end, name="end_r_2")
    c("DistanceX", *ROOT_PT, L[4], 1, r_mid, name="pin_r")
    c("DistanceY", L[3], 1, L[0], 1, end_len, name="end_len")
    c("DistanceY", L[9], 1, L[6], 1, end_len, name="end_len_2")
    c("DistanceY", L[9], 1, L[0], 1, length, name="pin_len")
    me = sk.Name
    for name in ("tip_chamfer_v", "tip_chamfer_2", "tip_chamfer_2v"):
        fp.drive(sk, name, f"{me}.Constraints.tip_chamfer")
    fp.drive(sk, "end_r", f"{P('pin_end_d')} / 2")
    fp.drive(sk, "end_r_2", f"{P('pin_end_d')} / 2")
    fp.drive(sk, "pin_r", f"{P('pin_d')} / 2")
    fp.drive(sk, "end_len", P("pin_end_len"))
    fp.drive(sk, "end_len_2", P("pin_end_len"))
    fp.drive(sk, "pin_len", P("pin_len"))


def build(doc):
    bdy = fp.body(doc, "Pin_For_Ball_Bearing")
    sk = fp.sketch(bdy, "Pin profile", "XY_Plane")
    profile(sk)
    fp.revolution(bdy, "Pin", sk, axis="V_Axis")
    # The flat: everything below the journals' underside, through the length.
    flat = fp.sketch(bdy, "Flat", "XZ_Plane")
    r_end = V("pin_end_d") / 2
    fp.polyline(flat, [(-3, -r_end), (3, -r_end), (3, -3), (-3, -3)], name="flat")
    names = [c.Name for c in flat.Constraints]
    flat.renameConstraint(names.index("flat_y0"), "flat_z")
    fp.drive(flat, "flat_z", f"-{P('pin_end_d')} / 2")
    fp.pocket(bdy, "Flat", flat, None, midplane=True)
    datums(bdy)
    return bdy


def datums(bdy):
    """Where the assemblies join the pin.

    CLAW_A and CLAW_B are where the pin passes a wheel side's washer face,
    `washer_offset` either side of its middle, with Z down the hole that end
    sits in; MIDDLE is where the roller turns.  SHOULDER_A and SHOULDER_B are
    the shoulders at the ends of the middle, Z out along the journal, where a
    bearing's inner face rests.  X is the flat's outward normal on all of
    them, so the claw a pin goes into decides which way its flat faces.
    """
    half, wo = V("pin_len") / 2, V("washer_offset")
    axis_x = (0, 0, -1)                      # the flat is on -Z
    for label, y, z, expr in (
            ("CLAW_A", -half + wo, 1, f"-{P('pin_len')} / 2 + {P('washer_offset')}"),
            ("CLAW_B", -half - wo, -1, f"-{P('pin_len')} / 2 - {P('washer_offset')}"),
            ("MIDDLE", -half, -1, f"-{P('pin_len')} / 2"),
            ("SHOULDER_A", -V("pin_end_len"), 1, f"-{P('pin_end_len')}"),
            ("SHOULDER_B", -2 * half + V("pin_end_len"), -1,
             f"-{P('pin_len')} + {P('pin_end_len')}")):
        axis, roll = fp.frame(axis_x, (0, z, 0))
        fp.lcs(bdy, label, at=(0, y, 0), axis=axis, roll=roll,
               expressions={"Placement.Base.y": expr})


def test(doc, bdy):
    sk = doc.getObjectsByLabel("Pin profile")[0]
    return fctest.flex(doc, bdy, [
        (sk, "tip_chamfer", 0.3),
        ("sheet", "pin_d", "=3.5 mm"),
        ("sheet", "pin_end_d", "=2.7 mm"),
    ])


fp.make(__file__, "Pin_For_Ball_Bearing", build, test=test)
