import React from "react";

type ErrorBoundaryProps = {
  children: React.ReactNode;
};

type ErrorBoundaryState = {
  hasError: boolean;
  message: string;
};

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    hasError: false,
    message: "",
  };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      message: error.message || "Something went wrong in the app.",
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("Unhandled frontend error", error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen text-ink">
          <div className="mx-auto flex min-h-screen w-full max-w-4xl items-center px-4 py-8 md:px-6">
            <div className="glass-panel w-full rounded-[32px] p-8 shadow-soft">
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-ink/45">App recovery</p>
              <h1 className="mt-3 font-display text-4xl text-ink md:text-5xl">The app hit a frontend error.</h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-ink/70">
                Your data should still be safe, but this screen means a React error interrupted rendering. Reloading
                usually gets you moving again while we clean up the underlying issue.
              </p>
              {this.state.message ? (
                <div className="mt-5 rounded-[22px] border border-clay/20 bg-clay/10 px-4 py-3 text-sm text-ink">
                  {this.state.message}
                </div>
              ) : null}
              <div className="mt-6 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={this.handleReload}
                  className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white shadow-soft"
                >
                  Reload app
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
