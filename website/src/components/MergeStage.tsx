import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, LayoutGroup, motion, useInView, useReducedMotion } from 'motion/react'
import { Check, Count, MailIcon, Mark, ease, useIsNarrow } from './bits'
import { giftTotal, gifts, money, reasons, records, totalFor } from '../data/sample'

type Phase = 'arrive' | 'match' | 'ask' | 'merge' | 'done' | 'apart'
type Rec = (typeof records)[number]

function RecordCard({ record, lit, delay }: { record: Rec; lit: boolean; delay: number }) {
  const last = record.name.replace(/^.*\s/, '')
  const first = record.name.slice(0, record.name.length - last.length).trim()
  const hasPhone = record.phone.startsWith('(')
  const count = gifts.filter(g => g.record === record.id).length
  return (
    <div className="card">
      <div className="card-top"><span className="card-kind"><MailIcon /><span>Year-end letter</span></span><span className="card-src">{record.source}</span></div>
      <p className="card-name">{first && <><Mark on={lit} delay={delay + 0.15}>{first}</Mark>{' '}</>}<Mark on={lit} delay={delay}>{last}</Mark></p>
      <p className="card-line">{record.email}</p>
      <p className="card-line">{hasPhone ? <Mark on={lit} delay={delay + 0.3}>{record.phone}</Mark> : <span className="faint">{record.phone}</span>}</p>
      <div className="card-foot"><span>{count} {count === 1 ? 'gift' : 'gifts'}</span><strong>{money(totalFor(record.id))}</strong></div>
    </div>
  )
}

function MergedCard() {
  return (
    <div className="card">
      <div className="card-top"><span className="card-kind"><MailIcon />Year-end letter</span><span className="card-badge"><Check />Merged</span></div>
      <p className="card-name">Rosa M. Delgado</p>
      <p className="card-line">rosa.delgado@example.com</p>
      <p className="card-line">rdelgado@example.org</p>
      <p className="card-line">(305) 555-0142</p>
      <div className="card-foot"><span>{gifts.length} gifts, 3 lists</span><strong><Count to={giftTotal} on /></strong></div>
    </div>
  )
}

