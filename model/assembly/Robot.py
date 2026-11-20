"""Robot: the body, the controller's baseplate and four wheels.

- The robot's frame: x along its length, y across, z up from the underside
  of the floor.  The body is drawn with its length along y, so it is grounded
  turned a quarter round.
- The baseplate's BOARD1 sits on Body_Low_Right's FLOOR_SCREW.
- A motor (an envelope) on each quarter's MOTOR datum, held by four screws.
- Each wheel turns on its quarter's WHEEL datum by its motor side's HUB: a
  revolute joint, so that the wheels can be turned.  That leaves four degrees
  of freedom, one per wheel.  The motor's shaft is drawn with its flat where
  the D-bores of the hub and the motor side start and where the clamp screw
  presses on it, so a wheel turned away from there meets them: the contact
  check lets the shaft overlap all three for that reason.
- The battery stands on the alignment plate's BATTERY datum.
- The baseplate is screwed through the floor into its four inserts; the
  controller board stands on four spacers screwed from under the baseplate,
  and is held by four screws on top.  The board comes from its KiCad design
  (model/electronics); where that folder holds no board the robot is built
  without it.
- Mecanum wheels go in an X seen from above: the rollers on top of the
  wheels point towards the robot's centre.  With the quarters' signs (sx, sy)
  that puts a left-handed wheel where sx and sy differ, and the build checks
  the result on the rollers themselves (`roller_layout_check`).
"""

import math
import os

import FreeCAD as App

import fcasm
import paths

NEEDS = ["Body", "Wheel_Left", "Wheel_Right"]
# Each quarter's signs: which side of the body's centre it lies on in x and y.
QUARTERS = {"Body_Low_Right": (1, -1), "Body_Low_Left": (-1, -1),
            "Body_Upper_Right": (1, 1), "Body_Upper_Left": (-1, 1)}


def hand(sx, sy):
    """+1 for a left-handed wheel, -1 for a right-handed one."""
    return -sx * sy


def build():
    a = fcasm.Assembly(__file__, "Robot")
    a.subassembly("Body", paths.model("assembly", "Body.FCStd"))
    a.links["Body"].Placement = App.Placement(App.Vector(0, 0, 0),
                                              App.Rotation(App.Vector(0, 0, 1), -90))
    a.ground("Body")
    a.part("Baseplate", paths.model("body", "Baseplate_MotionSystemController.FCStd"))
    a.joint("Fixed", ("Baseplate", "BOARD1"), ("Body", "FLOOR_SCREW", "Body_Low_Right"))
    wheels = []
    for q, (sx, sy) in QUARTERS.items():
        h = hand(sx, sy)
        label = f"Wheel_{q[len('Body_'):]}"
        a.subassembly(label, paths.model(
            "assembly", f"Wheel_{'Left' if h > 0 else 'Right'}.FCStd"))
        a.joint("Revolute", (label, "HUB", "Motor_Side"), ("Body", "WHEEL", q))
        a.report.setdefault("wheels", {})[label] = "left" if h > 0 else "right"
        print(f"  {label}: {'left' if h > 0 else 'right'}-handed", flush=True)
        wheels.append(label)
    drive(a)
    electronics(a)
    a.solve(free=len(QUARTERS))
    a.contact_check(gap=0.5)
    roller_layout_check(a, wheels)
    a.save()


def drive(a):
    """Motors, their screws, the hubs' overlap with the shafts, the battery."""
    for q in QUARTERS:
        motor = f"Motor_{q[len('Body_'):]}"
        a.bought(motor, paths.model("bought", "NEMA17_Stepper.FCStd"), "FACE",
                 ("Body", "MOTOR", q))
        for i in range(1, 5):
            a.fastener(f"{motor}_Screw{i}", "ISO4762", "M3", 8.0, ("Body", f"NEMA_SCREW{i}", q),
                       "black_oxide", into=[motor])
        for bored in ("Motor_Hub", "Motor_Side", "Clamp_Screw"):
            a.overlaps.add(frozenset((motor, f"Wheel_{q[len('Body_'):]}/{bored}")))
    a.bought("Battery", paths.model("bought", "Battery_2200mAh.FCStd"), "BASE",
             ("Body", "BATTERY", "Body_Alignment_Plate"))


