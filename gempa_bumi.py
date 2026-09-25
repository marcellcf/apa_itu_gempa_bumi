"""
Gempa Bumi Itu Apa Sih? - video penjelasan animasi (Streamlit)

Jalankan di laptop:
  pip install -r requirements.txt
  streamlit run app.py

SUARA NARATOR
  - Kalau ada ElevenLabs API key  -> suara ElevenLabs (paling natural).
  - Kalau tidak ada                -> suara Microsoft "Ardi" (gratis, cadangan).
  API key ditaruh di file .streamlit/secrets.toml (lihat README.md),
  atau di menu Secrets saat deploy ke Streamlit Community Cloud.

  Suara dibuat otomatis saat pertama kali dibuka lalu disimpan di folder
  "suara_narator". Upload folder itu ke GitHub juga supaya versi online
  tidak perlu membuat ulang (hemat kuota ElevenLabs).

Ukuran: YouTube 16:9 atau TikTok 9:16 (pilih di atas video).
"""

import asyncio
import base64
import hashlib
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Gempa Bumi Itu Apa Sih?", page_icon="🌏", layout="wide")

st.markdown(
    """
    <style>
      .stApp { background: #0b1426; color: #eef3ff; }
      .block-container { padding-top: 1.2rem; padding-bottom: 0; }
      header[data-testid="stHeader"] { background: transparent; }
      /* tulisan Streamlit dibuat terang supaya kelihatan di latar gelap (tema apa pun) */
      .stApp label, .stApp p, .stApp span,
      [data-testid="stWidgetLabel"] *, [data-testid="stMarkdownContainer"] *,
      header[data-testid="stHeader"] *, [data-testid="stStatusWidget"] * { color: #eef0ff !important; }
      [data-testid="stTooltipIcon"] svg, header[data-testid="stHeader"] svg { fill: #c9cdf0 !important; color: #c9cdf0 !important; }
      .stSpinner * { color: #ffc95a !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
#  SUARA NARATOR
# ---------------------------------------------------------------------------
FOLDER_SUARA = Path(__file__).parent / "suara_narator"

# ElevenLabs — voice_id bisa diganti dengan suara lain dari Voice Library ElevenLabs
# (cari suara berbahasa Indonesia, lalu salin ID-nya ke secrets: ELEVENLABS_VOICE_ID).
ELEVENLABS_VOICE_DEFAULT = "JBFqnCBsd6RMkjVDRZzb"   # "George": hangat, cocok untuk narator
ELEVENLABS_MODEL = "eleven_multilingual_v2"         # model yang fasih Bahasa Indonesia
ELEVENLABS_PENGATURAN = {"stability": 0.5, "similarity_boost": 0.8, "style": 0.3, "use_speaker_boost": True}

# Cadangan gratis tanpa API key: suara Microsoft. Nada & kecepatan dibiarkan asli supaya tidak robotik.
EDGE_SUARA = {"voice": "id-ID-ArdiNeural", "rate": "+0%", "pitch": "+0Hz"}

# Semua kalimat narasi di video. Teksnya harus sama persis dengan di animasi.
NARASI = [
    "Pernah nggak, lagi santai tiba-tiba lantai bergoyang?",
    "Itu namanya gempa bumi. Tapi… sebenarnya kenapa bisa terjadi?",
    "Untuk tahu jawabannya, kita intip dulu isi Bumi.",
    "Paling luar ada kerak, lapisan tipis tempat kita berpijak.",
    "Di bawahnya ada mantel yang panas, lalu inti Bumi yang super panas.",
    "Nah, yang penting buat gempa adalah kerak ini.",
    "Kerak Bumi ternyata tidak utuh. Ia terpecah jadi potongan raksasa bernama lempeng tektonik.",
    "Lempeng-lempeng ini terus bergerak, beberapa sentimeter setiap tahun.",
    "Kurang lebih secepat kuku kita tumbuh!",
    "Indonesia letaknya istimewa: di pertemuan tiga lempeng besar.",
    "Lempeng Eurasia, Indo-Australia, dan Pasifik saling dorong di bawah negeri kita.",
    "Makanya Indonesia termasuk negara yang paling sering gempa.",
    "Di batas lempeng, dua lempeng bisa saling mengunci.",
    "Tekanannya terus menumpuk, seperti penggaris yang kita bengkokkan pelan-pelan…",
    "…sampai akhirnya tidak kuat dan lepas tiba-tiba!",
    "Energi yang lepas itu menyebar sebagai getaran. Itulah gempa bumi.",
    "Titik asal gempa di dalam Bumi disebut hiposentrum.",
    "Sedangkan titik di permukaan tepat di atasnya disebut episentrum.",
    "Getaran gempa merambat sebagai gelombang seismik.",
    "Gelombang P datang duluan: lebih cepat, tapi lebih lemah.",
    "Lalu gelombang S menyusul: lebih lambat, tapi guncangannya lebih kuat.",
    "Kekuatan gempa diukur dengan magnitudo.",
    "Naik satu angka saja, energinya kira-kira tiga puluh dua kali lipat!",
    "Kalau gempanya kuat dan terjadi di bawah laut, dasar laut bisa terangkat…",
    "…dan mendorong air laut menjadi gelombang tsunami.",
    "Terus, kalau gempa datang, kita harus apa?",
    "Merunduk, berlindung di bawah meja yang kuat, dan berpegangan.",
    "Jauhi kaca dan lemari yang bisa roboh.",
    "Kalau kamu di pantai dan gempanya kuat, segera lari ke tempat tinggi!",
    "Jadi, gempa bumi terjadi karena lempeng Bumi bergerak dan melepas energi secara tiba-tiba.",
    "Tetap tenang, dan selalu siaga ya!",
]


def ambil_rahasia(nama):
    """Baca dari .streamlit/secrets.toml / Secrets Streamlit Cloud, atau dari environment variable."""
    try:
        if nama in st.secrets:
            return str(st.secrets[nama]).strip()
    except Exception:
        pass
    return os.environ.get(nama, "").strip()


ELEVENLABS_KEY = ambil_rahasia("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE = ambil_rahasia("ELEVENLABS_VOICE_ID") or ELEVENLABS_VOICE_DEFAULT
PENYEDIA = "elevenlabs" if ELEVENLABS_KEY else "microsoft"


def identitas(teks):
    """Sidik suara: berubah kalau penyedia, suara, atau teksnya berubah."""
    if PENYEDIA == "elevenlabs":
        data = ["elevenlabs", ELEVENLABS_VOICE, ELEVENLABS_MODEL, ELEVENLABS_PENGATURAN, teks]
    else:
        data = ["microsoft", EDGE_SUARA, teks]
    return hashlib.md5(json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def file_suara(teks):
    return FOLDER_SUARA / f"{PENYEDIA}_{identitas(teks)}.mp3"


# daftar.json mencatat file mana untuk kalimat mana, supaya rekaman ElevenLabs yang sudah
# di-upload ke GitHub tetap dipakai walaupun server tidak punya API key.
DAFTAR = FOLDER_SUARA / "daftar.json"


def baca_daftar():
    try:
        return json.loads(DAFTAR.read_text(encoding="utf-8"))
    except Exception:
        return {}


def catat(teks):
    daftar = baca_daftar()
    lama = daftar.get(teks, {}).get("file")
    if lama and lama != file_suara(teks).name:
        (FOLDER_SUARA / lama).unlink(missing_ok=True)  # buang rekaman lama yang sudah diganti
    daftar[teks] = {"file": file_suara(teks).name, "penyedia": PENYEDIA, "id": identitas(teks)}
    DAFTAR.write_text(json.dumps(daftar, ensure_ascii=False, indent=1), encoding="utf-8")


def perlu_dibuat(teks, daftar):
    isi = daftar.get(teks)
    if not isi or not (FOLDER_SUARA / isi["file"]).exists():
        return True
    # ada API key tapi rekamannya beda suara / masih suara Microsoft -> buat ulang pakai ElevenLabs
    return PENYEDIA == "elevenlabs" and isi["id"] != identitas(teks)


def simpan_utuh(tujuan, data):
    sementara = tujuan.with_suffix(".tmp")
    sementara.write_bytes(data)
    sementara.replace(tujuan)  # baru dianggap jadi kalau file tersimpan utuh


def rekam_elevenlabs(yang_kurang):
    import requests

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}?output_format=mp3_44100_128"
    kepala = {"xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    progres = st.progress(0.0, text="Membuat suara narator (ElevenLabs)…")
    for i, teks in enumerate(yang_kurang, start=1):
        badan = {"text": teks, "model_id": ELEVENLABS_MODEL, "language_code": "id", "voice_settings": ELEVENLABS_PENGATURAN}
        r = requests.post(url, headers=kepala, json=badan, timeout=60)
        if r.status_code == 400 and "language_code" in r.text:
            badan.pop("language_code")  # model lama tidak menerima language_code
            r = requests.post(url, headers=kepala, json=badan, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"ElevenLabs menolak ({r.status_code}): {r.text[:200]}")
        simpan_utuh(file_suara(teks), r.content)
        catat(teks)
        progres.progress(i / len(yang_kurang), text=f"Membuat suara narator (ElevenLabs) {i}/{len(yang_kurang)}")
    progres.empty()


def rekam_microsoft(yang_kurang):
    try:
        import edge_tts
    except ModuleNotFoundError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "edge-tts"])
        importlib.invalidate_caches()
        import edge_tts

    async def satu(teks):
        rekaman = edge_tts.Communicate(teks, EDGE_SUARA["voice"], rate=EDGE_SUARA["rate"], pitch=EDGE_SUARA["pitch"])
        tujuan = file_suara(teks)
        sementara = tujuan.with_suffix(".tmp")
        await rekaman.save(str(sementara))
        sementara.replace(tujuan)

    async def semua():
        await asyncio.gather(*(satu(t) for t in yang_kurang))

    with st.spinner("Menyiapkan suara narator… (cuma pertama kali, beberapa detik)"):
        asyncio.run(semua())
    for teks in yang_kurang:
        catat(teks)


def rekam_narasi(yang_kurang):
    FOLDER_SUARA.mkdir(exist_ok=True)
    if PENYEDIA == "elevenlabs":
        rekam_elevenlabs(yang_kurang)
    else:
        rekam_microsoft(yang_kurang)


@st.cache_data(show_spinner=False)
def baca_narasi(daftar_file):
    hasil = {}
    for teks, path, _waktu_ubah in daftar_file:
        data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
        hasil[f"narator|{teks}"] = "data:audio/mpeg;base64," + data
    return hasil


def file_tersedia():
    daftar = baca_daftar()
    ada = []
    for teks in NARASI:
        isi = daftar.get(teks)
        if isi and (FOLDER_SUARA / isi["file"]).exists():
            p = FOLDER_SUARA / isi["file"]
            ada.append((teks, str(p), p.stat().st_mtime))
    return ada


yang_kurang = [t for t in NARASI if perlu_dibuat(t, baca_daftar())]

# ---------------------------------------------------------------------------
#  PILIHAN UKURAN
# ---------------------------------------------------------------------------
kiri, kanan = st.columns([2, 1])
with kiri:
    ukuran = st.radio("Ukuran video", ["YouTube (16:9)", "TikTok (9:16)"], horizontal=True)
with kanan:
    pakai_narator = st.toggle("Suara narator", value=True,
                              help="ElevenLabs" if PENYEDIA == "elevenlabs" else "Suara Microsoft (isi ELEVENLABS_API_KEY untuk suara yang lebih natural)")

if pakai_narator and yang_kurang and not st.session_state.get("narator_gagal"):
    # Otomatis, tanpa tombol. Hanya terjadi saat pertama kali dibuka (butuh internet, beberapa detik).
    try:
        rekam_narasi(yang_kurang)
    except Exception as e:
        st.session_state["narator_gagal"] = str(e)
    yang_kurang = [t for t in NARASI if perlu_dibuat(t, baca_daftar())]
if pakai_narator and st.session_state.get("narator_gagal"):
    st.warning("Suara narator belum bisa disiapkan. Video tetap bisa diputar dengan subtitle.\n\n"
               f"Penyebab: {st.session_state['narator_gagal']}")
    if st.button("Coba lagi"):
        st.session_state.pop("narator_gagal", None)
        st.rerun()

format_video = "916" if ukuran.startswith("TikTok") else "169"

HTML_ANIMASI = r'''<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gempa Bumi Itu Apa Sih?</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;700;800&family=Nunito:wght@700;800&display=swap">
<style>
  [hidden] { display: none !important; }
  :root {
    color-scheme: dark;
    --malam: #0b1426;
    --teks: #eef3ff;
    --redup: #93a3c7;
    --oranye: #ff7f3f;
    --garis: #22345a;
    --panel: #111d36;
  }
  html, body { height: 100%; }
  body {
    margin: 0; background: var(--malam); color: var(--teks);
    font-family: "Baloo 2", "Trebuchet MS", system-ui, sans-serif;
    display: flex; flex-direction: column; align-items: center;
    padding: 12px 16px; box-sizing: border-box;
  }
  .wadah { width: min(100%, 1200px, calc((100vh - 190px) * 16 / 9)); min-width: 280px; display: flex; flex-direction: column; gap: 10px; }
  .v916 .wadah { width: min(100%, 540px, calc((100vh - 230px) * 9 / 16)); min-width: 300px; }
  header { display: flex; justify-content: space-between; align-items: baseline; gap: 4px 12px; flex-wrap: wrap; }
  h1 { margin: 0; font-size: clamp(18px, 2.4vw, 24px); font-weight: 800; }
  h1 span { color: var(--oranye); }
  .sub { color: var(--redup); font-size: 13px; }
  .alat { display: flex; gap: 8px; flex-wrap: wrap; }
  .pilih { display: flex; background: var(--panel); border-radius: 999px; padding: 3px; box-shadow: inset 0 0 0 1px var(--garis); }
  .pilih button { background: transparent; color: var(--redup); box-shadow: none; padding: 7px 12px 5px; font-size: 13px; }
  .pilih button.on { background: var(--oranye); color: #1b0f08; }
  .panggung { position: relative; width: 100%; aspect-ratio: 16 / 9; border-radius: 12px; overflow: hidden; background: #000; box-shadow: 0 0 0 1px var(--garis), 0 30px 80px -30px #000; }
  .v916 .panggung { aspect-ratio: 9 / 16; border-radius: 16px; }
  canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
  .mulai { position: absolute; inset: 0; display: grid; place-content: end center; justify-items: center; gap: 10px; text-align: center; padding: 0 16px 8%;
    background: linear-gradient(180deg, rgba(11,20,38,0) 45%, rgba(11,20,38,.85)); }
  .mulai button { font-size: clamp(16px, 2.2vw, 20px); padding: 14px 28px 11px; }
  .mulai p { margin: 0; color: #cfd8f0; font-size: 14px; }
  button {
    font: 700 15px/1 "Baloo 2", sans-serif; color: #1b0f08; background: var(--oranye);
    border: 0; border-radius: 999px; padding: 10px 18px 8px; cursor: pointer;
    box-shadow: 0 6px 20px -6px rgba(255,127,63,.7);
  }
  button:hover { filter: brightness(1.08); }
  button:focus-visible { outline: 2px solid var(--teks); outline-offset: 3px; }
  button:disabled { opacity: .7; cursor: progress; }
  .kontrol { display: flex; gap: 8px; align-items: center; }
  .ikon { width: 40px; height: 40px; padding: 0; display: grid; place-items: center; font-size: 16px; flex: none;
    background: #15223f; color: var(--teks); box-shadow: 0 0 0 1px var(--garis); }
  .ikon.mati { opacity: .5; }
  .linimasa { flex: 1; display: flex; gap: 3px; min-width: 0; }
  .seg { flex-basis: 0; position: relative; height: 40px; border-radius: 6px; background: var(--panel); cursor: pointer; overflow: hidden;
    box-shadow: inset 0 0 0 1px var(--garis); border: 0; padding: 0; color: var(--redup); }
  .seg .isi { position: absolute; inset: 0 auto 0 0; width: 0; background: linear-gradient(90deg, rgba(255,127,63,.35), rgba(255,210,63,.45)); }
  .seg span { position: relative; font: 700 11px/40px "Baloo 2", sans-serif; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; padding: 0 4px; text-align: center; }
  .seg.aktif { box-shadow: inset 0 0 0 1px var(--oranye); color: var(--teks); }
  .v916 .seg span { font-size: 0; }
  footer { color: var(--redup); font-size: 12px; text-align: center; }
  kbd { font: 600 11px/1 ui-monospace, monospace; border: 1px solid #36507e; border-bottom-width: 2px; border-radius: 4px; padding: 2px 5px; color: var(--teks); }
  @media (max-width: 760px) { .seg span { font-size: 0; } .sub { display: none; } }
</style>
</head>
<body>

<div class="wadah">
  <header>
    <h1>Gempa Bumi Itu <span>Apa Sih?</span></h1>
    <div class="sub">video penjelasan · ± 2,5 menit · nyalakan suara</div>
  </header>
  <div class="alat" id="alat">
    <div class="pilih" role="group" aria-label="Ukuran video">
      <button data-format="169">YouTube 16:9</button>
      <button data-format="916">TikTok 9:16</button>
    </div>
  </div>
  <div class="panggung" id="panggung">
    <canvas id="kanvas"></canvas>
    <div class="mulai" id="layarMulai">
      <button id="tombolMulai">▶ Tonton</button>
      <p>Kenapa lantai bisa bergoyang? Yuk intip isi Bumi.</p>
    </div>
  </div>
  <div class="kontrol">
    <button class="ikon" id="bMain" aria-label="Putar">▶</button>
    <div class="linimasa" id="linimasa"></div>
    <button class="ikon" id="bDub" aria-label="Matikan suara narator" title="Suara narator">🗣️</button>
    <button class="ikon" id="bSuara" aria-label="Matikan suara" title="Suara">🔊</button>
  </div>
  <footer><kbd>Spasi</kbd> jeda/lanjut · <kbd>←</kbd> <kbd>→</kbd> pindah bagian · klik linimasa untuk lompat</footer>
</div>

<script>
(() => {
'use strict';
// =====================================================================
//  DASAR
// =====================================================================
const SW = 1280, SH = 720;          // ukuran "panggung" adegan
let VW = 1280, VH = 720, FORMAT = '169';
const kanvas = document.getElementById('kanvas');
const ctx = kanvas.getContext('2d');
let skala = 1, DPR = 1, waktu = 0;
const kurangGerak = matchMedia('(prefers-reduced-motion: reduce)').matches;
function ukur() {
  const r = kanvas.getBoundingClientRect();
  DPR = Math.min(window.devicePixelRatio || 1, 2);
  kanvas.width = Math.max(1, Math.round(r.width * DPR));
  kanvas.height = Math.max(1, Math.round(r.height * DPR));
  skala = r.width / VW;
}
const dasar = () => ctx.setTransform(skala * DPR, 0, 0, skala * DPR, 0, 0);
const lerp = (a, b, t) => a + (b - a) * t;
const klem = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const halus = t => t * t * (3 - 2 * t);
const acak = (a, b) => a + Math.random() * (b - a);
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function kf(t, keys, ease = x => x) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) if (t <= keys[i][0]) { const [t0, v0] = keys[i - 1], [t1, v1] = keys[i]; return lerp(v0, v1, ease((t - t0) / (t1 - t0))); }
  return keys[keys.length - 1][1];
}
const kfh = (t, keys) => kf(t, keys, halus);
function muncul(lt, t0, t1, masuk = 0.3, keluar = 0.3) { if (lt < t0 || lt > t1) return 0; return Math.min(1, (lt - t0) / masuk, (t1 - lt) / keluar); }
// skala "pop" dengan sedikit memantul
function pop(lt, t0, d = 0.45) { if (lt < t0) return 0; const u = klem((lt - t0) / d) - 1, c = 1.70158; return 1 + (c + 1) * u * u * u + c * u * u; }
function rrect(x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
function elips(x, y, rx, ry) { ctx.beginPath(); ctx.ellipse(x, y, Math.max(0.1, rx), Math.max(0.1, ry), 0, 0, 6.2832); }
function bulat(x, y, r) { ctx.beginPath(); ctx.arc(x, y, Math.max(0.1, r), 0, 6.2832); }
function poligon(p) { ctx.beginPath(); p.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.closePath(); }
function diSkala(x, y, s, fn) { if (s <= 0.001) return; ctx.save(); ctx.translate(x, y); ctx.scale(s, s); fn(); ctx.restore(); }

// warna
const W = {
  navy: '#1d3557', teks: '#1d2640', oranye: '#ff7f3f', kuning: '#ffd23f', merah: '#e63946', biru: '#3a86ff',
  laut: '#4cb3d4', daun: '#7cc576', krem: '#fff8ec', putih: '#ffffff',
};

// =====================================================================
//  SUARA: musik, efek, narator
// =====================================================================
const Suara = { ctx: null, master: null, musik: null, bising: null, nyala: true };
function siapkanAudio() {
  if (Suara.ctx) { if (Suara.ctx.state !== 'running' && main) Suara.ctx.resume(); return; }
  try {
    const a = new (window.AudioContext || window.webkitAudioContext)();
    Suara.ctx = a;
    Suara.master = a.createGain(); Suara.master.gain.value = Suara.nyala ? 0.8 : 0; Suara.master.connect(a.destination);
    Suara.musik = a.createGain(); Suara.musik.gain.value = 1;
    const tunda = a.createDelay(1); tunda.delayTime.value = 0.28;
    const umpan = a.createGain(); umpan.gain.value = 0.25;
    const lp = a.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 2600;
    Suara.musik.connect(Suara.master); Suara.musik.connect(tunda); tunda.connect(lp); lp.connect(umpan); umpan.connect(tunda); lp.connect(Suara.master);
    const buf = a.createBuffer(1, a.sampleRate * 2, a.sampleRate), d = buf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    Suara.bising = buf;
  } catch (_) { Suara.ctx = null; }
}
const siap = () => Suara.ctx && Suara.ctx.state === 'running';
function nada(midi, t, durasi, vol, jenis = 'sine', tujuan = Suara.musik, serang = 0.008) {
  const a = Suara.ctx, o = a.createOscillator(), g = a.createGain();
  o.type = jenis; o.frequency.value = 440 * Math.pow(2, (midi - 69) / 12);
  g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(vol, t + serang); g.gain.exponentialRampToValueAtTime(0.0001, t + durasi);
  o.connect(g).connect(tujuan); o.start(t); o.stop(t + durasi + 0.05);
}
function bising(t, durasi, vol, jenisFilter, frek, q = 1, tujuan = Suara.master) {
  const a = Suara.ctx, n = a.createBufferSource(); n.buffer = Suara.bising; n.loop = true;
  const f = a.createBiquadFilter(); f.type = jenisFilter; f.frequency.value = frek; f.Q.value = q;
  const g = a.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + Math.min(0.3, durasi / 3)); g.gain.exponentialRampToValueAtTime(0.0001, t + durasi);
  n.connect(f).connect(g).connect(tujuan); n.start(t, Math.random()); n.stop(t + durasi + 0.05);
  return f;
}
const sfx = {
  pop() { if (!siap()) return; const t = Suara.ctx.currentTime, a = Suara.ctx, o = a.createOscillator(), g = a.createGain(); o.frequency.setValueAtTime(420, t); o.frequency.exponentialRampToValueAtTime(900, t + 0.08); g.gain.setValueAtTime(0.12, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.12); o.connect(g).connect(Suara.master); o.start(t); o.stop(t + 0.15); },
  wus() { if (!siap()) return; const f = bising(Suara.ctx.currentTime, 0.45, 0.12, 'bandpass', 800, 0.8); f.frequency.exponentialRampToValueAtTime(3000, Suara.ctx.currentTime + 0.4); },
  gemuruh(d = 3, vol = 0.5) { if (!siap()) return; bising(Suara.ctx.currentTime, d, vol, 'lowpass', 140, 0.7); const t = Suara.ctx.currentTime; nada(31, t, d, vol * 0.6, 'sawtooth', Suara.master, 0.3); },
  prang() { if (!siap()) return; const t = Suara.ctx.currentTime; bising(t, 0.35, 0.3, 'highpass', 2500, 0.5); nada(88, t, 0.4, 0.06, 'triangle', Suara.master); nada(95, t + 0.03, 0.3, 0.05, 'triangle', Suara.master); },
  tek() { if (!siap()) return; const t = Suara.ctx.currentTime; bising(t, 0.12, 0.5, 'bandpass', 1800, 2); nada(40, t, 0.6, 0.35, 'sine', Suara.master); },
  ding(n = 84) { if (!siap()) return; const t = Suara.ctx.currentTime; nada(n, t, 1, 0.1, 'sine', Suara.master); nada(n + 7, t + 0.07, 1, 0.07, 'sine', Suara.master); },
  ombak() { if (!siap()) return; const f = bising(Suara.ctx.currentTime, 4, 0.22, 'lowpass', 500, 0.6); f.frequency.linearRampToValueAtTime(1600, Suara.ctx.currentTime + 3.5); },
};
const MUSIK = {
  penasaran: { bpm: 104, akor: [[60, 64, 67], [57, 60, 64], [53, 57, 60], [55, 59, 62]], vol: 0.045 },
  tegang:    { bpm: 84,  akor: [[50, 53, 57], [46, 50, 53], [48, 52, 55], [45, 49, 52]], vol: 0.045 },
  ceria:     { bpm: 116, akor: [[53, 57, 60], [60, 64, 67], [55, 59, 62], [60, 64, 67]], vol: 0.045 },
};
const Pemutar = { mood: null, ingin: null, langkah: 0, berikut: 0 };
const POLA = [0, 2, 1, 3, 2, 1, 3, 2];
function detakMusik() {
  if (!siap()) return;
  const a = Suara.ctx;
  if (Pemutar.berikut < a.currentTime) Pemutar.berikut = a.currentTime + 0.05;
  while (Pemutar.berikut < a.currentTime + 0.25) {
    if (Pemutar.langkah % 8 === 0) Pemutar.mood = Pemutar.ingin;
    const m = MUSIK[Pemutar.mood], dl = m ? 30 / m.bpm : 0.25;
    if (m) {
      const t = Pemutar.berikut, ak = m.akor[Math.floor(Pemutar.langkah / 8) % 4], l = Pemutar.langkah % 8;
      if (l === 0 || l === 4) nada(ak[0] - 24, t, dl * 3.5, m.vol * 1.2, 'sine');
      const i = POLA[l], n = i === 3 ? ak[0] + 12 : ak[i];
      nada(n + 12, t, dl * 1.4, m.vol, 'triangle');
      if (l % 2 === 1 && Math.random() < 0.35) nada(n + 24, t, 0.25, m.vol * 0.35, 'sine');
    }
    Pemutar.berikut += dl; Pemutar.langkah++;
  }
}
// narator: rekaman jadi yang diisi oleh app.py (Streamlit)
const SUARA_DUBBING = {};
const Dub = { nyala: true, buffer: {}, aktif: new Set(), ada: Object.keys(SUARA_DUBBING).length > 0, dimuat: null, bus: null };
function muatDubbing() {
  if (!Dub.ada || !Suara.ctx) return Promise.resolve();
  if (Dub.dimuat) return Dub.dimuat;
  Dub.bus = Suara.ctx.createGain(); Dub.bus.gain.value = 1.2; Dub.bus.connect(Suara.master);
  Dub.dimuat = Promise.all(Object.entries(SUARA_DUBBING).map(async ([k, uri]) => {
    try { const bin = atob(uri.slice(uri.indexOf(',') + 1)), arr = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i); Dub.buffer[k] = await Suara.ctx.decodeAudioData(arr.buffer); } catch (_) {}
  }));
  return Dub.dimuat;
}
function ucap(teks) {
  if (!Dub.nyala || !Suara.nyala || !main || !Suara.ctx || !Dub.bus) return;
  const buf = Dub.buffer[`narator|${teks}`]; if (!buf) return;
  const s = Suara.ctx.createBufferSource(); s.buffer = buf; s.connect(Dub.bus); s.start();
  Dub.aktif.add(s); s.onended = () => Dub.aktif.delete(s);
}
function diamkan() { for (const s of Dub.aktif) { try { s.stop(); } catch (_) {} } Dub.aktif.clear(); }

// =====================================================================
//  ALAT GAMBAR
// =====================================================================
function teks(s, x, y, ukuran, warna, berat = 800, rata = 'center', huruf = '"Baloo 2", sans-serif') {
  ctx.font = `${berat} ${ukuran}px ${huruf}`; ctx.textAlign = rata; ctx.textBaseline = 'middle'; ctx.fillStyle = warna; ctx.fillText(s, x, y);
}
// label kapsul yang "pop"
function label(lt, t0, x, y, s, opt = {}) {
  const k = pop(lt, t0); if (k <= 0) return;
  const ukuran = opt.ukuran || 24;
  ctx.font = `800 ${ukuran}px "Baloo 2", sans-serif`;
  const w = ctx.measureText(s).width + ukuran * 1.1, h = ukuran * 1.7;
  diSkala(x, y, k, () => {
    ctx.fillStyle = 'rgba(0,0,0,.18)'; rrect(-w / 2 + 3, -h / 2 + 5, w, h, h / 2); ctx.fill();
    ctx.fillStyle = opt.bg || W.putih; rrect(-w / 2, -h / 2, w, h, h / 2); ctx.fill();
    teks(s, 0, 2, ukuran, opt.warna || W.teks);
  });
}
function garisPenunjuk(lt, t0, x1, y1, x2, y2, warna = '#ffffff') {
  const p = klem((lt - t0) / 0.35); if (p <= 0) return;
  ctx.strokeStyle = warna; ctx.lineWidth = 3; ctx.setLineDash([]);
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(lerp(x1, x2, p), lerp(y1, y2, p)); ctx.stroke();
  ctx.fillStyle = warna; bulat(x1, y1, 6); ctx.fill();
}
function panah(x1, y1, x2, y2, warna, lebar = 10, p = 1) {
  if (p <= 0) return;
  const x = lerp(x1, x2, p), y = lerp(y1, y2, p), a = Math.atan2(y - y1, x - x1);
  ctx.strokeStyle = warna; ctx.fillStyle = warna; ctx.lineWidth = lebar; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x - Math.cos(a) * lebar * 1.2, y - Math.sin(a) * lebar * 1.2); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - Math.cos(a - 0.5) * lebar * 2.6, y - Math.sin(a - 0.5) * lebar * 2.6); ctx.lineTo(x - Math.cos(a + 0.5) * lebar * 2.6, y - Math.sin(a + 0.5) * lebar * 2.6); ctx.closePath(); ctx.fill();
}
function gelembungTeks(lt, t0, t1, x, y, s) {
  const a = muncul(lt, t0, t1, 0.2, 0.25); if (a <= 0) return;
  ctx.font = '800 26px "Baloo 2", sans-serif';
  const w = ctx.measureText(s).width + 36, h = 54;
  diSkala(x, y, pop(lt, t0, 0.35), () => {
    ctx.globalAlpha = a;
    ctx.fillStyle = W.putih; rrect(-w / 2, -h, w, h, 18); ctx.fill();
    ctx.beginPath(); ctx.moveTo(-12, -2); ctx.lineTo(-24, 18); ctx.lineTo(8, -2); ctx.fill();
    teks(s, 0, -h / 2 + 2, 26, W.teks);
    ctx.globalAlpha = 1;
  });
}
function bintangLedak(x, y, r, warna) {
  ctx.fillStyle = warna; ctx.beginPath();
  for (let i = 0; i < 20; i++) { const a = i * Math.PI / 10, rr = i % 2 ? r * 0.55 : r; ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); }
  ctx.closePath(); ctx.fill();
}
function kartu(x, y, w, h, warna = W.putih, r = 22) {
  ctx.fillStyle = 'rgba(0,0,0,.16)'; rrect(x + 4, y + 7, w, h, r); ctx.fill();
  ctx.fillStyle = warna; rrect(x, y, w, h, r); ctx.fill();
}
function rumah(x, y, s = 1, warna = '#f4a261') {
  diSkala(x, y, s, () => {
    ctx.fillStyle = warna; ctx.fillRect(-26, -40, 52, 40);
    ctx.fillStyle = W.merah; ctx.beginPath(); ctx.moveTo(-34, -38); ctx.lineTo(0, -66); ctx.lineTo(34, -38); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#6b4226'; ctx.fillRect(-7, -22, 14, 22);
    ctx.fillStyle = '#bde0fe'; ctx.fillRect(12, -32, 10, 10);
  });
}
function pohon(x, y, s = 1) {
  diSkala(x, y, s, () => {
    ctx.fillStyle = '#8d5a3b'; ctx.fillRect(-5, -40, 10, 40);
    ctx.fillStyle = '#4caf6d'; bulat(0, -56, 24); ctx.fill(); bulat(-16, -44, 16); ctx.fill(); bulat(16, -44, 16); ctx.fill();
  });
}
function meja(x, y, w = 200) {
  ctx.fillStyle = '#9c6644'; rrect(x - w / 2, y - 92, w, 16, 5); ctx.fill();
  ctx.fillStyle = '#7f5539'; ctx.fillRect(x - w / 2 + 12, y - 78, 14, 78); ctx.fillRect(x + w / 2 - 26, y - 78, 14, 78);
}

// ---------- Kiki, pemandu cerita (gaya flat, menghadap depan)
function kiki(x, y, s = 1, o = {}) {
  const jk = o.jongkok ? 1 : 0;
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  if (o.jalan) ctx.rotate(Math.sin(waktu * 12) * 0.04);
  const bob = o.jalan ? -Math.abs(Math.sin(waktu * 12)) * 6 : Math.sin(waktu * 2.2) * 1.5 * (1 - jk);
  ctx.fillStyle = 'rgba(0,0,0,.15)'; elips(0, 0, 40, 7); ctx.fill();
  ctx.fillStyle = '#34405f';
  if (!jk) {
    const l = o.jalan ? Math.sin(waktu * 12) * 8 : 0;
    rrect(-22, -64 - l, 18, 64 + l, 8); ctx.fill(); rrect(4, -64 + l, 18, 64 - l, 8); ctx.fill();
    ctx.fillStyle = '#ffffff'; rrect(-27, -11 - Math.max(0, l), 25, 11, 5); ctx.fill(); rrect(2, -11 - Math.max(0, -l), 25, 11, 5); ctx.fill();
  } else {
    rrect(-34, -36, 30, 22, 10); ctx.fill(); rrect(4, -36, 30, 22, 10); ctx.fill();
    ctx.fillStyle = '#ffffff'; rrect(-36, -13, 26, 12, 5); ctx.fill(); rrect(10, -13, 26, 12, 5); ctx.fill();
  }
  ctx.translate(0, (jk ? 34 : 0) + bob);
  // lengan
  const tangan = {
    turun: [[-42, -66], [42, -66]], tunjuk: [[-42, -66], [84, -150]], angkat: [[-60, -178], [60, -178]],
    kepala: [[-34, -186], [34, -186]], lambai: [[-42, -66], [66, -176 + Math.sin(waktu * 12) * 10]],
    pegang: [[-40, -40], [40, -40]], lindungi: [[-22, -196], [22, -196]], lari: [[-48 + Math.sin(waktu * 12) * 14, -80], [48 - Math.sin(waktu * 12) * 14, -80]],
  }[o.tangan || 'turun'];
  ctx.strokeStyle = '#ff7f3f'; ctx.lineWidth = 13; ctx.lineCap = 'round';
  for (const [[hx, hy], sx] of [[tangan[0], -28], [tangan[1], 28]]) {
    ctx.beginPath(); ctx.moveTo(sx, -112); ctx.quadraticCurveTo((sx + hx) / 2 + (sx < 0 ? -8 : 8), (-112 + hy) / 2, hx, hy); ctx.stroke();
  }
  ctx.fillStyle = '#f5c9a1'; for (const [hx, hy] of tangan) { bulat(hx, hy, 8); ctx.fill(); }
  // badan
  ctx.fillStyle = '#ff7f3f'; rrect(-32, -128, 64, 72, 22); ctx.fill();
  ctx.fillStyle = '#ffd23f'; bulat(0, -96, 11); ctx.fill();
  ctx.fillStyle = '#e8672e'; ctx.fillRect(-32, -64, 64, 8);
  // kepala
  const hy = -166;
  ctx.fillStyle = '#f5c9a1'; bulat(-36, hy + 2, 8); ctx.fill(); bulat(36, hy + 2, 8); ctx.fill(); bulat(0, hy, 37); ctx.fill();
  ctx.fillStyle = '#2b2233';
  ctx.beginPath(); ctx.arc(0, hy - 2, 39, Math.PI * 1.03, Math.PI * 1.97);
  ctx.quadraticCurveTo(26, hy - 12, 10, hy - 8); ctx.quadraticCurveTo(-4, hy - 22, -18, hy - 8); ctx.quadraticCurveTo(-30, hy - 6, -38, hy + 2); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = '#2b2233'; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(2, hy - 40); ctx.quadraticCurveTo(14, hy - 58, 22, hy - 48); ctx.stroke();
  const e = o.ekspresi || 'senyum', ex = 13, ey = hy + 2;
  const kedip = e === 'senyum' && (waktu % 3.4) < 0.12;
  ctx.fillStyle = '#2b2233'; ctx.strokeStyle = '#2b2233'; ctx.lineWidth = 3.5;
  if (e === 'kaget') { for (const d of [-1, 1]) { ctx.fillStyle = '#fff'; bulat(d * ex, ey, 9); ctx.fill(); ctx.fillStyle = '#2b2233'; bulat(d * ex, ey, 4.5); ctx.fill(); } }
  else if (e === 'senang') { for (const d of [-1, 1]) { ctx.beginPath(); ctx.arc(d * ex, ey + 3, 6, Math.PI * 1.1, Math.PI * 1.9); ctx.stroke(); } }
  else if (kedip) { for (const d of [-1, 1]) { ctx.beginPath(); ctx.moveTo(d * ex - 5, ey); ctx.lineTo(d * ex + 5, ey); ctx.stroke(); } }
  else { const lx = e === 'mikir' ? 2 : 0, ly = e === 'mikir' ? -3 : 0; for (const d of [-1, 1]) { bulat(d * ex + lx, ey + ly, 5); ctx.fill(); } }
  if (e === 'mikir') { ctx.beginPath(); ctx.moveTo(4, ey - 14); ctx.lineTo(20, ey - 18); ctx.stroke(); }
  if (e === 'kaget') { ctx.fillStyle = '#7a2230'; elips(0, hy + 22, 7, 9); ctx.fill(); }
  else if (e === 'senang') { ctx.fillStyle = '#7a2230'; ctx.beginPath(); ctx.arc(0, hy + 16, 10, 0, Math.PI); ctx.closePath(); ctx.fill(); }
  else if (e === 'mikir') { ctx.beginPath(); ctx.moveTo(-4, hy + 20); ctx.lineTo(8, hy + 18); ctx.stroke(); }
  else { ctx.beginPath(); ctx.arc(0, hy + 14, 8, 0.15 * Math.PI, 0.85 * Math.PI); ctx.stroke(); }
  ctx.fillStyle = 'rgba(255,120,130,.45)'; elips(-24, hy + 14, 7, 4); ctx.fill(); elips(24, hy + 14, 7, 4); ctx.fill();
  if (e === 'kaget' && o.keringat !== false) { ctx.fillStyle = '#8fd4ff'; elips(42, hy - 18 + (waktu * 30) % 12, 5, 8); ctx.fill(); }
  ctx.restore();
}

// ---------- Bumi
const RB = rng(8);
const BENUA = Array.from({ length: 9 }, () => ({ u: RB(), v: RB() * 1.4 - 0.7, r: 0.18 + RB() * 0.22, n: Array.from({ length: 7 }, () => 0.7 + RB() * 0.5) }));
function bumi(cx, cy, R, putar) {
  ctx.save(); bulat(cx, cy, R); ctx.clip();
  ctx.fillStyle = '#3a9bd9'; ctx.fillRect(cx - R, cy - R, R * 2, R * 2);
  ctx.fillStyle = W.daun;
  for (const b of BENUA) {
    for (const geser of [0, 1]) {
      const u = ((b.u + putar) % 1 + geser) * 2 - 1;
      const x = cx + (u - 1) * R * 1.3 + R * 1.3, y = cy + b.v * R;
      ctx.beginPath();
      b.n.forEach((k, i) => { const a = i / b.n.length * 6.2832; const px = x + Math.cos(a) * b.r * R * k, py = y + Math.sin(a) * b.r * R * k * 0.8; i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
      ctx.closePath(); ctx.fill();
    }
  }
  const g = ctx.createRadialGradient(cx - R * 0.35, cy - R * 0.35, R * 0.2, cx, cy, R);
  g.addColorStop(0, 'rgba(255,255,255,.18)'); g.addColorStop(1, 'rgba(0,20,60,.35)');
  ctx.fillStyle = g; ctx.fillRect(cx - R, cy - R, R * 2, R * 2);
  ctx.restore();
}
const BINTANG = (() => { const r = rng(3); return Array.from({ length: 120 }, () => [r() * SW, r() * SH, 0.6 + r() * 1.6, r() * 6]); })();
function langitMalam(w1 = '#16213e', w2 = '#1f3b63') {
  const g = ctx.createLinearGradient(0, 0, 0, SH); g.addColorStop(0, w1); g.addColorStop(1, w2);
  ctx.fillStyle = g; ctx.fillRect(-20, -20, SW + 40, SH + 40);
  for (const [x, y, r, f] of BINTANG) { ctx.fillStyle = `rgba(255,255,255,${0.3 + 0.5 * (0.5 + 0.5 * Math.sin(waktu * 2 + f))})`; bulat(x, y, r); ctx.fill(); }
}
function latarTerang(w1 = '#dff3f7', w2 = '#bfe6f0') {
  const g = ctx.createLinearGradient(0, 0, 0, SH); g.addColorStop(0, w1); g.addColorStop(1, w2);
  ctx.fillStyle = g; ctx.fillRect(-20, -20, SW + 40, SH + 40);
  ctx.fillStyle = 'rgba(255,255,255,.35)';
  for (let i = 0; i < 6; i++) { const x = ((i * 260 + waktu * 12) % 1500) - 150, y = 70 + (i % 3) * 40; elips(x, y, 60, 18); ctx.fill(); elips(x + 30, y - 12, 36, 16); ctx.fill(); }
}

// =====================================================================
//  ADEGAN
// =====================================================================
let goncang = 0; // guncangan layar (0..1) yang diatur tiap adegan
const ADEGAN = [
  // ---------------------------------------------------------------- 0. PEMBUKA
  {
    nama: 'Pembuka', dur: 9.5, musik: lt => lt < 5 ? null : 'penasaran',
    teks: [[0.5, 3.9, 'Pernah nggak, lagi santai tiba-tiba lantai bergoyang?'], [5.2, 9.3, 'Itu namanya gempa bumi. Tapi… sebenarnya kenapa bisa terjadi?']],
    acara: [[0.9, () => sfx.gemuruh(3.4, 0.45)], [2.6, sfx.prang], [5.0, sfx.wus]],
    gambar(lt) {
      goncang = lt > 0.9 && lt < 4.3 ? kf(lt, [[0.9, 0.2], [1.6, 1], [3.6, 1], [4.3, 0]]) : 0;
      // kamar
      ctx.fillStyle = '#d7eef0'; ctx.fillRect(-20, -20, SW + 40, 560);
      ctx.fillStyle = '#c8956a'; ctx.fillRect(-20, 530, SW + 40, 220);
      ctx.strokeStyle = 'rgba(0,0,0,.08)'; ctx.lineWidth = 3; for (let y = 560; y < 720; y += 36) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(SW, y); ctx.stroke(); }
      ctx.fillStyle = '#b37d52'; ctx.fillRect(-20, 522, SW + 40, 12);
      // jendela
      kartu(900, 110, 230, 200, '#ffffff', 10); ctx.fillStyle = '#9fd9f0'; ctx.fillRect(912, 122, 206, 176);
      ctx.fillStyle = '#fff'; elips(990, 190, 40, 14); ctx.fill(); ctx.fillRect(1012, 122, 6, 176); ctx.fillRect(912, 206, 206, 6);
      // rak buku
      ctx.save(); ctx.translate(200, 250); ctx.rotate(Math.sin(waktu * 20) * 0.03 * goncang);
      ctx.fillStyle = '#9c6644'; ctx.fillRect(-90, 0, 180, 12);
      ['#e63946', '#3a86ff', '#ffd23f', '#2a9d8f', '#ff7f3f', '#8e7dbe'].forEach((c, i) => { ctx.save(); ctx.translate(-80 + i * 28, 0); ctx.rotate(Math.sin(waktu * 25 + i) * 0.12 * goncang); ctx.fillStyle = c; ctx.fillRect(0, -60 + (i % 2) * 8, 22, 60 - (i % 2) * 8); ctx.restore(); });
      ctx.restore();
      // lampu gantung
      const ayun = Math.sin(waktu * 6) * 0.35 * goncang + Math.sin(lt * 2) * 0.05 * klem(1 - (lt - 4.3) / 2);
      ctx.save(); ctx.translate(640, -10); ctx.rotate(ayun);
      ctx.strokeStyle = '#444'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, 150); ctx.stroke();
      ctx.fillStyle = '#ffd23f'; ctx.beginPath(); ctx.moveTo(-50, 200); ctx.lineTo(50, 200); ctx.lineTo(24, 150); ctx.lineTo(-24, 150); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#fff6c8'; bulat(0, 204, 14); ctx.fill();
      ctx.restore();
      // meja & cangkir jatuh
      meja(870, 640, 240);
      let cx = kf(lt, [[1.4, 900], [2.4, 985]]), cy = 548, rot = 0;
      if (lt > 2.4) { const u = klem((lt - 2.4) / 0.35); cx = 985 + u * 30; cy = 548 + u * u * 90; rot = u * 1.6; }
      if (lt < 2.75) { ctx.save(); ctx.translate(cx, cy); ctx.rotate(rot); ctx.fillStyle = '#fff'; rrect(-18, -30, 36, 30, 6); ctx.fill(); ctx.strokeStyle = '#fff'; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(20, -16, 9, -1.2, 1.2); ctx.stroke(); ctx.restore(); }
      else { ctx.fillStyle = '#fff'; for (const [dx, dy, r] of [[-14, 0, 8], [8, 4, 10], [26, -2, 7], [40, 6, 6]]) { ctx.beginPath(); ctx.moveTo(1015 + dx, 646 + dy); ctx.lineTo(1015 + dx + r, 640 + dy); ctx.lineTo(1015 + dx + r * 1.5, 648 + dy); ctx.fill(); } }
      // Kiki
      const ek = lt < 0.9 ? 'senyum' : lt < 4.6 ? 'kaget' : 'mikir';
      kiki(430, 640, 1.15, { ekspresi: ek, tangan: lt > 1.1 && lt < 4.4 ? 'angkat' : lt > 5 ? 'kepala' : 'turun' });
      gelembungTeks(lt, 1.3, 3.9, 470, 380, 'Eh… eh… goyang?!');
      // garis getar
      if (goncang > 0.1) { ctx.strokeStyle = 'rgba(29,53,87,.5)'; ctx.lineWidth = 4; for (const [x, y] of [[330, 420], [540, 420], [320, 480], [550, 480]]) { ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + (x < 430 ? -18 : 18), y - 8); ctx.stroke(); } }
      // kartu judul
      const k = pop(lt, 5.0, 0.6);
      if (k > 0) {
        ctx.fillStyle = `rgba(29,53,87,${0.55 * klem((lt - 5) / 0.4)})`; ctx.fillRect(-20, -20, SW + 40, SH + 40);
        diSkala(640, 330, k, () => {
          ctx.save(); ctx.rotate(-0.03);
          kartu(-360, -130, 720, 250, W.navy, 28);
          teks('GEMPA BUMI', 0, -40, 110, W.oranye);
          teks('itu apa sih?', 0, 60, 58, W.putih);
          ctx.strokeStyle = W.kuning; ctx.lineWidth = 6; ctx.lineJoin = 'round';
          ctx.beginPath(); ctx.moveTo(-330, -110); ctx.lineTo(-300, -80); ctx.lineTo(-318, -60); ctx.lineTo(-290, -30); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(330, 90); ctx.lineTo(300, 60); ctx.lineTo(316, 40); ctx.lineTo(290, 12); ctx.stroke();
          ctx.restore();
        });
      }
    }
  },
  // ---------------------------------------------------------------- 1. ISI BUMI
  {
    nama: 'Isi Bumi', dur: 15, musik: () => 'penasaran',
    teks: [[0.4, 3.2, 'Untuk tahu jawabannya, kita intip dulu isi Bumi.'], [3.4, 7.0, 'Paling luar ada kerak, lapisan tipis tempat kita berpijak.'], [7.2, 12.0, 'Di bawahnya ada mantel yang panas, lalu inti Bumi yang super panas.'], [12.2, 14.8, 'Nah, yang penting buat gempa adalah kerak ini.']],
    acara: [[0.3, sfx.wus], [2.2, sfx.wus], [3.6, sfx.pop], [7.4, sfx.pop], [9.4, sfx.pop], [10.6, sfx.pop], [12.3, () => sfx.ding(88)]],
    gambar(lt) {
      goncang = 0;
      langitMalam();
      const cx = 480, cy = 350, R = 215, s = pop(lt, 0.2, 0.7);
      diSkala(cx, cy, s, () => bumi(0, 0, R, waktu * 0.02));
      const span = kfh(lt, [[2.2, 0], [3.2, 1.35]]), a0 = -1.05;
      if (span > 0.01) {
        const lap = [[R, '#8d6e63'], [R - 16, '#e76f51'], [R * 0.56, '#f4a261'], [R * 0.3, '#ffe08a']];
        for (const [r, c] of lap) { ctx.fillStyle = c; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, r, a0, a0 + span); ctx.closePath(); ctx.fill(); }
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.3); g.addColorStop(0, 'rgba(255,255,220,.9)'); g.addColorStop(1, 'rgba(255,240,150,0)');
        ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, R * 0.3, a0, a0 + span); ctx.closePath(); ctx.fill();
        // sorot kerak
        if (lt > 12.2) { ctx.strokeStyle = `rgba(255,210,63,${0.6 + 0.4 * Math.sin(waktu * 8)})`; ctx.lineWidth = 8; ctx.beginPath(); ctx.arc(cx, cy, R - 4, a0, a0 + span); ctx.stroke(); }
      }
      const am = a0 + 1.35 * 0.55;
      const titik = [[R - 7, 3.6, 'Kerak', 150], [R * 0.78, 7.4, 'Mantel', 250], [R * 0.43, 9.4, 'Inti luar', 350], [R * 0.14, 10.6, 'Inti dalam', 450]];
      for (const [r, t0, nama, ly] of titik) {
        const px = cx + Math.cos(am) * r, py = cy + Math.sin(am) * r;
        garisPenunjuk(lt, t0, px, py, 860, ly);
        label(lt, t0 + 0.2, 960, ly, nama, { bg: nama === 'Kerak' && lt > 12.2 ? W.kuning : W.putih });
      }
      label(lt, 4.4, 1110, 150, '± 5–70 km', { ukuran: 18, bg: W.oranye, warna: '#fff' });
    }
  },
  // ---------------------------------------------------------------- 2. LEMPENG
  {
    nama: 'Lempeng', dur: 14.5, musik: () => 'penasaran',
    teks: [[0.4, 5.6, 'Kerak Bumi ternyata tidak utuh. Ia terpecah jadi potongan raksasa bernama lempeng tektonik.'], [5.9, 10.0, 'Lempeng-lempeng ini terus bergerak, beberapa sentimeter setiap tahun.'], [10.3, 14.2, 'Kurang lebih secepat kuku kita tumbuh!']],
    acara: [[1.5, sfx.tek], [2.2, sfx.pop], [6.2, sfx.wus], [10.4, sfx.pop]],
    gambar(lt) {
      goncang = lt > 1.5 && lt < 1.9 ? 0.5 : 0;
      latarTerang();
      const L = [180, 130, 1100, 530];
      kartu(L[0] - 14, L[1] - 14, L[2] - L[0] + 28, L[3] - L[1] + 28, '#3a9bd9', 26);
      const PL = [
        [[180, 130], [520, 130], [480, 300], [180, 340]], [[520, 130], [860, 130], [820, 280], [480, 300]], [[860, 130], [1100, 130], [1100, 360], [820, 280]],
        [[180, 340], [480, 300], [560, 530], [180, 530]], [[480, 300], [820, 280], [1100, 360], [1100, 530], [560, 530]],
      ];
      const warna = ['#9bd18b', '#c9dd8a', '#e6c88f', '#a8d5a2', '#d7b98e'];
      const gerakArah = [[-1, -0.4], [0.2, -1], [1, -0.2], [-0.6, 1], [0.7, 0.8]];
      const pisah = kfh(lt, [[1.5, 0], [2.4, 9]]);
      PL.forEach((p, i) => {
        const cxp = p.reduce((s, q) => s + q[0], 0) / p.length, cyp = p.reduce((s, q) => s + q[1], 0) / p.length;
        const dx = (cxp - 640) / 460 * pisah + gerakArah[i][0] * Math.sin(waktu * 0.9) * 4 * klem(lt - 5.8), dy = (cyp - 330) / 200 * pisah + gerakArah[i][1] * Math.sin(waktu * 0.9) * 4 * klem(lt - 5.8);
        ctx.save(); ctx.translate(dx, dy);
        ctx.beginPath(); p.forEach(([x, y], j) => { const kx = lerp(x, cxp, 0.012), ky = lerp(y, cyp, 0.012); j ? ctx.lineTo(kx, ky) : ctx.moveTo(kx, ky); }); ctx.closePath();
        ctx.fillStyle = warna[i]; ctx.fill();
        ctx.fillStyle = 'rgba(255,255,255,.25)'; for (let k = 0; k < 4; k++) { elips(cxp - 40 + k * 30, cyp - 20 + (k % 2) * 30, 18, 8); ctx.fill(); }
        const pa = klem((lt - 6.2) / 0.5);
        panah(cxp - gerakArah[i][0] * 30, cyp - gerakArah[i][1] * 30, cxp + gerakArah[i][0] * 40, cyp + gerakArah[i][1] * 40, W.merah, 9, pa);
        ctx.restore();
      });
      label(lt, 2.2, 640, 78, 'Lempeng Tektonik', { ukuran: 30, bg: W.navy, warna: '#fff' });
      // kartu kuku
      const k = pop(lt, 10.4, 0.5);
      diSkala(980, 470, k, () => {
        kartu(-150, -90, 300, 170, W.krem, 24);
        ctx.fillStyle = '#f5c9a1'; rrect(-120, -40, 120, 56, 26); ctx.fill();
        ctx.fillStyle = '#ffd6de'; rrect(-40, -30, 36, 36, 12); ctx.fill();
        ctx.strokeStyle = '#d99a7b'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(-80, -10); ctx.lineTo(-80, 6); ctx.stroke();
        teks('≈ 2–10 cm', 70, -22, 30, W.merah);
        teks('per tahun', 70, 12, 22, W.teks, 700);
        teks('secepat kuku tumbuh 💅', 0, 56, 20, W.teks, 700);
      });
    }
  },
  // ---------------------------------------------------------------- 3. INDONESIA
  {
    nama: 'Indonesia', dur: 14, musik: () => 'penasaran',
    teks: [[0.4, 4.6, 'Indonesia letaknya istimewa: di pertemuan tiga lempeng besar.'], [4.9, 9.6, 'Lempeng Eurasia, Indo-Australia, dan Pasifik saling dorong di bawah negeri kita.'], [9.9, 13.8, 'Makanya Indonesia termasuk negara yang paling sering gempa.']],
    acara: [[5.2, sfx.pop], [6.6, sfx.pop], [8.0, sfx.pop], [10, () => sfx.gemuruh(1.2, 0.25)]],
    gambar(lt) {
      goncang = lt > 10 && lt < 11 ? 0.35 : 0;
      const g = ctx.createLinearGradient(0, 0, 0, SH); g.addColorStop(0, '#8fd3e8'); g.addColorStop(1, '#5fb8d6'); ctx.fillStyle = g; ctx.fillRect(-20, -20, SW + 40, SH + 40);
      ctx.strokeStyle = 'rgba(255,255,255,.35)'; ctx.lineWidth = 2;
      for (let i = 0; i < 12; i++) { const y = 60 + i * 55, x = ((i * 137 + waktu * 20) % 1400) - 100; ctx.beginPath(); ctx.moveTo(x, y); ctx.quadraticCurveTo(x + 15, y - 8, x + 30, y); ctx.quadraticCurveTo(x + 45, y + 8, x + 60, y); ctx.stroke(); }
      const k = pop(lt, 0.3, 0.6);
      diSkala(640, 360, k, () => {
        ctx.translate(-640, -360);
        const pulau = [
          [[170, 220], [215, 215], [300, 300], [380, 390], [420, 450], [400, 470], [330, 420], [250, 340], [185, 270]],
          [[430, 480], [520, 478], [620, 495], [660, 510], [650, 528], [560, 522], [470, 512], [428, 500]],
          [[450, 230], [520, 170], [600, 170], [640, 230], [630, 320], [570, 380], [500, 390], [460, 330]],
          [[720, 250], [790, 230], [800, 245], [745, 265], [760, 300], [820, 300], [815, 318], [760, 320], [770, 380], [750, 390], [735, 330], [715, 300]],
          [[940, 300], [1010, 280], [1090, 310], [1130, 360], [1120, 420], [1060, 430], [1000, 400], [960, 360], [930, 330]],
        ];
        ctx.fillStyle = '#e9d8a6'; for (const p of pulau) { ctx.save(); ctx.translate(0, 6); poligon(p); ctx.fill(); ctx.restore(); }
        ctx.fillStyle = W.daun; for (const p of pulau) { poligon(p); ctx.fill(); }
        for (const [x, y, rx] of [[690, 522, 12], [728, 528, 14], [770, 532, 16], [815, 535, 14], [858, 530, 12], [872, 322, 14], [884, 384, 12]]) { elips(x, y, rx, 8); ctx.fill(); }
        // batas lempeng
        const batas = [[120, 240], [190, 380], [320, 505], [450, 565], [600, 585], [760, 578], [900, 560], [980, 500], [1010, 380], [1020, 250], [960, 160], [900, 110]];
        const p = klem((lt - 2) / 2.5), n = Math.floor(p * (batas.length - 1));
        ctx.strokeStyle = W.merah; ctx.lineWidth = 6; ctx.setLineDash([16, 10]); ctx.lineDashOffset = -waktu * 30;
        ctx.beginPath(); ctx.moveTo(...batas[0]);
        for (let i = 1; i <= n; i++) ctx.lineTo(...batas[i]);
        if (n < batas.length - 1) { const f = p * (batas.length - 1) - n; ctx.lineTo(lerp(batas[n][0], batas[n + 1][0], f), lerp(batas[n][1], batas[n + 1][1], f)); }
        ctx.stroke(); ctx.setLineDash([]);
        // titik-titik gempa
        if (lt > 9.9) { const r = rng(4); for (let i = 0; i < 16; i++) { const j = Math.floor(r() * (batas.length - 1)), f = r(); const x = lerp(batas[j][0], batas[j + 1][0], f) + (r() - 0.5) * 50, y = lerp(batas[j][1], batas[j + 1][1], f) + (r() - 0.5) * 50; const puls = (waktu * 1.4 + r()) % 1; ctx.strokeStyle = `rgba(230,57,70,${1 - puls})`; ctx.lineWidth = 3; bulat(x, y, 6 + puls * 22); ctx.stroke(); ctx.fillStyle = W.merah; bulat(x, y, 5); ctx.fill(); } }
        panah(470, 640, 520, 590, W.navy, 10, klem((lt - 6.8) / 0.5));
        panah(1230, 250, 1150, 270, W.navy, 10, klem((lt - 8.2) / 0.5));
      });
      label(lt, 0.9, 640, 60, '🇮🇩 Indonesia', { ukuran: 26, bg: W.navy, warna: '#fff' });
      label(lt, 5.2, 520, 118, 'Lempeng Eurasia', { ukuran: 22 });
      label(lt, 6.6, 300, 610, 'Lempeng Indo-Australia', { ukuran: 22 });
      label(lt, 8.0, 1130, 190, 'Lempeng Pasifik', { ukuran: 22 });
    }
  },
  // ---------------------------------------------------------------- 4. KENAPA GEMPA
  {
    nama: 'Kenapa Gempa', dur: 18, musik: lt => lt < 9.4 ? 'tegang' : lt < 12 ? null : 'tegang',
    teks: [[0.4, 3.9, 'Di batas lempeng, dua lempeng bisa saling mengunci.'], [4.2, 9.2, 'Tekanannya terus menumpuk, seperti penggaris yang kita bengkokkan pelan-pelan…'], [9.4, 12.3, '…sampai akhirnya tidak kuat dan lepas tiba-tiba!'], [12.6, 17.6, 'Energi yang lepas itu menyebar sebagai getaran. Itulah gempa bumi.']],
    acara: [[1.2, sfx.pop], [2.2, sfx.pop], [2.9, sfx.pop], [4.3, sfx.wus], [9.4, () => { sfx.tek(); sfx.gemuruh(3, 0.5); }], [12.8, sfx.pop]],
    gambar(lt) {
      let b = kf(lt, [[1, 0], [9.4, 1]], halus);
      if (lt > 9.4) { const u = lt - 9.4; b = -0.55 * Math.exp(-u * 1.8) * Math.cos(u * 9); }
      goncang = lt > 9.4 && lt < 12.5 ? kf(lt, [[9.4, 1], [12.5, 0]]) : (lt > 6 && lt < 9.4 ? (lt - 6) / 3.4 * 0.12 : 0);
      ctx.fillStyle = '#bfe6f2'; ctx.fillRect(-20, -20, SW + 40, 360);
      ctx.fillStyle = '#e9885b'; ctx.fillRect(-20, 300, SW + 40, 460);
      ctx.fillStyle = 'rgba(255,255,255,.12)'; for (let i = 0; i < 10; i++) { elips((i * 157 + waktu * 15) % 1300, 520 + (i % 3) * 50, 60, 14); ctx.fill(); }
      // laut
      const naik = Math.max(0, -b) * 26;
      ctx.fillStyle = '#4aa8d8'; ctx.beginPath(); ctx.moveTo(-20, 330); ctx.lineTo(-20, 240);
      for (let x = -20; x <= 640; x += 20) ctx.lineTo(x, 240 + Math.sin(x * 0.03 + waktu * 2) * 4 - naik * Math.exp(-Math.pow((x - 520) / 90, 2)));
      ctx.lineTo(640, 330); ctx.closePath(); ctx.fill();
      // lempeng samudra (menunjam)
      ctx.fillStyle = '#6c7a92'; ctx.beginPath(); ctx.moveTo(-20, 330); ctx.lineTo(580, 330); ctx.quadraticCurveTo(720, 345, 1000, 640); ctx.lineTo(900, 760); ctx.quadraticCurveTo(640, 450, 540, 425); ctx.lineTo(-20, 425); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,.2)'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(-20, 375); ctx.lineTo(560, 375); ctx.quadraticCurveTo(690, 390, 950, 700); ctx.stroke();
      // lempeng benua (ujungnya terseret)
      const tx = 575, ty = 330 + b * 45;
      ctx.fillStyle = '#b08968'; ctx.beginPath(); ctx.moveTo(tx, ty); ctx.quadraticCurveTo(650, 300 + b * 20, 760, 290); ctx.lineTo(SW + 20, 290); ctx.lineTo(SW + 20, 430); ctx.lineTo(820, 430); ctx.quadraticCurveTo(700, 400 + b * 20, tx + 12, ty + 14); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#7cc576'; ctx.beginPath(); ctx.moveTo(700, 296 + b * 8); ctx.quadraticCurveTo(740, 286, 780, 288); ctx.lineTo(SW + 20, 288); ctx.lineTo(SW + 20, 300); ctx.lineTo(700, 306 + b * 8); ctx.fill();
      ctx.fillStyle = '#8d6e63'; for (const [x, h] of [[930, 90], [1040, 130], [1150, 80]]) { ctx.beginPath(); ctx.moveTo(x - h * 0.8, 290); ctx.lineTo(x, 290 - h); ctx.lineTo(x + h * 0.8, 290); ctx.fill(); ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.moveTo(x - h * 0.2, 290 - h * 0.75); ctx.lineTo(x, 290 - h); ctx.lineTo(x + h * 0.2, 290 - h * 0.75); ctx.fill(); ctx.fillStyle = '#8d6e63'; }
      rumah(820, 290, 0.8); rumah(870, 290, 0.7, '#e9c46a');
      // panah dorongan
      panah(120, 380, 300, 380, W.navy, 12, klem((lt - 1) / 0.6));
      // gembok (terkunci)
      const kunci = muncul(lt, 2.9, 9.4, 0.3, 0.2);
      if (kunci > 0) diSkala(620, 350, pop(lt, 2.9) * kunci, () => { ctx.fillStyle = W.kuning; rrect(-18, -10, 36, 30, 6); ctx.fill(); ctx.strokeStyle = W.kuning; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(0, -10, 12, Math.PI, 0); ctx.stroke(); ctx.fillStyle = W.navy; bulat(0, 4, 4); ctx.fill(); });
      // gelombang getar
      if (lt > 9.6) for (let k = 0; k < 5; k++) { const r = (lt - 9.6 - k * 0.45) * 320; if (r > 0) { ctx.strokeStyle = `rgba(255,255,255,${klem(1 - r / 900) * 0.9})`; ctx.lineWidth = 6; bulat(640, 370, r); ctx.stroke(); } }
      if (lt > 9.4 && lt < 9.7) { ctx.fillStyle = `rgba(255,255,255,${(9.7 - lt) / 0.3 * 0.7})`; ctx.fillRect(-20, -20, SW + 40, SH + 40); }
      if (lt > 9.4) { const k = pop(lt, 9.45, 0.4) * muncul(lt, 9.4, 12, 0.1, 0.5); diSkala(640, 370, k, () => bintangLedak(0, 0, 50, W.kuning)); }
      label(lt, 1.2, 200, 460, 'Lempeng samudra', { ukuran: 20 });
      label(lt, 2.2, 1100, 400, 'Lempeng benua', { ukuran: 20 });
      label(lt, 12.8, 640, 250, 'GEMPA!', { ukuran: 34, bg: W.merah, warna: '#fff' });
      // meteran tekanan
      const tk = lt < 9.4 ? kf(lt, [[1, 0], [9.4, 1]]) : klem(1 - (lt - 9.4) * 3);
      const mm = pop(lt, 3.9);
      diSkala(1190, 170, mm, () => {
        kartu(-44, -120, 88, 220, '#fff', 18);
        ctx.fillStyle = '#e8edf5'; rrect(-14, -96, 28, 150, 14); ctx.fill();
        ctx.fillStyle = tk > 0.7 ? W.merah : tk > 0.4 ? W.oranye : '#2a9d8f'; rrect(-14, -96 + 150 * (1 - tk), 28, 150 * tk + 0.1, 14); ctx.fill();
        teks('Tekanan', 0, 78, 16, W.teks);
      });
      // penggaris (perumpamaan)
      const pg = muncul(lt, 4.3, 12.3, 0.4, 0.4);
      if (pg > 0) diSkala(330, 160, pop(lt, 4.3) * pg, () => {
        kartu(-170, -95, 340, 180, W.krem, 22);
        if (lt < 9.4) {
          const bend = kf(lt, [[4.4, 0], [9.4, 1]]) * 60;
          ctx.strokeStyle = W.kuning; ctx.lineWidth = 16; ctx.lineCap = 'butt';
          ctx.beginPath(); ctx.moveTo(-120, 30); ctx.quadraticCurveTo(0, 30 - bend * 1.6, 120, 30); ctx.stroke();
          ctx.strokeStyle = '#c9a227'; ctx.lineWidth = 2; for (let i = -100; i <= 100; i += 20) { const y = 30 - bend * 1.6 * (1 - (i / 120) ** 2) * 0.5; ctx.beginPath(); ctx.moveTo(i, y - 6); ctx.lineTo(i, y + 2); ctx.stroke(); }
          ctx.fillStyle = '#f5c9a1'; bulat(-126, 34, 20); ctx.fill(); bulat(126, 34, 20); ctx.fill();
        } else {
          ctx.strokeStyle = W.kuning; ctx.lineWidth = 16;
          ctx.beginPath(); ctx.moveTo(-120, 30); ctx.lineTo(-14, -20); ctx.stroke(); ctx.beginPath(); ctx.moveTo(120, 30); ctx.lineTo(14, -20); ctx.stroke();
          ctx.fillStyle = '#f5c9a1'; bulat(-126, 34, 20); ctx.fill(); bulat(126, 34, 20); ctx.fill();
          diSkala(0, -40, pop(lt, 9.4, 0.3), () => { bintangLedak(0, 0, 46, W.merah); teks('TEK!', 0, 2, 26, '#fff'); });
        }
        teks('seperti penggaris…', 0, -68, 20, W.teks, 700);
      });
    }
  },
  // ---------------------------------------------------------------- 5. TITIK GEMPA
  {
    nama: 'Titik Gempa', dur: 11, musik: () => 'penasaran',
    teks: [[0.4, 4.6, 'Titik asal gempa di dalam Bumi disebut hiposentrum.'], [5.0, 10.6, 'Sedangkan titik di permukaan tepat di atasnya disebut episentrum.']],
    acara: [[1.2, sfx.pop], [5.6, sfx.pop], [6.0, sfx.pop]],
    gambar(lt) {
      goncang = 0;
      latarTerang();
      const lap = [[300, '#7cc576'], [318, '#b08968'], [420, '#9c7a5b'], [540, '#86664b']];
      for (let i = 0; i < lap.length; i++) { ctx.fillStyle = lap[i][1]; ctx.fillRect(-20, lap[i][0], SW + 40, 800); }
      ctx.strokeStyle = 'rgba(0,0,0,.08)'; ctx.lineWidth = 3; for (let i = 0; i < 18; i++) { const x = (i * 97) % 1280, y = 350 + (i * 53) % 300; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 30, y + 6); ctx.stroke(); }
      rumah(460, 300, 0.9); rumah(820, 300, 0.9, '#e9c46a'); pohon(560, 300); pohon(740, 300, 0.9); rumah(1060, 300, 0.8, '#a8dadc'); pohon(220, 300, 1.1);
      const fx = 640, fy = 540, puls = (waktu * 1.2) % 1;
      for (let k = 0; k < 2; k++) { const u = (puls + k * 0.5) % 1; ctx.strokeStyle = `rgba(230,57,70,${1 - u})`; ctx.lineWidth = 5; bulat(fx, fy, 20 + u * 70); ctx.stroke(); }
      diSkala(fx, fy, pop(lt, 0.8), () => bintangLedak(0, 0, 26, W.merah));
      const p = klem((lt - 4.9) / 0.8);
      if (p > 0) { ctx.strokeStyle = W.navy; ctx.lineWidth = 4; ctx.setLineDash([12, 10]); ctx.beginPath(); ctx.moveTo(fx, fy - 26); ctx.lineTo(fx, lerp(fy - 26, 300, p)); ctx.stroke(); ctx.setLineDash([]); }
      diSkala(fx, 300, pop(lt, 5.6), () => { ctx.fillStyle = W.merah; ctx.beginPath(); ctx.moveTo(0, 0); ctx.bezierCurveTo(-30, -40, -24, -70, 0, -70); ctx.bezierCurveTo(24, -70, 30, -40, 0, 0); ctx.fill(); ctx.fillStyle = '#fff'; bulat(0, -48, 10); ctx.fill(); });
      garisPenunjuk(lt, 1.2, fx + 30, fy, 860, fy);
      label(lt, 1.4, 1000, fy, 'Hiposentrum', { ukuran: 26, bg: W.merah, warna: '#fff' });
      label(lt, 2.2, 1000, fy + 52, 'titik asal di dalam Bumi', { ukuran: 18 });
      garisPenunjuk(lt, 6.0, fx - 30, 250, 420, 190);
      label(lt, 6.2, 300, 190, 'Episentrum', { ukuran: 26, bg: W.navy, warna: '#fff' });
      label(lt, 6.8, 300, 240, 'tepat di atasnya, di permukaan', { ukuran: 18 });
    }
  },
  // ---------------------------------------------------------------- 6. GELOMBANG
  {
    nama: 'Gelombang', dur: 14, musik: () => 'penasaran',
    teks: [[0.4, 4.0, 'Getaran gempa merambat sebagai gelombang seismik.'], [4.4, 8.2, 'Gelombang P datang duluan: lebih cepat, tapi lebih lemah.'], [8.4, 13.8, 'Lalu gelombang S menyusul: lebih lambat, tapi guncangannya lebih kuat.']],
    acara: [[4.4, sfx.pop], [8.4, () => { sfx.pop(); sfx.gemuruh(2, 0.3); }], [1, sfx.pop]],
    gambar(lt) {
      latarTerang();
      ctx.fillStyle = '#7cc576'; ctx.fillRect(-20, 260, SW + 40, 18); ctx.fillStyle = '#a07855'; ctx.fillRect(-20, 276, SW + 40, 500);
      const fx = 220, fy = 580, sx = 1000, sy = 262;
      const vP = 245, vS = 113, rP = Math.max(0, (lt - 1) * vP), rS = Math.max(0, (lt - 1) * vS);
      const tibaP = lt > 4.4, tibaS = lt > 8.4;
      goncang = tibaS ? klem(1 - (lt - 8.4) / 4) * 0.5 : 0;
      ctx.save(); ctx.beginPath(); ctx.rect(-20, 276, SW + 40, 600); ctx.clip();
      for (const [r, w, lebar] of [[rP, W.biru, 6], [rS, W.merah, 10]]) {
        for (let k = 0; k < 3; k++) { const rr = r - k * 26; if (rr > 0) { ctx.strokeStyle = w; ctx.globalAlpha = 0.9 - k * 0.28; ctx.lineWidth = lebar - k * 2; bulat(fx, fy, rr); ctx.stroke(); } }
      }
      ctx.globalAlpha = 1; ctx.restore();
      diSkala(fx, fy, pop(lt, 0.2), () => bintangLedak(0, 0, 24, W.merah));
      // stasiun
      ctx.save(); ctx.translate(sx + (tibaP ? Math.sin(waktu * 60) * (tibaS ? 5 : 1.5) * klem(1 - (lt - (tibaS ? 8.4 : 4.4)) / 4) : 0), sy);
      ctx.fillStyle = '#f1faee'; ctx.fillRect(-50, -70, 100, 70); ctx.fillStyle = W.navy; ctx.beginPath(); ctx.moveTo(-60, -66); ctx.lineTo(0, -104); ctx.lineTo(60, -66); ctx.fill();
      ctx.fillStyle = '#bde0fe'; ctx.fillRect(-36, -52, 26, 22); ctx.fillRect(10, -52, 26, 22);
      ctx.strokeStyle = '#555'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(30, -84); ctx.lineTo(30, -130); ctx.stroke(); ctx.fillStyle = W.merah; bulat(30, -132, 5); ctx.fill();
      ctx.restore();
      label(lt, 1.2, sx + 150, 225, 'Stasiun seismograf', { ukuran: 18 });
      // seismogram
      const px = 640, py = 40, pw = 600, ph = 110;
      kartu(px, py, pw, ph, '#fff', 14);
      ctx.strokeStyle = '#e8edf5'; ctx.lineWidth = 1; for (let x = px + 20; x < px + pw; x += 30) { ctx.beginPath(); ctx.moveTo(x, py + 10); ctx.lineTo(x, py + ph - 10); ctx.stroke(); }
      ctx.strokeStyle = W.teks; ctx.lineWidth = 2.5; ctx.beginPath();
      const tAkhir = Math.min(lt, 14);
      for (let t = 0; t <= tAkhir; t += 0.02) {
        let amp = 1.2 * Math.sin(t * 40);
        if (t > 4.4) amp += 9 * Math.sin(t * 55) * Math.exp(-(t - 4.4) * 0.4);
        if (t > 8.4) amp += 38 * Math.sin(t * 30) * Math.exp(-(t - 8.4) * 0.5);
        const x = px + 20 + t / 14 * (pw - 40), y = py + ph / 2 + amp;
        t ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }
      ctx.stroke();
      if (tibaP) label(lt, 4.4, px + 20 + 4.4 / 14 * (pw - 40), py + ph + 26, 'P', { ukuran: 18, bg: W.biru, warna: '#fff' });
      if (tibaS) label(lt, 8.4, px + 20 + 8.4 / 14 * (pw - 40), py + ph + 26, 'S', { ukuran: 18, bg: W.merah, warna: '#fff' });
      label(lt, 4.6, 330, 190, 'Gelombang P · cepat', { ukuran: 22, bg: W.biru, warna: '#fff' });
      label(lt, 8.6, 330, 236, 'Gelombang S · lebih kuat', { ukuran: 22, bg: W.merah, warna: '#fff' });
    }
  },
  // ---------------------------------------------------------------- 7. MAGNITUDO
  {
    nama: 'Magnitudo', dur: 11, musik: () => 'penasaran',
    teks: [[0.4, 3.6, 'Kekuatan gempa diukur dengan magnitudo.'], [4.0, 10.6, 'Naik satu angka saja, energinya kira-kira tiga puluh dua kali lipat!']],
    acara: [[1, sfx.pop], [3.2, sfx.pop], [5.6, sfx.pop], [4.2, sfx.wus], [6.4, sfx.wus]],
    gambar(lt) {
      goncang = 0;
      latarTerang('#fff3e0', '#ffe0b2');
      label(lt, 0.3, 640, 70, 'Magnitudo & energi', { ukuran: 30, bg: W.navy, warna: '#fff' });
      const kolom = [[250, 1, 'M 5', '1×'], [640, 3.2, 'M 6', '32×'], [1030, 5.4, 'M 7', '1.024×']];
      for (const [x, t0, m, kali] of kolom) {
        diSkala(x, 150, pop(lt, t0), () => { kartu(-80, -36, 160, 72, W.putih, 36); teks(m, 0, 2, 38, W.oranye); });
        label(lt, t0 + 1, x, 590, kali + ' energi', { ukuran: 24, bg: W.kuning });
      }
      diSkala(250, 370, pop(lt, 1.2), () => { ctx.fillStyle = W.oranye; bulat(0, 0, 16); ctx.fill(); });
      for (let i = 0; i < 32; i++) { const cx = 640 - 3.5 * 28 + (i % 8) * 28, cy = 370 - 1.5 * 28 + Math.floor(i / 8) * 28; diSkala(cx, cy, pop(lt, 3.4 + i * 0.03, 0.3), () => { ctx.fillStyle = W.oranye; bulat(0, 0, 11); ctx.fill(); }); }
      const n = Math.floor(klem((lt - 5.6) / 1.6) * 1024);
      ctx.fillStyle = W.oranye;
      for (let i = 0; i < n; i++) { const cx = 1030 - 15.5 * 9 + (i % 32) * 9, cy = 370 - 15.5 * 9 + Math.floor(i / 32) * 9; bulat(cx, cy, 3.6); ctx.fill(); }
      panah(360, 370, 500, 370, W.navy, 8, klem((lt - 4.2) / 0.5));
      panah(780, 370, 860, 370, W.navy, 8, klem((lt - 6.4) / 0.5));
      label(lt, 4.3, 430, 330, '×32', { ukuran: 22 });
      label(lt, 6.5, 820, 330, '×32', { ukuran: 22 });
    }
  },
  // ---------------------------------------------------------------- 8. TSUNAMI
  {
    nama: 'Tsunami', dur: 10, musik: () => 'tegang',
    teks: [[0.4, 4.6, 'Kalau gempanya kuat dan terjadi di bawah laut, dasar laut bisa terangkat…'], [5.0, 9.6, '…dan mendorong air laut menjadi gelombang tsunami.']],
    acara: [[1, () => { sfx.tek(); sfx.gemuruh(1.5, 0.35); }], [2.4, sfx.ombak], [5.4, sfx.pop], [1.4, sfx.pop]],
    gambar(lt) {
      goncang = lt > 1 && lt < 2 ? 0.5 : 0;
      latarTerang('#e0f4ff', '#bfe6f2');
      const angkat = kfh(lt, [[1, 0], [1.4, 26]]);
      const dasar = x => x < 300 ? 600 : x < 460 ? 600 - angkat * Math.sin((x - 300) / 160 * Math.PI) : x < 900 ? 600 : 600 - (x - 900) * 0.9;
      const xc = kf(lt, [[1.4, 380], [8.6, 1000]], halus), A = kf(lt, [[1.4, 18], [6, 40], [8.6, 110]]), lebar = kf(lt, [[1.4, 130], [8.6, 90]]);
      const permukaan = x => 300 - (lt > 1.2 ? A * Math.exp(-Math.pow((x - xc) / lebar, 2)) : 0) + Math.sin(x * 0.03 + waktu * 2) * 3;
      // air
      ctx.fillStyle = '#3a9bd9'; ctx.beginPath(); ctx.moveTo(-20, 720);
      for (let x = -20; x <= 1300; x += 10) ctx.lineTo(x, Math.min(permukaan(x), dasar(x)));
      ctx.lineTo(1300, 720); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,.7)'; ctx.lineWidth = 4; ctx.beginPath();
      for (let x = -20; x <= 1300; x += 10) { const y = Math.min(permukaan(x), dasar(x)); x === -20 ? ctx.moveTo(x, y) : ctx.lineTo(x, y); }
      ctx.stroke();
      // dasar laut & pantai
      ctx.fillStyle = '#c9a26b'; ctx.beginPath(); ctx.moveTo(-20, 720); for (let x = -20; x <= 1300; x += 10) ctx.lineTo(x, dasar(x)); ctx.lineTo(1300, 720); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#e9d8a6'; ctx.beginPath(); ctx.moveTo(1180, 300); ctx.lineTo(SW + 20, 300); ctx.lineTo(SW + 20, 720); ctx.lineTo(1180, 720); ctx.fill();
      ctx.fillStyle = '#7cc576'; ctx.fillRect(1180, 290, 120, 12);
      rumah(1215, 292, 0.7); pohon(1260, 292, 0.8);
      // pohon kelapa
      ctx.strokeStyle = '#8d5a3b'; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(1120, 360); ctx.quadraticCurveTo(1130, 300, 1110, 250); ctx.stroke();
      ctx.fillStyle = '#4caf6d'; for (let i = 0; i < 5; i++) { ctx.save(); ctx.translate(1110, 250); ctx.rotate(-2.6 + i * 0.9 + Math.sin(waktu * 2 + i) * 0.05); elips(24, 0, 28, 7); ctx.fill(); ctx.restore(); }
      if (lt > 1) diSkala(380, 590, pop(lt, 1) * klem(1 - (lt - 3) / 0.5 + 1), () => bintangLedak(0, 0, 22, W.kuning));
      panah(380, 560, 380, 480, W.kuning, 9, klem((lt - 1.3) / 0.4) * klem(1 - (lt - 4.5)));
      label(lt, 1.4, 380, 450, 'Dasar laut terangkat', { ukuran: 20 });
      if (lt > 5.4) label(lt, 5.4, xc, permukaan(xc) - 50, 'Tsunami!', { ukuran: 30, bg: W.merah, warna: '#fff' });
    }
  },
  // ---------------------------------------------------------------- 9. SAAT GEMPA
  {
    nama: 'Saat Gempa', dur: 16.5, musik: () => 'ceria',
    teks: [[0.4, 3.2, 'Terus, kalau gempa datang, kita harus apa?'], [3.4, 8.2, 'Merunduk, berlindung di bawah meja yang kuat, dan berpegangan.'], [8.4, 11.2, 'Jauhi kaca dan lemari yang bisa roboh.'], [11.5, 16.2, 'Kalau kamu di pantai dan gempanya kuat, segera lari ke tempat tinggi!']],
    acara: [[3.6, sfx.pop], [5.0, sfx.pop], [6.6, sfx.pop], [8.6, sfx.pop], [11.4, sfx.wus]],
    gambar(lt) {
      goncang = 0;
      latarTerang('#e8f7ee', '#cdebd9');
      const geser = kfh(lt, [[11.2, 0], [11.9, -1400]]);
      ctx.save(); ctx.translate(geser, 0);
      if (lt < 3.6) kiki(640, 600, 0.9, { ekspresi: 'mikir', tangan: 'kepala' });
      const kartuLangkah = [[240, 3.6, '1', 'Merunduk'], [640, 5.0, '2', 'Berlindung'], [1040, 6.6, '3', 'Berpegangan']];
      for (const [x, t0, n, judul] of kartuLangkah) {
        diSkala(x, 300, pop(lt, t0, 0.5), () => {
          kartu(-170, -210, 340, 400, W.putih, 26);
          ctx.fillStyle = W.oranye; bulat(-128, -168, 24); ctx.fill(); teks(n, -128, -166, 28, '#fff');
          teks(judul, 20, -166, 34, W.teks);
          ctx.save(); ctx.beginPath(); rrect(-150, -130, 300, 300, 18); ctx.clip();
          ctx.fillStyle = '#eef6fb'; ctx.fillRect(-150, -130, 300, 300);
          ctx.fillStyle = '#d9c4a5'; ctx.fillRect(-150, 120, 300, 60);
          if (n === '1') kiki(0, 130, 0.95, { jongkok: true, tangan: 'lindungi', ekspresi: 'mikir', keringat: false });
          if (n === '2') { meja(0, 132, 230); kiki(0, 132, 0.8, { jongkok: true, tangan: 'lindungi', ekspresi: 'mikir' }); }
          if (n === '3') { meja(0, 132, 230); kiki(-10, 132, 0.8, { jongkok: true, tangan: 'pegang', ekspresi: 'senyum' }); }
          ctx.restore();
        });
      }
      // jauhi kaca & lemari
      diSkala(640, 610, pop(lt, 8.6), () => {
        kartu(-250, -40, 500, 80, W.krem, 40);
        ctx.fillStyle = '#9fd9f0'; ctx.fillRect(-220, -24, 44, 48); ctx.strokeStyle = W.merah; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(-226, -28); ctx.lineTo(-170, 28); ctx.moveTo(-170, -28); ctx.lineTo(-226, 28); ctx.stroke();
        teks('Jauhi kaca & lemari!', 30, 2, 30, W.teks);
      });
      ctx.restore();
      // pantai → ke tempat tinggi
      const g2 = kfh(lt, [[11.2, 1400], [11.9, 0]]);
      if (g2 < 1390) {
        ctx.save(); ctx.translate(g2, 0);
        ctx.fillStyle = '#3a9bd9'; ctx.beginPath(); ctx.moveTo(-20, 560); for (let x = -20; x <= 420; x += 10) ctx.lineTo(x, 540 + Math.sin(x * 0.05 + waktu * 3) * 8); ctx.lineTo(420, 720); ctx.lineTo(-20, 720); ctx.fill();
        ctx.fillStyle = '#e9d8a6'; ctx.fillRect(380, 560, 300, 200);
        ctx.fillStyle = '#7cc576'; ctx.beginPath(); ctx.moveTo(600, 580); ctx.quadraticCurveTo(900, 560, 1000, 300); ctx.lineTo(1300, 250); ctx.lineTo(1300, 720); ctx.lineTo(600, 720); ctx.fill();
        rumah(1150, 262, 1);
        const u = klem((lt - 12.2) / 3.6), kx = lerp(560, 1060, u), ky = u < 0.5 ? lerp(600, 480, u * 2) : lerp(480, 285, (u - 0.5) * 2);
        kiki(kx, ky, 0.75, { jalan: u < 1, tangan: 'lari', ekspresi: u < 1 ? 'kaget' : 'senang', keringat: false });
        panah(700, 520, 960, 330, W.oranye, 10, klem((lt - 12) / 0.6));
        label(lt, 12.6, 880, 170, 'Segera ke tempat tinggi!', { ukuran: 30, bg: W.merah, warna: '#fff' });
        label(lt, 12, 220, 470, 'Di pantai + gempa kuat', { ukuran: 20 });
        ctx.restore();
      }
    }
  },
  // ---------------------------------------------------------------- 10. PENUTUP
  {
    nama: 'Penutup', dur: 10, musik: () => 'ceria',
    teks: [[0.4, 6.0, 'Jadi, gempa bumi terjadi karena lempeng Bumi bergerak dan melepas energi secara tiba-tiba.'], [6.3, 9.8, 'Tetap tenang, dan selalu siaga ya!']],
    acara: [[0.8, sfx.pop], [2.3, sfx.pop], [3.8, sfx.pop], [6.4, () => sfx.ding(84)]],
    gambar(lt) {
      goncang = 0;
      langitMalam('#1d3557', '#2a6f97');
      bumi(990, 360, 190, waktu * 0.02);
      kiki(360, 640, 1.2, { ekspresi: 'senang', tangan: lt > 6.2 ? 'lambai' : 'tunjuk' });
      const langkah = [[0.8, 'Lempeng bergerak'], [2.3, 'Energi menumpuk'], [3.8, 'Lepas tiba-tiba → Bumi bergetar']];
      langkah.forEach(([t0, s], i) => { label(lt, t0, 620, 120 + i * 90, s, { ukuran: 26, bg: i === 2 ? W.oranye : W.putih, warna: i === 2 ? '#fff' : W.teks }); if (i < 2) panah(620, 150 + i * 90, 620, 184 + i * 90, W.kuning, 6, klem((lt - t0 - 0.6) / 0.3)); });
      const k = pop(lt, 6.3, 0.5);
      diSkala(990, 610, k, () => { kartu(-230, -42, 460, 84, W.kuning, 42); teks('Tetap tenang & siaga! 💪', 0, 2, 32, W.teks); });
    }
  },
];
let AWAL = [], TOTAL = 0;
for (const a of ADEGAN) { AWAL.push(TOTAL); TOTAL += a.dur; }
const indeksAdegan = t => { for (let i = ADEGAN.length - 1; i >= 0; i--) if (t >= AWAL[i]) return i; return 0; };

// =====================================================================
//  PEMUTAR
// =====================================================================
let T = 0, main = false, idx = -1, ltSebelum = 0, selesai = false, pertama = true;
function bungkus(s, maks) {
  const kata = s.split(' '), baris = []; let b = '';
  for (const k of kata) { const c = b ? b + ' ' + k : k; if (ctx.measureText(c).width > maks && b) { baris.push(b); b = k; } else b = c; }
  if (b) baris.push(b); return baris;
}
function subtitle(a, lt, x, y, ukuran, maks, kotak) {
  for (const [t0, t1, s] of a.teks || []) {
    const al = muncul(lt, t0, t1, 0.25, 0.25); if (al <= 0) continue;
    ctx.save(); ctx.globalAlpha = al;
    ctx.font = `800 ${ukuran}px Nunito, "Baloo 2", sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    const baris = bungkus(s, maks), lh = ukuran * 1.3;
    if (kotak) {
      const w = Math.max(...baris.map(b => ctx.measureText(b).width)) + ukuran * 1.2, h = baris.length * lh + ukuran * 0.6;
      ctx.fillStyle = 'rgba(16,24,44,.78)'; rrect(x - w / 2, y - h / 2, w, h, 14); ctx.fill();
      ctx.fillStyle = '#fff'; baris.forEach((b, i) => ctx.fillText(b, x, y + (i - (baris.length - 1) / 2) * lh + 1));
    } else {
      ctx.lineJoin = 'round'; ctx.lineWidth = ukuran * 0.22; ctx.strokeStyle = 'rgba(0,0,0,.85)';
      baris.forEach((b, i) => { const yy = y + (i - (baris.length - 1) / 2) * lh; ctx.strokeText(b, x, yy); ctx.fillStyle = '#fff'; ctx.fillText(b, x, yy); });
    }
    ctx.restore();
  }
}
function gambarAdegan(a, lt) {
  // transisi: lingkaran membuka di awal adegan
  ctx.save();
  const p = klem(lt / 0.55);
  if (p < 1 && idx > 0) { ctx.beginPath(); ctx.arc(SW / 2, SH / 2, halus(p) * 760, 0, 6.2832); ctx.clip(); }
  if (goncang > 0.01 && !kurangGerak) ctx.translate(Math.sin(waktu * 70) * 9 * goncang, Math.cos(waktu * 57) * 6 * goncang);
  a.gambar(lt);
  ctx.restore();
}
let terakhir = performance.now();
function bingkai(now) {
  const dt = Math.min((now - terakhir) / 1000, 0.05); terakhir = now;
  if (main) { T += dt; if (T >= TOTAL) { T = TOTAL - 0.001; setMain(false); selesai = true; tombolMulai.textContent = '↻ Tonton lagi'; layarMulai.hidden = false; } }
  const i = indeksAdegan(T);
  if (i !== idx) { idx = i; ltSebelum = T - AWAL[i] - 0.0001; segEls.forEach((s, k) => s.classList.toggle('aktif', k === i)); }
  const a = ADEGAN[i], lt = T - AWAL[i];
  if (main) {
    const lewat = t => ltSebelum < t && t <= lt;
    for (const [t, fn] of a.acara || []) if (lewat(t)) fn();
    for (const [t0, , s] of a.teks || []) if (lewat(t0)) ucap(s);
    waktu += dt;
  }
  ltSebelum = lt;
  Pemutar.ingin = a.musik ? a.musik(lt) : null;
  if (main) detakMusik();
  if (Suara.musik) Suara.musik.gain.setTargetAtTime(Dub.aktif.size ? 0.35 : 1, Suara.ctx.currentTime, 0.12);
  dasar(); ctx.fillStyle = '#0b1426'; ctx.fillRect(0, 0, VW, VH);
  if (FORMAT === '169') {
    gambarAdegan(a, lt);
    subtitle(a, lt, SW / 2, SH - 48, 26, SW - 260, true);
  } else {
    // 9:16: video di tengah, judul di atas, subtitle besar di bawah
    const g = ctx.createLinearGradient(0, 0, 0, VH); g.addColorStop(0, '#1d3557'); g.addColorStop(1, '#0b1426');
    ctx.fillStyle = g; ctx.fillRect(0, 0, VW, VH);
    ctx.save(); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = '#ff7f3f'; ctx.font = '800 64px "Baloo 2", sans-serif'; ctx.fillText('GEMPA BUMI', VW / 2, 220);
    ctx.fillStyle = '#fff'; ctx.font = '800 44px "Baloo 2", sans-serif'; ctx.fillText('itu apa sih? 🌏', VW / 2, 282);
    ctx.fillStyle = 'rgba(255,255,255,.14)'; rrect(VW / 2 - 130, 330, 260, 40, 20); ctx.fill();
    ctx.fillStyle = '#ffd23f'; ctx.font = '700 22px "Baloo 2", sans-serif'; ctx.fillText(`${i + 1}/${ADEGAN.length} · ${a.nama}`, VW / 2, 351);
    ctx.restore();
    const sk = (VW - 24) / SW, oy = 400;
    ctx.save(); ctx.translate(12, oy); ctx.scale(sk, sk);
    rrect(0, 0, SW, SH, 36); ctx.clip();
    gambarAdegan(a, lt);
    ctx.restore();
    subtitle(a, lt, VW / 2, 930, 36, VW - 80, false);
  }
  segEls.forEach((s, k) => { s.firstChild.style.width = (klem((T - AWAL[k]) / ADEGAN[k].dur) * 100) + '%'; });
  requestAnimationFrame(bingkai);
}

// =====================================================================
//  KONTROL
// =====================================================================
const KONFIG_AWAL = { format: '169', kontrol: true };
const layarMulai = document.getElementById('layarMulai');
const tombolMulai = document.getElementById('tombolMulai');
const bMain = document.getElementById('bMain');
const bSuara = document.getElementById('bSuara');
const bDub = document.getElementById('bDub');
const linimasa = document.getElementById('linimasa');
const segEls = ADEGAN.map((a, k) => {
  const b = document.createElement('button'); b.className = 'seg'; b.style.flexGrow = a.dur; b.title = a.nama;
  b.setAttribute('aria-label', `Lompat ke ${a.nama}`);
  b.innerHTML = '<div class="isi"></div><span></span>'; b.lastChild.textContent = a.nama;
  b.addEventListener('click', () => lompatKe(k)); linimasa.appendChild(b); return b;
});
function setMain(v) {
  main = v; bMain.textContent = v ? '❚❚' : '▶'; bMain.setAttribute('aria-label', v ? 'Jeda' : 'Putar');
  if (Suara.ctx) { if (v) Suara.ctx.resume(); else Suara.ctx.suspend(); }
}
async function mulai() {
  siapkanAudio();
  if (Dub.ada && !Dub.dimuat) { tombolMulai.textContent = 'Memuat suara…'; tombolMulai.disabled = true; await muatDubbing(); tombolMulai.disabled = false; tombolMulai.textContent = '▶ Tonton'; }
  if (pertama || selesai || T >= TOTAL - 0.01) { diamkan(); T = 0; idx = -1; selesai = false; pertama = false; waktu = 0; }
  layarMulai.hidden = true; setMain(true);
}
function lompatKe(k) {
  k = Math.max(0, Math.min(ADEGAN.length - 1, k));
  diamkan(); T = AWAL[k] + 0.001; idx = -1; selesai = false; pertama = false;
  if (!main) { siapkanAudio(); muatDubbing(); layarMulai.hidden = true; setMain(true); }
}
function gantiFormat(f) {
  FORMAT = f; if (f === '916') { VW = 720; VH = 1280; } else { VW = 1280; VH = 720; }
  document.body.classList.toggle('v916', f === '916');
  document.querySelectorAll('[data-format]').forEach(b => { b.classList.toggle('on', b.dataset.format === f); b.setAttribute('aria-pressed', String(b.dataset.format === f)); });
  ukur();
}
tombolMulai.addEventListener('click', mulai);
bMain.addEventListener('click', () => { if (!main) mulai(); else setMain(false); });
bSuara.addEventListener('click', () => {
  Suara.nyala = !Suara.nyala; bSuara.textContent = Suara.nyala ? '🔊' : '🔇';
  bSuara.setAttribute('aria-label', Suara.nyala ? 'Matikan suara' : 'Nyalakan suara');
  if (Suara.master) Suara.master.gain.setTargetAtTime(Suara.nyala ? 0.8 : 0, Suara.ctx.currentTime, 0.05);
  if (!Suara.nyala) diamkan();
});
bDub.addEventListener('click', () => { Dub.nyala = !Dub.nyala; bDub.classList.toggle('mati', !Dub.nyala); bDub.setAttribute('aria-label', Dub.nyala ? 'Matikan suara narator' : 'Nyalakan suara narator'); if (!Dub.nyala) diamkan(); });
if (!Dub.ada) bDub.hidden = true;
document.querySelectorAll('[data-format]').forEach(b => b.addEventListener('click', () => gantiFormat(b.dataset.format)));
addEventListener('keydown', e => {
  if (e.target.tagName === 'BUTTON' && e.key === ' ') return;
  if (e.key === ' ') { e.preventDefault(); if (main) setMain(false); else mulai(); }
  else if (e.key === 'ArrowRight') lompatKe(indeksAdegan(T) + 1);
  else if (e.key === 'ArrowLeft') lompatKe(T - AWAL[indeksAdegan(T)] > 2 ? indeksAdegan(T) : indeksAdegan(T) - 1);
});
new ResizeObserver(ukur).observe(kanvas);
if (!KONFIG_AWAL.kontrol) document.getElementById('alat').hidden = true;
gantiFormat(KONFIG_AWAL.format);
T = 6.2; waktu = 6.2; // poster: kartu judul terlihat
window.__video = { lompat: t => { T = t; idx = -1; }, format: gantiFormat, total: TOTAL };
requestAnimationFrame(bingkai);
})();
</script>
</body>
</html>
'''

html_siap = HTML_ANIMASI.replace(
    "const KONFIG_AWAL = { format: '169', kontrol: true };",
    f"const KONFIG_AWAL = {{ format: '{format_video}', kontrol: false }};",
)
if pakai_narator:
    ada = file_tersedia()
    if ada:
        html_siap = html_siap.replace("const SUARA_DUBBING = {};", "const SUARA_DUBBING = " + json.dumps(baca_narasi(ada)) + ";")

# Ubah angka height kalau animasinya terpotong atau ada ruang kosong di layarmu.
tinggi = 1000 if format_video == "916" else 800
components.html(html_siap, height=tinggi, scrolling=False)
