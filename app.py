from flask import Flask, request, Response
import os
import requests
import re
import time

app = Flask(__name__)

TMDB_TOKEN = os.environ.get("TMDB_API_TOKEN")
TMDB_URL = "https://api.themoviedb.org/3/search/movie"

# -------------------------------------------------
# BUSCAR PÓSTER EN TMDB
# -------------------------------------------------

def buscar_poster(titulo):

    if not TMDB_TOKEN:
        return None

    # Limpiar título
    titulo = re.sub(r"\s+", " ", titulo).strip()

    # Quitar información que normalmente no pertenece al título
    titulo = re.sub(
        r"\b(19|20)\d{2}\b",
        "",
        titulo,
        flags=re.IGNORECASE
    )

    titulo = re.sub(
        r"\b(HD|FHD|4K|UHD|SD|FULL HD|LATINO|CASTELLANO|ESPAÑOL|SUB|SUBTITULADO)\b",
        "",
        titulo,
        flags=re.IGNORECASE
    )

    titulo = re.sub(r"[\[\]\(\)\{\}]", " ", titulo)
    titulo = re.sub(r"\s+", " ", titulo).strip()

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
            timeout=15
        )

        if r.status_code != 200:
            return None

        resultados = r.json().get("results", [])

        if not resultados:
            return None

        # Buscar el primer resultado que tenga póster
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

    try:

        respuesta = requests.get(
            m3u_url,
            timeout=60
        )

        if respuesta.status_code != 200:

            return Response(
                "No se pudo descargar el M3U. HTTP "
                + str(respuesta.status_code),
                status=500,
                mimetype="text/plain"
            )

        contenido = respuesta.text

    except Exception as e:

        return Response(
            "No se pudo descargar el M3U: " + str(e),
            status=500,
            mimetype="text/plain"
        )

    lineas = contenido.splitlines()

    salida = []

    peliculas_procesadas = 0
    posters_encontrados = 0

    for linea in lineas:

        # Solo procesar líneas EXTINF
        if linea.startswith("#EXTINF"):

            # Si ya tiene logo, no modificar
            if "tvg-logo=" not in linea:

                partes = linea.split(",", 1)

                if len(partes) == 2:

                    titulo = partes[1].strip()

                    peliculas_procesadas += 1

                    poster = buscar_poster(titulo)

                    if poster:

                        linea = linea.replace(
                            "#EXTINF:-1",
                            '#EXTINF:-1 tvg-logo="' + poster + '"',
                            1
                        )

                        posters_encontrados += 1

                    # Pequeña pausa para no saturar TMDB
                    time.sleep(0.05)

        salida.append(linea)

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
