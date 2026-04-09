"""CST Studio interface wrapper backed by the official CST Python API."""

from __future__ import annotations

import json
import math
import platform
import re
import time
from pathlib import Path
from typing import Optional

from utils.logger import get_logger


logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.json"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Failed to load CST config: {exc}")
        return {}


class CSTApp:
    """Thin wrapper over the CST design environment and active 3D project."""
    
    def __init__(self, executable_path: str = None, project_dir: str = None):
        self.executable_path = executable_path or r"C:\Program Files\CST Studio Suite 2024\CST Studio.exe"
        config = _load_config()
        configured_project_dir = config.get("cst", {}).get("project_dir")
        self.project_dir = Path(project_dir or configured_project_dir or (Path.home() / "CST Projects"))
        self.project_dir.mkdir(parents=True, exist_ok=True)

        self.app = None
        self.project = None
        self.mws = None
        self.connected = False
        self._history_counter = 0
        
        logger.info("CSTApp initialized")

    def _sync_project_handles(self) -> None:
        self.mws = self.project.model3d if self.project is not None else None

    def _refresh_active_project(self) -> None:
        if self.app is None:
            return
        try:
            self.project = self.app.active_project() if self.app.has_active_project() else self.project
            self._sync_project_handles()
        except Exception as exc:
            logger.debug(f"Failed to refresh active CST project handle: {exc}")

    def _resolve_artifact_path(self, destination_hint: str, extension: str) -> Path:
        safe_hint = "_".join(str(destination_hint).strip().split()) or "artifact"
        artifacts_dir = Path("artifacts") / "exports"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        return artifacts_dir / f"{safe_hint}.{extension.lstrip('.')}"

    @staticmethod
    def _normalize_history_title(title: str) -> str:
        raw = str(title or "").strip()
        if not raw:
            return "command"
        normalized = raw.replace("_", " ").replace(":", " ").strip()
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized[:80]
    
    def connect(self) -> bool:
        """Connect to a running CST design environment or create one."""
        if platform.system() != "Windows":
            logger.error("CST requires Windows")
            return False
        
        try:
            import cst.interface

            self.app = cst.interface.DesignEnvironment.connect_to_any_or_new()
            self.project = self.app.active_project() if self.app.has_active_project() else None
            self._sync_project_handles()
            self.connected = True
            if self.project is not None:
                logger.info(f"Connected to CST with active project: {self.project.filename()}")
            else:
                logger.info("Connected to CST without an active project")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to CST: {e}")
            return False
    
    def create_project(self, project_name: str) -> Optional[str]:
        """Create a new MWS project and persist it with the requested filename."""
        if not self.connected or self.app is None:
            logger.error("Not connected to CST")
            return None
        
        try:
            safe_name = "_".join(project_name.strip().split()) or "command_console_project"
            self.project = self.app.new_mws()
            self._sync_project_handles()
            project_path = self.project_dir / f"{safe_name}.cst"
            self.mws.SaveAs(str(project_path.resolve()), True)
            self._refresh_active_project()
            logger.info(f"Created project: {project_path}")
            return str(project_path.resolve())
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return None
    
    def open_project(self, project_path: str) -> bool:
        """Open an existing CST project file."""
        if not self.connected or self.app is None:
            logger.error("Not connected to CST")
            return False
        
        try:
            self.project = self.app.open_project(str(Path(project_path).resolve()))
            self._sync_project_handles()
            self._refresh_active_project()
            logger.info(f"Opened project: {project_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to open project: {e}")
            return False
    
    def execute_macro(self, macro_code: str, title: str = "command") -> bool:
        """Execute VBA macro by adding it to CST history and rebuilding."""
        for attempt in range(2):
            if not self.mws:
                self._refresh_active_project()
            if not self.mws:
                if attempt == 0 and self.connect():
                    self._refresh_active_project()
                if not self.mws:
                    logger.error("No active project")
                    return False

            try:
                self._refresh_active_project()
                if not self.mws:
                    logger.error("No active project after refresh")
                    return False
                self._history_counter += 1
                normalized = self._normalize_history_title(title)
                history_title = f"{self._history_counter:04d} | {normalized}"
                try:
                    self.mws.add_to_history(history_title, macro_code)
                except Exception as exc:
                    msg = str(exc).lower()
                    if normalized.startswith("define material") and "already exists" in msg:
                        logger.info("Material already exists; skipping redefinition")
                        return True
                    if "connection has been closed" in msg and attempt == 0:
                        logger.warning("CST connection dropped during macro execution; reconnecting and retrying once")
                        self.connected = False
                        self.project = None
                        self.mws = None
                        if self.connect():
                            self._refresh_active_project()
                            continue
                    raise
                self._refresh_active_project()
                logger.debug(f"Macro executed via CST history: {history_title}")
                return True
            except Exception as e:
                logger.error(f"Failed to execute macro: {e}")
                return False

        return False

    def run_simulation(self, timeout_sec: int = 600) -> bool:
        """Run solver using CST's model3d API."""
        self._refresh_active_project()
        if not self.mws:
            logger.error("No active project")
            return False
        try:
            timeout = int(timeout_sec) if timeout_sec else None
            self.mws.run_solver(timeout=timeout)
            self._refresh_active_project()
            return True
        except Exception as exc:
            logger.error(f"Failed to run simulation: {exc}")
            return False

    def rebuild_model(self, full_history: bool = False) -> bool:
        """Rebuild the active model outside of history macro execution."""
        self._refresh_active_project()
        if not self.mws:
            logger.error("No active project")
            return False
        try:
            if full_history:
                self.mws.full_history_rebuild()
            else:
                self.mws.Rebuild()
            self._refresh_active_project()
            return True
        except Exception as exc:
            logger.error(f"Failed to rebuild model: {exc}")
            return False

    def set_parameter(self, name: str, value: object, description: str | None = None, create_only: bool = False) -> bool:
        """Set a project parameter through CST's parameter API, not history macros."""
        self._refresh_active_project()
        if not self.mws:
            logger.error("No active project")
            return False

        parameter_name = str(name or "").strip()
        if not parameter_name:
            logger.error("Parameter name is required")
            return False

        text_value = str(value).strip()
        if not text_value:
            logger.error(f"Parameter value is required for '{parameter_name}'")
            return False

        try:
            if create_only:
                if description and hasattr(self.mws, "StoreParameterWithDescription"):
                    self.mws.StoreParameterWithDescription(parameter_name, text_value, str(description))
                else:
                    self.mws.StoreParameter(parameter_name, text_value)
            else:
                if isinstance(value, (int, float)) and hasattr(self.mws, "StoreDoubleParameter"):
                    self.mws.StoreDoubleParameter(parameter_name, float(value))
                else:
                    self.mws.StoreParameter(parameter_name, text_value)
            self._refresh_active_project()
            return True
        except Exception as exc:
            logger.error(f"Failed to set parameter '{parameter_name}': {exc}")
            return False

    def export_s_parameters(self, destination_hint: str = "s11") -> Optional[str]:
        """Export S-parameter 1D curve to ASCII from common result tree locations."""
        self._refresh_active_project()
        if not self.mws:
            logger.error("No active project")
            return None

        export_path = self._resolve_artifact_path(destination_hint, "txt")
        candidates: list[str] = []
        for _ in range(10):
            try:
                self._refresh_active_project()
                tree_items = list(self.mws.get_tree_items())
            except Exception:
                tree_items = []

            exact = [item for item in tree_items if item.startswith("1D Results\\S-Parameters\\")]
            if exact:
                candidates = exact
                break

            alt = [
                item
                for item in tree_items
                if item.startswith("1D Results\\Port signals\\") and item.lower().endswith("o1,1")
            ]
            if alt:
                candidates = alt
                break

            time.sleep(1.0)

        if not candidates:
            # Fallback to historical names if tree listing is sparse
            candidates = [
                r"1D Results\S-Parameters\S1,1",
                r"1D Results\S-Parameters\S(1,1)",
                r"1D Results\S-Parameters\SZmax(1),Zmax(1)",
                r"1D Results\Port signals\o1,1",
            ]

        for item in candidates:
            try:
                self.mws.SelectTreeItem(item)
                self.mws.StoreCurvesInASCIIFile(str(export_path.resolve()))
                if export_path.exists() and export_path.stat().st_size > 0:
                    logger.info(f"Exported S-parameters to {export_path}")
                    return str(export_path.resolve())
            except Exception as exc:
                logger.debug(f"S-parameter export candidate failed for '{item}': {exc}")
                continue

        logger.error(f"Failed to export S-parameters from candidate items: {candidates}")
        return None

    @staticmethod
    def _parse_frequency_ghz_from_item(item: str) -> Optional[float]:
        normalized = re.sub(r"(?<=\d)p(?=\d)", ".", item, flags=re.IGNORECASE)
        match = re.search(r"(?:f\s*=\s*)?([0-9]+(?:[\.,][0-9]+)?)\s*(ghz|mhz|khz|hz)?", normalized, flags=re.IGNORECASE)
        if not match:
            return None
        value = float(match.group(1).replace(",", "."))
        unit = (match.group(2) or "ghz").lower()
        if unit == "ghz":
            return value
        if unit == "mhz":
            return value / 1_000.0
        if unit == "khz":
            return value / 1_000_000.0
        return value / 1_000_000_000.0

    @staticmethod
    def _extract_summary_value(summary_text: str, label: str) -> Optional[float]:
        pattern = rf"{re.escape(label)}\s*:?\s*([-+]?\d+(?:\.\d+)?)"
        match = re.search(pattern, summary_text, flags=re.IGNORECASE)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _parse_theta_cut_points(theta_cut_text: str) -> list[tuple[float, float]]:
        points: list[tuple[float, float]] = []
        for raw in theta_cut_text.splitlines():
            line = raw.strip()
            if not line:
                continue
            parts = [p for p in line.replace(",", " ").split() if p]
            if len(parts) < 3:
                continue
            try:
                theta = float(parts[0])
                gain = float(parts[-1])
            except ValueError:
                continue
            points.append((theta, gain))
        return points

    @staticmethod
    def extract_farfield_metrics_from_files(
        summary_file: str,
        theta_cut_file: str,
        source_file: Optional[str] = None,
    ) -> Optional[dict]:
        summary_path = Path(summary_file)
        theta_cut_path = Path(theta_cut_file)
        source_path = Path(source_file) if source_file else None

        if not summary_path.exists():
            return None

        summary_text = summary_path.read_text(encoding="utf-8", errors="ignore")
        points: list[tuple[float, float]] = []
        if theta_cut_path.exists():
            theta_text = theta_cut_path.read_text(encoding="utf-8", errors="ignore")
            points = CSTApp._parse_theta_cut_points(theta_text)

        main_lobe_direction_deg = None
        max_cut_gain_dbi = None
        beamwidth_3db_deg = None
        back_theta = None
        back_gain = None
        front_to_back_ratio_db = None

        if points:
            max_idx = max(range(len(points)), key=lambda i: points[i][1])
            main_lobe_direction_deg = points[max_idx][0]
            max_cut_gain_dbi = points[max_idx][1]
            threshold = max_cut_gain_dbi - 3.0

            left = max_idx
            while left > 0 and points[left][1] >= threshold:
                left -= 1
            right = max_idx
            while right < len(points) - 1 and points[right][1] >= threshold:
                right += 1
            beamwidth_3db_deg = max(points[right][0] - points[left][0], 0.0)

            opposite_angle = (main_lobe_direction_deg + 180.0) % 360.0
            back_theta, back_gain = min(points, key=lambda p: abs(p[0] - opposite_angle))
            front_to_back_ratio_db = max_cut_gain_dbi - back_gain

        metrics = {
            "main_lobe_direction_deg": main_lobe_direction_deg,
            "beamwidth_3db_deg": beamwidth_3db_deg,
            "front_to_back_ratio_db": front_to_back_ratio_db,
            "max_gain_dbi": CSTApp._extract_summary_value(summary_text, "Maximum gain [dB]"),
            "max_realized_gain_dbi": CSTApp._extract_summary_value(summary_text, "Maximum realized gain [dB]"),
            "max_directivity_dbi": CSTApp._extract_summary_value(summary_text, "Maximum directivity [dB]"),
            "radiation_efficiency_db": CSTApp._extract_summary_value(summary_text, "Radiation efficiency"),
            "total_efficiency_db": CSTApp._extract_summary_value(summary_text, "Total efficiency"),
            "theta_cut_peak_gain_dbi": max_cut_gain_dbi,
            "theta_cut_back_gain_dbi": back_gain,
            "theta_cut_back_theta_deg": back_theta,
            "theta_cut_available": bool(points),
            "summary_file": str(summary_path.resolve()),
            "theta_cut_file": str(theta_cut_path.resolve()) if theta_cut_path.exists() else None,
            "source_file": str(source_path.resolve()) if source_path and source_path.exists() else None,
        }
        if not points:
            metrics["warning"] = (
                "Theta-cut export is unavailable. "
                "Summary-based far-field metrics were extracted without beamwidth/front-to-back values."
            )
        return metrics

    def extract_farfield_metrics(self, destination_hint: str = "farfield") -> Optional[dict]:
        source_path = self._resolve_artifact_path(destination_hint, "txt")
        summary_path = self._resolve_artifact_path(f"{destination_hint}_summary", "txt")
        cut_path = self._resolve_artifact_path(f"{destination_hint}_theta_cut", "txt")
        metrics_path = self._resolve_artifact_path(f"{destination_hint}_metrics", "json")

        metrics = self.extract_farfield_metrics_from_files(
            summary_file=str(summary_path),
            theta_cut_file=str(cut_path),
            source_file=str(source_path),
        )
        if not metrics:
            return None

        metrics["metrics_file"] = str(metrics_path.resolve())
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        return metrics

    def export_farfield(self, frequency_ghz: float = 2.4, destination_hint: str = "farfield") -> Optional[str]:
        """Export far-field artifacts using CST's dedicated FarfieldPlot API."""
        self._refresh_active_project()
        if not self.mws:
            logger.error("No active project")
            return None

        source_path = self._resolve_artifact_path(destination_hint, "txt")
        summary_path = self._resolve_artifact_path(f"{destination_hint}_summary", "txt")
        cut_path = self._resolve_artifact_path(f"{destination_hint}_theta_cut", "txt")
        metadata_path = self._resolve_artifact_path(f"{destination_hint}_meta", "json")

        try:
            tree_items = []
            for _ in range(10):
                self._refresh_active_project()
                tree_items = list(self.mws.get_tree_items())
                if any("farfield" in item.lower() for item in tree_items):
                    break
                time.sleep(1.0)
        except Exception as exc:
            logger.error(f"Unable to enumerate CST tree items for far-field export: {exc}")
            tree_items = []

        farfield_items = [
            item
            for item in tree_items
            if "farfield" in item.lower() and ("\\" in item or "/" in item)
        ]
        ranked: list[tuple[float, str]] = []
        for item in farfield_items:
            parsed = self._parse_frequency_ghz_from_item(item)
            score = abs(parsed - frequency_ghz) if parsed is not None else 1e9
            ranked.append((score, item))
        ranked.sort(key=lambda x: x[0])

        candidates = [item for _, item in ranked]
        if not candidates:
            candidates = [
                fr"Farfields\\farfield (f={frequency_ghz}GHz)",
                fr"2D/3D Results\\Farfields\\farfield (f={frequency_ghz}GHz)",
                r"Farfields\\farfield",
            ]

        for item in candidates:
            try:
                self.mws.SelectTreeItem(item)
                farfield_plot = self.mws.FarfieldPlot
                farfield_plot.SetFrequency(str(frequency_ghz))
                farfield_plot.ASCIIExportSummary(str(summary_path.resolve()))
                farfield_plot.ASCIIExportAsSource(str(source_path.resolve()))
                farfield_plot.SetPlotMode("directivity")
                farfield_plot.Vary("theta")
                farfield_plot.Phi("0")
                farfield_plot.Step("5")
                farfield_plot.Plot()
                theta_cut_exported = False
                theta_cut_error = None
                try:
                    cut_name = f"{destination_hint}_theta_cut"
                    farfield_plot.CopyFarfieldTo1DResults(r"1D Results\Farfields", cut_name)
                    cut_candidates = [
                        rf"1D Results\1D Results\Farfields\{cut_name}",
                        rf"1D Results\Farfields\{cut_name}",
                    ]
                    for cut_tree_item in cut_candidates:
                        try:
                            self.mws.SelectTreeItem(cut_tree_item)
                            self.mws.StoreCurvesInASCIIFile(str(cut_path.resolve()))
                            if cut_path.exists() and cut_path.stat().st_size > 0:
                                theta_cut_exported = True
                                break
                        except Exception:
                            continue
                    if not theta_cut_exported:
                        theta_cut_error = "Theta-cut copy/export did not produce a curve file"
                except Exception as exc:
                    theta_cut_error = str(exc)
                    logger.warning(f"Far-field theta-cut export unavailable for '{item}': {exc}")

                if source_path.exists() and source_path.stat().st_size > 0:
                    farfield_metrics = self.extract_farfield_metrics(destination_hint=destination_hint)
                    metadata = {
                        "requested_frequency_ghz": frequency_ghz,
                        "selected_tree_item": item,
                        "source_export_path": str(source_path.resolve()),
                        "summary_export_path": str(summary_path.resolve()),
                        "theta_cut_export_path": str(cut_path.resolve()) if theta_cut_exported else None,
                        "theta_cut_exported": theta_cut_exported,
                        "theta_cut_error": theta_cut_error,
                        "metrics_export_path": (
                            str(Path(farfield_metrics["metrics_file"]).resolve())
                            if farfield_metrics and farfield_metrics.get("metrics_file")
                            else None
                        ),
                    }
                    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
                    logger.info(f"Exported far-field data to {source_path} from {item}")
                    return str(source_path.resolve())
            except Exception:
                continue

        logger.error(
            "Failed to export far-field data. "
            f"Candidates checked: {candidates}. "
            "Ensure a far-field monitor exists and simulation has completed."
        )
        return None

    @staticmethod
    def extract_summary_metrics(sparam_file: str) -> Optional[dict]:
        """Extract resonance metrics from ASCII S-parameter export.

        Supports both:
        - two-column format: frequency, S11_dB
        - CST XY complex format: frequency, real, imag, ...
        """
        path = Path(sparam_file)
        if not path.exists():
            return None

        freq = []
        s11_db = []
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue
            parts = [p for p in line.replace(",", " ").split() if p]
            if len(parts) < 2:
                continue
            try:
                f = float(parts[0])
                if len(parts) >= 3:
                    real = float(parts[1])
                    imag = float(parts[2])
                    mag = (real * real + imag * imag) ** 0.5
                    mag = max(mag, 1e-12)
                    v = 20.0 * math.log10(mag)
                else:
                    v = float(parts[1])
            except ValueError:
                continue
            freq.append(f)
            s11_db.append(v)

        if not freq:
            return None

        # Convert frequency to GHz when source is MHz/Hz scale.
        max_freq = max(freq)
        if max_freq > 1000.0:
            freq = [f / 1_000_000_000.0 for f in freq]
        elif max_freq > 100.0:
            freq = [f / 1000.0 for f in freq]

        min_idx = min(range(len(s11_db)), key=lambda i: s11_db[i])
        center = freq[min_idx]

        threshold = -10.0
        in_band = [i for i, value in enumerate(s11_db) if value <= threshold]
        if len(in_band) >= 2:
            # Keep only contiguous -10 dB region around the resonance dip.
            dip_index_set = set(in_band)
            left = min_idx
            while (left - 1) in dip_index_set:
                left -= 1
            right = min_idx
            while (right + 1) in dip_index_set:
                right += 1
            start = freq[left]
            stop = freq[right]
            bandwidth = max(stop - start, 0.0)
        else:
            start = stop = center
            bandwidth = 0.0

        return {
            "center_frequency": center,
            "bandwidth": bandwidth,
            "min_s11_db": s11_db[min_idx],
            "start_freq": start,
            "stop_freq": stop,
            "sample_count": len(freq),
        }
    
    def get_project_path(self) -> Optional[str]:
        """Get the currently open CST project path."""
        if self.project is None:
            return None
        
        try:
            return str(self.project.filename())
        except Exception as e:
            logger.error(f"Failed to get project path: {e}")
            return None
    
    def close_project(self, save: bool = False) -> bool:
        """Close the active project."""
        if self.project is None:
            return True
        
        try:
            if save:
                self.project.save()
            self.project.close()
            self.project = None
            self.mws = None
            logger.info("Project closed")
            return True
        except Exception as e:
            logger.error(f"Failed to close project: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from CST and release handles."""
        try:
            self.close_project(save=False)
            if self.app is not None:
                try:
                    self.app.close()
                except Exception:
                    pass
            self.app = None
            self.project = None
            self.connected = False
            logger.info("Disconnected from CST")
            return True
        except Exception as e:
            logger.error(f"Failed to disconnect: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to CST
        
        Returns:
            True if connected
        """
        return self.connected and self.app is not None
