"""M3 x 5 hex spacer, female both ends: the controller board stands on four.

A bought part, drawn as an interface model: a hexagon 5 mm across the flats,
5 long, with an M3 tapping bore through (Ø2.5).  It stands on z = 0.
"""

import fcprim as fp
import fctest

ACROSS_FLATS, LENGTH, BORE_D = 5.0, 5.0, 2.5


def build(doc):
    bdy = fp.body(doc, "Spacer_M3x5")
    fp.designation(bdy, f"Hex spacer M3 x {LENGTH:g}, female/female, {ACROSS_FLATS:g} mm across flats")
    sk = fp.sketch(bdy, "Hexagon", "XY_Plane")
    fp.polygon(sk, (0, 0), ACROSS_FLATS, sides=6, name="hex")
    fp.circle(sk, (0, 0), BORE_D, name="bore")
    fp.pad(bdy, "Spacer", sk, LENGTH)
    # Its two ends, Z up the spacer: it stands on BOTTOM, the board on TOP.
    fp.lcs(bdy, "BOTTOM")
    fp.lcs(bdy, "TOP", at=(0, 0, LENGTH),
           expressions={"Placement.Base.z": "Spacer.Length"})
    return bdy


def test(doc, bdy):
    sk = doc.getObjectsByLabel("Hexagon")[0]
    pad = doc.getObjectsByLabel("Spacer")[0]
    first = fctest.flex(doc, bdy, [(sk, "bore_dia", 3.2)])
    return first + fctest.flex(doc, bdy, [(pad, "Length", 6.0)])


fp.make(__file__, "Spacer_M3x5", build, test=test, made_of="brass")
