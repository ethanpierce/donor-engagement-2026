import { motion } from 'motion/react'
import { Check, Rise, WinBar, ease, useSeen } from './bits'
import { monthly } from '../data/sample'

export default function FeatureFailed() {
  const [ref, on] = useSeen<HTMLDivElement>(0.5)
  return (
    <section className="failed wrap section">
      <Rise>
        <h2 className="section-title">A failed monthly gift shows up in <em>days, not months.</em></h2>
        <p className="lede">When a monthly gift fails, it goes to the top of the list so someone can reach out before the gifts quietly stop.</p>
      </Rise>
      <div className="failed-win win" ref={ref}>
        <WinBar title="Monthly gift · $25" right="Sample data" />
        <div className="track" aria-label="Sample monthly gifts from June to November, with November failed">
          <motion.i className="track-line" initial={{ scaleX: 0 }} animate={on ? { scaleX: 1 } : {}} transition={{ duration: 1.1, ease }} />
          {monthly.map((m, i) => (
            <div key={m.month} className={m.ok ? 'node-col' : 'node-col bad'}>
              <span className="node-wrap">
                {!m.ok && on && (
                  <motion.span className="ring" initial={{ scale: 1, opacity: 0.5 }} animate={{ scale: 2.4, opacity: 0 }}
                    transition={{ delay: 1.3, duration: 1.6, repeat: 2, ease: 'easeOut' }} />
                )}
                <motion.span className="node" initial={{ scale: 0.5, opacity: 0 }} animate={on ? { scale: 1, opacity: 1 } : {}}
                  transition={{ delay: 0.15 + i * 0.14, duration: 0.45, ease }}>{m.ok ? <Check /> : '!'}</motion.span>
              </span>
              <span className="node-m">{m.month}</span>
              <span className="node-v">{m.ok ? '$25 paid' : 'Failed'}</span>
            </div>
          ))}
        </div>
        <motion.p className="months-note" initial={{ opacity: 0, y: 6 }} animate={on ? { opacity: 1, y: 0 } : {}} transition={{ delay: 1.1, duration: 0.6, ease }}>
          <span className="tag-late">Failed Nov 3</span><span>On your list Nov 5, two days later.</span>
        </motion.p>
      </div>
    </section>
  )
}
