"""Motor_Side_Left: the left-handed wheel's motor side, 2 of them in the robot.

Drawn by `_wheelside.py`, which says what a wheel side is; this
script only says which hand and which side it is.  The wheel axis runs
along Y, its back face on y = 0.
"""

import os

import fcprim as fp
import _wheelside as wheelside

fp.open_parameters()


def build(doc):
    return wheelside.build(doc, "Motor_Side_Left", hand=1, motor=True)


fp.make(__file__, "Motor_Side_Left", build,
        test=wheelside.test)
