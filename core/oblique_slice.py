"""Oblique plane definition and slice extraction for cardiac view planning."""

from dataclasses import dataclass
from typing import Tuple, Optional, NamedTuple
import numpy as np
from scipy.ndimage import map_coordinates


class P4CHPlaneResult(NamedTuple):
    """Result from P4CH plane creation, including rotation optimization info."""
    plane: 'ObliquePlane'
    rotation_axis: np.ndarray  # Long axis (rotation axis)
    base_normal: np.ndarray    # Normal at 0 degrees
    base_u_axis: np.ndarray    # U-axis at 0 degrees


def normalize(v: np.ndarray) -> np.ndarray:
    """Normalize a vector to unit length."""
    norm = np.linalg.norm(v)
    if norm < 1e-10:
        return v
    return v / norm


@dataclass
class ObliquePlane:
    """Definition of an oblique plane in 3D volume space.

    The plane is defined by:
    - origin: center point of the slice in volume coordinates (x, y, z)
    - u_axis: unit vector for horizontal axis of the 2D slice
    - v_axis: unit vector for vertical axis of the 2D slice
    - normal: unit normal vector (should be u_axis × v_axis)
    - width, height: output image dimensions in pixels
    """
    origin: np.ndarray      # 3D point (x, y, z) - center of the slice
    u_axis: np.ndarray      # Unit vector for horizontal axis
    v_axis: np.ndarray      # Unit vector for vertical axis
    normal: np.ndarray      # Unit normal vector (u × v)
    width: int              # Output image width in pixels
    height: int             # Output image height in pixels

    def map_2d_to_3d(self, x2d: float, y2d: float, offset: float = 0.0) -> Tuple[float, float, float]:
        """Convert 2D slice coordinates to 3D volume coordinates.

        Args:
            x2d: Horizontal position in slice (0 = left edge, width = right edge)
            y2d: Vertical position in slice (0 = top edge, height = bottom edge)
            offset: Distance along normal from origin (for scrolling)

        Returns:
            (x, y, z) in volume coordinates
        """
        # Convert from pixel coords (0 to width/height) to centered coords
        u = x2d - self.width / 2
        v = y2d - self.height / 2

        # Calculate 3D position
        pos = self.origin + u * self.u_axis + v * self.v_axis + offset * self.normal
        return (float(pos[0]), float(pos[1]), float(pos[2]))

    def map_3d_to_2d(self, x: float, y: float, z: float,
                     tolerance: float = 5.0) -> Optional[Tuple[float, float]]:
        """Project 3D point to 2D slice coordinates.

        Args:
            x, y, z: 3D volume coordinates
            tolerance: Maximum distance from plane to consider point visible

        Returns:
            (x2d, y2d) in slice coordinates, or None if point is not near the plane
        """
        point = np.array([x, y, z])

        # Vector from origin to point
        diff = point - self.origin

        # Distance from plane
        dist = np.abs(np.dot(diff, self.normal))
        if dist > tolerance:
            return None

        # Project to 2D
        u = np.dot(diff, self.u_axis)
        v = np.dot(diff, self.v_axis)

        # Convert to pixel coordinates
        x2d = u + self.width / 2
        y2d = v + self.height / 2

        return (float(x2d), float(y2d))

    def with_offset(self, offset: float) -> 'ObliquePlane':
        """Create a new plane parallel to this one, shifted by offset along normal."""
        return ObliquePlane(
            origin=self.origin + offset * self.normal,
            u_axis=self.u_axis.copy(),
            v_axis=self.v_axis.copy(),
            normal=self.normal.copy(),
            width=self.width,
            height=self.height
        )


def extract_oblique_slice(volume: np.ndarray, plane: ObliquePlane,
                          offset: float = 0.0) -> np.ndarray:
    """Extract an arbitrary oblique slice from a 3D volume.

    Args:
        volume: 3D numpy array in (z, y, x) order
        plane: ObliquePlane defining the slice orientation and position
        offset: Distance along normal from plane origin (for scrolling)

    Returns:
        2D numpy array of shape (height, width)
    """
    # Create sampling grid in plane coordinates
    # u goes from -width/2 to +width/2, v goes from -height/2 to +height/2
    u_coords = np.arange(plane.width) - plane.width / 2
    v_coords = np.arange(plane.height) - plane.height / 2
    uu, vv = np.meshgrid(u_coords, v_coords)

    # Apply offset along normal
    origin = plane.origin + offset * plane.normal

    # Convert to 3D volume coordinates
    # point_3d = origin + u * u_axis + v * v_axis
    x_coords = origin[0] + uu * plane.u_axis[0] + vv * plane.v_axis[0]
    y_coords = origin[1] + uu * plane.u_axis[1] + vv * plane.v_axis[1]
    z_coords = origin[2] + uu * plane.u_axis[2] + vv * plane.v_axis[2]

    # Stack for scipy interpolation
    # Volume is in (z, y, x) order, so coords should be [z, y, x]
    coords = np.array([z_coords, y_coords, x_coords])

    # Interpolate using linear interpolation
    slice_data = map_coordinates(volume, coords, order=1, mode='constant', cval=0)

    return slice_data


