"""Nema_17_Mount: the hub that joins a stepper shaft to its wheel, 4 of them.

The shaft axis runs along +Y.

- A Ø28 flange from y = 18 to 20 with four Ø3.2 holes on a Ø20 circle at
  45 degrees, and a 0.5 mm marker notch in its rim at the top.
- A Ø12 hub on the flange up to y = 27, with a boss on top for the radial
  screw: flat topped at z = 10, its sides rising from where they meet the
  hub's circle at z = 5 (which is what makes it 2 x sqrt(11) wide).
- A Ø5.2 D-bore for the 5 mm shaft, the flat 2.1 above the axis, through.

The bolt circle and the D-bore are the spreadsheet's (`hub_screw_circle_d`,
`shaft_bore_d`, `shaft_flat`), because the motor side has the same: its
inserts take these screws and its bore the same shaft.
- A Ø4.1 radial hole from the boss top down to the shaft axis, for a heat-set
  insert and the screw that clamps the hub on the shaft's flat.
"""

import math
import os

import fcprim as fp
import fctest

fp.open_parameters()
P, V = fp.param, fp.sheet_value

FLANGE_D, FLANGE_T, FLANGE_TOP = 28.0, 2.0, 20.0
HUB_D, HUB_LEN = 12.0, 7.0
BOSS_BASE, BOSS_TOP = 5.0, 10.0
BOLT_D = 3.2
SCREW_D, SCREW_Y, SCREW_DEPTH = 4.1, 23.35, 10.0
NOTCH_W, NOTCH_DEPTH = 0.5, 1.0
V_AXIS, ROOT_PT = -2, (-1, 1)


def hub_profile(sk):
    """The hub's circle with the boss on top, as one closed outline."""
    r = HUB_D / 2
    x = math.sqrt(r * r - BOSS_BASE ** 2)
    a0 = math.atan2(BOSS_BASE, -x)                  # left corner, ~140 deg
    a1 = math.atan2(BOSS_BASE, x) + 2 * math.pi     # right corner, the long way
    arc = sk.addGeometry(fp.Part.ArcOfCircle(fp.Part.Circle(
        fp.Vector(0, 0, 0), fp.Vector(0, 0, 1), r), a0, a1), False)
    right = fp.line(sk, (x, BOSS_BASE), (x, BOSS_TOP))
    top = fp.line(sk, (x, BOSS_TOP), (-x, BOSS_TOP))
    left = fp.line(sk, (-x, BOSS_TOP), (-x, BOSS_BASE))
    c = lambda *args, name=None: fp.con(sk, *args, name=name)
    c("Coincident", arc, 2, right, 1)
    c("Coincident", right, 2, top, 1)
    c("Coincident", top, 2, left, 1)
    c("Coincident", left, 2, arc, 1)
    c("Coincident", arc, 3, *ROOT_PT)
    c("Diameter", arc, HUB_D, name="hub_d")
    c("Vertical", right)
    c("Vertical", left)
    c("Horizontal", top)
    c("DistanceY", *ROOT_PT, top, 1, BOSS_TOP, name="boss_top")
    c("Horizontal", arc, 1, arc, 2)
    c("DistanceY", *ROOT_PT, arc, 2, BOSS_BASE, name="boss_base")


def bore_profile(sk):
    """A circle with a flat across its top: the D of the motor shaft."""
    bore_d, flat_z = V("shaft_bore_d"), V("shaft_flat")
    r = bore_d / 2
    x = math.sqrt(r * r - flat_z ** 2)
    a0 = math.atan2(flat_z, -x)
    a1 = math.atan2(flat_z, x) + 2 * math.pi
    arc = sk.addGeometry(fp.Part.ArcOfCircle(fp.Part.Circle(
        fp.Vector(0, 0, 0), fp.Vector(0, 0, 1), r), a0, a1), False)
    flat = fp.line(sk, (x, flat_z), (-x, flat_z))
    c = lambda *args, name=None: fp.con(sk, *args, name=name)
    c("Coincident", arc, 2, flat, 1)
    c("Coincident", flat, 2, arc, 1)
    c("Coincident", arc, 3, *ROOT_PT)
    c("Diameter", arc, bore_d, name="bore_d")
    c("Horizontal", flat)
    c("DistanceY", *ROOT_PT, flat, 1, flat_z, name="flat_z")
    fp.drive(sk, "bore_d", P("shaft_bore_d"))
    fp.drive(sk, "flat_z", P("shaft_flat"))


