' Create substrate layer
With Brick
    .Reset
    .Name "{{substrate_name}}"
    .Component "component1"
    .Material "{{material}}"
    .Xmin {{x_min}}
    .Xmax {{x_max}}
    .Ymin {{y_min}}
    .Ymax {{y_max}}
    .Zmin {{z_min}}
    .Zmax {{z_max}}
    .Create
End With
