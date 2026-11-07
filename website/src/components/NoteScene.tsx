import { motion } from 'motion/react'
import { WinBar, ease, useSeen } from './bits'
import { PRODUCT_NAME } from '../config'
import { money, noteDonor, noteSign, noteText } from '../data/sample'

const years = [
  { label: "Dec '21", state: 'gift' }, { label: "Dec '22", state: 'gift' }, { label: "Dec '23", state: 'gift' },
  { label: "Dec '24", state: 'gift' }, { label: "Dec '25", state: 'missed' }, { label: "Dec '26", state: 'due' },
]

const sentences = noteText.match(/[^.?!]+[.?!]+/g) ?? [noteText]

export default function NoteScene() {
  const [ref, seen] = useSeen<HTMLDivElement>(0.5)
  const [chart, chartOn] = useSeen<HTMLDivElement>(0.5)
  return (
    <section className="note-band section" id="note">
      <div className="note wrap">
        <div>
          <h2 className="section-title">A note for {noteDonor.name}, <em>ready before you call.</em></h2>
          <div className="chart win" ref={chart}>
            <WinBar title={`${noteDonor.name} · gifts each December`} right="Sample data" />
            <div className="bars">
              {years.map((y, i) => (
                <div key={y.label} className={`bar-col ${y.state}`}>
                  <span className="bar-top">{y.state === 'gift' ? money(noteDonor.amount) : y.state === 'missed' ? 'Missed' : 'Next'}</span>
                  <motion.span className="bar" initial={{ scaleY: 0 }} animate={chartOn ? { scaleY: 1 } : {}} transition={{ delay: 0.1 + i * 0.09, duration: 0.7, ease }} />
                  <span className="bar-label">{y.label}</span>
                </div>
              ))}
            </div>
            <div className="chart-foot"><span>Last gift {noteDonor.last}</span><span className="tag-late">No gift last December</span></div>
          </div>
        </div>
        <div className="note-sheet" ref={ref}>
          <div className="note-head"><span>Suggested note</span><span>Sample data</span></div>
          <p className="note-text">
            {sentences.map((s, i) => (
              <motion.span key={i} initial={{ opacity: 0, filter: 'blur(6px)' }} animate={seen ? { opacity: 1, filter: 'blur(0px)' } : {}}
                transition={{ delay: 0.15 + i * 0.35, duration: 0.8, ease }}>{s}</motion.span>
            ))}
          </p>
          <motion.p className="note-sign" initial={{ opacity: 0 }} animate={seen ? { opacity: 1 } : {}} transition={{ delay: 0.15 + sentences.length * 0.35, duration: 0.6 }}>{noteSign}</motion.p>
          <p className="note-foot">Staff edit it and make the call. {PRODUCT_NAME} never sends anything.</p>
        </div>
      </div>
    </section>
  )
}
