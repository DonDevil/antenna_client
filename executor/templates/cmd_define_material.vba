' Define material
With Material
    .Reset
    .Name "{{material_name}}"
    .Folder ""
    .Epsilon {{epsilon_r}}
    .TangentD {{loss_tangent}}
    .Mu {{mu_r}}
    .Rho {{rho}}
    .Create
End With
