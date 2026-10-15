import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown, safeUrl } from "@/components/Markdown";

describe("Markdown (untrusted content)", () => {
  it("does not render raw HTML or scripts", () => {
    const { container } = render(<Markdown content={'<script>alert(1)</script><img src=x onerror="alert(2)"><b>bold</b>'} />);
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(container.innerHTML).not.toContain("onerror=");
  });

  it("strips javascript: and data: URLs", () => {
    const { container } = render(<Markdown content="[x](javascript:alert(1)) [y](data:text/html,hi) [ok](https://example.com)" />);
    const hrefs = Array.from(container.querySelectorAll("a")).map((a) => a.getAttribute("href"));
    expect(hrefs.some((h) => h?.startsWith("javascript:"))).toBe(false);
    expect(hrefs.some((h) => h?.startsWith("data:"))).toBe(false);
    expect(hrefs).toContain("https://example.com");
    expect(safeUrl("vbscript:x")).toBe("");
  });

  it("opens links safely and does not load images", () => {
    const { container, getByText } = render(<Markdown content="[docs](https://example.com) ![chart](https://evil.example/t.png)" />);
    const a = container.querySelector("a")!;
    expect(a.getAttribute("rel")).toContain("noopener");
    expect(a.getAttribute("rel")).toContain("noreferrer");
    expect(container.querySelector("img")).toBeNull();
    expect(getByText(/image: chart/)).toBeInTheDocument();
  });

  it("renders GFM task lists and tables", () => {
    const { container } = render(<Markdown content={"- [ ] todo\n\n| a | b |\n|---|---|\n| 1 | 2 |"} />);
    expect(container.querySelector('input[type="checkbox"]')).not.toBeNull();
    expect(container.querySelector("table")).not.toBeNull();
  });
});
