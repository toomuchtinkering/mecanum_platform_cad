# Bill of materials

Counted from the built assemblies by `code/bom.py` (`python3 code/rebuild.py bom`), so it changes when they do. The documents named here hold each part. Assembly: `model/assembly/Robot.FCStd`.

## Printed parts

| Part | Material | Quantity | Document |
|---|---|---|---|
| Baseplate_MotionSystemController | PLA | 1 | `model/body/Baseplate_MotionSystemController.FCStd` |
| Body_Alignment_Plate | PLA | 1 | `model/body/Body_Alignment_Plate.FCStd` |
| Body_Low_Left | PLA | 1 | `model/body/Body_Low_Left.FCStd` |
| Body_Low_Right | PLA | 1 | `model/body/Body_Low_Right.FCStd` |
| Body_Upper_Left | PLA | 1 | `model/body/Body_Upper_Left.FCStd` |
| Body_Upper_Right | PLA | 1 | `model/body/Body_Upper_Right.FCStd` |
| Nema_17_Mount | PLA | 4 | `model/drive/Nema_17_Mount.FCStd` |
| Ellipsoidal_Roller | TPU | 36 | `model/wheel/Ellipsoidal_Roller.FCStd` |
| Motor_Side_Left | PLA | 2 | `model/wheel/Motor_Side_Left.FCStd` |
| Motor_Side_Right | PLA | 2 | `model/wheel/Motor_Side_Right.FCStd` |
| Outer_Side_Left | PLA | 2 | `model/wheel/Outer_Side_Left.FCStd` |
| Outer_Side_Right | PLA | 2 | `model/wheel/Outer_Side_Right.FCStd` |
| Pin_For_Ball_Bearing | PLA | 36 | `model/wheel/Pin_For_Ball_Bearing.FCStd` |
| Washer | PLA | 72 | `model/wheel/Washer.FCStd` |
| **162 in all** | | | |

## Bought parts

| Part | Quantity | Document |
|---|---|---|
| Ball bearing 673ZZ, 3 x 6 x 2.5 mm | 72 | `model/bought/Ball_Bearing_673ZZ.FCStd` |
| Battery pack 2200 mAh, 108 x 35 x 25 mm | 1 | `model/bought/Battery_2200mAh.FCStd` |
| Hex spacer M3 x 5, female/female, 5 mm across flats | 4 | `model/bought/Spacer_M3x5.FCStd` |
| NEMA 17 stepper motor, 42.3 mm square, 40 mm long, Ø5 mm shaft with flat | 4 | `model/bought/NEMA17_Stepper.FCStd` |
| **81 in all** | | |

## Screws and inserts

| Fastener | Standard | Size | Material | Quantity |
|---|---|---|---|---|
| Insert | IUTHeatInsert | M3 x 3 | brass | 16 |
| Insert | IUTHeatInsert | M3 x 4 | brass | 4 |
| Insert | IUTHeatInsert | M3 x 5.74 | brass | 48 |
| Screw | ISO 10642 | M3 x 4 | steel, black oxide | 16 |
| Screw | ISO 10642 | M3 x 6 | steel, black oxide | 4 |
| Screw | ISO 10642 | M3 x 8 | steel, black oxide | 4 |
| Screw | ISO 4762 | M3 x 6 | steel, black oxide | 16 |
| Screw | ISO 4762 | M3 x 8 | steel, black oxide | 32 |
| Screw | ISO 4762 | M3 x 10 | steel, black oxide | 4 |
| **144 in all** | | | | |

## Sub-assemblies, for orientation (their parts are counted above)

| Assembly | Quantity | Document |
|---|---|---|
| Body | 1 | `model/assembly/Body.FCStd` |
| Roller_Assembly | 36 | `model/assembly/Roller_Assembly.FCStd` |
| Wheel_Left | 2 | `model/assembly/Wheel_Left.FCStd` |
| Wheel_Right | 2 | `model/assembly/Wheel_Right.FCStd` |

## Not counted

- The controller board is designed in KiCad and is not part of this repository, so neither it nor the four ISO 4762 M3 x 4 screws that hold it on its spacers are counted here.
