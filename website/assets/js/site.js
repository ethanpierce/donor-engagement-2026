// Page motion for the Tidepath Family landing page. No framework, no build step.
// Replaces the former React + Motion code with the same timings and easing.
(function () {
  'use strict'

  var reduced = matchMedia('(prefers-reduced-motion: reduce)').matches
  var wideQuery = matchMedia('(max-width:960px)') // matches = narrow
  var stageQuery = matchMedia('(max-width:820px)')
  var EASE = 'cubic-bezier(.22,1,.36,1)'
  var ease = bezier(0.22, 1, 0.36, 1)

  function bezier(x1, y1, x2, y2) {
    function at(t, p1, p2) { return 3 * (1 - t) * (1 - t) * t * p1 + 3 * (1 - t) * t * t * p2 + t * t * t }
    return function (x) {
      if (x <= 0) return 0
      if (x >= 1) return 1
      var lo = 0, hi = 1, t = 0.5
      for (var i = 0; i < 30; i++) {
        if (at(t, x1, x2) < x) lo = t; else hi = t
        t = (lo + hi) / 2
      }
      return at(t, y1, y2)
    }
  }
  function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)) }
  // Piecewise linear map, clamped at both ends.
  function interp(v, xs, ys) {
    if (v <= xs[0]) return ys[0]
    for (var i = 1; i < xs.length; i++) {
      if (v <= xs[i]) {
        var span = xs[i] - xs[i - 1]
        return span === 0 ? ys[i] : ys[i - 1] + (ys[i] - ys[i - 1]) * (v - xs[i - 1]) / span
      }
    }
    return ys[ys.length - 1]
  }
  function each(sel, root, fn) { Array.prototype.forEach.call((root || document).querySelectorAll(sel), fn) }

  // Numbers that count up from 0.
  function setCount(el, n) { el.textContent = el.getAttribute('data-prefix') + Math.round(n).toLocaleString('en-US') }
  function resetCount(el) { cancelAnimationFrame(el._raf); setCount(el, 0) }
  function runCount(el) {
    var to = +el.getAttribute('data-count')
    cancelAnimationFrame(el._raf)
    if (reduced) { setCount(el, to); return }
    var start = null
    function step(t) {
      if (start === null) start = t
      var p = Math.min(1, (t - start) / 900)
      setCount(el, to * ease(p))
      if (p < 1) el._raf = requestAnimationFrame(step)
    }
    el._raf = requestAnimationFrame(step)
  }

  // One-time "seen" triggers: [data-seen="amount"] adds .seen, lights marks, runs counters.
  function reveal(el) {
    el.classList.add('seen')
    each('.hl', el, function (h) { h.classList.add('on') })
    each('[data-count]', el, runCount)
  }
  each('[data-seen] [data-count]', null, resetCount)
  if ('IntersectionObserver' in window) {
    each('[data-seen]', null, function (el) {
      var io = new IntersectionObserver(function (entries) {
        if (entries[0].isIntersecting) { io.disconnect(); reveal(el) }
      }, { threshold: +el.getAttribute('data-seen') })
      io.observe(el)
    })
  } else {
    each('[data-seen]', null, reveal)
  }

  // Hero entrance on load.
  requestAnimationFrame(function () {
    requestAnimationFrame(function () { each('[data-enter]', null, function (el) { el.classList.add('seen') }) })
  })

  // Scroll-linked parts: hero tilt, quote words, pinned "How it works".
  var tiltEl = document.querySelector('[data-tilt]')
  function tilt() {
    if (!tiltEl) return
    var flat = reduced || wideQuery.matches
    var p = clamp(window.scrollY / 360, 0, 1)
    var rx = flat ? 0 : 9 * (1 - p)
    var sc = flat ? 1 : 0.965 + 0.035 * p
    tiltEl.style.transform = 'perspective(1600px) scale(' + sc + ') rotateX(' + rx + 'deg)'
  }

  var quote = document.querySelector('[data-scroll-words]')
  var words = quote ? quote.querySelectorAll('span > span') : []
  function quoteWords() {
    if (!quote || reduced) return
    var r = quote.getBoundingClientRect(), vh = window.innerHeight
    var p = clamp((0.85 * vh - r.top) / (0.35 * vh + r.height), 0, 1)
    var n = words.length
    for (var i = 0; i < n; i++) words[i].style.opacity = interp(p, [i / n, (i + 1.5) / n], [0.2, 1])
  }

  var how = document.querySelector('[data-how]')
  var howState = { x: 0, v: 0, last: 0, raf: 0, active: 0 }
  function howTarget() {
    var r = how.getBoundingClientRect()
    return clamp(-r.top / (r.height - window.innerHeight), 0, 1)
  }
  function howRender(x) {
    var pos = interp(x, [0, 0.14, 0.3, 0.44, 0.56, 0.7, 0.86, 1], [0, 0, 1, 1, 2, 2, 3, 3])
    how.querySelector('[data-how-track]').style.transform = 'translateX(' + (-pos * 25) + '%)'
    how.querySelector('[data-how-bar]').style.transform = 'scaleX(' + interp(pos, [0, 3], [0.06, 1]) + ')'
    each('[data-slide]', how, function (s, i) {
      s.style.opacity = interp(pos, [i - 1, i, i + 1], [0.3, 1, 0.3])
      s.style.transform = 'scale(' + interp(pos, [i - 1, i, i + 1], [0.9, 1, 0.9]) + ')'
    })
    var active = clamp(Math.round(pos), 0, 3)
    if (active !== howState.active) { howState.active = active; howStep(active) }
  }
  var nowTimer = 0
  function howStep(active) {
    each('[data-step]', how, function (li, i) { li.classList.toggle('on', i === active) })
    var now = how.querySelector('[data-how-now]')
    clearTimeout(nowTimer)
    now.classList.remove('in')
    now.classList.add('out')
    nowTimer = setTimeout(function () {
      var li = how.querySelectorAll('[data-step]')[howState.active]
      now.querySelector('h3').innerHTML = li.querySelector('h3').innerHTML
      now.querySelector('p').textContent = li.querySelector('p').textContent
      now.classList.remove('out')
      void now.offsetWidth
      now.classList.add('in')
    }, 300)
  }
  // Spring that follows scroll progress (stiffness 160, damping 32, mass 0.4).
  function howTick(t) {
    var target = howTarget()
    var dt = Math.min(0.064, (t - (howState.last || t)) / 1000)
    howState.last = t
    for (var s = 0; s < dt; s += 0.002) {
      var a = (-160 * (howState.x - target) - 32 * howState.v) / 0.4
      howState.v += a * 0.002
      howState.x += howState.v * 0.002
    }
    if (Math.abs(howState.x - target) < 0.0005 && Math.abs(howState.v) < 0.01) {
      howState.x = target; howState.v = 0; howState.raf = 0; howState.last = 0
    } else {
      howState.raf = requestAnimationFrame(howTick)
    }
    howRender(howState.x)
  }
  function howScroll() {
    if (!how) return
    if (reduced) { howState.x = howTarget(); howRender(howState.x); return }
    if (!howState.raf) howState.raf = requestAnimationFrame(howTick)
  }
  if (how) { howState.x = howTarget(); howRender(howState.x) }

  var scrollQueued = false
  function onScroll() {
    if (scrollQueued) return
    scrollQueued = true
    requestAnimationFrame(function () { scrollQueued = false; tilt(); quoteWords(); howScroll() })
  }
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('resize', onScroll)
  tilt(); quoteWords()

  // Lists: on wide screens, lines draw from Rosa's three rows into one person.
  var box = document.querySelector('[data-lists]')
  if (box) {
    var svg = box.querySelector('[data-lines]'), person = box.querySelector('[data-person]')
    var drawLines = function () {
      var wide = !wideQuery.matches
      person.style.setProperty('--d', wide ? '1.8s' : '.9s')
      svg.toggleAttribute('hidden', !wide)
      if (!wide) { svg.innerHTML = ''; return }
      var tx = person.offsetLeft + person.offsetWidth / 2, ty = person.offsetTop, out = ''
      each('[data-rosa]', box, function (name, i) {
        var sheet = name.closest('.sheet')
        var x = sheet.offsetLeft + name.offsetLeft + name.offsetWidth / 2
        var y = sheet.offsetTop + sheet.offsetHeight
        var mid = (y + ty) / 2, d = (1 + i * 0.12).toFixed(2) + 's'
        out += '<g><circle cx="' + x + '" cy="' + y + '" r="3" style="--d:' + d + '"></circle>' +
          '<path d="M' + x + ' ' + y + ' C' + x + ' ' + mid + ' ' + tx + ' ' + mid + ' ' + tx + ' ' + ty + '" pathLength="1" style="--d:' + d + '"></path></g>'
      })
      svg.innerHTML = out
    }
    if ('ResizeObserver' in window) new ResizeObserver(drawLines).observe(box)
    else drawLines()
    wideQuery.addEventListener('change', drawLines)
  }

  // Hero merge demo: arrive -> match -> ask -> (approve) merge -> done, or ask -> apart.
  var stage = document.querySelector('[data-stage]')
  if (stage) mergeStage(stage)

  function mergeStage(el) {
    var grid = el.querySelector('[data-grid]'), done = el.querySelector('[data-done]')
    var slots = grid.querySelectorAll('[data-slot]'), merged = done.querySelector('[data-merged]')
    var rowAsk = el.querySelector('[data-row-ask]'), rowEnd = el.querySelector('[data-row-end]')
    var result = el.querySelector('[data-result]'), cursor = el.querySelector('.cursor')
    var approveBtn = el.querySelector('[data-approve]'), apartBtn = el.querySelector('[data-apart]')
    var marks = grid.querySelectorAll('.hl')
    var phase = '', touched = false, barSeen = false, timers = [], auto = [], rowTimer = 0, anims = []

    function clear(list) { list.forEach(clearTimeout); list.length = 0 }
    function setPhase(p) {
      phase = p
      var lit = p !== 'arrive'
      el.classList.toggle('lit', lit)
      el.classList.toggle('ask', p === 'ask')
      approveBtn.disabled = apartBtn.disabled = p !== 'ask'
      for (var i = 0; i < marks.length; i++) marks[i].classList.toggle('on', lit)
      armAuto()
      if (p === 'merge') merge()
      if (p === 'done') { showDone(); showRow(rowEnd, 'One donor, one letter, and the total is right.') }
      if (p === 'apart') showRow(rowEnd, "Kept apart. We won't suggest this pair again.")
    }
    // If nobody clicks, the demo presses Approve itself, but only while the buttons are on screen.
    function armAuto() {
      clear(auto)
      if (phase !== 'ask' || reduced || !barSeen) return
      auto.push(setTimeout(function () { if (!touched) showCursor(true) }, 4200))
      auto.push(setTimeout(function () { if (!touched) approve() }, 5400))
    }
    function showCursor(on) {
      if (on) {
        cursor.removeAttribute('hidden')
        cursor.animate([{ transform: 'translate(60px,40px)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: 900, easing: EASE, fill: 'both' })
      } else if (!cursor.hasAttribute('hidden')) {
        cursor.animate([{ opacity: 0 }], { duration: 300, easing: EASE, fill: 'forwards' }).onfinish = function () { cursor.setAttribute('hidden', '') }
      }
    }
    // AnimatePresence mode="wait": the old row fades out, then the new one comes in.
    function showRow(row, text) {
      clearTimeout(rowTimer)
      var old = row === rowEnd ? rowAsk : rowEnd
      if (text) result.textContent = text
      if (old.hidden) return
      old.animate([{ opacity: 1 }, { opacity: 0 }], { duration: old === rowAsk ? 250 : 400, easing: EASE, fill: 'forwards' })
      rowTimer = setTimeout(function () {
        old.hidden = true
        old.getAnimations().forEach(function (a) { a.cancel() })
        row.hidden = false
        if (row === rowEnd) row.animate([{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }], { duration: 400, easing: EASE })
      }, old === rowAsk ? 250 : 400)
    }
    function merge() {
      var narrow = stageQuery.matches
      ;[0, 2].forEach(function (i) {
        var s = slots[i], side = i - 1
        var frames = narrow
          ? [{ height: s.offsetHeight + 'px', marginTop: getComputedStyle(s).marginTop, opacity: 1 }, { height: '0px', marginTop: '0px', opacity: 0 }]
          : [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateX(' + (-side * 104) + '%) scale(.96)' }]
        anims.push(s.animate(frames, { duration: 550, easing: EASE, fill: 'forwards' }))
      })
      timers.push(setTimeout(function () { setPhase('done') }, reduced ? 0 : 650))
    }
    function showDone() {
      var from = slots[1].getBoundingClientRect()
      each('[data-count]', done, resetCount)
      done.classList.remove('seen')
      grid.hidden = true
      done.hidden = false
      var to = merged.getBoundingClientRect()
      if (!reduced) {
        merged.animate([
          { transformOrigin: '0 0', transform: 'translate(' + (from.left - to.left) + 'px,' + (from.top - to.top) + 'px) scale(' + from.width / to.width + ',' + from.height / to.height + ')' },
          { transformOrigin: '0 0', transform: 'none' }
        ], { duration: 600, easing: EASE })
      }
      void done.offsetWidth
      reveal(done)
    }
    function approve() { showCursor(false); setPhase('merge') }
    function start(first) {
      clear(timers)
      touched = false
      cursor.setAttribute('hidden', '')
      anims.forEach(function (a) { a.cancel() }); anims = []
      done.hidden = true
      grid.hidden = false
      if (!first) showRow(rowAsk)
      setPhase(reduced ? 'ask' : 'arrive')
      if (reduced) return
      for (var i = 0; i < slots.length; i++) {
        anims.push(slots[i].animate([{ opacity: 0, transform: 'translateY(16px)' }, { opacity: 1, transform: 'none' }],
          { duration: 700, delay: 250 + i * 100, easing: EASE, fill: 'backwards' }))
      }
      timers.push(setTimeout(function () { setPhase('match') }, 1300))
      timers.push(setTimeout(function () { setPhase('ask') }, 3000))
    }

    approveBtn.addEventListener('click', function () { touched = true; approve() })
    apartBtn.addEventListener('click', function () { touched = true; showCursor(false); setPhase('apart') })
    el.querySelector('[data-replay]').addEventListener('click', function () { start(false) })
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) { barSeen = entries[0].isIntersecting; armAuto() }, { threshold: 0.8 })
        .observe(el.querySelector('[data-bar]'))
    }
    start(true)
  }
})()
