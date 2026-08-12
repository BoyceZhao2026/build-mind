from __future__ import annotations

from dataclasses import dataclass

import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import snap, split, unary_union

from .geometry_models import (
    GeometryCheck,
    GeometryOperationResult,
    Point2D,
    PolygonGeometry,
    SegmentGeometry,
    ToleranceProfile,
)


@dataclass(frozen=True)
class KernelPolygon:
    entity_id: str
    geometry: Polygon


class GeometryKernel:
    """Adapter boundary around Shapely; domain code never exposes GEOS objects."""

    engine_name = "shapely"
    engine_version = shapely.__version__

    @staticmethod
    def _polygon(value: PolygonGeometry) -> Polygon:
        return Polygon([(point.x, point.y) for point in value.points])

    @staticmethod
    def _segment(value: SegmentGeometry) -> LineString:
        return LineString([(value.start.x, value.start.y), (value.end.x, value.end.y)])

    @staticmethod
    def _dto(value: Polygon) -> PolygonGeometry:
        # Shapely closes polygon rings; the API stores each vertex only once.
        return PolygonGeometry(
            points=[Point2D(x=float(x), y=float(y)) for x, y in list(value.exterior.coords)[:-1]]
        )

    def split_region(
        self,
        region_id: str,
        region_value: PolygonGeometry,
        splitter_id: str,
        splitter_value: SegmentGeometry,
        tolerance: ToleranceProfile,
    ) -> GeometryOperationResult:
        region = self._polygon(region_value)
        splitter = self._segment(splitter_value)
        checks: list[GeometryCheck] = []

        checks.append(GeometryCheck(
            check="original_region_valid",
            passed=bool(region.is_valid and not region.is_empty and region.area > 0),
            detail="原区域必须是非空、无自相交的有效多边形",
        ))
        if not checks[-1].passed:
            return self._failure(region_id, splitter_id, tolerance, checks, "原区域不是有效多边形")

        snap_distance = tolerance.boundary_snap_ratio
        snapped_splitter = snap(splitter, region.boundary, snap_distance)
        boundary_hits = snapped_splitter.intersection(region.boundary)
        hit_count = self._point_count(boundary_hits)
        checks.append(GeometryCheck(
            check="splitter_intersects_boundary_twice",
            passed=hit_count >= 2,
            detail=f"辅助线与原区域边界检测到 {hit_count} 个交点",
            measured_value=float(hit_count),
            allowed_value=2,
        ))
        if hit_count < 2:
            return self._failure(region_id, splitter_id, tolerance, checks, "辅助线没有完整穿过目标区域")

        try:
            collection = split(region, snapped_splitter)
            parts = [part for part in collection.geoms if isinstance(part, Polygon)]
        except Exception as exc:
            return self._failure(region_id, splitter_id, tolerance, checks, f"区域分割失败：{type(exc).__name__}")

        checks.append(GeometryCheck(
            check="created_multiple_regions",
            passed=len(parts) >= 2,
            detail=f"分割产生 {len(parts)} 个区域",
            measured_value=float(len(parts)),
            allowed_value=2,
        ))
        if len(parts) < 2:
            return self._failure(region_id, splitter_id, tolerance, checks, "辅助线没有形成两个区域")

        valid_parts = all(part.is_valid and not part.is_empty and part.area > 0 for part in parts)
        checks.append(GeometryCheck(
            check="output_regions_valid",
            passed=valid_parts,
            detail="所有结果区域都必须有效且面积大于零",
        ))

        overlap_area = sum(
            parts[left].intersection(parts[right]).area
            for left in range(len(parts))
            for right in range(left + 1, len(parts))
        )
        overlap_limit = region.area * tolerance.overlap_area_ratio
        checks.append(GeometryCheck(
            check="output_regions_disjoint",
            passed=overlap_area <= overlap_limit,
            detail="结果区域内部不能出现实质重叠",
            measured_value=float(overlap_area),
            allowed_value=float(overlap_limit),
        ))

        merged = unary_union(parts)
        coverage_error = region.symmetric_difference(merged).area
        coverage_limit = region.area * tolerance.coverage_area_ratio
        checks.append(GeometryCheck(
            check="union_matches_original",
            passed=coverage_error <= coverage_limit,
            detail="所有结果区域的并集应覆盖原区域",
            measured_value=float(coverage_error),
            allowed_value=float(coverage_limit),
        ))

        smallest_ratio = min(part.area for part in parts) / region.area
        checks.append(GeometryCheck(
            check="no_tiny_fragments",
            passed=smallest_ratio >= tolerance.fragment_area_ratio,
            detail="不能产生超过容差定义的极小碎片",
            measured_value=float(smallest_ratio),
            allowed_value=tolerance.fragment_area_ratio,
        ))

        passed = all(check.passed for check in checks)
        output_ids = [f"{region_id}_part_{index + 1}" for index in range(len(parts))]
        return GeometryOperationResult(
            operation="split_region_by_segment",
            status="valid" if passed else "invalid",
            input_entities=[region_id, splitter_id],
            output_entities=output_ids,
            output_regions=[self._dto(part) for part in parts],
            checks=checks,
            tolerance_profile=tolerance.profile_id,
            geometry_engine=self.engine_name,
            geometry_engine_version=self.engine_version,
            reason=None if passed else "分割结果没有通过全部空间一致性检查",
        )

    def _failure(
        self,
        region_id: str,
        splitter_id: str,
        tolerance: ToleranceProfile,
        checks: list[GeometryCheck],
        reason: str,
    ) -> GeometryOperationResult:
        return GeometryOperationResult(
            operation="split_region_by_segment",
            status="invalid",
            input_entities=[region_id, splitter_id],
            checks=checks,
            tolerance_profile=tolerance.profile_id,
            geometry_engine=self.engine_name,
            geometry_engine_version=self.engine_version,
            reason=reason,
        )

    @staticmethod
    def _point_count(geometry) -> int:
        if geometry.is_empty:
            return 0
        if geometry.geom_type == "Point":
            return 1
        if hasattr(geometry, "geoms"):
            return sum(GeometryKernel._point_count(item) for item in geometry.geoms)
        # A splitter overlapping a boundary is ambiguous rather than two clean hits.
        return 0

