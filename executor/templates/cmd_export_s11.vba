' Export S11 results
With Result
    .ActivateTree "Schematic", "1D Results", "S-Parameters", "S11"
    .Plot
    .ExportFile "{{export_path}}"
End With
