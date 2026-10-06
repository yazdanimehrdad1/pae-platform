// powerflow's profile CSVs: a header row, then plain comma-separated values (no quoting).

export interface ParsedCsv {
  columns: string[];
  rows: string[][];
}

export function parseCsv(text: string): ParsedCsv {
  const lines = text.split(/\r?\n/).filter((line) => line.trim() !== "");
  if (lines.length === 0) return { columns: [], rows: [] };
  const [header, ...body] = lines;
  return {
    columns: header.split(",").map((column) => column.trim()),
    rows: body.map((line) => line.split(",").map((cell) => cell.trim())),
  };
}

/** At most `limit` evenly spaced rows (for charting long profiles). */
export function downsample<T>(rows: T[], limit: number): T[] {
  if (rows.length <= limit) return rows;
  const stride = rows.length / limit;
  return Array.from({ length: limit }, (_, index) => rows[Math.floor(index * stride)]);
}
