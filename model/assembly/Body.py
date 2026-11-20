"""Body: the four quarters and the alignment plate, with their fasteners.

Every part of the body is drawn about the body's centre in one frame, so each
joins Body_Low_Right, which is grounded, on its CENTRE datum.  Then the
fasteners, each on its datum: an insert in every joint tongue, lid hole and
plate hole, a countersunk screw through every joint skin into the insert of
the neighbour's tongue there, and the plate's screws up through each floor
into the plate's inserts.  Which insert a screw goes into is found by where
it lies, since the pinwheel decides which quarter's tongue is under a skin.
"""

import FreeCAD as App

import fcasm
import paths

NEEDS = []
PARTS = ["Body_Low_Right", "Body_Low_Left", "Body_Upper_Right", "Body_Upper_Left",
         "Body_Alignment_Plate"]


def build():
    a = fcasm.Assembly(__file__, "Body")
    for p in PARTS:
        a.part(p, paths.model("body", p + ".FCStd"))
    a.ground("Body_Low_Right")
    for p in PARTS[1:]:
        a.joint("Fixed", (p, "CENTRE"), ("Body_Low_Right", "CENTRE"))
    fasteners(a)
    a.solve(free=0)
    a.contact_check(gap=0.5)
    a.save()


def fasteners(a):
    """The inserts and screws, Fasteners objects each fixed on its hole's datum."""
    def insert(label, length, onto, into):
        a.fastener(label, "IUTHeatInsert", "M3", length, onto, "brass", into=into)

    short = lambda q: q[len("Body_"):]
    inserts = {}
    for q in PARTS[:4]:
        for i in (1, 2):
            label = f"{short(q)}_Joint_Insert{i}"
            insert(label, 3.0, (q, f"JOINT_INSERT{i}"), [q])
            inserts[label] = a.frame((q, f"JOINT_INSERT{i}")).Base
        for i in (1, 2, 3):
            insert(f"{short(q)}_Lid_Insert{i}", 5.74, (q, f"LID_INSERT{i}"), [q])
    plate = "Body_Alignment_Plate"
    plate_inserts = {}
    for n in range(1, 9):
        label = f"Plate_Insert{n}"
        insert(label, 3.0, (plate, f"INSERT{n}"), [plate])
        plate_inserts[label] = a.frame((plate, f"INSERT{n}")).Base
    for q in PARTS[:4]:
        for name, datum, found in (("Joint_Screw", "JOINT_SCREW", inserts),
                                   ("Plate_Screw", "PLATE_SCREW", plate_inserts)):
            for i in (1, 2):
                here = a.frame((q, f"{datum}{i}"))
                into = _in_line(here, found)
                a.fastener(f"{short(q)}_{name}{i}", "ISO10642", "M3", 4.0,
                           (q, f"{datum}{i}"), "black_oxide", into=[into])


def _in_line(frame, found):
    """The one insert in `found` on the axis of the screw at `frame`."""
    axis = frame.Rotation.multVec(App.Vector(0, 0, 1))
    hits = []
    for label, p in found.items():
        d = p - frame.Base
        off = (d - axis * d.dot(axis)).Length
        if off < 1e-6 and d.dot(axis) < 0:
            hits.append(label)
    if len(hits) != 1:
        raise SystemExit(f"screw at {frame.Base}: {len(hits)} inserts on its axis")
    return hits[0]


build()
