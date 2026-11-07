import { useEffect, useRef, useState } from 'react'
import { MotionConfig, motion, useReducedMotion, useScroll, useTransform } from 'motion/react'
import MergeStage from './components/MergeStage'
import HowItWorks from './components/HowItWorks'
import NoteScene from './components/NoteScene'
import FeatureFailed from './components/FeatureFailed'
import { Check, FileGlyph, MailIcon, Mark, Rise, ScrollWords, WinBar, ease, useIsNarrow, useSeen } from './components/bits'
import { DEMO_URL, PRODUCT_NAME } from './config'
import { files, giftTotal, gifts, lateDonors, lists, money } from './data/sample'

const enter = (delay: number) => ({
  initial: { opacity: 0, y: 14, filter: 'blur(8px)' },
  animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
  transition: { duration: 0.8, delay, ease },
})

// The merge demo sits inside a product window that tilts flat as you scroll.
function HeroWindow() {
  const reduced = useReducedMotion()
  const narrow = useIsNarrow(960)
  const flat = reduced || narrow
  const { scrollY } = useScroll()
  const rotateX = useTransform(scrollY, [0, 360], [flat ? 0 : 9, 0])
  const scale = useTransform(scrollY, [0, 360], [flat ? 1 : 0.965, 1])
  const late = lateDonors.filter(d => d.late).length
  return (
    <motion.div className="hero-win-wrap" {...enter(0.4)}>
      <motion.div className="win hero-win" style={{ rotateX, scale, transformPerspective: 1600 }}>
        <WinBar title={`${PRODUCT_NAME} · Year-end letter list`} />
        <div className="app">
          <aside className="app-side" aria-hidden="true">
            <p className="app-side-h">Lists</p>
            <ul>{files.map(f => <li key={f.file}><FileGlyph /><span>{f.name}</span><em>{f.rows}</em></li>)}</ul>
            <p className="app-side-h">Review</p>
            <ul>
              <li className="on"><span className="app-dot" /><span>Possible matches</span><em>1</em></li>
              <li><span className="app-dot late" /><span>Late gifts</span><em className="late">{late}</em></li>
            </ul>
          </aside>
          <div className="app-main"><MergeStage /></div>
        </div>
      </motion.div>
    </motion.div>
  )
}

// Four spreadsheets. On wide screens, lines draw from Rosa's three rows into one person.
function Lists() {
  const [ref, on] = useSeen<HTMLDivElement>(0.35)
  const wide = !useIsNarrow(960)
  const person = useRef<HTMLDivElement>(null)
  const [paths, setPaths] = useState<{ d: string; x: number; y: number }[]>([])

  useEffect(() => {
    const box = ref.current
    if (!box || !wide) return
    // offsetTop/Left ignore the entrance transforms, so lines land where cards end up.
    const ro = new ResizeObserver(() => {
      const target = person.current
      if (!target) return
      const tx = target.offsetLeft + target.offsetWidth / 2
      const ty = target.offsetTop
      const out: { d: string; x: number; y: number }[] = []
      box.querySelectorAll<HTMLElement>('[data-rosa]').forEach(name => {
        const sheet = name.closest<HTMLElement>('.sheet')
        if (!sheet) return
        const x = sheet.offsetLeft + name.offsetLeft + name.offsetWidth / 2
        const y = sheet.offsetTop + sheet.offsetHeight
        const mid = (y + ty) / 2
        out.push({ d: `M${x} ${y} C${x} ${mid} ${tx} ${mid} ${tx} ${ty}`, x, y })
      })
      setPaths(out)
    })
    ro.observe(box)
    return () => ro.disconnect()
  }, [wide, ref])

  return (
    <div className="lists-box" ref={ref}>
      <div className="lists">
        {lists.map((list, i) => (
          <motion.div className="sheet" key={list.title} initial={{ opacity: 0, y: 12 }}
            animate={on ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.6, delay: i * 0.08, ease }}>
            <div className="sheet-bar"><FileGlyph /><h3>{list.title}</h3><span>{files[i].file.replace(/^.*\./, '.')}</span></div>
            <div className="sheet-cols"><i /><span>Name</span><span>Amount</span></div>
            <ul>
              {list.rows.map(([name, amount, rosa], r) => (
                <li key={name}>
                  <i>{r + 2}</i>
                  <span>{rosa ? <span data-rosa><Mark on={on} delay={0.6 + i * 0.15}>{name}</Mark></span> : name}</span>
                  <span>{money(amount)}</span>
                </li>
              ))}
            </ul>
          </motion.div>
        ))}
      </div>
      {wide && paths.length > 0 && (
        <svg className="lists-lines" aria-hidden="true">
          {paths.map((p, i) => (
            <g key={i}>
              <motion.circle cx={p.x} cy={p.y} r="3" initial={{ opacity: 0 }} animate={on ? { opacity: 1 } : {}} transition={{ delay: 1 + i * 0.12, duration: 0.3 }} />
              <motion.path d={p.d} initial={{ pathLength: 0 }} animate={on ? { pathLength: 1 } : {}} transition={{ delay: 1 + i * 0.12, duration: 0.9, ease }} />
            </g>
          ))}
        </svg>
      )}
      <motion.div className="person" ref={person} initial={{ opacity: 0, y: 10, filter: 'blur(6px)' }}
        animate={on ? { opacity: 1, y: 0, filter: 'blur(0px)' } : {}} transition={{ delay: wide ? 1.8 : 0.9, duration: 0.7, ease }}>
        <span className="avatar" aria-hidden="true">RD</span>
        <span><strong>Rosa M. Delgado</strong><small>One person on three lists · {gifts.length} gifts · {money(giftTotal)}</small></span>
      </motion.div>
    </div>
  )
}

