"""One wheel, either hand: two sides, the motor hub and a roller assembly per claw.

The motor side is grounded, so the wheel's frame is the motor side's own:
the wheel axis along Y, the back face on y = 0, the motor beyond it.
Everything else joins the motor side:

- the outer side's TUBE_END on its TUBE, which turns the outer side half
  round so that its claws face the motor side's;
- the motor hub's FLANGE on its HUB;
- roller assembly k by its pin's CLAW_A on PINk.  The pin's other end then
  sits in a claw of the outer side, which nothing joins, so that a check, not a
  joint, says whether the two sides' claws line up: each pin's CLAW_B must
  lie on one of the outer side's PIN datums, a different one for each pin.
  (The outer side is turned half round, so its numbering runs the other way.)
- the fasteners, objects of the Fasteners workbench made here: the hub's
  four screws into inserts in the motor side, the four screws that join the
  sides, through the motor side's counterbores into inserts in the outer
  side's tube (each insert found by where it lies, for the same reason as the
  pins), and the screw that clamps the hub on the shaft's flat, in an insert
  in the hub's radial hole, joined by its tip.
"""

import math

import fcasm
import fcprim
import paths


def build(script, name, hand):
    fcprim.open_parameters()
    side = "Left" if hand > 0 else "Right"
    count = int(round(fcprim.sheet_value("claw_count")))
    a = fcasm.Assembly(script, name)
    a.part("Motor_Side", paths.model("wheel", f"Motor_Side_{side}.FCStd"))
    a.part("Outer_Side", paths.model("wheel", f"Outer_Side_{side}.FCStd"))
    a.part("Motor_Hub", paths.model("drive", "Nema_17_Mount.FCStd"))
    for k in range(count):
        a.subassembly(f"Roller{k + 1}", paths.model("assembly", "Roller_Assembly.FCStd"))
    a.ground("Motor_Side")
    a.joint("Fixed", ("Outer_Side", "TUBE_END"), ("Motor_Side", "TUBE"))
    a.joint("Fixed", ("Motor_Hub", "FLANGE"), ("Motor_Side", "HUB"))
    for k in range(count):
        a.joint("Fixed", (f"Roller{k + 1}", "CLAW_A", "Pin"), ("Motor_Side", f"PIN{k + 1}"))
    fasteners(a)
    a.solve(free=0)
    outer = {f"PIN{j + 1}": a.frame(("Outer_Side", f"PIN{j + 1}")) for j in range(count)}
    used = set()
    for k in range(count):
        end = (f"Roller{k + 1}", "CLAW_B", "Pin")
        here = a.frame(end).Base
        pin = min(outer, key=lambda j: (outer[j].Base - here).Length)
        a.datum_check(end, ("Outer_Side", pin))
        used.add(pin)
    if len(used) != count:
        raise SystemExit(f"{name}: {count} pins in {len(used)} of the outer side's claws")
    a.contact_check(gap=0.5)
    a.save()


def fasteners(a):
    """The screws and inserts, Fasteners objects each fixed on its hole's datum."""
    def insert(label, onto, into):
        a.fastener(label, "IUTHeatInsert", "M3", 5.74, onto, "brass", into=into)

    def screw(label, length, onto, into, at="seat"):
        a.fastener(label, "ISO4762", "M3", length, onto, "black_oxide", at=at, into=into)

    for k in range(1, 5):
        insert(f"Hub_Insert{k}", ("Motor_Side", f"HUB_INSERT{k}"), ["Motor_Side"])
        screw(f"Hub_Screw{k}", 6.0, ("Motor_Hub", f"FLANGE_SCREW{k}"), [f"Hub_Insert{k}"])
    tube = {k: a.frame(("Outer_Side", f"TUBE_INSERT{k}")).Base for k in range(1, 5)}
    for k in range(1, 5):
        insert(f"Tube_Insert{k}", ("Outer_Side", f"TUBE_INSERT{k}"), ["Outer_Side"])
    for k in range(1, 5):
        here = a.frame(("Motor_Side", f"SIDE_SCREW{k}")).Base
        j = min(tube, key=lambda j: (tube[j].x - here.x) ** 2 + (tube[j].z - here.z) ** 2)
        off = math.hypot(tube[j].x - here.x, tube[j].z - here.z)
        if off > 1e-6:
            raise SystemExit(f"side screw {k} is {off:.6f} mm off the tube's insert {j}")
        screw(f"Side_Screw{k}", 8.0, ("Motor_Side", f"SIDE_SCREW{k}"), [f"Tube_Insert{j}"])
    insert("Clamp_Insert", ("Motor_Hub", "RADIAL_INSERT"), ["Motor_Hub"])
    # Joined by its tip, which presses on the shaft's flat whatever its length.
    screw("Clamp_Screw", 10.0, ("Motor_Hub", "CLAMP"), ["Clamp_Insert"], at="tip")
