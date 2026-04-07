' Define cone solid
With Cone
    .Reset
    .Name "{{name}}"
    .Component "{{component}}"
    .Material "{{material}}"
    .BottomRadius "{{bottom_radius}}"
    .TopRadius "{{top_radius}}"
    .Axis "{{axis}}"
    .Zrange "{{z_min}}", "{{z_max}}"
    .Xcenter "{{xcenter}}"
    .Ycenter "{{ycenter}}"
    .Segments "{{segments}}"
    .Create
End With
