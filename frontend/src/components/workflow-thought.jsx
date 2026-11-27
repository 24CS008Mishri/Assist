import { useReducedMotion } from 'motion/react';
import ThoughtLine from './ThoughtLine';
import './workflow-thought.css';

export default function WorkflowThought({ working, steps, label = 'Thinking…', doneLabel = 'Thought for' }) {
  const reducedMotion = useReducedMotion();
  return <ThoughtLine
    className="workflow-thought"
    color="#4b3567"
    glyphColor="#8153b0"
    working={working}
    steps={steps}
    label={label}
    doneLabel={doneLabel}
    glyph="sparkle"
    fontSize={16}
    breathPeriod={1.6}
    breathDepth={reducedMotion ? 0 : 0.45}
    settleDuration={reducedMotion ? 0 : 350}
    settleBlur={reducedMotion ? 0 : 2}
    collapsible
    collapseOnSettle
    showTimer
  />;
}
