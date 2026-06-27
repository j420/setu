import { describe, it, expect } from "vitest";
import { PNG } from "pngjs";
import { compareImages } from "./faceServer";

// Build a tiny PNG data URL from a pixel-painting function.
function png(w: number, h: number, paint: (x: number, y: number) => [number, number, number]): string {
  const p = new PNG({ width: w, height: h });
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      const [r, g, b] = paint(x, y);
      p.data[i] = r;
      p.data[i + 1] = g;
      p.data[i + 2] = b;
      p.data[i + 3] = 255;
    }
  }
  const buf = PNG.sync.write(p);
  return "data:image/png;base64," + buf.toString("base64");
}

const gradient = png(80, 80, (x, y) => [x * 3, y * 3, 128]);
const gradientCopy = png(80, 80, (x, y) => [x * 3, y * 3, 128]);
const inverted = png(80, 80, (x, y) => [255 - x * 3, 255 - y * 3, 128]);
const checker = png(80, 80, (x, y) => {
  const v = (Math.floor(x / 8) + Math.floor(y / 8)) % 2 ? 240 : 10;
  return [v, v, v];
});

describe("server-side photo comparison", () => {
  it("identical images score ~1", () => {
    const r = compareImages(gradient, gradientCopy);
    expect(r.similarity).toBeGreaterThan(0.95);
    expect(r.persisted).toBe(false);
  });

  it("a different image scores clearly lower than an identical one", () => {
    const same = compareImages(gradient, gradientCopy).similarity;
    const diff = compareImages(gradient, checker).similarity;
    expect(diff).toBeLessThan(same);
  });

  it("an inverted image is less similar than identical", () => {
    const same = compareImages(gradient, gradientCopy).similarity;
    const inv = compareImages(gradient, inverted).similarity;
    expect(inv).toBeLessThan(same);
  });

  it("is deterministic", () => {
    expect(compareImages(gradient, checker).similarity).toBe(
      compareImages(gradient, checker).similarity,
    );
  });

  it("rejects non-image input", () => {
    expect(() => compareImages("not-a-data-url", gradient)).toThrow();
  });
});
