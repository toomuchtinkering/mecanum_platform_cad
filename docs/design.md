# How the parts are built

Every part is one PartDesign Body, written by the script next to its document. The sketches are fully
constrained, and each constraint is named after what it drives (`bore_d`, `roller_angle`), so the Constraints
panel reads. A value that more than one document uses is a cell of the spreadsheet in `model/Parameters.FCStd`,
bound to the sketches by expressions, and is written down nowhere else. Within a part, one sketch holds a position
that others take by expression: a hole, its countersink and its boss move together. A repeated feature is a
pattern whose count and spacing are parameters.

The assemblies join parts on named datums (`PartDesign::CoordinateSystem` objects that each part script writes),
never on faces or edges, so a part can be rebuilt without breaking a joint. Each assembly is what the Assembly
workbench's own command makes, with its joints in `Joints`, and sorts what it holds into `Printed_parts`,
`Norm_parts` (screws and inserts), `COTS` (the other bought parts) and `Assemblies` (sub-assemblies). Which group a
part goes in follows from what it is made of (`model/project.py`).

## The wheel

A wheel is two sides with nine rollers between them. Each roller turns on two ball bearings on a pin, between two
washers, and the pin's ends sit in a claw on each side.

### Ellipsoidal roller

One revolve of one profile whose running surface is a single ellipse centred on the wheel axis:

- **The running surface**, from one end chamfer to the other, follows the section of the wheel's envelope
  cylinder, radius `envelope_r` (`roller_axis_r` + `roller_r`), by the plane through the roller axis at
  `roller_angle` (45°) to the wheel axis: an ellipse with semi-axes `envelope_r` / sin(45°) and `envelope_r`.
  This is the classic mecanum profile: the rollers together trace a circle as the wheel turns. The roller is
  `roller_r` (6.8) in radius at its middle.
- The outer end edge has a 0.2 mm chamfer, equal along both faces. A bearing seat at each end, Ø`seat_d` (6.1) ×
  `seat_depth` (3.6) with a 0.2 mm lead-in, and a Ø4.5 bore between them.

Changing `roller_angle` or `roller_r` reshapes the profile.

### Roller pin

A turned pin: Ø3.7 between shoulders 27 mm apart, a Ø2.88 × 6.5 journal at each end that carries a bearing and
goes on into the wheel side, 0.1 mm tip chamfers, and a flat along the whole length at 1.44 below the axis. The
flat is tangent to the journals, so it only cuts the middle, and the pin prints lying on it. Its datums CLAW_A and
CLAW_B are where it passes a wheel side's washer face, MIDDLE where the roller turns.

### Washer

A Ø3.2 / Ø4.6 × 1.4 ring with all four edges broken by 0.05 mm chamfers.

### Wheel sides

The four wheel sides, motor and outer side of a left- and a right-handed wheel, are one description
(`model/wheel/_wheelside.py`). The four scripts only say which hand (+1 left, −1 right) and which side. A
right-handed side is a left-handed one mirrored in X. Both carry the same marker notch across the top of the rim,
`notch_w` (0.5) wide and `notch_depth` (0.5) deep.

A wheel side is:

- a disc of radius `wheel_r` (32.5), `side_t` (6) thick;
- nine claws, one per roller, patterned round the wheel axis. Roller k's pin axis passes closest to the wheel axis
  at `claw_phase` + k × 40°, at `pin_axis_r`, and runs at `roller_angle` to the wheel axis. The washer face,
  square to the pin, crosses the pin axis on the claw face, `washer_offset` (17.4) along the pin from the roller's
  middle. Round the pin axis:
  - the knob: a Ø14 boss below the washer face, standing proud of the claw face on the half where that face falls
    away from the washer face, with a 2 mm round on its end;
  - the cup: Ø14 cut above the washer face, where the roller's end turns, its exit through the claw face broken by
    a 1.6 mm chamfer and an R5 round between the cup and that chamfer;
  - the pin hole: Ø3.3, 3.35 deep below the washer face, a flat bottom with an R1 round and a 0.2 mm lead-in;
- everything beyond `wheel_r` trimmed, with a 2.5 mm round on the back edge of the rim;
- the hub. Motor side: a Ø12 boss, the D-bore for the 5 mm motor shaft, four inserts for the motor hub's screws
  and four counterbored screws through to the outer side. Outer side: a Ø28 tube that spans the gap between the two
  discs, bored to take the motor side's boss, with four inserts in its end.

