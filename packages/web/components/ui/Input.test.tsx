import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Input } from "./Input";

describe("Input", () => {
  it("should render an input element", () => {
    render(<Input placeholder="Enter text" />);

    const input = screen.getByPlaceholderText("Enter text");
    expect(input).toBeInTheDocument();
    expect(input.tagName).toBe("INPUT");
  });

  it("should render a label when provided", () => {
    render(<Input label="Email" />);

    const label = screen.getByText("Email");
    expect(label).toBeInTheDocument();

    const input = screen.getByLabelText("Email");
    expect(input).toBeInTheDocument();
  });

  it("should handle value changes", async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();

    render(<Input onChange={handleChange} />);

    const input = screen.getByRole("textbox");
    await user.type(input, "hello");

    expect(handleChange).toHaveBeenCalled();
    expect(input).toHaveValue("hello");
  });

  it("should be disabled when disabled prop is true", () => {
    render(<Input disabled placeholder="Nope" />);

    const input = screen.getByPlaceholderText("Nope");
    expect(input).toBeDisabled();
  });

  it("should display error message", () => {
    render(<Input error="This field is required" label="Name" />);

    const errorMessage = screen.getByText("This field is required");
    expect(errorMessage).toBeInTheDocument();
    expect(errorMessage).toHaveAttribute("role", "alert");
  });

  it("should mark input as invalid when error is present", () => {
    render(<Input error="Invalid" label="Email" />);

    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("aria-invalid", "true");
  });

  it("should display hint text when no error", () => {
    render(<Input hint="Enter your email address" label="Email" />);

    const hint = screen.getByText("Enter your email address");
    expect(hint).toBeInTheDocument();
  });

  it("should show error instead of hint when both are provided", () => {
    render(<Input hint="This is a hint" error="This is an error" label="Field" />);

    expect(screen.getByText("This is an error")).toBeInTheDocument();
    expect(screen.queryByText("This is a hint")).not.toBeInTheDocument();
  });

  it("should generate id from label if no id is provided", () => {
    render(<Input label="First Name" />);

    const input = screen.getByLabelText("First Name");
    expect(input).toHaveAttribute("id", "first-name");
  });

  it("should use provided id over generated one", () => {
    render(<Input label="Email" id="custom-email-id" />);

    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("id", "custom-email-id");
  });
});
