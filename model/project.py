"""This project's settings: what the build's helpers in code/lib build with.

The helpers know how to build a FreeCAD model from scripts; what is particular
to this model lives here: the licence its documents carry, and what its parts
are made of and the colour each shows in.  Plain Python without FreeCAD, so
that the build driver can read it too.
"""

# The licence every document carries in its `License` and `LicenseURL`.  The
# author fields (`CreatedBy`, `LastModifiedBy`, `Company`) are left to whoever
# builds or edits a document, as their FreeCAD preferences fill them.
LICENSE = "CERN-OHL-P-2.0"
LICENSE_URL = "https://ohwr.org/cern_ohl_p_v2.txt"

# What a part can be made of: the FreeCAD material card it gets, the colour it
# shows in (sRGB, 0 to 255), whether it is printed, which puts its links in an
# assembly's `Printed_parts` group rather than `COTS`, and the name the bill
# of materials gives it.  The printed parts are PLA except the TPU
# rollers, for which FreeCAD has no card.  The colours are the real robot's:
# mid grey PLA, charcoal rollers, black screws, brass inserts and spacers, a
# dark motor and a blue battery.  A document built headless has no view
# provider to carry a colour, so the colours are applied in the GUI pass.
_DEFAULT_CARD = "7f9fd73b-50c9-41d8-b7b2-575a030c1eeb"
_STEEL_CARD = "4b849c55-6b3a-4f75-a055-40c0d0324596"
_PLA_CARD = "93861244-fbbe-41a9-a7e0-aeed53abd782"       # PLA-Generic
_BRASS_CARD = "4151e19c-fd6a-4ca4-83d4-d5e17d76cb9c"     # Brass
MATERIALS = {
    "printed": {"card": _PLA_CARD, "colour": (138, 142, 150), "printed": True, "name": "PLA"},
    "tpu": {"card": _DEFAULT_CARD, "colour": (40, 40, 42), "printed": True, "name": "TPU"},
    "steel": {"card": _STEEL_CARD, "colour": (200, 200, 205), "printed": False, "name": "steel"},
    "black_oxide": {"card": _STEEL_CARD, "colour": (45, 45, 48), "printed": False, "name": "steel, black oxide"},
    "brass": {"card": _BRASS_CARD, "colour": (200, 160, 80), "printed": False, "name": "brass"},
    "motor": {"card": _STEEL_CARD, "colour": (60, 60, 64), "printed": False, "name": "bought"},
    "battery": {"card": _DEFAULT_CARD, "colour": (26, 75, 155), "printed": False, "name": "bought"},
}
# What a part is made of when its script does not say.
DEFAULT_MATERIAL = "printed"

# The controller board's solder mask; its components keep the colours of
# their KiCad 3D models.
SOLDER_MASK = (15, 45, 55)