Every dimension the four share is a spreadsheet cell, so a change is one edit, not four. The datums PIN1 to PIN9
sit where each pin passes the washer face, with X the way the pin's flat faces: away from the wheel axis on
left-handed sides and towards it on right-handed ones.

## The drive

### Motor hub (`Nema_17_Mount`)

The hub that joins a stepper shaft to its wheel: a Ø28 × 2 flange with four Ø3.2 holes on a Ø20 circle at 45° and
a 0.5 × 1 marker notch in the rim, a Ø12 hub, a Ø5.2 D-bore (flat 2.1 from the axis), and a boss for a Ø4.1 radial
hole 3.35 mm above the flange. The boss's sides rise from where they meet the hub's circle at z = 5. The bolt
circle and the D-bore are cells (`hub_screw_circle_d`, `shaft_bore_d`, `shaft_flat`) that the motor side shares.

## The body

### Body quarters

Four quarters of one part, built by one description (`model/body/_quarter.py`) in four quadrants with signs
(sx, sy). Each script names only its quadrant and its extras, and every dimension the quarters share is a cell.

- **A quarter** is an L-shaped 5 mm floor with an R8 corner, an S-shaped wall 45 mm high with R8 inner corners, a
  NEMA 17 face in the wall across the quarter (Ø22.3 boss hole and four Ø3.4 screws on 31 mm), and three Ø4 lid
  holes 15 deep with 118° drill points in the wall corners. The body is 220 × 254 mm and 50 mm high. A triangular
  pocket x + y < 70, 3 deep, takes the alignment plate, which is screwed through the floor from below.
- **The quarters join in a pinwheel.** At each joint one quarter reaches over with a 3 mm tongue, 15 long, with
  two Ø4 insert holes; the other leaves a 2 mm skin, 15.5 long, with two countersunk Ø3.4 screws. The tongue is on
  the side wall when sx and sy have the same sign and on the back wall otherwise, which places all four joints
  consistently. Every tongue and skin end has a 0.3 mm chamfer on one corner. So the quarters are not mirror
  images of each other.
- **The extras:** the upper quarters have two 15 × 4 slots under the alignment plate's slots. The lower ones each
  have a countersunk floor screw at (35.7, −48.3) and (−39.2, −48.3), and every quarter has half of a countersunk
  hole under one of the alignment plate's two pin holes on the X axis. `Body_Low_Right` has a 13.4 × 9 window in
  its side wall with a 0.3 mm chamfer outside.
- The floor screws and pin holes are where the controller's baseplate is fixed, so they are not numbers of their
  own: the spreadsheet holds the baseplate's four holes (`board_hole1_x` to `_4_x`, `board_row1_y`,
  `board_row2_y`) and where the baseplate lies in the body (`baseplate_x`, `baseplate_y`), and the quarters, the
  alignment plate and the baseplate all place their holes from those cells.

### Body alignment plate

Seen in a frame turned 45°, the outline is a square whose sides sit 0.1 inside a 70 mm diamond (35√2 − 0.1 from
the centre, a fit clearance against the quarters' pockets), with 5 mm corner chamfers and a 0.5 mm chamfer round the
bottom edge, drawn as a tapered pad. Eight Ø4 screw holes: one pair, 8 mm in from the diamond's side and ±25 along
it, patterned four times. Two 15 × 4 slots, and two Ø3.6 holes on the X axis for the pins that locate the
baseplate.

### Controller baseplate

A 102 × 69 plate, 3 mm thick with a 0.5 mm top chamfer, on 1 mm bosses. The controller board stands on four
spacers, screwed on from below through four countersunk Ø3.2 holes at its mounting holes, as the board's KiCad
layout has them (`board_screw1_u` to `board_screw4_v`). Four Ø4 holes with heat-set inserts fix the plate to the
body. The bosses are chains of tangent arcs in one sketch: circles round the holes, R10 blends
between neighbours, R2 fillets where one group runs out to the edge. Only the boss centres and radii are
dimensioned; the blends follow from tangency, so moving a hole moves its blends.

## Bought parts

The parts that are bought are in the assemblies as interface models: what they occupy and where they are held,
nothing inside.

- **Screws and heat-set inserts** are objects of the Fasteners workbench, made in the assembly that uses them
  (`fcasm.Assembly.fastener`): ISO 4762 socket head and ISO 10642 countersunk M3 screws, 4 to 10 mm, and M3
  inserts shortened to fit their holes (3 mm in the 3 mm joint tongues and the alignment plate, 4 mm in the
  baseplate, the full 5.74 mm elsewhere). The workbench draws each with its axis on Z and the shank or body
  running down from its origin, which is where a screw's length is measured from (the head's bearing face, the
  top of a countersunk head) and an insert's mouth. A Fixed joint holds that origin on the hole's datum; the
  screw that clamps a motor hub is held by its tip instead, through an offset that follows its length. Its type,
  diameter and length are the object's own properties, so a screw is changed in FreeCAD like one placed by
  hand.
