"""
ResultExtractor - Extract and parse CST simulation results

Responsible for:
- Parse S11 data from CST exports
- Extract key metrics (center frequency, bandwidth, VSWR)
- Handle different export formats
"""

from typing import Dict, Optional, List, Tuple
import re
from utils.logger import get_logger


logger = get_logger(__name__)


class ResultExtractor:
    """Extract measurement data from CST results"""
    
    def extract_s11(self, result_file: str) -> Optional[Dict[str, any]]:
        """Extract S11 data from CST result file
        
        Args:
            result_file: Path to S11 result file
            
        Returns:
            Dictionary with S11 data or None if failed
        """
        try:
            # Parse S11 file (CSV or TXT format)
            frequencies = []
            s11_db = []
            
            # TODO: Implement actual file parsing
            # For now, return mock data
            logger.debug(f"Parsed S11 from: {result_file}")
            return {
                "frequencies": frequencies,
                "s11_db": s11_db,
                "file": result_file
            }
        except Exception as e:
            logger.error(f"Failed to extract S11: {e}")
            return None
    
    def extract_metrics(self, s11_data: Dict) -> Optional[Dict[str, float]]:
        """Extract key metrics from S11 data
        
        Args:
            s11_data: S11 data dictionary from extract_s11
            
        Returns:
            Dictionary with metrics or None if failed
        """
        try:
            # TODO: Implement actual metric extraction
            metrics = {
                "center_frequency_ghz": 2.4,
                "bandwidth_mhz": 50.0,
                "vswr": 1.5,
                "return_loss_db": -15.0,
                "gain_dbi": 6.0
            }
            logger.debug(f"Extracted metrics: {metrics}")
            return metrics
        except Exception as e:
            logger.error(f"Failed to extract metrics: {e}")
            return None
    
    def find_center_frequency(self, frequencies: List[float], s11_db: List[float]) -> float:
        """Find center frequency from S11 curve
        
        Args:
            frequencies: List of frequency points (GHz)
            s11_db: List of S11 magnitude (dB)
            
        Returns:
            Center frequency in GHz
        """
        if not frequencies or not s11_db:
            return 0.0
        
        # Find frequency with minimum S11 (best match)
        min_idx = s11_db.index(min(s11_db))
        center_freq = frequencies[min_idx]
        logger.debug(f"Center frequency: {center_freq} GHz")
        return center_freq
    
    def calculate_bandwidth(self, frequencies: List[float], s11_db: List[float], 
                          s11_threshold: float = -10) -> Tuple[float, Optional[float], Optional[float]]:
        """Calculate bandwidth from S11 curve
        
        Args:
            frequencies: List of frequency points (GHz)
            s11_db: List of S11 magnitude (dB)
            s11_threshold: S11 level for bandwidth definition (dB)
            
        Returns:
            Tuple of (bandwidth_mhz, start_freq_ghz, end_freq_ghz)
        """
        if not frequencies or not s11_db:
            return (0.0, None, None)
        
        # Find points where S11 < threshold
        in_band = [(f, s) for f, s in zip(frequencies, s11_db) if s < s11_threshold]
        
        if len(in_band) < 2:
            return (0.0, None, None)
        
        start_freq = in_band[0][0]
        end_freq = in_band[-1][0]
        bandwidth = (end_freq - start_freq) * 1000  # Convert GHz to MHz
        
        logger.debug(f"Bandwidth: {bandwidth} MHz ({start_freq}-{end_freq} GHz)")
        return (bandwidth, start_freq, end_freq)
    
    def calculate_vswr(self, s11_linear: float) -> float:
        """Calculate VSWR from S11 (linear)
        
        Args:
            s11_linear: S11 reflection coefficient (linear, 0-1)
            
        Returns:
            VSWR value
        """
        if s11_linear >= 1:
            return float('inf')
        
        vswr = (1 + s11_linear) / (1 - s11_linear)
        return vswr
    
    def calculate_return_loss(self, s11_db: float) -> float:
        """Return loss is negative S11 in dB
        
        Args:
            s11_db: S11 magnitude in dB
            
        Returns:
            Return loss value in dB
        """
        return -s11_db


class MeasurementValidator:
    """Validate measurement data"""
    
    @staticmethod
    def is_valid_frequency(freq_ghz: float) -> bool:
        """Check if frequency is valid
        
        Args:
            freq_ghz: Frequency in GHz
            
        Returns:
            True if valid
        """
        return 0.1 <= freq_ghz <= 300
    
    @staticmethod
    def is_valid_bandwidth(bw_mhz: float) -> bool:
        """Check if bandwidth is valid
        
        Args:
            bw_mhz: Bandwidth in MHz
            
        Returns:
            True if valid
        """
        return 1 <= bw_mhz <= 10000
    
    @staticmethod
    def is_valid_vswr(vswr: float) -> bool:
        """Check if VSWR is valid
        
        Args:
            vswr: VSWR value
            
        Returns:
            True if valid
        """
        return 1.0 <= vswr <= 50.0