export default function MergeStage() {
  const reduced = useReducedMotion()
  const narrow = useIsNarrow()
  const [phase, setPhase] = useState<Phase>(reduced ? 'ask' : 'arrive')
  const [run, setRun] = useState(0)
  const [cursor, setCursor] = useState(false)
  const touched = useRef(false)
  const bar = useRef<HTMLDivElement>(null)
  const barSeen = useInView(bar, { amount: 0.8 })

  const approve = () => { setCursor(false); setPhase('merge') }

  useEffect(() => {
    if (reduced) return
    const timers = [setTimeout(() => setPhase('match'), 1300), setTimeout(() => setPhase('ask'), 3000)]
    return () => timers.forEach(clearTimeout)
  }, [run, reduced])

  // If nobody clicks, the demo presses Approve itself, but only while the buttons are on screen.
  useEffect(() => {
    if (phase !== 'ask' || reduced || !barSeen) return
    const show = setTimeout(() => { if (!touched.current) setCursor(true) }, 4200)
    const press = setTimeout(() => { if (!touched.current) approve() }, 5400)
    return () => { clearTimeout(show); clearTimeout(press) }
  }, [phase, reduced, run, barSeen])

  useEffect(() => {
    if (phase !== 'merge') return
    const t = setTimeout(() => setPhase('done'), reduced ? 0 : 650)
    return () => clearTimeout(t)
  }, [phase, reduced])

  function apart() { touched.current = true; setCursor(false); setPhase('apart') }
  function replay() {
    touched.current = false
    setCursor(false)
    setPhase(reduced ? 'ask' : 'arrive')
    setRun(r => r + 1)
  }

  const done = phase === 'done'
  const lit = phase !== 'arrive'

  function pose(i: number) {
    const side = i - 1
    if (phase === 'merge' && side !== 0) {
      return narrow
        ? { opacity: 0, height: 0, marginTop: 0, y: 0, x: '0%', scale: 1 }
        : { opacity: 0, x: `${-side * 104}%`, scale: 0.96, y: 0 }
    }
    return { opacity: 1, x: '0%', y: 0, scale: 1, height: 'auto', marginTop: narrow && i > 0 ? 10 : 0 }
  }

  return (
    <section className="stage" aria-label="Sample merge of one donor found on three lists">
      <div className="stage-head"><span>One donor, three lists</span><span>Sample data</span></div>
      <LayoutGroup>
        <div className={done ? 'stage-grid is-done' : 'stage-grid'} key={run}>
          {!done ? records.map((record, i) => (
            <motion.div key={record.id} layoutId={record.id === 'b' ? `rosa-${run}` : undefined}
              className="slot" style={{ overflow: narrow ? 'hidden' : 'visible', zIndex: i === 1 ? 2 : 1, position: 'relative' }}
              initial={reduced ? false : { opacity: 0, y: 16 }}
              animate={pose(i)}
              transition={{ duration: phase === 'merge' ? 0.55 : 0.7, ease, delay: phase === 'arrive' ? 0.25 + i * 0.1 : 0 }}>
              <RecordCard record={record} lit={lit} delay={0.1 + i * 0.15} />
            </motion.div>
          )) : (
            <>
              <motion.div layoutId={`rosa-${run}`} className="slot" transition={{ duration: 0.6, ease }}>
                <MergedCard />
              </motion.div>
              <motion.div className="history" initial={{ opacity: 0, y: 12, filter: 'blur(6px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                transition={{ duration: 0.7, ease, delay: 0.3 }}>
                <div className="history-head"><span>Giving history</span><span>All gifts kept</span></div>
                <ul>
                  {gifts.map((g, i) => (
                    <motion.li key={g.date + g.source} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.45 + i * 0.06, duration: 0.5 }}>
                      <span>{g.date}</span><span>{g.source}</span><span>{money(g.amount)}</span>
                    </motion.li>
                  ))}
                </ul>
                <div className="history-foot"><span>{gifts.length} gifts kept. None lost.</span><strong><Count to={giftTotal} on /></strong></div>
              </motion.div>
            </>
          )}
        </div>
      </LayoutGroup>

      <div className="stage-bar" ref={bar}>
        <AnimatePresence mode="wait" initial={false}>
          {done || phase === 'apart' ? (
            <motion.div key="end" className="stage-bar-row" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.4, ease }}>
              <p className="stage-result">{done ? 'One donor, one letter, and the total is right.' : "Kept apart. We won't suggest this pair again."}</p>
              <button className="text-btn" onClick={replay}>Replay</button>
            </motion.div>
          ) : (
            <motion.div key="ask" className="stage-bar-row" exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <ul className="chips" aria-label="Why these records seem to match">
                {reasons.map((reason, i) => (
                  <motion.li key={reason} initial={false}
                    animate={lit ? { opacity: 1, y: 0 } : { opacity: 0, y: 6 }}
                    transition={{ duration: 0.5, ease, delay: lit ? 0.2 + i * 0.12 : 0 }}><Check />{reason}</motion.li>
                ))}
              </ul>
              <motion.div className="stage-actions" initial={false}
                animate={phase === 'ask' ? { opacity: 1, y: 0 } : { opacity: 0, y: 6 }} transition={{ duration: 0.5, ease }}>
                <button className="btn" disabled={phase !== 'ask'} onClick={() => { touched.current = true; approve() }}>
                  Approve merge
                  <AnimatePresence>
                    {cursor && (
                      <motion.svg className="cursor" viewBox="0 0 24 24" aria-hidden="true" initial={{ x: 60, y: 40, opacity: 0 }}
                        animate={{ x: 0, y: 0, opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.9, ease }}>
                        <path d="M4 3l6.5 17 2.4-7.1L20 10.5z" />
                      </motion.svg>
                    )}
                  </AnimatePresence>
                </button>
                <button className="text-btn" disabled={phase !== 'ask'} onClick={apart}>Not the same person</button>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  )
}
