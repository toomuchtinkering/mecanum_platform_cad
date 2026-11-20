"""Washer: the spacer on each pin end between roller and wheel side, 72 of them.

A ring along -Y from the origin, every edge broken by a small 45 degree
chamfer.  One revolve of one profile.
"""

import os

import fcprim as fp
import fctest

INNER_D, OUTER_D, THICKNESS, CHAMFER = 3.2, 4.6, 1.4, 0.05
H_AXIS, ROOT_PT = -1, (-1, 1)


def profile(sk):
    """Half section in the XY plane: X is the radius, the ring runs to -Y."""
    ri, ro, t, ch = INNER_D / 2, OUTER_D / 2, THICKNESS, CHAMFER
    pts = [(ri + ch, 0), (ro - ch, 0), (ro, -ch), (ro, ch - t),
           (ro - ch, -t), (ri + ch, -t), (ri, ch - t), (ri, -ch)]
    L = [fp.line(sk, pts[i], pts[(i + 1) % 8]) for i in range(8)]
    c = lambda *args, name=None: fp.con(sk, *args, name=name)
    for i in range(8):
        c("Coincident", L[i], 2, L[(i + 1) % 8], 1)
    c("Horizontal", L[0])
    c("Horizontal", L[4])
    c("Vertical", L[2])
    c("Vertical", L[6])
    c("PointOnObject", L[0], 1, H_AXIS)
    c("DistanceY", L[4], 2, L[0], 1, t, name="thickness")
    c("DistanceX", *ROOT_PT, L[2], 1, ro, name="outer_r")
    c("DistanceX", *ROOT_PT, L[6], 1, ri, name="inner_r")
    # Each chamfer by its two legs; the first leg drives all the others.
    c("DistanceX", L[1], 1, L[1], 2, ch, name="chamfer")
    legs = [("DistanceY", L[1], 2, L[1], 1), ("DistanceX", L[3], 2, L[3], 1),
            ("DistanceY", L[3], 2, L[3], 1), ("DistanceX", L[5], 2, L[5], 1),
            ("DistanceY", L[5], 1, L[5], 2), ("DistanceX", L[7], 1, L[7], 2),
            ("DistanceY", L[7], 1, L[7], 2)]
    for n, leg in enumerate(legs, start=2):
        c(*leg, ch, name=f"chamfer_{n}")
        fp.drive(sk, f"chamfer_{n}", f"{sk.Name}.Constraints.chamfer")


def build(doc):
    bdy = fp.body(doc, "Washer")
    sk = fp.sketch(bdy, "Washer profile", "XY_Plane")
    profile(sk)
    fp.revolution(bdy, "Washer", sk, axis="V_Axis")
    # Where the assemblies join it: the face at y = 0, Z pointing away from
    # the ring, which is the face that sits on a wheel side.
    axis, roll = fp.frame((1, 0, 0), (0, 1, 0))
    fp.lcs(bdy, "FACE", axis=axis, roll=roll)
    return bdy


def test(doc, bdy):
    sk = doc.getObjectsByLabel("Washer profile")[0]
    return fctest.flex(doc, bdy, [(sk, "thickness", 2.0), (sk, "chamfer", 0.2),
                             (sk, "inner_r", 1.5)])


fp.make(__file__, "Washer", build, test=test)
