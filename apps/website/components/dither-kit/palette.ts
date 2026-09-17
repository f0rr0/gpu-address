export type Rgb = [number, number, number]

export type DitherColor =
  | "green"
  | "blue"
  | "purple"
  | "pink"
  | "orange"
  | "red"
  | "grey"
  | "white"
  | "silver"
  | "steel"

export type Seed = { fill: Rgb; line: Rgb; star: Rgb }

// Each seed: the area-fill hue, the bright series line, and the star sparkle.
export const PALETTE: Record<DitherColor, Seed> = {
  white: { fill: [229, 229, 229], line: [237, 237, 237], star: [250, 250, 250] },
  silver: { fill: [176, 176, 176], line: [200, 200, 200], star: [229, 229, 229] },
  steel: { fill: [128, 128, 128], line: [163, 163, 163], star: [200, 200, 200] },
  green: { fill: [163, 201, 168], line: [150, 255, 180], star: [200, 255, 220] },
  blue: { fill: [145, 185, 216], line: [150, 200, 255], star: [205, 228, 255] },
  purple: {
    fill: [181, 160, 214],
    line: [200, 175, 255],
    star: [225, 210, 255],
  },
  pink: { fill: [217, 160, 174], line: [255, 170, 220], star: [255, 205, 235] },
  orange: {
    fill: [223, 188, 130],
    line: [255, 195, 130],
    star: [255, 220, 175],
  },
  red: { fill: [240, 70, 70], line: [255, 150, 140], star: [255, 195, 185] },
  // No-data: a muted grey so empty metrics read as "nothing here".
  grey: { fill: [92, 92, 92], line: [140, 140, 140], star: [165, 165, 165] },
}

export const rgb = ([r, g, b]: Rgb, k = 1, a = 1) =>
  `rgba(${Math.round(r * k)},${Math.round(g * k)},${Math.round(b * k)},${a})`

export const seedOfColor = (color: DitherColor): Seed => PALETTE[color]

export const isDitherColor = (value: unknown): value is DitherColor =>
  typeof value === "string" && value in PALETTE
