"""Ellipsoidal Roller: the 36 rollers round the four wheels.

One revolve of one fully constrained profile.  The roller axis runs along X
at `roller_axis_r` above the origin, and the origin is where the wheel axis
passes, so the ellipse that makes the profile is centred on it.

- The running surface, from one end chamfer to the other, follows the section
  of the wheel's envelope cylinder, radius `envelope_r`, by the plane through
  the roller axis at `roller_angle` to the wheel axis: an ellipse with
  semi-axes envelope_r / sin(angle) and envelope_r, centred on the wheel axis.
  This is the classic mecanum profile.
- The outer end edge carries a 0.2 mm chamfer, equal along both faces.
- A bearing seat at each end, Ø`seat_d` x `seat_depth`, 0.2 mm lead-in, and
  the bore between them.
"""

import math

import fcprim as fp
import fctest

fp.open_parameters()
P, V = fp.param, fp.sheet_value

BORE_D = 4.5          # bore between the bearing seats
CHAMFER = 0.2         # bearing seat lead-in, and the outer end edge

V_AXIS, ROOT_PT = -2, (-1, 1)


def ellipse_point(a, b, u):
    return (a * math.cos(u), b * math.sin(u))


def profile(sk):
    zc = V("roller_axis_r")
    R = V("envelope_r")
    a = R / math.sin(math.radians(V("roller_angle")))
    half = V("roller_len") / 2.0
    seat_r = V("seat_d") / 2.0
    seat_x = half - V("seat_depth")
    bore_r = BORE_D / 2.0

    # Where the points start; the constraints below decide where they end.
    u_c = math.acos(half / a)                       # sharp outer corner
    corner = ellipse_point(a, R, u_c)
    lo, hi = u_c, u_c + 0.1                         # chamfer end on the ellipse
    for _ in range(60):
        mid = (lo + hi) / 2
        p = ellipse_point(a, R, mid)
        if math.hypot(p[0] - corner[0], p[1] - corner[1]) < CHAMFER:
            lo = mid
        else:
            hi = mid
    u6 = lo
    A1, A2 = (seat_x, zc + bore_r), (seat_x, zc + seat_r)
    A3, A4 = (half - CHAMFER, zc + seat_r), (half, zc + seat_r + CHAMFER)
    A5 = (half, corner[1] - CHAMFER)
    A6 = ellipse_point(a, R, u6)
    mirror = lambda p: (-p[0], p[1])
    B1, B2, B3, B4, B5, B6 = map(mirror, (A1, A2, A3, A4, A5, A6))

    # The roller axis comes first, so that it is construction line Axis0,
    # which the revolve turns about.
    axis = fp.line(sk, (0.0, zc), (half, zc), construction=True)
    L1, L2, L3 = fp.line(sk, A1, A2), fp.line(sk, A2, A3), fp.line(sk, A3, A4)
    L4, L5 = fp.line(sk, A4, A5), fp.line(sk, A5, A6)
    E1, E1maj, E1min = fp.ellipse_arc(sk, (0, 0), a, R, u6, math.pi - u6)
    L6, L7, L8 = fp.line(sk, B6, B5), fp.line(sk, B5, B4), fp.line(sk, B4, B3)
    L9, L10, L11 = fp.line(sk, B3, B2), fp.line(sk, B2, B1), fp.line(sk, B1, A1)
    CR, CL = fp.point(sk, corner), fp.point(sk, mirror(corner))

    c = lambda *args, name=None: fp.con(sk, *args, name=name)
    loop = [L1, L2, L3, L4, L5, E1, L6, L7, L8, L9, L10, L11]
    for one, two in zip(loop, loop[1:] + loop[:1]):
        c("Coincident", one, 2, two, 1)

    # The roller axis, at roller_axis_r from the wheel axis.
    c("PointOnObject", axis, 1, V_AXIS)
    c("Horizontal", axis)
    c("DistanceY", *ROOT_PT, axis, 1, zc, name="roller_axis_r")
    c("PointOnObject", axis, 2, L4)

    # The envelope ellipse, centred on the wheel axis: the whole running
    # surface lies on it, from one end chamfer to the other.
    c("Coincident", E1, 3, *ROOT_PT)
    c("Horizontal", E1maj)
    c("Distance", E1maj, 2 * a, name="envelope_major_axis")
    c("Distance", E1min, 2 * R, name="envelope_minor_axis")

    # Right-hand end: bearing seat, end face, chamfers.
    c("Vertical", L1)
    c("Horizontal", L2)
    c("Vertical", L4)
    c("DistanceX", L1, 1, L4, 1, half - seat_x, name="seat_depth")
    c("DistanceY", axis, 1, L1, 1, bore_r, name="bore_r")
    c("DistanceY", axis, 1, L2, 1, seat_r, name="seat_r")
    c("DistanceX", L3, 1, L3, 2, CHAMFER, name="seat_chamfer")
    c("DistanceY", L3, 1, L3, 2, CHAMFER, name="seat_chamfer_v")
    c("DistanceX", L7, 2, L4, 1, 2 * half, name="roller_len")
    c("PointOnObject", CR, 1, E1)
    c("PointOnObject", CR, 1, L4)
    c("Distance", CR, 1, L5, 1, CHAMFER, name="edge_chamfer")
    c("Distance", CR, 1, L5, 2, CHAMFER, name="edge_chamfer_2")

    # Left-hand end: the mirror image about the roller's middle.
    c("Symmetric", L1, 1, L10, 2, V_AXIS)
    c("Symmetric", L1, 2, L10, 1, V_AXIS)
    c("Symmetric", L2, 2, L9, 1, V_AXIS)
    c("Symmetric", L3, 2, L8, 1, V_AXIS)
    c("Symmetric", L4, 2, L7, 1, V_AXIS)
    c("Symmetric", CR, 1, CL, 1, V_AXIS)
    c("Distance", CL, 1, L6, 1, CHAMFER, name="edge_chamfer_3")

    # Dimensions shared with other parts come from the spreadsheet; the
    # chamfers' second legs follow their first.
    me = sk.Name
    fp.drive(sk, "roller_axis_r", P("roller_axis_r"))
    fp.drive(sk, "envelope_major_axis",
             f"2 * {P('envelope_r')} / sin({P('roller_angle')})")
    fp.drive(sk, "envelope_minor_axis", f"2 * {P('envelope_r')}")
    fp.drive(sk, "seat_depth", P("seat_depth"))
    fp.drive(sk, "seat_r", f"{P('seat_d')} / 2")
    fp.drive(sk, "roller_len", P("roller_len"))
    fp.drive(sk, "seat_chamfer_v", f"{me}.Constraints.seat_chamfer")
    fp.drive(sk, "edge_chamfer_2", f"{me}.Constraints.edge_chamfer")
    fp.drive(sk, "edge_chamfer_3", f"{me}.Constraints.edge_chamfer")
    return sk


def build(doc):
    bdy = fp.body(doc, "Ellipsoidal_Roller")
    sk = fp.sketch(bdy, "Roller profile", "XZ_Plane")
    profile(sk)
    fp.revolution(bdy, "Roller", sk, axis="Axis0")
    # Where the assemblies join it: the middle of its axis, Z along the axis.
    axis, roll = fp.frame((0, 0, 1), (1, 0, 0))
    fp.lcs(bdy, "AXIS", at=(0, 0, V("roller_axis_r")), axis=axis, roll=roll,
           expressions={"Placement.Base.z": P("roller_axis_r")})
    return bdy


def test(doc, bdy):
    sk = doc.getObjectsByLabel("Roller profile")[0]
    return fctest.flex(doc, bdy, [
        (sk, "bore_r", 2.0),
        (sk, "edge_chamfer", 0.4),
        ("sheet", "roller_angle", "=46 deg"),
        ("sheet", "roller_r", "=7 mm"),
        ("sheet", "seat_d", "=7 mm"),
    ])


fp.make(__file__, "Ellipsoidal_Roller", build, test=test, made_of="tpu")
