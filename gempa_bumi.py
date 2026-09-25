"""
Gempa Bumi Itu Apa Sih? - video penjelasan animasi (Streamlit)

Jalankan di laptop:
  pip install -r requirements.txt
  streamlit run app.py

SUARA NARATOR (ekspresif, intonasi naik-turun)
  - GEMINI_API_KEY      -> suara Google Gemini TTS  (GRATIS, ambil key di aistudio.google.com)
  - ELEVENLABS_API_KEY  -> suara ElevenLabs          (kalau diisi, dipakai lebih dulu)
  Taruh key di file .streamlit/secrets.toml (lihat README.md),
  atau di menu Secrets saat deploy ke Streamlit Community Cloud.

  Suara dibuat otomatis saat pertama kali dibuka, lalu disimpan di folder
  "suara_narator". Upload folder itu ke GitHub juga supaya versi online
  langsung bersuara tanpa membuat ulang (hemat kuota gratis).

Ukuran: YouTube 16:9 atau TikTok 9:16 (pilih di atas video).
"""

import base64
import hashlib
import io
import json
import os
import zipfile
from array import array
import re
import time
import wave
from pathlib import Path

import requests
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
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
#  SUARA NARATOR
# ---------------------------------------------------------------------------
FOLDER_SUARA = Path(__file__).parent / "suara_narator"

# Gemini TTS (gratis). Nama suara lain yang bisa dicoba: "Puck" (ceria), "Achird" (ramah),
# "Sadaltager" (berwawasan), "Kore" (tegas, perempuan), "Aoede" (santai, perempuan), "Charon" (informatif).
GEMINI_MODEL = "gemini-3.8-flash-tts"
GEMINI_MODEL_CADANGAN = "gemini-2.5-flash-preview-tts"
GEMINI_SUARA = "Puck"
ISI_PER_PERMINTAAN = 6   # berapa kalimat dibacakan dalam satu permintaan (hemat kuota harian)
GAYA_DASAR = ("Indonesian narrator of a fun educational YouTube animation, speaking natural Indonesian "
              "with lively, expressive intonation that rises and falls, clear pacing, never monotone. Mood: ")

# ElevenLabs (opsional, dipakai kalau ELEVENLABS_API_KEY diisi)
ELEVENLABS_VOICE_DEFAULT = "JBFqnCBsd6RMkjVDRZzb"
ELEVENLABS_MODEL = "eleven_multilingual_v2"
ELEVENLABS_PENGATURAN = {"stability": 0.4, "similarity_boost": 0.8, "style": 0.45, "use_speaker_boost": True}

