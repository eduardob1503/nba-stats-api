import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


MERCADOS_REAIS = ("pontos", "assistencias", "rebotes", "cestas_3", "pa", "ar", "par")
STATUS_FINALIZADOS = {"finished", "final", "ended", "completed", "cancelled", "canceled"}


def normalizar_texto(valor):
    texto = " ".join(str(valor or "").strip().split())
    texto = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caractere)
    )
    return texto.casefold()


def normalizar_nome_jogador(nome):
    original = " ".join(str(nome or "").strip().split())
    if "," in original:
        sobrenome, primeiro_nome = original.split(",", 1)
        original = f"{primeiro_nome.strip()} {sobrenome.strip()}"
    return normalizar_texto(original)


def _decimal(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return numero if numero.is_finite() else None


def _primeiro(dados, *chaves):
    if not isinstance(dados, dict):
        return None
    mapa = {str(chave).casefold(): valor for chave, valor in dados.items()}
    for chave in chaves:
        valor = mapa.get(chave.casefold())
        if valor not in (None, ""):
            return valor
    return None


def _nome_entidade(valor):
    if isinstance(valor, dict):
        return _primeiro(valor, "name", "displayName", "fullName", "participantName")
    return valor


def _lista(payload, chaves):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for chave in chaves:
        valor = _primeiro(payload, chave)
        if isinstance(valor, list):
            return valor
        if isinstance(valor, dict):
            encontrada = _lista(valor, chaves)
            if encontrada:
                return encontrada
    for valor in payload.values():
        if isinstance(valor, dict):
            encontrada = _lista(valor, chaves)
            if encontrada:
                return encontrada
    return []


def identificar_mercado(item, sport_id=None):
    if not isinstance(item, dict):
        return None
    item_sport_id = _primeiro(item, "sportId", "sport_id")
    if sport_id is not None and item_sport_id not in (None, ""):
        try:
            if int(item_sport_id) != int(sport_id):
                return None
        except (TypeError, ValueError):
            return None

    player_prop = _primeiro(item, "playerProp", "player_prop", "isPlayerProp")
    if player_prop is False or str(player_prop).casefold() == "false":
        return None

    campos = [
        _primeiro(item, "marketName", "market_name", "name", "marketType", "market_type"),
        _primeiro(item, "description", "label"),
    ]
    texto = " ".join(normalizar_texto(valor) for valor in campos if valor)
    if not texto:
        return None
    texto = re.sub(r"[^a-z0-9+ ]+", " ", texto)
    texto = " ".join(texto.split())

    if re.search(r"\b(pra|points?\s*\+\s*rebounds?\s*\+\s*assists?|points? rebounds? assists?)\b", texto):
        return "par"
    if re.search(r"\b(points?\s*\+\s*assists?|points? assists?)\b", texto):
        return "pa"
    if re.search(r"\b(assists?\s*\+\s*rebounds?|assists? rebounds?)\b", texto):
        return "ar"
    if "points + rebounds" in texto or "point rebounds" in texto:
        return None
    if re.search(r"\b(three pointers?|threes?|3 pointers?|3pt made)\b", texto):
        return "cestas_3"
    prop_explicita = player_prop is True or str(player_prop).casefold() == "true"
    if (
        re.search(r"\bpoints?\b", texto)
        and not re.search(r"\b(assists?|rebounds?|three|threes?)\b", texto)
        and (prop_explicita or "player" in texto)
    ):
        return "pontos"
    if (
        re.search(r"\bassists?\b", texto)
        and not re.search(r"\b(points?|rebounds?)\b", texto)
        and (prop_explicita or "player" in texto)
    ):
        return "assistencias"
    if (
        re.search(r"\brebounds?\b", texto)
        and not re.search(r"\b(points?|assists?)\b", texto)
        and (prop_explicita or "player" in texto)
    ):
        return "rebotes"
    return None


def normalizar_catalogo_mercados(payload, sport_id):
    itens = _lista(payload, ("markets", "data", "results", "items"))
    catalogo = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        nome = _primeiro(item, "marketName", "market_name", "name")
        market_id = _primeiro(item, "id", "marketId", "market_id")
        if market_id is None and nome:
            market_id = "nome:" + hashlib.sha256(str(nome).encode("utf-8")).hexdigest()[:24]
        if market_id is None:
            continue
        catalogo.append({
            "provedor_market_id": str(market_id),
            "nome_provedor": str(nome) if nome is not None else None,
            "mercado": identificar_mercado(item, sport_id),
            "player_prop": _primeiro(item, "playerProp", "player_prop", "isPlayerProp"),
            "payload": item,
        })
    return catalogo


def _data_utc(valor):
    if isinstance(valor, datetime):
        data = valor
    elif valor:
        texto = str(valor).strip().replace("Z", "+00:00")
        try:
            data = datetime.fromisoformat(texto)
        except ValueError:
            return None
    else:
        return None
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return data.astimezone(timezone.utc)


def normalizar_fixtures(payload, sport_id, tournament_id):
    itens = _lista(payload, ("fixtures", "data", "results", "items"))
    fixtures = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        fixture_id = _primeiro(item, "id", "fixtureId", "fixture_id")
        inicio = _data_utc(
            _primeiro(item, "startTime", "start_time", "startsAt", "date", "start")
        )
        if fixture_id is None or inicio is None:
            continue
        casa = _nome_entidade(_primeiro(item, "home", "homeTeam", "home_team"))
        fora = _nome_entidade(_primeiro(item, "away", "awayTeam", "away_team"))
        participantes = _primeiro(item, "participants", "competitors")
        if isinstance(participantes, list) and len(participantes) >= 2:
            casa = casa or _nome_entidade(participantes[0])
            fora = fora or _nome_entidade(participantes[1])
        status = str(_primeiro(item, "status", "state") or "scheduled")
        tem_odds = _primeiro(item, "hasOdds", "has_odds", "oddsAvailable")
        fixtures.append({
            "provedor_fixture_id": str(fixture_id),
            "sport_id": int(sport_id),
            "tournament_id": int(tournament_id),
            "time_casa": str(casa) if casa else None,
            "time_fora": str(fora) if fora else None,
            "inicio_em": inicio,
            "status": status,
            "tem_odds": bool(tem_odds),
        })
    return fixtures


def fixture_elegivel(fixture, agora, fim_janela):
    return (
        fixture["inicio_em"] >= agora
        and fixture["inicio_em"] <= fim_janela
        and normalizar_texto(fixture.get("status")) not in STATUS_FINALIZADOS
    )


def _blocos_bookmaker(payload):
    encontrados = []

    def visitar(item):
        if isinstance(item, dict):
            nome = _nome_entidade(
                _primeiro(item, "bookmaker", "bookmakerName", "bookmaker_name", "name")
            )
            mercados = _primeiro(item, "markets", "odds", "betOffers")
            if nome and isinstance(mercados, list):
                encontrados.append((normalizar_texto(nome), mercados))
            else:
                for valor in item.values():
                    visitar(valor)
        elif isinstance(item, list):
            for valor in item:
                visitar(valor)

    visitar(payload)
    return encontrados


def _lado(item, identificador):
    texto = normalizar_texto(
        _primeiro(item, "side", "name", "label", "outcome", "type") or identificador
    )
    for lado in ("over", "under", "yes", "no"):
        if re.search(rf"\b{lado}\b", texto):
            return lado
    return None


def _linha(item, mercado, identificador):
    valor = _primeiro(item, "handicap", "line", "points", "total", "value")
    if valor is None:
        valor = _primeiro(mercado, "handicap", "line", "points", "total")
    numero = _decimal(valor)
    if numero is not None:
        return numero
    numeros = re.findall(r"(?<!\d)(\d+(?:[.,]\d+)?)(?!\d)", str(identificador or ""))
    return _decimal(numeros[-1].replace(",", ".")) if numeros else None


def _jogador(item, mercado, identificador):
    jogador = _primeiro(item, "player", "participant", "competitor")
    jogador_id = None
    nome = None
    if isinstance(jogador, dict):
        jogador_id = _primeiro(jogador, "id", "playerId", "participantId")
        nome = _nome_entidade(jogador)
    elif jogador:
        nome = jogador
    jogador_id = jogador_id or _primeiro(
        item, "playerId", "player_id", "participantId", "participant_id"
    ) or _primeiro(mercado, "playerId", "participantId")
    nome = nome or _primeiro(
        item, "playerName", "player_name", "participantName"
    ) or _primeiro(mercado, "playerName", "participantName")
    if not nome:
        texto = str(identificador or "")
        texto = re.sub(r"\b(over|under|yes|no)\b", " ", texto, flags=re.I)
        texto = re.sub(r"\d+(?:[.,]\d+)?", " ", texto)
        texto = " ".join(re.sub(r"[^\wÀ-ÿ'-]+", " ", texto).split())
        nome = texto or None
    return (str(jogador_id) if jogador_id is not None else None, str(nome) if nome else None)


def normalizar_odds(payload, bookmaker, catalogo=None, mercados_permitidos=None):
    catalogo = catalogo or {}
    mercados_permitidos = set(mercados_permitidos or MERCADOS_REAIS)
    props = []
    for nome_bookmaker, mercados in _blocos_bookmaker(payload):
        if nome_bookmaker != normalizar_texto(bookmaker):
            continue
        for market in mercados:
            if not isinstance(market, dict):
                continue
            market_id = _primeiro(market, "id", "marketId", "market_id")
            market_id = str(market_id) if market_id is not None else ""
            mercado = catalogo.get(market_id) or identificar_mercado(market)
            if mercado not in mercados_permitidos:
                continue
            outcomes = _lista(market, ("outcomes", "results", "selections", "prices"))
            for outcome in outcomes:
                if not isinstance(outcome, dict):
                    continue
                ativo = _primeiro(outcome, "active", "isActive", "enabled", "open")
                if ativo is False or str(ativo).casefold() == "false":
                    continue
                identificador = _primeiro(
                    outcome, "bookmakerOutcomeId", "outcomeId", "id", "key"
                )
                lado = _lado(outcome, identificador)
                if lado not in {"over", "under", "yes", "no"}:
                    continue
                odd = _decimal(_primeiro(outcome, "odds", "price", "decimal", "value"))
                linha = _linha(outcome, market, identificador)
                jogador_id, jogador_nome = _jogador(outcome, market, identificador)
                if odd is None or odd <= 1 or linha is None or linha < 0 or not jogador_nome:
                    continue
                atualizado = _data_utc(
                    _primeiro(outcome, "updatedAt", "updated_at", "lastUpdated")
                    or _primeiro(market, "updatedAt", "updated_at", "lastUpdated")
                )
                hash_payload = hashlib.sha256(
                    json.dumps(outcome, sort_keys=True, default=str).encode("utf-8")
                ).hexdigest()
                props.append({
                    "bookmaker": bookmaker.lower(),
                    "provedor_market_id": market_id or str(identificar_mercado(market)),
                    "mercado": mercado,
                    "provedor_player_id": jogador_id,
                    "jogador_nome_provedor": jogador_nome,
                    "nome_normalizado": normalizar_nome_jogador(jogador_nome),
                    "linha": linha,
                    "lado": lado,
                    "odd": odd,
                    "atualizada_em_provedor": atualizado,
                    "payload_hash": hash_payload,
                })
    return props