- **Envelopes**, drawn in PartDesign from the standards' dimensions, in `model/bought`: the NEMA 17 motor (42.3
  square, 40 long, the centring boss, a Ø5 shaft with its flat, four tapped holes on `nema_pitch`, the connector),
  the 2200 mAh battery, the 673ZZ bearing with its shields, and the M3 × 5 hex spacer.
- **Where they go**: every hole a bought part goes into carries a datum written by its part's script, with Z out
  of the material, so that the bought part joined to it sits in the hole. A countersunk screw's datum lies flush
  with the surface. The assemblies join each with `fcasm.Assembly.fastener` or, for an envelope,
  `fcasm.Assembly.bought`, which also name the one part it may overlap: an insert overlaps the part it is pressed into, a screw the insert or tapped hole it threads into,
  since neither is drawn with threads. Any other overlap fails the build.
- **Colours** follow the real robot: mid grey PLA, charcoal TPU rollers, black screws, brass inserts and
  spacers, a dark motor, a blue battery (`model/project.py`). Each part says what it is made of (`PartMaterial`),
  and the GUI stage colours it from that.

## The assemblies

- **Roller_Assembly**: a roller on its pin between two washers. The pin is grounded; the roller turns on the pin's
  MIDDLE, the one degree of freedom; a 673ZZ bearing rests on each of the pin's shoulders, inside the roller's
  seat, and a washer sits on each of the pin's CLAW datums.
- **Wheel_Left, Wheel_Right** (`model/assembly/_wheelasm.py`): the motor side is grounded, so the wheel's frame is
  the motor side's own. The outer side joins it tube end to claw face, turned half round; the motor hub's flange
  joins its back face; roller assembly k joins claw k by its pin. Nothing joins the pins to the outer side, so a
  check, not a joint, shows that the two sides' claws line up: each pin's far end must lie on the outer side's
  matching datum. Four screws fix the hub's flange to inserts in the motor side, four more join the sides through
  the motor side's counterbores into inserts in the outer side's tube, and one in an insert in the hub's radial
  hole clamps the hub on the shaft's flat, held by its tip.
- **Body**: the four quarters and the alignment plate, each joined to `Body_Low_Right` on CENTRE, the body's
  centre that every one of them is drawn about. Inserts sit in every joint tongue, lid hole and plate hole;
  countersunk screws go through each joint skin into the neighbour's tongue, and up through each floor into the
  alignment plate.
- **Robot**: x along the robot's length, z up from the underside of the floor. The body is grounded, the
  controller's baseplate sits on `Body_Low_Right`'s FLOOR_SCREW by its hole 1, screwed through the floor into its
  inserts, and a wheel turns on each quarter's WHEEL datum, on the motor axis `wheel_gap` (13 mm) beyond the motor
  wall: four degrees of freedom, one per wheel. A motor sits on each quarter's MOTOR datum behind its wall, held
  by four screws, its connector towards the back wall; the wheel's datum is turned so that the hub's flat starts on
  the shaft's. The battery stands on the alignment plate's BATTERY datum (`battery_x`, `battery_y`), and the
  controller board, where its document is present, on four spacers on the baseplate.
- **The wheels go in an X.** Seen from above, the rollers on top of the wheels point towards the robot's centre:
  left-handed wheels at `Low_Right` and `Upper_Left`, right-handed at `Low_Left` and `Upper_Right`. The robot's
  build checks this on the rollers themselves: each wheel's top roller must lie within 22.5° of the line to the
  centre (it is about 1.5° off; the other layout would be about 89° off).
