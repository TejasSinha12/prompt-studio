export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadText(filename: string, content: string, type = "text/plain"): void {
  downloadBlob(filename, new Blob([content], { type: `${type};charset=utf-8` }));
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback for browsers that block the async clipboard API.
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  }
}

/** Read a user-selected file as text with a size cap (untrusted input). */
export function readFileText(file: File, maxBytes: number): Promise<string> {
  if (file.size > maxBytes) {
    return Promise.reject(new Error(`File is too large (max ${Math.round(maxBytes / 1024 / 1024)} MB).`));
  }
  return file.text();
}
