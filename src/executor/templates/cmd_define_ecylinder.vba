' Define elliptical cylinder solid
With ECylinder
    .Reset
    .Name "{{name}}"
    .Component "{{component}}"
    .Material "{{material}}"
    .Xradius "{{xradius}}"
    .Yradius "{{yradius}}"
    .Axis "{{axis}}"
    .Zrange "{{z_min}}", "{{z_max}}"
    .Xcenter "{{xcenter}}"
    .Ycenter "{{ycenter}}"
    .Segments "{{segments}}"
    .Create
End With