# Semua kalimat narasi di video: (teks, suasana). Teks harus sama persis dengan di animasi.
NARASI = [
    ("Pukul tiga pagi. Kota sedang tertidur lelap…", "low, slow and ominous, almost whispering, like the opening of a horror documentary"),
    ("Lalu, tanpa peringatan…", "hushed and suspenseful, trailing off"),
    ("Apa yang sebenarnya terjadi di bawah kaki kita?", "grave and dramatic, a heavy rhetorical question"),
    ("Untuk menjawabnya, kita harus menyelam jauh ke dalam Bumi.", "curious and adventurous, inviting the viewer on a journey"),
    ("Paling luar ada kerak: lapisan tipis tempat kita berdiri.", "clear and explanatory"),
    ("Di bawahnya, mantel yang panas dan perlahan mengalir, lalu inti Bumi yang membara.", "impressed and vivid, emphasize 'membara'"),
    ("Dan kunci dari gempa… ada di kerak ini.", "mysterious, like revealing a key clue"),
    ("Kerak Bumi ternyata retak-retak menjadi potongan raksasa: lempeng tektonik.", "surprised discovery, emphasize 'lempeng tektonik'"),
    ("Lempeng-lempeng ini terus bergerak, beberapa sentimeter setiap tahun.", "calm and informative"),
    ("Pelan sekali… kira-kira secepat kuku kita tumbuh.", "playful and amused"),
    ("Indonesia berada di tempat yang istimewa, sekaligus berbahaya.", "serious with a hint of danger"),
    ("Tiga lempeng besar bertemu di sini: Eurasia, Indo-Australia, dan Pasifik.", "energetic, listing the three names clearly"),
    ("Itulah kenapa negeri kita termasuk yang paling sering diguncang gempa.", "serious and concerned, emphasize 'paling sering'"),
    ("Di perbatasan lempeng, dua raksasa saling dorong dan saling mengunci.", "tense and dramatic"),
    ("Tekanan menumpuk sedikit demi sedikit, bertahun-tahun, seperti penggaris yang dibengkokkan…", "slowly building tension, stretching the words"),
    ("…sampai akhirnya patah, dan lepas tiba-tiba!", "explosive and sudden, strong emphasis on 'tiba-tiba'"),
    ("Energi raksasa itu menyebar ke segala arah sebagai getaran. Itulah gempa bumi.", "powerful and awe-struck, clear conclusion"),
    ("Titik asal gempa di dalam Bumi disebut hiposentrum.", "clear and informative"),
    ("Sedangkan titik di permukaan, tepat di atasnya, disebut episentrum.", "clear and informative, emphasize 'episentrum'"),
    ("Dari sana, getaran merambat sebagai gelombang seismik.", "informative and energetic"),
    ("Gelombang P datang lebih dulu: cepat, tapi lemah.", "quick and light, emphasize 'lebih dulu'"),
    ("Disusul gelombang S: lebih lambat, tapi guncangannya jauh lebih kuat.", "heavy and intense, emphasize 'jauh lebih kuat'"),
    ("Kekuatan gempa diukur dengan magnitudo.", "clear and confident"),
    ("Naik satu angka saja, energinya kira-kira tiga puluh dua kali lipat!", "amazed and emphatic, emphasize 'tiga puluh dua kali lipat'"),
    ("Jika gempa kuat terjadi di bawah laut, dasar laut bisa terangkat…", "serious and tense"),
    ("…mendorong kolom air raksasa menjadi gelombang tsunami.", "urgent and grave, dramatic"),
    ("Lalu, apa yang harus kita lakukan saat gempa datang?", "friendly and caring question"),
    ("Merunduk, berlindung di bawah meja yang kuat, dan berpegangan.", "instructive, calm and reassuring, clear pauses between the three steps"),
    ("Jauhi kaca dan lemari yang bisa roboh.", "firm friendly warning"),
    ("Dan jika kamu di pantai setelah gempa kuat, segera lari ke tempat tinggi!", "urgent but caring, emphasize 'tempat tinggi'"),
    ("Jadi, gempa terjadi karena lempeng Bumi bergerak, menumpuk energi, lalu melepaskannya tiba-tiba.", "warm, concluding summary"),
    ("Kita tidak bisa mencegahnya, tapi kita bisa selalu siap. Tetap waspada!", "inspiring and encouraging, strong finish on 'Tetap waspada'"),
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
GEMINI_KEY = ambil_rahasia("GEMINI_API_KEY")
GEMINI_SUARA = ambil_rahasia("GEMINI_VOICE") or GEMINI_SUARA
PENYEDIA = "elevenlabs" if ELEVENLABS_KEY else "gemini" if GEMINI_KEY else None


class KuotaHabis(Exception):
    pass


def identitas(teks, gaya):
    if PENYEDIA == "elevenlabs":
        data = ["elevenlabs", ELEVENLABS_VOICE, ELEVENLABS_MODEL, ELEVENLABS_PENGATURAN, teks]
    else:
        data = ["gemini", GEMINI_SUARA, GAYA_DASAR + gaya, teks]  # sama seperti versi sebelumnya: 6 rekaman yang sudah jadi tetap dipakai
    return hashlib.md5(json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def file_suara(teks, gaya):
    ekstensi = "mp3" if PENYEDIA == "elevenlabs" else "wav"
    return FOLDER_SUARA / f"{PENYEDIA}_{identitas(teks, gaya)}.{ekstensi}"


# daftar.json mencatat file mana untuk kalimat mana, supaya rekaman yang sudah di-upload
# ke GitHub tetap dipakai walaupun server tidak punya API key.
DAFTAR = FOLDER_SUARA / "daftar.json"


def baca_daftar():
    try:
        return json.loads(DAFTAR.read_text(encoding="utf-8"))
    except Exception:
        return {}


def catat(teks, gaya):
    daftar = baca_daftar()
    lama = daftar.get(teks, {}).get("file")
    baru = file_suara(teks, gaya).name
    if lama and lama != baru:
        (FOLDER_SUARA / lama).unlink(missing_ok=True)  # buang rekaman lama yang sudah diganti
    daftar[teks] = {"file": baru, "penyedia": PENYEDIA, "id": identitas(teks, gaya)}
    DAFTAR.write_text(json.dumps(daftar, ensure_ascii=False, indent=1), encoding="utf-8")


def perlu_dibuat(teks, gaya, daftar):
    isi = daftar.get(teks)
    if not isi or not (FOLDER_SUARA / isi["file"]).exists():
        return True
    if not PENYEDIA:
        return False
    peringkat = {"microsoft": 0, "gemini": 1, "elevenlabs": 2}
    if peringkat.get(isi.get("penyedia"), 0) < peringkat[PENYEDIA]:
        return True  # naik kelas: semua kalimat dibuat ulang dengan penyedia yang lebih bagus, supaya suaranya seragam
    # suara/gaya berubah untuk penyedia yang sama -> buat ulang
    return isi.get("penyedia") == PENYEDIA and isi["id"] != identitas(teks, gaya)


def simpan_utuh(tujuan, data):
    sementara = tujuan.with_suffix(".tmp")
    sementara.write_bytes(data)
    sementara.replace(tujuan)  # baru dianggap jadi kalau file tersimpan utuh


def pcm_ke_wav(pcm, rate=24000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def cari_audio(obj):
    """Cari potongan audio base64 terakhir di dalam jawaban JSON (bentuknya bisa berbeda antar versi API)."""
    ketemu = None
    if isinstance(obj, dict):
        if obj.get("type") == "audio" and isinstance(obj.get("data"), str):
            ketemu = (obj["data"], obj.get("mime_type") or obj.get("mimeType") or "")
        if isinstance(obj.get("inlineData"), dict) and obj["inlineData"].get("data"):
            ketemu = (obj["inlineData"]["data"], obj["inlineData"].get("mimeType", ""))
        for v in obj.values():
            ketemu = cari_audio(v) or ketemu
    elif isinstance(obj, list):
        for v in obj:
            ketemu = cari_audio(v) or ketemu
    return ketemu


def jadikan_wav(b64, mime):
    data = base64.b64decode(b64)
    if data[:4] == b"RIFF":
        return data
    cocok = re.search(r"rate=(\d+)", mime or "")
    return pcm_ke_wav(data, int(cocok.group(1)) if cocok else 24000)


def minta_gemini(teks, gaya):
    """Satu permintaan ke Gemini TTS. Coba model terbaru dulu, lalu model cadangan."""
    kepala = {"x-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"}
    badan_baru = {
        "model": GEMINI_MODEL,
        "input": [{"type": "user_input", "content": [{
            "type": "text", "text": teks,
            "annotations": [{"type": "speech_metadata", "style": gaya}],
        }]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": GEMINI_SUARA}]},
    }
    r = requests.post("https://generativelanguage.googleapis.com/v1beta/interactions", headers=kepala, json=badan_baru, timeout=180)
    if r.status_code in (400, 404) and "quota" not in r.text.lower():
        teks_lama = teks.replace("<long pause>", "...")
        badan_lama = {
            "contents": [{"parts": [{"text": f"Bacakan dengan gaya: {gaya}\n\n{teks_lama}"}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": GEMINI_SUARA}}}},
        }
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_CADANGAN}:generateContent",
                          headers=kepala, json=badan_lama, timeout=180)
    return r


def minta_dengan_sabar(teks, gaya, progres, keterangan):
    """Kirim permintaan; kalau kuota per menit penuh, tunggu lalu coba lagi."""
    for _ in range(8):
        r = minta_gemini(teks, gaya)
        if r.status_code == 200:
            audio = cari_audio(r.json())
            if not audio:
                raise RuntimeError("Jawaban Gemini tidak berisi audio.")
            return jadikan_wav(*audio)
        if r.status_code == 429:
            if "PerDay" in r.text or "per day" in r.text.lower():
                raise KuotaHabis(keterangan)
            jeda = re.search(r'"retryDelay":\s*"(\d+)', r.text)
            tunggu = min(65, int(jeda.group(1)) + 2 if jeda else 20)
            progres.progress(0.0, text=f"Kuota gratis per menit penuh, menunggu {tunggu} detik… ({keterangan})")
            time.sleep(tunggu)
            continue
        raise RuntimeError(f"Gemini menolak ({r.status_code}): {r.text[:300]}")
    raise KuotaHabis(keterangan)


def belah_audio(wav_bytes, jumlah):
    """Potong satu rekaman panjang jadi `jumlah` bagian, di jeda-jeda hening yang paling panjang."""
    with wave.open(io.BytesIO(wav_bytes)) as w:
        rate, kanal = w.getframerate(), w.getnchannels()
        sampel = array("h")
        sampel.frombytes(w.readframes(w.getnframes()))
    if kanal == 2:
        sampel = sampel[::2]
    if jumlah == 1:
        return [pcm_ke_wav(sampel.tobytes(), rate)]
    jendela = max(1, int(rate * 0.02))  # potongan 20 milidetik
    puncak = [max(map(abs, sampel[i:i + jendela])) for i in range(0, len(sampel), jendela)]
    ambang = max(300, 0.05 * max(puncak))
    jeda = []  # (panjang, awal, akhir) tiap bagian hening di tengah rekaman
    i = 0
    while i < len(puncak):
        if puncak[i] < ambang:
            j = i
            while j < len(puncak) and puncak[j] < ambang:
                j += 1
            if i > 0 and j < len(puncak):
                jeda.append((j - i, i, j))
            i = j
        else:
            i += 1
    if len(jeda) < jumlah - 1:
        raise ValueError("jeda antar kalimat tidak cukup jelas")
    terpilih = sorted(sorted(jeda, reverse=True)[:jumlah - 1], key=lambda g: g[1])
    potong = [0] + [((a + b) // 2) * jendela for _, a, b in terpilih] + [len(sampel)]
    hasil, sisa = [], int(rate * 0.08)
    for awal, akhir in zip(potong, potong[1:]):
        bagian = sampel[awal:akhir]
        k = [n for n in range(0, len(bagian), jendela) if max(map(abs, bagian[n:n + jendela]), default=0) >= ambang]
        if k:
            bagian = bagian[max(0, k[0] - sisa):min(len(bagian), k[-1] + jendela + sisa)]
        hasil.append(pcm_ke_wav(bagian.tobytes(), rate))
    return hasil


def rekam_gemini(yang_kurang, progres):
    """Hemat kuota: beberapa kalimat dibacakan dalam SATU permintaan, lalu rekamannya dipotong per kalimat."""
    kelompok = [yang_kurang[i:i + ISI_PER_PERMINTAAN] for i in range(0, len(yang_kurang), ISI_PER_PERMINTAAN)]
    selesai = 0
    for grup in kelompok:
        ket = f"{selesai} dari {len(yang_kurang)} kalimat selesai"
        progres.progress(selesai / len(yang_kurang), text=f"Membuat suara narator (Gemini)… {ket}")
        naskah = "\n\n<long pause>\n\n".join(teks for teks, _ in grup)
        gaya = (GAYA_DASAR + "the script contains separate sentences; after EACH sentence take a clear, long pause "
                "(about one second) before the next. Mood of each sentence in order: "
                + "; ".join(f"({n}) {g}" for n, (_, g) in enumerate(grup, start=1)))
        wav_gabung = minta_dengan_sabar(naskah, gaya, progres, ket)
        try:
            potongan = belah_audio(wav_gabung, len(grup))
        except ValueError:
            potongan = None
        if potongan:
            for (teks, g), data in zip(grup, potongan):
                simpan_utuh(file_suara(teks, g), data)
                catat(teks, g)
                selesai += 1
        else:  # jarang terjadi: jeda tidak jelas, jadi rekam satu per satu
            for teks, g in grup:
                simpan_utuh(file_suara(teks, g), minta_dengan_sabar(teks, GAYA_DASAR + g, progres, f"{selesai} dari {len(yang_kurang)} kalimat selesai"))
                catat(teks, g)
                selesai += 1


def rekam_elevenlabs(yang_kurang, progres):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}?output_format=mp3_44100_128"
    kepala = {"xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    for i, (teks, gaya) in enumerate(yang_kurang, start=1):
        progres.progress((i - 1) / len(yang_kurang), text=f"Membuat suara narator (ElevenLabs) {i}/{len(yang_kurang)}…")
        badan = {"text": teks, "model_id": ELEVENLABS_MODEL, "language_code": "id", "voice_settings": ELEVENLABS_PENGATURAN}
        r = requests.post(url, headers=kepala, json=badan, timeout=60)
        if r.status_code == 400 and "language_code" in r.text:
            badan.pop("language_code")
            r = requests.post(url, headers=kepala, json=badan, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"ElevenLabs menolak ({r.status_code}): {r.text[:200]}")
        simpan_utuh(file_suara(teks, gaya), r.content)
        catat(teks, gaya)


def rekam_narasi(yang_kurang):
    FOLDER_SUARA.mkdir(exist_ok=True)
    progres = st.progress(0.0, text="Menyiapkan suara narator…")
    try:
        (rekam_elevenlabs if PENYEDIA == "elevenlabs" else rekam_gemini)(yang_kurang, progres)
    finally:
        progres.empty()


@st.cache_data(show_spinner=False)
def baca_narasi(daftar_file):
    hasil = {}
    for teks, path, _waktu_ubah in daftar_file:
        jenis = "audio/mpeg" if path.endswith(".mp3") else "audio/wav"
        hasil[f"narator|{teks}"] = f"data:{jenis};base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return hasil


def file_tersedia():
    daftar = baca_daftar()
    ada = []
    for teks, _gaya in NARASI:
        isi = daftar.get(teks)
        if isi and isi.get("penyedia") != "microsoft" and (FOLDER_SUARA / isi["file"]).exists():
            p = FOLDER_SUARA / isi["file"]
            ada.append((teks, str(p), p.stat().st_mtime))
    return ada


yang_kurang = [(t, g) for t, g in NARASI if perlu_dibuat(t, g, baca_daftar())]

# ---------------------------------------------------------------------------
#  PILIHAN UKURAN
# ---------------------------------------------------------------------------
kiri, kanan = st.columns([2, 1])
with kiri:
    ukuran = st.radio("Ukuran video", ["YouTube (16:9)", "TikTok (9:16)"], horizontal=True)
with kanan:
    pakai_narator = st.toggle("Suara narator", value=True,
                              help={"elevenlabs": "Suara ElevenLabs", "gemini": "Suara Google Gemini (gratis)"}.get(PENYEDIA, "Isi GEMINI_API_KEY untuk mengaktifkan suara"))

if pakai_narator and not PENYEDIA and yang_kurang:
    st.info("Suara narator belum aktif. Ambil API key **gratis** di aistudio.google.com (menu *Get API key*), "
            "lalu isi `GEMINI_API_KEY` di `.streamlit/secrets.toml` atau di menu **Secrets** Streamlit Cloud. "
            "Video tetap bisa diputar dengan subtitle.")
elif pakai_narator and yang_kurang and not st.session_state.get("narator_gagal"):
    # Otomatis, tanpa tombol. Hanya terjadi saat pertama kali (atau sampai semua kalimat selesai).
    try:
        rekam_narasi(yang_kurang)
    except KuotaHabis as e:
        st.session_state["narator_gagal"] = f"Kuota gratis hari ini sudah habis ({e}). Sisanya dibuat otomatis saat dibuka lagi besok."
    except Exception as e:
        st.session_state["narator_gagal"] = str(e)
    yang_kurang = [(t, g) for t, g in NARASI if perlu_dibuat(t, g, baca_daftar())]
if pakai_narator and st.session_state.get("narator_gagal"):
    st.warning("Sebagian suara narator belum bisa dibuat. Video tetap bisa diputar; bagian yang belum bersuara tetap ada subtitlenya.\n\n"
               f"Keterangan: {st.session_state['narator_gagal']}")
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
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Share+Tech+Mono&family=Nunito:wght@700;800;900&display=swap">
<style>
  [hidden] { display: none !important; }
  :root {
    color-scheme: dark;
    --malam: #05070f;
    --teks: #eef3ff;
    --redup: #8e9bbd;
    --oranye: #ff7a2f;
    --garis: #1c2744;
    --panel: #0d1428;
  }
  html, body { height: 100%; }
  body {
    margin: 0; background: var(--malam); color: var(--teks);
    font-family: Nunito, system-ui, sans-serif;
    display: flex; flex-direction: column; align-items: center;
    padding: 12px 16px; box-sizing: border-box;
  }
  .wadah { width: min(100%, 1200px, calc((100vh - 190px) * 16 / 9)); min-width: 280px; display: flex; flex-direction: column; gap: 10px; }
  .v916 .wadah { width: min(100%, 540px, calc((100vh - 230px) * 9 / 16)); min-width: 300px; }
  header { display: flex; justify-content: space-between; align-items: baseline; gap: 4px 12px; flex-wrap: wrap; }
  h1 { margin: 0; font: 400 clamp(24px, 3vw, 32px)/1 "Bebas Neue", Impact, sans-serif; letter-spacing: .04em; }
  h1 span { color: var(--oranye); }
  .sub { color: var(--redup); font-size: 13px; font-weight: 700; }
  .alat { display: flex; gap: 8px; flex-wrap: wrap; }
  .pilih { display: flex; background: var(--panel); border-radius: 999px; padding: 3px; box-shadow: inset 0 0 0 1px var(--garis); }
  .pilih button { background: transparent; color: var(--redup); box-shadow: none; padding: 7px 12px; font-size: 13px; }
  .pilih button.on { background: var(--oranye); color: #1b0c04; }
  .panggung { position: relative; width: 100%; aspect-ratio: 16 / 9; border-radius: 12px; overflow: hidden; background: #000; box-shadow: 0 0 0 1px var(--garis), 0 30px 80px -30px #000; }
  .v916 .panggung { aspect-ratio: 9 / 16; border-radius: 16px; }
  canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
  .mulai { position: absolute; inset: 0; display: grid; place-content: end center; justify-items: center; gap: 10px; text-align: center; padding: 0 16px 8%;
    background: linear-gradient(180deg, rgba(5,7,15,0) 40%, rgba(5,7,15,.9)); }
  .mulai button { font-size: clamp(16px, 2.2vw, 20px); padding: 14px 28px; }
  .mulai p { margin: 0; color: #c8d2ee; font-size: 14px; font-weight: 700; }
  button {
    font: 800 15px/1 Nunito, sans-serif; color: #1b0c04; background: var(--oranye);
    border: 0; border-radius: 999px; padding: 10px 18px; cursor: pointer;
    box-shadow: 0 6px 24px -6px rgba(255,122,47,.8);
  }
  button:hover { filter: brightness(1.08); }
  button:focus-visible { outline: 2px solid var(--teks); outline-offset: 3px; }
  button:disabled { opacity: .7; cursor: progress; }
  .kontrol { display: flex; gap: 8px; align-items: center; }
  .ikon { width: 40px; height: 40px; padding: 0; display: grid; place-items: center; font-size: 16px; flex: none;
    background: #111a33; color: var(--teks); box-shadow: 0 0 0 1px var(--garis); }
  .ikon.mati { opacity: .5; }
  .linimasa { flex: 1; display: flex; gap: 3px; min-width: 0; }
  .seg { flex-basis: 0; position: relative; height: 40px; border-radius: 6px; background: var(--panel); cursor: pointer; overflow: hidden;
    box-shadow: inset 0 0 0 1px var(--garis); border: 0; padding: 0; color: var(--redup); }
  .seg .isi { position: absolute; inset: 0 auto 0 0; width: 0; background: linear-gradient(90deg, rgba(255,60,40,.35), rgba(255,160,60,.5)); }
  .seg span { position: relative; font: 800 11px/40px Nunito, sans-serif; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; padding: 0 4px; text-align: center; }
  .seg.aktif { box-shadow: inset 0 0 0 1px var(--oranye); color: var(--teks); }
  .v916 .seg span { font-size: 0; }
  footer { color: var(--redup); font-size: 12px; text-align: center; font-weight: 700; }
  kbd { font: 600 11px/1 ui-monospace, monospace; border: 1px solid #33456f; border-bottom-width: 2px; border-radius: 4px; padding: 2px 5px; color: var(--teks); }
  @media (max-width: 760px) { .seg span { font-size: 0; } .sub { display: none; } }
</style>
</head>
<body>


<div class="wadah">
  <header>
    <h1>Gempa Bumi Itu <span>Apa Sih?</span></h1>
    <div class="sub">video penjelasan sinematik · ± 3 menit · nyalakan suara 🔊</div>
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
      <p>Pukul 03:14. Kota sedang tertidur…</p>
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
//  DASAR & KANVAS
// =====================================================================
const SW = 1280, SH = 720;
let VW = 1280, VH = 720, FORMAT = '169';
const kanvas = document.getElementById('kanvas');
const L = kanvas.getContext('2d');                 // layar akhir
const buf = document.createElement('canvas');      // adegan digambar di sini dulu, lalu diberi efek
const bctx = buf.getContext('2d');
let ctx = bctx;                                    // semua fungsi gambar memakai ctx
let skala = 1, DPR = 1, Q = 1, waktu = 0;
const kurangGerak = matchMedia('(prefers-reduced-motion: reduce)').matches;
function ukur() {
  const r = kanvas.getBoundingClientRect();
  DPR = Math.min(window.devicePixelRatio || 1, 2);
  kanvas.width = Math.max(1, Math.round(r.width * DPR));
  kanvas.height = Math.max(1, Math.round(r.height * DPR));
  skala = r.width / VW;
  const lebarAdegan = FORMAT === '169' ? r.width : r.width - 24 * skala;
  Q = klem(lebarAdegan * DPR / SW, 0.5, 1.5);
  buf.width = Math.round(SW * Q); buf.height = Math.round(SH * Q);
}
const lerp = (a, b, t) => a + (b - a) * t;
const klem = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const halus = t => t * t * (3 - 2 * t);
const keluar3 = t => 1 - Math.pow(1 - klem(t), 3);
const acak = (a, b) => a + Math.random() * (b - a);
const pilih = arr => arr[Math.floor(Math.random() * arr.length)];
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function kf(t, keys, ease = x => x) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) if (t <= keys[i][0]) { const [t0, v0] = keys[i - 1], [t1, v1] = keys[i]; return lerp(v0, v1, ease((t - t0) / (t1 - t0 || 1))); }
  return keys[keys.length - 1][1];
}
const kfh = (t, keys) => kf(t, keys, halus);
function muncul(lt, t0, t1, masuk = 0.3, keluar = 0.3) { if (lt < t0 || lt > t1) return 0; return Math.min(1, (lt - t0) / masuk, (t1 - lt) / keluar); }
function pop(lt, t0, d = 0.45) { if (lt < t0) return 0; const u = klem((lt - t0) / d) - 1, c = 1.70158; return 1 + (c + 1) * u * u * u + c * u * u; }
function rrect(x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
function elips(x, y, rx, ry, rot = 0) { ctx.beginPath(); ctx.ellipse(x, y, Math.max(0.1, rx), Math.max(0.1, ry), rot, 0, 6.2832); }
function bulat(x, y, r) { ctx.beginPath(); ctx.arc(x, y, Math.max(0.1, r), 0, 6.2832); }
function poligonHalus(p) { ctx.beginPath(); const n = p.length, m = i => [(p[i % n][0] + p[(i + 1) % n][0]) / 2, (p[i % n][1] + p[(i + 1) % n][1]) / 2]; ctx.moveTo(...m(0)); for (let i = 1; i <= n; i++) ctx.quadraticCurveTo(p[i % n][0], p[i % n][1], ...m(i)); ctx.closePath(); }
function poligon(p) { ctx.beginPath(); p.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.closePath(); }
function diSkala(x, y, s, fn) { if (s <= 0.001) return; ctx.save(); ctx.translate(x, y); ctx.scale(s, s); fn(); ctx.restore(); }
function sinar(warna, blur) { ctx.shadowColor = warna; ctx.shadowBlur = blur; }
function tanpaSinar() { ctx.shadowBlur = 0; ctx.shadowColor = 'transparent'; }
function lingkarGlow(x, y, r, warna, alfa = 1) {
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, warna.replace('A', alfa)); g.addColorStop(1, warna.replace('A', 0));
  ctx.fillStyle = g; ctx.fillRect(x - r, y - r, r * 2, r * 2);
}
// kamera di dalam adegan
function kamera(z, cx, cy, rot = 0) {
  ctx.translate(SW / 2 + gx, SH / 2 + gy); ctx.rotate(rot + gr); ctx.scale(z * pukul * TR.pukul, z * pukul * TR.pukul); ctx.translate(-cx, -cy);
}
// efek global yang diatur tiap adegan
let goncang = 0, glitch = 0, kilat = 0, pukul = 1, gx = 0, gy = 0, gr = 0, bloom = 1, grain = 1;

const W = {
  navy: '#0f1b3d', teks: '#18203a', oranye: '#ff7a2f', kuning: '#ffd23f', merah: '#ff3b30', biru: '#35a7ff', cyan: '#3ff0ff',
  magma: '#ff5a1f', putih: '#ffffff', krem: '#fff6ea', daun: '#58c26b',
};
const FONT_JUDUL = '"Bebas Neue", Impact, "Arial Narrow", sans-serif';
const FONT_HUD = '"Share Tech Mono", ui-monospace, monospace';
const FONT_TEKS = 'Nunito, "Segoe UI", sans-serif';
function teks(s, x, y, ukuran, warna, font = FONT_TEKS, berat = 900, rata = 'center', maks) {
  ctx.font = `${berat} ${ukuran}px ${font}`; ctx.textAlign = rata; ctx.textBaseline = 'middle'; ctx.fillStyle = warna; maks ? ctx.fillText(s, x, y, maks) : ctx.fillText(s, x, y);
}
// teks kinetik: huruf muncul satu per satu (membesar lalu mengecil ke ukuran normal)
function teksKinetik(lt, t0, s, x, y, ukuran, o = {}) {
  if (lt < t0) return;
  const jeda = o.jeda ?? 0.045, dari = o.dari ?? 2.2, font = o.font || FONT_JUDUL, berat = o.berat ?? 400;
  ctx.font = `${berat} ${ukuran}px ${font}`; ctx.textBaseline = 'middle'; ctx.textAlign = 'left';
  if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
  const spasi = o.spasi || 0, maksL = o.maks || SW - 90;
  let lebarHuruf = [...s].map(ch => ctx.measureText(ch).width + spasi), lebar = lebarHuruf.reduce((p, q) => p + q, 0) - spasi;
  if (lebar > maksL) { const f = maksL / lebar; ukuran *= f; ctx.font = `${berat} ${ukuran}px ${font}`; lebarHuruf = [...s].map(ch => ctx.measureText(ch).width + spasi * f); lebar = maksL; }
  let px = x - lebar / 2;
  const hilang = o.sampai ? klem((o.sampai - lt) / 0.4) : 1;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i], w = lebarHuruf[i];
    const u = klem((lt - t0 - i * jeda) / (o.durasi || 0.35));
    if (u > 0) {
      const k = lerp(dari, 1, keluar3(u));
      ctx.save(); ctx.translate(px + w / 2, y + (1 - keluar3(u)) * (o.naik || 0)); ctx.scale(k, k);
      ctx.globalAlpha = klem(u * 2) * hilang;
      if (o.glow) sinar(o.glow, o.glowBesar || 24);
      if (o.gradasi) { const g = ctx.createLinearGradient(0, -ukuran / 2, 0, ukuran / 2); o.gradasi.forEach((c, j) => g.addColorStop(j / (o.gradasi.length - 1), c)); ctx.fillStyle = g; }
      else ctx.fillStyle = o.warna || '#fff';
      ctx.textAlign = 'center'; ctx.fillText(ch, -spasi / 2, 0);
      if (o.garis) { tanpaSinar(); ctx.lineWidth = o.garis; ctx.strokeStyle = o.warnaGaris || 'rgba(0,0,0,.4)'; ctx.strokeText(ch, 0, 0); }
      ctx.restore();
    }
    px += w;
  }
}
// label HUD: titik berdenyut → garis tergambar → kotak meluncur → teks diketik
function hud(lt, t0, ax, ay, x, y, judul, sub = '', warna = W.cyan, kanan = true) {
  if (lt < t0) return;
  const u = lt - t0;
  const ping = (u * 1.2) % 1;
  ctx.strokeStyle = warna; ctx.globalAlpha = 1 - ping; ctx.lineWidth = 2; bulat(ax, ay, 6 + ping * 22); ctx.stroke(); ctx.globalAlpha = 1;
  sinar(warna, 12); ctx.fillStyle = warna; bulat(ax, ay, 5); ctx.fill();
  const p1 = klem(u / 0.3), p2 = klem((u - 0.3) / 0.25);
  const ex = x + (kanan ? -30 : 30);
  ctx.strokeStyle = warna; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(lerp(ax, ex, p1), lerp(ay, y, p1)); if (p2 > 0) ctx.lineTo(lerp(ex, x, p2), y); ctx.stroke();
  tanpaSinar();
  const p3 = klem((u - 0.5) / 0.3); if (p3 <= 0) return;
  ctx.font = `400 30px ${FONT_JUDUL}`; const wj = ctx.measureText(judul).width;
  ctx.font = `400 17px ${FONT_HUD}`; const ws = ctx.measureText(sub).width;
  const w = Math.max(wj, ws) + 34, h = sub ? 66 : 44, bx = kanan ? x : x - w;
  ctx.save(); ctx.globalAlpha = p3; ctx.translate((1 - keluar3(p3)) * (kanan ? -20 : 20), 0);
  ctx.fillStyle = 'rgba(6,14,30,.78)'; ctx.fillRect(bx, y - h / 2, w, h);
  ctx.strokeStyle = warna; ctx.lineWidth = 2;
  for (const [cx, cy, dx, dy] of [[bx, y - h / 2, 1, 1], [bx + w, y - h / 2, -1, 1], [bx, y + h / 2, 1, -1], [bx + w, y + h / 2, -1, -1]]) { ctx.beginPath(); ctx.moveTo(cx + dx * 12, cy); ctx.lineTo(cx, cy); ctx.lineTo(cx, cy + dy * 12); ctx.stroke(); }
  ctx.fillStyle = warna; ctx.fillRect(bx + (kanan ? 0 : w - 4), y - h / 2, 4, h);
  const n = Math.floor(klem((u - 0.6) / 0.5) * judul.length);
  teks(judul.slice(0, n), bx + 16, y - (sub ? 12 : 0), 30, '#ffffff', FONT_JUDUL, 400, 'left');
  if (sub) { const m = Math.floor(klem((u - 0.9) / 0.5) * sub.length); teks(sub.slice(0, m), bx + 16, y + 17, 17, warna, FONT_HUD, 400, 'left'); }
  ctx.restore();
}
function panah(x1, y1, x2, y2, warna, lebar = 10, p = 1) {
  if (p <= 0) return;
  const x = lerp(x1, x2, p), y = lerp(y1, y2, p), a = Math.atan2(y - y1, x - x1);
  ctx.strokeStyle = warna; ctx.fillStyle = warna; ctx.lineWidth = lebar; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x - Math.cos(a) * lebar * 1.2, y - Math.sin(a) * lebar * 1.2); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - Math.cos(a - 0.5) * lebar * 2.6, y - Math.sin(a - 0.5) * lebar * 2.6); ctx.lineTo(x - Math.cos(a + 0.5) * lebar * 2.6, y - Math.sin(a + 0.5) * lebar * 2.6); ctx.closePath(); ctx.fill();
}
function kartuKaca(x, y, w, h, r = 20, warna = 'rgba(255,255,255,.1)', garis = 'rgba(255,255,255,.35)') {
  ctx.save(); sinar('rgba(0,0,0,.45)', 30); ctx.fillStyle = warna; rrect(x, y, w, h, r); ctx.fill(); tanpaSinar();
  const g = ctx.createLinearGradient(x, y, x + w, y + h); g.addColorStop(0, 'rgba(255,255,255,.18)'); g.addColorStop(0.5, 'rgba(255,255,255,0)'); ctx.fillStyle = g; rrect(x, y, w, h, r); ctx.fill();
  ctx.strokeStyle = garis; ctx.lineWidth = 1.5; rrect(x, y, w, h, r); ctx.stroke(); ctx.restore();
}
function bintangLedak(x, y, r, warna) {
  ctx.fillStyle = warna; ctx.beginPath();
  for (let i = 0; i < 20; i++) { const a = i * Math.PI / 10, rr = i % 2 ? r * 0.55 : r; ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); }
  ctx.closePath(); ctx.fill();
}
// gelombang kejut: beberapa cincin terang yang membesar
function gelombangKejut(x, y, u, rMaks, warna = '255,255,255', sy = 1) {
  for (let k = 0; k < 3; k++) {
    const v = u - k * 0.12; if (v <= 0 || v > 1) continue;
    const r = keluar3(v) * rMaks;
    ctx.strokeStyle = `rgba(${warna},${(1 - v) * 0.9})`; ctx.lineWidth = 14 * (1 - v) + 2;
    sinar(`rgba(${warna},.8)`, 25); elips(x, y, r, r * sy); ctx.stroke(); tanpaSinar();
  }
}

// ---------- partikel
let P = [];
function tebar(n, f) { for (let i = 0; i < n; i++) P.push(f(i)); }
function updatePartikel(dt) {
  for (const p of P) { p.vx *= Math.pow(p.gesek ?? 0.99, dt * 60); p.vy *= Math.pow(p.gesek ?? 0.99, dt * 60); p.vy += (p.g || 0) * dt; p.x += p.vx * dt; p.y += p.vy * dt; p.umur -= dt; p.rot = (p.rot || 0) + (p.vr || 0) * dt; }
  P = P.filter(p => p.umur > 0);
  if (P.length > 2500) P.splice(0, P.length - 2500);
}
function gambarPartikel(lapis) {
  for (const p of P) {
    if ((p.lapis || 0) !== lapis) continue;
    const f = klem(p.umur / p.umurAwal);
    ctx.globalAlpha = (p.alfa ?? 1) * Math.min(1, f * 2) * Math.min(1, (p.umurAwal - p.umur) * 6 + 0.2);
    if (p.jenis === 'bara' || p.jenis === 'percik' || p.jenis === 'kilau') {
      ctx.globalCompositeOperation = 'lighter';
      const r = p.r * (p.jenis === 'kilau' ? (0.6 + 0.4 * Math.sin(waktu * 12 + p.x)) : f);
      const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 3); g.addColorStop(0, p.warna); g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g; ctx.fillRect(p.x - r * 3, p.y - r * 3, r * 6, r * 6);
      if (p.jenis === 'percik') { ctx.strokeStyle = p.warna; ctx.lineWidth = r * 0.8; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x - p.vx * 0.03, p.y - p.vy * 0.03); ctx.stroke(); }
      ctx.globalCompositeOperation = 'source-over';
    } else if (p.jenis === 'puing') {
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot); ctx.fillStyle = p.warna; ctx.fillRect(-p.r, -p.r * 0.6, p.r * 2, p.r * 1.2); ctx.restore();
    } else { // debu / asap
      ctx.fillStyle = p.warna; bulat(p.x, p.y, p.r * (p.jenis === 'asap' ? (2 - f) : 1)); ctx.fill();
    }
  }
  ctx.globalAlpha = 1;
}

// =====================================================================
//  SUARA: musik sinematik, efek, narator
// =====================================================================
const Suara = { ctx: null, master: null, musik: null, gema: null, bising: null, nyala: true };
function siapkanAudio() {
  if (Suara.ctx) { if (Suara.ctx.state !== 'running' && main) Suara.ctx.resume(); return; }
  try {
    const a = new (window.AudioContext || window.webkitAudioContext)();
    Suara.ctx = a;
    const kompres = a.createDynamicsCompressor(); kompres.threshold.value = -14; kompres.ratio.value = 4; kompres.connect(a.destination);
    Suara.master = a.createGain(); Suara.master.gain.value = Suara.nyala ? 0.85 : 0; Suara.master.connect(kompres);
    // gema (reverb) buatan
    const pj = a.sampleRate * 2.8, ir = a.createBuffer(2, pj, a.sampleRate);
    for (let c = 0; c < 2; c++) { const d = ir.getChannelData(c); for (let i = 0; i < pj; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / pj, 3.2); }
    Suara.gema = a.createConvolver(); Suara.gema.buffer = ir;
    const gemaG = a.createGain(); gemaG.gain.value = 0.32; Suara.gema.connect(gemaG).connect(Suara.master);
    Suara.musik = a.createGain(); Suara.musik.gain.value = 1; Suara.musik.connect(Suara.master); Suara.musik.connect(Suara.gema);
    const buf2 = a.createBuffer(1, a.sampleRate * 2, a.sampleRate), d = buf2.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    Suara.bising = buf2;
  } catch (_) { Suara.ctx = null; }
}
const siap = () => Suara.ctx && Suara.ctx.state === 'running';
const hz = m => 440 * Math.pow(2, (m - 69) / 12);
function nada(midi, t, durasi, vol, jenis = 'sine', tujuan = Suara.musik, serang = 0.008) {
  const a = Suara.ctx, o = a.createOscillator(), g = a.createGain();
  o.type = jenis; o.frequency.value = hz(midi);
  g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(vol, t + serang); g.gain.exponentialRampToValueAtTime(0.0001, t + durasi);
  o.connect(g).connect(tujuan); o.start(t); o.stop(t + durasi + 0.05);
}
function bising(t, durasi, vol, jenisFilter, frek, q = 1, tujuan = Suara.master, serang = 0.01) {
  const a = Suara.ctx, n = a.createBufferSource(); n.buffer = Suara.bising; n.loop = true;
  const f = a.createBiquadFilter(); f.type = jenisFilter; f.frequency.value = frek; f.Q.value = q;
  const g = a.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + serang); g.gain.exponentialRampToValueAtTime(0.0001, t + durasi);
  n.connect(f).connect(g).connect(tujuan); n.start(t, Math.random()); n.stop(t + durasi + 0.05);
  return f;
}
// instrumen sinematik
const ALAT = {
  braam(t, midi = 38, vol = 0.22) {           // hantaman "BRAAAM" ala trailer
    const a = Suara.ctx, lp = a.createBiquadFilter(), g = a.createGain();
    lp.type = 'lowpass'; lp.Q.value = 6; lp.frequency.setValueAtTime(180, t); lp.frequency.exponentialRampToValueAtTime(1900, t + 0.18); lp.frequency.exponentialRampToValueAtTime(260, t + 2.6);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.06); g.gain.exponentialRampToValueAtTime(0.0001, t + 3.2);
    lp.connect(g).connect(Suara.musik);
    for (const [m, det, jenis] of [[midi, -9, 'sawtooth'], [midi, 8, 'sawtooth'], [midi + 12, 4, 'square'], [midi - 12, 0, 'sawtooth'], [midi + 7, -5, 'sawtooth']]) {
      const o = a.createOscillator(); o.type = jenis; o.frequency.value = hz(m); o.detune.value = det; o.connect(lp); o.start(t); o.stop(t + 3.3);
    }
  },
  taiko(t, vol = 0.6) {
    const a = Suara.ctx, o = a.createOscillator(), g = a.createGain();
    o.frequency.setValueAtTime(95, t); o.frequency.exponentialRampToValueAtTime(42, t + 0.35);
    g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.7);
    o.connect(g).connect(Suara.musik); o.start(t); o.stop(t + 0.75);
    bising(t, 0.25, vol * 0.35, 'lowpass', 500, 1, Suara.musik, 0.002);
  },
  kick(t, vol = 0.5) { const a = Suara.ctx, o = a.createOscillator(), g = a.createGain(); o.frequency.setValueAtTime(140, t); o.frequency.exponentialRampToValueAtTime(42, t + 0.16); g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.32); o.connect(g).connect(Suara.musik); o.start(t); o.stop(t + 0.35); },
  snare(t, vol = 0.18) { bising(t, 0.16, vol, 'bandpass', 1900, 0.8, Suara.musik, 0.002); nada(55, t, 0.1, vol * 0.5, 'triangle'); },
  hat(t, vol = 0.04) { bising(t, 0.045, vol, 'highpass', 7500, 0.7, Suara.musik, 0.001); },
  detak(t, vol = 0.12) { nada(96, t, 0.03, vol, 'square', Suara.master, 0.001); },
  jantung(t, vol = 0.7) { for (const [dt, v] of [[0, 1], [0.2, 0.7]]) { const a = Suara.ctx, o = a.createOscillator(), g = a.createGain(); o.frequency.setValueAtTime(70, t + dt); o.frequency.exponentialRampToValueAtTime(38, t + dt + 0.12); g.gain.setValueAtTime(vol * v, t + dt); g.gain.exponentialRampToValueAtTime(0.001, t + dt + 0.22); o.connect(g).connect(Suara.master); o.start(t + dt); o.stop(t + dt + 0.25); } },
  subdrop(t, vol = 0.6) { const a = Suara.ctx, o = a.createOscillator(), g = a.createGain(); o.frequency.setValueAtTime(110, t); o.frequency.exponentialRampToValueAtTime(26, t + 1.6); g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.001, t + 1.8); o.connect(g).connect(Suara.master); o.start(t); o.stop(t + 1.9); },
  crash(t, vol = 0.22) { bising(t, 1.6, vol, 'highpass', 4500, 0.5, Suara.musik, 0.002); },
  sirene(t, d = 3, vol = 0.07) {
    const a = Suara.ctx, o = a.createOscillator(), lfo = a.createOscillator(), lg = a.createGain(), g = a.createGain();
    o.type = 'triangle'; o.frequency.value = 700; lfo.frequency.value = 0.7; lg.gain.value = 180; lfo.connect(lg).connect(o.frequency);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.5); g.gain.setValueAtTime(vol, t + d - 0.6); g.gain.exponentialRampToValueAtTime(0.0001, t + d);
    o.connect(g).connect(Suara.musik); o.start(t); lfo.start(t); o.stop(t + d + 0.1); lfo.stop(t + d + 0.1);
  },
  bip(t, n = 86, vol = 0.08) { nada(n, t, 0.12, vol, 'sine', Suara.master, 0.002); },
};
const sfx = {
  pop() { if (!siap()) return; const a = Suara.ctx, t = a.currentTime, o = a.createOscillator(), g = a.createGain(); o.frequency.setValueAtTime(380, t); o.frequency.exponentialRampToValueAtTime(1100, t + 0.07); g.gain.setValueAtTime(0.09, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.12); o.connect(g).connect(Suara.master); o.start(t); o.stop(t + 0.15); },
  wus(d = 0.5) { if (!siap()) return; const t = Suara.ctx.currentTime; const f = bising(t, d, 0.16, 'bandpass', 500, 0.9, Suara.master, d * 0.5); f.frequency.exponentialRampToValueAtTime(4000, t + d); },
  gemuruh(d = 3, vol = 0.5) { if (!siap()) return; const t = Suara.ctx.currentTime; bising(t, d, vol, 'lowpass', 120, 0.7, Suara.master, 0.3); nada(29, t, d, vol * 0.5, 'sawtooth', Suara.master, 0.3); },
  tek() { if (!siap()) return; const t = Suara.ctx.currentTime; bising(t, 0.14, 0.6, 'bandpass', 1700, 2, Suara.master, 0.002); nada(40, t, 0.7, 0.4, 'sine', Suara.master); },
  hantam(m = 38) { if (!siap()) return; const t = Suara.ctx.currentTime; ALAT.braam(t, m, 0.2); ALAT.taiko(t, 0.8); ALAT.subdrop(t, 0.45); ALAT.crash(t, 0.2); },
  riser(d = 2) { if (!siap()) return; const a = Suara.ctx, t = a.currentTime; const f = bising(t, d, 0.2, 'highpass', 300, 0.8, Suara.master, d * 0.95); f.frequency.exponentialRampToValueAtTime(7000, t + d); const o = a.createOscillator(), g = a.createGain(); o.type = 'sawtooth'; o.frequency.setValueAtTime(140, t); o.frequency.exponentialRampToValueAtTime(1000, t + d); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.05, t + d * 0.95); g.gain.exponentialRampToValueAtTime(0.0001, t + d + 0.05); o.connect(g).connect(Suara.master); o.start(t); o.stop(t + d + 0.1); },
  ding(n = 84) { if (!siap()) return; const t = Suara.ctx.currentTime; nada(n, t, 1.4, 0.09, 'sine', Suara.musik); nada(n + 7, t + 0.07, 1.4, 0.06, 'sine', Suara.musik); },
  petir() { if (!siap()) return; const t = Suara.ctx.currentTime; bising(t, 0.5, 0.4, 'highpass', 1200, 0.5, Suara.master, 0.002); bising(t + 0.1, 3, 0.35, 'lowpass', 180, 0.6, Suara.master, 0.2); },
  ombak() { if (!siap()) return; const f = bising(Suara.ctx.currentTime, 5, 0.25, 'lowpass', 400, 0.6, Suara.master, 1.5); f.frequency.linearRampToValueAtTime(1800, Suara.ctx.currentTime + 4); },
  pecah() { if (!siap()) return; const t = Suara.ctx.currentTime; for (let i = 0; i < 6; i++) { nada(90 + Math.random() * 10, t + i * 0.04, 0.3, 0.05, 'triangle', Suara.master); } bising(t, 0.4, 0.25, 'highpass', 3000, 0.5, Suara.master, 0.002); },
  jantung() { if (siap()) ALAT.jantung(Suara.ctx.currentTime); },
  detak() { if (siap()) ALAT.detak(Suara.ctx.currentTime); },
  bip(n) { if (siap()) ALAT.bip(Suara.ctx.currentTime, n); },
  sirene(d) { if (siap()) ALAT.sirene(Suara.ctx.currentTime, d); },
  braam(m) { if (siap()) ALAT.braam(Suara.ctx.currentTime, m); },
};
// musik berlapis: makin tinggi energi adegan, makin banyak lapisan yang masuk
const MUSIK = {
  horor:     { akor: [[38, 41, 45], [38, 39, 45], [37, 41, 44], [38, 41, 44]], gelap: true },
  misteri:   { akor: [[50, 53, 57], [46, 50, 53], [43, 46, 50], [45, 49, 52]], motif: [0, 2, 1, 3, 2, 1, 0, 2] },
  penasaran: { akor: [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]], motif: [0, 1, 2, 1, 3, 2, 1, 0] },
  tegang:    { akor: [[50, 53, 57], [46, 50, 53], [48, 51, 55], [49, 52, 56]], motif: [0, 0, 2, 1, 0, 2, 3, 2], ostinato: true },
  harapan:   { akor: [[53, 57, 60], [48, 52, 55], [50, 53, 57], [46, 50, 53]], motif: [2, 1, 0, 1, 2, 3, 2, 1] },
  epik:      { akor: [[50, 53, 57], [46, 50, 53], [48, 52, 55], [45, 49, 52]], motif: [0, 2, 3, 2, 1, 2, 0, 1], ostinato: true },
};
const BPM = 96, L16 = 60 / BPM / 4;
const Pemutar = { mood: null, ingin: null, langkah: 0, berikut: 0, energi: 0, target: 0 };
function detakMusik() {
  if (!siap()) return;
  const a = Suara.ctx;
  if (Pemutar.berikut < a.currentTime) Pemutar.berikut = a.currentTime + 0.05;
  while (Pemutar.berikut < a.currentTime + 0.2) {
    const t = Pemutar.berikut, l = Pemutar.langkah % 16, bar = Math.floor(Pemutar.langkah / 16);
    if (l === 0) Pemutar.mood = Pemutar.ingin;
    const m = MUSIK[Pemutar.mood], E = Pemutar.energi;
    if (m && E > 0.02) {
      const ak = m.akor[bar % 4], v = 0.025 + 0.03 * E;
      if (m.gelap) {
        // dengung gelap & cluster disonan
        if (l === 0) { nada(ak[0], t, L16 * 17, v * 2.2, 'sawtooth', Suara.musik, 1.2); nada(ak[0] + 0.1, t, L16 * 17, v * 1.6, 'sawtooth', Suara.musik, 1.2); nada(ak[0] - 12, t, L16 * 17, v * 2.5, 'sine', Suara.musik, 1); }
        if (l === 8 && E > 0.3) nada(ak[1] + 24, t, L16 * 8, v * 0.8, 'sine', Suara.musik, 0.8);
        if (E > 0.55 && l % 4 === 0) ALAT.taiko(t, 0.25 + 0.3 * E);
      } else {
        if (l === 0) for (const n of ak) { nada(n, t, L16 * 16, v * (0.45 + 0.5 * E), 'sawtooth', Suara.musik, 0.6); }
        if (l === 0) nada(ak[0] - 24, t, L16 * 16, v * 2.2, 'sine', Suara.musik, 0.3);
        if (m.ostinato && E > 0.3 && (l % 2 === 0 || E > 0.7)) nada(ak[0] - 12, t, L16 * 0.9, v * 1.3, 'sawtooth');
        if (!m.ostinato && E > 0.3 && (l % 2 === 0 || E > 0.8)) { const i = [0, 1, 2, 1][(l >> (E > 0.8 ? 0 : 1)) % 4]; nada(ak[i] + 12, t, L16 * 2.2, v * 0.8, 'triangle'); }
        if (E > 0.45 && l % 4 === 0) { const i = m.motif[(bar % 2) * 4 + l / 4]; const n = i === 3 ? ak[0] + 12 : ak[i]; nada(n + 24, t, L16 * 3.5, v * 0.7, 'sine'); }
        if (E > 0.35 && (l % 2 === 0 || E > 0.85)) ALAT.hat(t, 0.02 + 0.03 * E);
        if (E > 0.5 && (l === 0 || l === 8 || (E > 0.72 && (l === 6 || l === 10)))) ALAT.kick(t, 0.3 + 0.25 * E);
        if (E > 0.62 && (l === 4 || l === 12)) ALAT.snare(t, 0.1 + 0.1 * E);
        if (E > 0.75 && (l === 0 || l === 3 || l === 6)) ALAT.taiko(t, 0.2 + 0.3 * E);
        if (E > 0.7 && bar % 4 === 3 && l >= 12) ALAT.snare(t, 0.05 + 0.1 * (l - 11) / 4);
        if (E > 0.85 && bar % 4 === 0 && l === 0) ALAT.braam(t, ak[0] - 12, 0.12);
      }
    }
    Pemutar.berikut += L16; Pemutar.langkah++;
  }
}
// narator: rekaman jadi yang diisi oleh app.py (Streamlit)
const SUARA_DUBBING = {};
const Dub = { nyala: true, buffer: {}, aktif: new Set(), ada: Object.keys(SUARA_DUBBING).length > 0, dimuat: null, bus: null };
function muatDubbing() {
  if (!Dub.ada || !Suara.ctx) return Promise.resolve();
  if (Dub.dimuat) return Dub.dimuat;
  Dub.bus = Suara.ctx.createGain(); Dub.bus.gain.value = 1.25; Dub.bus.connect(Suara.master);
  Dub.dimuat = Promise.all(Object.entries(SUARA_DUBBING).map(async ([k, uri]) => {
    try { const bin = atob(uri.slice(uri.indexOf(',') + 1)), arr = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i); Dub.buffer[k] = await Suara.ctx.decodeAudioData(arr.buffer); } catch (_) {}
  })).then(siapkanWaktu);
  return Dub.dimuat;
}
const durasiSuara = s => { const b = Dub.buffer[`narator|${s}`]; return b ? b.duration : 0; };
function ucap(s) {
  if (!Dub.nyala || !Suara.nyala || !main || !Suara.ctx || !Dub.bus) return;
  const b = Dub.buffer[`narator|${s}`]; if (!b) return;
  diamkan(); // jaminan: tidak pernah ada dua kalimat bertumpuk
  const src = Suara.ctx.createBufferSource(); src.buffer = b; src.connect(Dub.bus); src.start();
  Dub.aktif.add(src); src.onended = () => Dub.aktif.delete(src);
}
function diamkan() { for (const s of Dub.aktif) { try { s.stop(); } catch (_) {} } Dub.aktif.clear(); }

