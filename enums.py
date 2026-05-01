# enums.py - All enumeration classes for DBD Expert System

from enum import Enum

class GenanganAir(str, Enum):
    ADA = "ada"
    TIDAK_ADA = "tidak_ada"

class DurasiGenangan(str, Enum):
    KURANG_3 = "<3 hari"
    TIGA_ENAM = "3-6 hari"
    LEBIH_7 = ">=7 hari"

class KeberadaanJentik(str, Enum):
    LUAS = "luas"
    JARANG = "jarang"
    TIDAK_ADA = "tidak_ada"

class NyamukAedes(str, Enum):
    BANYAK = "banyak"
    JARANG = "jarang"
    TIDAK_TERLIHAT = "tidak_terlihat"

class FrekuensiHujan(str, Enum):
    SERING = "sering"
    JARANG = "jarang"
    TIDAK_PERNAH = "tidak_pernah"

class IntensitasHujan(str, Enum):
    RINGAN = "ringan"
    SEDANG = "sedang"
    DERAS = "deras"

class MobilitasPenduduk(str, Enum):
    TINGGI = "tinggi"
    RENDAH = "rendah"

class KepadatanPenduduk(str, Enum):
    PADAT = "padat"
    RENGGANG = "renggang"

class KondisiLingkungan(str, Enum):
    KUMUH = "kumuh"
    BERSIH = "bersih"

class PotensiPerkembangbiakan(str, Enum):
    RENDAH = "rendah"
    SEDANG = "sedang"
    TINGGI = "tinggi"

class Iklim(str, Enum):
    MENDUKUNG = "mendukung"
    KURANG_MENDUKUNG = "kurang_mendukung"
    TIDAK_MENDUKUNG = "tidak_mendukung"

class FaktorEksposurManusia(str, Enum):
    RENTAN = "rentan"
    AMAN = "aman"

class TingkatResikoDBD(str, Enum):
    RENDAH = "rendah"
    SEDANG = "sedang"
    TINGGI = "tinggi"

# Question mapping for UI
QUESTIONS = {
    'genangan_air_terbuka': {
        'text': 'Apakah terdapat genangan air terbuka di sekitar area?',
        'options': {'ada': 'Ada', 'tidak_ada': 'Tidak Ada'},
        'explanation': {
            'ada': '📍 Genangan air terlihat di permukaan tanah - potensi tempat perindukan nyamuk Aedes aegypti',
            'tidak_ada': '✅ Area kering, tidak ada genangan air - risiko minimal untuk perkembangbiakan nyamuk'
        }
    },
    'durasi_genangan_air': {
        'text': 'Berapa durasi genangan air yang terjadi?',
        'options': {'<3 hari': '< 3 Hari', '3-6 hari': '3-6 Hari', '>=7 hari': '≥ 7 Hari'},
        'explanation': {
            '<3 hari': '⏱️ Genangan cepat kering (<3 hari) - terlalu singkat untuk siklus telur nyamuk menjadi larva',
            '3-6 hari': '⚠️ Durasi 3-6 hari - cukup untuk siklus telur nyamuk menjadi larva (biasanya 5-7 hari)',
            '>=7 hari': '🔴 Lebih dari 1 minggu - sangat ideal untuk perkembangbiakan nyamuk (multi generasi)'
        }
    },
    'keberadaan_jentik': {
        'text': 'Bagaimana keberadaan jentik (larva) nyamuk di genangan air?',
        'options': {'luas': 'Luas', 'jarang': 'Jarang', 'tidak_ada': 'Tidak Ada'},
        'explanation': {
            'luas': '🦟 >50 jentik per meter persegi - tersebar di banyak genangan, indikasi perkembangbiakan aktif',
            'jarang': '🔍 5-50 jentik per meter persegi - hanya di beberapa tempat, masih dalam batas kewaspadaan',
            'tidak_ada': '✨ 0 jentik - air bersih dari larva, tidak ada tanda perkembangbiakan'
        }
    },
    'nyamuk_aedes': {
        'text': 'Seberapa banyak nyamuk Aedes aegypti (bercorak putih) yang terlihat?',
        'options': {'banyak': 'Banyak', 'jarang': 'Jarang', 'tidak_terlihat': 'Tidak Terlihat'},
        'explanation': {
            'banyak': '⚠️ >10 ekor per jam atau >50 ekor per rumah - populasi tinggi, risiko penularan sangat tinggi',
            'jarang': '🐝 1-10 ekor per jam atau 5-50 ekor per rumah - populasi sedang, perlu kewaspadaan',
            'tidak_terlihat': '✅ 0 ekor - tidak ada aktivitas nyamuk Aedes, risiko rendah'
        }
    },
    'frekuensi_hujan': {
        'text': 'Seberapa sering hujan terjadi di daerah ini (dalam 1 bulan terakhir)?',
        'options': {'sering': 'Sering', 'jarang': 'Jarang', 'tidak_pernah': 'Tidak Pernah'},
        'explanation': {
            'sering': '🌧️ >15 hari hujan per bulan - menciptakan banyak genangan air baru secara terus-menerus',
            'jarang': '☁️ 5-15 hari hujan per bulan - genangan air terbatas, fluktuatif',
            'tidak_pernah': '☀️ <5 hari hujan per bulan - minim genangan air alami'
        }
    },
    'intensitas_hujan': {
        'text': 'Bagaimana intensitas curah hujan yang terjadi?',
        'options': {'ringan': 'Ringan', 'sedang': 'Sedang', 'deras': 'Deras'},
        'explanation': {
            'ringan': '💧 <10 mm/hari - gerimis, tidak menciptakan genangan berarti',
            'sedang': '🌊 10-50 mm/hari - hujan biasa, menciptakan genangan sementara',
            'deras': '⛈️ >50 mm/hari - hujan lebat, menciptakan genangan luas dan banjir'
        }
    },
    'mobilitas_penduduk': {
        'text': 'Bagaimana tingkat mobilitas penduduk di area tersebut (perpindahan orang keluar/masuk)?',
        'options': {'tinggi': 'Tinggi', 'rendah': 'Rendah'},
        'explanation': {
            'tinggi': '🚶 >100 orang per hari - area terminal/stasiun/pasar/industri, berisiko membawa virus dari luar',
            'rendah': '🏠 <100 orang per hari - area perumahan tertutup/desa, sirkulasi penduduk terbatas'
        }
    },
    'kepadatan_penduduk': {
        'text': 'Bagaimana kepadatan penduduk di area tersebut (jumlah jiwa per km²)?',
        'options': {'padat': 'Padat', 'renggang': 'Renggang'},
        'explanation': {
            'padat': '🏙️ >5.000 jiwa/km² - seperti perkotaan, perumahan padat, memudahkan penularan antar rumah',
            'renggang': '🌾 <5.000 jiwa/km² - seperti perumahan, pedesaan, jarak antar rumah cukup jauh'
        }
    },
    'kondisi_lingkungan_sekitar': {
        'text': 'Bagaimana kondisi kebersihan lingkungan sekitar?',
        'options': {'kumuh': 'Kumuh', 'bersih': 'Bersih'},
        'explanation': {
            'kumuh': '🗑️ Banyak sampah, saluran air tersumbat, tempat gelap lembab - ideal tempat nyamuk bertelur',
            'bersih': '✨ Minim sampah, saluran lancar, rapi dan terawat - tidak mendukung perkembangbiakan nyamuk'
        }
    }
}