import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "./ErrorBoundary";

function Bomb(): never {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  it("renders children when no error is thrown", () => {
    render(
      <ErrorBoundary>
        <div>safe child</div>
      </ErrorBoundary>,
    );

    expect(screen.getByText("safe child")).toBeInTheDocument();
  });

  it("shows recovery UI when a child throws", () => {
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );

    expect(screen.getByText("The app hit a frontend error.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload app" })).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();

    consoleErrorSpy.mockRestore();
  });
});