// ---------- efek akhir: bloom, glitch, butiran film, vignette
const butir = document.createElement('canvas'); butir.width = butir.height = 256;
(() => { const g = butir.getContext('2d'), d = g.createImageData(256, 256); for (let i = 0; i < d.data.length; i += 4) { const v = Math.random() * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; } g.putImageData(d, 0, 0); })();
function komposisi(x, y, w, h) {
  L.save(); L.beginPath(); L.rect(x, y, w, h); L.clip();
  L.drawImage(buf, x, y, w, h);
  if (bloom > 0.01) { L.globalCompositeOperation = 'screen'; L.globalAlpha = 0.38 * bloom; L.filter = `blur(${Math.round(12 * w / SW)}px) brightness(1.15)`; L.drawImage(buf, x, y, w, h); L.filter = 'none'; L.globalAlpha = 1; L.globalCompositeOperation = 'source-over'; }
  if (glitch > 0.02 && !kurangGerak) {
    const n = Math.round(4 + glitch * 10);
    for (let k = 0; k < n; k++) {
      const sy = Math.random() * SH, sh = acak(4, 40), dx = acak(-1, 1) * 60 * glitch;
      L.drawImage(buf, 0, sy * Q, buf.width, sh * Q, x + dx * w / SW, y + sy * h / SH, w, sh * h / SH);
      L.fillStyle = pilih(['rgba(255,0,60,.18)', 'rgba(0,255,255,.16)']); L.fillRect(x + (dx + acak(-20, 20)) * w / SW, y + sy * h / SH, w, sh * h / SH);
    }
  }
  if (kilat > 0.01) { L.fillStyle = `rgba(255,255,255,${klem(kilat)})`; L.fillRect(x, y, w, h); }
  const vg = L.createRadialGradient(x + w / 2, y + h / 2, Math.min(w, h) * 0.35, x + w / 2, y + h / 2, Math.max(w, h) * 0.75);
  vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,.55)'); L.fillStyle = vg; L.fillRect(x, y, w, h);
  if (grain > 0.01) { L.globalAlpha = 0.06 * grain; L.globalCompositeOperation = 'overlay'; const pat = L.createPattern(butir, 'repeat'); L.translate(Math.random() * 256, Math.random() * 256); L.fillStyle = pat; L.fillRect(x - 256, y - 256, w + 512, h + 512); }
  L.restore();
}

