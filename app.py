import base64
import io
import re
from urllib.parse import quote

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

# Handle: 2+ chars of letters/digits/._-  Bank: 2+ letters only.
VPA_RE = re.compile(r"^[A-Za-z0-9._-]{2,256}@[A-Za-z]{2,64}$")
GST_SLABS = {0, 5, 12, 18, 28}
MAX_RUPEES = 100000

PAGE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>UPISave — UPI QR Generator</title>
<style>
  :root {
    --bg: #0d1117;
    --panel: #161b22;
    --panel2: #1c2330;
    --border: #2d333b;
    --text: #e6edf3;
    --muted: #8b949e;
    --accent: #3fb950;
    --accent2: #58a6ff;
    --error: #f85149;
    --track: #30363d;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    min-height: 100vh;
    padding: 32px 24px;
  }
  h1 { font-size: 22px; font-weight: 600; margin-bottom: 4px; }
  .sub { color: var(--muted); font-size: 13px; margin-bottom: 28px; }
  .layout {
    display: grid;
    grid-template-columns: minmax(320px, 460px) minmax(320px, 420px);
    gap: 24px;
    max-width: 960px;
    margin: 0 auto;
  }
  .header { max-width: 960px; margin: 0 auto; }
  .card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
  }
  .field { margin-bottom: 18px; }
  label { display: block; font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
  .input-wrap { position: relative; }
  input[type="text"] {
    width: 100%;
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    padding: 10px 36px 10px 12px;
    font-size: 14px;
    outline: none;
  }
  input[type="text"]:focus { border-color: var(--accent2); }
  input[type="text"].bad { border-color: var(--error); }
  input[type="text"].ok { border-color: var(--accent); }
  input::placeholder { color: #545d68; }
  .valid-mark {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--accent);
    font-weight: 700;
    display: none;
    pointer-events: none;
  }
  .valid-mark.show { display: block; }
  .slider-row { display: flex; align-items: center; gap: 12px; }
  input[type="range"] {
    flex: 1;
    -webkit-appearance: none;
    appearance: none;
    height: 6px;
    border-radius: 3px;
    background: var(--track);
    outline: none;
  }
  input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 18px; height: 18px;
    border-radius: 50%;
    background: var(--accent2);
    border: 2px solid var(--bg);
    cursor: pointer;
  }
  input[type="range"]::-moz-range-thumb {
    width: 16px; height: 16px;
    border-radius: 50%;
    background: var(--accent2);
    border: 2px solid var(--bg);
    cursor: pointer;
  }
  input[type="number"], input.amount-input {
    width: 84px;
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    padding: 8px 10px;
    font-size: 14px;
    outline: none;
    text-align: right;
  }
  input[type="number"]:focus, input.amount-input:focus { border-color: var(--accent2); }
  input.amount-input {
    width: 100%;
    text-align: left;
    padding: 10px 12px;
    font-size: 16px;
  }
  input.amount-input.bad { border-color: var(--error); }
  .pills { display: flex; gap: 8px; }
  .pill {
    flex: 1;
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 999px;
    color: var(--text);
    padding: 8px 0;
    font-size: 13px;
    cursor: pointer;
    text-align: center;
  }
  .pill.active { background: var(--accent2); border-color: var(--accent2); color: #0d1117; font-weight: 600; }
  .chips { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
  .chip {
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 999px;
    color: var(--text);
    padding: 6px 14px;
    font-size: 13px;
    cursor: pointer;
  }
  .chip.active { background: var(--accent2); border-color: var(--accent2); color: #0d1117; font-weight: 600; }
  .err { color: var(--error); font-size: 12px; margin-top: 5px; min-height: 15px; }
  .breakdown { font-size: 14px; }
  .breakdown .row { display: flex; justify-content: space-between; padding: 7px 0; color: var(--muted); }
  .breakdown .row span:last-child { color: var(--text); font-variant-numeric: tabular-nums; }
  .breakdown .total {
    border-top: 1px solid var(--border);
    margin-top: 6px; padding-top: 12px;
    font-size: 17px; font-weight: 700;
  }
  .breakdown .total span { color: var(--accent) !important; }
  .uri-box {
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11.5px;
    color: var(--accent2);
    word-break: break-all;
    margin-top: 8px;
    line-height: 1.5;
  }
  .qr-wrap { text-align: center; margin-top: 20px; }
  .qr-wrap img {
    width: 240px; height: 240px;
    border-radius: 12px;
    background: #fff;
    padding: 10px;
    display: none;
  }
  .qr-wrap img.show { display: inline-block; }
  .qr-placeholder {
    width: 240px; height: 240px;
    border: 2px dashed var(--border);
    border-radius: 12px;
    display: inline-flex;
    flex-direction: column;
    align-items: center; justify-content: center;
    gap: 12px;
    color: var(--muted);
    font-size: 13px;
    overflow: hidden;
  }
  .ghost-qr {
    width: 140px; height: 140px;
    color: var(--muted);
    filter: blur(2px);
    opacity: 0.3;
  }
  .qr-actions { display: flex; gap: 10px; justify-content: center; }
  .btn {
    display: inline-block;
    margin-top: 14px;
    background: var(--accent);
    color: #0d1117;
    border: none;
    border-radius: 8px;
    padding: 10px 22px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    text-decoration: none;
  }
  .btn.secondary { background: var(--panel2); color: var(--text); border: 1px solid var(--border); }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .section-title { font-size: 13px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }
  .right-col > .card + .card { margin-top: 24px; }
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
  }
  .brand-logo {
    width: 30px; height: 30px;
    border-radius: 8px;
    background: linear-gradient(135deg, var(--accent2), var(--accent));
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
  }
  .brand-logo svg { width: 18px; height: 18px; }
  .brand-name { font-size: 15px; font-weight: 700; letter-spacing: 0.2px; }
  .header-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
  .auth-area { display: flex; align-items: center; gap: 10px; min-height: 40px; }
  .user-chip {
    display: flex; align-items: center; gap: 8px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 5px 12px 5px 6px;
    font-size: 13px;
  }
  .user-chip img { width: 26px; height: 26px; border-radius: 50%; }
  .link-btn { background: none; border: none; color: var(--accent2); font-size: 12px; cursor: pointer; padding: 0; }
  .nav-tabs { display: flex; gap: 16px; margin-bottom: 24px; }
  .nav-tab {
    color: var(--muted);
    text-decoration: none;
    font-size: 14px; font-weight: 600;
    padding-bottom: 4px;
    border-bottom: 2px solid transparent;
  }
  .nav-tab.active { color: var(--text); border-bottom-color: var(--accent2); }
  .save-hint { color: var(--muted); font-size: 12px; margin-top: 10px; }
  .lib-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
    max-width: 960px;
    margin: 0 auto;
  }
  .lib-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    text-align: center;
  }
  .lib-card img { width: 100%; max-width: 180px; background: #fff; border-radius: 8px; padding: 6px; }
  .lib-name { font-weight: 600; font-size: 14px; margin-top: 10px; }
  .lib-amount { color: var(--accent); font-weight: 700; font-size: 15px; margin-top: 4px; }
  .lib-meta { color: var(--muted); font-size: 12px; margin-top: 4px; word-break: break-word; }
  .lib-actions { display: flex; gap: 8px; justify-content: center; margin-top: 12px; }
  .btn.small { padding: 6px 12px; font-size: 12px; margin-top: 0; }
  .btn.danger { background: transparent; color: var(--error); border: 1px solid var(--error); }
  .empty-lib { text-align: center; color: var(--muted); padding: 60px 20px; max-width: 960px; margin: 0 auto; font-size: 14px; }
  .footer-badge {
    position: fixed;
    left: 20px;
    bottom: 20px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 12px;
    color: var(--muted);
    box-shadow: 0 4px 14px rgba(0,0,0,0.35);
    z-index: 10;
  }
  .footer-badge strong { color: var(--text); }
  @media (max-width: 760px) {
    .footer-badge { position: static; margin: 24px auto 0; width: fit-content; }
  }
  @media (max-width: 760px) {
    .layout { grid-template-columns: 1fr; }
    /* Flatten right-col so all three cards become grid items, then reorder:
       form first so users complete it before seeing the output */
    .right-col { display: contents; }
    .right-col > .card + .card { margin-top: 0; }
    .form-card { order: 0; }
    .qr-card { order: 1; }
    .calc-card { order: 2; }
  }
</style>
</head>
<body>
<div class="header">
  <div class="header-row">
    <div class="brand">
      <div class="brand-logo">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="3" y="3" width="7" height="7" rx="1.5" fill="#0d1117"/>
          <rect x="14" y="3" width="7" height="7" rx="1.5" fill="#0d1117"/>
          <rect x="3" y="14" width="7" height="7" rx="1.5" fill="#0d1117"/>
          <rect x="14" y="14" width="7" height="7" rx="1.5" fill="#0d1117" fill-opacity="0.55"/>
        </svg>
      </div>
      <div class="brand-name">UPISave</div>
    </div>
    <div class="auth-area">
      <div id="gsiBtn"></div>
      <div class="user-chip" id="userChip" style="display:none">
        <img id="userPic" alt="" referrerpolicy="no-referrer">
        <span id="userName"></span>
        <button class="link-btn" id="signOutBtn" type="button">Sign out</button>
      </div>
    </div>
  </div>
  <h1>UPI QR Generator</h1>
  <div class="sub">Generate a scannable UPI payment QR with live amount calculation</div>
  <div class="nav-tabs">
    <a class="nav-tab active" id="tabGen" href="#">Generator</a>
    <a class="nav-tab" id="tabLib" href="#library" style="display:none">My Library</a>
  </div>
</div>
<div class="layout">
  <div class="card form-card">
    <div class="field">
      <label for="vpa">UPI ID (VPA)</label>
      <div class="input-wrap">
        <input type="text" id="vpa" value="" placeholder="yourname@bank" spellcheck="false" autocapitalize="none" autocomplete="off">
        <span class="valid-mark" id="vpaOk">&#10003;</span>
      </div>
      <div class="err" id="vpaErr"></div>
    </div>
    <div class="field">
      <label for="name">Payee Name</label>
      <input type="text" id="name" value="" placeholder="e.g. Asha General Stores">
    </div>
    <div class="field">
      <label for="note">Transaction Note</label>
      <input type="text" id="note" value="" placeholder="Optional — e.g. Invoice #42">
    </div>
    <div class="field">
      <label for="rupeesNum">Amount (&#8377;)</label>
      <input class="amount-input" type="text" id="rupeesNum" inputmode="numeric" value="500" placeholder="Enter amount" autocomplete="off">
      <div class="chips" id="amountChips">
        <button type="button" class="chip" data-amt="100">&#8377;100</button>
        <button type="button" class="chip" data-amt="500">&#8377;500</button>
        <button type="button" class="chip" data-amt="1000">&#8377;1,000</button>
        <button type="button" class="chip" data-amt="2000">&#8377;2,000</button>
        <button type="button" class="chip" data-amt="5000">&#8377;5,000</button>
      </div>
      <div class="err" id="amtErr"></div>
    </div>
    <div class="field">
      <label for="paiseNum">Paise</label>
      <div class="slider-row">
        <input type="range" id="paise" min="0" max="99" value="0">
        <input type="number" id="paiseNum" inputmode="numeric" min="0" max="99" value="0">
      </div>
    </div>
    <div class="field">
      <label for="tip_pctNum">Tip %</label>
      <div class="slider-row">
        <input type="range" id="tip_pct" min="0" max="25" value="0">
        <input type="number" id="tip_pctNum" inputmode="numeric" min="0" max="25" value="0">
      </div>
      <div class="chips" id="tipChips">
        <button type="button" class="chip" data-tip="0">0%</button>
        <button type="button" class="chip" data-tip="5">5%</button>
        <button type="button" class="chip" data-tip="10">10%</button>
        <button type="button" class="chip" data-tip="15">15%</button>
        <button type="button" class="chip" data-tip="20">20%</button>
      </div>
    </div>
    <div class="field">
      <label>GST %</label>
      <div class="pills" id="gstPills">
        <button type="button" class="pill active" data-gst="0">0%</button>
        <button type="button" class="pill" data-gst="5">5%</button>
        <button type="button" class="pill" data-gst="12">12%</button>
        <button type="button" class="pill" data-gst="18">18%</button>
        <button type="button" class="pill" data-gst="28">28%</button>
      </div>
    </div>
    <div class="err" id="apiErr"></div>
  </div>

  <div class="right-col">
    <div class="card calc-card">
      <div class="section-title">Calculation</div>
      <div class="breakdown">
        <div class="row"><span id="subLabel">Subtotal</span><span id="subtotal">&#8377;0.00</span></div>
        <div class="row"><span id="tipLabel">Tip (0%)</span><span id="tipAmt">&#8377;0.00</span></div>
        <div class="row"><span id="gstLabel">GST (0%)</span><span id="gstAmt">&#8377;0.00</span></div>
        <div class="row total"><span>Total</span><span id="total">&#8377;0.00</span></div>
      </div>
      <div class="section-title" style="margin-top:18px;">UPI URI</div>
      <div class="uri-box" id="uriPreview">&mdash;</div>
    </div>
    <div class="card qr-card">
      <div class="section-title">QR Code</div>
      <div class="qr-wrap">
        <div class="qr-placeholder" id="qrPlaceholder">
          <svg class="ghost-qr" viewBox="0 0 25 25" xmlns="http://www.w3.org/2000/svg" fill="currentColor" aria-hidden="true">
            <rect x="0" y="0" width="7" height="7"/><rect x="2" y="2" width="3" height="3" fill="var(--panel)"/>
            <rect x="18" y="0" width="7" height="7"/><rect x="20" y="2" width="3" height="3" fill="var(--panel)"/>
            <rect x="0" y="18" width="7" height="7"/><rect x="2" y="20" width="3" height="3" fill="var(--panel)"/>
            <rect x="9" y="0" width="2" height="2"/><rect x="13" y="1" width="2" height="2"/>
            <rect x="10" y="4" width="2" height="2"/><rect x="14" y="5" width="2" height="2"/>
            <rect x="0" y="9" width="2" height="2"/><rect x="4" y="10" width="2" height="2"/>
            <rect x="8" y="9" width="2" height="2"/><rect x="12" y="10" width="3" height="2"/>
            <rect x="17" y="9" width="2" height="2"/><rect x="21" y="10" width="2" height="2"/>
            <rect x="2" y="13" width="2" height="2"/><rect x="6" y="14" width="2" height="2"/>
            <rect x="10" y="13" width="2" height="3"/><rect x="15" y="13" width="2" height="2"/>
            <rect x="19" y="14" width="3" height="2"/><rect x="23" y="13" width="2" height="2"/>
            <rect x="9" y="18" width="2" height="2"/><rect x="13" y="19" width="2" height="2"/>
            <rect x="17" y="18" width="2" height="2"/><rect x="21" y="19" width="2" height="2"/>
            <rect x="10" y="22" width="3" height="2"/><rect x="15" y="22" width="2" height="2"/>
            <rect x="20" y="22" width="2" height="2"/>
          </svg>
          <span id="qrHint">Fill in a valid UPI ID and amount</span>
        </div>
        <img id="qrImg" alt="UPI QR code">
        <div class="qr-actions">
          <button class="btn" id="downloadBtn" disabled>Download QR</button>
          <button class="btn secondary" id="shareBtn" disabled>Share</button>
          <button class="btn secondary" id="saveBtn" disabled>Save</button>
        </div>
        <div class="save-hint" id="saveHint">Sign in with Google to save QRs to your library.</div>
      </div>
    </div>
  </div>
</div>

<div id="libraryView" style="display:none">
  <div class="lib-grid" id="libGrid"></div>
  <div class="empty-lib" id="libEmpty" style="display:none"></div>
</div>

<div class="footer-badge">UPISave by <strong>Veer Aditya Mirza</strong></div>

<script>
(function () {
  var DEBOUNCE_MS = 400;
  var MAX_RUPEES = 100000;
  var debounceTimer = null;
  var gst = 0;

  var $ = function (id) { return document.getElementById(id); };
  var VPA_RE = /^[A-Za-z0-9._-]{2,}@[A-Za-z]{2,}$/;
  var inr = new Intl.NumberFormat("en-IN", {
    style: "currency", currency: "INR",
    minimumFractionDigits: 2, maximumFractionDigits: 2
  });

  function fmt(n) { return inr.format(n); }

  function paintSlider(el) {
    var min = +el.min, max = +el.max, val = +el.value;
    var pct = ((val - min) / (max - min)) * 100;
    el.style.background =
      "linear-gradient(to right, var(--accent2) " + pct + "%, var(--track) " + pct + "%)";
  }

  // Paired slider + number inputs (paise, tip). The number box only ever
  // holds digits and is clamped immediately, so what you see is what is used.
  ["paise", "tip_pct"].forEach(function (id) {
    var range = $(id), num = $(id + "Num");
    range.addEventListener("input", function () {
      num.value = range.value;
      paintSlider(range);
      onChange();
    });
    num.addEventListener("input", function () {
      var digits = num.value.replace(/\D/g, "");
      var v = digits === "" ? 0 : Math.min(+range.max, +digits);
      if (num.value !== String(v) && digits !== "") num.value = v;
      range.value = v;
      paintSlider(range);
      onChange();
    });
    num.addEventListener("blur", function () {
      var digits = num.value.replace(/\D/g, "");
      num.value = digits === "" ? 0 : Math.min(+range.max, +digits);
    });
    paintSlider(range);
  });

  // Amount: free typing with digits only; validated, never silently changed.
  $("rupeesNum").addEventListener("input", function () {
    var cleaned = this.value.replace(/\D/g, "");
    if (this.value !== cleaned) this.value = cleaned;
    syncAmountChips();
    onChange();
  });

  $("amountChips").addEventListener("click", function (e) {
    var chip = e.target.closest(".chip");
    if (!chip) return;
    $("rupeesNum").value = chip.dataset.amt;
    syncAmountChips();
    onChange();
  });

  function syncAmountChips() {
    var v = $("rupeesNum").value;
    document.querySelectorAll("#amountChips .chip").forEach(function (c) {
      c.classList.toggle("active", c.dataset.amt === v);
    });
  }

  $("tipChips").addEventListener("click", function (e) {
    var chip = e.target.closest(".chip");
    if (!chip) return;
    $("tip_pctNum").value = chip.dataset.tip;
    $("tip_pct").value = chip.dataset.tip;
    paintSlider($("tip_pct"));
    onChange();
  });

  function syncTipChips(v) {
    document.querySelectorAll("#tipChips .chip").forEach(function (c) {
      c.classList.toggle("active", c.dataset.tip === String(v));
    });
  }

  ["vpa", "name", "note"].forEach(function (id) {
    $(id).addEventListener("input", onChange);
  });

  $("gstPills").addEventListener("click", function (e) {
    var btn = e.target.closest(".pill");
    if (!btn) return;
    gst = +btn.dataset.gst;
    document.querySelectorAll(".pill").forEach(function (p) { p.classList.remove("active"); });
    btn.classList.add("active");
    onChange();
  });

  function readState() {
    return {
      vpa: $("vpa").value.trim(),
      name: $("name").value.trim(),
      note: $("note").value.trim(),
      rupees: parseInt($("rupeesNum").value, 10),
      paise: Math.min(99, parseInt($("paiseNum").value, 10) || 0),
      tip_pct: Math.min(25, parseInt($("tip_pctNum").value, 10) || 0),
      gst_pct: gst
    };
  }

  // GST applies to the subtotal only; tips are not taxed.
  function computeLocal(s) {
    var subtotal = s.rupees + s.paise / 100;
    var tipAmt = subtotal * s.tip_pct / 100;
    var gstAmt = subtotal * s.gst_pct / 100;
    var total = Math.round((subtotal + tipAmt + gstAmt) * 100) / 100;
    return { subtotal: subtotal, tipAmt: tipAmt, gstAmt: gstAmt, total: total };
  }

  function buildUri(s, total) {
    var uri = "upi://pay?pa=" + s.vpa;
    if (s.name) uri += "&pn=" + encodeURIComponent(s.name);
    uri += "&am=" + total.toFixed(2) + "&cu=INR";
    if (s.note) uri += "&tn=" + encodeURIComponent(s.note);
    return uri;
  }

  function validate(s) {
    var vpaOk = VPA_RE.test(s.vpa);
    var vpaField = $("vpa");
    vpaField.classList.toggle("bad", !vpaOk && s.vpa !== "");
    vpaField.classList.toggle("ok", vpaOk);
    $("vpaOk").classList.toggle("show", vpaOk);
    if (s.vpa === "") {
      $("vpaErr").textContent = "UPI ID is required.";
    } else if (!vpaOk) {
      $("vpaErr").textContent = "Enter as name@bank, e.g. shopname@okaxis";
    } else {
      $("vpaErr").textContent = "";
    }

    var amtRaw = $("rupeesNum").value.trim();
    var amtOk = amtRaw !== "" && Number.isInteger(s.rupees) && s.rupees >= 1 && s.rupees <= MAX_RUPEES;
    $("rupeesNum").classList.toggle("bad", !amtOk);
    if (amtRaw === "") {
      $("amtErr").textContent = "Amount is required.";
    } else if (!amtOk) {
      $("amtErr").textContent = "Enter an amount between ₹1 and ₹1,00,000.";
    } else {
      $("amtErr").textContent = "";
    }

    return vpaOk && amtOk;
  }

  function setOutputEnabled(on) {
    $("downloadBtn").disabled = !on;
    $("shareBtn").disabled = !on;
    if (!on) {
      $("saveBtn").disabled = true;
      $("qrImg").classList.remove("show");
      $("qrPlaceholder").style.display = "inline-flex";
      $("uriPreview").textContent = "—";
    }
  }

  function updatePreview() {
    var s = readState();
    var valid = validate(s);
    var safe = { rupees: valid ? s.rupees : 0, paise: s.paise, tip_pct: s.tip_pct, gst_pct: s.gst_pct };
    var c = computeLocal(safe);

    $("subtotal").textContent = fmt(c.subtotal);
    $("tipLabel").textContent = "Tip (" + s.tip_pct + "%)";
    $("tipAmt").textContent = fmt(c.tipAmt);
    $("gstLabel").textContent = "GST (" + s.gst_pct + "%)";
    $("gstAmt").textContent = fmt(c.gstAmt);
    $("total").textContent = fmt(c.total);
    syncTipChips(s.tip_pct);

    if (valid && c.total > 0) {
      $("uriPreview").textContent = buildUri(s, c.total);
      return true;
    }
    return false;
  }

  function onChange() {
    var valid = updatePreview();
    clearTimeout(debounceTimer);
    if (!valid) {
      setOutputEnabled(false);
      return;
    }
    saveDetails();
    debounceTimer = setTimeout(fetchQR, DEBOUNCE_MS);
  }

  function fetchQR() {
    var s = readState();
    fetch("/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(s)
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) {
          $("apiErr").textContent = data.error;
          setOutputEnabled(false);
          return;
        }
        $("apiErr").textContent = "";
        var img = $("qrImg");
        img.src = data.qr;
        img.classList.add("show");
        $("qrPlaceholder").style.display = "none";
        $("uriPreview").textContent = data.uri;
        $("downloadBtn").disabled = false;
        $("shareBtn").disabled = false;
        syncSaveBtn();
      })
      .catch(function () {
        $("apiErr").textContent = "Could not reach server.";
        setOutputEnabled(false);
      });
  }

  $("downloadBtn").addEventListener("click", function () {
    var img = $("qrImg");
    if (!img.src || this.disabled) return;
    var a = document.createElement("a");
    a.href = img.src;
    a.download = "upi-qr.png";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  });

  // Web Share API: share the QR image where supported, else the URI text.
  if (!navigator.share) {
    $("shareBtn").style.display = "none";
  }
  $("shareBtn").addEventListener("click", function () {
    var img = $("qrImg");
    if (!img.src || this.disabled) return;
    var uri = $("uriPreview").textContent;
    fetch(img.src)
      .then(function (r) { return r.blob(); })
      .then(function (blob) {
        var file = new File([blob], "upi-qr.png", { type: "image/png" });
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
          return navigator.share({ files: [file], title: "UPI payment QR", text: uri });
        }
        return navigator.share({ title: "UPI payment QR", text: uri });
      })
      .catch(function () { /* user cancelled or share unsupported */ });
  });

  // Remember VPA and payee name for returning users.
  function saveDetails() {
    try {
      localStorage.setItem("upisave_vpa", $("vpa").value.trim());
      localStorage.setItem("upisave_name", $("name").value.trim());
    } catch (e) { /* storage unavailable */ }
  }
  function restoreDetails() {
    try {
      var vpa = localStorage.getItem("upisave_vpa");
      var name = localStorage.getItem("upisave_name");
      if (vpa) $("vpa").value = vpa;
      if (name) $("name").value = name;
    } catch (e) { /* storage unavailable */ }
  }

  // ---------- Google sign-in ----------
  var GOOGLE_CLIENT_ID = "1060359730160-umr1mvsjoccn3sijmd76jfj47lgobaab.apps.googleusercontent.com";
  var user = null;
  try { user = JSON.parse(localStorage.getItem("upisave_user") || "null"); } catch (e) {}

  window.gisLoaded = function () {
    if (!window.google || !google.accounts) return;
    google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: onCredential
    });
    renderSignInButtons();
  };

  function renderSignInButtons() {
    if (user || !window.google || !google.accounts) return;
    google.accounts.id.renderButton($("gsiBtn"), { theme: "filled_black", size: "medium", shape: "pill" });
    var libBtn = $("libSignIn");
    if (libBtn) google.accounts.id.renderButton(libBtn, { theme: "filled_black", size: "large", shape: "pill" });
    // If Google refuses this origin, the button iframe collapses to 0x0 —
    // surface that instead of showing nothing.
    setTimeout(function () {
      if (user) return;
      var iframe = $("gsiBtn").querySelector("iframe");
      if (iframe && iframe.getBoundingClientRect().width === 0) {
        $("gsiBtn").textContent = "Sign-in unavailable: this site's address is not an authorized origin for the Google client ID.";
        $("gsiBtn").style.cssText = "font-size:11px;color:var(--error);max-width:260px;";
      }
    }, 2500);
  }

  function onCredential(resp) {
    try {
      var payload = JSON.parse(atob(resp.credential.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
      user = { sub: payload.sub, name: payload.name || payload.email || "User", picture: payload.picture || "" };
      localStorage.setItem("upisave_user", JSON.stringify(user));
    } catch (e) { return; }
    updateAuthUI();
  }

  $("signOutBtn").addEventListener("click", function () {
    user = null;
    localStorage.removeItem("upisave_user");
    if (window.google && google.accounts) google.accounts.id.disableAutoSelect();
    if (location.hash === "#library") location.hash = "";
    updateAuthUI();
    renderSignInButtons();
  });

  function updateAuthUI() {
    var signedIn = !!user;
    $("gsiBtn").style.display = signedIn ? "none" : "block";
    $("userChip").style.display = signedIn ? "flex" : "none";
    if (signedIn) {
      $("userName").textContent = user.name;
      $("userPic").style.display = user.picture ? "block" : "none";
      if (user.picture) $("userPic").src = user.picture;
    }
    $("tabLib").style.display = signedIn ? "inline-block" : "none";
    $("saveHint").style.display = signedIn ? "none" : "block";
    syncSaveBtn();
    route();
  }

  function syncSaveBtn() {
    $("saveBtn").disabled = !(user && $("qrImg").classList.contains("show"));
  }

  // ---------- QR library (stored per Google account in this browser) ----------
  function libKey() { return "upisave_library_" + user.sub; }
  function getLib() {
    try { return JSON.parse(localStorage.getItem(libKey()) || "[]"); } catch (e) { return []; }
  }

  $("saveBtn").addEventListener("click", function () {
    if (!user || this.disabled) return;
    var s = readState();
    var items = getLib();
    items.unshift({
      id: String(Date.now()),
      qr: $("qrImg").src,
      uri: $("uriPreview").textContent,
      payee: s.name,
      amount: $("total").textContent,
      note: s.note,
      savedAt: new Date().toISOString()
    });
    try {
      localStorage.setItem(libKey(), JSON.stringify(items));
    } catch (e) {
      $("apiErr").textContent = "Could not save — browser storage is full.";
      return;
    }
    var btn = this;
    btn.textContent = "Saved ✓";
    setTimeout(function () { btn.textContent = "Save"; }, 1200);
  });

  function renderLibrary() {
    var grid = $("libGrid"), empty = $("libEmpty");
    grid.innerHTML = "";
    if (!user) {
      empty.style.display = "block";
      empty.innerHTML = "";
      var msg = document.createElement("div");
      msg.textContent = "Sign in with Google to save and view your QR library.";
      msg.style.marginBottom = "16px";
      var btnHost = document.createElement("div");
      btnHost.id = "libSignIn";
      btnHost.style.display = "inline-block";
      empty.appendChild(msg);
      empty.appendChild(btnHost);
      renderSignInButtons();
      return;
    }
    var items = getLib();
    if (!items.length) {
      empty.style.display = "block";
      empty.textContent = "No saved QRs yet — generate one and press Save.";
      return;
    }
    empty.style.display = "none";
    items.forEach(function (item) {
      var card = document.createElement("div");
      card.className = "lib-card";
      var img = document.createElement("img");
      img.src = item.qr;
      img.alt = "Saved UPI QR";
      var nm = document.createElement("div");
      nm.className = "lib-name";
      nm.textContent = item.payee || "(no payee name)";
      var amt = document.createElement("div");
      amt.className = "lib-amount";
      amt.textContent = item.amount;
      var meta = document.createElement("div");
      meta.className = "lib-meta";
      meta.textContent = (item.note ? item.note + " · " : "") +
        new Date(item.savedAt).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
      var actions = document.createElement("div");
      actions.className = "lib-actions";
      var dl = document.createElement("button");
      dl.className = "btn small";
      dl.textContent = "Download";
      dl.addEventListener("click", function () {
        var a = document.createElement("a");
        a.href = item.qr;
        a.download = "upi-qr-" + item.id + ".png";
        document.body.appendChild(a);
        a.click();
        a.remove();
      });
      var del = document.createElement("button");
      del.className = "btn small danger";
      del.textContent = "Delete";
      del.addEventListener("click", function () {
        var next = getLib().filter(function (x) { return x.id !== item.id; });
        localStorage.setItem(libKey(), JSON.stringify(next));
        renderLibrary();
      });
      actions.appendChild(dl);
      actions.appendChild(del);
      card.appendChild(img);
      card.appendChild(nm);
      card.appendChild(amt);
      card.appendChild(meta);
      card.appendChild(actions);
      grid.appendChild(card);
    });
  }

  function route() {
    var onLib = location.hash === "#library";
    document.querySelector(".layout").style.display = onLib ? "none" : "grid";
    $("libraryView").style.display = onLib ? "block" : "none";
    $("tabGen").classList.toggle("active", !onLib);
    $("tabLib").classList.toggle("active", onLib);
    if (onLib) renderLibrary();
  }
  window.addEventListener("hashchange", route);

  restoreDetails();
  syncAmountChips();
  updateAuthUI();
  onChange();
})();
</script>
<script src="https://accounts.google.com/gsi/client" onload="gisLoaded()" async defer></script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}

    vpa = str(data.get("vpa", "")).strip()
    name = str(data.get("name", "")).strip()
    note = str(data.get("note", "")).strip()

    if not VPA_RE.match(vpa):
        return jsonify(error="Invalid UPI ID. Expected format: name@bank"), 400

    try:
        rupees = float(data.get("rupees", 0))
        paise = float(data.get("paise", 0))
        tip_pct = float(data.get("tip_pct", 0))
        gst_pct = float(data.get("gst_pct", 0))
    except (TypeError, ValueError):
        return jsonify(error="All numeric fields must be numbers."), 400

    if not (1 <= rupees <= MAX_RUPEES):
        return jsonify(error="Amount must be between ₹1 and ₹1,00,000."), 400
    if not (0 <= paise <= 99):
        return jsonify(error="Paise must be between 0 and 99."), 400
    if not (0 <= tip_pct <= 25):
        return jsonify(error="Tip must be between 0% and 25%."), 400
    if int(gst_pct) != gst_pct or int(gst_pct) not in GST_SLABS:
        return jsonify(error="GST must be one of 0, 5, 12, 18, 28."), 400

    # GST applies to the subtotal only; tips are not taxed.
    subtotal = rupees + paise / 100
    tip_amt = subtotal * tip_pct / 100
    gst_amt = subtotal * gst_pct / 100
    total = round(subtotal + tip_amt + gst_amt, 2)

    if total <= 0:
        return jsonify(error="Amount must be greater than zero."), 400

    amount = f"{total:.2f}"
    uri = f"upi://pay?pa={vpa}"
    if name:
        uri += f"&pn={quote(name)}"
    uri += f"&am={amount}&cu=INR"
    if note:
        uri += f"&tn={quote(note)}"

    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return jsonify(
        qr=f"data:image/png;base64,{b64}",
        uri=uri,
        amount=amount,
        breakdown={
            "subtotal": round(subtotal, 2),
            "tip": round(tip_amt, 2),
            "gst": round(gst_amt, 2),
            "total": total,
        },
    )


if __name__ == "__main__":
    import os
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=True)
