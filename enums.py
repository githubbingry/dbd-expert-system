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


# Question mapping for UI. The option values must stay aligned with rules.json.
QUESTIONS = {
    'genangan_air_terbuka': {
        'text': 'Apakah terdapat genangan air terbuka di sekitar area?',
        'options': {'ada': 'Ada', 'tidak_ada': 'Tidak Ada'},
        'explanation': {
            'ada': 'Ada minimal 1 titik air diam terbuka dalam radius sekitar 10 meter, misalnya ember, pot, ban bekas, talang, selokan tersumbat, atau cekungan dengan air setinggi minimal 1 cm.',
            'tidak_ada': 'Setelah mengecek radius sekitar 10 meter, tidak ada air diam terbuka setinggi minimal 1 cm, atau semua wadah air sudah tertutup, terbalik, atau kering.'
        }
    },
    'durasi_genangan_air': {
        'text': 'Berapa lama genangan air biasanya bertahan?',
        'options': {'<3 hari': '< 3 Hari', '3-6 hari': '3-6 Hari', '>=7 hari': '>= 7 Hari'},
        'explanation': {
            '<3 hari': 'Air biasanya hilang dalam 1 sampai 2 hari setelah hujan atau setelah wadah terisi.',
            '3-6 hari': 'Air masih terlihat selama 3 sampai 6 hari berturut-turut sejak hujan terakhir atau sejak wadah terisi.',
            '>=7 hari': 'Air bertahan 7 hari atau lebih, atau wadah jarang dikuras dalam satu minggu terakhir.'
        }
    },
    'keberadaan_jentik': {
        'text': 'Bagaimana keberadaan jentik nyamuk di genangan air?',
        'options': {'luas': 'Luas', 'jarang': 'Jarang', 'tidak_ada': 'Tidak Ada'},
        'explanation': {
            'luas': 'Saat memeriksa sampai 10 wadah atau titik genangan, jentik terlihat di 3 titik atau lebih, atau ada lebih dari 10 jentik pada satu wadah setelah diamati 30 detik.',
            'jarang': 'Jentik terlihat di 1 sampai 2 titik, atau jumlahnya 1 sampai 10 jentik pada satu wadah setelah diamati 30 detik.',
            'tidak_ada': 'Tidak terlihat jentik sama sekali setelah memeriksa wadah atau genangan yang ada selama sekitar 30 detik per titik.'
        }
    },
    'nyamuk_aedes': {
        'text': 'Seberapa banyak nyamuk Aedes aegypti yang terlihat?',
        'options': {'banyak': 'Banyak', 'jarang': 'Jarang', 'tidak_terlihat': 'Tidak Terlihat'},
        'explanation': {
            'banyak': 'Dalam pengamatan 10 menit di pagi atau sore hari, terlihat lebih dari 10 nyamuk bercorak hitam-putih di satu area rumah atau halaman.',
            'jarang': 'Dalam pengamatan 10 menit di pagi atau sore hari, terlihat 1 sampai 10 nyamuk bercorak hitam-putih.',
            'tidak_terlihat': 'Dalam pengamatan 10 menit, tidak terlihat nyamuk bercorak hitam-putih di area yang diperiksa.'
        }
    },
    'frekuensi_hujan': {
        'text': 'Seberapa sering hujan terjadi di daerah ini dalam satu bulan terakhir?',
        'options': {'sering': 'Sering', 'jarang': 'Jarang', 'tidak_pernah': 'Tidak Pernah'},
        'explanation': {
            'sering': 'Dalam 30 hari terakhir, hujan terjadi lebih dari 15 hari. Hitung dari catatan pribadi, ingatan harian, atau riwayat cuaca setempat.',
            'jarang': 'Dalam 30 hari terakhir, hujan terjadi 5 sampai 15 hari.',
            'tidak_pernah': 'Dalam 30 hari terakhir, hujan terjadi kurang dari 5 hari atau hampir tidak pernah hujan.'
        }
    },
    'intensitas_hujan': {
        'text': 'Bagaimana intensitas curah hujan yang terjadi?',
        'options': {'ringan': 'Ringan', 'sedang': 'Sedang', 'deras': 'Deras'},
        'explanation': {
            'ringan': 'Curah hujan sekitar 5 sampai 20 mm per hari, atau gerimis sampai hujan kecil yang biasanya tidak membuat genangan bertahan lama.',
            'sedang': 'Curah hujan sekitar 20 sampai 50 mm per hari, atau hujan cukup lama yang membuat genangan sementara di halaman, wadah, atau saluran.',
            'deras': 'Curah hujan lebih dari 50 mm per hari, atau hujan lebat yang membuat genangan luas, saluran meluap, atau air bertahan hingga esok hari.'
        }
    },
    'mobilitas_penduduk': {
        'text': 'Bagaimana tingkat mobilitas penduduk di area tersebut?',
        'options': {'tinggi': 'Tinggi', 'rendah': 'Rendah'},
        'explanation': {
            'tinggi': 'Diperkirakan lebih dari 100 orang keluar-masuk area per hari, misalnya dekat pasar, sekolah, terminal, tempat kerja, kos besar, atau jalan ramai.',
            'rendah': 'Diperkirakan 100 orang atau kurang keluar-masuk area per hari, misalnya gang permukiman kecil, komplek tertutup, atau lingkungan yang jarang dikunjungi orang luar.'
        }
    },
    'kepadatan_penduduk': {
        'text': 'Bagaimana kepadatan penduduk di area tersebut?',
        'options': {'padat': 'Padat', 'renggang': 'Renggang'},
        'explanation': {
            'padat': 'Dalam radius sekitar 100 meter terdapat lebih dari 30 rumah, atau jarak antar rumah umumnya kurang dari 5 meter.',
            'renggang': 'Dalam radius sekitar 100 meter terdapat 30 rumah atau kurang, atau jarak antar rumah umumnya 5 meter atau lebih.'
        }
    },
    'kondisi_lingkungan_sekitar': {
        'text': 'Bagaimana kondisi kebersihan lingkungan sekitar?',
        'options': {'kumuh': 'Kumuh', 'bersih': 'Bersih'},
        'explanation': {
            'kumuh': 'Dalam radius sekitar 10 meter ada 3 atau lebih titik sampah, barang bekas, wadah terbuka, saluran tersumbat, atau area lembap yang tidak dibersihkan lebih dari 7 hari.',
            'bersih': 'Dalam radius sekitar 10 meter ada 0 sampai 2 titik sampah atau wadah terbuka, saluran air lancar, dan area dibersihkan setidaknya seminggu sekali.'
        }
    }
}
