' Create ground plane
With Brick
    .Reset
    .Name "{{ground_name}}"
    .Component "component1"
    .Material "PEC"
    .Xmin {{x_min}}
    .Xmax {{x_max}}
    .Ymin {{y_min}}
    .Ymax {{y_max}}
    .Zmin {{z_min}}
    .Zmax {{z_max}}
    .Create
End With
