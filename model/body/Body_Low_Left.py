"""Body_Low_Left: the quarter at -x, -y.

Drawn by `_quarter.py`, which says what a quarter is; this script only
says which quadrant it sits in and what it has that the others do not.
"""

import _quarter as quarter
import fcprim as fp
import os

fp.open_parameters()


def build(doc):
    return quarter.build(doc, "Body_Low_Left", -1, -1, pin_hole=3, floor_screws=[4])


fp.make(__file__, "Body_Low_Left", build,
        test=quarter.test)
