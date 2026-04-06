' Create excitation port
With Port
    .Reset
    .PortNumber {{port_number}}
    .Label "{{port_label}}"
    .Impedance {{impedance}}
    .XrangeA {{x_min}}
    .XrangeB {{x_max}}
    .YrangeA {{y_min}}
    .YrangeB {{y_max}}
    .ZrangeA {{z_min}}
    .ZrangeB {{z_max}}
    .Create
End With
