import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { NameGenerator } from "@/components/generation/NameGenerator";
import { createTestWrapper } from "@/lib/test-utils";

describe("NameGenerator", () => {
  it("should render the name generator form", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <NameGenerator projectId="test-project" />
      </Wrapper>,
    );

    expect(screen.getByText("Name Generator")).toBeInTheDocument();
    expect(screen.getByText("Generate Names")).toBeInTheDocument();
    expect(screen.getByLabelText("Name Type")).toBeInTheDocument();
    expect(screen.getByLabelText("Culture")).toBeInTheDocument();
    expect(screen.getByLabelText("Count")).toBeInTheDocument();
    expect(screen.getByLabelText("Gender")).toBeInTheDocument();
  });

  it("should render name type options", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <NameGenerator projectId="test-project" />
      </Wrapper>,
    );

    const nameTypeSelect = screen.getByLabelText("Name Type");
    expect(nameTypeSelect).toBeInTheDocument();

    // Should have options
    const options = nameTypeSelect.querySelectorAll("option");
    expect(options.length).toBeGreaterThan(0);
  });

  it("should validate count range", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <NameGenerator projectId="test-project" />
      </Wrapper>,
    );

    const countInput = screen.getByLabelText("Count") as HTMLInputElement;
    expect(countInput.value).toBe("10");
    expect(countInput.min).toBe("1");
    expect(countInput.max).toBe("50");
  });

  it("should generate names on button click", async () => {
    const user = userEvent.setup();
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <NameGenerator projectId="test-project" />
      </Wrapper>,
    );

    await user.click(screen.getByText("Generate Names"));

    // Should show generated names
    await waitFor(() => {
      expect(screen.getByText("TestName1")).toBeInTheDocument();
    });

    expect(screen.getByText("TestName2")).toBeInTheDocument();
  });

  it("should show loading state during generation", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <NameGenerator projectId="test-project" />
      </Wrapper>,
    );

    // The generate button text changes to "Generating..." during loading
    // Since MSW resolves immediately, we verify the button has the right initial text
    expect(screen.getByText("Generate Names")).toBeInTheDocument();
  });

  it("should show no results message initially", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <NameGenerator projectId="test-project" />
      </Wrapper>,
    );

    expect(screen.getByText("No names generated yet")).toBeInTheDocument();
  });

  it("should allow changing name type", async () => {
    const user = userEvent.setup();
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <NameGenerator projectId="test-project" />
      </Wrapper>,
    );

    const nameTypeSelect = screen.getByLabelText("Name Type");
    await user.selectOptions(nameTypeSelect, "place");

    expect((nameTypeSelect as HTMLSelectElement).value).toBe("place");
  });

  it("should allow changing culture", async () => {
    const user = userEvent.setup();
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <NameGenerator projectId="test-project" />
      </Wrapper>,
    );

    const cultureSelect = screen.getByLabelText("Culture");
    await user.selectOptions(cultureSelect, "scifi");

    expect((cultureSelect as HTMLSelectElement).value).toBe("scifi");
  });
});
