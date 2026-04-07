' Define rotated solid from profile point list
With Rotate
    .Reset
    .Name "{{name}}"
    .Component "{{component}}"
    .Material "{{material}}"
    .Mode "Pointlist"
    .StartAngle "{{start_angle}}"
    .Angle "{{angle}}"
    .Height "{{height}}"
    .RadiusRatio "{{radius_ratio}}"
    .NSteps "{{nsteps}}"
    .SplitClosedEdges "{{split_closed_edges}}"
    .SegmentedProfile "{{segmented_profile}}"
    .SimplifySolid "{{simplify_solid}}"
    .UseAdvancedSegmentedRotation "{{use_advanced_segmented_rotation}}"
    .CutEndOff "{{cut_end_off}}"
    .Origin "{{ox}}", "{{oy}}", "{{oz}}"
    .Rvector "{{rx}}", "{{ry}}", "{{rz}}"
    .Zvector "{{zx}}", "{{zy}}", "{{zz}}"
    ' Add .Point and .LineTo rows dynamically before .Create
    .Create
End With
