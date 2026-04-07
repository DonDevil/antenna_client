' Define cylinder solid
With Cylinder
    .Reset
    .Name "{{name}}"
    .Component "{{component}}"
    .Material "{{material}}"
    .OuterRadius "{{outer_radius}}"
    .InnerRadius "{{inner_radius}}"
    .Axis "{{axis}}"
    .Zrange "{{z_min}}", "{{z_max}}"
    .Xcenter "{{xcenter}}"
    .Ycenter "{{ycenter}}"
    .Segments "{{segments}}"
    .Create
End With