def create_p2ch_plane_from_axial_line(
    line_x1: float, line_y1: float, line_x2: float, line_y2: float,
    axial_slice_z: float, volume_shape: Tuple[int, int, int]
) -> ObliquePlane:
    """Create pseudo-2ch plane from a line segment on the axial view.

    The p2ch plane is perpendicular to the axial plane and passes through
    the line segment. The viewing direction looks along the line.

    Args:
        line_x1, line_y1: First endpoint of line in volume (x, y) coords
        line_x2, line_y2: Second endpoint of line in volume (x, y) coords
        axial_slice_z: Z-index of the axial slice where line was drawn
        volume_shape: (z_dim, y_dim, x_dim) shape of volume

    Returns:
        ObliquePlane for the pseudo-2ch view
    """
    z_dim, y_dim, x_dim = volume_shape

    # Line direction in XY plane
    line_dir = np.array([line_x2 - line_x1, line_y2 - line_y1, 0.0])
    line_dir = normalize(line_dir)

    # Normal is PERPENDICULAR to line direction in XY plane
    # This makes the plane CONTAIN the line (pass through it)
    # We look at the line from the side, not along it
    normal = np.array([-line_dir[1], line_dir[0], 0.0])
    normal = normalize(normal)

    # U-axis: along the line direction, so the line appears horizontal in the view
    u_axis = line_dir

    # V-axis: Z direction (up in the body, but negative so superior is up in display)
    v_axis = np.array([0.0, 0.0, -1.0])

    # Origin: midpoint of line, centered in Z
    origin = np.array([
        (line_x1 + line_x2) / 2,
        (line_y1 + line_y2) / 2,
        z_dim / 2  # Center in Z for full coverage
    ])

    # Calculate appropriate dimensions
    # Width: span perpendicular to line (use max of x_dim, y_dim for safety)
    # Height: full Z range
    width = int(max(x_dim, y_dim) * 1.5)
    height = z_dim

    return ObliquePlane(
        origin=origin,
        u_axis=u_axis,
        v_axis=v_axis,
        normal=normal,
        width=width,
        height=height
    )


