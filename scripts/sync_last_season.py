"""Baixa uma temporada permitida no PC e envia os dados para a Oracle."""

import argparse
import gzip
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from nba_api.stats.endpoints import leaguegamelog


SUPPORTED_SEASONS = ("2025-26", "2026-27")
SEASON_TYPES = ("Regular Season", "Playoffs")
DEFAULT_API_URL = "https://138-2-244-252.sslip.io"
ROOT_DIR = Path(__file__).resolve().parents[1]
TOKEN_FILE = ROOT_DIR / ".sync-token"


def _primitive(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        return _primitive(value.item())
    return value


def _normalizar_linha(linha):
    def campo(nome):
        return _primitive(linha.get(nome))

    data = str(campo("GAME_DATE") or "")[:10]
    if not campo("GAME_ID") or not campo("PLAYER_ID") or not data:
        return None

    return {
        "game_id": str(campo("GAME_ID")),
        "game_date": data,
        "player_id": int(campo("PLAYER_ID")),
        "player_name": str(campo("PLAYER_NAME")),
        "team_id": campo("TEAM_ID"),
        "team_abbreviation": campo("TEAM_ABBREVIATION"),
        "matchup": campo("MATCHUP"),
        "wl": campo("WL"),
        "min": campo("MIN"),
        "pts": campo("PTS"),
        "reb": campo("REB"),
        "ast": campo("AST"),
        "stl": campo("STL"),
        "blk": campo("BLK"),
        "tov": campo("TOV"),
        "fgm": campo("FGM"),
        "fga": campo("FGA"),
        "fg3m": campo("FG3M"),
        "fg3a": campo("FG3A"),
        "ftm": campo("FTM"),
        "fta": campo("FTA"),
        "plus_minus": campo("PLUS_MINUS"),
    }


def baixar_temporada(temporada, timeout):
    tipos = {}
    for tipo in SEASON_TYPES:
        print(f"Consultando NBA: {temporada} — {tipo}...")
        resposta = leaguegamelog.LeagueGameLog(
            counter=0,
            direction="DESC",
            league_id="00",
            player_or_team_abbreviation="P",
            season=temporada,
            season_type_all_star=tipo,
            sorter="DATE",
            timeout=timeout,
        )
        conjuntos = resposta.get_normalized_dict()
        linhas = conjuntos.get("LeagueGameLog") or next(iter(conjuntos.values()), [])
        tipos[tipo] = [
            registro
            for linha in linhas
            if (registro := _normalizar_linha(linha)) is not None
        ]
        print(f"  {len(tipos[tipo])} atuações encontradas.")

    return {
        "season": temporada,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "season_types": tipos,
    }


def salvar_cache(dados, caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(caminho, "wt", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, separators=(",", ":"))
    print(f"Cache salvo em: {caminho}")


def carregar_cache(caminho, temporada):
    if not caminho.exists():
        raise SystemExit(f"Cache não encontrado: {caminho}")
    with gzip.open(caminho, "rt", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    if dados.get("season") != temporada:
        raise SystemExit(f"O cache não pertence à temporada {temporada}.")
    return dados


def obter_status(api_url, token, temporada, tipo_temporada=None):
    parametros = {"temporada": temporada}
    if tipo_temporada:
        parametros["tipo"] = tipo_temporada
    resposta = requests.get(
        f"{api_url.rstrip('/')}/sync/status",
        headers={"X-Sync-Token": token},
        params=parametros,
        timeout=30,
    )
    if not resposta.ok:
        raise SystemExit(
            f"Não foi possível consultar o status: HTTP {resposta.status_code} — "
            f"{resposta.text}"
        )
    return resposta.json()


def enviar_temporada(dados, api_url, token, batch_size, envio_completo=False):
    temporada = dados["season"]
    endpoint = f"{api_url.rstrip('/')}/sync/nba"
    headers = {"X-Sync-Token": token, "Content-Type": "application/json"}
    total = 0

    for tipo in SEASON_TYPES:
        registros = dados.get("season_types", {}).get(tipo, [])
        if not envio_completo:
            status_tipo = obter_status(api_url, token, temporada, tipo)
            ultima_data = status_tipo.get("ultima_partida")
            if ultima_data:
                registros = [
                    registro
                    for registro in registros
                    if registro["game_date"] >= ultima_data
                ]
                print(
                    f"Atualização incremental de {tipo} a partir de {ultima_data}."
                )

        print(f"Enviando {tipo}: {len(registros)} atuações...")
        if not registros:
            continue
        for inicio in range(0, len(registros), batch_size):
            lote = registros[inicio : inicio + batch_size]
            resposta = requests.post(
                endpoint,
                headers=headers,
                json={
                    "season": temporada,
                    "season_type": tipo,
                    "records": lote,
                },
                timeout=90,
            )
            if not resposta.ok:
                raise SystemExit(
                    f"Falha no lote {inicio // batch_size + 1}: "
                    f"HTTP {resposta.status_code} — {resposta.text}"
                )
            total += len(lote)
            print(f"  {min(inicio + len(lote), len(registros))}/{len(registros)}")

    status = obter_status(api_url, token, temporada)
    print(f"Sincronização concluída: {total} atuações enviadas.")
    print(f"Oracle: {status}")


def main():
    load_dotenv(ROOT_DIR / ".env")
    parser = argparse.ArgumentParser(
        description="Sincroniza uma temporada NBA permitida com a Oracle."
    )
    parser.add_argument(
        "--season",
        choices=SUPPORTED_SEASONS,
        default=os.getenv("NBA_SYNC_SEASON", "2025-26").strip(),
        help="temporada que será consultada e enviada",
    )
    parser.add_argument("--fetch-only", action="store_true", help="somente baixa e salva")
    parser.add_argument("--upload-only", action="store_true", help="somente envia o cache")
    parser.add_argument("--full", action="store_true", help="reenvia a temporada inteira")
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--batch-size", type=int, default=400)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()

    if args.fetch_only and args.upload_only:
        parser.error("use apenas uma das opções --fetch-only ou --upload-only")
    if not 1 <= args.batch_size <= 500:
        parser.error("--batch-size deve ficar entre 1 e 500")
    cache = args.cache or ROOT_DIR / "data" / f"nba-{args.season}.json.gz"

    if args.upload_only:
        dados = carregar_cache(cache, args.season)
    else:
        dados = baixar_temporada(args.season, args.timeout)
        salvar_cache(dados, cache)

    if args.fetch_only:
        return

    token = os.getenv("SYNC_TOKEN", "").strip()
    if not token and TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise SystemExit("Defina SYNC_TOKEN no .env ou crie o arquivo .sync-token.")
    api_url = os.getenv("SYNC_API_URL", DEFAULT_API_URL).strip()
    enviar_temporada(dados, api_url, token, args.batch_size, args.full)


if __name__ == "__main__":
    main()
