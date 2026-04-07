' Define sphere solid
With Sphere
    .Reset
    .Name "{{name}}"
    .Component "{{component}}"
    .Material "{{material}}"
    .Axis "{{axis}}"
    .CenterRadius "{{center_radius}}"
    .TopRadius "{{top_radius}}"
    .BottomRadius "{{bottom_radius}}"
    .Center "{{cx}}", "{{cy}}", "{{cz}}"
    .Segments "{{segments}}"
    .Create
End With
