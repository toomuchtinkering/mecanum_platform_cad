"""Body_Low_Right: the quarter at +x, -y, with the window in its side wall.

Drawn by `_quarter.py`, which says what a quarter is; this script only
says which quadrant it sits in and what it has that the others do not.
"""

import _quarter as quarter
import fcprim as fp
import os

fp.open_parameters()


def build(doc):
    return quarter.build(doc, "Body_Low_Right", 1, -1, pin_hole=2, floor_screws=[1], window=True)


fp.make(__file__, "Body_Low_Right", build,
        test=quarter.test)
