' Create new CST project
With Project
    .Reset
    .Name "{{project_name}}"
    .Frequency "{{frequency_unit}}"
    .Create
End With
