' Define torus solid
With Torus
    .Reset
    .Name "{{name}}"
    .Component "{{component}}"
    .Material "{{material}}"
    .OuterRadius "{{outer_radius}}"
    .InnerRadius "{{inner_radius}}"
    .Axis "{{axis}}"
    .Xcenter "{{xcenter}}"
    .Ycenter "{{ycenter}}"
    .Zcenter "{{zcenter}}"
    .Segments "{{segments}}"
    .Create
End With
