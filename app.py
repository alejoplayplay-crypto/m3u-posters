from flask import Flask, request, Response
import os
import requests
import re
from urllib.parse import quote

app = Flask(__name__)

TMDB_TOKEN = os.environ.get("TMDB_API_TOKEN")

TMDB_URL = "https://api.themoviedb.org/3/search/movie"

@app.route("/")
def home():
    return "M3U Posters funcionando"

def buscar_poster(titulo):
    if not TMDB_TOKEN:
        return None

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

        poster = resultados[0].get("poster_path")

        if not poster:
            return None

        return "https://image.tmdb.org/t/p/w500" + poster

    except Exception:
        return None


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
        contenido = requests.get(
            m3u_url,
            timeout=30
        ).text

    except Exception as e:
        return Response(
            "No se pudo descargar el M3U: " + str(e),
            status=500,
            mimetype="text/plain"
        )

    lineas = contenido.splitlines()
    salida = []

    for linea in lineas:

        if linea.startswith("#EXTINF"):

            if "tvg-logo=" not in linea:

                partes = linea.split(",", 1)

                if len(partes) == 2:

                    titulo = partes[1].strip()

                    poster = buscar_poster(titulo)

                    if poster:
                        linea = linea.replace(
                            "#EXTINF:-1",
                            '#EXTINF:-1 tvg-logo="' + poster + '"',
                            1
                        )

        salida.append(linea)

    return Response(
        "\n".join(salida),
        mimetype="audio/x-mpegurl"
  )
