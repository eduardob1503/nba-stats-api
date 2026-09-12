"""Baixa a temporada 2025-26 no PC e envia os dados para a Oracle."""

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


SEASON = "2025-26"
SEASON_TYPES = ("Regular Season", "Playoffs")
DEFAULT_API_URL = "https://138-2-244-252.sslip.io"
ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT_DIR / "data" / "nba-2025-26.json.gz"


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


def baixar_temporada(timeout):
    tipos = {}
    for tipo in SEASON_TYPES:
        print(f"Consultando NBA: {SEASON} — {tipo}...")
        resposta = leaguegamelog.LeagueGameLog(
            counter=0,
            direction="DESC",
            league_id="00",
            player_or_team_abbreviation="P",
            season=SEASON,
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
        "season": SEASON,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "season_types": tipos,
    }


def salvar_cache(dados, caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(caminho, "wt", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, separators=(",", ":"))
    print(f"Cache salvo em: {caminho}")


def carregar_cache(caminho):
    if not caminho.exists():
        raise SystemExit(f"Cache não encontrado: {caminho}")
    with gzip.open(caminho, "rt", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    if dados.get("season") != SEASON:
        raise SystemExit(f"O cache não pertence à temporada {SEASON}.")
    return dados


def enviar_temporada(dados, api_url, token, batch_size):
    endpoint = f"{api_url.rstrip('/')}/sync/nba"
    headers = {"X-Sync-Token": token, "Content-Type": "application/json"}
    total = 0

    for tipo in SEASON_TYPES:
        registros = dados.get("season_types", {}).get(tipo, [])
        print(f"Enviando {tipo}: {len(registros)} atuações...")
        for inicio in range(0, len(registros), batch_size):
            lote = registros[inicio : inicio + batch_size]
            resposta = requests.post(
                endpoint,
                headers=headers,
                json={
                    "season": SEASON,
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

    status = requests.get(
        f"{api_url.rstrip('/')}/sync/status",
        headers={"X-Sync-Token": token},
        timeout=30,
    )
    status.raise_for_status()
    print(f"Sincronização concluída: {total} atuações enviadas.")
    print(f"Oracle: {status.json()}")


def main():
    load_dotenv(ROOT_DIR / ".env")
    parser = argparse.ArgumentParser(
        description="Sincroniza somente a temporada NBA 2025-26 com a Oracle."
    )
    parser.add_argument("--fetch-only", action="store_true", help="somente baixa e salva")
    parser.add_argument("--upload-only", action="store_true", help="somente envia o cache")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--batch-size", type=int, default=400)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()

    if args.fetch_only and args.upload_only:
        parser.error("use apenas uma das opções --fetch-only ou --upload-only")
    if not 1 <= args.batch_size <= 500:
        parser.error("--batch-size deve ficar entre 1 e 500")

    if args.upload_only:
        dados = carregar_cache(args.cache)
    else:
        dados = baixar_temporada(args.timeout)
        salvar_cache(dados, args.cache)

    if args.fetch_only:
        return

    token = os.getenv("SYNC_TOKEN", "").strip()
    if not token:
        raise SystemExit("Defina SYNC_TOKEN no arquivo .env antes de enviar.")
    api_url = os.getenv("SYNC_API_URL", DEFAULT_API_URL).strip()
    enviar_temporada(dados, api_url, token, args.batch_size)


if __name__ == "__main__":
    main()