def build(doc):
    bdy = fp.body(doc, "Nema_17_Mount")
    # On XZ a sketch's offset runs to -Y and a pad goes to -Y.
    at_flange_top = dict(plane="XZ_Plane", offset=-FLANGE_TOP)

    flange = fp.sketch(bdy, "Flange", **at_flange_top)
    fp.circle(flange, (0, 0), FLANGE_D, name="flange")
    fp.pad(bdy, "Flange", flange, FLANGE_T)

    hub = fp.sketch(bdy, "Hub", **at_flange_top)
    hub_profile(hub)
    hub_pad = fp.pad(bdy, "Hub", hub, HUB_LEN, reversed_=True)

    bore = fp.sketch(bdy, "Shaft bore", **at_flange_top)
    bore_profile(bore)
    fp.pocket(bdy, "Shaft bore", bore, None, midplane=True)

    holes = fp.sketch(bdy, "Bolt holes", **at_flange_top)
    fp.bolt_circle(holes, (0, 0), V("hub_screw_circle_d") / 2, BOLT_D, 4, angle=45.0,
                   name="bolt")
    for xy in ("bolt_u", "bolt_v"):
        fp.drive(holes, xy, f"{P('hub_screw_circle_d')} / 2 * cos(45 deg)")
    fp.pocket(bdy, "Bolt holes", holes, None, midplane=True)

    notch = fp.sketch(bdy, "Marker notch", **at_flange_top)
    top = FLANGE_D / 2
    fp.polyline(notch, [(-NOTCH_W / 2, top - NOTCH_DEPTH), (NOTCH_W / 2, top - NOTCH_DEPTH),
                        (NOTCH_W / 2, top + 1), (-NOTCH_W / 2, top + 1)], name="notch")
    names = [c.Name for c in notch.Constraints]
    for old, new in (("notch_x0", "notch_left"), ("notch_x1", "notch_right"),
                     ("notch_y0", "notch_bottom"), ("notch_y2", "notch_clear")):
        notch.renameConstraint(names.index(old), new)
    fp.pocket(bdy, "Marker notch", notch, None, midplane=True)

    # The radial hole, from the boss top down: on XY a pocket cuts to -Z.
    # It starts at the boss top and reaches the shaft axis, whatever the boss.
    screw = fp.sketch(bdy, "Radial hole", "XY_Plane", offset=BOSS_TOP)
    top = f"{hub.Name}.Constraints.boss_top"
    screw.setExpression(".AttachmentOffset.Base.z", top)
    fp.circle(screw, (0, SCREW_Y), SCREW_D, name="screw")
    fp.pocket(bdy, "Radial hole", screw, SCREW_DEPTH).setExpression("Length", top)
    # Where the assemblies join it: the flange face that sits on the motor
    # side, Z pointing into the wheel, X along the part's X so that the
    # flange holes line up with the motor side's inserts.
    axis, roll = fp.frame((1, 0, 0), (0, -1, 0))
    fp.lcs(bdy, "FLANGE", at=(0, FLANGE_TOP - FLANGE_T, 0), axis=axis, roll=roll)
    # Where the bought parts go, Z out of the material.  FLANGE_SCREW1 to 4:
    # the heads of the screws through the flange, on its face away from the
    # wheel.  RADIAL_INSERT: the insert in the radial hole, at the boss top.
    # CLAMP: where the clamp screw's tip stops, on the bore's flat.
    rc, rce = V("hub_screw_circle_d") / 2, f"{P('hub_screw_circle_d')} / 2 * cos(45 deg)"
    c45 = math.cos(math.radians(45.0))
    for k, (sx, sz) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1)), start=1):
        fp.lcs(bdy, f"FLANGE_SCREW{k}", at=(sx * rc * c45, FLANGE_TOP, sz * rc * c45),
               axis=(0, 1, 0), expressions={
                   "Placement.Base.x": rce if sx > 0 else f"-{rce}",
                   "Placement.Base.z": rce if sz > 0 else f"-{rce}"})
    fp.lcs(bdy, "RADIAL_INSERT", at=(0, SCREW_Y, BOSS_TOP),
           expressions={"Placement.Base.z": top})
    fp.lcs(bdy, "CLAMP", at=(0, SCREW_Y, V("shaft_flat")),
           expressions={"Placement.Base.z": P("shaft_flat")})
    return bdy


def test(doc, bdy):
    get = lambda label: doc.getObjectsByLabel(label)[0]
    return fctest.flex(doc, bdy, [
        (get("Hub"), "boss_top", 11.0),
        (get("Hub"), "hub_d", 13.0),
        ("sheet", "shaft_flat", "=2 mm"),
        ("sheet", "hub_screw_circle_d", "=22 mm"),
        (get("Bolt holes"), "bolt_dia", 3.5),
    ])


fp.make(__file__, "Nema_17_Mount", build, test=test)
