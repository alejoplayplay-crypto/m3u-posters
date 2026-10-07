from flask import Flask, request, Response
import os
import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

TMDB_TOKEN = os.environ.get("TMDB_API_TOKEN")
TMDB_URL = "https://api.themoviedb.org/3/search/movie"

# Cantidad de búsquedas simultáneas
MAX_WORKERS = 8


# -------------------------------------------------
# BUSCAR PÓSTER EN TMDB
# -------------------------------------------------

def buscar_poster(titulo):

    if not TMDB_TOKEN:
        return None

    titulo_original = titulo

    # Limpiar título
    titulo = re.sub(r"\s+", " ", titulo).strip()

    # Quitar año
    titulo = re.sub(
        r"\b(19|20)\d{2}\b",
        "",
        titulo,
        flags=re.IGNORECASE
    )

    # Quitar etiquetas habituales
    titulo = re.sub(
        r"\b(HD|FHD|4K|UHD|SD|FULL HD|LATINO|CASTELLANO|ESPAÑOL|SUB|SUBTITULADO)\b",
        "",
        titulo,
        flags=re.IGNORECASE
    )

    titulo = re.sub(r"[\[\]\(\)\{\}]", " ", titulo)
    titulo = re.sub(r"\s+", " ", titulo).strip()

    if not titulo:
        titulo = titulo_original

    headers = {
        "Authorization": f"Bearer {TMDB_TOKEN}",
        "accept": "application/json"
    }

    params = {
        "query": titulo,
        "language": "es-AR",
        "include_adult": "false"
    }

    try:

        r = requests.get(
            TMDB_URL,
            headers=headers,
            params=params,
            timeout=8
        )

        if r.status_code != 200:
            return None

        resultados = r.json().get("results", [])

        for pelicula in resultados:

            poster = pelicula.get("poster_path")

            if poster:

                return (
                    "https://image.tmdb.org/t/p/w500"
                    + poster
                )

        return None

    except Exception:

        return None


# -------------------------------------------------
# INICIO
# -------------------------------------------------

@app.route("/")
def home():

    return "M3U Posters funcionando"


# -------------------------------------------------
# PRUEBA TMDB
# -------------------------------------------------

@app.route("/test")
def test():

    poster = buscar_poster("Superman")

    if poster:
        return poster

    return (
        "TMDB no respondió o no encontró la película",
        500
    )


# -------------------------------------------------
# PROCESAR M3U
# -------------------------------------------------

@app.route("/procesar")
def procesar():

    m3u_url = request.args.get("url")

    if not m3u_url:

        return Response(
            "Falta el parametro url",
            status=400,
            mimetype="text/plain"
        )

    # ---------------------------------------------
    # DESCARGAR M3U
    # ---------------------------------------------

    try:

        respuesta = requests.get(
            m3u_url,
            timeout=30
        )

        respuesta.raise_for_status()

        contenido = respuesta.text

    except Exception as e:

        return Response(
            "No se pudo descargar el M3U: " + str(e),
            status=500,
            mimetype="text/plain"
        )

    lineas = contenido.splitlines()

    # ---------------------------------------------
    # ENCONTRAR PELÍCULAS
    # ---------------------------------------------

    trabajos = {}

    for i, linea in enumerate(lineas):

        if not linea.startswith("#EXTINF"):
            continue

        # Si ya tiene logo, no tocar
        if "tvg-logo=" in linea:
            continue

        partes = linea.split(",", 1)

        if len(partes) != 2:
            continue

        titulo = partes[1].strip()

        if not titulo:
            continue

        # Guardar títulos únicos.
        # Si una película aparece varias veces,
        # solo consultamos TMDB una vez.
        if titulo not in trabajos:
            trabajos[titulo] = []

        trabajos[titulo].append(i)

    # ---------------------------------------------
    # BUSCAR PÓSTERS EN PARALELO
    # ---------------------------------------------

    posters = {}

    titulos = list(trabajos.keys())

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futuros = {
            executor.submit(buscar_poster, titulo): titulo
            for titulo in titulos
        }

        for futuro in as_completed(futuros):

            titulo = futuros[futuro]

            try:

                poster = futuro.result()

                if poster:
                    posters[titulo] = poster

            except Exception:
                pass

    # ---------------------------------------------
    # CONSTRUIR M3U FINAL
    # ---------------------------------------------

    salida = list(lineas)

    peliculas_procesadas = 0
    posters_encontrados = 0

    for titulo, indices in trabajos.items():

        peliculas_procesadas += 1

        poster = posters.get(titulo)

        if not poster:
            continue

        for indice in indices:

            linea = salida[indice]

            # Agregar tvg-logo después de #EXTINF:-1
            nueva_linea = linea.replace(
                "#EXTINF:-1",
                '#EXTINF:-1 tvg-logo="' + poster + '"',
                1
            )

            salida[indice] = nueva_linea

            posters_encontrados += 1

    resultado = "\n".join(salida)

    return Response(
        resultado,
        mimetype="audio/x-mpegurl",
        headers={
            "Content-Disposition":
                "inline; filename=lista_con_posters.m3u",

            "X-Peliculas-Procesadas":
                str(peliculas_procesadas),

            "X-Posters-Encontrados":
                str(posters_encontrados)
        }
    )


# -------------------------------------------------
# EJECUTAR
# -------------------------------------------------

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 10000)
    )

    app.run(
        host="0.0.0.0",
        port=port
        )