def electronics(a):
    """The baseplate's inserts and floor screws, the spacers, the board."""
    def screw(label, kind, length, onto, into):
        a.fastener(label, kind, "M3", length, onto, "black_oxide", into=into)

    for n in range(1, 5):
        a.fastener(f"Baseplate_Insert{n}", "IUTHeatInsert", "M3", 4.0,
                   ("Baseplate", f"INSERT{n}"), "brass", into=["Baseplate"])
    # Which baseplate hole each quarter's floor screw and pin screw go into.
    for q, datum, n in (("Body_Low_Right", "FLOOR_SCREW_HEAD", 1),
                        ("Body_Low_Right", "PIN_SCREW_HEAD", 2),
                        ("Body_Low_Left", "PIN_SCREW_HEAD", 3),
                        ("Body_Low_Left", "FLOOR_SCREW_HEAD", 4)):
        screw(f"Floor_Screw{n}", "ISO10642", 8.0, ("Body", datum, q), [f"Baseplate_Insert{n}"])
    spacer = paths.model("bought", "Spacer_M3x5.FCStd")
    for n in range(1, 5):
        a.bought(f"Spacer{n}", spacer, "BOTTOM", ("Baseplate", f"SPACER{n}"))
        screw(f"Spacer_Screw{n}", "ISO10642", 6.0, ("Baseplate", f"SCREW{n}"), [f"Spacer{n}"])
    board = paths.model("electronics", "MotionSystemController.FCStd")
    if not os.path.exists(board):
        a.report["board"] = "left out: no board document in model/electronics"
        a.note("The controller board is designed in KiCad and is not part of this repository, "
               "so neither it nor the four ISO 4762 M3 x 4 screws that hold it on its spacers "
               "are counted here.")
        print("\n  board: left out, no board document in model/electronics", flush=True)
        return
    a.bought("Board", board, "HOLE1", ("Spacer1", "TOP"))
    for n in range(1, 5):
        a.datum_check(("Board", f"HOLE{n}"), (f"Spacer{n}", "TOP"))
        screw(f"Board_Screw{n}", "ISO4762", 4.0, ("Board", f"SCREW{n}"), [f"Spacer{n}"])
    a.report["board"] = os.path.basename(board)


def roller_layout_check(a, wheels):
    """The rollers on top of the wheels point towards the robot's centre.

    Seen from above, each wheel's highest roller axis must lie nearer the line
    from the wheel to the robot's centre than the other diagonal.  The wheels
    sit at 39 degrees off the robot's axis and the rollers at 45, so the right
    layout gives about 6 degrees and the wrong one about 84.
    """
    items = a.items()
    for w in wheels:
        tops = []
        for name, (body, pl) in items.items():
            if name.startswith(w + "/") and name.endswith("/Roller"):
                axis = pl.multiply(fcasm._datum_of(body, "AXIS").Placement)
                tops.append((axis.Base.z, axis))
        axis = max(tops, key=lambda t: t[0])[1]
        d = axis.Rotation.multVec(App.Vector(0, 0, 1))
        d = App.Vector(d.x, d.y, 0).normalize()
        to_centre = App.Vector(-axis.Base.x, -axis.Base.y, 0).normalize()
        angle = math.degrees(math.acos(min(1.0, abs(d.dot(to_centre)))))
        if angle > 22.5:
            raise SystemExit(f"{w}: its top roller is {angle:.1f} degrees off the line "
                             f"to the centre; it must point there")
        a.report.setdefault("top_roller_off_centre_line_deg", {})[w] = round(angle, 2)
        print(f"\n  rollers: {w}'s top roller {angle:.1f} degrees off the line to the "
              f"centre", flush=True)


build()
