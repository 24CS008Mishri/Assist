import { Component } from 'react';

function toError(value) {
  if (value instanceof Error) return value;
  if (typeof value === 'string') return new Error(value);
  try {
    return new Error(JSON.stringify(value));
  } catch {
    return new Error(String(value));
  }
}

function DefaultFallback({ error, resetError }) {
  return (
    <div style={{ minHeight: '100dvh', width: '100%', display: 'grid', placeItems: 'center', padding: 24 }}>
      <div className="surface" style={{ maxWidth: 460, width: '100%', padding: 32, textAlign: 'center' }}>
        <h1 className="font-display" style={{ fontSize: 20, margin: 0 }}>Something went wrong</h1>
        <p className="muted" style={{ marginTop: 10, fontSize: 13, lineHeight: 1.6 }}>
          This part of the app hit an error. The rest of the app is still running.
        </p>
        {import.meta.env.DEV ? (
          <pre style={{ marginTop: 16, overflowX: 'auto', borderRadius: 12, background: '#f3edf9', padding: 12, textAlign: 'left', fontSize: 11, color: '#5b4a72' }}>
            {error.message || String(error)}
          </pre>
        ) : null}
        <button type="button" className="btn btn-primary" style={{ marginTop: 16 }} onClick={resetError}>
          Try again
        </button>
      </div>
    </div>
  );
}

export class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error: toError(error) };
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught an error:', toError(error), info.componentStack);
  }

  componentDidUpdate(prevProps) {
    if (this.state.error !== null && prevProps.resetKey !== this.props.resetKey) {
      this.resetError();
    }
  }

  resetError = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (error === null) return this.props.children;
    const Fallback = this.props.FallbackComponent ?? DefaultFallback;
    return <Fallback error={error} resetError={this.resetError} />;
  }
}
