// Tidepath portal page script: language switch, conditional fields,
// validation messages, photo resize and form submit. No dependencies.
(function () {
  "use strict";
  var I18N = window.TP_I18N;
  var LANGS = ["en", "es", "ht"];
  var params = new URLSearchParams(location.search);

  function store(key, value) {
    try {
      if (value === undefined) return localStorage.getItem(key);
      localStorage.setItem(key, value);
    } catch (e) { return null; }
  }

  function pickLang() {
    var q = params.get("lang");
    if (LANGS.indexOf(q) >= 0) return q;
    var saved = store("tp-lang");
    if (LANGS.indexOf(saved) >= 0) return saved;
    var nav = (navigator.language || "en").slice(0, 2).toLowerCase();
    return LANGS.indexOf(nav) >= 0 ? nav : "en";
  }

  var lang = pickLang();
  function t(key) {
    return (I18N[lang] && I18N[lang][key]) || I18N.en[key] || key;
  }

  function applyLang() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach(function (el) { el.textContent = t(el.getAttribute("data-i18n")); });
    document.querySelectorAll("[data-i18n-ph]").forEach(function (el) { el.placeholder = t(el.getAttribute("data-i18n-ph")); });
    document.querySelectorAll("[data-i18n-aria]").forEach(function (el) { el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria"))); });
    document.querySelectorAll(".lang-switch button").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.value === lang));
    });
    document.querySelectorAll("a[data-keep-lang]").forEach(function (a) {
      var u = new URL(a.getAttribute("href"), location.href);
      u.searchParams.set("lang", lang);
      a.href = u.pathname + u.search;
    });
    var titleKey = document.body.getAttribute("data-title");
    document.title = (titleKey ? t(titleKey) + " · " : "") + "Tidepath";
    // Re-translate any visible errors.
    document.querySelectorAll("[data-err]").forEach(function (el) { el.textContent = t(el.getAttribute("data-err")); });
  }

  function buildLangSwitch() {
    var box = document.querySelector(".lang-switch");
    if (!box) return;
    LANGS.forEach(function (code) {
      var b = document.createElement("button");
      b.type = "button";
      b.value = code;
      b.lang = code;
      b.textContent = I18N[code]["lang.name"];
      b.addEventListener("click", function () {
        lang = code;
        store("tp-lang", code);
        var u = new URL(location.href);
        u.searchParams.set("lang", code);
        history.replaceState(null, "", u.pathname + u.search);
        applyLang();
      });
      box.appendChild(b);
    });
  }

  // ---------- forms ----------

  function values(form) {
    var out = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.disabled || el.type === "file" || el.type === "submit" || el.type === "button") return;
      if (el.type === "radio") { if (el.checked) out[el.name] = el.value; else if (!(el.name in out)) out[el.name] = ""; return; }
      if (el.type === "checkbox") { out[el.name] = el.checked; return; }
      out[el.name] = el.value.trim();
    });
    return out;
  }

  function updateConditionals(form) {
    var v = values(form);
    form.querySelectorAll("[data-show-if]").forEach(function (box) {
      var parts = box.getAttribute("data-show-if").split("=");
      var show = v[parts[0]] === parts[1];
      box.hidden = !show;
      box.querySelectorAll("input, textarea, select").forEach(function (el) { el.disabled = !show; });
    });
  }

  function clearErrors(form) {
    form.querySelectorAll(".field.invalid").forEach(function (f) { f.classList.remove("invalid"); });
    form.querySelectorAll(".field .err").forEach(function (e) { e.textContent = ""; e.removeAttribute("data-err"); });
    form.querySelectorAll("[aria-invalid]").forEach(function (e) { e.removeAttribute("aria-invalid"); });
    var alert = form.querySelector(".alert");
    if (alert) { alert.hidden = true; alert.textContent = ""; alert.removeAttribute("data-err"); }
  }

  function showFieldErrors(form, errors) {
    var first = null;
    Object.keys(errors).forEach(function (name) {
      var field = form.querySelector('.field[data-field="' + name + '"]');
      if (!field) return;
      field.classList.add("invalid");
      var err = field.querySelector(".err");
      if (err) { err.setAttribute("data-err", "err." + errors[name]); err.textContent = t("err." + errors[name]); }
      var input = field.querySelector("input, textarea, select");
      if (input) input.setAttribute("aria-invalid", "true");
      if (!first) first = field;
    });
    showAlert(form, "err.summary");
    if (first) {
      first.scrollIntoView({ behavior: "smooth", block: "center" });
      var focusable = first.querySelector("input, textarea, select");
      if (focusable) setTimeout(function () { focusable.focus({ preventScroll: true }); }, 300);
    }
  }

  function showAlert(form, key) {
    var alert = form.querySelector(".alert");
    if (!alert) return;
    alert.hidden = false;
    alert.setAttribute("data-err", key);
    alert.textContent = t(key);
  }

  // Light client checks for instant feedback. The server checks everything again.
  function localErrors(form, v) {
    var e = {};
    form.querySelectorAll("[required]").forEach(function (el) {
      if (el.disabled) return;
      if (el.type === "checkbox") { if (!el.checked) e[el.name] = el.getAttribute("data-err-code") || "required"; return; }
      if (el.type === "radio") { if (!v[el.name]) e[el.name] = "required"; return; }
      if (!el.value.trim()) e[el.name] = el.type === "date" ? "date" : "required";
    });
    form.querySelectorAll('input[type="email"]').forEach(function (el) {
      if (!el.disabled && el.value.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(el.value.trim())) e[el.name] = "email";
    });
    form.querySelectorAll('input[type="tel"]').forEach(function (el) {
      var s = el.value.trim();
      if (!el.disabled && s && (!/^[+()\d\s.-]{7,20}$/.test(s) || s.replace(/\D/g, "").length < 7)) e[el.name] = "phone";
    });
    if (form.hasAttribute("data-need-contact") && !v.phone && !v.email && !e.phone) e.phone = "contact";
    return e;
  }

  // Resize a photo to at most 1600 px and JPEG, so phone photos fit the limit.
  function readPhoto(file) {
    return new Promise(function (resolve, reject) {
      if (!/^image\/(jpeg|png|webp|gif)$/.test(file.type)) return reject("photo");
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () {
        var scale = Math.min(1, 1600 / Math.max(img.width, img.height));
        var c = document.createElement("canvas");
        c.width = Math.round(img.width * scale);
        c.height = Math.round(img.height * scale);
        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(url);
        var data = c.toDataURL("image/jpeg", 0.82);
        if (data.length * 0.75 > 5 * 1024 * 1024) return reject("photoSize");
        resolve(data);
      };
      img.onerror = function () { URL.revokeObjectURL(url); reject("photo"); };
      img.src = url;
    });
  }

  function setupPhoto(form) {
    var input = form.querySelector('input[type="file"]');
    if (!input) return;
    var preview = form.querySelector(".photo-preview");
    var remove = form.querySelector(".photo-remove");
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) { preview.hidden = true; return; }
      preview.querySelector("img").src = URL.createObjectURL(file);
      preview.hidden = false;
    });
    remove.addEventListener("click", function () {
      input.value = "";
      preview.hidden = true;
    });
  }

  function submit(form, extra) {
    clearErrors(form);
    var v = values(form);
    Object.keys(extra || {}).forEach(function (k) { v[k] = extra[k]; });
    var errs = localErrors(form, v);
    if (Object.keys(errs).length) return showFieldErrors(form, errs);

    var button = (extra && extra.decision && form.querySelector('[data-decision="' + extra.decision + '"]')) || form.querySelector('button[type="submit"]');
    var buttons = form.querySelectorAll("button");
    var label = button.getAttribute("data-label") || button.querySelector("[data-i18n]").getAttribute("data-i18n");
    button.setAttribute("data-label", label);
    buttons.forEach(function (b) { b.disabled = true; });
    var labelEl = button.querySelector("[data-i18n]");
    labelEl.setAttribute("data-i18n", "sending");
    labelEl.textContent = t("sending");
    function done() {
      buttons.forEach(function (b) { b.disabled = false; });
      labelEl.setAttribute("data-i18n", label);
      labelEl.textContent = t(label);
    }

    var fileInput = form.querySelector('input[type="file"]');
    var file = fileInput && fileInput.files && fileInput.files[0];
    var ready = file ? readPhoto(file).then(function (d) { v.photo = d; }) : Promise.resolve();

    ready.then(function () {
      return fetch("/api/submit/" + form.getAttribute("data-form"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(v),
      }).catch(function () { throw { network: true }; });
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (body) {
        if (res.ok && body.ok) {
          var q = new URLSearchParams({ form: form.getAttribute("data-form"), ref: body.ref || "", lang: lang });
          if (v.urgent === "yes") q.set("urgent", "1");
          location.href = "/thanks?" + q.toString();
          return;
        }
        done();
        if (res.status === 400 && body.fields) return showFieldErrors(form, body.fields);
        var key = { 429: "err.rate", 413: "err.too_large", 502: "err.upstream", 503: "err.config" }[res.status] || "err.server";
        showAlert(form, key);
        form.querySelector(".alert").scrollIntoView({ behavior: "smooth", block: "center" });
      });
    }).catch(function (err) {
      done();
      if (err === "photo" || err === "photoSize") return showFieldErrors(form, { photo: err });
      showAlert(form, err && err.network ? "err.network" : "err.server");
    });
  }

  function setupForm(form) {
    form.addEventListener("change", function () { updateConditionals(form); });
    form.addEventListener("input", function (ev) {
      var field = ev.target.closest(".field.invalid");
      if (field) {
        field.classList.remove("invalid");
        var err = field.querySelector(".err");
        if (err) { err.textContent = ""; err.removeAttribute("data-err"); }
      }
    });
    form.querySelectorAll('input[type="date"][data-today]').forEach(function (el) {
      if (!el.value) {
        var d = new Date();
        el.value = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
      }
      el.max = el.value;
    });
    setupPhoto(form);
    updateConditionals(form);
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      submit(form);
    });
  }

  // ---------- page specific ----------

  function setupApprove() {
    var form = document.querySelector('form[data-form="approve"]');
    if (!form) return;
    var request = (params.get("request") || "").toUpperCase();
    var version = (params.get("version") || "").toLowerCase();
    var valid = /^W\d{3,6}$/.test(request) && /^v\d{1,3}$/.test(version);
    if (!valid) {
      document.querySelector(".approve-missing").hidden = false;
      document.querySelector(".approve-body").hidden = true;
      return;
    }
    document.querySelectorAll("[data-request]").forEach(function (el) { el.textContent = request; });
    document.querySelectorAll("[data-version]").forEach(function (el) { el.textContent = version; });
    form.querySelector('[name="request"]').value = request;
    form.querySelector('[name="version"]').value = version;
    var changes = form.querySelector(".changes-box");
    form.querySelector('[data-decision="approve"]').addEventListener("click", function () {
      changes.hidden = true;
      changes.querySelector("textarea").disabled = true;
      submit(form, { decision: "approve" });
    });
    form.querySelector('[data-action="show-changes"]').addEventListener("click", function () {
      changes.hidden = false;
      var ta = changes.querySelector("textarea");
      ta.disabled = false;
      ta.focus();
    });
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      submit(form, { decision: "changes" });
    });
  }

  function setupThanks() {
    var box = document.querySelector(".thanks");
    if (!box) return;
    var form = params.get("form");
    var key = { volunteer: "thanks.volunteer", workshop: "thanks.workshop", family: "thanks.family", approve: "thanks.approve" }[form] || "thanks.volunteer";
    box.querySelector(".thanks-text").setAttribute("data-i18n", key);
    if (form === "volunteer" && params.get("urgent") === "1") box.querySelector(".thanks-urgent").hidden = false;
    var ref = params.get("ref");
    if (ref && /^TP-[0-9A-F]{6}$/.test(ref)) {
      box.querySelector(".ref-code").textContent = ref;
      box.querySelector(".ref").hidden = false;
    }
  }

  buildLangSwitch();
  document.querySelectorAll("form[data-form]").forEach(function (f) {
    if (f.getAttribute("data-form") !== "approve") setupForm(f);
  });
  setupApprove();
  setupThanks();
  applyLang();
})();
