"""Wheel_Left: a left-handed wheel, 2 of them in the robot.

Drawn by `_wheelasm.py`, which says what a wheel is; this script
only says which hand.  The frame is the motor side's own.
"""

import _wheelasm as wheelasm

NEEDS = ["Roller_Assembly"]

wheelasm.build(__file__, "Wheel_Left", hand=1)
