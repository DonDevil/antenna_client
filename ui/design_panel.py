"""
DesignPanel - Design specifications and antenna parameters display

Responsible for:
- Current design specs display
- Antenna family selector
- Frequency/bandwidth input fields
- Constraints editor
- Quick-action buttons
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QGroupBox, QSpinBox, QDoubleSpinBox,
    QFormLayout
)
from PySide6.QtCore import Qt, Signal


class DesignPanel(QWidget):
    """Widget for antenna design specifications"""
    
    design_changed = Signal(dict)
    
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
        self.antenna_combo.addItems(["Patch", "Helical", "Horn", "Log Periodic"])
        specs_layout.addRow("Antenna Type:", self.antenna_combo)
        
        # Frequency
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.1, 300)
        self.freq_spin.setValue(2.4)
        self.freq_spin.setSuffix(" GHz")
        self.freq_spin.setSingleStep(0.1)
        specs_layout.addRow("Frequency:", self.freq_spin)
        
        # Bandwidth
        self.bw_spin = QDoubleSpinBox()
        self.bw_spin.setRange(1, 10000)
        self.bw_spin.setValue(50)
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
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        reset_btn = QPushButton("Reset")
        export_btn = QPushButton("Export")
        reset_btn.clicked.connect(self.reset_values)
        buttons_layout.addWidget(reset_btn)
        buttons_layout.addWidget(export_btn)
        layout.addLayout(buttons_layout)
        
        layout.addStretch()
    
    def reset_values(self):
        """Reset to default values"""
        self.freq_spin.setValue(2.4)
        self.bw_spin.setValue(50)
    
    def get_specs(self) -> dict:
        """Get current design specifications
        
        Returns:
            Dictionary with design specs
        """
        return {
            "antenna_family": self.antenna_combo.currentText().lower(),
            "frequency_ghz": self.freq_spin.value(),
            "bandwidth_mhz": self.bw_spin.value(),
            "constraints": {
                "max_vswr": self.vswr_spin.value(),
                "target_gain_dbi": self.gain_spin.value()
            }
        }
