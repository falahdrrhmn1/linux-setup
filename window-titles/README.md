# Judul jendela di alt+tab

Nama tiap jendela tampil di bawah thumbnail saat `Alt+Tab` (mode grid XFCE),
dan nama itu bisa diganti sendiri dengan `Alt+F2`.

- `Alt+F2` lalu isi nama -> jendela memakai nama itu.
- Kosongkan isian lalu OK -> kembali ke nama asli aplikasi.
- Nama bertahan walau aplikasi mengganti judulnya sendiri (tab baru Firefox,
  prompt terminal, dan sebagainya).
- Di terminal cukup ketik `nama TESIS` (atau `nama` untuk kembali).

## Kenapa perlu patch

xfwm4 menyimpan judul di `_NET_WM_NAME`, properti yang juga ditulis aplikasi.
Aplikasi selalu menang, jadi nama buatan sendiri cepat hilang. Patch di
`xfwm4-4.20-window-titles.patch`:

1. Menampilkan `c->name` di bawah setiap thumbnail grid alt+tab.
2. Memprioritaskan `_NET_WM_VISIBLE_NAME` (properti terpisah yang tidak dipakai
   aplikasi) di `getWindowName()`, sehingga rename tidak bisa ditimpa.

xfwm4 hasil build dipasang di `/usr/local/bin/xfwm4`; paket `xfwm4` dari apt
tidak disentuh. `/usr/local/bin` sudah ada di depan PATH, jadi sesi XFCE
langsung memakai versi ini setelah login.

## Pasang

```bash
./setup-window-titles.sh
```

Butuh `sudo` (dependensi build + pemasangan ke `/usr/local`). Diuji pada
Debian 13 / XFCE 4.20 / X11. Bila `deb-src` tidak aktif, script memakai tarball
rilis xfwm4 4.20.0.

## Lepas

```bash
./uninstall.sh
```

Lalu login ulang. Setelah itu `Alt+F2` kembali membuka Application Finder.
