export type AssetNode = string[] | { [key: string]: AssetNode };

export interface HistorianMetadata {
  identification: Record<string, string>;
  electrical: Record<string, string>;
  integration: Record<string, string>;
}