// =====================================================================
//  BENDA-BENDA
// =====================================================================
function kiki(x, y, s = 1, o = {}) {
  const jk = o.jongkok ? 1 : 0;
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  if (o.jalan) ctx.rotate(Math.sin(waktu * 12) * 0.04);
  const bob = o.jalan ? -Math.abs(Math.sin(waktu * 12)) * 6 : Math.sin(waktu * 2.2) * 1.5 * (1 - jk);
  ctx.fillStyle = 'rgba(0,0,0,.25)'; elips(0, 0, 40, 7); ctx.fill();
  ctx.fillStyle = '#2c3656';
  if (!jk) {
    const l = o.jalan ? Math.sin(waktu * 12) * 8 : 0;
    rrect(-22, -64 - l, 18, 64 + l, 8); ctx.fill(); rrect(4, -64 + l, 18, 64 - l, 8); ctx.fill();
    ctx.fillStyle = '#fff'; rrect(-27, -11 - Math.max(0, l), 25, 11, 5); ctx.fill(); rrect(2, -11 - Math.max(0, -l), 25, 11, 5); ctx.fill();
  } else {
    rrect(-34, -36, 30, 22, 10); ctx.fill(); rrect(4, -36, 30, 22, 10); ctx.fill();
    ctx.fillStyle = '#fff'; rrect(-36, -13, 26, 12, 5); ctx.fill(); rrect(10, -13, 26, 12, 5); ctx.fill();
  }
  ctx.translate(0, (jk ? 34 : 0) + bob);
  const tangan = {
    turun: [[-42, -66], [42, -66]], tunjuk: [[-42, -66], [84, -150]], angkat: [[-60, -178], [60, -178]],
    kepala: [[-34, -186], [34, -186]], lambai: [[-42, -66], [66, -176 + Math.sin(waktu * 12) * 10]],
    pegang: [[-40, -40], [40, -40]], lindungi: [[-22, -196], [22, -196]], lari: [[-48 + Math.sin(waktu * 12) * 14, -80], [48 - Math.sin(waktu * 12) * 14, -80]],
  }[o.tangan || 'turun'];
  ctx.strokeStyle = '#ff7a2f'; ctx.lineWidth = 13; ctx.lineCap = 'round';
  for (const [[hx, hy], sx] of [[tangan[0], -28], [tangan[1], 28]]) { ctx.beginPath(); ctx.moveTo(sx, -112); ctx.quadraticCurveTo((sx + hx) / 2 + (sx < 0 ? -8 : 8), (-112 + hy) / 2, hx, hy); ctx.stroke(); }
  ctx.fillStyle = '#f5c9a1'; for (const [hx, hy] of tangan) { bulat(hx, hy, 8); ctx.fill(); }
  const gb = ctx.createLinearGradient(-32, -128, 32, -56); gb.addColorStop(0, '#ff9a4f'); gb.addColorStop(1, '#e8561f');
  ctx.fillStyle = gb; rrect(-32, -128, 64, 72, 22); ctx.fill();
  ctx.fillStyle = '#ffd23f'; bulat(0, -96, 11); ctx.fill();
  const hy = -166;
  ctx.fillStyle = '#f5c9a1'; bulat(-36, hy + 2, 8); ctx.fill(); bulat(36, hy + 2, 8); ctx.fill(); bulat(0, hy, 37); ctx.fill();
  ctx.fillStyle = 'rgba(255,255,255,.18)'; bulat(-12, hy - 14, 14); ctx.fill();
  ctx.fillStyle = '#231b2e';
  ctx.beginPath(); ctx.arc(0, hy - 2, 39, Math.PI * 1.03, Math.PI * 1.97);
  ctx.quadraticCurveTo(26, hy - 12, 10, hy - 8); ctx.quadraticCurveTo(-4, hy - 22, -18, hy - 8); ctx.quadraticCurveTo(-30, hy - 6, -38, hy + 2); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = '#231b2e'; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(2, hy - 40); ctx.quadraticCurveTo(14, hy - 58, 22, hy - 48); ctx.stroke();
  const e = o.ekspresi || 'senyum', ex = 13, ey = hy + 2, kedip = e === 'senyum' && (waktu % 3.4) < 0.12;
  ctx.fillStyle = '#231b2e'; ctx.strokeStyle = '#231b2e'; ctx.lineWidth = 3.5;
  if (e === 'kaget') { for (const d of [-1, 1]) { ctx.fillStyle = '#fff'; bulat(d * ex, ey, 9); ctx.fill(); ctx.fillStyle = '#231b2e'; bulat(d * ex, ey, 4.5); ctx.fill(); } }
  else if (e === 'senang') { for (const d of [-1, 1]) { ctx.beginPath(); ctx.arc(d * ex, ey + 3, 6, Math.PI * 1.1, Math.PI * 1.9); ctx.stroke(); } }
  else if (kedip) { for (const d of [-1, 1]) { ctx.beginPath(); ctx.moveTo(d * ex - 5, ey); ctx.lineTo(d * ex + 5, ey); ctx.stroke(); } }
  else { const lx = e === 'mikir' ? 2 : 0, ly = e === 'mikir' ? -3 : 0; for (const d of [-1, 1]) { bulat(d * ex + lx, ey + ly, 5); ctx.fill(); } }
  if (e === 'mikir') { ctx.beginPath(); ctx.moveTo(4, ey - 14); ctx.lineTo(20, ey - 18); ctx.stroke(); }
  if (e === 'kaget') { ctx.fillStyle = '#7a2230'; elips(0, hy + 22, 7, 9); ctx.fill(); }
  else if (e === 'senang') { ctx.fillStyle = '#7a2230'; ctx.beginPath(); ctx.arc(0, hy + 16, 10, 0, Math.PI); ctx.closePath(); ctx.fill(); }
  else if (e === 'mikir') { ctx.beginPath(); ctx.moveTo(-4, hy + 20); ctx.lineTo(8, hy + 18); ctx.stroke(); }
  else { ctx.beginPath(); ctx.arc(0, hy + 14, 8, 0.15 * Math.PI, 0.85 * Math.PI); ctx.stroke(); }
  ctx.fillStyle = 'rgba(255,120,130,.45)'; elips(-24, hy + 14, 7, 4); ctx.fill(); elips(24, hy + 14, 7, 4); ctx.fill();
  ctx.restore();
}
function meja(x, y, w = 200) {
  ctx.fillStyle = '#9c6644'; rrect(x - w / 2, y - 92, w, 16, 5); ctx.fill();
  ctx.fillStyle = '#7f5539'; ctx.fillRect(x - w / 2 + 12, y - 78, 14, 78); ctx.fillRect(x + w / 2 - 26, y - 78, 14, 78);
}
function rumah(x, y, s = 1, warna = '#f4a261', lampu = 0) {
  diSkala(x, y, s, () => {
    ctx.fillStyle = warna; ctx.fillRect(-26, -40, 52, 40);
    ctx.fillStyle = '#c0392b'; ctx.beginPath(); ctx.moveTo(-34, -38); ctx.lineTo(0, -66); ctx.lineTo(34, -38); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#4a2c1a'; ctx.fillRect(-7, -22, 14, 22);
    ctx.fillStyle = lampu ? '#ffd27a' : '#bde0fe'; if (lampu) sinar('#ffb347', 12); ctx.fillRect(12, -32, 10, 10); tanpaSinar();
  });
}
function pohon(x, y, s = 1, warna = '#3fa860') {
  diSkala(x, y, s, () => {
    ctx.fillStyle = '#6b4226'; ctx.fillRect(-5, -40, 10, 40);
    ctx.fillStyle = warna; bulat(0, -56, 24); ctx.fill(); bulat(-16, -44, 16); ctx.fill(); bulat(16, -44, 16); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,.15)'; bulat(-6, -64, 10); ctx.fill();
  });
}
// ---------- Bumi dengan atmosfer, lampu kota, awan
const RB = rng(8);
const BENUA = Array.from({ length: 9 }, () => ({ u: RB(), v: RB() * 1.4 - 0.7, r: 0.18 + RB() * 0.22, n: Array.from({ length: 8 }, () => 0.7 + RB() * 0.5) }));
const AWAN = Array.from({ length: 14 }, () => ({ u: RB(), v: RB() * 1.6 - 0.8, r: 0.06 + RB() * 0.1 }));
const KOTA = Array.from({ length: 70 }, () => [RB() * 2 - 1, RB() * 2 - 1]);
function bumi(cx, cy, R, putar, o = {}) {
  lingkarGlow(cx, cy, R * 1.35, 'rgba(80,170,255,A)', 0.45);
  ctx.save(); bulat(cx, cy, R); ctx.clip();
  const lo = ctx.createRadialGradient(cx - R * 0.4, cy - R * 0.4, R * 0.1, cx, cy, R); lo.addColorStop(0, '#4fb3ff'); lo.addColorStop(1, '#0d3b82');
  ctx.fillStyle = lo; ctx.fillRect(cx - R, cy - R, R * 2, R * 2);
  const gambarBlob = (list, warna, kec) => {
    ctx.fillStyle = warna;
    for (const b of list) for (const geser of [0, 1]) {
      const u = ((b.u + putar * kec) % 1 + geser) * 2 - 1, x = cx + u * R * 1.3, y = cy + b.v * R;
      if (b.n) { ctx.beginPath(); b.n.forEach((k, i) => { const a = i / b.n.length * 6.2832; const px = x + Math.cos(a) * b.r * R * k, py = y + Math.sin(a) * b.r * R * k * 0.8; i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }); ctx.closePath(); ctx.fill(); }
      else { elips(x, y, b.r * R * 2, b.r * R * 0.6); ctx.fill(); }
    }
  };
  gambarBlob(BENUA, '#3fae62', 1);
  gambarBlob(AWAN, 'rgba(255,255,255,.55)', 1.6);
  // sisi malam + lampu kota
  const sm = ctx.createLinearGradient(cx - R * 0.2, 0, cx + R, 0); sm.addColorStop(0, 'rgba(2,6,20,0)'); sm.addColorStop(0.45, 'rgba(2,6,20,.75)'); sm.addColorStop(1, 'rgba(2,6,20,.92)');
  ctx.fillStyle = sm; ctx.fillRect(cx - R, cy - R, R * 2, R * 2);
  ctx.fillStyle = '#ffcf6a'; sinar('#ffae3c', 6);
  for (const [u, v] of KOTA) { const x = cx + (0.35 + ((u + 1) / 2) * 0.6) * R, y = cy + v * R * 0.8; if (Math.hypot(x - cx, y - cy) < R * 0.97) { ctx.globalAlpha = 0.5 + 0.5 * Math.sin(waktu * 3 + u * 9); bulat(x, y, 1.6); ctx.fill(); } }
  ctx.globalAlpha = 1; tanpaSinar();
  ctx.restore();
  // pinggiran atmosfer
  ctx.strokeStyle = 'rgba(120,200,255,.6)'; ctx.lineWidth = 3; sinar('rgba(120,200,255,1)', 20); bulat(cx, cy, R); ctx.stroke(); tanpaSinar();
}
const BINTANG = (() => { const r = rng(3); return Array.from({ length: 220 }, () => [r() * SW * 1.4 - SW * 0.2, r() * SH * 1.4 - SH * 0.2, 0.5 + r() * 1.7, r() * 6, r()]); })();
function angkasa(geserX = 0) {
  const g = ctx.createLinearGradient(0, 0, 0, SH); g.addColorStop(0, '#04050d'); g.addColorStop(1, '#0a1030'); ctx.fillStyle = g; ctx.fillRect(-400, -400, SW + 800, SH + 800);
  // nebula
  ctx.globalCompositeOperation = 'lighter';
  lingkarGlow(250 + Math.sin(waktu * 0.1) * 40, 180, 420, 'rgba(120,40,170,A)', 0.28);
  lingkarGlow(1050, 560 + Math.cos(waktu * 0.12) * 30, 480, 'rgba(20,90,190,A)', 0.3);
  lingkarGlow(900, 120, 260, 'rgba(255,90,60,A)', 0.12);
  ctx.globalCompositeOperation = 'source-over';
  for (const [x, y, r, f, d] of BINTANG) { ctx.fillStyle = `rgba(255,255,255,${0.3 + 0.6 * (0.5 + 0.5 * Math.sin(waktu * 2 + f))})`; bulat(x + geserX * d, y, r); ctx.fill(); }
}
// retakan bercabang (untuk layar & tanah)
function buatRetak(seed, cx, cy, cabang = 7, langkah = 14) {
  const r = rng(seed), seg = [];
  const jalan = (x, y, a, n, lebar, d0) => {
    for (let i = 0; i < n; i++) {
      const pj = 22 + r() * 38; a += (r() - 0.5) * 0.9;
      const nx = x + Math.cos(a) * pj, ny = y + Math.sin(a) * pj;
      seg.push({ x1: x, y1: y, x2: nx, y2: ny, lebar, d: d0 + i });
      if (r() < 0.22 && lebar > 1.5) jalan(nx, ny, a + (r() < 0.5 ? -1 : 1) * (0.6 + r() * 0.6), Math.floor(n * 0.5), lebar * 0.6, d0 + i);
      x = nx; y = ny; lebar *= 0.93;
    }
  };
  for (let k = 0; k < cabang; k++) jalan(cx, cy, k / cabang * 6.2832 + r() * 0.5, langkah, 6, 0);
  const maks = Math.max(...seg.map(s => s.d));
  return { seg, maks };
}
function gambarRetak(R, p, warna = '#f2f5ff', glow = 'rgba(160,210,255,.9)') {
  const batas = p * (R.maks + 1);
  ctx.lineCap = 'round';
  ctx.strokeStyle = 'rgba(0,0,0,.55)';
  for (const s of R.seg) if (s.d < batas) { ctx.lineWidth = s.lebar + 3; ctx.beginPath(); ctx.moveTo(s.x1, s.y1); const f = klem(batas - s.d); ctx.lineTo(lerp(s.x1, s.x2, f), lerp(s.y1, s.y2, f)); ctx.stroke(); }
  sinar(glow, 14); ctx.strokeStyle = warna;
  for (const s of R.seg) if (s.d < batas) { ctx.lineWidth = s.lebar * 0.6; ctx.beginPath(); ctx.moveTo(s.x1, s.y1); const f = klem(batas - s.d); ctx.lineTo(lerp(s.x1, s.x2, f), lerp(s.y1, s.y2, f)); ctx.stroke(); }
  tanpaSinar();
}
// grafik seismograf (layar monitor)
function monitorSeismo(x, y, w, h, lt, amp, warnaGaris, judul, o = {}) {
  ctx.save();
  ctx.fillStyle = 'rgba(4,10,20,.82)'; rrect(x, y, w, h, 12); ctx.fill();
  ctx.strokeStyle = warnaGaris; ctx.globalAlpha = 0.5; ctx.lineWidth = 1.5; rrect(x, y, w, h, 12); ctx.stroke(); ctx.globalAlpha = 1;
  ctx.beginPath(); rrect(x, y, w, h, 12); ctx.clip();
  ctx.strokeStyle = 'rgba(120,200,255,.08)'; ctx.lineWidth = 1;
  for (let gx2 = x; gx2 < x + w; gx2 += 24) { ctx.beginPath(); ctx.moveTo(gx2, y); ctx.lineTo(gx2, y + h); ctx.stroke(); }
  for (let gy2 = y; gy2 < y + h; gy2 += 24) { ctx.beginPath(); ctx.moveTo(x, gy2); ctx.lineTo(x + w, gy2); ctx.stroke(); }
  const kec = o.kecepatan || 140, tengah = y + h / 2 + 8;
  sinar(warnaGaris, 10); ctx.strokeStyle = warnaGaris; ctx.lineWidth = 2.2; ctx.beginPath();
  for (let px = 0; px <= w - 30; px += 2) {
    const t = lt - (w - 30 - px) / kec;
    const A = Math.min(h * 0.45, amp(t));
    const yy = tengah + A * Math.sin(t * 70 + Math.sin(t * 13) * 3) * (0.6 + 0.4 * Math.sin(t * 31));
    px ? ctx.lineTo(x + px, yy) : ctx.moveTo(x + px, yy);
  }
  ctx.stroke(); tanpaSinar();
  ctx.fillStyle = warnaGaris; bulat(x + w - 30, tengah, 4); ctx.fill();
  for (let sy = y; sy < y + h; sy += 4) { ctx.fillStyle = 'rgba(0,0,0,.18)'; ctx.fillRect(x, sy, w, 1.5); }
  ctx.restore();
  teks(judul, x + 16, y + 18, 15, warnaGaris, FONT_HUD, 400, 'left');
}

