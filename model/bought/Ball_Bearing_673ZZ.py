"""Ball bearing 673ZZ, 3 x 6 x 2.5: an envelope, two in every roller.

A bought part, drawn as an interface model: the rings and the two shields,
set back 0.2 mm between the rings, as one revolve about Z.  The face that
rests on the pin's shoulder lies on z = 0.
"""

import fcprim as fp
import fctest

BORE_D, OUTER_D, WIDTH = 3.0, 6.0, 2.5
SHIELD_IN_D, SHIELD_OUT_D, SHIELD_SET = 3.6, 5.4, 0.2


def build(doc):
    bdy = fp.body(doc, "Ball_Bearing_673ZZ")
    fp.designation(bdy, f"Ball bearing 673ZZ, {BORE_D:g} x {OUTER_D:g} x {WIDTH:g} mm")
    ri, ro, w = BORE_D / 2, OUTER_D / 2, WIDTH
    si, so, s = SHIELD_IN_D / 2, SHIELD_OUT_D / 2, SHIELD_SET
    sk = fp.sketch(bdy, "Section", "XZ_Plane")
    fp.polyline(sk, [(ri, 0), (si, 0), (si, s), (so, s), (so, 0), (ro, 0),
                     (ro, w), (so, w), (so, w - s), (si, w - s), (si, w), (ri, w)],
                name="ring")
    fp.revolution(bdy, "Bearing", sk, axis="V_Axis")
    # Where it sits: the face on the pin's shoulder, Z through the bearing.
    fp.lcs(bdy, "INNER")
    return bdy


def test(doc, bdy):
    sk = doc.getObjectsByLabel("Section")[0]
    return fctest.flex(doc, bdy, [(sk, "ring_x5", 3.5), (sk, "ring_y6", 3.0)])


fp.make(__file__, "Ball_Bearing_673ZZ", build, test=test, made_of="steel")
