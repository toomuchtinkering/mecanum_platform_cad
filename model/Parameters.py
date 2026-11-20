"""The shared spreadsheet: values more than one part depends on.

Builds `Parameters.FCStd`, one spreadsheet whose cells carry aliases.  Part
documents bind their sketch dimensions to these cells by cross-document
expressions (`Parameters#Spreadsheet.roller_angle`), so changing a cell here in
the GUI and recomputing moves every part that uses it.

A value goes in here only when a second part needs it.  Everything else stays a
named constraint in the sketch that draws it.
"""

import os

import FreeCAD as App

import fcprim

# alias, value, unit, what it is.  A value given as text is an expression of
# other cells.
CELLS = [
    ("roller_angle", 45.0, "deg",
     "Angle between a roller axis and the wheel axis"),
    ("roller_axis_r", 26.823, "mm",
     "Wheel axis to roller axis, at the roller's middle"),
    ("roller_r", 6.8, "mm",
     "Roller radius at its middle, out to the wheel's envelope"),
    ("envelope_r", "roller_axis_r + roller_r", "mm",
     "Wheel radius the roller profile is drawn for: the roller follows the "
     "45 degree section of this cylinder, an ellipse"),
    ("roller_len", 34.0, "mm", "Roller length, end face to end face"),
    ("seat_d", 6.1, "mm", "Bearing seat diameter in the roller"),
    ("seat_depth", 3.6, "mm", "Bearing seat depth from the roller end face"),
    ("pin_len", 40.0, "mm", "Roller pin length"),
    ("pin_d", 3.7, "mm", "Roller pin diameter between the shoulders"),
    ("pin_end_d", 2.88, "mm",
     "Roller pin diameter at the ends, through the bearings and into the "
     "wheel sides"),
    ("pin_end_len", 6.5, "mm", "Length of each pin end, tip to shoulder"),
    # The body: four quarters round the origin, and the plate that joins them.
    ("body_x", 110.0, "mm", "Body quarter: outer side wall, from the centre line"),
    ("body_y", 127.0, "mm", "Body quarter: outer back wall, from the centre line"),
    ("body_h", 50.0, "mm", "Body quarter: height to the top of the walls"),
    ("floor_t", 5.0, "mm", "Body quarter: floor thickness"),
    ("wall_t", 5.0, "mm", "Body quarter: wall thickness"),
    ("skin_t", 2.0, "mm",
     "Body quarter: outer skin left at a joint recess; a tongue is wall_t - skin_t"),
    ("tongue_len", 15.0, "mm", "Body quarter: how far a joint tongue reaches into the next quarter"),
    ("tongue_gap", 0.5, "mm", "Body quarter: a recess is this much longer than the tongue"),
    ("joint_chamfer", 0.3, "mm", "Body quarter: chamfer on the end of a tongue or skin"),
    ("step_y", 52.0, "mm", "Body quarter: outer face of the wall across the quarter"),
    ("motor_x", 60.0, "mm", "Body quarter: outer face of the motor wall"),
    ("corner_r", 8.0, "mm", "Body quarter: radius of the wall corners"),
    ("motor_y", 89.5, "mm", "Body quarter: motor axis, from the centre line"),
    ("motor_z", 26.15, "mm", "Body quarter: motor axis height"),
    ("nema_pitch", 31.0, "mm", "NEMA 17 screw spacing"),
    ("nema_boss_d", 22.3, "mm", "Hole for the NEMA 17 centring boss"),
    ("nema_screw_d", 3.4, "mm", "NEMA 17 screw clearance"),
    ("wheel_gap", 13.0, "mm",
     "From the outer face of a quarter's motor wall to its wheel's back face, "
     "where the motor hub's flange sits: set by the motor and its shaft"),
    ("plate_diag", 70.0, "mm",
     "Alignment plate: the diamond it is cut from reaches this far along each axis"),
    ("plate_t", 3.0, "mm", "Alignment plate thickness, and the depth of its pocket"),
    ("plate_hole_in", 8.0, "mm", "Alignment plate screws: in from the diamond's side"),
    ("plate_hole_spread", 25.0, "mm", "Alignment plate screws: either side of a side's middle"),
    ("plate_slot_w", 15.0, "mm",
     "Slots under the alignment plate, in the plate and the upper quarters' floors: width, along x"),
    ("plate_slot_h", 4.0, "mm", "Slots under the alignment plate: height, along y"),
    ("plate_slot_y1", 19.0, "mm", "Slots under the alignment plate: the first one's middle, along y"),
    ("plate_slot_y2", 48.0, "mm", "Slots under the alignment plate: the second one's middle, along y"),
    ("floor_hole_d", 3.6, "mm",
     "Body quarter: holes through the floor, for the plate screws, the floor screws and the board "
     "pins; the board pins' holes in the alignment plate"),
    ("countersink_d", 6.72, "mm", "Body quarter: countersink diameter of every screw"),
    ("joint_insert_d", 4.0, "mm", "Body quarter: insert holes in a joint tongue"),
    ("joint_screw_d", 3.4, "mm", "Body quarter: screw holes through a joint skin"),
    ("joint_z1", 15.0, "mm", "Body quarter: height of a joint's lower screw"),
    ("joint_z2", 45.0, "mm", "Body quarter: height of a joint's upper screw"),
    ("lid_hole_d", 4.0, "mm", "Body quarter: lid screw holes, down into the wall corners"),
    ("lid_hole_depth", 15.0, "mm", "Body quarter: depth of the lid screw holes"),
    # The baseplate under the controller board, and its four Ø4 holes, where
    # two floor screws and the two pins of the alignment plate fix it to the
    # body.  The pins sit on the body's centre line, the floor screws 48.3 mm
    # from them.  The board itself screws onto the baseplate at the mounting
    # holes of its KiCad layout, below.
    ("board_hole1_x", 15.3, "mm", "Baseplate hole 1 (a floor screw), x on the baseplate"),
    ("board_hole2_x", 14.0, "mm", "Baseplate hole 2 (a pin), x on the baseplate"),
    ("board_hole3_x", 96.5, "mm", "Baseplate hole 3 (a pin), x on the baseplate"),
    ("board_hole4_x", 90.2, "mm", "Baseplate hole 4 (a floor screw), x on the baseplate"),
    ("board_row1_y", -15.05, "mm", "Baseplate holes 1 and 4, y on the baseplate"),
    ("board_row2_y", -63.35, "mm", "Baseplate holes 2 and 3, y on the baseplate"),
    ("baseplate_x", 51.0, "mm",
     "Baseplate: its own origin in the body's frame, x; it lies turned half round, so a point "
     "(u, v) on it is at (baseplate_x - u, baseplate_y - v) in the body"),
    ("baseplate_y", -63.35, "mm", "Baseplate: its own origin in the body's frame, y"),
    # The controller board's four mounting holes, where the baseplate takes its
    # screws and spacers: the holes of the board's KiCad layout less (25, 50.5),
    # with y turned up, so (u, v) on the baseplate.  The board's 3D model
    # comes from KiCad with that origin, so its own frame is the baseplate's.
    ("board_screw1_u", 3.75, "mm", "Controller board: mounting hole 1, u on the baseplate"),
    ("board_screw1_v", -39.5, "mm", "Controller board: mounting hole 1, v on the baseplate"),
    ("board_screw2_u", 3.75, "mm", "Controller board: mounting hole 2, u on the baseplate"),
    ("board_screw2_v", -9.0, "mm", "Controller board: mounting hole 2, v on the baseplate"),
    ("board_screw3_u", 97.25, "mm", "Controller board: mounting hole 3, u on the baseplate"),
    ("board_screw3_v", -19.25, "mm", "Controller board: mounting hole 3, v on the baseplate"),
    ("board_screw4_u", 93.0, "mm", "Controller board: mounting hole 4, u on the baseplate"),
    ("board_screw4_v", -58.25, "mm", "Controller board: mounting hole 4, v on the baseplate"),
    # The battery, standing on the floor of the body, held by the alignment
    # plate's datum BATTERY.
    ("battery_x", 5.0, "mm", "Battery: the middle of its length, x in the body"),
    ("battery_y", 21.0, "mm", "Battery: its face towards the centre, y in the body"),
    # The wheel sides: a disc with a claw for each roller's pin, and a hub.
    ("wheel_r", 32.5, "mm", "Wheel side: rim radius"),
    ("side_t", 6.0, "mm", "Wheel side: disc thickness"),
    ("rim_round", 2.5, "mm", "Wheel side: round on the back edge of the rim"),
    ("claw_count", 9, "", "Rollers per wheel, and claws round each wheel side"),
    ("claw_phase", 10.0, "deg",
     "Wheel angle at which the first roller axis passes closest to the wheel axis"),
    ("pin_axis_r", 27.081, "mm",
     "Wheel axis to a roller pin axis at closest approach"),
    ("washer_offset", 17.4, "mm",
     "Along the pin, from the roller's middle to a wheel side's washer face, "
     "which crosses the pin axis on the disc face"),
    ("claw_d", 14.0, "mm", "Wheel side: claw boss and roller cup diameter"),
    ("claw_round", 2.0, "mm", "Wheel side: round on the end of the claw boss"),
    ("cup_chamfer", 1.6, "mm", "Wheel side: chamfer where the roller cup leaves the disc"),
    ("cup_round", 5.0, "mm", "Wheel side: round between the roller cup and that chamfer"),
    ("pin_hole_d", 3.3, "mm", "Wheel side: roller pin hole diameter"),
    ("pin_hole_depth", 3.35, "mm", "Wheel side: pin hole depth below the washer face"),
    ("hub_boss_d", 12.0, "mm",
     "Motor side's hub boss, which fits the outer side's tube bore"),
    ("hub_screw_circle_d", 20.0, "mm",
     "Screw circle of the motor hub's flange, and of the screws that join the "
     "wheel sides"),
    ("shaft_bore_d", 5.2, "mm", "D-bore for the 5 mm motor shaft: diameter"),
    ("shaft_flat", 2.1, "mm", "D-bore for the motor shaft: flat, from the axis"),
    ("pin_hole_round", 1.0, "mm", "Wheel side: round at the pin hole's flat bottom"),
    ("pin_hole_lead", 0.2, "mm", "Wheel side: 45 degree lead-in at the pin hole's mouth"),
    ("hub_boss_len", 5.0, "mm", "Motor side: how far its hub boss stands off the claw face"),
    ("hub_boss_chamfer", 0.75, "mm", "Motor side: chamfer on the end of its hub boss"),
    ("tube_d", 28.0, "mm", "Outer side: tube diameter"),
    ("tube_chamfer", 0.75, "mm", "Outer side: chamfer on the tube's end, inside and out"),
    ("tube_bore_clearance", 0.2, "mm", "Outer side: tube bore over the motor side's hub boss"),
    ("tube_insert_depth", 8.0, "mm", "Outer side: insert holes, into the tube's end"),
    ("side_screw_d", 3.2, "mm", "Motor side: holes for the screws that join the wheel sides"),
    ("side_insert_d", 4.1, "mm",
     "Wheel side: insert holes, for the motor hub's screws and in the outer side's tube"),
    ("counterbore_d", 6.5, "mm", "Motor side: counterbores for the screws that join the wheel sides"),
    ("counterbore_depth", 3.5, "mm", "Motor side: depth of those counterbores and of the marker slot"),
    ("marker_slot_w", 0.5, "mm", "Motor side: width of the marker slot on its back face"),
    ("marker_slot_r", 14.0, "mm", "Motor side: how far out the marker slot runs"),
    ("notch_w", 0.5, "mm", "Wheel side: width of the marker notch across the rim"),
    ("notch_depth", 0.5, "mm", "Wheel side: depth of the marker notch"),
]