// =====================================================================
//  ADEGAN 0–4
// =====================================================================
const GEDUNG = (() => { const r = rng(21), a = []; for (const [lapis, n, hMin, hMax, warna] of [[0, 26, 120, 260, '#0d1226'], [1, 18, 180, 380, '#080c1a'], [2, 10, 240, 460, '#04060e']]) { let x = -120; for (let i = 0; i < n * 2 && x < SW + 120; i++) { const w = 50 + r() * (60 + lapis * 30), h = hMin + r() * (hMax - hMin), jendela = []; for (let jy = 16; jy < h - 20; jy += 22) for (let jx = 8; jx < w - 12; jx += 16) if (r() < 0.32) jendela.push([jx, jy, r()]); a.push({ lapis, x, w, h, warna, jendela, f: r() * 6, antena: r() < 0.3 }); x += w + r() * 14 - 4; } } return a; })();
const RETAK_LAYAR = buatRetak(77, 640, 360, 8, 13);
const ADEGAN = [
  // ================================================================ 0. PEMBUKA SERAM
  {
    nama: 'Pembuka', dur: 16, transisi: 'tidak', musik: lt => lt < 11.6 ? 'horor' : lt < 12.2 ? null : 'epik',
    energi: lt => kf(lt, [[0, 0.3], [6, 0.45], [6.2, 0.7], [11.5, 0.9], [11.6, 0], [12.2, 0], [12.3, 0.95], [16, 0.7]]),
    teks: [[1.2, 5.2, 'Pukul tiga pagi. Kota sedang tertidur lelap…'], [6.6, 8.8, 'Lalu, tanpa peringatan…'], [13.4, 15.8, 'Apa yang sebenarnya terjadi di bawah kaki kita?']],
    acara: [
      ...[0.3, 1.25, 2.15, 3.0, 3.8, 4.5, 5.15, 5.75].map(t => [t, sfx.jantung]),
      ...[3.2, 4.0, 4.8, 5.6].map(t => [t, () => sfx.bip(86)]),
      ...Array.from({ length: 12 }, (_, i) => [0.5 + i * 0.5, sfx.detak]),
      [6.2, () => { sfx.braam(38); sfx.sirene(5); }], [6.25, () => sfx.gemuruh(5.4, 0.35)], [7.6, () => sfx.braam(37)],
      [9.0, () => { sfx.braam(36); sfx.gemuruh(2.6, 0.7); sfx.pecah(); }], [10.2, sfx.pecah], [9.6, () => sfx.riser(2)],
      [12.2, () => sfx.hantam(38)],
    ],
    gambar(lt, dt) {
      const gempa = kf(lt, [[6, 0], [6.4, 0.35], [8.9, 0.55], [9, 1], [11.5, 1], [11.6, 0]]);
      goncang = gempa * (lt < 9 ? 0.45 : 1.2);
      glitch = lt > 6 && lt < 11.6 ? (lt < 9 ? 0.12 + 0.35 * Math.max(0, Math.sin(waktu * 11)) : 0.25 + 0.5 * Math.random()) : (lt > 12.2 && lt < 12.45 ? 0.9 : 0);
      kilat = lt > 12.2 ? klem(1 - (lt - 12.2) / 0.35) : (lt > 9 && lt < 9.15 ? 0.6 : 0);
      pukul = lt > 12.2 ? 1 + 0.12 * klem(1 - (lt - 12.2) / 0.5) : 1;
      bloom = 1.2; grain = 1.6;
      if (lt < 11.6) {
        ctx.save(); kamera(kf(lt, [[0, 1.02], [9, 1.14], [11.6, 1.22]]), 640, 380, gempa * Math.sin(waktu * 21) * 0.012);
        const g = ctx.createLinearGradient(0, -200, 0, 620); g.addColorStop(0, '#020309'); g.addColorStop(0.6, '#0b1230'); g.addColorStop(1, lt > 6 ? campur('#1d1030', '#3a0a10', gempa) : '#1d1030');
        ctx.fillStyle = g; ctx.fillRect(-400, -400, SW + 800, SH + 800);
        for (const [x, y, r, f] of BINTANG) { if (y > 420) continue; ctx.fillStyle = `rgba(200,210,255,${0.15 + 0.35 * (0.5 + 0.5 * Math.sin(waktu * 1.5 + f))})`; bulat(x, y, r * 0.8); ctx.fill(); }
        // bulan di balik awan
        lingkarGlow(1010, 150, 190, 'rgba(210,220,255,A)', 0.22); ctx.fillStyle = '#e8ecff'; bulat(1010, 150, 46); ctx.fill();
        ctx.fillStyle = 'rgba(10,14,32,.85)'; for (let i = 0; i < 5; i++) { elips(((i * 330 + waktu * 14) % 1700) - 200, 150 + (i % 3) * 26, 170, 26); ctx.fill(); }
        // gedung tiga lapis
        for (const b of GEDUNG) {
          const dasar = 610 + b.lapis * 18, goyang = gempa * Math.sin(waktu * (9 + b.lapis * 3) + b.f) * 0.022 * (b.h / 300);
          ctx.save(); ctx.translate(b.x + b.w / 2, dasar); ctx.rotate(goyang);
          ctx.fillStyle = b.warna; ctx.fillRect(-b.w / 2, -b.h, b.w, b.h + 30);
          if (b.antena) { ctx.fillRect(-2, -b.h - 30, 4, 30); ctx.fillStyle = Math.sin(waktu * 4 + b.f) > 0 ? '#ff2d2d' : '#3a0a0a'; sinar('#ff2d2d', 10); bulat(0, -b.h - 32, 3); ctx.fill(); tanpaSinar(); }
          for (const [jx, jy, f] of b.jendela) {
            const padam = lt > 9 && f < (lt - 9) / 2.2, kedip = lt > 6 && Math.random() < 0.08 * gempa;
            if (padam || kedip || f > 0.55) continue;
            ctx.fillStyle = `rgba(255,${190 + b.lapis * 10},110,${0.35 + 0.25 * b.lapis})`; ctx.fillRect(-b.w / 2 + jx, -b.h + jy, 8, 11);
          }
          ctx.restore();
        }
        // kabut
        for (let i = 0; i < 4; i++) { const fg = ctx.createLinearGradient(0, 480, 0, 700); fg.addColorStop(0, 'rgba(60,70,110,0)'); fg.addColorStop(1, 'rgba(60,70,110,.35)'); ctx.fillStyle = fg; ctx.fillRect(((i * 400 + waktu * 20) % 1800) - 400, 470, 900, 300); }
        if (lt > 6) { ctx.fillStyle = `rgba(255,20,30,${0.18 * gempa * (0.6 + 0.4 * Math.sin(waktu * 8))})`; ctx.fillRect(-400, -400, SW + 800, SH + 800); }
        ctx.restore();
        // retak & puing (layar)
        if (lt > 9) {
          gambarRetak(RETAK_LAYAR, klem((lt - 9) / 1.8));
          if (dt > 0 && Math.random() < dt * 40) tebar(2, () => ({ jenis: pilih(['puing', 'debu']), x: acak(0, SW), y: -10, vx: acak(-40, 40), vy: acak(80, 220), g: 900, umur: 2, umurAwal: 2, r: acak(2, 7), rot: acak(0, 6), vr: acak(-8, 8), warna: pilih(['#8b8fa3', '#5d6275', '#c9ccd8']), lapis: 1 }));
        }
        gambarPartikel(1);
        // HUD
        const detik = 7 + Math.floor(lt);
        teks(`03:14:${String(detik).padStart(2, '0')} WIB`, 70, 92, 26, '#d7e1ff', FONT_HUD, 400, 'left');
        teks('KAM-07 · KOTA', 70, 122, 16, 'rgba(215,225,255,.6)', FONT_HUD, 400, 'left');
        if (Math.floor(waktu * 1.6) % 2 === 0) { ctx.fillStyle = '#ff3030'; sinar('#ff3030', 12); bulat(1128, 90, 8); ctx.fill(); tanpaSinar(); }
        teks('REC', 1146, 91, 22, '#ffd7d7', FONT_HUD, 400, 'left');
        const merah = lt > 6;
        monitorSeismo(150, 530, 980, 110, lt, t => t < 6 ? 2 + Math.random() * 1.5 : t < 9 ? 6 + (t - 6) * 12 : 80, merah ? '#ff4040' : '#46ffb4', merah ? 'SEISMOGRAF · GETARAN KUAT' : 'SEISMOGRAF · LIVE', { kecepatan: 160 });
        if (lt > 6.2 && lt < 11.6) {
          const nyala = Math.sin(waktu * 12) > -0.3;
          if (nyala) { ctx.save(); ctx.translate(acak(-6, 6) * glitch, 0); teks('⚠ PERINGATAN', 640, 300, 96, '#ff3b30', FONT_JUDUL, 400); ctx.globalCompositeOperation = 'lighter'; teks('⚠ PERINGATAN', 646, 302, 96, 'rgba(0,255,255,.35)', FONT_JUDUL, 400); ctx.restore(); }
          teks('AKTIVITAS SEISMIK TERDETEKSI', 640, 368, 22, '#ffd0d0', FONT_HUD, 400);
        }
        ctx.fillStyle = '#000'; ctx.fillRect(0, 0, SW, 44); ctx.fillRect(0, SH - 44, SW, 44);
      } else if (lt > 12.2) {
        // kartu judul
        const bg = ctx.createRadialGradient(640, 360, 20, 640, 360, 800); bg.addColorStop(0, '#3a0d08'); bg.addColorStop(0.6, '#120508'); bg.addColorStop(1, '#030103');
        ctx.fillStyle = bg; ctx.fillRect(0, 0, SW, SH);
        ctx.globalAlpha = 0.5; gambarRetak(RETAK_LAYAR, 1, '#2a0c08', 'rgba(255,90,30,.6)'); ctx.globalAlpha = 1;
        if (dt > 0 && Math.random() < dt * 30) tebar(1, () => ({ jenis: 'bara', x: acak(200, 1080), y: 740, vx: acak(-20, 20), vy: acak(-160, -60), umur: 3, umurAwal: 3, r: acak(1.5, 4), warna: pilih(['rgba(255,140,40,1)', 'rgba(255,80,20,1)', 'rgba(255,210,120,1)']) }));
        gambarPartikel(0);
        gelombangKejut(640, 330, klem((lt - 12.2) / 1.2), 900, '255,170,90');
        teksKinetik(lt, 12.25, 'GEMPA BUMI', 640, 318, 220, { dari: 3, jeda: 0.06, durasi: 0.3, gradasi: ['#fff6e0', '#ffb347', '#ff5a1f', '#8a1a0a'], glow: 'rgba(255,90,20,.9)', glowBesar: 40, spasi: 6 });
        teksKinetik(lt, 13.3, 'APA YANG TERJADI DI BAWAH KAKI KITA?', 640, 452, 34, { dari: 1.6, jeda: 0.02, font: FONT_HUD, warna: '#ffd9c2', spasi: 3 });
      }
    }
  },
  // ================================================================ 1. ISI BUMI
  {
    nama: 'Isi Bumi', dur: 16.5, transisi: 'kilat', musik: () => 'misteri', energi: lt => kf(lt, [[0, 0.35], [8, 0.5], [16, 0.55]]),
    teks: [[0.6, 4, 'Untuk menjawabnya, kita harus menyelam jauh ke dalam Bumi.'], [4.4, 8, 'Paling luar ada kerak: lapisan tipis tempat kita berdiri.'], [8.4, 12.8, 'Di bawahnya, mantel yang panas dan perlahan mengalir, lalu inti Bumi yang membara.'], [13.2, 16.2, 'Dan kunci dari gempa… ada di kerak ini.']],
    acara: [[0.1, () => sfx.wus(0.8)], [3.4, () => { sfx.wus(0.6); sfx.braam(41); }], [4.6, sfx.pop], [8.6, sfx.pop], [10.6, sfx.pop], [11.8, sfx.pop], [13.2, () => sfx.ding(86)]],
    gambar(lt, dt) {
      goncang = 0; glitch = 0; bloom = 1.3; grain = 1;
      ctx.save(); kamera(kfh(lt, [[0, 0.7], [3.4, 1], [16.5, 1.1]]), kfh(lt, [[0, 520], [16.5, 560]]), 360, kfh(lt, [[0, -0.08], [4, 0]]));
      angkasa(-lt * 6);
      const cx = 500, cy = 360, R = 230;
      bumi(cx, cy, R, waktu * 0.015);
      const span = kfh(lt, [[3.3, 0], [4.2, 1.45]]), a0 = -1.0;
      if (span > 0.01) {
        const wedge = (r1, r0 = 0) => { ctx.beginPath(); ctx.arc(cx, cy, r1, a0, a0 + span); if (r0 > 0) ctx.arc(cx, cy, r0, a0 + span, a0, true); else ctx.lineTo(cx, cy); ctx.closePath(); };
        let g = ctx.createRadialGradient(cx, cy, R - 18, cx, cy, R); g.addColorStop(0, '#6b4a33'); g.addColorStop(1, '#9c7552');
        ctx.fillStyle = g; wedge(R, R - 16); ctx.fill();
        g = ctx.createRadialGradient(cx, cy, R * 0.56, cx, cy, R - 16); g.addColorStop(0, '#ff7a1a'); g.addColorStop(0.5, '#d9361a'); g.addColorStop(1, '#6e1a12');
        ctx.fillStyle = g; wedge(R - 16, R * 0.56); ctx.fill();
        // aliran magma di mantel
        ctx.save(); wedge(R - 16, R * 0.56); ctx.clip(); ctx.globalCompositeOperation = 'lighter';
        for (let i = 0; i < 16; i++) { const a = a0 + ((i * 0.37 + waktu * 0.05 * (1 + i % 3)) % 1) * span, rr = R * (0.6 + 0.3 * ((i * 0.53) % 1)) + Math.sin(waktu + i) * 8; lingkarGlow(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, 26 + (i % 4) * 8, 'rgba(255,170,60,A)', 0.35); }
        ctx.restore();
        g = ctx.createRadialGradient(cx, cy, R * 0.3, cx, cy, R * 0.56); g.addColorStop(0, '#ffd166'); g.addColorStop(1, '#ff8c1a');
        ctx.fillStyle = g; wedge(R * 0.56, R * 0.3); ctx.fill();
        const denyut = 0.85 + 0.15 * Math.sin(waktu * 3);
        g = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.3); g.addColorStop(0, '#ffffff'); g.addColorStop(0.5, '#fff1b8'); g.addColorStop(1, '#ffc24a');
        ctx.fillStyle = g; sinar('rgba(255,220,120,1)', 40 * denyut); wedge(R * 0.3); ctx.fill(); tanpaSinar();
        ctx.strokeStyle = 'rgba(255,230,180,.9)'; ctx.lineWidth = 2; sinar('#ffb347', 14);
        ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(a0) * R, cy + Math.sin(a0) * R); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(a0 + span) * R, cy + Math.sin(a0 + span) * R); ctx.stroke(); tanpaSinar();
        if (dt > 0 && Math.random() < dt * 18) { const a = a0 + Math.random() * span, rr = R * acak(0.3, 0.9); tebar(1, () => ({ jenis: 'bara', x: cx + Math.cos(a) * rr, y: cy + Math.sin(a) * rr, vx: Math.cos(a) * acak(20, 60), vy: Math.sin(a) * acak(20, 60), umur: 1.6, umurAwal: 1.6, r: acak(1.5, 3), warna: 'rgba(255,170,70,1)' })); }
        gambarPartikel(0);
        if (lt > 13.2) { const sa = a0 + ((lt - 13.2) * 0.9 % 1) * span; ctx.strokeStyle = '#fff'; ctx.lineWidth = 8; sinar('#ffe08a', 30); ctx.beginPath(); ctx.arc(cx, cy, R - 7, a0, a0 + span); ctx.stroke(); ctx.lineWidth = 14; ctx.beginPath(); ctx.arc(cx, cy, R - 7, sa - 0.08, sa + 0.08); ctx.stroke(); tanpaSinar(); }
        const am = a0 + span * 0.55;
        const titik = [[R - 8, 4.6, 'KERAK', '5–70 km', 150], [R * 0.78, 8.6, 'MANTEL', '± 2.900 km', 265], [R * 0.43, 10.6, 'INTI LUAR', 'logam cair', 380], [R * 0.13, 11.8, 'INTI DALAM', '± 5.000 °C', 495]];
        for (const [r, t0, nm, sub, ly] of titik) hud(lt, t0, cx + Math.cos(am) * r, cy + Math.sin(am) * r, 900, ly, nm, sub, nm === 'KERAK' && lt > 13.2 ? W.kuning : W.cyan);
      }
      ctx.restore();
      teksKinetik(lt, 0.3, 'PERJALANAN KE PUSAT BUMI', 640, 64, 34, { dari: 1.6, jeda: 0.03, font: FONT_HUD, warna: '#9fdcff', spasi: 4, sampai: 3.4 });
    }
  },
  // ================================================================ 2. LEMPENG
  {
    nama: 'Lempeng', dur: 15, transisi: 'geser', musik: () => 'penasaran', energi: lt => kf(lt, [[0, 0.45], [5.6, 0.6], [15, 0.62]]),
    teks: [[0.5, 5.2, 'Kerak Bumi ternyata retak-retak menjadi potongan raksasa: lempeng tektonik.'], [5.6, 9.6, 'Lempeng-lempeng ini terus bergerak, beberapa sentimeter setiap tahun.'], [10, 14.6, 'Pelan sekali… kira-kira secepat kuku kita tumbuh.']],
    acara: [[1.6, () => { sfx.tek(); sfx.braam(40); }], [2.4, sfx.pop], [5.8, () => sfx.wus(0.7)], [10.2, sfx.pop]],
    gambar(lt, dt) {
      goncang = lt > 1.6 && lt < 2 ? 0.6 : 0; glitch = 0; bloom = 1.1; grain = 1;
      const bg = ctx.createRadialGradient(640, 380, 50, 640, 380, 900); bg.addColorStop(0, '#12305c'); bg.addColorStop(1, '#050b1c');
      ctx.fillStyle = bg; ctx.fillRect(-100, -100, SW + 200, SH + 200);
      ctx.strokeStyle = 'rgba(80,160,255,.07)'; ctx.lineWidth = 1; for (let x = 0; x < SW; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, SH); ctx.stroke(); } for (let y = 0; y < SH; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(SW, y); ctx.stroke(); }
      // proyeksi 3D sederhana
      const rot = kfh(lt, [[0, -0.2], [15, -0.05]]), sy = 0.56, z = kfh(lt, [[0, 0.9], [15, 1.05]]), T = 30;
      const pr = (x, y) => { const dx = (x - 640) * z, dy = (y - 330) * z; return [640 + dx * Math.cos(rot) - dy * Math.sin(rot), 400 + (dx * Math.sin(rot) + dy * Math.cos(rot)) * sy]; };
      const PL = [
        [[180, 130], [520, 130], [480, 300], [180, 340]], [[520, 130], [860, 130], [820, 280], [480, 300]], [[860, 130], [1100, 130], [1100, 360], [820, 280]],
        [[180, 340], [480, 300], [560, 530], [180, 530]], [[480, 300], [820, 280], [1100, 360], [1100, 530], [560, 530]],
      ];
      const warna = [['#5fd08a', '#2f8a55'], ['#b9d86a', '#6f8a2f'], ['#e3b877', '#946535'], ['#79c7a2', '#3b7d5f'], ['#d49a6a', '#8a5533']];
      const arah = [[-1, -0.4], [0.2, -1], [1, -0.2], [-0.6, 1], [0.7, 0.8]];
      const pisah = kfh(lt, [[1.6, 0], [2.6, 12]]) + (lt > 5.6 ? Math.sin(waktu * 0.9) * 3 : 0);
      // magma di bawah celah
      const dasarPoly = [pr(170, 120), pr(1110, 120), pr(1110, 540), pr(170, 540)].map(([x, y]) => [x, y + T]);
      ctx.save(); poligon(dasarPoly); const mg = ctx.createLinearGradient(0, 200, 0, 700); mg.addColorStop(0, '#ff8a2a'); mg.addColorStop(1, '#b3200e'); ctx.fillStyle = mg; sinar('#ff5a1f', 40 * klem(pisah / 12)); ctx.fill(); tanpaSinar(); ctx.restore();
      const urut = PL.map((p, i) => ({ p, i, cy: p.reduce((s, q) => s + q[1], 0) / p.length })).sort((a, b) => a.cy - b.cy);
      for (const { p, i } of urut) {
        const cxp = p.reduce((s, q) => s + q[0], 0) / p.length, cyp = p.reduce((s, q) => s + q[1], 0) / p.length;
        const ox = (cxp - 640) / 460 * pisah + arah[i][0] * 3 * klem(lt - 5.6) * Math.sin(waktu), oy = (cyp - 330) / 200 * pisah + arah[i][1] * 3 * klem(lt - 5.6) * Math.sin(waktu);
        const atas = p.map(([x, y]) => pr(lerp(x, cxp, 0.01) + ox, lerp(y, cyp, 0.01) + oy));
        const bawah = atas.map(([x, y]) => [x, y + T]);
        ctx.fillStyle = warna[i][1];
        for (let k = 0; k < atas.length; k++) { const a = atas[k], b = atas[(k + 1) % atas.length]; if (b[0] < a[0]) continue; poligon([a, b, bawah[(k + 1) % atas.length], bawah[k]]); ctx.fillStyle = campur(warna[i][1], '#000000', 0.25); ctx.fill(); }
        poligon(atas); const g = ctx.createLinearGradient(0, Math.min(...atas.map(q => q[1])), 0, Math.max(...atas.map(q => q[1]))); g.addColorStop(0, warna[i][0]); g.addColorStop(1, warna[i][1]); ctx.fillStyle = g; ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,.35)'; ctx.lineWidth = 1.5; ctx.stroke();
        // tekstur gunung kecil
        const r = rng(i + 5); ctx.fillStyle = 'rgba(255,255,255,.18)'; for (let k = 0; k < 7; k++) { const [x, y] = pr(cxp + (r() - 0.5) * 200 + ox, cyp + (r() - 0.5) * 120 + oy); ctx.beginPath(); ctx.moveTo(x - 10, y); ctx.lineTo(x, y - 12); ctx.lineTo(x + 10, y); ctx.fill(); }
        // panah aliran (chevron bergerak)
        if (lt > 5.8) {
          const [px, py] = pr(cxp + ox, cyp + oy), [qx, qy] = pr(cxp + ox + arah[i][0] * 60, cyp + oy + arah[i][1] * 60), a = Math.atan2(qy - py, qx - px);
          ctx.save(); ctx.translate(px, py); ctx.rotate(a); sinar('#ff3b30', 10);
          for (let k = 0; k < 3; k++) { const s = ((waktu * 0.8 + k / 3) % 1); ctx.globalAlpha = Math.sin(s * Math.PI) * klem((lt - 5.8) * 2); ctx.strokeStyle = '#ff4b3b'; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(-40 + s * 80 - 10, -12); ctx.lineTo(-40 + s * 80, 0); ctx.lineTo(-40 + s * 80 - 10, 12); ctx.stroke(); }
          ctx.restore(); tanpaSinar();
        }
      }
      teksKinetik(lt, 2.2, 'LEMPENG TEKTONIK', 640, 80, 72, { dari: 2.6, jeda: 0.05, gradasi: ['#ffffff', '#9fdcff'], glow: 'rgba(80,180,255,.9)', spasi: 4 });
      const k = pop(lt, 10.2, 0.5);
      diSkala(1010, 560, k, () => {
        kartuKaca(-190, -80, 380, 150, 20, 'rgba(10,20,45,.7)', 'rgba(150,210,255,.5)');
        ctx.fillStyle = '#f5c9a1'; rrect(-165, -30, 120, 56, 26); ctx.fill(); ctx.fillStyle = '#ffd6de'; rrect(-86, -22, 36, 36, 12); ctx.fill();
        const n = kf(lt, [[10.4, 0], [11.6, 5]]);
        teks(`±${n.toFixed(0)} cm`, 70, -26, 52, '#ffd23f', FONT_JUDUL, 400); teks('PER TAHUN', 70, 16, 18, '#9fdcff', FONT_HUD, 400); teks('≈ secepat kuku tumbuh', 70, 46, 16, '#e8efff', FONT_TEKS, 800);
      });
    }
  },
  // ================================================================ 3. INDONESIA (peta radar)
  {
    nama: 'Indonesia', dur: 15, transisi: 'glitch', musik: () => 'tegang', energi: lt => kf(lt, [[0, 0.45], [10, 0.6], [10.4, 0.85], [15, 0.7]]),
    teks: [[0.5, 4.8, 'Indonesia berada di tempat yang istimewa, sekaligus berbahaya.'], [5.2, 10, 'Tiga lempeng besar bertemu di sini: Eurasia, Indo-Australia, dan Pasifik.'], [10.4, 14.6, 'Itulah kenapa negeri kita termasuk yang paling sering diguncang gempa.']],
    acara: [[0.2, () => sfx.wus(0.6)], [5.6, sfx.pop], [7.0, sfx.pop], [8.4, sfx.pop], [10.4, () => { sfx.braam(38); sfx.gemuruh(1.5, 0.3); }], ...[1.5, 3.5, 5.5, 7.5, 9.5, 11.5, 13.5].map(t => [t, () => sfx.bip(98)])],
    gambar(lt, dt) {
      goncang = lt > 10.4 && lt < 11.2 ? 0.4 : 0; glitch = lt > 10.4 && lt < 10.7 ? 0.5 : 0; bloom = 1.3; grain = 1.2;
      ctx.fillStyle = '#030a16'; ctx.fillRect(-100, -100, SW + 200, SH + 200);
      ctx.save(); kamera(kfh(lt, [[0, 1.12], [6, 1.0], [15, 1.04]]), kfh(lt, [[0, 600], [15, 650]]), 380);
      ctx.strokeStyle = 'rgba(60,200,255,.08)'; ctx.lineWidth = 1; for (let x = -200; x < 1500; x += 40) { ctx.beginPath(); ctx.moveTo(x, -200); ctx.lineTo(x, 900); ctx.stroke(); } for (let y = -200; y < 900; y += 40) { ctx.beginPath(); ctx.moveTo(-200, y); ctx.lineTo(1500, y); ctx.stroke(); }
      // sapuan radar
      const sudut = waktu * 1.4;
      ctx.save(); ctx.globalCompositeOperation = 'lighter';
      for (let k = 0; k < 24; k++) { ctx.fillStyle = `rgba(40,255,200,${0.1 * (1 - k / 24)})`; ctx.beginPath(); ctx.moveTo(640, 380); ctx.arc(640, 380, 900, sudut - k * 0.03 - 0.03, sudut - k * 0.03); ctx.closePath(); ctx.fill(); }
      ctx.restore();
      for (let r = 120; r < 900; r += 120) { ctx.strokeStyle = 'rgba(40,255,200,.08)'; bulat(640, 380, r); ctx.stroke(); }
      const pulau = [
        [[170, 220], [215, 215], [300, 300], [380, 390], [420, 450], [400, 470], [330, 420], [250, 340], [185, 270]],
        [[430, 480], [520, 478], [620, 495], [660, 510], [650, 528], [560, 522], [470, 512], [428, 500]],
        [[450, 230], [520, 170], [600, 170], [640, 230], [630, 320], [570, 380], [500, 390], [460, 330]],
        [[735, 245], [800, 232], [806, 246], [752, 262], [758, 290], [818, 298], [814, 314], [762, 312], [772, 372], [754, 386], [740, 330], [722, 318], [706, 338], [700, 322], [720, 296]],
        [[940, 300], [1010, 280], [1090, 310], [1130, 360], [1120, 420], [1060, 430], [1000, 400], [960, 360], [930, 330]],
      ];
      const tampil = klem(lt / 1.5);
      ctx.save(); ctx.globalAlpha = tampil;
      for (const p of pulau) { poligonHalus(p); ctx.fillStyle = '#0d3a45'; ctx.fill(); ctx.strokeStyle = '#3ff0ff'; ctx.lineWidth = 2; sinar('#3ff0ff', 12); ctx.stroke(); tanpaSinar(); }
      for (const [x, y, rx] of [[690, 522, 12], [728, 528, 14], [770, 532, 16], [815, 535, 14], [858, 530, 12], [872, 322, 14], [884, 384, 12]]) { elips(x, y, rx, 8); ctx.fillStyle = '#0d3a45'; ctx.fill(); ctx.strokeStyle = '#3ff0ff'; ctx.stroke(); }
      ctx.restore();
      const batas = [[120, 240], [190, 380], [320, 505], [450, 565], [600, 585], [760, 578], [900, 560], [980, 500], [1010, 380], [1020, 250], [960, 160], [900, 110]];
      const pj = []; let tot = 0; for (let i = 1; i < batas.length; i++) { const d = Math.hypot(batas[i][0] - batas[i - 1][0], batas[i][1] - batas[i - 1][1]); pj.push(d); tot += d; }
      const titikDi = s => { let d = s * tot; for (let i = 0; i < pj.length; i++) { if (d <= pj[i]) { const f = d / pj[i]; return [lerp(batas[i][0], batas[i + 1][0], f), lerp(batas[i][1], batas[i + 1][1], f)]; } d -= pj[i]; } return batas[batas.length - 1]; };
      const p = klem((lt - 1.8) / 3);
      ctx.strokeStyle = '#ff3b30'; ctx.lineWidth = 5; sinar('#ff3b30', 22); ctx.beginPath();
      for (let s = 0; s <= p; s += 0.005) { const [x, y] = titikDi(s); s ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
      ctx.stroke(); tanpaSinar();
      if (p >= 1) for (let k = 0; k < 6; k++) { const [x, y] = titikDi((waktu * 0.12 + k / 6) % 1); lingkarGlow(x, y, 22, 'rgba(255,200,160,A)', 0.9); }
      const panahRadar = (x1, y1, x2, y2, t0) => { const u = klem((lt - t0) / 0.6); if (u <= 0) return; sinar('#ffb347', 14); panah(x1, y1, lerp(x1, x2, 0.6 + 0.4 * Math.sin(waktu * 3) * 0.2 + 0.2), lerp(y1, y2, 0.6 + 0.4 * Math.sin(waktu * 3) * 0.2 + 0.2), `rgba(255,179,71,${u})`, 9, u); tanpaSinar(); };
      panahRadar(470, 660, 510, 590, 7.0); panahRadar(1240, 250, 1150, 270, 8.4); panahRadar(560, 60, 560, 130, 5.6);
      if (lt > 10.4) { const r = rng(4); for (let i = 0; i < 20; i++) { const [x0, y0] = titikDi(r()); const x = x0 + (r() - 0.5) * 60, y = y0 + (r() - 0.5) * 60, ps = (waktu * 1.3 + r()) % 1; if (lt - 10.4 < r() * 1.5) continue; ctx.strokeStyle = `rgba(255,70,60,${1 - ps})`; ctx.lineWidth = 3; bulat(x, y, 6 + ps * 26); ctx.stroke(); ctx.fillStyle = '#ff4b3b'; sinar('#ff3b30', 10); bulat(x, y, 4.5); ctx.fill(); tanpaSinar(); } }
      hud(lt, 5.6, 560, 150, 700, 110, 'EURASIA', 'lempeng benua', '#3ff0ff', true);
      hud(lt, 7.0, 500, 600, 150, 575, 'INDO-AUSTRALIA', 'bergerak ke utara', '#ffb347', true);
      hud(lt, 8.4, 1130, 260, 1170, 160, 'PASIFIK', 'bergerak ke barat', '#ff6b6b', false);
      ctx.restore();
      teks('PETA LEMPENG · INDONESIA', 40, 40, 20, 'rgba(63,240,255,.85)', FONT_HUD, 400, 'left');
      teks(`LAT ${(-2.5 + Math.sin(waktu) * 0.01).toFixed(3)}  LON ${(118 + Math.cos(waktu) * 0.01).toFixed(3)}`, 40, 66, 15, 'rgba(63,240,255,.55)', FONT_HUD, 400, 'left');
      if (lt > 10.4) { const a = klem((lt - 10.4) * 2); ctx.globalAlpha = a; kartuKaca(900, 24, 340, 64, 12, 'rgba(60,5,5,.7)', 'rgba(255,90,80,.7)'); teks('⚠ ZONA RAWAN GEMPA', 1070, 57, 30, '#ff6b5e', FONT_JUDUL, 400, 'center', 310); ctx.globalAlpha = 1; }
    }
  },
  // ================================================================ 4. KENAPA GEMPA
  {
    nama: 'Kenapa Gempa', dur: 19, transisi: 'kilat', musik: lt => lt < 10.6 ? 'tegang' : lt < 11.4 ? null : 'epik',
    energi: lt => kf(lt, [[0, 0.35], [8, 0.75], [10.5, 0.95], [10.6, 0], [11.4, 0], [11.5, 1], [14, 0.9], [19, 0.5]]),
    teks: [[0.5, 4.2, 'Di perbatasan lempeng, dua raksasa saling dorong dan saling mengunci.'], [4.6, 9.4, 'Tekanan menumpuk sedikit demi sedikit, bertahun-tahun, seperti penggaris yang dibengkokkan…'], [9.8, 12.4, '…sampai akhirnya patah, dan lepas tiba-tiba!'], [13, 18.6, 'Energi raksasa itu menyebar ke segala arah sebagai getaran. Itulah gempa bumi.']],
    acara: [[1.0, sfx.pop], [2.0, sfx.pop], [3.0, () => sfx.braam(38)], [4.8, () => sfx.wus(0.6)], [8.4, () => sfx.riser(2.2)], [10.6, () => { sfx.tek(); sfx.hantam(36); sfx.gemuruh(3.5, 0.6); }], [13.2, () => sfx.braam(41)]],
    gambar(lt, dt) {
      const SNAP = 10.6;
      let b = kf(lt, [[1, 0], [SNAP, 1]], halus);
      if (lt > SNAP) { const u = lt - SNAP; b = -0.6 * Math.exp(-u * 1.7) * Math.cos(u * 9); }
      goncang = lt > SNAP && lt < 14 ? kf(lt, [[SNAP, 1.3], [14, 0]]) : (lt > 7 && lt < SNAP ? (lt - 7) / 3.6 * 0.18 : 0);
      glitch = lt > SNAP && lt < SNAP + 0.5 ? 0.8 : 0; kilat = lt > SNAP ? klem(1 - (lt - SNAP) / 0.3) * 0.9 : 0;
      pukul = lt > SNAP ? 1 + 0.1 * Math.exp(-(lt - SNAP) * 4) : 1; bloom = 1.2; grain = 1.1;
      if (lt > SNAP && lt < SNAP + 0.1 && dt > 0 && !this._ledak) { this._ledak = true; tebar(90, () => { const a = acak(0, 6.28), v = acak(150, 650); return { jenis: pilih(['percik', 'puing', 'percik']), x: 640, y: 360, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 100, g: 600, umur: acak(0.8, 1.8), umurAwal: 1.8, r: acak(2, 5), rot: acak(0, 6), vr: acak(-10, 10), warna: pilih(['rgba(255,200,120,1)', 'rgba(255,120,40,1)', '#6b5446', '#8a7466']) }; }); }
      if (lt < SNAP) this._ledak = false;
      ctx.save(); kamera(kfh(lt, [[0, 1.0], [SNAP, 1.14], [SNAP + 0.01, 1.0], [19, 1.06]]), kfh(lt, [[0, 640], [SNAP, 620], [19, 640]]), kfh(lt, [[0, 360], [SNAP, 380], [19, 360]]));
      const langit = ctx.createLinearGradient(0, -100, 0, 330); langit.addColorStop(0, '#0b1a3a'); langit.addColorStop(0.7, '#6b3a5a'); langit.addColorStop(1, '#f08a4b');
      ctx.fillStyle = langit; ctx.fillRect(-200, -200, SW + 400, 560);
      lingkarGlow(1000, 250, 220, 'rgba(255,170,90,A)', 0.5);
      const mantel = ctx.createLinearGradient(0, 300, 0, 900); mantel.addColorStop(0, '#b3321a'); mantel.addColorStop(1, '#3a0808');
      ctx.fillStyle = mantel; ctx.fillRect(-200, 300, SW + 400, 700);
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; for (let i = 0; i < 14; i++) lingkarGlow(((i * 157 + waktu * 22) % 1500) - 100, 520 + (i % 4) * 50, 70, 'rgba(255,120,30,A)', 0.3); ctx.restore();
      const naik = Math.max(0, -b) * 30;
      const laut = ctx.createLinearGradient(0, 230, 0, 330); laut.addColorStop(0, '#2b8fd6'); laut.addColorStop(1, '#0c3c78');
      ctx.fillStyle = laut; ctx.beginPath(); ctx.moveTo(-200, 332); ctx.lineTo(-200, 240);
      for (let x = -200; x <= 640; x += 16) ctx.lineTo(x, 240 + Math.sin(x * 0.03 + waktu * 2) * 4 - naik * Math.exp(-Math.pow((x - 520) / 90, 2)));
      ctx.lineTo(640, 332); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,.5)'; ctx.lineWidth = 2; ctx.beginPath(); for (let x = -200; x <= 620; x += 16) { const y = 240 + Math.sin(x * 0.03 + waktu * 2) * 4 - naik * Math.exp(-Math.pow((x - 520) / 90, 2)); x === -200 ? ctx.moveTo(x, y) : ctx.lineTo(x, y); } ctx.stroke();
      // lempeng samudra
      ctx.beginPath(); ctx.moveTo(-200, 330); ctx.lineTo(580, 330); ctx.quadraticCurveTo(720, 345, 1000, 640); ctx.lineTo(900, 820); ctx.quadraticCurveTo(640, 450, 540, 425); ctx.lineTo(-200, 425); ctx.closePath();
      let g = ctx.createLinearGradient(0, 330, 0, 430); g.addColorStop(0, '#7d8aa6'); g.addColorStop(1, '#3d4760'); ctx.fillStyle = g; ctx.fill();
      ctx.save(); ctx.clip(); const rt = rng(3); ctx.fillStyle = 'rgba(255,255,255,.08)'; for (let i = 0; i < 160; i++) { bulat(rt() * 1100 - 150, 330 + rt() * 300, rt() * 3); ctx.fill(); } ctx.restore();
      ctx.strokeStyle = 'rgba(255,255,255,.18)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(-200, 375); ctx.lineTo(560, 375); ctx.quadraticCurveTo(690, 390, 950, 700); ctx.stroke();
      // lempeng benua
      const tx = 575, ty = 330 + b * 45;
      ctx.beginPath(); ctx.moveTo(tx, ty); ctx.quadraticCurveTo(650, 300 + b * 20, 760, 290); ctx.lineTo(SW + 200, 290); ctx.lineTo(SW + 200, 430); ctx.lineTo(820, 430); ctx.quadraticCurveTo(700, 400 + b * 20, tx + 12, ty + 14); ctx.closePath();
      g = ctx.createLinearGradient(0, 290, 0, 430); g.addColorStop(0, '#c49a6c'); g.addColorStop(1, '#6e4b2e'); ctx.fillStyle = g; ctx.fill();
      ctx.save(); ctx.clip(); const rt2 = rng(9); ctx.fillStyle = 'rgba(0,0,0,.12)'; for (let i = 0; i < 140; i++) { bulat(560 + rt2() * 800, 290 + rt2() * 140, rt2() * 3); ctx.fill(); } ctx.strokeStyle = 'rgba(255,255,255,.1)'; for (const yy of [330, 370, 405]) { ctx.beginPath(); ctx.moveTo(600, yy); ctx.lineTo(1500, yy); ctx.stroke(); } ctx.restore();
      ctx.fillStyle = '#4caf6d'; ctx.beginPath(); ctx.moveTo(700, 296 + b * 8); ctx.quadraticCurveTo(740, 286, 780, 288); ctx.lineTo(SW + 200, 288); ctx.lineTo(SW + 200, 300); ctx.lineTo(700, 306 + b * 8); ctx.fill();
      for (const [x, h] of [[930, 110], [1050, 150], [1170, 95]]) { const mg = ctx.createLinearGradient(x - h, 0, x + h, 0); mg.addColorStop(0, '#8a6a52'); mg.addColorStop(1, '#4a3526'); ctx.fillStyle = mg; ctx.beginPath(); ctx.moveTo(x - h * 0.8, 290); ctx.lineTo(x, 290 - h); ctx.lineTo(x + h * 0.8, 290); ctx.fill(); ctx.fillStyle = '#f4f6ff'; ctx.beginPath(); ctx.moveTo(x - h * 0.2, 290 - h * 0.75); ctx.lineTo(x, 290 - h); ctx.lineTo(x + h * 0.2, 290 - h * 0.75); ctx.fill(); }
      const miring = lt > SNAP ? Math.sin(waktu * 30) * 0.08 * klem(1 - (lt - SNAP) / 3) : 0;
      ctx.save(); ctx.translate(820, 290); ctx.rotate(miring); rumah(0, 0, 0.8, '#f4a261', 1); ctx.restore(); ctx.save(); ctx.translate(875, 290); ctx.rotate(-miring); rumah(0, 0, 0.7, '#e9c46a', 1); ctx.restore();
      // tekanan: cahaya panas & retakan kecil di titik kunci
      const tk = lt < SNAP ? kf(lt, [[1, 0], [SNAP, 1]]) : klem(1 - (lt - SNAP) * 2);
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; lingkarGlow(630, 350, 60 + 120 * tk, 'rgba(255,120,40,A)', 0.2 + 0.7 * tk); if (tk > 0.6) lingkarGlow(630, 350, 40, 'rgba(255,255,220,A)', (tk - 0.6) * 2); ctx.restore();
      panah(-40, 380, 220, 380, 'rgba(255,255,255,.9)', 12, klem((lt - 1) / 0.6));
      const kunci = muncul(lt, 3, SNAP, 0.3, 0.1);
      if (kunci > 0) diSkala(630, 300, pop(lt, 3) * kunci, () => { sinar('#ffd23f', 20); ctx.fillStyle = W.kuning; rrect(-18, -10, 36, 30, 6); ctx.fill(); ctx.strokeStyle = W.kuning; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(0, -10, 12, Math.PI, 0); ctx.stroke(); tanpaSinar(); ctx.fillStyle = '#1b1b1b'; bulat(0, 4, 4); ctx.fill(); });
      if (lt > SNAP) { gelombangKejut(640, 370, klem((lt - SNAP - 0.05) / 1.6), 1100, '255,230,200'); gelombangKejut(640, 370, klem((lt - SNAP - 0.9) / 1.8), 1100, '255,160,90'); }
      gambarPartikel(0);
      ctx.restore();
      hud(lt, 1.0, 200, 400, 150, 470, 'LEMPENG SAMUDRA', 'menunjam ke bawah', W.cyan, true);
      hud(lt, 2.0, 1100, 380, 1130, 470, 'LEMPENG BENUA', 'tertahan & terseret', '#ffb347', false);
      // meteran tekanan
      diSkala(1190, 170, pop(lt, 4.6), () => {
        kartuKaca(-46, -118, 92, 230, 16, 'rgba(10,15,30,.7)', 'rgba(255,255,255,.3)');
        ctx.fillStyle = 'rgba(255,255,255,.1)'; rrect(-14, -96, 28, 160, 14); ctx.fill();
        const gm = ctx.createLinearGradient(0, 64, 0, -96); gm.addColorStop(0, '#2ee6a6'); gm.addColorStop(0.5, '#ffd23f'); gm.addColorStop(1, '#ff3b30');
        ctx.fillStyle = gm; sinar(tk > 0.7 ? '#ff3b30' : '#ffd23f', 18); rrect(-14, -96 + 160 * (1 - tk), 28, 160 * tk + 0.1, 14); ctx.fill(); tanpaSinar();
        teks('TEKANAN', 0, 88, 15, '#dfe7ff', FONT_HUD, 400);
      });
      // penggaris
      const pg = muncul(lt, 4.8, 11.4, 0.4, 0.4);
      if (pg > 0) diSkala(330, 150, pop(lt, 4.8) * pg, () => {
        kartuKaca(-175, -95, 350, 185, 20, 'rgba(10,15,30,.72)', 'rgba(255,255,255,.35)');
        if (lt < SNAP) {
          const bend = kf(lt, [[4.9, 0], [SNAP, 1]]) * 60, get = bend > 50 ? acak(-1.5, 1.5) : 0;
          ctx.strokeStyle = W.kuning; ctx.lineWidth = 16; ctx.lineCap = 'butt'; sinar('rgba(255,210,63,.6)', 12);
          ctx.beginPath(); ctx.moveTo(-120, 30 + get); ctx.quadraticCurveTo(0, 30 - bend * 1.6, 120, 30 - get); ctx.stroke(); tanpaSinar();
          ctx.fillStyle = '#f5c9a1'; bulat(-126, 34, 20); ctx.fill(); bulat(126, 34, 20); ctx.fill();
        } else {
          ctx.strokeStyle = W.kuning; ctx.lineWidth = 16;
          ctx.beginPath(); ctx.moveTo(-120, 30); ctx.lineTo(-14, -20); ctx.stroke(); ctx.beginPath(); ctx.moveTo(120, 30); ctx.lineTo(14, -20); ctx.stroke();
          ctx.fillStyle = '#f5c9a1'; bulat(-126, 34, 20); ctx.fill(); bulat(126, 34, 20); ctx.fill();
          diSkala(0, -40, pop(lt, SNAP, 0.3), () => { sinar('#ff3b30', 20); bintangLedak(0, 0, 46, '#ff3b30'); tanpaSinar(); teks('TEK!', 0, 2, 30, '#fff', FONT_JUDUL, 400); });
        }
        teks('SEPERTI PENGGARIS…', 0, -70, 18, '#9fdcff', FONT_HUD, 400);
      });
      teksKinetik(lt, SNAP + 0.05, 'GEMPA!', 640, 210, 170, { dari: 3.2, jeda: 0.05, durasi: 0.25, gradasi: ['#ffffff', '#ffb347', '#ff3b30'], glow: 'rgba(255,60,30,.95)', glowBesar: 40, sampai: 14.2 });
    }
  },
  // ================================================================ 5. TITIK GEMPA (balok 3D)
  {
    nama: 'Titik Gempa', dur: 12.5, transisi: 'iris', musik: () => 'misteri', energi: lt => kf(lt, [[0, 0.4], [12, 0.5]]),
    teks: [[0.5, 5, 'Titik asal gempa di dalam Bumi disebut hiposentrum.'], [5.4, 11.8, 'Sedangkan titik di permukaan, tepat di atasnya, disebut episentrum.']],
    acara: [[1.0, () => sfx.braam(43)], [1.4, sfx.pop], [6.2, sfx.pop], [6.6, sfx.pop]],
    gambar(lt, dt) {
      goncang = 0; glitch = 0; bloom = 1.25; grain = 1;
      const bg = ctx.createLinearGradient(0, 0, 0, SH); bg.addColorStop(0, '#0b1633'); bg.addColorStop(1, '#1d2a55'); ctx.fillStyle = bg; ctx.fillRect(-100, -100, SW + 200, SH + 200);
      for (const [x, y, r, f] of BINTANG) { if (y > 300) continue; ctx.fillStyle = `rgba(255,255,255,${0.2 + 0.3 * Math.sin(waktu + f)})`; bulat(x, y, r * 0.7); ctx.fill(); }
      ctx.save(); kamera(kfh(lt, [[0, 0.92], [12.5, 1.04]]), 640, kfh(lt, [[0, 380], [12.5, 360]]), kfh(lt, [[0, 0.02], [12.5, -0.01]]));
      const A = [640, 190], B = [1010, 300], C = [640, 410], D = [270, 300], H = 330;
      // sisi kiri & kanan dengan lapisan batuan
      const lapisan = [['#6aa84f', 0, 14], ['#a47c55', 14, 90], ['#8a6445', 90, 190], ['#6e4d36', 190, H]];
      for (const [warna, y0, y1] of lapisan) {
        ctx.fillStyle = warna; poligon([[D[0], D[1] + y0], [C[0], C[1] + y0], [C[0], C[1] + y1], [D[0], D[1] + y1]]); ctx.fill();
        ctx.fillStyle = campur(warna, '#000000', 0.22); poligon([[C[0], C[1] + y0], [B[0], B[1] + y0], [B[0], B[1] + y1], [C[0], C[1] + y1]]); ctx.fill();
      }
      ctx.save(); poligon([D, C, [C[0], C[1] + H], [D[0], D[1] + H]]); ctx.clip(); const rt = rng(12); ctx.fillStyle = 'rgba(0,0,0,.12)'; for (let i = 0; i < 120; i++) { bulat(270 + rt() * 370, 300 + rt() * 450, rt() * 3); ctx.fill(); } ctx.restore();
      // permukaan atas
      const ga = ctx.createLinearGradient(D[0], 0, B[0], 0); ga.addColorStop(0, '#6fd08a'); ga.addColorStop(1, '#3f9a5c'); ctx.fillStyle = ga; poligon([A, B, C, D]); ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,.4)'; ctx.lineWidth = 2; poligon([A, B, C, D]); ctx.stroke();
      const iso = (u, v) => [lerp(lerp(D[0], A[0], v), lerp(C[0], B[0], v), u), lerp(lerp(D[1], A[1], v), lerp(C[1], B[1], v), u)];
      const r = rng(5); for (let i = 0; i < 14; i++) { const [x, y] = iso(r() * 0.9 + 0.05, r() * 0.9 + 0.05); if (Math.hypot(x - 640, y - 300) < 70) continue; r() < 0.5 ? pohon(x, y, 0.45) : rumah(x, y, 0.45, pilih(['#f4a261', '#e9c46a', '#a8dadc']), 1); }
      // riak permukaan dari episentrum
      if (lt > 6.4) for (let k = 0; k < 3; k++) { const u = ((lt - 6.4) * 0.6 + k / 3) % 1; ctx.strokeStyle = `rgba(255,80,60,${1 - u})`; ctx.lineWidth = 3; elips(640, 300, 30 + u * 260, (30 + u * 260) * 0.33); ctx.stroke(); }
      // hiposentrum di dalam balok
      const fx = 640, fy = 600, ps = (waktu * 1.2) % 1;
      ctx.save(); ctx.globalCompositeOperation = 'lighter';
      lingkarGlow(fx, fy, 120, 'rgba(255,70,40,A)', 0.55 * pop(lt, 1));
      for (let k = 0; k < 3; k++) { const u = (ps + k / 3) % 1; ctx.strokeStyle = `rgba(255,120,80,${(1 - u) * pop(lt, 1)})`; ctx.lineWidth = 3; elips(fx, fy, 20 + u * 150, (20 + u * 150) * 0.45); ctx.stroke(); }
      ctx.restore();
      diSkala(fx, fy, pop(lt, 1), () => { sinar('#ff3b30', 30); bintangLedak(0, 0, 26, '#ff5a3b'); bintangLedak(0, 0, 12, '#fff3d6'); tanpaSinar(); });
      const p = klem((lt - 5.6) / 0.8);
      if (p > 0) { ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 3; ctx.setLineDash([10, 8]); ctx.lineDashOffset = -waktu * 30; sinar('#ffffff', 10); ctx.beginPath(); ctx.moveTo(fx, fy - 28); ctx.lineTo(fx, lerp(fy - 28, 300, p)); ctx.stroke(); ctx.setLineDash([]); tanpaSinar(); }
      const pin = pop(lt, 6.2, 0.6);
      if (pin > 0) { ctx.save(); ctx.translate(640, 300 - (1 - Math.min(1, pin)) * 80); sinar('#ff3b30', 20); ctx.fillStyle = '#ff3b30'; ctx.beginPath(); ctx.moveTo(0, 0); ctx.bezierCurveTo(-30, -40, -24, -72, 0, -72); ctx.bezierCurveTo(24, -72, 30, -40, 0, 0); ctx.fill(); tanpaSinar(); ctx.fillStyle = '#fff'; bulat(0, -48, 10); ctx.fill(); ctx.restore(); lingkarGlow(640, 70, 140, 'rgba(255,90,60,A)', 0.2 * pin); }
      ctx.restore();
      hud(lt, 1.4, 660, 610, 870, 610, 'HIPOSENTRUM', 'titik asal di dalam Bumi', '#ff6b5e', true);
      hud(lt, 6.6, 620, 240, 410, 150, 'EPISENTRUM', 'tepat di atasnya', '#ffd23f', false);
    }
  },
  // ================================================================ 6. GELOMBANG
  {
    nama: 'Gelombang', dur: 15, transisi: 'geser', musik: () => 'tegang', energi: lt => kf(lt, [[0, 0.45], [4.4, 0.6], [8.8, 0.62], [8.9, 0.95], [15, 0.7]]),
    teks: [[0.5, 4, 'Dari sana, getaran merambat sebagai gelombang seismik.'], [4.4, 8.4, 'Gelombang P datang lebih dulu: cepat, tapi lemah.'], [8.8, 14.6, 'Disusul gelombang S: lebih lambat, tapi guncangannya jauh lebih kuat.']],
    acara: [[4.8, sfx.pop], [4.8, () => sfx.bip(92)], [8.9, () => { sfx.hantam(40); sfx.gemuruh(2.4, 0.4); }]],
    gambar(lt, dt) {
      const fx = 220, fy = 600, sx = 1000, sy = 262, vP = 245, vS = 106, jarak = Math.hypot(sx - fx, sy - fy);
      const tP = 1 + jarak / vP, tS = 1 + jarak / vS;
      goncang = lt > tS ? klem(1 - (lt - tS) / 3) * 0.7 : (lt > tP ? klem(1 - (lt - tP) / 2) * 0.12 : 0);
      glitch = 0; bloom = 1.35; grain = 1; kilat = lt > tS ? klem(1 - (lt - tS) / 0.25) * 0.5 : 0;
      const bg = ctx.createLinearGradient(0, 0, 0, 260); bg.addColorStop(0, '#08122b'); bg.addColorStop(1, '#1b2c5a'); ctx.fillStyle = bg; ctx.fillRect(-100, -100, SW + 200, 400);
      const tn = ctx.createLinearGradient(0, 260, 0, SH); tn.addColorStop(0, '#3a2a22'); tn.addColorStop(1, '#120c10'); ctx.fillStyle = tn; ctx.fillRect(-100, 260, SW + 200, 600);
      ctx.strokeStyle = 'rgba(255,200,150,.06)'; ctx.lineWidth = 2; for (let y = 300; y < SH; y += 40) { ctx.beginPath(); ctx.moveTo(-100, y); for (let x = -100; x < SW + 100; x += 40) ctx.lineTo(x, y + Math.sin(x * 0.01 + y) * 8); ctx.stroke(); }
      ctx.fillStyle = '#2e7d4f'; ctx.fillRect(-100, 254, SW + 200, 10);
      ctx.save(); ctx.beginPath(); ctx.rect(-100, 262, SW + 200, 600); ctx.clip(); ctx.globalCompositeOperation = 'lighter';
      const muka = (r, warna, lebar) => { if (r <= 0) return; for (let k = 0; k < 4; k++) { const rr = r - k * 18; if (rr <= 0) continue; ctx.strokeStyle = `rgba(${warna},${0.9 - k * 0.22})`; ctx.lineWidth = lebar - k * 2; sinar(`rgba(${warna},1)`, 18); bulat(fx, fy, rr); ctx.stroke(); } tanpaSinar(); const rr2 = rng(Math.floor(r)); for (let i = 0; i < 24; i++) { const a = -Math.PI * rr2(); lingkarGlow(fx + Math.cos(a) * r, fy + Math.sin(a) * r, 10, `rgba(${warna},A)`, 0.8); } };
      muka(Math.max(0, (lt - 1) * vP), '60,200,255', 6); muka(Math.max(0, (lt - 1) * vS), '255,70,90', 10);
      ctx.restore();
      diSkala(fx, fy, pop(lt, 0.3), () => { sinar('#ff3b30', 30); bintangLedak(0, 0, 26, '#ff5a3b'); bintangLedak(0, 0, 11, '#fff3d6'); tanpaSinar(); });
      const getar = lt > tS ? Math.sin(waktu * 60) * 6 * klem(1 - (lt - tS) / 3) : lt > tP ? Math.sin(waktu * 60) * 1.5 : 0;
      ctx.save(); ctx.translate(sx + getar, sy);
      ctx.fillStyle = '#e8eefc'; ctx.fillRect(-52, -72, 104, 72); ctx.fillStyle = '#20355e'; ctx.beginPath(); ctx.moveTo(-62, -68); ctx.lineTo(0, -108); ctx.lineTo(62, -68); ctx.fill();
      ctx.fillStyle = '#ffd27a'; sinar('#ffb347', 12); ctx.fillRect(-36, -54, 26, 22); ctx.fillRect(10, -54, 26, 22); tanpaSinar();
      ctx.strokeStyle = '#8a95b0'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(30, -88); ctx.lineTo(30, -140); ctx.stroke();
      ctx.fillStyle = Math.sin(waktu * 6) > 0 ? '#ff3b30' : '#551010'; sinar('#ff3b30', 16); bulat(30, -142, 5); ctx.fill(); tanpaSinar();
      ctx.restore();
      if (lt > tP) gelombangKejut(sx, sy - 30, klem((lt - tP) / 1), 120, '60,200,255');
      if (lt > tS) gelombangKejut(sx, sy - 30, klem((lt - tS) / 1.2), 220, '255,90,90');
      hud(lt, 0.8, sx - 60, sy - 60, 820, 150, 'STASIUN SEISMIK', 'mencatat getaran', '#9fdcff', false);
      monitorSeismo(680, 30, 560, 110, lt, t => { let a = 1.5; if (t > tP) a += 12 * Math.exp(-(t - tP) * 0.4); if (t > tS) a += 44 * Math.exp(-(t - tS) * 0.45); return a; }, lt > tS ? '#ff5a6a' : '#46ffb4', 'SEISMOGRAM', { kecepatan: 90 });
      if (lt > 4.4) { const a = pop(lt, 4.4); diSkala(330, 150, a, () => { kartuKaca(-170, -30, 340, 60, 30, 'rgba(10,40,80,.75)', 'rgba(60,200,255,.8)'); teks('GELOMBANG P · CEPAT', 0, 2, 30, '#6fd8ff', FONT_JUDUL, 400, 'center', 310); }); }
      if (lt > 8.8) { const a = pop(lt, 8.8); diSkala(330, 220, a, () => { kartuKaca(-190, -30, 380, 60, 30, 'rgba(80,10,20,.75)', 'rgba(255,90,100,.8)'); teks('GELOMBANG S · LEBIH KUAT', 0, 2, 30, '#ff8a95', FONT_JUDUL, 400, 'center', 350); }); }
    }
  },
  // ================================================================ 7. MAGNITUDO
  {
    nama: 'Magnitudo', dur: 12.5, transisi: 'kilat', musik: () => 'tegang', energi: lt => kf(lt, [[0, 0.55], [4.6, 0.7], [7.4, 0.9], [12.5, 0.7]]),
    teks: [[0.5, 4, 'Kekuatan gempa diukur dengan magnitudo.'], [4.4, 11.8, 'Naik satu angka saja, energinya kira-kira tiga puluh dua kali lipat!']],
    acara: [[4.6, () => { sfx.braam(40); sfx.pop(); }], [7.4, () => { sfx.hantam(38); }]],
    gambar(lt, dt) {
      goncang = lt > 7.4 && lt < 8.2 ? 0.5 : 0; glitch = 0; bloom = 1.5; grain = 1; kilat = (lt > 4.6 && lt < 4.8 ? 0.35 : 0) + (lt > 7.4 && lt < 7.7 ? 0.6 : 0);
      const bg = ctx.createRadialGradient(640, 400, 20, 640, 400, 800); bg.addColorStop(0, '#2a1440'); bg.addColorStop(1, '#05030d'); ctx.fillStyle = bg; ctx.fillRect(-100, -100, SW + 200, SH + 200);
      ctx.save(); ctx.globalCompositeOperation = 'lighter';
      const m = lt < 4.6 ? 5 : lt < 7.4 ? 6 : 7;
      const cx = 640, cy = 400;
      if (m === 5) { const k = pop(lt, 0.8); lingkarGlow(cx, cy, 160 * k, 'rgba(255,170,60,A)', 0.8); lingkarGlow(cx, cy, 50 * k, 'rgba(255,255,220,A)', 1); }
      if (m === 6) { const u = klem((lt - 4.6) / 0.6); for (let i = 0; i < 32; i++) { const a = i / 32 * 6.2832 + waktu * 0.6, r = keluar3(u) * (110 + (i % 4) * 30); lingkarGlow(cx + Math.cos(a) * r, cy + Math.sin(a) * r * 0.8, 34, 'rgba(255,150,50,A)', 0.8); lingkarGlow(cx + Math.cos(a) * r, cy + Math.sin(a) * r * 0.8, 9, 'rgba(255,255,220,A)', 1); } lingkarGlow(cx, cy, 220, 'rgba(255,90,40,A)', 0.35); }
      if (m === 7) { const u = klem((lt - 7.4) / 1.2); for (let i = 0; i < 1024; i++) { const a = i * 2.39996 + waktu * (0.3 + (i % 7) * 0.05), r = keluar3(u) * Math.sqrt(i) * 11; const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r * 0.62; ctx.fillStyle = i % 5 ? 'rgba(255,170,70,.85)' : 'rgba(255,255,220,.95)'; ctx.fillRect(x - 1.6, y - 1.6, 3.2, 3.2); } lingkarGlow(cx, cy, 380, 'rgba(255,70,30,A)', 0.4); }
      ctx.restore();
      if (lt > 4.6) gelombangKejut(cx, cy, klem((lt - 4.6) / 1), 500, '255,190,120', 0.8);
      if (lt > 7.4) gelombangKejut(cx, cy, klem((lt - 7.4) / 1.2), 900, '255,120,60', 0.8);
      teksKinetik(lt, 0.3, 'MAGNITUDO', 640, 70, 54, { dari: 2, jeda: 0.04, warna: '#d9c8ff', glow: 'rgba(160,120,255,.8)', spasi: 10 });
      const angka = lt < 4.6 ? 5 : lt < 7.4 ? lerp(5, 6, klem((lt - 4.6) / 0.4)) : lerp(6, 7, klem((lt - 7.4) / 0.4));
      diSkala(640, 170, 1 + 0.15 * (Math.exp(-Math.max(0, lt - 4.6) * 6) * (lt > 4.6 ? 1 : 0) + Math.exp(-Math.max(0, lt - 7.4) * 6) * (lt > 7.4 ? 1 : 0)), () => {
        sinar('rgba(255,140,40,1)', 30); teks(`M ${angka.toFixed(1)}`, 0, 0, 110, '#ffe7c2', FONT_JUDUL, 400); tanpaSinar();
      });
      const kali = m === 5 ? '1×' : m === 6 ? '32×' : '1.024×';
      diSkala(640, 585, pop(lt, m === 5 ? 1 : m === 6 ? 4.6 : 7.4), () => { kartuKaca(-190, -34, 380, 68, 34, 'rgba(40,10,5,.7)', 'rgba(255,170,90,.7)'); teks(`ENERGI ${kali}`, 0, 2, 40, '#ffd23f', FONT_JUDUL, 400); });
      if (lt > 4.6) teks('×32', 440, 330, 42, 'rgba(255,210,150,.8)', FONT_JUDUL, 400);
      if (lt > 7.4) teks('×32 lagi', 850, 300, 42, 'rgba(255,210,150,.8)', FONT_JUDUL, 400);
    }
  },
  // ================================================================ 8. TSUNAMI
  {
    nama: 'Tsunami', dur: 11.5, transisi: 'glitch', musik: () => 'epik', energi: lt => kf(lt, [[0, 0.65], [1, 0.8], [5.4, 0.9], [5.5, 1], [11.5, 0.8]]),
    teks: [[0.5, 5, 'Jika gempa kuat terjadi di bawah laut, dasar laut bisa terangkat…'], [5.4, 11, '…mendorong kolom air raksasa menjadi gelombang tsunami.']],
    acara: [[1, () => { sfx.tek(); sfx.gemuruh(1.6, 0.4); }], [2.4, sfx.ombak], [3.2, () => sfx.riser(2.2)], [5.4, () => { sfx.hantam(36); sfx.sirene(5.5); }], [2.0, sfx.petir], [8.2, sfx.petir]],
    gambar(lt, dt) {
      goncang = (lt > 1 && lt < 2 ? 0.6 : 0) + (lt > 5.4 ? 0.2 : 0); glitch = 0; bloom = 1.2; grain = 1.3;
      const petir = (lt > 2 && lt < 2.25) || (lt > 8.2 && lt < 8.4); kilat = petir ? 0.35 : 0;
      ctx.save(); kamera(kfh(lt, [[0, 1.0], [11.5, 1.1]]), kfh(lt, [[0, 560], [11.5, 780]]), 360);
      const langit = ctx.createLinearGradient(0, -100, 0, 320); langit.addColorStop(0, '#0a0e1c'); langit.addColorStop(1, '#3b3f5c'); ctx.fillStyle = langit; ctx.fillRect(-200, -200, SW + 500, 540);
      ctx.fillStyle = 'rgba(20,22,40,.85)'; for (let i = 0; i < 8; i++) { elips(((i * 240 + waktu * 26) % 1900) - 300, 60 + (i % 3) * 40, 220, 50); ctx.fill(); }
      if (petir) { ctx.strokeStyle = '#e8f0ff'; ctx.lineWidth = 4; sinar('#bcd4ff', 30); ctx.beginPath(); let x = lt < 5 ? 400 : 900, y = -50; ctx.moveTo(x, y); for (let i = 0; i < 8; i++) { x += acak(-40, 40); y += 45; ctx.lineTo(x, y); } ctx.stroke(); tanpaSinar(); }
      const angkat = kfh(lt, [[1, 0], [1.4, 30]]);
      const dasar = x => x < 300 ? 620 : x < 460 ? 620 - angkat * Math.sin((x - 300) / 160 * Math.PI) : x < 900 ? 620 : 620 - (x - 900) * 0.9;
      const xc = kf(lt, [[1.4, 380], [10.5, 1060]], halus), A = kf(lt, [[1.4, 16], [6, 50], [10.5, 170]]), lebar = kf(lt, [[1.4, 130], [10.5, 85]]);
      const muka = x => 300 - (lt > 1.2 ? A * Math.exp(-Math.pow((x - xc) / lebar, 2)) * (x < xc ? 0.8 : 1.1) : 0) + Math.sin(x * 0.03 + waktu * 2.4) * 4;
      const air = ctx.createLinearGradient(0, 180, 0, 700); air.addColorStop(0, '#1f7fbf'); air.addColorStop(1, '#06203d');
      ctx.fillStyle = air; ctx.beginPath(); ctx.moveTo(-200, 800); for (let x = -200; x <= 1500; x += 8) ctx.lineTo(x, Math.min(muka(x), dasar(x))); ctx.lineTo(1500, 800); ctx.closePath(); ctx.fill();
      ctx.save(); ctx.clip(); ctx.globalCompositeOperation = 'lighter'; for (let i = 0; i < 6; i++) { const x = ((i * 250 + waktu * 20) % 1600) - 200; const g = ctx.createLinearGradient(x, 300, x + 80, 700); g.addColorStop(0, 'rgba(120,200,255,.12)'); g.addColorStop(1, 'rgba(120,200,255,0)'); ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(x, 300); ctx.lineTo(x + 60, 300); ctx.lineTo(x + 200, 700); ctx.lineTo(x + 100, 700); ctx.fill(); } ctx.restore();
      ctx.strokeStyle = 'rgba(255,255,255,.85)'; ctx.lineWidth = 4; sinar('rgba(255,255,255,.6)', 10); ctx.beginPath(); for (let x = -200; x <= 1500; x += 8) { const y = Math.min(muka(x), dasar(x)); x === -200 ? ctx.moveTo(x, y) : ctx.lineTo(x, y); } ctx.stroke(); tanpaSinar();
      if (lt > 5 && dt > 0) tebar(Math.floor(A / 20), () => ({ jenis: 'debu', x: xc + acak(-30, 50), y: muka(xc) - acak(0, 10), vx: acak(40, 160), vy: acak(-160, -40), g: 400, umur: 1.2, umurAwal: 1.2, r: acak(2, 5), warna: 'rgba(235,245,255,.9)' }));
      gambarPartikel(0);
      const tanah = ctx.createLinearGradient(0, 400, 0, 800); tanah.addColorStop(0, '#8a6a4a'); tanah.addColorStop(1, '#3a2a1c');
      ctx.fillStyle = tanah; ctx.beginPath(); ctx.moveTo(-200, 800); for (let x = -200; x <= 1500; x += 10) ctx.lineTo(x, dasar(x)); ctx.lineTo(1500, 800); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#e2cf9f'; ctx.fillRect(1180, 300, 400, 500); ctx.fillStyle = '#3f9a5c'; ctx.fillRect(1180, 290, 400, 12);
      for (const [x, w] of [[1215, '#f4a261'], [1275, '#e9c46a'], [1335, '#a8dadc']]) rumah(x, 292, 0.7, w, 1);
      ctx.strokeStyle = '#6b4226'; ctx.lineWidth = 8; ctx.beginPath(); ctx.moveTo(1140, 360); ctx.quadraticCurveTo(1150, 300, 1130, 250); ctx.stroke();
      ctx.fillStyle = '#3f9a5c'; for (let i = 0; i < 5; i++) { ctx.save(); ctx.translate(1130, 250); ctx.rotate(-2.6 + i * 0.9 + Math.sin(waktu * 3 + i) * 0.12); elips(26, 0, 30, 7); ctx.fill(); ctx.restore(); }
      if (lt > 1) { ctx.save(); ctx.globalCompositeOperation = 'lighter'; lingkarGlow(380, 600, 90, 'rgba(255,150,60,A)', klem(1 - (lt - 1) / 2)); ctx.restore(); }
      panah(380, 580, 380, 470, `rgba(255,210,63,${klem(1 - (lt - 4))})`, 9, klem((lt - 1.2) / 0.4));
      ctx.restore();
      hud(lt, 1.3, 400, 600, 150, 520, 'DASAR LAUT TERANGKAT', '', '#ffd23f', true);
      if (lt > 5.4) { const n = Math.sin(waktu * 8) > -0.2; if (n) { kartuKaca(380, 70, 520, 84, 14, 'rgba(90,5,5,.75)', 'rgba(255,90,80,.9)'); teks('⚠ PERINGATAN TSUNAMI', 640, 113, 50, '#ff6b5e', FONT_JUDUL, 400, 'center', 490); } }
    }
  },
  // ================================================================ 9. SAAT GEMPA
  {
    nama: 'Saat Gempa', dur: 17.5, transisi: 'iris', musik: () => 'harapan', energi: lt => kf(lt, [[0, 0.45], [11.8, 0.6], [12.4, 0.85], [17.5, 0.8]]),
    teks: [[0.5, 3.4, 'Lalu, apa yang harus kita lakukan saat gempa datang?'], [3.8, 8.8, 'Merunduk, berlindung di bawah meja yang kuat, dan berpegangan.'], [9.2, 11.6, 'Jauhi kaca dan lemari yang bisa roboh.'], [12, 17.2, 'Dan jika kamu di pantai setelah gempa kuat, segera lari ke tempat tinggi!']],
    acara: [[4.0, sfx.pop], [5.4, sfx.pop], [7.0, sfx.pop], [9.4, sfx.pecah], [11.8, () => sfx.wus(0.7)], [12.6, () => sfx.braam(45)]],
    gambar(lt, dt) {
      goncang = 0; glitch = 0; bloom = 1; grain = 0.8;
      const bg = ctx.createLinearGradient(0, 0, SW, SH); bg.addColorStop(0, '#12355b'); bg.addColorStop(0.5, '#1f5f7a'); bg.addColorStop(1, '#3b2a6a'); ctx.fillStyle = bg; ctx.fillRect(-100, -100, SW + 200, SH + 200);
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; for (let i = 0; i < 9; i++) lingkarGlow(((i * 163 + waktu * 18) % 1500) - 100, 100 + (i * 97) % 520, 60 + (i % 3) * 40, pilih(['rgba(120,220,255,A)']), 0.14); ctx.restore();
      const geser = kfh(lt, [[11.8, 0], [12.5, -1500]]);
      ctx.save(); ctx.translate(geser, 0);
      teksKinetik(lt, 0.3, 'SAAT GEMPA TERJADI', 640, 70, 60, { dari: 2.2, jeda: 0.035, warna: '#ffffff', glow: 'rgba(120,220,255,.8)', spasi: 6 });
      if (lt < 3.8) kiki(640, 600, 1.1, { ekspresi: 'mikir', tangan: 'kepala' });
      const langkah = [[240, 4.0, '1', 'MERUNDUK'], [640, 5.4, '2', 'BERLINDUNG'], [1040, 7.0, '3', 'BERPEGANGAN']];
      for (const [x, t0, n, judul] of langkah) {
        diSkala(x, 330, pop(lt, t0, 0.5), () => {
          kartuKaca(-170, -200, 340, 390, 26, 'rgba(255,255,255,.12)', 'rgba(255,255,255,.45)');
          sinar('#ff7a2f', 20); ctx.fillStyle = '#ff7a2f'; bulat(-126, -158, 26); ctx.fill(); tanpaSinar(); teks(n, -126, -155, 34, '#fff', FONT_JUDUL, 400);
          teks(judul, 26, -156, 40, '#ffffff', FONT_JUDUL, 400, 'center', 230);
          ctx.save(); rrect(-150, -118, 300, 290, 18); ctx.clip();
          const gg = ctx.createLinearGradient(0, -118, 0, 172); gg.addColorStop(0, 'rgba(255,255,255,.9)'); gg.addColorStop(1, 'rgba(220,235,255,.9)'); ctx.fillStyle = gg; ctx.fillRect(-150, -118, 300, 290);
          ctx.fillStyle = '#d9c4a5'; ctx.fillRect(-150, 130, 300, 60);
          if (n === '1') kiki(0, 132, 0.95, { jongkok: true, tangan: 'lindungi', ekspresi: 'mikir' });
          if (n === '2') { meja(0, 134, 230); kiki(0, 134, 0.8, { jongkok: true, tangan: 'lindungi', ekspresi: 'mikir' }); }
          if (n === '3') { meja(0, 134, 230); kiki(-10, 134, 0.8, { jongkok: true, tangan: 'pegang', ekspresi: 'senyum' }); }
          ctx.restore();
        });
      }
      diSkala(640, 640, pop(lt, 9.4), () => {
        kartuKaca(-270, -40, 540, 80, 40, 'rgba(90,10,10,.6)', 'rgba(255,120,110,.7)');
        ctx.fillStyle = '#9fd9f0'; ctx.fillRect(-235, -24, 44, 48); ctx.strokeStyle = '#ff3b30'; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(-241, -28); ctx.lineTo(-185, 28); ctx.moveTo(-185, -28); ctx.lineTo(-241, 28); ctx.stroke();
        teks('JAUHI KACA & LEMARI!', 30, 3, 44, '#ffffff', FONT_JUDUL, 400, 'center', 420);
      });
      ctx.restore();
      const g2 = kfh(lt, [[11.8, 1500], [12.5, 0]]);
      if (g2 < 1490) {
        ctx.save(); ctx.translate(g2, 0);
        const s = ctx.createLinearGradient(0, 0, 0, 560); s.addColorStop(0, '#2a1a4a'); s.addColorStop(0.6, '#ff7a5a'); s.addColorStop(1, '#ffc27a'); ctx.fillStyle = s; ctx.fillRect(-100, -100, SW + 200, 700);
        lingkarGlow(300, 470, 200, 'rgba(255,220,150,A)', 0.8); ctx.fillStyle = '#fff1c8'; bulat(300, 470, 50); ctx.fill();
        const laut = ctx.createLinearGradient(0, 520, 0, 720); laut.addColorStop(0, '#1f6fb0'); laut.addColorStop(1, '#0a2748');
        ctx.fillStyle = laut; ctx.beginPath(); ctx.moveTo(-100, 560); for (let x = -100; x <= 460; x += 10) ctx.lineTo(x, 540 + Math.sin(x * 0.05 + waktu * 3) * 8 - Math.max(0, lt - 13) * 10 * Math.exp(-Math.pow((x - 200) / 150, 2))); ctx.lineTo(460, 800); ctx.lineTo(-100, 800); ctx.fill();
        ctx.fillStyle = '#e9d8a6'; ctx.fillRect(420, 560, 300, 200);
        const bk = ctx.createLinearGradient(600, 250, 1300, 700); bk.addColorStop(0, '#5fd08a'); bk.addColorStop(1, '#2f7a4a');
        ctx.fillStyle = bk; ctx.beginPath(); ctx.moveTo(600, 580); ctx.quadraticCurveTo(900, 560, 1000, 300); ctx.lineTo(1400, 250); ctx.lineTo(1400, 800); ctx.lineTo(600, 800); ctx.fill();
        rumah(1150, 262, 1, '#f4a261', 1);
        const u = klem((lt - 12.8) / 3.6), kx = lerp(560, 1060, u), ky = u < 0.5 ? lerp(600, 480, u * 2) : lerp(480, 285, (u - 0.5) * 2);
        kiki(kx, ky, 0.75, { jalan: u < 1, tangan: 'lari', ekspresi: u < 1 ? 'kaget' : 'senang' });
        sinar('#ffd23f', 20); panah(700, 520, 960, 330, '#ffd23f', 11, klem((lt - 12.4) / 0.6)); tanpaSinar();
        teksKinetik(lt, 13, 'SEGERA KE TEMPAT TINGGI!', 700, 150, 64, { dari: 2.2, jeda: 0.03, warna: '#ffffff', glow: 'rgba(255,90,60,.9)', spasi: 3 });
        ctx.restore();
      }
    }
  },
  // ================================================================ 10. PENUTUP
  {
    nama: 'Penutup', dur: 13, transisi: 'kilat', musik: lt => lt < 12 ? 'epik' : null, energi: lt => kf(lt, [[0, 0.8], [6.4, 1], [10.5, 0.8], [12.5, 0.2]]),
    teks: [[0.5, 6.2, 'Jadi, gempa terjadi karena lempeng Bumi bergerak, menumpuk energi, lalu melepaskannya tiba-tiba.'], [6.6, 12, 'Kita tidak bisa mencegahnya, tapi kita bisa selalu siap. Tetap waspada!']],
    acara: [[0.8, sfx.pop], [2.4, sfx.pop], [4.0, sfx.pop], [6.6, () => sfx.hantam(41)], [11.8, () => sfx.braam(38)]],
    gambar(lt, dt) {
      goncang = 0; glitch = 0; bloom = 1.4; grain = 1; kilat = lt > 6.6 && lt < 6.9 ? 0.4 : 0;
      ctx.save(); kamera(kfh(lt, [[0, 1.05], [13, 0.95]]), 640, 360, kfh(lt, [[0, 0.03], [13, -0.02]]));
      angkasa(lt * 8);
      bumi(930, 380, 200, waktu * 0.02);
      ctx.save(); ctx.globalCompositeOperation = 'lighter';
      for (let i = 0; i < 90; i++) { const a = i / 90 * 6.2832 + waktu * 0.25, x = 930 + Math.cos(a) * 290, y = 380 + Math.sin(a) * 90; if (Math.sin(a) < 0 && Math.hypot(x - 930, y - 380) < 200) continue; lingkarGlow(x, y, 6, 'rgba(255,190,110,A)', 0.8); }
      ctx.restore();
      ctx.restore();
      const langkah = [[0.8, 'LEMPENG BERGERAK'], [2.4, 'ENERGI MENUMPUK'], [4.0, 'LEPAS TIBA-TIBA → BUMI BERGETAR']];
      langkah.forEach(([t0, s], i) => diSkala(360, 170 + i * 110, pop(lt, t0), () => {
        kartuKaca(-270, -38, 540, 76, 38, i === 2 ? 'rgba(255,100,40,.35)' : 'rgba(255,255,255,.1)', i === 2 ? 'rgba(255,160,90,.9)' : 'rgba(255,255,255,.4)');
        sinar(i === 2 ? '#ff7a2f' : '#9fdcff', 16); ctx.fillStyle = i === 2 ? '#ff7a2f' : '#3fa9ff'; bulat(-230, 0, 18); ctx.fill(); tanpaSinar(); teks(String(i + 1), -230, 2, 26, '#fff', FONT_JUDUL, 400);
        teks(s, 20, 3, 38, '#ffffff', FONT_JUDUL, 400, 'center', 440);
      }));
      teksKinetik(lt, 6.8, 'TETAP SIAGA', 640, 560, 120, { dari: 3, jeda: 0.06, gradasi: ['#ffffff', '#ffd23f', '#ff7a2f'], glow: 'rgba(255,140,40,.9)', glowBesar: 36, spasi: 8 });
      if (lt > 12) { ctx.fillStyle = `rgba(0,0,0,${klem((lt - 12) / 1)})`; ctx.fillRect(0, 0, SW, SH); }
    }
  },
];
function hex(h) { return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]; }
function campur(a, b, t) { const A = hex(a), B = hex(b); t = klem(t); return `rgb(${Math.round(A[0] + (B[0] - A[0]) * t)},${Math.round(A[1] + (B[1] - A[1]) * t)},${Math.round(A[2] + (B[2] - A[2]) * t)})`; }

