import { test, describe } from "node:test";
import assert from "node:assert";
import { transformBBox } from "../src/lib/bbox-utils";

describe("bbox-utils: transformBBox", () => {
  test("returns null if rawBox is undefined or null", () => {
    assert.strictEqual(transformBBox(undefined, 800, 1000), null);
    assert.strictEqual(transformBBox(null, 800, 1000), null);
  });

  test("correctly transforms normalized coordinates [ymin, xmin, ymax, xmax]", () => {
    const rawBox = {
      ymin: 0.1,
      xmin: 0.2,
      ymax: 0.3,
      xmax: 0.5,
    };

    const viewportWidth = 1000;
    const viewportHeight = 800;

    const result = transformBBox(rawBox, viewportWidth, viewportHeight);
    assert.ok(result);
    assert.strictEqual(result.x, 200); // 0.2 * 1000
    assert.strictEqual(result.y, 80);  // 0.1 * 800
    assert.strictEqual(result.width, 300); // (0.5 - 0.2) * 1000
    assert.strictEqual(result.height, 160); // (0.3 - 0.1) * 800
  });

  test("correctly transforms PDF point coordinates [x0, y0, x1, y1] with inverted Y axis", () => {
    const rawBox = {
      x0: 50,
      y0: 100,
      x1: 200,
      y1: 150,
    };

    // Standard letter page: 612 x 792 points at 1.0 scale
    const viewportWidth = 612;
    const viewportHeight = 792;
    const pageHeightPoints = 792;

    const result = transformBBox(rawBox, viewportWidth, viewportHeight, pageHeightPoints);
    assert.ok(result);
    assert.strictEqual(result.x, 50);
    assert.strictEqual(result.width, 150); // 200 - 50
    assert.strictEqual(result.height, 50); // 150 - 100
    assert.strictEqual(result.y, 792 - 150); // (792 - y1)
  });

  test("enforces minimum bounding box dimensions (4px min)", () => {
    const zeroBox = {
      ymin: 0.5,
      xmin: 0.5,
      ymax: 0.5,
      xmax: 0.5,
    };

    const result = transformBBox(zeroBox, 1000, 800);
    assert.ok(result);
    assert.strictEqual(result.width, 4);
    assert.strictEqual(result.height, 4);
  });
});
