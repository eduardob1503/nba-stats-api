import os
import re
import unicodedata
from datetime import date, datetime
from math import isfinite

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


def encontrar_jogador_por_id(nba_player_id):
    try:
        jogador = nba_players.find_player_by_id(int(nba_player_id))
    except (TypeError, ValueError):
        jogador = None

    if not jogador:
        raise JogadorNBAInexistente("jogador da NBA inexistente")

    return {
        "id": int(jogador["id"]),
        "nome": jogador["full_name"],
        "ativo": bool(jogador.get("is_active", False)),
    }


def buscar_jogadores_nba(busca, limite=25):
    """Pesquisa o catálogo completo da NBA, priorizando as melhores correspondências."""
    termo = _nome_normalizado(busca or "")
    if len(termo) < 2:
        return []

    termos = termo.split()
    resultados = []
    for jogador in nba_players.get_players():
        nome = jogador["full_name"]
        nome_normalizado = _nome_normalizado(nome)
        palavras = nome_normalizado.split()

        if not all(any(parte in palavra for palavra in palavras) for parte in termos):
            continue

        if nome_normalizado == termo:
            relevancia = 0
        elif nome_normalizado.startswith(termo):
            relevancia = 1
        elif all(any(palavra.startswith(parte) for palavra in palavras) for parte in termos):
            relevancia = 2
        else:
            relevancia = 3

        resultados.append(
            (
                relevancia,
                not bool(jogador.get("is_active", False)),
                len(nome_normalizado),
                nome_normalizado,
                {
                    "id": f"nba:{int(jogador['id'])}",
                    "nome": nome,
                    "nba_player_id": int(jogador["id"]),
                    "ativo": bool(jogador.get("is_active", False)),
                },
            )
        )

    resultados.sort(key=lambda item: item[:4])
    return [item[4] for item in resultados[:limite]]


def _converter_data(data_texto):
    if not data_texto:
        return None
    for formato in ("%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(data_texto, formato).date()
        except ValueError:
            continue
    return None


def _numero(valor, inteiro=False):
    if valor in (None, "") or isinstance(valor, bool):
        return None
    try:
        if isinstance(valor, str) and ":" in valor and not inteiro:
            minutos, segundos = valor.split(":", 1)
            numero = float(minutos) + float(segundos) / 60
        else:
            numero = float(valor)
    except (TypeError, ValueError):
        return None
    if not isfinite(numero):
        return None
    return int(numero) if inteiro else round(numero, 2)


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
        if game_id is None:
            continue
        jogos.append(
            {
                "game_id": str(game_id),
                "data": _converter_data(registro.get("GAME_DATE")),
                "adversario": registro.get("MATCHUP"),
                "resultado": registro.get("WL"),
                "minutos": _numero(registro.get("MIN")),
                "pontos": _numero(registro.get("PTS"), inteiro=True),
                "rebotes": _numero(registro.get("REB"), inteiro=True),
                "assistencias": _numero(registro.get("AST"), inteiro=True),
                "roubos": _numero(registro.get("STL"), inteiro=True),
                "tocos": _numero(registro.get("BLK"), inteiro=True),
                "turnovers": _numero(registro.get("TOV"), inteiro=True),
                "cestas_3": _numero(registro.get("FG3M"), inteiro=True),
                "tentativas_3": _numero(registro.get("FG3A"), inteiro=True),
                "plus_minus": _numero(registro.get("PLUS_MINUS")),
            }
        )

    jogos.sort(key=lambda jogo: jogo["data"] or date.min, reverse=True)
    return {
        "jogador": jogador,
        "temporada": temporada,
        "tipo_temporada": tipo_temporada,
        "jogos": jogos,
    }
