import { lazy, Suspense, useEffect, useState, useSyncExternalStore } from 'react';
import { ErrorBoundary } from './error-boundary';

const ColorBends = lazy(() => import('./ColorBends'));
const colors = ['#ff5c7a', '#8a5cff', '#00ffd1'];
const reducedMotionQuery = '(prefers-reduced-motion: reduce)';

function subscribeToMotion(onChange) {
  const query = window.matchMedia(reducedMotionQuery);
  query.addEventListener('change', onChange);
  return () => query.removeEventListener('change', onChange);
}

function StaticBackdrop() {
  return null;
}

export default function SignInBackdrop({ paused }) {
  const reducedMotion = useSyncExternalStore(subscribeToMotion, () => window.matchMedia(reducedMotionQuery).matches);
  const [webglSupported, setWebglSupported] = useState(false);

  useEffect(() => {
    if (reducedMotion) return;
    const gl = document.createElement('canvas').getContext('webgl2');
    setWebglSupported(Boolean(gl));
    gl?.getExtension('WEBGL_lose_context')?.loseContext();
  }, [reducedMotion]);

  return <div className="signin-flow" aria-hidden="true">
    {webglSupported && !paused && !reducedMotion && <ErrorBoundary FallbackComponent={StaticBackdrop}>
      <Suspense fallback={null}>
        <ColorBends
          colors={colors}
          rotation={90}
          speed={0.2}
          scale={1}
          frequency={1}
          warpStrength={1}
          mouseInfluence={1}
          noise={0.15}
          parallax={0.5}
          iterations={1}
          intensity={1.5}
          bandWidth={6}
          transparent
        />
      </Suspense>
    </ErrorBoundary>}
  </div>;
}
