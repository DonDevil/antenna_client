' Define extruded solid from point list
With Extrude
    .Reset
    .Name "{{name}}"
    .Component "{{component}}"
    .Material "{{material}}"
    .Mode "Pointlist"
    .Height "{{height}}"
    .Twist "{{twist}}"
    .Taper "{{taper}}"
    .Origin "{{ox}}", "{{oy}}", "{{oz}}"
    .Uvector "{{ux}}", "{{uy}}", "{{uz}}"
    .Vvector "{{vx}}", "{{vy}}", "{{vz}}"
    ' Add .Point and .LineTo rows dynamically before .Create
    .Create
End With
