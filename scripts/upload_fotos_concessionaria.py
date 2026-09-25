"""Envia ao GCS as fotos locais das oito unidades da base concessionária."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import dotenv_values
from google.cloud import storage
from google.oauth2 import service_account

ROOT = Path(__file__).resolve().parents[1]
PREFIXO_GCS = "catalogo/concessionaria/"

PASTAS = {
    "Chevrolet Plus LTZ": "chevrolet-onix-plus-ltz-2023",
    "Hyundai Platinum Plus": "hyundai-hb20-platinum-plus-2023",
    "Volkswagen Comfortline": "volkswagen-t-cross-comfortline-2022",
    "Toyota XEI": "toyota-corolla-xei-2022",
    "Jeep T270 80 Anos": "jeep-compass-80-anos-2022",
    "Chevrolet Spirit_ LT": "chevrolet-celta-spirit-lt-2010",
    "Kia Motors 1.6 16V Mec.": "kia-cerato-1-6-manual-2011",
    "Renault Intense": "renault-kwid-intense-2020",
}


def _cliente():
    cfg = dotenv_values(ROOT / ".env")
    raw = (cfg.get("GCS_CREDENTIALS") or "").strip()
    if raw.startswith("{"):
        info = json.loads(raw)
        creds = service_account.Credentials.from_service_account_info(info)
        client = storage.Client(project=info.get("project_id"), credentials=creds)
    else:
        caminho = Path(raw)
        if not caminho.is_absolute():
            caminho = ROOT / caminho
        client = storage.Client.from_service_account_json(str(caminho))
    return client, (cfg.get("GCS_BUCKET") or "").strip()


def _numero(path: Path) -> int:
    achou = re.search(r"imgi_(\d+)_", path.name)
    return int(achou.group(1)) if achou else 9999


def main():
    client, bucket_nome = _cliente()
    if not bucket_nome:
        raise RuntimeError("GCS_BUCKET não configurado")
    bucket = client.bucket(bucket_nome)

    conjuntos = {}
    for pasta in ROOT.iterdir():
        if not pasta.is_dir():
            continue
        slug = next((s for inicio, s in PASTAS.items() if pasta.name.startswith(inicio)), None)
        if not slug:
            continue
        fotos = sorted(
            (p for p in pasta.iterdir() if p.suffix.lower() in {".webp", ".jpg", ".jpeg", ".png"}),
            key=_numero,
        )
        if fotos:
            conjuntos[slug] = (pasta, fotos)

    faltando = sorted(set(PASTAS.values()) - set(conjuntos))
    if faltando:
        raise RuntimeError(f"faltam pastas/fotos para: {', '.join(faltando)}")

    antigos = list(client.list_blobs(bucket, prefix=PREFIXO_GCS))
    if antigos:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda blob: blob.delete(), antigos))
        print(f"Objetos anteriores removidos: {len(antigos)}", flush=True)

    tarefas = []
    manifest = {}
    for slug, (pasta, fotos) in conjuntos.items():
        listing = next(iter(re.findall(r"\b\d{10}\b", pasta.name)), "")
        manifest[slug] = []
        for ordem, foto in enumerate(fotos, 1):
            extensao = foto.suffix.lower().lstrip(".")
            mime = {"webp": "image/webp", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}[extensao]
            objeto = f"{PREFIXO_GCS}{slug}/{ordem:02d}.{extensao}"
            manifest[slug].append({"gcs_objeto": objeto, "mime": mime})
            tarefas.append((foto, objeto, mime, listing, ordem))

    def _upload(tarefa):
        foto, objeto, mime, listing, ordem = tarefa
        blob = bucket.blob(objeto)
        blob.cache_control = "private, max-age=86400"
        blob.metadata = {
            "source": "user-provided OLX listing photos",
            "olx_listing_id": listing,
            "original_filename": foto.name,
            "catalog_order": str(ordem),
        }
        blob.upload_from_filename(str(foto), content_type=mime)
        return objeto

    with ThreadPoolExecutor(max_workers=8) as pool:
        enviados = list(pool.map(_upload, tarefas))

    for slug, fotos in manifest.items():
        print(f"{slug}: {len(fotos)} foto(s)", flush=True)
    print(f"TOTAL_ENVIADO={len(enviados)}", flush=True)
    print("MANIFEST_JSON=" + json.dumps(manifest, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
