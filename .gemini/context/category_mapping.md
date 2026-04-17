# Mapeo de Categorías Newznab

## Tabla Completa

| ID | Nombre | Subcategorías | Usado por |
|:--:|:-------|:--------------|:---------:|
| **2000** | Movies | 2010 Foreign, 2030 SD, 2040 HD, 2045 UHD, 2050 BluRay, 2080 WEB-DL | Radarr |
| **5000** | TV | 5010 WEB-DL, 5020 Foreign, 5030 SD, 5040 HD, 5045 UHD, 5070 Anime | Sonarr |
| **7000** | Books | 7020 Ebook, 7030 Comics, 7040 Magazines | Readarr |
| **8000** | Books (alt) | 8010 Ebook, 8020 Comics, 8030 Magazines | Readarr |

## Detalle de Subcategorías

### Libros (7000-8999)
- `7020`: Ebook
- `7030`: Comics
- `7040`: Magazines
- `8010`: Ebook (alt)
- `8020`: Comics (alt)
- `8030`: Magazines (alt)

### Películas (2000-2999)
- `2030`: SD (DVDRip, etc.)
- `2040`: HD (BluRay 1080p, etc.)
- `2045`: UHD (4K, etc.)
- `2080`: WEB-DL

### TV (5000-5999)
- `5030`: SD (HDTV, etc.)
- `5040`: HD (HDTV 720p/1080p)
- `5045`: UHD
- `5070`: Anime

## Notas Importantes

- **Readarr busca en 7000 Y 8000 simultáneamente** - el proxy debe declarar ambas
- Nuestro proxy mapea libros a: `[7000, 7020, 8000, 8010]`
- Rangos:
  - Libros: `7000-8999`
  - Películas: `2000-2999`
  - TV: `5000-5999`
  - Video (cualquiera): `2000-5999`
