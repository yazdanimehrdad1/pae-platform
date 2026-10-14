import { Component, ReactNode } from "react";
import { isChunkLoadError, reloadForNewBuild } from "./staleBuild";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    // A page from an older build than the server's: reload once to get the current one.
    if (isChunkLoadError(error) && reloadForNewBuild()) return;
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="flex flex-col items-center justify-center p-8 text-center">
          <p className="text-destructive font-semibold mb-2">Something went wrong</p>
          <p className="text-muted-foreground text-sm">
            {isChunkLoadError(this.state.error)
              ? "This page couldn't load, probably because the app was updated. Reload the page to get the new version."
              : (this.state.error?.message ?? "An unexpected error occurred.")}
          </p>
          <button
            className="mt-4 text-sm underline text-primary"
            onClick={() => (isChunkLoadError(this.state.error) ? window.location.reload() : this.setState({ hasError: false, error: null }))}
          >
            {isChunkLoadError(this.state.error) ? "Reload" : "Try again"}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
