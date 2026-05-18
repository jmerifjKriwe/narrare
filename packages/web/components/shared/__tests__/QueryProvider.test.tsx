import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { QueryProvider } from "@/components/shared/QueryProvider";

describe("QueryProvider", () => {
  it("renders children", () => {
    const { container } = render(
      <QueryProvider>
        <div data-testid="child">test</div>
      </QueryProvider>,
    );
    expect(container.querySelector('[data-testid="child"]')).toBeDefined();
  });
});
