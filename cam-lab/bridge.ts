import { processSvg } from './engine/src/engine/dxf/contourDetector';
import type { ParsedGeometry } from './engine/src/engine/geometry/types';

export interface CNCVectorImportSummary {
  units: 'mm';
  segmentCount: number;
  openPathCount: number;
  closedLoopCount: number;
  regionCount: number;
  circleCount: number;
  geometry: ParsedGeometry;
}

function assertFiniteGeometry(geometry: ParsedGeometry): void {
  const values: number[] = [];
  for (const segment of geometry.segments) {
    values.push(segment.start.x, segment.start.y, segment.end.x, segment.end.y);
    if (segment.type === 'arc') {
      values.push(segment.center.x, segment.center.y, segment.radius);
    }
  }
  for (const path of geometry.openPaths) {
    for (const segment of path) {
      values.push(segment.start.x, segment.start.y, segment.end.x, segment.end.y);
    }
  }
  for (const loop of geometry.loops) {
    for (const segment of loop.segments) {
      values.push(segment.start.x, segment.start.y, segment.end.x, segment.end.y);
    }
  }
  if (!values.every(Number.isFinite)) {
    throw new Error('SVG geometry contains non-finite coordinates');
  }
}

export function parseSvgForCNC(svgText: string): CNCVectorImportSummary {
  if (typeof svgText !== 'string' || !svgText.trim()) {
    throw new Error('SVG content is empty');
  }
  const geometry = processSvg(svgText);
  assertFiniteGeometry(geometry);
  if (!geometry.loops.length && !geometry.openPaths.length) {
    throw new Error('SVG contains no supported vector geometry');
  }
  return {
    units: 'mm',
    segmentCount: geometry.segments.length,
    openPathCount: geometry.openPaths.length,
    closedLoopCount: geometry.loops.length,
    regionCount: geometry.regions.length,
    circleCount: geometry.circles.length,
    geometry,
  };
}

declare global {
  interface Window {
    CNCVectorCAM?: {
      version: string;
      parseSvg: typeof parseSvgForCNC;
    };
  }
}

if (typeof window !== 'undefined') {
  window.CNCVectorCAM = {
    version: 'onemanlabs-66eba04',
    parseSvg: parseSvgForCNC,
  };
}
