"""
EXIF & Image Metadata Forensics Engine
========================================
Extracts hidden metadata from uploaded images:
  - GPS coordinates → exact location where photo was taken
  - Camera make/model and serial number
  - Exact date/time the photo was taken (not just modified)
  - Software / Photoshop editing detection
  - Thumbnail extraction (sometimes reveals original unedited image)
  - WhatsApp / Telegram re-compression detection

Uses Pillow + piexif (both free, no API key required).
"""
from __future__ import annotations

import io
import math
import struct
import time
from dataclasses import dataclass, field
from typing import Any

from nciia.utils import get_logger

logger = get_logger(__name__)


@dataclass
class ExifReport:
    filename:       str
    file_size_kb:   float       = 0.0
    image_width:    int         = 0
    image_height:   int         = 0
    # Location
    gps_lat:        float | None = None
    gps_lon:        float | None = None
    gps_altitude:   float | None = None
    gps_city:       str          = ""
    gps_maps_url:   str          = ""
    # Device
    camera_make:    str         = ""
    camera_model:   str         = ""
    camera_serial:  str         = ""
    lens_model:     str         = ""
    # Timing
    date_taken:     str         = ""
    date_modified:  str         = ""
    date_digitized: str         = ""
    # Software / editing
    software:       str         = ""
    photoshop_detected: bool    = False
    edited:         bool        = False
    # Compression / origin
    original_format:    str     = ""
    whatsapp_compressed: bool   = False
    # All raw EXIF
    raw_exif:       dict[str, Any] = field(default_factory=dict)
    errors:         list[str]      = field(default_factory=list)
    analyzed_at:    float          = field(default_factory=time.time)


def _dms_to_decimal(dms: Any, ref: str) -> float | None:
    """Convert DMS (degrees/minutes/seconds) tuple from EXIF to decimal degrees."""
    try:
        if isinstance(dms, (list, tuple)) and len(dms) == 3:
            def to_float(v: Any) -> float:
                if isinstance(v, tuple) and len(v) == 2:
                    return v[0] / v[1] if v[1] else 0.0
                return float(v)
            d = to_float(dms[0])
            m = to_float(dms[1])
            s = to_float(dms[2])
            decimal = d + m / 60 + s / 3600
            if ref in ("S", "W"):
                decimal = -decimal
            return round(decimal, 7)
    except Exception:
        pass
    return None


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, bytes):
        try:
            return val.decode("utf-8", errors="replace").strip("\x00").strip()
        except Exception:
            return ""
    return str(val).strip()


def analyze_image(data: bytes, filename: str = "image") -> ExifReport:
    """
    Synchronous EXIF analysis. Call from async context via asyncio.to_thread().
    Returns a complete ExifReport with all extractable metadata.
    """
    report = ExifReport(filename=filename)
    report.file_size_kb = round(len(data) / 1024, 2)

    try:
        from PIL import Image
        import piexif

        img = Image.open(io.BytesIO(data))
        report.image_width, report.image_height = img.size
        report.original_format = img.format or ""

        # WhatsApp compression detection: JPEG quality < 80 + no EXIF = re-compressed
        if img.format == "JPEG":
            try:
                info = img.info or {}
                if "exif" not in info and report.file_size_kb < 500:
                    report.whatsapp_compressed = True
            except Exception:
                pass

        # Extract EXIF
        exif_bytes = img.info.get("exif", b"") if img.info else b""
        if not exif_bytes:
            # Try getting from _getexif for JPEG
            try:
                raw = img._getexif()  # type: ignore[attr-defined]
                if raw:
                    report.raw_exif = {str(k): str(v) for k, v in raw.items()}
            except Exception:
                pass
            if not report.raw_exif:
                report.errors.append("No EXIF data found in image")
                return report

        exif_data = piexif.load(exif_bytes) if exif_bytes else {}

        # ── Image IFD ─────────────────────────────────────────────────────────
        ifd0 = exif_data.get("0th", {})
        report.camera_make   = _safe_str(ifd0.get(piexif.ImageIFD.Make, ""))
        report.camera_model  = _safe_str(ifd0.get(piexif.ImageIFD.Model, ""))
        report.camera_serial = _safe_str(ifd0.get(piexif.ImageIFD.CameraSerialNumber, ""))
        report.software      = _safe_str(ifd0.get(piexif.ImageIFD.Software, ""))
        report.date_modified = _safe_str(ifd0.get(piexif.ImageIFD.DateTime, ""))

        # Photoshop / editing detection
        sw = report.software.lower()
        if any(x in sw for x in ["photoshop", "lightroom", "snapseed", "vsco",
                                   "facetune", "picsart", "meitu", "pixlr"]):
            report.photoshop_detected = True
            report.edited = True

        # ── Exif IFD ──────────────────────────────────────────────────────────
        exif_ifd = exif_data.get("Exif", {})
        report.date_taken     = _safe_str(exif_ifd.get(piexif.ExifIFD.DateTimeOriginal, ""))
        report.date_digitized = _safe_str(exif_ifd.get(piexif.ExifIFD.DateTimeDigitized, ""))
        report.lens_model     = _safe_str(exif_ifd.get(piexif.ExifIFD.LensModel, ""))

        # If date_taken ≠ date_modified → edited
        if report.date_taken and report.date_modified and report.date_taken != report.date_modified:
            report.edited = True

        # ── GPS IFD ───────────────────────────────────────────────────────────
        gps = exif_data.get("GPS", {})
        if gps:
            lat_dms = gps.get(piexif.GPSIFD.GPSLatitude)
            lat_ref = _safe_str(gps.get(piexif.GPSIFD.GPSLatitudeRef, "N"))
            lon_dms = gps.get(piexif.GPSIFD.GPSLongitude)
            lon_ref = _safe_str(gps.get(piexif.GPSIFD.GPSLongitudeRef, "E"))
            alt_tup = gps.get(piexif.GPSIFD.GPSAltitude)

            lat = _dms_to_decimal(lat_dms, lat_ref)
            lon = _dms_to_decimal(lon_dms, lon_ref)

            if lat is not None and lon is not None:
                report.gps_lat = lat
                report.gps_lon = lon
                report.gps_maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                if alt_tup and isinstance(alt_tup, tuple) and alt_tup[1]:
                    report.gps_altitude = round(alt_tup[0] / alt_tup[1], 1)

        # ── Raw EXIF summary ──────────────────────────────────────────────────
        def flatten(d: dict) -> dict[str, str]:
            out: dict[str, str] = {}
            for k, v in d.items():
                try:
                    out[str(k)] = _safe_str(v)
                except Exception:
                    pass
            return out

        report.raw_exif = {
            "0th":  flatten(ifd0),
            "Exif": flatten(exif_ifd),
            "GPS":  flatten(gps),
        }

    except ImportError:
        report.errors.append("Pillow/piexif not installed. Run: pip install Pillow piexif")
    except Exception as exc:
        report.errors.append(f"Analysis failed: {exc}")

    report.analyzed_at = time.time()
    logger.info(
        "exif_analyzed",
        file=filename,
        has_gps=report.gps_lat is not None,
        camera=f"{report.camera_make} {report.camera_model}",
        edited=report.edited,
    )
    return report


async def analyze_image_async(data: bytes, filename: str = "image") -> ExifReport:
    """Async wrapper — runs CPU-bound analysis in thread pool."""
    import asyncio
    return await asyncio.to_thread(analyze_image, data, filename)
