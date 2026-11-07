import { useEffect, useRef, useState } from 'react'
import { animate, motion, useInView, useMotionValue, useReducedMotion, useScroll, useTransform } from 'motion/react'
import type { MotionValue } from 'motion/react'

// One easing for the whole page: quick start, long soft landing, no overshoot.
export const ease = [0.22, 1, 0.36, 1] as const

export function Mark({ on, delay = 0, children }: { on: boolean; delay?: number; children: React.ReactNode }) {
  return <span className={on ? 'hl on' : 'hl'} style={{ transitionDelay: `${delay}s` }}>{children}</span>
}

export function Count({ to, on, prefix = '$' }: { to: number; on: boolean; prefix?: string }) {
  const value = useMotionValue(0)
  const reduced = useReducedMotion()
  const [shown, setShown] = useState(0)
  useEffect(() => value.on('change', v => setShown(Math.round(v))), [value])
  useEffect(() => {
    if (!on) { value.set(0); return }
    if (reduced) { value.set(to); return }
    const controls = animate(value, to, { duration: 0.9, ease })
    return () => controls.stop()
  }, [on, to, value, reduced])
  return <>{prefix}{shown.toLocaleString('en-US')}</>
}

function Word({ word, range, progress }: { word: string; range: [number, number]; progress: MotionValue<number> }) {
  const opacity = useTransform(progress, range, [0.2, 1])
  return <motion.span style={{ opacity }}>{word}</motion.span>
}

// Words come up with scroll. The text stays real text for screen readers.
export function ScrollWords({ text, className }: { text: string; className?: string }) {
  const ref = useRef<HTMLParagraphElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start 0.85', 'end 0.5'] })
  const words = text.split(/\s+/)
  return (
    <p ref={ref} className={className}>
      {words.map((w, i) => (
        <span key={i}>
          {reduced ? w : <Word word={w} progress={scrollYProgress} range={[i / words.length, (i + 1.5) / words.length]} />}{' '}
        </span>
      ))}
    </p>
  )
}

export function Rise({ children, delay = 0, className }: { children: React.ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div className={className} initial={{ opacity: 0, y: 12, filter: 'blur(6px)' }}
      whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      viewport={{ once: true, amount: 0.3 }} transition={{ duration: 0.7, delay, ease }}>
      {children}
    </motion.div>
  )
}

export function useSeen<T extends Element>(amount = 0.35) {
  const ref = useRef<T>(null)
  const seen = useInView(ref, { once: true, amount })
  return [ref, seen] as const
}

export function useIsNarrow(px = 820) {
  const [narrow, setNarrow] = useState(() => window.matchMedia(`(max-width:${px}px)`).matches)
  useEffect(() => {
    const query = window.matchMedia(`(max-width:${px}px)`)
    const update = () => setNarrow(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [px])
  return narrow
}

export function MailIcon() {
  return <svg className="mail-icon" viewBox="0 0 20 16" aria-hidden="true"><rect x="1" y="1" width="18" height="14" rx="2" /><path d="M1.5 2.5 10 9l8.5-6.5" /></svg>
}

export function Check() {
  return <svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 6.5 4.8 9 10 3" strokeLinecap="round" strokeLinejoin="round" /></svg>
}

export function WinBar({ title, right }: { title: string; right?: React.ReactNode }) {
  return (
    <div className="win-bar">
      <span className="win-dots" aria-hidden="true"><i /><i /><i /></span>
      <span className="win-title">{title}</span>
      <span className="win-right">{right}</span>
    </div>
  )
}

export function FileGlyph() {
  return <svg className="file-glyph" viewBox="0 0 14 16" aria-hidden="true"><path d="M1 1h8l4 4v10H1z M9 1v4h4" /></svg>
}
