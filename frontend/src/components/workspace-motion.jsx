import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import './workspace-motion.css';

const mobileQuery = '(max-width: 900px)';

function subscribeToViewport(onChange) {
  const query = window.matchMedia(mobileQuery);
  query.addEventListener('change', onChange);
  return () => query.removeEventListener('change', onChange);
}

export function useWorkspaceSidebar(mobileOpen, setMobileOpen) {
  const mobile = useSyncExternalStore(subscribeToViewport, () => window.matchMedia(mobileQuery).matches);
  const [desktopOpen, setDesktopOpen] = useState(true);
  const toggleRef = useRef(null);
  const sidebarRef = useRef(null);
  const visible = mobile ? mobileOpen : desktopOpen;

  useEffect(() => {
    if (!mobile || !mobileOpen) return;
    const toggle = toggleRef.current;
    const sidebar = sidebarRef.current;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    function handleKey(event) {
      if (event.key === 'Escape') {
        event.preventDefault();
        setMobileOpen(false);
        toggle.focus({ preventScroll: true });
      }
      if (event.key === 'Tab') {
        const controls = [toggle, ...sidebar.querySelectorAll('a[href], button:not(:disabled)')];
        const index = controls.indexOf(document.activeElement);
        const step = event.shiftKey ? -1 : 1;
        const next = index < 0 ? 0 : (index + step + controls.length) % controls.length;
        event.preventDefault();
        controls[next].focus();
      }
    }

    document.addEventListener('keydown', handleKey);
    return () => {
      document.body.style.overflow = oldOverflow;
      document.removeEventListener('keydown', handleKey);
    };
  }, [mobile, mobileOpen, setMobileOpen]);

  function closeDrawer() {
    if (!mobile) return;
    setMobileOpen(false);
    toggleRef.current?.focus({ preventScroll: true });
  }

  function toggle() {
    if (mobile) setMobileOpen(!mobileOpen);
    else setDesktopOpen(!desktopOpen);
  }

  return { mobile, visible, toggle, closeDrawer, toggleRef, sidebarRef };
}

export function WorkspaceMenuButton({ visible, toggle, toggleRef }) {
  return <button ref={toggleRef} className="btn icon-btn workspace-menu-toggle" type="button" onClick={toggle}
    aria-controls="workspace-navigation" aria-expanded={visible} aria-label={visible ? 'Hide navigation' : 'Show navigation'}
    data-testid="button-open-navigation">
    <span className="workspace-menu-bars" aria-hidden="true"><span /><span /><span /></span>
  </button>;
}
