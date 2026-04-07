' Define brick solid
With Brick
    .Reset
    .Name "{{name}}"
    .Component "{{component}}"
    .Material "{{material}}"
    .Xrange "{{x_min}}", "{{x_max}}"
    .Yrange "{{y_min}}", "{{y_max}}"
    .Zrange "{{z_min}}", "{{z_max}}"
    .Create
End With
