"""Battery: an envelope of the 2200 mAh pack, a bought part.

Drawn as an interface model: a block 108 long (X), 35 wide (Y) and 25 thick
(Z, from z = 0), one end rounded R10 top and bottom, and at that end the
block the leads leave from, 5 proud on the side of +Y.  No leads.
"""

import fcprim as fp
import fctest

LENGTH, WIDTH, THICK, END_R = 108.0, 35.0, 25.0, 10.0
LEAD_X, LEAD_H, LEAD_OUT = 6.0, 10.0, 5.0


def build(doc):
    bdy = fp.body(doc, "Battery_2200mAh")
    fp.designation(bdy, f"Battery pack 2200 mAh, {LENGTH:g} x {WIDTH:g} x {THICK:g} mm")
    half = LENGTH / 2
    # Side view in XZ, padded across Y symmetrically; the rounded end at -X.
    sk = fp.sketch(bdy, "Side outline", "XZ_Plane")
    fp.polyline(sk, [(-half, 0), (half, 0), (half, THICK), (-half, THICK)],
                name="side", fillets={0: END_R, 3: END_R})
    fp.drive(sk, "side_r3", f"{sk.Name}.Constraints.side_r0")
    fp.pad(bdy, "Pack", sk, WIDTH, midplane=True)

    # The lead block, on the face at y = +WIDTH / 2.  On XZ a pad runs
    # towards -Y, so the sketch sits at that face and the pad is reversed.
    sk = fp.sketch(bdy, "Lead block outline", "XZ_Plane", offset=-WIDTH / 2)
    fp.polyline(sk, [(-half + 0.4, (THICK - LEAD_H) / 2), (-half + LEAD_X, (THICK - LEAD_H) / 2),
                     (-half + LEAD_X, (THICK + LEAD_H) / 2), (-half + 0.4, (THICK + LEAD_H) / 2)],
                name="lead")
    fp.pad(bdy, "Lead block", sk, LEAD_OUT, reversed_=True)

    # Where it is placed: the middle of the edge where the face it stands on
    # (y = -WIDTH / 2) meets z = 0, Z into the pack, X along it.
    axis, roll = fp.frame((1, 0, 0), (0, 1, 0))
    fp.lcs(bdy, "BASE", at=(0, -WIDTH / 2, 0), axis=axis, roll=roll)
    return bdy


def test(doc, bdy):
    sk = doc.getObjectsByLabel("Side outline")[0]
    pack = doc.getObjectsByLabel("Pack")[0]
    first = fctest.flex(doc, bdy, [(sk, "side_r0", 8.0)])
    return first + fctest.flex(doc, bdy, [(pack, "Length", 34.0)])


fp.make(__file__, "Battery_2200mAh", build, test=test, made_of="battery")