const flowIn = [12.5, 37.5, 62.5, 87.5]

function Flow() {
  return (
    <Rise className="flow" delay={0.1}>
      <ul className="flow-files">
        {files.map(f => <li key={f.file}><FileGlyph /><span>{f.file}</span></li>)}
      </ul>
      <svg className="flow-lines" viewBox="0 0 80 100" preserveAspectRatio="none" aria-hidden="true">
        {flowIn.map(y => <path key={y} d={`M0 ${y} C44 ${y} 36 50 80 50`} vectorEffect="non-scaling-stroke" />)}
      </svg>
      <div className="flow-core"><span><MailIcon />{PRODUCT_NAME}</span><small>Finds matches, waits for you, watches gift timing</small></div>
      <svg className="flow-lines" viewBox="0 0 80 100" preserveAspectRatio="none" aria-hidden="true">
        {[25, 75].map(y => <path key={y} d={`M0 50 C44 50 36 ${y} 80 ${y}`} vectorEffect="non-scaling-stroke" />)}
      </svg>
      <ul className="flow-out">
        <li><strong>One list, each donor once</strong><small>Every gift still attached</small></li>
        <li><strong>Late gifts to call</strong><small>Each week, with a note ready</small></li>
      </ul>
    </Rise>
  )
}

export default function App() {
  const hasDemo = DEMO_URL.length > 0
  return (
    <MotionConfig reducedMotion="user">
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="top" id="top">
        <div className="wrap">
          <a className="logo" href="#top" aria-label={`${PRODUCT_NAME} home`}><MailIcon />{PRODUCT_NAME}</a>
          <nav aria-label="Main">
            <a href="#how">How it works</a>
            <a className="btn" href="#demo">Try the demo</a>
          </nav>
        </div>
      </header>

      <main id="main">
        <section className="hero">
          <div className="hero-bg" aria-hidden="true" />
          <div className="wrap">
            <motion.h1 {...enter(0.05)}>Rosa got the same letter <em>three times.</em></motion.h1>
            <motion.p className="hero-sub" {...enter(0.18)}>{PRODUCT_NAME} finds the same donor across your gift lists, shows you why, and merges only when you approve. Then it tells you when a regular gift is late, while there's still time to call.</motion.p>
            <motion.div className="hero-cta" {...enter(0.28)}>
              <a className="btn btn-accent" href="#how">See how it works</a>
              <a className="btn btn-ghost" href="#demo">Try the demo</a>
            </motion.div>
            <HeroWindow />
          </div>
        </section>

        <section className="wrap section" id="problem">
          <Rise><h2 className="section-title">Every gift arrives on <em>its own list.</em></h2></Rise>
          <Lists />
          <Rise><p className="hours">About <strong>5 hours</strong> every month goes to downloading those lists, importing them and typing in checks.</p></Rise>
        </section>

        <section className="quote section">
          <div className="wrap">
            <ScrollWords className="quote-text" text="“I just want to know each donor is on our list once, and to hear about a late gift while there's still time to call.”" />
            <p className="quote-who"><span className="avatar small" aria-hidden="true">D</span>Denise, fundraising coordinator, Tidepath Family Alliance</p>
          </div>
        </section>

        <HowItWorks />
        <NoteScene />
        <FeatureFailed />

        <section className="fit wrap section" id="fit">
          <Rise>
            <h2 className="section-title">Keep your <em>donor database.</em></h2>
            <p className="lede">{PRODUCT_NAME} works from the spreadsheets you already download, so there is nothing to migrate and nothing new to connect. It's built to be simple enough for a part-time staff member to run every week.</p>
          </Rise>
          <Rise className="promises" delay={0.1}>
            <h3>What {PRODUCT_NAME} promises</h3>
            <ul>
              {['Nothing merges without staff approval.', 'No giving history is ever deleted.', 'Nothing is sent to a donor without a person.', 'Donor information stays private.'].map(p => (
                <li key={p}><Check />{p}</li>
              ))}
            </ul>
          </Rise>
          <Flow />
        </section>
      </main>

      <footer className="end">
        <section className="demo wrap" id="demo">
          <h2 className="section-title">See it on <em>made-up donors.</em></h2>
          {hasDemo ? <a className="btn" href={DEMO_URL}>Open the demo</a> : <button className="btn" disabled>Demo link coming</button>}
        </section>
        <div className="end-notes wrap">
          <p>Tidepath Family Alliance and every donor on this page are made up. The problems are real, from a survey of 14 South Florida nonprofits.</p>
          <p>Built with Codex at the DevDay Exchange Community Hackathon, Miami, November 2026.<br />The Token Maxxers</p>
        </div>
        <p className="wordmark" aria-hidden="true">{PRODUCT_NAME}</p>
      </footer>
    </MotionConfig>
  )
}
