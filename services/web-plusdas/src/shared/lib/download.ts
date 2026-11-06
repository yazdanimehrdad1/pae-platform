// Saving a file in the browser.

/** Save text as a file the browser downloads (nothing is sent anywhere). */
export function downloadFile(fileName: string, content: string, mimeType: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: mimeType }));
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** "daily_energy-hourly.csv": lower-case words joined by '-' or '_', nothing else. */
export function fileName(...parts: string[]): string {
  return parts
    .map(part => part.toLowerCase().replace(/[^a-z0-9_]+/g, "-").replace(/^-+|-+$/g, ""))
    .filter(Boolean)
    .join("-");
}
