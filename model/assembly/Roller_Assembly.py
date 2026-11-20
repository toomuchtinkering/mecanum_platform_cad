"""Roller_Assembly: a roller on its pin between two washers, 36 in the robot.

The pin is grounded in its own frame.  The roller turns on the pin's MIDDLE,
a 673ZZ ball bearing (an envelope) rests on each of the pin's shoulders,
inside the roller's bearing seat, and a washer sits on each of the pin's CLAW
datums with its FACE outwards, where the wheel sides' washer faces will be.
"""

import fcasm
import paths

NEEDS = []


def build():
    a = fcasm.Assembly(__file__, "Roller_Assembly")
    a.part("Pin", paths.model("wheel", "Pin_For_Ball_Bearing.FCStd"))
    a.part("Roller", paths.model("wheel", "Ellipsoidal_Roller.FCStd"))
    a.part("Washer_A", paths.model("wheel", "Washer.FCStd"))
    a.part("Washer_B", paths.model("wheel", "Washer.FCStd"))
    a.ground("Pin")             # the pin's frame is the assembly's
    a.joint("Revolute", ("Roller", "AXIS"), ("Pin", "MIDDLE"))
    a.joint("Fixed", ("Washer_A", "FACE"), ("Pin", "CLAW_A"))
    a.joint("Fixed", ("Washer_B", "FACE"), ("Pin", "CLAW_B"))
    bearing = paths.model("bought", "Ball_Bearing_673ZZ.FCStd")
    a.bought("Bearing_A", bearing, "INNER", ("Pin", "SHOULDER_A"))
    a.bought("Bearing_B", bearing, "INNER", ("Pin", "SHOULDER_B"))
    a.solve(free=1)
    a.contact_check(gap=0.5)
    a.save()


build()