def build():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        fcprim.PARAMS_DOC + ".FCStd")
    doc = fcprim.document(fcprim.PARAMS_DOC)
    sheet = doc.addObject("Spreadsheet::Sheet", fcprim.PARAMS_SHEET)
    sheet.Label = "Parameters"
    for col, title in zip("ABCD", ("Name", "Value", "Unit", "Meaning")):
        sheet.set(f"{col}1", title)
    for row, (alias, value, unit, meaning) in enumerate(CELLS, start=2):
        sheet.set(f"A{row}", alias)
        if isinstance(value, str):
            sheet.set(f"B{row}", f"={value}")
        else:
            sheet.set(f"B{row}", f"={value:.15g} {unit}".rstrip())
        sheet.setAlias(f"B{row}", alias)
        sheet.set(f"C{row}", unit)
        sheet.set(f"D{row}", meaning)
    sheet.setColumnWidth("A", 130)
    sheet.setColumnWidth("D", 520)
    doc.recompute()
    fcprim.fail_on_invalid(doc)
    known = {}
    for alias, value, unit, _ in CELLS:
        if isinstance(value, str):
            value = eval(value, {}, dict(known))
        known[alias] = value
        got = fcprim.sheet_value(alias)
        if abs(got - value) > 1e-9:
            raise SystemExit(f"cell {alias} reads {got}, wanted {value}")
    fcprim.meta(doc)
    fcprim.dress(doc)
    doc.saveAs(path)
    print(f"  saved {path} with {len(CELLS)} parameters", flush=True)


build()
