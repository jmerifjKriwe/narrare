import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { NameResults } from "@/components/generation/NameResults";
import { createTestWrapper } from "@/lib/test-utils";
import { createGeneratedName } from "@/mocks/data";
import type { NameGenerateResponse } from "@/types";

describe("NameResults", () => {
  it("should show no results message when results are null", () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <NameResults results={null} isLoading={false} />
      </Wrapper>,
    );

    expect(screen.getByText("No names generated yet")).toBeInTheDocument();
  });

  it("should show no results message when results are empty", () => {
    const Wrapper = createTestWrapper();
    const emptyResults: NameGenerateResponse = {
      names: [],
      count: 0,
      culture: "fantasy",
      name_type: "character",
    };

    render(
      <Wrapper>
        <NameResults results={emptyResults} isLoading={false} />
      </Wrapper>,
    );

    expect(screen.getByText("No names generated yet")).toBeInTheDocument();
  });

  it("should display generated names", () => {
    const Wrapper = createTestWrapper();
    const results: NameGenerateResponse = {
      names: [
        createGeneratedName({ name: "Aelindra" }),
        createGeneratedName({ name: "Theron", pronunciation: null, meaning: null }),
      ],
      count: 2,
      culture: "fantasy",
      name_type: "character",
    };

    render(
      <Wrapper>
        <NameResults results={results} isLoading={false} />
      </Wrapper>,
    );

    expect(screen.getByText("Aelindra")).toBeInTheDocument();
    expect(screen.getByText("Theron")).toBeInTheDocument();
  });

  it("should show pronunciation when available", () => {
    const Wrapper = createTestWrapper();
    const results: NameGenerateResponse = {
      names: [createGeneratedName({ name: "Aelindra", pronunciation: "AY-lin-dra" })],
      count: 1,
      culture: "fantasy",
      name_type: "character",
    };

    render(
      <Wrapper>
        <NameResults results={results} isLoading={false} />
      </Wrapper>,
    );

    expect(screen.getByText(/AY-lin-dra/)).toBeInTheDocument();
  });

  it("should show meaning when available", () => {
    const Wrapper = createTestWrapper();
    const results: NameGenerateResponse = {
      names: [createGeneratedName({ name: "Aelindra", meaning: "Starlight wanderer" })],
      count: 1,
      culture: "fantasy",
      name_type: "character",
    };

    render(
      <Wrapper>
        <NameResults results={results} isLoading={false} />
      </Wrapper>,
    );

    expect(screen.getByText(/Starlight wanderer/)).toBeInTheDocument();
  });

  it("should show duplicate badge for duplicate names", () => {
    const Wrapper = createTestWrapper();
    const results: NameGenerateResponse = {
      names: [createGeneratedName({ name: "Aelindra", is_duplicate: true })],
      count: 1,
      culture: "fantasy",
      name_type: "character",
    };

    render(
      <Wrapper>
        <NameResults results={results} isLoading={false} />
      </Wrapper>,
    );

    expect(screen.getByText("Duplicate")).toBeInTheDocument();
  });

  it("should not show duplicate badge for non-duplicate names", () => {
    const Wrapper = createTestWrapper();
    const results: NameGenerateResponse = {
      names: [createGeneratedName({ name: "Aelindra", is_duplicate: false })],
      count: 1,
      culture: "fantasy",
      name_type: "character",
    };

    render(
      <Wrapper>
        <NameResults results={results} isLoading={false} />
      </Wrapper>,
    );

    expect(screen.queryByText("Duplicate")).not.toBeInTheDocument();
  });

  it("should show save to KB button for each name", () => {
    const consoleSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    const Wrapper = createTestWrapper();
    const results: NameGenerateResponse = {
      names: [createGeneratedName({ name: "Aelindra" })],
      count: 1,
      culture: "fantasy",
      name_type: "character",
    };

    render(
      <Wrapper>
        <NameResults results={results} isLoading={false} />
      </Wrapper>,
    );

    expect(screen.getByText("Save to KB")).toBeInTheDocument();
    consoleSpy.mockRestore();
  });

  it("should log action when save to KB is clicked", async () => {
    const user = userEvent.setup();
    const consoleSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    const Wrapper = createTestWrapper();
    const results: NameGenerateResponse = {
      names: [createGeneratedName({ name: "Aelindra" })],
      count: 1,
      culture: "fantasy",
      name_type: "character",
    };

    render(
      <Wrapper>
        <NameResults results={results} isLoading={false} />
      </Wrapper>,
    );

    await user.click(screen.getByText("Save to KB"));

    expect(consoleSpy).toHaveBeenCalledWith("[TODO] Save to KB: Aelindra");
    consoleSpy.mockRestore();
  });

  it("should show loading spinner when isLoading is true", () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <NameResults results={null} isLoading={true} />
      </Wrapper>,
    );

    expect(screen.getByText("Generating...")).toBeInTheDocument();
  });
});
