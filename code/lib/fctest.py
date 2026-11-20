"""The test every part runs on itself: change named dimensions and recompute.

"Modifiable" is the point of the model, so each part script names a few of
its dimensions, sketch constraints or cells of the shared spreadsheet, and
`flex` changes each one, recomputes, checks that the solid really changed and
that nothing failed, and puts the value back.
"""

import math

import FreeCAD as App


def _recompute(doc):
    for d in App.listDocuments().values():
        d.recompute()
    bad = [o.Label for o in doc.Objects if "Invalid" in o.State or "Error" in o.State]
    if bad:
        raise SystemExit(f"{doc.Name}: recompute failed after a change: {bad}")


def flex(doc, bdy, changes):
    """Change named dimensions, recompute, and put them back.

    `changes` is a list of `(object, constraint name, new value)` for a sketch
    constraint, `("sheet", alias, new value)` for a cell of the shared
    spreadsheet, or `(object, property, new value)` for a property of any
    other object, such as a fastener's `Length`.  Each change must recompute without a failed feature and must
    actually change the solid -- its vertices must move, since moving a hole
    changes no volume -- and the original values are restored afterwards and
    the solid has to come back to its volume.

    A constraint driven by an expression is refused: `setDatum` on it is
    silently overwritten by the expression, so the test would prove nothing.
    Flex the spreadsheet cell instead.

    Returns what was changed, for the build report.
    """
    def signature(shape):
        return sorted((round(v.X, 6), round(v.Y, 6), round(v.Z, 6))
                      for v in shape.Vertexes)
    import fcprim
    before = bdy.Shape.Volume
    before_sig = signature(bdy.Shape)
    done = []
    for target, name, value in changes:
        if target == "sheet":
            sheet = App.getDocument(fcprim.PARAMS_DOC).getObject(fcprim.PARAMS_SHEET)
            cell = sheet.getCellFromAlias(name)
            old = sheet.getContents(cell)
            sheet.set(cell, str(value))
            restore = lambda: sheet.set(cell, old)
        elif not hasattr(target, "Constraints"):
            old = getattr(target, name)
            setattr(target, name, value)
            restore = lambda t=target, n=name, o=old: setattr(t, n, o)
        else:
            driven = [path for path, _ in target.ExpressionEngine
                      if path.endswith(f"Constraints.{name}")]
            if driven:
                raise SystemExit(f"{doc.Name}: {name} is driven by an expression;"
                                 " flex the spreadsheet cell instead")
            idx = [c.Name for c in target.Constraints].index(name)
            old = target.Constraints[idx].Value
            unit = "deg" if target.Constraints[idx].Type == "Angle" else "mm"
            if unit == "deg":
                target.setDatum(idx, App.Units.Quantity(f"{value} deg"))
                restore = lambda t=target, i=idx, o=old: t.setDatum(
                    i, App.Units.Quantity(f"{math.degrees(o)} deg"))
            else:
                target.setDatum(idx, App.Units.Quantity(f"{value} mm"))
                restore = lambda t=target, i=idx, o=old: t.setDatum(
                    i, App.Units.Quantity(f"{o} mm"))
        _recompute(doc)
        after = bdy.Shape.Volume
        if not bdy.Shape.isValid() or signature(bdy.Shape) == before_sig:
            raise SystemExit(f"{doc.Name}: changing {name} to {value} did not "
                             f"change the solid ({before:.3f} -> {after:.3f})")
        print(f"\n  flex {name} -> {value}: volume {before:.3f} -> {after:.3f}, "
              f"recomputes clean", flush=True)
        restore()
        _recompute(doc)
        back = bdy.Shape.Volume
        if abs(back - before) > 1e-6 * max(1.0, before):
            raise SystemExit(f"{doc.Name}: restoring {name} did not restore the "
                             f"volume ({before:.6f} -> {back:.6f})")
        done.append({"dimension": name, "to": str(value).lstrip("="),
                     "volume": round(after, 3)})
    return done
