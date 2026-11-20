"""Body_Upper_Left: the quarter at -x, +y.

Drawn by `_quarter.py`, which says what a quarter is; this script only
says which quadrant it sits in and what it has that the others do not.
"""

import _quarter as quarter
import fcprim as fp
import os

fp.open_parameters()


def build(doc):
    return quarter.build(doc, "Body_Upper_Left", -1, 1, slots=True, pin_hole=3)


fp.make(__file__, "Body_Upper_Left", build,
        test=quarter.test)
