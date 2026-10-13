from pathlib import Path
from shutil import copy2
from copy import copy
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from openpyxl.drawing.image import Image
from PIL import Image as PILImage
from django.conf import settings
class HojaVidaService:
    def __init__(self, workspace):
        self.plantilla = settings.RESOURCES_ROOT / 'plantillas/HojaVida.xlsx'
        self.temp = Path(workspace)
    def generar(self, equipo):

        try:


            nombre = f"HV_{equipo.pk}.xlsx"

            destino = self.temp / nombre


            copy2(self.plantilla, destino)


            wb = load_workbook(destino)

            ws = wb.active


            datos = equipo.datos_hoja_vida
            mantenimientos = [{"tipo":m.tipo,"fecha":m.fecha,"empresa":m.empresa,"garantia":m.garantia,"responsable":m.responsable_legacy or m.tecnico.get_full_name() or m.tecnico.username,"especificaciones":m.especificaciones,"observaciones":m.observaciones + ("\n" + m.resumen_tiempo if m.lote else "") + ("\nREPUESTOS: " + m.repuestos if m.repuestos else "")} for m in equipo.mantenimiento_set.select_related('tecnico').order_by('fecha','id')]

            # ---------------- FOTO ----------------

            from .legacy_photo import FotoService

            foto_service = FotoService()

            ruta_foto = equipo.foto.path if equipo.foto else foto_service.obtener_foto(equipo.marca, equipo.modelo)

            if ruta_foto:

                foto = PILImage.open(ruta_foto)

                foto = foto.convert("RGB")

                ANCHO = 210
                ALTO = 195

                foto.thumbnail((ANCHO, ALTO))

                lienzo = PILImage.new(
                    "RGB",
                    (ANCHO, ALTO),
                    "white"
                )

                x = (ANCHO - foto.width) // 2
                y = (ALTO - foto.height) // 2

                lienzo.paste(
                    foto,
                    (x, y)
                )

                ruta_temp = self.temp / "foto_temp.jpg"

                lienzo.save(ruta_temp)

                img = Image(str(ruta_temp))

                img.width = ANCHO
                img.height = ALTO

                ws.add_image(img, "Z9")

            # ---------------- DATOS ----------------

            ws["H8"] = "COORDINACIÓN LABORATORIOS FACULTAD DE INGENIERÍA"
            ws["H9"] = str(equipo.laboratorio)
            ws["H10"] = self.nombre_equipo(equipo.descripcion)
            ws["H11"] = equipo.marca
            ws["H12"] = equipo.serial
            ws["H13"] = equipo.placa
            ws["H14"] = equipo.numero_interno

            ws["H15"] = datos.get("FECHA DE ADQUISICIÓN", "")
            ws["H16"] = datos.get("# DE FACTURA COMPRA", "")
            ws["H17"] = datos.get("FRECUENCIA DE MTTO", "")

            ws["S10"] = datos.get("PROVEEDOR", "")
            ws["S11"] = datos.get("# DE REMISIÓN COMPRA", "")
            ws["S12"] = datos.get("VALOR DE COMPRA", "")
            ws["S13"] = datos.get("PAÍS DE ORIGEN", "")

            ws["S14"] = datos.get(
                "REFERENCIA/MODELO",
                equipo.modelo
            )

            ws["S15"] = datos.get("TIEMPO DE GARANTÍA", "")
            ws["S16"] = datos.get("TIEMPO DE VIDA ÚTIL", "")
            ws["S17"] = datos.get("POTENCIA ELÉCTRICA", "")

            ws["F22"] = datos.get("¿Cuenta con manual?", "")
            ws["K22"] = datos.get("Accesorios", "")

            ws["C21"] = equipo.descripcion

            FILAS_BASE = 7

            if len(mantenimientos) > FILAS_BASE:

                filas_extra = len(mantenimientos) - FILAS_BASE

                ws.insert_rows(37, filas_extra)

                for i in range(filas_extra):

                    self.copiar_fila(
                        ws,
                        36,
                        37 + i
                    )

            from datetime import datetime, date

            fila = 30

            for i, mtto in enumerate(
                mantenimientos,
                start=1
            ):

                ws[f"C{fila}"] = i
                ws[f"D{fila}"] = mtto["tipo"]

                fecha = mtto["fecha"]

                if isinstance(fecha, (datetime, date)):
                    ws[f"F{fila}"] = fecha.strftime("%d/%m/%Y")
                else:
                    ws[f"F{fila}"] = str(fecha) if fecha is not None else "No registrada"

                ws[f"H{fila}"] = mtto["empresa"]
                ws[f"M{fila}"] = mtto["garantia"]
                ws[f"O{fila}"] = mtto["especificaciones"]
                ws[f"U{fila}"] = mtto["responsable"]
                ws[f"Z{fila}"] = mtto["observaciones"]

                for col in [
                    "D",
                    "F",
                    "H",
                    "M",
                    "O",
                    "U",
                    "Z"
                ]:
                    if isinstance(ws[f"{col}{fila}"].value, str):
                        ws[f"{col}{fila}"].data_type = 's'

                    ws[f"{col}{fila}"].alignment = Alignment(
                        horizontal="center",
                        vertical="center",
                        wrap_text=True
                    )

                texto = max(
                    len(str(mtto["especificaciones"])),
                    len(str(mtto["observaciones"]))
                )

                lineas = max(
                    1,
                    texto // 35 + 1
                )

                ws.row_dimensions[fila].height = lineas * 15

                fila += 1

            ws.row_breaks.brk = []
            ws.col_breaks.brk = []
            for address in ['H8','H9','H10','H11','H12','H13','H14','H15','H16','H17','S10','S11','S12','S13','S14','S15','S16','S17','F22','K22','C21']:
                if isinstance(ws[address].value, str):
                    ws[address].data_type = 's'

            wb.save(destino)

            wb.close()

            return destino

        except Exception:

            import traceback
            traceback.print_exc()

            return None