// =====================================================================
//  WAKTU MENYESUAIKAN PANJANG SUARA NARATOR (supaya tidak bertabrakan)
// =====================================================================
let AWAL = [], TOTAL = 0;
function siapkanWaktu() {
  for (const a of ADEGAN) {
    let akhir = 0, geser = 0;
    const titik = [[0, 0]];
    a.garis = (a.teks || []).map(([t0, t1, s]) => {
      const d = durasiSuara(s);
      const mulai = Math.max(t0 + geser, akhir + 0.3);
      geser = mulai - t0;
      titik.push([t0, mulai]);
      akhir = mulai + (d || (t1 - t0));
      return { s, mulai, selesai: Math.max(mulai + (t1 - t0), mulai + d + 0.4) };
    });
    a.garis.forEach((g, i) => { if (a.garis[i + 1]) g.selesai = Math.min(g.selesai, a.garis[i + 1].mulai - 0.1); });
    a.durNyata = Math.max(a.dur + geser, akhir + 0.8);
    titik.push([a.dur, a.durNyata]);
    a.peta = titik;
  }
  AWAL = []; TOTAL = 0;
  for (const a of ADEGAN) { AWAL.push(TOTAL); TOTAL += a.durNyata; }
  segEls.forEach((s, k) => { s.style.flexGrow = ADEGAN[k].durNyata; });
}
// waktu nyata di adegan -> waktu rencana animasi
function keRencana(a, r) {
  const p = a.peta;
  for (let i = 1; i < p.length; i++) if (r <= p[i][1]) { const [p0, r0] = p[i - 1], [p1, r1] = p[i]; return r1 > r0 ? lerp(p0, p1, (r - r0) / (r1 - r0)) : p1; }
  return a.dur;
}
const indeksAdegan = t => { for (let i = ADEGAN.length - 1; i >= 0; i--) if (t >= AWAL[i]) return i; return 0; };

