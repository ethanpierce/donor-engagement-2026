import { useRef, useState } from 'react'
import { AnimatePresence, motion, useMotionValueEvent, useReducedMotion, useScroll, useSpring, useTransform } from 'motion/react'
import type { MotionValue } from 'motion/react'
import { Check, Count, Mark, WinBar, FileGlyph, ease, useIsNarrow, useSeen } from './bits'
import { compare, fileRowTotal, files, giftTotal, gifts, lateDonors, money } from '../data/sample'

const steps = [
  { title: 'Bring your lists', text: 'Drop in the spreadsheets you already download. Online gifts, tickets, auction, checks.' },
  { title: 'See why they match', text: "Every suggested match shows what lines up and what doesn't." },
  { title: 'You approve', text: 'Nothing merges until a staff member says so. Every gift stays attached.' },
  { title: 'Hear about late gifts', text: 'Each week, see whose regular gift is late, in time to call.' },
]

const item = (i: number, on: boolean, base = 0.12) => ({
  initial: { opacity: 0, y: 8 },
  animate: on ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 },
  transition: { delay: base + i * 0.08, duration: 0.5, ease },
})

function Files() {
  const [ref, on] = useSeen<HTMLDivElement>()
  return (
    <div ref={ref}>
      <ul className="files">
        {files.map((f, i) => (
          <motion.li key={f.file} {...item(i, on)}>
            <span className="file-icon"><FileGlyph /></span>
            <span><strong>{f.name}</strong><small>{f.file}</small></span>
            <em>{f.rows} rows</em>
          </motion.li>
        ))}
      </ul>
      <motion.p className="screen-foot" {...item(4, on)}><span>4 lists in</span><strong><Count to={fileRowTotal} on={on} prefix="" /> rows</strong></motion.p>
    </div>
  )
}

function Compare() {
  const [ref, on] = useSeen<HTMLDivElement>()
  return (
    <div ref={ref}>
      <div className="compare">
        {compare.map((row, i) => (
          <motion.div className="compare-row" key={row.field} {...item(i, on)}>
            <small>{row.field}</small>
            <span>{row.same ? <Mark on={on} delay={0.3 + i * 0.2}>{row.left}</Mark> : row.left}</span>
            <span>{row.same ? <Mark on={on} delay={0.4 + i * 0.2}>{row.right}</Mark> : row.right}</span>
            <em className={row.same ? '' : 'differs'}>{row.verdict}</em>
          </motion.div>
        ))}
      </div>
      <motion.p className="screen-foot" {...item(3, on, 0.3)}><span>Online donations and Checks in the mail</span><strong>Needs your call</strong></motion.p>
    </div>
  )
}

function Approve() {
  const [ref, on] = useSeen<HTMLDivElement>()
  return (
    <div ref={ref}>
      <motion.div className="approved" {...item(0, on)}>
        <span>Rosa M. Delgado</span>
        <motion.span className="card-badge" initial={{ opacity: 0, scale: 0.94 }} animate={on ? { opacity: 1, scale: 1 } : {}}
          transition={{ duration: 0.5, ease, delay: 0.4 }}><Check />Approved by Denise</motion.span>
      </motion.div>
      <ul className="mini-ledger">
        {gifts.map((g, i) => (
          <motion.li key={g.date + g.source} {...item(i + 1, on, 0.35)}><span>{g.date}</span><span>{g.source}</span><span>{money(g.amount)}</span></motion.li>
        ))}
      </ul>
      <motion.p className="screen-foot" {...item(7, on, 0.35)}><span>{gifts.length} gifts kept. None lost.</span><strong><Count to={giftTotal} on={on} /></strong></motion.p>
    </div>
  )
}

function Late() {
  const [ref, on] = useSeen<HTMLDivElement>()
  return (
    <div ref={ref}>
      <ul className="late">
        {lateDonors.map((d, i) => (
          <motion.li key={d.name} {...item(i, on)}>
            <strong>{d.name}</strong>
            <span className="late-meta">Last gift {d.last} · {money(d.amount)}<br />{d.timing}</span>
            <span className="late-status"><span className={d.late ? 'tag-late' : 'tag-ok'}>{d.status}</span></span>
          </motion.li>
        ))}
      </ul>
      <motion.p className="screen-foot" {...item(3, on, 0.5)}><span>This week</span><strong>{lateDonors.filter(d => d.late).length} donors to call</strong></motion.p>
    </div>
  )
}

const screens = [Files, Compare, Approve, Late]

function Panel({ index }: { index: number }) {
  const Screen = screens[index]
  return (
    <div className="screen win">
      <WinBar title={steps[index].title} right="Sample data" />
      <div className="screen-body"><Screen /></div>
    </div>
  )
}

function Slide({ i, pos }: { i: number; pos: MotionValue<number> }) {
  const opacity = useTransform(pos, [i - 1, i, i + 1], [0.3, 1, 0.3])
  const scale = useTransform(pos, [i - 1, i, i + 1], [0.9, 1, 0.9])
  return <motion.div className="slide" style={{ opacity, scale }}><Panel index={i} /></motion.div>
}

// The section pins to the screen. Scrolling slides the four product screens sideways,
// with a short pause on each one.
export default function HowItWorks() {
  const reduced = useReducedMotion()
  const narrow = useIsNarrow(960)
  const track = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(0)
  const { scrollYProgress } = useScroll({ target: track, offset: ['start start', 'end end'] })
  const smooth = useSpring(scrollYProgress, { stiffness: 160, damping: 32, mass: 0.4 })
  const pos = useTransform(reduced ? scrollYProgress : smooth, [0, 0.14, 0.3, 0.44, 0.56, 0.7, 0.86, 1], [0, 0, 1, 1, 2, 2, 3, 3])
  const x = useTransform(pos, v => `${-v * 25}%`)
  const bar = useTransform(pos, [0, 3], [0.06, 1])
  useMotionValueEvent(pos, 'change', v => setActive(Math.min(3, Math.max(0, Math.round(v)))))

  return (
    <section className="how" id="how" ref={track}>
      <div className="how-sticky wrap">
        <div className="how-left">
          <h2 className="section-title">How it works</h2>
          <div className="how-bar"><motion.i style={{ scaleX: bar }} /></div>
          {narrow ? (
            <AnimatePresence mode="wait" initial={false}>
              <motion.div key={active} className="how-now" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.3, ease }}>
                <h3><span>{active + 1}</span>{steps[active].title}</h3>
                <p>{steps[active].text}</p>
              </motion.div>
            </AnimatePresence>
          ) : (
            <ol>
              {steps.map((step, i) => (
                <li key={step.title} className={i === active ? 'on' : ''}>
                  <h3><span>{i + 1}</span>{step.title}</h3>
                  <motion.div initial={false} animate={{ height: i === active ? 'auto' : 0, opacity: i === active ? 1 : 0 }} transition={{ duration: 0.45, ease }} style={{ overflow: 'hidden' }}>
                    <p>{step.text}</p>
                  </motion.div>
                </li>
              ))}
            </ol>
          )}
        </div>
        <div className="panel">
          <motion.div className="how-track" style={{ x }}>
            {steps.map((step, i) => <Slide key={step.title} i={i} pos={pos} />)}
          </motion.div>
        </div>
      </div>
    </section>
  )
}
