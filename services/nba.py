import os
import re
import unicodedata
from datetime import date, datetime

from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players as nba_players


TIPOS_DE_TEMPORADA = {
    "Regular Season",
    "Playoffs",
    "Pre Season",
    "All Star",
}


class NBAServiceError(Exception):
    """Erro genérico ao consultar os dados da NBA."""


class JogadorNBAInexistente(NBAServiceError):
    """O nome cadastrado não corresponde a um jogador da NBA."""


class NBAIndisponivel(NBAServiceError):
    """A NBA não respondeu dentro do prazo ou retornou uma resposta inválida."""


def _nome_normalizado(nome):
    sem_acentos = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", nome)
        if not unicodedata.combining(caractere)
    )
    return " ".join(sem_acentos.casefold().split())


def temporada_atual(hoje=None):
    """Retorna a temporada mais recente no formato aceito pela NBA, como 2025-26."""
    hoje = hoje or date.today()
    ano_inicial = hoje.year if hoje.month >= 10 else hoje.year - 1
    return f"{ano_inicial}-{str(ano_inicial + 1)[-2:]}"


def validar_temporada(temporada):
    temporada = temporada or temporada_atual()
    if not re.fullmatch(r"\d{4}-\d{2}", temporada):
        raise ValueError("temporada deve usar o formato AAAA-AA, por exemplo 2025-26")

    ano_inicial = int(temporada[:4])
    ano_final = int(temporada[-2:])
    if ano_final != (ano_inicial + 1) % 100:
        raise ValueError("temporada inválida: o ano final deve ser o seguinte ao inicial")
    return temporada


def encontrar_jogador(nome):
    nome_procurado = _nome_normalizado(nome)
    encontrados = [
        jogador
        for jogador in nba_players.get_players()
        if _nome_normalizado(jogador["full_name"]) == nome_procurado
    ]

    if not encontrados:
        raise JogadorNBAInexistente(
            f"nenhum jogador da NBA encontrado com o nome '{nome}'"
        )

    encontrados.sort(key=lambda jogador: jogador.get("is_active", False), reverse=True)
    jogador = encontrados[0]
    return {
        "id": int(jogador["id"]),
        "nome": jogador["full_name"],
        "ativo": bool(jogador.get("is_active", False)),
    }


def _converter_data(data_texto):
    if not data_texto:
        return None
    for formato in ("%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(data_texto, formato).date()
        except ValueError:
            continue
    return None


def buscar_jogos(nome, temporada=None, tipo_temporada="Regular Season", nba_player_id=None):
    temporada = validar_temporada(temporada)
    if tipo_temporada not in TIPOS_DE_TEMPORADA:
        raise ValueError(
            "tipo_temporada deve ser Regular Season, Playoffs, Pre Season ou All Star"
        )

    jogador = (
        {"id": int(nba_player_id), "nome": nome, "ativo": None}
        if nba_player_id
        else encontrar_jogador(nome)
    )

    try:
        timeout = float(os.getenv("NBA_API_TIMEOUT", "20"))
        resposta = playergamelog.PlayerGameLog(
            player_id=jogador["id"],
            season=temporada,
            season_type_all_star=tipo_temporada,
            timeout=timeout,
        )
        registros = resposta.get_normalized_dict().get("PlayerGameLog", [])
    except Exception as erro:
        raise NBAIndisponivel("não foi possível consultar a NBA neste momento") from erro

    jogos = []
    for registro in registros:
        # O endpoint histórico usa "Game_ID", enquanto outras respostas da NBA
        # normalizam o mesmo campo como "GAME_ID".
        game_id = registro.get("GAME_ID") or registro.get("Game_ID")
        pontos = registro.get("PTS")
        if game_id is None or not isinstance(pontos, (int, float)):
            continue
        jogos.append(
            {
                "game_id": str(game_id),
                "data": _converter_data(registro.get("GAME_DATE")),
                "adversario": registro.get("MATCHUP"),
                "pontos": pontos,
            }
        )

    jogos.sort(key=lambda jogo: jogo["data"] or date.min, reverse=True)
    return {
        "jogador": jogador,
        "temporada": temporada,
        "tipo_temporada": tipo_temporada,
        "jogos": jogos,
    }
