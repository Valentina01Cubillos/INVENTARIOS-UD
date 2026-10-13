from pathlib import Path
from django.conf import settings


class FotoService:

    def __init__(self):

        self.base = settings.RESOURCES_ROOT

        self.carpeta_fotos = (
            self.base /
            "fotos"
        )

    # =====================================================

    def obtener_foto(self, marca, modelo):

        nombre = self.normalizar_nombre(
            marca,
            modelo
        )
        if not nombre:
            return None

        extensiones = [
            ".jpg",
            ".jpeg",
            ".png",
            ".webp"
        ]

        for ext in extensiones:

            ruta = self.carpeta_fotos / f"{nombre}{ext}"

            if ruta.exists():

                return ruta

        return None

    # =====================================================

    def normalizar_nombre(self, marca, modelo):

        marca = "" if marca is None else str(marca)
        modelo = "" if modelo is None else str(modelo)

        texto = f"{marca}_{modelo}"

        texto = texto.upper()

        reemplazos = [
            ("Á", "A"),
            ("É", "E"),
            ("Í", "I"),
            ("Ó", "O"),
            ("Ú", "U"),
            ("Ñ", "N"),
            ("/", "_"),
            ("\\", "_"),
            ("-", "_"),
            (" ", "_"),
            (".", "_"),
            (",", "_"),
            ("(", ""),
            (")", "")
        ]

        for viejo, nuevo in reemplazos:

            texto = texto.replace(viejo, nuevo)

        while "__" in texto:

            texto = texto.replace("__", "_")

        return texto.strip("_")