// =====================================================================
//  PEMUTAR
// =====================================================================
let T = 0, main = false, idx = -1, rSebelum = 0, pSebelum = 0, selesai = false, pertama = true;
function bungkus(s, maks) {
  const kata = s.split(' '), baris = []; let b = '';
  for (const k of kata) { const c = b ? b + ' ' + k : k; if (L.measureText(c).width > maks && b) { baris.push(b); b = k; } else b = c; }
  if (b) baris.push(b); return baris;
}
function subtitle(a, r, x, y, ukuran, maks, gaya916) {
  for (const g of a.garis || []) {
    const al = muncul(r, g.mulai, g.selesai, 0.2, 0.2); if (al <= 0) continue;
    L.save(); L.globalAlpha = al; L.font = `900 ${ukuran}px ${FONT_TEKS}`; L.textAlign = 'center'; L.textBaseline = 'middle';
    const baris = bungkus(g.s, maks), lh = ukuran * 1.28;
    if (!gaya916) {
      const w = Math.max(...baris.map(b => L.measureText(b).width)) + ukuran * 1.3, h = baris.length * lh + ukuran * 0.6;
      L.fillStyle = 'rgba(4,8,18,.72)'; L.beginPath(); L.roundRect ? L.roundRect(x - w / 2, y - h / 2, w, h, 14) : L.rect(x - w / 2, y - h / 2, w, h); L.fill();
      L.fillStyle = '#fff'; baris.forEach((b, i) => L.fillText(b, x, y + (i - (baris.length - 1) / 2) * lh + 1));
    } else {
      L.lineJoin = 'round'; L.lineWidth = ukuran * 0.24; L.strokeStyle = 'rgba(0,0,0,.9)';
      baris.forEach((b, i) => { const yy = y + (i - (baris.length - 1) / 2) * lh; L.strokeText(b, x, yy); L.fillStyle = i === 0 ? '#fff' : '#ffe08a'; L.fillText(b, x, yy); });
    }
    L.restore();
  }
}
const TR = { kilat: 0, glitch: 0, pukul: 1 };
function transisi(a, r) {
  TR.kilat = 0; TR.glitch = 0; TR.pukul = 1;
  const u = klem(r / 0.7); if (u >= 1 || !a.transisi || a.transisi === 'tidak') return;
  if (a.transisi === 'kilat') { TR.kilat = 1 - u; TR.pukul = 1 + 0.12 * (1 - keluar3(u)); }
  if (a.transisi === 'glitch') TR.glitch = 1 - u;
  if (a.transisi === 'iris') { ctx.beginPath(); ctx.arc(SW / 2, SH / 2, keluar3(u) * 800, 0, 6.2832); ctx.clip(); }
  if (a.transisi === 'geser') a._geser = u;
}
function gambarAdegan(a, r, lt, dt) {
  ctx.setTransform(Q, 0, 0, Q, 0, 0);
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, SW, SH);
  ctx.save();
  a._geser = 1;
  transisi(a, r);
  gx = goncang > 0.01 && !kurangGerak ? Math.sin(waktu * 71) * 10 * goncang : 0; gy = goncang > 0.01 && !kurangGerak ? Math.cos(waktu * 57) * 7 * goncang : 0; gr = goncang > 0.01 && !kurangGerak ? Math.sin(waktu * 43) * 0.006 * goncang : 0;
  ctx.translate(gx, gy);
  a.gambar(lt, dt);
  ctx.restore();
  kilat = Math.max(kilat, TR.kilat); glitch = Math.max(glitch, TR.glitch);
  if (a._geser < 1) { const u = keluar3(a._geser); ['#ff7a2f', '#ffd23f', '#3fa9ff'].forEach((c, i) => { const v = klem(u * 1.4 - i * 0.15); ctx.fillStyle = c; ctx.fillRect(SW * v + i * 30 - 60, 0, SW + 200, SH); }); }
}
let terakhir = performance.now();
function bingkai(now) {
  const dt = Math.min((now - terakhir) / 1000, 0.05); terakhir = now;
  if (main) { T += dt; if (T >= TOTAL) { T = TOTAL - 0.001; setMain(false); selesai = true; tombolMulai.textContent = '↻ Tonton lagi'; layarMulai.hidden = false; } }
  const i = indeksAdegan(T);
  if (i !== idx) { idx = i; P = []; rSebelum = T - AWAL[i] - 0.0001; pSebelum = keRencana(ADEGAN[i], rSebelum); segEls.forEach((s, k) => s.classList.toggle('aktif', k === i)); }
  const a = ADEGAN[i], r = T - AWAL[i], lt = keRencana(a, r), dts = main ? dt : 0;
  if (main) {
    for (const [t, fn] of a.acara || []) if (pSebelum < t && t <= lt) fn();
    for (const g of a.garis || []) if (rSebelum < g.mulai && g.mulai <= r) ucap(g.s);
    waktu += dt;
  }
  rSebelum = r; pSebelum = lt;
  Pemutar.ingin = a.musik ? a.musik(lt) : null;
  Pemutar.target = a.energi ? a.energi(lt) : 0.4;
  Pemutar.energi += (Pemutar.target - Pemutar.energi) * Math.min(1, dt * (Pemutar.target < Pemutar.energi - 0.3 ? 20 : 3));
  if (main) detakMusik();
  if (Suara.musik) Suara.musik.gain.setTargetAtTime(Dub.aktif.size ? 0.4 : 1, Suara.ctx.currentTime, 0.12);
  kilat = 0; glitch = 0; pukul = 1;
  updatePartikel(dts);
  gambarAdegan(a, r, lt, dts);
  L.setTransform(skala * DPR, 0, 0, skala * DPR, 0, 0);
  L.fillStyle = '#000'; L.fillRect(0, 0, VW, VH);
  if (FORMAT === '169') {
    komposisi(0, 0, VW, VH);
    subtitle(a, r, VW / 2, VH - 58, 25, VW - 280, false);
  } else {
    const g = L.createLinearGradient(0, 0, 0, VH); g.addColorStop(0, '#140608'); g.addColorStop(0.5, '#05070f'); g.addColorStop(1, '#0a0f24'); L.fillStyle = g; L.fillRect(0, 0, VW, VH);
    L.save(); L.textAlign = 'center'; L.textBaseline = 'middle';
    L.shadowColor = 'rgba(255,90,20,.9)'; L.shadowBlur = 24; L.fillStyle = '#ff7a2f'; L.font = `400 92px ${FONT_JUDUL}`; L.fillText('GEMPA BUMI', VW / 2, 215);
    L.shadowBlur = 0; L.fillStyle = '#fff'; L.font = `900 38px ${FONT_TEKS}`; L.fillText('itu apa sih? 🌏', VW / 2, 282);
    L.fillStyle = 'rgba(255,255,255,.1)'; L.fillRect(VW / 2 - 140, 330, 280, 40);
    L.fillStyle = '#ffd23f'; L.font = `400 22px ${FONT_HUD}`; L.fillText(`${i + 1}/${ADEGAN.length} · ${a.nama.toUpperCase()}`, VW / 2, 351);
    L.restore();
    komposisi(12, 400, VW - 24, (VW - 24) * SH / SW);
    subtitle(a, r, VW / 2, 930, 36, VW - 80, true);
  }
  segEls.forEach((s, k) => { s.firstChild.style.width = (klem((T - AWAL[k]) / ADEGAN[k].durNyata) * 100) + '%'; });
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
async function lompatKe(k) {
  k = Math.max(0, Math.min(ADEGAN.length - 1, k));
  diamkan();
  if (!main) { siapkanAudio(); await muatDubbing(); layarMulai.hidden = true; setMain(true); }
  T = AWAL[k] + 0.001; idx = -1; selesai = false; pertama = false;
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
  if (Suara.master) Suara.master.gain.setTargetAtTime(Suara.nyala ? 0.85 : 0, Suara.ctx.currentTime, 0.05);
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
siapkanWaktu();
gantiFormat(KONFIG_AWAL.format);
T = 14.2; waktu = 14.2; // poster: judul "GEMPA BUMI" sudah tampil
window.__video = { lompat: t => { T = t; idx = -1; }, format: gantiFormat, total: () => TOTAL, awal: () => AWAL.slice() };
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

# ---------------------------------------------------------------------------
#  SIMPAN REKAMAN SECARA PERMANEN
# ---------------------------------------------------------------------------
ada_semua = file_tersedia()
if ada_semua:
    with st.expander(f"💾 Simpan rekaman narator permanen ({len(ada_semua)}/{len(NARASI)} kalimat sudah bersuara)"):
        st.markdown(
            "Rekaman di server Streamlit bisa hilang saat app di-restart. Supaya permanen:\n"
            "1. Klik tombol di bawah untuk download zip rekaman.\n"
            "2. Ekstrak zip-nya, nanti muncul folder **suara_narator**.\n"
            "3. Upload folder itu ke repo GitHub-mu (sejajar dengan app.py)."
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(FOLDER_SUARA.iterdir()):
                if f.suffix in (".wav", ".mp3", ".json"):
                    z.write(f, f"suara_narator/{f.name}")
        st.download_button("⬇️ Download rekaman suara (zip)", buf.getvalue(), file_name="suara_narator.zip", mime="application/zip")
