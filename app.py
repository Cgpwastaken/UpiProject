import base64
import io
import re
from urllib.parse import quote

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

VPA_RE = re.compile(r"^[\w.\-]+@[\w]+$")
GST_SLABS = {0, 5, 12, 18, 28}

PAGE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>UPI QR Generator</title>
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
  input[type="text"] {
    width: 100%;
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    padding: 10px 12px;
    font-size: 14px;
    outline: none;
  }
  input[type="text"]:focus { border-color: var(--accent2); }
  input[type="text"].bad { border-color: var(--error); }
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
  input[type="number"] {
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
  input[type="number"]:focus { border-color: var(--accent2); }
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
    align-items: center; justify-content: center;
    color: var(--muted);
    font-size: 13px;
  }
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
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .section-title { font-size: 13px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }
  .right-col > .card + .card { margin-top: 24px; }
  @media (max-width: 760px) { .layout { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="header">
  <h1>UPI QR Generator</h1>
  <div class="sub">Generate a scannable UPI payment QR with live amount calculation</div>
</div>
<div class="layout">
  <div class="card">
    <div class="field">
      <label for="vpa">UPI ID (VPA)</label>
      <input type="text" id="vpa" value="9884511462-6@okaxis" spellcheck="false">
      <div class="err" id="vpaErr"></div>
    </div>
    <div class="field">
      <label for="name">Payee Name</label>
      <input type="text" id="name" value="Veer Aditya Mirza">
    </div>
    <div class="field">
      <label for="note">Transaction Note</label>
      <input type="text" id="note" value="test">
    </div>
    <div class="field">
      <label>Rupees</label>
      <div class="slider-row">
        <input type="range" id="rupees" min="1" max="10000" value="500">
        <input type="number" id="rupeesNum" min="1" max="10000" value="500">
      </div>
    </div>
    <div class="field">
      <label>Paise</label>
      <div class="slider-row">
        <input type="range" id="paise" min="0" max="99" value="0">
        <input type="number" id="paiseNum" min="0" max="99" value="0">
      </div>
    </div>
    <div class="field">
      <label>Quantity</label>
      <div class="slider-row">
        <input type="range" id="quantity" min="1" max="50" value="1">
        <input type="number" id="quantityNum" min="1" max="50" value="1">
      </div>
    </div>
    <div class="field">
      <label>Tip %</label>
      <div class="slider-row">
        <input type="range" id="tip_pct" min="0" max="25" value="0">
        <input type="number" id="tip_pctNum" min="0" max="25" value="0">
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
    <div class="card">
      <div class="section-title">Calculation</div>
      <div class="breakdown">
        <div class="row"><span id="subLabel">Subtotal</span><span id="subtotal">₹0.00</span></div>
        <div class="row"><span id="tipLabel">Tip (0%)</span><span id="tipAmt">₹0.00</span></div>
        <div class="row"><span id="gstLabel">GST (0%)</span><span id="gstAmt">₹0.00</span></div>
        <div class="row total"><span>Total</span><span id="total">₹0.00</span></div>
      </div>
      <div class="section-title" style="margin-top:18px;">UPI URI</div>
      <div class="uri-box" id="uriPreview">—</div>
    </div>
    <div class="card">
      <div class="section-title">QR Code</div>
      <div class="qr-wrap">
        <div class="qr-placeholder" id="qrPlaceholder">QR appears here</div>
        <img id="qrImg" alt="UPI QR code">
        <br>
        <button class="btn" id="downloadBtn" disabled>Download QR</button>
      </div>
    </div>
  </div>
</div>

<script>
(function () {
  var DEBOUNCE_MS = 400;
  var debounceTimer = null;
  var gst = 0;

  var sliders = ["rupees", "paise", "quantity", "tip_pct"];
  var $ = function (id) { return document.getElementById(id); };

  function paintSlider(el) {
    var min = +el.min, max = +el.max, val = +el.value;
    var pct = ((val - min) / (max - min)) * 100;
    el.style.background =
      "linear-gradient(to right, var(--accent2) " + pct + "%, var(--track) " + pct + "%)";
  }

  function clamp(v, min, max) {
    v = parseInt(v, 10);
    if (isNaN(v)) v = min;
    return Math.min(max, Math.max(min, v));
  }

  sliders.forEach(function (id) {
    var range = $(id), num = $(id + "Num");
    range.addEventListener("input", function () {
      num.value = range.value;
      paintSlider(range);
      onChange();
    });
    num.addEventListener("input", function () {
      var v = clamp(num.value, +range.min, +range.max);
      range.value = v;
      paintSlider(range);
      onChange();
    });
    num.addEventListener("blur", function () {
      num.value = clamp(num.value, +range.min, +range.max);
    });
    paintSlider(range);
  });

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

  var VPA_RE = /^[\w.\-]+@[\w]+$/;

  function readState() {
    return {
      vpa: $("vpa").value.trim(),
      name: $("name").value.trim(),
      note: $("note").value.trim(),
      rupees: clamp($("rupeesNum").value, 1, 10000),
      paise: clamp($("paiseNum").value, 0, 99),
      quantity: clamp($("quantityNum").value, 1, 50),
      tip_pct: clamp($("tip_pctNum").value, 0, 25),
      gst_pct: gst
    };
  }

  function fmt(n) {
    return "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function computeLocal(s) {
    var subtotal = (s.rupees + s.paise / 100) * s.quantity;
    var tipAmt = subtotal * s.tip_pct / 100;
    var gstAmt = (subtotal + tipAmt) * s.gst_pct / 100;
    var total = Math.round((subtotal + tipAmt + gstAmt) * 100) / 100;
    return { subtotal: subtotal, tipAmt: tipAmt, gstAmt: gstAmt, total: total };
  }

  function updatePreview() {
    var s = readState();
    var c = computeLocal(s);
    $("subLabel").textContent = "Subtotal (" + fmt(s.rupees + s.paise / 100).slice(1) + " × " + s.quantity + ")";
    $("subtotal").textContent = fmt(c.subtotal);
    $("tipLabel").textContent = "Tip (" + s.tip_pct + "%)";
    $("tipAmt").textContent = fmt(c.tipAmt);
    $("gstLabel").textContent = "GST (" + s.gst_pct + "%)";
    $("gstAmt").textContent = fmt(c.gstAmt);
    $("total").textContent = fmt(c.total);

    var uri = "upi://pay?pa=" + s.vpa +
      "&pn=" + encodeURIComponent(s.name) +
      "&am=" + c.total.toFixed(2) +
      "&cu=INR" +
      "&tn=" + encodeURIComponent(s.note);
    $("uriPreview").textContent = uri;

    var vpaOk = VPA_RE.test(s.vpa);
    $("vpa").classList.toggle("bad", !vpaOk);
    $("vpaErr").textContent = vpaOk ? "" : "Invalid VPA — expected format: name@bank";
    return vpaOk && c.total > 0;
  }

  function onChange() {
    var valid = updatePreview();
    clearTimeout(debounceTimer);
    if (!valid) return;
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
          return;
        }
        $("apiErr").textContent = "";
        var img = $("qrImg");
        img.src = data.qr;
        img.classList.add("show");
        $("qrPlaceholder").style.display = "none";
        $("uriPreview").textContent = data.uri;
        $("downloadBtn").disabled = false;
      })
      .catch(function () {
        $("apiErr").textContent = "Could not reach server.";
      });
  }

  $("downloadBtn").addEventListener("click", function () {
    var img = $("qrImg");
    if (!img.src) return;
    var a = document.createElement("a");
    a.href = img.src;
    a.download = "upi-qr.png";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  });

  // Initial render + first QR
  updatePreview();
  fetchQR();
})();
</script>
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
        return jsonify(error="Invalid VPA. Expected format: name@bank"), 400

    try:
        rupees = float(data.get("rupees", 0))
        paise = float(data.get("paise", 0))
        quantity = float(data.get("quantity", 1))
        tip_pct = float(data.get("tip_pct", 0))
        gst_pct = float(data.get("gst_pct", 0))
    except (TypeError, ValueError):
        return jsonify(error="All numeric fields must be numbers."), 400

    if int(gst_pct) != gst_pct or int(gst_pct) not in GST_SLABS:
        return jsonify(error="GST must be one of 0, 5, 12, 18, 28."), 400

    subtotal = (rupees + paise / 100) * quantity
    tip_amt = subtotal * tip_pct / 100
    gst_amt = (subtotal + tip_amt) * gst_pct / 100
    total = round(subtotal + tip_amt + gst_amt, 2)

    if total <= 0:
        return jsonify(error="Amount must be greater than zero."), 400

    amount = f"{total:.2f}"
    uri = (
        f"upi://pay?pa={vpa}"
        f"&pn={quote(name)}"
        f"&am={amount}"
        f"&cu=INR"
        f"&tn={quote(note)}"
    )

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
