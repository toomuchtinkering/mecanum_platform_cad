"""NEMA 17 stepper motor: an envelope of the four drive motors, a bought part.

Drawn from the standard's dimensions, as an interface model: the outline,
the centring boss, the shaft with its flat, the four tapped holes and the
connector, nothing inside.  The mounting face lies on z = 0 and the shaft
runs along +Z.

- A 42.3 mm square body, 40 long, its corners chamfered 4 mm.
- A Ø22 x 2 centring boss, which fits the body's Ø`nema_boss_d` hole.
- A Ø5 shaft 24 mm out from the face, with a flat 0.5 deep along its last
  15 mm, on the side of +Y.
- Four M3 holes, Ø2.65 x 4.5 deep, on a square of `nema_pitch`.
- The connector, 15 wide and 8 proud, at the back end on the side of -Y.
"""

import fcprim as fp
import fctest

fp.open_parameters()
P, V = fp.param, fp.sheet_value

SIDE, LENGTH, CORNER = 42.3, 40.0, 4.0
BOSS_D, BOSS_H = 22.0, 2.0
SHAFT_D, SHAFT_OUT, FLAT_DEPTH, FLAT_LEN = 5.0, 24.0, 0.5, 15.0
TAP_D, TAP_DEPTH = 2.65, 4.5
PLUG_W, PLUG_LEN, PLUG_OUT = 15.0, 10.0, 8.0


def build(doc):
    bdy = fp.body(doc, "NEMA17_Stepper")
    fp.designation(bdy, f"NEMA 17 stepper motor, {SIDE:g} mm square, {LENGTH:g} mm long, "
                        f"Ø{SHAFT_D:g} mm shaft with flat")
    h, c = SIDE / 2, CORNER
    sk = fp.sketch(bdy, "Body outline", "XY_Plane")
    fp.polyline(sk, [(h - c, -h), (h, c - h), (h, h - c), (h - c, h),
                     (c - h, h), (-h, h - c), (-h, c - h), (c - h, -h)], name="body")
    fp.pad(bdy, "Body", sk, LENGTH, reversed_=True)

    sk = fp.sketch(bdy, "Boss circle", "XY_Plane")
    fp.circle(sk, (0, 0), BOSS_D, name="boss")
    fp.pad(bdy, "Boss", sk, BOSS_H)

    sk = fp.sketch(bdy, "Shaft circle", "XY_Plane", offset=BOSS_H)
    fp.circle(sk, (0, 0), SHAFT_D, name="shaft")
    fp.pad(bdy, "Shaft", sk, SHAFT_OUT - BOSS_H)

    # The flat: what lies beyond it, cut down from the shaft's end.
    r = SHAFT_D / 2
    sk = fp.sketch(bdy, "Flat outline", "XY_Plane", offset=SHAFT_OUT)
    fp.polyline(sk, [(-r - 1, r - FLAT_DEPTH), (r + 1, r - FLAT_DEPTH),
                     (r + 1, r + 1), (-r - 1, r + 1)], name="flat")
    fp.pocket(bdy, "Shaft flat", sk, FLAT_LEN)

    sk = fp.sketch(bdy, "Tapped hole circle", "XY_Plane")
    pitch = V("nema_pitch")
    fp.bolt_circle(sk, (0, 0), pitch / 2 * 2 ** 0.5, TAP_D, 4, angle=45.0, name="tap")
    for xy in ("tap_u", "tap_v"):
        fp.drive(sk, xy, f"{P('nema_pitch')} / 2")
    fp.pocket(bdy, "Tapped holes", sk, TAP_DEPTH)

    sk = fp.sketch(bdy, "Connector outline", "XY_Plane", offset=-LENGTH)
    fp.polyline(sk, [(-PLUG_W / 2, -h - PLUG_OUT), (PLUG_W / 2, -h - PLUG_OUT),
                     (PLUG_W / 2, -h), (-PLUG_W / 2, -h)], name="plug")
    fp.pad(bdy, "Connector", sk, PLUG_LEN)

    # Where the body takes it: the mounting face, Z along the shaft.
    fp.lcs(bdy, "FACE")
    return bdy


def test(doc, bdy):
    first = fctest.flex(doc, bdy, [
        (doc.getObjectsByLabel("Boss circle")[0], "boss_dia", 22.5),
        (doc.getObjectsByLabel("Shaft circle")[0], "shaft_dia", 6.35),
        ("sheet", "nema_pitch", "=31.5 mm")])
    return first + fctest.flex(doc, bdy, [(doc.getObjectsByLabel("Body")[0], "Length", 48.0)])


fp.make(__file__, "NEMA17_Stepper", build, test=test, made_of="motor")
