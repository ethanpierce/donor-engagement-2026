// Announcement banners: hide the ones this browser dismissed, wire the dismiss buttons.
// Runs inline right after the banners, so dismissed banners never flash.
(function () {
  var PREFIX = 'tidepath:announcement-dismissed:'
  function dismissed(key) { try { return localStorage.getItem(PREFIX + key) === '1' } catch (e) { return false } }
  document.querySelectorAll('[data-announcement-key]').forEach(function (el) {
    var key = el.getAttribute('data-announcement-key')
    if (dismissed(key)) { el.hidden = true; return }
    var btn = el.querySelector('[data-announce-dismiss]')
    if (btn) btn.addEventListener('click', function () {
      el.hidden = true
      try { localStorage.setItem(PREFIX + key, '1') } catch (e) {}
    })
  })
})()