def create_p4ch_plane_from_p2ch_line(
    line_2d_x1: float, line_2d_y1: float, line_2d_x2: float, line_2d_y2: float,
    p2ch_plane: ObliquePlane, volume_shape: Tuple[int, int, int],
    rotation_degrees: float = 0.0,
    rotation_mode: str = "long_axis",
    return_rotation_info: bool = False
):
    """Create pseudo-4ch plane from a line segment on the p2ch view.

    The p4ch plane passes through the first endpoint of the line (valve point)
    and contains the long axis. The plane can be rotated around the long axis
    using rotation_degrees.

    Line convention: point 1 = valve (mid-valve), point 2 = apex
    The long axis L goes from valve to apex.

    Args:
        line_2d_x1, line_2d_y1: First endpoint (VALVE) in p2ch 2D coordinates
        line_2d_x2, line_2d_y2: Second endpoint (APEX) in p2ch 2D coordinates
        p2ch_plane: The ObliquePlane of the p2ch view
        volume_shape: (z_dim, y_dim, x_dim) shape of volume
        rotation_degrees: Rotation angle around long axis
        rotation_mode: Either 'long_axis' (default) or 'perp_p2ch'
            - 'long_axis': 0° = same viewing direction as p2ch
            - 'perp_p2ch': 0° = perpendicular to p2ch plane
        return_rotation_info: If True, return P4CHPlaneResult with rotation info
            for optimized local rotation computation

    Returns:
        ObliquePlane for the pseudo-4ch view, or P4CHPlaneResult if return_rotation_info=True
    """
    z_dim, y_dim, x_dim = volume_shape

    # Convert 2D line endpoints to 3D
    # Point 1 = valve, Point 2 = apex
    valve_3d = np.array(p2ch_plane.map_2d_to_3d(line_2d_x1, line_2d_y1))
    apex_3d = np.array(p2ch_plane.map_2d_to_3d(line_2d_x2, line_2d_y2))

    # Long axis direction: from valve to apex
    long_axis = normalize(apex_3d - valve_3d)

    # Determine base normal based on rotation mode
    if rotation_mode == "perp_p2ch":
        # Mode: perpendicular to p2ch at 0°
        # Base normal is perpendicular to both p2ch normal and long axis
        base_normal = normalize(np.cross(p2ch_plane.normal, long_axis))
    else:
        # Mode: rotate around long axis (default)
        # Base normal is p2ch normal projected onto the plane perpendicular to long axis
        # This makes 0° = same viewing direction as p2ch
        proj = p2ch_plane.normal - np.dot(p2ch_plane.normal, long_axis) * long_axis
        if np.linalg.norm(proj) < 1e-6:
            # Edge case: p2ch normal is parallel to long axis
            # Fall back to perpendicular mode
            base_normal = normalize(np.cross(p2ch_plane.normal, long_axis))
        else:
            base_normal = normalize(proj)

    # Apply rotation around long axis using Rodrigues' formula
    # v_rot = v*cos(θ) + (k×v)*sin(θ) + k*(k·v)*(1-cos(θ))
    # where k = long_axis, v = base_normal
    theta = np.radians(rotation_degrees)
    cos_t = np.cos(theta)
    sin_t = np.sin(theta)

    # Since base_normal ⊥ long_axis, the (k·v) term is 0
    p4ch_normal = base_normal * cos_t + np.cross(long_axis, base_normal) * sin_t
    p4ch_normal = normalize(p4ch_normal)

    # V-axis: along the long axis (so heart appears vertical in image)
    # Want apex at bottom, valve at top (superior)
    v_axis = -long_axis  # Negative so valve (superior) is at top

    # U-axis: perpendicular to both v_axis and normal (horizontal in image)
    u_axis = normalize(np.cross(v_axis, p4ch_normal))

    # Compute base u_axis (at 0 degrees) for rotation optimization
    base_u_axis = normalize(np.cross(v_axis, base_normal))

    # Origin: valve point (the plane passes through valve)
    origin = valve_3d.copy()

    # Dimensions similar to p2ch
    width = int(max(x_dim, y_dim) * 1.5)
    height = z_dim

    plane = ObliquePlane(
        origin=origin,
        u_axis=u_axis,
        v_axis=v_axis,
        normal=p4ch_normal,
        width=width,
        height=height
    )

    if return_rotation_info:
        return P4CHPlaneResult(
            plane=plane,
            rotation_axis=long_axis,
            base_normal=base_normal,
            base_u_axis=base_u_axis
        )

    return plane


def create_sax_plane_from_p4ch_line(
    line_2d_x1: float, line_2d_y1: float, line_2d_x2: float, line_2d_y2: float,
    p4ch_plane: ObliquePlane, volume_shape: Tuple[int, int, int]
) -> ObliquePlane:
    """Create short-axis (SAX) plane from a line segment on the p4ch view.

    The SAX plane is perpendicular to BOTH the line direction AND the p4ch plane.
    This line typically represents the long axis of the heart.

    Args:
        line_2d_x1, line_2d_y1: First endpoint in p4ch 2D coordinates
        line_2d_x2, line_2d_y2: Second endpoint in p4ch 2D coordinates
        p4ch_plane: The ObliquePlane of the p4ch view
        volume_shape: (z_dim, y_dim, x_dim) shape of volume

    Returns:
        ObliquePlane for the short-axis view
    """
    z_dim, y_dim, x_dim = volume_shape

    # Convert 2D line endpoints to 3D
    p1_3d = np.array(p4ch_plane.map_2d_to_3d(line_2d_x1, line_2d_y1))
    p2_3d = np.array(p4ch_plane.map_2d_to_3d(line_2d_x2, line_2d_y2))

    # Line direction in 3D (this is the long axis of the heart)
    line_dir_3d = normalize(p2_3d - p1_3d)

    # SAX normal: along the line direction (perpendicular to short axis plane)
    sax_normal = line_dir_3d

    # U-axis and V-axis: perpendicular to normal
    # Use p4ch's u_axis as reference, project out the normal component
    ref = p4ch_plane.u_axis
    u_axis = ref - np.dot(ref, sax_normal) * sax_normal
    if np.linalg.norm(u_axis) < 1e-6:
        # If parallel, use v_axis instead
        ref = p4ch_plane.v_axis
        u_axis = ref - np.dot(ref, sax_normal) * sax_normal
    u_axis = normalize(u_axis)

    # V-axis: perpendicular to both
    v_axis = normalize(np.cross(sax_normal, u_axis))

    # Origin: midpoint of line
    origin = (p1_3d + p2_3d) / 2

    # SAX slices are typically more square
    size = int(max(x_dim, y_dim) * 1.2)

    return ObliquePlane(
        origin=origin,
        u_axis=u_axis,
        v_axis=v_axis,
        normal=sax_normal,
        width=size,
        height=size
    )
