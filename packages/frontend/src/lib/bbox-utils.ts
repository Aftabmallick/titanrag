export interface NormalizedBBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface RawBBoxInput {
  x0?: number;
  y0?: number;
  x1?: number;
  y1?: number;
  ymin?: number;
  xmin?: number;
  ymax?: number;
  xmax?: number;
  page?: number;
}

/**
 * Transforms Docling bounding box representations (either normalized [0,1] or PDF points [72 DPI])
 * into SVG/Canvas screen coordinates relative to the rendered page viewport.
 */
export function transformBBox(
  rawBox: RawBBoxInput | undefined | null,
  viewportWidth: number,
  viewportHeight: number,
  pageHeightPoints?: number
): NormalizedBBox | null {
  if (!rawBox) return null;

  // Case 1: Normalized coordinates [ymin, xmin, ymax, xmax] in [0, 1]
  if (
    rawBox.ymin !== undefined &&
    rawBox.xmin !== undefined &&
    rawBox.ymax !== undefined &&
    rawBox.xmax !== undefined
  ) {
    const x = rawBox.xmin * viewportWidth;
    const y = rawBox.ymin * viewportHeight;
    const width = Math.max(4, (rawBox.xmax - rawBox.xmin) * viewportWidth);
    const height = Math.max(4, (rawBox.ymax - rawBox.ymin) * viewportHeight);

    return { x, y, width, height };
  }

  // Case 2: PDF Point coordinates [x0, y0, x1, y1] (72 DPI)
  if (
    rawBox.x0 !== undefined &&
    rawBox.y0 !== undefined &&
    rawBox.x1 !== undefined &&
    rawBox.y1 !== undefined
  ) {
    const scaleX = viewportWidth / (pageHeightPoints ? (viewportWidth / viewportHeight) * pageHeightPoints : 612);
    const scaleY = viewportHeight / (pageHeightPoints || 792);

    const x = rawBox.x0 * scaleX;
    const width = Math.max(4, (rawBox.x1 - rawBox.x0) * scaleX);

    // Flip Y axis (PDF bottom-left origin vs DOM top-left origin)
    const baseHeight = pageHeightPoints || 792;
    const y = (baseHeight - rawBox.y1) * scaleY;
    const height = Math.max(4, (rawBox.y1 - rawBox.y0) * scaleY);

    return { x, y, width, height };
  }

  return null;
}