# ======================================================
# GENERAR PDF
# ======================================================

    def nombre_equipo(self, descripcion):

        if descripcion is None:
            return ""

        descripcion = str(descripcion).upper()

        nombres = [
            "OSCILOSCOPIO",
            "MULTÍMETRO",
            "FUENTE DC",
            "FUENTE",
            "GENERADOR DE SEÑALES",
            "GENERADOR",
            "LCR",
            "MEDIDOR LCR",
            "PINZA AMPERIMÉTRICA",
            "CÁMARA TÉRMICA",
            "IMPRESORA 3D",
            "ANALIZADOR",
            "MEGÓMETRO",
            "CALIBRADOR",
            "COMPUTADOR",
            "PORTÁTIL",
            "MONITOR"
        ]

        for nombre in nombres:

            if nombre in descripcion:
                return nombre

        return descripcion.title()


    # ======================================================
    # COPIAR FORMATO DE UNA FILA
    # ======================================================

    def copiar_fila(
        self,
        ws,
        fila_origen,
        fila_destino
    ):

        if fila_origen in ws.row_dimensions:

            ws.row_dimensions[fila_destino].height = (
                ws.row_dimensions[fila_origen].height
            )

        for columna in range(
            1,
            ws.max_column + 1
        ):

            origen = ws.cell(
                row=fila_origen,
                column=columna
            )

            destino = ws.cell(
                row=fila_destino,
                column=columna
            )

            if origen.has_style:

                destino.font = copy(origen.font)
                destino.fill = copy(origen.fill)
                destino.border = copy(origen.border)
                destino.alignment = copy(origen.alignment)
                destino.number_format = copy(origen.number_format)
                destino.protection = copy(origen.protection)

            if (
                isinstance(origen.value, str)
                and origen.value.startswith("=")
            ):

                destino.value = origen.value

        from openpyxl.utils import get_column_letter

        for rango in list(ws.merged_cells.ranges):

            if (
                rango.min_row == fila_origen
                and rango.max_row == fila_origen
            ):

                col_ini = get_column_letter(
                    rango.min_col
                )

                col_fin = get_column_letter(
                    rango.max_col
                )

                ws.merge_cells(
                    f"{col_ini}{fila_destino}:{col_fin}{fila_destino}"
                )

