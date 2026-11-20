"""Outer_Side_Right: the right-handed wheel's outer side, 2 of them in the robot.

Drawn by `_wheelside.py`, which says what a wheel side is; this
script only says which hand and which side it is.  The wheel axis runs
along Y, its back face on y = -35 (`wheelside.OUTER_BACK_Y`).
"""

import os

import fcprim as fp
import _wheelside as wheelside

fp.open_parameters()


def build(doc):
    return wheelside.build(doc, "Outer_Side_Right", hand=-1, motor=False)


fp.make(__file__, "Outer_Side_Right", build,
        test=wheelside.test)
