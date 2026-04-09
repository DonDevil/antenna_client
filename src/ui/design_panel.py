"""Design-side controls for pipeline input, feedback, and export."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QGroupBox,
    QDoubleSpinBox,
    QFormLayout,
)
from PySide6.QtCore import Signal


FAMILY_QUALIFIER_DEFAULTS = {
    "amc_patch": {
        "patch_shape": "auto",
        "feed_type": "auto",
        "polarization": "unspecified",
    },
    "microstrip_patch": {
        "patch_shape": "rectangular",
        "feed_type": "edge",
        "polarization": "linear",
    },
    "wban_patch": {
        "patch_shape": "auto",
        "feed_type": "auto",
        "polarization": "unspecified",
    },
}


class DesignPanel(QWidget):
    """Widget for antenna design specifications"""

    design_changed = Signal(dict)
    start_pipeline_requested = Signal()
    reset_requested = Signal()
    export_requested = Signal()
    feedback_requested = Signal(dict)
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """Initialize design panel layout"""
        layout = QVBoxLayout(self)
        
        # Design specs group
        specs_group = QGroupBox("Design Specifications")
        specs_layout = QFormLayout()
        
        # Antenna family
        self.antenna_combo = QComboBox()
        self.antenna_combo.addItems(["amc_patch", "microstrip_patch", "wban_patch"])
        specs_layout.addRow("Antenna Type:", self.antenna_combo)

        self.patch_shape_combo = QComboBox()
        self.patch_shape_combo.addItems(["auto", "rectangular", "circular"])
        specs_layout.addRow("Patch Shape:", self.patch_shape_combo)

        self.feed_type_combo = QComboBox()
        self.feed_type_combo.addItems(["auto", "edge", "inset", "coaxial"])
        specs_layout.addRow("Feed Type:", self.feed_type_combo)

        self.polarization_combo = QComboBox()
        self.polarization_combo.addItems(["linear", "circular", "dual", "unspecified"])
        specs_layout.addRow("Polarization:", self.polarization_combo)

        # Chat behavior mode
        self.chat_mode_combo = QComboBox()
        self.chat_mode_combo.addItem("Speed (Intent Parse)", "speed")
        self.chat_mode_combo.addItem("Quality (Rich Chat)", "quality")
        specs_layout.addRow("Chat Mode:", self.chat_mode_combo)
        
        # Frequency
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.1, 100.0)
        self.freq_spin.setValue(2.4)
        self.freq_spin.setSuffix(" GHz")
        self.freq_spin.setSingleStep(0.1)
        specs_layout.addRow("Frequency:", self.freq_spin)
        
        # Bandwidth
        self.bw_spin = QDoubleSpinBox()
        self.bw_spin.setRange(1, 5000)
        self.bw_spin.setValue(100)
        self.bw_spin.setSuffix(" MHz")
        self.bw_spin.setSingleStep(10)
        specs_layout.addRow("Bandwidth:", self.bw_spin)
        
        specs_group.setLayout(specs_layout)
        layout.addWidget(specs_group)
        
        # Constraints group
        constraints_group = QGroupBox("Constraints")
        constraints_layout = QFormLayout()
        
        self.vswr_spin = QDoubleSpinBox()
        self.vswr_spin.setRange(1.0, 10.0)
        self.vswr_spin.setValue(1.5)
        self.vswr_spin.setSingleStep(0.1)
        constraints_layout.addRow("Max VSWR:", self.vswr_spin)
        
        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setRange(0, 20)
        self.gain_spin.setValue(6.0)
        self.gain_spin.setSuffix(" dBi")
        constraints_layout.addRow("Target Gain:", self.gain_spin)
        
        constraints_group.setLayout(constraints_layout)
        layout.addWidget(constraints_group)

        # Session info
        session_group = QGroupBox("Pipeline State")
        session_layout = QFormLayout()
        self.session_label = QLabel("-")
        self.trace_label = QLabel("-")
        self.stage_label = QLabel("Idle")
        self.command_count_label = QLabel("0")
        session_layout.addRow("Session ID:", self.session_label)
        session_layout.addRow("Trace ID:", self.trace_label)
        session_layout.addRow("Stage:", self.stage_label)
        session_layout.addRow("Commands:", self.command_count_label)
        session_group.setLayout(session_layout)
        layout.addWidget(session_group)

        # Feedback group
        feedback_group = QGroupBox("Simulation Feedback")
        feedback_layout = QFormLayout()

        self.fb_freq_spin = QDoubleSpinBox()
        self.fb_freq_spin.setRange(0.0, 100.0)
        self.fb_freq_spin.setDecimals(4)
        self.fb_freq_spin.setSuffix(" GHz")
        feedback_layout.addRow("Center Freq:", self.fb_freq_spin)

        self.fb_bw_spin = QDoubleSpinBox()
        self.fb_bw_spin.setRange(0.0, 5000.0)
        self.fb_bw_spin.setDecimals(2)
        self.fb_bw_spin.setSuffix(" MHz")
        feedback_layout.addRow("Bandwidth:", self.fb_bw_spin)

        self.fb_vswr_spin = QDoubleSpinBox()
        self.fb_vswr_spin.setRange(1.0, 100.0)
        self.fb_vswr_spin.setDecimals(2)
        self.fb_vswr_spin.setValue(1.5)
        feedback_layout.addRow("VSWR:", self.fb_vswr_spin)

        self.fb_gain_spin = QDoubleSpinBox()
        self.fb_gain_spin.setRange(-100.0, 100.0)
        self.fb_gain_spin.setDecimals(2)
        self.fb_gain_spin.setSuffix(" dBi")
        self.fb_gain_spin.setValue(0.0)
        feedback_layout.addRow("Gain:", self.fb_gain_spin)

        self.submit_feedback_btn = QPushButton("Submit Feedback")
        self.submit_feedback_btn.clicked.connect(self._emit_feedback_requested)
        feedback_layout.addRow(self.submit_feedback_btn)

        feedback_group.setLayout(feedback_layout)
        layout.addWidget(feedback_group)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        start_btn = QPushButton("Start Pipeline")
        reset_btn = QPushButton("Reset")
        export_btn = QPushButton("Export")
        start_btn.clicked.connect(self.start_pipeline_requested.emit)
        reset_btn.clicked.connect(self.reset_requested.emit)
        export_btn.clicked.connect(self.export_requested.emit)
        buttons_layout.addWidget(start_btn)
        buttons_layout.addWidget(reset_btn)
        buttons_layout.addWidget(export_btn)
        layout.addLayout(buttons_layout)
        
        self.antenna_combo.currentTextChanged.connect(self._on_antenna_family_changed)
        self.patch_shape_combo.currentTextChanged.connect(self._emit_design_changed)
        self.feed_type_combo.currentTextChanged.connect(self._emit_design_changed)
        self.polarization_combo.currentTextChanged.connect(self._emit_design_changed)
        self.freq_spin.valueChanged.connect(self._emit_design_changed)
        self.bw_spin.valueChanged.connect(self._emit_design_changed)
        self.vswr_spin.valueChanged.connect(self._emit_design_changed)
        self.gain_spin.valueChanged.connect(self._emit_design_changed)

        self._apply_family_defaults(self.antenna_combo.currentText())

        layout.addStretch()
    
    def reset_values(self):
        """Reset to default values"""
        self.antenna_combo.setCurrentText("amc_patch")
        self.chat_mode_combo.setCurrentIndex(0)
        self.freq_spin.setValue(2.4)
        self.bw_spin.setValue(100)
        self.vswr_spin.setValue(1.5)
        self.gain_spin.setValue(6.0)
        self.fb_freq_spin.setValue(0.0)
        self.fb_bw_spin.setValue(0.0)
        self.fb_vswr_spin.setValue(1.5)
        self.fb_gain_spin.setValue(0.0)
        self._apply_family_defaults(self.antenna_combo.currentText())
        self.set_session_metadata(None, None, "Idle", 0)

    def set_spec_values(
        self,
        *,
        frequency_ghz: float | None = None,
        bandwidth_mhz: float | None = None,
        antenna_family: str | None = None,
        patch_shape: str | None = None,
        feed_type: str | None = None,
        polarization: str | None = None,
    ) -> None:
        """Update fields from parsed chat or session state."""
        if antenna_family and antenna_family in [self.antenna_combo.itemText(i) for i in range(self.antenna_combo.count())]:
            self.antenna_combo.setCurrentText(antenna_family)
        self._set_combo_text(self.patch_shape_combo, patch_shape)
        self._set_combo_text(self.feed_type_combo, feed_type)
        self._set_combo_text(self.polarization_combo, polarization)
        if frequency_ghz is not None:
            self.freq_spin.setValue(max(self.freq_spin.minimum(), min(self.freq_spin.maximum(), float(frequency_ghz))))
        if bandwidth_mhz is not None:
            self.bw_spin.setValue(max(self.bw_spin.minimum(), min(self.bw_spin.maximum(), float(bandwidth_mhz))))

    def set_supported_families(self, families: list[str]) -> None:
        """Update antenna family options from server capabilities."""
        cleaned = [str(item).strip() for item in families if str(item).strip()]
        if not cleaned:
            return

        current = self.antenna_combo.currentText()
        self.antenna_combo.blockSignals(True)
        self.antenna_combo.clear()
        self.antenna_combo.addItems(cleaned)
        if current in cleaned:
            self.antenna_combo.setCurrentText(current)
        self.antenna_combo.blockSignals(False)

    def set_session_metadata(
        self,
        session_id: str | None,
        trace_id: str | None,
        stage: str,
        command_count: int,
    ) -> None:
        self.session_label.setText(session_id or "-")
        self.trace_label.setText(trace_id or "-")
        self.stage_label.setText(stage or "Idle")
        self.command_count_label.setText(str(command_count))

    def set_feedback_values(
        self,
        *,
        center_frequency_ghz: float | None = None,
        bandwidth_mhz: float | None = None,
        vswr: float | None = None,
        gain_dbi: float | None = None,
    ) -> None:
        """Prefill feedback controls from extracted CST metrics."""
        if center_frequency_ghz is not None:
            self.fb_freq_spin.setValue(max(self.fb_freq_spin.minimum(), min(self.fb_freq_spin.maximum(), float(center_frequency_ghz))))
        if bandwidth_mhz is not None:
            self.fb_bw_spin.setValue(max(self.fb_bw_spin.minimum(), min(self.fb_bw_spin.maximum(), float(bandwidth_mhz))))
        if vswr is not None:
            self.fb_vswr_spin.setValue(max(self.fb_vswr_spin.minimum(), min(self.fb_vswr_spin.maximum(), float(vswr))))
        if gain_dbi is not None:
            self.fb_gain_spin.setValue(max(self.fb_gain_spin.minimum(), min(self.fb_gain_spin.maximum(), float(gain_dbi))))

    def _emit_feedback_requested(self):
        self.feedback_requested.emit(self.get_feedback_values())

    def _on_antenna_family_changed(self, antenna_family: str) -> None:
        self._apply_family_defaults(antenna_family)
        self._emit_design_changed()

    def _apply_family_defaults(self, antenna_family: str) -> None:
        defaults = FAMILY_QUALIFIER_DEFAULTS.get(antenna_family, FAMILY_QUALIFIER_DEFAULTS["amc_patch"])
        self._set_combo_text(self.patch_shape_combo, defaults["patch_shape"])
        self._set_combo_text(self.feed_type_combo, defaults["feed_type"])
        self._set_combo_text(self.polarization_combo, defaults["polarization"])

    @staticmethod
    def _set_combo_text(combo: QComboBox, value: str | None) -> None:
        if value is None:
            return
        resolved = str(value).strip()
        if not resolved:
            return
        if combo.findText(resolved) >= 0:
            combo.setCurrentText(resolved)

    def _emit_design_changed(self):
        self.design_changed.emit(self.get_specs())
    
    def get_specs(self) -> dict:
        """Get current design specifications
        
        Returns:
            Dictionary with design specs
        """
        return {
            "antenna_family": self.antenna_combo.currentText(),
            "patch_shape": self.patch_shape_combo.currentText(),
            "feed_type": self.feed_type_combo.currentText(),
            "polarization": self.polarization_combo.currentText(),
            "frequency_ghz": self.freq_spin.value(),
            "bandwidth_mhz": self.bw_spin.value(),
            "constraints": {
                "max_vswr": self.vswr_spin.value(),
                "target_gain_dbi": self.gain_spin.value()
            }
        }

    def get_chat_mode(self) -> str:
        """Return selected chat endpoint behavior mode."""
        mode = self.chat_mode_combo.currentData()
        if mode in {"speed", "quality"}:
            return str(mode)
        return "speed"

    def get_feedback_values(self) -> dict:
        """Collect CST feedback values from the panel."""
        return {
            "actual_center_frequency_ghz": self.fb_freq_spin.value(),
            "actual_bandwidth_mhz": self.fb_bw_spin.value(),
            "actual_vswr": self.fb_vswr_spin.value(),
            "actual_gain_dbi": self.fb_gain_spin.value(),
        }
